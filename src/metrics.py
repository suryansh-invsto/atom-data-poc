"""Performance metrics tracking for cache architecture POC."""

from collections import defaultdict
from typing import Dict, List, Any
import time


class PerformanceMetrics:
    """Track latencies and cache statistics."""

    def __init__(self):
        self.latencies: Dict[str, List[float]] = defaultdict(list)
        self.cache_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {'hits': 0, 'misses': 0}
        )
        self.start_time = time.time()

    def record_latency(self, operation: str, latency_ms: float):
        """Record operation latency in milliseconds."""
        self.latencies[operation].append(latency_ms)

    def record_cache_hit(self, tier: str):
        """Record a cache hit for a specific tier."""
        self.cache_stats[tier]['hits'] += 1

    def record_cache_miss(self, tier: str):
        """Record a cache miss for a specific tier."""
        self.cache_stats[tier]['misses'] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Calculate and return performance summary."""
        summary = {
            "latencies": {},
            "cache_hit_rates": {},
            "total_runtime_seconds": time.time() - self.start_time
        }

        # Calculate percentiles for each operation
        for op, values in self.latencies.items():
            if values:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                summary["latencies"][op] = {
                    "p50": sorted_vals[n // 2],
                    "p95": sorted_vals[int(n * 0.95)] if n > 20 else sorted_vals[-1],
                    "p99": sorted_vals[int(n * 0.99)] if n > 100 else sorted_vals[-1],
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }

        # Calculate hit rates
        for tier, stats in self.cache_stats.items():
            total = stats['hits'] + stats['misses']
            if total > 0:
                summary["cache_hit_rates"][tier] = {
                    "rate": (stats['hits'] / total) * 100,
                    "hits": stats['hits'],
                    "misses": stats['misses'],
                    "total": total
                }

        return summary

    def print_interim_stats(self, elapsed_minutes: int):
        """Print interim statistics during test run."""
        print(f"\n[{elapsed_minutes}m] Interim Statistics:")

        # Print recent cache hit rates
        for tier, stats in self.cache_stats.items():
            total = stats['hits'] + stats['misses']
            if total > 0:
                rate = (stats['hits'] / total) * 100
                print(f"  {tier} cache: {rate:.1f}% hit rate ({stats['hits']}/{total})")

        # Print average latencies for key operations
        key_ops = ['get_bar_memory_hit', 'get_bar_redis_hit', 'get_bar_api_fetch']
        for op in key_ops:
            if op in self.latencies and self.latencies[op]:
                avg = sum(self.latencies[op]) / len(self.latencies[op])
                print(f"  {op}: {avg:.3f}ms avg")
