from pathlib import Path

from midi_analysis import (
    ANALYSIS_FIELDS,
    MIDI_ANALYSIS_REPORT_NAME,
    load_midi_analysis_report,
)


def _display_value(field, value):
    if value == "--":
        return value
    if field == "Song Duration":
        seconds = float(value)
        minutes, seconds = divmod(seconds, 60)
        return f"{int(minutes):02d}:{seconds:06.3f}"
    if field == "Tempo":
        return f"{float(value):g} BPM"
    if field == "Import Status":
        return "⚠ Repaired" if value == "Repaired" else "✓ Original"
    return str(value)


def clear_analysis_panel(app):
    for variable in app.analysis_vars.values():
        variable.set("--")


def update_analysis_from_midi_path(app, midi_path):
    midi_path = Path(midi_path)
    report = load_midi_analysis_report(
        midi_path.parent / MIDI_ANALYSIS_REPORT_NAME
    )
    if not report:
        clear_analysis_panel(app)
    else:
        for field in ANALYSIS_FIELDS:
            app.analysis_vars[field].set(_display_value(field, report.get(field, "--")))

    selected_stats = getattr(app, "selected_direct_midi_stats", None)
    if selected_stats:
        app.analysis_vars["Selected Notes"].set(str(selected_stats["notes"]))
        app.analysis_vars["Selected Tracks"].set(str(selected_stats["tracks"]))
        app.analysis_vars["Selected Channels"].set(str(selected_stats["channels"]))
    profile_var = getattr(app, "keyboard_profile_var", None)
    if report and profile_var is not None:
        from keyboard_profiles import get_keyboard_profile

        profile = get_keyboard_profile(profile_var.get())
        app.analysis_vars["Keyboard Profile"].set(
            f"{profile.name} ({profile.range_label})"
        )
    mapping_var = getattr(app, "mapping_profile_var", None)
    if mapping_var is not None and "Mapping Profile" in app.analysis_vars:
        app.analysis_vars["Mapping Profile"].set(mapping_var.get())
