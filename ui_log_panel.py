import tkinter as tk
from tkinter import ttk


def build_log_panel(app, parent, row):
    selected = ttk.Label(
        parent,
        textvariable=app.selected_midi_var,
        padding=(12, 0, 12, 8),
        foreground="#444",
    )
    selected.grid(row=row, column=0, sticky="new")

    log_frame = ttk.Frame(parent, padding=(12, 0, 12, 8))
    log_frame.grid(row=row + 1, column=0, sticky="nsew")
    log_frame.columnconfigure(0, weight=1)
    log_frame.rowconfigure(0, weight=1)
    app.log = tk.Text(log_frame, height=16, wrap="word", state="disabled")
    app.log.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(log_frame, command=app.log.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    app.log.configure(yscrollcommand=scrollbar.set)

    status = ttk.Label(parent, textvariable=app.status_var, padding=(12, 0, 12, 12))
    status.grid(row=row + 2, column=0, sticky="ew")
    parent.rowconfigure(row + 1, weight=1)
