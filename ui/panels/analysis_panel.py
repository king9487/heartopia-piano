from tkinter import ttk

from midi_analysis import ANALYSIS_FIELDS


def build_analysis_panel(app, parent, row):
    panel = ttk.LabelFrame(parent, text="MIDI Analysis", padding=10)
    panel.grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8))
    panel.columnconfigure(1, weight=1)
    panel.columnconfigure(3, weight=1)

    midpoint = (len(ANALYSIS_FIELDS) + 1) // 2
    for index, field in enumerate(ANALYSIS_FIELDS):
        column_group = 0 if index < midpoint else 1
        local_row = index if column_group == 0 else index - midpoint
        label_column = column_group * 2
        ttk.Label(panel, text=field).grid(
            row=local_row, column=label_column, sticky="w", pady=2
        )
        ttk.Label(panel, textvariable=app.analysis_vars[field]).grid(
            row=local_row,
            column=label_column + 1,
            sticky="w",
            padx=(8, 28),
            pady=2,
        )
    return row + 1
