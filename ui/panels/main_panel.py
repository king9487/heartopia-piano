from tkinter import ttk

from ui.panels.cleanup_panel import build_cleanup_panel
from ui.panels.analysis_panel import build_analysis_panel
from ui.panels.convert_panel import build_convert_panel, build_import_panel
from ui.panels.log_panel import build_log_panel
from ui.panels.midi_panel import build_main_midi_panel, build_midi_sources_panel
from ui.panels.settings_panel import build_settings_panel
from ui.panels.studio_panel import build_studio_panel


def build_main_panel(app, parent):
    parent.columnconfigure(0, weight=1)
    next_row = build_convert_panel(app, parent)
    next_row = build_main_midi_panel(app, parent, next_row)
    build_log_panel(app, parent, next_row)


def build_application_ui(app):
    app.root.columnconfigure(0, weight=1)
    app.root.rowconfigure(0, weight=1)

    notebook = ttk.Notebook(app.root)
    notebook.grid(row=0, column=0, sticky="nsew")
    main_tab = ttk.Frame(notebook)
    import_tab = ttk.Frame(notebook)
    optimization_tab = ttk.Frame(notebook)
    playback_tab = ttk.Frame(notebook)
    studio_tab = ttk.Frame(notebook)
    analysis_tab = ttk.Frame(notebook)
    notebook.add(main_tab, text="Main")
    notebook.add(import_tab, text="Import")
    notebook.add(optimization_tab, text="Optimization")
    notebook.add(playback_tab, text="Playback")
    notebook.add(studio_tab, text="Studio")
    notebook.add(analysis_tab, text="Analysis")
    notebook.bind("<<NotebookTabChanged>>", app.on_notebook_tab_changed)

    app.notebook = notebook
    app.main_tab = main_tab
    app.import_tab = import_tab
    app.optimization_tab = optimization_tab
    app.playback_tab = playback_tab
    app.cleanup_tab = optimization_tab
    app.studio_tab = studio_tab
    app.analysis_tab = analysis_tab

    import_tab.columnconfigure(0, weight=1)
    optimization_tab.columnconfigure(0, weight=1)
    playback_tab.columnconfigure(0, weight=1)
    analysis_tab.columnconfigure(0, weight=1)
    build_main_panel(app, main_tab)
    build_import_panel(app, import_tab)
    build_cleanup_panel(app, optimization_tab)
    playback_row = build_midi_sources_panel(app, playback_tab)
    build_settings_panel(app, playback_tab, playback_row)
    build_studio_panel(app, studio_tab)
    build_analysis_panel(app, analysis_tab, 0)

    assert app.log is not None
    assert app.convert_button is not None
    assert app.local_audio_button is not None
    assert app.external_midi_button is not None
    assert app.process_external_midi_button is not None
    assert app.preview_original_midi_button is not None
    assert app.play_original_midi_button is not None
    assert app.open_original_midi_button is not None
    assert app.stop_button is not None
    assert app.play_button is not None
    assert app.midi_source_combo is not None
    assert app.cached_combo is not None
    assert app.studio_seek is not None
    assert app.studio_play_button is not None
    assert app.studio_pause_button is not None
    assert app.studio_stop_button is not None
    assert app.staff_view is not None
    assert app.editor_tree is not None
