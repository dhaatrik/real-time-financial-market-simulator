"""Streamlit dashboard for the Real-Time Financial Market Simulator.

The UI is decomposed into focused rendering functions that return user
inputs, while ``main()`` acts as a thin orchestrator wiring them together.
"""

import json
import logging
import os
import queue
import threading
from typing import Any

import asyncio
import numpy as np
import pandas as pd
import streamlit as st
import websockets

from market_simulator.constants import DataSource, GBMConfig, StrategyType
from market_simulator.data.alpha_vantage import AlphaVantage, AlphaVantageError
from market_simulator.gbm import GeometricBrownianMotion
from market_simulator.trading.backtester import Backtester
from market_simulator.trading.strategies import MovingAverageStrategy, RSI_Strategy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WebSocket streaming — background-thread approach (no event-loop leaks)
# ---------------------------------------------------------------------------


def _ws_worker(uri: str, n_points: int, price_queue: "queue.Queue[float | None]") -> None:
    """Background thread target: opens a WebSocket, reads *n_points* prices,
    pushes each onto *price_queue*, then enqueues ``None`` as a sentinel.

    Args:
        uri: WebSocket URI to connect to.
        n_points: Number of price ticks to collect before closing.
        price_queue: Thread-safe queue shared with the Streamlit main thread.
    """
    async def _collect() -> None:
        async with websockets.connect(uri) as ws:
            for _ in range(n_points):
                msg = await ws.recv()
                data: dict[str, Any] = json.loads(msg)
                price_queue.put(data["price"])

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_collect())
    except Exception as exc:  # noqa: BLE001
        logger.error("WebSocket worker error: %s", exc)
    finally:
        loop.close()
        price_queue.put(None)


def run_websocket_client(uri: str, n_points: int = 100) -> list[float]:
    """Collect *n_points* price ticks from a WebSocket server.

    Args:
        uri: WebSocket URI (e.g. ``ws://localhost:8765``).
        n_points: Number of price ticks to retrieve.

    Returns:
        List of streamed float prices (length <= *n_points*).
    """
    price_queue: "queue.Queue[float | None]" = queue.Queue()
    thread = threading.Thread(
        target=_ws_worker,
        args=(uri, n_points, price_queue),
        daemon=True,
    )
    thread.start()

    prices: list[float] = []
    while True:
        try:
            item = price_queue.get(timeout=15)
        except queue.Empty:
            logger.warning("WebSocket stream timed out after 15 s.")
            break
        if item is None:
            break
        prices.append(item)

    thread.join(timeout=5)
    return prices


# ---------------------------------------------------------------------------
# Cached data fetching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Fetching data from Alpha Vantage...")
def fetch_av_data(symbol: str, api_key: str | None) -> pd.DataFrame:
    """Fetch daily close prices from Alpha Vantage and cache for 1 hour.

    Args:
        symbol: Equity ticker symbol (e.g. ``'AAPL'``).
        api_key: Alpha Vantage API key.

    Returns:
        A ``pd.DataFrame`` with a ``'Close'`` column sorted by date.

    Raises:
        AlphaVantageError: On API-level errors or rate-limit notices.
    """
    av = AlphaVantage(api_key=api_key)
    av_data_json = av.get_stock_data(symbol)
    time_series: dict = av_data_json["Time Series (Daily)"]
    df = pd.DataFrame(
        {"Close": [float(v["4. close"]) for v in time_series.values()]},
        index=pd.to_datetime(list(time_series.keys())),
    )
    return df.sort_index()


# ---------------------------------------------------------------------------
# Sidebar rendering functions
# ---------------------------------------------------------------------------

def _render_gbm_sidebar() -> GBMConfig:
    """Render GBM parameter controls and return a validated config."""
    st.sidebar.header("GBM Parameters")
    S0 = st.sidebar.number_input("Initial Price (S0)", value=100.0, min_value=0.01)
    mu = st.sidebar.number_input("Drift (mu)", value=0.05)
    sigma = st.sidebar.number_input("Volatility (sigma)", value=0.2, min_value=0.001)
    T = st.sidebar.number_input("Time Horizon (years, T)", value=1.0, min_value=0.01)
    dt = st.sidebar.number_input(
        "Time Step (dt)", value=1 / 252.0, min_value=0.0001, format="%0.6f",
    )
    return GBMConfig(S0=S0, mu=mu, sigma=sigma, T=T, dt=dt)


def _render_strategy_sidebar() -> StrategyType:
    """Render strategy selector and return the chosen enum value."""
    st.sidebar.header("Trading Strategy")
    return st.sidebar.selectbox(
        "Select Strategy",
        options=list(StrategyType),
        format_func=lambda s: s.value,
    )


def _render_data_source_sidebar() -> tuple[DataSource, str, str | None]:
    """Render data source controls.

    Returns:
        Tuple of (data_source, av_symbol, av_api_key).
    """
    st.sidebar.header("Data Source")
    data_source: DataSource = st.sidebar.selectbox(
        "Select Data Source",
        options=list(DataSource),
        format_func=lambda d: d.value,
    )
    av_symbol: str = st.sidebar.text_input("Alpha Vantage Symbol", value="AAPL")
    av_api_key: str | None = os.getenv("ALPHA_VANTAGE_API_KEY")
    return data_source, av_symbol, av_api_key


def _render_streaming_sidebar() -> tuple[bool, str, int]:
    """Render real-time streaming controls.

    Returns:
        Tuple of (ws_enabled, ws_uri, n_points).
    """
    st.sidebar.header("Real-Time Streaming")
    if st.sidebar.button("Start Real-Time Stream"):
        st.info(
            "Open a new terminal and run:\n"
            "  python -m market_simulator.websocket_server"
        )
        st.info("Then connect any WebSocket client to ws://localhost:8765")

    ws_enabled: bool = st.sidebar.checkbox("Visualize Real-Time WebSocket Prices")
    ws_uri: str = st.sidebar.text_input("WebSocket URI", value="ws://localhost:8765")
    n_points: int = int(st.sidebar.number_input("Points to Stream", value=100, min_value=1))
    return ws_enabled, ws_uri, n_points


# ---------------------------------------------------------------------------
# Backtest & export rendering
# ---------------------------------------------------------------------------

def _run_backtest_ui(df: pd.DataFrame, strategy_type: StrategyType) -> None:
    """Render strategy parameters, run backtest, and display results."""
    if strategy_type == StrategyType.MOVING_AVERAGE:
        short_window = int(st.sidebar.number_input("Short Window", value=10, min_value=1))
        long_window = int(st.sidebar.number_input("Long Window", value=30, min_value=1))
        strategy = MovingAverageStrategy(short_window, long_window)
        signals = strategy.generate_signals(df)
        st.line_chart(signals[["short_mavg", "long_mavg"]])
        st.write(signals.tail())
        bt = Backtester(strategy, df)
        bt.run_backtest()
        perf = bt.calculate_performance()
        _render_performance(perf)

    elif strategy_type == StrategyType.RSI:
        window = int(st.sidebar.number_input("RSI Window", value=14, min_value=1))
        overbought = float(st.sidebar.number_input("Overbought Threshold", value=70))
        oversold = float(st.sidebar.number_input("Oversold Threshold", value=30))
        strategy_rsi = RSI_Strategy(window, overbought, oversold)
        signals_rsi = strategy_rsi.generate_signals(df)
        st.line_chart(signals_rsi["rsi"])
        st.write(signals_rsi.tail())
        bt_rsi = Backtester(strategy_rsi, df)
        bt_rsi.run_backtest()
        perf_rsi = bt_rsi.calculate_performance()
        _render_performance(perf_rsi)


def _render_performance(perf: dict[str, float]) -> None:
    """Display backtest performance metrics."""
    st.subheader("Backtest Performance")
    st.metric("Total Return", f"{perf['total_return']:.2%}")
    st.metric("Annualised Sharpe", f"{perf['annualised_sharpe']:.2f}")
    st.metric("Max Drawdown", f"{perf['max_drawdown']:.2%}")


def _render_export(df: pd.DataFrame) -> None:
    """Render CSV and JSON download buttons."""
    st.header("Export Results")
    csv = df.to_csv().encode("utf-8")
    st.download_button("Download CSV", csv, "results.csv", "text/csv")
    json_str = df.to_json()
    st.download_button("Download JSON", json_str, "results.json", "application/json")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

ALLOWED_WS_URIS: list[str] = ["ws://localhost:8765", "wss://localhost:8765"]


def main() -> None:
    """Entry point for the Streamlit dashboard."""
    st.title("Real-Time Financial Market Simulator")

    # ---- Sidebar controls ----
    gbm_config = _render_gbm_sidebar()
    strategy_type = _render_strategy_sidebar()
    data_source, av_symbol, av_api_key = _render_data_source_sidebar()
    ws_enabled, ws_uri, n_points = _render_streaming_sidebar()

    # ---- Alpha Vantage fetch (cached) ----
    av_data: pd.DataFrame | None = None
    if data_source == DataSource.ALPHA_VANTAGE and st.sidebar.button("Fetch Alpha Vantage Data"):
        try:
            av_data = fetch_av_data(av_symbol, av_api_key)
            st.success(f"Fetched {len(av_data)} data points for {av_symbol}")
            st.line_chart(av_data["Close"])
        except AlphaVantageError as exc:
            st.error(str(exc))
        except Exception as exc:
            logger.error(
                "Alpha Vantage data processing failed for '%s': %s",
                av_symbol, exc, exc_info=True,
            )
            st.error(
                f"An error occurred while fetching data for '{av_symbol}'. "
                "Please check the symbol or try again later."
            )

    # ---- WebSocket streaming ----
    if ws_enabled and st.button("Start WebSocket Stream", key="btn_ws_stream"):
        if ws_uri in ALLOWED_WS_URIS:
            st.info(f"Connecting to {ws_uri} and streaming {n_points} price points...")
            streamed_prices = run_websocket_client(ws_uri, n_points)
            st.line_chart(streamed_prices)
            st.write(f"Received {len(streamed_prices)} streamed prices.")
        else:
            st.error(
                f"Invalid WebSocket URI: '{ws_uri}'. "
                "Only connections to 'localhost:8765' (ws:// or wss://) are allowed."
            )

    # ---- Simulate / Backtest ----
    if st.button("Simulate/Run Backtest", key="btn_simulate"):
        if data_source == DataSource.ALPHA_VANTAGE and av_data is not None:
            df: pd.DataFrame = av_data.copy()
        else:
            gbm = GeometricBrownianMotion(config=gbm_config)
            prices: np.ndarray = gbm.simulate()
            df = pd.DataFrame({"Close": prices})

        st.line_chart(df["Close"])
        st.write(f"Loaded {len(df)} price points.")

        _run_backtest_ui(df, strategy_type)
        _render_export(df)


if __name__ == "__main__":
    main()
