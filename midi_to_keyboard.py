import time
from dataclasses import dataclass

import keyboard
import mido


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
OCTAVE_FIT_OFF = "off"
OCTAVE_FIT_SHIFT = "shift"
OCTAVE_FIT_DROP = "drop"


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


def fit_note_to_map(note, note_map, octave_fit_mode):
    if note in note_map:
        return note

    if octave_fit_mode in (OCTAVE_FIT_OFF, OCTAVE_FIT_DROP):
        return None

    playable_notes = sorted(note_map)
    if not playable_notes:
        return None

    lowest = playable_notes[0]
    highest = playable_notes[-1]
    candidates = []
    for octave_shift in range(-10, 11):
        candidate = note + (12 * octave_shift)
        if lowest <= candidate <= highest and candidate in note_map:
            candidates.append((abs(octave_shift), candidate))

    if not candidates:
        return None

    return sorted(candidates, key=lambda item: item[0])[0][1]


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


def build_clean_note_events(
    midi_path,
    note_map=None,
    transpose=0,
    min_note_duration=0.0,
    velocity_threshold=0,
    merge_gap=0.03,
    max_simultaneous_notes=0,
    octave_fit_mode=OCTAVE_FIT_OFF,
):
    note_map = note_map or DEFAULT_NOTE_MAP
    clean_events = []

    for start, end, raw_note, velocity in extract_raw_note_events(
        midi_path, transpose=transpose, velocity_threshold=velocity_threshold
    ):
        note = fit_note_to_map(raw_note, note_map, octave_fit_mode)
        if note is None:
            continue

        duration = end - start
        if duration < min_note_duration:
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
    octave_fit_mode=OCTAVE_FIT_OFF,
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
    octave_fit_mode=OCTAVE_FIT_OFF,
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
    octave_fit_mode=OCTAVE_FIT_OFF,
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
    octave_fit_mode=OCTAVE_FIT_OFF,
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
