"""Shared constants, enums, and configuration models.

Centralises all "magic strings" and validated parameter schemas so that
the rest of the codebase can import them by name rather than relying on
raw string comparisons.
"""

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StrategyType(str, Enum):
    """Available trading strategies for the dashboard selectbox."""

    NONE = "None"
    MOVING_AVERAGE = "Moving Average"
    RSI = "RSI"


class DataSource(str, Enum):
    """Available data sources for price data."""

    SIMULATED = "Simulated (GBM)"
    ALPHA_VANTAGE = "Alpha Vantage"


# ---------------------------------------------------------------------------
# Pydantic configuration models
# ---------------------------------------------------------------------------

class GBMConfig(BaseModel):
    """Validated configuration for a Geometric Brownian Motion simulation.

    All physical constraints are enforced at construction time via Pydantic
    field validators.  Invalid values (e.g. negative volatility) raise a
    ``pydantic.ValidationError`` with a clear message.

    Args:
        S0: Initial asset price.  Must be > 0.
        mu: Expected annualised drift (unconstrained — can be negative).
        sigma: Annualised volatility.  Must be > 0.
        T: Time horizon in years.  Must be > 0.
        dt: Length of a single time step in years.  Must be > 0.
    """

    S0: float = Field(gt=0, description="Initial asset price")
    mu: float = Field(description="Annualised drift")
    sigma: float = Field(gt=0, description="Annualised volatility")
    T: float = Field(gt=0, description="Time horizon in years")
    dt: float = Field(gt=0, description="Time step in years")
