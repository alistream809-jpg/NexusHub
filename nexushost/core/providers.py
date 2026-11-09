"""Server software providers: version lists and real installation logic for each type."""
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .http import download, get_json
from .javamgr import NOWINDOW, JavaInstall, JavaManager
from .reporter import Cancelled, Reporter

FORGE_MARKER = "@forge"  # jar_file value meaning "launch through Forge's args files"


class InstallError(Exception):
    pass


def vkey(version: str):
    return tuple(int(n) for n in re.findall(r"\d+", version))


_manifest_cache = None
_java_cache = {}


def mojang_manifest():
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = get_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
    return _manifest_cache


def mojang_releases():
    return [v["id"] for v in mojang_manifest()["versions"] if v["type"] == "release"]


def mojang_version_info(version: str) -> dict:
    for entry in mojang_manifest()["versions"]:
        if entry["id"] == version:
            return get_json(entry["url"])
    raise InstallError(f"Minecraft {version} is not known to Mojang.")


def required_java(version: str) -> int:
    if version not in _java_cache:
        try:
            _java_cache[version] = int(mojang_version_info(version).get("javaVersion", {}).get("majorVersion", 8))
        except InstallError:
            _java_cache[version] = 21
    return _java_cache[version]


def run_logged(cmd, cwd, rep: Reporter) -> int:
    """Run an external tool, streaming its output into the reporter, honouring cancel."""
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NOWINDOW)
    try:
        for raw in iter(proc.stdout.readline, b""):
            rep.log(raw.decode("utf-8", "replace").rstrip())
            if rep.cancel.is_set():
                proc.terminate()
                raise Cancelled()
        return proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()


@dataclass
class Provider:
    name: str = ""
    description: str = ""
    content_folder: str = ""  # "plugins", "mods" or "" when unsupported
    content_label: str = ""

    def versions(self):
        raise NotImplementedError

    def install(self, version: str, dest: Path, java: JavaInstall, javamgr: JavaManager, rep: Reporter) -> str:
        """Install into dest and return the jar_file value used for launching."""
        raise NotImplementedError


class Vanilla(Provider):
    def __init__(self):
        super().__init__("Vanilla", "The unmodified server published by Mojang.", "", "")

    def versions(self):
        return mojang_releases()

    def install(self, version, dest, java, javamgr, rep):
        info = mojang_version_info(version)
        server = info.get("downloads", {}).get("server")
        if not server:
            raise InstallError(f"Mojang publishes no server download for {version}.")
        rep.status(f"Downloading Minecraft server {version}")
        download(server["url"], dest / "server.jar", rep, sha1=server.get("sha1"))
        return "server.jar"


class Paper(Provider):
    API = "https://api.papermc.io/v2/projects/paper"

    def __init__(self):
        super().__init__("Paper", "High-performance fork of Spigot. Supports Bukkit and Spigot plugins.", "plugins", "plugins")

    def versions(self):
        return list(reversed(get_json(self.API)["versions"]))

    def install(self, version, dest, java, javamgr, rep):
        builds = get_json(f"{self.API}/versions/{version}/builds")["builds"]
        if not builds:
            raise InstallError(f"Paper has no build for {version}.")
        stable = [b for b in builds if b.get("channel", "default") == "default"] or builds
        build = stable[-1]
        app = build["downloads"]["application"]
        rep.status(f"Downloading Paper {version} build {build['build']}")
        url = f"{self.API}/versions/{version}/builds/{build['build']}/downloads/{app['name']}"
        download(url, dest / "paper.jar", rep, sha256=app.get("sha256"))
        return "paper.jar"


class Purpur(Provider):
    API = "https://api.purpurmc.org/v2/purpur"

    def __init__(self):
        super().__init__("Purpur", "Paper fork with extra gameplay options and plugin support.", "plugins", "plugins")

    def versions(self):
        return list(reversed(get_json(self.API)["versions"]))

    def install(self, version, dest, java, javamgr, rep):
        build = get_json(f"{self.API}/{version}")["builds"]["latest"]
        rep.status(f"Downloading Purpur {version} build {build}")
        download(f"{self.API}/{version}/{build}/download", dest / "purpur.jar", rep)
        return "purpur.jar"


class Spigot(Provider):
    URL = "https://hub.spigotmc.org/jenkins/job/BuildTools/lastSuccessfulBuild/artifact/target/BuildTools.jar"

    def __init__(self):
        super().__init__(
            "Spigot",
            "Reference Bukkit implementation. Compiled on your PC with BuildTools (5 to 15 minutes).",
            "plugins", "plugins",
        )

    def versions(self):
        return [v for v in mojang_releases() if vkey(v) >= (1, 8)]

    def install(self, version, dest, java, javamgr, rep):
        work = dest / "_buildtools"
        work.mkdir(parents=True, exist_ok=True)
        rep.status("Downloading Spigot BuildTools")
        download(self.URL, work / "BuildTools.jar", rep)
        rep.progress(None)
        build_java = javamgr.ensure(max(17, java.major), need_jdk=True, rep=rep)
        rep.status(f"Compiling Spigot {version}. This takes several minutes and needs internet access.")
        code = run_logged([build_java.path, "-jar", "BuildTools.jar", "--rev", version, "--output-dir", str(dest)], work, rep)
        jar = dest / f"spigot-{version}.jar"
        if code != 0 or not jar.exists():
            raise InstallError(f"Spigot BuildTools failed (exit code {code}). Read the log above, or choose Paper instead.")
        shutil.rmtree(work, ignore_errors=True)
        return jar.name


class Fabric(Provider):
    META = "https://meta.fabricmc.net/v2/versions"

    def __init__(self):
        super().__init__("Fabric", "Lightweight mod loader. Mods go in the mods folder.", "mods", "mods")

    def versions(self):
        games = get_json(f"{self.META}/game")
        return [g["version"] for g in games if g.get("stable") and vkey(g["version"]) >= (1, 14)]

    def install(self, version, dest, java, javamgr, rep):
        loader = next(x["version"] for x in get_json(f"{self.META}/loader") if x.get("stable"))
        installer = next(x["version"] for x in get_json(f"{self.META}/installer") if x.get("stable"))
        rep.status(f"Downloading Fabric launcher (loader {loader})")
        url = f"{self.META}/loader/{version}/{loader}/{installer}/server/jar"
        download(url, dest / "fabric-server-launch.jar", rep)
        return "fabric-server-launch.jar"


class Forge(Provider):
    PROMOS = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"

    def __init__(self):
        super().__init__("Forge", "Classic mod loader with the largest mod library. Installs on first creation.", "mods", "mods")

    def _promos(self):
        return get_json(self.PROMOS)["promos"]

    def versions(self):
        found = set()
        for key in self._promos():
            mc, _, kind = key.rpartition("-")
            if kind in ("latest", "recommended") and vkey(mc) >= (1, 12, 2):
                found.add(mc)
        return sorted(found, key=vkey, reverse=True)

    def install(self, version, dest, java, javamgr, rep):
        promos = self._promos()
        forge = promos.get(f"{version}-recommended") or promos.get(f"{version}-latest")
        if not forge:
            raise InstallError(f"Forge has no release for Minecraft {version}.")
        full = f"{version}-{forge}"
        url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{full}/forge-{full}-installer.jar"
        installer = dest / "forge-installer.jar"
        rep.status(f"Downloading Forge {forge}")
        download(url, installer, rep)
        rep.progress(None)
        rep.status("Running the Forge installer. It downloads libraries and can take a few minutes.")
        code = run_logged([java.path, "-jar", installer.name, "--installServer"], dest, rep)
        if code != 0:
            raise InstallError(f"The Forge installer failed (exit code {code}). Read the log above for details.")
        args_name = "win_args.txt" if os.name == "nt" else "unix_args.txt"
        result = FORGE_MARKER if list(dest.glob(f"libraries/net/minecraftforge/forge/*/{args_name}")) else ""
        if not result:  # Forge 1.16 and older produce a runnable jar
            jars = [j for j in dest.glob("forge-*.jar") if "installer" not in j.name]
            if not jars:
                raise InstallError("Forge finished but produced no server files.")
            result = max(jars, key=lambda j: j.stat().st_size).name
        installer.unlink(missing_ok=True)
        (dest / "forge-installer.jar.log").unlink(missing_ok=True)
        return result


PROVIDERS = {p.name: p for p in (Vanilla(), Paper(), Purpur(), Spigot(), Fabric(), Forge())}
