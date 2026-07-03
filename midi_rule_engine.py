from dataclasses import dataclass
from pathlib import Path

import mido

from midi_to_keyboard import (
    DEFAULT_NOTE_MAP,
    OCTAVE_FIT_DROP,
    OCTAVE_FIT_OFF,
    OCTAVE_FIT_OCTAVE_SHIFT,
    OCTAVE_FIT_SHIFT,
    OCTAVE_FIT_SMART,
)


CLEAN_37KEY_MIDI_NAME = "clean_37key.mid"
SMART_MAX_RANGE_DISTANCE = 24
DEFAULT_37KEY_CLEAN_OPTIONS = {
    "min_note_duration_ms": 35,
    "velocity_threshold": 12,
    "max_simultaneous_notes": 3,
    "out_of_range_mode": OCTAVE_FIT_SMART,
    "prefer_melody": True,
    "quantize_ms": None,
}
WINDOW_MS = 30


DEFAULT_PPQ = 480
DEFAULT_TEMPO = 500000


def normalize_tempo_map(tempo_map=None):
    entries = {int(tick): int(tempo) for tick, tempo in (tempo_map or ())}
    entries.setdefault(0, DEFAULT_TEMPO)
    return tuple(sorted(entries.items()))


def ticks_to_seconds(tick, ppq, tempo_map):
    target = max(0, int(tick))
    previous_tick = 0
    tempo = DEFAULT_TEMPO
    seconds = 0.0
    for change_tick, change_tempo in normalize_tempo_map(tempo_map):
        if change_tick > target:
            break
        seconds += mido.tick2second(change_tick - previous_tick, ppq, tempo)
        previous_tick = change_tick
        tempo = change_tempo
    return seconds + mido.tick2second(target - previous_tick, ppq, tempo)


def seconds_to_ticks(seconds, ppq, tempo_map):
    remaining = max(0.0, float(seconds))
    previous_tick = 0
    tempo = DEFAULT_TEMPO
    for change_tick, change_tempo in normalize_tempo_map(tempo_map):
        segment_seconds = mido.tick2second(change_tick - previous_tick, ppq, tempo)
        if remaining < segment_seconds:
            return previous_tick + int(round(mido.second2tick(remaining, ppq, tempo)))
        remaining -= segment_seconds
        previous_tick = change_tick
        tempo = change_tempo
    return previous_tick + int(round(mido.second2tick(remaining, ppq, tempo)))


@dataclass(init=False)
class RuleNote:
    start_tick: int
    end_tick: int
    original_note: int
    note: int
    velocity: int
    octave_shift: int
    ppq: int
    tempo_map: tuple

    def __init__(
        self, start=None, end=None, original_note=0, note=0, velocity=64,
        octave_shift=0, *, start_tick=None, end_tick=None, ppq=DEFAULT_PPQ,
        tempo_map=None,
    ):
        self.ppq = max(1, int(ppq))
        self.tempo_map = normalize_tempo_map(tempo_map)
        self.start_tick = (
            max(0, int(start_tick))
            if start_tick is not None
            else seconds_to_ticks(start or 0.0, self.ppq, self.tempo_map)
        )
        self.end_tick = (
            max(self.start_tick + 1, int(end_tick))
            if end_tick is not None
            else max(
                self.start_tick + 1,
                seconds_to_ticks(end if end is not None else start or 0.0, self.ppq, self.tempo_map),
            )
        )
        self.original_note = int(original_note)
        self.note = int(note)
        self.velocity = int(velocity)
        self.octave_shift = int(octave_shift)

    @property
    def start(self):
        return ticks_to_seconds(self.start_tick, self.ppq, self.tempo_map)

    @start.setter
    def start(self, value):
        self.start_tick = seconds_to_ticks(value, self.ppq, self.tempo_map)

    @property
    def end(self):
        return ticks_to_seconds(self.end_tick, self.ppq, self.tempo_map)

    @end.setter
    def end(self, value):
        self.end_tick = max(
            self.start_tick + 1,
            seconds_to_ticks(value, self.ppq, self.tempo_map),
        )

    @property
    def duration(self):
        return self.end - self.start

    @property
    def start_ms(self):
        return self.start * 1000

    @property
    def end_ms(self):
        return self.end * 1000

    @property
    def duration_ms(self):
        return self.duration * 1000


def is_note_off(message):
    return message.type == "note_off" or (
        message.type == "note_on" and message.velocity == 0
    )


def playable_range(note_map):
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


def read_midi_notes(input_midi):
    midi = mido.MidiFile(input_midi)
    merged = mido.merge_tracks(midi.tracks)
    absolute_tick = 0
    tempo_entries = []
    for message in merged:
        absolute_tick += message.time
        if message.type == "set_tempo":
            tempo_entries.append((absolute_tick, message.tempo))
    tempo_map = normalize_tempo_map(tempo_entries)

    absolute_tick = 0
    active_notes = {}
    notes = []

    for message in merged:
        absolute_tick += message.time

        if message.type == "note_on" and message.velocity > 0:
            key = (getattr(message, "channel", 0), message.note)
            active_notes.setdefault(key, []).append((absolute_tick, message.velocity))
        elif is_note_off(message):
            key = (getattr(message, "channel", 0), message.note)
            starts = active_notes.get(key)
            if not starts:
                continue
            start_tick, velocity = starts.pop(0)
            if not starts:
                active_notes.pop(key, None)
            if absolute_tick > start_tick:
                notes.append(
                    RuleNote(
                        start_tick=start_tick,
                        end_tick=absolute_tick,
                        ppq=midi.ticks_per_beat,
                        tempo_map=tempo_map,
                        original_note=message.note,
                        note=message.note,
                        velocity=velocity,
                    )
                )

    return notes


def clean_notes(notes, min_note_duration_ms=0, velocity_threshold=0):
    min_duration = max(0, int(min_note_duration_ms)) / 1000
    velocity_threshold = max(0, min(int(velocity_threshold), 127))
    return [
        note
        for note in notes
        if note.duration >= min_duration and note.velocity >= velocity_threshold
    ]


def octave_shift_into_range(note, note_map):
    lowest, highest = playable_range(note_map)
    if lowest is None:
        return None, 0

    candidate = note
    octave_shift = 0
    while candidate < lowest:
        candidate += 12
        octave_shift += 12
    while candidate > highest:
        candidate -= 12
        octave_shift -= 12

    if lowest <= candidate <= highest and candidate in note_map:
        return candidate, octave_shift
    return None, 0


def fit_note_to_37key(note, note_map, out_of_range_mode):
    if note in note_map:
        return note, 0

    if out_of_range_mode in (OCTAVE_FIT_OFF, OCTAVE_FIT_DROP):
        return None, 0

    lowest, highest = playable_range(note_map)
    if lowest is None:
        return None, 0

    if out_of_range_mode == OCTAVE_FIT_SMART:
        if distance_from_range(note, lowest, highest) > SMART_MAX_RANGE_DISTANCE:
            return None, 0
        return octave_shift_into_range(note, note_map)

    if out_of_range_mode in (OCTAVE_FIT_OCTAVE_SHIFT, OCTAVE_FIT_SHIFT):
        return octave_shift_into_range(note, note_map)

    return None, 0


def fit_notes_into_range(notes, note_map, out_of_range_mode):
    fitted_notes = []
    for note in notes:
        fitted_note, octave_shift = fit_note_to_37key(
            note.original_note, note_map, out_of_range_mode
        )
        if fitted_note is None:
            continue
        fitted_notes.append(
            RuleNote(
                start_tick=note.start_tick,
                end_tick=note.end_tick,
                ppq=note.ppq,
                tempo_map=note.tempo_map,
                original_note=note.original_note,
                note=fitted_note,
                velocity=note.velocity,
                octave_shift=octave_shift,
            )
        )
    return fitted_notes


def pitch_stability_bonus(note):
    if note.octave_shift == 0:
        return 6.0
    return max(0.0, 5.0 - (abs(note.octave_shift) / 12.0))


def rank_note(note, prefer_melody=True):
    melody_bonus = note.note * 0.08 if prefer_melody else 0
    return (
        note.velocity * 1.0
        + note.duration_ms * 0.2
        + pitch_stability_bonus(note)
        + melody_bonus
    )


def group_notes_by_windows(notes, window_ms=WINDOW_MS):
    window_seconds = max(1, int(window_ms)) / 1000
    grouped = {}
    for note in notes:
        window_key = int(note.start / window_seconds)
        grouped.setdefault(window_key, []).append(note)
    return grouped


def limit_notes_by_window(notes, max_simultaneous_notes, prefer_melody=True):
    if max_simultaneous_notes is None or max_simultaneous_notes <= 0:
        return sorted(notes, key=lambda note: (note.start, note.note))

    selected = []
    for group in group_notes_by_windows(notes).values():
        selected.extend(
            sorted(
                group,
                key=lambda note: rank_note(note, prefer_melody=prefer_melody),
                reverse=True,
            )[:max_simultaneous_notes]
        )

    return sorted(selected, key=lambda note: (note.start, note.note))


def quantize_seconds(value, quantize_ms):
    if not quantize_ms:
        return value

    quantum = max(1, int(quantize_ms)) / 1000
    return round(value / quantum) * quantum


def write_clean_midi(notes, output_midi, quantize_ms=None):
    output_midi = Path(output_midi)
    output_midi.parent.mkdir(parents=True, exist_ok=True)

    notes = list(notes)
    ticks_per_beat = notes[0].ppq if notes else DEFAULT_PPQ
    tempo_map = notes[0].tempo_map if notes else normalize_tempo_map()
    midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi.tracks.append(track)

    timed_messages = []
    for tick, tempo in tempo_map:
        timed_messages.append(
            (tick, 0, mido.MetaMessage("set_tempo", tempo=tempo, time=0))
        )

    for note in notes:
        if (
            not quantize_ms
            and note.ppq == ticks_per_beat
            and note.tempo_map == tempo_map
        ):
            start_tick = note.start_tick
            end_tick = note.end_tick
        else:
            start = quantize_seconds(note.start, quantize_ms)
            end = quantize_seconds(note.end, quantize_ms)
            start_tick = seconds_to_ticks(start, ticks_per_beat, tempo_map)
            end_tick = max(
                start_tick + 1,
                seconds_to_ticks(end, ticks_per_beat, tempo_map),
            )

        velocity = max(1, min(int(note.velocity), 127))
        timed_messages.append(
            (start_tick, 2, mido.Message("note_on", note=note.note, velocity=velocity))
        )
        timed_messages.append(
            (end_tick, 1, mido.Message("note_off", note=note.note, velocity=0))
        )

    timed_messages.sort(key=lambda item: (item[0], item[1]))

    emitted_tick = 0
    for absolute_tick, _, message in timed_messages:
        message.time = max(0, int(absolute_tick) - emitted_tick)
        track.append(message)
        emitted_tick = int(absolute_tick)

    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.save(output_midi)
    return output_midi


def build_clean_37key_notes(input_midi, note_map=None, options=None):
    note_map = note_map or DEFAULT_NOTE_MAP
    options = {**DEFAULT_37KEY_CLEAN_OPTIONS, **(options or {})}

    notes = read_midi_notes(input_midi)
    notes = clean_notes(
        notes,
        min_note_duration_ms=options.get("min_note_duration_ms", 0),
        velocity_threshold=options.get("velocity_threshold", 0),
    )
    notes = fit_notes_into_range(
        notes,
        note_map,
        options.get("out_of_range_mode") or OCTAVE_FIT_SMART,
    )
    notes = limit_notes_by_window(
        notes,
        int(options.get("max_simultaneous_notes") or 0),
        prefer_melody=bool(options.get("prefer_melody", True)),
    )
    return notes


def convert_to_37key_midi(input_midi, output_midi, note_map=None, options=None):
    options = {**DEFAULT_37KEY_CLEAN_OPTIONS, **(options or {})}
    notes = build_clean_37key_notes(input_midi, note_map=note_map, options=options)
    return write_clean_midi(notes, output_midi, quantize_ms=options.get("quantize_ms"))
