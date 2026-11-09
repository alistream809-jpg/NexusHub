from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QComboBox, QLineEdit, QListWidget, QPlainTextEdit

from ..core.controller import ServerError, Status
from .theme import LINE_COLORS
from .widgets import Card, Page, button, hbox, label, show_error, vbox

FILTERS = {"All output": None, "Errors and warnings": ("error", "warn"), "Player activity": ("player",)}


class HistoryLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.history, self.index = [], 0

    def remember(self, text):
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.index = len(self.history)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up and self.history:
            self.index = max(0, self.index - 1)
            self.setText(self.history[self.index])
        elif event.key() == Qt.Key.Key_Down and self.history:
            self.index = min(len(self.history), self.index + 1)
            self.setText(self.history[self.index] if self.index < len(self.history) else "")
        else:
            super().keyPressEvent(event)


class ConsolePage(Page):
    title = "Console"

    def __init__(self, ctx):
        super().__init__(ctx)
        root = vbox((28, 24, 28, 24), 12)
        self.setLayout(root)

        bar = hbox()
        self.filter = QComboBox()
        self.filter.addItems(list(FILTERS))
        self.filter.currentTextChanged.connect(self._render_all)
        clear = button("Clear view", "ghost")
        clear.clicked.connect(self.view_clear)
        bar.addWidget(label("Show", "Muted"))
        bar.addWidget(self.filter)
        bar.addStretch(1)
        bar.addWidget(clear)
        root.addLayout(bar)

        body = hbox(14)
        left = vbox(spacing=10)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(6000)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Cascadia Mono")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.output.setFont(font)
        left.addWidget(self.output, 1)
        send_row = hbox(8)
        self.input = HistoryLineEdit()
        self.input.setPlaceholderText("Type a server command and press Enter")
        self.input.returnPressed.connect(self._send)
        self.send_btn = button("Send", "primary")
        self.send_btn.clicked.connect(self._send)
        send_row.addWidget(self.input, 1)
        send_row.addWidget(self.send_btn)
        left.addLayout(send_row)
        body.addLayout(left, 1)

        side = Card()
        side.setFixedWidth(230)
        side.box.addWidget(label("Online players", "H2"))
        self.count = label("0 online", "Muted")
        side.box.addWidget(self.count)
        self.roster = QListWidget()
        side.box.addWidget(self.roster, 1)
        body.addWidget(side)
        root.addLayout(body, 1)

    # ------------------------------------------------------------------ binding
    def bind(self, handle):
        old = self.handle
        if old is not None:
            for sig, slot in ((old.line, self._line), (old.status_changed, self._status), (old.players_changed, self._players)):
                try:
                    sig.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        super().bind(handle)
        if handle is None:
            self.output.clear()
            self._status(Status.STOPPED)
            return
        handle.line.connect(self._line)
        handle.status_changed.connect(self._status)
        handle.players_changed.connect(self._players)
        self._render_all()
        self._status(handle.status)
        self._players(sorted(handle.c.player_names), handle.c.player_count, handle.c.max_players)

    # ------------------------------------------------------------------ rendering
    def _allowed(self, kind):
        wanted = FILTERS[self.filter.currentText()]
        return wanted is None or kind in wanted or kind == "system"

    def _append(self, kind, text):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(LINE_COLORS.get(kind, LINE_COLORS["info"])))
        bar = self.output.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self.output.document().isEmpty():
            cursor.insertBlock()
        cursor.insertText(text, fmt)
        if at_end:
            bar.setValue(bar.maximum())

    def _render_all(self, *_):
        self.output.clear()
        if self.handle is None:
            return
        for kind, text in list(self.handle.c.console):
            if self._allowed(kind):
                self._append(kind, text)

    def view_clear(self):
        self.output.clear()

    def _line(self, kind, text):
        if self._allowed(kind):
            self._append(kind, text)

    def _status(self, status):
        online = status == Status.ONLINE
        self.input.setEnabled(online)
        self.send_btn.setEnabled(online)
        self.input.setPlaceholderText("Type a server command and press Enter" if online
                                      else "Commands are available while the server is online")

    def _players(self, names, count, _max):
        self.roster.clear()
        self.roster.addItems(names)
        self.count.setText(f"{count} online")

    def _send(self):
        text = self.input.text().strip()
        if not text or self.handle is None:
            return
        try:
            self.handle.c.send_command(text)
        except ServerError as exc:
            show_error(self, str(exc))
            return
        self.input.remember(text)
        self.input.clear()
