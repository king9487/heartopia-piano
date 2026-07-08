from pathlib import Path
from tkinter import messagebox

from midi_ai_optimizer import (
    AI_OPTIMIZED_MIDI_NAME,
    FINAL_37KEY_MIDI_NAME,
    PIANO_COVER_MIDI_NAME,
    PITCH_CORRECTED_MIDI_NAME,
)
from midi_editor import EDITED_37KEY_MIDI_NAME
from midi_piano_arranger import PIANO_ARRANGED_MIDI_NAME
from midi_rule_engine import CLEAN_37KEY_MIDI_NAME
from transpose import TRANSPOSED_MIDI_NAME
from ui.helpers.analysis import clear_analysis_panel, update_analysis_from_midi_path


MIDI_SOURCE_PRIORITY = (
    "Edited MIDI",
    "Edited",
    "Final 37-Key MIDI",
    "Final",
    "Final MIDI",
    "Piano Arranged MIDI",
    "Piano Arranged",
    "Piano Cover MIDI",
    "Pitch Corrected MIDI",
    "AI Optimized MIDI",
    "Clean 37-Key MIDI",
    "Clean",
    "Imported MIDI",
    "Full Imported MIDI",
    "Selected Parts MIDI",
    "Raw MIDI",
    "Transposed MIDI",
)
COMPARE_SOURCE_PRIORITY = (
    "Imported MIDI",
    "Full Imported MIDI",
    "Selected Parts MIDI",
    "Imported",
    "Raw MIDI",
    "Clean",
    "Clean 37-Key MIDI",
    "Piano Arranged MIDI",
    "Piano Arranged",
    "Piano Cover MIDI",
    "AI Optimized MIDI",
    "Pitch Corrected MIDI",
    "Final 37-Key MIDI",
    "Final",
    "Final MIDI",
    "Edited MIDI",
    "Edited",
)
MIDI_SOURCE_FILENAMES = {
    "Transposed MIDI": TRANSPOSED_MIDI_NAME,
    "Edited MIDI": EDITED_37KEY_MIDI_NAME,
    "Piano Arranged MIDI": PIANO_ARRANGED_MIDI_NAME,
    "Piano Cover MIDI": PIANO_COVER_MIDI_NAME,
    "Final 37-Key MIDI": FINAL_37KEY_MIDI_NAME,
    "Pitch Corrected MIDI": PITCH_CORRECTED_MIDI_NAME,
    "AI Optimized MIDI": AI_OPTIMIZED_MIDI_NAME,
    "Clean 37-Key MIDI": CLEAN_37KEY_MIDI_NAME,
}


def resolve_existing_midi_sources(sources, priority=MIDI_SOURCE_PRIORITY):
    resolved = {}
    for label in priority:
        value = sources.get(label)
        if not value:
            continue
        path = Path(value)
        if path.exists():
            resolved[label] = path
    return resolved


class MidiSelectionMixin:
    """MIDI source/version resolution shared by all UI callbacks."""

    def clear_midi_source_options(self):
        self.available_midi_sources = {}
        self.available_compare_sources = {}
        if self.midi_source_combo:
            self.midi_source_combo.configure(values=())
        self.midi_source_var.set("")
        self.selected_midi_var.set("")
        clear_analysis_panel(self)
        self.compare_a_source_var.set("")
        self.compare_b_source_var.set("")
        if self.compare_a_combo:
            self.compare_a_combo.configure(values=())
        if self.compare_b_combo:
            self.compare_b_combo.configure(values=())

    def set_midi_source_options(self, sources):
        available = resolve_existing_midi_sources(sources)

        self.available_midi_sources = available
        labels = tuple(available)
        assert self.midi_source_combo is not None
        self.midi_source_combo.configure(values=labels)
        self.refresh_compare_sources(sources)
        if not labels:
            self.midi_source_var.set("")
            self.selected_midi_var.set("")
            clear_analysis_panel(self)
            return

        self.midi_source_var.set(labels[0])
        self.on_midi_source_selected()

    def refresh_compare_sources(self, sources):
        available = resolve_existing_midi_sources(
            sources, priority=COMPARE_SOURCE_PRIORITY
        )
        self.available_compare_sources = available
        labels = tuple(available)
        if self.compare_a_combo:
            self.compare_a_combo.configure(values=labels)
        if self.compare_b_combo:
            self.compare_b_combo.configure(values=labels)

        current_a = self.compare_a_source_var.get()
        current_b = self.compare_b_source_var.get()
        if current_a not in available:
            preferred_a = next(
                (
                    label
                    for label in (
                        "Imported MIDI", "Full Imported MIDI", "Clean",
                        "Clean 37-Key MIDI", "Raw MIDI",
                    )
                    if label in available
                ),
                labels[0] if labels else "",
            )
            self.compare_a_source_var.set(preferred_a)
        if current_b not in available:
            preferred_b = next(
                (
                    label
                    for label in (
                        "Selected Parts MIDI",
                        "Piano Arranged MIDI",
                        "Piano Arranged",
                        "Piano Cover MIDI",
                        "Final 37-Key MIDI",
                        "Final",
                        "Final MIDI",
                    )
                    if label in available
                ),
                labels[1] if len(labels) > 1 else (labels[0] if labels else ""),
            )
            self.compare_b_source_var.set(preferred_b)

    def get_compare_midi(self, side):
        variable = self.compare_a_source_var if side == "A" else self.compare_b_source_var
        return self.available_compare_sources.get(variable.get())

    def play_compare_midi(self, side):
        variable = self.compare_a_source_var if side == "A" else self.compare_b_source_var
        label = variable.get()
        midi_path = self.get_compare_midi(side)
        if midi_path:
            self.start_playback(
                midi_path=midi_path,
                original_events=label in {
                    "Full Imported MIDI", "Imported MIDI", "Selected Parts MIDI"
                },
            )

    def set_compare_as_current(self, side):
        variable = self.compare_a_source_var if side == "A" else self.compare_b_source_var
        label = variable.get()
        midi_path = self.available_compare_sources.get(label)
        if midi_path:
            self.midi_source_var.set(label)
            self.selected_midi_var.set(str(midi_path))
            update_analysis_from_midi_path(self, midi_path)

    def collect_result_midi_sources(self):
        if not self.results:
            return {}

        if self.results.get("input_source") == "external_midi":
            sources = {
                "Imported MIDI": self.results.get("selected_direct_midi"),
                "Full Imported MIDI": (
                    self.results.get("source_midi")
                    or self.results.get("imported_midi")
                ),
                "Selected Parts MIDI": self.results.get("selected_parts_midi"),
                "Clean": self.results.get("clean_midi"),
                "Piano Arranged": self.results.get("piano_arranged_midi"),
                "AI Optimized MIDI": self.results.get("ai_optimized_midi"),
                "Pitch Corrected MIDI": self.results.get("pitch_corrected_midi"),
                "Final MIDI": self.results.get("final_midi"),
            }
            if self.results.get("base_dir"):
                sources["Edited"] = (
                    Path(self.results["base_dir"]) / EDITED_37KEY_MIDI_NAME
                )
            return sources

        raw_key = self.midi_choice_var.get()
        if not self.results.get(raw_key) and raw_key == "vocal_midi":
            self.midi_choice_var.set("accompaniment_midi")
            raw_key = "accompaniment_midi"
        prefix = "vocal" if raw_key == "vocal_midi" else "accompaniment"
        sources = {
            "Piano Arranged MIDI": self.results.get(
                f"{prefix}_piano_arranged_midi"
            ),
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
            sources["Piano Arranged MIDI"] = parent_dir / PIANO_ARRANGED_MIDI_NAME
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
            update_analysis_from_midi_path(self, midi_path)

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
