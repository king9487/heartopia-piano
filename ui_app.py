import bisect
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import keyboard
import mido

from converter import (
    audio_file_to_midi,
    ensure_clean_results,
    list_converted_outputs,
    results_from_output_dir,
    youtube_to_midi,
)
from midi_ai_optimizer import (
    AI_OPTIMIZED_MIDI_NAME,
    FINAL_37KEY_MIDI_NAME,
    PITCH_CORRECTED_MIDI_NAME,
    post_process_37key_midi,
)
from midi_editor import (
    EDITED_37KEY_MIDI_NAME,
    find_suspicious_notes,
    load_editor_notes,
    save_edited_midi,
)
from midi_range import CHORUS_MIDI_NAME, export_midi_range
from midi_rule_engine import CLEAN_37KEY_MIDI_NAME
from midi_to_keyboard import iter_note_events, midi_note_name, play_midi_as_keyboard
from tools import (
    CancellationToken,
    CancelledError,
    check_cli_dependencies,
    default_demucs_device,
    format_command_error,
)


MIDI_SOURCE_PRIORITY = (
    "Edited MIDI",
    "Final 37-Key MIDI",
    "Pitch Corrected MIDI",
    "AI Optimized MIDI",
    "Clean 37-Key MIDI",
    "Raw MIDI",
)
MIDI_SOURCE_FILENAMES = {
    "Edited MIDI": EDITED_37KEY_MIDI_NAME,
    "Final 37-Key MIDI": FINAL_37KEY_MIDI_NAME,
    "Pitch Corrected MIDI": PITCH_CORRECTED_MIDI_NAME,
    "AI Optimized MIDI": AI_OPTIMIZED_MIDI_NAME,
    "Clean 37-Key MIDI": CLEAN_37KEY_MIDI_NAME,
}


class YoutubeMidiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube MIDI Keyboard")
        self.root.geometry("820x620")
        self.root.minsize(660, 480)
        self.root.attributes("-topmost", True)

        self.queue = queue.Queue()
        self.results = None
        self.converting = False
        self.convert_cancel_token = None
        self.playing = False
        self.stop_event = threading.Event()
        self.stop_hotkey = None

        self.url_var = tk.StringVar()
        self.always_top_var = tk.BooleanVar(value=True)
        self.midi_choice_var = tk.StringVar(value="accompaniment_midi")
        self.midi_source_var = tk.StringVar()
        self.available_midi_sources = {}
        self.convert_vocals_midi_var = tk.BooleanVar(value=False)
        self.selected_midi_var = tk.StringVar()
        self.cached_choice_var = tk.StringVar()
        self.cached_outputs = []
        self.demucs_device_var = tk.StringVar(value=default_demucs_device() or "auto")
        self.speed_var = tk.DoubleVar(value=1.0)
        self.countdown_var = tk.IntVar(value=3)
        self.transpose_var = tk.IntVar(value=0)
        self.chord_delay_var = tk.IntVar(value=18)
        self.min_hold_var = tk.IntVar(value=75)
        self.min_note_duration_var = tk.IntVar(value=35)
        self.velocity_threshold_var = tk.IntVar(value=12)
        self.max_simultaneous_var = tk.IntVar(value=0)
        self.octave_fit_var = tk.StringVar(value="smart")
        self.melody_only_var = tk.BooleanVar(value=False)
        self.melody_max_notes_var = tk.IntVar(value=1)
        self.melody_window_var = tk.IntVar(value=80)
        self.optimizer_mode_var = tk.StringVar(value="Rule")
        self.range_start_var = tk.DoubleVar(value=0.0)
        self.range_end_var = tk.DoubleVar(value=30.0)
        self.status_var = tk.StringVar(value="Ready")
        self.studio_position_var = tk.DoubleVar(value=0.0)
        self.studio_current_time_var = tk.StringVar(value="00:00.000")
        self.studio_total_time_var = tk.StringVar(value="00:00.000")
        self.studio_status_var = tk.StringVar(value="No MIDI loaded")
        self.studio_loaded_path = None
        self.studio_events = []
        self.studio_event_times = []
        self.studio_event_index = 0
        self.studio_total_duration = 0.0
        self.studio_position = 0.0
        self.studio_started_at = 0.0
        self.studio_state = "stopped"
        self.studio_output = None
        self.studio_after_id = None
        self.studio_updating_slider = False
        self.editor_source_path = None
        self.editor_notes = []
        self.editor_suspicious_reasons = {}

        self.build_ui()
        self.refresh_converted_outputs()
        self.root.bind("<F8>", self.stop_keyboard_playback)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll_queue()

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.main_tab = ttk.Frame(self.notebook)
        self.studio_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Converter")
        self.notebook.add(self.studio_tab, text="MIDI Studio")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_notebook_tab_changed)

        self.main_tab.columnconfigure(0, weight=1)
        self.main_tab.rowconfigure(6, weight=1)

        top = ttk.Frame(self.main_tab, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="YouTube URL").grid(row=0, column=0, sticky="w")
        url_entry = ttk.Entry(top, textvariable=self.url_var)
        url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        url_entry.focus_set()

        self.convert_button = ttk.Button(top, text="Convert URL", command=self.start_convert)
        self.convert_button.grid(row=0, column=2, sticky="e")
        self.local_audio_button = ttk.Button(
            top, text="Open Audio", command=self.start_local_audio_convert
        )
        self.local_audio_button.grid(row=0, column=3, sticky="e", padx=(8, 0))

        options = ttk.Frame(self.main_tab, padding=(12, 0, 12, 8))
        options.grid(row=1, column=0, sticky="ew")
        options.columnconfigure(4, weight=1)

        ttk.Checkbutton(
            options,
            text="Always on top",
            variable=self.always_top_var,
            command=self.apply_topmost,
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(options, text="Speed").grid(row=0, column=1, sticky="w", padx=(18, 4))
        ttk.Spinbox(
            options,
            from_=0.25,
            to=3.0,
            increment=0.25,
            textvariable=self.speed_var,
            width=6,
        ).grid(row=0, column=2, sticky="w")

        ttk.Label(options, text="Focus delay").grid(row=0, column=3, sticky="w", padx=(18, 4))
        ttk.Spinbox(
            options,
            from_=1,
            to=10,
            increment=1,
            textvariable=self.countdown_var,
            width=5,
        ).grid(row=0, column=4, sticky="w")

        ttk.Label(options, text="Demucs").grid(row=0, column=5, sticky="w", padx=(18, 4))
        ttk.Combobox(
            options,
            textvariable=self.demucs_device_var,
            values=("cuda:0", "auto", "cpu"),
            state="readonly",
            width=8,
        ).grid(row=0, column=6, sticky="w")

        ttk.Checkbutton(
            options,
            text="Convert vocals MIDI",
            variable=self.convert_vocals_midi_var,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        timing = ttk.Frame(self.main_tab, padding=(12, 0, 12, 8))
        timing.grid(row=2, column=0, sticky="ew")
        timing.columnconfigure(6, weight=1)

        ttk.Label(timing, text="Transpose").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            timing,
            from_=-36,
            to=36,
            increment=1,
            textvariable=self.transpose_var,
            width=6,
        ).grid(row=0, column=1, sticky="w", padx=(4, 18))

        ttk.Label(timing, text="Chord gap ms").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(
            timing,
            from_=0,
            to=80,
            increment=2,
            textvariable=self.chord_delay_var,
            width=6,
        ).grid(row=0, column=3, sticky="w", padx=(4, 18))

        ttk.Label(timing, text="Min hold ms").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(
            timing,
            from_=20,
            to=250,
            increment=5,
            textvariable=self.min_hold_var,
            width=6,
        ).grid(row=0, column=5, sticky="w", padx=(4, 0))

        cleanup = ttk.Frame(self.main_tab, padding=(12, 0, 12, 8))
        cleanup.grid(row=3, column=0, sticky="ew")
        cleanup.columnconfigure(7, weight=1)

        ttk.Label(cleanup, text="Min note ms").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            cleanup,
            from_=0,
            to=500,
            increment=5,
            textvariable=self.min_note_duration_var,
            width=6,
        ).grid(row=0, column=1, sticky="w", padx=(4, 18))

        ttk.Label(cleanup, text="Velocity").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(
            cleanup,
            from_=0,
            to=127,
            increment=1,
            textvariable=self.velocity_threshold_var,
            width=6,
        ).grid(row=0, column=3, sticky="w", padx=(4, 18))

        ttk.Label(cleanup, text="Max notes").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(
            cleanup,
            from_=0,
            to=12,
            increment=1,
            textvariable=self.max_simultaneous_var,
            width=6,
        ).grid(row=0, column=5, sticky="w", padx=(4, 18))

        ttk.Label(cleanup, text="Range mode").grid(row=0, column=6, sticky="w")
        ttk.Combobox(
            cleanup,
            textvariable=self.octave_fit_var,
            values=("smart", "drop", "octave_shift"),
            state="readonly",
            width=12,
        ).grid(row=0, column=7, sticky="w", padx=(4, 0))

        ttk.Checkbutton(
            cleanup,
            text="Melody only",
            variable=self.melody_only_var,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        ttk.Label(cleanup, text="Melody notes").grid(
            row=1, column=2, sticky="w", pady=(8, 0)
        )
        ttk.Spinbox(
            cleanup,
            from_=1,
            to=3,
            increment=1,
            textvariable=self.melody_max_notes_var,
            width=6,
        ).grid(row=1, column=3, sticky="w", padx=(4, 18), pady=(8, 0))

        ttk.Label(cleanup, text="Window ms").grid(
            row=1, column=4, sticky="w", pady=(8, 0)
        )
        ttk.Spinbox(
            cleanup,
            from_=20,
            to=250,
            increment=10,
            textvariable=self.melody_window_var,
            width=6,
        ).grid(row=1, column=5, sticky="w", padx=(4, 18), pady=(8, 0))

        midi_panel = ttk.Frame(self.main_tab, padding=(12, 0, 12, 8))
        midi_panel.grid(row=4, column=0, sticky="ew")
        midi_panel.columnconfigure(5, weight=1)

        ttk.Radiobutton(
            midi_panel,
            text="Vocals MIDI",
            value="vocal_midi",
            variable=self.midi_choice_var,
            command=self.update_selected_midi,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            midi_panel,
            text="Accompaniment MIDI",
            value="accompaniment_midi",
            variable=self.midi_choice_var,
            command=self.update_selected_midi,
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))

        ttk.Button(midi_panel, text="Open MIDI", command=self.open_midi).grid(
            row=0, column=2, padx=(12, 0)
        )
        ttk.Button(midi_panel, text="Open Converted", command=self.open_converted).grid(
            row=0, column=3, padx=(8, 0)
        )
        ttk.Button(midi_panel, text="Preview", command=self.preview_selected_midi).grid(
            row=0, column=4, padx=(8, 0)
        )
        self.play_button = ttk.Button(
            midi_panel, text="Play to Game", command=self.start_keyboard_playback
        )
        self.play_button.grid(row=0, column=5, sticky="e")
        self.stop_button = ttk.Button(
            midi_panel, text="Stop", command=self.stop_current_task, state="disabled"
        )
        self.stop_button.grid(row=0, column=6, sticky="e", padx=(8, 0))

        ttk.Label(midi_panel, text="Converted").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.cached_combo = ttk.Combobox(
            midi_panel, textvariable=self.cached_choice_var, state="readonly"
        )
        self.cached_combo.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(midi_panel, text="Refresh", command=self.refresh_converted_outputs).grid(
            row=1, column=4, sticky="w", padx=(8, 0), pady=(8, 0)
        )
        ttk.Button(midi_panel, text="Load", command=self.load_selected_converted).grid(
            row=1, column=5, sticky="w", padx=(8, 0), pady=(8, 0)
        )
        ttk.Label(midi_panel, text="MIDI source").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.midi_source_combo = ttk.Combobox(
            midi_panel,
            textvariable=self.midi_source_var,
            state="readonly",
            width=24,
        )
        self.midi_source_combo.grid(
            row=2, column=1, columnspan=3, sticky="w", padx=(8, 0), pady=(8, 0)
        )
        self.midi_source_combo.bind(
            "<<ComboboxSelected>>", self.on_midi_source_selected
        )
        ttk.Label(midi_panel, text="Optimizer").grid(row=2, column=4, sticky="e", pady=(8, 0))
        ttk.Combobox(
            midi_panel,
            textvariable=self.optimizer_mode_var,
            values=("None", "Rule", "OpenAI"),
            state="readonly",
            width=8,
        ).grid(row=2, column=5, sticky="w", padx=(4, 0), pady=(8, 0))
        ttk.Button(midi_panel, text="Optimize MIDI", command=self.start_optimize_midi).grid(
            row=2, column=6, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        ttk.Label(midi_panel, text="Start seconds").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Spinbox(
            midi_panel,
            from_=0,
            to=86400,
            increment=1,
            textvariable=self.range_start_var,
            width=8,
        ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Label(midi_panel, text="End seconds").grid(
            row=3, column=2, sticky="e", padx=(12, 0), pady=(8, 0)
        )
        ttk.Spinbox(
            midi_panel,
            from_=0.1,
            to=86400,
            increment=1,
            textvariable=self.range_end_var,
            width=8,
        ).grid(row=3, column=3, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Button(midi_panel, text="Play Range", command=self.start_range_playback).grid(
            row=3, column=4, sticky="e", padx=(8, 0), pady=(8, 0)
        )
        ttk.Button(midi_panel, text="Export Range", command=self.export_selected_range).grid(
            row=3, column=5, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        selected = ttk.Label(
            self.main_tab,
            textvariable=self.selected_midi_var,
            padding=(12, 0, 12, 8),
            foreground="#444",
        )
        selected.grid(row=5, column=0, sticky="new")

        log_frame = ttk.Frame(self.main_tab, padding=(12, 0, 12, 8))
        log_frame.grid(row=6, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(log_frame, height=16, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        status = ttk.Label(
            self.main_tab, textvariable=self.status_var, padding=(12, 0, 12, 12)
        )
        status.grid(row=7, column=0, sticky="ew")

        self.build_midi_studio_ui()

    def build_midi_studio_ui(self):
        self.studio_tab.columnconfigure(0, weight=1)
        self.studio_tab.rowconfigure(3, weight=1)

        source = ttk.Frame(self.studio_tab, padding=(12, 12, 12, 8))
        source.grid(row=0, column=0, sticky="ew")
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Selected MIDI").grid(row=0, column=0, sticky="w")
        ttk.Label(source, textvariable=self.selected_midi_var, foreground="#444").grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        controls = ttk.Frame(self.studio_tab, padding=(12, 0, 12, 8))
        controls.grid(row=1, column=0, sticky="ew")
        controls.columnconfigure(6, weight=1)
        self.studio_play_button = ttk.Button(
            controls, text="Play", command=self.play_studio_midi
        )
        self.studio_play_button.grid(row=0, column=0, sticky="w")
        self.studio_pause_button = ttk.Button(
            controls, text="Pause", command=self.pause_studio_midi, state="disabled"
        )
        self.studio_pause_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.studio_stop_button = ttk.Button(
            controls, text="Stop", command=self.stop_studio_midi, state="disabled"
        )
        self.studio_stop_button.grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Label(controls, textvariable=self.studio_current_time_var).grid(
            row=0, column=3, sticky="e", padx=(20, 4)
        )
        ttk.Label(controls, text="/").grid(row=0, column=4)
        ttk.Label(controls, textvariable=self.studio_total_time_var).grid(
            row=0, column=5, sticky="w", padx=(4, 0)
        )
        ttk.Label(controls, textvariable=self.studio_status_var).grid(
            row=0, column=6, sticky="e", padx=(16, 0)
        )

        self.studio_seek = ttk.Scale(
            self.studio_tab,
            from_=0,
            to=1,
            variable=self.studio_position_var,
            command=self.on_studio_seek,
        )
        self.studio_seek.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

        editor = ttk.Frame(self.studio_tab, padding=(12, 0, 12, 8))
        editor.grid(row=3, column=0, sticky="nsew")
        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(1, weight=1)

        editor_actions = ttk.Frame(editor)
        editor_actions.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Button(
            editor_actions,
            text="Open Selected MIDI",
            command=self.open_selected_midi_in_editor,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            editor_actions,
            text="Delete selected notes",
            command=self.delete_selected_editor_notes,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Button(
            editor_actions,
            text="Delete same pitch",
            command=self.delete_same_pitch_editor_notes,
        ).grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Button(
            editor_actions,
            text="Delete suspicious notes",
            command=self.delete_suspicious_editor_notes,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            editor_actions,
            text="Save as edited_37key.mid",
            command=self.save_editor_midi,
        ).grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0))

        columns = (
            "start_ms",
            "duration_ms",
            "note",
            "note_name",
            "velocity",
            "suspicious_reason",
        )
        self.editor_tree = ttk.Treeview(
            editor,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        headings = {
            "start_ms": "start_ms",
            "duration_ms": "duration_ms",
            "note": "note",
            "note_name": "note_name",
            "velocity": "velocity",
            "suspicious_reason": "suspicious_reason",
        }
        widths = {
            "start_ms": 90,
            "duration_ms": 95,
            "note": 55,
            "note_name": 75,
            "velocity": 65,
            "suspicious_reason": 260,
        }
        for column in columns:
            self.editor_tree.heading(column, text=headings[column])
            self.editor_tree.column(
                column,
                width=widths[column],
                minwidth=45,
                stretch=column == "suspicious_reason",
                anchor="w" if column == "suspicious_reason" else "center",
            )
        self.editor_tree.tag_configure("suspicious", foreground="#b42318")
        self.editor_tree.grid(row=1, column=0, sticky="nsew")
        editor_scrollbar = ttk.Scrollbar(
            editor, orient="vertical", command=self.editor_tree.yview
        )
        editor_scrollbar.grid(row=1, column=1, sticky="ns")
        self.editor_tree.configure(yscrollcommand=editor_scrollbar.set)

        self.studio_canvas = tk.Canvas(
            self.studio_tab,
            background="#202225",
            highlightthickness=0,
            height=80,
        )
        self.studio_canvas.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))

    def open_selected_midi_in_editor(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return
        try:
            self.editor_notes = load_editor_notes(midi_path)
        except Exception as exc:
            messagebox.showerror("MIDI Editor", f"Could not read MIDI:\n{exc}")
            return

        self.editor_source_path = midi_path
        self.refresh_editor_tree()
        self.studio_status_var.set(f"Editor: {len(self.editor_notes)} notes")

    def refresh_editor_tree(self):
        self.editor_suspicious_reasons = find_suspicious_notes(self.editor_notes)
        children = self.editor_tree.get_children()
        if children:
            self.editor_tree.delete(*children)
        for index, note in enumerate(self.editor_notes):
            reason = self.editor_suspicious_reasons.get(index, "")
            tags = ("suspicious",) if reason else ()
            self.editor_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    int(round(note.start * 1000)),
                    int(round(note.duration_ms)),
                    note.note,
                    midi_note_name(note.note),
                    note.velocity,
                    reason,
                ),
                tags=tags,
            )

    def selected_editor_indices(self):
        return {int(item_id) for item_id in self.editor_tree.selection()}

    def delete_selected_editor_notes(self):
        selected = self.selected_editor_indices()
        if not selected:
            messagebox.showwarning("MIDI Editor", "Select one or more notes first.")
            return
        self.editor_notes = [
            note for index, note in enumerate(self.editor_notes) if index not in selected
        ]
        self.refresh_editor_tree()

    def delete_same_pitch_editor_notes(self):
        selected = self.selected_editor_indices()
        if not selected:
            messagebox.showwarning("MIDI Editor", "Select a pitch first.")
            return
        pitches = {self.editor_notes[index].note for index in selected}
        self.editor_notes = [
            note for note in self.editor_notes if note.note not in pitches
        ]
        self.refresh_editor_tree()

    def delete_suspicious_editor_notes(self):
        suspicious = set(find_suspicious_notes(self.editor_notes))
        if not suspicious:
            messagebox.showinfo("MIDI Editor", "No suspicious notes were found.")
            return
        self.editor_notes = [
            note
            for index, note in enumerate(self.editor_notes)
            if index not in suspicious
        ]
        self.refresh_editor_tree()

    def save_editor_midi(self):
        if self.editor_source_path is None:
            messagebox.showwarning("MIDI Editor", "Open the selected MIDI first.")
            return

        output_path = self.editor_source_path.parent / EDITED_37KEY_MIDI_NAME
        if output_path.resolve() == self.editor_source_path.resolve():
            messagebox.showerror(
                "MIDI Editor",
                "The selected MIDI is already edited_37key.mid. Open its original source "
                "before saving so it is not overwritten.",
            )
            return
        try:
            save_edited_midi(self.editor_notes, output_path)
        except Exception as exc:
            messagebox.showerror("MIDI Editor", f"Could not save MIDI:\n{exc}")
            return

        self.stop_studio_midi()
        self.studio_loaded_path = None
        if self.results:
            self.update_selected_midi()
        else:
            self.configure_midi_sources_from_path(output_path)
        self.studio_status_var.set("Edited MIDI saved")
        self.log_message(f"Edited 37-Key MIDI: {output_path}")

    def apply_topmost(self):
        self.root.attributes("-topmost", self.always_top_var.get())

    @staticmethod
    def format_studio_time(seconds):
        milliseconds = max(0, int(round(float(seconds) * 1000)))
        minutes, remainder = divmod(milliseconds, 60000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"

    def on_notebook_tab_changed(self, event=None):
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
            self.studio_output = mido.open_output()  # type: ignore[attr-defined]
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
        self.studio_play_button.configure(state="disabled")
        self.studio_pause_button.configure(state="normal")
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
        self.studio_play_button.configure(state="normal")
        self.studio_pause_button.configure(state="disabled")
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
        if hasattr(self, "studio_play_button"):
            self.studio_play_button.configure(state="normal")
            self.studio_pause_button.configure(state="disabled")
            self.studio_stop_button.configure(state="disabled")
        if self.studio_loaded_path is not None:
            self.studio_status_var.set("Stopped")

    def send_studio_all_notes_off(self):
        if self.studio_output is None:
            return
        try:
            for channel in range(16):
                self.studio_output.send(
                    mido.Message("control_change", channel=channel, control=123, value=0)
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
        self.studio_play_button.configure(state="normal")
        self.studio_pause_button.configure(state="disabled")
        self.studio_stop_button.configure(state="disabled")
        self.studio_status_var.set("Finished")

    def on_close(self):
        self.stop_event.set()
        self.unregister_stop_hotkey()
        self.stop_studio_midi()
        self.root.destroy()

    def log_message(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll_queue(self):
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.log_message(payload)
            elif kind == "status":
                self.status_var.set(payload)
            elif kind == "converted":
                self.results = payload
                self.converting = False
                self.convert_cancel_token = None
                self.update_selected_midi()
                self.refresh_converted_outputs()
                self.convert_button.configure(state="normal")
                self.local_audio_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_var.set("Conversion finished")
            elif kind == "convert_error":
                self.converting = False
                self.convert_cancel_token = None
                self.convert_button.configure(state="normal")
                self.local_audio_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_var.set("Conversion failed")
                messagebox.showerror("Conversion failed", payload)
            elif kind == "convert_cancelled":
                self.converting = False
                self.convert_cancel_token = None
                self.convert_button.configure(state="normal")
                self.local_audio_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.status_var.set("Conversion cancelled")
                self.log_message("Conversion cancelled.")
            elif kind == "play_done":
                self.playing = False
                self.unregister_stop_hotkey()
                self.play_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.root.deiconify()
                self.apply_topmost()
                self.status_var.set("Keyboard playback finished")
            elif kind == "play_error":
                self.playing = False
                self.unregister_stop_hotkey()
                self.play_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                self.root.deiconify()
                self.apply_topmost()
                self.status_var.set("Keyboard playback failed")
                messagebox.showerror("Keyboard playback failed", payload)
            elif kind == "optimize_done":
                if self.results:
                    self.update_selected_midi()
                else:
                    self.configure_midi_sources_from_path(payload["final_midi"])
                self.status_var.set("MIDI optimized")
                self.log_message(f"AI optimized MIDI: {payload['ai_optimized_midi']}")
                self.log_message(f"Pitch corrected MIDI: {payload['pitch_corrected_midi']}")
                self.log_message(f"Final 37-Key MIDI: {payload['final_midi']}")
                self.log_message(f"Detected key: {payload['detected_key']}")
            elif kind == "optimize_error":
                self.status_var.set("MIDI optimization failed")
                messagebox.showerror("MIDI optimization failed", payload)

        self.root.after(100, self.poll_queue)

    def start_convert(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube URL first.")
            return

        self.convert_button.configure(state="disabled")
        self.local_audio_button.configure(state="disabled")
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

        self.convert_button.configure(state="disabled")
        self.local_audio_button.configure(state="disabled")
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
        except CancelledError:
            self.queue.put(("convert_cancelled", None))
        except Exception as exc:
            self.queue.put(("convert_error", format_command_error(exc)))

    def clear_midi_source_options(self):
        self.available_midi_sources = {}
        self.midi_source_combo.configure(values=())
        self.midi_source_var.set("")
        self.selected_midi_var.set("")

    def set_midi_source_options(self, sources):
        available = {}
        for label in MIDI_SOURCE_PRIORITY:
            value = sources.get(label)
            if not value:
                continue
            path = Path(value)
            if path.exists():
                available[label] = path

        self.available_midi_sources = available
        labels = tuple(available)
        self.midi_source_combo.configure(values=labels)
        if not labels:
            self.midi_source_var.set("")
            self.selected_midi_var.set("")
            return

        self.midi_source_var.set(labels[0])
        self.on_midi_source_selected()

    def collect_result_midi_sources(self):
        if not self.results:
            return {}

        raw_key = self.midi_choice_var.get()
        if not self.results.get(raw_key) and raw_key == "vocal_midi":
            self.midi_choice_var.set("accompaniment_midi")
            raw_key = "accompaniment_midi"
        prefix = "vocal" if raw_key == "vocal_midi" else "accompaniment"
        sources = {
            "Final 37-Key MIDI": self.results.get(f"{prefix}_final_midi"),
            "Pitch Corrected MIDI": self.results.get(
                f"{prefix}_pitch_corrected_midi"
            ),
            "AI Optimized MIDI": self.results.get(f"{prefix}_ai_optimized_midi"),
            "Clean 37-Key MIDI": self.results.get(f"{prefix}_clean_midi"),
            "Raw MIDI": self.results.get(raw_key),
        }
        parent_source = next((value for value in sources.values() if value), None)
        if parent_source:
            sources["Edited MIDI"] = Path(parent_source).parent / EDITED_37KEY_MIDI_NAME
        return sources

    def configure_midi_sources_from_path(self, midi_path):
        midi_path = Path(midi_path)
        sources = {
            label: midi_path.parent / filename
            for label, filename in MIDI_SOURCE_FILENAMES.items()
        }
        known_label = next(
            (
                label
                for label, filename in MIDI_SOURCE_FILENAMES.items()
                if midi_path.name.lower() == filename.lower()
            ),
            None,
        )
        if known_label:
            sources[known_label] = midi_path
        else:
            sources["Raw MIDI"] = midi_path
        self.set_midi_source_options(sources)

    def on_midi_source_selected(self, event=None):
        midi_path = self.available_midi_sources.get(self.midi_source_var.get())
        if midi_path:
            self.selected_midi_var.set(str(midi_path))

    def update_selected_midi(self):
        self.set_midi_source_options(self.collect_result_midi_sources())

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

    def get_selected_midi(self):
        value = self.selected_midi_var.get().strip()
        if not value:
            messagebox.showwarning("No MIDI selected", "Convert or open a MIDI file first.")
            return None

        midi_path = Path(value)
        if not midi_path.exists():
            messagebox.showerror("MIDI not found", str(midi_path))
            return None

        return midi_path

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

        for timestamp, action, note, key in iter_note_events(midi_path, **cleanup_settings):
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

    def start_optimize_midi(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return

        mode = self.optimizer_mode_var.get().strip().lower()
        if mode == "none":
            messagebox.showwarning("Optimizer disabled", "Choose Rule or OpenAI first.")
            return

        try:
            options = {
                "mode": mode,
                "max_notes_per_window": max(1, min(int(self.melody_max_notes_var.get()), 3)),
                "min_note_duration_ms": int(self.min_note_duration_var.get()),
            }
        except (TypeError, ValueError):
            messagebox.showerror("Invalid setting", "Optimizer settings must be numbers.")
            return

        self.status_var.set("Optimizing MIDI")
        self.log_message(f"Optimizing MIDI with {self.optimizer_mode_var.get()} mode: {midi_path}")
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

    def start_keyboard_playback(self):
        self.start_playback()

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
        self.play_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set(f"Hiding window. Focus the game within {countdown} seconds.")
        if start_sec is None:
            playback_label = "Keyboard playback"
        else:
            playback_label = f"Range playback ({start_sec:g}s to {end_sec:g}s)"
        self.log_message(f"{playback_label} will start in {countdown} seconds. Press F8 to stop.")
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


def main():
    root = tk.Tk()
    YoutubeMidiApp(root)
    root.mainloop()
