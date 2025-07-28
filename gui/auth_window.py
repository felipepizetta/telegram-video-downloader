from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError, PhoneCodeInvalidError, FloodWaitError, RPCError
import asyncio
import logging

class AuthWindow(QDialog):
    auth_completed = pyqtSignal()

    def __init__(self, client, loop, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Telegram Authentication")
        self.setMinimumSize(300, 200)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.client = client
        self.loop = loop
        self.phone_number = None

        # Layout
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Status label
        self.status_label = QLabel("Enter your phone number (e.g., +5519991880399) to receive a code.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Phone number input
        phone_layout = QHBoxLayout()
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Phone number (e.g., +5519991880399)")
        self.submit_button = QPushButton("Send Code")
        self.submit_button.clicked.connect(self.submit_action)
        phone_layout.addWidget(QLabel("Phone:"))
        phone_layout.addWidget(self.phone_input)
        phone_layout.addWidget(self.submit_button)
        layout.addLayout(phone_layout)

        # Code input
        code_layout = QHBoxLayout()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter authentication code")
        self.code_input.setVisible(False)
        self.code_input.setEnabled(False)
        code_layout.addWidget(QLabel("Code:"))
        code_layout.addWidget(self.code_input)
        layout.addLayout(code_layout)

        # Retry button
        retry_layout = QHBoxLayout()
        self.retry_button = QPushButton("Retry")
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry)
        retry_layout.addStretch()
        retry_layout.addWidget(self.retry_button)
        layout.addLayout(retry_layout)

        self.setLayout(layout)
        self.state = "phone"

    def submit_action(self):
        if self.state == "phone":
            self.send_code()
        elif self.state == "code":
            self.sign_in()

    def send_code(self):
        phone = self.phone_input.text().strip()
        if not phone:
            self.status_label.setText("Please enter a phone number.")
            QMessageBox.warning(self, "Error", "Please enter a phone number.")
            logging.warning("Empty phone number entered")
            return

        async def send_code_request():
            try:
                if self.client.is_connected():
                    await self.client.disconnect()
                await self.client.connect()
                await self.client.send_code_request(phone)
                return True, None
            except PhoneNumberInvalidError:
                return False, "Invalid phone number format. Use format like +5519991880399."
            except FloodWaitError as e:
                return False, f"Too many requests. Please wait {e.seconds} seconds."
            except RPCError as e:
                return False, f"Failed to send code: {str(e)}"
            except Exception as e:
                return False, f"Unexpected error: {str(e)}"

        try:
            self.status_label.setText("Sending code...")
            self.submit_button.setEnabled(False)
            self.retry_button.setEnabled(False)
            self.phone_input.setEnabled(False)
            logging.info(f"Attempting to send code to {phone}")

            future = asyncio.run_coroutine_threadsafe(send_code_request(), self.loop)
            success, error = future.result()

            if success:
                self.phone_number = phone
                logging.info(f"Code sent to {phone}")
                self.status_label.setText("Code sent. Enter the authentication code received via Telegram.")
                self.state = "code"
                self.code_input.setVisible(True)
                self.code_input.setEnabled(True)
                self.submit_button.setText("Sign In")
                self.submit_button.setEnabled(True)
                self.code_input.setFocus()
            else:
                logging.error(error)
                self.status_label.setText(error)
                QMessageBox.critical(self, "Error", error)
                self.retry_button.setEnabled(True)
                self.submit_button.setEnabled(True)
                self.phone_input.setEnabled(True)
        except Exception as e:
            error_msg = f"Unexpected error in send_code: {str(e)}"
            logging.error(error_msg)
            self.status_label.setText(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            self.retry_button.setEnabled(True)
            self.submit_button.setEnabled(True)
            self.phone_input.setEnabled(True)

    def sign_in(self):
        code = self.code_input.text().strip()
        if not code:
            self.status_label.setText("Please enter the authentication code.")
            QMessageBox.warning(self, "Error", "Please enter the authentication code.")
            logging.warning("Empty authentication code entered")
            return

        async def sign_in_request():
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self.client.sign_in(self.phone_number, code)
                return True, None
            except SessionPasswordNeededError:
                return False, "2FA is not supported."
            except PhoneCodeInvalidError:
                return False, "Invalid authentication code."
            except RPCError as e:
                return False, f"Sign-in failed: {str(e)}"
            except Exception as e:
                return False, f"Unexpected error in sign_in: {str(e)}"

        try:
            self.status_label.setText("Signing in...")
            self.submit_button.setEnabled(False)
            self.retry_button.setEnabled(False)
            self.code_input.setEnabled(False)
            logging.info("Attempting to sign in")

            future = asyncio.run_coroutine_threadsafe(sign_in_request(), self.loop)
            success, error = future.result()

            if success:
                logging.info("Successfully signed in")
                self.status_label.setText("Authentication successful.")
                self.auth_completed.emit()
                self.accept()
            else:
                logging.error(error)
                self.status_label.setText(error)
                QMessageBox.critical(self, "Error", error)
                self.retry_button.setEnabled(True)
                self.submit_button.setEnabled(True)
                self.code_input.setEnabled(True)
        except Exception as e:
            error_msg = f"Unexpected error in sign_in: {str(e)}"
            logging.error(error_msg)
            self.status_label.setText(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            self.retry_button.setEnabled(True)
            self.submit_button.setEnabled(True)
            self.code_input.setEnabled(True)

    def retry(self):
        self.state = "phone"
        self.phone_number = None
        self.phone_input.setEnabled(True)
        self.phone_input.clear()
        self.code_input.setEnabled(False)
        self.code_input.clear()
        self.code_input.setVisible(False)
        self.submit_button.setText("Send Code")
        self.submit_button.setEnabled(True)
        self.retry_button.setEnabled(False)
        self.status_label.setText("Enter your phone number (e.g., +5519991880399) to receive a code.")
        logging.info("Retry authentication initiated")

    async def disconnect_client(self):
        if self.client.is_connected():
            try:
                await self.client.disconnect()
                logging.info("Telegram client disconnected")
            except Exception as e:
                logging.warning(f"Error during disconnect: {str(e)}")

    def closeEvent(self, event):
        try:
            future = asyncio.run_coroutine_threadsafe(self.disconnect_client(), self.loop)
            future.result()
        except Exception as e:
            logging.warning(f"Error during disconnect: {str(e)}")
        event.accept()