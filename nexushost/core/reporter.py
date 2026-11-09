"""Progress / log / cancel channel passed into long-running tasks."""
import threading


class Cancelled(Exception):
    """Raised when the user cancels a running task."""


class Reporter:
    def __init__(self, on_status=None, on_progress=None, on_log=None, cancel=None):
        self._on_status = on_status
        self._on_progress = on_progress
        self._on_log = on_log
        self.cancel = cancel or threading.Event()

    def status(self, text: str):
        if self._on_status:
            self._on_status(text)
        self.log(text)

    def progress(self, fraction):
        """fraction in 0..1, or None for an indeterminate task."""
        if self._on_progress:
            self._on_progress(-1.0 if fraction is None else float(fraction))

    def log(self, line: str):
        if self._on_log:
            self._on_log(line)

    def check(self):
        if self.cancel.is_set():
            raise Cancelled()
