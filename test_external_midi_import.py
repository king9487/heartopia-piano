import hashlib
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import mido

from converter import import_external_midi, write_selected_parts_midi
from midi_import import safe_load_midi
from midi_analysis import inspect_midi_file
from midi_to_keyboard import build_original_keyboard_schedule


def write_midi(path, *, ppq=480, tracks=1, tempo=500000, notes=(60, 64, 76)):
    midi = mido.MidiFile(type=1 if tracks > 1 else 0, ticks_per_beat=ppq)
    for track_index in range(tracks):
        track = mido.MidiTrack()
        midi.tracks.append(track)
        if track_index == 0 and tempo is not None:
            track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
        for note in notes if track_index == tracks - 1 else ():
            track.append(mido.Message("note_on", note=note, velocity=80, time=0))
            track.append(mido.Message("note_off", note=note, velocity=0, time=ppq))
    midi.save(path)


def _variable_length_quantity(value):
    bytes_ = [value & 0x7f]
    value >>= 7
    while value:
        bytes_.append((value & 0x7f) | 0x80)
        value >>= 7
    return bytes(reversed(bytes_))


def write_raw_midi(path, events, *, ppq=480):
    track_data = b"".join(
        _variable_length_quantity(delta) + bytes(message)
        for delta, message in events
    )
    track_data += b"\x00\xff\x2f\x00"
    path.write_bytes(
        b"MThd"
        + (6).to_bytes(4, "big")
        + (0).to_bytes(2, "big")
        + (1).to_bytes(2, "big")
        + ppq.to_bytes(2, "big")
        + b"MTrk"
        + len(track_data).to_bytes(4, "big")
        + track_data
    )


class ExternalMidiImportTests(unittest.TestCase):
    def test_safe_load_midi_repairs_invalid_data_bytes_and_writes_copy(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bad-note.mid"
            sanitized = root / "output" / "imported_sanitized.mid"
            write_raw_midi(
                source,
                (
                    (0, (0x90, 128, 64)),
                    (480, (0x80, 128, 0)),
                ),
            )
            source_bytes = source.read_bytes()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                midi = safe_load_midi(source, sanitized_path=sanitized)

            self.assertTrue(midi.import_repaired)
            self.assertTrue(sanitized.is_file())
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(
                [message.note for message in midi.tracks[0] if message.type == "note_on"],
                [127],
            )
            log = stdout.getvalue()
            self.assertIn("Original import failed:", log)
            self.assertIn("<data byte must be in range 0..127>", log)
            self.assertIn("Retry with clip=True...", log)
            self.assertIn("WARNING:", log)
            self.assertIn("Invalid MIDI data bytes detected.", log)
            self.assertIn("Values outside 0..127 were clipped.", log)
            self.assertIn("Import repaired successfully.", log)

    def test_malformed_midi_import_cases_are_repaired_without_crashing(self):
        cases = {
            "invalid-note.mid": (
                (0, (0x90, 128, 64)),
                (480, (0x80, 128, 0)),
            ),
            "invalid-velocity.mid": (
                (0, (0x90, 60, 200)),
                (480, (0x80, 60, 0)),
            ),
            "invalid-cc-value.mid": (
                (0, (0xB0, 7, 200)),
            ),
            "invalid-program.mid": (
                (0, (0xC0, 200)),
            ),
        }
        skips = {
            "cleanup": True,
            "piano_arranger": True,
            "ai_optimizer": True,
            "pitch_correction": True,
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, events in cases.items():
                with self.subTest(filename=filename):
                    source = root / filename
                    write_raw_midi(source, events)
                    source_bytes = source.read_bytes()

                    result = import_external_midi(
                        source,
                        output_root=root / "output",
                        skips=skips,
                    )

                    self.assertEqual(source.read_bytes(), source_bytes)
                    self.assertTrue(result["import_repaired"])
                    self.assertTrue(result["sanitized_midi"].is_file())
                    self.assertEqual(
                        result["sanitized_midi"],
                        root / "output" / "imported_sanitized.mid",
                    )
                    self.assertTrue(result["imported_midi"].is_file())
                    self.assertTrue(result["final_midi"].is_file())
                    self.assertEqual(
                        result["analysis_report"]["Import Status"],
                        "Repaired",
                    )
                    self.assertEqual(
                        inspect_midi_file(result["imported_midi"])["import_status"],
                        "Original",
                    )

    def test_unrepairable_midi_raises_clear_message(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "not-midi.mid"
            source.write_bytes(b"not a midi file")

            with self.assertRaisesRegex(
                ValueError, "This MIDI file cannot be repaired automatically."
            ):
                safe_load_midi(source, sanitized_path=Path(directory) / "fixed.mid")

    def test_type_two_midi_is_normalized_only_in_the_working_copy(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sequences.mid"
            midi = mido.MidiFile(type=2, ticks_per_beat=480)
            for note in (60, 64):
                track = mido.MidiTrack()
                track.append(mido.Message("note_on", note=note, velocity=80, time=0))
                track.append(mido.Message("note_off", note=note, velocity=0, time=480))
                midi.tracks.append(track)
            midi.save(source)
            original = source.read_bytes()

            result = import_external_midi(source, output_root=root / "output")

            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(mido.MidiFile(source).type, 2)
            self.assertEqual(mido.MidiFile(result["imported_midi"]).type, 1)
            self.assertTrue(result["final_midi"].exists())

    def test_import_preserves_original_and_writes_complete_pipeline(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "normal.mid"
            write_midi(source)
            original_hash = hashlib.sha256(source.read_bytes()).digest()

            progress = []
            result = import_external_midi(
                source,
                output_root=root / "output",
                progress_callback=progress.append,
            )

            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original_hash)
            self.assertNotEqual(result["imported_midi"], source)
            for key in (
                "imported_midi", "selected_parts_midi", "clean_midi", "piano_arranged_midi",
                "ai_optimized_midi", "pitch_corrected_midi", "final_midi",
            ):
                self.assertTrue(result[key].is_file(), key)
                self.assertEqual(result[key].parent, result["base_dir"])
            self.assertIn("Running Cleanup...", progress)
            self.assertIn("Running Piano Arranger...", progress)
            self.assertIn("Running AI Optimizer...", progress)
            self.assertIn("Running Pitch Correction...", progress)
            self.assertEqual(progress[-1], "All MIDI processing stages completed.")

    def test_piano_cover_and_musescore_style_files_are_accepted(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            piano_cover = root / "Piano Cover.mid"
            musescore = root / "MuseScore Export.midi"
            write_midi(piano_cover, tracks=2, notes=(48, 55, 60, 64, 67, 72))
            write_midi(musescore, ppq=960, tracks=3, tempo=600000)

            piano_result = import_external_midi(piano_cover, output_root=root / "output")
            muse_result = import_external_midi(musescore, output_root=root / "output")

            self.assertTrue(piano_result["final_midi"].exists())
            self.assertEqual(muse_result["metadata"]["ppq"], 960)
            self.assertEqual(muse_result["metadata"]["tracks"], 3)
            self.assertAlmostEqual(muse_result["metadata"]["bpm"], 100.0)

    def test_metadata_counts_range_and_reports_missing_tempo(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "untimed.mid"
            write_midi(source, tempo=None, notes=(35, 60, 72, 73))
            metadata = inspect_midi_file(source)
            self.assertIsNone(metadata["bpm"])
            self.assertEqual(metadata["total_notes"], 4)
            self.assertEqual(metadata["notes_inside_map"], 2)
            self.assertEqual(metadata["notes_outside_map"], 2)

    def test_metadata_reports_note_counts_by_track_and_channel(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "tracks-and-channels.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            meta_track = mido.MidiTrack()
            meta_track.name = "Conductor"
            meta_track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
            midi.tracks.append(meta_track)
            piano_track = mido.MidiTrack()
            piano_track.name = "Piano"
            piano_track.extend(
                (
                    mido.Message("program_change", channel=0, program=1, time=0),
                    mido.Message("control_change", channel=0, control=64, value=127, time=0),
                    mido.Message("note_on", channel=0, note=60, velocity=80, time=0),
                    mido.Message("note_on", channel=0, note=73, velocity=80, time=0),
                    mido.Message("note_off", channel=0, note=60, velocity=0, time=480),
                    mido.Message("note_off", channel=0, note=73, velocity=0, time=0),
                )
            )
            midi.tracks.append(piano_track)
            bass_track = mido.MidiTrack()
            bass_track.name = "Bass"
            bass_track.extend((
                mido.Message("note_on", channel=2, note=48, velocity=80, time=0),
                mido.Message("note_off", channel=2, note=48, velocity=0, time=480),
            ))
            midi.tracks.append(bass_track)
            midi.save(source)

            metadata = inspect_midi_file(source)

            tracks = metadata["notes_per_track"]
            self.assertEqual([track["track_index"] for track in tracks], [0, 1, 2])
            self.assertEqual([track["name"] for track in tracks], [
                "Conductor", "Piano", "Bass"
            ])
            self.assertEqual([track["notes"] for track in tracks], [0, 2, 1])
            self.assertEqual(tracks[0]["channel_programs"], [])
            self.assertEqual(
                tracks[1]["channel_programs"],
                [{
                    "channel": 0, "display_channel": 1, "program": 1,
                    "instrument": "Bright Acoustic Piano",
                    "program_explicit": True, "notes": 2,
                    "playable_notes": 1, "out_of_range_notes": 1,
                    "min_note": 60, "max_note": 73,
                }],
            )
            self.assertEqual(tracks[2]["channel_programs"][0]["channel"], 2)
            self.assertEqual(tracks[2]["channel_programs"][0]["program"], 0)
            self.assertFalse(tracks[2]["channel_programs"][0]["program_explicit"])
            self.assertEqual(metadata["notes_per_channel"][0]["notes"], 2)
            self.assertEqual(metadata["notes_per_channel"][2]["notes"], 1)
            self.assertEqual(
                sum(item["notes"] for item in metadata["notes_per_channel"]), 3
            )

    def test_track_analysis_keeps_618_517_and_312_as_physical_tracks(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "three-source-tracks.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            for track_index, note_count in enumerate((618, 517, 312)):
                track = mido.MidiTrack()
                track.name = f"Part {track_index}"
                channel = track_index
                for note_index in range(note_count):
                    note = 48 + (note_index % 24)
                    track.append(mido.Message(
                        "note_on", channel=channel, note=note, velocity=80, time=0
                    ))
                    track.append(mido.Message(
                        "note_off", channel=channel, note=note, velocity=0, time=1
                    ))
                midi.tracks.append(track)
            midi.save(source)

            with patch("midi_analysis.mido.merge_tracks") as merge_tracks:
                metadata = inspect_midi_file(source)

            merge_tracks.assert_not_called()
            self.assertEqual(metadata["tracks"], 3)
            self.assertEqual(
                [track["track_index"] for track in metadata["notes_per_track"]],
                [0, 1, 2],
            )
            self.assertEqual(
                [track["notes"] for track in metadata["notes_per_track"]],
                [618, 517, 312],
            )

    def test_track_analysis_counts_only_completed_pairs(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "pairs.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            track = mido.MidiTrack()
            track.extend((
                mido.Message("note_on", channel=0, note=60, velocity=80, time=0),
                mido.Message("note_off", channel=0, note=60, velocity=0, time=120),
                mido.Message("note_on", channel=0, note=62, velocity=80, time=0),
            ))
            midi.tracks.append(track)
            midi.tracks.append(mido.MidiTrack())
            midi.save(source)

            metadata = inspect_midi_file(source)

            self.assertEqual(
                [track["notes"] for track in metadata["notes_per_track"]], [1, 0]
            )

    def test_original_keyboard_schedule_uses_raw_messages_and_timing(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "raw-events.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            conductor = mido.MidiTrack()
            conductor.append(mido.MetaMessage("set_tempo", tempo=1000000, time=0))
            midi.tracks.append(conductor)
            notes = mido.MidiTrack()
            notes.extend((
                mido.Message("program_change", channel=0, program=40, time=0),
                mido.Message("note_on", channel=0, note=60, velocity=80, time=480),
                mido.Message("control_change", channel=0, control=64, value=127, time=240),
                mido.Message("note_off", channel=0, note=60, velocity=0, time=240),
            ))
            midi.tracks.append(notes)
            midi.save(source)
            source_bytes = source.read_bytes()

            with patch("midi_to_keyboard.mido.merge_tracks") as merge_tracks:
                schedule = build_original_keyboard_schedule(source)

            merge_tracks.assert_not_called()
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual([event[1:] for event in schedule], [
                ("down", 60, "q"), ("up", 60, "q")
            ])
            self.assertAlmostEqual(schedule[0][0], 1.0)
            self.assertAlmostEqual(schedule[1][0], 2.0)

    def test_selected_parts_midi_filters_by_physical_track_and_channel(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "parts.mid"
            selected = root / "selected.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            first = mido.MidiTrack()
            first.extend((
                mido.Message("note_on", channel=0, note=84, velocity=80, time=0),
                mido.Message("note_off", channel=0, note=84, velocity=0, time=120),
                mido.Message("note_on", channel=1, note=60, velocity=80, time=0),
                mido.Message("note_off", channel=1, note=60, velocity=0, time=120),
            ))
            second = mido.MidiTrack()
            second.extend((
                mido.Message("note_on", channel=0, note=48, velocity=80, time=0),
                mido.Message("note_off", channel=0, note=48, velocity=0, time=120),
            ))
            midi.tracks.extend((first, second))
            midi.save(source)
            source_hash = hashlib.sha256(source.read_bytes()).digest()

            write_selected_parts_midi(source, selected, {(0, 1)}, "keep")

            metadata = inspect_midi_file(selected)
            self.assertEqual(
                [track["notes"] for track in metadata["notes_per_track"]], [1, 0]
            )
            self.assertEqual(metadata["musical_parts"][0]["track_index"], 0)
            self.assertEqual(metadata["musical_parts"][0]["channel"], 1)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), source_hash)

    def test_selected_parts_preserves_global_and_selected_channel_events(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "events.mid"
            selected = root / "selected.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            meta = mido.MidiTrack()
            meta.extend((
                mido.MetaMessage("set_tempo", tempo=600000, time=0),
                mido.MetaMessage(
                    "time_signature", numerator=3, denominator=4, time=0
                ),
            ))
            notes = mido.MidiTrack()
            notes.extend((
                mido.Message("program_change", channel=0, program=5, time=0),
                mido.Message("control_change", channel=0, control=64, value=127, time=0),
                mido.Message("note_on", channel=0, note=60, velocity=80, time=0),
                mido.Message("note_off", channel=0, note=60, velocity=0, time=120),
                mido.Message("program_change", channel=1, program=9, time=0),
                mido.Message("control_change", channel=1, control=1, value=64, time=0),
                mido.Message("note_on", channel=1, note=64, velocity=80, time=0),
                mido.Message("note_off", channel=1, note=64, velocity=0, time=120),
            ))
            midi.tracks.extend((meta, notes))
            midi.save(source)

            write_selected_parts_midi(source, selected, {(1, 1)}, "keep")

            messages = [message for track in mido.MidiFile(selected).tracks for message in track]
            self.assertTrue(any(message.type == "set_tempo" for message in messages))
            self.assertTrue(any(message.type == "time_signature" for message in messages))
            self.assertTrue(any(
                message.type == "program_change" and message.channel == 1
                for message in messages
            ))
            self.assertTrue(any(
                message.type == "control_change" and message.channel == 1
                for message in messages
            ))
            self.assertFalse(any(
                not message.is_meta and getattr(message, "channel", None) == 0
                for message in messages
            ))

    def test_selected_parts_range_modes_shift_or_drop_out_of_range_notes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "range.mid"
            shifted = root / "shifted.mid"
            dropped = root / "dropped.mid"
            write_midi(source, notes=(84,))

            write_selected_parts_midi(source, shifted, {(0, 0)}, "octave_shift")
            write_selected_parts_midi(source, dropped, {(0, 0)}, "drop")

            self.assertEqual(
                inspect_midi_file(shifted)["musical_parts"][0]["min_note"], 72
            )
            self.assertEqual(inspect_midi_file(dropped)["total_notes"], 0)

    def test_import_pipeline_starts_from_optimization_selected_parts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "pipeline-parts.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            track = mido.MidiTrack()
            for channel, note in ((0, 60), (1, 64)):
                track.append(mido.Message(
                    "note_on", channel=channel, note=note, velocity=80, time=0
                ))
                track.append(mido.Message(
                    "note_off", channel=channel, note=note, velocity=0, time=120
                ))
            midi.tracks.append(track)
            midi.save(source)
            source_bytes = source.read_bytes()

            result = import_external_midi(
                source,
                output_root=root / "output",
                selected_parts={(0, 1)},
                skips={
                    "cleanup": True,
                    "piano_arranger": True,
                    "ai_optimizer": True,
                    "pitch_correction": True,
                },
            )

            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(result["imported_midi"].read_bytes(), source_bytes)
            selected_metadata = inspect_midi_file(result["selected_parts_midi"])
            self.assertEqual(selected_metadata["total_notes"], 1)
            self.assertEqual(selected_metadata["musical_parts"][0]["channel"], 1)
            self.assertEqual(
                result["clean_midi"].read_bytes(),
                result["selected_parts_midi"].read_bytes(),
            )

    def test_original_schedule_filters_track_channel_parts_and_octave_shifts(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "direct-parts.mid"
            midi = mido.MidiFile(type=1, ticks_per_beat=480)
            track = mido.MidiTrack()
            track.extend((
                mido.Message("note_on", channel=0, note=60, velocity=80, time=0),
                mido.Message("note_off", channel=0, note=60, velocity=0, time=120),
                mido.Message("note_on", channel=1, note=84, velocity=80, time=0),
                mido.Message("note_off", channel=1, note=84, velocity=0, time=120),
            ))
            midi.tracks.append(track)
            midi.save(source)

            schedule = build_original_keyboard_schedule(
                source,
                part_filter={(0, 1)},
                out_of_range_mode="octave_shift",
            )

            self.assertEqual(
                [(event[1], event[2], event[3]) for event in schedule],
                [("down", 72, "i"), ("up", 72, "i")],
            )

    def test_skipped_stages_create_named_pass_through_working_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "skip.mid"
            write_midi(source, notes=(35, 60, 73))
            result = import_external_midi(
                source,
                output_root=root / "output",
                skips={
                    "cleanup": True,
                    "piano_arranger": True,
                    "ai_optimizer": True,
                    "pitch_correction": True,
                },
            )
            imported_bytes = result["imported_midi"].read_bytes()
            for key in (
                "clean_midi", "piano_arranged_midi", "ai_optimized_midi",
                "pitch_corrected_midi",
            ):
                self.assertEqual(result[key].read_bytes(), imported_bytes)
            self.assertTrue(result["final_midi"].exists())
            final_metadata = inspect_midi_file(result["final_midi"])
            self.assertEqual(final_metadata["notes_outside_map"], 0)


if __name__ == "__main__":
    unittest.main()
