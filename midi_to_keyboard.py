import time
from dataclasses import dataclass

import keyboard
import mido


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
OCTAVE_FIT_OFF = "off"
OCTAVE_FIT_OCTAVE_SHIFT = "octave_shift"
OCTAVE_FIT_SHIFT = "shift"
OCTAVE_FIT_DROP = "drop"
OCTAVE_FIT_SMART = "smart"

SMART_MAX_RANGE_DISTANCE = 24
SMART_MIN_OUT_OF_RANGE_DURATION = 0.08
SMART_MIN_OUT_OF_RANGE_VELOCITY = 35
DEFAULT_37KEY_CLEAN_OPTIONS = {
    "min_note_duration_ms": 35,
    "velocity_threshold": 12,
    "max_simultaneous_notes": 3,
    "out_of_range_mode": OCTAVE_FIT_SMART,
    "prefer_melody": True,
    "quantize_ms": None,
}


DEFAULT_NOTE_MAP = {
    # Lower row in the game UI.
    36: ",",  # C2, Do
    37: "l",  # C#2 / Db2
    38: ".",  # D2, Re
    39: ";",  # D#2 / Eb2
    40: "/",  # E2, Mi
    41: "o",  # F2, Fa
    42: "0",  # F#2 / Gb2
    43: "p",  # G2, Sol
    44: "-",  # G#2 / Ab2
    45: "[",  # A2, La
    46: "=",  # A#2 / Bb2
    47: "]",  # B2, Si

    # Middle row in the game UI.
    48: "z",  # C3, Do
    49: "s",  # C#3 / Db3
    50: "x",  # D3, Re
    51: "d",  # D#3 / Eb3
    52: "c",  # E3, Mi
    53: "v",  # F3, Fa
    54: "g",  # F#3 / Gb3
    55: "b",  # G3, Sol
    56: "h",  # G#3 / Ab3
    57: "n",  # A3, La
    58: "j",  # A#3 / Bb3
    59: "m",  # B3, Si

    # Upper row in the game UI.
    60: "q",  # C4, Do, middle C
    61: "2",  # C#4 / Db4
    62: "w",  # D4, Re
    63: "3",  # D#4 / Eb4
    64: "e",  # E4, Mi
    65: "r",  # F4, Fa
    66: "5",  # F#4 / Gb4
    67: "t",  # G4, Sol
    68: "6",  # G#4 / Ab4
    69: "y",  # A4, La
    70: "7",  # A#4 / Bb4
    71: "u",  # B4, Si
    72: "i",  # C5, Do
}


def midi_note_name(note):
    octave = (note // 12) - 1
    name = NOTE_NAMES[note % 12]
    return f"{name}{octave}"


def is_note_off(message):
    return message.type == "note_off" or (
        message.type == "note_on" and message.velocity == 0
    )


@dataclass
class CleanNoteEvent:
    start: float
    end: float
    note: int
    key: str
    velocity: int

    @property
    def duration(self):
        return self.end - self.start


def playable_note_range(note_map):
    playable_notes = sorted(note_map)
    if not playable_notes:
        return None, None
    return playable_notes[0], playable_notes[-1]


def distance_from_range(note, lowest, highest):
    if note < lowest:
        return lowest - note
    if note > highest:
        return note - highest
    return 0


def octave_shift_note(note, note_map):
    lowest, highest = playable_note_range(note_map)
    if lowest is None:
        return None

    candidate = note
    while candidate < lowest:
        candidate += 12
    while candidate > highest:
        candidate -= 12

    if lowest <= candidate <= highest and candidate in note_map:
        return candidate
    return None


def fit_note_to_map(
    note,
    note_map,
    octave_fit_mode,
    duration=0.0,
    velocity=127,
    min_note_duration=0.0,
    velocity_threshold=0,
):
    if note in note_map:
        return note

    if octave_fit_mode in (OCTAVE_FIT_OFF, OCTAVE_FIT_DROP):
        return None

    lowest, highest = playable_note_range(note_map)
    if lowest is None:
        return None

    if octave_fit_mode in (OCTAVE_FIT_OCTAVE_SHIFT, OCTAVE_FIT_SHIFT):
        return octave_shift_note(note, note_map)

    if octave_fit_mode == OCTAVE_FIT_SMART:
        if distance_from_range(note, lowest, highest) > SMART_MAX_RANGE_DISTANCE:
            return None

        if duration < max(min_note_duration, SMART_MIN_OUT_OF_RANGE_DURATION):
            return None

        if velocity < max(velocity_threshold, SMART_MIN_OUT_OF_RANGE_VELOCITY):
            return None

        return octave_shift_note(note, note_map)

    return None


def extract_raw_note_events(midi_path, transpose=0, velocity_threshold=0):
    midi = mido.MidiFile(midi_path)
    current_time = 0.0
    active_notes = {}
    note_events = []

    for message in midi:
        current_time += message.time

        if message.type == "note_on" and message.velocity > 0:
            if message.velocity < velocity_threshold:
                continue
            note = message.note + transpose
            if note < 0 or note > 127:
                continue
            active_notes.setdefault(message.note, []).append(
                (current_time, note, message.velocity)
            )
        elif is_note_off(message):
            starts = active_notes.get(message.note)
            if not starts:
                continue
            start_time, note, velocity = starts.pop(0)
            if not starts:
                active_notes.pop(message.note, None)
            if current_time > start_time:
                note_events.append((start_time, current_time, note, velocity))

    return note_events


def merge_close_repeated_notes(note_events, merge_gap):
    if merge_gap <= 0:
        return note_events

    merged = []
    by_note = {}
    for event in sorted(note_events, key=lambda item: (item.note, item.start)):
        previous = by_note.get(event.note)
        if previous and event.start - previous.end <= merge_gap:
            previous.end = max(previous.end, event.end)
            previous.velocity = max(previous.velocity, event.velocity)
        else:
            clone = CleanNoteEvent(
                start=event.start,
                end=event.end,
                note=event.note,
                key=event.key,
                velocity=event.velocity,
            )
            by_note[event.note] = clone
            merged.append(clone)

    return sorted(merged, key=lambda event: (event.start, event.note))


def drop_close_raw_repeated_notes(raw_note_events, min_gap):
    if min_gap <= 0:
        return raw_note_events

    kept_events = []
    last_end_by_note = {}
    for start, end, note, velocity in sorted(
        raw_note_events, key=lambda item: (item[0], item[2])
    ):
        previous_end = last_end_by_note.get(note)
        if previous_end is not None and start - previous_end <= min_gap:
            continue

        kept_events.append((start, end, note, velocity))
        last_end_by_note[note] = end

    return kept_events


def limit_simultaneous_notes(note_events, max_simultaneous_notes):
    if max_simultaneous_notes is None or max_simultaneous_notes <= 0:
        return note_events

    by_start = {}
    for event in note_events:
        by_start.setdefault(round(event.start, 3), []).append(event)

    limited = []
    for events in by_start.values():
        if len(events) <= max_simultaneous_notes:
            limited.extend(events)
            continue

        limited.extend(
            sorted(
                events,
                key=lambda event: (event.velocity, event.duration, event.note),
                reverse=True,
            )[:max_simultaneous_notes]
        )

    return sorted(limited, key=lambda event: (event.start, event.note))


def apply_melody_only(note_events, melody_window=0.08, melody_max_notes=1):
    if not note_events:
        return note_events

    if melody_window <= 0:
        melody_window = 0.08

    melody_max_notes = max(1, min(int(melody_max_notes), 3))
    by_window = {}
    for event in note_events:
        window_key = int(event.start / melody_window)
        by_window.setdefault(window_key, []).append(event)

    selected = []
    for events in by_window.values():
        selected.extend(
            sorted(
                events,
                key=lambda event: (event.velocity, event.duration, event.note),
                reverse=True,
            )[:melody_max_notes]
        )

    return sorted(selected, key=lambda event: (event.start, event.note))


def fit_note_for_37key_midi(note, note_map, out_of_range_mode):
    if note in note_map:
        return note

    if out_of_range_mode in (OCTAVE_FIT_OFF, OCTAVE_FIT_DROP):
        return None

    lowest, highest = playable_note_range(note_map)
    if lowest is None:
        return None

    if out_of_range_mode == OCTAVE_FIT_SMART:
        if distance_from_range(note, lowest, highest) > SMART_MAX_RANGE_DISTANCE:
            return None
        return octave_shift_note(note, note_map)

    if out_of_range_mode in (OCTAVE_FIT_OCTAVE_SHIFT, OCTAVE_FIT_SHIFT):
        return octave_shift_note(note, note_map)

    return None


def rank_37key_event(event, prefer_melody=True):
    duration_ms = event.duration * 1000
    pitch_bonus = event.note * 0.08 if prefer_melody else 0
    return event.velocity * 1.0 + duration_ms * 0.2 + pitch_bonus


def group_37key_events(note_events, window_seconds, max_simultaneous_notes, prefer_melody):
    if max_simultaneous_notes is None or max_simultaneous_notes <= 0:
        return note_events

    if window_seconds <= 0:
        window_seconds = 0.03

    by_window = {}
    for event in note_events:
        window_key = int(event.start / window_seconds)
        by_window.setdefault(window_key, []).append(event)

    selected = []
    for events in by_window.values():
        selected.extend(
            sorted(
                events,
                key=lambda event: rank_37key_event(event, prefer_melody=prefer_melody),
                reverse=True,
            )[:max_simultaneous_notes]
        )

    return sorted(selected, key=lambda event: (event.start, event.note))


def quantize_seconds(value, quantize_ms):
    if not quantize_ms:
        return value

    quantum = quantize_ms / 1000
    if quantum <= 0:
        return value

    return round(value / quantum) * quantum


def write_clean_midi(note_events, output_midi, quantize_ms=None):
    output_midi = str(output_midi)
    ticks_per_beat = 480
    tempo = mido.bpm2tempo(120)
    midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    timed_messages = []
    min_duration = (quantize_ms / 1000) if quantize_ms else 0.001
    for event in note_events:
        start = max(0.0, quantize_seconds(event.start, quantize_ms))
        end = max(0.0, quantize_seconds(event.end, quantize_ms))
        if end <= start:
            end = start + min_duration

        velocity = max(1, min(int(event.velocity), 127))
        timed_messages.append((start, 1, mido.Message("note_on", note=event.note, velocity=velocity)))
        timed_messages.append((end, 0, mido.Message("note_off", note=event.note, velocity=0)))

    timed_messages.sort(key=lambda item: (item[0], item[1]))

    previous_time = 0.0
    for timestamp, _, message in timed_messages:
        delta_seconds = max(0.0, timestamp - previous_time)
        message.time = int(round(mido.second2tick(delta_seconds, ticks_per_beat, tempo)))
        track.append(message)
        previous_time = timestamp

    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.save(output_midi)


def convert_to_37key_midi(input_midi, output_midi, note_map=None, options=None):
    note_map = note_map or DEFAULT_NOTE_MAP
    options = {**DEFAULT_37KEY_CLEAN_OPTIONS, **(options or {})}
    min_note_duration = max(0, int(options.get("min_note_duration_ms", 0))) / 1000
    velocity_threshold = max(0, min(int(options.get("velocity_threshold", 0)), 127))
    max_simultaneous_notes = int(options.get("max_simultaneous_notes") or 0)
    out_of_range_mode = options.get("out_of_range_mode") or OCTAVE_FIT_SMART
    prefer_melody = bool(options.get("prefer_melody", True))
    quantize_ms = options.get("quantize_ms")
    if quantize_ms is not None:
        quantize_ms = max(1, int(quantize_ms))

    clean_events = []
    for start, end, raw_note, velocity in extract_raw_note_events(
        input_midi, velocity_threshold=velocity_threshold
    ):
        duration = end - start
        if duration < min_note_duration:
            continue

        note = fit_note_for_37key_midi(raw_note, note_map, out_of_range_mode)
        if note is None:
            continue

        clean_events.append(
            CleanNoteEvent(
                start=start,
                end=end,
                note=note,
                key=note_map[note],
                velocity=velocity,
            )
        )

    clean_events = group_37key_events(
        clean_events,
        window_seconds=0.03,
        max_simultaneous_notes=max_simultaneous_notes,
        prefer_melody=prefer_melody,
    )
    write_clean_midi(clean_events, output_midi, quantize_ms=quantize_ms)
    return output_midi


def build_clean_note_events(
    midi_path,
    note_map=None,
    transpose=0,
    min_note_duration=0.0,
    velocity_threshold=0,
    merge_gap=0.03,
    max_simultaneous_notes=0,
    octave_fit_mode=OCTAVE_FIT_SMART,
    harmonic_fill=False,
    melody_only=False,
    melody_window=0.08,
    melody_max_notes=1,
    out_of_range_mode=None,
):
    note_map = note_map or DEFAULT_NOTE_MAP
    if out_of_range_mode is not None:
        octave_fit_mode = out_of_range_mode
    clean_events = []
    raw_events = extract_raw_note_events(
        midi_path, transpose=transpose, velocity_threshold=velocity_threshold
    )
    filtered_raw_events = []

    for start, end, raw_note, velocity in raw_events:
        duration = end - start
        if duration < min_note_duration:
            continue
        filtered_raw_events.append((start, end, raw_note, velocity))

    filtered_raw_events = drop_close_raw_repeated_notes(filtered_raw_events, merge_gap)

    for start, end, raw_note, velocity in filtered_raw_events:
        duration = end - start
        note = fit_note_to_map(
            raw_note,
            note_map,
            octave_fit_mode,
            duration=duration,
            velocity=velocity,
            min_note_duration=min_note_duration,
            velocity_threshold=velocity_threshold,
        )
        if note is None:
            continue

        clean_events.append(
            CleanNoteEvent(
                start=start,
                end=end,
                note=note,
                key=note_map[note],
                velocity=velocity,
            )
        )

    clean_events = merge_close_repeated_notes(clean_events, merge_gap)
    if melody_only:
        clean_events = apply_melody_only(
            clean_events,
            melody_window=melody_window,
            melody_max_notes=melody_max_notes,
        )
    clean_events = limit_simultaneous_notes(clean_events, max_simultaneous_notes)
    return clean_events


def iter_note_events(
    midi_path,
    note_map=None,
    transpose=0,
    min_note_duration=0.0,
    velocity_threshold=0,
    merge_gap=0.03,
    max_simultaneous_notes=0,
    octave_fit_mode=OCTAVE_FIT_SMART,
    harmonic_fill=False,
    melody_only=False,
    melody_window=0.08,
    melody_max_notes=1,
    out_of_range_mode=None,
):
    note_events = build_clean_note_events(
        midi_path,
        note_map=note_map,
        transpose=transpose,
        min_note_duration=min_note_duration,
        velocity_threshold=velocity_threshold,
        merge_gap=merge_gap,
        max_simultaneous_notes=max_simultaneous_notes,
        octave_fit_mode=octave_fit_mode,
        harmonic_fill=harmonic_fill,
        melody_only=melody_only,
        melody_window=melody_window,
        melody_max_notes=melody_max_notes,
        out_of_range_mode=out_of_range_mode,
    )

    keyboard_events = []
    for event in note_events:
        keyboard_events.append((event.start, "down", event.note, event.key))
        keyboard_events.append((event.end, "up", event.note, event.key))

    keyboard_events.sort(key=lambda event: (event[0], 0 if event[1] == "up" else 1))
    yield from keyboard_events


def preview_midi_keyboard(
    midi_path,
    note_map=None,
    limit=80,
    transpose=0,
    min_note_duration=0.0,
    velocity_threshold=0,
    merge_gap=0.03,
    max_simultaneous_notes=0,
    octave_fit_mode=OCTAVE_FIT_SMART,
    harmonic_fill=False,
    melody_only=False,
    melody_window=0.08,
    melody_max_notes=1,
    out_of_range_mode=None,
):
    print("\nPreviewing MIDI keyboard events:")
    count = 0
    for timestamp, action, note, key in iter_note_events(
        midi_path,
        note_map,
        transpose=transpose,
        min_note_duration=min_note_duration,
        velocity_threshold=velocity_threshold,
        merge_gap=merge_gap,
        max_simultaneous_notes=max_simultaneous_notes,
        octave_fit_mode=octave_fit_mode,
        harmonic_fill=harmonic_fill,
        melody_only=melody_only,
        melody_window=melody_window,
        melody_max_notes=melody_max_notes,
        out_of_range_mode=out_of_range_mode,
    ):
        note_name = midi_note_name(note)
        print(f"{timestamp:8.3f}s  note {note:3d} {note_name:3s}  {action:4s}  key {key}")
        count += 1
        if count >= limit:
            print(f"... preview stopped after {limit} events")
            break

    if count == 0:
        print("No mapped note events found in this MIDI file.")


def build_keyboard_schedule(
    midi_path,
    note_map=None,
    speed=1.0,
    chord_delay=0.018,
    min_hold=0.075,
    transpose=0,
    min_note_duration=0.0,
    velocity_threshold=0,
    merge_gap=0.03,
    max_simultaneous_notes=0,
    octave_fit_mode=OCTAVE_FIT_SMART,
    harmonic_fill=False,
    melody_only=False,
    melody_window=0.08,
    melody_max_notes=1,
    out_of_range_mode=None,
):
    if speed <= 0:
        raise ValueError("speed must be greater than 0")
    if chord_delay < 0:
        raise ValueError("chord_delay must be greater than or equal to 0")
    if min_hold < 0:
        raise ValueError("min_hold must be greater than or equal to 0")

    schedule = []
    chord_counts = {}
    note_events = build_clean_note_events(
        midi_path,
        note_map=note_map,
        transpose=transpose,
        min_note_duration=min_note_duration,
        velocity_threshold=velocity_threshold,
        merge_gap=merge_gap,
        max_simultaneous_notes=max_simultaneous_notes,
        octave_fit_mode=octave_fit_mode,
        harmonic_fill=harmonic_fill,
        melody_only=melody_only,
        melody_window=melody_window,
        melody_max_notes=melody_max_notes,
        out_of_range_mode=out_of_range_mode,
    )

    for event in note_events:
        start_time = event.start / speed
        end_time = event.end / speed
        chord_index = chord_counts.get(event.start, 0)
        chord_counts[event.start] = chord_index + 1
        press_time = start_time + (chord_index * chord_delay)
        release_time = max(end_time, press_time + min_hold)
        schedule.append((press_time, "down", event.note, event.key))
        schedule.append((release_time, "up", event.note, event.key))

    schedule.sort(key=lambda event: (event[0], 0 if event[1] == "up" else 1))
    return schedule


def play_midi_as_keyboard(
    midi_path,
    note_map=None,
    speed=1.0,
    stop_event=None,
    chord_delay=0.018,
    min_hold=0.075,
    transpose=0,
    min_note_duration=0.0,
    velocity_threshold=0,
    merge_gap=0.03,
    max_simultaneous_notes=0,
    octave_fit_mode=OCTAVE_FIT_SMART,
    harmonic_fill=False,
    melody_only=False,
    melody_window=0.08,
    melody_max_notes=1,
    out_of_range_mode=None,
):
    if speed <= 0:
        raise ValueError("speed must be greater than 0")

    active_keys = set()
    started_at = time.perf_counter()
    schedule = build_keyboard_schedule(
        midi_path,
        note_map=note_map,
        speed=speed,
        chord_delay=chord_delay,
        min_hold=min_hold,
        transpose=transpose,
        min_note_duration=min_note_duration,
        velocity_threshold=velocity_threshold,
        merge_gap=merge_gap,
        max_simultaneous_notes=max_simultaneous_notes,
        octave_fit_mode=octave_fit_mode,
        harmonic_fill=harmonic_fill,
        melody_only=melody_only,
        melody_window=melody_window,
        melody_max_notes=melody_max_notes,
        out_of_range_mode=out_of_range_mode,
    )

    try:
        for timestamp, action, note, key in schedule:
            if stop_event is not None and stop_event.is_set():
                break

            target_time = started_at + timestamp
            delay = target_time - time.perf_counter()
            while delay > 0:
                if stop_event is not None and stop_event.is_set():
                    return
                time.sleep(min(delay, 0.05))
                delay = target_time - time.perf_counter()

            if action == "down":
                keyboard.press(key)
                active_keys.add(key)
            else:
                keyboard.release(key)
                active_keys.discard(key)
    finally:
        for key in active_keys:
            keyboard.release(key)
