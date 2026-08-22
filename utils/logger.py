# utils/logger.py
"""
Logging configuration for ErgoBoost
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str, log_file: Path = None) -> logging.Logger:
    """Setup logger with console and file handlers"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    if log_file is None:
        from utils.path_helper import get_writable_path
        log_dir = get_writable_path("logs")
        log_file = log_dir / f"ergoboost_{datetime.now().strftime('%Y%m%d')}.log"

    # Make sure directory containing the log file exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger
