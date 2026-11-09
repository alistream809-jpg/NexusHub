"""Reusable widgets: cards, status indicator, animated bar, fading page stack."""
from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, QVariantAnimation, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .theme import STATUS_COLORS, STATUS_LABELS


def label(text="", name=None, wrap=False) -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, variant=None, tooltip=None) -> QPushButton:
    btn = QPushButton(text)
    if variant:
        btn.setProperty("variant", variant)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def show_error(parent, text, title="NEXUS HOST"):
    QMessageBox.critical(parent, title, text)


def show_info(parent, text, title="NEXUS HOST"):
    QMessageBox.information(parent, title, text)


def confirm(parent, text, title="Confirm") -> bool:
    return QMessageBox.question(parent, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


class Card(QFrame):
    def __init__(self, layout=None):
        super().__init__()
        self.setObjectName("Card")
        self.box = layout if layout is not None else QVBoxLayout()
        self.box.setContentsMargins(20, 18, 20, 18)
        self.box.setSpacing(10)
        self.setLayout(self.box)


class StatusDot(QWidget):
    """Coloured status indicator that pulses while the server is changing state."""

    def __init__(self, size=12):
        super().__init__()
        self.setFixedSize(size + 8, size + 8)
        self._color = QColor(STATUS_COLORS["stopped"])
        self._alpha = 1.0
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.25)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(700)
        self._pulse.setLoopCount(-1)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse.valueChanged.connect(self._tick)

    def _tick(self, value):
        self._alpha = float(value)
        self.update()

    def set_status(self, status: str):
        self._color = QColor(STATUS_COLORS.get(status, STATUS_COLORS["stopped"]))
        if status in ("starting", "stopping"):
            if self._pulse.state() != QAbstractAnimation.State.Running:
                self._pulse.start()
        else:
            self._pulse.stop()
            self._alpha = 1.0
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color)
        color.setAlphaF(self._alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(self.rect().adjusted(4, 4, -4, -4))


class StatusBadge(QWidget):
    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.dot = StatusDot()
        self.text = label("Offline")
        row.addWidget(self.dot)
        row.addWidget(self.text)

    def set_status(self, status: str):
        self.dot.set_status(status)
        self.text.setText(STATUS_LABELS.get(status, status))
        self.text.setStyleSheet(f"color: {STATUS_COLORS.get(status, '#8b949e')}; font-weight: 600;")


class AnimatedBar(QProgressBar):
    def __init__(self):
        super().__init__()
        self.setRange(0, 100)
        self.setTextVisible(False)
        self.setFixedHeight(8)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_target(self, value: int):
        value = max(0, min(100, int(value)))
        self._anim.stop()
        self._anim.setStartValue(self.value())
        self._anim.setEndValue(value)
        self._anim.start()


class StatCard(Card):
    def __init__(self, title: str, with_bar=False):
        super().__init__()
        self.title = label(title, "Muted")
        self.value = label("-", "BigValue")
        self.sub = label("", "Muted")
        self.bar = AnimatedBar() if with_bar else None
        self.box.setSpacing(4)
        self.box.addWidget(self.title)
        self.box.addWidget(self.value)
        if self.bar:
            self.box.addWidget(self.bar)
        self.box.addWidget(self.sub)

    def set(self, value: str, sub: str = "", percent=None):
        self.value.setText(value)
        self.sub.setText(sub)
        if self.bar is not None and percent is not None:
            self.bar.set_target(percent)


class FadeStack(QStackedWidget):
    """Stacked widget that fades the incoming page in."""

    def __init__(self):
        super().__init__()
        self._anim = None

    def fade_to(self, index: int):
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)
        page = self.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        self._anim = QPropertyAnimation(effect, b"opacity", self)
        self._anim.setDuration(240)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(lambda: page.setGraphicsEffect(None))
        self._anim.start()


class Page(QWidget):
    """Base class for pages bound to the currently selected server."""
    title = ""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.handle = None

    def bind(self, handle):
        self.handle = handle

    def on_show(self):
        pass


def vbox(margins=(0, 0, 0, 0), spacing=12) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setContentsMargins(*margins)
    box.setSpacing(spacing)
    return box


def hbox(spacing=10) -> QHBoxLayout:
    box = QHBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(spacing)
    return box
