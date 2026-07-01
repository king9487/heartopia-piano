from tkinter import ttk


def build_settings_panel(app, parent):
    panel = ttk.LabelFrame(parent, text="Playback and conversion", padding=12)
    panel.grid(row=0, column=0, sticky="new", padx=12, pady=12)
    panel.columnconfigure(1, weight=1)

    ttk.Checkbutton(
        panel,
        text="Always on top",
        variable=app.always_top_var,
        command=app.apply_topmost,
    ).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(panel, text="Speed").grid(row=1, column=0, sticky="w", pady=(10, 0))
    ttk.Spinbox(
        panel,
        from_=0.25,
        to=3.0,
        increment=0.25,
        textvariable=app.speed_var,
        width=8,
    ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
    ttk.Label(panel, text="Focus delay").grid(row=2, column=0, sticky="w", pady=(8, 0))
    ttk.Spinbox(
        panel,
        from_=1,
        to=10,
        increment=1,
        textvariable=app.countdown_var,
        width=8,
    ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Label(panel, text="Transpose").grid(row=3, column=0, sticky="w", pady=(8, 0))
    ttk.Spinbox(
        panel,
        from_=-36,
        to=36,
        increment=1,
        textvariable=app.transpose_var,
        width=8,
    ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Label(panel, text="Chord gap ms").grid(row=4, column=0, sticky="w", pady=(8, 0))
    ttk.Spinbox(
        panel,
        from_=0,
        to=80,
        increment=2,
        textvariable=app.chord_delay_var,
        width=8,
    ).grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Label(panel, text="Min hold ms").grid(row=5, column=0, sticky="w", pady=(8, 0))
    ttk.Spinbox(
        panel,
        from_=20,
        to=250,
        increment=5,
        textvariable=app.min_hold_var,
        width=8,
    ).grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Label(panel, text="Demucs device").grid(row=6, column=0, sticky="w", pady=(8, 0))
    ttk.Combobox(
        panel,
        textvariable=app.demucs_device_var,
        values=("cuda:0", "auto", "cpu"),
        state="readonly",
        width=10,
    ).grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    ttk.Checkbutton(
        panel,
        text="Convert vocals MIDI",
        variable=app.convert_vocals_midi_var,
    ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))


# Backward-compatible name used by older panel composition code.
build_playback_settings_panel = build_settings_panel
