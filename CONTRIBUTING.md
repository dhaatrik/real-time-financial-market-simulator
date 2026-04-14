# Contributing to Real-Time Financial Market Simulator

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behaviour by opening a GitHub issue.

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/dhaatrik/real-time-financial-market-simulator/issues) to avoid duplicates.
2. Open a new issue with:
   - A clear, descriptive title
   - Steps to reproduce the bug
   - Expected vs. actual behaviour
   - Python version and OS

### Suggesting Features

1. Open an issue with the **Feature Request** label.
2. Describe the problem you're trying to solve and your proposed solution.

### Submitting Changes

1. **Fork** the repository.
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Install the project in editable mode** with dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
4. **Make your changes**, following the conventions below.
5. **Run the tests** and ensure they all pass:
   ```bash
   python -m pytest market_simulator/tests/ -v
   ```
6. **Run the linter** to catch style issues:
   ```bash
   python -m flake8 market_simulator/ --max-line-length 120
   ```
7. **Commit** with a clear, descriptive message:
   ```bash
   git commit -m "Add RSI divergence strategy"
   ```
8. **Push** your branch and open a **Pull Request** against `main`.

## Code Conventions

- **Type hints** on all public function signatures
- **Docstrings** in Google/NumPy style on all public classes and functions
- **`.loc`-based Pandas assignments** (never chained indexing)
- **Maximum line length**: 120 characters
- **Testing**: add or update tests for any new feature or bug fix

## Development Setup

```bash
# Clone your fork
git clone https://github.com/<your-username>/real-time-financial-market-simulator.git
cd real-time-financial-market-simulator

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Run the test suite
python -m pytest market_simulator/tests/ -v
```

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
