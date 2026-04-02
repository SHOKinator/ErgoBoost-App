# utils/performance_monitor.py
"""
Performance monitoring utilities
"""

import time
import psutil
from collections import deque
from typing import Dict


class PerformanceMonitor:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
        self.process = psutil.Process()
        self.start_time = time.time()

    def record_frame_time(self, frame_time: float):
        self.frame_times.append(frame_time)

    def get_fps(self) -> float:
        if not self.frame_times:
            return 0.0
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0.0

    def get_metrics(self) -> Dict:
        cpu_percent = self.process.cpu_percent()
        memory_info = self.process.memory_info()
        uptime = time.time() - self.start_time
        return {
            'fps': self.get_fps(),
            'cpu_percent': cpu_percent,
            'memory_mb': memory_info.rss / 1024 / 1024,
            'uptime_seconds': uptime
        }
