import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from test_external_midi_import import write_midi
from ui.actions.convert_actions import UiConvertActionsMixin


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Button:
    def __init__(self):
        self.state = "disabled"

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)


class ExternalMidiUiHarness(UiConvertActionsMixin):
    def __init__(self):
        self.external_midi_path_var = Variable()
        self.external_midi_info_vars = {
            key: Variable("--")
            for key in (
                "file_name", "duration", "bpm", "key", "ppq", "tracks",
                "total_notes", "notes_inside_map", "notes_outside_map",
                "playable_percentage", "recommended",
            )
        }
        self.status_var = Variable()
        self.process_external_midi_button = Button()
        self.preview_original_midi_button = Button()
        self.play_original_midi_button = Button()
        self.open_original_midi_button = Button()
        self.results = None
        self.logs = []
        self.previewed = []
        self.played = []
        self.sources_refreshed = 0

    def clear_midi_source_options(self):
        pass

    def update_selected_midi(self):
        self.sources_refreshed += 1

    def log_message(self, message):
        self.logs.append(message)

    def preview_selected_midi(self, midi_path=None):
        self.previewed.append(midi_path)

    def start_playback(self, midi_path=None):
        self.played.append(midi_path)


class ExternalMidiUiTests(unittest.TestCase):
    def test_browse_analyzes_and_enables_direct_actions_without_processing(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "direct.mid"
            write_midi(source, notes=(60, 64, 67))
            app = ExternalMidiUiHarness()

            with patch(
                "ui.actions.convert_actions.filedialog.askopenfilename",
                return_value=str(source),
            ):
                app.browse_external_midi()

            self.assertEqual(app.results["source_midi"], source)
            self.assertEqual(app.sources_refreshed, 1)
            self.assertEqual(app.process_external_midi_button.state, "normal")
            self.assertEqual(app.preview_original_midi_button.state, "normal")
            self.assertEqual(app.play_original_midi_button.state, "normal")
            self.assertFalse((root / "output").exists())

    def test_original_actions_reuse_preview_and_playback_with_source_path(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "original.mid"
            write_midi(source)
            app = ExternalMidiUiHarness()
            app.external_midi_path_var.set(str(source))

            app.preview_original_midi()
            app.play_original_midi()
            with patch.object(os, "startfile", create=True) as startfile:
                app.open_original_midi()

            self.assertEqual(app.previewed, [source])
            self.assertEqual(app.played, [source])
            startfile.assert_called_once_with(source)

    def test_recommendation_uses_playable_percentage_thresholds(self):
        app = ExternalMidiUiHarness()
        metadata = {
            "file_name": "song.mid", "duration": 10.0, "bpm": 120.0,
            "key": "C major", "ppq": 480, "tracks": 2,
            "total_notes": 100, "notes_inside_map": 91,
            "notes_outside_map": 9,
        }
        app.show_external_midi_metadata(metadata)
        self.assertEqual(app.external_midi_info_vars["recommended"].get(), "Direct Play")
        metadata.update(notes_inside_map=79, notes_outside_map=21)
        app.show_external_midi_metadata(metadata)
        self.assertEqual(
            app.external_midi_info_vars["recommended"].get(),
            "Optimize for Heartopia",
        )


if __name__ == "__main__":
    unittest.main()
