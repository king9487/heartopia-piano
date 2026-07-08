import unittest
from types import SimpleNamespace

from ui_workflow import QUICK_PLAY, STUDIO_MODE, UiWorkflowManager


class FakeWidget:
    def __init__(self):
        self.visible = True

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class FakeNotebook:
    def __init__(self):
        self.states = {}
        self.selected = None

    def tab(self, tab, **options):
        self.states[tab] = options["state"]

    def select(self, tab):
        self.selected = tab


class WorkflowManagerTests(unittest.TestCase):
    def make_app(self):
        app = SimpleNamespace(notebook=FakeNotebook())
        for name in (
            "main_tab", "import_tab", "optimization_tab", "playback_tab",
            "studio_tab", "analysis_tab", "input_source_choices",
            "conversion_options_frame", "open_midi_button",
            "open_converted_button", "preview_button", "main_log_frame",
            "main_log_source_frame", "main_status_frame",
            "import_analysis_frame", "import_selection_frame",
            "import_optimizer_frame", "playback_sources_frame",
            "playback_compare_frame",
        ):
            setattr(app, name, FakeWidget())
        app.import_actions_frame = (FakeWidget(), FakeWidget(), FakeWidget())
        app.playback_advanced_settings = (FakeWidget(), FakeWidget())
        app.input_source_refreshes = 0

        def refresh_source():
            app.input_source_refreshes += 1

        app.on_input_source_changed = refresh_source
        return app

    def test_quick_play_hides_advanced_tabs_and_sections(self):
        app = self.make_app()
        manager = UiWorkflowManager(app)
        manager.apply(QUICK_PLAY)

        self.assertEqual(app.notebook.states[app.main_tab], "normal")
        self.assertEqual(app.notebook.states[app.analysis_tab], "hidden")
        self.assertFalse(app.import_analysis_frame.visible)
        self.assertFalse(app.playback_advanced_settings[0].visible)
        self.assertEqual(app.notebook.selected, app.main_tab)

    def test_studio_mode_restores_the_same_widgets(self):
        app = self.make_app()
        manager = UiWorkflowManager(app)
        original_analysis = app.import_analysis_frame
        manager.apply(QUICK_PLAY)
        manager.apply(STUDIO_MODE)

        self.assertIs(app.import_analysis_frame, original_analysis)
        self.assertTrue(original_analysis.visible)
        self.assertTrue(all(state == "normal" for state in app.notebook.states.values()))
        self.assertEqual(app.input_source_refreshes, 2)


if __name__ == "__main__":
    unittest.main()
