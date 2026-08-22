import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from ai_providers import create_provider
from ai_providers.base import ProviderError, normalize_removal_result
from ai_providers.gemini_provider import _parse_gemini_json
from keyboard_mapping import get_playable_note_constraints
from midi_ai_optimizer import (
    build_ai_chunk_windows,
    build_optimizer_prompt,
    optimize_notes_with_ai,
)


def settings(provider):
    return {"provider": provider, "api_key": "test-secret", "model": "test-model",
            "base_url": "http://local.test/v1", "timeout_seconds": 1, "max_retries": 0}


def note(note_id=0, pitch=60, **metadata):
    return {"id": note_id, "start_ms": note_id * 100, "duration_ms": 90,
            "note": pitch, "velocity": 90, **metadata}


class FakeResponse:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return json.dumps(self.value).encode()


class AiProviderTests(unittest.TestCase):
    def test_optimizer_prompt_defines_temporary_id_field(self):
        prompt = build_optimizer_prompt([60, 64])
        field_section = prompt.split("Each note event contains exactly:", 1)[1].split(
            "Task:", 1
        )[0]
        self.assertIn("- id", field_section)
        self.assertIn("- decision", field_section)
        self.assertIn("temporary integer id unique", prompt)
        self.assertIn("Never include context-only IDs in removed_ids", prompt)
        self.assertIn("The default decision is KEEP", prompt)
        self.assertIn("Removal requires high confidence", prompt)
        self.assertNotIn("Prefer melody over accompaniment", prompt)
        self.assertIn('"removed_ids" must be an array of integer IDs', prompt)

    def test_gemini_json_recovery_handles_fences_and_extra_text(self):
        self.assertEqual(_parse_gemini_json('```json\n{"removed_ids": []}\n```'), {"removed_ids": []})
        self.assertEqual(_parse_gemini_json('Result: {"removed_ids": [1]} trailing'), {"removed_ids": [1]})

    def test_provider_selection(self):
        self.assertEqual(create_provider(settings("openai")).provider_name, "openai")
        self.assertEqual(create_provider(settings("gemini")).provider_name, "gemini")

    def test_removal_result_deduplicates_and_validates_ids(self):
        removed, explanation = normalize_removal_result(
            {"removed_ids": [2, 2, 0], "explanation": "clean"}, {0, 1, 2}
        )
        self.assertEqual((removed, explanation), ([2, 0], "clean"))
        with self.assertRaisesRegex(ValueError, "not present"):
            normalize_removal_result({"removed_ids": [9]}, {0, 1})
        with self.assertRaisesRegex(ValueError, "obsolete"):
            normalize_removal_result({"notes": []}, set())
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            normalize_removal_result({"removed_ids": ["1"]}, {1})
        with self.assertRaisesRegex(ValueError, "removed_ids"):
            normalize_removal_result(
                {"id": 0, "start_ms": 0, "duration_ms": 90,
                 "note": 60, "velocity": 90},
                {0},
            )

    def test_openai_normalizes_removed_ids(self):
        response = {"output_text": '{"removed_ids":[1],"explanation":"noise"}',
                    "usage": {"input_tokens": 2, "output_tokens": 3}}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            result = create_provider(settings("openai")).optimize_midi("prompt", [note(0), note(1)])
        self.assertEqual(result["removed_ids"], [1])

    def test_gemini_request_uses_id_schema_and_lightweight_payload(self):
        configured = settings("gemini")
        configured["model"] = "gemini-3-flash-preview"
        response = {"candidates": [{"content": {"parts": [{"text":
            '{"removed_ids":[],"explanation":"keep"}'}]}}]}
        payload = [note(0)]
        with TemporaryDirectory() as directory, mock.patch(
            "ai_providers.gemini_provider.GEMINI_REQUEST_LOG", Path(directory) / "request.json"
        ), mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)) as urlopen:
            result = create_provider(configured).optimize_midi("prompt", payload)
            request_log = json.loads((Path(directory) / "request.json").read_text(encoding="utf-8"))
        body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        schema = body["generationConfig"]["responseJsonSchema"]
        self.assertEqual(schema["required"], ["removed_ids"])
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["removed_ids"]["items"]["type"], "integer")
        self.assertEqual(schema["properties"]["explanation"]["type"], "string")
        self.assertNotIn("notes", schema["properties"])
        self.assertEqual(request_log["lightweight_ai_notes"], payload)
        self.assertEqual(request_log["generation_config"], body["generationConfig"])
        self.assertEqual(request_log["request_body"], body)
        self.assertEqual(
            request_log["request_body"]["generationConfig"]["responseJsonSchema"],
            schema,
        )
        self.assertEqual(result["removed_ids"], [])

    def test_gemini_25_flash_connection_disables_thinking(self):
        configured = settings("gemini")
        configured["model"] = "gemini-2.5-flash"
        response = {"candidates": [{"content": {"parts": [{"text":
            '{"removed_ids":[],"explanation":"connected"}'}]}}]}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)) as urlopen:
            result = create_provider(configured).test_connection()
        body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertTrue(result.success)
        self.assertEqual(body["generationConfig"]["thinkingConfig"], {"thinkingBudget": 0})

    def test_gemini_rejects_old_note_object_response(self):
        response = {"candidates": [{"content": {"parts": [{"text":
            '{"notes":[],"removed_notes":[],"explanation":"old"}'}]}}]}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            with self.assertRaisesRegex(ProviderError, "obsolete"):
                create_provider(settings("gemini")).optimize_midi("prompt", [])

    def test_no_removed_ids_keeps_original_objects(self):
        notes = [note(0, start_tick=1), note(1, pitch=62, start_tick=20)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {"removed_ids": [], "explanation": "keep"}
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60, 62]))
        self.assertEqual(result, notes)
        self.assertIs(result[0], notes[0])
        self.assertIs(result[1], notes[1])

    def test_removed_id_preserves_original_metadata(self):
        metadata = {"start_tick": 101, "end_tick": 202, "ppq": 960,
                    "tempo_map": [[0, 500000], [100, 400000]], "custom": {"source": "untouched"}}
        notes = [note(0, **metadata), note(1, pitch=62)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {"removed_ids": [1], "explanation": "remove"}
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60, 62], 1.0))
        self.assertEqual(result, [notes[0]])
        self.assertIs(result[0], notes[0])
        self.assertEqual({key: result[0][key] for key in metadata}, metadata)
        payload = provider.optimize_midi.call_args.args[1]
        self.assertEqual(
            set(payload[0]),
            {"id", "start_ms", "duration_ms", "note", "velocity", "decision"},
        )

    def test_duplicate_removed_ids_are_safe(self):
        notes = [note(0), note(1, pitch=62), note(2, pitch=64)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [1, 1], "explanation": "duplicate"
        }
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60, 62, 64], 1.0))
        self.assertEqual(result, [notes[0], notes[2]])

    def test_invalid_removed_id_rejects_result_without_mutating_notes(self):
        notes = [note(0), note(1, pitch=62)]
        snapshot = json.loads(json.dumps(notes))
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [99], "explanation": "invalid"
        }
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            with self.assertRaisesRegex(ValueError, "not present"):
                optimize_notes_with_ai(notes, self._options([60, 62]))
        self.assertEqual(notes, snapshot)

    def test_mapping_gap_is_prefiltered_before_provider(self):
        notes = [note(0, 60), note(1, 61), note(2, 64)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {"removed_ids": [], "explanation": "keep"}
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60, 64]))
        payload = provider.optimize_midi.call_args.args[1]
        self.assertEqual([item["id"] for item in payload], [0, 2])
        self.assertEqual(result, [notes[0], notes[2]])

    def test_optimizer_summary_logs_filter_and_ai_counts(self):
        notes = [note(0, 60), note(1, 61), note(2, 64)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [2], "explanation": "remove"
        }
        with TemporaryDirectory() as directory, mock.patch(
            "midi_ai_optimizer.AI_OPTIMIZER_SUMMARY_LOG",
            Path(directory) / "summary.json",
        ), mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            optimize_notes_with_ai(notes, self._options([60, 64], 1.0))
            summary = json.loads(
                (Path(directory) / "summary.json").read_text(encoding="utf-8")
            )
        self.assertEqual(summary["input_note_count"], 3)
        self.assertEqual(summary["keyboard_removed_count"], 1)
        self.assertEqual(summary["ai_removed_count"], 1)
        self.assertEqual(summary["final_retained_note_count"], 1)
        self.assertEqual(summary["removed_ids"], [2])
        self.assertEqual(summary["keyboard_constraints"]["allowed_notes"], [60, 64])

    def test_optimizer_summary_leads_with_counts_and_pipeline_stages(self):
        notes = [note(index, start_ms=index * 100) for index in range(20)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [0, 1], "explanation": "cleanup"
        }
        messages = []
        options = self._options([60])
        options.update(
            {
                "log_callback": messages.append,
                "optimizer_pipeline_context": {
                    "original_note_count": 45,
                    "pipeline_counts": [
                        {
                            "stage": "arrange_piano_midi",
                            "input": 45,
                            "removed": 25,
                            "output": 20,
                            "reason": "test arrangement",
                        }
                    ],
                },
            }
        )
        with TemporaryDirectory() as directory, mock.patch(
            "midi_ai_optimizer.AI_OPTIMIZER_SUMMARY_LOG",
            Path(directory) / "summary.json",
        ), mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            optimize_notes_with_ai(notes, options)
            logged = json.loads(
                (Path(directory) / "summary.json").read_text(encoding="utf-8")
            )
        self.assertEqual(list(logged)[0:2], ["summary", "pipeline_counts"])
        self.assertEqual(
            logged["summary"],
            {
                "original_note_count": 45,
                "optimizer_input_note_count": 20,
                "pre_ai_removed_count": 25,
                "keyboard_removed_count": 0,
                "ai_requested_removal_count": 2,
                "ai_applied_removal_count": 2,
                "ai_rejected_removal_count": 0,
                "final_retained_note_count": 18,
                "ai_applied_removal_percentage": 10.0,
            },
        )
        self.assertEqual(
            [stage["stage"] for stage in logged["pipeline_counts"]],
            ["arrange_piano_midi", "keyboard_mapping_filter", "optimize_notes_with_ai"],
        )
        chunk = logged["chunks"][0]
        self.assertEqual(chunk["decision_note_count"], 20)
        self.assertEqual(chunk["context_only_note_count"], 0)
        self.assertEqual(chunk["requested_removal_count"], 2)
        self.assertEqual(chunk["requested_removal_percentage"], 10.0)
        self.assertEqual(chunk["applied_removed_ids"], [0, 1])
        self.assertEqual(chunk["applied_removal_count"], 2)
        self.assertTrue(
            any(
                message.startswith("AI Optimizer Summary\nOriginal notes: 45")
                for message in messages
            )
        )

    def test_next_request_uses_changed_mapping(self):
        prompts = []
        provider = mock.Mock()
        provider.optimize_midi.side_effect = lambda prompt, _payload: (
            prompts.append(prompt) or {"removed_ids": [], "explanation": "keep"}
        )
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            optimize_notes_with_ai([note(0)], self._options([60, 61]))
            optimize_notes_with_ai([note(0)], self._options([60, 64]))
        self.assertIn("Currently mapped MIDI notes: [60, 61]", prompts[0])
        self.assertIn("Currently mapped MIDI notes: [60, 64]", prompts[1])

    def test_empty_mapping_blocks_provider(self):
        with mock.patch("midi_ai_optimizer.create_provider") as provider:
            with self.assertRaisesRegex(ValueError, "no assigned playable notes"):
                optimize_notes_with_ai([], {"ai_settings": settings("gemini"), "note_map": (60,),
                                            "playable_note_constraints": {}})
        provider.assert_not_called()

    def test_middle_chunk_has_previous_and_future_context(self):
        notes = [
            note(0, start_ms=5900),
            note(1, start_ms=6100),
            note(2, start_ms=8000),
            note(3, start_ms=15999),
            note(4, start_ms=17000),
            note(5, start_ms=18100),
        ]
        windows = build_ai_chunk_windows(notes)
        middle = next(item for item in windows if item["decision_start_ms"] == 8000)
        self.assertEqual(
            (middle["decision_start_ms"], middle["decision_end_ms"]),
            (8000, 16000),
        )
        self.assertEqual(
            (middle["context_start_ms"], middle["context_end_ms"]),
            (6000, 18000),
        )
        self.assertEqual(middle["note_ids"], [1, 2, 3, 4])
        self.assertEqual(middle["decision_ids"], [2, 3])

    def test_first_and_final_chunk_context_are_clamped(self):
        notes = [note(0, start_ms=100), note(1, start_ms=16500, duration_ms=300)]
        windows = build_ai_chunk_windows(notes)
        self.assertEqual(windows[0]["context_start_ms"], 0)
        self.assertEqual(windows[-1]["decision_start_ms"], 16000)
        self.assertEqual(windows[-1]["decision_end_ms"], 16800)
        self.assertEqual(windows[-1]["context_end_ms"], 16800)

    def test_boundary_note_has_one_decision_owner_and_neighbor_context(self):
        notes = [note(0, start_ms=7500), note(1, start_ms=8000)]
        windows = build_ai_chunk_windows(notes)
        self.assertEqual(
            sum(1 in window["decision_ids"] for window in windows), 1
        )
        self.assertNotIn(1, windows[0]["decision_ids"])
        self.assertIn(1, windows[0]["note_ids"])
        self.assertIn(1, windows[1]["decision_ids"])
        self.assertIn(0, windows[1]["note_ids"])
        self.assertNotIn(0, windows[1]["decision_ids"])

    def test_context_id_returned_by_provider_is_rejected(self):
        notes = [note(0, start_ms=7500), note(1, start_ms=8500)]
        provider = mock.Mock()
        provider.optimize_midi.side_effect = [
            {"removed_ids": [], "explanation": "keep"},
            {"removed_ids": [0], "explanation": "invalid context removal"},
        ]
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            with self.assertRaisesRegex(ValueError, "not present"):
                optimize_notes_with_ai(notes, self._options([60]))
        second_payload = provider.optimize_midi.call_args_list[1].args[1]
        context_note = next(item for item in second_payload if item["id"] == 0)
        self.assertFalse(context_note["decision"])

    def test_global_ids_and_decisions_are_stable_across_requests(self):
        notes = [
            note(0, start_ms=7500, start_tick=75),
            note(1, start_ms=8500, pitch=62, start_tick=85),
            note(2, start_ms=16500, pitch=64, start_tick=165),
        ]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {"removed_ids": [], "explanation": "keep"}
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60, 62, 64]))
        payloads = [call.args[1] for call in provider.optimize_midi.call_args_list]
        id_zero_occurrences = [
            item for payload in payloads for item in payload if item["id"] == 0
        ]
        self.assertEqual([item["decision"] for item in id_zero_occurrences], [True, False])
        decision_ids = [
            item["id"] for payload in payloads for item in payload if item["decision"]
        ]
        self.assertEqual(sorted(decision_ids), [0, 1, 2])
        self.assertEqual(len(decision_ids), len(set(decision_ids)))
        self.assertEqual(result, notes)
        self.assertTrue(all(actual is original for actual, original in zip(result, notes)))

    def test_ai_removals_below_limit_are_applied(self):
        notes = [note(index, start_ms=index * 100) for index in range(20)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [0, 1], "explanation": "high confidence"
        }
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60]))
        self.assertEqual(result, notes[2:])

    def test_ai_removals_at_exact_limit_are_applied(self):
        notes = [note(index, start_ms=index * 100) for index in range(20)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [0, 1, 2], "explanation": "high confidence"
        }
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60]))
        self.assertEqual(result, notes[3:])

    def test_ai_removals_over_limit_are_rejected_for_whole_chunk(self):
        notes = [note(index, start_ms=index * 100) for index in range(20)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [0, 1, 2, 3], "explanation": "too aggressive"
        }
        with TemporaryDirectory() as directory, mock.patch(
            "midi_ai_optimizer.AI_OPTIMIZER_SUMMARY_LOG",
            Path(directory) / "summary.json",
        ), mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60]))
            summary = json.loads(
                (Path(directory) / "summary.json").read_text(encoding="utf-8")
            )
        self.assertEqual(result, notes)
        self.assertEqual(summary["ai_removed_count"], 0)
        self.assertEqual(summary["rejected_ai_removal_count"], 4)
        self.assertTrue(summary["chunks"][0]["safety_limit_exceeded"])

    def test_context_notes_do_not_inflate_removal_allowance(self):
        decision_notes = [note(index, start_ms=6000 + index * 20) for index in range(20)]
        context_notes = [
            note(index + 20, start_ms=8100 + index * 20) for index in range(20)
        ]
        notes = decision_notes + context_notes
        provider = mock.Mock()
        provider.optimize_midi.side_effect = [
            {"removed_ids": [0, 1, 2, 3], "explanation": "too many"},
            {"removed_ids": [], "explanation": "keep"},
        ]
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60]))
        self.assertEqual(result, notes)
        first_payload = provider.optimize_midi.call_args_list[0].args[1]
        self.assertEqual(sum(item["decision"] for item in first_payload), 20)
        self.assertEqual(sum(not item["decision"] for item in first_payload), 20)

    def test_keyboard_removals_do_not_reduce_ai_allowance(self):
        playable = [note(index, pitch=60, start_ms=index * 100) for index in range(20)]
        unplayable = [
            note(index + 20, pitch=61, start_ms=3000 + index * 100)
            for index in range(10)
        ]
        notes = playable + unplayable
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [0, 1, 2], "explanation": "at limit"
        }
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60]))
        self.assertEqual(result, playable[3:])

    def test_duplicate_ids_do_not_inflate_removal_ratio(self):
        notes = [note(index, start_ms=index * 100) for index in range(20)]
        provider = mock.Mock()
        provider.optimize_midi.return_value = {
            "removed_ids": [0, 0, 1, 1, 2, 2], "explanation": "duplicates"
        }
        with mock.patch("midi_ai_optimizer.create_provider", return_value=provider):
            result = optimize_notes_with_ai(notes, self._options([60]))
        self.assertEqual(result, notes[3:])

    @staticmethod
    def _options(allowed_notes, max_ai_removal_ratio=0.15):
        return {"ai_settings": settings("gemini"),
                "note_map": tuple(range(min(allowed_notes), max(allowed_notes) + 1)),
                "playable_note_constraints": get_playable_note_constraints(allowed_notes),
                "max_ai_removal_ratio": max_ai_removal_ratio}


if __name__ == "__main__":
    unittest.main()
