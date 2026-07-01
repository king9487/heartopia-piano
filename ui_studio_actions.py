import bisect
from pathlib import Path
import time
import tkinter as tk
from tkinter import messagebox

import mido

from midi_range import CHORUS_MIDI_NAME, export_midi_range


class UiStudioActionsMixin:
    @staticmethod
    def format_studio_time(seconds):
        milliseconds = max(0, int(round(float(seconds) * 1000)))
        minutes, remainder = divmod(milliseconds, 60000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"

    def on_notebook_tab_changed(self, event=None):
        assert self.notebook is not None
        assert self.studio_tab is not None
        if self.notebook.select() == str(self.studio_tab):
            self.load_studio_midi()

    def load_studio_midi(self, force=False):
        value = self.selected_midi_var.get().strip()
        if not value:
            self.studio_status_var.set("No MIDI selected")
            return False

        midi_path = Path(value)
        if not midi_path.exists():
            self.studio_status_var.set("MIDI not found")
            return False
        if not force and midi_path == self.studio_loaded_path:
            return True

        self.stop_studio_midi()
        try:
            midi = mido.MidiFile(midi_path)
            absolute_time = 0.0
            events = []
            for message in midi:
                absolute_time += float(message.time)
                if not message.is_meta:
                    events.append((absolute_time, message.copy(time=0)))
        except Exception as exc:
            self.studio_status_var.set("Load failed")
            messagebox.showerror("MIDI Studio", f"Could not load MIDI:\n{exc}")
            return False

        self.studio_loaded_path = midi_path
        self.studio_events = events
        self.studio_event_times = [timestamp for timestamp, _ in events]
        self.studio_total_duration = max(float(midi.length), absolute_time, 0.0)
        self.studio_event_index = 0
        self.studio_position = 0.0
        assert self.studio_seek is not None
        self.studio_seek.configure(to=max(self.studio_total_duration, 0.001))
        self.update_studio_position(0.0)
        self.studio_total_time_var.set(
            self.format_studio_time(self.studio_total_duration)
        )
        self.studio_status_var.set("Ready")
        return True

    def update_studio_position(self, position):
        self.studio_position = max(
            0.0, min(float(position), self.studio_total_duration)
        )
        self.studio_updating_slider = True
        self.studio_position_var.set(self.studio_position)
        self.studio_updating_slider = False
        self.studio_current_time_var.set(
            self.format_studio_time(self.studio_position)
        )

    def on_studio_seek(self, value):
        if self.studio_updating_slider or self.studio_loaded_path is None:
            return

        position = max(0.0, min(float(value), self.studio_total_duration))
        if self.studio_state in ("playing", "paused"):
            self.send_studio_all_notes_off()
        self.studio_event_index = bisect.bisect_left(
            self.studio_event_times, position
        )
        self.update_studio_position(position)
        if self.studio_state == "playing":
            self.studio_started_at = time.perf_counter() - position

    def open_studio_output(self):
        if self.studio_output is not None:
            return True
        try:
            self.studio_output = mido.open_output()  # type: ignore[attr-defined]  # pylint: disable=no-member
        except Exception as exc:
            self.studio_status_var.set("No MIDI output")
            messagebox.showerror(
                "MIDI Studio",
                "Could not open a MIDI output port. Install the project requirements "
                f"and make sure a MIDI synthesizer is available.\n\n{exc}",
            )
            return False
        return True

    def play_studio_midi(self):
        if not self.load_studio_midi():
            return
        if not self.studio_events or self.studio_total_duration <= 0:
            messagebox.showwarning("MIDI Studio", "This MIDI has no playable events.")
            return
        if not self.open_studio_output():
            return

        if self.studio_position >= self.studio_total_duration:
            self.studio_event_index = 0
            self.update_studio_position(0.0)

        self.studio_state = "playing"
        self.studio_started_at = time.perf_counter() - self.studio_position
        assert self.studio_play_button is not None
        self.studio_play_button.configure(state="disabled")
        assert self.studio_pause_button is not None
        self.studio_pause_button.configure(state="normal")
        assert self.studio_stop_button is not None
        self.studio_stop_button.configure(state="normal")
        self.studio_status_var.set("Playing")
        self.studio_tick()

    def pause_studio_midi(self):
        if self.studio_state != "playing":
            return

        position = min(
            self.studio_total_duration,
            time.perf_counter() - self.studio_started_at,
        )
        self.update_studio_position(position)
        self.studio_state = "paused"
        self.cancel_studio_tick()
        self.send_studio_all_notes_off()
        assert self.studio_play_button is not None
        self.studio_play_button.configure(state="normal")
        assert self.studio_pause_button is not None
        self.studio_pause_button.configure(state="disabled")
        assert self.studio_stop_button is not None
        self.studio_stop_button.configure(state="normal")
        self.studio_status_var.set("Paused")

    def stop_studio_midi(self):
        self.cancel_studio_tick()
        self.send_studio_all_notes_off()
        if self.studio_output is not None:
            try:
                self.studio_output.close()
            except Exception:
                pass
            self.studio_output = None

        self.studio_state = "stopped"
        self.studio_event_index = 0
        self.update_studio_position(0.0)
        if self.studio_play_button:
            self.studio_play_button.configure(state="normal")
        if self.studio_pause_button:
            self.studio_pause_button.configure(state="disabled")
        if self.studio_stop_button:
            self.studio_stop_button.configure(state="disabled")
        if self.studio_loaded_path is not None:
            self.studio_status_var.set("Stopped")

    def send_studio_all_notes_off(self):
        if self.studio_output is None:
            return
        try:
            for channel in range(16):
                self.studio_output.send(
                    mido.Message(
                        "control_change", channel=channel, control=123, value=0
                    )
                )
        except Exception:
            pass

    def cancel_studio_tick(self):
        if self.studio_after_id is not None:
            self.root.after_cancel(self.studio_after_id)
            self.studio_after_id = None

    def schedule_studio_tick(self):
        self.cancel_studio_tick()
        self.studio_after_id = self.root.after(50, self.studio_tick)

    def studio_tick(self):
        self.studio_after_id = None
        if self.studio_state != "playing":
            return

        position = min(
            self.studio_total_duration,
            time.perf_counter() - self.studio_started_at,
        )
        try:
            while (
                self.studio_event_index < len(self.studio_events)
                and self.studio_events[self.studio_event_index][0] <= position
            ):
                _, message = self.studio_events[self.studio_event_index]
                if self.studio_output is not None:
                    self.studio_output.send(message)
                self.studio_event_index += 1
        except Exception as exc:
            self.stop_studio_midi()
            self.studio_status_var.set("Playback failed")
            messagebox.showerror("MIDI Studio", f"MIDI playback failed:\n{exc}")
            return

        self.update_studio_position(position)
        if position >= self.studio_total_duration:
            self.finish_studio_playback()
        else:
            self.schedule_studio_tick()

    def finish_studio_playback(self):
        self.cancel_studio_tick()
        self.send_studio_all_notes_off()
        if self.studio_output is not None:
            try:
                self.studio_output.close()
            except Exception:
                pass
            self.studio_output = None
        self.studio_state = "stopped"
        self.studio_event_index = len(self.studio_events)
        self.update_studio_position(self.studio_total_duration)
        assert self.studio_play_button is not None
        self.studio_play_button.configure(state="normal")
        assert self.studio_pause_button is not None
        self.studio_pause_button.configure(state="disabled")
        assert self.studio_stop_button is not None
        self.studio_stop_button.configure(state="disabled")
        self.studio_status_var.set("Finished")

    def get_range_settings(self):
        try:
            start_sec = float(self.range_start_var.get())
            end_sec = float(self.range_end_var.get())
        except (TypeError, ValueError, tk.TclError):
            messagebox.showerror("Invalid range", "Start and end seconds must be numbers.")
            return None

        if start_sec < 0 or end_sec <= start_sec:
            messagebox.showerror(
                "Invalid range",
                "Start seconds must be 0 or greater, and end must be after start.",
            )
            return None
        return start_sec, end_sec

    def start_range_playback(self):
        midi_range = self.get_range_settings()
        if midi_range is not None:
            self.start_playback(start_sec=midi_range[0], end_sec=midi_range[1])

    def export_selected_range(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return
        midi_range = self.get_range_settings()
        if midi_range is None:
            return

        output_path = midi_path.parent / CHORUS_MIDI_NAME
        try:
            export_midi_range(midi_path, output_path, *midi_range)
        except Exception as exc:
            messagebox.showerror("Range export failed", str(exc))
            return

        self.status_var.set("MIDI range exported")
        self.log_message(f"Exported MIDI range: {output_path}")
