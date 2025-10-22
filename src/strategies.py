"""Mock trading strategies for load testing different cache architectures."""

import asyncio
import random
from datetime import datetime
from typing import List, Dict, Any, Optional


class BaseStrategy:
    """Base class for trading strategies."""

    def __init__(self, name: str, instruments: List[str], timeframe: str, lookback: int):
        self.name = name
        self.instruments = instruments
        self.timeframe = timeframe
        self.lookback = lookback
        self.data_service = None  # Injected by test runner
        self.execution_count = 0

    async def on_bar(self, current_time: datetime):
        """
        Called when a new bar closes for this strategy's timeframe.

        Simulates:
        1. Fetching current bar for each instrument
        2. Fetching historical bars for indicators
        3. Computing indicators and signals
        """
        self.execution_count += 1

        # Process all instruments in parallel
        tasks = []
        for instrument in self.instruments:
            tasks.append(self._process_instrument(instrument))

        results = await asyncio.gather(*tasks)

        # Simulate strategy computation (CPU time)
        await self._simulate_computation()

        return results

    async def _process_instrument(self, instrument: str) -> Dict[str, Any]:
        """Process a single instrument."""
        # Get current bar
        current_bar = await self.data_service.get_current_bar(instrument, self.timeframe)

        # Get historical bars for indicators
        hist_bars = await self.data_service.get_bars(instrument, self.lookback, self.timeframe)

        # Simulate indicator calculations
        indicators = self._calculate_indicators(hist_bars)

        return {
            'instrument': instrument,
            'current_bar': current_bar,
            'indicators': indicators
        }

    def _calculate_indicators(self, bars: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Simulate indicator calculations (RSI, MA, etc.).
        In reality, this would use numpy/pandas for computation.
        """
        if not bars:
            return {}

        # Simulate some computation time based on number of bars
        # Real indicators would process the actual data
        return {
            'rsi': random.uniform(30, 70),
            'ma_fast': random.uniform(100, 200),
            'ma_slow': random.uniform(100, 200),
            'volume_sma': random.uniform(1000000, 5000000)
        }

    async def _simulate_computation(self):
        """Simulate indicator and signal calculations (CPU bound work)."""
        # Simulate 10-30ms of computation time
        await asyncio.sleep(random.uniform(0.01, 0.03))

    def __str__(self):
        return f"{self.name} ({self.timeframe}, {len(self.instruments)} instruments, {self.lookback} bars)"


class ScalpingStrategy(BaseStrategy):
    """
    High-frequency scalping strategy.
    - Runs every 1 minute
    - Trades 3 instruments
    - Uses 50-bar lookback (for RSI)
    """

    def __init__(self):
        super().__init__(
            name="Scalper",
            instruments=["AAPL", "GOOGL", "MSFT"],
            timeframe="1m",
            lookback=50
        )


class DayTradingStrategy(BaseStrategy):
    """
    Intraday trading strategy.
    - Runs every 1 minute
    - Trades 3 instruments
    - Uses 100-bar lookback (for multiple indicators)
    """

    def __init__(self):
        super().__init__(
            name="DayTrader",
            instruments=["AAPL", "TSLA", "NVDA"],
            timeframe="1m",
            lookback=100
        )


class SwingStrategy(BaseStrategy):
    """
    Swing trading strategy.
    - Runs every 5 minutes
    - Trades 3 instruments
    - Uses 200-bar lookback (for trend analysis)
    """

    def __init__(self):
        super().__init__(
            name="Swing",
            instruments=["GOOGL", "AMZN", "META"],
            timeframe="5m",
            lookback=200
        )


class PositionStrategy(BaseStrategy):
    """
    Position trading strategy.
    - Runs every 15 minutes
    - Trades 3 instruments
    - Uses 100-bar lookback
    """

    def __init__(self):
        super().__init__(
            name="Position",
            instruments=["MSFT", "TSLA", "META"],
            timeframe="15m",
            lookback=100
        )


def get_all_strategies() -> List[BaseStrategy]:
    """Get all strategy instances for testing."""
    return [
        ScalpingStrategy(),
        DayTradingStrategy(),
        SwingStrategy(),
        PositionStrategy()
    ]
