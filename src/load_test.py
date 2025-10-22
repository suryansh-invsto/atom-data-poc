"""Load test orchestration for cache architecture comparison."""

import asyncio
from datetime import datetime, timedelta
from typing import List

from .data_services import TwoTierDataService, ThreeTierDataService
from .strategies import get_all_strategies, BaseStrategy
from .metrics import PerformanceMetrics


class LoadTest:
    """Orchestrates load testing for cache architecture comparison."""

    def __init__(self, cache_mode: str):
        self.cache_mode = cache_mode

        # Create appropriate data service
        if cache_mode == "2-tier":
            self.data_service = TwoTierDataService()
        elif cache_mode == "3-tier":
            self.data_service = ThreeTierDataService()
        else:
            raise ValueError(f"Invalid cache mode: {cache_mode}. Use '2-tier' or '3-tier'")

        # Create strategies and inject data service
        self.strategies = get_all_strategies()
        for strategy in self.strategies:
            strategy.data_service = self.data_service

        print(f"\n{'='*60}")
        print(f"Initialized {cache_mode.upper()} Load Test")
        print(f"{'='*60}")
        print(f"Strategies:")
        for strategy in self.strategies:
            print(f"  - {strategy}")

    async def run_test(self, duration_minutes: int = 60) -> PerformanceMetrics:
        """
        Run load test for specified duration.

        Args:
            duration_minutes: How long to run the test (simulated time)

        Returns:
            PerformanceMetrics object with results
        """
        print(f"\nStarting test for {duration_minutes} simulated minutes...")

        # Simulated time starts at market open
        simulated_time = datetime(2025, 1, 15, 9, 30)

        # Warm-up phase - populate caches
        print("\n[Warmup] Populating caches with initial data...")
        await self._warmup()
        print("[Warmup] Complete")

        # Main test loop
        print(f"\n[Test] Running main test loop...")
        start_time = datetime.now()

        for minute in range(duration_minutes):
            minute_tasks = []

            # Trigger 1-minute strategies (Scalper, DayTrader)
            if minute % 1 == 0:
                minute_tasks.append(self.strategies[0].on_bar(simulated_time))  # Scalper
                minute_tasks.append(self.strategies[1].on_bar(simulated_time))  # DayTrader

            # Trigger 5-minute strategy (Swing)
            if minute % 5 == 0:
                minute_tasks.append(self.strategies[2].on_bar(simulated_time))  # Swing

            # Trigger 15-minute strategy (Position)
            if minute % 15 == 0:
                minute_tasks.append(self.strategies[3].on_bar(simulated_time))  # Position

            # Execute all strategies for this minute in parallel
            if minute_tasks:
                await asyncio.gather(*minute_tasks)

            # Advance simulated time
            simulated_time += timedelta(minutes=1)

            # Progress update every 10 minutes
            if minute % 10 == 0 and minute > 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"\n[{minute}/{duration_minutes}m] Elapsed: {elapsed:.1f}s")
                self.data_service.metrics.print_interim_stats(minute)

        # Final statistics
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n[Test] Complete - Total elapsed: {elapsed:.1f}s")

        return self.data_service.metrics

    async def _warmup(self):
        """
        Pre-fetch data to warm caches.
        Simulates strategies fetching initial historical data.
        """
        warmup_tasks = []

        for strategy in self.strategies:
            for instrument in strategy.instruments:
                # Fetch historical data needed by each strategy
                warmup_tasks.append(
                    self.data_service.get_bars(
                        instrument,
                        strategy.lookback,
                        strategy.timeframe
                    )
                )

        # Execute all warmup fetches in parallel
        await asyncio.gather(*warmup_tasks)

    def print_summary(self):
        """Print detailed test summary."""
        summary = self.data_service.metrics.get_summary()

        print(f"\n{'='*60}")
        print(f"{self.cache_mode.upper()} Test Results Summary")
        print(f"{'='*60}")

        # Strategy execution stats
        print("\nStrategy Execution Counts:")
        for strategy in self.strategies:
            print(f"  {strategy.name}: {strategy.execution_count} times")

        # Cache hit rates
        print("\nCache Hit Rates:")
        if summary["cache_hit_rates"]:
            for tier, stats in summary["cache_hit_rates"].items():
                print(f"  {tier:15s}: {stats['rate']:6.2f}% "
                      f"({stats['hits']:,} hits / {stats['total']:,} total)")
        else:
            print("  No cache statistics available")

        # Latency statistics
        print("\nLatency Statistics (milliseconds):")
        if summary["latencies"]:
            # Group by operation type
            for op, stats in sorted(summary["latencies"].items()):
                print(f"\n  {op}:")
                print(f"    p50: {stats['p50']:8.3f}ms")
                print(f"    p95: {stats['p95']:8.3f}ms")
                print(f"    p99: {stats['p99']:8.3f}ms")
                print(f"    avg: {stats['avg']:8.3f}ms")
                print(f"    min: {stats['min']:8.3f}ms")
                print(f"    max: {stats['max']:8.3f}ms")
                print(f"    count: {stats['count']:,}")
        else:
            print("  No latency statistics available")

        # Total runtime
        print(f"\nTotal Runtime: {summary['total_runtime_seconds']:.2f} seconds")

        print(f"{'='*60}\n")
