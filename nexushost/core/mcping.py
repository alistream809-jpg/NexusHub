"""Minecraft Server List Ping: asks the running server itself who is online."""
import json
import socket
import struct


def _varint(n: int) -> bytes:
    out = b""
    while True:
        part = n & 0x7F
        n >>= 7
        if n:
            out += bytes([part | 0x80])
        else:
            return out + bytes([part])


def _recv(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def _read_varint(sock) -> int:
    result = 0
    for i in range(5):
        byte = _recv(sock, 1)[0]
        result |= (byte & 0x7F) << (7 * i)
        if not byte & 0x80:
            return result
    raise ValueError("varint too long")


def status(host: str, port: int, timeout: float = 2.0) -> dict:
    """Return {'online': int, 'max': int, 'version': str}. Raises OSError/ValueError on failure."""
    with socket.create_connection((host, port), timeout) as sock:
        sock.settimeout(timeout)
        host_bytes = host.encode("utf-8")
        handshake = _varint(0) + _varint(767) + _varint(len(host_bytes)) + host_bytes + struct.pack(">H", port) + _varint(1)
        sock.sendall(_varint(len(handshake)) + handshake + b"\x01\x00")
        _read_varint(sock)  # packet length
        if _read_varint(sock) != 0:
            raise ValueError("unexpected packet")
        data = _recv(sock, _read_varint(sock))
    info = json.loads(data.decode("utf-8", "replace"))
    players = info.get("players", {})
    return {
        "online": int(players.get("online", 0)),
        "max": int(players.get("max", 0)),
        "version": str(info.get("version", {}).get("name", "")),
    }
