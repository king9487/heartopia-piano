from ui.panels.timeline_renderer import _NoteCanvas


class StaffRenderer(_NoteCanvas):
    """Simplified time-based staff visualization; not a notation editor."""

    LEFT_MARGIN = 48
    STAFF_TOP = 42
    LINE_GAP = 12
    MIDDLE_C_Y = STAFF_TOP + (LINE_GAP * 5.5)
    PITCH_STEP = 3.5

    renderer_name = "Staff View"

    def __init__(self, parent, selection_callback=None, **kwargs):
        super().__init__(
            parent,
            background="#fffdf8",
            height=210,
            **kwargs,
        )
        self.selection_callback = selection_callback
        self.pixels_per_second = 100.0
        self.selected_index = None
        self.note_positions = []
        self.total_duration = 0.0
        self.bind("<Button-1>", self._on_click)
        self.bind("<Shift-MouseWheel>", self._on_horizontal_wheel)

    @classmethod
    def pitch_to_y(cls, midi_note):
        return cls.MIDDLE_C_Y - ((int(midi_note) - 60) * cls.PITCH_STEP)

    def time_to_x(self, seconds):
        return self.LEFT_MARGIN + (max(0.0, float(seconds)) * self.pixels_per_second)

    def render_notes(self, notes=None):
        if notes is not None:
            self.notes = notes
        self.delete("all")
        self.note_positions = []
        self.total_duration = max((note.end for note in self.notes), default=0.0)
        canvas_width, canvas_height = self._canvas_size()
        width = max(canvas_width, self.time_to_x(self.total_duration) + 80)

        if not self.notes:
            self.rendered_notes = 0
            self._log_render_stats(
                canvas_width, canvas_height, 0, 0, "no notes were loaded"
            )
        elif canvas_width <= 1 or canvas_height <= 1:
            self.rendered_notes = 0
            self._log_render_stats(
                canvas_width, canvas_height, 0, 0, "canvas has no drawable area"
            )
            return

        for line_index in range(5):
            y = self.STAFF_TOP + (line_index * self.LINE_GAP)
            self.create_line(12, y, width, y, fill="#555", width=1)
        self.create_text(24, self.STAFF_TOP + 24, text="𝄞", font=("Segoe UI Symbol", 26))

        visible_notes = 0
        self.rendered_notes = 0
        for index, note in enumerate(self.notes):
            x = self.time_to_x(note.start)
            y = self.pitch_to_y(note.note)
            tail_end = max(x + 8, self.time_to_x(note.end))
            if tail_end >= 0 and x <= width and -4 <= y <= canvas_height + 4:
                visible_notes += 1
            color = "#c2410c" if index == self.selected_index else "#1d4ed8"
            self.create_line(x, y, tail_end, y, fill=color, width=3, tags=("note",))
            self.create_oval(
                x - 6, y - 4, x + 6, y + 4,
                fill=color, outline=color, tags=("note", f"note_{index}"),
            )
            self.note_positions.append((x, y))
            self.rendered_notes += 1

        self.create_line(
            self.LEFT_MARGIN, 12, self.LEFT_MARGIN, 205,
            fill="#dc2626", width=2, tags=("playhead",),
        )
        self.configure(scrollregion=(0, 0, width, 215))
        if self.notes:
            reason = None
            if self.rendered_notes == 0:
                reason = "all notes were outside the drawable timeline"
            self._log_render_stats(
                canvas_width, canvas_height, visible_notes, self.rendered_notes, reason
            )

    def set_playhead(self, seconds):
        x = self.time_to_x(seconds)
        if self.find_withtag("playhead"):
            self.coords("playhead", x, 12, x, 205)

    def set_zoom(self, pixels_per_second):
        self.pixels_per_second = max(25.0, min(float(pixels_per_second), 800.0))
        self.render_notes()

    def zoom_by(self, factor):
        self.set_zoom(self.pixels_per_second * float(factor))

    def select_note_at(self, x, y):
        canvas_x = self.canvasx(x)
        canvas_y = self.canvasy(y)
        candidates = [
            ((note_x - canvas_x) ** 2 + (note_y - canvas_y) ** 2, index)
            for index, (note_x, note_y) in enumerate(self.note_positions)
            if abs(note_x - canvas_x) <= 10 and abs(note_y - canvas_y) <= 9
        ]
        if not candidates:
            return None
        _, index = min(candidates)
        self.selected_index = index
        self.render_notes()
        if self.selection_callback is not None:
            self.selection_callback(index, self.notes[index])
        return index

    def _on_click(self, event):
        self.select_note_at(event.x, event.y)

    def _on_horizontal_wheel(self, event):
        self.xview_scroll(-1 if event.delta > 0 else 1, "units")


# Backwards-compatible name for callers and tests that used the old widget name.
StaffViewCanvas = StaffRenderer
