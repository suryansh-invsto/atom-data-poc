#!/usr/bin/env python3
"""Comprehensive test: 500 strategies, 500 instruments with timeframe aggregation."""

import os
import sys
import json
import asyncio
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from src.data_services import TwoTierDataService, ThreeTierDataService
from src.mock_data_service import MockThreeTierDataService, Mock2TierDataService
from src.load_strategies import StrategyGenerator
from src.system_metrics import SystemMetricsCollector


def aggregate_to_5min(bars_1m):
    """Aggregate 1-minute bars to 5-minute bars."""
    start = time.perf_counter()
    bars_5m = []

    for i in range(0, len(bars_1m), 5):
        chunk = bars_1m[i:i+5]
        if not chunk:
            continue

        bars_5m.append({
            "instrument": chunk[0]["instrument"],
            "starttime": chunk[0]["starttime"],
            "open": chunk[0]["open"],
            "high": max(b["high"] for b in chunk),
            "low": min(b["low"] for b in chunk),
            "close": chunk[-1]["close"],
            "volume": sum(b["volume"] for b in chunk)
        })

    latency_ms = (time.perf_counter() - start) * 1000
    return bars_5m, latency_ms


def aggregate_to_15min(bars_1m):
    """Aggregate 1-minute bars to 15-minute bars."""
    start = time.perf_counter()
    bars_15m = []

    for i in range(0, len(bars_1m), 15):
        chunk = bars_1m[i:i+15]
        if not chunk:
            continue

        bars_15m.append({
            "instrument": chunk[0]["instrument"],
            "starttime": chunk[0]["starttime"],
            "open": chunk[0]["open"],
            "high": max(b["high"] for b in chunk),
            "low": min(b["low"] for b in chunk),
            "close": chunk[-1]["close"],
            "volume": sum(b["volume"] for b in chunk)
        })

    latency_ms = (time.perf_counter() - start) * 1000
    return bars_15m, latency_ms


async def run_comprehensive_test(cache_mode: str):
    """
    Run comprehensive test with:
    - 500 strategies
    - ~500 instruments
    - Multi-timeframe aggregation
    - Detailed metrics
    """

    print(f"\n{'='*70}")
    print(f"COMPREHENSIVE TEST: {cache_mode.upper()}")
    print(f"{'='*70}\n")

    # Setup
    output_dir = Path('./comprehensive_results')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select data service based on mode
    if cache_mode == "2-tier":
        data_service = TwoTierDataService()
    elif cache_mode == "3-tier":
        data_service = ThreeTierDataService()
    elif cache_mode == "mock-3tier":
        data_service = MockThreeTierDataService()
    elif cache_mode == "mock-2tier":
        data_service = Mock2TierDataService()
    else:
        raise ValueError(f"Invalid cache mode: {cache_mode}")

    generator = StrategyGenerator()
    system_metrics = SystemMetricsCollector()

    # Generate 500 strategies
    print("[1/6] Generating 500 strategies...")
    strategies = generator.generate_strategies(500)
    stats = generator.get_statistics(strategies)

    print(f"  ✓ Total strategies: {stats['total_strategies']}")
    print(f"  ✓ Unique instruments: {stats['instruments']['unique_count']}")
    print(f"  ✓ Total instrument slots: {stats['instruments']['total_count']}")
    print(f"  ✓ Avg instruments per strategy: {stats['instruments']['avg_per_strategy']:.1f}")

    # Inject data service
    for strategy in strategies:
        strategy.data_service = data_service

    # Start metrics collection
    system_metrics.start_collection()

    # Warmup
    print("\n[2/6] Warming up caches...")
    warmup_start = time.time()

    unique_requests = set()
    for strategy in strategies:
        for instrument in strategy.instruments:
            unique_requests.add((instrument, strategy.lookback, strategy.timeframe))

    print(f"  Warming up {len(unique_requests)} unique requests in batches...")
    batch_size = 50
    requests_list = list(unique_requests)

    for i in range(0, len(requests_list), batch_size):
        batch = requests_list[i:i+batch_size]
        warmup_tasks = [
            data_service.get_bars(instrument, lookback, timeframe)
            for instrument, lookback, timeframe in batch
        ]
        await asyncio.gather(*warmup_tasks)
        if (i + batch_size) % 200 == 0:
            print(f"    ...warmed up {i+batch_size}/{len(requests_list)}")

    warmup_time = time.time() - warmup_start
    print(f"  ✓ Warmup completed in {warmup_time:.2f}s")

    system_metrics.collect_snapshot()

    # Test: Fetch 1m bars
    print("\n[3/6] Testing 1m bar fetches (10 simulated minutes)...")
    test_1m_start = time.time()

    fetch_times_1m = []
    for minute in range(10):
        minute_tasks = []
        for strategy in strategies:
            if minute % (60 if strategy.timeframe == "60m" else
                        15 if strategy.timeframe == "15m" else
                        5 if strategy.timeframe == "5m" else 1) == 0:
                minute_tasks.append(strategy.on_bar(None))

        if minute_tasks:
            iter_start = time.perf_counter()
            await asyncio.gather(*minute_tasks)
            fetch_times_1m.append((time.perf_counter() - iter_start) * 1000)

    test_1m_time = time.time() - test_1m_start
    print(f"  ✓ 1m test completed in {test_1m_time:.2f}s")
    print(f"  ✓ Avg iteration: {sum(fetch_times_1m)/len(fetch_times_1m):.2f}ms")

    system_metrics.collect_snapshot()

    # Test: Aggregate to 5m
    print("\n[4/6] Testing 5m aggregation from 1m bars...")
    agg_5m_start = time.time()

    agg_times_5m = []
    sample_instruments = list(set(s.instruments[0] for s in strategies[:100]))

    for instrument in sample_instruments:
        bars_1m = await data_service.get_bars(instrument, 100, "1m")
        _, latency = aggregate_to_5min(bars_1m)
        agg_times_5m.append(latency)

    agg_5m_time = time.time() - agg_5m_start
    print(f"  ✓ 5m aggregation test completed in {agg_5m_time:.2f}s")
    print(f"  ✓ Avg aggregation time: {sum(agg_times_5m)/len(agg_times_5m):.4f}ms")
    print(f"  ✓ Tested {len(sample_instruments)} instruments")

    # Test: Aggregate to 15m
    print("\n[5/6] Testing 15m aggregation from 1m bars...")
    agg_15m_start = time.time()

    agg_times_15m = []
    for instrument in sample_instruments:
        bars_1m = await data_service.get_bars(instrument, 300, "1m")
        _, latency = aggregate_to_15min(bars_1m)
        agg_times_15m.append(latency)

    agg_15m_time = time.time() - agg_15m_start
    print(f"  ✓ 15m aggregation test completed in {agg_15m_time:.2f}s")
    print(f"  ✓ Avg aggregation time: {sum(agg_times_15m)/len(agg_times_15m):.4f}ms")

    system_metrics.collect_snapshot()

    # Final metrics
    print("\n[6/6] Collecting final metrics...")
    perf_summary = data_service.metrics.get_summary()
    sys_summary = system_metrics.get_summary()

    # Compile results
    results = {
        "test_name": "comprehensive_500x500",
        "cache_mode": cache_mode,
        "strategy_count": 500,
        "instrument_count": stats['instruments']['unique_count'],
        "timestamp": datetime.now().isoformat(),
        "timings": {
            "warmup_seconds": warmup_time,
            "test_1m_seconds": test_1m_time,
            "agg_5m_seconds": agg_5m_time,
            "agg_15m_seconds": agg_15m_time,
            "fetch_1m_iterations_ms": {
                "avg": sum(fetch_times_1m) / len(fetch_times_1m),
                "min": min(fetch_times_1m),
                "max": max(fetch_times_1m),
                "p50": sorted(fetch_times_1m)[len(fetch_times_1m)//2],
                "p99": sorted(fetch_times_1m)[int(len(fetch_times_1m)*0.99)]
            },
            "aggregation_5m_ms": {
                "avg": sum(agg_times_5m) / len(agg_times_5m),
                "min": min(agg_times_5m),
                "max": max(agg_times_5m),
                "count": len(agg_times_5m)
            },
            "aggregation_15m_ms": {
                "avg": sum(agg_times_15m) / len(agg_times_15m),
                "min": min(agg_times_15m),
                "max": max(agg_times_15m),
                "count": len(agg_times_15m)
            }
        },
        "strategy_stats": stats,
        "performance": perf_summary,
        "system": sys_summary
    }

    # Save results
    result_file = output_dir / f"comprehensive_{cache_mode}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Results saved to {result_file}")

    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Memory (Python RSS):")
    print(f"  Average: {sys_summary['memory']['avg_rss_mb']:.1f} MB")
    print(f"  Peak:    {sys_summary['memory']['max_rss_mb']:.1f} MB")
    print(f"\nTimings:")
    print(f"  Warmup:       {warmup_time:.2f}s")
    print(f"  1m test:      {test_1m_time:.2f}s")
    print(f"  5m agg test:  {agg_5m_time:.2f}s (avg {sum(agg_times_5m)/len(agg_times_5m):.4f}ms per)")
    print(f"  15m agg test: {agg_15m_time:.2f}s (avg {sum(agg_times_15m)/len(agg_times_15m):.4f}ms per)")
    print(f"\nCache Hit Rates:")
    for tier, stats in perf_summary.get('cache_hit_rates', {}).items():
        print(f"  {tier:15s}: {stats['rate']:.2f}%")
    print(f"{'='*70}\n")

    return results


def main():
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python comprehensive_test.py [mock-2tier|mock-3tier|2-tier|3-tier]")
        return 1

    cache_mode = sys.argv[1]

    try:
        asyncio.run(run_comprehensive_test(cache_mode))
        print("\n✅ Comprehensive test complete!")
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
