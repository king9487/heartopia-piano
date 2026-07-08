import threading
from tkinter import messagebox

from converter import rebuild_midi_stages
from keyboard_profiles import get_keyboard_profile, processing_options_for_profile
from midi_ai_optimizer import post_process_37key_midi
from ui.presets import apply_processing_preset


class UiOptimizerActionsMixin:
    def on_keyboard_profile_changed(self, event=None):
        profile = get_keyboard_profile(self.keyboard_profile_var.get())
        self.keyboard_profile_var.set(profile.name)
        if "Keyboard Profile" in self.analysis_vars:
            self.analysis_vars["Keyboard Profile"].set(
                f"{profile.name} ({profile.range_label})"
            )

    def on_processing_preset_changed(self, event=None):
        preset = self.processing_preset_var.get()
        apply_processing_preset(self, preset)
        self.log_message(f"Processing preset applied: {preset}")

    def get_processing_options(self):
        return {
            "mode": self.optimizer_mode_var.get().strip().lower(),
            "arrangement_style": self.arrangement_style_var.get().strip().lower(),
            "max_notes_per_window": max(1, min(int(self.melody_max_notes_var.get()), 3)),
            "arrangement_window_ms": int(self.melody_window_var.get()),
            "min_note_duration_ms": int(self.min_note_duration_var.get()),
            "velocity_threshold": int(self.velocity_threshold_var.get()),
            "max_simultaneous_notes": int(self.max_simultaneous_var.get()),
            "out_of_range_mode": self.octave_fit_var.get(),
            "prefer_melody": True,
            **processing_options_for_profile(self.keyboard_profile_var.get()),
        }

    def _raw_midi_for_rebuild(self):
        if self.results:
            raw_key = self.midi_choice_var.get()
            raw_midi = self.results.get(raw_key)
            if raw_midi:
                return raw_midi
        selected = self.get_selected_midi()
        if selected and selected.name.lower() not in {
            "edited_37key.mid", "clean_37key.mid", "piano_arranged_37key.mid",
            "piano_cover_37key.mid", "ai_optimized_37key.mid",
            "pitch_corrected_37key.mid", "final_37key.mid",
        }:
            return selected
        messagebox.showwarning("Raw MIDI unavailable", "Load a conversion with its Raw MIDI before rebuilding stages.")
        return None

    def start_rebuild_stage(self, stage):
        raw_midi = self._raw_midi_for_rebuild()
        if not raw_midi:
            return
        try:
            options = self.get_processing_options()
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Processing settings must be numbers.")
            return
        label = stage.replace("_", " ").title()
        self.status_var.set(f"Rebuilding {label}")
        self.log_message(f"Rebuild requested from {label} stage: {raw_midi}")
        self.log_message(f"Keyboard profile: {options['keyboard_profile']}")
        threading.Thread(
            target=self.rebuild_stage_worker,
            args=(raw_midi, stage, options),
            daemon=True,
        ).start()

    def rebuild_stage_worker(self, raw_midi, stage, options):
        try:
            result = rebuild_midi_stages(raw_midi, stage, options=options)
            self.queue.put(("rebuild_done", result))
        except Exception as exc:
            self.queue.put(("rebuild_error", str(exc)))

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
                **processing_options_for_profile(self.keyboard_profile_var.get()),
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
        self.log_message(f"Keyboard profile: {options['keyboard_profile']}")
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
