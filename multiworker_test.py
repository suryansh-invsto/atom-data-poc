#!/usr/bin/env python3
"""Multi-worker comprehensive test for cache architecture comparison."""

import os
import sys
import json
import time
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

from src.load_strategies import StrategyGenerator
from src.worker_manager import (
    WorkerConfig, WorkerAssignment, WorkerStrategyAssigner,
    WorkerMetricsCollector, worker_process
)
from src.shared_cache import SharedMemoryCache


def run_multiworker_test(num_workers: int, cache_mode: str,
                         assignment_mode: WorkerAssignment,
                         num_strategies: int = 500):
    """
    Run multi-worker test.

    Args:
        num_workers: Number of worker processes
        cache_mode: "2-tier", "3-tier-redundant", or "3-tier-sticky"
        assignment_mode: Worker assignment strategy
        num_strategies: Total number of strategies to test
    """

    print(f"\n{'='*80}")
    print(f"MULTI-WORKER TEST")
    print(f"{'='*80}")
    print(f"Workers: {num_workers}")
    print(f"Cache Mode: {cache_mode}")
    print(f"Assignment: {assignment_mode.value}")
    print(f"Strategies: {num_strategies}")
    print(f"{'='*80}\n")

    # Generate strategies with controlled instrument distribution per worker
    print(f"[1/5] Generating {num_strategies} strategies with controlled distribution...")
    generator = StrategyGenerator(num_workers=num_workers)

    # Generate strategies per worker to ensure controlled instrument overlap
    strategies_per_worker = num_strategies // num_workers
    remainder = num_strategies % num_workers

    worker_strategies: List[List] = [[] for _ in range(num_workers)]
    all_strategies = []

    for worker_id in range(num_workers):
        # Add remainder to first worker
        count = strategies_per_worker + (1 if worker_id < remainder else 0)

        # Generate strategies for this worker using its instrument group
        strategies = generator.generate_strategies(count, worker_id=worker_id)

        worker_strategies[worker_id] = strategies
        all_strategies.extend(strategies)

    stats = generator.get_statistics(all_strategies)

    print(f"  ✓ Total strategies: {stats['total_strategies']}")
    print(f"  ✓ Unique instruments: {stats['instruments']['unique_count']}")
    print(f"  ✓ Total instrument slots: {stats['instruments']['total_count']}")
    print(f"  ✓ Strategies per worker: {[len(ws) for ws in worker_strategies]}")

    # Note: We're now directly generating per worker, so skip the assignment phase
    print(f"\n[2/5] Worker assignment (pre-generated with controlled distribution)...")
    assigner = WorkerStrategyAssigner(num_workers, assignment_mode)

    # Register strategies with assigner for statistics
    for worker_id, strategies in enumerate(worker_strategies):
        for strategy in strategies:
            assigner.strategy_to_worker[f"{strategy.strategy_type}_{strategy.strategy_id}"] = worker_id
            assigner.worker_loads[worker_id] += 1

    # Print assignment stats
    load_stats = assigner.get_load_balance_stats()
    print(f"  ✓ Strategies per worker: {load_stats['per_worker']}")
    print(f"  ✓ Min/Max/Avg: {load_stats['min_load']}/{load_stats['max_load']}/{load_stats['avg_load']:.1f}")
    print(f"  ✓ Imbalance factor: {load_stats['imbalance_factor']:.2f}x")

    # Calculate unique instruments per worker
    worker_instruments = []
    for strategies in worker_strategies:
        unique_insts = set()
        for s in strategies:
            unique_insts.update(s.instruments)
        worker_instruments.append(len(unique_insts))

    print(f"  ✓ Instruments per worker: {worker_instruments}")
    print(f"  ✓ Total unique instruments: {sum(worker_instruments)}")
    if cache_mode == "3-tier-redundant":
        print(f"  ⚠️  Cache redundancy: Each worker caches all {stats['instruments']['unique_count']} instruments")
    elif cache_mode == "3-tier-sticky":
        print(f"  ✓ Cache optimization: Workers only cache assigned instruments")

    # Setup shared cache if needed
    shared_cache = None
    if cache_mode == "3-tier-shared":
        print(f"\n  Setting up shared memory cache...")
        manager = mp.Manager()
        shared_cache = SharedMemoryCache(manager)
        print(f"  ✓ Shared cache initialized")

    # Spawn worker processes
    print(f"\n[3/5] Spawning {num_workers} worker processes...")

    result_queue = mp.Queue()
    error_queue = mp.Queue()
    processes = []

    start_time = time.time()

    for worker_id in range(num_workers):
        config = WorkerConfig(
            worker_id=worker_id,
            num_workers=num_workers,
            assignment_mode=assignment_mode,
            cache_mode=cache_mode
        )

        p = mp.Process(
            target=worker_process,
            args=(worker_id, config, worker_strategies[worker_id], result_queue, error_queue, shared_cache)
        )
        p.start()
        processes.append(p)
        print(f"  ✓ Started worker {worker_id} ({len(worker_strategies[worker_id])} strategies)")

    # Wait for all workers to complete (5 minutes + warmup time)
    print(f"\n[4/5] Waiting for workers to complete (~5 minutes real-time)...")
    for i, p in enumerate(processes):
        p.join()
        print(f"  ✓ Worker {i} finished")

    total_time = time.time() - start_time

    # Check for errors
    errors = []
    while not error_queue.empty():
        errors.append(error_queue.get())

    if errors:
        print(f"\n❌ Errors occurred in {len(errors)} workers:")
        for error in errors:
            print(f"  Worker {error['worker_id']}: {error['error']}")
            print(f"  {error['traceback']}")
        return None

    # Collect results
    print(f"\n[5/5] Collecting results from workers...")
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())

    results.sort(key=lambda x: x['worker_id'])

    # Aggregate metrics
    metrics_collector = WorkerMetricsCollector()
    for result in results:
        metrics_collector.add_worker_metrics(result['worker_id'], result)

    aggregate = metrics_collector.get_aggregate_metrics()

    # Compile full results
    full_results = {
        'test_name': f'multiworker_{num_workers}w_{cache_mode}_{assignment_mode.value}',
        'timestamp': datetime.now().isoformat(),
        'configuration': {
            'num_workers': num_workers,
            'cache_mode': cache_mode,
            'assignment_mode': assignment_mode.value,
            'num_strategies': num_strategies,
            'strategies_per_worker': load_stats['per_worker'],
            'instruments_per_worker': worker_instruments
        },
        'strategy_stats': stats,
        'load_balance': load_stats,
        'aggregate_metrics': aggregate,
        'worker_results': results,
        'total_wall_clock_seconds': total_time
    }

    # Save results
    output_dir = Path('./multiworker_results')
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"multiworker_{num_workers}w_{cache_mode}_{assignment_mode.value}.json"
    filepath = output_dir / filename

    with open(filepath, 'w') as f:
        json.dump(full_results, f, indent=2)

    print(f"\n✓ Results saved to {filepath}")

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total Memory (all workers): {aggregate['total_memory_mb']:.1f} MB")
    print(f"Avg Memory per worker: {aggregate['avg_memory_per_worker_mb']:.1f} MB")
    print(f"Memory redundancy factor: {aggregate['memory_redundancy_factor']:.2f}x")
    print(f"Total execution time: {total_time:.2f}s")
    print(f"Max worker execution time: {aggregate['total_execution_time_seconds']:.2f}s")

    print(f"\nCache Hit Rates:")
    for tier, stats in aggregate.get('cache_hit_rates', {}).items():
        print(f"  {tier:15s}: {stats['rate']:.2f}%")

    print(f"\nPer-Worker Memory:")
    for i, mem in enumerate(aggregate['per_worker_memory']):
        print(f"  Worker {i}: {mem:.1f} MB ({len(worker_strategies[i])} strategies, {worker_instruments[i]} instruments)")

    print(f"{'='*80}\n")

    return full_results


def main():
    load_dotenv()

    if len(sys.argv) < 4:
        print("Usage: python multiworker_test.py <num_workers> <cache_mode> <assignment_mode>")
        print("")
        print("  num_workers: Number of worker processes (e.g., 4)")
        print("  cache_mode: 2-tier | 3-tier-redundant | 3-tier-sticky | 3-tier-shared")
        print("  assignment_mode: random | sticky | least_loaded | sharded")
        print("")
        print("Examples:")
        print("  python multiworker_test.py 4 2-tier sticky")
        print("  python multiworker_test.py 4 3-tier-redundant sticky")
        print("  python multiworker_test.py 4 3-tier-sticky sticky")
        print("  python multiworker_test.py 4 3-tier-shared sticky")
        return 1

    num_workers = int(sys.argv[1])
    cache_mode = sys.argv[2]
    assignment_str = sys.argv[3]

    # Parse assignment mode
    assignment_map = {
        'random': WorkerAssignment.RANDOM,
        'sticky': WorkerAssignment.STICKY,
        'least_loaded': WorkerAssignment.LEAST_LOADED,
        'sharded': WorkerAssignment.INSTRUMENT_SHARDED
    }

    assignment_mode = assignment_map.get(assignment_str)
    if not assignment_mode:
        print(f"Invalid assignment mode: {assignment_str}")
        print(f"Valid modes: {list(assignment_map.keys())}")
        return 1

    try:
        results = run_multiworker_test(num_workers, cache_mode, assignment_mode)
        if results:
            print("\n✅ Multi-worker test complete!")
            return 0
        else:
            print("\n❌ Test failed with errors")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Required for multiprocessing on macOS
    mp.set_start_method('spawn', force=True)
    sys.exit(main())
