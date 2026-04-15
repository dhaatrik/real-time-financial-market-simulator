"""Quantitative tests for the Geometric Brownian Motion simulation.

Verifies statistical properties, output shape, Pydantic validation,
and edge-case behaviour of :class:`GeometricBrownianMotion`.

Run with::

    python -m pytest market_simulator/tests/test_gbm.py -v
"""

import numpy as np
import pytest
from pydantic import ValidationError

from market_simulator.constants import GBMConfig
from market_simulator.gbm import GeometricBrownianMotion


class TestGBMOutputShape:
    """Verify basic output shape and initial conditions."""

    def test_output_length_equals_n(self):
        """The simulated path length must equal T / dt."""
        gbm = GeometricBrownianMotion(S0=100, mu=0.05, sigma=0.2, T=1, dt=1 / 252)
        S = gbm.simulate()
        assert len(S) == gbm.n

    def test_initial_price_is_S0(self):
        """The first element of the simulated path must be S0."""
        gbm = GeometricBrownianMotion(S0=42.0, mu=0.0, sigma=0.1, T=1, dt=0.01)
        S = gbm.simulate()
        assert S[0] == pytest.approx(42.0)

    def test_all_prices_positive(self):
        """GBM is a log-normal process — all prices must be > 0."""
        gbm = GeometricBrownianMotion(S0=100, mu=-0.1, sigma=0.5, T=2, dt=1 / 252)
        S = gbm.simulate()
        assert np.all(S > 0)


class TestGBMStatisticalProperties:
    """Monte Carlo tests for statistical accuracy."""

    def test_terminal_mean_matches_theory(self):
        r"""Running 10,000 paths, the terminal mean must approximate
        :math:`S_0 \\cdot e^{\\mu T}` within 5 % relative tolerance.
        """
        S0, mu, T = 100.0, 0.05, 1.0
        sigma, dt = 0.2, 1 / 252
        n_paths = 10_000

        terminals = np.empty(n_paths)
        for i in range(n_paths):
            gbm = GeometricBrownianMotion(S0=S0, mu=mu, sigma=sigma, T=T, dt=dt)
            S = gbm.simulate()
            terminals[i] = S[-1]

        theoretical_mean = S0 * np.exp(mu * T)
        empirical_mean = terminals.mean()
        assert empirical_mean == pytest.approx(theoretical_mean, rel=0.05)


class TestGBMConfig:
    """Verify construction via GBMConfig and Pydantic validation."""

    def test_config_object_accepted(self):
        """Constructing with a GBMConfig object must work."""
        cfg = GBMConfig(S0=100, mu=0.05, sigma=0.2, T=1, dt=0.01)
        gbm = GeometricBrownianMotion(config=cfg)
        assert gbm.config.S0 == 100

    def test_negative_sigma_raises_validation_error(self):
        """Negative volatility must be rejected by Pydantic."""
        with pytest.raises(ValidationError):
            GBMConfig(S0=100, mu=0.05, sigma=-0.2, T=1, dt=0.004)

    def test_zero_T_raises_validation_error(self):
        """Zero time horizon must be rejected by Pydantic."""
        with pytest.raises(ValidationError):
            GBMConfig(S0=100, mu=0.05, sigma=0.2, T=0, dt=0.004)

    def test_negative_S0_raises_validation_error(self):
        """Negative initial price must be rejected by Pydantic."""
        with pytest.raises(ValidationError):
            GBMConfig(S0=-100, mu=0.05, sigma=0.2, T=1, dt=0.004)
