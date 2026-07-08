import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from midi_ai_optimizer import detect_key_for_midi
from midi_rule_engine import RuleNote, write_clean_midi


class MidiKeyDetectionTests(unittest.TestCase):
    def test_detect_key_for_midi_allows_notes_outside_default_note_map(self):
        with TemporaryDirectory() as directory:
            input_midi = Path(directory) / "wide_range.mid"
            write_clean_midi(
                [
                    RuleNote(0.0, 0.5, note=21, original_note=21, velocity=80),
                    RuleNote(0.5, 1.0, note=96, original_note=96, velocity=84),
                ],
                input_midi,
            )

            detected_key = detect_key_for_midi(input_midi)

        self.assertIsInstance(detected_key, str)
        self.assertTrue(detected_key)


if __name__ == "__main__":
    unittest.main()
