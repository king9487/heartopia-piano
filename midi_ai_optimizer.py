import json
import os
from pathlib import Path
from urllib import request

from midi_rule_engine import RuleNote, read_midi_notes, write_clean_midi
from midi_to_keyboard import DEFAULT_NOTE_MAP


AI_OPTIMIZED_MIDI_NAME = "ai_optimized_37key.mid"
PITCH_CORRECTED_MIDI_NAME = "pitch_corrected_37key.mid"
FINAL_37KEY_MIDI_NAME = "final_37key.mid"
PITCH_CLASS_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)
OPTIMIZER_NONE = "none"
OPTIMIZER_RULE = "rule"
OPTIMIZER_OPENAI = "openai"
OPTIMIZER_PIANO_COVER = "piano cover"
PIANO_COVER_MIDI_NAME = "piano_cover_37key.mid"
DEFAULT_AI_OPTIMIZER_OPTIONS = {
    "mode": OPTIMIZER_RULE,
    "chunk_ms": 8000,
    "window_ms": 50,
    "max_notes_per_window": 2,
    "min_note_duration_ms": 35,
    "openai_model": "gpt-4.1-mini",
}
OPENAI_OPTIMIZER_PROMPT = """You are optimizing MIDI notes for a 37-key music game.

Input is a JSON list of note events:
start_ms, duration_ms, note, velocity.

Task:
- Remove noisy, accidental, or unstable notes.
- Preserve the recognizable melody.
- Preserve simple harmony only when it helps.
- Prefer smooth melodic movement.
- Avoid too many simultaneous notes.
- Avoid sudden jumps unless musically necessary.
- Do not create a new song.
- Do not change the 37-key note range.
- Return JSON only."""


def midi_notes_to_dicts(input_midi):
    notes = []
    for note in read_midi_notes(input_midi):
        notes.append(
            {
                "start_ms": int(round(note.start * 1000)),
                "duration_ms": max(1, int(round(note.duration * 1000))),
                "note": int(note.note),
                "velocity": int(note.velocity),
            }
        )
    return notes


def dicts_to_rule_notes(notes):
    rule_notes = []
    for note in notes:
        start = int(note["start_ms"]) / 1000
        duration = int(note["duration_ms"]) / 1000
        midi_note = int(note["note"])
        rule_notes.append(
            RuleNote(
                start=start,
                end=start + duration,
                original_note=midi_note,
                note=midi_note,
                velocity=int(note["velocity"]),
            )
        )
    return rule_notes


def split_notes_into_chunks(notes, chunk_ms=8000):
    chunk_ms = max(1000, int(chunk_ms))
    chunks = []
    current_chunk = []
    current_index = None

    for note in sorted(notes, key=lambda item: (item["start_ms"], item["note"])):
        chunk_index = note["start_ms"] // chunk_ms
        if current_index is None:
            current_index = chunk_index
        if chunk_index != current_index:
            chunks.append(current_chunk)
            current_chunk = []
            current_index = chunk_index
        current_chunk.append(note)

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def is_valid_note_dict(note, lowest, highest):
    try:
        start_ms = int(note["start_ms"])
        duration_ms = int(note["duration_ms"])
        midi_note = int(note["note"])
        velocity = int(note["velocity"])
    except (KeyError, TypeError, ValueError):
        return False

    return (
        start_ms >= 0
        and duration_ms > 0
        and lowest <= midi_note <= highest
        and velocity >= 1
        and velocity <= 127
    )


def validate_note_dicts(notes, note_map=None):
    note_map = note_map or DEFAULT_NOTE_MAP
    lowest = min(note_map)
    highest = max(note_map)
    if not isinstance(notes, list):
        raise ValueError("AI output must be a JSON list")

    validated = []
    for note in notes:
        if not isinstance(note, dict) or not is_valid_note_dict(note, lowest, highest):
            raise ValueError("AI output contains invalid notes")
        validated.append(
            {
                "start_ms": int(note["start_ms"]),
                "duration_ms": int(note["duration_ms"]),
                "note": int(note["note"]),
                "velocity": int(note["velocity"]),
            }
        )

    return sorted(validated, key=lambda item: (item["start_ms"], item["note"]))


def remove_isolated_short_notes(notes, min_note_duration_ms=35):
    filtered = []
    for index, note in enumerate(notes):
        if note["duration_ms"] >= min_note_duration_ms:
            filtered.append(note)
            continue

        previous_note = notes[index - 1] if index > 0 else None
        next_note = notes[index + 1] if index + 1 < len(notes) else None
        previous_gap = (
            note["start_ms"] - (previous_note["start_ms"] + previous_note["duration_ms"])
            if previous_note
            else 999999
        )
        next_gap = next_note["start_ms"] - note["start_ms"] if next_note else 999999
        if previous_gap <= 120 or next_gap <= 120:
            filtered.append(note)

    return filtered


def rule_score(note, previous_pitch=None):
    score = note["velocity"] * 1.0 + note["duration_ms"] * 0.18
    if previous_pitch is None:
        return score

    pitch_delta = abs(note["note"] - previous_pitch)
    if pitch_delta <= 5:
        score += 10
    elif pitch_delta <= 12:
        score += 4
    else:
        score -= min(24, pitch_delta * 1.5)
    return score


def optimize_notes_with_rules(notes, options=None):
    options = {**DEFAULT_AI_OPTIMIZER_OPTIONS, **(options or {})}
    max_notes = max(1, min(int(options.get("max_notes_per_window") or 2), 3))
    window_ms = max(10, int(options.get("window_ms") or 50))
    min_note_duration_ms = max(1, int(options.get("min_note_duration_ms") or 35))
    notes = validate_note_dicts(notes)
    notes = remove_isolated_short_notes(notes, min_note_duration_ms=min_note_duration_ms)

    grouped = {}
    for note in notes:
        grouped.setdefault(note["start_ms"] // window_ms, []).append(note)

    selected = []
    previous_pitch = None
    for _, group in sorted(grouped.items()):
        ranked = sorted(
            group,
            key=lambda note: rule_score(note, previous_pitch=previous_pitch),
            reverse=True,
        )[:max_notes]
        ranked = sorted(ranked, key=lambda note: (note["start_ms"], note["note"]))
        selected.extend(ranked)
        if ranked:
            previous_pitch = ranked[-1]["note"]

    return validate_note_dicts(selected)


def _normalize_optimizer_mode(mode):
    return " ".join(str(mode or "").lower().replace("_", " ").replace("-", " ").split())


def _onset_groups(notes, window_ms):
    window_seconds = max(1, int(window_ms)) / 1000
    groups = []
    for note in sorted(notes, key=lambda item: (item.start, item.original_note)):
        if not groups or note.start - groups[-1][0].start > window_seconds:
            groups.append([note])
        else:
            groups[-1].append(note)
    return groups


def _octave_candidates(pitch, lowest, highest):
    return [candidate for candidate in range(lowest, highest + 1) if candidate % 12 == pitch % 12]


def _melody_pitch(pitch, lowest, highest, allow_octave_up=True):
    candidates = _octave_candidates(pitch, lowest, highest)
    if not candidates:
        return None
    if lowest <= pitch <= highest:
        # Give a low melody one octave of separation from the left hand when possible.
        if allow_octave_up and pitch < lowest + 24 and pitch + 12 <= highest:
            return pitch + 12
        return pitch
    melody_floor = min(highest, lowest + 24)
    return min(candidates, key=lambda candidate: (abs(candidate - melody_floor), -candidate))


def _accompaniment_pitch(pitch, melody_pitch, lowest, highest, bass=False):
    candidates = [
        candidate
        for candidate in _octave_candidates(pitch, lowest, highest)
        if candidate <= melody_pitch - 3
    ]
    if not candidates:
        return None
    target = lowest + (7 if bass else 17)
    return min(candidates, key=lambda candidate: (abs(candidate - target), candidate))


def arrange_piano_cover_notes(notes, note_map=None, options=None):
    """Reduce a transcription to a melody-first, three-note piano arrangement."""
    options = options or {}
    note_map = note_map or DEFAULT_NOTE_MAP
    lowest, highest = min(note_map), max(note_map)
    min_duration = max(0, int(options.get("min_note_duration_ms", 35))) / 1000
    velocity_threshold = max(0, int(options.get("velocity_threshold", 12)))
    window_ms = max(20, int(options.get("arrangement_window_ms", 60)))
    max_notes = max(2, min(int(options.get("max_notes_per_window", 3)), 3))
    repeat_seconds = max(0, int(options.get("bass_repeat_ms", 450))) / 1000
    allow_octave_up = bool(options.get("melody_octave_up", True))

    source = [
        note for note in notes
        if note.duration >= min_duration and note.velocity >= velocity_threshold
    ]
    groups = _onset_groups(source, window_ms)
    arranged = []
    active_melody = None
    last_bass_pitch = None
    last_bass_start = -float("inf")

    for group_index, group in enumerate(groups):
        group_start = min(note.start for note in group)
        next_start = (
            min(note.start for note in groups[group_index + 1])
            if group_index + 1 < len(groups)
            else None
        )
        top = max(group, key=lambda note: (note.original_note, note.duration, note.velocity))
        active_remaining = active_melody.end - group_start if active_melody else 0
        keep_sustained_melody = bool(
            active_melody
            and active_remaining > 0
            and top.original_note <= active_melody.original_note
            and top.duration < active_remaining
        )

        melody_source = None if keep_sustained_melody else top
        if melody_source is not None:
            pitch = _melody_pitch(
                melody_source.original_note, lowest, highest, allow_octave_up=allow_octave_up
            )
            if pitch is None:
                continue
            if active_melody and active_melody.end > group_start:
                active_melody.end = max(active_melody.start + 0.001, group_start)
            active_melody = RuleNote(
                start=melody_source.start,
                end=melody_source.end,
                original_note=melody_source.original_note,
                note=pitch,
                velocity=min(127, melody_source.velocity + 8),
                octave_shift=pitch - melody_source.original_note,
            )
            arranged.append(active_melody)

        if not active_melody or active_melody.end <= group_start:
            continue
        melody_pitch = active_melody.note
        accompaniment = [note for note in group if note is not melody_source]
        if not accompaniment:
            continue

        bass_source = min(
            accompaniment,
            key=lambda note: (note.original_note, -note.duration, -note.velocity),
        )
        bass_pitch = _accompaniment_pitch(
            bass_source.original_note, melody_pitch, lowest, highest, bass=True
        )
        chosen = []
        if (
            bass_pitch is not None
            and not (
                bass_pitch == last_bass_pitch
                and group_start - last_bass_start < repeat_seconds
            )
        ):
            chosen.append((bass_source, bass_pitch))
            last_bass_pitch, last_bass_start = bass_pitch, group_start

        harmony_candidates = []
        for note in accompaniment:
            if note is bass_source:
                continue
            pitch = _accompaniment_pitch(
                note.original_note, melody_pitch, lowest, highest, bass=False
            )
            if pitch is None or pitch == bass_pitch or pitch == melody_pitch:
                continue
            score = note.duration_ms * 0.22 + note.velocity - abs((melody_pitch - pitch) - 7)
            harmony_candidates.append((score, note, pitch))
        harmony_candidates.sort(key=lambda item: item[0], reverse=True)
        for _, note, pitch in harmony_candidates:
            if len(chosen) >= max_notes - 1:
                break
            if pitch not in {chosen_pitch for _, chosen_pitch in chosen}:
                chosen.append((note, pitch))

        for note, pitch in chosen:
            # Accompaniment yields at the next onset; the sustained melody does not.
            end = min(note.end, active_melody.end)
            if next_start is not None:
                end = min(end, next_start)
            if end <= group_start:
                continue
            arranged.append(
                RuleNote(
                    start=group_start,
                    end=end,
                    original_note=note.original_note,
                    note=pitch,
                    velocity=max(1, min(note.velocity, active_melody.velocity - 8)),
                    octave_shift=pitch - note.original_note,
                )
            )

    return sorted(arranged, key=lambda note: (note.start, -note.note))


def arrange_piano_cover_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = (
        Path(output_midi)
        if output_midi
        else input_midi.with_name(PIANO_COVER_MIDI_NAME)
    )
    notes = arrange_piano_cover_notes(read_midi_notes(input_midi), options=options)
    write_clean_midi(notes, output_midi, quantize_ms=(options or {}).get("final_quantize_ms", 10))
    return output_midi


def extract_json_from_response(payload):
    if isinstance(payload, dict):
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]

        output = payload.get("output")
        if isinstance(output, list):
            text_parts = []
            for item in output:
                for content in item.get("content", []):
                    if content.get("type") in ("output_text", "text"):
                        text_parts.append(content.get("text", ""))
            if text_parts:
                return "".join(text_parts)

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            if isinstance(message.get("content"), str):
                return message["content"]

    raise ValueError("OpenAI response did not contain text")


def optimize_notes_with_openai(notes, options):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    options = {**DEFAULT_AI_OPTIMIZER_OPTIONS, **(options or {})}
    body = {
        "model": options.get("openai_model") or DEFAULT_AI_OPTIMIZER_OPTIONS["openai_model"],
        "input": [
            {
                "role": "system",
                "content": "You are a MIDI cleanup assistant. Return valid JSON only.",
            },
            {
                "role": "user",
                "content": (
                    OPENAI_OPTIMIZER_PROMPT
                    + "\n\nNotes JSON:\n"
                    + json.dumps(notes, separators=(",", ":"))
                ),
            },
        ],
    }

    request_data = json.dumps(body).encode("utf-8")
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=request_data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    text = extract_json_from_response(payload).strip()
    return validate_note_dicts(json.loads(text))


def optimize_chunk(notes, options):
    mode = _normalize_optimizer_mode(options.get("mode") or OPTIMIZER_RULE)
    if mode == OPTIMIZER_OPENAI:
        try:
            return validate_note_dicts(optimize_notes_with_openai(notes, options))
        except Exception:
            return optimize_notes_with_rules(notes, options)

    return optimize_notes_with_rules(notes, options)


def optimize_37key_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = Path(output_midi) if output_midi else input_midi.with_name(AI_OPTIMIZED_MIDI_NAME)
    options = {**DEFAULT_AI_OPTIMIZER_OPTIONS, **(options or {})}

    notes = validate_note_dicts(midi_notes_to_dicts(input_midi))
    optimized_notes = []
    for chunk in split_notes_into_chunks(notes, chunk_ms=options.get("chunk_ms", 8000)):
        optimized_notes.extend(optimize_chunk(chunk, options))

    optimized_notes = validate_note_dicts(optimized_notes)
    write_clean_midi(dicts_to_rule_notes(optimized_notes), output_midi)
    return output_midi


def detect_song_key(notes):
    notes = validate_note_dicts(notes)
    best_score = -1
    best_root = 0
    best_mode = "major"

    for root in range(12):
        for mode, intervals in (("major", MAJOR_SCALE), ("minor", MINOR_SCALE)):
            scale = {(root + interval) % 12 for interval in intervals}
            score = 0
            for note in notes:
                if note["note"] % 12 in scale:
                    score += note["duration_ms"] * max(1, note["velocity"])
            if score > best_score:
                best_score = score
                best_root = root
                best_mode = mode

    scale = {
        (best_root + interval) % 12
        for interval in (MAJOR_SCALE if best_mode == "major" else MINOR_SCALE)
    }
    return {
        "root": best_root,
        "mode": best_mode,
        "scale": scale,
        "name": f"{PITCH_CLASS_NAMES[best_root]} {best_mode}",
    }


def nearest_in_scale_candidates(note_number, scale, note_map=None, max_distance=2):
    note_map = note_map or DEFAULT_NOTE_MAP
    lowest = min(note_map)
    highest = max(note_map)
    candidates = []
    for distance in range(1, max_distance + 1):
        for direction in (-1, 1):
            candidate = note_number + (direction * distance)
            if lowest <= candidate <= highest and candidate % 12 in scale:
                candidates.append((candidate, distance, direction))
    return candidates


def is_jump_return(notes, index):
    if index <= 0 or index + 1 >= len(notes):
        return False

    previous_note = notes[index - 1]["note"]
    current_note = notes[index]["note"]
    next_note = notes[index + 1]["note"]
    current_start = notes[index]["start_ms"]
    next_start = notes[index + 1]["start_ms"]
    return (
        abs(current_note - previous_note) > 12
        and abs(next_note - previous_note) <= 3
        and next_start - current_start <= 350
    )


def choose_pitch_correction(note, previous_note, next_note, scale, note_map=None):
    candidates = nearest_in_scale_candidates(note["note"], scale, note_map=note_map)
    if not candidates:
        return None

    def movement_score(candidate):
        corrected_note, distance, direction = candidate
        score = distance * 10
        if previous_note is not None:
            score += abs(corrected_note - previous_note["note"])
        if next_note is not None:
            score += abs(next_note["note"] - corrected_note) * 0.5
        score += 0.2 if direction > 0 else 0
        return score

    return sorted(candidates, key=movement_score)[0][0]


def pitch_correct_notes(notes, options=None):
    options = options or {}
    note_map = options.get("note_map") or DEFAULT_NOTE_MAP
    min_short_ms = int(options.get("pitch_short_note_ms", 70))
    low_velocity = int(options.get("pitch_low_velocity", 35))
    notes = validate_note_dicts(notes, note_map=note_map)
    key_info = detect_song_key(notes)
    scale = key_info["scale"]

    corrected = []
    for index, note in enumerate(notes):
        previous_note = notes[index - 1] if index > 0 else None
        next_note = notes[index + 1] if index + 1 < len(notes) else None
        in_key = note["note"] % 12 in scale
        jump_return = is_jump_return(notes, index)

        if in_key and not jump_return:
            corrected.append(note)
            continue

        if note["duration_ms"] <= min_short_ms and not in_key:
            continue
        if note["velocity"] <= low_velocity and not in_key:
            continue

        corrected_note = choose_pitch_correction(
            note,
            previous_note,
            next_note,
            scale,
            note_map=note_map,
        )
        if corrected_note is None:
            continue

        fixed = dict(note)
        fixed["note"] = corrected_note
        corrected.append(fixed)

    return validate_note_dicts(corrected, note_map=note_map), key_info


def pitch_correct_37key_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = (
        Path(output_midi)
        if output_midi
        else input_midi.with_name(PITCH_CORRECTED_MIDI_NAME)
    )
    corrected_notes, key_info = pitch_correct_notes(midi_notes_to_dicts(input_midi), options=options)
    write_clean_midi(dicts_to_rule_notes(corrected_notes), output_midi)
    return output_midi, key_info


def detect_key_for_midi(input_midi):
    return detect_song_key(midi_notes_to_dicts(input_midi))["name"]


def smooth_note_events(notes, options=None):
    options = options or {}
    min_duration_ms = max(20, int(options.get("final_min_duration_ms", 45)))
    quantize_ms = max(1, int(options.get("final_quantize_ms", 10)))
    notes = validate_note_dicts(notes)

    smoothed = []
    last_end_by_note = {}
    for note in sorted(notes, key=lambda item: (item["start_ms"], item["note"])):
        start_ms = int(round(note["start_ms"] / quantize_ms) * quantize_ms)
        duration_ms = max(min_duration_ms, int(round(note["duration_ms"] / quantize_ms) * quantize_ms))
        midi_note = note["note"]

        previous_end = last_end_by_note.get(midi_note)
        if previous_end is not None and start_ms < previous_end:
            start_ms = previous_end

        end_ms = start_ms + duration_ms
        last_end_by_note[midi_note] = end_ms
        smoothed.append(
            {
                "start_ms": start_ms,
                "duration_ms": duration_ms,
                "note": midi_note,
                "velocity": note["velocity"],
            }
        )

    return validate_note_dicts(smoothed)


def smooth_37key_midi(input_midi, output_midi=None, options=None):
    input_midi = Path(input_midi)
    output_midi = Path(output_midi) if output_midi else input_midi.with_name(FINAL_37KEY_MIDI_NAME)
    smoothed_notes = smooth_note_events(midi_notes_to_dicts(input_midi), options=options)
    write_clean_midi(dicts_to_rule_notes(smoothed_notes), output_midi)
    return output_midi


def post_process_37key_midi(clean_midi, options=None):
    clean_midi = Path(clean_midi)
    options = options or {}
    if _normalize_optimizer_mode(options.get("mode")) == OPTIMIZER_PIANO_COVER:
        piano_cover_midi = clean_midi.with_name(PIANO_COVER_MIDI_NAME)
        final_midi = clean_midi.with_name(FINAL_37KEY_MIDI_NAME)
        arrange_piano_cover_midi(clean_midi, output_midi=piano_cover_midi, options=options)
        key_name = detect_key_for_midi(piano_cover_midi)
        smooth_37key_midi(piano_cover_midi, output_midi=final_midi, options=options)
        return {
            "clean_midi": clean_midi,
            "piano_cover_midi": piano_cover_midi,
            "ai_optimized_midi": None,
            "pitch_corrected_midi": None,
            "final_midi": final_midi,
            "detected_key": key_name,
            "arrangement_mode": "Piano Cover",
        }

    ai_midi = clean_midi.with_name(AI_OPTIMIZED_MIDI_NAME)
    pitch_corrected_midi = clean_midi.with_name(PITCH_CORRECTED_MIDI_NAME)
    final_midi = clean_midi.with_name(FINAL_37KEY_MIDI_NAME)

    optimize_37key_midi(clean_midi, output_midi=ai_midi, options=options)
    _, key_info = pitch_correct_37key_midi(
        ai_midi, output_midi=pitch_corrected_midi, options=options
    )
    smooth_37key_midi(pitch_corrected_midi, output_midi=final_midi, options=options)
    return {
        "clean_midi": clean_midi,
        "ai_optimized_midi": ai_midi,
        "pitch_corrected_midi": pitch_corrected_midi,
        "final_midi": final_midi,
        "detected_key": key_info["name"],
    }
