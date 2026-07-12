"""Visibility-only workflow profiles for the Tkinter application UI."""

from dataclasses import dataclass


QUICK_PLAY = "quick_play"
STUDIO_MODE = "studio_mode"


@dataclass(frozen=True)
class WorkflowProfile:
    visible_tabs: tuple[str, ...]
    hidden_sections: tuple[str, ...] = ()
    selected_tab: str = "main"


class UiWorkflowManager:
    """Apply extensible UI profiles without creating or replacing widgets."""

    def __init__(self, app):
        self.app = app
        self.tabs = {
            "main": app.main_tab,
            "import": app.import_tab,
            "optimization": app.optimization_tab,
            "playback": app.playback_tab,
            "keyboard_mapping": getattr(app, "keyboard_mapping_tab", None),
            "studio": app.studio_tab,
            "analysis": app.analysis_tab,
        }
        self.tabs = {name: tab for name, tab in self.tabs.items() if tab is not None}
        self.sections = {
            "source_choices": app.input_source_choices,
            "conversion_options": app.conversion_options_frame,
            "main_open_midi": app.open_midi_button,
            "main_open_converted": app.open_converted_button,
            "main_preview": app.preview_button,
            "main_log": app.main_log_frame,
            "main_log_source": app.main_log_source_frame,
            "main_status": app.main_status_frame,
            "import_actions": app.import_actions_frame,
            "import_analysis": app.import_analysis_frame,
            "import_selection": app.import_selection_frame,
            "import_optimizer": app.import_optimizer_frame,
            "playback_sources": app.playback_sources_frame,
            "playback_compare": app.playback_compare_frame,
            "playback_advanced_settings": app.playback_advanced_settings,
        }
        all_tabs = tuple(self.tabs)
        self.profiles = {
            QUICK_PLAY: WorkflowProfile(
                visible_tabs=("main", "import", "playback"),
                hidden_sections=tuple(self.sections),
                selected_tab="main",
            ),
            STUDIO_MODE: WorkflowProfile(visible_tabs=all_tabs),
        }

    def add_profile(self, name, profile):
        """Register a future workflow such as Beginner or Developer."""
        self.profiles[name] = profile

    def apply(self, name):
        profile = self.profiles[name]
        notebook = self.app.notebook
        for tab_name, tab in self.tabs.items():
            notebook.tab(tab, state=(
                "normal" if tab_name in profile.visible_tabs else "hidden"
            ))

        hidden = set(profile.hidden_sections)
        for section_name, widgets in self.sections.items():
            if not isinstance(widgets, (tuple, list)):
                widgets = (widgets,)
            for widget in widgets:
                if widget is not None:
                    (widget.grid_remove if section_name in hidden else widget.grid)()

        self.app.on_input_source_changed()
        selected = self.tabs.get(profile.selected_tab)
        if selected is not None:
            notebook.select(selected)


def show_quick_play(app):
    app.workflow_manager.apply(QUICK_PLAY)


def show_studio_mode(app):
    app.workflow_manager.apply(STUDIO_MODE)


def apply_selected_workflow(app):
    if app.workflow_var.get() == QUICK_PLAY:
        app.skip_leading_silence_var.set(True)
    else:
        app.skip_leading_silence_var.set(False)
    app.workflow_manager.apply(app.workflow_var.get())
