# test/evaluate_model.py
"""
Script to evaluate trained ML model on manually collected real posture data.
Generates performance metrics and visual reports.

Usage:
    python test/evaluate_model.py
"""

import sys
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DATA_FILE = Path(__file__).parent / "posture_test_data.csv"
MODEL_FILE = project_root / "ml" / "models" / "posture_classifier.pkl"
OUTPUT_DIR = Path(__file__).parent / "results"

def load_model():
    if not MODEL_FILE.exists():
        print(f"ERROR: Model file not found at {MODEL_FILE}")
        print("Please train the model first using: python -m ml.train_model")
        return None, None
    
    with open(MODEL_FILE, 'rb') as f:
        data = pickle.load(f)
        
    return data['model'], data['scaler']

def main():
    print("=" * 60)
    print("  ErgoBoost — ML Model Evaluation on Real Data")
    print("=" * 60)
    
    if not DATA_FILE.exists():
        print(f"ERROR: Test data not found at {DATA_FILE}")
        print("Please run 'python test/collect_posture_data.py' first to collect data.")
        return
        
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load data
    df = pd.read_csv(DATA_FILE)
    print(f"\nLoaded {len(df)} samples from {DATA_FILE.name}")
    print(f"Class distribution:\n{df['true_label'].value_counts()}")
    
    # Convert labels: OK -> 0, BAD -> 1
    y_true = (df['true_label'] == 'BAD').astype(int)
    
    # Load model
    model, scaler = load_model()
    if model is None:
        return
        
    print(f"\nModel loaded successfully.")
    
    # Prepare features
    # Features required by the model: forward_shift, lateral_tilt, shift_abs, tilt_abs, shift_x_tilt
    # We use the deviation fields from our test data as they represent the shift from baseline
    features = [
        'deviation_fwd',
        'deviation_tilt',
        'shift_abs',
        'tilt_abs',
        'shift_x_tilt'
    ]
    
    X = df[features].values
    
    # Scale features
    X_scaled = scaler.transform(X)
    
    # Predict
    y_pred = model.predict(X_scaled)
    y_prob = model.predict_proba(X_scaled)[:, 1] if hasattr(model, "predict_proba") else None
    
    df['predicted_label'] = np.where(y_pred == 1, 'BAD', 'OK')
    
    # Calculate metrics
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    
    print("\n" + "=" * 60)
    print("  Evaluation Results")
    print("=" * 60)
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=['OK', 'BAD']))
    
    # ==========================================
    # Generate Visualizations
    # ==========================================
    sns.set_theme(style="whitegrid")
    
    # 1. Confusion Matrix
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=['OK', 'BAD'], yticklabels=['OK', 'BAD'])
    plt.title('Confusion Matrix on Real Data')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    cm_path = OUTPUT_DIR / "confusion_matrix.png"
    plt.savefig(cm_path)
    print(f"\nSaved confusion matrix to {cm_path}")
    
    # 2. Timeline Plot
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, y_true, label='True Label (1=BAD, 0=OK)', 
             marker='o', linestyle='', alpha=0.5, color='blue')
    plt.plot(df.index, y_pred + 0.05, label='Predicted Label (offset)', 
             marker='x', linestyle='', alpha=0.5, color='red')
    
    if y_prob is not None:
        plt.plot(df.index, y_prob, label='BAD Probability', color='orange', alpha=0.3)
        plt.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
        
    plt.title('Prediction Timeline')
    plt.xlabel('Sample Index (Time)')
    plt.ylabel('Class / Probability')
    plt.yticks([0, 0.5, 1], ['OK (0)', '0.5', 'BAD (1)'])
    plt.legend()
    plt.tight_layout()
    tl_path = OUTPUT_DIR / "timeline.png"
    plt.savefig(tl_path)
    print(f"Saved timeline plot to {tl_path}")
    
    # 3. Feature Distribution (BAD vs OK)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    sns.kdeplot(data=df, x='deviation_fwd', hue='true_label', 
                common_norm=False, fill=True, ax=axes[0])
    axes[0].set_title('Forward Shift Distribution')
    
    sns.kdeplot(data=df, x='deviation_tilt', hue='true_label', 
                common_norm=False, fill=True, ax=axes[1])
    axes[1].set_title('Lateral Tilt Distribution')
    
    plt.tight_layout()
    dist_path = OUTPUT_DIR / "feature_distributions.png"
    plt.savefig(dist_path)
    print(f"Saved feature distributions to {dist_path}")
    
    # 4. Feature Importance
    if hasattr(model, 'feature_importances_'):
        plt.figure(figsize=(8, 5))
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        sns.barplot(x=importances[indices], y=np.array(features)[indices], 
                    hue=np.array(features)[indices], palette="viridis", legend=False)
        plt.title('Feature Importances')
        plt.xlabel('Relative Importance')
        plt.ylabel('Feature')
        plt.tight_layout()
        feat_path = OUTPUT_DIR / "feature_importance.png"
        plt.savefig(feat_path)
        print(f"Saved feature importance plot to {feat_path}")
        
    # 5. ROC Curve
    if y_prob is not None:
        from sklearn.metrics import roc_curve, auc
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        roc_auc = auc(fpr, tpr)
        
        plt.figure(figsize=(7, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.2f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC)')
        plt.legend(loc="lower right")
        plt.tight_layout()
        roc_path = OUTPUT_DIR / "roc_curve.png"
        plt.savefig(roc_path)
        print(f"Saved ROC curve plot to {roc_path}")

    # 6. Scatter Plot (Decision Boundary Visualization)
    plt.figure(figsize=(9, 7))
    sns.scatterplot(data=df, x='deviation_fwd', y='deviation_tilt', hue='true_label', 
                    style='predicted_label', palette={'OK': 'green', 'BAD': 'red'}, s=80, alpha=0.7)
    
    # Draw simple baseline threshold lines for visual context
    plt.axvline(x=0.1, color='gray', linestyle='--', alpha=0.5)
    plt.axvline(x=-0.1, color='gray', linestyle='--', alpha=0.5)
    plt.axhline(y=5.0, color='gray', linestyle='--', alpha=0.5)
    plt.axhline(y=-5.0, color='gray', linestyle='--', alpha=0.5)
    
    plt.title('Forward Shift vs Lateral Tilt (True vs Predicted)')
    plt.xlabel('Forward Shift (Deviation)')
    plt.ylabel('Lateral Tilt (Deviation)')
    plt.tight_layout()
    scatter_path = OUTPUT_DIR / "decision_scatter.png"
    plt.savefig(scatter_path)
    print(f"Saved decision scatter plot to {scatter_path}")

    # 7. Metrics Table Image
    plt.figure(figsize=(6, 3))
    plt.axis('off')
    metrics_data = [
        ['Accuracy', f"{acc:.4f}"],
        ['Precision', f"{prec:.4f}"],
        ['Recall', f"{rec:.4f}"],
        ['F1 Score', f"{f1:.4f}"]
    ]
    table = plt.table(cellText=metrics_data, colLabels=['Metric', 'Value'], loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(14)
    table.scale(1, 2)
    
    # Style the table
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('#d0d0d0')
        if row == 0:
            cell.set_facecolor('#4a6adf')
            cell.set_text_props(color='white', fontweight='bold')
        else:
            cell.set_facecolor('#f8f8fc' if row % 2 == 0 else 'white')
            
    plt.title('Model Performance Metrics', fontsize=16, pad=20, fontweight='bold')
    plt.tight_layout()
    metrics_path = OUTPUT_DIR / "metrics_table.png"
    plt.savefig(metrics_path)
    print(f"Saved metrics table to {metrics_path}")

    print("\nEvaluation complete! Check the 'results' folder for plots.")

if __name__ == "__main__":
    main()
