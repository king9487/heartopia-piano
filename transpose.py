from collections import defaultdict
from pathlib import Path

import mido


KEY_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
KEY_TO_PITCH_CLASS = {name: index for index, name in enumerate(KEY_NAMES)}
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
TRANSPOSED_MIDI_NAME = "transposed_37key.mid"


def normalize_key_name(key_name):
    if key_name is None:
        return None
    value = str(key_name).strip()
    aliases = {
        "Db": "C#",
        "D#": "Eb",
        "Gb": "F#",
        "G#": "Ab",
        "A#": "Bb",
    }
    value = aliases.get(value, value)
    if value not in KEY_TO_PITCH_CLASS:
        raise ValueError(f"Unsupported musical key: {key_name}")
    return value


def calculate_transpose_semitones(original_key, target_key):
    original = KEY_TO_PITCH_CLASS[normalize_key_name(original_key)]
    target = KEY_TO_PITCH_CLASS[normalize_key_name(target_key)]
    semitones = (target - original) % 12
    if semitones > 6:
        semitones -= 12
    return semitones


def detect_midi_key(input_midi):
    """Estimate a major key from duration and velocity weighted pitch classes."""
    midi = mido.MidiFile(input_midi)
    current_time = 0.0
    active_notes = defaultdict(list)
    pitch_weights = [0.0] * 12

    for message in midi:
        current_time += float(message.time)
        if message.is_meta or not hasattr(message, "channel") or message.channel == 9:
            continue
        if message.type == "note_on" and message.velocity > 0:
            active_notes[(message.channel, message.note)].append(
                (current_time, message.velocity)
            )
        elif message.type == "note_off" or (
            message.type == "note_on" and message.velocity == 0
        ):
            starts = active_notes.get((message.channel, message.note))
            if not starts:
                continue
            start_time, velocity = starts.pop(0)
            if not starts:
                active_notes.pop((message.channel, message.note), None)
            duration = max(0.001, current_time - start_time)
            pitch_weights[message.note % 12] += duration * max(1, velocity)

    if not any(pitch_weights):
        return None

    best_key = None
    best_score = -1.0
    for root, key_name in enumerate(KEY_NAMES):
        scale = {(root + interval) % 12 for interval in MAJOR_SCALE}
        score = sum(
            weight * (1.0 if pitch_class in scale else -0.35)
            for pitch_class, weight in enumerate(pitch_weights)
        )
        score += pitch_weights[root] * 0.15
        if score > best_score:
            best_key = key_name
            best_score = score
    return best_key


def transpose_midi_file(input_midi, output_midi, semitones):
    """Transpose melodic channels and preserve all MIDI timing and metadata."""
    input_path = Path(input_midi)
    output_path = Path(output_midi)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("output_midi must be different from input_midi")

    midi = mido.MidiFile(input_path)
    semitones = int(semitones)
    for track in midi.tracks:
        for message in track:
            if (
                message.type in ("note_on", "note_off")
                and hasattr(message, "channel")
                and message.channel != 9
            ):
                message.note = max(0, min(127, message.note + semitones))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(output_path)
    return output_path


def transpose_midi_to_key(
    input_midi,
    output_midi,
    target_key,
    original_key=None,
):
    detected_key = detect_midi_key(input_midi)
    source_key = normalize_key_name(original_key) if original_key else detected_key
    target_key = normalize_key_name(target_key)
    if source_key is None:
        return {
            "output_midi": None,
            "detected_key": detected_key,
            "original_key": None,
            "target_key": target_key,
            "semitones": 0,
        }

    semitones = calculate_transpose_semitones(source_key, target_key)
    output_path = transpose_midi_file(input_midi, output_midi, semitones)
    return {
        "output_midi": output_path,
        "detected_key": detected_key,
        "original_key": source_key,
        "target_key": target_key,
        "semitones": semitones,
    }
