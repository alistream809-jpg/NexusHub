import shutil
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import QAbstractItemView, QFileDialog, QHeaderView, QTableWidget, QTableWidgetItem

from ..core.providers import PROVIDERS
from .widgets import Card, Page, button, confirm, hbox, label, show_error, show_info, vbox


def open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class PluginsPage(Page):
    title = "Plugins and Mods"

    def __init__(self, ctx):
        super().__init__(ctx)
        root = vbox((28, 24, 28, 24), 14)
        self.setLayout(root)
        self.heading = label("Plugins and mods", "H1")
        self.note = label("", "Muted", wrap=True)
        root.addWidget(self.heading)
        root.addWidget(self.note)

        self.tools = hbox(8)
        self.install_btn = button("Install", "primary")
        self.remove_btn = button("Remove", "danger")
        self.toggle_btn = button("Enable or disable")
        self.refresh_btn = button("Refresh", "ghost")
        for b in (self.install_btn, self.remove_btn, self.toggle_btn, self.refresh_btn):
            self.tools.addWidget(b)
        self.tools.addStretch(1)
        root.addLayout(self.tools)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File", "Size", "State"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        folders = Card()
        folders.box.addWidget(label("Open folders", "H2"))
        row = hbox(8)
        self.open_content = button("Plugins or mods folder")
        self.open_server = button("Server folder")
        self.open_world = button("World folder")
        self.open_logs = button("Logs folder")
        for b in (self.open_content, self.open_server, self.open_world, self.open_logs):
            row.addWidget(b)
        row.addStretch(1)
        folders.box.addLayout(row)
        root.addWidget(folders)

        self.install_btn.clicked.connect(self._install)
        self.remove_btn.clicked.connect(self._remove)
        self.toggle_btn.clicked.connect(self._toggle)
        self.refresh_btn.clicked.connect(self._refresh)
        self.open_content.clicked.connect(lambda: self.handle and self._content_dir() and open_folder(self._content_dir()))
        self.open_server.clicked.connect(lambda: self.handle and open_folder(self.handle.record.folder))
        self.open_world.clicked.connect(self._open_world)
        self.open_logs.clicked.connect(lambda: self.handle and open_folder(self.handle.record.folder / "logs"))

    def bind(self, handle):
        super().bind(handle)
        self._refresh()

    def on_show(self):
        self._refresh()

    def _provider(self):
        return PROVIDERS[self.handle.record.type] if self.handle else None

    def _content_dir(self):
        provider = self._provider()
        if not provider or not provider.content_folder:
            return None
        return self.handle.record.folder / provider.content_folder

    def _refresh(self):
        self.table.setRowCount(0)
        has = self.handle is not None
        for b in (self.open_server, self.open_world, self.open_logs):
            b.setEnabled(has)
        folder = self._content_dir()
        supported = folder is not None
        for b in (self.install_btn, self.remove_btn, self.toggle_btn, self.refresh_btn, self.open_content):
            b.setEnabled(supported)
        if not has:
            self.heading.setText("Plugins and mods")
            self.note.setText("Create or select a server first.")
            return
        provider = self._provider()
        if not supported:
            self.heading.setText("Plugins and mods")
            self.note.setText("Vanilla servers cannot load plugins or mods. Create a Paper, Purpur or Spigot server for "
                              "plugins, or a Fabric or Forge server for mods.")
            return
        kind = provider.content_label
        self.heading.setText(kind.capitalize())
        running = " The server is running, so restart it to apply any change." if self.handle.c.running else ""
        self.note.setText(f"Jar files in {folder}. Disabled files are renamed with a .disabled suffix and are not loaded.{running}")
        folder.mkdir(parents=True, exist_ok=True)
        files = sorted(p for p in folder.iterdir() if p.is_file() and (p.suffix == ".jar" or p.name.endswith(".jar.disabled")))
        self.table.setRowCount(len(files))
        for row, path in enumerate(files):
            disabled = path.name.endswith(".disabled")
            size = path.stat().st_size
            state = QTableWidgetItem("Disabled" if disabled else "Enabled")
            state.setForeground(QColor("#8b949e" if disabled else "#22c55e"))
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{size / 1024:,.0f} KB" if size < 1_048_576 else f"{size / 1_048_576:,.1f} MB"))
            self.table.setItem(row, 2, state)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, str(path))

    def _selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [Path(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)) for r in rows]

    def _install(self):
        folder = self._content_dir()
        names, _ = QFileDialog.getOpenFileNames(self, "Select jar files to install", "", "Java archives (*.jar)")
        if not names:
            return
        installed, problems = 0, []
        for name in names:
            src = Path(name)
            if not zipfile.is_zipfile(src):
                problems.append(f"{src.name} is not a valid jar file.")
                continue
            target = folder / src.name
            if target.exists() and not confirm(self, f"{src.name} is already installed. Replace it?"):
                continue
            try:
                shutil.copy2(src, target)
                (folder / (src.name + ".disabled")).unlink(missing_ok=True)
                installed += 1
            except OSError as exc:
                problems.append(f"{src.name}: {exc}")
        self._refresh()
        if problems:
            show_error(self, "\n".join(problems))
        if installed:
            show_info(self, f"Installed {installed} file(s). Restart the server to load them.")

    def _remove(self):
        files = self._selected()
        if not files:
            show_info(self, "Select one or more files first.")
            return
        if not confirm(self, f"Permanently delete {len(files)} file(s)?", "Remove"):
            return
        for path in files:
            try:
                path.unlink()
            except OSError as exc:
                show_error(self, f"Could not delete {path.name}: {exc}")
        self._refresh()

    def _toggle(self):
        files = self._selected()
        if not files:
            show_info(self, "Select one or more files first.")
            return
        for path in files:
            try:
                if path.name.endswith(".disabled"):
                    path.rename(path.with_name(path.name[: -len(".disabled")]))
                else:
                    path.rename(path.with_name(path.name + ".disabled"))
            except OSError as exc:
                show_error(self, f"Could not rename {path.name}: {exc}")
        self._refresh()

    def _open_world(self):
        if not self.handle:
            return
        from ..core.props import Properties
        name = Properties(self.handle.record.folder / "server.properties").get("level-name", "world")
        open_folder(self.handle.record.folder / name)
