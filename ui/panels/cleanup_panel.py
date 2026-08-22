from tkinter import ttk

from transpose import KEY_NAMES
from ui.presets import PROCESSING_PRESETS


def build_cleanup_panel(app, parent, start_row=0):
    controls = ttk.LabelFrame(parent, text="Presets", padding=12)
    controls.grid(row=start_row, column=0, sticky="new", padx=12, pady=(12, 8))
    ttk.Label(controls, text="Preset").grid(row=0, column=0, sticky="w")
    preset_combo = ttk.Combobox(
        controls,
        textvariable=app.processing_preset_var,
        values=tuple(PROCESSING_PRESETS),
        state="readonly",
        width=14,
    )
    preset_combo.grid(row=0, column=1, sticky="w", padx=(8, 24))
    preset_combo.bind("<<ComboboxSelected>>", app.on_processing_preset_changed)

    cleanup = ttk.LabelFrame(parent, text="MIDI Cleanup", padding=12)
    cleanup.grid(row=start_row + 1, column=0, sticky="new", padx=12, pady=(0, 8))

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
        values=("smart", "drop", "octave_shift", "compress"),
        state="readonly",
        width=12,
    ).grid(row=0, column=3, sticky="w", padx=(8, 0), pady=(0, 8))
    ttk.Checkbutton(
        cleanup, text="Melody only", variable=app.melody_only_var
    ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(0, 8))
    ttk.Button(
        cleanup,
        text="Rebuild Clean",
        command=lambda: app.start_rebuild_stage("clean"),
    ).grid(row=2, column=0, columnspan=2, sticky="w")

    arrangement = ttk.LabelFrame(
        parent, text="Piano Arranger / Arrangement Style", padding=12
    )
    arrangement.grid(row=start_row + 2, column=0, sticky="new", padx=12, pady=(0, 8))
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
    ttk.Label(arrangement, text="Arrangement style").grid(
        row=1, column=0, sticky="w", pady=(8, 0)
    )
    ttk.Combobox(
        arrangement,
        textvariable=app.arrangement_style_var,
        values=("original", "melody_only", "piano_cover"),
        state="readonly",
        width=12,
    ).grid(row=1, column=1, sticky="w", padx=(8, 24), pady=(8, 0))
    ttk.Button(
        arrangement,
        text="Rebuild Piano Arranged",
        command=lambda: app.start_rebuild_stage("piano_arranged"),
    ).grid(row=1, column=2, columnspan=2, sticky="w", pady=(8, 0))

    ai_optimizer = ttk.LabelFrame(parent, text="AI Optimizer", padding=12)
    ai_optimizer.grid(row=start_row + 3, column=0, sticky="new", padx=12, pady=(0, 8))
    ttk.Label(ai_optimizer, text="Optimizer mode").grid(row=0, column=0, sticky="w")
    ttk.Combobox(
        ai_optimizer,
        textvariable=app.optimizer_mode_var,
        values=("None", "Rule", "AI"),
        state="readonly",
        width=12,
    ).grid(row=0, column=1, sticky="w", padx=(8, 24))
    ttk.Button(
        ai_optimizer, text="Optimize MIDI", command=app.start_optimize_midi
    ).grid(row=0, column=2, sticky="w")

    pitch = ttk.LabelFrame(parent, text="Pitch Correction", padding=12)
    pitch.grid(row=start_row + 4, column=0, sticky="new", padx=12, pady=(0, 8))
    ttk.Label(
        pitch, text="Pitch correction feeds the final smoothing stage."
    ).grid(row=0, column=0, sticky="w", padx=(0, 16))
    ttk.Button(
        pitch,
        text="Rebuild Final",
        command=lambda: app.start_rebuild_stage("final"),
    ).grid(row=0, column=1, sticky="w")

    key_transpose = ttk.LabelFrame(parent, text="Key Transpose", padding=12)
    key_transpose.grid(row=start_row + 5, column=0, sticky="new", padx=12, pady=(0, 12))
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
    return start_row + 6
