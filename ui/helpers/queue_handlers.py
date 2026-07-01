import queue
from tkinter import messagebox


class UiQueueHandlersMixin:
    """Dispatch background-worker messages on the Tk main thread."""

    def poll_queue(self):
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            self.handle_queue_message(kind, payload)

        self.root.after(100, self.poll_queue)

    def handle_queue_message(self, kind, payload):
        handler = {
            "log": self._handle_log_message,
            "status": self._handle_status_message,
            "converted": self._handle_converted,
            "convert_error": self._handle_convert_error,
            "convert_cancelled": self._handle_convert_cancelled,
            "play_done": self._handle_play_done,
            "play_error": self._handle_play_error,
            "optimize_done": self._handle_optimize_done,
            "optimize_error": self._handle_optimize_error,
        }.get(kind)
        if handler is not None:
            handler(payload)

    def _restore_conversion_buttons(self):
        assert self.convert_button is not None
        self.convert_button.configure(state="normal")
        assert self.local_audio_button is not None
        self.local_audio_button.configure(state="normal")
        assert self.stop_button is not None
        self.stop_button.configure(state="disabled")

    def _restore_playback_buttons(self):
        assert self.play_button is not None
        self.play_button.configure(state="normal")
        assert self.stop_button is not None
        self.stop_button.configure(state="disabled")

    def _handle_log_message(self, payload):
        self.log_message(payload)

    def _handle_status_message(self, payload):
        self.set_status(payload)

    def _handle_converted(self, payload):
        self.results = payload
        self.converting = False
        self.convert_cancel_token = None
        self.update_selected_midi()
        self.on_key_transpose_changed()
        self.refresh_converted_outputs()
        self._restore_conversion_buttons()
        self.set_status("Conversion finished")

    def _handle_convert_error(self, payload):
        self.converting = False
        self.convert_cancel_token = None
        self._restore_conversion_buttons()
        self.set_status("Conversion failed")
        messagebox.showerror("Conversion failed", payload)

    def _handle_convert_cancelled(self, payload):
        self.converting = False
        self.convert_cancel_token = None
        self._restore_conversion_buttons()
        self.set_status("Conversion cancelled")
        self.log_message("Conversion cancelled.")

    def _finish_playback(self, status):
        self.playing = False
        self.unregister_stop_hotkey()
        self._restore_playback_buttons()
        self.root.deiconify()
        self.apply_topmost()
        self.set_status(status)

    def _handle_play_done(self, payload):
        self._finish_playback("Keyboard playback finished")

    def _handle_play_error(self, payload):
        self._finish_playback("Keyboard playback failed")
        messagebox.showerror("Keyboard playback failed", payload)

    def _handle_optimize_done(self, payload):
        if self.results:
            self.update_selected_midi()
        else:
            self.configure_midi_sources_from_path(payload["final_midi"])
        self.set_status("MIDI optimized")
        if payload.get("piano_cover_midi"):
            self.log_message(f"Piano Cover MIDI: {payload['piano_cover_midi']}")
        if payload.get("ai_optimized_midi"):
            self.log_message(f"AI optimized MIDI: {payload['ai_optimized_midi']}")
        if payload.get("pitch_corrected_midi"):
            self.log_message(f"Pitch corrected MIDI: {payload['pitch_corrected_midi']}")
        self.log_message(f"Final 37-Key MIDI: {payload['final_midi']}")
        self.log_message(f"Detected key: {payload['detected_key']}")

    def _handle_optimize_error(self, payload):
        self.set_status("MIDI optimization failed")
        messagebox.showerror("MIDI optimization failed", payload)
