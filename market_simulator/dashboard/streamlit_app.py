"""Streamlit dashboard for the Real-Time Financial Market Simulator."""

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

from market_simulator.gbm import GeometricBrownianMotion
from market_simulator.trading.strategies import MovingAverageStrategy, RSI_Strategy
from market_simulator.trading.backtester import Backtester
from market_simulator.data.alpha_vantage import AlphaVantage, AlphaVantageError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WebSocket streaming — background-thread approach (no event-loop leaks)
# ---------------------------------------------------------------------------

def _ws_worker(uri: str, n_points: int, price_queue: "queue.Queue[float | None]") -> None:
    """Background thread target: opens a WebSocket, reads ``n_points`` prices,
    pushes each onto *price_queue*, then enqueues ``None`` as a sentinel.

    Running the ``asyncio`` event loop in a dedicated thread guarantees the
    Streamlit main thread is never blocked and that resources are properly
    cleaned up when the thread exits — regardless of how many times Streamlit
    reruns the script.

    Args:
        uri: WebSocket URI to connect to (e.g. ``ws://localhost:8765``).
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
        price_queue.put(None)  # sentinel — collection finished


def run_websocket_client(uri: str, n_points: int = 100) -> list[float]:
    """Collect *n_points* price ticks from a WebSocket server.

    Spawns a single background thread with its own ``asyncio`` event loop.
    The Streamlit main thread blocks on :py:meth:`queue.Queue.get` (with a
    per-message timeout) so the UI remains responsive between ticks.

    Args:
        uri: WebSocket URI (e.g. ``ws://localhost:8765``).
        n_points: Number of price ticks to retrieve.

    Returns:
        List of streamed float prices (length ≤ ``n_points``).
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
        if item is None:  # sentinel
            break
        prices.append(item)

    thread.join(timeout=5)
    return prices


# ---------------------------------------------------------------------------
# Main Streamlit application
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the Streamlit dashboard."""
    st.title("Real-Time Financial Market Simulator")

    # ---- Sidebar: GBM parameters ----
    st.sidebar.header("GBM Parameters")
    S0: float = st.sidebar.number_input("Initial Price (S0)", value=100.0)
    mu: float = st.sidebar.number_input("Drift (mu)", value=0.05)
    sigma: float = st.sidebar.number_input("Volatility (sigma)", value=0.2)
    T: float = st.sidebar.number_input("Time Horizon (years, T)", value=1.0)
    dt: float = st.sidebar.number_input(
        "Time Step (dt)", value=1 / 252.0, format="%0.6f"
    )

    # ---- Sidebar: Trading strategy ----
    st.sidebar.header("Trading Strategy")
    strategy_type: str = st.sidebar.selectbox(
        "Select Strategy", ["None", "Moving Average", "RSI"]
    )

    # ---- Sidebar: Data source ----
    st.sidebar.header("Data Source")
    data_source: str = st.sidebar.selectbox(
        "Select Data Source", ["Simulated (GBM)", "Alpha Vantage"]
    )
    av_symbol: str = st.sidebar.text_input("Alpha Vantage Symbol", value="AAPL")
    av_api_key: str | None = os.getenv("ALPHA_VANTAGE_API_KEY")
    av_data: pd.DataFrame | None = None

    if data_source == "Alpha Vantage" and st.sidebar.button("Fetch Alpha Vantage Data"):
        av = AlphaVantage(api_key=av_api_key)
        try:
            av_data_json = av.get_stock_data(av_symbol)
            time_series: dict = av_data_json["Time Series (Daily)"]
            av_data = pd.DataFrame(
                {"Close": [float(v["4. close"]) for v in time_series.values()]},
                index=pd.to_datetime(list(time_series.keys())),
            )
            av_data = av_data.sort_index()
            st.success(f"Fetched {len(av_data)} data points for {av_symbol}")
            st.line_chart(av_data["Close"])
        except AlphaVantageError as exc:
            st.error(str(exc))
        except Exception as exc:
            logger.error(
                "Alpha Vantage data processing failed for '%s': %s",
                av_symbol,
                exc,
                exc_info=True,
            )
            st.error(
                f"An error occurred while fetching data for '{av_symbol}'. "
                "Please check the symbol or try again later."
            )

    # ---- Sidebar: Real-time streaming ----
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

    ALLOWED_WS_URIS: list[str] = ["ws://localhost:8765", "wss://localhost:8765"]

    if ws_enabled and st.button("Start WebSocket Stream", key="btn_ws_stream"):
        if ws_uri in ALLOWED_WS_URIS:
            st.info(f"Connecting to {ws_uri} and streaming {n_points} price points…")
            streamed_prices = run_websocket_client(ws_uri, n_points)
            st.line_chart(streamed_prices)
            st.write(f"Received {len(streamed_prices)} streamed prices.")
        else:
            st.error(
                f"Invalid WebSocket URI: '{ws_uri}'. "
                "Only connections to 'localhost:8765' (ws:// or wss://) are allowed."
            )

    # ---- Main simulation / backtest ----
    if st.button("Simulate/Run Backtest", key="btn_simulate"):
        if data_source == "Alpha Vantage" and av_data is not None:
            df: pd.DataFrame = av_data.copy()
        else:
            gbm = GeometricBrownianMotion(S0, mu, sigma, T, dt)
            prices: np.ndarray = gbm.simulate()
            df = pd.DataFrame({"Close": prices})

        st.line_chart(df["Close"])
        st.write(f"Loaded {len(df)} price points.")

        if strategy_type == "Moving Average":
            short_window: int = int(
                st.sidebar.number_input("Short Window", value=10, min_value=1)
            )
            long_window: int = int(
                st.sidebar.number_input("Long Window", value=30, min_value=1)
            )
            strategy = MovingAverageStrategy(short_window, long_window)
            signals: pd.DataFrame = strategy.generate_signals(df)
            st.line_chart(signals[["short_mavg", "long_mavg"]])
            st.write(signals.tail())
            backtester = Backtester(strategy, df)
            backtester.run_backtest()
            perf = backtester.calculate_performance()
            st.subheader("Backtest Performance")
            st.metric("Total Return", f"{perf['total_return']:.2%}")
            st.metric("Annualised Sharpe", f"{perf['annualised_sharpe']:.2f}")
            st.metric("Max Drawdown", f"{perf['max_drawdown']:.2%}")

        elif strategy_type == "RSI":
            window: int = int(st.sidebar.number_input("RSI Window", value=14, min_value=1))
            overbought: float = float(
                st.sidebar.number_input("Overbought Threshold", value=70)
            )
            oversold: float = float(
                st.sidebar.number_input("Oversold Threshold", value=30)
            )
            strategy_rsi = RSI_Strategy(window, overbought, oversold)
            signals_rsi: pd.DataFrame = strategy_rsi.generate_signals(df)
            st.line_chart(signals_rsi["rsi"])
            st.write(signals_rsi.tail())
            backtester_rsi = Backtester(strategy_rsi, df)
            backtester_rsi.run_backtest()
            perf_rsi = backtester_rsi.calculate_performance()
            st.subheader("Backtest Performance")
            st.metric("Total Return", f"{perf_rsi['total_return']:.2%}")
            st.metric("Annualised Sharpe", f"{perf_rsi['annualised_sharpe']:.2f}")
            st.metric("Max Drawdown", f"{perf_rsi['max_drawdown']:.2%}")

        # ---- Export ----
        st.header("Export Results")
        csv = df.to_csv().encode("utf-8")
        st.download_button("Download CSV", csv, "results.csv", "text/csv")
        json_str = df.to_json()
        st.download_button("Download JSON", json_str, "results.json", "application/json")


if __name__ == "__main__":
    main()