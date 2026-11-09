"""Runs one real Minecraft server process and tracks its true state.

A server is only reported ONLINE after the process itself prints its "Done" line,
player counts come from the server's own status endpoint, and every stop goes
through "save-all flush" followed by "stop" before any forced termination.
"""
import collections
import os
import re
import shlex
import subprocess
import threading
import time
from pathlib import Path

import psutil

from . import mcping, netutil
from .db import Database, ServerRecord
from .events import Event
from .providers import FORGE_MARKER

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
RE_DONE = re.compile(r"Done \([\d.,]+\s*s\)!")
RE_JOIN = re.compile(r"(?:^|\]:\s|\]\s)(?:\[[^\]]*\]\s)?(\w{1,32}) joined the game\s*$")
RE_LEFT = re.compile(r"(?:^|\]:\s|\]\s)(?:\[[^\]]*\]\s)?(\w{1,32}) left the game\s*$")
RE_SAVED = re.compile(r"Saved the (?:game|world)|All dimensions are saved")
RE_ERROR = re.compile(r"[/\s](?:ERROR|FATAL)\]|^\s+at [\w.$<>/]+\(|^Caused by:|^Exception in thread|^[\w.$]+(?:Exception|Error)\b")
RE_WARN = re.compile(r"[/\s]WARN\]|\[WARN\]")

HINTS = (
    ("Failed to bind to port", "The port is already in use by another program. Change the port in Networking."),
    ("UnsupportedClassVersionError", "This server needs a newer Java. Open Application and install the matching Java."),
    ("Could not reserve enough space", "Not enough free RAM for this allocation. Lower the RAM in Server Settings."),
    ("OutOfMemoryError", "The server ran out of memory. Increase its RAM in Server Settings."),
    ("You need to agree to the EULA", "The Minecraft EULA has not been accepted for this server."),
)


class Status:
    STOPPED = "stopped"
    STARTING = "starting"
    ONLINE = "online"
    STOPPING = "stopping"
    CRASHED = "crashed"


class ServerError(Exception):
    pass


def classify(line: str) -> str:
    if RE_ERROR.search(line):
        return "error"
    if RE_WARN.search(line):
        return "warn"
    if RE_JOIN.search(line) or RE_LEFT.search(line):
        return "player"
    return "info"


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def build_command(record: ServerRecord, java_path: str):
    folder = Path(record.path)
    extra = shlex.split(record.jvm_args, posix=(os.name != "nt")) if record.jvm_args.strip() else []
    heap = [f"-Xms{min(record.ram_mb, 1024)}M", f"-Xmx{record.ram_mb}M", "-Dfile.encoding=UTF-8"] + extra
    if record.jar_file == FORGE_MARKER:
        name = "win_args.txt" if os.name == "nt" else "unix_args.txt"
        found = sorted(folder.glob(f"libraries/net/minecraftforge/forge/*/{name}"))
        if not found:
            raise ServerError("Forge launch files are missing. Delete and recreate this server.")
        (folder / "user_jvm_args.txt").write_text("\n".join(heap) + "\n", encoding="utf-8")
        return [java_path, "@user_jvm_args.txt", "@" + found[-1].relative_to(folder).as_posix(), "nogui"]
    if not record.jar_file or not (folder / record.jar_file).is_file():
        raise ServerError(f"The server jar '{record.jar_file}' is missing from {folder}.")
    return [java_path, *heap, "-jar", record.jar_file, "nogui"]


class ServerController:
    def __init__(self, record: ServerRecord, db: Database, javamgr):
        self.record = record
        self.db = db
        self.javamgr = javamgr
        self.status = Status.STOPPED
        self.on_status = Event()      # (status)
        self.on_line = Event()        # (kind, text)
        self.on_players = Event()     # (names, count, max)
        self.on_countdown = Event()   # (seconds remaining, or -1 when inactive)
        self.on_stats = Event()       # (ram_bytes, uptime_seconds)
        self.console = collections.deque(maxlen=5000)
        self.player_names = set()
        self.player_count = 0
        self.max_players = 0
        self.ram_bytes = 0
        self.started_at = 0.0
        self.countdown_remaining = -1.0
        self.last_stop_reason = ""
        self._proc = None
        self._lock = threading.RLock()
        self._saved = threading.Event()
        self._wake = threading.Event()
        self._stop_requested = False
        self._restart_pending = False
        self._deadline = None
        self._seen_player = False
        self._ping_count = None
        self._ping_ts = 0.0
        self._last_ping = 0.0
        self._last_player_event = 0.0
        self._tail = collections.deque(maxlen=60)

    # ------------------------------------------------------------------ helpers
    @property
    def running(self) -> bool:
        return self.status in (Status.STARTING, Status.ONLINE, Status.STOPPING)

    def _set_status(self, status: str):
        with self._lock:
            if self.status == status:
                return
            self.status = status
        self.on_status.emit(status)

    def _emit_line(self, kind: str, text: str):
        self.console.append((kind, text))
        self.on_line.emit(kind, text)

    def system(self, text: str, kind: str = "system"):
        self._emit_line(kind, f"[NEXUS] {text}")

    def _send(self, text: str) -> bool:
        with self._lock:
            proc = self._proc
            if not proc or proc.poll() is not None or not proc.stdin:
                return False
            try:
                proc.stdin.write((text + "\n").encode("utf-8"))
                proc.stdin.flush()
                return True
            except (OSError, ValueError):
                return False

    # ---------------------------------------------------------------- lifecycle
    def start(self):
        with self._lock:
            if self.status not in (Status.STOPPED, Status.CRASHED):
                raise ServerError("The server is already running.")
            java = self.javamgr.find(self.record.java_major)
            if java is None:
                raise ServerError(
                    f"Java {self.record.java_major} is not installed. Open the Application page and install it.")
            command = build_command(self.record, java.path)
            if not netutil.port_available(self.record.port):
                raise ServerError(
                    f"Port {self.record.port} is already in use by another program. Choose a different port in Networking.")
            self._stop_requested = False
            self._seen_player = False
            self._deadline = None
            self._ping_count = None
            self.player_names = set()
            self.player_count = 0
            self.max_players = 0
            self.last_stop_reason = ""
            self._tail.clear()
            flags = (CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
            try:
                self._proc = subprocess.Popen(
                    command, cwd=self.record.path, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, creationflags=flags)
            except OSError as exc:
                raise ServerError(f"Could not launch Java: {exc}") from exc
            self.started_at = time.time()
            proc = self._proc
        self._set_status(Status.STARTING)
        self.system(f"Starting {self.record.type} {self.record.mc_version} with {java.label()}")
        self.on_players.emit([], 0, 0)
        self.on_countdown.emit(-1.0)
        self.db.update_server(self.record.id, last_started=time.strftime("%Y-%m-%dT%H:%M:%S"))
        reader = threading.Thread(target=self._read_output, args=(proc,), daemon=True)
        reader.start()
        threading.Thread(target=self._monitor, args=(proc, reader), daemon=True).start()

    def stop(self, reason: str = "user") -> bool:
        with self._lock:
            if self.status in (Status.STOPPED, Status.CRASHED):
                return False
            if self.status == Status.STOPPING:
                return True
            previous = self.status
            self._stop_requested = True
            self.last_stop_reason = reason
            proc = self._proc
        self._set_status(Status.STOPPING)
        self._deadline = None
        self.on_countdown.emit(-1.0)
        threading.Thread(target=self._graceful_stop, args=(proc, previous), daemon=True).start()
        return True

    def restart(self):
        with self._lock:
            if self.status in (Status.STOPPED, Status.CRASHED):
                pass
            else:
                self._restart_pending = True
                self.stop("restart")
                return
        self.start()

    def kill(self):
        with self._lock:
            proc = self._proc
            self._stop_requested = True
        if proc and proc.poll() is None:
            self.system("Force killing the server process", "warn")
            proc.kill()

    def send_command(self, command: str):
        command = command.strip().lstrip("/")
        if not command:
            return
        if self.status != Status.ONLINE:
            raise ServerError("Commands can only be sent while the server is online.")
        self._emit_line("command", f"> {command}")
        if not self._send(command):
            raise ServerError("The server did not accept the command (its input is closed).")

    def _graceful_stop(self, proc, previous):
        try:
            if previous == Status.ONLINE:
                self.system("Saving the world")
                self._saved.clear()
                if self._send("save-all flush"):
                    self._saved.wait(15)
            self.system("Stopping the server")
            self._send("stop")
            try:
                proc.wait(timeout=60 if previous == Status.ONLINE else 30)
                return
            except subprocess.TimeoutExpired:
                pass
            self.system("The server did not stop in time. Terminating it.", "warn")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as exc:  # never let the stop thread die silently
            self.system(f"Error while stopping: {exc}", "error")
            if proc.poll() is None:
                proc.kill()

    # ------------------------------------------------------------ output / state
    def _read_output(self, proc):
        for raw in iter(proc.stdout.readline, b""):
            line = ANSI.sub("", raw.decode("utf-8", "replace").rstrip("\r\n"))
            if line.strip():
                self._handle_line(line)

    def _handle_line(self, line: str):
        self._tail.append(line)
        self._emit_line(classify(line), line)
        if self.status == Status.STARTING and RE_DONE.search(line):
            self._set_status(Status.ONLINE)
            self.system("Server is online and accepting connections")
        if RE_SAVED.search(line):
            self._saved.set()
        join, left = RE_JOIN.search(line), RE_LEFT.search(line)
        if join:
            self._seen_player = True
            self._last_player_event = time.time()
            self.player_names.add(join.group(1))
            self._publish_players()
        elif left:
            self._last_player_event = time.time()
            self.player_names.discard(left.group(1))
            self._publish_players()

    def _effective_count(self) -> int:
        if self._ping_count is not None and self._ping_ts >= self._last_player_event:
            return self._ping_count
        return len(self.player_names)

    def _publish_players(self):
        self.player_count = self._effective_count()
        self.on_players.emit(sorted(self.player_names), self.player_count, self.max_players)

    def _monitor(self, proc, reader):
        while proc.poll() is None:
            self._wake.wait(1.0)
            if proc.poll() is not None:
                break
            try:
                self._tick(proc)
            except Exception as exc:
                self.system(f"Monitor error: {exc}", "warn")
        reader.join(timeout=5)
        for pipe in (proc.stdin, proc.stdout):
            try:
                pipe.close()
            except (OSError, ValueError):
                pass
        self._on_exit(proc.returncode)

    def _tick(self, proc):
        now = time.time()
        try:
            main = psutil.Process(proc.pid)
            self.ram_bytes = main.memory_info().rss
        except psutil.Error:
            pass
        self.on_stats.emit(self.ram_bytes, now - self.started_at)
        if self.status != Status.ONLINE:
            return
        if now - self._last_ping >= 5:
            self._last_ping = now
            try:
                info = mcping.status("127.0.0.1", self.record.port)
                self._ping_count, self._ping_ts, self.max_players = info["online"], time.time(), info["max"]
                if info["online"] == 0:
                    self.player_names.clear()
            except (OSError, ValueError):
                self._ping_count = None
            self._publish_players()
        self._autostop(now)

    def _autostop(self, now: float):
        if self.status != Status.ONLINE or self._stop_requested:
            return
        if not self.record.auto_stop_enabled:
            if self._deadline is not None:
                self._deadline = None
                self.on_countdown.emit(-1.0)
            return
        count = self._effective_count()
        if count > 0:
            if self._deadline is not None:
                self._deadline = None
                self.countdown_remaining = -1.0
                self.system("A player joined. Auto-shutdown countdown cancelled.")
                self.on_countdown.emit(-1.0)
            return
        seconds = max(1, int(self.record.auto_stop_seconds))
        if self._deadline is None:
            count_on_start = self.db.get_setting("autostop_on_start", "1") == "1"
            if self._seen_player or count_on_start:
                self._deadline = now + seconds
                self.system(f"No players online. The server will stop in {format_duration(seconds)} unless someone joins.")
            else:
                return
        remaining = self._deadline - now
        self.countdown_remaining = max(0.0, remaining)
        self.on_countdown.emit(self.countdown_remaining)
        if remaining <= 0:
            self.system("Nobody joined in time. Saving the world and stopping the server.")
            self.stop("autostop")

    def _on_exit(self, code):
        with self._lock:
            requested = self._stop_requested
            restart = self._restart_pending
            was_starting = self.status == Status.STARTING
            self._restart_pending = False
            self._proc = None
        crashed = (code not in (0, None)) and not requested
        if code == 0 and was_starting and not requested:
            crashed = True  # exited before ever coming online
        self.player_names.clear()
        self.player_count = 0
        self.ram_bytes = 0
        self._deadline = None
        self._ping_count = None
        self.on_players.emit([], 0, 0)
        self.on_countdown.emit(-1.0)
        self.on_stats.emit(0, 0.0)
        if crashed:
            self.system(f"The server stopped unexpectedly (exit code {code}).", "error")
            blob = "\n".join(self._tail)
            for needle, hint in HINTS:
                if needle in blob:
                    self.system(hint, "error")
                    break
            self._set_status(Status.CRASHED)
        else:
            self.system(f"Server stopped (exit code {code}).")
            self._set_status(Status.STOPPED)
        if restart and not crashed:
            time.sleep(1.0)
            try:
                self.start()
            except ServerError as exc:
                self.system(f"Restart failed: {exc}", "error")
