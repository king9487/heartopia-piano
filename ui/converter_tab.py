"""Compatibility builder for the converter UI.

The application now composes its notebook tabs directly in ``ui_app.py``.  This
entry point remains for callers that previously imported ``build_converter_tab``.
"""

from ui_cleanup_panel import build_cleanup_panel
from ui_convert_panel import build_convert_panel
from ui_log_panel import build_log_panel
from ui_midi_panel import build_midi_panel
from ui_settings_panel import build_settings_panel


def build_converter_tab(app):
    next_row = build_convert_panel(app, app.main_tab)
    next_row = build_midi_panel(app, app.main_tab, next_row)
    build_log_panel(app, app.main_tab, next_row)
    if getattr(app, "playback_tab", None) is not None:
        build_settings_panel(app, app.playback_tab)
    if getattr(app, "cleanup_tab", None) is not None:
        build_cleanup_panel(app, app.cleanup_tab)
