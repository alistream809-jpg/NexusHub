"""Owns every server controller and the application database."""
import shutil
import time

from .controller import ServerController, ServerError
from .db import Database
from .events import Event
from .javamgr import JavaManager
from .paths import db_path, default_servers_dir, runtimes_dir
from .provisioner import CreateSpec, create_server
from .reporter import Reporter


class ServerManager:
    def __init__(self, database_path=None):
        self.db = Database(database_path or db_path())
        self.javamgr = JavaManager(runtimes_dir(), lambda: self.db.get_setting("custom_java", ""))
        self.controllers = {}
        self.on_added = Event()    # (controller)
        self.on_removed = Event()  # (server_id)
        for record in self.db.list_servers():
            self.controllers[record.id] = ServerController(record, self.db, self.javamgr)

    @property
    def servers_dir(self):
        from pathlib import Path
        custom = self.db.get_setting("servers_dir", "")
        return Path(custom) if custom else default_servers_dir()

    def all(self):
        return list(self.controllers.values())

    def get(self, server_id):
        return self.controllers.get(server_id)

    def create(self, spec: CreateSpec, rep: Reporter):
        self.servers_dir.mkdir(parents=True, exist_ok=True)
        record = create_server(self.db, self.javamgr, self.servers_dir, spec, rep)
        controller = ServerController(record, self.db, self.javamgr)
        self.controllers[record.id] = controller
        self.on_added.emit(controller)
        return controller

    def delete(self, server_id: int, delete_files: bool = True):
        controller = self.controllers.get(server_id)
        if not controller:
            return
        if controller.running:
            raise ServerError("Stop the server before deleting it.")
        self.db.delete_server(server_id)
        del self.controllers[server_id]
        if delete_files:
            shutil.rmtree(controller.record.path, ignore_errors=True)
        self.on_removed.emit(server_id)

    def update(self, server_id: int, **values):
        controller = self.controllers[server_id]
        self.db.update_server(server_id, **values)
        for key, value in values.items():
            setattr(controller.record, key, value)

    def running(self):
        return [c for c in self.controllers.values() if c.running]

    def shutdown(self, pump=None, timeout: float = 90.0):
        """Gracefully stop every server and wait. pump() is called while waiting (keeps a GUI alive)."""
        for controller in self.running():
            controller.stop("app-exit")
        deadline = time.time() + timeout
        while self.running() and time.time() < deadline:
            if pump:
                pump()
            time.sleep(0.05)
        for controller in self.running():
            controller.kill()
        self.db.close()
