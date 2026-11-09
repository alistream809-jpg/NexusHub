"""Tiny thread-agnostic event class so the core engine has no GUI dependency."""
import logging

log = logging.getLogger(__name__)


class Event:
    def __init__(self):
        self._subscribers = []

    def connect(self, fn):
        self._subscribers.append(fn)

    def emit(self, *args):
        for fn in list(self._subscribers):
            try:
                fn(*args)
            except Exception:  # a broken listener must never break the engine
                log.exception("Event listener failed")
