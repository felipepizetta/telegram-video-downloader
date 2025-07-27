from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
    QTextEdit, QLabel, QProgressBar, QScrollArea, QLineEdit, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path
import asyncio
import sys
from utils.downloader import VideoDownloader

class DownloadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str, float)  # message_id, filename, percentage

    def __init__(self, downloader, groups, min_size):
        super().__init__()
        self.downloader = downloader
        self.groups = groups
        self.min_size = min_size
        self.loop = asyncio.get_event_loop()
        self.downloader.progress_callback = self.progress_update

    def progress_update(self, message_id, filename, percentage):
        """Emit progress signal to update GUI."""
        self.progress_signal.emit(message_id, filename, percentage)

    def run(self):
        self.loop.run_until_complete(self.downloader.run(self.groups, self.min_size))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram Video Downloader")
        self.setMinimumSize(550, 450)
        # Disable maximize button
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint)

        # Initialize download folder
        self.download_folder = "downloads"

        # Load stylesheet
        with open('gui/styles/styles.qss', 'r') as f:
            self.setStyleSheet(f.read())

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_widget.setLayout(main_layout)

        # Download folder selection
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(4)
        self.folder_label = QLabel(f"Save to: {self.download_folder}")
        self.folder_button = QPushButton("Choose")
        self.folder_button.clicked.connect(self.choose_folder)
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_button)
        main_layout.addLayout(folder_layout)

        # Minimum video size
        size_layout = QHBoxLayout()
        size_layout.setSpacing(4)
        self.size_input = QLineEdit("0MB")
        self.size_input.setPlaceholderText("e.g., 10MB")
        self.size_input.setMaximumWidth(80)
        size_layout.addWidget(QLabel("Size:"))
        size_layout.addWidget(self.size_input)
        main_layout.addLayout(size_layout)

        # Group input
        group_input_layout = QHBoxLayout()
        group_input_layout.setSpacing(4)
        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("Enter group name")
        self.group_input.setMaximumWidth(200)
        self.add_group_button = QPushButton("Add")
        self.add_group_button.clicked.connect(self.add_group)
        self.remove_group_button = QPushButton("Remove")
        self.remove_group_button.clicked.connect(self.remove_group)
        group_input_layout.addWidget(QLabel("Add Group:"))
        group_input_layout.addWidget(self.group_input)
        group_input_layout.addWidget(self.add_group_button)
        group_input_layout.addWidget(self.remove_group_button)
        main_layout.addLayout(group_input_layout)

        # Groups list
        self.groups_list = QListWidget()
        self.groups_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        main_layout.addWidget(QLabel("Groups:"))
        main_layout.addWidget(self.groups_list)

        # Load groups from file
        self.load_groups()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(4)
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_download)
        self.clear_log_button = QPushButton("Clear")
        self.clear_log_button.clicked.connect(self.clear_log)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.clear_log_button)
        main_layout.addLayout(button_layout)

        # Progress bars
        main_layout.addWidget(QLabel("Downloads:"))
        self.progress_scroll = QScrollArea()
        self.progress_scroll.setWidgetResizable(True)
        self.progress_container = QWidget()
        self.progress_layout = QVBoxLayout()
        self.progress_layout.setSpacing(4)
        self.progress_container.setLayout(self.progress_layout)
        self.progress_scroll.setWidget(self.progress_container)
        main_layout.addWidget(self.progress_scroll)
        self.progress_bars = {}  # Track progress bars by message_id

        # Log display
        main_layout.addWidget(QLabel("Log:"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)

        # Initialize downloader
        self.downloader = VideoDownloader(self.download_folder, gui_callback=self.log_message)
        self.download_thread = None

    def load_groups(self):
        """Load groups from config/groups.txt."""
        self.groups_list.clear()
        groups_file = Path('config/groups.txt')
        if groups_file.exists():
            with groups_file.open('r', encoding='utf-8') as f:
                groups = [line.strip() for line in f if line.strip()]
                self.groups_list.addItems(groups)

    def add_group(self):
        """Add a new group to config/groups.txt and refresh the list."""
        group_name = self.group_input.text().strip()
        if not group_name:
            self.log_message("Please enter a group name.")
            return

        groups_file = Path('config/groups.txt')
        groups_file.parent.mkdir(exist_ok=True)
        with groups_file.open('a', encoding='utf-8') as f:
            f.write(f"{group_name}\n")
        
        self.log_message(f"Added group: {group_name}")
        self.group_input.clear()
        self.load_groups()

    def remove_group(self):
        """Remove selected groups from config/groups.txt and refresh the list."""
        selected_groups = [item.text() for item in self.groups_list.selectedItems()]
        if not selected_groups:
            self.log_message("Select at least one group to remove.")
            return

        groups_file = Path('config/groups.txt')
        if groups_file.exists():
            with groups_file.open('r', encoding='utf-8') as f:
                groups = [line.strip() for line in f if line.strip()]
            groups = [g for g in groups if g not in selected_groups]
            with groups_file.open('w', encoding='utf-8') as f:
                for group in groups:
                    f.write(f"{group}\n")
        
        for group in selected_groups:
            self.log_message(f"Removed group: {group}")
        self.load_groups()

    def choose_folder(self):
        """Open a dialog to choose the download folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.download_folder = folder
            self.folder_label.setText(f"Save to: {folder}")
            self.downloader.download_folder = Path(folder)
            self.downloader.download_folder.mkdir(exist_ok=True)
            self.log_message(f"Folder set to: {folder}")

    def start_download(self):
        """Start the download process in a separate thread."""
        selected_groups = [item.text() for item in self.groups_list.selectedItems()]
        if not selected_groups:
            self.log_message("Select at least one group to download.")
            return

        self.start_button.setEnabled(False)
        self.clear_progress_bars()
        self.download_thread = DownloadThread(self.downloader, selected_groups, self.size_input.text())
        self.download_thread.log_signal.connect(self.log_message)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.start()

    def update_progress(self, message_id, filename, percentage):
        """Update or create progress bar for a download."""
        if message_id not in self.progress_bars:
            # Create new progress bar
            progress_widget = QWidget()
            progress_layout = QHBoxLayout()
            progress_layout.setContentsMargins(4, 2, 4, 2)
            progress_widget.setLayout(progress_layout)
            label = QLabel(f"{filename}")
            label.setObjectName("progressLabel")
            progress_bar = QProgressBar()
            progress_bar.setMaximum(100)
            progress_bar.setValue(int(percentage))
            progress_layout.addWidget(label)
            progress_layout.addWidget(progress_bar)
            self.progress_layout.addWidget(progress_widget)
            self.progress_bars[message_id] = (progress_widget, progress_bar)
        else:
            # Update existing progress bar
            _, progress_bar = self.progress_bars[message_id]
            progress_bar.setValue(int(percentage))

        # Remove completed progress bars
        if percentage >= 100:
            self.remove_progress_bar(message_id)

    def remove_progress_bar(self, message_id):
        """Remove a progress bar from the layout."""
        if message_id in self.progress_bars:
            progress_widget, _ = self.progress_bars[message_id]
            self.progress_layout.removeWidget(progress_widget)
            progress_widget.deleteLater()
            del self.progress_bars[message_id]

    def clear_progress_bars(self):
        """Clear all progress bars."""
        for message_id in list(self.progress_bars.keys()):
            self.remove_progress_bar(message_id)

    def download_finished(self):
        """Re-enable start button when download completes."""
        self.start_button.setEnabled(True)

    def log_message(self, message):
        """Append message to log display."""
        self.log_display.append(message)

    def clear_log(self):
        """Clear the log display."""
        self.log_display.clear()