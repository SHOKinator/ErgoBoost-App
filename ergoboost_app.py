# ergoboost_app.py
"""
ErgoBoost - Main Application Launcher
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gui.main_window import main

if __name__ == "__main__":
    main()