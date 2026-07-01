from tkinter import ttk

from ui_settings_panel import build_playback_settings_panel


def build_convert_panel(app, parent, start_row=0):
    top = ttk.Frame(parent, padding=12)
    top.grid(row=start_row, column=0, sticky="ew")
    top.columnconfigure(1, weight=1)

    ttk.Label(top, text="YouTube URL").grid(row=0, column=0, sticky="w")
    url_entry = ttk.Entry(top, textvariable=app.url_var)
    url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
    url_entry.focus_set()

    app.convert_button = ttk.Button(top, text="Convert URL", command=app.start_convert)
    app.convert_button.grid(row=0, column=2, sticky="e")
    app.local_audio_button = ttk.Button(
        top, text="Open Audio", command=app.start_local_audio_convert
    )
    app.local_audio_button.grid(row=0, column=3, sticky="e", padx=(8, 0))

    return start_row + 1
