"""Filesystem locations used by NEXUS HOST."""
import os
import sys
from pathlib import Path

from .. import APP_ID


def resource_path(relative: str) -> Path:
    """Resolve a bundled resource, both from source and from a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parents[2]
    return root / relative


def data_dir() -> Path:
    override = os.environ.get("NEXUSHOST_HOME")
    if override:
        path = Path(override)
    elif os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_ID
    else:
        path = Path.home() / ".nexushost"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_servers_dir() -> Path:
    path = data_dir() / "servers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtimes_dir() -> Path:
    path = data_dir() / "runtimes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "nexushost.db"


def log_path() -> Path:
    return data_dir() / "nexushost.log"
