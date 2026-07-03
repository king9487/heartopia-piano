import tkinter as tk
from tkinter import ttk

from ui.panels.midi_editor_panel import build_midi_editor_panel
from ui.panels.staff_view import StaffViewCanvas


def build_studio_panel(app, parent):
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(4, weight=1)

    source = ttk.Frame(parent, padding=(12, 12, 12, 8))
    source.grid(row=0, column=0, sticky="ew")
    source.columnconfigure(1, weight=1)
    ttk.Label(source, text="Selected MIDI").grid(row=0, column=0, sticky="w")
    ttk.Label(source, textvariable=app.selected_midi_var, foreground="#444").grid(
        row=0, column=1, sticky="ew", padx=(8, 0)
    )

    controls = ttk.Frame(parent, padding=(12, 0, 12, 8))
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
        parent,
        from_=0,
        to=1,
        variable=app.studio_position_var,
        command=app.on_studio_seek,
    )
    app.studio_seek.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

    range_tools = ttk.LabelFrame(
        parent, text="Range Export", padding=(10, 6, 10, 8)
    )
    range_tools.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
    ttk.Label(range_tools, text="Start seconds").grid(row=0, column=0, sticky="w")
    ttk.Spinbox(
        range_tools,
        from_=0,
        to=86400,
        increment=1,
        textvariable=app.range_start_var,
        width=8,
    ).grid(row=0, column=1, sticky="w", padx=(8, 16))
    ttk.Label(range_tools, text="End seconds").grid(row=0, column=2, sticky="w")
    ttk.Spinbox(
        range_tools,
        from_=0.1,
        to=86400,
        increment=1,
        textvariable=app.range_end_var,
        width=8,
    ).grid(row=0, column=3, sticky="w", padx=(8, 16))
    ttk.Button(
        range_tools, text="Play Range", command=app.start_range_playback
    ).grid(row=0, column=4, sticky="w")
    ttk.Button(
        range_tools, text="Export Range", command=app.export_selected_range
    ).grid(row=0, column=5, sticky="w", padx=(8, 0))

    build_midi_editor_panel(app, parent, row=4)

    timeline = ttk.LabelFrame(parent, text="Timeline", padding=(10, 6, 10, 8))
    timeline.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))
    timeline.columnconfigure(0, weight=1)
    view_controls = ttk.Frame(timeline)
    view_controls.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    ttk.Label(view_controls, text="View Mode").grid(row=0, column=0, sticky="w")
    view_combo = ttk.Combobox(
        view_controls,
        textvariable=app.studio_view_mode_var,
        values=("Piano Roll", "Staff View"),
        state="readonly",
        width=12,
    )
    view_combo.grid(row=0, column=1, sticky="w", padx=(8, 16))
    view_combo.bind("<<ComboboxSelected>>", app.on_studio_view_mode_changed)
    ttk.Button(view_controls, text="Zoom -", command=lambda: app.zoom_staff_view(0.8)).grid(
        row=0, column=2, sticky="w"
    )
    ttk.Button(view_controls, text="Zoom +", command=lambda: app.zoom_staff_view(1.25)).grid(
        row=0, column=3, sticky="w", padx=(6, 0)
    )

    app.piano_roll_frame = ttk.Frame(timeline)
    app.piano_roll_frame.grid(row=1, column=0, sticky="ew")
    app.piano_roll_frame.columnconfigure(0, weight=1)
    app.studio_canvas = tk.Canvas(
        app.piano_roll_frame,
        background="#202225",
        highlightthickness=0,
        height=80,
    )
    app.studio_canvas.grid(row=0, column=0, sticky="ew")

    app.staff_view_frame = ttk.Frame(timeline)
    app.staff_view_frame.columnconfigure(0, weight=1)
    app.staff_view = StaffViewCanvas(
        app.staff_view_frame, selection_callback=app.on_staff_note_selected
    )
    app.staff_view.grid(row=0, column=0, sticky="ew")
    staff_scroll = ttk.Scrollbar(
        app.staff_view_frame, orient="horizontal", command=app.staff_view.xview
    )
    staff_scroll.grid(row=1, column=0, sticky="ew")
    app.staff_view.configure(xscrollcommand=staff_scroll.set)
    ttk.Label(
        app.staff_view_frame, textvariable=app.staff_selected_note_var
    ).grid(row=2, column=0, sticky="w", pady=(6, 0))

    future = ttk.LabelFrame(parent, text="Future AI Repair", padding=10)
    future.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 12))
    ttk.Label(
        future,
        text="Reserved for assisted note repair and recovery tools.",
        foreground="#666",
    ).grid(row=0, column=0, sticky="w")
