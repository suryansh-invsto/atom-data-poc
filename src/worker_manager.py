"""Worker process management for multi-worker testing."""

import os
import hashlib
import multiprocessing as mp
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class WorkerAssignment(Enum):
    """Strategy assignment modes."""
    RANDOM = "random"
    STICKY = "sticky"  # Consistent hashing
    LEAST_LOADED = "least_loaded"
    INSTRUMENT_SHARDED = "sharded"


@dataclass
class WorkerConfig:
    """Configuration for a worker process."""
    worker_id: int
    num_workers: int
    assignment_mode: WorkerAssignment
    cache_mode: str  # "2-tier", "3-tier-redundant", "3-tier-sticky"
    redis_url: str = "redis://localhost:6379"


class WorkerStrategyAssigner:
    """Assigns strategies to workers based on different strategies."""

    def __init__(self, num_workers: int, mode: WorkerAssignment):
        self.num_workers = num_workers
        self.mode = mode
        self.strategy_to_worker: Dict[str, int] = {}
        self.worker_loads: List[int] = [0] * num_workers

    def assign_strategy(self, strategy_id: str, instruments: List[str]) -> int:
        """Assign a strategy to a worker."""
        if self.mode == WorkerAssignment.RANDOM:
            return self._random_assignment(strategy_id)
        elif self.mode == WorkerAssignment.STICKY:
            return self._sticky_assignment(strategy_id)
        elif self.mode == WorkerAssignment.LEAST_LOADED:
            return self._least_loaded_assignment(strategy_id)
        elif self.mode == WorkerAssignment.INSTRUMENT_SHARDED:
            return self._instrument_sharded_assignment(strategy_id, instruments)
        else:
            raise ValueError(f"Unknown assignment mode: {self.mode}")

    def _random_assignment(self, strategy_id: str) -> int:
        """Random assignment (for testing)."""
        # Use hash for deterministic "random"
        hash_val = int(hashlib.md5(strategy_id.encode()).hexdigest(), 16)
        worker_id = hash_val % self.num_workers
        self.strategy_to_worker[strategy_id] = worker_id
        self.worker_loads[worker_id] += 1
        return worker_id

    def _sticky_assignment(self, strategy_id: str) -> int:
        """Consistent hashing for sticky sessions."""
        if strategy_id in self.strategy_to_worker:
            return self.strategy_to_worker[strategy_id]

        # Use consistent hashing
        hash_val = int(hashlib.md5(strategy_id.encode()).hexdigest(), 16)
        worker_id = hash_val % self.num_workers
        self.strategy_to_worker[strategy_id] = worker_id
        self.worker_loads[worker_id] += 1
        return worker_id

    def _least_loaded_assignment(self, strategy_id: str) -> int:
        """Assign to worker with least load."""
        if strategy_id in self.strategy_to_worker:
            return self.strategy_to_worker[strategy_id]

        # Find worker with least load
        worker_id = self.worker_loads.index(min(self.worker_loads))
        self.strategy_to_worker[strategy_id] = worker_id
        self.worker_loads[worker_id] += 1
        return worker_id

    def _instrument_sharded_assignment(self, strategy_id: str, instruments: List[str]) -> int:
        """Shard by primary instrument for cache locality."""
        if strategy_id in self.strategy_to_worker:
            return self.strategy_to_worker[strategy_id]

        # Use first instrument as shard key
        primary_instrument = instruments[0] if instruments else strategy_id
        hash_val = int(hashlib.md5(primary_instrument.encode()).hexdigest(), 16)
        worker_id = hash_val % self.num_workers
        self.strategy_to_worker[strategy_id] = worker_id
        self.worker_loads[worker_id] += 1
        return worker_id

    def get_worker_assignment(self, strategy_id: str) -> int:
        """Get assigned worker for a strategy."""
        return self.strategy_to_worker.get(strategy_id, -1)

    def get_worker_load(self, worker_id: int) -> int:
        """Get number of strategies assigned to worker."""
        return self.worker_loads[worker_id]

    def get_load_balance_stats(self) -> Dict[str, Any]:
        """Get load balancing statistics."""
        loads = self.worker_loads
        return {
            "total_strategies": sum(loads),
            "per_worker": loads,
            "min_load": min(loads),
            "max_load": max(loads),
            "avg_load": sum(loads) / len(loads),
            "imbalance_factor": max(loads) / (sum(loads) / len(loads)) if sum(loads) > 0 else 1.0
        }


class WorkerMetricsCollector:
    """Collect metrics from multiple workers."""

    def __init__(self):
        self.worker_metrics: Dict[int, Dict] = {}

    def add_worker_metrics(self, worker_id: int, metrics: Dict):
        """Add metrics from a worker."""
        self.worker_metrics[worker_id] = metrics

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Aggregate metrics across all workers."""
        if not self.worker_metrics:
            return {}

        num_workers = len(self.worker_metrics)

        # Aggregate memory
        total_memory = sum(m['system']['memory']['max_rss_mb']
                          for m in self.worker_metrics.values())
        avg_memory = total_memory / num_workers

        # Aggregate timing (handle both old and new key names)
        total_time = max(m['timings'].get('test_duration_seconds', m['timings'].get('test_1m_seconds', 0))
                        for m in self.worker_metrics.values())

        # Aggregate cache hits
        total_cache_hits = {}
        for worker_metrics in self.worker_metrics.values():
            for tier, stats in worker_metrics.get('performance', {}).get('cache_hit_rates', {}).items():
                if tier not in total_cache_hits:
                    total_cache_hits[tier] = {'hits': 0, 'misses': 0, 'total': 0}
                total_cache_hits[tier]['hits'] += stats['hits']
                total_cache_hits[tier]['misses'] += stats['misses']
                total_cache_hits[tier]['total'] += stats['total']

        # Calculate aggregate cache hit rates
        cache_hit_rates = {}
        for tier, stats in total_cache_hits.items():
            if stats['total'] > 0:
                cache_hit_rates[tier] = {
                    'rate': (stats['hits'] / stats['total']) * 100,
                    'hits': stats['hits'],
                    'misses': stats['misses'],
                    'total': stats['total']
                }

        return {
            'num_workers': num_workers,
            'total_memory_mb': total_memory,
            'avg_memory_per_worker_mb': avg_memory,
            'total_execution_time_seconds': total_time,
            'cache_hit_rates': cache_hit_rates,
            'per_worker_memory': [
                self.worker_metrics[i]['system']['memory']['max_rss_mb']
                for i in range(num_workers)
            ],
            'memory_redundancy_factor': total_memory / avg_memory if avg_memory > 0 else 1.0
        }

    def get_worker_metrics(self, worker_id: int) -> Dict:
        """Get metrics for a specific worker."""
        return self.worker_metrics.get(worker_id, {})


def worker_process(worker_id: int, config: WorkerConfig, strategies: List,
                   result_queue: mp.Queue, error_queue: mp.Queue, shared_cache=None):
    """Worker process function - runs strategies assigned to this worker."""
    try:
        import asyncio
        from src.mock_data_service import MockThreeTierDataService, Mock2TierDataService
        from src.shared_cache import MockSharedCacheDataService
        from src.system_metrics import SystemMetricsCollector
        import time

        # Create data service based on cache mode
        if config.cache_mode == "2-tier":
            data_service = Mock2TierDataService()
        elif config.cache_mode in ["3-tier-redundant", "3-tier-sticky"]:
            data_service = MockThreeTierDataService()
        elif config.cache_mode == "3-tier-shared":
            if shared_cache is None:
                raise ValueError("Shared cache required for 3-tier-shared mode")
            data_service = MockSharedCacheDataService(shared_cache)
        else:
            raise ValueError(f"Unknown cache mode: {config.cache_mode}")

        # Inject data service into strategies
        for strategy in strategies:
            strategy.data_service = data_service

        # Start metrics collection
        system_metrics = SystemMetricsCollector()
        system_metrics.start_collection()

        # Combined warmup and test phase in single event loop
        async def run_worker():
            # Cold start: Load last 1000 bars for each unique instrument
            unique_instruments = set()
            for strategy in strategies:
                unique_instruments.update(strategy.instruments)

            warmup_tasks = []
            for instrument in unique_instruments:
                # Load 1000 1m bars for each instrument
                warmup_tasks.append(data_service.get_bars(instrument, 1000, "1m"))

            warmup_start = time.time()
            await asyncio.gather(*warmup_tasks)
            warmup_time = time.time() - warmup_start

            system_metrics.collect_snapshot()

            # Real-time test phase - run for 5 real minutes (300 seconds)
            fetch_times = []
            minute_metrics = []
            test_start = time.time()
            test_duration = 300  # 5 minutes in seconds
            minute_count = 0

            while (time.time() - test_start) < test_duration:
                minute_start = time.time()

                # Fetch 1 new 1m bar for each instrument
                new_bar_tasks = []
                for instrument in unique_instruments:
                    new_bar_tasks.append(data_service.get_current_bar(instrument, "1m"))

                await asyncio.gather(*new_bar_tasks)

                # Execute strategies based on their timeframe
                strategy_tasks = []
                for strategy in strategies:
                    interval_minutes = {
                        "1m": 1, "5m": 5, "15m": 15, "60m": 60
                    }.get(strategy.timeframe, 1)

                    # Execute if this minute aligns with strategy's interval
                    if minute_count % interval_minutes == 0:
                        strategy_tasks.append(strategy.on_bar(None))

                if strategy_tasks:
                    iter_start = time.perf_counter()
                    await asyncio.gather(*strategy_tasks)
                    iter_time = (time.perf_counter() - iter_start) * 1000
                    fetch_times.append(iter_time)

                    minute_metrics.append({
                        'minute': minute_count,
                        'strategies_executed': len(strategy_tasks),
                        'execution_time_ms': iter_time
                    })

                minute_count += 1

                # Sleep until next minute (60 seconds from minute_start)
                elapsed = time.time() - minute_start
                sleep_time = max(0, 60 - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            test_time = time.time() - test_start
            system_metrics.collect_snapshot()

            return warmup_time, test_time, fetch_times, minute_metrics

        # Run both warmup and test in single event loop
        warmup_time, test_time, fetch_times, minute_metrics = asyncio.run(run_worker())

        # Collect results
        perf_summary = data_service.metrics.get_summary()
        sys_summary = system_metrics.get_summary()

        # Count unique instruments cached by this worker
        unique_instruments = set()
        for strategy in strategies:
            unique_instruments.update(strategy.instruments)

        result = {
            'worker_id': worker_id,
            'num_strategies': len(strategies),
            'num_instruments': len(unique_instruments),
            'timings': {
                'warmup_seconds': warmup_time,
                'test_duration_seconds': test_time,
                'fetch_iterations_ms': {
                    'avg': sum(fetch_times) / len(fetch_times) if fetch_times else 0,
                    'min': min(fetch_times) if fetch_times else 0,
                    'max': max(fetch_times) if fetch_times else 0
                },
                'minutes_executed': len(minute_metrics)
            },
            'minute_by_minute': minute_metrics,
            'performance': perf_summary,
            'system': sys_summary
        }

        result_queue.put(result)

    except Exception as e:
        import traceback
        error_queue.put({
            'worker_id': worker_id,
            'error': str(e),
            'traceback': traceback.format_exc()
        })
