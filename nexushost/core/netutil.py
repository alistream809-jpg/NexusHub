"""Networking helpers: local addresses, port checks, public IP and Windows Firewall."""
import ipaddress
import os
import socket

import psutil

from .http import NetworkError, _open


def local_addresses():
    """Return [(interface, ipv4)] for usable private/LAN addresses."""
    result = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family != socket.AF_INET:
                continue
            ip = ipaddress.ip_address(addr.address)
            if ip.is_loopback or ip.is_link_local:
                continue
            result.append((name, addr.address))
    return result


def primary_ip() -> str:
    """The address the OS would use to reach the internet (no packets are sent)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        addrs = local_addresses()
        return addrs[0][1] if addrs else "127.0.0.1"
    finally:
        sock.close()


def port_available(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def public_ip() -> str:
    try:
        with _open("https://api.ipify.org", 10) as response:
            value = response.read().decode("ascii", "replace").strip()
        ipaddress.ip_address(value)
        return value
    except (NetworkError, ValueError) as exc:
        raise NetworkError("Could not determine your public IP address.") from exc


def add_firewall_rule(port: int) -> bool:
    """Ask Windows (UAC prompt) to allow inbound TCP on the port. Returns True if the request was launched."""
    if os.name != "nt":
        return False
    import ctypes
    params = (f'advfirewall firewall add rule name="NEXUS HOST Minecraft {port}" '
              f'dir=in action=allow protocol=TCP localport={port}')
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", params, None, 0)
    return result > 32
