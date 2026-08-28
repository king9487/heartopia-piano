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
        return ["wsl.exe", "-d", self.distro]

    def _run_check(self, args):
        try:
            return self.runner(
                self._base_command() + args,
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

    def is_available(self):
        result = self._run_check(["true"])
        return result.returncode == 0

    def windows_to_wsl_path(self, path):
        result = self._run_check(["wslpath", "-a", str(Path(path).resolve())])
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise TranskunWSLError(
                f"Could not convert Windows path for WSL: {path}"
                + (f"\n{detail}" if detail else "")
            )
        return result.stdout.strip()

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

    def _transcribe_command(self, input_wsl, output_wsl, use_cuda):
        script = (
            f"exec {self.python_command} -m transkun.transcribe \"$1\" \"$2\""
            + (" --device cuda" if use_cuda else "")
        )
        return self._base_command() + [
            "bash", "-lc", script, "_", input_wsl, output_wsl
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
        use_cuda = requested == "CUDA" or (requested == "Auto" and self.check_cuda())
        selected = "CUDA" if use_cuda else "CPU"
        command = self._transcribe_command(input_wsl, output_wsl, use_cuda)

        for message in (
            "Transcription engine: Transkun (WSL)",
            f"WSL distro: {self.distro}",
            f"Input Windows path: {input_path}",
            f"Input WSL path: {input_wsl}",
            f"Output Windows path: {output_path}",
            f"Output WSL path: {output_wsl}",
            f"Device requested: {requested}",
            f"Device selected: {selected}",
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
