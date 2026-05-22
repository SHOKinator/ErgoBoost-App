# test/collect_posture_data.py
"""
Real posture data collector for testing ML models.

Controls:
    B  — set label to BAD  (sit with bad posture)
    O  — set label to OK   (sit with good posture)
    Q  — quit and save

Flow:
    1. Calibration phase (5 seconds) — sit in your normal good posture
    2. Collection phase — switch between OK/BAD with keyboard
    3. Data saved to test/posture_test_data.csv
"""

import sys
import csv
import cv2
import math
import time
import numpy as np
from pathlib import Path
from collections import deque
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ============================================================
#  НАСТРОЙКИ — менять здесь
# ============================================================
LOG_INTERVAL = 1.0          # запись в CSV каждые N секунд
CALIBRATION_DURATION = 5.0  # длительность калибровки (сек)
MIN_CALIBRATION_SAMPLES = 30
SMOOTHING_WINDOW = 8
OUTPUT_CSV = Path(__file__).parent / "posture_test_data.csv"

# Landmark indices (same as project)
L_EAR, R_EAR = 8, 7
L_SHOULDER, R_SHOULDER = 12, 11


def calculate_forward_shift(landmarks, buffer):
    """Same formula as services/pose_detector.py"""
    le, re = landmarks[L_EAR], landmarks[R_EAR]
    ls, rs = landmarks[L_SHOULDER], landmarks[R_SHOULDER]

    if min(le.visibility, re.visibility, ls.visibility, rs.visibility) < 0.3:
        return None

    ear_center_z = (le.z + re.z) * 0.5
    shoulder_center_z = (ls.z + rs.z) * 0.5
    shoulder_width = abs(ls.x - rs.x)

    if shoulder_width < 1e-4:
        return None

    raw = (ear_center_z - shoulder_center_z) / shoulder_width
    buffer.append(raw)
    return sum(buffer) / len(buffer)


def calculate_lateral_tilt(landmarks, buffer):
    """Same formula as services/pose_detector.py"""
    ls, rs = landmarks[L_SHOULDER], landmarks[R_SHOULDER]

    if min(ls.visibility, rs.visibility) < 0.3:
        return None

    dx = rs.x - ls.x
    dy = rs.y - ls.y
    raw = math.degrees(math.atan2(dy, dx))
    buffer.append(raw)
    return sum(buffer) / len(buffer)


def main():
    print("=" * 60)
    print("  ErgoBoost — Real Posture Data Collector")
    print("=" * 60)
    print()
    print("Controls:")
    print("  O — label = OK   (good posture)")
    print("  B — label = BAD  (bad posture)")
    print("  Q — quit and save")
    print()

    # --- Load MediaPipe Pose ---
    pose_options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(
            model_asset_path=str(project_root / "models" / "pose_landmarker_lite.task")
        ),
        output_segmentation_masks=False,
    )
    pose_detector = vision.PoseLandmarker.create_from_options(pose_options)

    # --- Open camera ---
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open camera!")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # --- Smoothing buffers ---
    fwd_buffer = deque(maxlen=SMOOTHING_WINDOW)
    tilt_buffer = deque(maxlen=SMOOTHING_WINDOW)

    # ==========================================================
    #  PHASE 1: CALIBRATION
    # ==========================================================
    print("\n[CALIBRATION] Sit in your normal comfortable posture...")
    print(f"  Collecting baseline for {CALIBRATION_DURATION} seconds...\n")

    cal_samples = []
    cal_start = time.time()

    while time.time() - cal_start < CALIBRATION_DURATION:
        ret, frame = cap.read()
        if not ret:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = pose_detector.detect(mp_image)

        if result.pose_landmarks:
            lm = result.pose_landmarks[0]
            fwd = calculate_forward_shift(lm, fwd_buffer)
            tilt = calculate_lateral_tilt(lm, tilt_buffer)
            if fwd is not None and tilt is not None:
                cal_samples.append({'forward_shift': fwd, 'lateral_tilt': tilt})

        elapsed = time.time() - cal_start
        progress = min(1.0, elapsed / CALIBRATION_DURATION)
        bar = "█" * int(progress * 30) + "░" * (30 - int(progress * 30))
        cv2.putText(frame, f"CALIBRATING... {progress*100:.0f}%", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 255), 2)
        cv2.imshow("ErgoBoost Collector", frame)
        cv2.waitKey(1)

    if len(cal_samples) < MIN_CALIBRATION_SAMPLES:
        print(f"ERROR: Only {len(cal_samples)} samples collected. Need {MIN_CALIBRATION_SAMPLES}.")
        cap.release()
        cv2.destroyAllWindows()
        return

    # Compute baseline (median)
    baseline_fwd = float(np.median([s['forward_shift'] for s in cal_samples]))
    baseline_tilt = float(np.median([s['lateral_tilt'] for s in cal_samples]))

    print(f"  Baseline computed from {len(cal_samples)} samples:")
    print(f"    forward_shift = {baseline_fwd:.4f}")
    print(f"    lateral_tilt  = {baseline_tilt:.2f}°")

    # Reset smoothing buffers after calibration
    fwd_buffer.clear()
    tilt_buffer.clear()

    # ==========================================================
    #  PHASE 2: DATA COLLECTION
    # ==========================================================
    print("\n[COLLECTING] Press O for OK, B for BAD, Q to quit")
    print("  Start in OK pose. Press B when you switch to bad posture.\n")

    # =============================================
    #  ТЕКУЩАЯ МЕТКА — менять кнопками O / B
    # =============================================
    current_label = "OK"

    # Deviation weights (same as baseline_calibrator.py)
    WEIGHT_FWD = 1.5
    WEIGHT_TILT = 1.0

    # Prepare CSV
    csv_fields = [
        'timestamp', 'forward_shift', 'lateral_tilt',
        'deviation_fwd', 'deviation_tilt',
        'shift_abs', 'tilt_abs', 'shift_x_tilt',
        'severity', 'true_label'
    ]

    rows_collected = []
    last_log_time = 0
    ok_count = 0
    bad_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = pose_detector.detect(mp_image)

        fwd = None
        tilt = None

        if result.pose_landmarks:
            lm = result.pose_landmarks[0]
            fwd = calculate_forward_shift(lm, fwd_buffer)
            tilt = calculate_lateral_tilt(lm, tilt_buffer)

        now = time.time()

        # Log every LOG_INTERVAL seconds
        if fwd is not None and tilt is not None and (now - last_log_time) >= LOG_INTERVAL:
            last_log_time = now

            # Compute deviations from baseline (same as baseline_calibrator.py)
            raw_dev_fwd = fwd - baseline_fwd
            raw_dev_tilt = tilt - baseline_tilt
            if abs(raw_dev_fwd) < 0.01:
                raw_dev_fwd = 0
            if abs(raw_dev_tilt) < 0.01:
                raw_dev_tilt = 0

            dev_fwd = raw_dev_fwd * WEIGHT_FWD
            dev_tilt = raw_dev_tilt * WEIGHT_TILT

            shift_abs = abs(dev_fwd)
            tilt_abs_val = abs(dev_tilt)
            shift_x_tilt = shift_abs * tilt_abs_val

            # Severity (same as pose_detector evaluate_posture)
            severity = 0.0
            if abs(dev_fwd) > 0.1:
                severity += abs(dev_fwd) / 0.1
            if abs(dev_tilt) > 5.0:
                severity += abs(dev_tilt) / 5.0

            row = {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
                'forward_shift': round(dev_fwd, 6),
                'lateral_tilt': round(dev_tilt, 4),
                'deviation_fwd': round(dev_fwd, 6),
                'deviation_tilt': round(dev_tilt, 4),
                'shift_abs': round(shift_abs, 6),
                'tilt_abs': round(tilt_abs_val, 4),
                'shift_x_tilt': round(shift_x_tilt, 6),
                'severity': round(severity, 4),
                'true_label': current_label,
            }
            rows_collected.append(row)

            if current_label == "OK":
                ok_count += 1
            else:
                bad_count += 1

        # === Display ===
        label_color = (0, 200, 0) if current_label == "OK" else (0, 0, 230)
        cv2.putText(frame, f"Label: {current_label}", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, label_color, 3)
        cv2.putText(frame, f"Samples: {len(rows_collected)} (OK={ok_count}, BAD={bad_count})",
                    (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

        if fwd is not None:
            dev_display = fwd - baseline_fwd
            cv2.putText(frame, f"fwd_dev: {dev_display:.4f}", (30, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
        if tilt is not None:
            dev_display = tilt - baseline_tilt
            cv2.putText(frame, f"tilt_dev: {dev_display:.2f}", (30, 170),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        cv2.putText(frame, "O=OK  B=BAD  Q=Quit", (30, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (140, 140, 140), 1)

        cv2.imshow("ErgoBoost Collector", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('o') or key == ord('O'):
            current_label = "OK"
            print(f"  >>> Label switched to OK  (samples: {len(rows_collected)})")
        elif key == ord('b') or key == ord('B'):
            current_label = "BAD"
            print(f"  >>> Label switched to BAD (samples: {len(rows_collected)})")
        elif key == ord('q') or key == ord('Q'):
            break

    # ==========================================================
    #  SAVE CSV
    # ==========================================================
    cap.release()
    cv2.destroyAllWindows()

    if not rows_collected:
        print("\nNo data collected!")
        return

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(rows_collected)

    print(f"\n{'=' * 60}")
    print(f"  Data saved to: {OUTPUT_CSV}")
    print(f"  Total samples: {len(rows_collected)}")
    print(f"  OK: {ok_count}, BAD: {bad_count}")
    print(f"  Baseline: fwd={baseline_fwd:.4f}, tilt={baseline_tilt:.2f}°")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
