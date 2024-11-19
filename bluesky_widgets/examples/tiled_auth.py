import getpass
import sys

from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from tiled.client import context as tiled_context_module
from tiled.client import from_uri
from tiled.client.context import Context


class TiledReaderManager:
    """Auth manager that will hold the client and valid API key for the tiled server"""

    client = None
    api_key = None
    context = None


class UsernamePasswordMonkeyPatch:
    """Monkey patch for getpass and prompt_for_username to allow for non-interactive authentication,
    while still using Tiled source code."""

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __call__(self, *args, **kwargs):
        return self.password

    def patch_prompt_for_username(self, username=None):
        return self.username if username is None else username


class TiledAuthWidget(QWidget):
    def __init__(self, auth_manager: TiledReaderManager):
        super().__init__()
        self.setWindowTitle("Tiled Authentication")

        # Layouts
        layout = QVBoxLayout()
        warning_layout = QHBoxLayout()
        server_layout = QHBoxLayout()
        credentials_layout = QVBoxLayout()
        timeout_layout = QHBoxLayout()
        button_layout = QHBoxLayout()

        # Warning label
        self.warning_label = QLabel(
            "Warning: Logging into a Tiled server allows the users of this app to read "
            "all of the data you have access to within the timeout set. Press Logout when finished."
        )
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet(
            "background-color: #F5F5F5; color: black; font-weight: bold; padding: 5px; "
            "border: 2px solid red; border-radius: 5px;"
        )
        warning_layout.addWidget(self.warning_label)

        # Server dropdown and manual input
        self.server_label = QLabel("Tiled Server:")
        self.server_dropdown = QComboBox()
        self.server_dropdown.addItems(["https://tiled.nsls2.bnl.gov", "https://example-server2.com"])
        self.server_dropdown.setEditable(True)  # Allow manual typing
        server_layout.addWidget(self.server_label)
        server_layout.addWidget(self.server_dropdown)

        # Username and password fields
        self.username_label = QLabel("Username:")
        self.username_input = QLineEdit()
        self.password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)  # Hide password input
        self.password_input.returnPressed.connect(self.authenticate)  # Allow pressing Enter to authenticate
        credentials_layout.addWidget(self.username_label)
        credentials_layout.addWidget(self.username_input)
        credentials_layout.addWidget(self.password_label)
        credentials_layout.addWidget(self.password_input)

        # API key timeout
        self.timeout_label = QLabel("API Key Timeout (hours):")
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(1, 168)  # Set range for timeout (1 to 168 hours)
        self.timeout_input.setValue(12)  # Default value
        timeout_layout.addWidget(self.timeout_label)
        timeout_layout.addWidget(self.timeout_input)

        # Logout button
        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.logout)
        self.logout_button.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.logout_button)

        # Authenticate and generate API key button
        self.authenticate_button = QPushButton("Authenticate")
        self.authenticate_button.clicked.connect(self.authenticate)
        button_layout.addWidget(self.authenticate_button)

        # Assemble layouts
        layout.addLayout(warning_layout)
        layout.addLayout(server_layout)
        layout.addLayout(credentials_layout)
        layout.addLayout(timeout_layout)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Actual API key and client
        self.auth_manager = auth_manager

    def authenticate(self):
        server_url = self.server_dropdown.currentText()
        username = self.username_input.text()
        password = self.password_input.text()
        timeout = self.timeout_input.value() * 3600  # Convert hours to seconds

        if not server_url or not username or not password:
            QMessageBox.warning(self, "Error", "All fields must be filled out.")
            return

        # Override some of the Tiled Context behavior that depends on TTY input
        username_password_monkey_patch = UsernamePasswordMonkeyPatch(username, password)
        original_prompt_for_username = tiled_context_module.prompt_for_username
        tiled_context_module.prompt_for_username = username_password_monkey_patch.patch_prompt_for_username
        original_getpass = getpass.getpass
        getpass.getpass = username_password_monkey_patch

        try:
            context = Context.from_any_uri(server_url)[0]
            context.authenticate(username=username)

            # Generate API key
            key_info = context.create_api_key(
                scopes=["read:metadata", "read:data"], expires_in=timeout, note="Bluesky Widgets Autogenerated Key"
            )
            QMessageBox.information(
                self,
                "Success",
                f"Authentication successful!\nAPI Key: {key_info['first_eight']}\n"
                f"Expires: {key_info['expiration_time'].isoformat()}",
            )

            self.auth_manager.api_key = key_info["secret"]
            self.auth_manager.context = context
            self.auth_manager.client = from_uri(server_url, api_key=self.auth_manager.api_key)
            self.logout_button.setEnabled(True)  # Enable the logout button

        except Exception as e:
            QMessageBox.critical(self, "Authentication Failed", str(e))

        finally:
            # Restore original getpass and prompt_for_username functions
            getpass.getpass = original_getpass
            tiled_context_module.prompt_for_username = original_prompt_for_username

    def logout(self):
        try:
            self.auth_manager.context.revoke_api_key(self.auth_manager.api_key)
            self.auth_manager.context.logout()
            self.auth_manager.api_key = None
            self.auth_manager.client = None
            self.logout_button.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Logout Failed", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    auth_manager = TiledReaderManager()
    widget = TiledAuthWidget(auth_manager=auth_manager)
    widget.show()
    # Can use the auth manager as a singleton in visualization widgets
    sys.exit(app.exec_())
