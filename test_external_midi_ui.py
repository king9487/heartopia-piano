import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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


class Tree:
    def __init__(self):
        self.rows = []

    def get_children(self, parent=""):
        return tuple(
            index for index, row in enumerate(self.rows)
            if row is not None and row[0] == parent
        )

    def delete(self, item):
        self.rows[item] = None

    def insert(self, parent, _position, values, text="", **_kwargs):
        item = len(self.rows)
        self.rows.append((parent, text, values))
        return item

    def set(self, item, column, value):
        item = int(item)
        parent, text, values = self.rows[item]
        values = list(values)
        values[{"direct": 0, "optimize": 1}[column]] = value
        self.rows[item] = (parent, text, tuple(values))


class ExternalMidiUiHarness(UiConvertActionsMixin):
    def __init__(self):
        self.external_midi_path_var = Variable()
        self.external_part_range_mode_var = Variable("keep")
        self.external_part_warning_var = Variable()
        self.external_part_selections = {}
        self.external_part_tree_items = {}
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
        self.external_midi_track_tree = Tree()
        self.external_midi_channel_tree = Tree()
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

    def start_playback(self, midi_path=None, **kwargs):
        self.played.append((midi_path, kwargs))


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
            selected_direct = app.results["selected_direct_midi"]
            self.assertTrue(selected_direct.is_file())
            self.assertNotEqual(selected_direct, source)
            self.assertEqual(app.results["selected_direct_midi_stats"], {
                "tracks": 1, "channels": 1, "notes": 3,
            })
            self.assertEqual(app.sources_refreshed, 1)
            self.assertEqual(app.process_external_midi_button.state, "normal")
            self.assertEqual(app.preview_original_midi_button.state, "normal")
            self.assertEqual(app.play_original_midi_button.state, "normal")
            self.assertEqual(
                app.external_midi_track_tree.rows,
                [
                    ("", "Track 0", (
                        "", "", "1 channel(s)", 3, 3, 0, 60, 67, "Tempo/Meta"
                    )),
                    (0, "Channel 0 (MIDI 1)", (
                        "☑", "☑", "0 — Acoustic Grand Piano (default)",
                        3, 3, 0, 60, 67, "--",
                    )),
                ],
            )
            self.assertEqual(len(app.external_midi_channel_tree.rows), 16)
            self.assertEqual(
                app.external_midi_channel_tree.rows[0],
                ("", "", ("MIDI 1 (file 0)", 3)),
            )
            self.assertIn("Original MIDI track count: 1", app.logs)
            self.assertIn("Track 0 note count: 3", app.logs)
            self.assertIn("Selected Direct MIDI created", app.logs)
            self.assertIn("Tracks kept: 1", app.logs)
            self.assertIn("Channels kept: 1", app.logs)
            self.assertIn("Notes kept: 3", app.logs)
            self.assertFalse((root / "output").exists())

            tree = app.external_midi_track_tree
            tree.identify = lambda _kind, _x, _y: "cell"
            tree.identify_column = lambda _x: "#1"
            tree.identify_row = lambda _y: "1"
            app.external_part_tree_items["1"] = (0, 0)
            app.on_external_part_tree_click(SimpleNamespace(x=1, y=1))
            self.assertFalse(app.external_part_selections[(0, 0)]["direct"])
            app.selected_direct_temp_dir.cleanup()
            self.assertEqual(tree.rows[1][2][0], "☐")

    def test_original_actions_reuse_preview_and_playback_with_source_path(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "original.mid"
            write_midi(source)
            app = ExternalMidiUiHarness()
            app.external_midi_path_var.set(str(source))
            app.external_part_selections = {
                (0, 0): {"direct": True, "optimize": True}
            }

            app.preview_original_midi()
            app.play_original_midi()
            with patch.object(os, "startfile", create=True) as startfile:
                app.open_original_midi()

            self.assertEqual(app.previewed, [source])
            self.assertEqual(app.played, [(source, {"original_events": True})])
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

    def test_part_defaults_select_playable_parts_and_warn_about_outliers(self):
        app = ExternalMidiUiHarness()
        metadata = {
            "file_name": "song.mid", "duration": 10.0, "bpm": 120.0,
            "key": "C major", "ppq": 480, "tracks": 1,
            "total_notes": 20, "notes_inside_map": 15,
            "notes_outside_map": 5, "notes_per_track": [],
            "notes_per_channel": [],
            "musical_parts": [
                {
                    "track_index": 0, "channel": 0, "notes": 10,
                    "playable_notes": 10, "out_of_range_notes": 0,
                    "playable_percentage": 100.0,
                },
                {
                    "track_index": 0, "channel": 1, "notes": 10,
                    "playable_notes": 5, "out_of_range_notes": 5,
                    "playable_percentage": 50.0,
                },
            ],
        }

        app.show_external_midi_metadata(metadata)

        self.assertTrue(app.external_part_selections[(0, 0)]["direct"])
        self.assertTrue(app.external_part_selections[(0, 0)]["optimize"])
        self.assertFalse(app.external_part_selections[(0, 1)]["direct"])
        self.assertIn("T0/Ch1", app.external_part_warning_var.get())


if __name__ == "__main__":
    unittest.main()
