#!/usr/bin/env python3
"""Main test runner with profiling for cache architecture POC."""

import os
import sys
import json
import asyncio
import argparse
import tracemalloc
import cProfile
import pstats
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from src.load_test import LoadTest


async def run_test_with_profiling(cache_mode: str, duration: int, output_dir: Path):
    """
    Run load test with comprehensive profiling.

    Args:
        cache_mode: Either '2-tier' or '3-tier'
        duration: Test duration in simulated minutes
        output_dir: Directory to save profiling results
    """
    print(f"\n{'='*60}")
    print(f"Cache Architecture Performance POC")
    print(f"{'='*60}")
    print(f"Mode: {cache_mode}")
    print(f"Duration: {duration} simulated minutes")
    print(f"Output: {output_dir}")
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Start memory tracking
    print("\n[Profiling] Starting memory tracking...")
    tracemalloc.start()

    # Start CPU profiling
    print("[Profiling] Starting CPU profiling...")
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        # Run the actual test
        test = LoadTest(cache_mode)
        metrics = await test.run_test(duration)

        # Print summary
        test.print_summary()

    finally:
        # Stop CPU profiling
        profiler.disable()

        # Save CPU profile
        cpu_profile_path = output_dir / f"cpu_{cache_mode}.prof"
        print(f"\n[Profiling] Saving CPU profile to {cpu_profile_path}...")
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.dump_stats(str(cpu_profile_path))

        # Generate text report
        cpu_report_path = output_dir / f"cpu_{cache_mode}.txt"
        with open(cpu_report_path, 'w') as f:
            stats = pstats.Stats(profiler, stream=f)
            stats.sort_stats('cumulative')
            stats.print_stats(50)  # Top 50 functions
        print(f"[Profiling] CPU report saved to {cpu_report_path}")

        # Memory snapshot
        print(f"[Profiling] Capturing memory snapshot...")
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')

        # Save memory profile
        memory_profile_path = output_dir / f"memory_{cache_mode}.txt"
        with open(memory_profile_path, 'w') as f:
            f.write(f"Top 50 Memory Allocations - {cache_mode}\n")
            f.write("="*80 + "\n\n")
            for stat in top_stats[:50]:
                f.write(f"{stat}\n")
        print(f"[Profiling] Memory profile saved to {memory_profile_path}")

        tracemalloc.stop()

        # Save metrics as JSON
        summary = metrics.get_summary()
        metrics_path = output_dir / f"metrics_{cache_mode}.json"
        print(f"[Profiling] Saving metrics to {metrics_path}...")
        with open(metrics_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n[Complete] All results saved to {output_dir}/")

        return summary


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run cache architecture performance POC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run 2-tier test for 60 minutes
  python main.py --mode 2-tier --duration 60

  # Run 3-tier test for 30 minutes
  python main.py --mode 3-tier --duration 30

  # Run with custom output directory
  python main.py --mode 3-tier --duration 60 --output ./results
        """
    )

    parser.add_argument(
        '--mode',
        choices=['2-tier', '3-tier'],
        required=True,
        help='Cache architecture mode to test'
    )

    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Test duration in simulated minutes (default: 60)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path('./profiling_output'),
        help='Output directory for results (default: ./profiling_output)'
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Validate environment
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        print("ERROR: REDIS_URL not set. Please create .env file.", file=sys.stderr)
        print("Example: cp .env.example .env", file=sys.stderr)
        sys.exit(1)

    api_url = os.getenv('DATA_API_URL')
    if not api_url:
        print("ERROR: DATA_API_URL not set. Please create .env file.", file=sys.stderr)
        sys.exit(1)

    # Run test
    try:
        asyncio.run(run_test_with_profiling(args.mode, args.duration, args.output))
        print("\n✓ Test completed successfully")
        return 0
    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
        return 130
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
