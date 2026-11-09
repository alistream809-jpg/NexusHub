"""Reads and edits whitelist.json for a server folder."""
import hashlib
import json
import re
import uuid
from pathlib import Path

from .http import NetworkError, get_json

NAME = re.compile(r"^\w{1,16}$")


class WhitelistError(Exception):
    pass


def _file(folder) -> Path:
    return Path(folder) / "whitelist.json"


def read(folder):
    path = _file(folder)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [{"uuid": e.get("uuid", ""), "name": e.get("name", "")} for e in data if e.get("name")]
    except (OSError, ValueError):
        return []


def _write(folder, entries):
    _file(folder).write_text(json.dumps(entries, indent=2), encoding="utf-8")


def offline_uuid(name: str) -> str:
    digest = hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest()
    return str(uuid.UUID(bytes=digest, version=3))


def lookup_uuid(name: str, online_mode: bool) -> str:
    if not online_mode:
        return offline_uuid(name)
    try:
        data = get_json(f"https://api.mojang.com/users/profiles/minecraft/{name}", timeout=10)
    except NetworkError as exc:
        if "404" in str(exc) or "204" in str(exc):
            raise WhitelistError(f"No Minecraft account named '{name}' exists.") from exc
        raise WhitelistError(str(exc)) from exc
    raw = data.get("id", "")
    if len(raw) != 32:
        raise WhitelistError(f"No Minecraft account named '{name}' exists.")
    return str(uuid.UUID(raw))


def add(folder, name: str, online_mode: bool):
    if not NAME.match(name):
        raise WhitelistError("Player names are 1 to 16 letters, digits or underscores.")
    entries = read(folder)
    if any(e["name"].lower() == name.lower() for e in entries):
        raise WhitelistError(f"{name} is already whitelisted.")
    entries.append({"uuid": lookup_uuid(name, online_mode), "name": name})
    _write(folder, entries)


def remove(folder, name: str):
    _write(folder, [e for e in read(folder) if e["name"].lower() != name.lower()])
