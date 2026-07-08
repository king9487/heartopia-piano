import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from keyboard_profiles import (
    DEFAULT_KEYBOARD_PROFILE,
    KEYBOARD_PROFILES,
    processing_options_for_profile,
)
from midi_rule_engine import RuleNote, convert_to_37key_midi, read_midi_notes, write_clean_midi


class KeyboardProfileTests(unittest.TestCase):
    def test_profiles_have_the_required_ranges(self):
        self.assertEqual(DEFAULT_KEYBOARD_PROFILE, "Heartopia")
        self.assertEqual(
            (KEYBOARD_PROFILES["Heartopia"].playable_low,
             KEYBOARD_PROFILES["Heartopia"].playable_high,
             KEYBOARD_PROFILES["Heartopia"].preferred_melody_low,
             KEYBOARD_PROFILES["Heartopia"].preferred_melody_high),
            (48, 84, 48, 72),
        )
        self.assertEqual(
            (KEYBOARD_PROFILES["Standard 37-Key"].playable_low,
             KEYBOARD_PROFILES["Standard 37-Key"].playable_high),
            (36, 72),
        )
        self.assertEqual(
            (KEYBOARD_PROFILES["Full Piano"].playable_low,
             KEYBOARD_PROFILES["Full Piano"].playable_high),
            (21, 108),
        )

    def test_selected_profile_is_applied_only_when_processing(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.mid"
            output = Path(directory) / "clean_37key.mid"
            write_clean_midi([RuleNote(0.0, 0.5, 84, 84, 80)], source)
            before = source.read_bytes()

            options = processing_options_for_profile("Standard 37-Key")
            self.assertEqual(source.read_bytes(), before)
            convert_to_37key_midi(source, output, options=options)

            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(all(note.note <= 72 for note in read_midi_notes(output)))


if __name__ == "__main__":
    unittest.main()
