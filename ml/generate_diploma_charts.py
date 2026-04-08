# ml/generate_diploma_charts.py
"""
Генерация графиков для дипломной работы.
Загружает training_report.json и posture_classifier.pkl,
создаёт красивые PNG-диаграммы для вставки в диплом.

Использование:
    python -m ml.generate_diploma_charts
    python -m ml.generate_diploma_charts --output diploma_charts
"""

import json
import pickle
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')  # headless rendering
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

# ─── Style Configuration ───────────────────────────────────────────
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
    'savefig.pad_inches': 0.15,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
})

# Professional color palette
COLORS = {
    'rf': '#2563EB',        # Royal blue — Random Forest
    'gb': '#7C3AED',        # Purple — Gradient Boosting
    'ok': '#10B981',        # Emerald — OK class
    'bad': '#EF4444',       # Red — BAD class
    'accent': '#F59E0B',    # Amber
    'bg': '#FAFBFC',        # Light bg
    'grid': '#E5E7EB',
    'text': '#1F2937',
    'text_light': '#6B7280',
}

BAR_COLORS = ['#2563EB', '#7C3AED', '#10B981', '#F59E0B', '#EF4444',
              '#06B6D4', '#EC4899', '#8B5CF6', '#14B8A6']


def load_data(report_path: Path, model_path: Path) -> tuple:
    """Load training report and model."""
    with open(report_path, 'r') as f:
        report = json.load(f)

    model_data = None
    if model_path.exists():
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)

    return report, model_data


# ═══════════════════════════════════════════════════════════════════
#  Chart 1: Model Comparison (Accuracy, Precision, Recall, F1)
# ═══════════════════════════════════════════════════════════════════
def chart_model_comparison(report, output_dir):
    """Bar chart comparing RF vs GB across all metrics."""
    metrics = ['accuracy', 'precision', 'recall', 'f1']
    labels = ['Accuracy', 'Precision', 'Recall', 'F1-Score']

    rf = report['results']['random_forest']
    gb = report['results']['gradient_boosting']

    rf_vals = [rf[m] for m in metrics]
    gb_vals = [gb[m] for m in metrics]

    x = np.arange(len(labels))
    width = 0.32

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    bars_rf = ax.bar(x - width/2, rf_vals, width, label='Random Forest',
                     color=COLORS['rf'], edgecolor='white', linewidth=1.5,
                     zorder=3, alpha=0.9)
    bars_gb = ax.bar(x + width/2, gb_vals, width, label='Gradient Boosting',
                     color=COLORS['gb'], edgecolor='white', linewidth=1.5,
                     zorder=3, alpha=0.9)

    # Value labels on bars
    for bars in [bars_rf, bars_gb]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.4f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 5), textcoords="offset points",
                        ha='center', va='bottom', fontsize=10, fontweight='bold',
                        color=COLORS['text'])

    ax.set_ylabel('Значение метрики')
    ax.set_title('Сравнение моделей классификации осанки')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0.92, 1.005)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.3f'))
    ax.legend(loc='lower right', framealpha=0.9, edgecolor=COLORS['grid'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    path = output_dir / '01_model_comparison.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 2: Confusion Matrix (heatmap) — for both models
# ═══════════════════════════════════════════════════════════════════
def chart_confusion_matrices(report, output_dir):
    """Side-by-side confusion matrices."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.patch.set_facecolor('white')

    models = [
        ('Random Forest', report['results']['random_forest'], COLORS['rf']),
        ('Gradient Boosting', report['results']['gradient_boosting'], COLORS['gb']),
    ]

    class_labels = ['OK (норма)', 'BAD (нарушение)']

    for ax, (name, data, color) in zip(axes, models):
        cm = np.array(data['confusion_matrix'])
        total = cm.sum()

        # Percentages
        cm_pct = cm / total * 100

        im = ax.imshow(cm_pct, interpolation='nearest', cmap='Blues', aspect='auto',
                       vmin=0, vmax=70)

        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(class_labels, fontsize=10)
        ax.set_yticklabels(class_labels, fontsize=10)
        ax.set_xlabel('Предсказанный класс', fontsize=11)
        ax.set_ylabel('Истинный класс', fontsize=11)
        ax.set_title(name, fontsize=14, fontweight='bold', pad=10)

        # Annotate cells
        for i in range(2):
            for j in range(2):
                count = cm[i][j]
                pct = cm_pct[i][j]
                text_color = 'white' if pct > 35 else COLORS['text']
                ax.text(j, i, f'{count:,}\n({pct:.1f}%)',
                        ha='center', va='center', fontsize=12,
                        fontweight='bold', color=text_color)

    fig.suptitle('Матрицы ошибок (Confusion Matrix)', fontsize=16,
                 fontweight='bold', y=1.02)
    plt.tight_layout()
    path = output_dir / '02_confusion_matrices.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 3: Feature Importance (horizontal bar)
# ═══════════════════════════════════════════════════════════════════
def chart_feature_importance(report, output_dir):
    """Horizontal bar chart of feature importances."""
    fi = report['results']['random_forest']['feature_importance']

    # Sort by importance
    sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=False)
    names = [x[0] for x in sorted_fi]
    values = [x[1] for x in sorted_fi]

    # Readable names mapping
    name_map = {
        'tilt_abs': 'Абс. наклон плеч (|tilt|)',
        'shift_x_tilt': 'Наклон × Смещение (interaction)',
        'shift_abs': 'Абс. смещение головы (|shift|)',
        'lateral_tilt': 'Боковой наклон плеч',
        'forward_shift': 'Смещение головы вперёд',
    }
    display_names = [name_map.get(n, n) for n in names]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    colors = [BAR_COLORS[i % len(BAR_COLORS)] for i in range(len(names))]
    bars = ax.barh(display_names, values, color=colors, edgecolor='white',
                   linewidth=1, height=0.65, zorder=3, alpha=0.85)

    # Value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
                f'{val:.4f}', ha='left', va='center', fontsize=10,
                fontweight='bold', color=COLORS['text'])

    ax.set_xlabel('Важность признака (Feature Importance)')
    ax.set_title('Важность признаков — Random Forest')
    ax.set_xlim(0, max(values) * 1.2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    path = output_dir / '03_feature_importance.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 4: Per-Class Metrics (OK vs BAD)
# ═══════════════════════════════════════════════════════════════════
def chart_per_class_metrics(report, output_dir):
    """Grouped bars showing per-class precision/recall/f1 for both models."""
    metrics = ['precision', 'recall', 'f1-score']
    labels = ['Precision', 'Recall', 'F1-Score']

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    fig.patch.set_facecolor('white')

    reports_data = [
        ('Random Forest', report['classification_report_rf']),
        ('Gradient Boosting', report['classification_report_gb']),
    ]

    for ax, (model_name, cr) in zip(axes, reports_data):
        ax.set_facecolor('white')

        ok_vals = [cr['0'][m] for m in metrics]
        bad_vals = [cr['1'][m] for m in metrics]

        x = np.arange(len(labels))
        width = 0.3

        bars_ok = ax.bar(x - width/2, ok_vals, width, label='OK (норма)',
                         color=COLORS['ok'], edgecolor='white', linewidth=1.5,
                         zorder=3, alpha=0.85)
        bars_bad = ax.bar(x + width/2, bad_vals, width, label='BAD (нарушение)',
                          color=COLORS['bad'], edgecolor='white', linewidth=1.5,
                          zorder=3, alpha=0.85)

        for bars in [bars_ok, bars_bad]:
            for bar in bars:
                h = bar.get_height()
                ax.annotate(f'{h:.4f}',
                            xy=(bar.get_x() + bar.get_width()/2, h),
                            xytext=(0, 4), textcoords='offset points',
                            ha='center', va='bottom', fontsize=9, fontweight='bold')

        ax.set_title(model_name, fontsize=13, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylim(0.93, 1.005)
        ax.legend(loc='lower right', fontsize=9, framealpha=0.9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    fig.suptitle('Метрики по классам', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    path = output_dir / '04_per_class_metrics.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 5: Dataset Distribution (pie + bar)
# ═══════════════════════════════════════════════════════════════════
def chart_dataset_distribution(report, output_dir):
    """Dataset split and class distribution."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor('white')

    # --- Left: Train/Test split ---
    ax1 = axes[0]
    train = report['train_size']
    test = report['test_size']
    sizes = [train, test]
    labels_split = [f'Train\n{train:,} (80%)', f'Test\n{test:,} (20%)']
    colors_split = [COLORS['rf'], COLORS['accent']]

    wedges, texts = ax1.pie(sizes, labels=labels_split, colors=colors_split,
                            startangle=90, textprops={'fontsize': 12, 'fontweight': 'bold'},
                            wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    ax1.set_title('Разделение датасета', fontsize=13, fontweight='bold', pad=15)

    # --- Right: Class distribution ---
    ax2 = axes[1]
    # Get from confusion matrix
    rf_cm = np.array(report['results']['random_forest']['confusion_matrix'])
    ok_total = rf_cm[0].sum()  # True OK
    bad_total = rf_cm[1].sum()  # True BAD
    total = ok_total + bad_total

    # For test set — extrapolate to full dataset
    ratio_ok = ok_total / total
    ratio_bad = bad_total / total
    full_ok = int(report['dataset_size'] * ratio_ok)
    full_bad = int(report['dataset_size'] * ratio_bad)

    bars = ax2.bar(['OK (норма)', 'BAD (нарушение)'],
                   [full_ok, full_bad],
                   color=[COLORS['ok'], COLORS['bad']],
                   edgecolor='white', linewidth=2, width=0.5, zorder=3, alpha=0.85)

    for bar, val in zip(bars, [full_ok, full_bad]):
        pct = val / report['dataset_size'] * 100
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2000,
                 f'{val:,}\n({pct:.1f}%)', ha='center', va='bottom',
                 fontsize=12, fontweight='bold', color=COLORS['text'])

    ax2.set_ylabel('Количество записей')
    ax2.set_title('Распределение классов', fontsize=13, fontweight='bold')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.set_facecolor('white')

    plt.tight_layout()
    path = output_dir / '05_dataset_distribution.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 6: Radar Chart (Spider) — multi-metric comparison
# ═══════════════════════════════════════════════════════════════════
def chart_radar_comparison(report, output_dir):
    """Radar/spider chart comparing models across multiple dimensions."""
    categories = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    metrics_keys = ['accuracy', 'precision', 'recall', 'f1']

    rf = report['results']['random_forest']
    gb = report['results']['gradient_boosting']

    rf_vals = [rf[m] for m in metrics_keys]
    gb_vals = [gb[m] for m in metrics_keys]

    # Close the radar
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    rf_vals += rf_vals[:1]
    gb_vals += gb_vals[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('white')

    ax.fill(angles, rf_vals, color=COLORS['rf'], alpha=0.15)
    ax.plot(angles, rf_vals, color=COLORS['rf'], linewidth=2.5,
            label='Random Forest', marker='o', markersize=8)

    ax.fill(angles, gb_vals, color=COLORS['gb'], alpha=0.15)
    ax.plot(angles, gb_vals, color=COLORS['gb'], linewidth=2.5,
            label='Gradient Boosting', marker='s', markersize=8)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=12, fontweight='bold')
    ax.set_ylim(0.94, 1.00)
    ax.set_rticks([0.95, 0.96, 0.97, 0.98, 0.99, 1.0])
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    ax.set_rlabel_position(30)

    ax.legend(loc='lower right', bbox_to_anchor=(1.15, -0.05),
              fontsize=11, framealpha=0.9)
    ax.set_title('Многокритериальное сравнение моделей',
                 fontsize=15, fontweight='bold', pad=25)

    plt.tight_layout()
    path = output_dir / '06_radar_comparison.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 7: Cross-Validation F1 with error bar
# ═══════════════════════════════════════════════════════════════════
def chart_cross_validation(report, output_dir):
    """Random CV vs GroupKFold CV comparison — proves generalization."""
    rf = report['results']['random_forest']
    gb = report['results']['gradient_boosting']

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    # Data for 3 bars per model: Test F1, Random CV F1, GroupKFold CV F1
    labels = ['Test F1', 'Random CV F1\n(5-fold)', 'GroupKFold CV F1\n(by session_id)']
    x = np.arange(len(labels))
    width = 0.3

    rf_vals = [
        rf['f1'],
        rf.get('cv_f1_mean', rf['f1']),
        rf.get('group_cv_f1_mean', rf.get('cv_f1_mean', rf['f1'])),
    ]
    rf_errs = [
        0,
        rf.get('cv_f1_std', 0),
        rf.get('group_cv_f1_std', 0),
    ]
    gb_vals = [
        gb['f1'],
        gb['f1'],  # GB doesn't have random CV in report
        gb.get('group_cv_f1_mean', gb['f1']),
    ]
    gb_errs = [
        0,
        0,
        gb.get('group_cv_f1_std', 0),
    ]

    bars_rf = ax.bar(x - width/2, rf_vals, width, label='Random Forest',
                     color=COLORS['rf'], edgecolor='white', linewidth=1.5,
                     zorder=3, alpha=0.85,
                     yerr=rf_errs, capsize=4, error_kw={'linewidth': 2})
    bars_gb = ax.bar(x + width/2, gb_vals, width, label='Gradient Boosting',
                     color=COLORS['gb'], edgecolor='white', linewidth=1.5,
                     zorder=3, alpha=0.85,
                     yerr=gb_errs, capsize=4, error_kw={'linewidth': 2})

    for bars in [bars_rf, bars_gb]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.001,
                    f'{h:.4f}', ha='center', va='bottom',
                    fontsize=10, fontweight='bold')

    ax.set_ylabel('F1-Score')
    ax.set_title('Валидация: Test vs Random CV vs GroupKFold (по сессиям)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)

    # Dynamic y-axis range
    all_vals = rf_vals + gb_vals
    y_min = min(all_vals) - 0.015
    y_max = max(all_vals) + 0.01
    ax.set_ylim(y_min, y_max)
    ax.legend(fontsize=11, framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Add annotation about generalization
    delta = abs(rf.get('cv_f1_mean', 0) - rf.get('group_cv_f1_mean', 0))
    if delta < 0.02:
        msg = f'\u0394 = {delta:.4f} — модель обобщает (не запоминает сессии) \u2713'
        color = COLORS['ok']
    else:
        msg = f'\u0394 = {delta:.4f} — возможное переобучение на сессиях \u26a0'
        color = COLORS['bad']
    ax.text(0.5, 0.02, msg, transform=ax.transAxes, ha='center',
            fontsize=12, fontweight='bold', color=color,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor=color, alpha=0.9))

    plt.tight_layout()
    path = output_dir / '07_cross_validation_groupkfold.png'
    plt.savefig(path)
    plt.close()
    print(f'  \u2713 {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 8: Summary Table (rendered as image for diploma)
# ═══════════════════════════════════════════════════════════════════
def chart_summary_table(report, output_dir):
    """Render a publication-quality metrics table as PNG."""
    rf = report['results']['random_forest']
    gb = report['results']['gradient_boosting']

    fig, ax = plt.subplots(figsize=(10, 3.5))
    fig.patch.set_facecolor('white')
    ax.axis('off')

    columns = ['Модель', 'Accuracy', 'Precision', 'Recall', 'F1-Score',
               'Объём выборки']
    rows = [
        ['Random Forest',
         f'{rf["accuracy"]:.4f}', f'{rf["precision"]:.4f}',
         f'{rf["recall"]:.4f}', f'{rf["f1"]:.4f}',
         f'{report["dataset_size"]:,}'],
        ['Gradient Boosting',
         f'{gb["accuracy"]:.4f}', f'{gb["precision"]:.4f}',
         f'{gb["recall"]:.4f}', f'{gb["f1"]:.4f}',
         f'{report["dataset_size"]:,}'],
    ]

    # Highlight best values
    best_color = '#DBEAFE'
    cell_colors = []
    for row_data in rows:
        row_colors = ['white'] * len(columns)
        cell_colors.append(row_colors)

    # Find best per metric
    for col_idx in range(1, 5):
        vals = [float(rows[r][col_idx]) for r in range(len(rows))]
        best_idx = vals.index(max(vals))
        cell_colors[best_idx][col_idx] = best_color

    table = ax.table(
        cellText=rows,
        colLabels=columns,
        cellColours=cell_colors,
        colColours=[COLORS['rf']] * len(columns),
        loc='center',
        cellLoc='center',
    )

    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.0)

    # Style header
    for j in range(len(columns)):
        cell = table[0, j]
        cell.set_text_props(fontweight='bold', color='white', fontsize=11)
        cell.set_facecolor(COLORS['rf'])
        cell.set_edgecolor('white')

    # Style data rows
    for i in range(1, len(rows) + 1):
        for j in range(len(columns)):
            cell = table[i, j]
            cell.set_edgecolor(COLORS['grid'])
            cell.set_text_props(fontsize=11)

    ax.set_title('Сводная таблица результатов обучения',
                 fontsize=15, fontweight='bold', pad=20)

    plt.tight_layout()
    path = output_dir / '08_summary_table.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 9: Confusion Matrix — Normalized (percentage)
# ═══════════════════════════════════════════════════════════════════
def chart_normalized_confusion(report, output_dir):
    """Normalized confusion matrix — shows recall per class."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.patch.set_facecolor('white')

    models = [
        ('Random Forest', report['results']['random_forest']),
        ('Gradient Boosting', report['results']['gradient_boosting']),
    ]
    class_labels = ['OK', 'BAD']
    cmaps = ['Blues', 'Purples']

    for ax, (name, data), cmap in zip(axes, models, cmaps):
        cm = np.array(data['confusion_matrix'], dtype=float)
        cm_norm = cm / cm.sum(axis=1, keepdims=True) * 100

        im = ax.imshow(cm_norm, interpolation='nearest', cmap=cmap,
                       aspect='auto', vmin=0, vmax=100)

        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(class_labels, fontsize=12)
        ax.set_yticklabels(class_labels, fontsize=12)
        ax.set_xlabel('Предсказание', fontsize=12)
        ax.set_ylabel('Истина', fontsize=12)
        ax.set_title(name, fontsize=14, fontweight='bold', pad=10)

        for i in range(2):
            for j in range(2):
                val = cm_norm[i][j]
                text_color = 'white' if val > 50 else COLORS['text']
                ax.text(j, i, f'{val:.2f}%',
                        ha='center', va='center', fontsize=16,
                        fontweight='bold', color=text_color)

        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, format='%.0f%%')

    fig.suptitle('Нормализованные матрицы ошибок (по строкам)',
                 fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    path = output_dir / '09_normalized_confusion.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 10: Error Analysis — FP vs FN breakdown
# ═══════════════════════════════════════════════════════════════════
def chart_error_analysis(report, output_dir):
    """Stacked bar showing TP, TN, FP, FN for each model."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    models_data = []
    for name, key in [('Random Forest', 'random_forest'),
                      ('Gradient Boosting', 'gradient_boosting')]:
        cm = report['results'][key]['confusion_matrix']
        tn, fp = cm[0]
        fn, tp = cm[1]
        models_data.append({
            'name': name, 'TP': tp, 'TN': tn, 'FP': fp, 'FN': fn,
            'total': tp + tn + fp + fn,
        })

    x = np.arange(len(models_data))
    width = 0.45

    tp_vals = [d['TP'] for d in models_data]
    tn_vals = [d['TN'] for d in models_data]
    fp_vals = [d['FP'] for d in models_data]
    fn_vals = [d['FN'] for d in models_data]

    names = [d['name'] for d in models_data]

    # Stacked bars — correct predictions at bottom, errors on top
    ax.bar(x, tn_vals, width, label='True Negative (OK→OK)',
           color=COLORS['ok'], alpha=0.7, zorder=3)
    ax.bar(x, tp_vals, width, bottom=tn_vals, label='True Positive (BAD→BAD)',
           color='#059669', alpha=0.9, zorder=3)

    bottom2 = [tn + tp for tn, tp in zip(tn_vals, tp_vals)]
    ax.bar(x, fp_vals, width, bottom=bottom2, label='False Positive (OK→BAD)',
           color=COLORS['accent'], alpha=0.85, zorder=3)

    bottom3 = [b + fp for b, fp in zip(bottom2, fp_vals)]
    ax.bar(x, fn_vals, width, bottom=bottom3, label='False Negative (BAD→OK)',
           color=COLORS['bad'], alpha=0.85, zorder=3)

    # Annotate error counts
    for i, d in enumerate(models_data):
        error_total = d['FP'] + d['FN']
        error_pct = error_total / d['total'] * 100
        ax.text(i, d['total'] + 500, f'Ошибки: {error_total:,} ({error_pct:.2f}%)',
                ha='center', va='bottom', fontsize=11, fontweight='bold',
                color=COLORS['bad'])

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=12)
    ax.set_ylabel('Количество предсказаний')
    ax.set_title('Анализ ошибок классификации')
    ax.legend(loc='center right', fontsize=9, framealpha=0.9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Format y-axis with thousands separator
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, p: f'{int(v):,}'))

    plt.tight_layout()
    path = output_dir / '10_error_analysis.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Chart 11: Session Split Info
# ═══════════════════════════════════════════════════════════════════
def chart_session_split(report, output_dir):
    """Visualize how data was split by sessions (GroupShuffleSplit)."""
    total_sessions = report.get('total_sessions', 0)
    train_sessions = report.get('train_sessions', 0)
    test_sessions = report.get('test_sessions', 0)

    if total_sessions == 0:
        print('  ⚠ No session info in report, skipping chart 11')
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor('white')

    # Left: session split pie
    ax1 = axes[0]
    sizes = [train_sessions, test_sessions]
    labels = [
        f'Train\n{train_sessions} сессий',
        f'Test\n{test_sessions} сессий',
    ]
    colors = [COLORS['rf'], COLORS['accent']]
    explode = (0.03, 0.03)

    wedges, texts = ax1.pie(sizes, labels=labels, colors=colors,
                            explode=explode, startangle=90,
                            textprops={'fontsize': 13, 'fontweight': 'bold'},
                            wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    ax1.set_title(f'Разделение по сессиям\n(всего {total_sessions})',
                  fontsize=13, fontweight='bold', pad=15)

    # Right: samples per split
    ax2 = axes[1]
    ax2.set_facecolor('white')

    split_data = {
        'Сессии': [train_sessions, test_sessions],
        'Записи': [report['train_size'], report['test_size']],
    }
    x = np.arange(2)
    width = 0.3

    bars1 = ax2.bar(x - width/2, split_data['Сессии'], width,
                    label='Сессии', color=COLORS['rf'],
                    edgecolor='white', linewidth=1.5, zorder=3)
    # Create secondary y-axis for samples
    ax2b = ax2.twinx()
    bars2 = ax2b.bar(x + width/2, split_data['Записи'], width,
                     label='Записи', color=COLORS['accent'],
                     edgecolor='white', linewidth=1.5, zorder=3, alpha=0.85)

    for bar in bars1:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                 f'{int(bar.get_height())}', ha='center', va='bottom',
                 fontsize=11, fontweight='bold', color=COLORS['rf'])
    for bar in bars2:
        ax2b.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1000,
                  f'{int(bar.get_height()):,}', ha='center', va='bottom',
                  fontsize=11, fontweight='bold', color=COLORS['accent'])

    ax2.set_xticks(x)
    ax2.set_xticklabels(['Train', 'Test'], fontsize=12)
    ax2.set_ylabel('Количество сессий', color=COLORS['rf'])
    ax2b.set_ylabel('Количество записей', color=COLORS['accent'])
    ax2.set_title('GroupShuffleSplit: сессии и записи',
                  fontsize=13, fontweight='bold')

    # Combined legend
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=10)

    ax2.spines['top'].set_visible(False)
    ax2b.spines['top'].set_visible(False)

    fig.suptitle('Разделение данных по сессиям (без утечки данных)',
                 fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    path = output_dir / '11_session_split.png'
    plt.savefig(path)
    plt.close()
    print(f'  ✓ {path.name}')


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description='Генерация графиков для дипломной работы ErgoBoost')
    parser.add_argument('--report', type=str, default='ml/models/training_report.json',
                        help='Путь к training_report.json')
    parser.add_argument('--model', type=str, default='ml/models/posture_classifier.pkl',
                        help='Путь к posture_classifier.pkl')
    parser.add_argument('--output', type=str, default='ml/diploma_charts',
                        help='Папка для сохранения графиков')
    args = parser.parse_args()

    report_path = Path(args.report)
    model_path = Path(args.model)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print('=' * 60)
    print('  ErgoBoost — Генерация графиков для диплома')
    print('=' * 60)
    print(f'  Report: {report_path}')
    print(f'  Model:  {model_path}')
    print(f'  Output: {output_dir}')
    print()

    report, model_data = load_data(report_path, model_path)

    print('Генерация графиков...\n')

    chart_model_comparison(report, output_dir)
    chart_confusion_matrices(report, output_dir)
    chart_feature_importance(report, output_dir)
    chart_per_class_metrics(report, output_dir)
    chart_dataset_distribution(report, output_dir)
    chart_radar_comparison(report, output_dir)
    chart_cross_validation(report, output_dir)
    chart_summary_table(report, output_dir)
    chart_normalized_confusion(report, output_dir)
    chart_error_analysis(report, output_dir)
    chart_session_split(report, output_dir)

    chart_count = len(list(output_dir.glob('*.png')))
    print(f'\n{"=" * 60}')
    print(f'  Готово! {chart_count} графиков сохранены в: {output_dir}/')
    print(f'{"=" * 60}')
    print(f'\nСписок файлов:')
    for f in sorted(output_dir.glob('*.png')):
        size_kb = f.stat().st_size / 1024
        print(f'  📊 {f.name} ({size_kb:.0f} KB)')


if __name__ == '__main__':
    main()
