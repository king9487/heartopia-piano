import json
import math
import shutil
from pathlib import Path

from ai_settings import (
    PROVIDER_DISABLED,
    get_active_provider_settings,
    load_ai_settings,
    validate_ai_settings,
)
from ai_providers import create_provider
from ai_providers.base import normalize_removal_result
from keyboard_mapping import get_playable_note_constraints

from midi_rule_engine import (
    RuleNote, normalize_tempo_map, read_midi_notes, seconds_to_ticks,
    ticks_to_seconds, write_clean_midi,
)
from midi_piano_arranger import PIANO_ARRANGED_MIDI_NAME, arrange_piano_midi
from midi_to_keyboard import DEFAULT_NOTE_MAP


AI_OPTIMIZED_MIDI_NAME = "ai_optimized_37key.mid"
PITCH_CORRECTED_MIDI_NAME = "pitch_corrected_37key.mid"
FINAL_37KEY_MIDI_NAME = "final_37key.mid"
PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)
OPTIMIZER_NONE = "none"
OPTIMIZER_RULE = "rule"
OPTIMIZER_OPENAI = "openai"
OPTIMIZER_PIANO_COVER = "piano cover"
PIANO_COVER_MIDI_NAME = "piano_cover_37key.mid"
ARRANGEMENT_ORIGINAL = "original"
ARRANGEMENT_MELODY_ONLY = "melody_only"
ARRANGEMENT_PIANO_COVER = "piano_cover"
DEFAULT_DECISION_WINDOW_MS = 8000
DEFAULT_CONTEXT_BEFORE_MS = 2000
DEFAULT_CONTEXT_AFTER_MS = 2000
DEFAULT_MAX_AI_REMOVAL_RATIO = 0.15
DEFAULT_AI_OPTIMIZER_OPTIONS = {
    "mode": OPTIMIZER_RULE,
    "arrangement_style": ARRANGEMENT_PIANO_COVER,
    "chunk_ms": DEFAULT_DECISION_WINDOW_MS,
    "context_before_ms": DEFAULT_CONTEXT_BEFORE_MS,
    "context_after_ms": DEFAULT_CONTEXT_AFTER_MS,
    "max_ai_removal_ratio": DEFAULT_MAX_AI_REMOVAL_RATIO,
    "window_ms": 50,
    "max_notes_per_window": 2,
    "min_note_duration_ms": 35,
}
OPENAI_OPTIMIZER_PROMPT = """You are optimizing MIDI notes for a keyboard-controlled music game.

Input is a JSON array of note events.

Each note event contains exactly:
- id
- start_ms
- duration_ms
- note
- velocity
- decision

Task:
- Perform conservative cleanup of the MIDI.
- Preserve the original musical arrangement as much as possible.
- Preserve the recognizable melody.
- Preserve accompaniment, bass notes, chords, and useful harmony.
- Remove a note only when there is strong evidence that it is a transcription artifact, accidental noise, duplicate artifact, or clearly unstable false detection.
- The default decision is KEEP.
- When uncertain whether a note is intentional, KEEP it.
- Do not simplify the song merely to reduce note density.
- Do not remove accompaniment simply because the melody is more prominent.
- Repeated notes of the same pitch may be intentional and should normally be kept.
- Chords and simultaneous notes may be intentional and should normally be kept.
- Sudden pitch jumps may be musically intentional and should only be removed when there is strong evidence they are transcription errors.

IMPORTANT:
The default decision is KEEP.
Removal requires high confidence.
When uncertain, keep the note.

KEEP/REMOVE rules:
- This optimizer is KEEP/REMOVE only.
- Every input note has a temporary integer id unique to this optimization run.
- Decide only which existing note IDs should be removed.
- Do not add new notes.
- Do not modify notes.
- Do not invent IDs.
- Do not return IDs that are not present in the input.
- Notes not listed in removed_ids are retained unchanged.

Chunk context:
- Some input notes are provided only as musical context.
- Each note has a "decision" field.
- You may only remove notes where decision is true.
- Notes where decision is false are context only.
- Never include context-only IDs in removed_ids.
- Use context-only notes to understand melodic direction, harmony, repetition, and phrase continuity.

Output:
- Return exactly one JSON object.
- The root object must contain "removed_ids".
- "removed_ids" must be an array of integer IDs from the input.
- If no notes should be removed, return an empty array.
- You may include a short string field named "explanation".
- Do not return notes, removed_notes, retained IDs, or complete note objects.
- Do not invent IDs.
- Do not include Markdown, code fences, or text outside the JSON object."""

AI_OPTIMIZER_SUMMARY_LOG = Path("logs") / "last_ai_optimizer_summary.json"


def build_optimizer_prompt(allowed_notes):
    constraints = get_playable_note_constraints(allowed_notes)

    return (
        OPENAI_OPTIMIZER_PROMPT
        + "\n\nKeyboard constraints:\n"
        + f"- Current playable range: {constraints['min_note_name']} "
        + f"({constraints['min_note']}) to {constraints['max_note_name']} "
        + f"({constraints['max_note']}).\n"
        + "- Currently mapped MIDI notes: "
        + json.dumps(constraints["allowed_notes"])
        + ".\n"
        + "- Only notes present in the current Keyboard Mapping are playable.\n"
        + "- Unplayable notes are filtered deterministically before this request.\n"
        + "- Do not assume a fixed 37-key range.\n"
        + "- Treat the current Keyboard Mapping as the authoritative "
        + "playable-note configuration."
    )


def build_lightweight_ai_notes(notes, allowed_notes, decision_ids=None):
    """Return globally indexed AI payload and deterministic keyboard removals."""
    allowed_notes = set(allowed_notes)
    decision_ids = set(range(len(notes))) if decision_ids is None else set(decision_ids)
    lightweight = []
    pre_removed_ids = []
    for note_id, note in enumerate(notes):
        if int(note["note"]) not in allowed_notes:
            pre_removed_ids.append(note_id)
            continue
        lightweight.append(
            {
                "id": note_id,
                "start_ms": int(note["start_ms"]),
                "duration_ms": int(note["duration_ms"]),
                "note": int(note["note"]),
                "velocity": int(note["velocity"]),
                "decision": note_id in decision_ids,
            }
        )
    return lightweight, pre_removed_ids


def build_ai_chunk_windows(
    notes,
    decision_window_ms=DEFAULT_DECISION_WINDOW_MS,
    context_before_ms=DEFAULT_CONTEXT_BEFORE_MS,
    context_after_ms=DEFAULT_CONTEXT_AFTER_MS,
):
    """Build half-open decision windows with overlapping, context-only notes."""
    if not notes:
        return []
    decision_window_ms = max(1000, int(decision_window_ms))
    context_before_ms = max(0, int(context_before_ms))
    context_after_ms = max(0, int(context_after_ms))
    indexed = sorted(
        enumerate(notes), key=lambda item: (int(item[1]["start_ms"]), item[0])
    )
    song_end_ms = max(
        int(note["start_ms"]) + int(note["duration_ms"]) for note in notes
    )
    owner_indexes = sorted(
        {int(note["start_ms"]) // decision_window_ms for _, note in indexed}
    )
    windows = []
    for owner_index in owner_indexes:
        decision_start_ms = owner_index * decision_window_ms
        decision_end_ms = min(decision_start_ms + decision_window_ms, song_end_ms)
        context_start_ms = max(0, decision_start_ms - context_before_ms)
        context_end_ms = min(song_end_ms, decision_end_ms + context_after_ms)
        note_ids = [
            note_id
            for note_id, note in indexed
            if context_start_ms <= int(note["start_ms"]) < context_end_ms
        ]
        decision_ids = [
            note_id
            for note_id, note in indexed
            if decision_start_ms <= int(note["start_ms"]) < decision_end_ms
        ]
        windows.append(
            {
                "decision_start_ms": decision_start_ms,
                "decision_end_ms": decision_end_ms,
                "context_start_ms": context_start_ms,
                "context_end_ms": context_end_ms,
                "note_ids": note_ids,
                "decision_ids": decision_ids,
            }
        )
    return windows


def apply_removed_note_ids(notes, removed_ids):
    """Retain original note objects in input order after validated removals."""
    valid_ids = set(range(len(notes)))
    normalized = set()
    for index, note_id in enumerate(removed_ids):
        if isinstance(note_id, bool) or not isinstance(note_id, int):
            raise ValueError(f"removed_ids[{index}] must be an integer.")
        if note_id not in valid_ids:
            raise ValueError(f"removed_ids[{index}] is not present in the input.")
        normalized.add(note_id)
    return [note for note_id, note in enumerate(notes) if note_id not in normalized]


def _ai_settings_from_options(options=None):
    options = options or {}
    return get_active_provider_settings(options.get("ai_settings", load_ai_settings()))


def test_ai_connection(settings=None):
    raw_settings = settings or load_ai_settings()
    active = get_active_provider_settings(raw_settings)
    valid, errors = validate_ai_settings(raw_settings)
    if active.get("provider") == PROVIDER_DISABLED:
        return False, "AI disabled"
    if not valid:
        return False, " ".join(errors) or "Invalid configuration"

    result = create_provider(active).test_connection()
    return result.success, result.message


def midi_notes_to_dicts(input_midi):
    notes = []
    for note in read_midi_notes(input_midi):
        notes.append(
            {
                "start_ms": int(round(note.start * 1000)),
                "duration_ms": max(1, int(round(note.duration * 1000))),
                "note": int(note.note),
                "velocity": int(note.velocity),
                "start_tick": note.start_tick,
                "end_tick": note.end_tick,
                "ppq": note.ppq,
                "tempo_map": [list(entry) for entry in note.tempo_map],
            }
        )
    return notes


def dicts_to_rule_notes(notes):
    rule_notes = []
    for note in notes:
        start = int(note["start_ms"]) / 1000
        duration = int(note["duration_ms"]) / 1000
        midi_note = int(note["note"])
        ppq = int(note.get("ppq", 480))
        tempo_map = normalize_tempo_map(note.get("tempo_map"))
        source_start_tick = note.get("start_tick")
        source_end_tick = note.get("end_tick")
        preserve_start = source_start_tick is not None and abs(
            ticks_to_seconds(source_start_tick, ppq, tempo_map) - start
        ) <= 0.0005
        preserve_end = preserve_start and source_end_tick is not None and abs(
            (
                ticks_to_seconds(source_end_tick, ppq, tempo_map)
                - ticks_to_seconds(source_start_tick, ppq, tempo_map)
            ) - duration
        ) <= 0.0005
        start_tick = (
            int(source_start_tick)
            if preserve_start
            else seconds_to_ticks(start, ppq, tempo_map)
        )
        end_tick = (
            int(source_end_tick)
            if preserve_end
            else seconds_to_ticks(start + duration, ppq, tempo_map)
        )
        rule_notes.append(
            RuleNote(
                start_tick=start_tick,
                end_tick=max(start_tick + 1, end_tick),
                ppq=ppq,
                tempo_map=tempo_map,
                original_note=midi_note,
                note=midi_note,
                velocity=int(note["velocity"]),
            )
        )
    return rule_notes


def split_notes_into_chunks(notes, chunk_ms=8000):
    chunk_ms = max(1000, int(chunk_ms))
    chunks = []
    current_chunk = []
    current_index = None

    for note in sorted(notes, key=lambda item: (item["start_ms"], item["note"])):
        chunk_index = note["start_ms"] // chunk_ms
        if current_index is None:
            current_index = chunk_index
        if chunk_index != current_index:
            chunks.append(current_chunk)
            current_chunk = []
            current_index = chunk_index
        current_chunk.append(note)

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def is_valid_note_dict(note, lowest, highest):
    try:
        start_ms = int(note["start_ms"])
        duration_ms = int(note["duration_ms"])
        midi_note = int(note["note"])
        velocity = int(note["velocity"])
    except (KeyError, TypeError, ValueError):
        return False

    return (
        start_ms >= 0
        and duration_ms > 0
        and lowest <= midi_note <= highest
        and velocity >= 1
        and velocity <= 127
    )


def validate_note_dicts(notes, note_map=None, allow_out_of_range=False, skip_invalid=False):
    note_map = note_map or DEFAULT_NOTE_MAP
    lowest = 0 if allow_out_of_range else min(note_map)
    highest = 127 if allow_out_of_range else max(note_map)
    if not isinstance(notes, list):
        raise ValueError("AI output must be a JSON list")

    validated = []
    for note in notes:
        if not isinstance(note, dict) or not is_valid_note_dict(note, lowest, highest):
            if skip_invalid:
                continue
            raise ValueError("AI output contains invalid notes")
        validated_note = {
                "start_ms": int(note["start_ms"]),
                "duration_ms": int(note["duration_ms"]),
                "note": int(note["note"]),
                "velocity": int(note["velocity"]),
            }
        for timing_key in (
            "start_tick", "end_tick", "ppq", "tempo_map", "timing_changes"
        ):
            if timing_key in note:
                validated_note[timing_key] = note[timing_key]
        validated.append(validated_note)

    return sorted(validated, key=lambda item: (item["start_ms"], item["note"]))


def remove_isolated_short_notes(notes, min_note_duration_ms=35):
    filtered = []
    for index, note in enumerate(notes):
        if note["duration_ms"] >= min_note_duration_ms:
            filtered.append(note)
            continue

        previous_note = notes[index - 1] if index > 0 else None
        next_note = notes[index + 1] if index + 1 < len(notes) else None
        previous_gap = (
            note["start_ms"] - (previous_note["start_ms"] + previous_note["duration_ms"])
            if previous_note
            else 999999
        )
        next_gap = next_note["start_ms"] - note["start_ms"] if next_note else 999999
        if previous_gap <= 120 or next_gap <= 120:
            filtered.append(note)

    return filtered


def rule_score(note, previous_pitch=None):
    score = note["velocity"] * 1.0 + note["duration_ms"] * 0.18
    if previous_pitch is None:
        return score

    pitch_delta = abs(note["note"] - previous_pitch)
    if pitch_delta <= 5:
        score += 10
    elif pitch_delta <= 12:
        score += 4
    else:
        score -= min(24, pitch_delta * 1.5)
    return score


def optimize_notes_with_rules(notes, options=None):
    options = {**DEFAULT_AI_OPTIMIZER_OPTIONS, **(options or {})}
    max_notes = max(1, min(int(options.get("max_notes_per_window") or 2), 3))
    window_ms = max(10, int(options.get("window_ms") or 50))
    min_note_duration_ms = max(1, int(options.get("min_note_duration_ms") or 35))
    note_map = options.get("note_map") or DEFAULT_NOTE_MAP
    notes = validate_note_dicts(notes, note_map=note_map)
    notes = remove_isolated_short_notes(notes, min_note_duration_ms=min_note_duration_ms)

    grouped = {}
    for note in notes:
        grouped.setdefault(note["start_ms"] // window_ms, []).append(note)

    selected = []
    previous_pitch = None
    for _, group in sorted(grouped.items()):
        ranked = sorted(
            group,
            key=lambda note: rule_score(note, previous_pitch=previous_pitch),
            reverse=True,
        )[:max_notes]
        ranked = sorted(ranked, key=lambda note: (note["start_ms"], note["note"]))
        selected.extend(ranked)
        if ranked:
            previous_pitch = ranked[-1]["note"]

    return validate_note_dicts(selected, note_map=note_map)


def _normalize_optimizer_mode(mode):
    return " ".join(str(mode or "").lower().replace("_", " ").replace("-", " ").split())


def _normalize_arrangement_style(style):
    normalized = "_".join(
        str(style or ARRANGEMENT_ORIGINAL)
        .lower()
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )
    if normalized in (
        ARRANGEMENT_ORIGINAL,
        ARRANGEMENT_MELODY_ONLY,
        ARRANGEMENT_PIANO_COVER,
    ):
        return normalized
    return ARRANGEMENT_ORIGINAL


def _onset_groups(notes, window_ms):
    window_seconds = max(1, int(window_ms)) / 1000
    groups = []
    for note in sorted(notes, key=lambda item: (item.start, item.original_note)):
        if not groups or note.start - groups[-1][0].start > window_seconds:
            groups.append([note])
        else:
            groups[-1].append(note)
    return groups


def _octave_candidates(pitch, lowest, highest):
    return [candidate for candidate in range(lowest, highest + 1) if candidate % 12 == pitch % 12]


def _melody_pitch(pitch, lowest, highest, allow_octave_up=True):
    candidates = _octave_candidates(pitch, lowest, highest)
    if not candidates:
        return None
    if lowest <= pitch <= highest:
        # Give a low melody one octave of separation from the left hand when possible.
        if allow_octave_up and pitch < lowest + 24 and pitch + 12 <= highest:
            return pitch + 12
        return pitch
    melody_floor = min(highest, lowest + 24)
    return min(candidates, key=lambda candidate: (abs(candidate - melody_floor), -candidate))


def _accompaniment_pitch(pitch, melody_pitch, lowest, highest, bass=False):
    candidates = [
        candidate
        for candidate in _octave_candidates(pitch, lowest, highest)
        if candidate <= melody_pitch - 3
    ]
    if not candidates:
        return None
    target = lowest + (7 if bass else 17)
    return min(candidates, key=lambda candidate: (abs(candidate - target), candidate))


def arrange_piano_cover_notes(notes, note_map=None, options=None):
    """Reduce a transcription to a melody-first, three-note piano arrangement."""
    options = options or {}
    note_map = note_map or options.get("note_map") or DEFAULT_NOTE_MAP
    lowest, highest = min(note_map), max(note_map)
    min_duration = max(0, int(options.get("min_note_duration_ms", 35))) / 1000
    velocity_threshold = max(0, int(options.get("velocity_threshold", 12)))
    window_ms = max(20, int(options.get("arrangement_window_ms", 60)))
    max_notes = max(2, min(int(options.get("max_notes_per_window", 3)), 3))
    repeat_seconds = max(0, int(options.get("bass_repeat_ms", 450))) / 1000
    allow_octave_up = bool(options.get("melody_octave_up", True))

    source = [
        note for note in notes
        if note.duration >= min_duration and note.velocity >= velocity_threshold
    ]
    groups = _onset_groups(source, window_ms)
    arranged = []
    active_melody = None
    last_bass_pitch = None
    last_bass_start = -float("inf")

    for group_index, group in enumerate(groups):
        group_start = min(note.start for note in group)
        next_start = (
            min(note.start for note in groups[group_index + 1])
            if group_index + 1 < len(groups)
            else None
        )
        top = max(group, key=lambda note: (note.original_note, note.duration, note.velocity))
        active_remaining = active_melody.end - group_start if active_melody else 0
        keep_sustained_melody = bool(
            active_melody
            and active_remaining > 0
            and top.original_note <= active_melody.original_note
            and top.duration < active_remaining
        )

        melody_source = None if keep_sustained_melody else top
        if melody_source is not None:
            pitch = _melody_pitch(
                melody_source.original_note, lowest, highest, allow_octave_up=allow_octave_up
            )
            if pitch is None:
                continue
            if active_melody and active_melody.end > group_start:
                active_melody.end = max(active_melody.start + 0.001, group_start)
            active_melody = RuleNote(
                start=melody_source.start,
                end=melody_source.end,
                ppq=melody_source.ppq,
                tempo_map=melody_source.tempo_map,
                original_note=melody_source.original_note,
                note=pitch,
                velocity=min(127, melody_source.velocity + 8),
                octave_shift=pitch - melody_source.original_note,
            )
            arranged.append(active_melody)

        if not active_melody or active_melody.end <= group_start:
            continue
        melody_pitch = active_melody.note
        accompaniment = [note for note in group if note is not melody_source]
        if not accompaniment:
            continue

        bass_source = min(
            accompaniment,
            key=lambda note: (note.original_note, -note.duration, -note.velocity),
        )
        bass_pitch = _accompaniment_pitch(
            bass_source.original_note, melody_pitch, lowest, highest, bass=True
        )
        chosen = []
        if (
            bass_pitch is not None
            and not (
                bass_pitch == last_bass_pitch
                and group_start - last_bass_start < repeat_seconds
            )
        ):
            chosen.append((bass_source, bass_pitch))
            last_bass_pitch, last_bass_start = bass_pitch, group_start

        harmony_candidates = []
        for note in accompaniment:
            if note is bass_source:
                continue
            pitch = _accompaniment_pitch(
                note.original_note, melody_pitch, lowest, highest, bass=False
            )
            if pitch is None or pitch == bass_pitch or pitch == melody_pitch:
                continue
            score = note.duration_ms * 0.22 + note.velocity - abs((melody_pitch - pitch) - 7)
            harmony_candidates.append((score, note, pitch))
        harmony_candidates.sort(key=lambda item: item[0], reverse=True)
        for _, note, pitch in harmony_candidates:
            if len(chosen) >= max_notes - 1:
                break
            if pitch not in {chosen_pitch for _, chosen_pitch in chosen}:
                chosen.append((note, pitch))

        for note, pitch in chosen:
            # Accompaniment yields at the next onset; the sustained melody does not.
            end = min(note.end, active_melody.end)
            if next_start is not None:
                end = min(end, next_start)
            if end <= group_start:
                continue
            arranged.append(
                RuleNote(
                    start=group_start,
                    end=end,
                    ppq=note.ppq,
                    tempo_map=note.tempo_map,
                    original_note=note.original_note,
                    note=pitch,
                    velocity=max(1, min(note.velocity, active_melody.velocity - 8)),
                    octave_shift=pitch - note.original_note,
                )
            )

    return sorted(arranged, key=lambda note: (note.start, -note.note))


def arrange_melody_only_notes(notes, note_map=None, options=None):
    """Extract the sustained highest line as a monophonic playable melody."""
    options = options or {}
    note_map = note_map or options.get("note_map") or DEFAULT_NOTE_MAP
    lowest, highest = min(note_map), max(note_map)
    min_duration = max(0, int(options.get("min_note_duration_ms", 35))) / 1000
    velocity_threshold = max(0, int(options.get("velocity_threshold", 12)))
    window_ms = max(20, int(options.get("arrangement_window_ms", 60)))
    allow_octave_up = bool(options.get("melody_octave_up", True))
    source = [
        note
        for note in notes
        if note.duration >= min_duration and note.velocity >= velocity_threshold
    ]

    melody = []
    active_melody = None
    for group in _onset_groups(source, window_ms):
        group_start = min(note.start for note in group)
        top = max(
            group, key=lambda note: (note.original_note, note.duration, note.velocity)
        )
        active_remaining = active_melody.end - group_start if active_melody else 0
        if (
            active_melody
            and active_remaining > 0
            and top.original_note <= active_melody.original_note
            and top.duration < active_remaining
        ):
            continue

        pitch = _melody_pitch(
            top.original_note, lowest, highest, allow_octave_up=allow_octave_up
        )
        if pitch is None:
            continue
        if active_melody and active_melody.end > group_start:
            active_melody.end = max(active_melody.start + 0.001, group_start)
        active_melody = RuleNote(
            start=top.start,
            end=top.end,
            ppq=top.ppq,
            tempo_map=top.tempo_map,
            original_note=top.original_note,
            note=pitch,
            velocity=min(127, top.velocity + 8),
            octave_shift=pitch - top.original_note,
        )
        melody.append(active_melody)

    return sorted(melody, key=lambda note: (note.start, -note.note))


def arrange_piano_cover_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = (
        Path(output_midi)
        if output_midi
        else input_midi.with_name(PIANO_COVER_MIDI_NAME)
    )
    notes = arrange_piano_cover_notes(
        read_midi_notes(input_midi),
        note_map=(options or {}).get("note_map"),
        options=options,
    )
    write_clean_midi(notes, output_midi, quantize_ms=(options or {}).get("final_quantize_ms", 10))
    return output_midi


def arrange_melody_only_midi(input_midi, output_midi, options=None):
    input_midi = Path(input_midi)
    output_midi = Path(output_midi)
    notes = arrange_melody_only_notes(read_midi_notes(input_midi), options=options)
    write_clean_midi(
        notes,
        output_midi,
        quantize_ms=(options or {}).get("final_quantize_ms", 10),
    )
    return output_midi


def extract_json_from_response(payload):
    if isinstance(payload, dict):
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]

        output = payload.get("output")
        if isinstance(output, list):
            text_parts = []
            for item in output:
                for content in item.get("content", []):
                    if content.get("type") in ("output_text", "text"):
                        text_parts.append(content.get("text", ""))
            if text_parts:
                return "".join(text_parts)

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            if isinstance(message.get("content"), str):
                return message["content"]

    raise ValueError("OpenAI response did not contain text")


def optimize_notes_with_ai(notes, options):
    options = {**DEFAULT_AI_OPTIMIZER_OPTIONS, **(options or {})}
    settings = _ai_settings_from_options(options)
    valid, errors = validate_ai_settings(settings)
    if settings.get("provider") == PROVIDER_DISABLED:
        raise RuntimeError("AI provider is disabled")
    if not valid:
        raise RuntimeError(" ".join(errors) or "Invalid AI configuration")
    if "playable_note_constraints" in options:
        constraints = options["playable_note_constraints"]
        if not constraints:
            raise ValueError(
                "The current Keyboard Mapping has no assigned playable notes."
            )
    else:
        constraints = get_playable_note_constraints(options.get("note_map") or ())
    all_ai_notes, keyboard_removed_ids = build_lightweight_ai_notes(
        notes, constraints["allowed_notes"]
    )
    ai_notes_by_id = {note["id"]: note for note in all_ai_notes}
    windows = build_ai_chunk_windows(
        notes,
        decision_window_ms=options["chunk_ms"],
        context_before_ms=options["context_before_ms"],
        context_after_ms=options["context_after_ms"],
    )
    provider = create_provider(settings)
    prompt = build_optimizer_prompt(constraints["allowed_notes"])
    progress_callback = options.get("progress_callback")
    max_ai_removal_ratio = min(1.0, max(0.0, float(options["max_ai_removal_ratio"])))
    gemini_removed_ids = []
    rejected_ai_removal_count = 0
    chunk_summaries = []
    for chunk_index, window in enumerate(windows, start=1):
        if callable(progress_callback):
            progress_callback(chunk_index, len(windows))
        decision_ids = set(window["decision_ids"]) & set(ai_notes_by_id)
        payload = []
        for note_id in window["note_ids"]:
            if note_id not in ai_notes_by_id:
                continue
            item = dict(ai_notes_by_id[note_id])
            item["decision"] = note_id in decision_ids
            payload.append(item)
        context_only_count = sum(not item["decision"] for item in payload)
        print(f"Chunk: {chunk_index}/{len(windows)}")
        print(
            "Decision window: "
            f"{window['decision_start_ms']}-{window['decision_end_ms']} ms"
        )
        print(
            "Context window: "
            f"{window['context_start_ms']}-{window['context_end_ms']} ms"
        )
        print(f"Decision note count: {len(decision_ids)}")
        print(f"Context-only note count: {context_only_count}")
        print(f"Total notes sent: {len(payload)}")
        requested_removed_ids = []
        if decision_ids:
            result = provider.optimize_midi(prompt, payload)
            requested_removed_ids, _explanation = normalize_removal_result(
                result, decision_ids
            )
        maximum_removals = math.floor(len(decision_ids) * max_ai_removal_ratio)
        removal_ratio = (
            len(requested_removed_ids) / len(decision_ids) if decision_ids else 0.0
        )
        safety_limit_exceeded = len(requested_removed_ids) > maximum_removals
        applied_removed_ids = [] if safety_limit_exceeded else requested_removed_ids
        print(f"Gemini requested removals: {len(requested_removed_ids)}")
        print(f"Gemini removed IDs: {requested_removed_ids}")
        print(f"AI removal ratio: {removal_ratio:.1%}")
        print(f"Maximum AI removal ratio: {max_ai_removal_ratio:.1%}")
        print(f"Safety limit exceeded: {'YES' if safety_limit_exceeded else 'NO'}")
        print(f"Applied AI removals: {len(applied_removed_ids)}")
        if safety_limit_exceeded:
            rejected_ai_removal_count += len(requested_removed_ids)
            print("AI removal safety limit exceeded.")
            print(f"Chunk: {chunk_index}/{len(windows)}")
            print(f"Decision notes: {len(decision_ids)}")
            print(f"Requested removals: {len(requested_removed_ids)}")
            print(f"Maximum allowed: {maximum_removals}")
            print(
                "Action: rejected AI removals; kept original notes for this chunk."
            )
        gemini_removed_ids.extend(applied_removed_ids)
        chunk_summaries.append(
            {
                **window,
                "requested_removed_ids": requested_removed_ids,
                "removed_ids": applied_removed_ids,
                "maximum_ai_removals": maximum_removals,
                "safety_limit_exceeded": safety_limit_exceeded,
            }
        )
    retained = apply_removed_note_ids(
        notes, [*keyboard_removed_ids, *gemini_removed_ids]
    )
    summary = {
        "provider": settings.get("provider"),
        "input_note_count": len(notes),
        "lightweight_ai_notes": all_ai_notes,
        "chunks": chunk_summaries,
        "keyboard_constraints": constraints,
        "max_ai_removal_ratio": max_ai_removal_ratio,
        "removed_ids": gemini_removed_ids,
        "keyboard_removed_count": len(keyboard_removed_ids),
        "ai_removed_count": len(set(gemini_removed_ids)),
        "rejected_ai_removal_count": rejected_ai_removal_count,
        "final_retained_note_count": len(retained),
    }
    overall_ai_removal_ratio = (
        len(set(gemini_removed_ids)) / len(notes) if notes else 0.0
    )
    print(f"Original notes: {len(notes)}")
    print(f"Removed by keyboard mapping: {len(keyboard_removed_ids)}")
    print(f"Removed by AI: {len(set(gemini_removed_ids))}")
    print(f"Rejected AI removals: {rejected_ai_removal_count}")
    print(f"Final notes: {len(retained)}")
    print(f"Overall AI removal percentage: {overall_ai_removal_ratio:.1%}")
    AI_OPTIMIZER_SUMMARY_LOG.parent.mkdir(parents=True, exist_ok=True)
    AI_OPTIMIZER_SUMMARY_LOG.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return retained


# Backward-compatible public name for integrations importing the old helper.
optimize_notes_with_openai = optimize_notes_with_ai


def optimize_chunk(notes, options):
    mode = _normalize_optimizer_mode(options.get("mode") or OPTIMIZER_RULE)
    if mode in (OPTIMIZER_OPENAI, "ai"):
        return optimize_notes_with_ai(notes, options)

    return optimize_notes_with_rules(notes, options)


def optimize_37key_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = Path(output_midi) if output_midi else input_midi.with_name(AI_OPTIMIZED_MIDI_NAME)
    options = {**DEFAULT_AI_OPTIMIZER_OPTIONS, **(options or {})}

    note_map = options.get("note_map") or DEFAULT_NOTE_MAP
    notes = validate_note_dicts(midi_notes_to_dicts(input_midi), note_map=note_map)
    mode = _normalize_optimizer_mode(options.get("mode") or OPTIMIZER_RULE)
    if mode in (OPTIMIZER_OPENAI, "ai"):
        optimized_notes = optimize_notes_with_ai(notes, options)
    else:
        optimized_notes = []
        chunks = split_notes_into_chunks(notes, chunk_ms=options["chunk_ms"])
        progress_callback = options.get("progress_callback")
        for chunk_index, chunk in enumerate(chunks, start=1):
            if callable(progress_callback):
                progress_callback(chunk_index, len(chunks))
            optimized_notes.extend(optimize_chunk(chunk, options))

    optimized_notes = validate_note_dicts(optimized_notes, note_map=note_map)
    write_clean_midi(dicts_to_rule_notes(optimized_notes), output_midi)
    return output_midi


def detect_song_key(notes, note_map=None, allow_out_of_range=False, skip_invalid=False):
    notes = validate_note_dicts(
        notes,
        note_map=note_map,
        allow_out_of_range=allow_out_of_range,
        skip_invalid=skip_invalid,
    )
    if not notes:
        return {
            "root": None,
            "mode": "unknown",
            "scale": set(),
            "name": "Unknown",
        }

    best_score = -1
    best_root = 0
    best_mode = "major"

    for root in range(12):
        for mode, intervals in (("major", MAJOR_SCALE), ("minor", MINOR_SCALE)):
            scale = {(root + interval) % 12 for interval in intervals}
            score = 0
            for note in notes:
                if note["note"] % 12 in scale:
                    score += note["duration_ms"] * max(1, note["velocity"])
            if score > best_score:
                best_score = score
                best_root = root
                best_mode = mode

    scale = {
        (best_root + interval) % 12
        for interval in (MAJOR_SCALE if best_mode == "major" else MINOR_SCALE)
    }
    return {
        "root": best_root,
        "mode": best_mode,
        "scale": scale,
        "name": f"{PITCH_CLASS_NAMES[best_root]} {best_mode}",
    }


def nearest_in_scale_candidates(note_number, scale, note_map=None, max_distance=2):
    note_map = note_map or DEFAULT_NOTE_MAP
    lowest = min(note_map)
    highest = max(note_map)
    candidates = []
    for distance in range(1, max_distance + 1):
        for direction in (-1, 1):
            candidate = note_number + (direction * distance)
            if lowest <= candidate <= highest and candidate % 12 in scale:
                candidates.append((candidate, distance, direction))
    return candidates


def is_jump_return(notes, index):
    if index <= 0 or index + 1 >= len(notes):
        return False

    previous_note = notes[index - 1]["note"]
    current_note = notes[index]["note"]
    next_note = notes[index + 1]["note"]
    current_start = notes[index]["start_ms"]
    next_start = notes[index + 1]["start_ms"]
    return (
        abs(current_note - previous_note) > 12
        and abs(next_note - previous_note) <= 3
        and next_start - current_start <= 350
    )


def choose_pitch_correction(note, previous_note, next_note, scale, note_map=None):
    candidates = nearest_in_scale_candidates(note["note"], scale, note_map=note_map)
    if not candidates:
        return None

    def movement_score(candidate):
        corrected_note, distance, direction = candidate
        score = distance * 10
        if previous_note is not None:
            score += abs(corrected_note - previous_note["note"])
        if next_note is not None:
            score += abs(next_note["note"] - corrected_note) * 0.5
        score += 0.2 if direction > 0 else 0
        return score

    return sorted(candidates, key=movement_score)[0][0]


def pitch_correct_notes(notes, options=None):
    options = options or {}
    note_map = options.get("note_map") or DEFAULT_NOTE_MAP
    min_short_ms = int(options.get("pitch_short_note_ms", 70))
    low_velocity = int(options.get("pitch_low_velocity", 35))
    notes = validate_note_dicts(notes, note_map=note_map)
    key_info = detect_song_key(notes, note_map=note_map)
    scale = key_info["scale"]

    corrected = []
    for index, note in enumerate(notes):
        previous_note = notes[index - 1] if index > 0 else None
        next_note = notes[index + 1] if index + 1 < len(notes) else None
        in_key = note["note"] % 12 in scale
        jump_return = is_jump_return(notes, index)

        if in_key and not jump_return:
            corrected.append(note)
            continue

        if note["duration_ms"] <= min_short_ms and not in_key:
            continue
        if note["velocity"] <= low_velocity and not in_key:
            continue

        corrected_note = choose_pitch_correction(
            note,
            previous_note,
            next_note,
            scale,
            note_map=note_map,
        )
        if corrected_note is None:
            continue

        fixed = dict(note)
        fixed["note"] = corrected_note
        corrected.append(fixed)

    return validate_note_dicts(corrected, note_map=note_map), key_info


def pitch_correct_37key_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = (
        Path(output_midi)
        if output_midi
        else input_midi.with_name(PITCH_CORRECTED_MIDI_NAME)
    )
    corrected_notes, key_info = pitch_correct_notes(midi_notes_to_dicts(input_midi), options=options)
    write_clean_midi(dicts_to_rule_notes(corrected_notes), output_midi)
    return output_midi, key_info


def detect_key_for_midi(input_midi, note_map=None):
    return detect_song_key(
        midi_notes_to_dicts(input_midi),
        note_map=note_map,
        allow_out_of_range=True,
        skip_invalid=True,
    )["name"]


def smooth_note_events(notes, options=None):
    """Quantize final timing and annotate every deliberate start-time change."""
    options = options or {}
    min_duration_ms = max(20, int(options.get("final_min_duration_ms", 45)))
    quantize_ms = max(1, int(options.get("final_quantize_ms", 10)))
    note_map = options.get("note_map") or DEFAULT_NOTE_MAP
    notes = validate_note_dicts(notes, note_map=note_map)

    smoothed = []
    last_end_by_note = {}
    for note in sorted(notes, key=lambda item: (item["start_ms"], item["note"])):
        original_start_ms = int(note["start_ms"])
        start_ms = int(round(original_start_ms / quantize_ms) * quantize_ms)
        duration_ms = max(min_duration_ms, int(round(note["duration_ms"] / quantize_ms) * quantize_ms))
        midi_note = note["note"]

        previous_end = last_end_by_note.get(midi_note)
        timing_changes = []
        if start_ms != original_start_ms:
            timing_changes.append(
                f"quantized start {original_start_ms}ms -> {start_ms}ms"
            )
        if previous_end is not None and start_ms < previous_end:
            before_overlap_shift = start_ms
            start_ms = previous_end
            timing_changes.append(
                f"same-pitch overlap shift {before_overlap_shift}ms -> {start_ms}ms"
            )

        end_ms = start_ms + duration_ms
        last_end_by_note[midi_note] = end_ms
        smoothed_note = dict(note)
        smoothed_note.update(
            start_ms=start_ms,
            duration_ms=duration_ms,
            note=midi_note,
            velocity=note["velocity"],
            timing_changes=timing_changes,
        )
        smoothed.append(smoothed_note)

    return validate_note_dicts(smoothed, note_map=note_map)


def smooth_37key_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = Path(output_midi) if output_midi else input_midi.with_name(FINAL_37KEY_MIDI_NAME)
    smoothed_notes = smooth_note_events(midi_notes_to_dicts(input_midi), options=options)
    write_clean_midi(dicts_to_rule_notes(smoothed_notes), output_midi)
    return output_midi


def post_process_37key_midi(clean_midi, options=None):
    clean_midi = Path(clean_midi)
    options = {**DEFAULT_AI_OPTIMIZER_OPTIONS, **(options or {})}
    mode = _normalize_optimizer_mode(options.get("mode"))
    arrangement_style = _normalize_arrangement_style(
        options.get("arrangement_style")
    )
    # Preserve compatibility with the former optimizer-mode UI.
    if mode == OPTIMIZER_PIANO_COVER:
        arrangement_style = ARRANGEMENT_PIANO_COVER

    arrangement_input = clean_midi
    arrangement_midi = None
    arrangement_report = None
    legacy_piano_cover_midi = None
    arrangement_name = "Original"
    if arrangement_style == ARRANGEMENT_PIANO_COVER:
        arrangement_midi = clean_midi.with_name(PIANO_ARRANGED_MIDI_NAME)
        arranged_result = arrange_piano_midi(
            clean_midi, output_midi=arrangement_midi, options=options
        )
        arrangement_report = arranged_result["report_path"]
        legacy_piano_cover_midi = clean_midi.with_name(PIANO_COVER_MIDI_NAME)
        shutil.copyfile(arrangement_midi, legacy_piano_cover_midi)
        arrangement_input = arrangement_midi
        arrangement_name = "Piano Cover"
    elif arrangement_style == ARRANGEMENT_MELODY_ONLY:
        arrangement_midi = clean_midi.with_name(PIANO_ARRANGED_MIDI_NAME)
        arrange_melody_only_midi(clean_midi, arrangement_midi, options=options)
        legacy_piano_cover_midi = clean_midi.with_name(PIANO_COVER_MIDI_NAME)
        shutil.copyfile(arrangement_midi, legacy_piano_cover_midi)
        arrangement_input = arrangement_midi
        arrangement_name = "Melody Only"
    elif options.get("force_arrangement_stage"):
        # Targeted rebuilds still need a concrete arrangement-stage artifact.
        # For the Original style this is an intentional pass-through, so Safe
        # can avoid arrangement transformations without leaving the stage stale.
        arrangement_midi = clean_midi.with_name(PIANO_ARRANGED_MIDI_NAME)
        shutil.copyfile(clean_midi, arrangement_midi)
        arrangement_input = arrangement_midi

    ai_midi = clean_midi.with_name(AI_OPTIMIZED_MIDI_NAME)
    pitch_corrected_midi = clean_midi.with_name(PITCH_CORRECTED_MIDI_NAME)
    final_midi = clean_midi.with_name(FINAL_37KEY_MIDI_NAME)

    optimize_37key_midi(arrangement_input, output_midi=ai_midi, options=options)
    _, key_info = pitch_correct_37key_midi(
        ai_midi, output_midi=pitch_corrected_midi, options=options
    )
    smooth_37key_midi(pitch_corrected_midi, output_midi=final_midi, options=options)
    return {
        "clean_midi": clean_midi,
        "piano_arranged_midi": arrangement_midi,
        "piano_cover_midi": legacy_piano_cover_midi,
        "arrangement_report": arrangement_report,
        "ai_optimized_midi": ai_midi,
        "pitch_corrected_midi": pitch_corrected_midi,
        "final_midi": final_midi,
        "detected_key": key_info["name"],
        "arrangement_mode": arrangement_name,
    }
