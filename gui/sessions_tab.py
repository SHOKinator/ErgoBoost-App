# gui/sessions_tab.py
"""
Sessions tab - View and analyze past sessions
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from datetime import datetime

from data.sqlite_repo import SQLiteRepository
from gui.session_detail_dialog import SessionDetailDialog


class SessionsTab(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.db = SQLiteRepository()
        self._init_ui()
        self.refresh_sessions()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Sessions")
        title.setFont(QFont("Segoe UI", 20, QFont.DemiBold))
        title.setStyleSheet("color: #e0e0ee;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMinimumSize(90, 34)
        refresh_btn.clicked.connect(self.refresh_sessions)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(6)
        self.sessions_table.setHorizontalHeaderLabels([
            "ID", "Date", "Duration", "Score", "Status", ""
        ])

        hdr = self.sessions_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)

        self.sessions_table.setColumnWidth(0, 50)
        self.sessions_table.setColumnWidth(5, 80)
        self.sessions_table.setAlternatingRowColors(True)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sessions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessions_table.verticalHeader().setVisible(False)

        layout.addWidget(self.sessions_table)

    def refresh_sessions(self):
        sessions = self.db.get_all_sessions(limit=100)
        self.sessions_table.setRowCount(len(sessions))

        for row, session in enumerate(sessions):
            id_item = QTableWidgetItem(str(session['id']))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.sessions_table.setItem(row, 0, id_item)

            start_time = datetime.fromisoformat(session['start_time'])
            self.sessions_table.setItem(row, 1,
                QTableWidgetItem(start_time.strftime("%Y-%m-%d  %H:%M")))

            duration = session.get('duration_seconds')
            if duration:
                m, s = divmod(int(duration), 60)
                h, m = divmod(m, 60)
                d_str = f"{h}h {m}m" if h > 0 else f"{m}m {s}s"
            else:
                d_str = "In progress"
            d_item = QTableWidgetItem(d_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.sessions_table.setItem(row, 2, d_item)

            score = session.get('posture_score')
            if score is not None:
                s_item = QTableWidgetItem(f"{score:.0f}")
                s_item.setTextAlignment(Qt.AlignCenter)
                if score >= 80:
                    s_item.setForeground(QColor("#5a9a6a"))
                elif score >= 60:
                    s_item.setForeground(QColor("#b08030"))
                else:
                    s_item.setForeground(QColor("#c04050"))
            else:
                s_item = QTableWidgetItem("-")
                s_item.setTextAlignment(Qt.AlignCenter)
            self.sessions_table.setItem(row, 3, s_item)

            status = "Done" if session.get('end_time') else "Active"
            st_item = QTableWidgetItem(status)
            st_item.setTextAlignment(Qt.AlignCenter)
            self.sessions_table.setItem(row, 4, st_item)

            info_btn = QPushButton("Details")
            info_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
            info_btn.clicked.connect(lambda checked, s=session: self._show_details(s))
            self.sessions_table.setCellWidget(row, 5, info_btn)

    def _show_details(self, session):
        dialog = SessionDetailDialog(session, self.db, self)
        dialog.exec()
