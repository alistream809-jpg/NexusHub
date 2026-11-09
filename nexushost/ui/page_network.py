from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHeaderView, QScrollArea, QSpinBox, QTableWidget,
                               QTableWidgetItem, QWidget)

from ..core import mcping, netutil
from ..core.http import NetworkError
from ..core.props import Properties
from .widgets import Card, Page, button, hbox, label, show_error, show_info, vbox

GUIDE = """<b>Same Wi-Fi or network.</b> Friends on your home network join with the local address shown above, for example 192.168.1.20:25565.<br><br>
<b>Friends elsewhere on the internet.</b> There are two free approaches:<br>
<b>1. Port forwarding.</b> Open your router's admin page (often 192.168.0.1 or 192.168.1.1), find Port Forwarding, and forward TCP port <b>{port}</b> to this computer's local address. Then give friends your public IP address and the port. Allow the port through Windows Firewall with the button above. Some internet providers use CGNAT, which blocks port forwarding. If your public IP does not match the one shown in your router, use option 2.<br><br>
<b>2. A free tunnel or virtual LAN.</b> Programs such as Playit.gg, ZeroTier, Tailscale or Radmin VPN let friends connect without touching your router. Install the tool, follow its instructions to expose or share TCP port <b>{port}</b>, and give friends the address it provides.<br><br>
Only share your public IP with people you trust. Keep the whitelist enabled for private servers."""


class NetworkPage(Page):
    title = "Networking"

    def __init__(self, ctx):
        super().__init__(ctx)
        outer = vbox()
        self.setLayout(outer)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        inner = QWidget()
        scroll.setWidget(inner)
        root = vbox((28, 24, 28, 24), 16)
        inner.setLayout(root)
        root.addWidget(label("Networking", "H1"))
        self.note = label("", "Muted", wrap=True)
        root.addWidget(self.note)

        addr = Card()
        addr.box.addWidget(label("Your local addresses", "H2"))
        self.primary = label("", "Accent")
        copy = button("Copy", "ghost")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.primary.text()))
        row = hbox(8)
        row.addWidget(label("Main address for friends on your network:", "Muted"))
        row.addWidget(self.primary)
        row.addWidget(copy)
        row.addStretch(1)
        addr.box.addLayout(row)
        self.local = label("", "Mono")
        addr.box.addWidget(self.local)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Network adapter", "IPv4 address"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setFixedHeight(150)
        addr.box.addWidget(self.table)
        root.addWidget(addr)

        port = Card()
        port.box.addWidget(label("Port", "H2"))
        prow = hbox(8)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setMinimumWidth(110)
        self.save_port = button("Save port", "primary")
        self.check_port = button("Check if free")
        self.test = button("Test server")
        self.firewall = button("Allow in Windows Firewall")
        for w in (self.port, self.save_port, self.check_port, self.test, self.firewall):
            prow.addWidget(w)
        prow.addStretch(1)
        port.box.addLayout(prow)
        self.port_result = label("", "Muted", wrap=True)
        port.box.addWidget(self.port_result)
        root.addWidget(port)

        pub = Card()
        pub.box.addWidget(label("Public address", "H2"))
        prow2 = hbox(8)
        self.detect = button("Detect public IP")
        self.public = label("Not checked", "Mono")
        prow2.addWidget(self.detect)
        prow2.addWidget(self.public)
        prow2.addStretch(1)
        pub.box.addLayout(prow2)
        root.addWidget(pub)

        guide = Card()
        guide.box.addWidget(label("How friends can connect", "H2"))
        self.guide = label("", wrap=True)
        self.guide.setTextFormat(Qt.TextFormat.RichText)
        guide.box.addWidget(self.guide)
        root.addWidget(guide)
        root.addStretch(1)

        self.save_port.clicked.connect(self._save_port)
        self.check_port.clicked.connect(self._check_port)
        self.test.clicked.connect(self._test)
        self.firewall.clicked.connect(self._firewall)
        self.detect.clicked.connect(self._detect)

    def bind(self, handle):
        super().bind(handle)
        self._load()

    def on_show(self):
        self._load()

    def _load(self):
        ip = netutil.primary_ip()
        addrs = netutil.local_addresses()
        self.table.setRowCount(len(addrs))
        for i, (name, address) in enumerate(addrs):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(address))
        has = self.handle is not None
        for w in (self.port, self.save_port, self.check_port, self.test, self.firewall):
            w.setEnabled(has)
        port = self.handle.record.port if has else 25565
        self.port.setValue(port)
        self.primary.setText(f"{ip}:{port}")
        self.local.setText(f"On this computer: localhost:{port}")
        self.guide.setText(GUIDE.format(port=port))
        self.port_result.setText("")
        running = has and self.handle.c.running
        self.save_port.setEnabled(has and not running)
        self.note.setText("Select a server to configure its port." if not has else
                          "Stop the server to change its port." if running else
                          f"Settings for {self.handle.record.name}.")

    def _save_port(self):
        r = self.handle.record
        new = self.port.value()
        for other in self.ctx.handles.values():
            if other.id != r.id and other.record.port == new:
                show_error(self, f"Port {new} is already used by '{other.record.name}'.")
                return
        if new != r.port and not netutil.port_available(new):
            show_error(self, f"Port {new} is already in use by another program on this computer.")
            return
        try:
            p = Properties(r.folder / "server.properties")
            p.set("server-port", new)
            p.save()
        except OSError as exc:
            show_error(self, f"Could not write server.properties: {exc}")
            return
        self.ctx.manager.update(r.id, port=new)
        self._load()
        self.port_result.setText(f"Port saved: {new}")

    def _check_port(self):
        port = self.port.value()
        if self.handle and self.handle.c.running and port == self.handle.record.port:
            self.port_result.setText(f"Port {port} is in use by this running server, as expected.")
        elif netutil.port_available(port):
            self.port_result.setText(f"Port {port} is free on this computer.")
        else:
            self.port_result.setText(f"Port {port} is already used by another program.")

    def _test(self):
        port = self.handle.record.port
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            info = mcping.status("127.0.0.1", port)
            self.port_result.setText(f"The server answered on port {port}: {info['online']} of {info['max']} players, version {info['version']}.")
        except (OSError, ValueError):
            self.port_result.setText(f"Nothing answered on port {port}. The server is not running or is still starting.")
        finally:
            QApplication.restoreOverrideCursor()

    def _firewall(self):
        port = self.handle.record.port
        if netutil.add_firewall_rule(port):
            show_info(self, "Windows will ask for administrator permission to add the rule. Approve the prompt to continue.")
        else:
            show_error(self, "The firewall request could not be started. This feature only works on Windows.")

    def _detect(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ip = netutil.public_ip()
            port = self.handle.record.port if self.handle else 25565
            self.public.setText(f"{ip}:{port}")
        except NetworkError as exc:
            show_error(self, str(exc))
        finally:
            QApplication.restoreOverrideCursor()
