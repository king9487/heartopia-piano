from tkinter import ttk


def build_midi_panel(app, parent, row):
    actions = ttk.Frame(parent, padding=(12, 0, 12, 8))
    actions.grid(row=row, column=0, sticky="ew")
    actions.columnconfigure(6, weight=1)
    ttk.Button(actions, text="Open MIDI", command=app.open_midi).grid(row=0, column=0)
    ttk.Button(actions, text="Open Converted", command=app.open_converted).grid(
        row=0, column=1, padx=(8, 0)
    )
    ttk.Button(actions, text="Preview", command=app.preview_selected_midi).grid(
        row=0, column=2, padx=(8, 0)
    )
    app.play_button = ttk.Button(
        actions, text="Play to Game", command=app.start_keyboard_playback
    )
    app.play_button.grid(row=0, column=3, padx=(8, 0))
    app.stop_button = ttk.Button(
        actions, text="Stop", command=app.stop_current_task, state="disabled"
    )
    app.stop_button.grid(row=0, column=4, padx=(8, 0))

    sources = ttk.LabelFrame(parent, text="Current MIDI source / version", padding=10)
    sources.grid(row=row + 1, column=0, sticky="ew", padx=12, pady=(0, 8))
    sources.columnconfigure(3, weight=1)
    ttk.Radiobutton(
        sources, text="Vocals MIDI", value="vocal_midi",
        variable=app.midi_choice_var, command=app.update_selected_midi,
    ).grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(
        sources, text="Accompaniment MIDI", value="accompaniment_midi",
        variable=app.midi_choice_var, command=app.update_selected_midi,
    ).grid(row=0, column=1, sticky="w", padx=(12, 0))

    ttk.Label(sources, text="Converted").grid(row=1, column=0, sticky="w", pady=(8, 0))
    app.cached_combo = ttk.Combobox(
        sources, textvariable=app.cached_choice_var, state="readonly"
    )
    app.cached_combo.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(8, 0))
    ttk.Button(sources, text="Refresh", command=app.refresh_converted_outputs).grid(
        row=1, column=3, sticky="w", padx=(8, 0), pady=(8, 0)
    )
    ttk.Button(sources, text="Load", command=app.load_selected_converted).grid(
        row=1, column=4, sticky="w", padx=(8, 0), pady=(8, 0)
    )

    ttk.Label(sources, text="MIDI source").grid(row=2, column=0, sticky="w", pady=(8, 0))
    app.midi_source_combo = ttk.Combobox(
        sources, textvariable=app.midi_source_var, state="readonly", width=28
    )
    app.midi_source_combo.grid(
        row=2, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0)
    )
    app.midi_source_combo.bind("<<ComboboxSelected>>", app.on_midi_source_selected)
    return row + 2
