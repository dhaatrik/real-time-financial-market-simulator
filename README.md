<h1 align="center">Real-Time Financial Market Simulator</h1>

<p align="center">
  <em>Simulate, stream, and backtest financial markets — all from a single Python package.</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#testing">Testing</a> •
  <a href="#contributing">Contributing</a> •
  <a href="#license">License</a>
</p>

<p align="center">
  <a href="https://github.com/dhaatrik/real-time-financial-market-simulator/actions/workflows/ci.yml"><img src="https://github.com/dhaatrik/real-time-financial-market-simulator/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://streamlit.io/"><img src="https://img.shields.io/badge/streamlit-1.18+-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit"></a>
  <a href="https://github.com/dhaatrik/real-time-financial-market-simulator/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
  <a href="https://github.com/dhaatrik/real-time-financial-market-simulator/releases"><img src="https://img.shields.io/badge/version-0.3.0-blue" alt="Version 0.3.0"></a>
</p>

---

## Why This Project?

Financial modelling often requires expensive proprietary tools or fragmented scripts that are hard to reproduce. This project packages a complete workflow — **price simulation**, **live WebSocket streaming**, **trading strategy evaluation**, and an **interactive dashboard** — into one lightweight, installable Python package.

Under the hood, asset prices are generated using **Geometric Brownian Motion (GBM)**, the same stochastic model that underpins the Black-Scholes option pricing formula. The simulation engine is fully vectorized with NumPy for performance that scales to hundreds of thousands of time steps.

---

## Features

| Feature | Description |
|---------|-------------|
| **GBM Simulation** | Vectorized closed-form GBM producing realistic price paths in a single NumPy operation |
| **Real-Time Streaming** | WebSocket server streams price ticks at 10 Hz with configurable CLI parameters |
| **Trading Strategies** | Built-in Moving Average crossover and RSI mean-reversion strategies |
| **Backtesting Engine** | Vectorized backtester with performance metrics — total return, Sharpe ratio, max drawdown |
| **Streamlit Dashboard** | Interactive web UI for configuration, visualization, and one-click CSV/JSON export |
| **Alpha Vantage API** | Fetch real-world stock data with built-in error handling and rate-limit detection |
| **Async-Safe Utilities** | Both synchronous and async rate limiters for safe use in event loops |

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **pip** (included with Python)
- *(Optional)* A free [Alpha Vantage API key](https://www.alphavantage.co/support/#api-key) for real market data

### 1. Clone & Install

```bash
git clone https://github.com/dhaatrik/real-time-financial-market-simulator.git
cd real-time-financial-market-simulator
```

Create and activate a virtual environment:

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

Install the package in editable mode (this also installs all dependencies):

```bash
pip install -e .
```

> **Note:** Installing with `pip install -e .` registers `market_simulator` as a proper Python package, so all imports work cleanly without path hacks. You can also use `pip install -r requirements.txt` for a pinned-dependency install.

### 2. Configure Alpha Vantage *(Optional)*

Create a `.env` file in the project root:

```env
ALPHA_VANTAGE_API_KEY=your_api_key_here
```

> This file is already listed in `.gitignore` — your key will never be committed.

---

## Usage

### Launch the Streamlit Dashboard

```bash
streamlit run market_simulator/dashboard/streamlit_app.py
```

From the dashboard you can:

- **Simulate prices** — Set GBM parameters (drift, volatility, time horizon) and generate a price path
- **Fetch real data** — Switch the data source to Alpha Vantage and pull daily closes for any ticker
- **Run strategies** — Select Moving Average or RSI, tune parameters, and view signals in real time
- **View performance** — See total return, annualized Sharpe ratio, and maximum drawdown after backtesting
- **Export results** — Download simulated or fetched data as CSV or JSON

### Start the WebSocket Price Server

```bash
python -m market_simulator.websocket_server
```

The server streams JSON price ticks (`{"price": 102.34}`) at `ws://localhost:8765`. All simulation parameters are configurable:

```bash
python -m market_simulator.websocket_server \
  --s0 150    \
  --mu 0.08   \
  --sigma 0.3 \
  --host 0.0.0.0 \
  --port 9000
```

Run `--help` to see all available options:

```
$ python -m market_simulator.websocket_server --help

usage: websocket_server.py [-h] [--s0 S0] [--mu MU] [--sigma SIGMA]
                           [--T T] [--dt DT] [--host HOST] [--port PORT]

options:
  --s0 S0        Initial asset price           (default: 100.0)
  --mu MU        Annualised drift              (default: 0.05)
  --sigma SIGMA  Annualised volatility         (default: 0.2)
  --T T          Time horizon in years         (default: 1.0)
  --dt DT        Time step in years            (default: 1/252)
  --host HOST    Bind host                     (default: localhost)
  --port PORT    Bind port                     (default: 8765)
```

### Use as a Python Library

```python
from market_simulator.constants import GBMConfig
from market_simulator.gbm import GeometricBrownianMotion
from market_simulator.trading.strategies import MovingAverageStrategy
from market_simulator.trading.backtester import Backtester
import pandas as pd

# Validate parameters with Pydantic and simulate 252 trading days
config = GBMConfig(S0=100, mu=0.05, sigma=0.2, T=1, dt=1/252)
gbm = GeometricBrownianMotion(config=config)
prices = gbm.simulate()

# Wrap in a DataFrame and run a Moving Average strategy
df = pd.DataFrame({"Close": prices})
strategy = MovingAverageStrategy(short_window=10, long_window=30)
signals = strategy.generate_signals(df)

# Backtest and view performance
bt = Backtester(strategy, df)
bt.run_backtest()
print(bt.calculate_performance())
# {'total_return': 0.047, 'annualised_sharpe': 0.82, 'max_drawdown': -0.063}
```

---

## Project Structure

```
real-time-financial-market-simulator/
├── market_simulator/
│   ├── __init__.py
│   ├── constants.py              # Pydantic models & enums (GBMConfig, StrategyType)
│   ├── gbm.py                    # Vectorized GBM simulation engine
│   ├── utils.py                  # Sync & async rate-limiting decorators
│   ├── websocket_server.py       # CLI-configurable WebSocket price server
│   ├── dashboard/
│   │   └── streamlit_app.py      # Interactive Streamlit dashboard
│   ├── data/
│   │   └── alpha_vantage.py      # Alpha Vantage API client (httpx, sync + async)
│   ├── trading/
│   │   ├── __init__.py
│   │   ├── strategies.py         # MA crossover & RSI strategy implementations
│   │   └── backtester.py         # Vectorized backtester with performance metrics
│   └── tests/
│       ├── test_gbm.py           # Quantitative GBM tests (Monte Carlo + validation)
│       ├── test_strategies.py    # Deterministic strategy signal tests
│       └── dashboard/
│           └── test_streamlit_app.py  # AppTest-based dashboard tests
├── pyproject.toml                # PEP 517 build config & project metadata
├── requirements.txt              # Pinned dependencies
├── LICENSE                       # MIT License
└── README.md
```

---

## Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.11+ | Core language |
| **Simulation** | NumPy | Vectorized GBM price path generation |
| **Data** | Pandas | DataFrames for price series, signals, and returns |
| **Validation** | Pydantic | Strict parameter validation via `GBMConfig` |
| **Dashboard** | Streamlit | Interactive web UI with charts and controls |
| **Streaming** | websockets | Async WebSocket server for live price feeds |
| **Market Data** | Alpha Vantage API | Real-world stock and forex data |
| **HTTP** | httpx | Sync + async API client with timeout handling |
| **Testing** | pytest + Streamlit AppTest | Unit, quantitative, and integration testing |
| **Packaging** | setuptools (PEP 517) | Editable installs via `pyproject.toml` |

---

## Testing

The test suite uses **pytest** with Streamlit's official **AppTest** framework for UI integration tests.

```bash
# Run all tests
python -m pytest market_simulator/tests/ -v

# Run with verbose output and short tracebacks
python -m pytest market_simulator/tests/ -v --tb=short
```

**Test coverage includes:**

- **GBM statistical tests** — Monte Carlo terminal mean vs theory, output shape, all-positive prices
- **Pydantic validation** — rejects negative volatility, zero time horizon, negative prices
- **Strategy signal tests** — deterministic MA crossover and RSI overbought/oversold verification
- **WebSocket URI validation** — verifies that only allow-listed URIs can initiate a connection
- **GBM simulation smoke test** — confirms the dashboard renders without exceptions
- **Alpha Vantage error surfacing** — ensures API errors are displayed to the user via `st.error`

---

## Contributing

Contributions are welcome! Whether it's a bug fix, a new trading strategy, or documentation improvements, here's how to get started:

1. **Fork** the repository
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Install dev dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```
4. **Make your changes** and ensure all tests pass:
   ```bash
   python -m pytest market_simulator/tests/ -v
   ```
5. **Commit** with a clear, descriptive message
6. **Open a Pull Request** against `main`

### Guidelines

- Follow existing code style — type hints and docstrings on all public functions
- Add tests for any new feature or bug fix
- Keep pull requests focused on a single change
- Be respectful and constructive in all interactions

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/) Code of Conduct.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: market_simulator` | Run `pip install -e .` from the project root to register the package |
| WebSocket connection refused | Start the server first: `python -m market_simulator.websocket_server` |
| Alpha Vantage rate-limit error | Free API keys are limited to 25 requests/day. Wait or upgrade your plan |
| Alpha Vantage "Invalid API call" | Double-check the ticker symbol and ensure your `.env` file contains a valid key |
| Streamlit `ScriptRunContext` warning | Safe to ignore in test/bare-mode contexts |

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

Copyright &copy; 2026 **Dhaatrik Chowdhury**
