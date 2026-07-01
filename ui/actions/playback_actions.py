import threading
from tkinter import messagebox

import keyboard

from midi_to_keyboard import iter_note_events, midi_note_name, play_midi_as_keyboard


class UiPlaybackActionsMixin:
    """Preview and game-keyboard playback actions."""

    def get_cleanup_settings(self):
        try:
            min_note_duration = int(self.min_note_duration_var.get())
            velocity_threshold = int(self.velocity_threshold_var.get())
            max_simultaneous_notes = int(self.max_simultaneous_var.get())
            melody_max_notes = int(self.melody_max_notes_var.get())
            melody_window = int(self.melody_window_var.get())
            settings = {
                "transpose": int(self.transpose_var.get()),
                "min_note_duration": min_note_duration / 1000,
                "velocity_threshold": velocity_threshold,
                "max_simultaneous_notes": max_simultaneous_notes,
                "out_of_range_mode": self.octave_fit_var.get(),
                "melody_only": bool(self.melody_only_var.get()),
                "melody_max_notes": melody_max_notes,
                "melody_window": melody_window / 1000,
            }
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Cleanup settings must be numbers.")
            return None

        if (
            min_note_duration < 0
            or velocity_threshold < 0
            or velocity_threshold > 127
            or max_simultaneous_notes < 0
            or melody_max_notes < 1
            or melody_max_notes > 3
            or melody_window <= 0
        ):
            messagebox.showerror("Invalid setting", "Cleanup settings are out of range.")
            return None

        return settings

    def preview_selected_midi(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return

        self.log_message(f"Preview: {midi_path}")
        count = 0
        cleanup_settings = self.get_cleanup_settings()
        if cleanup_settings is None:
            return

        for timestamp, action, note, key in iter_note_events(
            midi_path, **cleanup_settings
        ):
            note_name = midi_note_name(note)
            self.log_message(
                f"{timestamp:8.3f}s  note {note:3d} {note_name:3s}  {action:4s}  key {key}"
            )
            count += 1
            if count >= 80:
                self.log_message("... preview stopped after 80 events")
                break
        if count == 0:
            self.log_message("No mapped note events found in this MIDI file.")

    def start_keyboard_playback(self):
        self.start_playback()

    def start_playback(self, start_sec=None, end_sec=None):
        midi_path = self.get_selected_midi()
        if not midi_path or self.playing:
            return

        try:
            speed = float(self.speed_var.get())
            countdown = int(self.countdown_var.get())
            chord_delay = int(self.chord_delay_var.get()) / 1000
            min_hold = int(self.min_hold_var.get()) / 1000
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Playback settings must be numbers.")
            return

        cleanup_settings = self.get_cleanup_settings()
        if cleanup_settings is None:
            return

        if speed <= 0 or countdown < 1 or chord_delay < 0 or min_hold < 0:
            messagebox.showerror("Invalid setting", "Playback settings are out of range.")
            return

        self.playing = True
        self.stop_event.clear()
        self.register_stop_hotkey()
        assert self.play_button is not None
        self.play_button.configure(state="disabled")
        assert self.stop_button is not None
        self.stop_button.configure(state="normal")
        self.status_var.set(f"Hiding window. Focus the game within {countdown} seconds.")
        if start_sec is None:
            playback_label = "Keyboard playback"
        else:
            playback_label = f"Range playback ({start_sec:g}s to {end_sec:g}s)"
        self.log_message(
            f"{playback_label} will start in {countdown} seconds. Press F8 to stop."
        )
        self.root.withdraw()

        thread = threading.Thread(
            target=self.play_worker,
            args=(
                midi_path,
                speed,
                countdown,
                chord_delay,
                min_hold,
                cleanup_settings,
                start_sec,
                end_sec,
            ),
            daemon=True,
        )
        thread.start()

    def play_worker(
        self,
        midi_path,
        speed,
        countdown,
        chord_delay,
        min_hold,
        cleanup_settings,
        start_sec=None,
        end_sec=None,
    ):
        try:
            if self.stop_event.wait(countdown):
                self.queue.put(("play_done", None))
                return
            play_midi_as_keyboard(
                midi_path,
                speed=speed,
                stop_event=self.stop_event,
                chord_delay=chord_delay,
                min_hold=min_hold,
                start_sec=start_sec,
                end_sec=end_sec,
                **cleanup_settings,
            )
            self.queue.put(("play_done", None))
        except Exception as exc:
            self.queue.put(("play_error", str(exc)))

    def stop_keyboard_playback(self, event=None):
        if self.playing:
            self.stop_event.set()
            self.status_var.set("Stopping keyboard playback")
            self.log_message("Stop requested.")

    def stop_current_task(self):
        if self.converting and self.convert_cancel_token:
            self.status_var.set("Cancelling conversion")
            self.log_message("Cancelling conversion...")
            self.convert_cancel_token.cancel()
            return

        self.stop_keyboard_playback()

    def register_stop_hotkey(self):
        self.unregister_stop_hotkey()
        self.stop_hotkey = keyboard.add_hotkey("f8", self.stop_keyboard_playback)

    def unregister_stop_hotkey(self):
        if self.stop_hotkey is not None:
            keyboard.remove_hotkey(self.stop_hotkey)
            self.stop_hotkey = None
