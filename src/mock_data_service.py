"""Mock data service for testing memory management without API calls."""

import json
import time
import random
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, List, Any
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


class CircularBuffer:
    """Memory-efficient circular buffer for storing bars."""

    def __init__(self, maxsize: int):
        self.buffer = deque(maxlen=maxsize)
        self.last_update = datetime.now()

    def append(self, bar: Dict[str, Any]):
        """Add a bar to the buffer."""
        self.buffer.append(bar)
        self.last_update = datetime.now()

    def get_last_n(self, n: int) -> List[Dict[str, Any]]:
        """Get the last n bars from the buffer."""
        if n > len(self.buffer):
            return None
        return list(self.buffer)[-n:]

    def get_current(self) -> Dict[str, Any]:
        """Get the most recent bar."""
        return self.buffer[-1] if self.buffer else None

    def is_stale(self, max_age_seconds: int = 120) -> bool:
        """Check if buffer data is stale."""
        age = (datetime.now() - self.last_update).total_seconds()
        return age > max_age_seconds


class MockThreeTierDataService:
    """3-Tier with mock data - tests pure memory management."""

    def __init__(self):
        self.redis = None
        self.redis_url = 'redis://localhost:6379'
        self.memory_cache: Dict[str, CircularBuffer] = {}
        self.metrics = PerformanceMetrics()

        # Pre-generate 1000 bars per instrument for realistic data
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

        # Check memory first (microseconds)
        if instrument in self.memory_cache:
            bar = self.memory_cache[instrument].get_current()
            if bar and self._is_recent(bar, timeframe):
                self.metrics.record_cache_hit('memory')
                latency_ms = (time.perf_counter() - start) * 1000
                self.metrics.record_latency('get_bar_memory_hit', latency_ms)
                return bar

        self.metrics.record_cache_miss('memory')

        # Check Redis (milliseconds)
        cache_key = f"{instrument}:ohlcv:{timeframe}:current"
        cached = await self.redis.get(cache_key)

        if cached:
            self.metrics.record_cache_hit('redis')
            bar = json.loads(cached)
            self._update_memory_cache(instrument, [bar])
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency('get_bar_redis_hit', latency_ms)
            return bar

        # "Fetch" from mock data (simulates API call)
        self.metrics.record_cache_miss('redis')
        await self._simulate_api_delay()

        data = self._get_mock_data(instrument, 100)
        bar = data[-1]

        # Populate both caches
        self._populate_memory_cache(instrument, data)
        await self._populate_redis_cache(instrument, data, timeframe)

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency('get_bar_mock_fetch', latency_ms)
        return bar

    async def get_bars(self, instrument: str, count: int, timeframe: str = "1m") -> List[Dict[str, Any]]:
        """Get historical bars for an instrument."""
        await self._ensure_redis()
        start = time.perf_counter()

        # Try memory first
        if instrument in self.memory_cache:
            if not self.memory_cache[instrument].is_stale():
                bars = self.memory_cache[instrument].get_last_n(count)
                if bars and len(bars) == count:
                    self.metrics.record_cache_hit('memory_bulk')
                    latency_ms = (time.perf_counter() - start) * 1000
                    self.metrics.record_latency(f'get_bars_{count}_memory', latency_ms)
                    return bars

        self.metrics.record_cache_miss('memory_bulk')

        # Check Redis
        cache_key = f"{instrument}:ohlcv:{timeframe}:last_{count}"
        cached = await self.redis.get(cache_key)

        if cached:
            self.metrics.record_cache_hit('redis_bulk')
            data = json.loads(cached)
            self._populate_memory_cache(instrument, data)
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency(f'get_bars_{count}_redis', latency_ms)
            return data

        # "Fetch" from mock data (simulates API call)
        self.metrics.record_cache_miss('redis_bulk')
        await self._simulate_api_delay()

        data = self._get_mock_data(instrument, count)

        # Populate both caches
        self._populate_memory_cache(instrument, data)
        await self._populate_redis_cache(instrument, data, timeframe, count)

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency(f'get_bars_{count}_mock', latency_ms)
        return data

    async def _simulate_api_delay(self):
        """Simulate realistic API latency (1-5ms instead of 1000ms)."""
        import asyncio
        await asyncio.sleep(random.uniform(0.001, 0.005))

    def _populate_memory_cache(self, instrument: str, bars: List[Dict[str, Any]]):
        """Populate memory cache with bars."""
        if instrument not in self.memory_cache:
            self.memory_cache[instrument] = CircularBuffer(1000)

        for bar in bars:
            self.memory_cache[instrument].append(bar)

    def _update_memory_cache(self, instrument: str, bars: List[Dict[str, Any]]):
        """Update memory cache with new bars."""
        self._populate_memory_cache(instrument, bars)

    async def _populate_redis_cache(self, instrument: str, bars: List[Dict[str, Any]],
                             timeframe: str, count: int = None):
        """Populate Redis cache with bars."""
        if bars:
            # Cache current bar
            current_key = f"{instrument}:ohlcv:{timeframe}:current"
            await self.redis.setex(current_key, 60, json.dumps(bars[-1]))

            # Cache historical data if count specified
            if count:
                hist_key = f"{instrument}:ohlcv:{timeframe}:last_{count}"
                await self.redis.setex(hist_key, 30, json.dumps(bars))

    def _is_recent(self, bar: Dict[str, Any], timeframe: str) -> bool:
        """Check if bar is recent enough based on timeframe."""
        try:
            bar_time = datetime.fromisoformat(bar.get('starttime', ''))
            age = (datetime.now() - bar_time).total_seconds()

            # Consider recent if within timeframe window
            timeframe_seconds = {
                '1m': 60,
                '5m': 300,
                '15m': 900,
                '1h': 3600
            }

            max_age = timeframe_seconds.get(timeframe, 60)
            return age < max_age * 2  # Allow 2x timeframe window
        except (ValueError, KeyError):
            return False


class Mock2TierDataService:
    """2-Tier with mock data - tests Redis-only cache (no memory layer)."""

    def __init__(self):
        self.redis = None
        self.redis_url = 'redis://localhost:6379'
        self.metrics = PerformanceMetrics()

        # Pre-generate 1000 bars per instrument for realistic data
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

        # Check Redis cache (no memory layer)
        cache_key = f"{instrument}:ohlcv:{timeframe}:current"
        cached = await self.redis.get(cache_key)

        if cached:
            self.metrics.record_cache_hit('redis')
            bar = json.loads(cached)
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency('get_bar_redis_hit', latency_ms)
            return bar

        # Cache miss - "fetch" from mock data (simulates API call)
        self.metrics.record_cache_miss('redis')
        await self._simulate_api_delay()

        data = self._get_mock_data(instrument, 1)
        bar = data[0] if data else {}

        # Store in Redis only (no memory cache)
        await self.redis.setex(cache_key, 60, json.dumps(bar))

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency('get_bar_mock_fetch', latency_ms)
        return bar

    async def get_bars(self, instrument: str, count: int, timeframe: str = "1m") -> List[Dict[str, Any]]:
        """Get historical bars for an instrument."""
        await self._ensure_redis()
        start = time.perf_counter()

        # Check Redis cache (no memory layer)
        cache_key = f"{instrument}:ohlcv:{timeframe}:last_{count}"
        cached = await self.redis.get(cache_key)

        if cached:
            self.metrics.record_cache_hit('redis_bulk')
            data = json.loads(cached)
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency(f'get_bars_{count}_redis', latency_ms)
            return data

        # Cache miss - "fetch" from mock data (simulates API call)
        self.metrics.record_cache_miss('redis_bulk')
        await self._simulate_api_delay()

        data = self._get_mock_data(instrument, count)

        # Store in Redis only (no memory cache)
        await self.redis.setex(cache_key, 30, json.dumps(data))

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency(f'get_bars_{count}_mock', latency_ms)
        return data

    async def _simulate_api_delay(self):
        """Simulate realistic API latency (1-5ms instead of 1000ms)."""
        await asyncio.sleep(random.uniform(0.001, 0.005))
