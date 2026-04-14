"""Real-time price streaming server using WebSockets and GBM.

Run the server with custom parameters::

    python -m market_simulator.websocket_server --s0 150 --mu 0.08 --sigma 0.25

Then connect any WebSocket client to ``ws://localhost:8765``.  The server
streams JSON messages of the form ``{"price": <float>}`` at 10 Hz.
"""

import argparse
import asyncio
import json
import logging
from typing import Any

import numpy as np
import websockets

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser` instance.
    """
    parser = argparse.ArgumentParser(
        description="Real-time GBM price streaming WebSocket server.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--s0", type=float, default=100.0, help="Initial asset price.")
    parser.add_argument("--mu", type=float, default=0.05, help="Annualised drift.")
    parser.add_argument("--sigma", type=float, default=0.2, help="Annualised volatility.")
    parser.add_argument("--T", type=float, default=1.0, help="Time horizon in years.")
    parser.add_argument(
        "--dt",
        type=float,
        default=1 / 252,
        help="Time step in years (default: 1 trading day).",
    )
    parser.add_argument("--host", type=str, default="localhost", help="Bind host.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    return parser


async def price_stream(
    websocket: Any,
    s0: float,
    mu: float,
    sigma: float,
    dt: float,
) -> None:
    """Stream GBM price ticks to a connected WebSocket client.

    Each iteration generates the next GBM step and sends a JSON message.
    Uses ``asyncio.sleep`` so the event loop is never blocked.

    Args:
        websocket: The connected client WebSocket.
        s0: Current price (mutated each iteration as the running price).
        mu: Annualised drift.
        sigma: Annualised volatility.
        dt: Length of one time step in years.
    """
    price: float = s0
    try:
        while True:
            W: float = float(np.random.normal(0, np.sqrt(dt)))
            price = price * float(np.exp((mu - 0.5 * sigma**2) * dt + sigma * W))
            await websocket.send(json.dumps({"price": price}))
            await asyncio.sleep(0.1)
    except websockets.exceptions.ConnectionClosedOK:
        logger.info("Client disconnected cleanly.")
    except websockets.exceptions.ConnectionClosedError as exc:
        logger.warning("Client connection closed with error: %s", exc)


async def main() -> None:
    """Parse CLI arguments, start the WebSocket server, and run forever."""
    args = _build_parser().parse_args()

    logger.info(
        "Starting WebSocket server on ws://%s:%d  "
        "[S0=%.2f, mu=%.4f, sigma=%.4f, T=%.2f, dt=%.6f]",
        args.host,
        args.port,
        args.s0,
        args.mu,
        args.sigma,
        args.T,
        args.dt,
    )

    async def _handler(websocket: Any) -> None:
        await price_stream(websocket, args.s0, args.mu, args.sigma, args.dt)

    async with websockets.serve(_handler, args.host, args.port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())