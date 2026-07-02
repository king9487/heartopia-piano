PROCESSING_PRESETS = {
    "Safe": {
        "min_note_duration_ms": 10,
        "velocity_threshold": 3,
        "max_simultaneous_notes": 0,
        "out_of_range_mode": "octave_shift",
        "melody_only": False,
        "max_notes_per_window": 3,
        "arrangement_window_ms": 100,
        "arrangement_style": "original",
        "optimizer_mode": "None",
    },
    "Balanced": {
        "min_note_duration_ms": 35,
        "velocity_threshold": 12,
        "max_simultaneous_notes": 0,
        "out_of_range_mode": "smart",
        "melody_only": False,
        "max_notes_per_window": 3,
        "arrangement_window_ms": 80,
        "arrangement_style": "piano_cover",
        "optimizer_mode": "Rule",
    },
    "Aggressive": {
        "min_note_duration_ms": 70,
        "velocity_threshold": 24,
        "max_simultaneous_notes": 2,
        "out_of_range_mode": "smart",
        "melody_only": False,
        "max_notes_per_window": 2,
        "arrangement_window_ms": 50,
        "arrangement_style": "piano_cover",
        "optimizer_mode": "Rule",
    },
    "Piano Cover": {
        "min_note_duration_ms": 35,
        "velocity_threshold": 12,
        "max_simultaneous_notes": 2,
        "out_of_range_mode": "smart",
        "melody_only": False,
        "max_notes_per_window": 2,
        "arrangement_window_ms": 80,
        "arrangement_style": "piano_cover",
        "optimizer_mode": "Rule",
    },
}


def apply_processing_preset(app, preset_name):
    """Apply a named preset to the existing cleanup/arrangement controls."""
    values = PROCESSING_PRESETS[preset_name]
    app.min_note_duration_var.set(values["min_note_duration_ms"])
    app.velocity_threshold_var.set(values["velocity_threshold"])
    app.max_simultaneous_var.set(values["max_simultaneous_notes"])
    app.octave_fit_var.set(values["out_of_range_mode"])
    app.melody_only_var.set(values["melody_only"])
    app.melody_max_notes_var.set(values["max_notes_per_window"])
    app.melody_window_var.set(values["arrangement_window_ms"])
    app.arrangement_style_var.set(values["arrangement_style"])
    app.optimizer_mode_var.set(values["optimizer_mode"])
    return values.copy()
