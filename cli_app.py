import argparse
import time
from pathlib import Path

from converter import audio_file_to_midi, youtube_to_midi
from midi_to_keyboard import play_midi_as_keyboard, preview_midi_keyboard
from tools import check_cli_dependencies, default_demucs_device, format_command_error
from transpose import KEY_NAMES, TRANSPOSED_MIDI_NAME, transpose_midi_to_key


def choose_midi_file(results):
    choices = []
    if results.get("accompaniment_transposed_midi"):
        choices.append(
            ("accompaniment transposed", results["accompaniment_transposed_midi"])
        )
    if results.get("accompaniment_piano_cover_midi"):
        choices.append(
            ("accompaniment piano cover", results["accompaniment_piano_cover_midi"])
        )
    choices.append(
        (
            "accompaniment final 37-key",
            results.get("accompaniment_final_midi")
            or results.get("accompaniment_clean_midi")
            or results["accompaniment_midi"],
        )
    )
    choices.append(
        (
            "accompaniment clean 37-key",
            results.get("accompaniment_clean_midi") or results["accompaniment_midi"],
        )
    )
    choices.append(("accompaniment raw", results["accompaniment_midi"]))
    if results.get("vocal_final_midi") or results.get("vocal_clean_midi") or results.get("vocal_midi"):
        choices.append(
            (
                "vocals final 37-key",
                results.get("vocal_final_midi")
                or results.get("vocal_clean_midi")
                or results["vocal_midi"],
            )
        )
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Convert audio to 37-key game MIDI")
    parser.add_argument(
        "--target-key",
        choices=KEY_NAMES,
        help="Transpose the accompaniment MIDI to this major key.",
    )
    parser.add_argument(
        "--original-key",
        choices=KEY_NAMES,
        help="Override automatic detection of the original major key.",
    )
    return parser.parse_args(argv)


def apply_cli_key_transpose(results, original_key, target_key):
    if not target_key:
        return None

    source_midi = (
        results.get("accompaniment_piano_cover_midi")
        or results.get("accompaniment_final_midi")
        or results.get("accompaniment_pitch_corrected_midi")
        or results.get("accompaniment_ai_optimized_midi")
        or results.get("accompaniment_clean_midi")
        or results["accompaniment_midi"]
    )
    output_midi = Path(source_midi).parent / TRANSPOSED_MIDI_NAME
    result = transpose_midi_to_key(
        source_midi,
        output_midi,
        original_key=original_key,
        target_key=target_key,
    )
    displayed_key = result["original_key"]
    if result["output_midi"] is None:
        print("Detected Key: Unknown")
        print("Key detection failed; continuing without transpose.")
        return result

    results["accompaniment_transposed_midi"] = result["output_midi"]
    print(f"Detected Key: {displayed_key} Major")
    print(f"Target Key: {result['target_key']} Major")
    print(f"Transpose: {result['semitones']:+d} semitones")
    print("Transposed MIDI:", result["output_midi"])
    return result


def main(argv=None):
    args = parse_args(argv)
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

    try:
        apply_cli_key_transpose(results, args.original_key, args.target_key)
    except Exception as exc:
        print(f"Key transpose failed; continuing without transpose: {exc}")

    print("\nDone!")
    print("Output folder:", results["base_dir"])
    if results.get("cached"):
        print("Loaded cached conversion.")
    print("Original WAV:", results["wav_file"])
    print("Vocals WAV:", results["vocals"])
    print("Accompaniment WAV:", results["no_vocals"])
    print("Vocals MIDI:", results.get("vocal_midi"))
    print("Accompaniment MIDI:", results["accompaniment_midi"])
    print("Vocals Piano Cover MIDI:", results.get("vocal_piano_cover_midi"))
    print("Accompaniment Piano Cover MIDI:", results.get("accompaniment_piano_cover_midi"))
    print("Vocals Clean 37-Key MIDI:", results.get("vocal_clean_midi"))
    print("Accompaniment Clean 37-Key MIDI:", results.get("accompaniment_clean_midi"))
    print("Vocals AI Optimized MIDI:", results.get("vocal_ai_optimized_midi"))
    print("Accompaniment AI Optimized MIDI:", results.get("accompaniment_ai_optimized_midi"))
    print("Vocals Pitch Corrected MIDI:", results.get("vocal_pitch_corrected_midi"))
    print("Accompaniment Pitch Corrected MIDI:", results.get("accompaniment_pitch_corrected_midi"))
    print("Vocals Final 37-Key MIDI:", results.get("vocal_final_midi"))
    print("Accompaniment Final 37-Key MIDI:", results.get("accompaniment_final_midi"))
    print("Vocals detected key:", results.get("vocal_detected_key"))
    print("Accompaniment detected key:", results.get("accompaniment_detected_key"))

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
