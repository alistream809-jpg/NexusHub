"""Reader/writer for Minecraft server.properties that preserves comments and order."""
import re
from pathlib import Path

_UNESC = re.compile(r"\\u([0-9a-fA-F]{4})|\\(.)")
_MAP = {"n": "\n", "t": "\t", "r": "\r", "f": "\f"}


def _unescape(value: str) -> str:
    out = _UNESC.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else _MAP.get(m.group(2), m.group(2)), value)
    try:  # recombine UTF-16 surrogate pairs
        return out.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        return out


def _escape(value: str) -> str:
    value = value.replace("\\", "\\\\").replace("\r", "").replace("\n", "")
    out = []
    for ch in value:
        code = ord(ch)
        if code < 128:
            out.append(ch)
        elif code > 0xFFFF:
            code -= 0x10000
            out.append("\\u%04X\\u%04X" % (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)))
        else:
            out.append("\\u%04X" % code)
    return "".join(out)


def _split(line: str):
    stripped = line.lstrip()
    if not stripped or stripped[0] in "#!":
        return None, None
    idx = stripped.find("=")
    if idx < 0:
        return None, None
    return stripped[:idx].strip(), _unescape(stripped[idx + 1:])


class Properties:
    def __init__(self, path):
        self.path = Path(path)
        self._lines = []
        self._values = {}
        self._dirty = set()
        self.load()

    def load(self):
        self._lines, self._values, self._dirty = [], {}, set()
        if self.path.exists():
            text = self.path.read_text(encoding="utf-8", errors="replace")
            for raw in text.splitlines():
                self._lines.append(raw)
                key, value = _split(raw)
                if key is not None:
                    self._values[key] = value

    def get(self, key, default=None):
        return self._values.get(key, default)

    def get_bool(self, key, default=False):
        value = self._values.get(key)
        return default if value is None else value.strip().lower() == "true"

    def get_int(self, key, default=0):
        try:
            return int(self._values.get(key, default))
        except (TypeError, ValueError):
            return default

    def set(self, key, value):
        if isinstance(value, bool):
            value = "true" if value else "false"
        value = str(value)
        if self._values.get(key) != value:
            self._dirty.add(key)
        self._values[key] = value

    def save(self):
        written = set()
        out = []
        for raw in self._lines:
            key, _ = _split(raw)
            if key is not None and key in self._dirty:
                out.append(f"{key}={_escape(self._values[key])}")
                written.add(key)
            else:
                out.append(raw)
                if key is not None:
                    written.add(key)
        for key, value in self._values.items():
            if key not in written:
                out.append(f"{key}={_escape(value)}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
        tmp.replace(self.path)
        self._lines = out
        self._dirty.clear()
