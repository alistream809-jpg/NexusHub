"""Constructs the whole GUI against a stubbed Qt to catch wiring errors (names, signatures, bind paths)."""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qt_stub; qt_stub.install()
os.environ["NEXUSHOST_HOME"] = tempfile.mkdtemp()

from nexushost.core.manager import ServerManager
from nexushost.ui.bridge import AppContext
from nexushost.ui.theme import stylesheet
from nexushost.ui.main_window import MainWindow, PAGES

assert "$" not in stylesheet(), "unreplaced colour token in QSS"
mgr = ServerManager()
ctx = AppContext(mgr)
win = MainWindow(ctx)                                     # no servers yet
for key, *_ in PAGES: win.navigate(key)
folder = Path(os.environ["NEXUSHOST_HOME"]) / "srv"; folder.mkdir(); (folder / "paper.jar").write_bytes(b"x")
(folder / "plugins").mkdir(); (folder / "plugins" / "a.jar").write_bytes(b"x")
(folder / "server.properties").write_text("max-players=10\nmotd=Hi\n")
rec = mgr.db.add_server(name="Demo", type="Paper", mc_version="1.21", ram_mb=2048, port=25570, path=str(folder), jar_file="paper.jar")
from nexushost.core.controller import ServerController
ctx.add_controller(ServerController(rec, mgr.db, mgr.javamgr))   # selects + binds every page
for key, *_ in PAGES:
    win.navigate(key)
h = ctx.selected; win._selected(h); win._fill_selector()
for slot in ("_status",): pass
page = win.pages["dashboard"]
for st in ("stopped", "starting", "online", "stopping", "crashed"):
    page._status(st)
page._players(["A", "B"], 2, 20); page._stats(500 * 1024 * 1024, 3725.0); page._countdown(65.0); page._countdown(-1.0)
con = win.pages["console"]
for kind in ("info", "warn", "error", "player", "system", "command"): con._line(kind, "test")
con._players(["A"], 1, 20)
print("UI smoke test OK")
