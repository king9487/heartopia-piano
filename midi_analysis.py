import json
from pathlib import Path

import mido

from midi_rule_engine import read_midi_notes
from midi_to_keyboard import DEFAULT_NOTE_MAP


PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
KEY_SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
}

GM_PROGRAM_NAMES = (
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano",
    "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2", "Harpsichord",
    "Clavinet", "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ",
    "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion",
    "Harmonica", "Tango Accordion", "Acoustic Guitar (nylon)",
    "Acoustic Guitar (steel)", "Electric Guitar (jazz)",
    "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar",
    "Distortion Guitar", "Guitar Harmonics", "Acoustic Bass",
    "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin",
    "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings",
    "Orchestral Harp", "Timpani", "String Ensemble 1", "String Ensemble 2",
    "Synth Strings 1", "Synth Strings 2", "Choir Aahs", "Voice Oohs",
    "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone", "Tuba",
    "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1",
    "Synth Brass 2", "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet", "Piccolo", "Flute",
    "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle",
    "Ocarina", "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)",
    "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)",
    "Lead 7 (fifths)", "Lead 8 (bass + lead)", "Pad 1 (new age)",
    "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)",
    "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)", "FX 1 (rain)",
    "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag Pipe", "Fiddle",
    "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum",
    "Melodic Tom", "Synth Drum", "Reverse Cymbal", "Guitar Fret Noise",
    "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter",
    "Applause", "Gunshot",
)


MIDI_ANALYSIS_REPORT_NAME = "report.json"
ANALYSIS_FIELDS = (
    "Keyboard Profile",
    "Song Duration",
    "Tempo",
    "Detected Key",
    "Total Notes",
    "Raw Notes",
    "Selected Notes",
    "Selected Tracks",
    "Selected Channels",
    "Clean Notes",
    "Piano Arranged Notes",
    "Final Notes",
    "Removed Notes",
    "Merged Notes",
    "Octave Shifted",
    "Bass Removed",
    "Harmony Simplified",
    "Melody Selected",
)


def midi_note_count(midi_path):
    midi_path = Path(midi_path) if midi_path else None
    if not midi_path or not midi_path.exists():
        return 0
    return len(read_midi_notes(midi_path))


def midi_duration_and_tempo(midi_path):
    midi_path = Path(midi_path)
    midi = mido.MidiFile(midi_path)
    tempo = 500000
    for track in midi.tracks:
        tempo_message = next(
            (message for message in track if message.type == "set_tempo"), None
        )
        if tempo_message is not None:
            tempo = tempo_message.tempo
            break
    return float(midi.length), float(mido.tempo2bpm(tempo))


def _analyze_track_note_pairs(track):
    """Return completed note starts with their channel program at note-on."""
    active_notes = {}
    paired_notes = []
    channel_programs = {}
    observed_programs = set()
    channel_events = set()
    program_change_events = []
    absolute_tick = 0
    for message in track:
        absolute_tick += message.time
        if hasattr(message, "channel"):
            channel_events.add(message.channel)
        if message.type == "program_change":
            channel_programs[message.channel] = message.program
            observed_programs.add((message.channel, message.program))
            program_change_events.append(
                {
                    "tick": absolute_tick,
                    "channel": message.channel,
                    "display_channel": message.channel + 1,
                    "program": message.program,
                    "instrument": GM_PROGRAM_NAMES[message.program],
                }
            )
        if message.type == "note_on" and message.velocity > 0:
            key = (message.channel, message.note)
            program = channel_programs.get(message.channel, 0)
            observed_programs.add((message.channel, program))
            active_notes.setdefault(key, []).append((message, program))
        elif message.type == "note_off" or (
            message.type == "note_on" and message.velocity == 0
        ):
            key = (message.channel, message.note)
            starts = active_notes.get(key)
            if not starts:
                continue
            paired_notes.append(starts.pop(0))
            if not starts:
                active_notes.pop(key, None)
    for channel in channel_events:
        if not any(item[0] == channel for item in observed_programs):
            observed_programs.add((channel, channel_programs.get(channel, 0)))
    return paired_notes, observed_programs, program_change_events


def _note_statistics(note_numbers):
    return {
        "notes": len(note_numbers),
        "playable_notes": sum(note in DEFAULT_NOTE_MAP for note in note_numbers),
        "out_of_range_notes": sum(
            note not in DEFAULT_NOTE_MAP for note in note_numbers
        ),
        "min_note": min(note_numbers, default=None),
        "max_note": max(note_numbers, default=None),
    }


def _track_duration_seconds(track, ticks_per_beat):
    seconds = 0.0
    absolute_tick = 0
    previous_tick = 0
    tempo = 500000
    for message in track:
        absolute_tick += message.time
        seconds += mido.tick2second(
            absolute_tick - previous_tick, ticks_per_beat, tempo
        )
        previous_tick = absolute_tick
        if message.type == "set_tempo":
            tempo = message.tempo
    return seconds


def _midi_duration_without_merge(midi):
    """Calculate source duration without flattening its physical tracks."""
    if midi.type == 2:
        return max(
            (_track_duration_seconds(track, midi.ticks_per_beat) for track in midi.tracks),
            default=0.0,
        )

    tempo_changes = []
    final_tick = 0
    for track_index, track in enumerate(midi.tracks):
        absolute_tick = 0
        for event_index, message in enumerate(track):
            absolute_tick += message.time
            if message.type == "set_tempo":
                tempo_changes.append(
                    (absolute_tick, track_index, event_index, message.tempo)
                )
        final_tick = max(final_tick, absolute_tick)

    seconds = 0.0
    previous_tick = 0
    tempo = 500000
    for change_tick, _track, _event, new_tempo in sorted(tempo_changes):
        seconds += mido.tick2second(
            change_tick - previous_tick, midi.ticks_per_beat, tempo
        )
        previous_tick = change_tick
        tempo = new_tempo
    return seconds + mido.tick2second(
        final_tick - previous_tick, midi.ticks_per_beat, tempo
    )


def inspect_midi_file(midi_path):
    """Return source-file metadata without creating or changing any files."""
    midi_path = Path(midi_path)
    midi = mido.MidiFile(midi_path)
    tempo_message = next(
        (
            message
            for track in midi.tracks
            for message in track
            if message.type == "set_tempo"
        ),
        None,
    )
    track_analysis = []
    musical_parts = []
    channel_counts = {channel: 0 for channel in range(16)}
    note_numbers = []
    for track_index, track in enumerate(midi.tracks):
        paired_notes, observed_programs, program_change_events = (
            _analyze_track_note_pairs(track)
        )
        paired_note_messages = [message for message, _program in paired_notes]
        track_notes = [message.note for message in paired_note_messages]
        note_numbers.extend(track_notes)
        for message in paired_note_messages:
            channel_counts[message.channel] += 1
        track_channels = {
            message.channel for message in track if hasattr(message, "channel")
        }
        has_tempo_events = any(message.type == "set_tempo" for message in track)
        has_meta_events = any(message.is_meta for message in track)
        track_statistics = _note_statistics(track_notes)
        part_analysis = []
        for channel, program in sorted(observed_programs):
            part_notes = [
                message.note
                for message, note_program in paired_notes
                if message.channel == channel and note_program == program
            ]
            part_analysis.append(
                {
                    "channel": channel,
                    "display_channel": channel + 1,
                    "program": program,
                    "instrument": GM_PROGRAM_NAMES[program],
                    "program_explicit": any(
                        event["channel"] == channel and event["program"] == program
                        for event in program_change_events
                    ),
                    **_note_statistics(part_notes),
                }
            )
        channel_parts = []
        for channel in sorted({channel for channel, _program in observed_programs}):
            channel_notes = [
                message.note
                for message, _program in paired_notes
                if message.channel == channel
            ]
            programs = sorted(
                program for part_channel, program in observed_programs
                if part_channel == channel
            )
            program_details = [
                {
                    "program": program,
                    "instrument": GM_PROGRAM_NAMES[program],
                    "explicit": any(
                        event["channel"] == channel
                        and event["program"] == program
                        for event in program_change_events
                    ),
                }
                for program in programs
            ]
            channel_part = {
                "track_index": track_index,
                "track_name": track.name or "",
                "channel": channel,
                "display_channel": channel + 1,
                "programs": program_details,
                "instrument": ", ".join(
                    f"{item['program']} — {item['instrument']}"
                    + ("" if item["explicit"] else " (default)")
                    for item in program_details
                ),
                **_note_statistics(channel_notes),
            }
            channel_part["playable_percentage"] = (
                channel_part["playable_notes"] / channel_part["notes"] * 100
                if channel_part["notes"] else 0.0
            )
            channel_parts.append(channel_part)
            musical_parts.append(channel_part)
        track_analysis.append(
            {
                "track_index": track_index,
                "track_number": track_index + 1,
                "name": track.name or "",
                **track_statistics,
                "channel_count": len(track_channels),
                "has_tempo_events": has_tempo_events,
                "has_meta_events": has_meta_events,
                "has_tempo_or_meta_events": has_tempo_events or has_meta_events,
                "has_control_changes": any(
                    message.type == "control_change" for message in track
                ),
                "has_program_changes": any(
                    message.type == "program_change" for message in track
                ),
                "program_change_events": program_change_events,
                "channel_programs": part_analysis,
                "channel_parts": channel_parts,
            }
        )

    detected_key = None
    if note_numbers:
        # Do not use the 37-key optimizer's detector here: source metadata must
        # also work when the imported performance contains out-of-range notes.
        root, mode = max(
            (
                (root, mode)
                for root in range(12)
                for mode in KEY_SCALES
            ),
            key=lambda candidate: sum(
                (note - candidate[0]) % 12 in KEY_SCALES[candidate[1]]
                for note in note_numbers
            ),
        )
        detected_key = f"{PITCH_CLASS_NAMES[root]} {mode}"

    duration = _midi_duration_without_merge(midi)

    return {
        "source_path": str(midi_path.resolve()),
        "file_name": midi_path.name,
        "duration": duration,
        "bpm": (
            float(mido.tempo2bpm(tempo_message.tempo))
            if tempo_message is not None
            else None
        ),
        "key": detected_key,
        "ppq": int(midi.ticks_per_beat),
        "tracks": len(midi.tracks),
        "total_notes": len(note_numbers),
        "notes_inside_map": sum(note in DEFAULT_NOTE_MAP for note in note_numbers),
        "notes_outside_map": sum(note not in DEFAULT_NOTE_MAP for note in note_numbers),
        "notes_per_track": track_analysis,
        "musical_parts": musical_parts,
        "notes_per_channel": [
            {"channel": channel + 1, "notes": channel_counts[channel]}
            for channel in range(16)
        ],
    }


def build_midi_analysis_report(
    raw_midi,
    clean_midi,
    piano_arranged_midi,
    final_midi,
    detected_key,
    arrangement_statistics=None,
    keyboard_profile="Heartopia",
):
    arrangement_statistics = arrangement_statistics or {}
    duration, tempo = midi_duration_and_tempo(raw_midi)
    raw_notes = midi_note_count(raw_midi)
    selected_parts = inspect_midi_file(raw_midi).get("musical_parts", ())
    return {
        "Keyboard Profile": keyboard_profile,
        "Song Duration": round(duration, 3),
        "Tempo": round(tempo, 2),
        "Detected Key": detected_key or "Unknown",
        "Total Notes": raw_notes,
        "Raw Notes": raw_notes,
        "Selected Notes": raw_notes,
        "Selected Tracks": len({
            part["track_index"] for part in selected_parts if part["notes"]
        }),
        "Selected Channels": len({
            part["channel"] for part in selected_parts if part["notes"]
        }),
        "Clean Notes": midi_note_count(clean_midi),
        "Piano Arranged Notes": midi_note_count(piano_arranged_midi),
        "Final Notes": midi_note_count(final_midi),
        "Removed Notes": int(arrangement_statistics.get("Removed Notes", 0)),
        "Merged Notes": int(arrangement_statistics.get("Merged Notes", 0)),
        "Octave Shifted": int(
            arrangement_statistics.get("Octave Shifted Notes", 0)
        ),
        "Bass Removed": int(arrangement_statistics.get("Bass Removed", 0)),
        "Harmony Simplified": int(
            arrangement_statistics.get("Harmony Simplified", 0)
        ),
        "Melody Selected": int(
            arrangement_statistics.get(
                "Melody Selected", arrangement_statistics.get("Melody Notes", 0)
            )
        ),
    }


def export_midi_analysis_report(report, output_path):
    output_path = Path(output_path)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return output_path


def load_midi_analysis_report(report_path):
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return {field: payload.get(field, "--") for field in ANALYSIS_FIELDS}
