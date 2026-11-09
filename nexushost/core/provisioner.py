"""Creates a real, ready-to-run server folder from a user's choices."""
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .db import Database, ServerRecord
from .javamgr import JavaManager
from .props import Properties
from .providers import PROVIDERS, required_java
from .reporter import Reporter


class ValidationError(ValueError):
    pass


@dataclass
class CreateSpec:
    name: str
    software: str
    version: str
    ram_mb: int
    port: int
    eula_accepted: bool


def validate(spec: CreateSpec, db: Database):
    name = spec.name.strip()
    if not name or len(name) > 40:
        raise ValidationError("Enter a server name of up to 40 characters.")
    if spec.software not in PROVIDERS:
        raise ValidationError("Choose a server software.")
    if not spec.version:
        raise ValidationError("Choose a Minecraft version.")
    if spec.ram_mb < 512:
        raise ValidationError("At least 512 MB of RAM is required.")
    if not 1024 <= spec.port <= 65535:
        raise ValidationError("The port must be between 1024 and 65535.")
    for other in db.list_servers():
        if other.port == spec.port:
            raise ValidationError(f"Port {spec.port} is already used by the server '{other.name}'.")
        if other.name.lower() == name.lower():
            raise ValidationError(f"A server named '{other.name}' already exists.")
    if not spec.eula_accepted:
        raise ValidationError("You must accept the Minecraft EULA to create a server.")


def _unique_dir(base: Path, name: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.") or "server"
    candidate, n = base / slug, 2
    while candidate.exists():
        candidate = base / f"{slug}-{n}"
        n += 1
    return candidate


def create_server(db: Database, javamgr: JavaManager, base_dir, spec: CreateSpec, rep: Reporter) -> ServerRecord:
    validate(spec, db)
    provider = PROVIDERS[spec.software]
    rep.status(f"Checking Java requirements for Minecraft {spec.version}")
    major = required_java(spec.version)
    java = javamgr.ensure(major, rep=rep)
    rep.check()

    dest = _unique_dir(Path(base_dir), spec.name.strip())
    dest.mkdir(parents=True)
    try:
        rep.progress(0)
        jar_file = provider.install(spec.version, dest, java, javamgr, rep)
        rep.check()
        rep.status("Writing server configuration")
        props = Properties(dest / "server.properties")
        props.set("server-port", spec.port)
        props.set("motd", f"{spec.name.strip()} - hosted with NEXUS HOST")
        props.save()
        (dest / "eula.txt").write_text(
            "# Accepted by the user inside NEXUS HOST (https://aka.ms/MinecraftEULA)\neula=true\n", encoding="utf-8")
        if provider.content_folder:
            (dest / provider.content_folder).mkdir(exist_ok=True)
        record = db.add_server(
            name=spec.name.strip(), type=spec.software, mc_version=spec.version, ram_mb=spec.ram_mb,
            port=spec.port, path=str(dest), jar_file=jar_file, java_major=major,
        )
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    rep.progress(1)
    rep.status("Server created")
    return record
