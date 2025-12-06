#!/bin/bash

# Visualization Script for Watermark Attack Results
# Generates plots showing AUROC and TPR metrics across different methods and attack ratios

echo "=========================================="
echo "Watermark Attack Results Visualization"
echo "=========================================="

# Create output directory for plots
PLOT_DIR="plots"
mkdir -p "$PLOT_DIR"

# Create Python script for plotting
cat > plot_results.py << 'EOF'
import matplotlib.pyplot as plt
import numpy as np
import json
import os
from pathlib import Path

# Configuration
METHODS = ["DIRECTORY", "MULTITOKEN", "MULTITOKEN5", "UNIGRAM", "CODEBERT"]
METHOD_NAMES = {
    "DIRECTORY": "Simple_1 (k=1)",
    "MULTITOKEN": "Multi-token (k=3)",
    "MULTITOKEN5": "Multi-token (k=5)",
    "UNIGRAM": "Unigram (k=0)",
    "CODEBERT": "CodeBERT"
}
RATIOS = [0, 25, 50, 75, 100]
COLORS = {
    "DIRECTORY": "#1f77b4",
    "MULTITOKEN": "#ff7f0e",
    "MULTITOKEN5": "#2ca02c",
    "UNIGRAM": "#d62728",
    "CODEBERT": "#9467bd"
}
MARKERS = {
    "DIRECTORY": "o",
    "MULTITOKEN": "s",
    "MULTITOKEN5": "^",
    "UNIGRAM": "D",
    "CODEBERT": "v"
}

def read_metrics(method, ratio):
    """Read metrics from file."""
    if method == "DIRECTORY":
        dir_name = f"OUTPUT_DIRECTORY_RENAMED_{ratio}"
    else:
        dir_name = f"OUTPUT_{method}_RENAMED_{ratio}"
    
    metrics_file = f"{dir_name}/metrics.txt"
    
    if not os.path.exists(metrics_file):
        return None
    
    try:
        with open(metrics_file, 'r') as f:
            lines = f.readlines()
            auroc = float(lines[0].strip())
            tpr_0 = float(lines[1].strip())
            tpr_1 = float(lines[2].strip())
            tpr_5 = float(lines[3].strip())
            return {
                'auroc': auroc,
                'tpr@0%': tpr_0,
                'tpr@1%': tpr_1,
                'tpr@5%': tpr_5
            }
    except (IndexError, ValueError) as e:
        print(f"Warning: Could not parse {metrics_file}: {e}")
        return None

def read_baseline_metrics(method):
    """Read baseline metrics (no attack)."""
    if method == "DIRECTORY":
        dir_name = "OUTPUT_DIRECTORY"
    else:
        dir_name = f"OUTPUT_{method}"
    
    eval_file = f"{dir_name}/evaluation_results.json"
    
    if not os.path.exists(eval_file):
        return None
    
    try:
        with open(eval_file, 'r') as f:
            data = json.load(f)
            if 'watermark_detection' in data:
                wd = data['watermark_detection']
                return {
                    'auroc': wd.get('AUROC', 0),
                    'tpr@0%': wd.get('TPR@0%FPR', 0),
                    'tpr@1%': wd.get('TPR@1%FPR', 0),
                    'tpr@5%': wd.get('TPR@5%FPR', 0)
                }
    except Exception as e:
        print(f"Warning: Could not parse {eval_file}: {e}")
    
    return None

# Collect all data
data = {}
for method in METHODS:
    data[method] = {}
    
    # Read baseline (0% attack is same as baseline)
    baseline = read_baseline_metrics(method)
    if baseline:
        data[method][0] = baseline
    
    # Read attack results
    for ratio in RATIOS:
        metrics = read_metrics(method, ratio)
        if metrics:
            data[method][ratio] = metrics

# Print summary table
print("\n" + "="*80)
print("SUMMARY TABLE")
print("="*80)
print(f"{'Method':<20} {'Ratio':<8} {'AUROC':<10} {'TPR@0%':<10} {'TPR@1%':<10} {'TPR@5%':<10}")
print("-"*80)

for method in METHODS:
    if method not in data or not data[method]:
        continue
    
    method_name = METHOD_NAMES.get(method, method)
    
    for ratio in sorted(data[method].keys()):
        metrics = data[method][ratio]
        print(f"{method_name:<20} {ratio:>3}%     {metrics['auroc']:.4f}     "
              f"{metrics['tpr@0%']:.4f}     {metrics['tpr@1%']:.4f}     "
              f"{metrics['tpr@5%']:.4f}")
    print("-"*80)

# Create plots
plt.style.use('seaborn-v0_8-darkgrid' if 'seaborn-v0_8-darkgrid' in plt.style.available else 'default')

# Plot 1: AUROC Grouped Bar Chart
fig, ax = plt.subplots(figsize=(12, 6))

# Prepare data for grouped bar chart
methods_with_data = [m for m in METHODS if m in data and data[m]]
x = np.arange(len(RATIOS))  # Label locations
width = 0.15  # Width of each bar
multiplier = 0

for method in methods_with_data:
    ratios_data = []
    for ratio in RATIOS:
        if ratio in data[method]:
            ratios_data.append(data[method][ratio]['auroc'])
        else:
            ratios_data.append(0)
    
    offset = width * multiplier
    rects = ax.bar(x + offset, ratios_data, width, 
                   label=METHOD_NAMES.get(method, method),
                   color=COLORS[method],
                   alpha=0.8,
                   edgecolor='black',
                   linewidth=0.5)
    
    # Add value labels on bars
    for i, rect in enumerate(rects):
        height = rect.get_height()
        if height > 0:
            ax.text(rect.get_x() + rect.get_width()/2., height,
                   f'{height:.3f}',
                   ha='center', va='bottom', fontsize=7, rotation=0)
    
    multiplier += 1

ax.set_xlabel('Variable Renaming Ratio (%)', fontsize=12, fontweight='bold')
ax.set_ylabel('AUROC', fontsize=12, fontweight='bold')
ax.set_title('Watermark Detection AUROC - Grouped by Attack Ratio', fontsize=14, fontweight='bold')
ax.set_xticks(x + width * (len(methods_with_data) - 1) / 2)
ax.set_xticklabels([f'{r}%' for r in RATIOS])
ax.legend(loc='upper right', fontsize=9, ncol=2)
ax.set_ylim(0, 1.1)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig('plots/auroc_bar_chart.png', dpi=300, bbox_inches='tight')
print("\nSaved: plots/auroc_bar_chart.png")

# Also keep the line plot
fig, ax = plt.subplots(figsize=(10, 6))
for method in METHODS:
    if method not in data or not data[method]:
        continue
    
    ratios = sorted(data[method].keys())
    aurocs = [data[method][r]['auroc'] for r in ratios]
    
    ax.plot(ratios, aurocs, 
            marker=MARKERS[method], 
            color=COLORS[method],
            linewidth=2.5,
            markersize=8,
            label=METHOD_NAMES.get(method, method))

ax.set_xlabel('Variable Renaming Ratio (%)', fontsize=12, fontweight='bold')
ax.set_ylabel('AUROC', fontsize=12, fontweight='bold')
ax.set_title('Watermark Detection AUROC vs Variable Renaming Attack', fontsize=14, fontweight='bold')
ax.legend(loc='best', fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 1.05)
ax.set_xticks(RATIOS)
plt.tight_layout()
plt.savefig('plots/auroc_vs_ratio.png', dpi=300, bbox_inches='tight')
print("Saved: plots/auroc_vs_ratio.png")

# Plot 2: TPR@0% vs Attack Ratio
fig, ax = plt.subplots(figsize=(10, 6))
for method in METHODS:
    if method not in data or not data[method]:
        continue
    
    ratios = sorted(data[method].keys())
    tprs = [data[method][r]['tpr@0%'] for r in ratios]
    
    ax.plot(ratios, tprs,
            marker=MARKERS[method],
            color=COLORS[method],
            linewidth=2.5,
            markersize=8,
            label=METHOD_NAMES.get(method, method))

ax.set_xlabel('Variable Renaming Ratio (%)', fontsize=12, fontweight='bold')
ax.set_ylabel('TPR @ 0% FPR', fontsize=12, fontweight='bold')
ax.set_title('True Positive Rate (0% FPR) vs Variable Renaming Attack', fontsize=14, fontweight='bold')
ax.legend(loc='best', fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 1.05)
ax.set_xticks(RATIOS)
plt.tight_layout()
plt.savefig('plots/tpr0_vs_ratio.png', dpi=300, bbox_inches='tight')
print("Saved: plots/tpr0_vs_ratio.png")

# Plot 3: TPR@5% vs Attack Ratio
fig, ax = plt.subplots(figsize=(10, 6))
for method in METHODS:
    if method not in data or not data[method]:
        continue
    
    ratios = sorted(data[method].keys())
    tprs = [data[method][r]['tpr@5%'] for r in ratios]
    
    ax.plot(ratios, tprs,
            marker=MARKERS[method],
            color=COLORS[method],
            linewidth=2.5,
            markersize=8,
            label=METHOD_NAMES.get(method, method))

ax.set_xlabel('Variable Renaming Ratio (%)', fontsize=12, fontweight='bold')
ax.set_ylabel('TPR @ 5% FPR', fontsize=12, fontweight='bold')
ax.set_title('True Positive Rate (5% FPR) vs Variable Renaming Attack', fontsize=14, fontweight='bold')
ax.legend(loc='best', fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 1.05)
ax.set_xticks(RATIOS)
plt.tight_layout()
plt.savefig('plots/tpr5_vs_ratio.png', dpi=300, bbox_inches='tight')
print("Saved: plots/tpr5_vs_ratio.png")

# Plot 4: All TPR metrics in subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Watermark Robustness Against Variable Renaming Attack', fontsize=16, fontweight='bold')

metrics_to_plot = [
    ('auroc', 'AUROC', axes[0, 0]),
    ('tpr@0%', 'TPR @ 0% FPR', axes[0, 1]),
    ('tpr@1%', 'TPR @ 1% FPR', axes[1, 0]),
    ('tpr@5%', 'TPR @ 5% FPR', axes[1, 1])
]

for metric_key, metric_name, ax in metrics_to_plot:
    for method in METHODS:
        if method not in data or not data[method]:
            continue
        
        ratios = sorted(data[method].keys())
        values = [data[method][r][metric_key] for r in ratios]
        
        ax.plot(ratios, values,
                marker=MARKERS[method],
                color=COLORS[method],
                linewidth=2.5,
                markersize=8,
                label=METHOD_NAMES.get(method, method))
    
    ax.set_xlabel('Variable Renaming Ratio (%)', fontsize=11, fontweight='bold')
    ax.set_ylabel(metric_name, fontsize=11, fontweight='bold')
    ax.set_title(metric_name, fontsize=12, fontweight='bold')
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)
    ax.set_xticks(RATIOS)

plt.tight_layout()
plt.savefig('plots/all_metrics.png', dpi=300, bbox_inches='tight')
print("Saved: plots/all_metrics.png")

# Plot 5: Heatmap of AUROC degradation
fig, ax = plt.subplots(figsize=(10, 6))

# Prepare data for heatmap
heatmap_data = []
method_labels = []

for method in METHODS:
    if method not in data or not data[method]:
        continue
    
    method_labels.append(METHOD_NAMES.get(method, method))
    row = []
    for ratio in RATIOS:
        if ratio in data[method]:
            row.append(data[method][ratio]['auroc'])
        else:
            row.append(0)
    heatmap_data.append(row)

if heatmap_data:
    heatmap_data = np.array(heatmap_data)
    
    im = ax.imshow(heatmap_data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
    
    # Set ticks
    ax.set_xticks(np.arange(len(RATIOS)))
    ax.set_yticks(np.arange(len(method_labels)))
    ax.set_xticklabels([f"{r}%" for r in RATIOS])
    ax.set_yticklabels(method_labels)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('AUROC', fontsize=12, fontweight='bold')
    
    # Add text annotations
    for i in range(len(method_labels)):
        for j in range(len(RATIOS)):
            text = ax.text(j, i, f'{heatmap_data[i, j]:.3f}',
                          ha="center", va="center", color="black", fontsize=10)
    
    ax.set_title('AUROC Heatmap: Method vs Attack Ratio', fontsize=14, fontweight='bold')
    ax.set_xlabel('Variable Renaming Ratio', fontsize=12, fontweight='bold')
    ax.set_ylabel('Watermark Method', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('plots/auroc_heatmap.png', dpi=300, bbox_inches='tight')
    print("Saved: plots/auroc_heatmap.png")

# Plot 6: Relative degradation (normalized to baseline)
fig, ax = plt.subplots(figsize=(10, 6))

for method in METHODS:
    if method not in data or not data[method] or 0 not in data[method]:
        continue
    
    baseline_auroc = data[method][0]['auroc']
    if baseline_auroc == 0:
        continue
    
    ratios = sorted([r for r in data[method].keys() if r > 0])
    relative_aurocs = [(data[method][r]['auroc'] / baseline_auroc) * 100 for r in ratios]
    
    ax.plot(ratios, relative_aurocs,
            marker=MARKERS[method],
            color=COLORS[method],
            linewidth=2.5,
            markersize=8,
            label=METHOD_NAMES.get(method, method))

ax.axhline(y=100, color='gray', linestyle='--', linewidth=1, alpha=0.5, label='Baseline (100%)')
ax.set_xlabel('Variable Renaming Ratio (%)', fontsize=12, fontweight='bold')
ax.set_ylabel('Relative AUROC (%)', fontsize=12, fontweight='bold')
ax.set_title('Watermark Detection Degradation (Relative to Baseline)', fontsize=14, fontweight='bold')
ax.legend(loc='best', fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_xticks([r for r in RATIOS if r > 0])
plt.tight_layout()
plt.savefig('plots/auroc_degradation.png', dpi=300, bbox_inches='tight')
print("Saved: plots/auroc_degradation.png")

print("\n" + "="*80)
print("All plots generated successfully!")
print("="*80)

# Generate CSV export
csv_file = 'plots/results_summary.csv'
with open(csv_file, 'w') as f:
    f.write("Method,Ratio,AUROC,TPR@0%,TPR@1%,TPR@5%\n")
    for method in METHODS:
        if method not in data or not data[method]:
            continue
        
        method_name = METHOD_NAMES.get(method, method)
        for ratio in sorted(data[method].keys()):
            metrics = data[method][ratio]
            f.write(f"{method_name},{ratio},"
                   f"{metrics['auroc']:.6f},"
                   f"{metrics['tpr@0%']:.6f},"
                   f"{metrics['tpr@1%']:.6f},"
                   f"{metrics['tpr@5%']:.6f}\n")

print(f"\nExported data to: {csv_file}")
EOF

# Run the Python plotting script
echo ""
echo "Generating plots..."
python plot_results.py

# Check if plots were created
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Visualization Complete!"
    echo "=========================================="
    echo ""
    echo "Generated files:"
    echo "  - plots/auroc_bar_chart.png      : AUROC grouped bar chart (NEW!)"
    echo "  - plots/auroc_vs_ratio.png       : AUROC vs attack ratio (line)"
    echo "  - plots/tpr0_vs_ratio.png        : TPR@0% vs attack ratio"
    echo "  - plots/tpr5_vs_ratio.png        : TPR@5% vs attack ratio"
    echo "  - plots/all_metrics.png          : All metrics in one figure"
    echo "  - plots/auroc_heatmap.png        : AUROC heatmap"
    echo "  - plots/auroc_degradation.png    : Relative degradation"
    echo "  - plots/results_summary.csv      : CSV data export"
    echo ""
    echo "You can view the plots with:"
    echo "  eog plots/*.png    # or your preferred image viewer"
else
    echo "Error: Plot generation failed"
    exit 1
fi
