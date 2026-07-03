import unittest

from ui.panels.timeline_renderer import TimelineRenderer


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


if __name__ == "__main__":
    unittest.main()
