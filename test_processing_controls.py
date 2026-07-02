import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from converter import rebuild_midi_stages
from midi_rule_engine import RuleNote, write_clean_midi
from ui.presets import PROCESSING_PRESETS, apply_processing_preset


class Variable:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class PresetHarness:
    def __init__(self):
        for name in (
            "min_note_duration_var",
            "velocity_threshold_var",
            "max_simultaneous_var",
            "octave_fit_var",
            "melody_only_var",
            "melody_max_notes_var",
            "melody_window_var",
            "arrangement_style_var",
            "optimizer_mode_var",
        ):
            setattr(self, name, Variable())


def source_note():
    return RuleNote(0.0, 0.5, 60, 60, 80)


class ProcessingPresetTests(unittest.TestCase):
    def test_every_preset_changes_ui_values(self):
        app = PresetHarness()
        snapshots = []
        for name in ("Safe", "Balanced", "Aggressive", "Piano Cover"):
            values = apply_processing_preset(app, name)
            self.assertEqual(values, PROCESSING_PRESETS[name])
            self.assertEqual(
                app.arrangement_style_var.get(), values["arrangement_style"]
            )
            snapshots.append(tuple(values.items()))
        self.assertEqual(len(set(snapshots)), 4)

    def test_piano_cover_prioritizes_melody_and_reduces_accompaniment(self):
        values = PROCESSING_PRESETS["Piano Cover"]
        self.assertEqual(values["arrangement_style"], "piano_cover")
        self.assertLessEqual(values["max_notes_per_window"], 2)


class RebuildStageTests(unittest.TestCase):
    def setUp(self):
        self.options = {
            "mode": "rule",
            "arrangement_style": "piano_cover",
            "min_note_duration_ms": 35,
            "velocity_threshold": 12,
            "max_notes_per_window": 2,
        }

    def test_rebuild_clean_and_arranged_create_downstream_files_without_edit(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            raw = folder / "raw.mid"
            edited = folder / "edited_37key.mid"
            write_clean_midi([source_note()], raw)
            edited.write_bytes(b"user edit must survive")

            clean_result = rebuild_midi_stages(raw, "clean", self.options)
            self.assertIn("Clean", clean_result["regenerated_stages"])
            self.assertTrue(clean_result["clean_midi"].exists())
            self.assertTrue(clean_result["final_midi"].exists())

            arranged_result = rebuild_midi_stages(raw, "piano_arranged", self.options)
            self.assertEqual(arranged_result["regenerated_stages"][0], "Piano Arranged")
            self.assertTrue(arranged_result["piano_arranged_midi"].exists())
            self.assertTrue(arranged_result["final_midi"].exists())
            self.assertEqual(edited.read_bytes(), b"user edit must survive")

    def test_safe_rebuild_writes_pass_through_arrangement_stage(self):
        with TemporaryDirectory() as directory:
            raw = Path(directory) / "raw.mid"
            write_clean_midi([source_note()], raw)
            safe_options = {
                **self.options,
                "arrangement_style": "original",
                "min_note_duration_ms": 10,
                "velocity_threshold": 3,
            }
            result = rebuild_midi_stages(raw, "piano_arranged", safe_options)
            self.assertTrue(result["piano_arranged_midi"].exists())
            self.assertIn("Piano Arranged", result["regenerated_stages"])

    def test_rebuild_final_only_smooths_existing_pitch_stage(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            raw = folder / "raw.mid"
            edited = folder / "edited_37key.mid"
            write_clean_midi([source_note()], raw)
            edited.write_bytes(b"untouched")
            initial = rebuild_midi_stages(raw, "clean", self.options)

            with patch("converter.smooth_37key_midi", wraps=__import__(
                "midi_ai_optimizer"
            ).smooth_37key_midi) as smooth, patch(
                "converter.post_process_37key_midi"
            ) as full_process, patch(
                "converter.convert_to_37key_midi"
            ) as clean_process:
                result = rebuild_midi_stages(raw, "final", self.options)

            smooth.assert_called_once()
            full_process.assert_not_called()
            clean_process.assert_not_called()
            self.assertEqual(result["regenerated_stages"], ["Final"])
            self.assertEqual(result["final_midi"], initial["final_midi"])
            self.assertEqual(edited.read_bytes(), b"untouched")

    def test_rebuild_final_does_not_recreate_unneeded_clean_stage(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            raw = folder / "raw.mid"
            write_clean_midi([source_note()], raw)
            initial = rebuild_midi_stages(raw, "clean", self.options)
            initial["clean_midi"].unlink()

            with patch("converter.convert_to_37key_midi") as clean_process:
                result = rebuild_midi_stages(raw, "final", self.options)

            clean_process.assert_not_called()
            self.assertFalse(initial["clean_midi"].exists())
            self.assertEqual(result["regenerated_stages"], ["Final"])

    def test_edited_midi_is_rejected_as_a_raw_rebuild_source(self):
        with TemporaryDirectory() as directory:
            edited = Path(directory) / "edited_37key.mid"
            edited.write_bytes(b"untouched")
            with self.assertRaises(ValueError):
                rebuild_midi_stages(edited, "clean", self.options)
            self.assertEqual(edited.read_bytes(), b"untouched")


if __name__ == "__main__":
    unittest.main()
