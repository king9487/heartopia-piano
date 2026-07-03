# Heartopia Piano

Heartopia Piano is a Windows desktop and command-line tool for turning YouTube videos, local audio, and existing MIDI files into playable arrangements for Heartopia's 37-key piano (`C2`-`C5`). It combines source separation, transcription, MIDI cleanup and arrangement, analysis, editing, preview, and keyboard playback.

## Features

- **YouTube conversion** - downloads one video's audio with `yt-dlp`, converts it to WAV, and runs the audio-to-MIDI pipeline.
- **Local audio conversion** - accepts a local audio file and processes it through the same separation and transcription stages without downloading it.
- **External MIDI import** - inspects `.mid` and `.midi` files, preserves an `imported.mid` working copy, and can send it through the Heartopia processing stages. Cleanup, arrangement, optimization, and pitch correction can be skipped independently.
- **Basic Pitch transcription** - transcribes the separated accompaniment and, optionally, the vocal stem to raw MIDI.
- **Demucs separation** - uses the `htdemucs` model to create `vocals.wav` and `no_vocals.wav`, with automatic, CPU, or CUDA device selection.
- **Rule Engine** - filters weak or short notes, fits pitches into the playable range, limits dense onset windows, supports melody-only cleanup, and preserves MIDI tempo/tick timing while writing `clean_37key.mid`.
- **Piano Arranger** - identifies melody, harmony, and bass roles; favors melodic continuity; simplifies accompaniment; reduces repeated notes; and writes arrangement statistics.
- **AI Optimizer** - provides `None`, local `Rule`, and optional `OpenAI` modes. OpenAI failures fall back to local rule optimization.
- **Pitch Correction** - detects a likely key and corrects unstable pitches toward nearby scale tones while keeping notes in range.
- **MIDI Studio** - offers external MIDI-output playback, play/pause/stop, seeking, range playback/export, Piano Roll, and Staff View.
- **MIDI Editor** - lists note timing, pitch, velocity, and suspicious-note reasons; supports deleting selected, repeated-pitch, or suspicious notes; and saves `edited_37key.mid`.
- **Playback to Heartopia** - maps MIDI notes `C2`-`C5` to the game's keyboard controls, with speed, focus delay, transpose, chord-gap, and minimum-hold settings. Press `F8` to stop playback.
- **MIDI Analysis** - reports duration, tempo, detected key, note counts at each processing stage, and Piano Arranger removal, merge, octave-shift, bass, harmony, and melody statistics in `report.json`.
- **Version comparison and export** - selects any generated MIDI stage, compares two versions with A/B playback, transposes to a target major key, and exports a selected range as `chorus_37key.mid`.

## Processing Pipeline

YouTube and local audio first pass through Demucs and Basic Pitch. External MIDI starts at the MIDI pipeline directly.

```text
YouTube ───────┐
               ├─> Demucs separation ─> Basic Pitch transcription ─┐
Local Audio ───┘                                                    │
                                                                    ├─> Cleanup
External MIDI ──────────────────────────────────────────────────────┘      │
                                                                           ↓
                                                                    Piano Arranger
                                                                           ↓
                                                                     AI Optimizer
                                                                           ↓
                                                                    Pitch Correction
                                                                           ↓
                                                                      Final MIDI
```

The main MIDI artifacts are:

1. A Basic Pitch-generated raw MIDI, or `imported.mid` for external MIDI.
2. `clean_37key.mid` from the Rule Engine.
3. `piano_arranged_37key.mid` from the selected arrangement style.
4. `ai_optimized_37key.mid` from the selected optimizer mode.
5. `pitch_corrected_37key.mid` after key-aware pitch correction.
6. `final_37key.mid` after final smoothing, minimum-duration enforcement, and timing quantization (10 ms by default).

Skipped external-MIDI stages still create their named output as a pass-through copy, so downstream stages and version selection remain consistent. The `original` arrangement style leaves the cleaned material unchanged, `melody_only` extracts a top line, and `piano_cover` produces a melody-led arrangement with simplified harmony and bass. `piano_cover_37key.mid` is retained as a compatibility copy of an arranged result.

## Project Structure

```text
youtube_to_midi.py       Desktop application entry point
cli_app.py               Interactive command-line conversion and playback
converter.py             Source acquisition and end-to-end pipeline orchestration
tools.py                 Executable discovery, subprocess control, and cancellation

midi_rule_engine.py      Timing-preserving cleanup and 37-key range fitting
midi_piano_arranger.py   Melody-led piano arrangement and statistics
midi_ai_optimizer.py     Local/OpenAI optimization, arrangement modes, pitch correction,
                         and final smoothing
midi_analysis.py         MIDI inspection and report.json generation
midi_to_keyboard.py      MIDI event parsing, preview, cleanup helpers, and key playback
midi_editor.py           Suspicious-note detection and edited MIDI writing
midi_range.py            Time-range extraction to chorus_37key.mid
transpose.py             Major-key detection and transposition
playable_range.py        Standalone note-range folding and grouping helpers

ui/app.py                Tk application lifecycle and mixin composition
ui/actions/              Conversion, optimization, playback, Studio, and editor callbacks
ui/helpers/              Shared state, selection, analysis, logging, and queue handling
ui/panels/               Notebook tabs, Studio views, and widget layout
ui/presets.py             Safe, Balanced, Aggressive, and Piano Cover processing presets

test_*.py                Unit and integration-oriented MIDI/UI behavior tests
output/                   Generated source folders, stems, MIDI stages, and reports
requirements.txt          Python dependency set (CUDA 12.1 PyTorch by default)
setup.ps1                 Windows virtual-environment setup script
start_ui.bat              Desktop launcher
start_cli.bat             CLI launcher
```

The active processing path uses `midi_rule_engine.py` for cleanup. The small panel wrapper modules retained under `ui/panels/` exist for compatibility; the live six-tab layout is composed by `ui/panels/main_panel.py`.

## UI

The desktop application contains six tabs.

### Main

Select a YouTube video, local audio file, or external MIDI file. YouTube input accepts a URL; local audio opens a file picker; MIDI opens the import workflow. Audio conversion also offers Demucs device selection and optional vocal-stem transcription. The tab shows the current MIDI, provides Open, Preview, Play to Game, and Stop actions, and displays conversion logs and status.

### Import

Review metadata for the selected external MIDI: filename, duration, tempo, detected key, tracks, PPQ, total notes, playable/out-of-range counts, playable percentage, and a direct-play or optimization recommendation. The original can be previewed, played, or opened without processing. Processing controls can skip Cleanup, Piano Arranger, AI Optimizer, or Pitch Correction and optionally preview the result immediately.

### Optimization

Choose a Safe, Balanced, Aggressive, or Piano Cover preset, then adjust individual stages:

- Cleanup thresholds, simultaneous-note limits, range mode, and melody-only filtering.
- Piano Arranger melody count, onset window, and `original`, `melody_only`, or `piano_cover` style.
- `None`, `Rule`, or `OpenAI` optimizer mode.
- Rebuild actions for Clean, Piano Arranged, and Final outputs.
- Automatic or overridden source-key detection and transposition to a target major key.

### Playback

Choose vocals or accompaniment, load a previous folder from `output/`, and select any available raw, cleaned, arranged, optimized, pitch-corrected, final, transposed, or edited MIDI. A/B controls play two versions and can make either one current. Playback settings control window topmost behavior, speed, focus countdown, semitone transpose, chord staggering, and minimum key-hold time.

### Studio

Load the current MIDI into a seekable player backed by an available MIDI output device. Play, pause, stop, seek, play/export a time range, and switch between a compact Piano Roll and zoomable, horizontally scrollable Staff View. The embedded MIDI Editor marks suspicious notes and supports selective deletion before saving `edited_37key.mid`.

Studio playback requires a MIDI output exposed through `python-rtmidi`, such as a hardware port or software synthesizer. This is separate from **Play to Game**, which sends computer-keyboard events to Heartopia.

### Analysis

Display the selected output folder's `report.json`: song duration, tempo, detected key, raw/clean/arranged/final note counts, and Piano Arranger statistics. Selecting a MIDI from a folder without a report clears the panel rather than inferring missing pipeline data.

## Screenshots

> Placeholder: Main conversion tab

<!-- Add screenshot: docs/screenshots/main.png -->

> Placeholder: Optimization tab

<!-- Add screenshot: docs/screenshots/optimization.png -->

> Placeholder: MIDI Studio and Editor

<!-- Add screenshot: docs/screenshots/studio.png -->

> Placeholder: MIDI Analysis tab

<!-- Add screenshot: docs/screenshots/analysis.png -->

## Installation

### Requirements

- Windows (the setup and launch scripts are Windows-specific, and Heartopia playback uses simulated keyboard input).
- Python 3.11 or newer is recommended. `setup.ps1` searches common Python 3.10, 3.11, and 3.12 installations.
- FFmpeg and FFprobe available on `PATH`.
- Internet access for YouTube downloads, model/package installation, and optional OpenAI optimization.

The checked-in Python dependencies are:

- `yt-dlp` for YouTube metadata and audio download.
- `torch==2.3.1+cu121` and `torchaudio==2.3.1+cu121` from the PyTorch CUDA 12.1 index.
- `demucs` for source separation.
- `basic-pitch` for audio transcription.
- `mido` and `python-rtmidi` for MIDI files and output ports.
- `keyboard` for Heartopia key playback.

Tkinter ships with the standard Windows Python installer. OpenAI mode uses Python's standard HTTP library, so no OpenAI SDK is required; set `OPENAI_API_KEY` to enable it. Without a key—or if the request fails—the optimizer uses local rules.

The default `requirements.txt` targets an NVIDIA CUDA 12.1 PyTorch build. CPU-only systems need a compatible CPU build of PyTorch and Torchaudio and should omit or replace the two CUDA-pinned entries when creating their environment.

### Install FFmpeg

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

Open a new terminal afterward so the updated `PATH` is visible.

### Automated setup

From the project directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

The script recreates `.venv`, upgrades `pip`, installs `requirements.txt`, and checks for FFmpeg. Do not use it if the existing `.venv` contains packages you need to preserve.

### Manual setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Run

Desktop application:

```powershell
.\.venv\Scripts\python.exe .\youtube_to_midi.py
```

Command-line application:

```powershell
.\.venv\Scripts\python.exe .\cli_app.py
```

The CLI accepts a YouTube URL or local audio path. Optional `--original-key` and `--target-key` arguments control major-key transposition. External MIDI import is currently provided by the desktop UI.

Generated files are stored under `output/`: YouTube folders use the video title and ID, local-audio folders end in `_local`, and imported-MIDI folders end in `_midi`.

## Roadmap

- Make generated-file caching and stage provenance explicit and reliable.
- Unify job cancellation and shutdown behavior across conversion and playback tasks.
- Preserve more performance metadata, including controllers, channels, and sustain semantics, through MIDI transformations.
- Improve Studio scheduling accuracy and separate playback timing from UI refresh timing.
- Consolidate duplicate cleanup/writer paths and split large orchestration modules into smaller services.
- Add reproducible CPU/CUDA dependency profiles and broader end-to-end, cancellation, and UI coverage.

## License

No license file is currently included.
