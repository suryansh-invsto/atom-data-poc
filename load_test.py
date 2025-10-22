#!/usr/bin/env python3
"""Progressive load test runner for cache architecture comparison."""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from src.data_services import TwoTierDataService, ThreeTierDataService
from src.mock_data_service import MockThreeTierDataService
from src.load_strategies import StrategyGenerator
from src.system_metrics import SystemMetricsCollector
from src.metrics import PerformanceMetrics


class ProgressiveLoadTest:
    """Run progressive load tests with increasing strategy counts."""

    def __init__(self, cache_mode: str, output_dir: Path):
        self.cache_mode = cache_mode
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create data service
        if cache_mode == "2-tier":
            self.data_service = TwoTierDataService()
        elif cache_mode == "3-tier":
            self.data_service = ThreeTierDataService()
        elif cache_mode == "mock":
            self.data_service = MockThreeTierDataService()
        else:
            raise ValueError(f"Invalid cache mode: {cache_mode}")

        self.generator = StrategyGenerator()
        self.all_results = []

    async def run_single_test(self, strategy_count: int, duration_minutes: int = 10):
        """
        Run a single load test with specified number of strategies.

        Args:
            strategy_count: Number of strategies to test
            duration_minutes: Duration of test in simulated minutes

        Returns:
            Dict with test results
        """
        print(f"\n{'='*70}")
        print(f"Load Test: {strategy_count} Strategies ({self.cache_mode})")
        print(f"{'='*70}")

        # Generate strategies
        print(f"\n[Setup] Generating {strategy_count} strategies...")
        strategies = self.generator.generate_strategies(strategy_count)

        # Print statistics
        stats = self.generator.get_statistics(strategies)
        print(f"  Total instruments in pool: {stats['instruments']['unique_count']}")
        print(f"  Total instrument slots: {stats['instruments']['total_count']}")
        print(f"  Avg instruments per strategy: {stats['instruments']['avg_per_strategy']:.1f}")
        print(f"\n  Strategy distribution:")
        for stype, count in stats['by_type'].items():
            print(f"    {stype:20s}: {count:3d} strategies")

        # Inject data service into strategies
        for strategy in strategies:
            strategy.data_service = self.data_service

        # Initialize metrics collector
        system_metrics = SystemMetricsCollector()
        system_metrics.start_collection()

        # Warmup phase
        print(f"\n[Warmup] Populating caches...")
        await self._warmup_phase(strategies)

        # Collect metrics after warmup
        system_metrics.collect_snapshot()

        # Main test loop
        print(f"\n[Test] Running for {duration_minutes} simulated minutes...")
        start_time = asyncio.get_event_loop().time()

        simulated_minute = 0
        while simulated_minute < duration_minutes:
            # Determine which strategies to execute
            minute_tasks = []

            for strategy in strategies:
                should_execute = self._should_execute_strategy(strategy, simulated_minute)
                if should_execute:
                    minute_tasks.append(strategy.on_bar(None))

            # Execute all strategies for this minute
            if minute_tasks:
                await asyncio.gather(*minute_tasks)

            # Collect system metrics every 10 minutes
            if simulated_minute % 10 == 0 and simulated_minute > 0:
                system_metrics.collect_snapshot()
                self._print_interim_stats(simulated_minute, system_metrics)

            simulated_minute += 1

        # Final metrics collection
        elapsed = asyncio.get_event_loop().time() - start_time
        system_metrics.collect_snapshot()

        print(f"\n[Complete] Total elapsed: {elapsed:.2f}s")

        # Compile results
        perf_summary = self.data_service.metrics.get_summary()
        sys_summary = system_metrics.get_summary()

        results = {
            "strategy_count": strategy_count,
            "cache_mode": self.cache_mode,
            "duration_minutes": duration_minutes,
            "wall_clock_seconds": elapsed,
            "strategy_stats": stats,
            "performance": perf_summary,
            "system": sys_summary,
            "timestamp": datetime.now().isoformat()
        }

        return results

    async def _warmup_phase(self, strategies):
        """Pre-fetch data to warm caches."""
        # Get unique instrument/lookback combinations
        unique_requests = set()
        for strategy in strategies:
            for instrument in strategy.instruments:
                unique_requests.add((instrument, strategy.lookback, strategy.timeframe))

        print(f"  Warming up {len(unique_requests)} unique data requests...")

        # Batch requests to avoid overwhelming the API (max 50 concurrent)
        batch_size = 50
        requests_list = list(unique_requests)

        for i in range(0, len(requests_list), batch_size):
            batch = requests_list[i:i+batch_size]
            warmup_tasks = [
                self.data_service.get_bars(instrument, lookback, timeframe)
                for instrument, lookback, timeframe in batch
            ]
            await asyncio.gather(*warmup_tasks)
            if i + batch_size < len(requests_list):
                print(f"    Warmed up {i+batch_size}/{len(requests_list)}...")
                await asyncio.sleep(0.5)  # Small delay between batches

    def _should_execute_strategy(self, strategy, simulated_minute: int) -> bool:
        """Determine if strategy should execute this minute."""
        timeframe_intervals = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "60m": 60
        }

        interval = timeframe_intervals.get(strategy.timeframe, 1)
        return simulated_minute % interval == 0

    def _print_interim_stats(self, minute: int, system_metrics: SystemMetricsCollector):
        """Print interim statistics."""
        snapshot = system_metrics.snapshots[-1]
        print(f"\n[{minute}m] System Status:")
        print(f"  CPU: {snapshot.cpu_percent:.1f}%")
        print(f"  Memory: {snapshot.memory_rss_mb:.1f} MB ({snapshot.memory_percent:.1f}%)")
        print(f"  Threads: {snapshot.num_threads}")

    def print_results(self, results: dict):
        """Print detailed test results."""
        print(f"\n{'='*70}")
        print(f"Results: {results['strategy_count']} Strategies ({results['cache_mode']})")
        print(f"{'='*70}")

        # Performance metrics
        perf = results['performance']
        if 'latencies' in perf and perf['latencies']:
            print(f"\nPerformance Latencies:")
            for op, stats in sorted(perf['latencies'].items())[:5]:  # Top 5
                print(f"  {op:30s}: p50={stats['p50']:.3f}ms, p99={stats['p99']:.3f}ms, "
                      f"avg={stats['avg']:.3f}ms ({stats['count']} calls)")

        # Cache hit rates
        if 'cache_hit_rates' in perf and perf['cache_hit_rates']:
            print(f"\nCache Hit Rates:")
            for tier, stats in perf['cache_hit_rates'].items():
                print(f"  {tier:15s}: {stats['rate']:.2f}%")

        # System metrics
        sys = results['system']
        print(f"\nSystem Resources:")
        print(f"  CPU Average:  {sys['cpu']['avg_percent']:.1f}%")
        print(f"  CPU Peak:     {sys['cpu']['max_percent']:.1f}%")
        print(f"  Memory Avg:   {sys['memory']['avg_rss_mb']:.1f} MB")
        print(f"  Memory Peak:  {sys['memory']['max_rss_mb']:.1f} MB")
        print(f"  Network Sent: {sys['network']['total_sent_mb']:.2f} MB")
        print(f"  Network Recv: {sys['network']['total_recv_mb']:.2f} MB")

        print(f"\nTotal Runtime: {results['wall_clock_seconds']:.2f}s")
        print(f"{'='*70}\n")

    async def run_progressive_tests(self, test_levels: list, duration_minutes: int = 10):
        """
        Run tests with progressively increasing load.

        Args:
            test_levels: List of strategy counts to test
            duration_minutes: Duration for each test
        """
        print(f"\n{'#'*70}")
        print(f"# Progressive Load Test: {self.cache_mode}")
        print(f"# Test Levels: {test_levels}")
        print(f"# Duration per test: {duration_minutes} minutes")
        print(f"{'#'*70}")

        for strategy_count in test_levels:
            # Run test
            results = await self.run_single_test(strategy_count, duration_minutes)

            # Save results
            filename = f"load_test_{self.cache_mode}_{strategy_count}strat.json"
            filepath = self.output_dir / filename
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n[Saved] Results to {filepath}")

            # Print summary
            self.print_results(results)

            # Store for final comparison
            self.all_results.append(results)

            # Check if system is degrading
            if not self._check_health_metrics(results):
                print(f"\n⚠️  System performance degraded at {strategy_count} strategies")
                print(f"Stopping progressive test.")
                break

        # Generate final summary
        self._generate_summary_report()

    def _check_health_metrics(self, results: dict) -> bool:
        """Check if system is still healthy."""
        perf = results['performance']
        sys = results['system']

        # Get worst P99 latency, excluding API fetches (they're expected to be slow)
        if 'latencies' in perf:
            p99_latencies = [
                stats.get('p99', 0)
                for op, stats in perf['latencies'].items()
                if '_api' not in op and 'api_fetch' not in op  # Exclude API operations
            ]
            max_p99 = max(p99_latencies) if p99_latencies else 0
        else:
            max_p99 = 0

        # Health criteria
        p99_ok = max_p99 < 200  # P99 < 200ms for cache hits
        memory_ok = sys['memory']['peak_percent'] < 80  # Memory < 80%
        cpu_ok = sys['cpu']['max_percent'] < 95  # CPU < 95%

        return p99_ok and memory_ok and cpu_ok

    def _generate_summary_report(self):
        """Generate final summary comparing all test levels."""
        if not self.all_results:
            return

        summary_file = self.output_dir / f"summary_{self.cache_mode}.md"

        with open(summary_file, 'w') as f:
            f.write(f"# Load Test Summary: {self.cache_mode}\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")

            # Results table
            f.write("## Performance vs Strategy Count\n\n")
            f.write("| Strategies | P50 Latency | P99 Latency | CPU % | Memory MB | Wall Time |\n")
            f.write("|------------|-------------|-------------|-------|-----------|-----------|\\n")

            for result in self.all_results:
                count = result['strategy_count']

                # Get representative latency
                if result['performance']['latencies']:
                    first_op = list(result['performance']['latencies'].values())[0]
                    p50 = first_op['p50']
                    p99 = first_op['p99']
                else:
                    p50 = p99 = 0

                cpu = result['system']['cpu']['avg_percent']
                memory = result['system']['memory']['avg_rss_mb']
                wall_time = result['wall_clock_seconds']

                f.write(f"| {count:10d} | {p50:11.3f} | {p99:11.3f} | {cpu:5.1f} | {memory:9.1f} | {wall_time:9.2f} |\n")

        print(f"\n📊 Summary report saved to {summary_file}")


def main():
    parser = argparse.ArgumentParser(description="Progressive load test for cache architectures")

    parser.add_argument('--mode', choices=['2-tier', '3-tier', 'mock'], required=True,
                        help='Cache architecture to test (mock = 3-tier with simulated data)')
    parser.add_argument('--levels', type=int, nargs='+', default=[10, 25, 50, 100],
                        help='Strategy counts to test (default: 10 25 50 100)')
    parser.add_argument('--duration', type=int, default=10,
                        help='Duration per test in simulated minutes (default: 10)')
    parser.add_argument('--output', type=Path, default=Path('./load_test_results'),
                        help='Output directory (default: ./load_test_results)')

    args = parser.parse_args()

    # Load environment
    load_dotenv()

    # Run tests
    tester = ProgressiveLoadTest(args.mode, args.output)

    try:
        asyncio.run(tester.run_progressive_tests(args.levels, args.duration))
        print("\n✅ Load testing complete!")
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
