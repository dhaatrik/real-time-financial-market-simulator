"""Geometric Brownian Motion (GBM) simulation module."""

import numpy as np


class GeometricBrownianMotion:
    """Simulates asset price paths using Geometric Brownian Motion.

    Uses the closed-form GBM solution with a fully vectorized NumPy
    implementation to generate price paths orders of magnitude faster
    than a step-by-step Python loop.

    Args:
        S0: Initial asset price.
        mu: Expected annualised drift (e.g. 0.05 for 5 %).
        sigma: Annualised volatility (e.g. 0.2 for 20 %).
        T: Time horizon in years (e.g. 1.0 for one year).
        dt: Length of a single time step in years (e.g. 1/252 for one trading day).

    Attributes:
        n: Total number of time steps.
        S: Simulated price path array of shape ``(n,)``.
    """

    def __init__(
        self,
        S0: float,
        mu: float,
        sigma: float,
        T: float,
        dt: float,
    ) -> None:
        self.S0 = S0
        self.mu = mu
        self.sigma = sigma
        self.T = T
        self.dt = dt
        self.n: int = int(T / dt)
        self.S: np.ndarray = np.zeros(self.n)
        self.S[0] = S0

    def simulate(self) -> np.ndarray:
        """Generate a complete GBM price path using NumPy vectorisation.

        Generates all Brownian increments at once, accumulates them via
        ``np.cumsum``, and applies the closed-form GBM formula across the
        entire array in a single operation — no Python-level loop required.

        Returns:
            A NumPy array of length ``n`` containing the simulated price path,
            with ``S[0] == S0``.
        """
        # Draw all increments at once and accumulate into a Brownian path
        increments: np.ndarray = np.random.normal(0, np.sqrt(self.dt), size=self.n)
        W: np.ndarray = np.cumsum(increments)

        # Time grid: dt, 2·dt, …, n·dt
        t: np.ndarray = np.linspace(self.dt, self.T, self.n)

        # Closed-form GBM applied element-wise across the whole array
        prices: np.ndarray = self.S0 * np.exp(
            (self.mu - 0.5 * self.sigma**2) * t + self.sigma * W
        )

        # Restore S0 at index 0 (shift the path back by one step)
        self.S = np.empty(self.n)
        self.S[0] = self.S0
        self.S[1:] = prices[:-1]
        return self.S
