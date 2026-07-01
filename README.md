# Heartopia Piano

Heartopia Piano converts YouTube videos or local audio into playable MIDI arrangements for a 37-key piano interface. It combines source separation, audio transcription, MIDI cleanup, arrangement tools, editing, preview, and keyboard playback in one desktop application.

## Features

- Convert a YouTube URL or local audio file to MIDI.
- Separate vocals and accompaniment with Demucs.
- Transcribe audio with Basic Pitch.
- Optimize notes for the supported 37-key range (`C2`–`C5`).
- Generate clean, AI/rule-optimized, pitch-corrected, and final playable MIDI files.
- Use arrangement styles:
  - `original`
  - `melody_only`
  - `piano_cover`
- Create `piano_cover_37key.mid` with melody priority, simplified harmony, and reduced bass repetition.
- Optimize locally with rules or optionally with the OpenAI API.
- Detect a likely key and correct short, weak, or unstable pitches.
- Preview mapped notes before playback.
- Send MIDI notes as keyboard input to the target piano interface.
- Load external `.mid` and `.midi` files.
- Play MIDI through an external MIDI output when a compatible output or software synthesizer is available.
- Inspect and edit notes in MIDI Studio and save `edited_37key.mid`.
- Play or export a selected time range as `chorus_37key.mid`.

## Processing Pipeline

```text
YouTube URL / Local Audio
            ↓
          Demucs
  vocals / accompaniment
            ↓
       Basic Pitch
            ↓
        Raw MIDI
            ↓
    clean_37key.mid
            ↓
 ai_optimized_37key.mid
            ↓
pitch_corrected_37key.mid
            ↓
    final_37key.mid
            ↓
         optional
    edited_37key.mid
            ↓
    Keyboard Playback
```

`piano_cover_37key.mid` is also generated from the raw transcription as a melody-first arrangement. The `melody_only` and `piano_cover` arrangement styles can also be selected when running Optimize MIDI.

## Project Structure

```text
youtube_to_midi.py          Application entry point
cli_app.py                  Command-line interface
converter.py                Download, separation, transcription, and pipeline orchestration
midi_rule_engine.py         37-key cleanup and range fitting
midi_ai_optimizer.py        Rule/OpenAI optimization, pitch correction, and arrangements
midi_editor.py              Suspicious-note detection and edited MIDI output
midi_range.py               Time-range export
midi_to_keyboard.py         MIDI preview and keyboard playback
transpose.py                Key detection and transposition
tools.py                    Executable discovery, subprocesses, and cancellation
playable_range.py           Playable-range helpers

ui/
├── app.py                  YoutubeMidiApp composition and application lifecycle
├── actions/                Conversion, playback, optimizer, editor, and Studio callbacks
├── helpers/                State, selection, logging, and queue handling
└── panels/                 Tkinter notebook tabs and widget layout

test_piano_cover.py         Piano Cover and arrangement tests
output/                     Generated conversion folders
```

MIDI processing remains in the root processing modules. The `ui/` package contains interface state, layout, and actions only.

## UI

### Main

Enter a YouTube URL or open local audio, choose a converted result and MIDI version, preview notes, start keyboard playback, stop the current task, and view logs and status.

### Playback Settings

Configure always-on-top behavior, playback speed, focus delay, semitone transpose, chord timing, minimum key hold, Demucs device, and optional vocals transcription.

### MIDI Cleanup

Configure minimum note length, velocity threshold, simultaneous-note limit, range fitting, melody controls, arrangement style, optimizer mode, and key transposition.

Available arrangement styles are:

- `original`: retain the normal optimization pipeline.
- `melody_only`: extract a playable monophonic top line.
- `piano_cover`: retain the main melody while simplifying bass and harmony to a playable cover.

### MIDI Studio

Load the selected MIDI, play/pause/stop through an external MIDI output, seek through the timeline, export a time range, inspect notes, delete selected or suspicious notes, and save an edited version.

## MIDI Versions

- **Raw MIDI**: Basic Pitch transcription before 37-key cleanup. Its filename is based on the transcribed source rather than literally `raw.mid`.
- **`clean_37key.mid`**: Filters short or weak notes, fits notes into the playable range, and limits dense note windows.
- **`piano_cover_37key.mid`**: Melody-first 37-key arrangement with simplified harmony and reduced repeated bass.
- **`ai_optimized_37key.mid`**: Output from the selected local rule or OpenAI optimizer. It is also used for the melody-only arrangement stage.
- **`pitch_corrected_37key.mid`**: Optimized MIDI adjusted using the detected key and pitch-correction rules.
- **`final_37key.mid`**: Smoothed and quantized result intended for preview and keyboard playback.
- **`edited_37key.mid`**: Optional result saved from MIDI Editor after manual note removal.
- **`chorus_37key.mid`**: Optional exported time range.

Not every intermediate file is produced by every arrangement style. Piano Cover and Melody Only preserve their selected melody directly rather than applying the normal pitch-correction chain.

## Requirements

### Python

Python 3.11 or newer is recommended. The included setup script searches common Python 3.10–3.12 installations.

### Python dependencies

Main dependencies are defined in [`requirements.txt`](requirements.txt):

- `torch` and `torchaudio`
- `demucs`
- `basic-pitch`
- `yt-dlp`
- `mido`
- `python-rtmidi`
- `keyboard`

OpenAI optimization is optional and requires an `OPENAI_API_KEY` environment variable. If the OpenAI request fails, the optimizer falls back to local rules.

### FFmpeg

FFmpeg and FFprobe must be available. On Windows:

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

### Setup

From the project directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Manual installation:

```powershell
python -m venv .venv
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

Generated files are stored under `output/`, grouped by video or local-audio source.

## Future Roadmap

- Further Piano Cover arrangement and melody-extraction improvements.
- A richer timeline player and visual note timeline.
- Advanced MIDI Editor operations.
- Multiple selectable transcription engines.
- Optional Omnizart or MT3 transcription support.

These roadmap items are planned and are not currently implemented unless described elsewhere in this README as an existing feature.

## License

No license file is currently included. Add a license before redistributing or accepting external contributions.
