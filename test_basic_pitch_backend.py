import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from converter import convert_audio_to_midi


class BasicPitchBackendTests(unittest.TestCase):
    diagnostics = {
        "version": "1.27.0",
        "providers": ["CUDAExecutionProvider", "CPUExecutionProvider"],
        "cuda_available": True,
        "error": None,
    }

    def _write_midi(self, output_dir):
        midi_path = Path(output_dir) / "transcribed.mid"
        midi_path.write_bytes(b"MThd")

    def test_onnx_backend_is_selected_and_diagnostics_are_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "midi"
            messages = []

            def fake_run(command, cancel_token=None):
                self._write_midi(output_dir)

            with mock.patch(
                "converter.get_basic_pitch_backend_diagnostics",
                return_value=self.diagnostics,
            ), mock.patch("converter.find_executable", return_value="basic-pitch"), mock.patch(
                "converter.run", side_effect=fake_run
            ) as run_mock:
                convert_audio_to_midi(
                    "input.wav",
                    output_dir,
                    progress_callback=messages.append,
                )

            command = run_mock.call_args.args[0]
            self.assertEqual(command[:3], ["basic-pitch", "--model-serialization", "onnx"])
            self.assertIn("ONNX Runtime version: 1.27.0", messages)
            self.assertIn("CUDAExecutionProvider available: yes", messages)

    def test_failed_onnx_backend_retries_tensorflow_cli(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "midi"
            messages = []

            def fake_run(command, cancel_token=None):
                if "--model-serialization" in command:
                    raise subprocess.CalledProcessError(1, command)
                self._write_midi(output_dir)

            with mock.patch(
                "converter.get_basic_pitch_backend_diagnostics",
                return_value=self.diagnostics,
            ), mock.patch("converter.find_executable", return_value="basic-pitch"), mock.patch(
                "converter.run", side_effect=fake_run
            ) as run_mock:
                convert_audio_to_midi(
                    "input.wav",
                    output_dir,
                    progress_callback=messages.append,
                )

            self.assertEqual(run_mock.call_count, 2)
            fallback_command = run_mock.call_args_list[1].args[0]
            self.assertEqual(fallback_command, ["basic-pitch", str(output_dir), "input.wav"])
            self.assertIn("Basic Pitch CLI is using TensorFlow backend.", messages)


if __name__ == "__main__":
    unittest.main()
