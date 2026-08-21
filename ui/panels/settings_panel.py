from tkinter import ttk

from keyboard_profiles import KEYBOARD_PROFILES


def build_settings_panel(app, parent, start_row=0):
    panel = ttk.LabelFrame(parent, text="Playback Settings", padding=12)
    panel.grid(row=start_row, column=0, sticky="new", padx=12, pady=(0, 12))
    panel.columnconfigure(1, weight=1)

    advanced_widgets = []
    always_top = ttk.Checkbutton(
        panel,
        text="Always on top",
        variable=app.always_top_var,
        command=app.apply_topmost,
    )
    always_top.grid(row=0, column=0, columnspan=2, sticky="w")
    advanced_widgets.append(always_top)
    skip_silence = ttk.Checkbutton(
        panel,
        text="Skip leading silence",
        variable=app.skip_leading_silence_var,
    )
    skip_silence.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
    ttk.Label(panel, text="Speed").grid(row=2, column=0, sticky="w", pady=(10, 0))
    speed_controls = ttk.Frame(panel)
    speed_controls.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
    ttk.Button(
        speed_controls, text="−", width=3, command=lambda: app.adjust_playback_speed(-0.25)
    ).grid(row=0, column=0)
    ttk.Spinbox(
        speed_controls,
        from_=0.25,
        to=3.0,
        increment=0.25,
        textvariable=app.speed_var,
        width=8,
    ).grid(row=0, column=1, padx=4)
    ttk.Button(
        speed_controls, text="+", width=3, command=lambda: app.adjust_playback_speed(0.25)
    ).grid(row=0, column=2)
    focus_label = ttk.Label(panel, text="Focus delay")
    focus_label.grid(row=3, column=0, sticky="w", pady=(8, 0))
    focus_input = ttk.Spinbox(
        panel,
        from_=1,
        to=10,
        increment=1,
        textvariable=app.countdown_var,
        width=8,
    )
    focus_input.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    advanced_widgets.extend((focus_label, focus_input))
    ttk.Label(panel, text="Transpose").grid(row=4, column=0, sticky="w", pady=(8, 0))
    ttk.Spinbox(
        panel,
        from_=-36,
        to=36,
        increment=1,
        textvariable=app.transpose_var,
        width=8,
    ).grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    chord_label = ttk.Label(panel, text="Chord gap ms")
    chord_label.grid(row=5, column=0, sticky="w", pady=(8, 0))
    chord_input = ttk.Spinbox(
        panel,
        from_=0,
        to=80,
        increment=2,
        textvariable=app.chord_delay_var,
        width=8,
    )
    chord_input.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    hold_label = ttk.Label(panel, text="Min hold ms")
    hold_label.grid(row=6, column=0, sticky="w", pady=(8, 0))
    hold_input = ttk.Spinbox(
        panel,
        from_=20,
        to=250,
        increment=5,
        textvariable=app.min_hold_var,
        width=8,
    )
    hold_input.grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
    advanced_widgets.extend((chord_label, chord_input, hold_label, hold_input))

    ttk.Label(panel, text="Keyboard Profile").grid(
        row=7, column=0, sticky="w", pady=(8, 0)
    )
    profile_combo = ttk.Combobox(
        panel,
        textvariable=app.keyboard_profile_var,
        values=tuple(KEYBOARD_PROFILES),
        state="readonly",
        width=22,
    )
    profile_combo.grid(
        row=7, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
    )
    profile_combo.bind("<<ComboboxSelected>>", app.on_keyboard_profile_changed)

    ttk.Label(panel, text="Mapping Profile").grid(
        row=8, column=0, sticky="w", pady=(8, 0)
    )
    mapping_combo = ttk.Combobox(
        panel,
        textvariable=app.mapping_profile_var,
        values=tuple(getattr(app, "keyboard_mapping_profiles", {})),
        state="readonly",
        width=22,
    )
    mapping_combo.grid(
        row=8, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
    )
    mapping_combo.bind("<<ComboboxSelected>>", app.on_mapping_profile_changed)
    app.playback_mapping_profile_combo = mapping_combo
    app.playback_advanced_settings = tuple(advanced_widgets)
    return start_row + 1


# Backward-compatible name used by older panel composition code.
build_playback_settings_panel = build_settings_panel
