import unittest
from types import SimpleNamespace

from ui.panels.staff_view import StaffViewCanvas


class SelectionHarness:
    canvasx = staticmethod(float)
    canvasy = staticmethod(float)

    def __init__(self):
        self.note_positions = [(100.0, 60.0), (160.0, 40.0)]
        self.notes = ["first", "second"]
        self.selected_index = None
        self.selected = []
        self.selection_callback = lambda index, note: self.selected.append((index, note))

    def render_notes(self):
        pass


class StaffViewTests(unittest.TestCase):
    def test_higher_midi_pitch_is_drawn_higher(self):
        self.assertLess(
            StaffViewCanvas.pitch_to_y(72),
            StaffViewCanvas.pitch_to_y(60),
        )
        self.assertGreater(
            StaffViewCanvas.pitch_to_y(48),
            StaffViewCanvas.pitch_to_y(60),
        )

    def test_time_mapping_and_zoom_scale_are_horizontal(self):
        view = SimpleNamespace(
            LEFT_MARGIN=StaffViewCanvas.LEFT_MARGIN,
            pixels_per_second=100.0,
        )
        self.assertEqual(StaffViewCanvas.time_to_x(view, 0), 48)
        self.assertEqual(StaffViewCanvas.time_to_x(view, 2.5), 298)

    def test_click_selects_nearby_note_and_invokes_callback(self):
        view = SelectionHarness()
        selected = StaffViewCanvas.select_note_at(view, 102, 61)
        self.assertEqual(selected, 0)
        self.assertEqual(view.selected_index, 0)
        self.assertEqual(view.selected, [(0, "first")])

    def test_click_away_from_notes_does_not_select(self):
        view = SelectionHarness()
        self.assertIsNone(StaffViewCanvas.select_note_at(view, 10, 190))
        self.assertIsNone(view.selected_index)


if __name__ == "__main__":
    unittest.main()
