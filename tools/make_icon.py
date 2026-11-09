"""Generates assets/nexus.png and assets/nexus.ico with no third-party libraries."""
import struct, zlib
from pathlib import Path

BG, GREEN, DARK = (13, 17, 23), (34, 197, 94), (21, 26, 33)
QUAD = [(0.28, 0.27), (0.39, 0.27), (0.72, 0.73), (0.61, 0.73)]


def inside_quad(x, y):
    sign = 0
    for i in range(4):
        (x1, y1), (x2, y2) = QUAD[i], QUAD[(i + 1) % 4]
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        s = cross > 0
        if sign == 0:
            sign = 1 if s else -1
        elif (sign == 1) != s:
            return False
    return True


def sample(x, y):
    """Colour (r,g,b,a) at normalised coordinates."""
    cx, cy, r = abs(x - 0.5), abs(y - 0.5), 0.2
    qx, qy = cx - (0.5 - r), cy - (0.5 - r)
    d = (max(qx, 0) ** 2 + max(qy, 0) ** 2) ** 0.5 + min(max(qx, qy), 0) - r  # rounded-box distance
    if d > 0:
        return (0, 0, 0, 0)
    if d > -0.05:
        return GREEN + (255,)
    if (0.28 <= x <= 0.37 or 0.63 <= x <= 0.72) and 0.27 <= y <= 0.73 or inside_quad(x, y):
        return GREEN + (255,)
    return DARK + (255,)


def render(size, ss=3):
    rows = []
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    c = sample((px + (sx + 0.5) / ss) / size, (py + (sy + 0.5) / ss) / size)
                    a = c[3]
                    acc[0] += c[0] * a; acc[1] += c[1] * a; acc[2] += c[2] * a; acc[3] += a
            n = ss * ss
            if acc[3]:
                row += bytes([round(acc[0] / acc[3]), round(acc[1] / acc[3]), round(acc[2] / acc[3]), round(acc[3] / n)])
            else:
                row += bytes(4)
        rows.append(bytes(row))
    return rows


def png(size):
    raw = b"".join(render(size))
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    out = Path(__file__).resolve().parents[1] / "assets"
    out.mkdir(exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = {s: png(s) for s in sizes}
    (out / "nexus.png").write_bytes(images[256])
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, blobs = b"", b""
    for s in sizes:
        data = images[s]
        entries += struct.pack("<BBBBHHII", 0 if s == 256 else s, 0 if s == 256 else s, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    (out / "nexus.ico").write_bytes(header + entries + blobs)
    print("wrote", out / "nexus.ico")


if __name__ == "__main__":
    main()
