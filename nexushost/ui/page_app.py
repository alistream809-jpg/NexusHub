from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHeaderView, QLineEdit,
                               QTableWidget, QTableWidgetItem)

from .. import __version__
from ..core.paths import data_dir
from .tasks import TaskDialog
from .widgets import Card, Page, button, hbox, label, show_error, show_info, vbox


class AppPage(Page):
    title = "Application"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.db = ctx.manager.db
        self.java = ctx.manager.javamgr
        root = vbox((28, 24, 28, 24), 16)
        self.setLayout(root)
        root.addWidget(label("Application", "H1"))

        jc = Card()
        jc.box.addWidget(label("Java runtimes", "H2"))
        jc.box.addWidget(label("Each Minecraft version needs a specific Java version. NEXUS HOST uses what is installed and can "
                               "download free Eclipse Temurin builds into its own folder.", "Muted", wrap=True))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Runtime", "Location", "Source"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setFixedHeight(170)
        jc.box.addWidget(self.table)
        row = hbox(8)
        self.major = QComboBox()
        self.major.addItems(["8", "17", "21", "25"])
        self.major.setCurrentText("21")
        dl = button("Download Java", "primary")
        dl.clicked.connect(self._download)
        rescan = button("Rescan")
        rescan.clicked.connect(self._rescan)
        row.addWidget(label("Version", "Muted"))
        row.addWidget(self.major)
        row.addWidget(dl)
        row.addWidget(rescan)
        row.addStretch(1)
        jc.box.addLayout(row)
        row2 = hbox(8)
        self.custom = QLineEdit(self.db.get_setting("custom_java", ""))
        self.custom.setPlaceholderText("Optional: path to a specific java.exe")
        browse = button("Browse")
        browse.clicked.connect(self._browse)
        save = button("Apply")
        save.clicked.connect(self._save_custom)
        row2.addWidget(self.custom, 1)
        row2.addWidget(browse)
        row2.addWidget(save)
        jc.box.addLayout(row2)
        root.addWidget(jc)

        pc = Card()
        pc.box.addWidget(label("Preferences and storage", "H2"))
        self.on_start = QCheckBox("Also start the shutdown countdown when a server comes online and nobody joins")
        self.on_start.setChecked(self.db.get_setting("autostop_on_start", "1") == "1")
        self.on_start.toggled.connect(lambda v: self.db.set_setting("autostop_on_start", "1" if v else "0"))
        pc.box.addWidget(self.on_start)
        self.folder = label("", "Mono")
        pc.box.addWidget(label("New servers are stored in:", "Muted"))
        pc.box.addWidget(self.folder)
        frow = hbox(8)
        choose = button("Change folder")
        choose.clicked.connect(self._choose_folder)
        open_data = button("Open data folder")
        open_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        frow.addWidget(choose)
        frow.addWidget(open_data)
        frow.addStretch(1)
        pc.box.addLayout(frow)
        root.addWidget(pc)

        about = Card()
        about.box.addWidget(label("About", "H2"))
        about.box.addWidget(label(f"NEXUS HOST {__version__}. Free local hosting for Minecraft Java Edition. "
                                  "Not affiliated with Mojang or Microsoft.", "Muted", wrap=True))
        root.addWidget(about)
        root.addStretch(1)

    def on_show(self):
        self.folder.setText(str(self.ctx.manager.servers_dir))
        if not self.table.rowCount():
            self._rescan()

    def _rescan(self):
        TaskDialog(self, "Scanning for Java", lambda rep: self.java.scan(force=True)).run()
        self._fill()

    def _fill(self):
        installs = self.java.scan()
        self.table.setRowCount(len(installs))
        for i, j in enumerate(installs):
            for col, text in enumerate((j.label(), j.path, "Managed by NEXUS HOST" if j.managed else "Installed")):
                self.table.setItem(i, col, QTableWidgetItem(text))

    def _download(self):
        major = int(self.major.currentText())
        _, error = TaskDialog(self, f"Installing Java {major}", lambda rep: self.java.ensure(major, rep=rep)).run()
        if error and error != "Cancelled.":
            show_error(self, error)
        self._fill()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select java.exe", "", "Java (java.exe);;All files (*)")
        if path:
            self.custom.setText(path)

    def _save_custom(self):
        self.db.set_setting("custom_java", self.custom.text().strip())
        self._rescan()
        show_info(self, "Java path saved.")

    def _choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose where new servers are stored", str(self.ctx.manager.servers_dir))
        if path:
            self.db.set_setting("servers_dir", path)
            self.folder.setText(path)
