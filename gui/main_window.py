from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
    QTextEdit, QLabel, QProgressBar, QScrollArea, QLineEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEventLoop
from pathlib import Path
from utils.downloader import VideoDownloader
from gui.auth_window import AuthWindow
from telethon.tl.types import MessageMediaDocument
import asyncio
import logging
import configparser
import sys

class DownloadThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str, float)
    error_signal = pyqtSignal(str)
    video_count_signal = pyqtSignal(int)

    def __init__(self, downloader, groups, min_size, max_total_size, loop):
        super().__init__()
        self.downloader = downloader
        self.groups = groups
        self.min_size = min_size
        self.max_total_size = max_total_size
        self.loop = loop
        self.is_running = True  # Control flag for graceful shutdown
        self.downloader.progress_callback = self.progress_update
        self.downloader.log_callback = self.log_update
        self.downloader.video_count_callback = self.video_count_update

    def progress_update(self, message_id, filename, percentage):
        try:
            self.progress_signal.emit(message_id, filename, percentage)
        except Exception as e:
            self.error_signal.emit(f"Progress update error: {str(e)}")
            logging.error(f"Progress update error: {str(e)}")

    def log_update(self, message):
        try:
            self.log_signal.emit(message)
        except Exception as e:
            self.error_signal.emit(f"Log update error: {str(e)}")
            logging.error(f"Log update error: {str(e)}")

    def video_count_update(self, total_videos):
        try:
            self.video_count_signal.emit(total_videos)
        except Exception as e:
            self.error_signal.emit(f"Video count update error: {str(e)}")
            logging.error(f"Video count update error: {str(e)}")

    def stop(self):
        self.is_running = False
        self.downloader.stop()  # Signal downloader to stop

    def run(self):
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.downloader.run(self.groups, self.min_size, self.max_total_size),
                self.loop
            )
            while self.is_running and not future.done():
                self.msleep(100)  # Allow thread to check for stop signal
            if not self.is_running:
                future.cancel()  # Cancel the coroutine if stopped
            future.result()  # Wait for result or cancellation
        except asyncio.CancelledError:
            logging.info("Download thread cancelled")
        except Exception as e:
            self.error_signal.emit(f"Download failed to start: {str(e)}")
            logging.error(f"Download failed to start: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self, loop, api_id=None, api_hash=None):
        super().__init__()
        self.loop = loop
        self.api_id = api_id
        self.api_hash = api_hash
        self.setWindowTitle("Telegram Video Downloader")
        self.setMinimumSize(550, 450)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint)

        self.download_folder = Path("downloads")
        self.download_folder.mkdir(exist_ok=True)
        self.downloader = None
        self.download_thread = None
        self.downloads_occurred = False
        self.validated_groups = []
        self.total_videos = 0
        self.remaining_videos = 0

        try:
            with open('gui/styles/styles.qss', 'r') as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            logging.warning("Stylesheet 'gui/styles/styles.qss' not found")

        # Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_widget.setLayout(main_layout)

        # API credentials
        api_layout = QHBoxLayout()
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("Enter API ID (optional if set in config)")
        self.api_id_input.setMaximumWidth(150)
        self.api_hash_input = QLineEdit()
        self.api_hash_input.setPlaceholderText("Enter API Hash (optional if set in config)")
        self.api_hash_input.setMaximumWidth(250)
        if self.api_id:
            self.api_id_input.setText(str(self.api_id))
            self.api_id_input.setEnabled(False)
        if self.api_hash:
            self.api_hash_input.setText(self.api_hash)
            self.api_hash_input.setEnabled(False)
        api_layout.addWidget(QLabel("API ID:"))
        api_layout.addWidget(self.api_id_input)
        api_layout.addWidget(QLabel("API Hash:"))
        api_layout.addWidget(self.api_hash_input)
        main_layout.addLayout(api_layout)

        # Download folder
        folder_layout = QHBoxLayout()
        self.folder_label = QLabel(f"Save to: {self.download_folder}")
        self.folder_button = QPushButton("Choose")
        self.folder_button.clicked.connect(self.choose_folder)
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_button)
        main_layout.addLayout(folder_layout)

        # Size inputs
        size_layout = QHBoxLayout()
        self.size_input = QLineEdit("0MB")
        self.size_input.setPlaceholderText("e.g., 10MB")
        self.size_input.setMaximumWidth(80)
        self.max_size_input = QLineEdit("10GB")
        self.max_size_input.setPlaceholderText("e.g., 10GB")
        self.max_size_input.setMaximumWidth(80)
        size_layout.addWidget(QLabel("Min Size:"))
        size_layout.addWidget(self.size_input)
        size_layout.addWidget(QLabel("Max Total Size:"))
        size_layout.addWidget(self.max_size_input)
        main_layout.addLayout(size_layout)

        # Group input
        group_input_layout = QHBoxLayout()
        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("Enter group name (e.g., @groupname or chat ID)")
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
        self.load_groups()

        # Buttons
        button_layout = QHBoxLayout()
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
        self.progress_bars = {}

        # Log display
        main_layout.addWidget(QLabel("Log:"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)

    def save_config(self, api_id, api_hash):
        """Save API credentials to config.ini."""
        config = configparser.ConfigParser()
        config['Telegram'] = {
            'API_ID': str(api_id),
            'API_HASH': api_hash
        }
        config_path = Path('config/config.ini')
        config_path.parent.mkdir(exist_ok=True)
        try:
            with config_path.open('w', encoding='utf-8') as f:
                config.write(f)
            self.log_message(f"Created config.ini at {config_path}")
            logging.info(f"Created config.ini at {config_path}")
        except Exception as e:
            self.log_message(f"Failed to create config.ini: {str(e)}")
            logging.error(f"Failed to create config.ini: {str(e)}")

    def load_groups(self):
        self.groups_list.clear()
        groups_file = Path('config/groups.txt')
        if groups_file.exists():
            with groups_file.open('r', encoding='utf-8') as f:
                groups = [line.strip() for line in f if line.strip()]
                self.groups_list.addItems(groups)

    def add_group(self):
        group_name = self.group_input.text().strip()
        if not group_name:
            self.log_message("Please enter a group name.")
            return
        groups_file = Path('config/groups.txt')
        groups_file.parent.mkdir(exist_ok=True)
        with groups_file.open('a', encoding='utf-8') as f:
            f.write(f"{group_name}\n")
        self.log_message(f"Added group: {group_name}")
        logging.info(f"Added group: {group_name}")
        self.group_input.clear()
        self.load_groups()

    def remove_group(self):
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
            logging.info(f"Removed group: {group}")
        self.load_groups()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.download_folder = Path(folder)
            self.folder_label.setText(f"Save to: {folder}")
            if self.downloader:
                self.downloader.download_folder = self.download_folder
                self.downloader.download_folder.mkdir(exist_ok=True)
            self.log_message(f"Folder set to: {folder}")
            logging.info(f"Folder set to: {folder}")

    def set_video_count(self, total_videos):
        self.total_videos = total_videos
        self.remaining_videos = total_videos
        self.log_message(f"Total videos to download: {total_videos}")

    def start_download(self):
        from utils.helpers import parse_size
        selected_groups = [item.text() for item in self.groups_list.selectedItems()]
        if not selected_groups:
            self.log_message("Select at least one group to download.")
            QMessageBox.warning(self, "Error", "Select at least one group to download.")
            return

        api_id = self.api_id
        api_hash = self.api_hash
        if not api_id or not api_hash:
            api_id = self.api_id_input.text().strip()
            api_hash = self.api_hash_input.text().strip()

        if not api_id or not api_hash:
            self.log_message("Please enter both API ID and API Hash in config.ini or the GUI.")
            QMessageBox.warning(self, "Error", "Please enter both API ID and API Hash in config.ini or the GUI.")
            return

        try:
            api_id = int(api_id)
        except ValueError:
            self.log_message("API ID must be a valid integer.")
            QMessageBox.warning(self, "Error", "API ID must be a valid integer.")
            return

        min_size = self.size_input.text().strip()
        max_total_size = self.max_size_input.text().strip()

        try:
            parse_size(min_size)
        except ValueError:
            self.log_message(f"Invalid min size format: {min_size}. Expected format like '10MB'.")
            QMessageBox.warning(self, "Error", f"Invalid min size format: {min_size}. Expected format like '10MB'.")
            return

        try:
            parse_size(max_total_size)
        except ValueError:
            self.log_message(f"Invalid max total size format: {max_total_size}. Expected format like '10GB'.")
            QMessageBox.warning(self, "Error", f"Invalid max total size format: {max_total_size}. Expected format like '10GB'.")
            return

        normalized_groups = []
        for group in selected_groups:
            if not group:
                self.log_message(f"Skipping empty group name.")
                continue
            if not (group.startswith(('@', '-')) or group.isdigit()):
                group = f"@{group}"
            normalized_groups.append(group)
        if not normalized_groups:
            self.log_message("No valid groups selected. Please add valid group names (e.g., @groupname or chat ID).")
            QMessageBox.warning(self, "Error", "No valid groups selected. Please add valid group names (e.g., @groupname or chat ID).")
            return

        try:
            self.downloader = VideoDownloader(self.download_folder, api_id, api_hash, gui_callback=self.log_message)
        except Exception as e:
            self.log_message(f"Failed to initialize downloader: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to initialize downloader: {str(e)}")
            logging.error(f"Failed to initialize downloader: {str(e)}")
            return

        async def check_auth():
            try:
                if self.downloader.client.is_connected():
                    await self.downloader.client.disconnect()
                await self.downloader.client.connect()
                is_authorized = await self.downloader.client.is_user_authorized()
                logging.info(f"Session authorized: {is_authorized}")
                return is_authorized, None
            except Exception as e:
                logging.error(f"Error checking session: {str(e)}")
                return False, f"Error checking session: {str(e)}"

        try:
            future = asyncio.run_coroutine_threadsafe(check_auth(), self.loop)
            is_authorized, error = future.result()
            if error:
                self.log_message(error)
                QMessageBox.critical(self, "Error", error)
                return
        except Exception as e:
            self.log_message(f"Authentication check failed: {str(e)}")
            QMessageBox.critical(self, "Error", f"Authentication check failed: {str(e)}")
            logging.error(f"Authentication check failed: {str(e)}")
            return

        if is_authorized:
            async def validate_groups(groups):
                valid_groups = []
                try:
                    if not self.downloader.client.is_connected():
                        await self.downloader.client.connect()
                    for group in groups:
                        try:
                            entity = await self.downloader.client.get_entity(group)
                            async for _ in self.downloader.client.iter_messages(entity, limit=1):
                                pass
                            valid_groups.append(group)
                            self.log_message(f"Group {group} is accessible.")
                        except Exception as e:
                            self.log_message(f"Cannot access group {group}: {str(e)}. Ensure the group exists, is accessible, and your account has permission to view messages.")
                            logging.error(f"Cannot access group {group}: {str(e)}")
                    return valid_groups
                except Exception as e:
                    self.log_message(f"Group validation failed: {str(e)}")
                    logging.error(f"Group validation failed: {str(e)}")
                    return []

            try:
                self.downloads_occurred = False
                future = asyncio.run_coroutine_threadsafe(validate_groups(normalized_groups), self.loop)
                self.validated_groups = future.result()
                if not self.validated_groups:
                    self.log_message("No accessible groups found. Please verify group names and permissions.")
                    QMessageBox.critical(self, "Error", "No accessible groups found. Please verify group names and permissions.")
                    return
                if not Path('config/config.ini').exists() and not (self.api_id and self.api_hash):
                    self.save_config(api_id, api_hash)
                self.start_download_thread(self.validated_groups, min_size, max_total_size)
            except Exception as e:
                self.log_message(f"Group validation error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Group validation error: {str(e)}")
                logging.error(f"Group validation error: {str(e)}")
        else:
            auth_window = AuthWindow(self.downloader.client, self.loop, parent=self)
            auth_window.auth_completed.connect(lambda: self.start_download_after_auth(normalized_groups, min_size, max_total_size, api_id, api_hash))
            auth_window.exec()

    def start_download_after_auth(self, groups, min_size, max_total_size, api_id, api_hash):
        async def validate_groups(groups):
            valid_groups = []
            try:
                if not self.downloader.client.is_connected():
                    await self.downloader.client.connect()
                for group in groups:
                    try:
                        entity = await self.downloader.client.get_entity(group)
                        async for _ in self.downloader.client.iter_messages(entity, limit=1):
                            pass
                        valid_groups.append(group)
                        self.log_message(f"Group {group} is accessible.")
                    except Exception as e:
                        self.log_message(f"Cannot access group {group}: {str(e)}. Ensure the group exists, is accessible, and your account has permission to view messages.")
                        logging.error(f"Cannot access group {group}: {str(e)}")
                return valid_groups
            except Exception as e:
                self.log_message(f"Group validation failed: {str(e)}")
                logging.error(f"Group validation failed: {str(e)}")
                return []

        try:
            self.downloads_occurred = False
            future = asyncio.run_coroutine_threadsafe(validate_groups(groups), self.loop)
            self.validated_groups = future.result()
            if not self.validated_groups:
                self.log_message("No accessible groups found. Please verify group names and permissions.")
                QMessageBox.critical(self, "Error", "No accessible groups found. Please verify group names and permissions.")
                return
            self.save_config(api_id, api_hash)
            self.start_download_thread(self.validated_groups, min_size, max_total_size)
        except Exception as e:
            self.log_message(f"Group validation error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Group validation error: {str(e)}")
            logging.error(f"Group validation error: {str(e)}")

    def start_download_thread(self, groups, min_size, max_total_size):
        try:
            self.start_button.setEnabled(False)
            self.clear_progress_bars()
            self.download_thread = DownloadThread(self.downloader, groups, min_size, max_total_size, self.loop)
            self.download_thread.log_signal.connect(self.log_message)
            self.download_thread.progress_signal.connect(self.update_progress)
            self.download_thread.error_signal.connect(self.handle_download_error)
            self.download_thread.video_count_signal.connect(self.set_video_count)
            self.download_thread.finished.connect(self.download_finished)
            self.download_thread.start()
            self.log_message("Starting download process...")
        except Exception as e:
            self.log_message(f"Failed to start download thread: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to start download thread: {str(e)}")
            logging.error(f"Failed to start download thread: {str(e)}")
            self.start_button.setEnabled(True)

    def handle_download_error(self, error):
        self.log_message(error)
        QMessageBox.critical(self, "Error", error)
        self.start_button.setEnabled(True)

    def update_progress(self, message_id, filename, percentage):
        try:
            self.downloads_occurred = True
            if message_id not in self.progress_bars:
                progress_widget = QWidget()
                progress_layout = QHBoxLayout()
                progress_layout.setContentsMargins(4, 2, 4, 2)
                progress_widget.setLayout(progress_layout)
                label = QLabel(f"{filename}")
                label.setObjectName("progressLabel")
                progress_bar = QProgressBar()
                progress_bar.setMaximum(100)
                progress_bar.setValue(int(percentage))
                remaining_label = QLabel(f"Remaining: {self.remaining_videos}")
                progress_layout.addWidget(label)
                progress_layout.addWidget(progress_bar)
                progress_layout.addWidget(remaining_label)
                self.progress_layout.addWidget(progress_widget)
                self.progress_bars[message_id] = (progress_widget, progress_bar, remaining_label)
            else:
                _, progress_bar, remaining_label = self.progress_bars[message_id]
                progress_bar.setValue(int(percentage))
                remaining_label.setText(f"Remaining: {self.remaining_videos}")
            if percentage >= 100:
                self.remaining_videos -= 1
                self.remove_progress_bar(message_id)
                for _, _, rem_label in self.progress_bars.values():
                    rem_label.setText(f"Remaining: {self.remaining_videos}")
        except Exception as e:
            self.log_message(f"Progress update error: {str(e)}")
            logging.error(f"Progress update error: {str(e)}")

    def remove_progress_bar(self, message_id):
        if message_id in self.progress_bars:
            progress_widget, _, _ = self.progress_bars[message_id]
            self.progress_layout.removeWidget(progress_widget)
            progress_widget.deleteLater()
            del self.progress_bars[message_id]

    def clear_progress_bars(self):
        for message_id in list(self.progress_bars.keys()):
            self.remove_progress_bar(message_id)

    def download_finished(self):
        self.start_button.setEnabled(True)
        if self.validated_groups and self.downloads_occurred:
            self.log_message(f"Download process completed. {self.remaining_videos} videos remaining.")
            logging.info(f"Download process completed. {self.remaining_videos} videos remaining.")
        else:
            self.log_message("No videos were downloaded due to inaccessible groups or no videos found.")
            logging.info("No videos were downloaded due to inaccessible groups or no videos found.")
        self.total_videos = 0
        self.remaining_videos = 0

    def log_message(self, message):
        self.log_display.append(message)

    def clear_log(self):
        self.log_display.clear()

    async def disconnect_client(self):
        if self.downloader and self.downloader.client and self.downloader.client.is_connected():
            try:
                await self.downloader.client.disconnect()
                logging.info("Telegram client disconnected")
            except Exception as e:
                logging.warning(f"Error during disconnect: {str(e)}")

    def closeEvent(self, event):
        try:
            if self.download_thread and self.download_thread.isRunning():
                self.log_message("Stopping download thread...")
                self.download_thread.stop()
                self.download_thread.wait(5000)  # Wait up to 5 seconds
                if self.download_thread.isRunning():
                    logging.warning("Download thread did not stop gracefully, forcing termination")
                    self.download_thread.terminate()
            # Run disconnect_client synchronously
            if self.downloader:
                loop = QEventLoop()
                asyncio.run_coroutine_threadsafe(self.disconnect_client(), self.loop).add_done_callback(lambda _: loop.quit())
                loop.exec()
            # Clean up asyncio loop
            try:
                tasks = asyncio.all_tasks(self.loop)
                for task in tasks:
                    task.cancel()
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
                self.loop.run_until_complete(self.loop.shutdown_default_executor())
            except Exception as e:
                logging.warning(f"Error cleaning up asyncio loop: {str(e)}")
        except Exception as e:
            logging.error(f"Error during close: {str(e)}")
        finally:
            event.accept()
