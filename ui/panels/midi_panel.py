from tkinter import ttk


def build_main_midi_panel(app, parent, row):
    current = ttk.LabelFrame(parent, text="Current MIDI", padding=10)
    current.grid(row=row, column=0, sticky="ew", padx=12, pady=(8, 8))
    current.columnconfigure(0, weight=1)
    ttk.Label(current, textvariable=app.selected_midi_var, foreground="#444").grid(
        row=0, column=0, sticky="ew"
    )

    actions = ttk.LabelFrame(parent, text="MIDI Actions", padding=10)
    actions.grid(row=row + 1, column=0, sticky="ew", padx=12, pady=(0, 8))
    actions.grid(row=row, column=0, sticky="ew")
    actions.columnconfigure(6, weight=1)
    app.open_midi_button = ttk.Button(actions, text="Open MIDI", command=app.open_midi)
    app.open_midi_button.grid(row=0, column=0)
    app.open_converted_button = ttk.Button(
        actions, text="Open Converted", command=app.open_converted
    )
    app.open_converted_button.grid(
        row=0, column=1, padx=(8, 0)
    )
    app.preview_button = ttk.Button(
        actions, text="Preview", command=app.preview_selected_midi
    )
    app.preview_button.grid(
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
    return row + 2


def build_midi_sources_panel(app, parent, row=0):
    sources = ttk.LabelFrame(parent, text="Current MIDI source / version", padding=10)
    app.playback_sources_frame = sources
    sources.grid(row=row, column=0, sticky="ew", padx=12, pady=(12, 8))
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

    compare = ttk.LabelFrame(parent, text="A/B Compare", padding=10)
    app.playback_compare_frame = compare
    compare.grid(row=row + 1, column=0, sticky="ew", padx=12, pady=(0, 8))
    compare.columnconfigure(1, weight=1)
    compare.columnconfigure(4, weight=1)
    ttk.Label(compare, text="A source").grid(row=0, column=0, sticky="w")
    app.compare_a_combo = ttk.Combobox(
        compare,
        textvariable=app.compare_a_source_var,
        state="readonly",
        width=24,
    )
    app.compare_a_combo.grid(row=0, column=1, sticky="ew", padx=(8, 8))
    ttk.Button(
        compare, text="Play A", command=lambda: app.play_compare_midi("A")
    ).grid(row=0, column=2, sticky="w")
    ttk.Button(
        compare, text="Set A as Current", command=lambda: app.set_compare_as_current("A")
    ).grid(row=0, column=3, sticky="w", padx=(8, 16))

    ttk.Label(compare, text="B source").grid(row=0, column=4, sticky="w")
    app.compare_b_combo = ttk.Combobox(
        compare,
        textvariable=app.compare_b_source_var,
        state="readonly",
        width=24,
    )
    app.compare_b_combo.grid(row=0, column=5, sticky="ew", padx=(8, 8))
    ttk.Button(
        compare, text="Play B", command=lambda: app.play_compare_midi("B")
    ).grid(row=0, column=6, sticky="w")
    ttk.Button(
        compare, text="Set B as Current", command=lambda: app.set_compare_as_current("B")
    ).grid(row=0, column=7, sticky="w", padx=(8, 8))
    ttk.Button(compare, text="Stop", command=app.stop_keyboard_playback).grid(
        row=0, column=8, sticky="w"
    )
    return row + 2


def build_midi_panel(app, parent, row):
    """Backward-compatible combined MIDI panel builder."""
    next_row = build_main_midi_panel(app, parent, row)
    return build_midi_sources_panel(app, parent, next_row)
