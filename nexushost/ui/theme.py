"""Dark theme with green accents."""
COLORS = {
    "bg": "#0d1117", "sidebar": "#090c10", "card": "#151a21", "card2": "#1b222b", "border": "#252d38",
    "text": "#e6edf3", "muted": "#8b949e", "accent": "#22c55e", "accent_hover": "#16a34a",
    "accent_dim": "#14532d", "danger": "#ef4444", "danger_hover": "#dc2626", "warn": "#f59e0b",
    "info": "#38bdf8", "input": "#0f141a",
}

STATUS_COLORS = {"stopped": "#6b7280", "starting": "#f59e0b", "online": "#22c55e", "stopping": "#f59e0b", "crashed": "#ef4444"}
STATUS_LABELS = {"stopped": "Offline", "starting": "Starting", "online": "Online", "stopping": "Stopping", "crashed": "Crashed"}
LINE_COLORS = {"info": "#c9d1d9", "warn": "#f59e0b", "error": "#f87171", "player": "#4ade80", "system": "#38bdf8", "command": "#a78bfa"}

_QSS = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: $text; outline: none; }
QWidget { background: transparent; }
QMainWindow, QDialog, QMessageBox, #Root { background: $bg; }
#Sidebar { background: $sidebar; border-right: 1px solid $border; }
#Logo { font-size: 17px; font-weight: 700; color: $text; }
#LogoAccent { color: $accent; }
#Header { background: $bg; border-bottom: 1px solid $border; }
#PageTitle { font-size: 20px; font-weight: 600; }
#H1 { font-size: 22px; font-weight: 700; }
#H2 { font-size: 15px; font-weight: 600; }
#Muted { color: $muted; }
#Mono { font-family: "Cascadia Mono", "Consolas", monospace; font-size: 12px; }
#Accent { color: $accent; font-weight: 600; }
#BigValue { font-size: 26px; font-weight: 700; }
#Card { background: $card; border: 1px solid $border; border-radius: 12px; }
#NavButton { text-align: left; padding: 11px 22px; border: none; border-radius: 0; color: $muted; font-size: 13px; background: transparent; }
#NavButton:hover { color: $text; background: $card; }
#NavButton:checked { color: $text; background: $card; font-weight: 600; }
QPushButton { background: $card2; border: 1px solid $border; border-radius: 8px; padding: 8px 16px; }
QPushButton:hover { border-color: $accent; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: #4b5563; background: $card; border-color: $border; }
QPushButton[variant="primary"] { background: $accent; border: 1px solid $accent; color: #04130a; font-weight: 600; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $accent_dim; border-color: $accent_dim; color: #4b6b57; }
QPushButton[variant="danger"] { background: transparent; border: 1px solid $danger; color: $danger; font-weight: 600; }
QPushButton[variant="danger"]:hover { background: $danger; color: white; }
QPushButton[variant="danger"]:disabled { border-color: #4b2a2a; color: #5b3a3a; background: transparent; }
QPushButton[variant="ghost"] { background: transparent; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {
    background: $input; border: 1px solid $border; border-radius: 8px; padding: 7px 10px; selection-background-color: $accent_dim; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: $accent; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { color: #4b5563; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid $muted; margin-right: 10px; }
QComboBox QAbstractItemView { background: $card2; border: 1px solid $border; selection-background-color: $accent_dim; padding: 4px; outline: none; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; }
QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a4452; background: $input; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; }
QSlider::groove:horizontal { height: 6px; background: $border; border-radius: 3px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }
QSlider::handle:horizontal { background: $text; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QProgressBar { background: $border; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: $accent; border-radius: 4px; }
QTableWidget, QListWidget { background: $card; border: 1px solid $border; border-radius: 10px; gridline-color: transparent; alternate-background-color: $card; outline: none; }
QTableWidget::item, QListWidget::item { padding: 8px 10px; border: none; }
QTableWidget::item:selected, QListWidget::item:selected { background: $accent_dim; color: $text; }
QHeaderView::section { background: $card; color: $muted; border: none; border-bottom: 1px solid $border; padding: 9px 10px; font-weight: 600; }
QTableCornerButton::section { background: $card; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2f3946; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #2f3946; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; border: none; width: 0; height: 0; }
QScrollArea { border: none; background: transparent; }
QToolTip { background: $card2; color: $text; border: 1px solid $border; padding: 6px; }
QMenu { background: $card2; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; }
QMenu::item:selected { background: $accent_dim; }
"""


def stylesheet() -> str:
    qss = _QSS
    for name in sorted(COLORS, key=len, reverse=True):
        qss = qss.replace("$" + name, COLORS[name])
    return qss
