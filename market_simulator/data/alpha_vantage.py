"""Alpha Vantage API integration module."""

import os
import requests


class AlphaVantageError(Exception):
    """Raised when the Alpha Vantage API returns an error or rate-limit notice."""


class AlphaVantage:
    """Thin wrapper around the Alpha Vantage REST API.

    API credentials are read from the ``ALPHA_VANTAGE_API_KEY`` environment
    variable when not supplied directly. All requests include a 10-second
    timeout to prevent indefinite hangs on slow or dropped connections.

    Args:
        api_key: Alpha Vantage API key.  Falls back to the
            ``ALPHA_VANTAGE_API_KEY`` environment variable when ``None``.

    Raises:
        AlphaVantageError: When the API returns a rate-limit notice, an error
            message, or any other non-data JSON payload.
        requests.exceptions.Timeout: When the HTTP request exceeds 10 seconds.
        requests.exceptions.RequestException: For any other network-level error.
    """

    _REQUEST_TIMEOUT: int = 10  # seconds

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key: str | None = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self.base_url: str = "https://www.alphavantage.co/query"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, params: dict) -> dict:
        """Make a GET request and validate the JSON response.

        Args:
            params: Query parameters to pass to the Alpha Vantage endpoint.

        Returns:
            The parsed JSON payload as a ``dict``.

        Raises:
            AlphaVantageError: If the response contains an API-level error or
                rate-limit notice instead of the expected data structure.
            requests.exceptions.Timeout: If the request exceeds
                :attr:`_REQUEST_TIMEOUT` seconds.
        """
        response = requests.get(
            self.base_url,
            params=params,
            timeout=self._REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data: dict = response.json()
        self._check_api_errors(data)
        return data

    @staticmethod
    def _check_api_errors(data: dict) -> None:
        """Inspect the JSON payload for API-level error keys.

        Alpha Vantage returns HTTP 200 even when the request fails at the
        application level.  The error condition is signalled by the presence
        of well-known keys in the response body.

        Args:
            data: Parsed JSON response from the API.

        Raises:
            AlphaVantageError: If ``'Error Message'``, ``'Note'``, or
                ``'Information'`` keys are found in *data*.
        """
        if "Error Message" in data:
            raise AlphaVantageError(
                f"Alpha Vantage API error: {data['Error Message']}"
            )
        if "Note" in data:
            raise AlphaVantageError(
                f"Alpha Vantage rate-limit notice: {data['Note']}"
            )
        if "Information" in data:
            raise AlphaVantageError(
                f"Alpha Vantage information notice: {data['Information']}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_stock_data(
        self,
        symbol: str,
        function: str = "TIME_SERIES_DAILY",
    ) -> dict:
        """Fetch time-series stock data for a given ticker symbol.

        Args:
            symbol: The equity ticker symbol (e.g. ``'AAPL'``).
            function: Alpha Vantage function name.  Defaults to
                ``'TIME_SERIES_DAILY'``.

        Returns:
            The full parsed JSON response from Alpha Vantage.

        Raises:
            AlphaVantageError: On API-level errors or rate-limit notices.
            requests.exceptions.Timeout: If the network request times out.
        """
        params: dict = {
            "function": function,
            "symbol": symbol,
            "apikey": self.api_key,
        }
        return self._get(params)

    def get_forex_data(
        self,
        from_currency: str,
        to_currency: str,
        function: str = "CURRENCY_EXCHANGE_RATE",
    ) -> dict:
        """Fetch the current exchange rate between two currencies.

        Args:
            from_currency: The source ISO 4217 currency code (e.g. ``'USD'``).
            to_currency: The target ISO 4217 currency code (e.g. ``'EUR'``).
            function: Alpha Vantage function name.  Defaults to
                ``'CURRENCY_EXCHANGE_RATE'``.

        Returns:
            The full parsed JSON response from Alpha Vantage.

        Raises:
            AlphaVantageError: On API-level errors or rate-limit notices.
            requests.exceptions.Timeout: If the network request times out.
        """
        params: dict = {
            "function": function,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "apikey": self.api_key,
        }
        return self._get(params)