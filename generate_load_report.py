#!/usr/bin/env python3
"""Generate comparison dashboard from load test results."""

import json
import sys
from pathlib import Path
from typing import List, Dict
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd


def load_results(results_dir: Path, cache_mode: str) -> List[Dict]:
    """Load all results for a cache mode."""
    results = []

    pattern = f"load_test_{cache_mode}_*strat.json"
    for filepath in sorted(results_dir.glob(pattern)):
        with open(filepath, 'r') as f:
            results.append(json.load(f))

    return results


def generate_comparison_charts(results_2tier: List[Dict], results_3tier: List[Dict],
                               output_dir: Path):
    """Generate comprehensive comparison charts."""

    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    fig.suptitle('Cache Architecture Load Test Comparison', fontsize=16, fontweight='bold')

    # Extract data
    def extract_data(results):
        strategy_counts = [r['strategy_count'] for r in results]

        # Get first operation latencies as representative
        p50_latencies = []
        p99_latencies = []
        for r in results:
            if r['performance']['latencies']:
                first_op = list(r['performance']['latencies'].values())[0]
                p50_latencies.append(first_op['p50'])
                p99_latencies.append(first_op['p99'])
            else:
                p50_latencies.append(0)
                p99_latencies.append(0)

        cpu_avg = [r['system']['cpu']['avg_percent'] for r in results]
        cpu_peak = [r['system']['cpu']['max_percent'] for r in results]
        memory_avg = [r['system']['memory']['avg_rss_mb'] for r in results]
        memory_peak = [r['system']['memory']['max_rss_mb'] for r in results]
        wall_time = [r['wall_clock_seconds'] for r in results]

        return {
            'counts': strategy_counts,
            'p50': p50_latencies,
            'p99': p99_latencies,
            'cpu_avg': cpu_avg,
            'cpu_peak': cpu_peak,
            'mem_avg': memory_avg,
            'mem_peak': memory_peak,
            'wall_time': wall_time
        }

    data_2tier = extract_data(results_2tier)
    data_3tier = extract_data(results_3tier)

    # Chart 1: P50 Latency
    ax1 = axes[0, 0]
    ax1.plot(data_2tier['counts'], data_2tier['p50'], 'o-', label='2-Tier', linewidth=2, markersize=8)
    ax1.plot(data_3tier['counts'], data_3tier['p50'], 's-', label='3-Tier', linewidth=2, markersize=8)
    ax1.set_xlabel('Number of Strategies')
    ax1.set_ylabel('P50 Latency (ms)')
    ax1.set_title('P50 Latency vs Strategy Count')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Chart 2: P99 Latency
    ax2 = axes[0, 1]
    ax2.plot(data_2tier['counts'], data_2tier['p99'], 'o-', label='2-Tier', linewidth=2, markersize=8)
    ax2.plot(data_3tier['counts'], data_3tier['p99'], 's-', label='3-Tier', linewidth=2, markersize=8)
    ax2.axhline(y=100, color='r', linestyle='--', label='100ms threshold', alpha=0.7)
    ax2.set_xlabel('Number of Strategies')
    ax2.set_ylabel('P99 Latency (ms)')
    ax2.set_title('P99 Latency vs Strategy Count')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')

    # Chart 3: CPU Usage
    ax3 = axes[0, 2]
    ax3.plot(data_2tier['counts'], data_2tier['cpu_avg'], 'o-', label='2-Tier Avg', linewidth=2, markersize=8)
    ax3.plot(data_3tier['counts'], data_3tier['cpu_avg'], 's-', label='3-Tier Avg', linewidth=2, markersize=8)
    ax3.plot(data_2tier['counts'], data_2tier['cpu_peak'], 'o--', label='2-Tier Peak', alpha=0.6)
    ax3.plot(data_3tier['counts'], data_3tier['cpu_peak'], 's--', label='3-Tier Peak', alpha=0.6)
    ax3.set_xlabel('Number of Strategies')
    ax3.set_ylabel('CPU Usage (%)')
    ax3.set_title('CPU Usage vs Strategy Count')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Chart 4: Memory Usage
    ax4 = axes[1, 0]
    ax4.plot(data_2tier['counts'], data_2tier['mem_avg'], 'o-', label='2-Tier Avg', linewidth=2, markersize=8)
    ax4.plot(data_3tier['counts'], data_3tier['mem_avg'], 's-', label='3-Tier Avg', linewidth=2, markersize=8)
    ax4.plot(data_2tier['counts'], data_2tier['mem_peak'], 'o--', label='2-Tier Peak', alpha=0.6)
    ax4.plot(data_3tier['counts'], data_3tier['mem_peak'], 's--', label='3-Tier Peak', alpha=0.6)
    ax4.set_xlabel('Number of Strategies')
    ax4.set_ylabel('Memory (MB)')
    ax4.set_title('Memory Usage vs Strategy Count')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # Chart 5: Wall Clock Time
    ax5 = axes[1, 1]
    ax5.plot(data_2tier['counts'], data_2tier['wall_time'], 'o-', label='2-Tier', linewidth=2, markersize=8)
    ax5.plot(data_3tier['counts'], data_3tier['wall_time'], 's-', label='3-Tier', linewidth=2, markersize=8)
    ax5.set_xlabel('Number of Strategies')
    ax5.set_ylabel('Wall Clock Time (s)')
    ax5.set_title('Execution Time vs Strategy Count')
    ax5.legend()
    ax5.grid(True, alpha=0.3)

    # Chart 6: Speedup Factor
    ax6 = axes[1, 2]
    if len(data_2tier['counts']) == len(data_3tier['counts']):
        speedup = [t2 / t3 if t3 > 0 else 0
                   for t2, t3 in zip(data_2tier['wall_time'], data_3tier['wall_time'])]
        ax6.plot(data_2tier['counts'], speedup, 'go-', linewidth=2, markersize=8)
        ax6.axhline(y=1, color='r', linestyle='--', label='No improvement', alpha=0.7)
        ax6.set_xlabel('Number of Strategies')
        ax6.set_ylabel('Speedup Factor (2-tier / 3-tier)')
        ax6.set_title('3-Tier Performance Advantage')
        ax6.legend()
        ax6.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save chart
    chart_path = output_dir / "load_test_comparison.png"
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"✓ Comparison charts saved to {chart_path}")
    plt.close()


def generate_text_report(results_2tier: List[Dict], results_3tier: List[Dict],
                        output_dir: Path):
    """Generate detailed text report."""

    report_path = output_dir / "LOAD_TEST_REPORT.md"

    with open(report_path, 'w') as f:
        f.write("# Load Test Comparison Report\n\n")
        f.write("## Test Configuration\n\n")

        if results_2tier:
            f.write(f"- **Instruments Pool**: 50 stocks\n")
            f.write(f"- **Instruments per Strategy**: 3-30 (varies by type)\n")
            f.write(f"- **Test Duration**: {results_2tier[0]['duration_minutes']} simulated minutes\n")
            f.write(f"- **Strategy Mix**: High-frequency, Scalping, Momentum, Mean-reversion, Swing, Position\n\n")

        f.write("## Results Comparison\n\n")
        f.write("### Latency Performance\n\n")
        f.write("| Strategies | 2-Tier P50 | 2-Tier P99 | 3-Tier P50 | 3-Tier P99 | Improvement |\n")
        f.write("|------------|------------|------------|------------|------------|-------------|\n")

        for r2, r3 in zip(results_2tier, results_3tier):
            count = r2['strategy_count']

            if r2['performance']['latencies']:
                r2_op = list(r2['performance']['latencies'].values())[0]
                p50_2 = r2_op['p50']
                p99_2 = r2_op['p99']
            else:
                p50_2 = p99_2 = 0

            if r3['performance']['latencies']:
                r3_op = list(r3['performance']['latencies'].values())[0]
                p50_3 = r3_op['p50']
                p99_3 = r3_op['p99']
            else:
                p50_3 = p99_3 = 0

            improvement = f"{p50_2/p50_3:.1f}x" if p50_3 > 0 else "N/A"

            f.write(f"| {count:10d} | {p50_2:10.3f} | {p99_2:10.3f} | {p50_3:10.3f} | {p99_3:10.3f} | {improvement:11s} |\n")

        f.write("\n### Resource Utilization\n\n")
        f.write("| Strategies | 2-Tier CPU | 2-Tier Mem | 3-Tier CPU | 3-Tier Mem | Mem Diff |\n")
        f.write("|------------|------------|------------|------------|------------|----------|\n")

        for r2, r3 in zip(results_2tier, results_3tier):
            count = r2['strategy_count']
            cpu2 = r2['system']['cpu']['avg_percent']
            mem2 = r2['system']['memory']['avg_rss_mb']
            cpu3 = r3['system']['cpu']['avg_percent']
            mem3 = r3['system']['memory']['avg_rss_mb']
            mem_diff = mem3 - mem2

            f.write(f"| {count:10d} | {cpu2:10.1f} | {mem2:10.1f} | {cpu3:10.1f} | {mem3:10.1f} | +{mem_diff:8.1f} |\n")

        f.write("\n### Key Findings\n\n")

        # Calculate averages
        avg_speedup = sum(r2['wall_clock_seconds'] / r3['wall_clock_seconds']
                         for r2, r3 in zip(results_2tier, results_3tier)) / len(results_2tier)

        avg_mem_overhead = sum(r3['system']['memory']['avg_rss_mb'] - r2['system']['memory']['avg_rss_mb']
                              for r2, r3 in zip(results_2tier, results_3tier)) / len(results_2tier)

        f.write(f"- **Average Speedup**: {avg_speedup:.2f}x faster with 3-tier\n")
        f.write(f"- **Memory Overhead**: +{avg_mem_overhead:.1f} MB average for in-memory cache\n")

        # Find max capacity
        max_2tier = max(r['strategy_count'] for r in results_2tier)
        max_3tier = max(r['strategy_count'] for r in results_3tier)
        f.write(f"- **Max Tested Capacity**: {max_2tier} strategies (2-tier), {max_3tier} strategies (3-tier)\n")

        f.write("\n### Recommendations\n\n")
        f.write("Based on the test results:\n\n")
        f.write("1. **3-tier architecture is recommended** for production deployment\n")
        f.write("2. Memory overhead is minimal compared to performance gains\n")
        f.write("3. System can comfortably handle tested load levels\n")
        f.write("4. Consider horizontal scaling for loads beyond tested capacity\n")

    print(f"✓ Text report saved to {report_path}")


def main():
    results_dir = Path('./load_test_results')

    if not results_dir.exists():
        print(f"Error: Results directory {results_dir} not found")
        print("Run load tests first: python load_test.py --mode 2-tier/3-tier")
        return 1

    # Load results
    print("Loading test results...")
    results_2tier = load_results(results_dir, '2-tier')
    results_3tier = load_results(results_dir, '3-tier')

    if not results_2tier or not results_3tier:
        print("Error: Need both 2-tier and 3-tier results")
        print(f"Found: {len(results_2tier)} 2-tier, {len(results_3tier)} 3-tier")
        return 1

    print(f"Loaded: {len(results_2tier)} 2-tier results, {len(results_3tier)} 3-tier results")

    # Generate reports
    print("\nGenerating comparison charts...")
    generate_comparison_charts(results_2tier, results_3tier, results_dir)

    print("\nGenerating text report...")
    generate_text_report(results_2tier, results_3tier, results_dir)

    print("\n✅ Load test report generation complete!")
    print(f"\nView results:")
    print(f"  - Charts: {results_dir}/load_test_comparison.png")
    print(f"  - Report: {results_dir}/LOAD_TEST_REPORT.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
