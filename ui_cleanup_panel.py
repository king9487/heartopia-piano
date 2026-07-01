from tkinter import ttk

from transpose import KEY_NAMES


def build_cleanup_panel(app, parent, start_row=0):
    cleanup = ttk.LabelFrame(parent, text="MIDI Cleanup", padding=12)
    cleanup.grid(row=start_row, column=0, sticky="new", padx=12, pady=(12, 8))

    fields = (
        ("Min note ms", app.min_note_duration_var, 0, 500, 5),
        ("Velocity threshold", app.velocity_threshold_var, 0, 127, 1),
        ("Max simultaneous notes", app.max_simultaneous_var, 0, 12, 1),
    )
    for row, (label, variable, low, high, increment) in enumerate(fields):
        ttk.Label(cleanup, text=label).grid(row=row, column=0, sticky="w", pady=(0, 8))
        ttk.Spinbox(
            cleanup, from_=low, to=high, increment=increment,
            textvariable=variable, width=8,
        ).grid(row=row, column=1, sticky="w", padx=(8, 24), pady=(0, 8))

    ttk.Label(cleanup, text="Range mode").grid(row=0, column=2, sticky="w", pady=(0, 8))
    ttk.Combobox(
        cleanup,
        textvariable=app.octave_fit_var,
        values=("smart", "drop", "octave_shift"),
        state="readonly",
        width=12,
    ).grid(row=0, column=3, sticky="w", padx=(8, 0), pady=(0, 8))
    ttk.Checkbutton(
        cleanup, text="Melody only", variable=app.melody_only_var
    ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(0, 8))

    arrangement = ttk.LabelFrame(parent, text="Arrangement / Piano Cover", padding=12)
    arrangement.grid(row=start_row + 1, column=0, sticky="new", padx=12, pady=(0, 8))
    ttk.Label(arrangement, text="Melody notes").grid(row=0, column=0, sticky="w")
    ttk.Spinbox(
        arrangement, from_=1, to=3, increment=1,
        textvariable=app.melody_max_notes_var, width=8,
    ).grid(row=0, column=1, sticky="w", padx=(8, 24))
    ttk.Label(arrangement, text="Melody window ms").grid(row=0, column=2, sticky="w")
    ttk.Spinbox(
        arrangement, from_=20, to=250, increment=10,
        textvariable=app.melody_window_var, width=8,
    ).grid(row=0, column=3, sticky="w", padx=(8, 24))
    ttk.Label(arrangement, text="Optimizer mode").grid(row=0, column=4, sticky="w")
    ttk.Combobox(
        arrangement,
        textvariable=app.optimizer_mode_var,
        values=("None", "Piano Cover", "Rule", "OpenAI"),
        state="readonly",
        width=12,
    ).grid(row=0, column=5, sticky="w", padx=(8, 12))
    ttk.Button(
        arrangement, text="Optimize MIDI", command=app.start_optimize_midi
    ).grid(row=0, column=6, sticky="w")

    key_transpose = ttk.LabelFrame(parent, text="Key Transpose", padding=12)
    key_transpose.grid(row=start_row + 2, column=0, sticky="new", padx=12, pady=(0, 12))
    ttk.Label(key_transpose, text="Original Key").grid(row=0, column=0, sticky="w")
    original_key_combo = ttk.Combobox(
        key_transpose,
        textvariable=app.original_key_var,
        values=("Auto Detect", *KEY_NAMES),
        state="readonly",
        width=12,
    )
    original_key_combo.grid(row=0, column=1, sticky="w", padx=(8, 24))
    original_key_combo.bind("<<ComboboxSelected>>", app.on_key_transpose_changed)
    ttk.Label(key_transpose, text="Target Key").grid(row=0, column=2, sticky="w")
    target_key_combo = ttk.Combobox(
        key_transpose,
        textvariable=app.target_key_var,
        values=("Original", *KEY_NAMES),
        state="readonly",
        width=12,
    )
    target_key_combo.grid(row=0, column=3, sticky="w", padx=(8, 0))
    target_key_combo.bind("<<ComboboxSelected>>", app.on_key_transpose_changed)
    ttk.Label(key_transpose, textvariable=app.detected_key_var).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )
    ttk.Label(key_transpose, textvariable=app.key_transpose_status_var).grid(
        row=1, column=2, columnspan=2, sticky="w", pady=(8, 0)
    )
    return start_row + 3
