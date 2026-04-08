# gui/auth_window.py
"""
Authentication window — Sign In / Sign Up.
Shown before the main application window.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QStackedWidget, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from data.sqlite_repo import SQLiteRepository
from services.auth_service import AuthService

STYLE = """
QDialog {
    background-color: #0f0f14;
}
QLabel {
    color: #c8c8d8;
    background: transparent;
}
QLineEdit {
    background-color: #1a1a24;
    color: #c8c8d8;
    border: 1px solid #2a2a3a;
    border-radius: 4px;
    padding: 10px 12px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #6c8cff;
}
QPushButton {
    background-color: #4a6adf;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #5a7aef;
}
QPushButton:pressed {
    background-color: #3a5acf;
}
QPushButton[class="secondary"] {
    background-color: transparent;
    color: #6c8cff;
    border: none;
    font-size: 12px;
}
QPushButton[class="secondary"]:hover {
    color: #8cacff;
}
"""


class AuthWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ErgoBoost — Sign In")
        self.setFixedSize(400, 480)
        self.setStyleSheet(STYLE)

        self.db = SQLiteRepository()
        self.auth = AuthService(self.db)
        self.authenticated_user = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(0)

        # Logo / title
        title = QLabel("ErgoBoost")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet("color: #6c8cff;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("AI Posture Monitor")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #5a5a6a; font-size: 12px; margin-bottom: 24px;")
        layout.addWidget(subtitle)

        # Stacked widget for sign in / sign up
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_signin_page())
        self.stack.addWidget(self._create_signup_page())
        layout.addWidget(self.stack)

    def _create_signin_page(self):
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        lbl = QLabel("Sign In")
        lbl.setFont(QFont("Segoe UI", 16, QFont.DemiBold))
        layout.addWidget(lbl)

        self.si_username = QLineEdit()
        self.si_username.setPlaceholderText("Username")
        layout.addWidget(self.si_username)

        self.si_password = QLineEdit()
        self.si_password.setPlaceholderText("Password")
        self.si_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.si_password)

        self.si_error = QLabel("")
        self.si_error.setStyleSheet("color: #c04050; font-size: 11px;")
        self.si_error.setWordWrap(True)
        layout.addWidget(self.si_error)

        btn = QPushButton("Sign In")
        btn.setMinimumHeight(42)
        btn.clicked.connect(self._do_signin)
        layout.addWidget(btn)

        # Enter key triggers sign in
        self.si_password.returnPressed.connect(self._do_signin)

        layout.addSpacing(8)

        switch = QPushButton("Don't have an account? Sign Up")
        switch.setProperty("class", "secondary")
        switch.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout.addWidget(switch, alignment=Qt.AlignCenter)

        layout.addStretch()
        return page

    def _create_signup_page(self):
        page = QWidget()
        page.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        lbl = QLabel("Create Account")
        lbl.setFont(QFont("Segoe UI", 16, QFont.DemiBold))
        layout.addWidget(lbl)

        self.su_display = QLineEdit()
        self.su_display.setPlaceholderText("Display Name")
        layout.addWidget(self.su_display)

        self.su_username = QLineEdit()
        self.su_username.setPlaceholderText("Username (min 3 characters)")
        layout.addWidget(self.su_username)

        self.su_password = QLineEdit()
        self.su_password.setPlaceholderText("Password (min 4 characters)")
        self.su_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.su_password)

        self.su_password2 = QLineEdit()
        self.su_password2.setPlaceholderText("Confirm Password")
        self.su_password2.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.su_password2)

        self.su_error = QLabel("")
        self.su_error.setStyleSheet("color: #c04050; font-size: 11px;")
        self.su_error.setWordWrap(True)
        layout.addWidget(self.su_error)

        btn = QPushButton("Sign Up")
        btn.setMinimumHeight(42)
        btn.clicked.connect(self._do_signup)
        layout.addWidget(btn)

        self.su_password2.returnPressed.connect(self._do_signup)

        layout.addSpacing(8)

        switch = QPushButton("Already have an account? Sign In")
        switch.setProperty("class", "secondary")
        switch.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        layout.addWidget(switch, alignment=Qt.AlignCenter)

        layout.addStretch()
        return page

    def _do_signin(self):
        username = self.si_username.text().strip()
        password = self.si_password.text()

        if not username or not password:
            self.si_error.setText("Please enter username and password")
            return

        try:
            user = self.auth.sign_in(username, password)
            self.authenticated_user = user
            self.accept()
        except ValueError as e:
            self.si_error.setText(str(e))

    def _do_signup(self):
        display_name = self.su_display.text().strip()
        username = self.su_username.text().strip()
        password = self.su_password.text()
        password2 = self.su_password2.text()

        if not username or not password:
            self.su_error.setText("Please fill all fields")
            return

        if password != password2:
            self.su_error.setText("Passwords do not match")
            return

        try:
            user = self.auth.sign_up(username, password, display_name)
            self.authenticated_user = user
            self.accept()
        except ValueError as e:
            self.su_error.setText(str(e))

    def get_user(self):
        return self.authenticated_user

    def get_auth_service(self):
        return self.auth

    def get_db(self):
        return self.db
