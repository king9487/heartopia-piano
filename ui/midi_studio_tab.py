import tkinter as tk
from tkinter import ttk

from ui.midi_editor_panel import build_midi_editor_panel

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

    build_midi_editor_panel(app, app.studio_tab)

    app.studio_canvas = tk.Canvas(
        app.studio_tab,
        background="#202225",
        highlightthickness=0,
        height=80,
    )
    app.studio_canvas.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))
