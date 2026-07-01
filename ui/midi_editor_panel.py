import tkinter as tk
from tkinter import ttk

def build_midi_editor_panel(app, parent, row=3):
    editor = ttk.Frame(parent, padding=(12, 0, 12, 8))
    editor.grid(row=row, column=0, sticky="nsew")
    editor.columnconfigure(0, weight=1)
    editor.rowconfigure(1, weight=1)

    editor_actions = ttk.Frame(editor)
    editor_actions.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    ttk.Button(
        editor_actions,
        text="Open Selected MIDI",
        command=app.open_selected_midi_in_editor,
    ).grid(row=0, column=0, sticky="w")
    ttk.Button(
        editor_actions,
        text="Delete selected notes",
        command=app.delete_selected_editor_notes,
    ).grid(row=0, column=1, sticky="w", padx=(8, 0))
    ttk.Button(
        editor_actions,
        text="Delete same pitch",
        command=app.delete_same_pitch_editor_notes,
    ).grid(row=0, column=2, sticky="w", padx=(8, 0))
    ttk.Button(
        editor_actions,
        text="Delete suspicious notes",
        command=app.delete_suspicious_editor_notes,
    ).grid(row=1, column=0, sticky="w", pady=(8, 0))
    ttk.Button(
        editor_actions,
        text="Save as edited_37key.mid",
        command=app.save_editor_midi,
    ).grid(row=1, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0))

    columns = (
        "start_ms",
        "duration_ms",
        "note",
        "note_name",
        "velocity",
        "suspicious_reason",
    )
    app.editor_tree = ttk.Treeview(
        editor,
        columns=columns,
        show="headings",
        selectmode="extended",
    )
    headings = {
        "start_ms": "start_ms",
        "duration_ms": "duration_ms",
        "note": "note",
        "note_name": "note_name",
        "velocity": "velocity",
        "suspicious_reason": "suspicious_reason",
    }
    widths = {
        "start_ms": 90,
        "duration_ms": 95,
        "note": 55,
        "note_name": 75,
        "velocity": 65,
        "suspicious_reason": 260,
    }
    for column in columns:
        app.editor_tree.heading(column, text=headings[column])
        app.editor_tree.column(
            column,
            width=widths[column],
            minwidth=45,
            stretch=column == "suspicious_reason",
            anchor="w" if column == "suspicious_reason" else "center",
        )
    app.editor_tree.tag_configure("suspicious", foreground="#b42318")
    app.editor_tree.grid(row=1, column=0, sticky="nsew")
    editor_scrollbar = ttk.Scrollbar(
        editor, orient="vertical", command=app.editor_tree.yview
    )
    editor_scrollbar.grid(row=1, column=1, sticky="ns")
    app.editor_tree.configure(yscrollcommand=editor_scrollbar.set)
