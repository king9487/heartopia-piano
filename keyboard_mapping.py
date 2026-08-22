"""User-editable MIDI note to keyboard key mapping profiles."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re


MAPPING_CONFIG_PATH = Path("config") / "keyboard_mappings.json"
DEFAULT_MAPPING_PROFILE = "Heartopia Default"
STANDARD_MAPPING_PROFILE = "Standard 37-Key"
EMPTY_CUSTOM_PROFILE = "Empty Custom"

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

STANDARD_37KEY_NOTE_MAP = {
    36: ",",
    37: "l",
    38: ".",
    39: ";",
    40: "/",
    41: "o",
    42: "0",
    43: "p",
    44: "-",
    45: "[",
    46: "=",
    47: "]",
    48: "z",
    49: "s",
    50: "x",
    51: "d",
    52: "c",
    53: "v",
    54: "g",
    55: "b",
    56: "h",
    57: "n",
    58: "j",
    59: "m",
    60: "q",
    61: "2",
    62: "w",
    63: "3",
    64: "e",
    65: "r",
    66: "5",
    67: "t",
    68: "6",
    69: "y",
    70: "7",
    71: "u",
    72: "i",
}
DEFAULT_NOTE_MAP = {
    note + 12: key
    for note, key in STANDARD_37KEY_NOTE_MAP.items()
}

VALID_NAMED_KEYS = {
    "space",
    "enter",
    "tab",
    "esc",
    "escape",
    "backspace",
    "delete",
    "insert",
    "home",
    "end",
    "page up",
    "page down",
    "up",
    "down",
    "left",
    "right",
    "shift",
    "ctrl",
    "control",
    "alt",
    "cmd",
    "windows",
    "caps lock",
}
FUNCTION_KEY_RE = re.compile(r"^f(?:[1-9]|1[0-9]|2[0-4])$")


@dataclass
class MappingProfile:
    name: str
    mappings: dict[int, str] = field(default_factory=dict)

    @property
    def playable_notes(self):
        return tuple(sorted(int(note) for note in self.mappings))

    @property
    def keyboard_map(self):
        return {
            int(note): str(key).strip()
            for note, key in self.mappings.items()
            if str(key).strip()
        }


def midi_note_name(note):
    note = int(note)
    return f"{NOTE_NAMES[note % 12]}{note // 12 - 1}"


def get_playable_note_constraints(mapping):
    """Derive playable-note constraints from assigned keyboard mappings."""
    if isinstance(mapping, MappingProfile):
        source = mapping.keyboard_map.keys()
    elif hasattr(mapping, "items"):
        source = (
            note for note, key in mapping.items() if str(key or "").strip()
        )
    else:
        source = mapping or ()

    allowed_notes = []
    for note in source:
        try:
            note = int(note)
        except (TypeError, ValueError):
            continue
        if 0 <= note <= 127:
            allowed_notes.append(note)
    allowed_notes = sorted(set(allowed_notes))
    if not allowed_notes:
        raise ValueError("The current Keyboard Mapping has no assigned playable notes.")

    min_note = allowed_notes[0]
    max_note = allowed_notes[-1]
    return {
        "min_note": min_note,
        "max_note": max_note,
        "min_note_name": midi_note_name(min_note),
        "max_note_name": midi_note_name(max_note),
        "allowed_notes": allowed_notes,
    }


def default_mapping_profiles():
    return {
        DEFAULT_MAPPING_PROFILE: MappingProfile(
            DEFAULT_MAPPING_PROFILE, dict(DEFAULT_NOTE_MAP)
        ),
        STANDARD_MAPPING_PROFILE: MappingProfile(
            STANDARD_MAPPING_PROFILE, dict(STANDARD_37KEY_NOTE_MAP)
        ),
        EMPTY_CUSTOM_PROFILE: MappingProfile(EMPTY_CUSTOM_PROFILE, {}),
    }


def _profile_to_payload(profile):
    return {
        "name": profile.name,
        "mappings": {
            str(int(note)): str(key)
            for note, key in sorted(profile.mappings.items())
        },
    }


def _profile_from_payload(payload):
    mappings = {}
    for note, key in payload.get("mappings", {}).items():
        try:
            note_number = int(note)
        except (TypeError, ValueError):
            continue
        if 0 <= note_number <= 127:
            mappings[note_number] = "" if key is None else str(key)
    return MappingProfile(str(payload.get("name", "")).strip(), mappings)


def _read_mapping_file(path):
    path = Path(path)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles = {}
    for item in payload.get("profiles", []):
        profile = _profile_from_payload(item)
        if profile.name:
            profiles[profile.name] = profile
    return profiles


def _write_mapping_file(profiles, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "profiles": [
            _profile_to_payload(profile)
            for profile in sorted(profiles.values(), key=lambda item: item.name.lower())
        ]
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_mapping_profiles(path=MAPPING_CONFIG_PATH):
    profiles = default_mapping_profiles()
    config_path = Path(path)
    if config_path.exists():
        profiles.update(_read_mapping_file(config_path))
    else:
        _write_mapping_file(profiles, config_path)
    return profiles


def load_mapping_profile(name=DEFAULT_MAPPING_PROFILE, path=MAPPING_CONFIG_PATH):
    profiles = load_mapping_profiles(path)
    return profiles.get(name) or profiles[DEFAULT_MAPPING_PROFILE]


def save_mapping_profile(profile, path=MAPPING_CONFIG_PATH):
    profiles = load_mapping_profiles(path)
    profiles[profile.name] = MappingProfile(profile.name, dict(profile.mappings))
    _write_mapping_file(profiles, path)
    return profile


def get_key_for_note(profile, note):
    if isinstance(profile, str):
        profile = load_mapping_profile(profile)
    return profile.keyboard_map.get(int(note))


def is_valid_key_format(key):
    key = str(key).strip()
    if not key:
        return True
    if len(key) == 1 and key.isprintable():
        return True
    lowered = key.lower()
    if lowered in VALID_NAMED_KEYS or FUNCTION_KEY_RE.match(lowered):
        return True
    return False


def validate_mapping_profile(profile, playable_notes=None):
    notes = tuple(playable_notes) if playable_notes is not None else profile.playable_notes
    warnings = []
    seen = {}
    for note in notes:
        key = str(profile.mappings.get(int(note), "")).strip()
        if not key:
            warnings.append(f"{midi_note_name(note)} has no assigned key.")
            continue
        if not is_valid_key_format(key):
            warnings.append(f"{midi_note_name(note)} has invalid key format: {key}")
        normalized = key.lower()
        if normalized in seen:
            warnings.append(
                f"{midi_note_name(note)} and {midi_note_name(seen[normalized])} both use key {key}."
            )
        else:
            seen[normalized] = int(note)
    return warnings
