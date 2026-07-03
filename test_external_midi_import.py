import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import mido

from converter import import_external_midi
from midi_analysis import inspect_midi_file


def write_midi(path, *, ppq=480, tracks=1, tempo=500000, notes=(60, 64, 76)):
    midi = mido.MidiFile(type=1 if tracks > 1 else 0, ticks_per_beat=ppq)
    for track_index in range(tracks):
        track = mido.MidiTrack()
        midi.tracks.append(track)
        if track_index == 0 and tempo is not None:
            track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
        for note in notes if track_index == tracks - 1 else ():
            track.append(mido.Message("note_on", note=note, velocity=80, time=0))
            track.append(mido.Message("note_off", note=note, velocity=0, time=ppq))
    midi.save(path)


class ExternalMidiImportTests(unittest.TestCase):
    def test_type_two_midi_is_normalized_only_in_the_working_copy(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sequences.mid"
            midi = mido.MidiFile(type=2, ticks_per_beat=480)
            for note in (60, 64):
                track = mido.MidiTrack()
                track.append(mido.Message("note_on", note=note, velocity=80, time=0))
                track.append(mido.Message("note_off", note=note, velocity=0, time=480))
                midi.tracks.append(track)
            midi.save(source)
            original = source.read_bytes()

            result = import_external_midi(source, output_root=root / "output")

            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(mido.MidiFile(source).type, 2)
            self.assertEqual(mido.MidiFile(result["imported_midi"]).type, 1)
            self.assertTrue(result["final_midi"].exists())

    def test_import_preserves_original_and_writes_complete_pipeline(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "normal.mid"
            write_midi(source)
            original_hash = hashlib.sha256(source.read_bytes()).digest()

            progress = []
            result = import_external_midi(
                source,
                output_root=root / "output",
                progress_callback=progress.append,
            )

            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original_hash)
            self.assertNotEqual(result["imported_midi"], source)
            for key in (
                "imported_midi", "clean_midi", "piano_arranged_midi",
                "ai_optimized_midi", "pitch_corrected_midi", "final_midi",
            ):
                self.assertTrue(result[key].is_file(), key)
                self.assertEqual(result[key].parent, result["base_dir"])
            self.assertIn("Running Cleanup...", progress)
            self.assertIn("Running Piano Arranger...", progress)
            self.assertIn("Running AI Optimizer...", progress)
            self.assertIn("Running Pitch Correction...", progress)
            self.assertEqual(progress[-1], "All MIDI processing stages completed.")

    def test_piano_cover_and_musescore_style_files_are_accepted(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            piano_cover = root / "Piano Cover.mid"
            musescore = root / "MuseScore Export.midi"
            write_midi(piano_cover, tracks=2, notes=(48, 55, 60, 64, 67, 72))
            write_midi(musescore, ppq=960, tracks=3, tempo=600000)

            piano_result = import_external_midi(piano_cover, output_root=root / "output")
            muse_result = import_external_midi(musescore, output_root=root / "output")

            self.assertTrue(piano_result["final_midi"].exists())
            self.assertEqual(muse_result["metadata"]["ppq"], 960)
            self.assertEqual(muse_result["metadata"]["tracks"], 3)
            self.assertAlmostEqual(muse_result["metadata"]["bpm"], 100.0)

    def test_metadata_counts_range_and_reports_missing_tempo(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "untimed.mid"
            write_midi(source, tempo=None, notes=(35, 60, 72, 73))
            metadata = inspect_midi_file(source)
            self.assertIsNone(metadata["bpm"])
            self.assertEqual(metadata["total_notes"], 4)
            self.assertEqual(metadata["notes_inside_map"], 2)
            self.assertEqual(metadata["notes_outside_map"], 2)

    def test_skipped_stages_create_named_pass_through_working_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "skip.mid"
            write_midi(source, notes=(35, 60, 73))
            result = import_external_midi(
                source,
                output_root=root / "output",
                skips={
                    "cleanup": True,
                    "piano_arranger": True,
                    "ai_optimizer": True,
                    "pitch_correction": True,
                },
            )
            imported_bytes = result["imported_midi"].read_bytes()
            for key in (
                "clean_midi", "piano_arranged_midi", "ai_optimized_midi",
                "pitch_corrected_midi",
            ):
                self.assertEqual(result[key].read_bytes(), imported_bytes)
            self.assertTrue(result["final_midi"].exists())
            final_metadata = inspect_midi_file(result["final_midi"])
            self.assertEqual(final_metadata["notes_outside_map"], 0)


if __name__ == "__main__":
    unittest.main()
