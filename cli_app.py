import time
from pathlib import Path

from converter import audio_file_to_midi, youtube_to_midi
from midi_to_keyboard import play_midi_as_keyboard, preview_midi_keyboard
from tools import check_cli_dependencies, default_demucs_device, format_command_error


def choose_midi_file(results):
    choices = []
    choices.append(
        (
            "accompaniment clean 37-key",
            results.get("accompaniment_clean_midi") or results["accompaniment_midi"],
        )
    )
    choices.append(("accompaniment raw", results["accompaniment_midi"]))
    if results.get("vocal_clean_midi") or results.get("vocal_midi"):
        choices.append(
            ("vocals clean 37-key", results.get("vocal_clean_midi") or results["vocal_midi"])
        )
        choices.append(("vocals raw", results["vocal_midi"]))

    numbered_choices = {str(index): choice for index, choice in enumerate(choices, start=1)}
    print("\nChoose MIDI for keyboard output:")
    for index, (label, _) in numbered_choices.items():
        print(f"{index}. {label.title()}")
    choice = input(f"Select 1-{len(numbered_choices)} [1]: ").strip() or "1"

    label, midi_file = numbered_choices.get(choice, numbered_choices["1"])
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
    convert_vocals_midi = ask_yes_no("Also convert vocals MIDI?", default=False)

    source_path = Path(source)
    try:
        if source_path.exists():
            results = audio_file_to_midi(
                source_path,
                demucs_device=default_demucs_device(),
                convert_vocals_midi=convert_vocals_midi,
            )
        else:
            results = youtube_to_midi(
                source,
                demucs_device=default_demucs_device(),
                convert_vocals_midi=convert_vocals_midi,
            )
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
    print("Vocals MIDI:", results.get("vocal_midi"))
    print("Accompaniment MIDI:", results["accompaniment_midi"])
    print("Vocals Clean 37-Key MIDI:", results.get("vocal_clean_midi"))
    print("Accompaniment Clean 37-Key MIDI:", results.get("accompaniment_clean_midi"))

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
