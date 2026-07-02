import json
from dataclasses import dataclass
from pathlib import Path

from midi_rule_engine import RuleNote, read_midi_notes, write_clean_midi
from midi_to_keyboard import DEFAULT_NOTE_MAP


PIANO_ARRANGED_MIDI_NAME = "piano_arranged_37key.mid"
PIANO_ARRANGEMENT_REPORT_NAME = "piano_arranged_37key_report.json"
DEFAULT_PIANO_ARRANGER_OPTIONS = {
    "arrangement_window_ms": 60,
    "max_notes_per_window": 3,
    "bass_repeat_ms": 450,
    "accompaniment_repeat_ms": 250,
    "merge_gap_ms": 80,
    "melody_octave_up": True,
}


@dataclass
class ArrangedEvent:
    note: RuleNote
    role: str


def _onset_groups(notes, window_ms):
    window_seconds = max(1, int(window_ms)) / 1000
    groups = []
    for note in sorted(notes, key=lambda item: (item.start, item.note)):
        if not groups or note.start - groups[-1][0].start > window_seconds:
            groups.append([note])
        else:
            groups[-1].append(note)
    return groups


def _melody_score(note, previous_pitch, lowest, last_bass_pitch):
    pitch_weight = (note.note - lowest) * 2.2
    duration_weight = min(note.duration_ms, 1400) * 0.065
    velocity_weight = note.velocity * 0.38
    continuity = 0.0
    if previous_pitch is not None:
        distance = abs(note.note - previous_pitch)
        continuity = max(-24.0, 30.0 - (distance * 2.5))
        if distance > 12:
            continuity -= (distance - 12) * 4.0
    short_penalty = 28.0 if note.duration_ms < 80 else 0.0
    repeated_bass_penalty = (
        30.0 if note.note <= lowest + 11 and note.note == last_bass_pitch else 0.0
    )
    return (
        pitch_weight
        + duration_weight
        + velocity_weight
        + continuity
        - short_penalty
        - repeated_bass_penalty
    )


def _lift_melody_pitch(note, previous_pitch, group, lowest, highest, enabled):
    pitch = note.note
    lifted = pitch + 12
    singing_floor = min(highest, lowest + 24)
    if not enabled or pitch >= singing_floor or lifted > highest:
        return pitch, False
    if lifted not in DEFAULT_NOTE_MAP:
        return pitch, False

    collision = any(other is not note and other.note == lifted for other in group)
    if collision:
        return pitch, False
    if previous_pitch is not None:
        original_distance = abs(pitch - previous_pitch)
        lifted_distance = abs(lifted - previous_pitch)
        if lifted_distance > original_distance and lifted_distance > 12:
            return pitch, False
    return lifted, True


def _fit_accompaniment_below(pitch, melody_pitch, lowest, highest):
    candidate = pitch
    while candidate > melody_pitch - 2 and candidate - 12 >= lowest:
        candidate -= 12
    if candidate < lowest or candidate > highest or candidate >= melody_pitch:
        return None
    return candidate if candidate in DEFAULT_NOTE_MAP else None


def _harmony_score(note, pitch, melody_pitch):
    interval = (melody_pitch - pitch) % 12
    consonance = 18 if interval in (0, 3, 4, 5, 7, 8, 9) else 0
    return note.duration_ms * 0.08 + note.velocity * 0.45 + consonance


def _merge_and_reduce_repeats(events, options):
    merge_gap = max(0, int(options["merge_gap_ms"])) / 1000
    accompaniment_repeat = max(0, int(options["accompaniment_repeat_ms"])) / 1000
    merged = 0
    ignored = 0
    result = []
    last_by_role_pitch = {}

    for event in sorted(events, key=lambda item: (item.note.start, -item.note.note)):
        key = (event.role, event.note.note)
        previous = last_by_role_pitch.get(key)
        if previous is not None:
            gap = event.note.start - previous.note.end
            repeat_distance = event.note.start - previous.note.start
            role_merge_gap = 0.05 if event.role == "melody" else merge_gap
            meaningful_melody_repeat = (
                event.role == "melody" and repeat_distance >= 0.18
            )
            if gap <= role_merge_gap and not meaningful_melody_repeat:
                previous.note.end = max(previous.note.end, event.note.end)
                previous.note.velocity = max(previous.note.velocity, event.note.velocity)
                merged += 1
                continue
            if event.role != "melody" and repeat_distance < accompaniment_repeat:
                ignored += 1
                continue
        result.append(event)
        last_by_role_pitch[key] = event
    return result, merged, ignored


def arrange_piano_notes(notes, note_map=None, options=None):
    options = {**DEFAULT_PIANO_ARRANGER_OPTIONS, **(options or {})}
    note_map = note_map or DEFAULT_NOTE_MAP
    lowest, highest = min(note_map), max(note_map)
    max_notes = max(2, min(int(options["max_notes_per_window"]), 3))
    bass_repeat = max(0, int(options["bass_repeat_ms"])) / 1000
    source = [note for note in notes if note.note in note_map]
    groups = _onset_groups(source, options["arrangement_window_ms"])

    selected = []
    active_melody = None
    previous_melody_pitch = None
    last_bass_pitch = None
    last_bass_start = -float("inf")
    octave_shifted = 0
    bass_removed = 0
    harmony_simplified = 0

    for index, group in enumerate(groups):
        start = min(note.start for note in group)
        next_start = (
            min(note.start for note in groups[index + 1])
            if index + 1 < len(groups)
            else None
        )
        ranked = sorted(
            group,
            key=lambda note: _melody_score(
                note, previous_melody_pitch, lowest, last_bass_pitch
            ),
            reverse=True,
        )
        candidate = ranked[0]
        active_remaining = active_melody.note.end - start if active_melody else 0
        keep_sustained = bool(
            active_melody
            and active_remaining > 0
            and candidate.note <= active_melody.note.original_note
            and candidate.duration < active_remaining
        )

        melody_source = None if keep_sustained else candidate
        if melody_source is not None:
            melody_pitch, shifted = _lift_melody_pitch(
                melody_source,
                previous_melody_pitch,
                group,
                lowest,
                highest,
                bool(options["melody_octave_up"]),
            )
            if active_melody and active_melody.note.end > start:
                active_melody.note.end = max(active_melody.note.start + 0.001, start)
            melody_note = RuleNote(
                start=melody_source.start,
                end=melody_source.end,
                original_note=melody_source.note,
                note=melody_pitch,
                velocity=min(127, melody_source.velocity + 8),
                octave_shift=melody_pitch - melody_source.note,
            )
            active_melody = ArrangedEvent(melody_note, "melody")
            selected.append(active_melody)
            previous_melody_pitch = melody_pitch
            octave_shifted += int(shifted)

        if not active_melody or active_melody.note.end <= start:
            continue
        melody_pitch = active_melody.note.note
        accompaniment = [note for note in group if note is not melody_source]
        if not accompaniment:
            continue

        bass_source = min(accompaniment, key=lambda note: (note.note, -note.duration))
        bass_pitch = _fit_accompaniment_below(
            bass_source.note, melody_pitch, lowest, highest
        )
        bass_is_repeat = bool(
            bass_pitch is not None
            and bass_pitch == last_bass_pitch
            and start - last_bass_start < bass_repeat
            and bass_source.duration_ms < 600
            and bass_source.velocity < 100
        )

        harmony_candidates = []
        for note in accompaniment:
            if note is bass_source:
                continue
            pitch = _fit_accompaniment_below(note.note, melody_pitch, lowest, highest)
            if pitch is None or pitch == melody_pitch or pitch == bass_pitch:
                continue
            harmony_candidates.append(
                (_harmony_score(note, pitch, melody_pitch), note, pitch)
            )
        harmony_candidates.sort(key=lambda item: item[0], reverse=True)

        chosen = []
        if harmony_candidates:
            _, harmony_source, harmony_pitch = harmony_candidates[0]
            chosen.append((harmony_source, harmony_pitch, "harmony"))
        if (
            len(chosen) < max_notes - 1
            and bass_pitch is not None
            and not bass_is_repeat
            and bass_pitch not in {pitch for _, pitch, _ in chosen}
        ):
            chosen.append((bass_source, bass_pitch, "bass"))
            last_bass_pitch = bass_pitch
            last_bass_start = start
        elif bass_pitch is not None:
            bass_removed += 1
        if len(chosen) < max_notes - 1:
            for _, harmony_source, harmony_pitch in harmony_candidates[1:]:
                if harmony_pitch not in {pitch for _, pitch, _ in chosen}:
                    chosen.append((harmony_source, harmony_pitch, "harmony"))
                if len(chosen) >= max_notes - 1:
                    break

        for source_note, pitch, role in chosen:
            end = min(source_note.end, active_melody.note.end)
            if next_start is not None:
                end = min(end, next_start)
            if end <= start:
                continue
            selected.append(
                ArrangedEvent(
                    RuleNote(
                        start=start,
                        end=end,
                        original_note=source_note.note,
                        note=pitch,
                        velocity=max(
                            1, min(source_note.velocity, active_melody.note.velocity - 8)
                        ),
                        octave_shift=pitch - source_note.note,
                    ),
                    role,
                )
            )
        harmony_source_count = max(0, len(accompaniment) - 1)
        harmony_kept = sum(1 for _, _, role in chosen if role == "harmony")
        harmony_simplified += max(0, harmony_source_count - harmony_kept)

    premerge_count = len(selected)
    arranged, merged, ignored = _merge_and_reduce_repeats(selected, options)
    role_counts = {
        role: sum(1 for event in arranged if event.role == role)
        for role in ("melody", "harmony", "bass")
    }
    statistics = {
        "Raw Notes": len(notes),
        "Melody Notes": role_counts["melody"],
        "Harmony Notes": role_counts["harmony"],
        "Bass Notes": role_counts["bass"],
        "Removed Notes": max(0, len(notes) - premerge_count) + ignored,
        "Merged Notes": merged,
        "Octave Shifted Notes": octave_shifted,
        "Bass Removed": bass_removed,
        "Harmony Simplified": harmony_simplified,
        "Melody Selected": role_counts["melody"],
        "Final Notes": len(arranged),
    }
    final_notes = sorted(
        (event.note for event in arranged), key=lambda note: (note.start, -note.note)
    )
    return final_notes, statistics


def arrange_piano_midi(input_midi, output_midi=None, options=None, report_path=None):
    input_midi = Path(input_midi)
    output_midi = (
        Path(output_midi)
        if output_midi
        else input_midi.with_name(PIANO_ARRANGED_MIDI_NAME)
    )
    report_path = (
        Path(report_path)
        if report_path
        else output_midi.with_name(PIANO_ARRANGEMENT_REPORT_NAME)
    )
    notes, statistics = arrange_piano_notes(
        read_midi_notes(input_midi), options=options
    )
    write_clean_midi(
        notes,
        output_midi,
        quantize_ms=(options or {}).get("final_quantize_ms", 10),
    )
    report_path.write_text(
        json.dumps(statistics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "output_midi": output_midi,
        "report_path": report_path,
        "statistics": statistics,
    }
