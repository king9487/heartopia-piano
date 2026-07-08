from tkinter import ttk

from converter import SEPARATION_MODES, SEPARATION_STEMS

def build_convert_panel(app, parent, start_row=0):
    top = ttk.LabelFrame(parent, text="Input Source", padding=12)
    top.grid(row=start_row, column=0, sticky="ew")
    top.columnconfigure(0, weight=1)

    choices = ttk.Frame(top)
    app.input_source_choices = choices
    choices.grid(row=0, column=0, sticky="w")
    for column, (text, value) in enumerate(
        (("YouTube Video", "youtube"), ("Audio File", "local_audio"), ("MIDI File", "external_midi"))
    ):
        ttk.Radiobutton(
            choices,
            text=text,
            value=value,
            variable=app.input_source_var,
            command=app.on_input_source_changed,
        ).grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 14, 0))

    convert = ttk.LabelFrame(parent, text="Convert", padding=12)
    convert.grid(row=start_row + 1, column=0, sticky="ew", padx=12, pady=(8, 0))
    convert.columnconfigure(0, weight=1)

    app.youtube_input_frame = ttk.Frame(convert)
    app.youtube_input_frame.grid(row=0, column=0, sticky="ew")
    app.youtube_input_frame.columnconfigure(1, weight=1)
    ttk.Label(app.youtube_input_frame, text="YouTube URL").grid(row=0, column=0, sticky="w")
    url_entry = ttk.Entry(app.youtube_input_frame, textvariable=app.url_var)
    url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
    url_entry.focus_set()
    app.convert_button = ttk.Button(
        app.youtube_input_frame, text="Convert URL", command=app.start_convert
    )
    app.convert_button.grid(row=0, column=2, sticky="e")

    app.local_audio_input_frame = ttk.Frame(convert)
    app.local_audio_input_frame.grid(row=0, column=0, sticky="w")
    app.local_audio_button = ttk.Button(
        app.local_audio_input_frame, text="Open Audio...", command=app.start_local_audio_convert
    )
    app.local_audio_button.grid(row=0, column=0, sticky="w")

    app.external_midi_input_frame = ttk.Frame(convert)
    app.external_midi_input_frame.grid(row=0, column=0, sticky="ew")
    app.external_midi_input_frame.columnconfigure(1, weight=1)
    app.external_midi_button = ttk.Button(
        app.external_midi_input_frame,
        text="Import MIDI...",
        command=app.browse_external_midi,
    )
    app.external_midi_button.grid(row=0, column=0, sticky="w")
    ttk.Label(
        app.external_midi_input_frame, textvariable=app.external_midi_path_var
    ).grid(row=0, column=1, sticky="w", padx=(10, 0))

    conversion_options = ttk.Frame(convert)
    app.conversion_options_frame = conversion_options
    conversion_options.grid(row=1, column=0, sticky="w", pady=(10, 0))
    ttk.Label(conversion_options, text="Demucs device").grid(row=0, column=0, sticky="w")
    ttk.Combobox(
        conversion_options,
        textvariable=app.demucs_device_var,
        values=("cuda:0", "auto", "cpu"),
        state="readonly",
        width=10,
    ).grid(row=0, column=1, sticky="w", padx=(8, 20))
    ttk.Checkbutton(
        conversion_options,
        text="Convert vocals MIDI",
        variable=app.convert_vocals_midi_var,
    ).grid(row=0, column=2, sticky="w")
    ttk.Label(conversion_options, text="Separation Mode").grid(
        row=1, column=0, sticky="w", pady=(8, 0)
    )
    ttk.Combobox(
        conversion_options,
        textvariable=app.separation_mode_var,
        values=SEPARATION_MODES,
        state="readonly",
        width=22,
    ).grid(row=1, column=1, sticky="w", padx=(8, 20), pady=(8, 0))
    ttk.Label(conversion_options, text="Stem to Convert").grid(
        row=2, column=0, sticky="w", pady=(8, 0)
    )
    ttk.Combobox(
        conversion_options,
        textvariable=app.stem_to_convert_var,
        values=SEPARATION_STEMS,
        state="readonly",
        width=22,
    ).grid(row=2, column=1, sticky="w", padx=(8, 20), pady=(8, 0))

    app.on_input_source_changed()

    return start_row + 2


def build_import_panel(app, parent, start_row=0):
    parent.columnconfigure(0, weight=1)

    original = ttk.LabelFrame(
        parent, text="Original MIDI", padding=12
    )
    original.grid(row=start_row, column=0, sticky="ew", padx=12, pady=(12, 8))
    app.preview_original_midi_button = ttk.Button(
        original,
        text="Preview Original",
        command=app.preview_original_midi,
        state="disabled",
    )
    app.preview_original_midi_button.grid(row=0, column=0, sticky="w")
    app.play_original_midi_button = ttk.Button(
        original,
        text="Play Original",
        command=app.play_original_midi,
        state="disabled",
    )
    app.play_original_midi_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
    app.open_original_midi_button = ttk.Button(
        original,
        text="Open Original",
        command=app.open_original_midi,
        state="disabled",
    )
    app.open_original_midi_button.grid(row=0, column=2, sticky="w", padx=(8, 0))
    app.import_actions_frame = (
        app.preview_original_midi_button,
        app.play_original_midi_button,
        app.open_original_midi_button,
    )

    info = ttk.Frame(original)
    info.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    fields = (
        ("Filename", "file_name"), ("Duration", "duration"),
        ("Tempo", "bpm"), ("Key", "key"), ("Tracks", "tracks"),
        ("PPQ", "ppq"), ("Total Notes", "total_notes"),
        ("Playable Notes", "notes_inside_map"),
        ("Out-of-range Notes", "notes_outside_map"),
        ("Playable Percentage", "playable_percentage"),
        ("Recommended", "recommended"),
    )
    for index, (label, key) in enumerate(fields):
        row, group = divmod(index, 2)
        label_column = group * 2
        ttk.Label(info, text=label).grid(row=row, column=label_column, sticky="w", pady=1)
        ttk.Label(info, textvariable=app.external_midi_info_vars[key]).grid(
            row=row, column=label_column + 1, sticky="w", padx=(8, 24), pady=1
        )

    analysis = ttk.Frame(original)
    app.import_analysis_frame = analysis
    analysis.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
    analysis.columnconfigure(0, weight=3)
    analysis.columnconfigure(1, weight=2)

    tracks = ttk.LabelFrame(analysis, text="Source Tracks", padding=6)
    tracks.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    tracks.columnconfigure(0, weight=1)
    app.external_midi_track_tree = ttk.Treeview(
        tracks,
        columns=(
            "direct", "optimize", "program", "notes", "playable",
            "outside", "min", "max", "events",
        ),
        show=("tree", "headings"),
        height=5,
    )
    app.external_midi_track_tree.heading("#0", text="Track / Channel")
    app.external_midi_track_tree.column("#0", width=180, minwidth=120, anchor="w")
    for column, heading, width, anchor in (
        ("direct", "Use Direct", 72, "center"),
        ("optimize", "Use Optimization", 105, "center"),
        ("program", "Program / Instrument", 190, "w"),
        ("notes", "Notes", 60, "e"),
        ("playable", "Playable", 70, "e"),
        ("outside", "Out of range", 90, "e"),
        ("min", "Min", 48, "e"),
        ("max", "Max", 48, "e"),
        ("events", "Track Events", 130, "w"),
    ):
        app.external_midi_track_tree.heading(column, text=heading)
        app.external_midi_track_tree.column(
            column, width=width, minwidth=50, anchor=anchor
        )
    app.external_midi_track_tree.grid(row=0, column=0, sticky="nsew")
    track_scroll = ttk.Scrollbar(
        tracks, orient="vertical", command=app.external_midi_track_tree.yview
    )
    track_scroll.grid(row=0, column=1, sticky="ns")
    app.external_midi_track_tree.configure(yscrollcommand=track_scroll.set)
    track_horizontal = ttk.Scrollbar(
        tracks, orient="horizontal", command=app.external_midi_track_tree.xview
    )
    track_horizontal.grid(row=1, column=0, sticky="ew")
    app.external_midi_track_tree.configure(xscrollcommand=track_horizontal.set)
    app.external_midi_track_tree.bind("<Button-1>", app.on_external_part_tree_click)

    channels = ttk.LabelFrame(
        analysis, text="Global Notes by Channel (MIDI 1–16 / file 0–15)", padding=6
    )
    channels.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
    channels.columnconfigure(0, weight=1)
    app.external_midi_channel_tree = ttk.Treeview(
        channels,
        columns=("channel", "notes"),
        show="headings",
        height=5,
    )
    app.external_midi_channel_tree.heading("channel", text="Channel")
    app.external_midi_channel_tree.heading("notes", text="Notes")
    app.external_midi_channel_tree.column("channel", width=100, anchor="w")
    app.external_midi_channel_tree.column("notes", width=70, anchor="e")
    app.external_midi_channel_tree.grid(row=0, column=0, sticky="nsew")
    channel_scroll = ttk.Scrollbar(
        channels, orient="vertical", command=app.external_midi_channel_tree.yview
    )
    channel_scroll.grid(row=0, column=1, sticky="ns")
    app.external_midi_channel_tree.configure(yscrollcommand=channel_scroll.set)

    selection_options = ttk.Frame(original)
    app.import_selection_frame = selection_options
    selection_options.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    ttk.Label(selection_options, text="Selected-part out-of-range handling:").grid(
        row=0, column=0, sticky="w"
    )
    for row, (text, value) in enumerate((
        ("Keep original (direct play)", "keep"),
        ("Octave shift into playable range", "octave_shift"),
        ("Drop out-of-range notes", "drop"),
    ), start=1):
        ttk.Radiobutton(
            selection_options,
            text=text,
            value=value,
            variable=app.external_part_range_mode_var,
            command=app.on_external_direct_selection_changed,
        ).grid(row=row, column=0, sticky="w", padx=(14, 0))
    ttk.Label(
        selection_options,
        textvariable=app.external_part_warning_var,
        foreground="#a05a00",
    ).grid(row=4, column=0, sticky="w", pady=(4, 0))

    optimize = ttk.LabelFrame(
        parent, text="Optimize for Heartopia", padding=12
    )
    app.import_optimizer_frame = optimize
    optimize.grid(row=start_row + 1, column=0, sticky="ew", padx=12, pady=(0, 12))
    app.process_external_midi_button = ttk.Button(
        optimize,
        text="Process Imported MIDI",
        command=app.start_external_midi_import,
        state="disabled",
    )
    app.process_external_midi_button.grid(row=0, column=0, sticky="w")

    options = ttk.Frame(optimize)
    options.grid(row=1, column=0, sticky="w", pady=(8, 0))
    for column, (text, variable) in enumerate((
        ("Skip Cleanup", app.skip_cleanup_var),
        ("Skip Piano Arranger", app.skip_piano_arranger_var),
        ("Skip AI Optimizer", app.skip_ai_optimizer_var),
        ("Skip Pitch Correction", app.skip_pitch_correction_var),
        ("Direct Preview after processing", app.direct_preview_var),
    )):
        ttk.Checkbutton(options, text=text, variable=variable).grid(
            row=column // 3, column=column % 3, sticky="w", padx=(0, 14), pady=2
        )

    return start_row + 2
