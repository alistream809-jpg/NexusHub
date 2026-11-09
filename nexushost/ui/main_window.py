
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout, QMainWindow, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..core.paths import resource_path
from .bridge import AppContext
from .page_app import AppPage
from .page_console import ConsolePage
from .page_create import CreatePage
from .page_dashboard import DashboardPage
from .page_network import NetworkPage
from .page_plugins import PluginsPage
from .page_settings import SettingsPage
from .widgets import FadeStack, StatusBadge, label

PAGES = [
    ("dashboard", "Dashboard", DashboardPage),
    ("create", "Create Server", CreatePage),
    ("console", "Console", ConsolePage),
    ("plugins", "Plugins and Mods", PluginsPage),
    ("settings", "Server Settings", SettingsPage),
    ("network", "Networking", NetworkPage),
    ("app", "Application", AppPage),
]


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        ctx.navigate = self.navigate
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.setMinimumSize(1060, 680)
        icon = resource_path("assets/nexus.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---------------- sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(236)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(0, 24, 0, 18)
        side.setSpacing(0)
        logo = QHBoxLayout()
        logo.setContentsMargins(22, 0, 22, 22)
        mark = label("NEXUS", "Logo")
        accent = label("HOST", "Logo")
        accent.setStyleSheet("color: #22c55e;")
        logo.addWidget(mark)
        logo.addSpacing(6)
        logo.addWidget(accent)
        logo.addStretch(1)
        side.addLayout(logo)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        self.pages = {}
        self.index = {}
        self.stack = FadeStack()
        for i, (key, title, cls) in enumerate(PAGES):
            btn = QPushButton(title)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.navigate(k))
            self.group.addButton(btn)
            side.addWidget(btn)
            self.buttons[key] = btn
            page = cls(ctx)
            self.pages[key] = page
            self.index[key] = i
            self.stack.addWidget(page)
        side.addStretch(1)
        side.addWidget(label(f"Version {__version__}", "Muted"), 0, Qt.AlignmentFlag.AlignHCenter)

        self.indicator = QFrame(self.sidebar)
        self.indicator.setStyleSheet("background: #22c55e; border-radius: 1px;")
        self.indicator.setGeometry(0, 0, 3, 0)
        self.indicator_anim = QPropertyAnimation(self.indicator, b"geometry", self)
        self.indicator_anim.setDuration(260)
        self.indicator_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        layout.addWidget(self.sidebar)

        # ---------------- main area
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(68)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(28, 0, 28, 0)
        self.page_title = label("Dashboard", "PageTitle")
        hl.addWidget(self.page_title)
        hl.addStretch(1)
        hl.addWidget(label("Server", "Muted"))
        self.selector = QComboBox()
        self.selector.setMinimumWidth(220)
        self.selector.activated.connect(self._selector_chosen)
        hl.addWidget(self.selector)
        self.header_status = StatusBadge()
        hl.addWidget(self.header_status)
        main.addWidget(header)
        main.addWidget(self.stack, 1)
        layout.addLayout(main, 1)

        ctx.servers_changed.connect(self._fill_selector)
        ctx.selected_changed.connect(self._selected)
        ctx.status_any.connect(self._any_status)

        self._fill_selector()
        self._selected(ctx.selected)
        self.stack.setCurrentIndex(0)
        self.buttons["dashboard"].setChecked(True)
        QTimer.singleShot(0, self._place_indicator)

    # ------------------------------------------------------------------ navigation
    def navigate(self, key: str):
        self.buttons[key].setChecked(True)
        self.page_title.setText(dict((k, t) for k, t, _ in PAGES)[key])
        self.stack.fade_to(self.index[key])
        self.pages[key].on_show()
        self._place_indicator(animated=True)

    def _place_indicator(self, animated=False):
        btn = next((b for b in self.buttons.values() if b.isChecked()), None)
        if btn is None:
            return
        target = QRect(0, btn.y(), 3, btn.height())
        if animated and self.indicator.height() > 0:
            self.indicator_anim.stop()
            self.indicator_anim.setStartValue(self.indicator.geometry())
            self.indicator_anim.setEndValue(target)
            self.indicator_anim.start()
        else:
            self.indicator.setGeometry(target)
        self.indicator.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "indicator"):
            self._place_indicator()

    # ------------------------------------------------------------------ server selector
    def _fill_selector(self):
        self.selector.blockSignals(True)
        self.selector.clear()
        for sid, h in self.ctx.handles.items():
            self.selector.addItem(h.record.name, sid)
        if not self.ctx.handles:
            self.selector.addItem("No servers")
        self.selector.setEnabled(bool(self.ctx.handles))
        if self.ctx.selected:
            idx = self.selector.findData(self.ctx.selected.id)
            self.selector.setCurrentIndex(max(0, idx))
        self.selector.blockSignals(False)

    def _selector_chosen(self, index):
        sid = self.selector.itemData(index)
        if sid is not None:
            self.ctx.select(sid)

    def _selected(self, handle):
        self._fill_selector()
        for page in self.pages.values():
            page.bind(handle)
        if self.header_status is not None:
            self.header_status.set_status(handle.status if handle else "stopped")

    def _any_status(self, server_id, status):
        if self.ctx.selected and self.ctx.selected.id == server_id:
            self.header_status.set_status(status)

    # ------------------------------------------------------------------ closing
    def closeEvent(self, event):
        running = self.ctx.manager.running()
        if running:
            names = ", ".join(c.record.name for c in running)
            answer = QMessageBox.question(
                self, "Servers are running",
                f"These servers are still running: {names}.\n\nStop them safely (the world is saved) and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.setEnabled(False)
            self.setWindowTitle(f"{APP_NAME} - saving worlds and stopping servers...")
        self.ctx.manager.shutdown(pump=QApplication.processEvents)
        event.accept()
