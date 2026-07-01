import tkinter as tk
from tkinter import ttk
from transpose import KEY_NAMES

def build_optimizer_panel(app, parent, start_row: int) -> int:
    row = start_row

    timing = ttk.Frame(parent, padding=(12, 0, 12, 8))
    timing.grid(row=row, column=0, sticky="ew")
    timing.columnconfigure(6, weight=1)
    row += 1

    ttk.Label(timing, text="Transpose").grid(row=0, column=0, sticky="w")
    ttk.Spinbox(
        timing,
        from_=-36,
        to=36,
        increment=1,
        textvariable=app.transpose_var,
        width=6,
    ).grid(row=0, column=1, sticky="w", padx=(4, 18))

    ttk.Label(timing, text="Chord gap ms").grid(row=0, column=2, sticky="w")
    ttk.Spinbox(
        timing,
        from_=0,
        to=80,
        increment=2,
        textvariable=app.chord_delay_var,
        width=6,
    ).grid(row=0, column=3, sticky="w", padx=(4, 18))

    ttk.Label(timing, text="Min hold ms").grid(row=0, column=4, sticky="w")
    ttk.Spinbox(
        timing,
        from_=20,
        to=250,
        increment=5,
        textvariable=app.min_hold_var,
        width=6,
    ).grid(row=0, column=5, sticky="w", padx=(4, 0))

    cleanup = ttk.Frame(parent, padding=(12, 0, 12, 8))
    cleanup.grid(row=row, column=0, sticky="ew")
    cleanup.columnconfigure(7, weight=1)
    row += 1

    ttk.Label(cleanup, text="Min note ms").grid(row=0, column=0, sticky="w")
    ttk.Spinbox(
        cleanup,
        from_=0,
        to=500,
        increment=5,
        textvariable=app.min_note_duration_var,
        width=6,
    ).grid(row=0, column=1, sticky="w", padx=(4, 18))

    ttk.Label(cleanup, text="Velocity").grid(row=0, column=2, sticky="w")
    ttk.Spinbox(
        cleanup,
        from_=0,
        to=127,
        increment=1,
        textvariable=app.velocity_threshold_var,
        width=6,
    ).grid(row=0, column=3, sticky="w", padx=(4, 18))

    ttk.Label(cleanup, text="Max notes").grid(row=0, column=4, sticky="w")
    ttk.Spinbox(
        cleanup,
        from_=0,
        to=12,
        increment=1,
        textvariable=app.max_simultaneous_var,
        width=6,
    ).grid(row=0, column=5, sticky="w", padx=(4, 18))

    ttk.Label(cleanup, text="Range mode").grid(row=0, column=6, sticky="w")
    ttk.Combobox(
        cleanup,
        textvariable=app.octave_fit_var,
        values=("smart", "drop", "octave_shift"),
        state="readonly",
        width=12,
    ).grid(row=0, column=7, sticky="w", padx=(4, 0))

    ttk.Checkbutton(
        cleanup,
        text="Melody only",
        variable=app.melody_only_var,
    ).grid(row=1, column=0, sticky="w", pady=(8, 0))

    ttk.Label(cleanup, text="Melody notes").grid(
        row=1, column=2, sticky="w", pady=(8, 0)
    )
    ttk.Spinbox(
        cleanup,
        from_=1,
        to=3,
        increment=1,
        textvariable=app.melody_max_notes_var,
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
        textvariable=app.melody_window_var,
        width=6,
    ).grid(row=1, column=5, sticky="w", padx=(4, 18), pady=(8, 0))

    key_transpose = ttk.LabelFrame(
        parent, text="Key Transpose", padding=(10, 6, 10, 8)
    )
    key_transpose.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
    row += 1

    ttk.Label(key_transpose, text="Original Key").grid(row=0, column=0, sticky="w")
    original_key_combo = ttk.Combobox(
        key_transpose,
        textvariable=app.original_key_var,
        values=("Auto Detect", *KEY_NAMES),
        state="readonly",
        width=12,
    )
    original_key_combo.grid(row=0, column=1, sticky="w", padx=(6, 18))
    original_key_combo.bind("<<ComboboxSelected>>", app.on_key_transpose_changed)

    ttk.Label(key_transpose, text="Target Key").grid(row=0, column=2, sticky="w")
    target_key_combo = ttk.Combobox(
        key_transpose,
        textvariable=app.target_key_var,
        values=("Original", *KEY_NAMES),
        state="readonly",
        width=12,
    )
    target_key_combo.grid(row=0, column=3, sticky="w", padx=(6, 18))
    target_key_combo.bind("<<ComboboxSelected>>", app.on_key_transpose_changed)

    ttk.Label(key_transpose, textvariable=app.detected_key_var).grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )
    ttk.Label(key_transpose, textvariable=app.key_transpose_status_var).grid(
        row=1, column=2, columnspan=2, sticky="w", pady=(8, 0)
    )

    return row
