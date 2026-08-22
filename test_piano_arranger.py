import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from midi_piano_arranger import arrange_piano_midi, arrange_piano_notes
from midi_rule_engine import RuleNote, read_midi_notes, write_clean_midi
from midi_to_keyboard import DEFAULT_NOTE_MAP


def note(start, duration, pitch, velocity=80):
    return RuleNote(start, start + duration, pitch, pitch, velocity)


class PianoArrangerV2Tests(unittest.TestCase):
    def test_arrangement_reduces_dense_chords_and_repeated_bass(self):
        source = [
            note(0.0, 0.5, 36),
            note(0.0, 0.5, 48),
            note(0.0, 0.5, 60),
            note(0.0, 0.5, 64),
            note(0.0, 0.8, 67, 96),
            note(0.2, 0.3, 36),
            note(0.2, 0.5, 69, 94),
            note(0.4, 0.3, 36),
            note(0.4, 0.5, 71, 92),
        ]
        arranged, stats = arrange_piano_notes(source)
        self.assertLess(len(arranged), len(source))
        self.assertLessEqual(len([item for item in arranged if item.start == 0]), 3)
        self.assertTrue(all(item.note in DEFAULT_NOTE_MAP for item in arranged))
        self.assertLessEqual(stats["Bass Notes"], 1)
        self.assertEqual(
            stats["Raw Notes"],
            stats["Final Notes"] + stats["Removed Notes"] + stats["Merged Notes"],
        )

    def test_low_melody_is_lifted_when_playable(self):
        arranged, stats = arrange_piano_notes([note(0, 1.0, 55, 90)])
        self.assertEqual(arranged[0].note, 67)
        self.assertEqual(stats["Octave Shifted Notes"], 1)

    def test_midi_and_statistics_report_are_written(self):
        with TemporaryDirectory() as directory:
            input_midi = Path(directory) / "clean_37key.mid"
            write_clean_midi(
                [note(0, 0.5, 48), note(0, 0.5, 64), note(0, 0.8, 67)],
                input_midi,
            )
            result = arrange_piano_midi(input_midi)
            self.assertEqual(result["output_midi"].name, "02_piano_arranged_37key.mid")
            self.assertTrue(result["output_midi"].exists())
            self.assertTrue(result["report_path"].exists())
            report = json.loads(result["report_path"].read_text(encoding="utf-8"))
            self.assertEqual(report, result["statistics"])
            self.assertTrue(
                all(item.note in DEFAULT_NOTE_MAP for item in read_midi_notes(result["output_midi"]))
            )


if __name__ == "__main__":
    unittest.main()
