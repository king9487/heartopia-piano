import tkinter as tk

from midi_editor import load_editor_notes


class _NoteCanvas(tk.Canvas):
    """Common diagnostics and note ownership for timeline canvases."""

    renderer_name = "Timeline"

    def __init__(self, parent, log_callback=None, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.notes = []
        self.log_callback = log_callback
        self.rendered_notes = 0
        self.bind("<Configure>", self._on_configure, add="+")

    def _log(self, label, value):
        if self.log_callback is not None:
            self.log_callback(f"[{self.renderer_name}] {label}: {value}")

    def _canvas_size(self):
        width = int(self.winfo_width())
        height = int(self.winfo_height())
        if height <= 1:
            height = int(float(self.cget("height") or 0))
        return width, height

    def _log_render_stats(self, width, height, visible, rendered, reason=None):
        self._log("Loaded notes", len(self.notes))
        self._log("Canvas width", width)
        self._log("Canvas height", height)
        self._log("Visible notes", visible)
        self._log("Rendered notes", rendered)
        if rendered == 0:
            self._log("Rendered notes reason", reason or "unknown")

    def _on_configure(self, _event=None):
        self.render_notes()


class PianoRollRenderer(_NoteCanvas):
    """Compact piano-roll renderer using the shared timeline note objects."""

    renderer_name = "Piano Roll"
    X_PADDING = 8
    Y_PADDING = 6

    def __init__(self, parent, **kwargs):
        super().__init__(parent, background="#202225", height=80, **kwargs)
        self.total_duration = 0.0
        self.playhead_seconds = 0.0

    def render_notes(self, notes=None):
        if notes is not None:
            self.notes = notes
        self.delete("all")
        width, height = self._canvas_size()
        self.rendered_notes = 0

        if not self.notes:
            self._log_render_stats(width, height, 0, 0, "no notes were loaded")
            return
        if width <= 1 or height <= 1:
            self._log_render_stats(
                width, height, 0, 0, "canvas has no drawable area"
            )
            return

        valid_notes = [
            note
            for note in self.notes
            if float(note.end) >= 0.0 and 0 <= int(note.note) <= 127
        ]
        if not valid_notes:
            self._log_render_stats(
                width, height, 0, 0, "all notes have invalid time or pitch values"
            )
            return

        self.total_duration = max(float(note.end) for note in valid_notes)
        if self.total_duration <= 0.0:
            self._log_render_stats(
                width, height, 0, 0, "note timeline has zero duration"
            )
            return

        low_pitch = min(int(note.note) for note in valid_notes)
        high_pitch = max(int(note.note) for note in valid_notes)
        pitch_span = max(1, high_pitch - low_pitch + 1)
        drawable_width = max(1, width - (2 * self.X_PADDING))
        drawable_height = max(1, height - (2 * self.Y_PADDING))

        for note in valid_notes:
            start = max(0.0, float(note.start))
            end = max(start, float(note.end))
            x1 = self.X_PADDING + (start / self.total_duration) * drawable_width
            x2 = self.X_PADDING + (end / self.total_duration) * drawable_width
            row = high_pitch - int(note.note)
            y1 = self.Y_PADDING + (row / pitch_span) * drawable_height
            y2 = self.Y_PADDING + ((row + 0.8) / pitch_span) * drawable_height
            velocity = max(0, min(127, int(note.velocity)))
            blue = 120 + int((velocity / 127) * 115)
            self.create_rectangle(
                x1, y1, max(x1 + 2, x2), max(y1 + 2, y2),
                fill=f"#3b82{blue:02x}", outline="",
            )
            self.rendered_notes += 1

        self._draw_playhead()
        self._log_render_stats(
            width, height, len(valid_notes), self.rendered_notes
        )

    def _draw_playhead(self):
        if self.total_duration <= 0:
            return
        width, height = self._canvas_size()
        drawable_width = max(1, width - (2 * self.X_PADDING))
        position = min(max(self.playhead_seconds, 0.0), self.total_duration)
        x = self.X_PADDING + (position / self.total_duration) * drawable_width
        self.create_line(x, 0, x, height, fill="#ef4444", width=2, tags=("playhead",))

    def set_playhead(self, seconds):
        self.playhead_seconds = max(0.0, float(seconds))
        self.delete("playhead")
        self._draw_playhead()


class TimelineRenderer:
    """Own one note list and coordinate every timeline representation."""

    def __init__(self, piano_roll_renderer, staff_renderer):
        self.piano_roll_renderer = piano_roll_renderer
        self.staff_renderer = staff_renderer
        self.notes = []

    def load_midi(self, path):
        # Keep the established MIDI-to-editor-note loader as the single source.
        self.set_notes(load_editor_notes(path))

    def set_notes(self, notes):
        self.notes = notes if isinstance(notes, list) else list(notes)
        self.piano_roll_renderer.render_notes(self.notes)
        self.staff_renderer.render_notes(self.notes)

    def render(self):
        self.piano_roll_renderer.render_notes(self.notes)
        self.staff_renderer.render_notes(self.notes)

    def set_playhead(self, seconds):
        self.piano_roll_renderer.set_playhead(seconds)
        self.staff_renderer.set_playhead(seconds)
