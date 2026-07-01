from pathlib import Path
from tkinter import messagebox

from midi_ai_optimizer import (
    AI_OPTIMIZED_MIDI_NAME,
    FINAL_37KEY_MIDI_NAME,
    PIANO_COVER_MIDI_NAME,
    PITCH_CORRECTED_MIDI_NAME,
)
from midi_editor import EDITED_37KEY_MIDI_NAME
from midi_rule_engine import CLEAN_37KEY_MIDI_NAME
from transpose import TRANSPOSED_MIDI_NAME


MIDI_SOURCE_PRIORITY = (
    "Transposed MIDI",
    "Edited MIDI",
    "Piano Cover MIDI",
    "Final 37-Key MIDI",
    "Pitch Corrected MIDI",
    "AI Optimized MIDI",
    "Clean 37-Key MIDI",
    "Raw MIDI",
)
MIDI_SOURCE_FILENAMES = {
    "Transposed MIDI": TRANSPOSED_MIDI_NAME,
    "Edited MIDI": EDITED_37KEY_MIDI_NAME,
    "Piano Cover MIDI": PIANO_COVER_MIDI_NAME,
    "Final 37-Key MIDI": FINAL_37KEY_MIDI_NAME,
    "Pitch Corrected MIDI": PITCH_CORRECTED_MIDI_NAME,
    "AI Optimized MIDI": AI_OPTIMIZED_MIDI_NAME,
    "Clean 37-Key MIDI": CLEAN_37KEY_MIDI_NAME,
}


class MidiSelectionMixin:
    """MIDI source/version resolution shared by all UI callbacks."""

    def clear_midi_source_options(self):
        self.available_midi_sources = {}
        if self.midi_source_combo:
            self.midi_source_combo.configure(values=())
        self.midi_source_var.set("")
        self.selected_midi_var.set("")

    def set_midi_source_options(self, sources):
        available = {}
        for label in MIDI_SOURCE_PRIORITY:
            value = sources.get(label)
            if not value:
                continue
            path = Path(value)
            if path.exists():
                available[label] = path

        self.available_midi_sources = available
        labels = tuple(available)
        assert self.midi_source_combo is not None
        self.midi_source_combo.configure(values=labels)
        if not labels:
            self.midi_source_var.set("")
            self.selected_midi_var.set("")
            return

        self.midi_source_var.set(labels[0])
        self.on_midi_source_selected()

    def collect_result_midi_sources(self):
        if not self.results:
            return {}

        raw_key = self.midi_choice_var.get()
        if not self.results.get(raw_key) and raw_key == "vocal_midi":
            self.midi_choice_var.set("accompaniment_midi")
            raw_key = "accompaniment_midi"
        prefix = "vocal" if raw_key == "vocal_midi" else "accompaniment"
        sources = {
            "Piano Cover MIDI": self.results.get(f"{prefix}_piano_cover_midi"),
            "Final 37-Key MIDI": self.results.get(f"{prefix}_final_midi"),
            "Pitch Corrected MIDI": self.results.get(
                f"{prefix}_pitch_corrected_midi"
            ),
            "AI Optimized MIDI": self.results.get(f"{prefix}_ai_optimized_midi"),
            "Clean 37-Key MIDI": self.results.get(f"{prefix}_clean_midi"),
            "Raw MIDI": self.results.get(raw_key),
        }
        parent_source = next((value for value in sources.values() if value), None)
        if parent_source:
            parent_dir = Path(parent_source).parent
            sources["Piano Cover MIDI"] = parent_dir / PIANO_COVER_MIDI_NAME
            sources["Transposed MIDI"] = parent_dir / TRANSPOSED_MIDI_NAME
            sources["Edited MIDI"] = parent_dir / EDITED_37KEY_MIDI_NAME
        return sources

    def configure_midi_sources_from_path(self, midi_path):
        midi_path = Path(midi_path)
        sources = {
            label: midi_path.parent / filename
            for label, filename in MIDI_SOURCE_FILENAMES.items()
        }
        known_label = next(
            (
                label
                for label, filename in MIDI_SOURCE_FILENAMES.items()
                if midi_path.name.lower() == filename.lower()
            ),
            None,
        )
        if known_label:
            sources[known_label] = midi_path
        else:
            sources["Raw MIDI"] = midi_path
        self.set_midi_source_options(sources)

    def on_midi_source_selected(self, event=None):
        midi_path = self.available_midi_sources.get(self.midi_source_var.get())
        if midi_path:
            self.selected_midi_var.set(str(midi_path))

    def update_selected_midi(self):
        self.set_midi_source_options(self.collect_result_midi_sources())

    def get_selected_midi(self):
        value = self.selected_midi_var.get().strip()
        if not value:
            messagebox.showwarning(
                "No MIDI selected", "Convert or open a MIDI file first."
            )
            return None

        midi_path = Path(value)
        if not midi_path.exists():
            messagebox.showerror("MIDI not found", str(midi_path))
            return None

        return midi_path
