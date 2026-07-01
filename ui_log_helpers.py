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
