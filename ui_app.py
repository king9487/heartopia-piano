from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from converter import (
    ensure_clean_results,
    list_converted_outputs,
    results_from_output_dir,
)
from transpose import (
    TRANSPOSED_MIDI_NAME,
    transpose_midi_to_key,
)
from ui_convert_actions import UiConvertActionsMixin
from ui_editor_actions import UiEditorActionsMixin
from ui_log_helpers import UiLogHelpersMixin
from ui_main_panel import build_application_ui
from ui_optimizer_actions import UiOptimizerActionsMixin
from ui_playback_actions import UiPlaybackActionsMixin
from ui_queue_handlers import UiQueueHandlersMixin
from ui_selection import MidiSelectionMixin
from ui_state import initialize_app_state
from ui_studio_actions import UiStudioActionsMixin


class YoutubeMidiApp(
    UiConvertActionsMixin,
    UiPlaybackActionsMixin,
    UiOptimizerActionsMixin,
    UiEditorActionsMixin,
    UiStudioActionsMixin,
    UiQueueHandlersMixin,
    UiLogHelpersMixin,
    MidiSelectionMixin,
):
    # State is initialized by initialize_app_state(). These declarations keep
    # IDEs and static checkers aware of the attributes shared by the mixins.
    queue: Any
    results: Any
    converting: bool
    convert_cancel_token: Any
    playing: bool
    stop_event: Any
    stop_hotkey: Any

    url_var: Any
    always_top_var: Any
    midi_choice_var: Any
    midi_source_var: Any
    available_midi_sources: dict
    convert_vocals_midi_var: Any
    selected_midi_var: Any
    cached_choice_var: Any
    cached_outputs: list
    demucs_device_var: Any
    speed_var: Any
    countdown_var: Any
    transpose_var: Any
    chord_delay_var: Any
    min_hold_var: Any
    min_note_duration_var: Any
    velocity_threshold_var: Any
    max_simultaneous_var: Any
    octave_fit_var: Any
    melody_only_var: Any
    melody_max_notes_var: Any
    melody_window_var: Any
    optimizer_mode_var: Any
    original_key_var: Any
    target_key_var: Any
    detected_key_var: Any
    key_transpose_status_var: Any
    range_start_var: Any
    range_end_var: Any
    status_var: Any

    studio_position_var: Any
    studio_current_time_var: Any
    studio_total_time_var: Any
    studio_status_var: Any
    studio_loaded_path: Any
    studio_events: list
    studio_event_times: list
    studio_event_index: int
    studio_total_duration: float
    studio_position: float
    studio_started_at: float
    studio_state: str
    studio_output: Any
    studio_after_id: Any
    studio_updating_slider: bool
    editor_source_path: Any
    editor_notes: list
    editor_suspicious_reasons: dict

    notebook: ttk.Notebook | None
    main_tab: ttk.Frame | None
    playback_tab: ttk.Frame | None
    cleanup_tab: ttk.Frame | None
    studio_tab: ttk.Frame | None
    log: tk.Text | None
    convert_button: ttk.Button | None
    local_audio_button: ttk.Button | None
    stop_button: ttk.Button | None
    play_button: ttk.Button | None
    midi_source_combo: ttk.Combobox | None
    cached_combo: ttk.Combobox | None
    studio_seek: ttk.Scale | None
    studio_play_button: ttk.Button | None
    studio_pause_button: ttk.Button | None
    studio_stop_button: ttk.Button | None
    editor_tree: ttk.Treeview | None
    studio_canvas: tk.Canvas | None

    def __init__(self, root):
        self.root = root
        self.root.title("YouTube MIDI Keyboard")
        self.root.geometry("820x620")
        self.root.minsize(660, 480)
        self.root.attributes("-topmost", True)

        initialize_app_state(self)

        self.build_ui()
        self.refresh_converted_outputs()
        self.root.bind("<F8>", self.stop_keyboard_playback)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll_queue()

    def build_ui(self):
        build_application_ui(self)

    def apply_topmost(self):
        self.root.attributes("-topmost", self.always_top_var.get())

    def on_close(self):
        self.stop_event.set()
        self.unregister_stop_hotkey()
        self.stop_studio_midi()
        self.root.destroy()

    def on_key_transpose_changed(self, event=None):
        target_key = self.target_key_var.get()
        if target_key == "Original":
            self.key_transpose_status_var.set("Transpose: 0 semitones")
            return

        midi_path = self.get_selected_midi()
        if not midi_path:
            return

        if midi_path.name == TRANSPOSED_MIDI_NAME:
            self.key_transpose_status_var.set("Select a non-transposed MIDI first")
            return

        original_key = self.original_key_var.get()
        if original_key == "Auto Detect":
            original_key = None

        output_path = midi_path.parent / TRANSPOSED_MIDI_NAME

        try:
            result = transpose_midi_to_key(
                midi_path,
                output_path,
                original_key=original_key,
                target_key=target_key,
            )
        except Exception as exc:
            messagebox.showerror("Key Transpose failed", str(exc))
            return

        detected_key = result.get("original_key")
        semitones = result.get("semitones", 0)

        if detected_key:
            self.detected_key_var.set(f"Detected Key: {detected_key} Major")
        else:
            self.detected_key_var.set("Detected Key: Unknown")

        self.key_transpose_status_var.set(f"Transpose: {semitones:+d} semitones")
        self.update_selected_midi()

    def open_midi(self):
        filename = filedialog.askopenfilename(
            title="Open MIDI file",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if filename:
            self.results = None
            self.configure_midi_sources_from_path(filename)

    def open_converted(self):
        output_root = Path("output")
        initial_dir = output_root if output_root.exists() else Path.cwd()
        dirname = filedialog.askdirectory(
            title="Open converted output folder",
            initialdir=initial_dir,
        )
        if not dirname:
            return

        results = results_from_output_dir(dirname)
        if not results:
            messagebox.showerror(
                "Converted folder not found",
                "This folder does not contain an accompaniment MIDI file.",
            )
            return

        results = ensure_clean_results(
            results, include_vocals=bool(self.convert_vocals_midi_var.get())
        )
        self.results = results
        self.update_selected_midi()
        self.log_message(f"Loaded converted folder: {results['base_dir']}")
        self.log_message(f"Vocals MIDI: {results.get('vocal_midi')}")
        self.log_message(f"Accompaniment MIDI: {results['accompaniment_midi']}")
        self.log_message(f"Vocals Clean 37-Key MIDI: {results.get('vocal_clean_midi')}")
        self.log_message(f"Vocals AI Optimized MIDI: {results.get('vocal_ai_optimized_midi')}")
        self.log_message(f"Vocals Pitch Corrected MIDI: {results.get('vocal_pitch_corrected_midi')}")
        self.log_message(f"Vocals Final 37-Key MIDI: {results.get('vocal_final_midi')}")
        self.log_message(f"Vocals detected key: {results.get('vocal_detected_key')}")
        self.log_message(
            f"Accompaniment Clean 37-Key MIDI: {results.get('accompaniment_clean_midi')}"
        )
        self.log_message(
            f"Accompaniment AI Optimized MIDI: {results.get('accompaniment_ai_optimized_midi')}"
        )
        self.log_message(
            "Accompaniment Pitch Corrected MIDI: "
            f"{results.get('accompaniment_pitch_corrected_midi')}"
        )
        self.log_message(
            f"Accompaniment Final 37-Key MIDI: {results.get('accompaniment_final_midi')}"
        )
        self.log_message(f"Accompaniment detected key: {results.get('accompaniment_detected_key')}")
        self.status_var.set("Converted folder loaded")

    def refresh_converted_outputs(self):
        self.cached_outputs = list_converted_outputs()
        names = [path.name for path in self.cached_outputs]
        if self.cached_combo:
            self.cached_combo.configure(values=names)
        if names and self.cached_choice_var.get() not in names:
            self.cached_choice_var.set(names[0])
        elif not names:
            self.cached_choice_var.set("")

    def load_selected_converted(self):
        name = self.cached_choice_var.get()
        if not name:
            messagebox.showwarning("No converted output", "No completed conversions were found.")
            return

        for path in self.cached_outputs:
            if path.name == name:
                results = results_from_output_dir(path)
                if results:
                    results = ensure_clean_results(
                        results, include_vocals=bool(self.convert_vocals_midi_var.get())
                    )
                    self.results = results
                    self.update_selected_midi()
                    self.log_message(f"Loaded converted folder: {results['base_dir']}")
                    self.log_message(f"Vocals Clean 37-Key MIDI: {results.get('vocal_clean_midi')}")
                    self.log_message(
                        f"Vocals AI Optimized MIDI: {results.get('vocal_ai_optimized_midi')}"
                    )
                    self.log_message(
                        f"Vocals Pitch Corrected MIDI: {results.get('vocal_pitch_corrected_midi')}"
                    )
                    self.log_message(f"Vocals Final 37-Key MIDI: {results.get('vocal_final_midi')}")
                    self.log_message(f"Vocals detected key: {results.get('vocal_detected_key')}")
                    self.log_message(
                        f"Accompaniment Clean 37-Key MIDI: {results.get('accompaniment_clean_midi')}"
                    )
                    self.log_message(
                        "Accompaniment AI Optimized MIDI: "
                        f"{results.get('accompaniment_ai_optimized_midi')}"
                    )
                    self.log_message(
                        "Accompaniment Pitch Corrected MIDI: "
                        f"{results.get('accompaniment_pitch_corrected_midi')}"
                    )
                    self.log_message(
                        f"Accompaniment Final 37-Key MIDI: {results.get('accompaniment_final_midi')}"
                    )
                    self.log_message(
                        f"Accompaniment detected key: {results.get('accompaniment_detected_key')}"
                    )
                    self.status_var.set("Converted folder loaded")
                return

def main():
    root = tk.Tk()
    YoutubeMidiApp(root)
    root.mainloop()
