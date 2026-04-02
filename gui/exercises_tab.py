# gui/exercises_tab.py
"""
Exercises tab - Ergonomic exercises and tips
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


EXERCISES = {
    "Eye Exercises": [
        ("20-20-20 Rule",
         "Every 20 minutes, look at something 20 feet away for 20 seconds."),
        ("Eye Rolling",
         "Slowly roll your eyes in a circle. 10 times clockwise, 10 counterclockwise."),
        ("Focus Change",
         "Focus on your finger a few inches away, then something far away. Repeat 10 times."),
        ("Palming",
         "Rub hands together, place warm palms over closed eyes for 30 seconds."),
        ("Rapid Blinking",
         "Blink rapidly for a few seconds, then close eyes and rest. Repeat 3-4 times."),
    ],
    "Posture Exercises": [
        ("Shoulder Rolls",
         "Roll shoulders backward in circles. 10 repetitions."),
        ("Neck Stretches",
         "Tilt head to each side, hold 15 seconds. 3 times per side."),
        ("Chin Tucks",
         "Pull chin back towards neck. Hold 5 seconds, repeat 10 times."),
        ("Upper Back Stretch",
         "Clasp hands in front, push away, round upper back. Hold 20 seconds."),
        ("Chest Opener",
         "Clasp hands behind back, straighten arms, lift slightly. Hold 20 seconds."),
    ],
}

TIPS = [
    "Monitor at arm's length (50-65 cm)",
    "Top of screen at or slightly below eye level",
    "Feet flat on the floor",
    "Knees at approximately 90 degrees",
    "Lower back supported",
    "Take regular breaks — stand and move",
    "Adjust lighting to reduce screen glare",
    "Keep shoulders relaxed",
    "Wrists straight when typing",
    "Stay hydrated",
]


class ExercisesTab(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Exercises & Tips")
        title.setFont(QFont("Segoe UI", 20, QFont.DemiBold))
        title.setStyleSheet("color: #e0e0ee;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(16)

        for section_title, exercises in EXERCISES.items():
            section = QFrame()
            section.setStyleSheet(
                "QFrame { background-color: #16161e; border: 1px solid #1e1e2a; border-radius: 4px; }"
            )
            s_layout = QVBoxLayout(section)
            s_layout.setContentsMargins(16, 14, 16, 14)
            s_layout.setSpacing(10)

            s_title = QLabel(section_title)
            s_title.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
            s_title.setStyleSheet("color: #c8c8d8; border: none;")
            s_layout.addWidget(s_title)

            for name, desc in exercises:
                n = QLabel(f"  {name}")
                n.setStyleSheet("color: #6c8cff; font-weight: 600; font-size: 12px; border: none;")
                s_layout.addWidget(n)

                d = QLabel(f"    {desc}")
                d.setWordWrap(True)
                d.setStyleSheet("color: #8a8a9a; font-size: 12px; margin-left: 16px; border: none;")
                s_layout.addWidget(d)

            c_layout.addWidget(section)

        # Tips
        tips_frame = QFrame()
        tips_frame.setStyleSheet(
            "QFrame { background-color: #16161e; border: 1px solid #1e1e2a; border-radius: 4px; }"
        )
        t_layout = QVBoxLayout(tips_frame)
        t_layout.setContentsMargins(16, 14, 16, 14)
        t_layout.setSpacing(6)

        t_title = QLabel("General Tips")
        t_title.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
        t_title.setStyleSheet("color: #c8c8d8; border: none;")
        t_layout.addWidget(t_title)

        for tip in TIPS:
            lbl = QLabel(f"  ·  {tip}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #8a8a9a; font-size: 12px; padding: 2px 0; border: none;")
            t_layout.addWidget(lbl)

        c_layout.addWidget(tips_frame)
        c_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
