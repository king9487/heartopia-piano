import tkinter as tk
from tkinter import ttk
from transpose import KEY_NAMES
from ui.optimizer_panel import build_optimizer_panel

def build_converter_tab(app):
    top = ttk.Frame(app.main_tab, padding=12)
    top.grid(row=0, column=0, sticky="ew")
    top.columnconfigure(1, weight=1)

    ttk.Label(top, text="YouTube URL").grid(row=0, column=0, sticky="w")
    url_entry = ttk.Entry(top, textvariable=app.url_var)
    url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
    url_entry.focus_set()

    app.convert_button = ttk.Button(top, text="Convert URL", command=app.start_convert)
    app.convert_button.grid(row=0, column=2, sticky="e")
    app.local_audio_button = ttk.Button(
        top, text="Open Audio", command=app.start_local_audio_convert
    )
    app.local_audio_button.grid(row=0, column=3, sticky="e", padx=(8, 0))

    options = ttk.Frame(app.main_tab, padding=(12, 0, 12, 8))
    options.grid(row=1, column=0, sticky="ew")
    options.columnconfigure(4, weight=1)

    ttk.Checkbutton(
        options,
        text="Always on top",
        variable=app.always_top_var,
        command=app.apply_topmost,
    ).grid(row=0, column=0, sticky="w")

    ttk.Label(options, text="Speed").grid(row=0, column=1, sticky="w", padx=(18, 4))
    ttk.Spinbox(
        options,
        from_=0.25,
        to=3.0,
        increment=0.25,
        textvariable=app.speed_var,
        width=6,
    ).grid(row=0, column=2, sticky="w")

    ttk.Label(options, text="Focus delay").grid(row=0, column=3, sticky="w", padx=(18, 4))
    ttk.Spinbox(
        options,
        from_=1,
        to=10,
        increment=1,
        textvariable=app.countdown_var,
        width=5,
    ).grid(row=0, column=4, sticky="w")

    ttk.Label(options, text="Demucs").grid(row=0, column=5, sticky="w", padx=(18, 4))
    ttk.Combobox(
        options,
        textvariable=app.demucs_device_var,
        values=("cuda:0", "auto", "cpu"),
        state="readonly",
        width=8,
    ).grid(row=0, column=6, sticky="w")

    ttk.Checkbutton(
        options,
        text="Convert vocals MIDI",
        variable=app.convert_vocals_midi_var,
    ).grid(row=1, column=0, sticky="w", pady=(8, 0))

    next_row = build_optimizer_panel(app, app.main_tab, 2)

    midi_panel = ttk.Frame(app.main_tab, padding=(12, 0, 12, 8))
    midi_panel.grid(row=next_row, column=0, sticky="ew")
    midi_panel.columnconfigure(5, weight=1)

    ttk.Radiobutton(
        midi_panel,
        text="Vocals MIDI",
        value="vocal_midi",
        variable=app.midi_choice_var,
        command=app.update_selected_midi,
    ).grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(
        midi_panel,
        text="Accompaniment MIDI",
        value="accompaniment_midi",
        variable=app.midi_choice_var,
        command=app.update_selected_midi,
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))

    ttk.Button(midi_panel, text="Open MIDI", command=app.open_midi).grid(
        row=0, column=2, padx=(12, 0)
    )
    ttk.Button(midi_panel, text="Open Converted", command=app.open_converted).grid(
        row=0, column=3, padx=(8, 0)
    )
    ttk.Button(midi_panel, text="Preview", command=app.preview_selected_midi).grid(
        row=0, column=4, padx=(8, 0)
    )
    app.play_button = ttk.Button(
        midi_panel, text="Play to Game", command=app.start_keyboard_playback
    )
    app.play_button.grid(row=0, column=5, sticky="e")
    app.stop_button = ttk.Button(
        midi_panel, text="Stop", command=app.stop_current_task, state="disabled"
    )
    app.stop_button.grid(row=0, column=6, sticky="e", padx=(8, 0))

    ttk.Label(midi_panel, text="Converted").grid(row=1, column=0, sticky="w", pady=(8, 0))
    app.cached_combo = ttk.Combobox(
        midi_panel, textvariable=app.cached_choice_var, state="readonly"
    )
    app.cached_combo.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))
    ttk.Button(midi_panel, text="Refresh", command=app.refresh_converted_outputs).grid(
        row=1, column=4, sticky="w", padx=(8, 0), pady=(8, 0)
    )
    ttk.Button(midi_panel, text="Load", command=app.load_selected_converted).grid(
        row=1, column=5, sticky="w", padx=(8, 0), pady=(8, 0)
    )
    ttk.Label(midi_panel, text="MIDI source").grid(row=2, column=0, sticky="w", pady=(8, 0))
    app.midi_source_combo = ttk.Combobox(
        midi_panel,
        textvariable=app.midi_source_var,
        state="readonly",
        width=24,
    )
    app.midi_source_combo.grid(
        row=2, column=1, columnspan=3, sticky="w", padx=(8, 0), pady=(8, 0)
    )
    app.midi_source_combo.bind(
        "<<ComboboxSelected>>", app.on_midi_source_selected
    )
    ttk.Label(midi_panel, text="Optimizer").grid(row=2, column=4, sticky="e", pady=(8, 0))
    ttk.Combobox(
        midi_panel,
        textvariable=app.optimizer_mode_var,
        values=("None", "Rule", "OpenAI"),
        state="readonly",
        width=8,
    ).grid(row=2, column=5, sticky="w", padx=(4, 0), pady=(8, 0))
    ttk.Button(midi_panel, text="Optimize MIDI", command=app.start_optimize_midi).grid(
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
        textvariable=app.range_start_var,
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
        textvariable=app.range_end_var,
        width=8,
    ).grid(row=3, column=3, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Button(midi_panel, text="Play Range", command=app.start_range_playback).grid(
        row=3, column=4, sticky="e", padx=(8, 0), pady=(8, 0)
    )
    ttk.Button(midi_panel, text="Export Range", command=app.export_selected_range).grid(
        row=3, column=5, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0)
    )

    selected = ttk.Label(
        app.main_tab,
        textvariable=app.selected_midi_var,
        padding=(12, 0, 12, 8),
        foreground="#444",
    )
    selected.grid(row=next_row + 1, column=0, sticky="new")

    log_frame = ttk.Frame(app.main_tab, padding=(12, 0, 12, 8))
    log_frame.grid(row=next_row + 2, column=0, sticky="nsew")
    log_frame.columnconfigure(0, weight=1)
    log_frame.rowconfigure(0, weight=1)

    app.log = tk.Text(log_frame, height=16, wrap="word", state="disabled")
    app.log.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(log_frame, command=app.log.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    app.log.configure(yscrollcommand=scrollbar.set)

    status = ttk.Label(
        app.main_tab, textvariable=app.status_var, padding=(12, 0, 12, 12)
    )
    status.grid(row=next_row + 3, column=0, sticky="ew")

    app.main_tab.rowconfigure(next_row + 2, weight=1)
