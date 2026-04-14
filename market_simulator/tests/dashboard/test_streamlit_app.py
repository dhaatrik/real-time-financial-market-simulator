"""Tests for the Streamlit dashboard using AppTest.

Uses ``AppTest.from_file`` to load the dashboard in Streamlit's sandboxed
test runner. Since ``from_file`` re-executes the script in its own namespace,
``unittest.mock.patch`` on the module boundary is not effective for functions
defined *inside* the script.

Test strategy:
- **URI validation**: Tests the allow-list logic directly—invalid URIs never
  reach ``run_websocket_client``, so no mock is needed.
- **GBM simulation**: Pure-UI smoke test; no external dependencies.
- **Alpha Vantage errors**: Patches ``requests.get`` (a third-party import
  that *is* shared across namespaces via ``sys.modules``).

Run with::

    python -m pytest market_simulator/tests/dashboard/ -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

from streamlit.testing.v1 import AppTest

# Absolute path to the script under test
_APP_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "dashboard" / "streamlit_app.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app() -> AppTest:
    """Return a fresh :class:`AppTest` instance for the dashboard script."""
    return AppTest.from_file(_APP_PATH, default_timeout=30)


def _get_widget_by_label(widget_list, label: str):
    """Find a widget in an AppTest widget list by its label attribute."""
    for w in widget_list:
        if getattr(w, "label", None) == label:
            return w
    raise KeyError(f"No widget found with label '{label}'")


# ---------------------------------------------------------------------------
# 1. WebSocket URI validation (pure logic — no network mock required)
# ---------------------------------------------------------------------------

class TestWebSocketURIValidation:
    """Verify that only allow-listed URIs can trigger a WebSocket connection."""

    def test_invalid_uri_shows_error(self):
        """An untrusted URI must display an error message."""
        at = _make_app()
        at.run()

        # Enable WebSocket checkbox and set a malicious URI
        at.sidebar.checkbox[0].set_value(True).run()
        _get_widget_by_label(at.sidebar.text_input, "WebSocket URI").set_value(
            "ws://malicious.com"
        ).run()

        # Click "Start WebSocket Stream"
        at.button("btn_ws_stream").click().run()

        assert any(
            "Invalid WebSocket URI" in str(getattr(e, "value", ""))
            for e in at.error
        ), "Expected an 'Invalid WebSocket URI' error message."

    def test_valid_uri_no_validation_error(self):
        """A trusted ws:// URI must NOT trigger a URI-validation error.

        Note: The actual WebSocket connection will fail (no server running)
        but the *validation* gate should pass.
        """
        at = _make_app()
        at.run()

        at.sidebar.checkbox[0].set_value(True).run()
        _get_widget_by_label(at.sidebar.text_input, "WebSocket URI").set_value(
            "ws://localhost:8765"
        ).run()

        at.button("btn_ws_stream").click().run()

        # No Invalid URI error should appear (connection errors are acceptable)
        assert not any(
            "Invalid WebSocket URI" in str(getattr(e, "value", ""))
            for e in at.error
        ), "Valid URI should not trigger URI-validation error."


# ---------------------------------------------------------------------------
# 2. GBM Simulation smoke test (pure AppTest)
# ---------------------------------------------------------------------------

class TestSimulateButton:
    """Smoke-test the 'Simulate/Run Backtest' button for the GBM data path."""

    def test_simulate_gbm_produces_output(self):
        """Clicking Simulate with GBM defaults should not crash."""
        at = _make_app()
        at.run()

        at.button("btn_simulate").click().run()

        # The app should not have crashed
        assert not at.exception, (
            f"App raised an exception: "
            f"{[str(e) for e in at.exception]}"
        )


# ---------------------------------------------------------------------------
# 3. Alpha Vantage error surfacing (patches at the requests library level)
# ---------------------------------------------------------------------------

class TestAlphaVantageErrorHandling:
    """Verify that API errors are surfaced as st.error in the UI."""

    def test_api_error_key_shown_in_ui(self):
        """When the Alpha Vantage API returns an 'Error Message' key, the
        dashboard must display an error via ``st.error``."""
        # Build a fake response object with a JSON containing an error key
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {
            "Error Message": "Invalid API call. Please retry."
        }

        with patch("requests.get", return_value=fake_response):
            at = _make_app()
            at.run()

            _get_widget_by_label(at.sidebar.selectbox, "Select Data Source").set_value(
                "Alpha Vantage"
            ).run()

            _get_widget_by_label(
                at.sidebar.button, "Fetch Alpha Vantage Data"
            ).click().run()

            error_texts = [str(getattr(e, "value", "")).lower() for e in at.error]
            assert any(
                "error" in t or "invalid" in t for t in error_texts
            ), f"Expected an API error message. Got: {error_texts}"
