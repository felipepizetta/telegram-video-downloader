from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError, PhoneCodeInvalidError, FloodWaitError, RPCError
import asyncio

class AuthError(Exception):
    """Exceção personalizada para erros de autenticação."""
    pass

class AuthWindow(QDialog):
    """Janela de diálogo para autenticação no Telegram."""
    
    auth_completed = pyqtSignal()
    STATE_PHONE = "phone"
    STATE_CODE = "code"
    DEFAULT_PHONE_FORMAT = "e.g., +5519991880399"

    def __init__(self, client, loop, parent=None):
        """Inicializa a janela de autenticação."""
        super().__init__(parent)
        self.setWindowTitle("Telegram Authentication")
        self.setMinimumSize(300, 200)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.client = client
        self.loop = loop
        self.phone_number = None
        self.state = self.STATE_PHONE

        self._setup_ui()
        self._initialize_state()

    def _setup_ui(self):
        """Configura a interface da janela."""
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Status label
        self.status_label = QLabel(f"Enter your phone number ({self.DEFAULT_PHONE_FORMAT}) to receive a code.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Phone number input
        phone_layout = QHBoxLayout()
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText(self.DEFAULT_PHONE_FORMAT)
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

    def _initialize_state(self):
        """Define o estado inicial da interface."""
        self.phone_input.setEnabled(True)
        self.code_input.setEnabled(False)
        self.submit_button.setEnabled(True)
        self.retry_button.setEnabled(False)

    def _set_loading_state(self, is_loading):
        """Altera o estado da UI para indicar carregamento."""
        self.phone_input.setEnabled(not is_loading)
        self.code_input.setEnabled(not is_loading)
        self.submit_button.setEnabled(not is_loading)
        self.retry_button.setEnabled(not is_loading)

    def submit_action(self):
        """Executa a ação apropriada com base no estado atual."""
        if self.state == self.STATE_PHONE:
            self.send_code()
        elif self.state == self.STATE_CODE:
            self.sign_in()

    async def _send_code_request(self, phone):
        """Envia solicitação de código para o número de telefone."""
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

    def send_code(self):
        """Processa o envio de código de autenticação."""
        phone = self.phone_input.text().strip()
        if not phone:
            self._show_error("Please enter a phone number.")
            return

        self._set_loading_state(True)
        self.status_label.setText("Sending code...")
        future = asyncio.run_coroutine_threadsafe(self._send_code_request(phone), self.loop)
        try:
            success, error = future.result()
            if success:
                self.phone_number = phone
                self._transition_to_code_state()
            else:
                self._handle_error(error)
        except Exception as e:
            self._handle_error(f"Unexpected error in send_code: {str(e)}")
        finally:
            self._set_loading_state(False)

    async def _sign_in_request(self, code):
        """Executa a solicitação de login com o código recebido."""
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

    def sign_in(self):
        """Processa o login com o código de autenticação."""
        code = self.code_input.text().strip()
        if not code:
            self._show_error("Please enter the authentication code.")
            return

        self._set_loading_state(True)
        self.status_label.setText("Signing in...")
        future = asyncio.run_coroutine_threadsafe(self._sign_in_request(code), self.loop)
        try:
            success, error = future.result()
            if success:
                self.status_label.setText("Authentication successful.")
                self.auth_completed.emit()
                self.accept()
            else:
                self._handle_error(error)
        except Exception as e:
            self._handle_error(f"Unexpected error in sign_in: {str(e)}")
        finally:
            self._set_loading_state(False)

    def _transition_to_code_state(self):
        """Transiciona a UI para o estado de entrada de código."""
        self.state = self.STATE_CODE
        self.status_label.setText("Code sent. Enter the authentication code received via Telegram.")
        self.code_input.setVisible(True)
        self.code_input.setEnabled(True)
        self.submit_button.setText("Sign In")
        self.code_input.setFocus()

    def retry(self):
        """Reinicia o processo de autenticação."""
        self.state = self.STATE_PHONE
        self.phone_number = None
        self._initialize_state()
        self.code_input.clear()
        self.code_input.setVisible(False)
        self.status_label.setText(f"Enter your phone number ({self.DEFAULT_PHONE_FORMAT}) to receive a code.")

    def _show_error(self, message):
        """Exibe uma mensagem de erro na UI."""
        self.status_label.setText(message)
        QMessageBox.critical(self, "Error", message)

    def _handle_error(self, error):
        """Trata erros e restaura o estado da UI."""
        self._show_error(error)
        self.retry_button.setEnabled(True)
        self.submit_button.setEnabled(True)

    async def disconnect_client(self):
        """Desconecta o cliente Telegram de forma segura."""
        if self.client.is_connected():
            try:
                await self.client.disconnect()
            except Exception:
                pass

    def closeEvent(self, event):
        """Gerencia o evento de fechamento da janela."""
        try:
            future = asyncio.run_coroutine_threadsafe(self.disconnect_client(), self.loop)
            future.result()
        except Exception:
            pass
        event.accept()