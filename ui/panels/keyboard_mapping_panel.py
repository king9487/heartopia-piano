from tkinter import ttk

from keyboard_mapping import DEFAULT_MAPPING_PROFILE


def build_keyboard_mapping_panel(app, parent, row=0):
    parent.columnconfigure(0, weight=1)

    controls = ttk.LabelFrame(parent, text="Keyboard Mapping", padding=12)
    controls.grid(row=row, column=0, sticky="new", padx=12, pady=(12, 8))
    controls.columnconfigure(1, weight=1)

    ttk.Label(controls, text="Mapping Profile").grid(row=0, column=0, sticky="w")
    profile_combo = ttk.Combobox(
        controls,
        textvariable=app.mapping_profile_var,
        values=tuple(getattr(app, "keyboard_mapping_profiles", {})) or (DEFAULT_MAPPING_PROFILE,),
        state="readonly",
        width=28,
    )
    profile_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
    profile_combo.bind("<<ComboboxSelected>>", app.on_mapping_profile_changed)
    app.mapping_profile_combo = profile_combo

    buttons = ttk.Frame(controls)
    buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
    ttk.Button(buttons, text="Save Mapping", command=app.save_current_mapping_profile).grid(
        row=0, column=0, padx=(0, 6)
    )
    ttk.Button(buttons, text="Load Mapping", command=app.load_current_mapping_profile).grid(
        row=0, column=1, padx=(0, 6)
    )
    ttk.Button(buttons, text="Reset to Default", command=app.reset_current_mapping_profile).grid(
        row=0, column=2, padx=(0, 6)
    )
    ttk.Button(buttons, text="Duplicate Profile", command=app.duplicate_current_mapping_profile).grid(
        row=0, column=3, padx=(0, 6)
    )
    ttk.Button(buttons, text="Validate Mapping", command=app.validate_current_mapping_profile).grid(
        row=0, column=4
    )

    table_frame = ttk.Frame(parent)
    table_frame.grid(row=row + 1, column=0, sticky="nsew", padx=12, pady=(0, 12))
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)

    tree = ttk.Treeview(
        table_frame,
        columns=("midi_note", "note_name", "assigned_key"),
        show="headings",
        height=18,
    )
    tree.heading("midi_note", text="MIDI note number")
    tree.heading("note_name", text="Note name")
    tree.heading("assigned_key", text="Assigned key")
    tree.column("midi_note", width=130, anchor="center")
    tree.column("note_name", width=100, anchor="center")
    tree.column("assigned_key", width=160, anchor="center")
    tree.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=scrollbar.set)
    tree.bind("<Double-1>", app.edit_mapping_cell)
    app.keyboard_mapping_tree = tree

    app.refresh_mapping_profiles()
    return row + 2
