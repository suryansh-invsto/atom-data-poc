#!/usr/bin/env python3
"""Generate detailed timing profile with explicit millisecond measurements."""

import cProfile
import pstats
import io
import sys
from pathlib import Path

def profile_test(mode: str):
    """Profile a comprehensive test and generate detailed timing report."""

    # Import here to avoid early execution
    from comprehensive_test import run_comprehensive_test
    import asyncio

    # Create profiler
    profiler = cProfile.Profile()

    print(f"\n{'='*70}")
    print(f"Profiling {mode.upper()} with detailed timing...")
    print(f"{'='*70}\n")

    # Profile the test
    profiler.enable()
    asyncio.run(run_comprehensive_test(mode))
    profiler.disable()

    # Save raw stats
    output_dir = Path('./comprehensive_results')
    stats_file = output_dir / f'profile_{mode}.stats'
    profiler.dump_stats(str(stats_file))
    print(f"\n✓ Raw profile saved to {stats_file}")

    # Generate detailed text report
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)

    # Sort by cumulative time
    ps.strip_dirs()
    ps.sort_stats('cumulative')

    # Generate report
    report_file = output_dir / f'profile_{mode}_timing.txt'

    with open(report_file, 'w') as f:
        f.write(f"{'='*80}\n")
        f.write(f"Detailed Timing Profile: {mode.upper()}\n")
        f.write(f"{'='*80}\n\n")

        # Get stats
        stats = ps.stats

        # Sort by cumulative time
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: x[1][3],  # cumulative time
            reverse=True
        )

        f.write(f"{'Function':<60} {'Calls':>10} {'Total(ms)':>12} {'Per Call(ms)':>14} {'Cumul(ms)':>12}\n")
        f.write(f"{'-'*60} {'-'*10} {'-'*12} {'-'*14} {'-'*12}\n")

        # Top 50 functions
        for i, (func, (cc, nc, tt, ct, callers)) in enumerate(sorted_stats[:50]):
            filename, line, func_name = func

            # Clean up function name
            if filename.startswith('/'):
                filename = filename.split('/')[-1]

            func_display = f"{filename}:{line}({func_name})"[:60]

            # Convert to milliseconds
            total_ms = tt * 1000
            per_call_ms = (tt / nc * 1000) if nc > 0 else 0
            cumul_ms = ct * 1000

            f.write(f"{func_display:<60} {nc:>10} {total_ms:>12.3f} {per_call_ms:>14.6f} {cumul_ms:>12.3f}\n")

        f.write(f"\n{'='*80}\n")
        f.write("Legend:\n")
        f.write("  Calls: Number of times function was called\n")
        f.write("  Total(ms): Total time spent in function (excluding subfunctions)\n")
        f.write("  Per Call(ms): Average time per call\n")
        f.write("  Cumul(ms): Cumulative time (including subfunctions)\n")
        f.write(f"{'='*80}\n")

        # Add summary statistics
        f.write("\n\nSUMMARY STATISTICS\n")
        f.write("="*80 + "\n\n")

        total_calls = sum(nc for _, (cc, nc, tt, ct, callers) in stats.items())
        total_time_ms = sum(tt for _, (cc, nc, tt, ct, callers) in stats.items()) * 1000

        f.write(f"Total function calls: {total_calls:,}\n")
        f.write(f"Total time: {total_time_ms:.2f} ms\n")
        f.write(f"Average call time: {total_time_ms/total_calls:.6f} ms\n\n")

        # Find key operations
        f.write("\nKEY OPERATIONS\n")
        f.write("="*80 + "\n\n")

        for func, (cc, nc, tt, ct, callers) in sorted_stats:
            filename, line, func_name = func

            # Look for specific operations
            if any(keyword in func_name.lower() for keyword in ['get_bar', 'redis', 'memory', 'aggregate']):
                if nc > 0:  # Only if called
                    func_display = f"{filename.split('/')[-1]}:{line}({func_name})"
                    total_ms = tt * 1000
                    per_call_ms = (tt / nc * 1000)
                    cumul_ms = ct * 1000

                    f.write(f"{func_display}\n")
                    f.write(f"  Calls: {nc:,}\n")
                    f.write(f"  Total time: {total_ms:.3f} ms\n")
                    f.write(f"  Per call: {per_call_ms:.6f} ms\n")
                    f.write(f"  Cumulative: {cumul_ms:.3f} ms\n\n")

    print(f"✓ Detailed timing report saved to {report_file}")

    # Also print top 10 to console
    print(f"\n{'='*80}")
    print("TOP 10 FUNCTIONS BY CUMULATIVE TIME")
    print(f"{'='*80}\n")
    print(f"{'Function':<50} {'Calls':>10} {'Cumul(ms)':>12}")
    print(f"{'-'*50} {'-'*10} {'-'*12}")

    for i, (func, (cc, nc, tt, ct, callers)) in enumerate(sorted_stats[:10]):
        filename, line, func_name = func
        func_display = f"{filename.split('/')[-1]}:{func_name}"[:50]
        cumul_ms = ct * 1000
        print(f"{func_display:<50} {nc:>10} {cumul_ms:>12.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python profile_with_timing.py [mock-2tier|mock-3tier]")
        sys.exit(1)

    mode = sys.argv[1]
    profile_test(mode)

    print(f"\n{'='*80}")
    print("✅ Profiling complete!")
    print(f"{'='*80}\n")
