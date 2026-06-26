from pathlib import Path
import re

from tools import find_executable, find_ffmpeg_location, run, run_capture


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
            "--print",
            "%(title)s\t%(id)s",
            "--skip-download",
            url,
        ],
        cancel_token=cancel_token,
    ).strip()

    line = output.splitlines()[-1] if output else "youtube_audio\tunknown"
    if "\t" in line:
        title, video_id = line.rsplit("\t", 1)
    else:
        title, video_id = line, "unknown"

    return title.strip() or "youtube_audio", video_id.strip() or "unknown"


def output_dir_for_url(url, output_root="output", cancel_token=None):
    title, video_id = get_youtube_info(url, cancel_token=cancel_token)
    folder_name = sanitize_filename(f"{title}_{video_id}")
    return Path(output_root) / folder_name


def output_dir_for_audio_file(audio_file, output_root="output"):
    audio_file = Path(audio_file)
    folder_name = sanitize_filename(f"{audio_file.stem}_local")
    return Path(output_root) / folder_name


def latest_midi_file(output_dir):
    output_dir = Path(output_dir)
    midi_files = sorted(
        output_dir.glob("*.mid"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    return midi_files[0] if midi_files else None


def results_from_output_dir(base_dir):
    base_dir = Path(base_dir)
    wav_file = base_dir / "download" / "song.wav"
    vocals = base_dir / "separated" / "htdemucs" / "song" / "vocals.wav"
    no_vocals = base_dir / "separated" / "htdemucs" / "song" / "no_vocals.wav"
    vocal_midi = latest_midi_file(base_dir / "midi" / "vocals")
    accompaniment_midi = latest_midi_file(base_dir / "midi" / "accompaniment")

    if not vocal_midi or not accompaniment_midi:
        return None

    return {
        "base_dir": base_dir,
        "wav_file": wav_file,
        "vocals": vocals,
        "no_vocals": no_vocals,
        "vocal_midi": vocal_midi,
        "accompaniment_midi": accompaniment_midi,
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


def convert_audio_to_midi(audio_file, output_dir, cancel_token=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_midi = latest_midi_file(output_dir)
    if existing_midi:
        print("Using existing MIDI:", existing_midi)
        return existing_midi

    run(
        [find_executable("basic-pitch"), str(output_dir), str(audio_file)],
        cancel_token=cancel_token,
    )

    midi_file = latest_midi_file(output_dir)
    if not midi_file:
        raise FileNotFoundError("No MIDI file generated")

    return midi_file


def youtube_to_midi(url, base_dir=None, cancel_token=None, demucs_device=None):
    base_dir = Path(base_dir) if base_dir else output_dir_for_url(url, cancel_token=cancel_token)
    download_dir = base_dir / "download"
    separated_dir = base_dir / "separated"
    midi_dir = base_dir / "midi"

    base_dir.mkdir(parents=True, exist_ok=True)

    cached_results = results_from_output_dir(base_dir)
    if cached_results:
        print("Using cached conversion:", base_dir)
        return cached_results

    print("Step 1: Downloading YouTube audio...")
    wav_file = download_youtube_audio(url, download_dir, cancel_token=cancel_token)

    print("Step 2: Separating vocals and accompaniment...")
    vocals, no_vocals = separate_vocals(
        wav_file, separated_dir, cancel_token=cancel_token, device=demucs_device
    )

    print("Step 3: Converting vocals to MIDI...")
    vocal_midi = convert_audio_to_midi(vocals, midi_dir / "vocals", cancel_token=cancel_token)

    print("Step 4: Converting accompaniment to MIDI...")
    accompaniment_midi = convert_audio_to_midi(
        no_vocals, midi_dir / "accompaniment", cancel_token=cancel_token
    )

    return {
        "base_dir": base_dir,
        "wav_file": wav_file,
        "vocals": vocals,
        "no_vocals": no_vocals,
        "vocal_midi": vocal_midi,
        "accompaniment_midi": accompaniment_midi,
        "cached": False,
    }


def audio_file_to_midi(audio_file, base_dir=None, cancel_token=None, demucs_device=None):
    base_dir = Path(base_dir) if base_dir else output_dir_for_audio_file(audio_file)
    download_dir = base_dir / "download"
    separated_dir = base_dir / "separated"
    midi_dir = base_dir / "midi"

    base_dir.mkdir(parents=True, exist_ok=True)

    cached_results = results_from_output_dir(base_dir)
    if cached_results:
        print("Using cached conversion:", base_dir)
        return cached_results

    print("Step 1: Preparing local audio...")
    wav_file = prepare_local_audio(audio_file, download_dir, cancel_token=cancel_token)

    print("Step 2: Separating vocals and accompaniment...")
    vocals, no_vocals = separate_vocals(
        wav_file, separated_dir, cancel_token=cancel_token, device=demucs_device
    )

    print("Step 3: Converting vocals to MIDI...")
    vocal_midi = convert_audio_to_midi(vocals, midi_dir / "vocals", cancel_token=cancel_token)

    print("Step 4: Converting accompaniment to MIDI...")
    accompaniment_midi = convert_audio_to_midi(
        no_vocals, midi_dir / "accompaniment", cancel_token=cancel_token
    )

    return {
        "base_dir": base_dir,
        "wav_file": wav_file,
        "vocals": vocals,
        "no_vocals": no_vocals,
        "vocal_midi": vocal_midi,
        "accompaniment_midi": accompaniment_midi,
        "cached": False,
    }
