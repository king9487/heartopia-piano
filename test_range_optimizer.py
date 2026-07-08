import json
import tempfile
import unittest
from pathlib import Path

from midi_rule_engine import RuleNote, convert_to_37key_midi, read_midi_notes, write_clean_midi
from range_optimizer import (
    CandidateStrategy,
    RANGE_OPTIMIZATION_REPORT_NAME,
    analyze_note_distribution,
    optimize_note_range,
    score_strategy,
)


LOW, HIGH = 48, 84
NOTE_MAP = {pitch: str(pitch) for pitch in range(LOW, HIGH + 1)}


def note(pitch, tick=0, duration=240, velocity=90):
    return RuleNote(
        start_tick=tick,
        end_tick=tick + duration,
        note=pitch,
        original_note=pitch,
        velocity=velocity,
    )


class RangeOptimizerTests(unittest.TestCase):
    def test_analysis_detects_registers_density_chords_and_overflow(self):
        notes = [
            note(40, 0), note(52, 0), note(88, 0),
            note(43, 480), note(55, 480), note(90, 480),
        ]
        analysis = analyze_note_distribution(notes, LOW, HIGH)

        self.assertEqual(analysis.note_histogram[40], 1)
        self.assertEqual(analysis.note_count, 6)
        self.assertEqual(analysis.outside_count, 4)
        self.assertEqual(analysis.outside_percentage, 66.67)
        self.assertEqual(analysis.below_count, 2)
        self.assertEqual(analysis.above_count, 2)
        self.assertEqual(analysis.melody_range.minimum, 88)
        self.assertEqual(analysis.bass_range.maximum, 43)
        self.assertEqual(analysis.chord_size_distribution, {3: 2})
        self.assertEqual(analysis.peak_onset_density, 3)
        self.assertGreater(analysis.note_density, 0)

    def test_keep_original_wins_when_song_is_already_playable(self):
        notes = [
            note(48, 0), note(52, 0), note(55, 0),
            note(60, 480), note(64, 480), note(67, 480),
        ]
        result = optimize_note_range(notes, LOW, HIGH)

        self.assertEqual(result.chosen.strategy.name, "keep_original")
        self.assertEqual(result.chosen.score.score, 100.0)
        self.assertEqual(
            [item.note for item in result.notes], [48, 52, 55, 60, 64, 67]
        )

    def test_whole_song_transpose_preserves_relative_chord_quality(self):
        notes = [note(48), note(52), note(55), note(60)]
        analysis = analyze_note_distribution(notes, LOW, HIGH)
        result = score_strategy(
            notes,
            analysis,
            CandidateStrategy("transpose", "test", whole_shift=5),
        )

        self.assertEqual(result.score.chord_quality, 100.0)
        self.assertEqual(result.transformed_pitches, (53, 57, 60, 65))

    def test_optimizer_combines_strategies_without_breaking_the_range(self):
        notes = [
            note(40, 0), note(52, 0), note(88, 0),
            note(43, 480), note(55, 480), note(90, 480),
            note(45, 960), note(57, 960), note(91, 960),
        ]
        first = optimize_note_range(notes, LOW, HIGH)
        second = optimize_note_range(notes, LOW, HIGH)

        self.assertEqual(first.chosen.strategy, second.chosen.strategy)
        self.assertEqual(first.chosen.score.score, second.chosen.score.score)
        self.assertEqual(len(first.notes), len(notes))
        self.assertTrue(all(LOW <= item.note <= HIGH for item in first.notes))
        self.assertIn("was selected because", first.explanation)
        self.assertIs(first.candidates[0], first.chosen)

    def test_smart_cleanup_writes_a_decision_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_midi = root / "source.mid"
            output_midi = root / "clean.mid"
            write_clean_midi([note(40), note(52), note(88)], input_midi)

            convert_to_37key_midi(
                input_midi,
                output_midi,
                note_map=NOTE_MAP,
                options={
                    "out_of_range_mode": "smart",
                    "min_note_duration_ms": 0,
                    "velocity_threshold": 0,
                    "max_simultaneous_notes": 0,
                },
            )

            report = json.loads(
                (root / RANGE_OPTIMIZATION_REPORT_NAME).read_text()
            )
            output_notes = read_midi_notes(output_midi)
            self.assertEqual(report["analysis"]["outside_count"], 2)
            self.assertGreaterEqual(
                report["chosen_strategy"]["metrics"]["score"], 0
            )
            self.assertTrue(report["explanation"])
            self.assertTrue(all(LOW <= item.note <= HIGH for item in output_notes))


if __name__ == "__main__":
    unittest.main()
