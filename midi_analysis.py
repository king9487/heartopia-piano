import json
from pathlib import Path

import mido

from midi_rule_engine import read_midi_notes
from midi_to_keyboard import DEFAULT_NOTE_MAP


PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
KEY_SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
}


MIDI_ANALYSIS_REPORT_NAME = "report.json"
ANALYSIS_FIELDS = (
    "Song Duration",
    "Tempo",
    "Detected Key",
    "Total Notes",
    "Raw Notes",
    "Clean Notes",
    "Piano Arranged Notes",
    "Final Notes",
    "Removed Notes",
    "Merged Notes",
    "Octave Shifted",
    "Bass Removed",
    "Harmony Simplified",
    "Melody Selected",
)


def midi_note_count(midi_path):
    midi_path = Path(midi_path) if midi_path else None
    if not midi_path or not midi_path.exists():
        return 0
    return len(read_midi_notes(midi_path))


def midi_duration_and_tempo(midi_path):
    midi_path = Path(midi_path)
    midi = mido.MidiFile(midi_path)
    tempo = 500000
    for track in midi.tracks:
        tempo_message = next(
            (message for message in track if message.type == "set_tempo"), None
        )
        if tempo_message is not None:
            tempo = tempo_message.tempo
            break
    return float(midi.length), float(mido.tempo2bpm(tempo))


def inspect_midi_file(midi_path):
    """Return source-file metadata without creating or changing any files."""
    midi_path = Path(midi_path)
    midi = mido.MidiFile(midi_path)
    tempo_message = next(
        (
            message
            for track in midi.tracks
            for message in track
            if message.type == "set_tempo"
        ),
        None,
    )
    note_numbers = [
        message.note
        for track in midi.tracks
        for message in track
        if message.type == "note_on" and message.velocity > 0
    ]

    detected_key = None
    if note_numbers:
        # Do not use the 37-key optimizer's detector here: source metadata must
        # also work when the imported performance contains out-of-range notes.
        root, mode = max(
            (
                (root, mode)
                for root in range(12)
                for mode in KEY_SCALES
            ),
            key=lambda candidate: sum(
                (note - candidate[0]) % 12 in KEY_SCALES[candidate[1]]
                for note in note_numbers
            ),
        )
        detected_key = f"{PITCH_CLASS_NAMES[root]} {mode}"

    try:
        duration = float(midi.length)
    except ValueError:
        # SMF type 2 stores independent sequences, so there is no merged mido
        # length. Present the longest sequence as the file duration.
        track_durations = []
        for track in midi.tracks:
            seconds = 0.0
            tempo = 500000
            for message in track:
                seconds += mido.tick2second(message.time, midi.ticks_per_beat, tempo)
                if message.type == "set_tempo":
                    tempo = message.tempo
            track_durations.append(seconds)
        duration = max(track_durations, default=0.0)

    return {
        "file_name": midi_path.name,
        "duration": duration,
        "bpm": (
            float(mido.tempo2bpm(tempo_message.tempo))
            if tempo_message is not None
            else None
        ),
        "key": detected_key,
        "ppq": int(midi.ticks_per_beat),
        "tracks": len(midi.tracks),
        "total_notes": len(note_numbers),
        "notes_inside_map": sum(note in DEFAULT_NOTE_MAP for note in note_numbers),
        "notes_outside_map": sum(note not in DEFAULT_NOTE_MAP for note in note_numbers),
    }


def build_midi_analysis_report(
    raw_midi,
    clean_midi,
    piano_arranged_midi,
    final_midi,
    detected_key,
    arrangement_statistics=None,
):
    arrangement_statistics = arrangement_statistics or {}
    duration, tempo = midi_duration_and_tempo(raw_midi)
    raw_notes = midi_note_count(raw_midi)
    return {
        "Song Duration": round(duration, 3),
        "Tempo": round(tempo, 2),
        "Detected Key": detected_key or "Unknown",
        "Total Notes": raw_notes,
        "Raw Notes": raw_notes,
        "Clean Notes": midi_note_count(clean_midi),
        "Piano Arranged Notes": midi_note_count(piano_arranged_midi),
        "Final Notes": midi_note_count(final_midi),
        "Removed Notes": int(arrangement_statistics.get("Removed Notes", 0)),
        "Merged Notes": int(arrangement_statistics.get("Merged Notes", 0)),
        "Octave Shifted": int(
            arrangement_statistics.get("Octave Shifted Notes", 0)
        ),
        "Bass Removed": int(arrangement_statistics.get("Bass Removed", 0)),
        "Harmony Simplified": int(
            arrangement_statistics.get("Harmony Simplified", 0)
        ),
        "Melody Selected": int(
            arrangement_statistics.get(
                "Melody Selected", arrangement_statistics.get("Melody Notes", 0)
            )
        ),
    }


def export_midi_analysis_report(report, output_path):
    output_path = Path(output_path)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return output_path


def load_midi_analysis_report(report_path):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return {field: payload.get(field, "--") for field in ANALYSIS_FIELDS}
