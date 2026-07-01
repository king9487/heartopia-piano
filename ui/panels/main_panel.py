from tkinter import ttk

from ui.panels.cleanup_panel import build_cleanup_panel
from ui.panels.convert_panel import build_convert_panel
from ui.panels.log_panel import build_log_panel
from ui.panels.midi_panel import build_midi_panel
from ui.panels.settings_panel import build_settings_panel
from ui.panels.studio_panel import build_studio_panel


def build_main_panel(app, parent):
    parent.columnconfigure(0, weight=1)
    next_row = build_convert_panel(app, parent)
    next_row = build_midi_panel(app, parent, next_row)
    build_log_panel(app, parent, next_row)


def build_application_ui(app):
    app.root.columnconfigure(0, weight=1)
    app.root.rowconfigure(0, weight=1)

    notebook = ttk.Notebook(app.root)
    notebook.grid(row=0, column=0, sticky="nsew")
    main_tab = ttk.Frame(notebook)
    playback_tab = ttk.Frame(notebook)
    cleanup_tab = ttk.Frame(notebook)
    studio_tab = ttk.Frame(notebook)
    notebook.add(main_tab, text="Main")
    notebook.add(playback_tab, text="Playback Settings")
    notebook.add(cleanup_tab, text="MIDI Cleanup")
    notebook.add(studio_tab, text="MIDI Studio")
    notebook.bind("<<NotebookTabChanged>>", app.on_notebook_tab_changed)

    app.notebook = notebook
    app.main_tab = main_tab
    app.playback_tab = playback_tab
    app.cleanup_tab = cleanup_tab
    app.studio_tab = studio_tab

    playback_tab.columnconfigure(0, weight=1)
    cleanup_tab.columnconfigure(0, weight=1)
    build_main_panel(app, main_tab)
    build_settings_panel(app, playback_tab)
    build_cleanup_panel(app, cleanup_tab)
    build_studio_panel(app, studio_tab)

    assert app.log is not None
    assert app.convert_button is not None
    assert app.local_audio_button is not None
    assert app.stop_button is not None
    assert app.play_button is not None
    assert app.midi_source_combo is not None
    assert app.cached_combo is not None
    assert app.studio_seek is not None
    assert app.studio_play_button is not None
    assert app.studio_pause_button is not None
    assert app.studio_stop_button is not None
    assert app.editor_tree is not None
