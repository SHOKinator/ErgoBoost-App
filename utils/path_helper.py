# utils/path_helper.py
"""
Path helper for ErgoBoost.
Handles path resolution in development and frozen environments (PyInstaller).
"""

import sys
from pathlib import Path

def get_resource_path(relative_path: str | Path) -> Path:
    """Get absolute path to read-only resource bundled in the .exe.
    
    For PyInstaller, resources are extracted to sys._MEIPASS.
    For normal Python running, they are relative to the project root.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller temporary extraction folder
        base_path = Path(sys._MEIPASS)
    else:
        # Project root directory (parent of utils folder)
        base_path = Path(__file__).resolve().parent.parent
    
    return base_path / relative_path

def get_writable_path(relative_path: str | Path) -> Path:
    """Get absolute path to writable files/folders.
    
    For PyInstaller, we write next to the executable (portable mode), 
    as sys._MEIPASS is read-only.
    For normal Python running, we write relative to the project root.
    """
    if getattr(sys, 'frozen', False):
        # Folder containing the compiled .exe file
        base_path = Path(sys.executable).resolve().parent
    else:
        # Project root directory
        base_path = Path(__file__).resolve().parent.parent
    
    path = base_path / relative_path
    # Automatically ensure folders exist. If the path has no file suffix, 
    # treat it as a directory and create it directly; otherwise, create its parent.
    if path.suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        path.mkdir(parents=True, exist_ok=True)
    return path

