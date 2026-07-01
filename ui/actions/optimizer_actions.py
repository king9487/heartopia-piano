import threading
from tkinter import messagebox

from midi_ai_optimizer import post_process_37key_midi


class UiOptimizerActionsMixin:
    def start_optimize_midi(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return

        mode = self.optimizer_mode_var.get().strip().lower()
        arrangement_style = self.arrangement_style_var.get().strip().lower()
        if mode == "none" and arrangement_style == "original":
            messagebox.showwarning(
                "Optimizer disabled",
                "Choose Rule/OpenAI or select a simplified arrangement style first.",
            )
            return

        try:
            options = {
                "mode": mode,
                "arrangement_style": arrangement_style,
                "max_notes_per_window": max(
                    1, min(int(self.melody_max_notes_var.get()), 3)
                ),
                "min_note_duration_ms": int(self.min_note_duration_var.get()),
            }
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Optimizer settings must be numbers.")
            return

        self.status_var.set("Optimizing MIDI")
        self.log_message(
            "Optimizing MIDI with "
            f"{self.arrangement_style_var.get()} arrangement / "
            f"{self.optimizer_mode_var.get()} mode: {midi_path}"
        )
        thread = threading.Thread(
            target=self.optimize_worker,
            args=(midi_path, options),
            daemon=True,
        )
        thread.start()

    def optimize_worker(self, midi_path, options):
        try:
            result = post_process_37key_midi(midi_path, options=options)
            self.queue.put(("optimize_done", result))
        except Exception as exc:
            self.queue.put(("optimize_error", str(exc)))
