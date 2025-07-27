import sys
import locale
import io
import os
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

# Configure encoding for Windows
if sys.platform == "win32":
    locale.setlocale(locale.LC_ALL, '')
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except AttributeError:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())