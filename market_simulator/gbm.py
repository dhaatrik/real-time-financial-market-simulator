"""Geometric Brownian Motion (GBM) simulation module."""

from __future__ import annotations

import numpy as np

from market_simulator.constants import GBMConfig


class GeometricBrownianMotion:
    """Simulates asset price paths using Geometric Brownian Motion.

    Uses the closed-form GBM solution with a fully vectorized NumPy
    implementation to generate price paths orders of magnitude faster
    than a step-by-step Python loop.

    The constructor accepts either a :class:`GBMConfig` object **or**
    individual keyword arguments (which are forwarded to ``GBMConfig``
    for validation).

    Args:
        config: A pre-built :class:`GBMConfig` instance.
        S0: Initial asset price (ignored when *config* is supplied).
        mu: Expected annualised drift.
        sigma: Annualised volatility.
        T: Time horizon in years.
        dt: Length of a single time step in years.

    Raises:
        pydantic.ValidationError: When any physical constraint is violated
            (e.g. ``sigma <= 0``).

    Attributes:
        config: The validated :class:`GBMConfig` for this simulation.
        n: Total number of time steps.
        S: Simulated price path array of shape ``(n,)``.\
    """

    def __init__(
        self,
        config: GBMConfig | None = None,
        *,
        S0: float = 0,
        mu: float = 0,
        sigma: float = 0,
        T: float = 0,
        dt: float = 0,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = GBMConfig(S0=S0, mu=mu, sigma=sigma, T=T, dt=dt)

        self.n: int = int(self.config.T / self.config.dt)
        self.S: np.ndarray = np.zeros(self.n)
        self.S[0] = self.config.S0

    def simulate(self) -> np.ndarray:
        """Generate a complete GBM price path using NumPy vectorisation.

        Generates all Brownian increments at once, accumulates them via
        ``np.cumsum``, and applies the closed-form GBM formula across the
        entire array in a single operation — no Python-level loop required.

        Returns:
            A NumPy array of length ``n`` containing the simulated price path,
            with ``S[0] == S0``.
        """
        cfg = self.config

        # Draw all increments at once and accumulate into a Brownian path
        increments: np.ndarray = np.random.normal(
            0, np.sqrt(cfg.dt), size=self.n,
        )
        W: np.ndarray = np.cumsum(increments)

        # Time grid: dt, 2·dt, …, n·dt
        t: np.ndarray = np.linspace(cfg.dt, cfg.T, self.n)

        # Closed-form GBM applied element-wise across the whole array
        prices: np.ndarray = cfg.S0 * np.exp(
            (cfg.mu - 0.5 * cfg.sigma**2) * t + cfg.sigma * W
        )

        # Restore S0 at index 0 (shift the path back by one step)
        self.S = np.empty(self.n)
        self.S[0] = cfg.S0
        self.S[1:] = prices[:-1]
        return self.S
