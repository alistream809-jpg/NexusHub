"""Background tasks with a modal progress dialog (downloads, installs, Java setup)."""
import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QProgressBar, QVBoxLayout

from ..core.reporter import Cancelled, Reporter
from .widgets import button, label


class Worker(QThread):
    status = Signal(str)
    progress = Signal(float)
    log = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.cancel = threading.Event()

    def run(self):
        rep = Reporter(self.status.emit, self.progress.emit, self.log.emit, self.cancel)
        try:
            self.done.emit(self.fn(rep))
        except Cancelled:
            self.failed.emit("__cancelled__")
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)


class TaskDialog(QDialog):
    def __init__(self, parent, title: str, fn):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(680, 460)
        self.result_value = None
        self.error_text = ""
        self._finished = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)
        root.addWidget(label(title, "H1"))
        self.status = label("Preparing...", "Accent", wrap=True)
        root.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        root.addWidget(self.bar)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("Mono")
        self.log.setMaximumBlockCount(3000)
        root.addWidget(self.log, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_btn = button("Cancel", "danger")
        self.cancel_btn.clicked.connect(self._cancel)
        row.addWidget(self.cancel_btn)
        root.addLayout(row)

        self.worker = Worker(fn)
        self.worker.status.connect(self.status.setText)
        self.worker.progress.connect(self._progress)
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)

    def _progress(self, fraction: float):
        if fraction < 0:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(fraction * 1000))

    def _cancel(self):
        if self._finished:
            self.reject()
            return
        self.worker.cancel.set()
        self.cancel_btn.setEnabled(False)
        self.status.setText("Cancelling...")

    def _done(self, result):
        self._finished = True
        self.result_value = result
        self.accept()

    def _failed(self, message: str):
        self._finished = True
        if message == "__cancelled__":
            self.error_text = "Cancelled."
            self.reject()
            return
        self.error_text = message
        self.status.setText(message)
        self.status.setStyleSheet("color: #f87171; font-weight: 600;")
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.cancel_btn.setText("Close")
        self.cancel_btn.setProperty("variant", "ghost")
        self.cancel_btn.style().unpolish(self.cancel_btn)
        self.cancel_btn.style().polish(self.cancel_btn)
        self.cancel_btn.setEnabled(True)

    def reject(self):
        if not self._finished:
            self._cancel()
            return
        super().reject()

    def run(self):
        """Run the task; returns (result, error_text)."""
        self.worker.start()
        self.exec()
        self.worker.wait()
        return self.result_value, self.error_text
