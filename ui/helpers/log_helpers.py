class UiLogHelpersMixin:
    """Shared log and application-status updates."""

    def log_message(self, message):
        assert self.log is not None
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_status(self, message):
        self.status_var.set(message)

    def show_import_repair_notice(self):
        notice_var = getattr(self, "import_repair_notice_var", None)
        if notice_var is not None:
            notice_var.set(
                "⚠ Invalid MIDI detected.\nA repaired working copy is being used."
            )
        notice = getattr(self, "import_repair_notice_frame", None)
        if notice is not None:
            notice.grid()

    def clear_import_repair_notice(self):
        notice_var = getattr(self, "import_repair_notice_var", None)
        if notice_var is not None:
            notice_var.set("")
        notice = getattr(self, "import_repair_notice_frame", None)
        if notice is not None:
            notice.grid_remove()
