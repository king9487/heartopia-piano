import tkinter as tk
from tkinter import ttk

from ui.panels.cleanup_panel import build_cleanup_panel
from ui.panels.analysis_panel import build_analysis_panel
from ui.panels.convert_panel import build_convert_panel, build_import_panel
from ui.panels.log_panel import build_log_panel
from ui.panels.midi_panel import build_main_midi_panel, build_midi_sources_panel
from ui.panels.settings_panel import build_settings_panel
from ui.panels.studio_panel import build_studio_panel
from ui_workflow import (
    QUICK_PLAY,
    STUDIO_MODE,
    UiWorkflowManager,
    apply_selected_workflow,
)


def build_main_panel(app, parent):
    parent.columnconfigure(0, weight=1)
    next_row = build_convert_panel(app, parent)
    next_row = build_main_midi_panel(app, parent, next_row)
    build_log_panel(app, parent, next_row)


class _AutoHidingScrollbar(ttk.Scrollbar):
    """Hide the scrollbar while its complete scroll region is visible."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._visible = True

    def set(self, first, last):
        should_show = float(first) > 0.0 or float(last) < 1.0
        if should_show and not self._visible:
            self.grid()
            self._visible = True
        elif not should_show and self._visible:
            self.grid_remove()
            self._visible = False
        super().set(first, last)


class ScrollableFrame(ttk.Frame):
    """Canvas-backed frame whose content scrolls vertically when necessary."""

    def __init__(self, master):
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        canvas_options = {"borderwidth": 0, "highlightthickness": 0}
        frame_background = ttk.Style(master).lookup("TFrame", "background")
        if frame_background:
            canvas_options["background"] = frame_background
        self.canvas = tk.Canvas(self, **canvas_options)
        self.scrollbar = _AutoHidingScrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.content = ttk.Frame(self.canvas)
        self.content.columnconfigure(0, weight=1)

        self._content_window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.content.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._fit_content_to_viewport)

    def _update_scroll_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _fit_content_to_viewport(self, event):
        self.canvas.itemconfigure(self._content_window, width=event.width)


def _bind_tab_mousewheel(root, notebook, tab_canvases):
    """Scroll only the selected tab while the pointer is inside it."""
    wheel_remainders = {str(tab): 0.0 for tab in tab_canvases}
    windowing_system = root.tk.call("tk", "windowingsystem")

    def is_descendant(widget, ancestor):
        while widget is not None:
            if widget == ancestor:
                return True
            widget = getattr(widget, "master", None)
        return False

    def scroll(event):
        selected = notebook.select()
        canvas = tab_canvases.get(selected)
        if canvas is None or not is_descendant(event.widget, canvas.master):
            return None

        # Let widgets with their own vertical viewport handle the wheel first.
        if isinstance(event.widget, (tk.Text, tk.Listbox, ttk.Treeview)):
            return None

        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return None
            movement = -delta / 120 if windowing_system == "win32" else -delta
            movement += wheel_remainders[selected]
            units = int(movement)
            wheel_remainders[selected] = movement - units

        if units:
            previous_view = canvas.yview()
            canvas.yview_scroll(units, "units")
            if canvas.yview() != previous_view:
                return "break"
        return None

    root.bind("<MouseWheel>", scroll, add="+")
    root.bind("<Button-4>", scroll, add="+")
    root.bind("<Button-5>", scroll, add="+")


def build_application_ui(app):
    app.root.columnconfigure(0, weight=1)
    app.root.rowconfigure(1, weight=1)

    workflow = ttk.LabelFrame(app.root, text="Playback Workflow", padding=(12, 6))
    workflow.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
    ttk.Radiobutton(
        workflow, text="Quick Play", value=QUICK_PLAY,
        variable=app.workflow_var,
        command=lambda: apply_selected_workflow(app),
    ).grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(
        workflow, text="Studio Mode", value=STUDIO_MODE,
        variable=app.workflow_var,
        command=lambda: apply_selected_workflow(app),
    ).grid(row=0, column=1, sticky="w", padx=(18, 0))

    notebook = ttk.Notebook(app.root)
    notebook.grid(row=1, column=0, sticky="nsew")
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

    tab_contents = {}
    tab_canvases = {}
    for tab in (
        main_tab,
        import_tab,
        optimization_tab,
        playback_tab,
        studio_tab,
        analysis_tab,
    ):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        scrollable = ScrollableFrame(tab)
        scrollable.grid(row=0, column=0, sticky="nsew")
        tab_contents[tab] = scrollable.content
        tab_canvases[str(tab)] = scrollable.canvas

    build_main_panel(app, tab_contents[main_tab])
    build_import_panel(app, tab_contents[import_tab])
    build_cleanup_panel(app, tab_contents[optimization_tab])
    playback_row = build_midi_sources_panel(app, tab_contents[playback_tab])
    build_settings_panel(app, tab_contents[playback_tab], playback_row)
    build_studio_panel(app, tab_contents[studio_tab])
    build_analysis_panel(app, tab_contents[analysis_tab], 0)
    _bind_tab_mousewheel(app.root, notebook, tab_canvases)

    app.workflow_manager = UiWorkflowManager(app)
    apply_selected_workflow(app)

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
