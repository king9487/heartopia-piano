from tkinter import messagebox, simpledialog

from keyboard_mapping import (
    DEFAULT_MAPPING_PROFILE,
    MappingProfile,
    default_mapping_profiles,
    load_mapping_profile,
    load_mapping_profiles,
    midi_note_name,
    save_mapping_profile,
    validate_mapping_profile,
)
from keyboard_profiles import get_keyboard_profile


class UiMappingActionsMixin:
    """Keyboard mapping profile editing actions."""

    def refresh_mapping_profiles(self):
        self.keyboard_mapping_profiles = load_mapping_profiles()
        names = tuple(self.keyboard_mapping_profiles)
        for combo in (self.mapping_profile_combo, self.playback_mapping_profile_combo):
            if combo is not None:
                combo.configure(values=names)
        if self.mapping_profile_var.get() not in self.keyboard_mapping_profiles:
            self.mapping_profile_var.set(DEFAULT_MAPPING_PROFILE)
        self.update_active_mapping_display()
        self.populate_keyboard_mapping_tree()

    def get_selected_mapping_profile(self):
        profile = load_mapping_profile(self.mapping_profile_var.get())
        keyboard_profile = get_keyboard_profile(self.keyboard_profile_var.get())
        mappings = {
            int(note): profile.mappings.get(int(note), "")
            for note in keyboard_profile.note_map
        }
        for note, key in profile.mappings.items():
            mappings.setdefault(int(note), key)
        return MappingProfile(profile.name, mappings)

    def update_active_mapping_display(self):
        name = self.mapping_profile_var.get() or DEFAULT_MAPPING_PROFILE
        if "Mapping Profile" in self.analysis_vars:
            self.analysis_vars["Mapping Profile"].set(name)
        if self.active_mapping_profile_var is not None:
            self.active_mapping_profile_var.set(name)

    def populate_keyboard_mapping_tree(self):
        tree = self.keyboard_mapping_tree
        if tree is None:
            return
        tree.delete(*tree.get_children())
        profile = self.get_selected_mapping_profile()
        keyboard_profile = get_keyboard_profile(self.keyboard_profile_var.get())
        for note in keyboard_profile.note_map:
            tree.insert(
                "",
                "end",
                iid=str(note),
                values=(note, midi_note_name(note), profile.mappings.get(note, "")),
            )

    def on_mapping_profile_changed(self, event=None):
        self.update_active_mapping_display()
        self.populate_keyboard_mapping_tree()

    def on_mapping_keyboard_profile_changed(self):
        self.populate_keyboard_mapping_tree()

    def edit_mapping_cell(self, event):
        tree = self.keyboard_mapping_tree
        if tree is None:
            return
        item = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        if not item or column != "#3":
            return
        values = tree.item(item, "values")
        current = values[2] if len(values) > 2 else ""
        note_name = values[1] if len(values) > 1 else item
        key = simpledialog.askstring(
            "Assigned key",
            f"Keyboard key for {note_name}:",
            initialvalue=current,
            parent=self.root,
        )
        if key is None:
            return
        tree.item(item, values=(values[0], values[1], key.strip()))

    def mapping_profile_from_tree(self):
        mappings = {}
        tree = self.keyboard_mapping_tree
        if tree is not None:
            for item in tree.get_children():
                values = tree.item(item, "values")
                mappings[int(values[0])] = values[2] if len(values) > 2 else ""
        return MappingProfile(self.mapping_profile_var.get(), mappings)

    def save_current_mapping_profile(self):
        profile = self.mapping_profile_from_tree()
        save_mapping_profile(profile)
        self.refresh_mapping_profiles()
        self.log_message(f"Saved mapping profile: {profile.name}")

    def load_current_mapping_profile(self):
        self.keyboard_mapping_profiles = load_mapping_profiles()
        self.populate_keyboard_mapping_tree()
        self.log_message(f"Loaded mapping profile: {self.mapping_profile_var.get()}")

    def reset_current_mapping_profile(self):
        name = self.mapping_profile_var.get()
        defaults = default_mapping_profiles()
        profile = defaults.get(name)
        if profile is None:
            keyboard_profile = get_keyboard_profile(self.keyboard_profile_var.get())
            profile = MappingProfile(name, {note: "" for note in keyboard_profile.note_map})
        tree = self.keyboard_mapping_tree
        if tree is not None:
            for item in tree.get_children():
                values = tree.item(item, "values")
                note = int(values[0])
                tree.item(item, values=(values[0], values[1], profile.mappings.get(note, "")))
        self.log_message("Mapping reset in the editor. Use Save Mapping to persist it.")

    def duplicate_current_mapping_profile(self):
        base_name = self.mapping_profile_var.get()
        name = simpledialog.askstring(
            "Duplicate Profile",
            "New mapping profile name:",
            initialvalue=f"{base_name} Copy",
            parent=self.root,
        )
        if not name:
            return
        name = name.strip()
        if not name:
            return
        profile = self.mapping_profile_from_tree()
        profile.name = name
        save_mapping_profile(profile)
        self.mapping_profile_var.set(name)
        self.refresh_mapping_profiles()
        self.log_message(f"Duplicated mapping profile: {name}")

    def validate_current_mapping_profile(self):
        profile = self.mapping_profile_from_tree()
        keyboard_profile = get_keyboard_profile(self.keyboard_profile_var.get())
        warnings = validate_mapping_profile(profile, keyboard_profile.note_map)
        if warnings:
            message = "\n".join(warnings[:25])
            if len(warnings) > 25:
                message += f"\n... and {len(warnings) - 25} more warnings."
            messagebox.showwarning("Mapping validation", message)
            self.log_message(f"Mapping validation found {len(warnings)} warning(s).")
        else:
            messagebox.showinfo("Mapping validation", "Mapping profile looks good.")
            self.log_message("Mapping validation passed.")
