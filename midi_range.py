from pathlib import Path

from midi_rule_engine import RuleNote, read_midi_notes, write_clean_midi


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

    ranged_notes = []
    for note in read_midi_notes(input_path):
        if note.end <= start_sec or note.start >= end_sec:
            continue

        trimmed_start = max(note.start, start_sec) - start_sec
        trimmed_end = min(note.end, end_sec) - start_sec
        if trimmed_end <= trimmed_start:
            continue

        ranged_notes.append(
            RuleNote(
                start=trimmed_start,
                end=trimmed_end,
                original_note=note.original_note,
                note=note.note,
                velocity=note.velocity,
                octave_shift=note.octave_shift,
            )
        )

    return write_clean_midi(ranged_notes, output_path)
