import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from midi_ai_optimizer import arrange_piano_cover_notes, post_process_37key_midi
from midi_rule_engine import RuleNote, read_midi_notes, write_clean_midi


def note(start, duration, pitch, velocity=80):
    return RuleNote(start, start + duration, pitch, pitch, velocity)


class PianoCoverArrangementTests(unittest.TestCase):
    def test_melody_wins_and_dense_chord_is_reduced(self):
        source = [
            note(0, 1.0, 48),
            note(0, 0.2, 55),
            note(0, 0.2, 60),
            note(0, 0.2, 64),
            note(0, 0.8, 67),
        ]
        result = arrange_piano_cover_notes(source)
        simultaneous = [item for item in result if item.start == 0]
        self.assertLessEqual(len(simultaneous), 3)
        self.assertIn(67, [item.note for item in simultaneous])

    def test_low_melody_can_move_up_one_octave(self):
        result = arrange_piano_cover_notes([note(0, 1.0, 55)])
        self.assertEqual(result[0].note, 67)

    def test_sustained_melody_beats_short_accompaniment(self):
        source = [note(0, 1.0, 69), note(0.25, 0.08, 60), note(0.25, 0.08, 48)]
        result = arrange_piano_cover_notes(source)
        melody = [item for item in result if item.original_note == 69][0]
        self.assertEqual(melody.end, 1.0)
        self.assertNotIn(60, [item.note for item in result if item.start == 0.25])

    def test_repeated_bass_is_reduced(self):
        source = [
            note(0, 0.3, 48), note(0, 0.3, 67),
            note(0.2, 0.3, 48), note(0.2, 0.3, 69),
        ]
        result = arrange_piano_cover_notes(source)
        bass_c = [item for item in result if item.note == 43 or item.note == 48]
        self.assertLessEqual(len(bass_c), 1)

    def test_piano_cover_mode_writes_a_playable_midi(self):
        source = [note(0, 0.5, 36), note(0, 0.5, 64), note(0, 0.5, 88)]
        with TemporaryDirectory() as directory:
            input_midi = Path(directory) / "source.mid"
            write_clean_midi(source, input_midi)
            result = post_process_37key_midi(input_midi, options={"mode": "Piano Cover"})
            output_notes = read_midi_notes(result["piano_cover_midi"])
            self.assertTrue(output_notes)
            self.assertTrue(all(36 <= item.note <= 72 for item in output_notes))
            self.assertLessEqual(len([item for item in output_notes if item.start < 0.01]), 3)


if __name__ == "__main__":
    unittest.main()
