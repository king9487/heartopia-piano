from tkinter import messagebox

from midi_editor import (
    EDITED_37KEY_MIDI_NAME,
    find_suspicious_notes,
    load_editor_notes,
    save_edited_midi,
)
from midi_to_keyboard import midi_note_name


class UiEditorActionsMixin:
    def open_selected_midi_in_editor(self):
        midi_path = self.get_selected_midi()
        if not midi_path:
            return
        try:
            self.editor_notes = load_editor_notes(midi_path)
        except Exception as exc:
            messagebox.showerror("MIDI Editor", f"Could not read MIDI:\n{exc}")
            return

        self.editor_source_path = midi_path
        self.refresh_editor_tree()
        self.studio_status_var.set(f"Editor: {len(self.editor_notes)} notes")

    def refresh_editor_tree(self):
        if self.editor_tree is None:
            return

        self.editor_suspicious_reasons = find_suspicious_notes(self.editor_notes)
        children = self.editor_tree.get_children()
        if children:
            self.editor_tree.delete(*children)
        for index, note in enumerate(self.editor_notes):
            reason = self.editor_suspicious_reasons.get(index, "")
            tags = ("suspicious",) if reason else ()
            self.editor_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    int(round(note.start * 1000)),
                    int(round(note.duration_ms)),
                    note.note,
                    midi_note_name(note.note),
                    note.velocity,
                    reason,
                ),
                tags=tags,
            )

    def selected_editor_indices(self):
        if self.editor_tree is None:
            return set()
        return {int(item_id) for item_id in self.editor_tree.selection()}

    def delete_selected_editor_notes(self):
        selected = self.selected_editor_indices()
        if not selected:
            messagebox.showwarning("MIDI Editor", "Select one or more notes first.")
            return
        self.editor_notes = [
            note
            for index, note in enumerate(self.editor_notes)
            if index not in selected
        ]
        self.refresh_editor_tree()

    def delete_same_pitch_editor_notes(self):
        selected = self.selected_editor_indices()
        if not selected:
            messagebox.showwarning("MIDI Editor", "Select a pitch first.")
            return
        pitches = {self.editor_notes[index].note for index in selected}
        self.editor_notes = [note for note in self.editor_notes if note.note not in pitches]
        self.refresh_editor_tree()

    def delete_suspicious_editor_notes(self):
        suspicious = set(find_suspicious_notes(self.editor_notes))
        if not suspicious:
            messagebox.showinfo("MIDI Editor", "No suspicious notes were found.")
            return
        self.editor_notes = [
            note
            for index, note in enumerate(self.editor_notes)
            if index not in suspicious
        ]
        self.refresh_editor_tree()

    def save_editor_midi(self):
        if self.editor_source_path is None:
            messagebox.showwarning("MIDI Editor", "Open the selected MIDI first.")
            return

        output_path = self.editor_source_path.parent / EDITED_37KEY_MIDI_NAME
        if output_path.resolve() == self.editor_source_path.resolve():
            messagebox.showerror(
                "MIDI Editor",
                "The selected MIDI is already edited_37key.mid. Open its original source "
                "before saving so it is not overwritten.",
            )
            return
        try:
            save_edited_midi(self.editor_notes, output_path)
        except Exception as exc:
            messagebox.showerror("MIDI Editor", f"Could not save MIDI:\n{exc}")
            return

        self.stop_studio_midi()
        self.studio_loaded_path = None
        if self.results:
            self.update_selected_midi()
        else:
            self.configure_midi_sources_from_path(output_path)
        self.studio_status_var.set("Edited MIDI saved")
        self.log_message(f"Edited 37-Key MIDI: {output_path}")
