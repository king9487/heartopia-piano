import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from converter import (
    DEFAULT_SEPARATION_MODE,
    DEFAULT_SEPARATION_STEM,
    prepare_separated_audio,
)


class SourceSeparationTests(unittest.TestCase):
    def make_source(self, folder):
        source = Path(folder) / "song.wav"
        source.write_bytes(b"audio")
        return source

    def test_defaults_preserve_two_stem_no_vocals_workflow(self):
        self.assertEqual(DEFAULT_SEPARATION_MODE, "Demucs vocals only")
        self.assertEqual(DEFAULT_SEPARATION_STEM, "no_vocals")

    def test_no_separation_uses_original_audio(self):
        with TemporaryDirectory() as directory:
            source = self.make_source(directory)
            with patch("converter.run") as run_mock:
                selected, stems = prepare_separated_audio(
                    source, Path(directory) / "separated", "No separation", "no_vocals"
                )
            self.assertEqual(selected, source)
            self.assertEqual(stems["no_vocals"], source)
            run_mock.assert_not_called()

    def test_vocals_only_routes_the_requested_stem(self):
        with TemporaryDirectory() as directory:
            source = self.make_source(directory)
            vocals = Path(directory) / "vocals.wav"
            no_vocals = Path(directory) / "no_vocals.wav"
            with patch("converter.separate_vocals", return_value=(vocals, no_vocals)):
                selected, stems = prepare_separated_audio(
                    source,
                    Path(directory) / "separated",
                    "Demucs vocals only",
                    "vocals",
                )
            self.assertEqual(selected, vocals)
            self.assertEqual(stems["no_vocals"], no_vocals)

    def test_four_stem_runs_full_demucs_and_selects_other(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root)
            output = root / "separated"
            stem_dir = output / "htdemucs" / "song"

            def fake_run(command, cancel_token=None):
                stem_dir.mkdir(parents=True, exist_ok=True)
                for name in ("vocals", "drums", "bass", "other"):
                    (stem_dir / f"{name}.wav").write_bytes(b"stem")

            with patch("converter.find_executable", side_effect=lambda name: name), patch(
                "converter.run", side_effect=fake_run
            ) as run_mock:
                selected, stems = prepare_separated_audio(
                    source, output, "Demucs 4-stem", "other", device="cuda:0"
                )

            command = run_mock.call_args.args[0]
            self.assertNotIn("--two-stems=vocals", command)
            self.assertIn("--device", command)
            self.assertEqual(selected, stem_dir / "other.wav")
            self.assertTrue(all(stems[name].exists() for name in ("vocals", "drums", "bass", "other")))

    def test_existing_no_vocals_does_not_run_demucs(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root)
            existing = root / "separated" / "htdemucs" / "song" / "no_vocals.wav"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"stem")
            with patch("converter.run") as run_mock:
                selected, _ = prepare_separated_audio(
                    source, root / "separated", "Existing no_vocals", "no_vocals"
                )
            self.assertEqual(selected, existing)
            run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
