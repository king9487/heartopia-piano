import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

from converter import audio_file_to_midi, import_external_midi, youtube_to_midi
from midi_analysis import inspect_midi_file
from tools import (
    CancellationToken,
    CancelledError,
    check_cli_dependencies,
    format_command_error,
)


class UiConvertActionsMixin:
    """UI callbacks and background work for URL/local-audio conversion."""

    def on_input_source_changed(self):
        frames = {
            "youtube": self.youtube_input_frame,
            "local_audio": self.local_audio_input_frame,
            "external_midi": self.external_midi_input_frame,
        }
        selected = self.input_source_var.get()
        for name, frame in frames.items():
            if frame is not None:
                (frame.grid if name == selected else frame.grid_remove)()

    def _begin_conversion(self, status, log_message, preserve_sources=False):
        assert self.convert_button is not None
        self.convert_button.configure(state="disabled")
        assert self.local_audio_button is not None
        self.local_audio_button.configure(state="disabled")
        if self.external_midi_button is not None:
            self.external_midi_button.configure(state="disabled")
        if self.process_external_midi_button is not None:
            self.process_external_midi_button.configure(state="disabled")
        assert self.stop_button is not None
        self.stop_button.configure(state="normal")
        if not preserve_sources:
            self.results = None
            self.clear_midi_source_options()
        self.converting = True
        self.convert_cancel_token = CancellationToken()
        self.status_var.set(status)
        self.log_message(log_message)

    def start_convert(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube URL first.")
            return

        self._begin_conversion("Checking dependencies", "Starting conversion...")

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

        self._begin_conversion(
            "Checking dependencies", f"Starting local audio conversion: {filename}"
        )

        thread = threading.Thread(
            target=self.local_audio_convert_worker, args=(filename,), daemon=True
        )
        thread.start()

    def browse_external_midi(self):
        filename = filedialog.askopenfilename(
            title="Import external MIDI",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if not filename:
            return
        for variable in self.external_midi_info_vars.values():
            variable.set("--")
        try:
            metadata = inspect_midi_file(filename)
        except Exception as exc:
            self.external_midi_path_var.set("")
            self.results = None
            self.clear_midi_source_options()
            for button in (
                self.process_external_midi_button,
                self.preview_original_midi_button,
                self.play_original_midi_button,
                self.open_original_midi_button,
            ):
                if button is not None:
                    button.configure(state="disabled")
            messagebox.showerror("Invalid MIDI", str(exc))
            return
        self.results = None
        self.clear_midi_source_options()
        self.external_midi_path_var.set(filename)
        self.show_external_midi_metadata(metadata)
        self.results = {
            "input_source": "external_midi",
            "source_midi": Path(filename),
            "imported_midi": Path(filename),
        }
        self.update_selected_midi()
        for button in (
            self.process_external_midi_button,
            self.preview_original_midi_button,
            self.play_original_midi_button,
            self.open_original_midi_button,
        ):
            if button is not None:
                button.configure(state="normal")
        self.status_var.set("Imported MIDI selected")
        self.log_message(f"Imported MIDI ready for direct playback: {filename}")

    def show_external_midi_metadata(self, metadata):
        total_notes = metadata["total_notes"]
        playable_notes = metadata["notes_inside_map"]
        playable_percentage = (
            (playable_notes / total_notes) * 100 if total_notes else 0.0
        )
        if playable_percentage > 90:
            recommended = "Direct Play"
        elif playable_percentage < 80:
            recommended = "Optimize for Heartopia"
        else:
            recommended = "Either workflow"
        display = {
            "file_name": metadata["file_name"],
            "duration": f"{metadata['duration']:.3f} s",
            "bpm": (
                f"{metadata['bpm']:g} BPM"
                if metadata["bpm"] is not None
                else "Not available"
            ),
            "key": metadata["key"] or "Unknown",
            "ppq": metadata["ppq"],
            "tracks": metadata["tracks"],
            "total_notes": metadata["total_notes"],
            "notes_inside_map": (
                f"{playable_notes} / {total_notes} ({playable_percentage:.1f}%)"
            ),
            "notes_outside_map": metadata["notes_outside_map"],
            "playable_percentage": f"{playable_percentage:.1f}%",
            "recommended": recommended,
        }
        for key, value in display.items():
            self.external_midi_info_vars[key].set(str(value))

    def get_imported_original_midi(self):
        filename = self.external_midi_path_var.get().strip()
        midi_path = Path(filename) if filename else None
        if not midi_path or not midi_path.is_file():
            messagebox.showerror("Imported MIDI not found", filename or "No MIDI selected")
            return None
        return midi_path

    def preview_original_midi(self):
        midi_path = self.get_imported_original_midi()
        if midi_path:
            self.preview_selected_midi(midi_path=midi_path)

    def play_original_midi(self):
        midi_path = self.get_imported_original_midi()
        if midi_path:
            self.start_playback(midi_path=midi_path)

    def open_original_midi(self):
        midi_path = self.get_imported_original_midi()
        if not midi_path:
            return
        try:
            os.startfile(midi_path)
        except OSError as exc:
            messagebox.showerror("Unable to open MIDI", str(exc))

    def start_external_midi_import(self):
        filename = self.external_midi_path_var.get().strip()
        if not filename:
            messagebox.showwarning("No MIDI selected", "Browse for a MIDI file first.")
            return
        try:
            options = self.get_processing_options()
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Processing settings must be numbers.")
            return
        skips = {
            "cleanup": bool(self.skip_cleanup_var.get()),
            "piano_arranger": bool(self.skip_piano_arranger_var.get()),
            "ai_optimizer": bool(self.skip_ai_optimizer_var.get()),
            "pitch_correction": bool(self.skip_pitch_correction_var.get()),
        }
        self._begin_conversion(
            "Processing imported MIDI...",
            f"Processing imported MIDI: {filename}",
            preserve_sources=True,
        )
        threading.Thread(
            target=self.external_midi_import_worker,
            args=(filename, options, skips),
            daemon=True,
        ).start()

    def external_midi_import_worker(self, filename, options, skips):
        try:
            result = import_external_midi(
                filename,
                options=options,
                skips=skips,
                progress_callback=lambda message: self.queue.put(("log", message)),
            )
            self.queue.put(("external_midi_done", result))
        except Exception as exc:
            self.queue.put(("convert_error", format_command_error(exc)))

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
        if results.get("accompaniment_report_path"):
            self.queue.put(
                ("log", f"MIDI analysis report: {results['accompaniment_report_path']}")
            )
        self.queue.put(("converted", results))
