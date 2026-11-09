from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout, QLineEdit, QListWidget, QScrollArea,
                               QSpinBox, QWidget)
from PySide6.QtCore import Qt

from ..core import whitelist
from ..core.props import Properties
from .widgets import Card, Page, button, hbox, label, show_error, show_info, vbox


class SettingsPage(Page):
    title = "Server Settings"

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

        root.addWidget(label("Server settings", "H1"))
        self.note = label("", "Muted", wrap=True)
        root.addWidget(self.note)

        # ---- gameplay
        card = Card()
        card.box.addWidget(label("Gameplay and access", "H2"))
        form = QFormLayout()
        form.setSpacing(12)
        self.max_players = QSpinBox()
        self.max_players.setRange(1, 1000)
        self.motd = QLineEdit()
        self.motd.setMaxLength(200)
        self.difficulty = QComboBox()
        self.difficulty.addItems(["peaceful", "easy", "normal", "hard"])
        self.gamemode = QComboBox()
        self.gamemode.addItems(["survival", "creative", "adventure", "spectator"])
        self.online_mode = QCheckBox("Verify players with Mojang accounts (recommended)")
        self.online_warn = label("Online mode off lets anyone join with any name, including impersonating other players. "
                                 "Only disable it for a private network or a proxy setup.", "Muted", wrap=True)
        self.online_warn.setStyleSheet("color: #f59e0b;")
        self.online_mode.toggled.connect(lambda on: self.online_warn.setVisible(not on))
        form.addRow("Maximum players", self.max_players)
        form.addRow("MOTD", self.motd)
        form.addRow("Difficulty", self.difficulty)
        form.addRow("Default gamemode", self.gamemode)
        form.addRow("Online mode", self.online_mode)
        form.addRow("", self.online_warn)
        card.box.addLayout(form)
        root.addWidget(card)

        # ---- whitelist
        wl = Card()
        wl.box.addWidget(label("Whitelist", "H2"))
        self.whitelist_on = QCheckBox("Only whitelisted players can join")
        wl.box.addWidget(self.whitelist_on)
        row = hbox(8)
        self.wl_name = QLineEdit()
        self.wl_name.setPlaceholderText("Player name")
        self.wl_name.returnPressed.connect(self._wl_add)
        add = button("Add player")
        add.clicked.connect(self._wl_add)
        rem = button("Remove selected", "danger")
        rem.clicked.connect(self._wl_remove)
        row.addWidget(self.wl_name, 1)
        row.addWidget(add)
        row.addWidget(rem)
        wl.box.addLayout(row)
        self.wl_list = QListWidget()
        self.wl_list.setFixedHeight(130)
        wl.box.addWidget(self.wl_list)
        root.addWidget(wl)

        # ---- resources + autostop
        res = Card()
        res.box.addWidget(label("Resources and automatic shutdown", "H2"))
        form2 = QFormLayout()
        form2.setSpacing(12)
        self.ram = QSpinBox()
        self.ram.setRange(512, 262144)
        self.ram.setSingleStep(256)
        self.ram.setSuffix(" MB")
        self.jvm = QLineEdit()
        self.jvm.setPlaceholderText("Optional extra Java arguments")
        self.auto_on = QCheckBox("Stop the server automatically when nobody is playing")
        self.auto_min = QSpinBox()
        self.auto_min.setRange(1, 720)
        self.auto_min.setSuffix(" minutes")
        self.auto_on.toggled.connect(self.auto_min.setEnabled)
        form2.addRow("RAM allocation", self.ram)
        form2.addRow("Java arguments", self.jvm)
        form2.addRow("Automatic shutdown", self.auto_on)
        form2.addRow("Countdown length", self.auto_min)
        res.box.addLayout(form2)
        res.box.addWidget(label("When the last player leaves, a countdown starts. If anyone joins it is cancelled. "
                                "If it reaches zero the world is saved and the server stops safely. The default is 7 minutes.",
                                "Muted", wrap=True))
        root.addWidget(res)

        actions = hbox(8)
        actions.addStretch(1)
        revert = button("Revert")
        revert.clicked.connect(self._load)
        self.save_btn = button("Save settings", "primary")
        self.save_btn.clicked.connect(self._save)
        actions.addWidget(revert)
        actions.addWidget(self.save_btn)
        root.addLayout(actions)
        root.addStretch(1)

    def bind(self, handle):
        super().bind(handle)
        self._load()

    def on_show(self):
        self._load()

    def _props(self):
        return Properties(self.handle.record.folder / "server.properties")

    def _load(self):
        has = self.handle is not None
        self.setEnabled(has)
        if not has:
            self.note.setText("Create or select a server first.")
            return
        r = self.handle.record
        p = self._props()
        self.note.setText(f"Editing {r.name}. " + ("The server is running, so most changes apply after a restart."
                                                    if self.handle.c.running else "Changes apply the next time the server starts."))
        self.max_players.setValue(p.get_int("max-players", 20))
        self.motd.setText(p.get("motd", "A Minecraft Server"))
        self.difficulty.setCurrentText(p.get("difficulty", "easy"))
        self.gamemode.setCurrentText(p.get("gamemode", "survival"))
        self.online_mode.setChecked(p.get_bool("online-mode", True))
        self.online_warn.setVisible(not self.online_mode.isChecked())
        self.whitelist_on.setChecked(p.get_bool("white-list", False))
        self.ram.setValue(r.ram_mb)
        self.jvm.setText(r.jvm_args)
        self.auto_on.setChecked(r.auto_stop_enabled)
        self.auto_min.setValue(max(1, r.auto_stop_seconds // 60))
        self.auto_min.setEnabled(r.auto_stop_enabled)
        self._wl_refresh()

    def _save(self):
        if not self.handle:
            return
        r = self.handle.record
        try:
            p = self._props()
            p.set("max-players", self.max_players.value())
            p.set("motd", self.motd.text())
            p.set("difficulty", self.difficulty.currentText())
            p.set("gamemode", self.gamemode.currentText())
            p.set("online-mode", self.online_mode.isChecked())
            p.set("white-list", self.whitelist_on.isChecked())
            p.set("enforce-whitelist", self.whitelist_on.isChecked())
            p.save()
        except OSError as exc:
            show_error(self, f"Could not write server.properties: {exc}")
            return
        self.ctx.manager.update(r.id, ram_mb=self.ram.value(), jvm_args=self.jvm.text().strip(),
                                auto_stop_enabled=self.auto_on.isChecked(), auto_stop_seconds=self.auto_min.value() * 60)
        show_info(self, "Settings saved." + (" Restart the server to apply them." if self.handle.c.running else ""))

    # ---------------------------------------------------------------- whitelist
    def _wl_refresh(self):
        self.wl_list.clear()
        if self.handle:
            self.wl_list.addItems([e["name"] for e in whitelist.read(self.handle.record.folder)])

    def _wl_add(self):
        name = self.wl_name.text().strip()
        if not name or not self.handle:
            return
        try:
            if self.handle.c.running:
                self.handle.c.send_command(f"whitelist add {name}")
                QTimer.singleShot(1500, self._wl_refresh)
            else:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    whitelist.add(self.handle.record.folder, name, self._props().get_bool("online-mode", True))
                finally:
                    QApplication.restoreOverrideCursor()
                self._wl_refresh()
            self.wl_name.clear()
        except Exception as exc:
            show_error(self, str(exc))

    def _wl_remove(self):
        item = self.wl_list.currentItem()
        if not item or not self.handle:
            return
        try:
            if self.handle.c.running:
                self.handle.c.send_command(f"whitelist remove {item.text()}")
                QTimer.singleShot(1500, self._wl_refresh)
            else:
                whitelist.remove(self.handle.record.folder, item.text())
                self._wl_refresh()
        except Exception as exc:
            show_error(self, str(exc))
