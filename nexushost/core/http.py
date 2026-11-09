"""HTTP helpers with integrity checking and friendly error messages."""
import hashlib
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import __version__

USER_AGENT = f"NexusHost/{__version__} (local Minecraft server manager)"


class NetworkError(Exception):
    pass


def _open(url: str, timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    host = urllib.parse.urlparse(url).netloc
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise NetworkError(f"{host} answered with HTTP {exc.code} for this request.") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise NetworkError(f"Could not reach {host}. Check your internet connection. ({exc})") from exc


def get_json(url: str, timeout: float = 20):
    with _open(url, timeout) as response:
        try:
            return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise NetworkError(f"Invalid response from {url}: {exc}") from exc


def download(url: str, dest, rep=None, sha1: str = None, sha256: str = None):
    """Download to dest atomically, optionally verifying a checksum."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    h1 = hashlib.sha1() if sha1 else None
    h256 = hashlib.sha256() if sha256 else None
    try:
        with _open(url, 60) as response, open(part, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                if rep:
                    rep.check()
                chunk = response.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                if h1:
                    h1.update(chunk)
                if h256:
                    h256.update(chunk)
                done += len(chunk)
                if rep:
                    rep.progress(done / total if total else None)
        if h1 and h1.hexdigest().lower() != sha1.lower():
            raise NetworkError("Downloaded file failed its SHA-1 integrity check.")
        if h256 and h256.hexdigest().lower() != sha256.lower():
            raise NetworkError("Downloaded file failed its SHA-256 integrity check.")
        os.replace(part, dest)
    except socket.timeout as exc:
        part.unlink(missing_ok=True)
        raise NetworkError("The download timed out.") from exc
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return dest
