"""Shared memory cache for multi-worker processes."""

import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from multiprocessing import Manager
import redis.asyncio as redis
import asyncio

from .metrics import PerformanceMetrics


def generate_mock_bar(instrument: str, timestamp: datetime) -> Dict[str, Any]:
    """Generate a realistic mock OHLCV bar."""
    base_price = random.uniform(50, 500)
    return {
        "instrument": instrument,
        "starttime": timestamp.isoformat(),
        "open": round(base_price, 2),
        "high": round(base_price * random.uniform(1.0, 1.02), 2),
        "low": round(base_price * random.uniform(0.98, 1.0), 2),
        "close": round(base_price * random.uniform(0.99, 1.01), 2),
        "volume": random.randint(100000, 10000000)
    }


class SharedMemoryCache:
    """Shared memory cache accessible by all workers using multiprocessing.Manager."""

    def __init__(self, manager: Manager):
        """
        Initialize shared cache.

        Args:
            manager: multiprocessing.Manager instance
        """
        # Use manager.dict() for shared memory across processes
        self.cache = manager.dict()
        self.metadata = manager.dict()  # Store timestamps, etc.

    def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get data from shared cache."""
        if key in self.cache:
            # Check if stale
            meta = self.metadata.get(key, {})
            if meta and not self._is_stale(meta):
                return json.loads(self.cache[key])
        return None

    def set(self, key: str, value: List[Dict[str, Any]], ttl_seconds: int = 120):
        """Set data in shared cache with TTL."""
        self.cache[key] = json.dumps(value)
        self.metadata[key] = {
            'timestamp': time.time(),
            'ttl': ttl_seconds
        }

    def _is_stale(self, meta: Dict) -> bool:
        """Check if cache entry is stale."""
        age = time.time() - meta.get('timestamp', 0)
        return age > meta.get('ttl', 120)

    def get_cache_size(self) -> int:
        """Get number of cached items."""
        return len(self.cache)

    def clear(self):
        """Clear the cache."""
        self.cache.clear()
        self.metadata.clear()


class MockSharedCacheDataService:
    """3-Tier with shared memory cache across all workers."""

    def __init__(self, shared_cache: SharedMemoryCache):
        self.redis = None
        self.redis_url = 'redis://localhost:6379'
        self.shared_cache = shared_cache  # Shared across all workers
        self.metrics = PerformanceMetrics()

        # Pre-generate base data (this is per-worker, not shared)
        self.base_data: Dict[str, List[Dict[str, Any]]] = {}

    async def _ensure_redis(self):
        """Ensure Redis connection is initialized."""
        if self.redis is None:
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)

    def _get_mock_data(self, instrument: str, count: int) -> List[Dict[str, Any]]:
        """Get or generate mock data for an instrument."""
        if instrument not in self.base_data:
            # Generate 1000 bars worth of data
            base_time = datetime.now() - timedelta(minutes=1000)
            self.base_data[instrument] = [
                generate_mock_bar(instrument, base_time + timedelta(minutes=i))
                for i in range(1000)
            ]

        # Return the last N bars
        return self.base_data[instrument][-count:]

    async def get_current_bar(self, instrument: str, timeframe: str = "1m") -> Dict[str, Any]:
        """Get the most recent bar for an instrument."""
        await self._ensure_redis()
        start = time.perf_counter()

        # Check shared memory cache first
        cache_key = f"{instrument}:current"
        cached = self.shared_cache.get(cache_key)

        if cached and len(cached) > 0:
            self.metrics.record_cache_hit('shared_memory')
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency('get_bar_shared_hit', latency_ms)
            return cached[-1]

        self.metrics.record_cache_miss('shared_memory')

        # Check Redis
        redis_key = f"{instrument}:ohlcv:{timeframe}:current"
        redis_cached = await self.redis.get(redis_key)

        if redis_cached:
            self.metrics.record_cache_hit('redis')
            bar = json.loads(redis_cached)
            # Update shared cache
            self.shared_cache.set(cache_key, [bar], ttl_seconds=60)
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency('get_bar_redis_hit', latency_ms)
            return bar

        # Cache miss - "fetch" from mock data
        self.metrics.record_cache_miss('redis')
        await self._simulate_api_delay()

        data = self._get_mock_data(instrument, 100)
        bar = data[-1]

        # Populate both caches
        self.shared_cache.set(cache_key, data, ttl_seconds=120)
        await self.redis.setex(redis_key, 60, json.dumps(bar))

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency('get_bar_mock_fetch', latency_ms)
        return bar

    async def get_bars(self, instrument: str, count: int, timeframe: str = "1m") -> List[Dict[str, Any]]:
        """Get historical bars for an instrument."""
        await self._ensure_redis()
        start = time.perf_counter()

        # Check shared memory cache
        cache_key = f"{instrument}:bars:{count}"
        cached = self.shared_cache.get(cache_key)

        if cached and len(cached) >= count:
            self.metrics.record_cache_hit('shared_memory_bulk')
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency(f'get_bars_{count}_shared', latency_ms)
            return cached[-count:]

        self.metrics.record_cache_miss('shared_memory_bulk')

        # Check Redis
        redis_key = f"{instrument}:ohlcv:{timeframe}:last_{count}"
        redis_cached = await self.redis.get(redis_key)

        if redis_cached:
            self.metrics.record_cache_hit('redis_bulk')
            data = json.loads(redis_cached)
            # Update shared cache
            self.shared_cache.set(cache_key, data, ttl_seconds=120)
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency(f'get_bars_{count}_redis', latency_ms)
            return data

        # Cache miss - "fetch" from mock data
        self.metrics.record_cache_miss('redis_bulk')
        await self._simulate_api_delay()

        data = self._get_mock_data(instrument, count)

        # Populate both caches
        self.shared_cache.set(cache_key, data, ttl_seconds=120)
        await self.redis.setex(redis_key, 30, json.dumps(data))

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency(f'get_bars_{count}_mock', latency_ms)
        return data

    async def _simulate_api_delay(self):
        """Simulate realistic API latency (1-5ms)."""
        await asyncio.sleep(random.uniform(0.001, 0.005))
