from collections import defaultdict, deque
from pathlib import Path

from midi_rule_engine import read_midi_notes, write_clean_midi


EDITED_37KEY_MIDI_NAME = "edited_37key.mid"
RAPID_REPEAT_MS = 80
SHORT_DURATION_MS = 50
LOW_VELOCITY = 20
MAX_PITCH_OCCURRENCES_PER_SECOND = 8


def load_editor_notes(input_midi):
    return sorted(read_midi_notes(input_midi), key=lambda note: (note.start, note.note))


def find_suspicious_notes(
    notes,
    rapid_repeat_ms=RAPID_REPEAT_MS,
    short_duration_ms=SHORT_DURATION_MS,
    low_velocity=LOW_VELOCITY,
    max_pitch_occurrences=MAX_PITCH_OCCURRENCES_PER_SECOND,
):
    reasons = defaultdict(list)

    for index, note in enumerate(notes):
        if note.duration_ms < short_duration_ms:
            reasons[index].append("short duration")
        if note.velocity < low_velocity:
            reasons[index].append("low velocity")

    pitch_indices = defaultdict(list)
    for index, note in enumerate(notes):
        pitch_indices[note.note].append(index)

    for indices in pitch_indices.values():
        indices.sort(key=lambda index: notes[index].start)
        previous_index = None
        recent = deque()

        for index in indices:
            if previous_index is not None:
                repeat_gap_ms = (notes[index].start - notes[previous_index].start) * 1000
                if repeat_gap_ms < rapid_repeat_ms:
                    reasons[index].append("rapid same-note repeat")
            previous_index = index

            while recent and notes[index].start - notes[recent[0]].start > 1.0:
                recent.popleft()
            recent.append(index)
            if len(recent) > max_pitch_occurrences:
                for frequent_index in recent:
                    if "same pitch too frequent" not in reasons[frequent_index]:
                        reasons[frequent_index].append("same pitch too frequent")

    return {
        index: "; ".join(note_reasons)
        for index, note_reasons in reasons.items()
        if note_reasons
    }


def save_edited_midi(notes, output_midi):
    output_path = Path(output_midi)
    return write_clean_midi(notes, output_path)
