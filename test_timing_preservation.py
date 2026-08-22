import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import mido

from midi_ai_optimizer import (
    midi_notes_to_dicts,
    optimize_37key_midi,
    pitch_correct_37key_midi,
    smooth_note_events,
)
from midi_piano_arranger import arrange_piano_midi
from midi_rule_engine import convert_to_37key_midi, read_midi_notes, write_clean_midi


def write_timing_fixture(path, note_count=40):
    ppq = 960
    midi = mido.MidiFile(type=1, ticks_per_beat=ppq)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    events = [(0, 0, mido.MetaMessage("set_tempo", tempo=600000, time=0))]
    for index in range(note_count):
        start = 37 + (index * 173)
        end = start + 91 + (index % 7)
        pitch = 60 + (index % 8)
        events.append((start, 2, mido.Message("note_on", note=pitch, velocity=80)))
        events.append((end, 1, mido.Message("note_off", note=pitch, velocity=0)))
    events.append((2500, 0, mido.MetaMessage("set_tempo", tempo=428571, time=0)))
    events.sort(key=lambda item: (item[0], item[1]))
    emitted = 0
    for absolute_tick, _, message in events:
        message.time = absolute_tick - emitted
        track.append(message)
        emitted = absolute_tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.save(path)


class TimingPreservationTests(unittest.TestCase):
    def test_write_clean_midi_round_trip_stays_within_one_tick(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.mid"
            rewritten = folder / "rewritten.mid"
            write_timing_fixture(source, note_count=100)

            before = sorted(read_midi_notes(source), key=lambda note: note.start_tick)
            write_clean_midi(before, rewritten)
            after = sorted(read_midi_notes(rewritten), key=lambda note: note.start_tick)

            self.assertEqual(len(after), len(before))
            timing_errors = [
                abs(left_tick - right_tick)
                for left, right in zip(before, after)
                for left_tick, right_tick in (
                    (left.start_tick, right.start_tick),
                    (left.end_tick, right.end_tick),
                )
            ]
            self.assertLessEqual(max(timing_errors, default=0), 1)

    def test_rule_notes_preserve_ticks_ppq_and_tempo_map(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.mid"
            write_timing_fixture(source)
            notes = sorted(read_midi_notes(source), key=lambda note: note.start_tick)
            self.assertEqual(notes[0].start_tick, 37)
            self.assertEqual(notes[0].end_tick, 128)
            self.assertEqual(notes[0].ppq, 960)
            self.assertIn((0, 600000), notes[0].tempo_map)
            self.assertIn((2500, 428571), notes[0].tempo_map)

    def test_cleanup_export_reimport_preserves_every_tick(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "imported.mid"
            clean = folder / "clean_37key.mid"
            exported = folder / "exported.mid"
            write_timing_fixture(source, note_count=100)
            options = {
                "min_note_duration_ms": 0,
                "velocity_threshold": 0,
                "max_simultaneous_notes": 0,
                "out_of_range_mode": "smart",
            }
            convert_to_37key_midi(source, clean, options=options)
            write_clean_midi(read_midi_notes(clean), exported)

            before = sorted(read_midi_notes(source), key=lambda note: note.start_tick)
            after = sorted(read_midi_notes(exported), key=lambda note: note.start_tick)
            self.assertEqual(len(after), len(before))
            self.assertEqual([note.start_tick for note in after], [note.start_tick for note in before])
            self.assertEqual([note.end_tick for note in after], [note.end_tick for note in before])
            self.assertLessEqual(
                max(abs(left.start_tick - right.start_tick) for left, right in zip(before, after)),
                1,
            )

    def test_arranger_outputs_only_source_group_onsets_without_quantizing(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.mid"
            arranged = folder / "piano_arranged_37key.mid"
            write_timing_fixture(source)
            source_notes = read_midi_notes(source)
            arrange_piano_midi(source, arranged, options={"max_notes_per_window": 2})
            arranged_notes = read_midi_notes(arranged)
            source_onsets = {note.start_tick for note in source_notes}
            self.assertTrue(arranged_notes)
            self.assertTrue(all(note.start_tick in source_onsets for note in arranged_notes))
            self.assertTrue(all(note.ppq == 960 for note in arranged_notes))

    def test_optimizer_and_pitch_correction_preserve_survivor_ticks(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.mid"
            optimized = folder / "ai_optimized_37key.mid"
            corrected = folder / "pitch_corrected_37key.mid"
            write_timing_fixture(source)
            optimize_37key_midi(
                source,
                optimized,
                options={"mode": "rule", "min_note_duration_ms": 1, "max_notes_per_window": 3},
            )
            pitch_correct_37key_midi(optimized, corrected)
            optimized_ticks = {note.start_tick for note in read_midi_notes(optimized)}
            corrected_notes = read_midi_notes(corrected)
            self.assertTrue(corrected_notes)
            self.assertTrue(all(note.start_tick in optimized_ticks for note in corrected_notes))
            self.assertTrue(all(note.ppq == 960 for note in corrected_notes))

    def test_optimizer_reports_each_chunk_progress(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.mid"
            optimized = folder / "optimized.mid"
            write_timing_fixture(source, note_count=40)
            progress = []

            optimize_37key_midi(
                source,
                optimized,
                options={
                    "mode": "rule",
                    "chunk_ms": 1000,
                    "progress_callback": lambda current, total: progress.append(
                        (current, total)
                    ),
                },
            )

            self.assertGreater(len(progress), 1)
            self.assertEqual(
                progress,
                [(index, len(progress)) for index in range(1, len(progress) + 1)],
            )

    def test_final_smoothing_documents_deliberate_start_changes(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.mid"
            write_timing_fixture(source, note_count=4)
            smoothed = smooth_note_events(midi_notes_to_dicts(source))
            self.assertTrue(all("timing_changes" in note for note in smoothed))
            self.assertTrue(any(note["timing_changes"] for note in smoothed))


if __name__ == "__main__":
    unittest.main()
