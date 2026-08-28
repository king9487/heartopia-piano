import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from converter import convert_audio_to_midi
from transkun_wsl import TranskunWSLBackend, TranskunWSLError


class FakeProcess:
    def __init__(self, command, output=None, returncode=0, stderr=""):
        self.command = command
        self.returncode = returncode
        self.output = output
        self.stderr = stderr

    def communicate(self):
        if self.output:
            Path(self.output).write_bytes(b"MThd")
        return "done", self.stderr


class TranskunWSLBackendTests(unittest.TestCase):
    def _runner(self, command, **kwargs):
        if "wslpath" in command:
            value = command[-1].replace("\\", "/")
            return subprocess.CompletedProcess(command, 0, "/mnt/" + value[0].lower() + value[2:] + "\n", "")
        if "torch.cuda" in " ".join(command):
            return subprocess.CompletedProcess(command, 0, "True\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    def test_wslpath_handles_spaces_unicode_and_other_drives(self):
        backend = TranskunWSLBackend(runner=self._runner)
        result = backend.windows_to_wsl_path(r"D:\音乐 (live)\曲.wav")
        self.assertIn("/mnt/d/", result)
        self.assertIn("音乐 (live)/曲.wav", result)

    def test_missing_wsl_distribution_is_readable(self):
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 1, "", "missing"))
        backend = TranskunWSLBackend(runner=runner)
        with mock.patch("transkun_wsl.shutil.which", return_value="wsl.exe"):
            with self.assertRaisesRegex(TranskunWSLError, "distribution Ubuntu-24.04"):
                backend.transcribe("in.wav", "out.mid")

    def test_requested_taipei_unicode_path_is_not_empty(self):
        windows_path = (
            "C:\\Users\\PC\\Desktop\\python_script\\youtube_to_midi\\output\\"
            "能不能和我留在台北 (陪我幾天) - 冰球樂團icyball - 鋼琴教學_NAfgID7h8nk\\"
            "download\\song.wav"
        )
        backend = TranskunWSLBackend(runner=self._runner)
        converted = backend.windows_to_wsl_path(windows_path)
        self.assertTrue(converted)
        self.assertIn("能不能和我留在台北 (陪我幾天)", converted)

    def test_empty_converted_path_aborts_before_transkun(self):
        runner = mock.Mock(
            side_effect=[
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 0, "   \n", ""),
            ]
        )
        popen = mock.Mock()
        backend = TranskunWSLBackend(runner=runner, popen=popen)
        with mock.patch("transkun_wsl.shutil.which", return_value="wsl.exe"):
            with self.assertRaisesRegex(TranskunWSLError, "empty path"):
                backend.transcribe("input.wav", "output.mid")
        popen.assert_not_called()

    def test_missing_wsl_input_aborts_with_both_paths(self):
        def runner(command, **kwargs):
            if "wslpath" in " ".join(command):
                return subprocess.CompletedProcess(command, 0, "/mnt/c/input.wav\n", "")
            if "test" in command and "-f" in command:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, "", "")
        popen = mock.Mock()
        backend = TranskunWSLBackend(runner=runner, popen=popen, logger=lambda _: None)
        with mock.patch("transkun_wsl.shutil.which", return_value="wsl.exe"):
            with self.assertRaises(TranskunWSLError) as raised:
                backend.transcribe("input.wav", "output.mid")
        self.assertIn("Windows input path:", str(raised.exception))
        self.assertIn("WSL input path: /mnt/c/input.wav", str(raised.exception))
        popen.assert_not_called()

    def test_missing_venv_or_import_failure_is_readable(self):
        calls = 0
        def runner(command, **kwargs):
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(command, 0 if calls == 1 else 1, "", "import failed")
        backend = TranskunWSLBackend(runner=runner)
        with mock.patch("transkun_wsl.shutil.which", return_value="wsl.exe"):
            with self.assertRaisesRegex(TranskunWSLError, "Transkun is not installed"):
                backend.transcribe("in.wav", "out.mid")

    def test_cpu_and_cuda_commands_and_output_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.wav"
            source.write_bytes(b"wav")
            for device, cuda_expected in (("CPU", False), ("CUDA", True)):
                output = Path(temp) / f"{device}.mid"
                made = []
                def popen(command, **kwargs):
                    made.append(command)
                    return FakeProcess(command, output)
                backend = TranskunWSLBackend(runner=self._runner, popen=popen, logger=lambda _: None)
                with mock.patch("transkun_wsl.shutil.which", return_value="wsl.exe"):
                    self.assertEqual(backend.transcribe(source, output, device=device), output.resolve())
                self.assertEqual(made[0][-4], "_")
                self.assertEqual(made[0][-1], device.lower())
                self.assertEqual(made[0][3], "--exec")
                self.assertIn('"$1" "$2"', made[0][-5])
                self.assertIn('"$3"', made[0][-5])

    def test_failure_and_missing_output_are_readable(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.wav"
            source.write_bytes(b"wav")
            for code, expected in ((2, "boom"), (0, "did not create")):
                backend = TranskunWSLBackend(
                    runner=self._runner,
                    popen=lambda command, **kwargs: FakeProcess(command, returncode=code, stderr="boom"),
                    logger=lambda _: None,
                )
                with mock.patch("transkun_wsl.shutil.which", return_value="wsl.exe"):
                    with self.assertRaisesRegex(TranskunWSLError, expected):
                        backend.transcribe(source, Path(temp) / f"missing{code}.mid", device="CPU")

    def test_engine_selection_does_not_invoke_basic_pitch(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "converter.TranskunWSLBackend"
        ) as backend_type, mock.patch("converter.find_executable") as basic_pitch:
            expected = Path(temp) / "raw.mid"
            backend_type.return_value.transcribe.return_value = expected
            actual = convert_audio_to_midi(
                "input.wav", Path(temp) / "midi", transcription_engine="Transkun (WSL)"
            )
            self.assertEqual(actual, expected)
            basic_pitch.assert_not_called()
            output_arg = backend_type.return_value.transcribe.call_args.args[1]
            self.assertEqual(output_arg.name, "transkun_raw.mid")

    def test_transkun_regenerates_even_when_midi_already_exists(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "converter.TranskunWSLBackend"
        ) as backend_type:
            output_dir = Path(temp) / "midi"
            output_dir.mkdir()
            (output_dir / "old_basic_pitch.mid").write_bytes(b"MThd")
            raw_path = output_dir / "raw_transcription" / "transkun_raw.mid"
            raw_path.parent.mkdir()
            raw_path.write_bytes(b"old")
            backend_type.return_value.transcribe.return_value = raw_path

            result = convert_audio_to_midi(
                "input.wav",
                output_dir,
                transcription_engine="Transkun (WSL)",
            )

            self.assertEqual(result, raw_path)
            backend_type.return_value.transcribe.assert_called_once()


if __name__ == "__main__":
    unittest.main()
