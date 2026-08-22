import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import mido

from keyboard_mapping import (
    DEFAULT_MAPPING_PROFILE,
    MappingProfile,
    STANDARD_MAPPING_PROFILE,
    get_playable_note_constraints,
    load_mapping_profile,
    load_mapping_profiles,
    save_mapping_profile,
)
from midi_to_keyboard import (
    OCTAVE_FIT_COMPRESS,
    OCTAVE_FIT_OCTAVE_SHIFT,
    build_keyboard_schedule,
    build_original_keyboard_schedule,
)


def write_test_midi(path, notes=(60,), ticks=120):
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    for note in notes:
        track.append(mido.Message("note_on", note=note, velocity=80, time=0))
        track.append(mido.Message("note_off", note=note, velocity=0, time=ticks))
    midi.save(path)


class KeyboardMappingTests(unittest.TestCase):
    def test_playable_constraints_for_contiguous_mapping(self):
        constraints = get_playable_note_constraints(
            MappingProfile("Range", {note: f"key-{note}" for note in range(48, 85)})
        )
        self.assertEqual(constraints["min_note"], 48)
        self.assertEqual(constraints["max_note"], 84)
        self.assertEqual(constraints["min_note_name"], "C3")
        self.assertEqual(constraints["max_note_name"], "C6")
        self.assertEqual(constraints["allowed_notes"], list(range(48, 85)))

    def test_playable_constraints_preserve_gaps_and_ignore_invalid_rows(self):
        constraints = get_playable_note_constraints(
            {48: "a", 49: "", 52: "d", "bad": "x", 128: "y"}
        )
        self.assertEqual(constraints["allowed_notes"], [48, 52])

    def test_playable_constraints_deduplicate_notes(self):
        constraints = get_playable_note_constraints([60, 60, "62", 62])
        self.assertEqual(constraints["allowed_notes"], [60, 62])

    def test_empty_mapping_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "no assigned playable notes"):
            get_playable_note_constraints(MappingProfile("Empty", {60: ""}))

    def test_mapping_json_is_created_with_defaults_when_missing(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "keyboard_mappings.json"

            profiles = load_mapping_profiles(path)

            self.assertTrue(path.exists())
            self.assertIn(DEFAULT_MAPPING_PROFILE, profiles)
            self.assertEqual(profiles[DEFAULT_MAPPING_PROFILE].mappings[60], "z")
            self.assertEqual(profiles[DEFAULT_MAPPING_PROFILE].mappings[72], "q")
            self.assertEqual(profiles[STANDARD_MAPPING_PROFILE].mappings[60], "q")

    def test_custom_mapping_can_be_saved_and_loaded(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "keyboard_mappings.json"
            profile = MappingProfile("My Mapping", {60: "a", 61: ""})

            save_mapping_profile(profile, path)
            loaded = load_mapping_profile("My Mapping", path)

            self.assertEqual(loaded.mappings, {60: "a", 61: ""})

    def test_default_profile_uses_heartopia_c3_to_c6_schedule(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "song.mid"
            write_test_midi(source, notes=(60, 72))

            profile = load_mapping_profile(DEFAULT_MAPPING_PROFILE)
            schedule = build_keyboard_schedule(source, mapping_profile=profile)

            self.assertEqual(
                [(event[1], event[2], event[3]) for event in schedule],
                [
                    ("down", 60, "z"),
                    ("up", 60, "z"),
                    ("down", 72, "q"),
                    ("up", 72, "q"),
                ],
            )

    def test_standard_profile_preserves_legacy_37_key_schedule(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "song.mid"
            write_test_midi(source, notes=(60,))

            profile = load_mapping_profile(STANDARD_MAPPING_PROFILE)
            schedule = build_keyboard_schedule(source, mapping_profile=profile)

            self.assertEqual(
                [(event[1], event[2], event[3]) for event in schedule],
                [("down", 60, "q"), ("up", 60, "q")],
            )

    def test_unmapped_notes_are_skipped_and_logged(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "song.mid"
            write_test_midi(source, notes=(60, 61))
            profile = MappingProfile("Sparse", {60: "q", 61: ""})
            logs = []

            schedule = build_keyboard_schedule(
                source,
                mapping_profile=profile,
                log_callback=logs.append,
            )

            self.assertEqual(
                [(event[1], event[2], event[3]) for event in schedule],
                [("down", 60, "q"), ("up", 60, "q")],
            )
            self.assertEqual(logs, ["Skipped unmapped note: C#4"])

    def test_sparse_mapping_defines_range_for_octave_compression(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "song.mid"
            write_test_midi(source, notes=(48, 59, 60, 72, 83))
            profile = MappingProfile(
                "C4 to C5",
                {
                    **{note: "" for note in range(48, 84)},
                    **{note: f"key-{note}" for note in range(60, 73)},
                },
            )

            schedule = build_keyboard_schedule(
                source,
                mapping_profile=profile,
                octave_fit_mode=OCTAVE_FIT_OCTAVE_SHIFT,
            )

            self.assertEqual(
                [event[2] for event in schedule if event[1] == "down"],
                [60, 71, 60, 72, 71],
            )

    def test_original_playback_uses_assigned_range_for_octave_compression(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "song.mid"
            write_test_midi(source, notes=(48, 83))
            profile = MappingProfile(
                "C4 to C5",
                {note: f"key-{note}" for note in range(60, 73)},
            )

            schedule = build_original_keyboard_schedule(
                source,
                mapping_profile=profile,
                out_of_range_mode="octave_shift",
            )

            self.assertEqual(
                [event[2] for event in schedule if event[1] == "down"],
                [60, 71],
            )

    def test_compress_mode_scales_actual_midi_extremes_to_mapping_extremes(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "song.mid"
            write_test_midi(source, notes=(36, 48, 60, 72, 84))
            profile = MappingProfile(
                "C4 to C5",
                {note: f"key-{note}" for note in range(60, 73)},
            )

            schedule = build_keyboard_schedule(
                source,
                mapping_profile=profile,
                octave_fit_mode=OCTAVE_FIT_COMPRESS,
            )

            self.assertEqual(
                [event[2] for event in schedule if event[1] == "down"],
                [60, 63, 66, 69, 72],
            )


if __name__ == "__main__":
    unittest.main()
