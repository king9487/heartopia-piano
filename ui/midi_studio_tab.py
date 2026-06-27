import tkinter as tk
from tkinter import ttk

def build_midi_studio_ui(app):
    app.studio_tab.columnconfigure(0, weight=1)
    app.studio_tab.rowconfigure(3, weight=1)

    source = ttk.Frame(app.studio_tab, padding=(12, 12, 12, 8))
    source.grid(row=0, column=0, sticky="ew")
    source.columnconfigure(1, weight=1)
    ttk.Label(source, text="Selected MIDI").grid(row=0, column=0, sticky="w")
    ttk.Label(source, textvariable=app.selected_midi_var, foreground="#444").grid(
        row=0, column=1, sticky="ew", padx=(8, 0)
    )

    controls = ttk.Frame(app.studio_tab, padding=(12, 0, 12, 8))
    controls.grid(row=1, column=0, sticky="ew")
    controls.columnconfigure(6, weight=1)
    app.studio_play_button = ttk.Button(
        controls, text="Play", command=app.play_studio_midi
    )
    app.studio_play_button.grid(row=0, column=0, sticky="w")
    app.studio_pause_button = ttk.Button(
        controls, text="Pause", command=app.pause_studio_midi, state="disabled"
    )
    app.studio_pause_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
    app.studio_stop_button = ttk.Button(
        controls, text="Stop", command=app.stop_studio_midi, state="disabled"
    )
    app.studio_stop_button.grid(row=0, column=2, sticky="w", padx=(8, 0))
    ttk.Label(controls, textvariable=app.studio_current_time_var).grid(
        row=0, column=3, sticky="e", padx=(20, 4)
    )
    ttk.Label(controls, text="/").grid(row=0, column=4)
    ttk.Label(controls, textvariable=app.studio_total_time_var).grid(
        row=0, column=5, sticky="w", padx=(4, 0)
    )
    ttk.Label(controls, textvariable=app.studio_status_var).grid(
        row=0, column=6, sticky="e", padx=(16, 0)
    )

    app.studio_seek = ttk.Scale(
        app.studio_tab,
        from_=0,
        to=1,
        variable=app.studio_position_var,
        command=app.on_studio_seek,
    )
    app.studio_seek.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

    editor = ttk.Frame(app.studio_tab, padding=(12, 0, 12, 8))
    editor.grid(row=3, column=0, sticky="nsew")
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

    app.studio_canvas = tk.Canvas(
        app.studio_tab,
        background="#202225",
        highlightthickness=0,
        height=80,
    )
    app.studio_canvas.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))
