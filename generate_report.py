#!/usr/bin/env python3
"""Generate comparison report from 2-tier and 3-tier test results."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import matplotlib.pyplot as plt
import pandas as pd


def load_metrics(metrics_path: Path) -> Optional[Dict[str, Any]]:
    """Load metrics JSON file."""
    try:
        with open(metrics_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {metrics_path} not found")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {metrics_path}: {e}")
        return None


def calculate_improvement(baseline: float, improved: float) -> float:
    """Calculate percentage improvement."""
    if baseline == 0:
        return 0
    return ((baseline - improved) / baseline) * 100


def generate_text_report(metrics_2tier: Dict[str, Any], metrics_3tier: Dict[str, Any]):
    """Generate detailed text comparison report."""
    print("\n" + "="*80)
    print("CACHE ARCHITECTURE PERFORMANCE COMPARISON")
    print("="*80)

    # Cache Hit Rates Comparison
    print("\n📊 CACHE HIT RATES")
    print("-"*80)

    print("\n2-Tier (API + Redis):")
    if metrics_2tier.get("cache_hit_rates"):
        for tier, stats in metrics_2tier["cache_hit_rates"].items():
            print(f"  {tier:15s}: {stats['rate']:6.2f}% ({stats['hits']:,}/{stats['total']:,})")
    else:
        print("  No cache data available")

    print("\n3-Tier (API + Redis + Memory):")
    if metrics_3tier.get("cache_hit_rates"):
        for tier, stats in metrics_3tier["cache_hit_rates"].items():
            print(f"  {tier:15s}: {stats['rate']:6.2f}% ({stats['hits']:,}/{stats['total']:,})")
    else:
        print("  No cache data available")

    # Latency Comparison
    print("\n\n⚡ LATENCY COMPARISON (milliseconds)")
    print("-"*80)

    # Get common operations
    ops_2tier = set(metrics_2tier.get("latencies", {}).keys())
    ops_3tier = set(metrics_3tier.get("latencies", {}).keys())
    common_ops = sorted(ops_2tier.intersection(ops_3tier))

    if common_ops:
        print(f"\n{'Operation':<30} {'2-Tier':<20} {'3-Tier':<20} {'Improvement':<15}")
        print("-"*85)

        for op in common_ops:
            stats_2 = metrics_2tier["latencies"][op]
            stats_3 = metrics_3tier["latencies"][op]

            # Compare P95 latencies
            lat_2 = stats_2["p95"]
            lat_3 = stats_3["p95"]
            improvement = calculate_improvement(lat_2, lat_3)

            symbol = "↓" if improvement > 0 else "↑" if improvement < 0 else "="
            print(f"{op:<30} {lat_2:>8.3f}ms (p95)    {lat_3:>8.3f}ms (p95)    "
                  f"{symbol} {abs(improvement):>6.1f}%")

    # Key Metrics Summary
    print("\n\n📈 KEY METRICS")
    print("-"*80)

    # Cache hit operations comparison
    if "get_bar_memory_hit" in metrics_3tier.get("latencies", {}):
        mem_hit = metrics_3tier["latencies"]["get_bar_memory_hit"]["p95"]
        print(f"\nMemory cache hit latency (3-tier):  {mem_hit:.3f}ms")

    if "get_bar_redis_hit" in metrics_2tier.get("latencies", {}):
        redis_hit_2 = metrics_2tier["latencies"]["get_bar_redis_hit"]["p95"]
        print(f"Redis cache hit latency (2-tier):   {redis_hit_2:.3f}ms")

        if "get_bar_memory_hit" in metrics_3tier.get("latencies", {}):
            speedup = redis_hit_2 / mem_hit
            print(f"Speedup (memory vs redis):          {speedup:.1f}x faster")

    # API fetch comparison
    if "get_bar_api_fetch" in metrics_2tier.get("latencies", {}):
        api_2 = metrics_2tier["latencies"]["get_bar_api_fetch"]
        api_3_count = metrics_3tier["latencies"].get("get_bar_api_fetch", {}).get("count", 0)

        print(f"\nAPI fetch count (2-tier):           {api_2['count']:,}")
        print(f"API fetch count (3-tier):           {api_3_count:,}")

        if api_2['count'] > 0 and api_3_count >= 0:
            reduction = calculate_improvement(api_2['count'], api_3_count)
            print(f"API call reduction:                 {reduction:.1f}%")

    # Total runtime
    runtime_2 = metrics_2tier.get("total_runtime_seconds", 0)
    runtime_3 = metrics_3tier.get("total_runtime_seconds", 0)

    print(f"\nTotal runtime (2-tier):             {runtime_2:.2f}s")
    print(f"Total runtime (3-tier):             {runtime_3:.2f}s")

    if runtime_2 > 0:
        runtime_improvement = calculate_improvement(runtime_2, runtime_3)
        print(f"Runtime improvement:                {runtime_improvement:.1f}%")

    # Summary
    print("\n\n✅ SUMMARY")
    print("-"*80)

    if metrics_3tier.get("cache_hit_rates", {}).get("memory"):
        mem_rate = metrics_3tier["cache_hit_rates"]["memory"]["rate"]
        print(f"• Memory cache achieved {mem_rate:.1f}% hit rate in 3-tier architecture")

    if "get_bar_memory_hit" in metrics_3tier.get("latencies", {}) and \
       "get_bar_redis_hit" in metrics_2tier.get("latencies", {}):
        mem_hit = metrics_3tier["latencies"]["get_bar_memory_hit"]["p95"]
        redis_hit = metrics_2tier["latencies"]["get_bar_redis_hit"]["p95"]
        speedup = redis_hit / mem_hit
        print(f"• Memory access is ~{speedup:.0f}x faster than Redis access")

    if "get_bar_api_fetch" in metrics_2tier.get("latencies", {}):
        api_2_count = metrics_2tier["latencies"]["get_bar_api_fetch"]["count"]
        api_3_count = metrics_3tier["latencies"].get("get_bar_api_fetch", {}).get("count", 0)
        if api_2_count > 0:
            reduction = calculate_improvement(api_2_count, api_3_count)
            print(f"• 3-tier architecture reduces API calls by {reduction:.0f}%")

    print("\n" + "="*80 + "\n")


def generate_charts(metrics_2tier: Dict[str, Any], metrics_3tier: Dict[str, Any], output_dir: Path):
    """Generate comparison charts."""
    print("\n📊 Generating charts...")

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Cache Architecture Performance Comparison', fontsize=16, fontweight='bold')

    # Chart 1: Cache Hit Rates
    ax1 = axes[0, 0]
    if metrics_2tier.get("cache_hit_rates") and metrics_3tier.get("cache_hit_rates"):
        tiers_2 = list(metrics_2tier["cache_hit_rates"].keys())
        rates_2 = [metrics_2tier["cache_hit_rates"][t]["rate"] for t in tiers_2]

        tiers_3 = list(metrics_3tier["cache_hit_rates"].keys())
        rates_3 = [metrics_3tier["cache_hit_rates"][t]["rate"] for t in tiers_3]

        x = range(max(len(tiers_2), len(tiers_3)))
        width = 0.35

        ax1.bar([i - width/2 for i in range(len(tiers_2))], rates_2, width, label='2-Tier', alpha=0.8)
        ax1.bar([i + width/2 for i in range(len(tiers_3))], rates_3, width, label='3-Tier', alpha=0.8)

        ax1.set_ylabel('Hit Rate (%)')
        ax1.set_title('Cache Hit Rates')
        ax1.set_xticks(range(max(len(tiers_2), len(tiers_3))))
        ax1.set_xticklabels(tiers_2 + [t for t in tiers_3 if t not in tiers_2], rotation=45)
        ax1.legend()
        ax1.grid(axis='y', alpha=0.3)

    # Chart 2: Latency Comparison (P95)
    ax2 = axes[0, 1]
    ops_2tier = set(metrics_2tier.get("latencies", {}).keys())
    ops_3tier = set(metrics_3tier.get("latencies", {}).keys())
    common_ops = sorted(list(ops_2tier.intersection(ops_3tier)))[:6]  # Top 6 operations

    if common_ops:
        p95_2 = [metrics_2tier["latencies"][op]["p95"] for op in common_ops]
        p95_3 = [metrics_3tier["latencies"][op]["p95"] for op in common_ops]

        x = range(len(common_ops))
        width = 0.35

        ax2.bar([i - width/2 for i in x], p95_2, width, label='2-Tier', alpha=0.8)
        ax2.bar([i + width/2 for i in x], p95_3, width, label='3-Tier', alpha=0.8)

        ax2.set_ylabel('Latency (ms)')
        ax2.set_title('P95 Latency Comparison')
        ax2.set_xticks(x)
        ax2.set_xticklabels([op.replace('get_', '').replace('_', '\n') for op in common_ops],
                           rotation=45, ha='right', fontsize=8)
        ax2.legend()
        ax2.grid(axis='y', alpha=0.3)
        ax2.set_yscale('log')

    # Chart 3: API Call Count
    ax3 = axes[1, 0]
    if "get_bar_api_fetch" in metrics_2tier.get("latencies", {}):
        api_counts = {
            '2-Tier': metrics_2tier["latencies"]["get_bar_api_fetch"]["count"],
            '3-Tier': metrics_3tier["latencies"]["get_bar_api_fetch"]["count"]
        }

        bars = ax3.bar(api_counts.keys(), api_counts.values(), alpha=0.8, color=['#1f77b4', '#ff7f0e'])
        ax3.set_ylabel('Number of API Calls')
        ax3.set_title('API Fetch Count')
        ax3.grid(axis='y', alpha=0.3)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height):,}',
                    ha='center', va='bottom')

    # Chart 4: Total Runtime
    ax4 = axes[1, 1]
    runtimes = {
        '2-Tier': metrics_2tier.get("total_runtime_seconds", 0),
        '3-Tier': metrics_3tier.get("total_runtime_seconds", 0)
    }

    bars = ax4.bar(runtimes.keys(), runtimes.values(), alpha=0.8, color=['#1f77b4', '#ff7f0e'])
    ax4.set_ylabel('Time (seconds)')
    ax4.set_title('Total Runtime')
    ax4.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}s',
                ha='center', va='bottom')

    plt.tight_layout()

    # Save chart
    chart_path = output_dir / "comparison_charts.png"
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    print(f"✓ Charts saved to {chart_path}")

    plt.close()


def main():
    """Main entry point."""
    output_dir = Path('./profiling_output')

    # Load metrics
    print("Loading test results...")
    metrics_2tier = load_metrics(output_dir / "metrics_2-tier.json")
    metrics_3tier = load_metrics(output_dir / "metrics_3-tier.json")

    if not metrics_2tier or not metrics_3tier:
        print("\nError: Both 2-tier and 3-tier test results are required.")
        print("Please run both tests first:")
        print("  python main.py --mode 2-tier --duration 60")
        print("  python main.py --mode 3-tier --duration 60")
        return 1

    # Generate text report
    generate_text_report(metrics_2tier, metrics_3tier)

    # Generate charts
    try:
        generate_charts(metrics_2tier, metrics_3tier, output_dir)
    except Exception as e:
        print(f"Warning: Could not generate charts: {e}")

    print("✓ Report generation complete\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
