"""Quantitative tests for the trading strategy implementations.

Uses hardcoded price series so that signal transitions can be verified
deterministically — no randomness involved.

Run with::

    python -m pytest market_simulator/tests/test_strategies.py -v
"""

import pandas as pd
import pytest

from market_simulator.trading.strategies import (
    MovingAverageStrategy,
    RSI_Strategy,
    TradingStrategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(prices: list[float]) -> pd.DataFrame:
    """Wrap a raw price list into a DataFrame with a 'Close' column."""
    return pd.DataFrame({"Close": prices})


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class TestTradingStrategyBase:
    """Verify the abstract base class contract."""

    def test_generate_signals_not_implemented(self):
        """Calling generate_signals on the base class must raise."""
        base = TradingStrategy("test")
        with pytest.raises(NotImplementedError):
            base.generate_signals(pd.DataFrame({"Close": [1, 2, 3]}))


# ---------------------------------------------------------------------------
# Moving Average crossover
# ---------------------------------------------------------------------------

class TestMovingAverageStrategy:
    """Deterministic tests for the dual-SMA crossover strategy."""

    def test_crossover_produces_signal_transition(self):
        """When the short MA crosses above the long MA, signal must flip to 1.0.

        Scenario: 15 bars of price=10 (flat), then 15 bars gradually rising.
        With short_window=3, long_window=10, the short MA reacts faster and
        crosses above the long MA — triggering a long signal.
        """
        prices = [10.0] * 15 + [10.0 + i * 3.0 for i in range(1, 16)]
        df = _make_price_df(prices)
        strategy = MovingAverageStrategy(short_window=3, long_window=10)
        signals = strategy.generate_signals(df)

        # After the ramp, the fast MA leads the slow MA → signal = 1.0
        late_signals = signals["signal"].iloc[25:]
        assert (late_signals == 1.0).all(), (
            f"Expected all-long signals after crossover, got:\n{late_signals}"
        )

    def test_flat_prices_produce_zero_signal(self):
        """When prices are flat, both MAs are equal — signal stays 0.0."""
        prices = [50.0] * 30
        df = _make_price_df(prices)
        strategy = MovingAverageStrategy(short_window=5, long_window=10)
        signals = strategy.generate_signals(df)

        # With min_periods=1 and flat prices, short == long → signal stays 0
        # (np.where tests >, not >=, so equal MAs give 0.0)
        assert (signals["signal"] == 0.0).all()

    def test_output_columns(self):
        """Signals DataFrame must contain the expected columns."""
        df = _make_price_df([10.0] * 20)
        strategy = MovingAverageStrategy(short_window=3, long_window=5)
        signals = strategy.generate_signals(df)
        assert set(signals.columns) == {"signal", "short_mavg", "long_mavg", "positions"}


# ---------------------------------------------------------------------------
# RSI strategy
# ---------------------------------------------------------------------------

class TestRSIStrategy:
    """Deterministic tests for the RSI mean-reversion strategy."""

    def test_rising_prices_trigger_overbought(self):
        """Monotonically rising prices should push RSI above the overbought
        threshold and produce a short signal (-1.0).
        """
        # Enough rising bars (all gains, no losses) → RSI → 100
        prices = [100.0 + i * 2.0 for i in range(30)]
        df = _make_price_df(prices)
        strategy = RSI_Strategy(window=14, overbought=70, oversold=30)
        signals = strategy.generate_signals(df)

        # After the RSI warm-up period, we expect overbought signals
        late = signals["signal"].iloc[20:]
        assert (late == -1.0).all(), (
            f"Expected overbought (short) signals, got:\n{late}"
        )

    def test_falling_prices_trigger_oversold(self):
        """Monotonically falling prices should push RSI below the oversold
        threshold and produce a long signal (1.0).
        """
        prices = [200.0 - i * 2.0 for i in range(30)]
        df = _make_price_df(prices)
        strategy = RSI_Strategy(window=14, overbought=70, oversold=30)
        signals = strategy.generate_signals(df)

        late = signals["signal"].iloc[20:]
        assert (late == 1.0).all(), (
            f"Expected oversold (long) signals, got:\n{late}"
        )

    def test_output_columns(self):
        """Signals DataFrame must contain the expected columns."""
        df = _make_price_df([100.0] * 20)
        strategy = RSI_Strategy(window=14, overbought=70, oversold=30)
        signals = strategy.generate_signals(df)
        assert set(signals.columns) == {"signal", "rsi", "positions"}
