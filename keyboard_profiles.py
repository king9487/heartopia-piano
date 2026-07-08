"""Keyboard range profiles shared by the UI and MIDI processing pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyboardProfile:
    name: str
    playable_low: int
    playable_high: int
    preferred_melody_low: int
    preferred_melody_high: int

    @property
    def note_map(self):
        return tuple(range(self.playable_low, self.playable_high + 1))

    @property
    def range_label(self):
        return f"{midi_note_name(self.playable_low)}-{midi_note_name(self.playable_high)}"


def midi_note_name(note):
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    note = int(note)
    return f"{names[note % 12]}{note // 12 - 1}"


KEYBOARD_PROFILES = {
    "Heartopia": KeyboardProfile("Heartopia", 48, 84, 48, 72),
    "Standard 37-Key": KeyboardProfile("Standard 37-Key", 36, 72, 36, 60),
    "Full Piano": KeyboardProfile("Full Piano", 21, 108, 21, 108),
}
DEFAULT_KEYBOARD_PROFILE = "Heartopia"


def get_keyboard_profile(name):
    return KEYBOARD_PROFILES.get(name, KEYBOARD_PROFILES[DEFAULT_KEYBOARD_PROFILE])


def processing_options_for_profile(name):
    profile = get_keyboard_profile(name)
    return {
        "keyboard_profile": profile.name,
        "note_map": profile.note_map,
        "preferred_melody_low": profile.preferred_melody_low,
        "preferred_melody_high": profile.preferred_melody_high,
    }
