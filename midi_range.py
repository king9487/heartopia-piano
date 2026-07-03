from pathlib import Path

from midi_rule_engine import (
    RuleNote, read_midi_notes, seconds_to_ticks, write_clean_midi,
)


CHORUS_MIDI_NAME = "chorus_37key.mid"


def export_midi_range(input_midi, output_midi, start_sec, end_sec):
    """Export notes overlapping [start_sec, end_sec), shifted to start at zero."""
    start_sec = float(start_sec)
    end_sec = float(end_sec)
    if start_sec < 0:
        raise ValueError("start_sec must be greater than or equal to 0")
    if end_sec <= start_sec:
        raise ValueError("end_sec must be greater than start_sec")

    input_path = Path(input_midi)
    output_path = Path(output_midi)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("output_midi must be different from input_midi")

    source_notes = read_midi_notes(input_path)
    ranged_notes = []
    if not source_notes:
        return write_clean_midi(ranged_notes, output_path)
    context = source_notes[0]
    range_start_tick = seconds_to_ticks(
        start_sec, context.ppq, context.tempo_map
    )
    range_end_tick = seconds_to_ticks(end_sec, context.ppq, context.tempo_map)
    active_tempo = context.tempo_map[0][1]
    shifted_tempo_map = []
    for tick, tempo in context.tempo_map:
        if tick <= range_start_tick:
            active_tempo = tempo
        elif tick < range_end_tick:
            shifted_tempo_map.append((tick - range_start_tick, tempo))
    shifted_tempo_map.insert(0, (0, active_tempo))

    for note in source_notes:
        if note.end <= start_sec or note.start >= end_sec:
            continue

        trimmed_start_tick = max(note.start_tick, range_start_tick) - range_start_tick
        trimmed_end_tick = min(note.end_tick, range_end_tick) - range_start_tick
        if trimmed_end_tick <= trimmed_start_tick:
            continue

        ranged_notes.append(
            RuleNote(
                start_tick=trimmed_start_tick,
                end_tick=trimmed_end_tick,
                ppq=context.ppq,
                tempo_map=shifted_tempo_map,
                original_note=note.original_note,
                note=note.note,
                velocity=note.velocity,
                octave_shift=note.octave_shift,
            )
        )

    return write_clean_midi(ranged_notes, output_path)
