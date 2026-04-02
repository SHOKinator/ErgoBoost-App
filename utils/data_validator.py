# utils/data_validator.py
"""
Data validation utilities
"""

from typing import Optional, Tuple


def validate_ear(ear: float) -> bool:
    return 0.0 <= ear <= 1.0


def validate_forward_shift(shift: Optional[float]) -> bool:
    if shift is None:
        return True
    return -1.0 <= shift <= 1.0


def validate_lateral_tilt(tilt: Optional[float]) -> bool:
    if tilt is None:
        return True
    return -90.0 <= tilt <= 90.0


def validate_distance_ratio(ratio: float) -> bool:
    return 0.0 <= ratio <= 1.0


def validate_metrics(metrics: dict) -> Tuple[bool, str]:
    if metrics.get('ear') is not None and not validate_ear(metrics['ear']):
        return False, "Invalid EAR value"
    if not validate_forward_shift(metrics.get('forward_shift')):
        return False, "Invalid forward shift value"
    if not validate_lateral_tilt(metrics.get('lateral_tilt')):
        return False, "Invalid lateral tilt value"
    if metrics.get('distance_ratio') is not None and not validate_distance_ratio(metrics['distance_ratio']):
        return False, "Invalid distance ratio value"
    return True, "Valid"
