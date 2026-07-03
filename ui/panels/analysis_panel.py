from tkinter import ttk

def build_analysis_panel(app, parent, row):
    parent.columnconfigure(0, weight=1)
    parent.columnconfigure(1, weight=1)

    groups = (
        ("Song Information", ("Song Duration", "Tempo", "Detected Key")),
        ("MIDI Statistics", ("Total Notes", "Raw Notes")),
        (
            "Conversion Report",
            ("Clean Notes", "Piano Arranged Notes", "Final Notes"),
        ),
        (
            "Note Statistics",
            (
                "Removed Notes", "Merged Notes", "Octave Shifted",
                "Bass Removed", "Harmony Simplified", "Melody Selected",
            ),
        ),
    )
    for index, (title, fields) in enumerate(groups):
        group = ttk.LabelFrame(parent, text=title, padding=12)
        group.grid(
            row=row + (index // 2),
            column=index % 2,
            sticky="nsew",
            padx=(12 if index % 2 == 0 else 6, 6 if index % 2 == 0 else 12),
            pady=(12 if index < 2 else 0, 8),
        )
        group.columnconfigure(1, weight=1)
        for field_row, field in enumerate(fields):
            ttk.Label(group, text=field).grid(
                row=field_row, column=0, sticky="w", pady=3
            )
            ttk.Label(group, textvariable=app.analysis_vars[field]).grid(
                row=field_row, column=1, sticky="w", padx=(12, 0), pady=3
            )
    return row + 2
