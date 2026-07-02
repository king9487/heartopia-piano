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
        return
    for field in ANALYSIS_FIELDS:
        app.analysis_vars[field].set(_display_value(field, report[field]))
