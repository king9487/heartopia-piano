import json
import os
from pathlib import Path
from urllib import request

from midi_rule_engine import RuleNote, read_midi_notes, write_clean_midi
from midi_to_keyboard import DEFAULT_NOTE_MAP


AI_OPTIMIZED_MIDI_NAME = "ai_optimized_37key.mid"
FINAL_37KEY_MIDI_NAME = "final_37key.mid"
OPTIMIZER_NONE = "none"
OPTIMIZER_RULE = "rule"
OPTIMIZER_OPENAI = "openai"
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
    mode = (options.get("mode") or OPTIMIZER_RULE).lower()
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
    ai_midi = clean_midi.with_name(AI_OPTIMIZED_MIDI_NAME)
    final_midi = clean_midi.with_name(FINAL_37KEY_MIDI_NAME)

    optimize_37key_midi(clean_midi, output_midi=ai_midi, options=options)
    smooth_37key_midi(ai_midi, output_midi=final_midi, options=options)
    return {
        "clean_midi": clean_midi,
        "ai_optimized_midi": ai_midi,
        "final_midi": final_midi,
    }
