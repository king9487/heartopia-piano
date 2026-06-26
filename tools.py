import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")


REQUIRED_TOOLS = ("yt-dlp", "demucs", "basic-pitch", "ffmpeg")


class CancelledError(RuntimeError):
    pass


class CancellationToken:
    def __init__(self):
        self._event = threading.Event()
        self._process = None
        self._lock = threading.Lock()

    def cancel(self):
        self._event.set()
        with self._lock:
            process = self._process

        if process and process.poll() is None:
            terminate_process_tree(process)

    def is_cancelled(self):
        return self._event.is_set()

    def set_process(self, process):
        with self._lock:
            self._process = process

        if self.is_cancelled() and process.poll() is None:
            terminate_process_tree(process)

    def clear_process(self, process):
        with self._lock:
            if self._process is process:
                self._process = None


def get_registered_windows_paths():
    if winreg is None:
        return []

    registry_locations = [
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    paths = []
    for root, subkey in registry_locations:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        paths.extend(Path(part) for part in value.split(os.pathsep) if part)

    return paths


def find_executable(name):
    path = shutil.which(name)
    if path and is_usable_executable(Path(path), name):
        return path

    env_paths = [Path(part) for part in os.environ.get("PATH", "").split(os.pathsep) if part]
    search_paths = env_paths + get_registered_windows_paths()

    scripts_dir = Path(sys.executable).resolve().parent
    search_paths.append(scripts_dir)

    candidates = []
    for directory in search_paths:
        candidates.extend(
            [
                directory / f"{name}.exe",
                directory / f"{name}.cmd",
                directory / name,
            ]
        )
    for candidate in candidates:
        if is_usable_executable(candidate, name):
            return str(candidate)

    return None


def is_usable_executable(path, name):
    if not path.exists():
        return False

    if name == "ffmpeg":
        return (path.parent / "ffprobe.exe").exists() or (path.parent / "ffprobe").exists()

    return True


def find_ffmpeg_location():
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        return None

    ffmpeg_dir = Path(ffmpeg).parent
    if not (ffmpeg_dir / "ffprobe.exe").exists() and not (ffmpeg_dir / "ffprobe").exists():
        return None

    return str(ffmpeg_dir)


def check_cli_dependencies():
    missing = [tool for tool in REQUIRED_TOOLS if not find_executable(tool)]
    if "ffmpeg" not in missing and not find_ffmpeg_location():
        missing.append("ffmpeg/ffprobe")
    if missing:
        raise RuntimeError(
            "Missing required command(s): "
            + ", ".join(missing)
            + "\nInstall the Python packages with: python -m pip install -r requirements.txt"
            + "\nInstall ffmpeg separately and make sure it is available in PATH."
        )


def default_demucs_device():
    try:
        import torch
    except ImportError:
        return None

    if torch.cuda.is_available():
        return "cuda:0"

    return None


def run(cmd, cancel_token=None, timeout=None):
    print("\nRunning:", " ".join(cmd))
    if cancel_token and cancel_token.is_cancelled():
        raise CancelledError("Operation cancelled")

    process = subprocess.Popen(cmd, env=subprocess_environment())
    if cancel_token:
        cancel_token.set_process(process)

    started_at = time.monotonic()
    try:
        while True:
            return_code = process.poll()
            if return_code is not None:
                break

            if cancel_token and cancel_token.is_cancelled():
                terminate_process_tree(process)
                raise CancelledError("Operation cancelled")

            if timeout is not None and time.monotonic() - started_at > timeout:
                terminate_process_tree(process)
                raise TimeoutError(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")

            time.sleep(0.2)
    finally:
        if cancel_token:
            cancel_token.clear_process(process)

    if cancel_token and cancel_token.is_cancelled():
        raise CancelledError("Operation cancelled")

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd)


def format_command_error(error):
    if isinstance(error, subprocess.CalledProcessError):
        parts = [
            f"Command failed with exit code {error.returncode}:",
            " ".join(str(part) for part in error.cmd),
        ]
        output = getattr(error, "output", None)
        stderr = getattr(error, "stderr", None)
        if output:
            parts.append("\nOutput:")
            parts.append(str(output).strip())
        if stderr:
            parts.append("\nError:")
            parts.append(str(stderr).strip())
        return "\n".join(part for part in parts if part)

    return str(error)


def run_capture(cmd, cancel_token=None, timeout=120):
    print("\nRunning:", " ".join(cmd))
    if cancel_token and cancel_token.is_cancelled():
        raise CancelledError("Operation cancelled")

    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as stdout_file:
        with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as stderr_file:
            process = subprocess.Popen(
                cmd,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=subprocess_environment(),
            )
            if cancel_token:
                cancel_token.set_process(process)

            started_at = time.monotonic()
            try:
                while True:
                    return_code = process.poll()
                    if return_code is not None:
                        break

                    if cancel_token and cancel_token.is_cancelled():
                        terminate_process_tree(process)
                        raise CancelledError("Operation cancelled")

                    if timeout is not None and time.monotonic() - started_at > timeout:
                        terminate_process_tree(process)
                        raise TimeoutError(
                            f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
                        )

                    time.sleep(0.2)
            finally:
                if cancel_token:
                    cancel_token.clear_process(process)

            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read()
            stderr = stderr_file.read()

            if cancel_token and cancel_token.is_cancelled():
                raise CancelledError("Operation cancelled")

            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, cmd, stdout, stderr)

            return stdout


def subprocess_environment():
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def terminate_process_tree(process):
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
