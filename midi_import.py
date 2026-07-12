from pathlib import Path

import mido


SANITIZED_IMPORT_NAME = "imported_sanitized.mid"


def safe_load_midi(path, sanitized_path=None):
    """Load a MIDI file, clipping malformed data bytes when mido can repair it."""
    path = Path(path)
    try:
        midi = mido.MidiFile(path)
        midi.import_repaired = False
        midi.sanitized_path = None
        return midi
    except Exception as original_exc:
        print("Original import failed:")
        print(f"<{original_exc}>")
        print("Retry with clip=True...")
        try:
            midi = mido.MidiFile(path, clip=True)
        except Exception as repair_exc:
            raise ValueError(
                "This MIDI file cannot be repaired automatically."
            ) from repair_exc

    print("WARNING:")
    print("Invalid MIDI data bytes detected.")
    print("Values outside 0..127 were clipped.")
    print("Import repaired successfully.")

    sanitized_path = (
        Path(sanitized_path)
        if sanitized_path is not None
        else Path("output") / SANITIZED_IMPORT_NAME
    )
    sanitized_path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(sanitized_path)
    midi.import_repaired = True
    midi.sanitized_path = sanitized_path
    return midi
