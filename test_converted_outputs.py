import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from converter import list_converted_outputs, results_from_output_dir


class ConvertedOutputTests(unittest.TestCase):
    def test_loads_custom_no_separation_output(self):
        with TemporaryDirectory() as directory:
            output_root = Path(directory)
            base_dir = output_root / "Piano Cover_video-id"
            wav_file = base_dir / "download" / "song.wav"
            midi_dir = base_dir / "midi" / "selected_No separation_no_vocals"
            wav_file.parent.mkdir(parents=True)
            midi_dir.mkdir(parents=True)
            wav_file.touch()
            raw_midi = midi_dir / "song_basic_pitch.mid"
            raw_midi.touch()
            final_midi = midi_dir / "05_final_37key.mid"
            final_midi.touch()

            results = results_from_output_dir(base_dir)

            self.assertIsNotNone(results)
            self.assertEqual(results["accompaniment_midi"], raw_midi)
            self.assertEqual(results["accompaniment_final_midi"], final_midi)
            self.assertEqual(results["selected_audio"], wav_file)
            self.assertEqual(results["separation_mode"], "No separation")
            self.assertEqual(results["stem_to_convert"], "no_vocals")
            self.assertIn(base_dir, list_converted_outputs(output_root))

    def test_legacy_accompaniment_output_remains_supported(self):
        with TemporaryDirectory() as directory:
            base_dir = Path(directory) / "Legacy_video-id"
            midi_dir = base_dir / "midi" / "accompaniment"
            midi_dir.mkdir(parents=True)
            raw_midi = midi_dir / "song_basic_pitch.mid"
            raw_midi.touch()

            results = results_from_output_dir(base_dir)

            self.assertIsNotNone(results)
            self.assertEqual(results["accompaniment_midi"], raw_midi)
            self.assertEqual(results["separation_mode"], "Demucs vocals only")
            self.assertEqual(results["stem_to_convert"], "no_vocals")


if __name__ == "__main__":
    unittest.main()
