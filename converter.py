from pathlib import Path
import json
import re
import shutil
import subprocess

import mido

from midi_ai_optimizer import (
    AI_OPTIMIZED_MIDI_NAME,
    FINAL_37KEY_MIDI_NAME,
    PIANO_COVER_MIDI_NAME,
    PITCH_CORRECTED_MIDI_NAME,
    detect_key_for_midi,
    pitch_correct_37key_midi,
    post_process_37key_midi,
    smooth_37key_midi,
    optimize_37key_midi,
)
from midi_rule_engine import DEFAULT_37KEY_CLEAN_OPTIONS, convert_to_37key_midi
from midi_analysis import (
    MIDI_ANALYSIS_REPORT_NAME,
    build_midi_analysis_report,
    export_midi_analysis_report,
    load_midi_analysis_report,
    inspect_midi_file,
)
from midi_piano_arranger import (
    PIANO_ARRANGED_MIDI_NAME,
    PIANO_ARRANGEMENT_REPORT_NAME,
    arrange_piano_midi,
)
from tools import find_executable, find_ffmpeg_location, run, run_capture
from midi_to_keyboard import DEFAULT_NOTE_MAP, octave_shift_note


CLEAN_37KEY_MIDI_NAME = "clean_37key.mid"
SELECTED_PARTS_MIDI_NAME = "selected_parts.mid"
GENERATED_MIDI_NAMES = {
    SELECTED_PARTS_MIDI_NAME,
    CLEAN_37KEY_MIDI_NAME,
    AI_OPTIMIZED_MIDI_NAME,
    PITCH_CORRECTED_MIDI_NAME,
    FINAL_37KEY_MIDI_NAME,
    PIANO_COVER_MIDI_NAME,
    PIANO_ARRANGED_MIDI_NAME,
}


def sanitize_filename(value, max_length=120):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    if not value:
        value = "youtube_audio"
    return value[:max_length].rstrip(" .")


def get_youtube_info(url, cancel_token=None):
    output = run_capture(
        [
            find_executable("yt-dlp"),
            "--no-playlist",
            "--no-check-certificates",
            "--socket-timeout",
            "20",
            "--retries",
            "2",
            "-J",
            "--skip-download",
            url,
        ],
        cancel_token=cancel_token,
        timeout=90,
    ).strip()

    try:
        info = json.loads(output)
    except json.JSONDecodeError:
        return "youtube_audio", "unknown"

    title = info.get("title") or "youtube_audio"
    video_id = info.get("id") or "unknown"

    return title.strip() or "youtube_audio", video_id.strip() or "unknown"


def output_dir_for_url(url, output_root="output", cancel_token=None):
    title, video_id = get_youtube_info(url, cancel_token=cancel_token)
    folder_name = sanitize_filename(f"{title}_{video_id}")
    return Path(output_root) / folder_name


def output_dir_for_audio_file(audio_file, output_root="output"):
    audio_file = Path(audio_file)
    folder_name = sanitize_filename(f"{audio_file.stem}_local")
    return Path(output_root) / folder_name


def output_dir_for_midi_file(midi_file, output_root="output"):
    midi_file = Path(midi_file)
    return Path(output_root) / sanitize_filename(f"{midi_file.stem}_midi")


def write_selected_parts_midi(
    input_midi, output_midi, selected_parts=None, range_mode="keep"
):
    """Write a working MIDI containing selected physical-track/channel parts."""
    if range_mode not in {"keep", "octave_shift", "drop"}:
        raise ValueError(f"Unknown selected-part range mode: {range_mode}")
    selected = None if selected_parts is None else {
        (int(track), int(channel)) for track, channel in selected_parts
    }
    if selected is not None and not selected:
        raise ValueError("At least one Track/Channel part must be selected")

    source = mido.MidiFile(input_midi)
    output = mido.MidiFile(type=source.type, ticks_per_beat=source.ticks_per_beat)
    for track_index, track in enumerate(source.tracks):
        output_track = mido.MidiTrack()
        output.tracks.append(output_track)
        pending_time = 0
        active_notes = {}
        for message in track:
            pending_time += message.time
            keep = message.is_meta
            copied = message
            if not message.is_meta:
                part_selected = (
                    selected is None
                    or not hasattr(message, "channel")
                    or (track_index, message.channel) in selected
                )
                if not part_selected:
                    keep = False
                elif message.type == "note_on" and message.velocity > 0:
                    target_note = message.note
                    if target_note not in DEFAULT_NOTE_MAP:
                        if range_mode == "octave_shift":
                            target_note = octave_shift_note(target_note, DEFAULT_NOTE_MAP)
                        elif range_mode == "drop":
                            target_note = None
                    key = (message.channel, message.note)
                    active_notes.setdefault(key, []).append(target_note)
                    keep = target_note is not None
                    if keep:
                        copied = message.copy(note=target_note)
                elif hasattr(message, "channel") and (
                    message.type == "note_off" or (
                    message.type == "note_on" and message.velocity == 0
                    )
                ):
                    key = (message.channel, message.note)
                    targets = active_notes.get(key)
                    target_note = targets.pop(0) if targets else message.note
                    if targets == []:
                        active_notes.pop(key, None)
                    keep = target_note is not None
                    if keep:
                        copied = message.copy(note=target_note)
                else:
                    keep = True
            if keep:
                output_track.append(copied.copy(time=pending_time))
                pending_time = 0

    output_midi = Path(output_midi)
    output.save(output_midi)
    return output_midi


def import_external_midi(
    midi_file,
    output_root="output",
    options=None,
    skips=None,
    progress_callback=None,
    selected_parts=None,
    part_range_mode="keep",
):
    """Copy and process an arbitrary MIDI through the Heartopia MIDI stages."""
    report_progress = progress_callback or (lambda message: None)
    source = Path(midi_file)
    if source.suffix.lower() not in {".mid", ".midi"}:
        raise ValueError("External MIDI must use the .mid or .midi extension")
    if not source.is_file():
        raise FileNotFoundError(source)

    # Parse before copying so malformed files fail without leaving a partial job.
    report_progress("Reading imported MIDI...")
    metadata = inspect_midi_file(source)
    base_dir = output_dir_for_midi_file(source, output_root=output_root)
    base_dir.mkdir(parents=True, exist_ok=True)
    imported_midi = base_dir / "imported.mid"
    report_progress("Creating MIDI working copy...")
    if source.resolve() != imported_midi.resolve():
        shutil.copy2(source, imported_midi)
    working_midi = mido.MidiFile(imported_midi)
    if working_midi.type == 2:
        # The existing pipeline consumes a single synchronous performance.
        # Combine type-2 sequences only in the working copy, starting each at 0.
        normalized = mido.MidiFile(type=1, ticks_per_beat=working_midi.ticks_per_beat)
        for track in working_midi.tracks:
            normalized.tracks.append(mido.MidiTrack(message.copy() for message in track))
        normalized.save(imported_midi)

    selected_parts_midi = base_dir / SELECTED_PARTS_MIDI_NAME
    report_progress("Creating selected Track/Channel working MIDI...")
    write_selected_parts_midi(
        imported_midi,
        selected_parts_midi,
        selected_parts=selected_parts,
        range_mode=part_range_mode,
    )
    pipeline_input = selected_parts_midi

    options = dict(options or {})
    skips = dict(skips or {})
    clean_midi = base_dir / CLEAN_37KEY_MIDI_NAME
    arranged_midi = base_dir / PIANO_ARRANGED_MIDI_NAME
    ai_midi = base_dir / AI_OPTIMIZED_MIDI_NAME
    pitch_midi = base_dir / PITCH_CORRECTED_MIDI_NAME
    final_midi = base_dir / FINAL_37KEY_MIDI_NAME

    if skips.get("cleanup"):
        report_progress("Cleanup skipped; creating clean_37key.mid pass-through.")
        shutil.copyfile(pipeline_input, clean_midi)
    else:
        report_progress("Running Cleanup...")
        convert_to_37key_midi(pipeline_input, clean_midi, options=options)

    arrangement_statistics = {}
    arrangement_report = base_dir / PIANO_ARRANGEMENT_REPORT_NAME
    if skips.get("piano_arranger"):
        report_progress(
            "Piano Arranger skipped; creating piano_arranged_37key.mid pass-through."
        )
        shutil.copyfile(clean_midi, arranged_midi)
        if arrangement_report.exists():
            arrangement_report.unlink()
    else:
        report_progress("Running Piano Arranger...")
        arranged = arrange_piano_midi(
            clean_midi,
            output_midi=arranged_midi,
            options=options,
            report_path=arrangement_report,
        )
        arrangement_statistics = arranged["statistics"]

    if skips.get("ai_optimizer"):
        report_progress(
            "AI Optimizer skipped; creating ai_optimized_37key.mid pass-through."
        )
        shutil.copyfile(arranged_midi, ai_midi)
    else:
        report_progress("Running AI Optimizer...")
        optimizer_input = arranged_midi
        if inspect_midi_file(arranged_midi)["notes_outside_map"]:
            # Cleanup is independently skippable, but the 37-key optimizer has
            # a strict input contract. Normalize only at this stage when an
            # earlier pass-through left unsupported pitches in the stream.
            convert_to_37key_midi(arranged_midi, ai_midi, options=options)
            optimizer_input = ai_midi
        optimize_37key_midi(optimizer_input, output_midi=ai_midi, options=options)

    if skips.get("pitch_correction"):
        report_progress(
            "Pitch Correction skipped; creating pitch_corrected_37key.mid pass-through."
        )
        shutil.copyfile(ai_midi, pitch_midi)
        detected_key = metadata["key"]
    else:
        report_progress("Running Pitch Correction...")
        pitch_input = ai_midi
        if inspect_midi_file(ai_midi)["notes_outside_map"]:
            convert_to_37key_midi(ai_midi, pitch_midi, options=options)
            pitch_input = pitch_midi
        _, key_info = pitch_correct_37key_midi(
            pitch_input, output_midi=pitch_midi, options=options
        )
        detected_key = key_info["name"]

    report_progress("Generating final_37key.mid...")
    final_input = pitch_midi
    if inspect_midi_file(pitch_midi)["notes_outside_map"]:
        convert_to_37key_midi(pitch_midi, final_midi, options=options)
        final_input = final_midi
    smooth_37key_midi(final_input, output_midi=final_midi, options=options)
    analysis_report = build_midi_analysis_report(
        selected_parts_midi,
        clean_midi,
        arranged_midi,
        final_midi,
        detected_key,
        arrangement_statistics=arrangement_statistics,
    )
    report_path = export_midi_analysis_report(
        analysis_report, base_dir / MIDI_ANALYSIS_REPORT_NAME
    )
    report_progress("All MIDI processing stages completed.")
    return {
        "input_source": "external_midi",
        "base_dir": base_dir,
        "source_midi": source,
        "imported_midi": imported_midi,
        "selected_parts_midi": selected_parts_midi,
        "clean_midi": clean_midi,
        "piano_arranged_midi": arranged_midi,
        "ai_optimized_midi": ai_midi,
        "pitch_corrected_midi": pitch_midi,
        "final_midi": final_midi,
        "report_path": report_path,
        "analysis_report": analysis_report,
        "metadata": metadata,
        "skips": skips,
    }


def latest_midi_file(output_dir, include_clean=False):
    output_dir = Path(output_dir)
    midi_files = list(output_dir.glob("*.mid"))
    if not include_clean:
        midi_files = [path for path in midi_files if path.name not in GENERATED_MIDI_NAMES]

    midi_files = sorted(midi_files, key=lambda path: path.stat().st_mtime, reverse=True)
    return midi_files[0] if midi_files else None


def clean_37key_midi_path(raw_midi):
    return Path(raw_midi).with_name(CLEAN_37KEY_MIDI_NAME)


def ai_optimized_midi_path(raw_or_clean_midi):
    return Path(raw_or_clean_midi).with_name(AI_OPTIMIZED_MIDI_NAME)


def final_37key_midi_path(raw_or_clean_midi):
    return Path(raw_or_clean_midi).with_name(FINAL_37KEY_MIDI_NAME)


def pitch_corrected_midi_path(raw_or_clean_midi):
    return Path(raw_or_clean_midi).with_name(PITCH_CORRECTED_MIDI_NAME)


def piano_cover_midi_path(raw_midi):
    return Path(raw_midi).with_name(PIANO_COVER_MIDI_NAME)


def piano_arranged_midi_path(raw_midi):
    return Path(raw_midi).with_name(PIANO_ARRANGED_MIDI_NAME)


def ensure_clean_37key_midi(raw_midi, options=None):
    output_midi = clean_37key_midi_path(raw_midi)
    if output_midi.exists() and output_midi.stat().st_mtime >= Path(raw_midi).stat().st_mtime:
        print("Using existing Clean 37-Key MIDI:", output_midi)
        return output_midi

    clean_options = {**DEFAULT_37KEY_CLEAN_OPTIONS, **(options or {})}
    print("Generating Clean 37-Key MIDI:", output_midi)
    return Path(
        convert_to_37key_midi(
            raw_midi,
            output_midi,
            options=clean_options,
        )
    )


def rebuild_midi_stages(raw_midi, start_stage, options=None):
    """Force one MIDI stage and its downstream stages, reusing prerequisites."""
    raw_midi = Path(raw_midi)
    if raw_midi.name.lower() == "edited_37key.mid":
        raise ValueError("edited_37key.mid cannot be used as a rebuild source")
    if not raw_midi.exists():
        raise FileNotFoundError(raw_midi)
    if start_stage not in {"clean", "piano_arranged", "final"}:
        raise ValueError(f"Unknown MIDI rebuild stage: {start_stage}")

    options = dict(options or {})
    clean_midi = clean_37key_midi_path(raw_midi)
    arranged_midi = piano_arranged_midi_path(raw_midi)
    ai_midi = ai_optimized_midi_path(raw_midi)
    pitch_midi = pitch_corrected_midi_path(raw_midi)
    final_midi = final_37key_midi_path(raw_midi)
    regenerated = []

    needs_clean = start_stage in {"clean", "piano_arranged"} or (
        start_stage == "final" and not pitch_midi.exists() and not ai_midi.exists()
    )
    if needs_clean and (start_stage == "clean" or not clean_midi.exists()):
        clean_options = {**DEFAULT_37KEY_CLEAN_OPTIONS, **options}
        convert_to_37key_midi(raw_midi, clean_midi, options=clean_options)
        regenerated.append("Clean")

    if start_stage in {"clean", "piano_arranged"}:
        result = post_process_37key_midi(
            clean_midi, options={**options, "force_arrangement_stage": True}
        )
        if result.get("piano_arranged_midi"):
            regenerated.append("Piano Arranged")
        if result.get("piano_cover_midi"):
            regenerated.append("Piano Cover")
        regenerated.extend(("AI Optimized", "Pitch Corrected", "Final"))
        result["regenerated_stages"] = regenerated
        return result

    if not pitch_midi.exists() and ai_midi.exists():
        pitch_correct_37key_midi(ai_midi, output_midi=pitch_midi, options=options)
        regenerated.append("Pitch Corrected")
    elif not pitch_midi.exists():
        # Final cannot be built without its prerequisite chain. Generate that
        # chain only when the intermediate optimized MIDI is unavailable.
        result = post_process_37key_midi(
            clean_midi, options={**options, "force_arrangement_stage": True}
        )
        if result.get("piano_arranged_midi"):
            regenerated.append("Piano Arranged")
        if result.get("piano_cover_midi"):
            regenerated.append("Piano Cover")
        regenerated.extend(("AI Optimized", "Pitch Corrected", "Final"))
        result["regenerated_stages"] = regenerated
        return result

    # The pitch-corrected file is the direct prerequisite for Final. Reusing it
    # keeps a Final rebuild from touching Clean, arrangement, or optimization.
    smooth_37key_midi(pitch_midi, output_midi=final_midi, options=options)
    regenerated.append("Final")
    return {
        "clean_midi": clean_midi,
        "piano_arranged_midi": arranged_midi if arranged_midi.exists() else None,
        "piano_cover_midi": (
            piano_cover_midi_path(raw_midi)
            if piano_cover_midi_path(raw_midi).exists()
            else None
        ),
        "ai_optimized_midi": ai_midi if ai_midi.exists() else None,
        "pitch_corrected_midi": pitch_midi,
        "final_midi": final_midi,
        "detected_key": detect_key_for_midi(pitch_midi),
        "regenerated_stages": regenerated,
    }


def ensure_full_post_processing(raw_midi, options=None):
    raw_midi = Path(raw_midi)
    clean_midi = ensure_clean_37key_midi(raw_midi, options=options)
    piano_arranged_midi = piano_arranged_midi_path(clean_midi)
    arrangement_report = clean_midi.with_name(PIANO_ARRANGEMENT_REPORT_NAME)
    piano_cover_midi = piano_cover_midi_path(clean_midi)
    ai_midi = ai_optimized_midi_path(clean_midi)
    pitch_midi = pitch_corrected_midi_path(clean_midi)
    final_midi = final_37key_midi_path(clean_midi)
    newest_input_time = clean_midi.stat().st_mtime
    post_process_result = None

    if (
        options is None
        and piano_arranged_midi.exists()
        and arrangement_report.exists()
        and piano_cover_midi.exists()
        and ai_midi.exists()
        and pitch_midi.exists()
        and final_midi.exists()
        and piano_arranged_midi.stat().st_mtime >= newest_input_time
        and piano_cover_midi.stat().st_mtime >= piano_arranged_midi.stat().st_mtime
        and ai_midi.stat().st_mtime >= piano_arranged_midi.stat().st_mtime
        and pitch_midi.stat().st_mtime >= ai_midi.stat().st_mtime
        and final_midi.stat().st_mtime >= pitch_midi.stat().st_mtime
    ):
        print("Using existing Piano Arranged MIDI:", piano_arranged_midi)
        print("Using existing Piano Cover MIDI:", piano_cover_midi)
        print("Using existing AI Optimized MIDI:", ai_midi)
        print("Using existing Pitch Corrected MIDI:", pitch_midi)
        print("Using existing Final 37-Key MIDI:", final_midi)
        detected_key = detect_key_for_midi(pitch_midi)
        print("Detected key:", detected_key)
    else:
        print("Generating Piano Arranged MIDI:", piano_arranged_midi)
        print("Generating AI Optimized MIDI:", ai_midi)
        print("Generating Pitch Corrected MIDI:", pitch_midi)
        print("Generating Final 37-Key MIDI:", final_midi)
        post_process_result = post_process_37key_midi(clean_midi, options=options)
        piano_arranged_midi = post_process_result.get("piano_arranged_midi")
        arrangement_report = post_process_result.get("arrangement_report")
        piano_cover_midi = post_process_result.get("piano_cover_midi")
        detected_key = post_process_result["detected_key"]
        print("Detected key:", detected_key)

    arrangement_statistics = {}
    if arrangement_report and Path(arrangement_report).exists():
        arrangement_statistics = json.loads(
            Path(arrangement_report).read_text(encoding="utf-8")
        )
    analysis_report = build_midi_analysis_report(
        raw_midi,
        clean_midi,
        piano_arranged_midi,
        final_midi,
        detected_key,
        arrangement_statistics=arrangement_statistics,
    )
    report_path = export_midi_analysis_report(
        analysis_report, clean_midi.with_name(MIDI_ANALYSIS_REPORT_NAME)
    )

    return {
        "piano_arranged_midi": piano_arranged_midi,
        "arrangement_report": arrangement_report,
        "analysis_report": analysis_report,
        "report_path": report_path,
        "piano_cover_midi": piano_cover_midi,
        "clean_midi": clean_midi,
        "ai_optimized_midi": ai_midi,
        "pitch_corrected_midi": pitch_midi,
        "final_midi": final_midi,
        "detected_key": detected_key,
    }


def results_from_output_dir(base_dir):
    base_dir = Path(base_dir)
    wav_file = base_dir / "download" / "song.wav"
    vocals = base_dir / "separated" / "htdemucs" / "song" / "vocals.wav"
    no_vocals = base_dir / "separated" / "htdemucs" / "song" / "no_vocals.wav"
    vocal_midi = latest_midi_file(base_dir / "midi" / "vocals")
    accompaniment_midi = latest_midi_file(base_dir / "midi" / "accompaniment")

    if not accompaniment_midi:
        return None

    vocal_clean_midi = clean_37key_midi_path(vocal_midi) if vocal_midi else None
    accompaniment_clean_midi = clean_37key_midi_path(accompaniment_midi)
    vocal_arranged_midi = piano_arranged_midi_path(vocal_midi) if vocal_midi else None
    accompaniment_arranged_midi = piano_arranged_midi_path(accompaniment_midi)
    vocal_piano_midi = piano_cover_midi_path(vocal_midi) if vocal_midi else None
    accompaniment_piano_midi = piano_cover_midi_path(accompaniment_midi)
    vocal_ai_midi = ai_optimized_midi_path(vocal_midi) if vocal_midi else None
    accompaniment_ai_midi = ai_optimized_midi_path(accompaniment_midi)
    vocal_pitch_midi = pitch_corrected_midi_path(vocal_midi) if vocal_midi else None
    accompaniment_pitch_midi = pitch_corrected_midi_path(accompaniment_midi)
    vocal_final_midi = final_37key_midi_path(vocal_midi) if vocal_midi else None
    accompaniment_final_midi = final_37key_midi_path(accompaniment_midi)
    vocal_report_path = (
        Path(vocal_midi).with_name(MIDI_ANALYSIS_REPORT_NAME) if vocal_midi else None
    )
    accompaniment_report_path = Path(accompaniment_midi).with_name(
        MIDI_ANALYSIS_REPORT_NAME
    )

    return {
        "base_dir": base_dir,
        "wav_file": wav_file,
        "vocals": vocals,
        "no_vocals": no_vocals,
        "vocal_midi": vocal_midi,
        "accompaniment_midi": accompaniment_midi,
        "vocal_report_path": (
            vocal_report_path if vocal_report_path and vocal_report_path.exists() else None
        ),
        "accompaniment_report_path": (
            accompaniment_report_path if accompaniment_report_path.exists() else None
        ),
        "vocal_analysis_report": (
            load_midi_analysis_report(vocal_report_path)
            if vocal_report_path and vocal_report_path.exists()
            else None
        ),
        "accompaniment_analysis_report": (
            load_midi_analysis_report(accompaniment_report_path)
            if accompaniment_report_path.exists()
            else None
        ),
        "vocal_piano_arranged_midi": (
            vocal_arranged_midi if vocal_arranged_midi and vocal_arranged_midi.exists() else None
        ),
        "accompaniment_piano_arranged_midi": (
            accompaniment_arranged_midi if accompaniment_arranged_midi.exists() else None
        ),
        "vocal_piano_cover_midi": (
            vocal_piano_midi if vocal_piano_midi and vocal_piano_midi.exists() else None
        ),
        "accompaniment_piano_cover_midi": (
            accompaniment_piano_midi if accompaniment_piano_midi.exists() else None
        ),
        "vocal_clean_midi": (
            vocal_clean_midi if vocal_clean_midi and vocal_clean_midi.exists() else None
        ),
        "accompaniment_clean_midi": (
            accompaniment_clean_midi if accompaniment_clean_midi.exists() else None
        ),
        "vocal_ai_optimized_midi": vocal_ai_midi if vocal_ai_midi and vocal_ai_midi.exists() else None,
        "accompaniment_ai_optimized_midi": (
            accompaniment_ai_midi if accompaniment_ai_midi.exists() else None
        ),
        "vocal_pitch_corrected_midi": (
            vocal_pitch_midi if vocal_pitch_midi and vocal_pitch_midi.exists() else None
        ),
        "accompaniment_pitch_corrected_midi": (
            accompaniment_pitch_midi if accompaniment_pitch_midi.exists() else None
        ),
        "vocal_final_midi": vocal_final_midi if vocal_final_midi and vocal_final_midi.exists() else None,
        "accompaniment_final_midi": (
            accompaniment_final_midi if accompaniment_final_midi.exists() else None
        ),
        "cached": True,
    }


def list_converted_outputs(output_root="output"):
    output_root = Path(output_root)
    if not output_root.exists():
        return []

    converted = []
    for path in output_root.iterdir():
        if path.is_dir() and results_from_output_dir(path):
            converted.append(path)

    return sorted(converted, key=lambda path: path.stat().st_mtime, reverse=True)


def ensure_clean_results(results, include_vocals=False):
    if not results:
        return results

    if include_vocals and results.get("vocal_midi"):
        vocal_outputs = ensure_full_post_processing(results["vocal_midi"])
        results["vocal_piano_arranged_midi"] = vocal_outputs["piano_arranged_midi"]
        results["vocal_analysis_report"] = vocal_outputs["analysis_report"]
        results["vocal_report_path"] = vocal_outputs["report_path"]
        results["vocal_piano_cover_midi"] = vocal_outputs["piano_cover_midi"]
        results["vocal_clean_midi"] = vocal_outputs["clean_midi"]
        results["vocal_ai_optimized_midi"] = vocal_outputs["ai_optimized_midi"]
        results["vocal_pitch_corrected_midi"] = vocal_outputs["pitch_corrected_midi"]
        results["vocal_final_midi"] = vocal_outputs["final_midi"]
        results["vocal_detected_key"] = vocal_outputs["detected_key"]
    if results.get("accompaniment_midi"):
        accompaniment_outputs = ensure_full_post_processing(results["accompaniment_midi"])
        results["accompaniment_piano_arranged_midi"] = accompaniment_outputs[
            "piano_arranged_midi"
        ]
        results["accompaniment_analysis_report"] = accompaniment_outputs[
            "analysis_report"
        ]
        results["accompaniment_report_path"] = accompaniment_outputs["report_path"]
        results["accompaniment_piano_cover_midi"] = accompaniment_outputs["piano_cover_midi"]
        results["accompaniment_clean_midi"] = accompaniment_outputs["clean_midi"]
        results["accompaniment_ai_optimized_midi"] = accompaniment_outputs["ai_optimized_midi"]
        results["accompaniment_pitch_corrected_midi"] = accompaniment_outputs[
            "pitch_corrected_midi"
        ]
        results["accompaniment_final_midi"] = accompaniment_outputs["final_midi"]
        results["accompaniment_detected_key"] = accompaniment_outputs["detected_key"]
    return results


def download_youtube_audio(url, output_dir, cancel_token=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_file = output_dir / "song.wav"
    if wav_file.exists():
        print("Using existing WAV:", wav_file)
        return wav_file

    output_template = str(output_dir / "song.%(ext)s")
    ffmpeg_location = find_ffmpeg_location()
    if not ffmpeg_location:
        raise RuntimeError("ffmpeg/ffprobe not found")

    run(
        [
            find_executable("yt-dlp"),
            "--no-playlist",
            "--no-check-certificates",
            "--socket-timeout",
            "20",
            "--retries",
            "2",
            "-x",
            "--ffmpeg-location",
            ffmpeg_location,
            "--audio-format",
            "wav",
            "-o",
            output_template,
            url,
        ],
        cancel_token=cancel_token,
        timeout=900,
    )

    if not wav_file.exists():
        raise FileNotFoundError("song.wav not found after download")

    return wav_file


def prepare_local_audio(audio_file, output_dir, cancel_token=None):
    audio_file = Path(audio_file)
    if not audio_file.exists():
        raise FileNotFoundError(str(audio_file))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_file = output_dir / "song.wav"
    if wav_file.exists():
        print("Using existing WAV:", wav_file)
        return wav_file

    ffmpeg_location = find_ffmpeg_location()
    if not ffmpeg_location:
        raise RuntimeError("ffmpeg/ffprobe not found")

    ffmpeg_exe = str(Path(ffmpeg_location) / "ffmpeg.exe")
    run(
        [
            ffmpeg_exe,
            "-y",
            "-i",
            str(audio_file),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "48000",
            str(wav_file),
        ],
        cancel_token=cancel_token,
    )

    if not wav_file.exists():
        raise FileNotFoundError("song.wav not found after local audio conversion")

    return wav_file


def separate_vocals(wav_file, output_dir, cancel_token=None, device=None):
    output_dir = Path(output_dir)
    song_name = wav_file.stem
    separated_dir = output_dir / "htdemucs" / song_name

    vocals = separated_dir / "vocals.wav"
    no_vocals = separated_dir / "no_vocals.wav"
    if vocals.exists() and no_vocals.exists():
        print("Using existing separated audio:", separated_dir)
        return vocals, no_vocals

    cmd = [
        find_executable("demucs"),
        "--two-stems=vocals",
        "-o",
        str(output_dir),
    ]
    if device:
        cmd.extend(["--device", device])
    cmd.append(str(wav_file))

    run(cmd, cancel_token=cancel_token)

    if not vocals.exists():
        raise FileNotFoundError("vocals.wav not found")

    if not no_vocals.exists():
        raise FileNotFoundError("no_vocals.wav not found")

    return vocals, no_vocals


def _report_basic_pitch_message(message, progress_callback=None):
    print(message)
    if progress_callback is not None:
        progress_callback(message)


def get_basic_pitch_backend_diagnostics():
    try:
        import onnxruntime
    except Exception as exc:
        return {
            "version": "unavailable",
            "providers": [],
            "cuda_available": False,
            "error": str(exc),
        }

    providers = list(onnxruntime.get_available_providers())
    return {
        "version": onnxruntime.__version__,
        "providers": providers,
        "cuda_available": "CUDAExecutionProvider" in providers,
        "error": None,
    }


def convert_audio_to_midi(
    audio_file,
    output_dir,
    cancel_token=None,
    progress_callback=None,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_midi = latest_midi_file(output_dir)
    if existing_midi:
        print("Using existing MIDI:", existing_midi)
        return existing_midi

    diagnostics = get_basic_pitch_backend_diagnostics()
    _report_basic_pitch_message(
        f"ONNX Runtime version: {diagnostics['version']}", progress_callback
    )
    _report_basic_pitch_message(
        f"ONNX Runtime available providers: {diagnostics['providers']}",
        progress_callback,
    )
    _report_basic_pitch_message(
        "CUDAExecutionProvider available: "
        + ("yes" if diagnostics["cuda_available"] else "no"),
        progress_callback,
    )

    basic_pitch = find_executable("basic-pitch")
    tensorflow_cmd = [basic_pitch, str(output_dir), str(audio_file)]
    if diagnostics["error"] is not None:
        _report_basic_pitch_message(
            f"ONNX backend unavailable: {diagnostics['error']}", progress_callback
        )
        _report_basic_pitch_message(
            "Basic Pitch CLI is using TensorFlow backend.", progress_callback
        )
        run(tensorflow_cmd, cancel_token=cancel_token)
    else:
        onnx_cmd = [
            basic_pitch,
            "--model-serialization",
            "onnx",
            str(output_dir),
            str(audio_file),
        ]
        _report_basic_pitch_message(
            "Basic Pitch backend: ONNX. Basic Pitch 0.4.0 may still import "
            "TensorFlow during CLI startup.",
            progress_callback,
        )
        _report_basic_pitch_message(
            "Basic Pitch 0.4.0 uses CPUExecutionProvider for its ONNX session.",
            progress_callback,
        )
        try:
            run(onnx_cmd, cancel_token=cancel_token)
        except subprocess.CalledProcessError:
            _report_basic_pitch_message(
                "Basic Pitch ONNX backend failed; retrying with TensorFlow fallback.",
                progress_callback,
            )
            _report_basic_pitch_message(
                "Basic Pitch CLI is using TensorFlow backend.", progress_callback
            )
            run(tensorflow_cmd, cancel_token=cancel_token)

    midi_file = latest_midi_file(output_dir)
    if not midi_file:
        raise FileNotFoundError("No MIDI file generated")

    return midi_file


def youtube_to_midi(
    url,
    base_dir=None,
    cancel_token=None,
    demucs_device=None,
    convert_vocals_midi=False,
    progress_callback=None,
):
    base_dir = Path(base_dir) if base_dir else output_dir_for_url(url, cancel_token=cancel_token)
    download_dir = base_dir / "download"
    separated_dir = base_dir / "separated"
    midi_dir = base_dir / "midi"

    base_dir.mkdir(parents=True, exist_ok=True)

    cached_results = results_from_output_dir(base_dir)
    if cached_results:
        print("Using cached conversion:", base_dir)
        if convert_vocals_midi and not cached_results.get("vocal_midi"):
            print("Cached output has no vocals MIDI. Converting vocals to MIDI...")
            cached_results["vocal_midi"] = convert_audio_to_midi(
                cached_results["vocals"],
                midi_dir / "vocals",
                cancel_token=cancel_token,
                progress_callback=progress_callback,
            )
        return ensure_clean_results(cached_results, include_vocals=convert_vocals_midi)

    print("Step 1: Downloading YouTube audio...")
    wav_file = download_youtube_audio(url, download_dir, cancel_token=cancel_token)

    print("Step 2: Separating vocals and accompaniment...")
    vocals, no_vocals = separate_vocals(
        wav_file, separated_dir, cancel_token=cancel_token, device=demucs_device
    )

    vocal_midi = None
    vocal_clean_midi = None
    if convert_vocals_midi:
        print("Step 3: Converting vocals to MIDI...")
        vocal_midi = convert_audio_to_midi(
            vocals,
            midi_dir / "vocals",
            cancel_token=cancel_token,
            progress_callback=progress_callback,
        )
    else:
        print("Step 3: Skipping vocals MIDI conversion.")

    print("Step 4: Converting accompaniment to MIDI...")
    accompaniment_midi = convert_audio_to_midi(
        no_vocals,
        midi_dir / "accompaniment",
        cancel_token=cancel_token,
        progress_callback=progress_callback,
    )

    print("Step 5: Generating Piano Cover and 37-Key MIDI files...")
    if vocal_midi:
        vocal_outputs = ensure_full_post_processing(vocal_midi)
        vocal_piano_arranged_midi = vocal_outputs["piano_arranged_midi"]
        vocal_analysis_report = vocal_outputs["analysis_report"]
        vocal_report_path = vocal_outputs["report_path"]
        vocal_piano_cover_midi = vocal_outputs["piano_cover_midi"]
        vocal_clean_midi = vocal_outputs["clean_midi"]
        vocal_ai_optimized_midi = vocal_outputs["ai_optimized_midi"]
        vocal_pitch_corrected_midi = vocal_outputs["pitch_corrected_midi"]
        vocal_final_midi = vocal_outputs["final_midi"]
        vocal_detected_key = vocal_outputs["detected_key"]
    else:
        vocal_piano_arranged_midi = None
        vocal_analysis_report = None
        vocal_report_path = None
        vocal_piano_cover_midi = None
        vocal_ai_optimized_midi = None
        vocal_pitch_corrected_midi = None
        vocal_final_midi = None
        vocal_detected_key = None
    accompaniment_outputs = ensure_full_post_processing(accompaniment_midi)
    accompaniment_piano_arranged_midi = accompaniment_outputs["piano_arranged_midi"]
    accompaniment_analysis_report = accompaniment_outputs["analysis_report"]
    accompaniment_report_path = accompaniment_outputs["report_path"]
    accompaniment_piano_cover_midi = accompaniment_outputs["piano_cover_midi"]
    accompaniment_clean_midi = accompaniment_outputs["clean_midi"]
    accompaniment_ai_optimized_midi = accompaniment_outputs["ai_optimized_midi"]
    accompaniment_pitch_corrected_midi = accompaniment_outputs["pitch_corrected_midi"]
    accompaniment_final_midi = accompaniment_outputs["final_midi"]
    accompaniment_detected_key = accompaniment_outputs["detected_key"]

    return {
        "base_dir": base_dir,
        "wav_file": wav_file,
        "vocals": vocals,
        "no_vocals": no_vocals,
        "vocal_midi": vocal_midi,
        "accompaniment_midi": accompaniment_midi,
        "vocal_analysis_report": vocal_analysis_report,
        "accompaniment_analysis_report": accompaniment_analysis_report,
        "vocal_report_path": vocal_report_path,
        "accompaniment_report_path": accompaniment_report_path,
        "vocal_piano_arranged_midi": vocal_piano_arranged_midi,
        "accompaniment_piano_arranged_midi": accompaniment_piano_arranged_midi,
        "vocal_piano_cover_midi": vocal_piano_cover_midi,
        "accompaniment_piano_cover_midi": accompaniment_piano_cover_midi,
        "vocal_clean_midi": vocal_clean_midi,
        "accompaniment_clean_midi": accompaniment_clean_midi,
        "vocal_ai_optimized_midi": vocal_ai_optimized_midi,
        "accompaniment_ai_optimized_midi": accompaniment_ai_optimized_midi,
        "vocal_pitch_corrected_midi": vocal_pitch_corrected_midi,
        "accompaniment_pitch_corrected_midi": accompaniment_pitch_corrected_midi,
        "vocal_final_midi": vocal_final_midi,
        "accompaniment_final_midi": accompaniment_final_midi,
        "vocal_detected_key": vocal_detected_key,
        "accompaniment_detected_key": accompaniment_detected_key,
        "cached": False,
    }


def audio_file_to_midi(
    audio_file,
    base_dir=None,
    cancel_token=None,
    demucs_device=None,
    convert_vocals_midi=False,
    progress_callback=None,
):
    base_dir = Path(base_dir) if base_dir else output_dir_for_audio_file(audio_file)
    download_dir = base_dir / "download"
    separated_dir = base_dir / "separated"
    midi_dir = base_dir / "midi"

    base_dir.mkdir(parents=True, exist_ok=True)

    cached_results = results_from_output_dir(base_dir)
    if cached_results:
        print("Using cached conversion:", base_dir)
        if convert_vocals_midi and not cached_results.get("vocal_midi"):
            print("Cached output has no vocals MIDI. Converting vocals to MIDI...")
            cached_results["vocal_midi"] = convert_audio_to_midi(
                cached_results["vocals"],
                midi_dir / "vocals",
                cancel_token=cancel_token,
                progress_callback=progress_callback,
            )
        return ensure_clean_results(cached_results, include_vocals=convert_vocals_midi)

    print("Step 1: Preparing local audio...")
    wav_file = prepare_local_audio(audio_file, download_dir, cancel_token=cancel_token)

    print("Step 2: Separating vocals and accompaniment...")
    vocals, no_vocals = separate_vocals(
        wav_file, separated_dir, cancel_token=cancel_token, device=demucs_device
    )

    vocal_midi = None
    vocal_clean_midi = None
    if convert_vocals_midi:
        print("Step 3: Converting vocals to MIDI...")
        vocal_midi = convert_audio_to_midi(
            vocals,
            midi_dir / "vocals",
            cancel_token=cancel_token,
            progress_callback=progress_callback,
        )
    else:
        print("Step 3: Skipping vocals MIDI conversion.")

    print("Step 4: Converting accompaniment to MIDI...")
    accompaniment_midi = convert_audio_to_midi(
        no_vocals,
        midi_dir / "accompaniment",
        cancel_token=cancel_token,
        progress_callback=progress_callback,
    )

    print("Step 5: Generating Piano Cover and 37-Key MIDI files...")
    if vocal_midi:
        vocal_outputs = ensure_full_post_processing(vocal_midi)
        vocal_piano_arranged_midi = vocal_outputs["piano_arranged_midi"]
        vocal_analysis_report = vocal_outputs["analysis_report"]
        vocal_report_path = vocal_outputs["report_path"]
        vocal_piano_cover_midi = vocal_outputs["piano_cover_midi"]
        vocal_clean_midi = vocal_outputs["clean_midi"]
        vocal_ai_optimized_midi = vocal_outputs["ai_optimized_midi"]
        vocal_pitch_corrected_midi = vocal_outputs["pitch_corrected_midi"]
        vocal_final_midi = vocal_outputs["final_midi"]
        vocal_detected_key = vocal_outputs["detected_key"]
    else:
        vocal_piano_arranged_midi = None
        vocal_analysis_report = None
        vocal_report_path = None
        vocal_piano_cover_midi = None
        vocal_ai_optimized_midi = None
        vocal_pitch_corrected_midi = None
        vocal_final_midi = None
        vocal_detected_key = None
    accompaniment_outputs = ensure_full_post_processing(accompaniment_midi)
    accompaniment_piano_arranged_midi = accompaniment_outputs["piano_arranged_midi"]
    accompaniment_analysis_report = accompaniment_outputs["analysis_report"]
    accompaniment_report_path = accompaniment_outputs["report_path"]
    accompaniment_piano_cover_midi = accompaniment_outputs["piano_cover_midi"]
    accompaniment_clean_midi = accompaniment_outputs["clean_midi"]
    accompaniment_ai_optimized_midi = accompaniment_outputs["ai_optimized_midi"]
    accompaniment_pitch_corrected_midi = accompaniment_outputs["pitch_corrected_midi"]
    accompaniment_final_midi = accompaniment_outputs["final_midi"]
    accompaniment_detected_key = accompaniment_outputs["detected_key"]

    return {
        "base_dir": base_dir,
        "wav_file": wav_file,
        "vocals": vocals,
        "no_vocals": no_vocals,
        "vocal_midi": vocal_midi,
        "accompaniment_midi": accompaniment_midi,
        "vocal_analysis_report": vocal_analysis_report,
        "accompaniment_analysis_report": accompaniment_analysis_report,
        "vocal_report_path": vocal_report_path,
        "accompaniment_report_path": accompaniment_report_path,
        "vocal_piano_arranged_midi": vocal_piano_arranged_midi,
        "accompaniment_piano_arranged_midi": accompaniment_piano_arranged_midi,
        "vocal_piano_cover_midi": vocal_piano_cover_midi,
        "accompaniment_piano_cover_midi": accompaniment_piano_cover_midi,
        "vocal_clean_midi": vocal_clean_midi,
        "accompaniment_clean_midi": accompaniment_clean_midi,
        "vocal_ai_optimized_midi": vocal_ai_optimized_midi,
        "accompaniment_ai_optimized_midi": accompaniment_ai_optimized_midi,
        "vocal_pitch_corrected_midi": vocal_pitch_corrected_midi,
        "accompaniment_pitch_corrected_midi": accompaniment_pitch_corrected_midi,
        "vocal_final_midi": vocal_final_midi,
        "accompaniment_final_midi": accompaniment_final_midi,
        "vocal_detected_key": vocal_detected_key,
        "accompaniment_detected_key": accompaniment_detected_key,
        "cached": False,
    }
