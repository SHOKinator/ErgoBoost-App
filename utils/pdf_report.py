# utils/pdf_report.py
"""
PDF report generator for ErgoBoost.
Uses matplotlib PdfPages — no extra dependencies.
"""

import numpy as np
from pathlib import Path
from datetime import datetime, timezone

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from data.sqlite_repo import SQLiteRepository
from utils.logger import setup_logger

logger = setup_logger(__name__)

BG = '#0f0f14'
TEXT = '#8a8a9a'
GRID = '#1e1e2a'
BLUE = '#6c8cff'
GREEN = '#5a9a6a'
RED = '#c04050'
ORANGE = '#b08030'
WHITE = '#e0e0ee'


def _style_ax(ax):
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT, labelsize=8)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    for sp in ('bottom', 'left'):
        ax.spines[sp].set_color(GRID)


def generate_pdf_report(db: SQLiteRepository, user_id: int, days: int,
                        output_path: Path) -> Path:
    """
    Generate a multi-page PDF report for the given period.
    Returns the path to the generated PDF file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sessions = db.get_historical_data(days=days, user_id=user_id)

    session_dates = []
    session_scores = []
    session_durations = []
    good_posture_pcts = []
    blink_rates = []

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
        good_posture_pcts.append(ps.get('good_posture_percent', 0))
        blink_rates.append(es.get('avg_blink_rate', 0))

    total_sessions = len(session_dates)
    avg_score = np.mean(session_scores) if session_scores else 0
    avg_good = np.mean(good_posture_pcts) if good_posture_pcts else 0
    avg_duration = np.mean(session_durations) if session_durations else 0
    avg_blink = np.mean(blink_rates) if blink_rates else 0
    total_time = sum(session_durations)

    with PdfPages(str(output_path)) as pdf:
        # === Page 1: Title + Summary ===
        fig = plt.figure(figsize=(8.5, 11), facecolor='white')

        fig.text(0.5, 0.92, 'ErgoBoost — Posture Report',
                 ha='center', fontsize=24, fontweight='bold', color='#2a2a3a')

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        fig.text(0.5, 0.88, f'Generated: {now_str}  |  Period: last {days} days',
                 ha='center', fontsize=11, color='#6a6a7a')

        # Summary table
        summary_data = [
            ['Total Sessions', str(total_sessions)],
            ['Total Monitoring Time', f'{total_time:.0f} min'],
            ['Avg Session Duration', f'{avg_duration:.0f} min'],
            ['Avg Posture Score', f'{avg_score:.1f} / 100'],
            ['Avg Good Posture', f'{avg_good:.1f}%'],
            ['Avg Blink Rate', f'{avg_blink:.1f} /min'],
        ]

        ax_table = fig.add_axes([0.15, 0.55, 0.7, 0.28])
        ax_table.axis('off')
        table = ax_table.table(
            cellText=summary_data,
            colLabels=['Metric', 'Value'],
            cellLoc='center',
            loc='center',
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1, 2)
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor('#d0d0d0')
            if row == 0:
                cell.set_facecolor('#4a6adf')
                cell.set_text_props(color='white', fontweight='bold')
            else:
                cell.set_facecolor('#f8f8fc' if row % 2 == 0 else 'white')

        # Score assessment
        if avg_score >= 80:
            assessment = "Excellent posture habits! Keep it up."
            a_color = '#3a8a5a'
        elif avg_score >= 60:
            assessment = "Good progress, but there's room for improvement."
            a_color = '#b08030'
        else:
            assessment = "Your posture needs attention. Consider adjusting your workspace."
            a_color = '#c04050'

        fig.text(0.5, 0.48, assessment,
                 ha='center', fontsize=13, color=a_color, fontstyle='italic')

        pdf.savefig(fig)
        plt.close(fig)

        if not session_dates:
            logger.info(f"PDF report saved to {output_path} (no session data)")
            return output_path

        # === Page 2: Score Trend ===
        fig, axes = plt.subplots(2, 1, figsize=(8.5, 11), facecolor='white')

        axes[0].plot(session_dates, session_scores, color='#4a6adf',
                     linewidth=2, marker='o', markersize=5)
        axes[0].fill_between(session_dates, session_scores, alpha=0.15, color='#4a6adf')
        axes[0].set_ylabel('Score', fontsize=10)
        axes[0].set_title('Posture Score Trend', fontsize=14, fontweight='600', pad=12)
        axes[0].set_ylim(0, 105)
        axes[0].axhline(y=80, color='#3a8a5a', linestyle='--', alpha=0.4, linewidth=1)
        axes[0].grid(True, alpha=0.15)
        plt.setp(axes[0].xaxis.get_majorticklabels(), rotation=30, ha='right')

        # Good posture bars
        x = range(len(session_dates))
        date_labels = [d.strftime('%m/%d') for d in session_dates]
        colors = ['#3a8a5a' if v >= 80 else '#b08030' if v >= 60 else '#c04050'
                  for v in good_posture_pcts]
        axes[1].bar(x, good_posture_pcts, color=colors, width=0.6)
        axes[1].set_ylabel('Good Posture %', fontsize=10)
        axes[1].set_title('Good Posture Percentage per Session', fontsize=14,
                          fontweight='600', pad=12)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(date_labels, rotation=30, ha='right')
        axes[1].set_ylim(0, 105)
        axes[1].grid(True, alpha=0.15, axis='y')

        plt.tight_layout(pad=3)
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 3: Duration + Blink Rate ===
        fig, axes = plt.subplots(2, 1, figsize=(8.5, 11), facecolor='white')

        axes[0].bar(x, session_durations, color='#4a6adf', alpha=0.7, width=0.6)
        axes[0].set_ylabel('Duration (min)', fontsize=10)
        axes[0].set_title('Session Duration', fontsize=14, fontweight='600', pad=12)
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(date_labels, rotation=30, ha='right')
        axes[0].grid(True, alpha=0.15, axis='y')

        axes[1].plot(session_dates, blink_rates, color='#b08030', linewidth=2,
                     marker='s', markersize=4)
        axes[1].axhspan(10, 25, alpha=0.08, color='#3a8a5a')
        axes[1].axhline(y=15, color='#3a8a5a', linestyle='--', alpha=0.4)
        axes[1].set_ylabel('Blinks/min', fontsize=10)
        axes[1].set_title('Average Blink Rate per Session', fontsize=14,
                          fontweight='600', pad=12)
        axes[1].grid(True, alpha=0.15)
        plt.setp(axes[1].xaxis.get_majorticklabels(), rotation=30, ha='right')

        plt.tight_layout(pad=3)
        pdf.savefig(fig)
        plt.close(fig)

    logger.info(f"PDF report saved to {output_path}")
    return output_path
