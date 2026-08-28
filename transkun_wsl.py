"""WSL-backed Transkun audio-to-MIDI transcription."""

from pathlib import Path
import shutil
import subprocess
import time

from tools import CancelledError, terminate_process_tree


DEFAULT_WSL_DISTRO = "Ubuntu-24.04"
DEFAULT_TRANSKUN_VENV = "~/.venvs/transkun"
TRANSKUN_DEVICES = ("Auto", "CPU", "CUDA")


class TranskunWSLError(RuntimeError):
    """A readable Transkun/WSL configuration or execution error."""


class TranskunWSLBackend:
    def __init__(
        self,
        distro=DEFAULT_WSL_DISTRO,
        venv=DEFAULT_TRANSKUN_VENV,
        runner=subprocess.run,
        popen=subprocess.Popen,
        logger=None,
    ):
        self.distro = distro
        self.venv = venv
        self.runner = runner
        self.popen = popen
        self.logger = logger or print

    @property
    def python_command(self):
        return '"$HOME/' + self.venv.removeprefix("~/") + '/bin/python"'

    def _base_command(self):
        # --exec bypasses WSL's default shell so backslashes, Unicode, and
        # bash -lc positional arguments arrive unchanged.
        return ["wsl.exe", "-d", self.distro, "--exec"]

    def _run_check(self, args, input_text=None):
        try:
            return self.runner(
                self._base_command() + args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                input=input_text,
            )
        except FileNotFoundError as exc:
            raise TranskunWSLError(
                "WSL is not installed or wsl.exe is not available."
            ) from exc

    def is_available(self):
        result = self._run_check(["true"])
        return result.returncode == 0

    def windows_to_wsl_path(self, path):
        windows_path = str(Path(path).resolve())
        try:
            result = self.runner(
                [
                    "wsl.exe", "-d", self.distro,
                    "--exec", "wslpath", "-a", windows_path,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except FileNotFoundError as exc:
            raise TranskunWSLError(
                "WSL is not installed or wsl.exe is not available."
            ) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise TranskunWSLError(
                f"Could not convert Windows path for WSL: {path}"
                + (f"\n{detail}" if detail else "")
            )
        converted = result.stdout.strip()
        if not converted:
            raise TranskunWSLError(
                "WSL path conversion returned an empty path.\n"
                f"Windows path: {windows_path}"
            )
        return converted

    def check_input_exists(self, input_path, input_wsl):
        if not input_wsl:
            raise TranskunWSLError(
                "Converted WSL input path is empty; Transkun was not started.\n"
                f"Windows input path: {input_path}"
            )
        result = self._run_check(["test", "-f", input_wsl])
        exists = result.returncode == 0
        self.logger(f"Input exists in WSL: {'true' if exists else 'false'}")
        if not exists:
            raise TranskunWSLError(
                "Input audio file was not found inside WSL.\n"
                f"Windows input path: {input_path}\n"
                f"WSL input path: {input_wsl}"
            )
        return True

    def check_transkun(self):
        script = (
            f"test -x {self.python_command} && "
            f"exec {self.python_command} -c 'import transkun'"
        )
        result = self._run_check(["bash", "-lc", script])
        if result.returncode != 0:
            raise TranskunWSLError(
                "Transkun is not installed in WSL.\n\n"
                f"Expected environment:\n{self.distro}\n{self.venv}\n\n"
                f"Run:\nsource {self.venv}/bin/activate\n"
                "python -m pip install transkun"
            )
        return True

    def check_cuda(self):
        script = (
            f"exec {self.python_command} -c "
            "'import torch; print(torch.cuda.is_available())'"
        )
        result = self._run_check(["bash", "-lc", script])
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    def _transcribe_command(self, input_wsl, output_wsl, selected_device):
        script = (
            f'if [ "$3" = cuda ]; then '
            f'exec {self.python_command} -m transkun.transcribe "$1" "$2" '
            f'--device "$3"; else '
            f'exec {self.python_command} -m transkun.transcribe "$1" "$2"; fi'
        )
        return self._base_command() + [
            "bash", "-lc", script, "_", input_wsl, output_wsl, selected_device
        ]

    def transcribe(self, input_path, output_path, device="Auto", cancel_token=None):
        requested = {"AUTO": "Auto", "CPU": "CPU", "CUDA": "CUDA"}.get(
            str(device).upper(), str(device)
        )
        if requested not in TRANSKUN_DEVICES:
            raise ValueError(f"Unsupported Transkun device: {device}")
        if not shutil.which("wsl.exe"):
            raise TranskunWSLError("WSL is not installed or wsl.exe is not available.")
        if not self.is_available():
            raise TranskunWSLError(
                f"WSL distribution {self.distro} is not installed or cannot be started."
            )
        self.check_transkun()

        input_path = Path(input_path).resolve()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        input_wsl = self.windows_to_wsl_path(input_path)
        output_wsl = self.windows_to_wsl_path(output_path)
        if not output_wsl:
            raise TranskunWSLError(
                "Converted WSL output path is empty; Transkun was not started.\n"
                f"Windows output path: {output_path}"
            )
        for message in (
            f"Windows input path: {input_path}",
            f"WSL input path: {input_wsl}",
            f"Windows output path: {output_path}",
            f"WSL output path: {output_wsl}",
        ):
            self.logger(message)
        self.check_input_exists(input_path, input_wsl)
        use_cuda = requested == "CUDA" or (requested == "Auto" and self.check_cuda())
        selected = "CUDA" if use_cuda else "CPU"
        command = self._transcribe_command(input_wsl, output_wsl, selected.lower())

        for message in (
            "Transcription engine: Transkun (WSL)",
            f"WSL distro: {self.distro}",
            f"Device requested: {requested}",
            f"Device selected: {selected}",
            f"Final subprocess argv: {command!r}",
        ):
            self.logger(message)

        started = time.monotonic()
        process = self.popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if cancel_token:
            cancel_token.set_process(process)
        try:
            stdout, stderr = process.communicate()
            if cancel_token and cancel_token.is_cancelled():
                raise CancelledError("Operation cancelled")
        finally:
            if cancel_token:
                cancel_token.clear_process(process)
        self.logger(f"Transkun exit code: {process.returncode}")
        self.logger(f"Elapsed time: {time.monotonic() - started:.1f}s")
        if stdout.strip():
            self.logger(f"Transkun stdout: {stdout.strip()}")
        if stderr.strip():
            self.logger(f"Transkun stderr: {stderr.strip()}")
        if process.returncode != 0:
            raise TranskunWSLError(
                f"Transkun transcription failed (exit code {process.returncode})."
                + (f"\n{stderr.strip()}" if stderr.strip() else "")
            )
        created = output_path.is_file() and output_path.stat().st_size > 0
        self.logger(f"MIDI created: {'yes' if created else 'no'}")
        if not created:
            raise TranskunWSLError(
                f"Transkun completed but did not create a MIDI file: {output_path}"
            )
        return output_path
