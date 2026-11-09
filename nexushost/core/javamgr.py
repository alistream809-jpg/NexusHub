"""Finds Java runtimes on the machine and downloads managed ones when needed."""
import os
import re
import shutil
import subprocess
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .http import download
from .reporter import Reporter

NOWINDOW = 0x08000000 if os.name == "nt" else 0
EXE = "java.exe" if os.name == "nt" else "java"
JAVAC = "javac.exe" if os.name == "nt" else "javac"


class JavaError(Exception):
    pass


@dataclass
class JavaInstall:
    path: str
    major: int
    version: str
    is_jdk: bool
    managed: bool = False

    def label(self) -> str:
        kind = "JDK" if self.is_jdk else "JRE"
        return f"Java {self.major} {kind} ({self.version})"


def probe(path: str, managed: bool = False):
    """Run `java -version` and parse the result. Returns None when the path is not a working Java."""
    try:
        result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=20, creationflags=NOWINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'version "([^"]+)"', (result.stderr or "") + (result.stdout or ""))
    if not match:
        return None
    version = match.group(1)
    parts = re.split(r"[._\-+]", version)
    try:
        major = int(parts[1]) if parts[0] == "1" and len(parts) > 1 else int(parts[0])
    except ValueError:
        return None
    is_jdk = (Path(path).parent / JAVAC).exists()
    return JavaInstall(str(path), major, version, is_jdk, managed)


def acceptable(install: JavaInstall, required: int) -> bool:
    """Java 8 style servers need exactly that major; 16+ servers run on any newer Java."""
    return install.major >= required if required >= 16 else install.major == required


class JavaManager:
    def __init__(self, runtimes_dir, custom_path_getter=None):
        self.runtimes = Path(runtimes_dir)
        self._custom = custom_path_getter or (lambda: "")
        self._cache = None
        self._lock = threading.RLock()

    def _candidates(self):
        seen, found = set(), []

        def add(p, managed=False):
            p = Path(p)
            if p.is_file():
                key = str(p.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    found.append((str(p), managed))

        if self.runtimes.is_dir():
            for child in self.runtimes.iterdir():
                add(child / "bin" / EXE, managed=True)
        custom = (self._custom() or "").strip()
        if custom:
            add(custom)
        if os.environ.get("JAVA_HOME"):
            add(Path(os.environ["JAVA_HOME"]) / "bin" / EXE)
        which = shutil.which("java")
        if which:
            add(which)
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if not base:
                continue
            for sub in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu", "Amazon Corretto", "BellSoft", "Semeru", "AdoptOpenJDK"):
                root = Path(base) / sub
                if root.is_dir():
                    for child in root.iterdir():
                        add(child / "bin" / EXE)
        appdata = os.environ.get("APPDATA")
        if appdata:  # runtimes bundled with the official Minecraft launcher
            mc_runtime = Path(appdata) / ".minecraft" / "runtime"
            if mc_runtime.is_dir():
                for exe in mc_runtime.glob(f"*/*/*/bin/{EXE}"):
                    add(exe)
        if os.name != "nt":
            for exe in Path("/usr/lib/jvm").glob(f"*/bin/{EXE}"):
                add(exe)
        return found

    def scan(self, force: bool = False):
        with self._lock:
            if self._cache is None or force:
                installs = []
                for path, managed in self._candidates():
                    info = probe(path, managed)
                    if info:
                        installs.append(info)
                self._cache = installs
            return list(self._cache)

    def find(self, required: int, need_jdk: bool = False):
        options = [i for i in self.scan() if acceptable(i, required) and (i.is_jdk or not need_jdk)]
        if not options:
            return None
        options.sort(key=lambda i: (i.major - required, not i.managed))
        return options[0]

    def ensure(self, required: int, need_jdk: bool = False, rep: Reporter = None) -> JavaInstall:
        """Return a suitable Java, downloading an Eclipse Temurin build if none is installed."""
        rep = rep or Reporter()
        found = self.find(required, need_jdk)
        if found:
            return found
        if os.name != "nt":
            raise JavaError(f"Java {required} was not found. Install it and try again.")
        kind = "jdk" if need_jdk else "jre"
        url = f"https://api.adoptium.net/v3/binary/latest/{required}/ga/windows/x64/{kind}/hotspot/normal/eclipse"
        archive = self.runtimes / f"download-{kind}-{required}.zip"
        rep.status(f"Downloading Java {required} ({kind.upper()}) from Eclipse Adoptium")
        download(url, archive, rep)
        rep.status("Extracting Java")
        rep.progress(None)
        target = self.runtimes / f"{kind}-{required}"
        staging = self.runtimes / f"_staging-{kind}-{required}"
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(target, ignore_errors=True)
        try:
            with zipfile.ZipFile(archive) as z:
                z.extractall(staging)
            roots = [p for p in staging.iterdir() if p.is_dir()]
            shutil.move(str(roots[0] if len(roots) == 1 else staging), str(target))
        except (zipfile.BadZipFile, OSError, IndexError) as exc:
            raise JavaError(f"Could not unpack the downloaded Java: {exc}") from exc
        finally:
            archive.unlink(missing_ok=True)
            shutil.rmtree(staging, ignore_errors=True)
        info = probe(str(target / "bin" / EXE), managed=True)
        if not info:
            raise JavaError("The downloaded Java does not run on this computer.")
        self.scan(force=True)
        return info
