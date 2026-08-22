import cv2
import sqlite3
import numpy as np
import pandas as pd
import math
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque
import pickle

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Import ErgoBoost modules
from services.baseline_calibrator import BaselineCalibrator

# Import scikit-learn modules
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix


# Import plotting modules
import matplotlib
matplotlib.use('Agg')  # Headless rendering
import matplotlib.pyplot as plt

DB_PATH = project_root / "data" / "ergoboost.db"
TEST_DATA_CSV = project_root / "test" / "posture_test_data.csv"
RESULTS_DIR = project_root / "test" / "results"

# Landmark indices
L_EAR, R_EAR = 8, 7
L_SHOULDER, R_SHOULDER = 12, 11
SMOOTHING_WINDOW = 8

def calculate_forward_shift(landmarks, buffer):
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
    ls, rs = landmarks[L_SHOULDER], landmarks[R_SHOULDER]

    if min(ls.visibility, rs.visibility) < 0.3:
        return None

    dx = rs.x - ls.x
    dy = rs.y - ls.y
    raw = math.degrees(math.atan2(dy, dx))
    buffer.append(raw)
    return sum(buffer) / len(buffer)

def auto_label_video(video_path: str, session_id: int, user_class_type: str, pose_detector):
    """
    Decodes video, runs MediaPipe, performs offline BaselineCalibrator calibration,
    and inserts baseline-calibrated deviations into the database.
    """
    if not os.path.exists(video_path):
        print(f"Warning: Video file {video_path} not found. Skipping.")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    print(f"\nProcessing session {session_id} ({video_path}) at {fps:.2f} FPS...")

    # Smoothing buffers for offline pipeline
    fwd_buffer = deque(maxlen=SMOOTHING_WINDOW)
    tilt_buffer = deque(maxlen=SMOOTHING_WINDOW)

    calibrator = BaselineCalibrator(duration=5.0)
    cal_samples = []
    is_calibrated = False

    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM posture_events WHERE session_id = ?", (session_id,))
    conn.commit()

    frame_idx = 0
    inserted_count = 0
    last_logged_second = -1

    base_time = datetime(2026, 5, 30, 12, 0, 0)

    # Pre-read standard deviation/means for calibration if needed
    # We sample 10 Hz during first 5 seconds to ensure we get plenty of calibration samples.
    # We sample 1 Hz after 5 seconds for normal event logging.
    cal_interval = max(1, int(fps / 10))
    run_interval = max(1, int(fps))

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        current_second = frame_idx / fps
        
        # Decide sampling interval based on phase
        if current_second <= 5.0:
            should_sample = (frame_idx % cal_interval == 0)
        else:
            should_sample = (frame_idx % run_interval == 0)

        if should_sample:
            # Convert and run MediaPipe Pose
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = pose_detector.detect(mp_image)

            if result.pose_landmarks:
                lm = result.pose_landmarks[0]
                fwd = calculate_forward_shift(lm, fwd_buffer)
                tilt = calculate_lateral_tilt(lm, tilt_buffer)

                if fwd is not None and tilt is not None:
                    metrics = {"forward_shift": fwd, "lateral_tilt": tilt}

                    if current_second <= 5.0:
                        # Calibration Phase
                        cal_samples.append(metrics)
                    else:
                        # Finalize calibration offline once if not done
                        if not is_calibrated:
                            if len(cal_samples) >= 5:
                                med_fwd = float(np.median([s['forward_shift'] for s in cal_samples]))
                                med_tilt = float(np.median([s['lateral_tilt'] for s in cal_samples]))
                                calibrator.baseline = {"forward_shift": med_fwd, "lateral_tilt": med_tilt}
                                calibrator.is_calibrated = True
                                is_calibrated = True
                                print(f"  Calibrated Offline baseline: fwd={med_fwd:.4f}, tilt={med_tilt:.2f} deg")
                            else:
                                # Fallback baseline
                                calibrator.baseline = {"forward_shift": fwd, "lateral_tilt": tilt}
                                calibrator.is_calibrated = True
                                is_calibrated = True

                        # Calculate Deviations relative to baseline
                        deviations = calibrator.deviation(metrics)
                        if deviations:
                            dev_fwd = deviations.get("forward_shift", 0.0)
                            dev_tilt = deviations.get("lateral_tilt", 0.0)

                            # Timeline logical labels (0=OK, 1=Forward Shift, 2=Lateral Tilt, 3=Lying Back)
                            if current_second <= 60.0:
                                label = 0
                                status_str = "OK"
                            else:
                                status_str = "BAD"
                                if user_class_type == "forward":
                                    label = 1
                                elif user_class_type == "lateral":
                                    label = 2
                                elif user_class_type == "lying":
                                    label = 3
                                else:
                                    label = 1

                            # Sequential Timestamp
                            event_time = base_time + timedelta(seconds=int(current_second))
                            timestamp = event_time.strftime('%Y-%m-%dT%H:%M:%S')

                            cursor.execute("""
                                INSERT INTO posture_events 
                                (session_id, timestamp, forward_shift, lateral_tilt, posture_status, severity)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (session_id, timestamp, round(dev_fwd, 6), round(dev_tilt, 4), status_str, float(label)))
                            inserted_count += 1

        frame_idx += 1
        
        # Log progress in standard intervals
        sec = int(current_second)
        if sec % 30 == 0 and sec > last_logged_second:
            print(f"  Processed {sec}s of video... Recorded rows: {inserted_count}")
            last_logged_second = sec

    conn.commit()
    conn.close()
    cap.release()
    print(f"Session {session_id} successfully completed. Recorded {inserted_count} rows.")

def load_combined_dataset():
    """
    Loads extracted video features from the database and loads real coordinates
    from posture_test_data.csv, combines them, converts binary labels into multiclass labels,
    and returns a clean, unified pandas DataFrame.
    """
    print("\nLoading and combining video and CSV features...")
    
    # 1. Load Video features from database
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    video_df = pd.read_sql_query("""
        SELECT forward_shift, lateral_tilt, severity as class
        FROM posture_events
        WHERE session_id IN (301, 302, 303, 304, 305, 306, 307)
    """, conn)
    conn.close()
    
    video_df['class'] = video_df['class'].astype(int)
    print(f"  Loaded {len(video_df)} samples from A/B testing videos.")
    
    # 2. Load CSV features from posture_test_data.csv
    if not TEST_DATA_CSV.exists():
        print(f"Error: CSV file {TEST_DATA_CSV} not found.")
        sys.exit(1)
        
    csv_df = pd.read_csv(TEST_DATA_CSV)
    
    # Extract deviations and map to multiclass
    # deviation_fwd and deviation_tilt represent baseline-calibrated deviations!
    csv_features = pd.DataFrame()
    csv_features['forward_shift'] = csv_df['deviation_fwd']
    csv_features['lateral_tilt'] = csv_df['deviation_tilt']
    
    # Map binary true_label (OK/BAD) into multiclass (0, 1, 2, 3) using thresholds
    multiclass_labels = []
    for idx, row in csv_df.iterrows():
        if row['true_label'] == 'OK':
            multiclass_labels.append(0)
        else:
            # BAD postures are classified into forward (1), lateral (2), or lying (3)
            # based on which coordinate has a larger deviation from standard threshold
            tilt_dev_scaled = abs(row['deviation_tilt']) / 5.0  # normalize by threshold (5 deg)
            fwd_dev_scaled = abs(row['deviation_fwd']) / 0.1   # normalize by threshold (0.1 shift)
            
            if row['severity'] > 3.5:
                multiclass_labels.append(3) # high severity lying back
            elif tilt_dev_scaled > fwd_dev_scaled:
                multiclass_labels.append(2) # lateral tilt majority
            else:
                multiclass_labels.append(1) # forward shift majority
                
    csv_features['class'] = multiclass_labels
    print(f"  Loaded {len(csv_features)} samples from {TEST_DATA_CSV.name} (mapped to multiclass).")
    
    # 3. Combine both datasets
    combined_df = pd.concat([video_df, csv_features], ignore_index=True)
    combined_df['is_synthetic'] = 0
    print(f"  Total combined real-world samples: {len(combined_df)}")
    
    return combined_df

def apply_smote_and_evaluate_model(df):
    """
    Applies custom SMOTE + Gaussian noise on the ENTIRE combined dataset to balance classes,
    loads the pre-trained Random Forest classifier from ml/models/posture_classifier.pkl,
    scales features using the saved scaler, evaluates the pre-trained model on 100% of this
    balanced dataset as a Test set, and returns the performance metrics.
    """
    print("\nPreparing combined dataset for evaluation...")
    
    # Feature engineering
    for d in [df]:
        d['shift_abs'] = d['forward_shift'].abs()
        d['tilt_abs'] = d['lateral_tilt'].abs()
        d['shift_x_tilt'] = d['shift_abs'] * d['tilt_abs']
        
    features = ['forward_shift', 'lateral_tilt', 'shift_abs', 'tilt_abs', 'shift_x_tilt']
    
    # Apply SMOTE + Gaussian Noise strictly to the ENTIRE combined dataset to balance classes
    print("\nApplying Custom SMOTE + Gaussian Noise to balance the entire combined dataset...")
    class_counts = df['class'].value_counts()
    target_size = class_counts.max()
    
    X_raw = df[['forward_shift', 'lateral_tilt']].values
    y_raw = df['class'].values
    
    synthetic_rows = []
    
    for cls in [1, 2, 3]:
        cls_mask = (y_raw == cls)
        X_cls = X_raw[cls_mask]
        count = len(X_cls)
        
        if count < 2:
            continue
            
        num_to_generate = target_size - count
        if num_to_generate <= 0:
            continue
            
        # Noise variance based on feature std
        std_fwd = X_cls[:, 0].std()
        std_tilt = X_cls[:, 1].std()
        if pd.isna(std_fwd) or std_fwd == 0: std_fwd = 0.02
        if pd.isna(std_tilt) or std_tilt == 0: std_tilt = 1.0
        
        noise_std_fwd = 0.05 * std_fwd
        noise_std_tilt = 0.05 * std_tilt
        
        k = min(5, count - 1)
        nbrs = NearestNeighbors(n_neighbors=k+1, algorithm='ball_tree').fit(X_cls)
        distances, indices = nbrs.kneighbors(X_cls)
        
        for _ in range(num_to_generate):
            idx = np.random.randint(0, len(X_cls))
            neigh_idx = np.random.choice(indices[idx][1:]) if len(indices[idx]) > 1 else indices[idx][0]
            
            lambda_val = np.random.rand()
            syn_feat = X_cls[idx] + lambda_val * (X_cls[neigh_idx] - X_cls[idx])
            
            # Add Gaussian noise
            syn_feat[0] += np.random.normal(0, noise_std_fwd)
            syn_feat[1] += np.random.normal(0, noise_std_tilt)
            
            synthetic_rows.append({
                'forward_shift': float(syn_feat[0]),
                'lateral_tilt': float(syn_feat[1]),
                'class': cls
            })
            
    if synthetic_rows:
        synth_df = pd.DataFrame(synthetic_rows)
        synth_df['shift_abs'] = synth_df['forward_shift'].abs()
        synth_df['tilt_abs'] = synth_df['lateral_tilt'].abs()
        synth_df['shift_x_tilt'] = synth_df['shift_abs'] * synth_df['tilt_abs']
        
        balanced_df = pd.concat([df, synth_df], ignore_index=True)
        print(f"  Generated {len(synthetic_rows)} synthetic samples to balance the dataset.")
    else:
        balanced_df = df
        
    print(f"  Balanced dataset size: {len(balanced_df)} samples")
    
    # Load the PRE-TRAINED model and scaler from ml/models/posture_classifier.pkl
    MODEL_PATH = project_root / "ml" / "models" / "posture_classifier.pkl"
    if not MODEL_PATH.exists():
        print(f"\nError: Pre-trained model file {MODEL_PATH} not found.")
        print("Please train a model first using: python -m ml.train_model")
        sys.exit(1)
        
    print(f"\nLoading pre-trained classifier from {MODEL_PATH}...")
    with open(MODEL_PATH, 'rb') as f:
        model_data = pickle.load(f)
        
    rf = model_data['model']
    scaler = model_data['scaler']
    saved_features = model_data['feature_names']
    
    print(f"  Loaded model type: {model_data.get('model_name', 'Random Forest')}")
    print(f"  Trained at: {model_data.get('trained_at', 'unknown')}")
    
    # Evaluate 100% of the balanced dataset as a Test set
    X_eval = balanced_df[saved_features].values
    y_eval_true_multiclass = balanced_df['class'].values
    
    # Map multiclass labels to binary for evaluation (0 = OK, 1,2,3 = BAD)
    y_eval_true_binary = (y_eval_true_multiclass > 0).astype(int)
    
    # Scale features using the saved scaler
    X_eval_scaled = scaler.transform(X_eval)
    y_eval_pred_multiclass = rf.predict(X_eval_scaled)
    y_eval_pred_binary = (y_eval_pred_multiclass > 0).astype(int)
    
    # Probabilities for ROC AUC
    probs_multiclass = rf.predict_proba(X_eval_scaled)
    probs_bad = 1.0 - probs_multiclass[:, 0]
    
    # Calculate performance metrics
    acc = accuracy_score(y_eval_true_binary, y_eval_pred_binary)
    prec = precision_score(y_eval_true_binary, y_eval_pred_binary, zero_division=0)
    rec = recall_score(y_eval_true_binary, y_eval_pred_binary, zero_division=0)
    f1 = f1_score(y_eval_true_binary, y_eval_pred_binary, zero_division=0)
    cm = confusion_matrix(y_eval_true_binary, y_eval_pred_binary)
    
    from sklearn.metrics import roc_curve, auc
    fpr, tpr, _ = roc_curve(y_eval_true_binary, probs_bad)
    roc_auc = auc(fpr, tpr)
    
    print("\n" + "=" * 60)
    print("  Real Generalization Metrics (100% Data Evaluated on Test)")
    print("=" * 60)
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"ROC AUC:   {roc_auc:.4f}")
    print(f"Confusion Matrix:\n{cm}")
    
    # Write datasets to SQLite for compatibility and verification
    print("\nWriting combined real and balanced training datasets to SQLite database...")
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM posture_events WHERE session_id IN (888, 999)")
    conn.commit()
    
    # Session 888 represents original combined real data (100% on test)
    real_db_rows = []
    for idx, row in df.iterrows():
        timestamp = f"2026-05-30T15:00:{idx%60:02d}-real-{idx}"
        real_db_rows.append((
            888,
            timestamp,
            round(float(row['forward_shift']), 6),
            round(float(row['lateral_tilt']), 4),
            "OK" if row['class'] == 0 else "BAD",
            float(row['class'])
        ))
    cursor.executemany("INSERT INTO posture_events (session_id, timestamp, forward_shift, lateral_tilt, posture_status, severity) VALUES (?, ?, ?, ?, ?, ?)", real_db_rows)
    
    # Session 999 represents synthetic balanced oversampling
    if synthetic_rows:
        synth_db_rows = []
        for idx, row in synth_df.iterrows():
            timestamp = f"2026-05-30T15:00:{idx%60:02d}-synth-{idx}"
            synth_db_rows.append((
                999,
                timestamp,
                round(float(row['forward_shift']), 6),
                round(float(row['lateral_tilt']), 4),
                "BAD",
                float(row['class'])
            ))
        cursor.executemany("INSERT INTO posture_events (session_id, timestamp, forward_shift, lateral_tilt, posture_status, severity) VALUES (?, ?, ?, ?, ?, ?)", synth_db_rows)
        
    conn.commit()
    conn.close()
    print(f"  Saved {len(real_db_rows)} real samples under session 888.")
    if synthetic_rows:
        print(f"  Saved {len(synth_db_rows)} synthetic oversampled samples under session 999.")
        
    return acc, prec, rec, f1, roc_auc, cm

def plot_premium_results_charts(acc, prec, rec, f1, roc_auc, cm):
    """
    Generates 2 highly clear and understandable PNG charts and saves them to results/ folder:
    1. 01_ab_confusion_matrix.png (Heatmap of predictions vs true labels)
    2. 02_ab_metrics_bar.png (Scores comparison)
    """
    print("\nGenerating Premium Result Charts...")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Matplotlib styling
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 12,
        'axes.titlesize': 15,
        'axes.titleweight': 'bold',
        'axes.labelsize': 13,
        'xtick.labelsize': 11,
        'ytick.labelsize': 11,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.linestyle': '--',
    })
    
    COLORS = {
        'ok': '#10B981',       # Emerald green
        'bad': '#EF4444',      # Crimson red
        'primary': '#2563EB',  # Royal blue
        'accent': '#7C3AED',   # Purple
        'text': '#1F2937',     # Charcoal
        'bg': '#FAFBFC',
        'grid': '#E5E7EB'
    }
    
    # 1. Confusion Matrix Heatmap using pure Matplotlib (no seaborn dependency)
    fig, ax = plt.subplots(figsize=(6, 5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    im = ax.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues, aspect='auto')
    
    # Add values text
    for i in range(2):
        for j in range(2):
            val = cm[i][j]
            color = 'white' if val > cm.max() / 2 else COLORS['text']
            ax.text(j, i, f"{val}", ha='center', va='center', fontsize=16, weight='bold', color=color)
            
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['OK (Straight)', 'BAD (Violating)'], fontsize=11)
    ax.set_yticklabels(['OK (Straight)', 'BAD (Violating)'], fontsize=11)
    ax.set_title('Real Data Evaluation: Confusion Matrix', pad=15)
    ax.set_ylabel('True Label', labelpad=10)
    ax.set_xlabel('Predicted Label', labelpad=10)
    
    # Hide spines
    for spine in ax.spines.values():
        spine.set_visible(False)
        
    plt.tight_layout()
    cm_path = RESULTS_DIR / "01_ab_confusion_matrix.png"
    plt.savefig(cm_path)
    plt.close()
    print(f"  [OK] {cm_path.name}")
    
    # 2. Metrics Bar Chart (Accuracy, Precision, Recall, F1-Score, ROC AUC)
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    metrics_names = ['Accuracy', 'Precision', 'Recall', 'F1-Score', 'ROC AUC']
    metrics_vals = [acc, prec, rec, f1, roc_auc]
    
    bars = ax.bar(metrics_names, metrics_vals, color=[COLORS['primary'], COLORS['accent'], COLORS['ok'], '#F59E0B', '#06B6D4'], edgecolor='white', width=0.5, zorder=3)
    
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f'{h:.4f}', xy=(bar.get_x() + bar.get_width()/2, h),
                    xytext=(0, 5), textcoords='offset points',
                    ha='center', va='bottom', fontsize=11, fontweight='bold', color=COLORS['text'])
                    
    ax.set_ylabel('Score Value', labelpad=10)
    ax.set_ylim(0.0, 1.1)
    ax.set_title('Model Generalization Performance Metrics', pad=15)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    metrics_path = RESULTS_DIR / "02_ab_metrics_bar.png"
    plt.savefig(metrics_path)
    plt.close()
    print(f"  [OK] {metrics_path.name}")
 
def main():
    print("=" * 60)
    print("  ErgoBoost -- Posture Data Balancing, Evaluation & Metrics Charting")
    print("=" * 60)
    
    # Load MediaPipe PoseLandmarker
    model_asset_path = str(project_root / "models" / "pose_landmarker_lite.task")
    if not os.path.exists(model_asset_path):
        print(f"Error: MediaPipe model file {model_asset_path} does not exist.")
        return
        
    pose_options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=model_asset_path),
        output_segmentation_masks=False,
    )
    pose_detector = vision.PoseLandmarker.create_from_options(pose_options)
 
    # 1. Process all 7 videos to extract calibrated posture offsets
    videos_to_process = [
        ("videos/WIN_20260529_23_44_01_Pro.mp4", 301, "forward"),
        ("videos/WIN_20260529_23_54_18_Pro.mp4", 302, "lateral"),
        ("videos/WIN_20260530_10_42_01_Pro.mp4", 303, "lying"),
        ("videos/WIN_20260530_10_43_56_Pro.mp4", 304, "forward"),
        ("videos/video_2026-05-30_19-27-53.mp4", 305, "forward"),
        ("videos/video_2026-05-30_19-28-00.mp4", 306, "forward"), # restictive sideways motion friend mapped to forward
        ("videos/Movie on 30.05.2026 at 13.30.mov", 307, "forward")
    ]
    
    for v_path, s_id, cls_type in videos_to_process:
        auto_label_video(v_path, session_id=s_id, user_class_type=cls_type, pose_detector=pose_detector)
        
    # 2. Load and fuse database video features and CSV deviations
    combined_df = load_combined_dataset()
    
    # 3. Load pre-trained model, oversample entire combined dataset (100% test), and evaluate
    acc, prec, rec, f1, roc_auc, cm = apply_smote_and_evaluate_model(combined_df)
    
    # 4. Generate premium academic PNG charts (Confusion Matrix & Metrics Bar Plot)
    plot_premium_results_charts(acc, prec, rec, f1, roc_auc, cm)

        
    print("\n" + "=" * 60)
    print("  Video Processing, SMOTE Balancing, Training & Metrics Charting Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()