"""Data service implementations for 2-tier and 3-tier cache architectures."""

import os
import json
import time
import redis.asyncio as redis
import aiohttp
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, Dict, List, Any

from .metrics import PerformanceMetrics

# Global connector with connection limits
_connector = None

def get_connector():
    """Get or create a global connector with limits."""
    global _connector
    if _connector is None:
        _connector = aiohttp.TCPConnector(
            limit=100,  # Max total connections
            limit_per_host=50  # Max connections per host
        )
    return _connector


class TwoTierDataService:
    """2-Tier architecture: API (PostgreSQL) -> Redis -> Strategy"""

    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis = None  # Will be initialized async
        self.redis_url = redis_url
        self.api_base = os.getenv('DATA_API_URL', 'https://de.invsto.xyz/us/1')
        self.metrics = PerformanceMetrics()

    async def _ensure_redis(self):
        """Ensure Redis connection is initialized."""
        if self.redis is None:
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)

    async def get_current_bar(self, instrument: str, timeframe: str = "1m") -> Dict[str, Any]:
        """Get the most recent bar for an instrument."""
        await self._ensure_redis()
        start = time.perf_counter()

        # Check Redis cache
        cache_key = f"{instrument}:ohlcv:{timeframe}:current"
        cached = await self.redis.get(cache_key)

        if cached:
            self.metrics.record_cache_hit('redis')
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency('get_bar_redis_hit', latency_ms)
            return json.loads(cached)

        # Cache miss - fetch from API
        self.metrics.record_cache_miss('redis')

        async with aiohttp.ClientSession(connector=get_connector(), connector_owner=False) as session:
            url = f"{self.api_base}/get_last_n?instrument_name={instrument}&n=1"
            async with session.get(url) as response:
                data = await response.json()

        # Handle both list and dict responses
        if isinstance(data, list):
            bar = data[0] if data else {}
        elif isinstance(data, dict):
            bar = data
        else:
            bar = {}

        # Store in Redis with 60-second expiry
        await self.redis.setex(cache_key, 60, json.dumps(bar))

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency('get_bar_api_fetch', latency_ms)
        return bar

    async def get_bars(self, instrument: str, count: int, timeframe: str = "1m") -> List[Dict[str, Any]]:
        """Get historical bars for an instrument."""
        await self._ensure_redis()
        start = time.perf_counter()

        # Check Redis for cached historical data
        cache_key = f"{instrument}:ohlcv:{timeframe}:last_{count}"
        cached = await self.redis.get(cache_key)

        if cached:
            self.metrics.record_cache_hit('redis_bulk')
            latency_ms = (time.perf_counter() - start) * 1000
            self.metrics.record_latency(f'get_bars_{count}_redis', latency_ms)
            return json.loads(cached)

        # Cache miss - fetch from API
        self.metrics.record_cache_miss('redis_bulk')

        async with aiohttp.ClientSession(connector=get_connector(), connector_owner=False) as session:
            url = f"{self.api_base}/get_last_n?instrument_name={instrument}&n={count}"
            async with session.get(url) as response:
                data = await response.json()

        # Cache for 30 seconds
        await self.redis.setex(cache_key, 30, json.dumps(data))

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency(f'get_bars_{count}_api', latency_ms)
        return data


class CircularBuffer:
    """Memory-efficient circular buffer for storing bars."""

    def __init__(self, maxsize: int):
        self.buffer = deque(maxlen=maxsize)
        self.last_update = datetime.now()

    def append(self, bar: Dict[str, Any]):
        """Add a bar to the buffer."""
        self.buffer.append(bar)
        self.last_update = datetime.now()

    def get_last_n(self, n: int) -> Optional[List[Dict[str, Any]]]:
        """Get the last n bars from the buffer."""
        if n > len(self.buffer):
            return None
        return list(self.buffer)[-n:]

    def get_current(self) -> Optional[Dict[str, Any]]:
        """Get the most recent bar."""
        return self.buffer[-1] if self.buffer else None

    def is_stale(self, max_age_seconds: int = 120) -> bool:
        """Check if buffer data is stale."""
        age = (datetime.now() - self.last_update).total_seconds()
        return age > max_age_seconds


class ThreeTierDataService:
    """3-Tier architecture: API (PostgreSQL) -> Redis -> Memory -> Strategy"""

    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis = None  # Will be initialized async
        self.redis_url = redis_url
        self.api_base = os.getenv('DATA_API_URL', 'https://de.invsto.xyz/us/1')
        self.memory_cache: Dict[str, CircularBuffer] = {}
        self.metrics = PerformanceMetrics()

    async def _ensure_redis(self):
        """Ensure Redis connection is initialized."""
        if self.redis is None:
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)

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

        # Cache miss - fetch from API (10-100ms)
        self.metrics.record_cache_miss('redis')

        async with aiohttp.ClientSession(connector=get_connector(), connector_owner=False) as session:
            url = f"{self.api_base}/get_last_n?instrument_name={instrument}&n=100"
            async with session.get(url) as response:
                data = await response.json()

        # Handle both list and dict responses
        if isinstance(data, list):
            bar = data[-1] if data else {}
        elif isinstance(data, dict):
            bar = data
            data = [data]  # Convert to list for cache population
        else:
            bar = {}
            data = []

        # Populate both caches
        self._populate_memory_cache(instrument, data)
        await self._populate_redis_cache(instrument, data, timeframe)

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency('get_bar_api_fetch', latency_ms)
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

        # Cache miss - fetch from API
        self.metrics.record_cache_miss('redis_bulk')

        async with aiohttp.ClientSession(connector=get_connector(), connector_owner=False) as session:
            url = f"{self.api_base}/get_last_n?instrument_name={instrument}&n={count}"
            async with session.get(url) as response:
                data = await response.json()

        # Handle both list and dict responses
        if isinstance(data, dict):
            data = [data]  # Convert to list

        # Populate both caches
        self._populate_memory_cache(instrument, data)
        await self._populate_redis_cache(instrument, data, timeframe, count)

        latency_ms = (time.perf_counter() - start) * 1000
        self.metrics.record_latency(f'get_bars_{count}_api', latency_ms)
        return data

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
                             timeframe: str, count: Optional[int] = None):
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
