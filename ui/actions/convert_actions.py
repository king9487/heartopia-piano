import threading
from tkinter import filedialog, messagebox

from converter import audio_file_to_midi, youtube_to_midi
from tools import (
    CancellationToken,
    CancelledError,
    check_cli_dependencies,
    format_command_error,
)


class UiConvertActionsMixin:
    """UI callbacks and background work for URL/local-audio conversion."""

    def start_convert(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube URL first.")
            return

        assert self.convert_button is not None
        self.convert_button.configure(state="disabled")
        assert self.local_audio_button is not None
        self.local_audio_button.configure(state="disabled")
        assert self.stop_button is not None
        self.stop_button.configure(state="normal")
        self.results = None
        self.clear_midi_source_options()
        self.converting = True
        self.convert_cancel_token = CancellationToken()
        self.status_var.set("Checking dependencies")
        self.log_message("Starting conversion...")

        thread = threading.Thread(target=self.convert_worker, args=(url,), daemon=True)
        thread.start()

    def start_local_audio_convert(self):
        filename = filedialog.askopenfilename(
            title="Open local audio file",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg *.webm *.aac"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        assert self.convert_button is not None
        self.convert_button.configure(state="disabled")
        assert self.local_audio_button is not None
        self.local_audio_button.configure(state="disabled")
        assert self.stop_button is not None
        self.stop_button.configure(state="normal")
        self.results = None
        self.clear_midi_source_options()
        self.converting = True
        self.convert_cancel_token = CancellationToken()
        self.status_var.set("Checking dependencies")
        self.log_message(f"Starting local audio conversion: {filename}")

        thread = threading.Thread(
            target=self.local_audio_convert_worker, args=(filename,), daemon=True
        )
        thread.start()

    def convert_worker(self, url):
        try:
            check_cli_dependencies()
            self.queue.put(("status", "Downloading and converting"))
            demucs_device = self.demucs_device_var.get()
            if demucs_device == "auto":
                demucs_device = None
            results = youtube_to_midi(
                url,
                cancel_token=self.convert_cancel_token,
                demucs_device=demucs_device,
                convert_vocals_midi=bool(self.convert_vocals_midi_var.get()),
            )
            self._queue_conversion_result(results)
        except CancelledError:
            self.queue.put(("convert_cancelled", None))
        except Exception as exc:
            self.queue.put(("convert_error", format_command_error(exc)))

    def local_audio_convert_worker(self, filename):
        try:
            check_cli_dependencies()
            self.queue.put(("status", "Converting local audio"))
            demucs_device = self.demucs_device_var.get()
            if demucs_device == "auto":
                demucs_device = None
            results = audio_file_to_midi(
                filename,
                cancel_token=self.convert_cancel_token,
                demucs_device=demucs_device,
                convert_vocals_midi=bool(self.convert_vocals_midi_var.get()),
            )
            self._queue_conversion_result(results)
        except CancelledError:
            self.queue.put(("convert_cancelled", None))
        except Exception as exc:
            self.queue.put(("convert_error", format_command_error(exc)))

    def _queue_conversion_result(self, results):
        self.queue.put(("log", f"Output folder: {results['base_dir']}"))
        if results.get("cached"):
            self.queue.put(("log", "Loaded cached conversion."))
        self.queue.put(("log", f"Original WAV: {results['wav_file']}"))
        self.queue.put(("log", f"Vocals MIDI: {results.get('vocal_midi')}"))
        self.queue.put(("log", f"Accompaniment MIDI: {results['accompaniment_midi']}"))
        self.queue.put(("log", f"Vocals Clean 37-Key MIDI: {results.get('vocal_clean_midi')}"))
        self.queue.put(
            ("log", f"Vocals AI Optimized MIDI: {results.get('vocal_ai_optimized_midi')}")
        )
        self.queue.put(
            (
                "log",
                f"Vocals Pitch Corrected MIDI: {results.get('vocal_pitch_corrected_midi')}",
            )
        )
        self.queue.put(("log", f"Vocals Final 37-Key MIDI: {results.get('vocal_final_midi')}"))
        self.queue.put(("log", f"Vocals detected key: {results.get('vocal_detected_key')}"))
        self.queue.put(
            (
                "log",
                f"Accompaniment Clean 37-Key MIDI: {results['accompaniment_clean_midi']}",
            )
        )
        self.queue.put(
            (
                "log",
                f"Accompaniment AI Optimized MIDI: {results['accompaniment_ai_optimized_midi']}",
            )
        )
        self.queue.put(
            (
                "log",
                "Accompaniment Pitch Corrected MIDI: "
                f"{results['accompaniment_pitch_corrected_midi']}",
            )
        )
        self.queue.put(
            ("log", f"Accompaniment Final 37-Key MIDI: {results['accompaniment_final_midi']}")
        )
        self.queue.put(
            ("log", f"Accompaniment detected key: {results.get('accompaniment_detected_key')}")
        )
        self.queue.put(("converted", results))
