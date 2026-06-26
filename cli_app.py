import time
from pathlib import Path

from converter import audio_file_to_midi, youtube_to_midi
from midi_to_keyboard import play_midi_as_keyboard, preview_midi_keyboard
from tools import check_cli_dependencies, default_demucs_device, format_command_error


def choose_midi_file(results):
    choices = {
        "1": ("vocals", results["vocal_midi"]),
        "2": ("accompaniment", results["accompaniment_midi"]),
    }

    print("\nChoose MIDI for keyboard output:")
    print("1. Vocals")
    print("2. Accompaniment")
    choice = input("Select 1 or 2 [1]: ").strip() or "1"

    label, midi_file = choices.get(choice, choices["1"])
    print(f"Selected {label} MIDI: {midi_file}")
    return midi_file


def ask_yes_no(prompt, default=False):
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def main():
    source = input("Paste YouTube URL or local audio path: ").strip().strip('"')
    if not source:
        raise ValueError("Source cannot be empty")

    check_cli_dependencies()

    source_path = Path(source)
    try:
        if source_path.exists():
            results = audio_file_to_midi(source_path, demucs_device=default_demucs_device())
        else:
            results = youtube_to_midi(source, demucs_device=default_demucs_device())
    except Exception as exc:
        print(format_command_error(exc))
        return

    print("\nDone!")
    print("Output folder:", results["base_dir"])
    if results.get("cached"):
        print("Loaded cached conversion.")
    print("Original WAV:", results["wav_file"])
    print("Vocals WAV:", results["vocals"])
    print("Accompaniment WAV:", results["no_vocals"])
    print("Vocals MIDI:", results["vocal_midi"])
    print("Accompaniment MIDI:", results["accompaniment_midi"])

    if not ask_yes_no("\nPreview keyboard events from a MIDI file?", default=True):
        return

    selected_midi = choose_midi_file(results)
    preview_midi_keyboard(selected_midi)

    if ask_yes_no("\nSend these MIDI events as real keyboard input?", default=False):
        print("Starting in 3 seconds. Focus the target window now.")
        time.sleep(3)
        play_midi_as_keyboard(selected_midi)
        print("Keyboard playback finished.")


if __name__ == "__main__":
    main()
