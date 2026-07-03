"""Compatibility builder for the converter UI.

The application now composes its notebook tabs directly in ``ui_app.py``.  This
entry point remains for callers that previously imported ``build_converter_tab``.
"""

from ui.panels.cleanup_panel import build_cleanup_panel
from ui.panels.convert_panel import build_convert_panel, build_import_panel
from ui.panels.log_panel import build_log_panel
from ui.panels.midi_panel import build_main_midi_panel, build_midi_sources_panel
from ui.panels.settings_panel import build_settings_panel


def build_converter_tab(app):
    next_row = build_convert_panel(app, app.main_tab)
    next_row = build_main_midi_panel(app, app.main_tab, next_row)
    build_log_panel(app, app.main_tab, next_row)
    if getattr(app, "import_tab", None) is not None:
        build_import_panel(app, app.import_tab)
    if getattr(app, "playback_tab", None) is not None:
        playback_row = build_midi_sources_panel(app, app.playback_tab)
        build_settings_panel(app, app.playback_tab, playback_row)
    if getattr(app, "cleanup_tab", None) is not None:
        build_cleanup_panel(app, app.cleanup_tab)
