import unittest

from ui.panels.timeline_renderer import PianoRollRenderer, TimelineRenderer


class RendererSpy:
    def __init__(self):
        self.notes = None
        self.playhead = None

    def render_notes(self, notes):
        self.notes = notes

    def set_playhead(self, seconds):
        self.playhead = seconds


class TimelineRendererTests(unittest.TestCase):
    def test_both_renderers_receive_the_exact_shared_note_list(self):
        piano_roll = RendererSpy()
        staff = RendererSpy()
        renderer = TimelineRenderer(piano_roll, staff)
        notes = [object(), object()]

        renderer.set_notes(notes)

        self.assertIs(renderer.notes, notes)
        self.assertIs(piano_roll.notes, notes)
        self.assertIs(staff.notes, notes)

    def test_playhead_is_forwarded_to_both_renderers(self):
        piano_roll = RendererSpy()
        staff = RendererSpy()
        renderer = TimelineRenderer(piano_roll, staff)

        renderer.set_playhead(1.25)

        self.assertEqual(piano_roll.playhead, 1.25)
        self.assertEqual(staff.playhead, 1.25)


class PianoRollScaleTests(unittest.TestCase):
    def make_renderer(self):
        renderer = PianoRollRenderer.__new__(PianoRollRenderer)
        renderer.pixels_per_second = PianoRollRenderer.DEFAULT_PIXELS_PER_SECOND
        return renderer

    def test_default_scale_uses_80_pixels_per_second(self):
        renderer = self.make_renderer()

        self.assertEqual(renderer.time_to_x(1.0), 80.0)
        self.assertEqual(renderer.time_to_x(180.0), 14400.0)

    def test_note_width_uses_duration_and_has_two_pixel_minimum(self):
        renderer = self.make_renderer()

        self.assertEqual(renderer.duration_to_width(0.5), 40.0)
        self.assertEqual(renderer.duration_to_width(0.001), 2.0)

    def test_zoom_changes_time_spacing(self):
        renderer = self.make_renderer()
        renderer.render_notes = lambda: None

        renderer.zoom_by(1.25)
        self.assertEqual(renderer.time_to_x(1.0), 100.0)
        renderer.zoom_by(0.8)
        self.assertEqual(renderer.time_to_x(1.0), 80.0)


if __name__ == "__main__":
    unittest.main()
