from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QHeaderView, QTableWidget, QTableWidgetItem, QWidget)

from ..core import netutil
from ..core.controller import ServerError, Status, format_duration
from ..core.props import Properties
from .tasks import TaskDialog
from .theme import STATUS_COLORS, STATUS_LABELS
from .widgets import (Card, Page, StatCard, StatusBadge, button, confirm, hbox, label, show_error, vbox)


class DashboardPage(Page):
    title = "Dashboard"

    def __init__(self, ctx):
        super().__init__(ctx)
        root = vbox((28, 24, 28, 24), 16)
        self.setLayout(root)

        # ---- empty state
        self.empty = Card()
        self.empty.box.addWidget(label("No servers yet", "H1"))
        self.empty.box.addWidget(label(
            "Create your first Minecraft Java server. It runs on this computer using its own RAM and CPU, "
            "with no hosting fees.", "Muted", wrap=True))
        first = button("Create Server", "primary")
        first.clicked.connect(lambda: ctx.navigate("create"))
        row = hbox()
        row.addWidget(first)
        row.addStretch(1)
        self.empty.box.addLayout(row)
        root.addWidget(self.empty)

        # ---- hero card
        self.hero = Card(hbox(20))
        left = vbox(spacing=6)
        self.name = label("", "H1")
        self.sub = label("", "Muted")
        status_row = hbox(6)
        self.badge = StatusBadge()
        self.detail = label("", "Muted")
        status_row.addWidget(self.badge)
        status_row.addWidget(self.detail)
        status_row.addStretch(1)
        addr_row = hbox(8)
        self.addr = label("", "Mono")
        copy = button("Copy address", "ghost")
        copy.clicked.connect(self._copy_address)
        addr_row.addWidget(label("Address", "Muted"))
        addr_row.addWidget(self.addr)
        addr_row.addWidget(copy)
        addr_row.addStretch(1)
        left.addWidget(self.name)
        left.addWidget(self.sub)
        left.addLayout(status_row)
        left.addLayout(addr_row)
        self.hero.box.addLayout(left, 1)

        controls = vbox(spacing=8)
        top = hbox(8)
        self.start_btn = button("Start", "primary")
        self.stop_btn = button("Stop", "danger")
        self.restart_btn = button("Restart")
        top.addWidget(self.start_btn)
        top.addWidget(self.stop_btn)
        top.addWidget(self.restart_btn)
        bottom = hbox(8)
        self.kill_btn = button("Force kill", "ghost", "Immediately terminate the server process (the world may lose recent changes)")
        new_btn = button("Create Server", "ghost")
        new_btn.clicked.connect(lambda: ctx.navigate("create"))
        bottom.addStretch(1)
        bottom.addWidget(self.kill_btn)
        bottom.addWidget(new_btn)
        controls.addLayout(top)
        controls.addLayout(bottom)
        self.hero.box.addLayout(controls)
        root.addWidget(self.hero)

        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(lambda: self._run(self.handle.c.stop))
        self.restart_btn.clicked.connect(lambda: self._run(self.handle.c.restart))
        self.kill_btn.clicked.connect(self._kill)

        # ---- stats
        grid = QGridLayout()
        grid.setSpacing(14)
        self.players = StatCard("Online players")
        self.ram = StatCard("RAM usage", with_bar=True)
        self.uptime = StatCard("Uptime")
        self.auto = StatCard("Automatic shutdown")
        for i, card in enumerate((self.players, self.ram, self.uptime, self.auto)):
            grid.addWidget(card, 0, i)
            grid.setColumnStretch(i, 1)
        self.stats_widget = QWidget()
        self.stats_widget.setLayout(grid)
        root.addWidget(self.stats_widget)

        # ---- server list
        list_head = hbox()
        list_head.addWidget(label("Your servers", "H2"))
        list_head.addStretch(1)
        self.delete_btn = button("Delete server", "danger")
        self.delete_btn.clicked.connect(self._delete)
        list_head.addWidget(self.delete_btn)
        root.addLayout(list_head)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Name", "Software", "Version", "Port", "RAM", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._table_selected)
        root.addWidget(self.table, 1)

        ctx.servers_changed.connect(self._fill_table)
        ctx.status_any.connect(lambda *_: self._fill_table())
        self._fill_table()

    # ------------------------------------------------------------------ binding
    def bind(self, handle):
        old = self.handle
        if old is not None:
            for sig, slot in ((old.status_changed, self._status), (old.players_changed, self._players),
                              (old.stats, self._stats), (old.countdown, self._countdown)):
                try:
                    sig.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        super().bind(handle)
        has = handle is not None
        self.empty.setVisible(not has)
        self.hero.setVisible(has)
        self.stats_widget.setVisible(has)
        if not has:
            return
        handle.status_changed.connect(self._status)
        handle.players_changed.connect(self._players)
        handle.stats.connect(self._stats)
        handle.countdown.connect(self._countdown)
        r = handle.record
        self.name.setText(r.name)
        self.sub.setText(f"{r.type} {r.mc_version}   |   {r.ram_mb} MB RAM allocated   |   Port {r.port}")
        self.addr.setText(f"{netutil.primary_ip()}:{r.port}")
        self._status(handle.status)
        self._players(sorted(handle.c.player_names), handle.c.player_count, handle.c.max_players)
        import time
        self._stats(handle.c.ram_bytes, (time.time() - handle.c.started_at) if handle.c.running and handle.c.started_at else 0.0)
        self._countdown(handle.c.countdown_remaining if handle.status == Status.ONLINE else -1.0)
        self._select_row(r.id)

    def on_show(self):
        if self.handle:
            self.bind(self.handle)

    # ------------------------------------------------------------------ slots
    def _status(self, status: str):
        self.badge.set_status(status)
        details = {
            Status.STOPPED: "The server process is not running.",
            Status.STARTING: "Launching. It is only marked online when the server reports it is ready.",
            Status.ONLINE: "Accepting connections.",
            Status.STOPPING: "Saving the world and shutting down.",
            Status.CRASHED: "Stopped unexpectedly. Check the Console for details.",
        }
        self.detail.setText(details.get(status, ""))
        idle = status in (Status.STOPPED, Status.CRASHED)
        self.start_btn.setEnabled(idle)
        self.stop_btn.setEnabled(status in (Status.STARTING, Status.ONLINE))
        self.restart_btn.setEnabled(status == Status.ONLINE)
        self.kill_btn.setEnabled(status in (Status.STARTING, Status.STOPPING, Status.ONLINE))
        self.delete_btn.setEnabled(True)
        if status in (Status.STOPPED, Status.CRASHED):
            self._players([], 0, 0)
            self._stats(0, 0.0)
        self._countdown(-1.0 if status != Status.ONLINE else self.handle.c.countdown_remaining)

    def _max_players(self) -> int:
        live = self.handle.c.max_players
        if live:
            return live
        return Properties(self.handle.record.folder / "server.properties").get_int("max-players", 20)

    def _players(self, names, count, max_players):
        if self.handle.status != Status.ONLINE:
            self.players.set("0", "Server is offline")
            return
        shown = ", ".join(names[:3]) + (" ..." if len(names) > 3 else "")
        self.players.set(f"{count} / {max_players or self._max_players()}", shown or "Nobody is playing")

    def _stats(self, ram_bytes: int, uptime: float):
        allocated = max(1, self.handle.record.ram_mb)
        used_mb = ram_bytes / (1024 * 1024)
        self.ram.set(f"{used_mb:,.0f} MB", f"of {allocated:,} MB allocated", used_mb / allocated * 100)
        h, rem = divmod(int(uptime), 3600)
        m, s = divmod(rem, 60)
        self.uptime.set(f"{h}:{m:02d}:{s:02d}" if uptime else "-", "Since the process started" if uptime else "Server is offline")

    def _countdown(self, seconds: float):
        r = self.handle.record
        if not r.auto_stop_enabled:
            self.auto.set("Disabled", "The server stays on until you stop it")
        elif seconds >= 0 and self.handle.status == Status.ONLINE:
            self.auto.set(format_duration(seconds), "until the idle server is stopped")
        elif self.handle.status == Status.ONLINE:
            self.auto.set("Armed", "Counts down when the last player leaves")
        else:
            self.auto.set("Standby", f"Stops after {r.auto_stop_seconds // 60} min without players")

    # ------------------------------------------------------------------ actions
    def _run(self, fn):
        try:
            fn()
        except ServerError as exc:
            show_error(self, str(exc))

    def _start(self):
        h = self.handle
        major = h.record.java_major
        mgr = self.ctx.manager.javamgr
        if mgr.find(major) is None:
            if not confirm(self, f"This server needs Java {major}, which is not installed.\n\n"
                                 "Download it now from Eclipse Adoptium? It is free and stays inside NEXUS HOST.",
                           "Java required"):
                return
            _, error = TaskDialog(self, f"Installing Java {major}", lambda rep: mgr.ensure(major, rep=rep)).run()
            if error:
                if error != "Cancelled.":
                    show_error(self, error)
                return
        self._run(h.c.start)

    def _kill(self):
        if confirm(self, "Force killing can lose recent world changes. Continue?", "Force kill"):
            self.handle.c.kill()

    def _copy_address(self):
        QGuiApplication.clipboard().setText(self.addr.text())

    def _delete(self):
        h = self.handle
        if h is None:
            return
        if h.c.running:
            show_error(self, "Stop the server before deleting it.")
            return
        if confirm(self, f"Delete '{h.record.name}' and ALL of its files, including the world?\nThis cannot be undone.", "Delete server"):
            try:
                self.ctx.remove(h.id)
            except ServerError as exc:
                show_error(self, str(exc))

    # ------------------------------------------------------------------ table
    def _fill_table(self):
        self.table.blockSignals(True)
        handles = list(self.ctx.handles.values())
        self.table.setRowCount(len(handles))
        for row, h in enumerate(handles):
            r = h.record
            values = [r.name, r.type, r.mc_version, str(r.port), f"{r.ram_mb} MB", STATUS_LABELS[h.status]]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, r.id)
                if col == 5:
                    from PySide6.QtGui import QColor
                    item.setForeground(QColor(STATUS_COLORS[h.status]))
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        if self.ctx.selected:
            self._select_row(self.ctx.selected.id)

    def _select_row(self, server_id):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == server_id:
                self.table.selectRow(row)
        self.table.blockSignals(False)

    def _table_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            sid = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            if not self.ctx.selected or self.ctx.selected.id != sid:
                self.ctx.select(sid)
