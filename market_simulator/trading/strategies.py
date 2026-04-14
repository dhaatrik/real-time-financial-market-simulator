"""Trading strategy implementations."""

import numpy as np
import pandas as pd


class TradingStrategy:
    """Abstract base class for all trading strategies.

    Args:
        name: Human-readable identifier for the strategy.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals for the supplied price data.

        Args:
            data: A ``pd.DataFrame`` that **must** contain a ``'Close'`` column
                of asset closing prices.

        Returns:
            A ``pd.DataFrame`` (same index as *data*) with at minimum:

            - ``'signal'``: ``1.0`` = long, ``-1.0`` = short, ``0.0`` = flat.
            - ``'positions'``: First difference of ``'signal'``,
              indicating entry/exit events.

        Raises:
            NotImplementedError: Subclasses must override this method.
        """
        raise NotImplementedError("Should implement generate_signals()")


class MovingAverageStrategy(TradingStrategy):
    """Dual-SMA crossover strategy.

    Goes long (``signal = 1.0``) when the short moving average crosses above
    the long moving average, and flat (``signal = 0.0``) otherwise.

    Args:
        short_window: Look-back period for the fast moving average (in bars).
        long_window: Look-back period for the slow moving average (in bars).
    """

    def __init__(self, short_window: int, long_window: int) -> None:
        super().__init__("Moving Average Strategy")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate SMA crossover signals.

        Args:
            data: ``pd.DataFrame`` with a ``'Close'`` column.

        Returns:
            Signal ``pd.DataFrame`` with ``'short_mavg'``, ``'long_mavg'``,
            ``'signal'``, and ``'positions'`` columns.
        """
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0.0

        signals["short_mavg"] = (
            data["Close"]
            .rolling(window=self.short_window, min_periods=1, center=False)
            .mean()
        )
        signals["long_mavg"] = (
            data["Close"]
            .rolling(window=self.long_window, min_periods=1, center=False)
            .mean()
        )

        # Use .loc to avoid SettingWithCopyWarning
        signals.loc[
            signals.index[self.short_window :],
            "signal",
        ] = np.where(
            signals["short_mavg"].iloc[self.short_window :]
            > signals["long_mavg"].iloc[self.short_window :],
            1.0,
            0.0,
        )

        signals["positions"] = signals["signal"].diff()
        return signals


class RSI_Strategy(TradingStrategy):
    """Relative Strength Index (RSI) mean-reversion strategy.

    Goes short (``signal = -1.0``) when RSI exceeds ``overbought``, long
    (``signal = 1.0``) when RSI falls below ``oversold``, and flat otherwise.

    Args:
        window: RSI look-back period in bars (commonly 14).
        overbought: RSI threshold above which the asset is considered overbought.
        oversold: RSI threshold below which the asset is considered oversold.
    """

    def __init__(self, window: int, overbought: float, oversold: float) -> None:
        super().__init__("RSI Strategy")
        self.window = window
        self.overbought = overbought
        self.oversold = oversold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate RSI-based trading signals.

        Args:
            data: ``pd.DataFrame`` with a ``'Close'`` column.

        Returns:
            Signal ``pd.DataFrame`` with ``'rsi'``, ``'signal'``, and
            ``'positions'`` columns.
        """
        signals = pd.DataFrame(index=data.index)
        signals["signal"] = 0.0

        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=self.window).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=self.window).mean()

        rs = gain / loss
        rsi: pd.Series = 100 - (100 / (1 + rs))

        signals["rsi"] = rsi

        # Use .loc-based assignment to avoid SettingWithCopyWarning
        signals.loc[rsi > self.overbought, "signal"] = -1.0
        signals.loc[rsi < self.oversold, "signal"] = 1.0

        signals["positions"] = signals["signal"].diff()
        return signals