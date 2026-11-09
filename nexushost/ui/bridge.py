"""Connects the Qt-free engine to the GUI through thread-safe Qt signals."""
from PySide6.QtCore import QObject, Signal

from ..core.controller import ServerController
from ..core.manager import ServerManager


class ServerHandle(QObject):
    status_changed = Signal(str)
    line = Signal(str, str)
    players_changed = Signal(list, int, int)
    countdown = Signal(float)
    stats = Signal(float, float)   # bytes can exceed 2^31, so never use int here

    def __init__(self, controller: ServerController):
        super().__init__()
        self.c = controller
        controller.on_status.connect(self.status_changed.emit)
        controller.on_line.connect(self.line.emit)
        controller.on_players.connect(self.players_changed.emit)
        controller.on_countdown.connect(self.countdown.emit)
        controller.on_stats.connect(self.stats.emit)

    @property
    def id(self) -> int:
        return self.c.record.id

    @property
    def record(self):
        return self.c.record

    @property
    def status(self) -> str:
        return self.c.status


class AppContext(QObject):
    servers_changed = Signal()
    selected_changed = Signal(object)
    status_any = Signal(int, str)

    def __init__(self, manager: ServerManager):
        super().__init__()
        self.manager = manager
        self.handles = {}
        self.selected = None
        self.navigate = lambda key: None
        for controller in manager.all():
            self._wrap(controller)
        wanted = self.manager.db.get_setting("selected_server", "")
        first = next(iter(self.handles), None)
        self.selected = self.handles.get(int(wanted)) if wanted.isdigit() and int(wanted) in self.handles else (
            self.handles[first] if first is not None else None)

    def _wrap(self, controller):
        handle = ServerHandle(controller)
        sid = handle.id
        handle.status_changed.connect(lambda status, i=sid: self.status_any.emit(i, status))
        self.handles[sid] = handle
        return handle

    def add_controller(self, controller):
        handle = self._wrap(controller)
        self.servers_changed.emit()
        self.select(handle.id)

    def remove(self, server_id: int):
        self.manager.delete(server_id)
        handle = self.handles.pop(server_id, None)
        if self.selected is handle:
            self.selected = next(iter(self.handles.values()), None)
            self.selected_changed.emit(self.selected)
        self.servers_changed.emit()

    def select(self, server_id):
        handle = self.handles.get(server_id)
        self.selected = handle
        self.manager.db.set_setting("selected_server", server_id if handle else "")
        self.selected_changed.emit(handle)
