"""Backward-compatible MIDI Studio builder."""

from ui.panels.studio_panel import build_studio_panel


def build_midi_studio_ui(app):
    build_studio_panel(app, app.studio_tab)
