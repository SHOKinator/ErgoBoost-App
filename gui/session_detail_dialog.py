# gui/session_detail_dialog.py
"""
Session detail dialog with charts and comprehensive analytics
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QGridLayout, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QImage
from datetime import datetime
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg


# Chart colors
BG_COLOR = '#0f0f14'
CARD_BG = '#16161e'
GRID_COLOR = '#1e1e2a'
TEXT_COLOR = '#8a8a9a'
ACCENT_BLUE = '#6c8cff'
ACCENT_GREEN = '#5a9a6a'
ACCENT_RED = '#c04050'
ACCENT_ORANGE = '#b08030'


def _fig_to_pixmap(fig):
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    buf = canvas.buffer_rgba()
    arr = np.asarray(buf)
    h, w, ch = arr.shape
    qimg = QImage(arr.data, w, h, ch * w, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class SessionDetailDialog(QDialog):
    def __init__(self, session, db, parent=None):
        super().__init__(parent)
        self.session = session
        self.db = db
        self.setWindowTitle(f"Session #{session['id']}")
        self.setMinimumSize(960, 720)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._create_overview_tab(), "Overview")
        tabs.addTab(self._create_posture_chart_tab(), "Posture")
        tabs.addTab(self._create_eye_chart_tab(), "Eyes")
        tabs.addTab(self._create_distance_chart_tab(), "Distance")
        layout.addWidget(tabs)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(export_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _create_header(self):
        header = QFrame()
        layout = QHBoxLayout(header)

        info_layout = QVBoxLayout()
        title = QLabel(f"Session #{self.session['id']}")
        title.setFont(QFont("Segoe UI", 16, QFont.DemiBold))
        title.setStyleSheet("color: #e0e0ee;")
        info_layout.addWidget(title)

        start = datetime.fromisoformat(self.session['start_time'])
        sub = f"{start.strftime('%Y-%m-%d  %H:%M')}"
        if self.session.get('duration_seconds'):
            m = int(self.session['duration_seconds'] / 60)
            sub += f"  ·  {m} min"
        sub_label = QLabel(sub)
        sub_label.setStyleSheet("color: #6a6a7a; font-size: 12px;")
        info_layout.addWidget(sub_label)
        layout.addLayout(info_layout)
        layout.addStretch()

        score = self.session.get('posture_score')
        if score is not None:
            sc_color = ACCENT_GREEN if score >= 80 else ACCENT_ORANGE if score >= 60 else ACCENT_RED
            score_label = QLabel(f"{score:.0f}")
            score_label.setFont(QFont("Segoe UI", 28, QFont.Bold))
            score_label.setStyleSheet(f"color: {sc_color};")
            layout.addWidget(score_label)

            sc_sub = QLabel("/100")
            sc_sub.setStyleSheet("color: #6a6a7a; font-size: 14px;")
            layout.addWidget(sc_sub)

        return header

    def _create_overview_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        layout = QGridLayout(content)
        layout.setSpacing(12)

        sid = self.session['id']
        ps = self.db.get_posture_statistics(sid)
        es = self.db.get_eye_statistics(sid)
        ds = self.db.get_distance_statistics(sid)
        prs = self.db.get_presence_statistics(sid)

        cards = [
            ("Good Posture", f"{ps['good_posture_percent']:.0f}%",
             ACCENT_GREEN if ps['good_posture_percent'] >= 80 else ACCENT_RED),
            ("Avg Severity", f"{ps['avg_severity']:.2f}",
             ACCENT_GREEN if ps['avg_severity'] < 1 else ACCENT_RED),
            ("Blink Rate", f"{es['avg_blink_rate']:.1f}/min",
             ACCENT_GREEN if 10 <= es['avg_blink_rate'] <= 25 else ACCENT_ORANGE),
            ("Eye Fatigue", f"{es['fatigue_percent']:.0f}%",
             ACCENT_GREEN if es['fatigue_percent'] < 10 else ACCENT_RED),
            ("Distance OK", f"{ds['distance_ok_percent']:.0f}%",
             ACCENT_GREEN if ds['distance_ok_percent'] >= 80 else ACCENT_ORANGE),
            ("Active Time", f"{prs['active_seconds']/60:.0f} min", ACCENT_BLUE),
            ("Breaks", str(prs['break_count']), ACCENT_BLUE),
            ("Posture Events", str(ps['total_events']), ACCENT_BLUE),
        ]

        for i, (label, value, color) in enumerate(cards):
            card = self._make_card(label, value, color)
            layout.addWidget(card, i // 4, i % 4)

        scroll.setWidget(content)
        return scroll

    def _make_card(self, label, value, color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {GRID_COLOR};
                border-radius: 4px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)

        v = QLabel(value)
        v.setFont(QFont("Segoe UI", 22, QFont.Bold))
        v.setStyleSheet(f"color: {color}; border: none;")
        v.setAlignment(Qt.AlignCenter)
        lay.addWidget(v)

        l = QLabel(label)
        l.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 11px; border: none;")
        l.setAlignment(Qt.AlignCenter)
        lay.addWidget(l)
        return card

    def _create_posture_chart_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        timeline = self.db.get_posture_timeline(self.session['id'])
        if not timeline:
            layout.addWidget(QLabel("No posture data available"))
            return widget

        timestamps = []
        severities = []
        fwd_shifts = []
        tilts = []
        for ev in timeline:
            try:
                t = datetime.fromisoformat(ev['timestamp'])
                timestamps.append(t)
                severities.append(ev['severity'] or 0)
                fwd_shifts.append(ev['forward_shift'] or 0)
                tilts.append(ev['lateral_tilt'] or 0)
            except:
                continue

        if not timestamps:
            layout.addWidget(QLabel("No valid posture data"))
            return widget

        # Severity timeline
        fig, axes = plt.subplots(2, 1, figsize=(9, 5), facecolor=BG_COLOR)

        for ax in axes:
            ax.set_facecolor(BG_COLOR)
            ax.tick_params(colors=TEXT_COLOR, labelsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color(GRID_COLOR)
            ax.spines['left'].set_color(GRID_COLOR)

        axes[0].fill_between(timestamps, severities, alpha=0.3, color=ACCENT_RED)
        axes[0].plot(timestamps, severities, color=ACCENT_RED, linewidth=1)
        axes[0].set_ylabel('Severity', color=TEXT_COLOR, fontsize=9)
        axes[0].set_title('Posture Severity Over Time', color='#c8c8d8', fontsize=11, fontweight='600')

        axes[1].plot(timestamps, fwd_shifts, color=ACCENT_BLUE, linewidth=1, label='Forward')
        axes[1].plot(timestamps, tilts, color=ACCENT_ORANGE, linewidth=1, label='Tilt')
        axes[1].set_ylabel('Value', color=TEXT_COLOR, fontsize=9)
        axes[1].legend(fontsize=8, facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)

        plt.tight_layout()
        pixmap = _fig_to_pixmap(fig)
        plt.close(fig)

        chart_label = QLabel()
        chart_label.setPixmap(pixmap)
        chart_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(chart_label)
        layout.addStretch()
        return widget

    def _create_eye_chart_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        timeline = self.db.get_eye_timeline(self.session['id'])
        if not timeline:
            layout.addWidget(QLabel("No eye data available"))
            return widget

        timestamps = []
        blink_rates = []
        ears = []
        for ev in timeline:
            try:
                t = datetime.fromisoformat(ev['timestamp'])
                timestamps.append(t)
                blink_rates.append(ev.get('blink_rate_per_min') or 0)
                ears.append(ev.get('ear') or 0)
            except:
                continue

        if not timestamps:
            layout.addWidget(QLabel("No valid eye data"))
            return widget

        fig, axes = plt.subplots(2, 1, figsize=(9, 5), facecolor=BG_COLOR)
        for ax in axes:
            ax.set_facecolor(BG_COLOR)
            ax.tick_params(colors=TEXT_COLOR, labelsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color(GRID_COLOR)
            ax.spines['left'].set_color(GRID_COLOR)

        axes[0].plot(timestamps, blink_rates, color=ACCENT_BLUE, linewidth=1)
        axes[0].axhline(y=15, color=ACCENT_GREEN, linestyle='--', alpha=0.5, linewidth=0.8)
        axes[0].fill_between(timestamps, 10, 25, alpha=0.05, color=ACCENT_GREEN)
        axes[0].set_ylabel('Blinks/min', color=TEXT_COLOR, fontsize=9)
        axes[0].set_title('Blink Rate Over Time', color='#c8c8d8', fontsize=11, fontweight='600')

        axes[1].plot(timestamps, ears, color=ACCENT_ORANGE, linewidth=1)
        axes[1].set_ylabel('EAR', color=TEXT_COLOR, fontsize=9)
        axes[1].set_title('Eye Aspect Ratio', color='#c8c8d8', fontsize=11, fontweight='600')

        plt.tight_layout()
        pixmap = _fig_to_pixmap(fig)
        plt.close(fig)

        chart_label = QLabel()
        chart_label.setPixmap(pixmap)
        chart_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(chart_label)
        layout.addStretch()
        return widget

    def _create_distance_chart_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        timeline = self.db.get_distance_timeline(self.session['id'])
        if not timeline:
            layout.addWidget(QLabel("No distance data available"))
            return widget

        timestamps = []
        ratios = []
        for ev in timeline:
            try:
                t = datetime.fromisoformat(ev['timestamp'])
                timestamps.append(t)
                ratios.append(ev.get('distance_ratio') or 0)
            except:
                continue

        if not timestamps:
            layout.addWidget(QLabel("No valid distance data"))
            return widget

        fig, ax = plt.subplots(1, 1, figsize=(9, 3), facecolor=BG_COLOR)
        ax.set_facecolor(BG_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color(GRID_COLOR)
        ax.spines['left'].set_color(GRID_COLOR)

        ax.plot(timestamps, ratios, color=ACCENT_BLUE, linewidth=1)
        ax.set_ylabel('Face Size Ratio', color=TEXT_COLOR, fontsize=9)
        ax.set_title('Screen Distance Over Time', color='#c8c8d8', fontsize=11, fontweight='600')

        plt.tight_layout()
        pixmap = _fig_to_pixmap(fig)
        plt.close(fig)

        chart_label = QLabel()
        chart_label.setPixmap(pixmap)
        chart_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(chart_label)
        layout.addStretch()
        return widget

    def _export_csv(self):
        from utils.export_utils import export_session_to_csv
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox
        try:
            output_dir = Path(f"exports/session_{self.session['id']}")
            export_session_to_csv(self.db, self.session['id'], output_dir)
            QMessageBox.information(self, "Exported", f"Saved to {output_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
