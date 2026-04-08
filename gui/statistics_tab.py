# gui/statistics_tab.py
"""
Statistics tab - Analytics with matplotlib charts.
Uses SQLite directly for reliable operation. PySpark available via export.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QGridLayout, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap, QImage
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from data.sqlite_repo import SQLiteRepository

BG = '#0f0f14'
CARD_BG = '#16161e'
GRID = '#1e1e2a'
TEXT = '#8a8a9a'
BLUE = '#6c8cff'
GREEN = '#5a9a6a'
RED = '#c04050'
ORANGE = '#b08030'


def _fig_to_pixmap(fig):
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    buf = canvas.buffer_rgba()
    arr = np.asarray(buf)
    h, w, ch = arr.shape
    qimg = QImage(arr.data, w, h, ch * w, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class StatsWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, db_path, days, user_id=0):
        super().__init__()
        self.db_path = Path(db_path)
        self.days = days
        self.user_id = user_id

    def run(self):
        try:
            db = SQLiteRepository(self.db_path)
            sessions = db.get_historical_data(days=self.days, user_id=self.user_id)

            session_scores = []
            session_dates = []
            session_durations = []
            total_good_posture = []
            total_blink_rates = []

            for s in sessions:
                if not s.get('end_time'):
                    continue
                sid = s['id']
                ps = db.get_posture_statistics(sid)
                es = db.get_eye_statistics(sid)

                dt = datetime.fromisoformat(s['start_time'])
                session_dates.append(dt)
                session_scores.append(s.get('posture_score') or 0)
                session_durations.append((s.get('duration_seconds') or 0) / 60)
                total_good_posture.append(ps.get('good_posture_percent', 0))
                total_blink_rates.append(es.get('avg_blink_rate', 0))

            # Generate charts
            charts = {}

            if session_dates:
                # Score trend
                fig, ax = plt.subplots(figsize=(9, 3), facecolor=BG)
                ax.set_facecolor(BG)
                ax.tick_params(colors=TEXT, labelsize=8)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_color(GRID)
                ax.spines['left'].set_color(GRID)

                ax.plot(session_dates, session_scores, color=BLUE, linewidth=1.5, marker='o', markersize=4)
                ax.fill_between(session_dates, session_scores, alpha=0.1, color=BLUE)
                ax.set_ylabel('Score', color=TEXT, fontsize=9)
                ax.set_title('Posture Score Trend', color='#c8c8d8', fontsize=11, fontweight='600')
                ax.set_ylim(0, 105)
                plt.xticks(rotation=30, ha='right')
                plt.tight_layout()
                charts['score_trend'] = _fig_to_pixmap(fig)
                plt.close(fig)

                # Duration + Good posture bars
                fig, ax1 = plt.subplots(figsize=(9, 3), facecolor=BG)
                ax1.set_facecolor(BG)
                ax1.tick_params(colors=TEXT, labelsize=8)
                ax1.spines['top'].set_visible(False)
                ax1.spines['right'].set_visible(False)
                ax1.spines['bottom'].set_color(GRID)
                ax1.spines['left'].set_color(GRID)

                x = range(len(session_dates))
                date_labels = [d.strftime('%m/%d') for d in session_dates]
                bars = ax1.bar(x, session_durations, color=BLUE, alpha=0.6, width=0.6)
                ax1.set_ylabel('Duration (min)', color=TEXT, fontsize=9)
                ax1.set_title('Session Duration', color='#c8c8d8', fontsize=11, fontweight='600')
                ax1.set_xticks(x)
                ax1.set_xticklabels(date_labels, rotation=30, ha='right')

                plt.tight_layout()
                charts['duration'] = _fig_to_pixmap(fig)
                plt.close(fig)

                # Good posture % trend
                fig, ax = plt.subplots(figsize=(9, 3), facecolor=BG)
                ax.set_facecolor(BG)
                ax.tick_params(colors=TEXT, labelsize=8)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['bottom'].set_color(GRID)
                ax.spines['left'].set_color(GRID)

                colors = [GREEN if v >= 80 else ORANGE if v >= 60 else RED for v in total_good_posture]
                ax.bar(x, total_good_posture, color=colors, width=0.6)
                ax.set_ylabel('Good Posture %', color=TEXT, fontsize=9)
                ax.set_title('Good Posture Percentage per Session', color='#c8c8d8', fontsize=11, fontweight='600')
                ax.set_xticks(x)
                ax.set_xticklabels(date_labels, rotation=30, ha='right')
                ax.set_ylim(0, 105)

                plt.tight_layout()
                charts['posture_pct'] = _fig_to_pixmap(fig)
                plt.close(fig)

            # Summary stats
            summary = {
                'total_sessions': len(sessions),
                'avg_score': np.mean(session_scores) if session_scores else 0,
                'avg_good_posture': np.mean(total_good_posture) if total_good_posture else 0,
                'avg_duration': np.mean(session_durations) if session_durations else 0,
                'avg_blink_rate': np.mean(total_blink_rates) if total_blink_rates else 0,
                'total_time': sum(session_durations),
            }

            db.close()
            self.finished.emit({'charts': charts, 'summary': summary})
        except Exception as e:
            self.error.emit(str(e))


class StatisticsTab(QWidget):
    def __init__(self, settings, user_id: int = 0):
        super().__init__()
        self.settings = settings
        self.user_id = user_id
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Statistics")
        title.setFont(QFont("Segoe UI", 20, QFont.DemiBold))
        title.setStyleSheet("color: #e0e0ee;")
        header.addWidget(title)
        header.addStretch()

        self.period_combo = QComboBox()
        self.period_combo.addItems(["7 days", "30 days", "90 days", "365 days"])
        self.period_combo.setCurrentText("30 days")
        self.period_combo.setMinimumWidth(100)
        self.period_combo.currentTextChanged.connect(lambda _: self.refresh_statistics())
        header.addWidget(self.period_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMinimumSize(80, 34)
        refresh_btn.clicked.connect(self.refresh_statistics)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(12)
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _clear_content(self):
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def refresh_statistics(self):
        if self.worker and self.worker.isRunning():
            return

        self._clear_content()
        loading = QLabel("Loading...")
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet("color: #6a6a7a; padding: 40px; font-size: 14px;")
        self.content_layout.addWidget(loading)

        days = int(self.period_combo.currentText().split()[0])
        db_path = self.settings.get('db_path', 'data/ergoboost.db')

        self.worker = StatsWorker(db_path, days, user_id=self.user_id)
        self.worker.finished.connect(self._display)
        self.worker.error.connect(self._show_error)
        self.worker.start()

    def _display(self, result):
        self._clear_content()

        summary = result['summary']
        charts = result['charts']

        # Summary cards
        cards_frame = QFrame()
        cards_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        cards_layout = QGridLayout(cards_frame)
        cards_layout.setSpacing(10)

        card_data = [
            ("Sessions", str(summary['total_sessions']), BLUE),
            ("Avg Score", f"{summary['avg_score']:.0f}",
             GREEN if summary['avg_score'] >= 80 else RED),
            ("Avg Good Posture", f"{summary['avg_good_posture']:.0f}%",
             GREEN if summary['avg_good_posture'] >= 80 else ORANGE),
            ("Avg Duration", f"{summary['avg_duration']:.0f} min", BLUE),
            ("Avg Blink Rate", f"{summary['avg_blink_rate']:.1f}/min",
             GREEN if 10 <= summary['avg_blink_rate'] <= 25 else ORANGE),
            ("Total Time", f"{summary['total_time']:.0f} min", BLUE),
        ]

        for i, (label, value, color) in enumerate(card_data):
            card = self._make_card(label, value, color)
            cards_layout.addWidget(card, i // 3, i % 3)

        self.content_layout.addWidget(cards_frame)

        # Charts
        for key in ['score_trend', 'posture_pct', 'duration']:
            if key in charts:
                lbl = QLabel()
                lbl.setPixmap(charts[key])
                lbl.setAlignment(Qt.AlignCenter)
                self.content_layout.addWidget(lbl)

        self.content_layout.addStretch()

    def _make_card(self, label, value, color):
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background-color: {CARD_BG}; border: 1px solid {GRID}; border-radius: 4px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)

        v = QLabel(value)
        v.setFont(QFont("Segoe UI", 20, QFont.Bold))
        v.setStyleSheet(f"color: {color}; border: none;")
        v.setAlignment(Qt.AlignCenter)
        lay.addWidget(v)

        l = QLabel(label)
        l.setStyleSheet(f"color: {TEXT}; font-size: 11px; border: none;")
        l.setAlignment(Qt.AlignCenter)
        lay.addWidget(l)
        return card

    def _show_error(self, msg):
        self._clear_content()
        err = QLabel(f"Error: {msg}")
        err.setStyleSheet("color: #c04050; padding: 40px;")
        err.setWordWrap(True)
        self.content_layout.addWidget(err)
