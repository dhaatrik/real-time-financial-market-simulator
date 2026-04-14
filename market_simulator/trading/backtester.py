"""Backtesting engine for trading strategies."""

import pandas as pd
import numpy as np
from market_simulator.trading.strategies import TradingStrategy


class Backtester:
    """Runs a vectorised backtest of a :class:`TradingStrategy` against price data.

    Instead of iterating row-by-row with ``iterrows()``, the backtester calls
    the strategy's ``generate_signals()`` method once to obtain a fully
    vectorised signal series, then computes returns using Pandas arithmetic.

    Args:
        strategy: Any concrete :class:`TradingStrategy` subclass that implements
            ``generate_signals(data)``.
        data: A ``pd.DataFrame`` with at minimum a ``'Close'`` column of asset
            closing prices. The index is expected to be monotonically increasing
            (e.g. a ``DatetimeIndex`` or an integer range index).

    Attributes:
        results: The signals ``pd.DataFrame`` returned by the strategy, populated
            after :meth:`run_backtest` is called.
        strategy_returns: Daily ``pd.Series`` of strategy P&L returns, populated
            after :meth:`run_backtest` is called.
    """

    def __init__(self, strategy: TradingStrategy, data: pd.DataFrame) -> None:
        self.strategy = strategy
        self.data = data
        self.results: pd.DataFrame | None = None
        self.strategy_returns: pd.Series | None = None

    def run_backtest(self) -> pd.DataFrame:
        """Run the vectorised backtest.

        Calls ``generate_signals()`` once on the full dataset and computes
        per-step strategy returns as::

            strategy_return[t] = market_return[t] * signal[t-1]

        where ``signal[t-1]`` is the position held going *into* step ``t``.

        Returns:
            The signals ``pd.DataFrame`` produced by the strategy, augmented
            with a ``'market_return'`` and a ``'strategy_return'`` column.
        """
        signals: pd.DataFrame = self.strategy.generate_signals(self.data)

        # Daily log-returns of the underlying asset
        signals["market_return"] = self.data["Close"].pct_change()

        # Strategy return: hold the previous bar's signal into each new bar
        signals["strategy_return"] = signals["market_return"] * signals["signal"].shift(1)

        self.results = signals
        self.strategy_returns = signals["strategy_return"].dropna()
        return self.results

    def calculate_performance(self) -> dict[str, float]:
        """Compute summary performance metrics for the backtest.

        Must be called *after* :meth:`run_backtest`.

        Returns:
            A dictionary with the following keys:

            - ``'total_return'``: Compounded total return over the period (decimal).
            - ``'annualised_sharpe'``: Sharpe ratio annualised using 252 trading days.
            - ``'max_drawdown'``: Worst peak-to-trough drawdown (negative decimal).

        Raises:
            RuntimeError: If called before :meth:`run_backtest`.
        """
        if self.strategy_returns is None:
            raise RuntimeError("Call run_backtest() before calculate_performance().")

        sr: pd.Series = self.strategy_returns.fillna(0.0)

        # --- Total return ---
        total_return: float = float((1 + sr).prod() - 1)

        # --- Annualised Sharpe ratio (assumes 252 trading days) ---
        mean_r: float = float(sr.mean())
        std_r: float = float(sr.std(ddof=1))
        sharpe: float = (mean_r / std_r * np.sqrt(252)) if std_r != 0 else 0.0

        # --- Maximum drawdown ---
        cumulative: pd.Series = (1 + sr).cumprod()
        rolling_max: pd.Series = cumulative.cummax()
        drawdown: pd.Series = (cumulative - rolling_max) / rolling_max
        max_drawdown: float = float(drawdown.min())

        return {
            "total_return": total_return,
            "annualised_sharpe": sharpe,
            "max_drawdown": max_drawdown,
        }