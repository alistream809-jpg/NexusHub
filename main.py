"""NEXUS HOST entry point."""
import logging
import os
import sys
import traceback

from nexushost import APP_ID, APP_NAME
from nexushost.core.paths import log_path, resource_path


def main() -> int:
    logging.basicConfig(filename=str(log_path()), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    if os.name == "nt":
        try:  # lets Windows show our own icon on the taskbar
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_ID}.Desktop")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    icon = resource_path("assets/nexus.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    from nexushost.ui.theme import stylesheet
    app.setStyleSheet(stylesheet())

    def excepthook(kind, value, tb):
        logging.error("Unhandled exception", exc_info=(kind, value, tb))
        QMessageBox.critical(None, APP_NAME, "An unexpected error occurred:\n\n"
                             + "".join(traceback.format_exception_only(kind, value))
                             + f"\nDetails were written to {log_path()}")

    sys.excepthook = excepthook

    from nexushost.core.manager import ServerManager
    from nexushost.ui.bridge import AppContext
    from nexushost.ui.main_window import MainWindow

    manager = ServerManager()
    ctx = AppContext(manager)
    window = MainWindow(ctx)
    window.show()
    # warm the Java scan in the background so Start is instant
    import threading
    threading.Thread(target=manager.javamgr.scan, daemon=True).start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
