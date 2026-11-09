"""A stand-in Minecraft server for tests: real stdout format, stdin commands and Server List Ping."""
import json, socket, sys, threading, time
from pathlib import Path

port = 25565
props = Path("server.properties")
if props.exists():
    for line in props.read_text().splitlines():
        if line.startswith("server-port="):
            port = int(line.split("=", 1)[1])

players = set()

def log(msg, level="INFO"):
    print(f"[{time.strftime('%H:%M:%S')} {level}]: {msg}", flush=True)

def varint(n):
    out = b""
    while True:
        p = n & 0x7F; n >>= 7
        if n: out += bytes([p | 0x80])
        else: return out + bytes([p])

def read_varint(c):
    r = 0
    for i in range(5):
        b = c.recv(1)[0]; r |= (b & 0x7F) << (7 * i)
        if not b & 0x80: return r

def serve(srv):
    while True:
        c, _ = srv.accept()
        try:
            read_varint(c)
            c.recv(1)  # packet id ... consume handshake body loosely
            c.settimeout(0.3)
            try: c.recv(4096)
            except OSError: pass
            body = json.dumps({"version": {"name": "fake", "protocol": 767},
                               "players": {"max": 20, "online": len(players)}}).encode()
            pkt = varint(0) + varint(len(body)) + body
            c.sendall(varint(len(pkt)) + pkt)
        except Exception:
            pass
        finally:
            c.close()

log("Starting minecraft server version fake")
time.sleep(0.8)
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", port)); srv.listen(5)
threading.Thread(target=serve, args=(srv,), daemon=True).start()
log('Done (0.8s)! For help, type "help"')

for raw in sys.stdin:
    cmd = raw.strip()
    if cmd == "stop":
        log("Stopping the server"); time.sleep(0.3); sys.exit(0)
    elif cmd == "save-all flush":
        time.sleep(0.2); log("Saved the game")
    elif cmd.startswith("fakejoin "):
        n = cmd.split()[1]; players.add(n); log(f"{n} joined the game")
    elif cmd.startswith("fakeleave "):
        n = cmd.split()[1]; players.discard(n); log(f"{n} left the game")
    elif cmd == "crash":
        log("Encountered an unexpected exception", "ERROR"); sys.exit(1)
    elif cmd == "hang":
        time.sleep(3600)
    else:
        log(f"Unknown command: {cmd}")
