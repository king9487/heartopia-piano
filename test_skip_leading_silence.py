import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import mido

from keyboard_mapping import MappingProfile
from midi_to_keyboard import (
    build_keyboard_schedule,
    build_original_keyboard_schedule,
    trim_leading_silence_midi,
)


def write_delayed_note_midi(path, *, delay_ticks=4800, note=60):
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(mido.Message("note_on", channel=0, note=note, velocity=80, time=delay_ticks))
    track.append(mido.Message("note_off", channel=0, note=note, velocity=0, time=480))
    midi.tracks.append(track)
    midi.save(path)


def absolute_events(midi_path):
    events = []
    for track_index, track in enumerate(mido.MidiFile(midi_path).tracks):
        absolute_tick = 0
        for message in track:
            absolute_tick += message.time
            events.append((track_index, absolute_tick, message))
    return events


class SkipLeadingSilenceTests(unittest.TestCase):
    def test_midi_with_five_seconds_leading_silence_starts_at_zero(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "silence.mid"
            write_delayed_note_midi(source)
            profile = MappingProfile("One Key", {60: "a"})
            logs = []

            schedule = build_keyboard_schedule(
                source,
                mapping_profile=profile,
                skip_leading_silence=True,
                log_callback=logs.append,
            )

            self.assertAlmostEqual(schedule[0][0], 0.0)
            self.assertAlmostEqual(schedule[1][0], 0.5)
            self.assertEqual(logs, ["Skipped leading silence: 5.000 seconds"])

    def test_range_playback_only_skips_when_range_begins_before_first_note(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "range.mid"
            write_delayed_note_midi(source)
            profile = MappingProfile("One Key", {60: "a"})

            before_note = build_keyboard_schedule(
                source,
                mapping_profile=profile,
                start_sec=3.0,
                end_sec=6.0,
                skip_leading_silence=True,
                log_callback=lambda _message: None,
            )
            at_note = build_keyboard_schedule(
                source,
                mapping_profile=profile,
                start_sec=5.0,
                end_sec=6.0,
                skip_leading_silence=True,
                log_callback=lambda _message: None,
            )

            self.assertAlmostEqual(before_note[0][0], 0.0)
            self.assertAlmostEqual(at_note[0][0], 0.0)

    def test_trim_export_with_meta_events_before_first_note_does_not_touch_source(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "meta.mid"
            trimmed = root / "trimmed.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            conductor = mido.MidiTrack()
            conductor.append(mido.MetaMessage("track_name", name="Lead-in", time=0))
            conductor.append(mido.MetaMessage("set_tempo", tempo=500000, time=2400))
            notes = mido.MidiTrack()
            notes.append(mido.Message("program_change", channel=0, program=1, time=0))
            notes.append(mido.Message("note_on", channel=0, note=60, velocity=80, time=4800))
            notes.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=480))
            midi.tracks.extend((conductor, notes))
            midi.save(source)
            source_hash = hashlib.sha256(source.read_bytes()).digest()

            trim_leading_silence_midi(
                source,
                trimmed,
                mapping_profile=MappingProfile("One Key", {60: "a"}),
                log_callback=lambda _message: None,
            )

            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), source_hash)
            events = absolute_events(trimmed)
            note_on_ticks = [
                tick
                for _track, tick, message in events
                if message.type == "note_on" and message.velocity > 0
            ]
            self.assertEqual(note_on_ticks, [0])
            self.assertTrue(any(message.type == "set_tempo" for _, _, message in events))

    def test_selected_tracks_exclude_earliest_source_note_before_skipping(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "tracks.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            early = mido.MidiTrack()
            early.append(mido.Message("note_on", channel=0, note=60, velocity=80, time=960))
            early.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=120))
            selected = mido.MidiTrack()
            selected.append(mido.Message("note_on", channel=1, note=64, velocity=80, time=2400))
            selected.append(mido.Message("note_off", channel=1, note=64, velocity=0, time=120))
            midi.tracks.extend((early, selected))
            midi.save(source)

            schedule = build_original_keyboard_schedule(
                source,
                mapping_profile=MappingProfile("One Key", {64: "b"}),
                part_filter={(1, 1)},
                skip_leading_silence=True,
                log_callback=lambda _message: None,
            )

            self.assertEqual([(event[1], event[2], event[3]) for event in schedule], [
                ("down", 64, "b"),
                ("up", 64, "b"),
            ])
            self.assertAlmostEqual(schedule[0][0], 0.0)
            self.assertAlmostEqual(schedule[1][0], 0.125)

    def test_all_notes_unmapped_does_not_log_silence_skip(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "unmapped.mid"
            write_delayed_note_midi(source)
            logs = []

            schedule = build_keyboard_schedule(
                source,
                mapping_profile=MappingProfile("Empty", {60: ""}),
                skip_leading_silence=True,
                log_callback=logs.append,
            )

            self.assertEqual(schedule, [])
            self.assertEqual(logs, ["Skipped unmapped note: C4"])


if __name__ == "__main__":
    unittest.main()
