import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from midi_analysis import ANALYSIS_FIELDS
from ui.helpers.selection import MidiSelectionMixin


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Combo:
    def __init__(self):
        self.results = None
        self.values = ()

    def configure(self, **kwargs):
        self.values = kwargs.get("values", self.values)


class SelectionHarness(MidiSelectionMixin):
    def __init__(self):
        self.available_midi_sources = {}
        self.available_compare_sources = {}
        self.midi_source_var = Variable()
        self.selected_midi_var = Variable()
        self.compare_a_source_var = Variable()
        self.compare_b_source_var = Variable()
        self.midi_source_combo = Combo()
        self.compare_a_combo = Combo()
        self.compare_b_combo = Combo()
        self.analysis_vars = {field: Variable("--") for field in ANALYSIS_FIELDS}
        self.played = []

    def start_playback(self, **kwargs):
        self.played.append(kwargs["midi_path"])


class MidiSelectionTests(unittest.TestCase):
    def test_external_import_sources_and_compare_defaults(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            names = {
                "imported_midi": "imported.mid",
                "selected_direct_midi": "selected_direct.mid",
                "selected_parts_midi": "selected_parts.mid",
                "clean_midi": "clean_37key.mid",
                "piano_arranged_midi": "piano_arranged_37key.mid",
                "ai_optimized_midi": "ai_optimized_37key.mid",
                "pitch_corrected_midi": "pitch_corrected_37key.mid",
                "final_midi": "final_37key.mid",
            }
            for filename in names.values():
                (folder / filename).touch()
            app = SelectionHarness()
            app.results = {
                "input_source": "external_midi",
                "base_dir": folder,
                **{key: folder / filename for key, filename in names.items()},
            }
            app.update_selected_midi()

            self.assertEqual(app.midi_source_var.get(), "Final MIDI")
            self.assertIn("Full Imported MIDI", app.available_midi_sources)
            self.assertIn("Imported MIDI", app.available_midi_sources)
            self.assertIn("Selected Parts MIDI", app.available_midi_sources)
            self.assertEqual(app.compare_a_source_var.get(), "Imported MIDI")
            self.assertEqual(app.compare_b_source_var.get(), "Selected Parts MIDI")
            self.assertEqual(
                app.available_compare_sources["Imported MIDI"],
                folder / "selected_direct.mid",
            )

    def test_ab_compare_uses_existing_sources_without_changing_current(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            paths = {
                "Raw MIDI": folder / "raw.mid",
                "Clean 37-Key MIDI": folder / "clean_37key.mid",
                "Piano Arranged MIDI": folder / "piano_arranged_37key.mid",
                "Piano Cover MIDI": folder / "piano_cover_37key.mid",
                "Final 37-Key MIDI": folder / "final_37key.mid",
                "Edited MIDI": folder / "edited_37key.mid",
            }
            for path in paths.values():
                path.touch()
            (folder / "report.json").write_text(
                json.dumps(
                    {
                        field: (123.5 if field == "Song Duration" else 42)
                        for field in ANALYSIS_FIELDS
                    }
                ),
                encoding="utf-8",
            )

            app = SelectionHarness()
            app.set_midi_source_options(paths)
            self.assertEqual(app.midi_source_var.get(), "Edited MIDI")
            self.assertEqual(app.selected_midi_var.get(), str(paths["Edited MIDI"]))
            self.assertEqual(app.analysis_vars["Song Duration"].get(), "02:03.500")
            self.assertEqual(app.analysis_vars["Raw Notes"].get(), "42")
            self.assertEqual(app.compare_a_source_var.get(), "Clean 37-Key MIDI")
            self.assertEqual(app.compare_b_source_var.get(), "Piano Arranged MIDI")

            current = app.selected_midi_var.get()
            app.play_compare_midi("A")
            app.play_compare_midi("B")
            self.assertEqual(
                app.played,
                [paths["Clean 37-Key MIDI"], paths["Piano Arranged MIDI"]],
            )
            self.assertEqual(app.selected_midi_var.get(), current)

            app.set_compare_as_current("B")
            self.assertEqual(app.selected_midi_var.get(), str(paths["Piano Arranged MIDI"]))

            app.set_midi_source_options(
                {label: path for label, path in paths.items() if label != "Edited MIDI"}
            )
            self.assertEqual(app.midi_source_var.get(), "Final 37-Key MIDI")
            self.assertEqual(app.selected_midi_var.get(), str(paths["Final 37-Key MIDI"]))


if __name__ == "__main__":
    unittest.main()
