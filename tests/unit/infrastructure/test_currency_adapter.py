"""Unit tests for FrankfurterCurrencyAdapter — httpx is fully mocked."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from sharetrip.infrastructure.adapters.currency_adapter import FrankfurterCurrencyAdapter


class TestFrankfurterCurrencyAdapter:
    def test_get_rate_returns_1_when_same_currency(self):
        assert FrankfurterCurrencyAdapter().get_rate("EUR", "EUR") == 1.0

    def test_get_rate_does_not_call_http_when_same_currency(self):
        with patch("httpx.get") as mock_get:
            FrankfurterCurrencyAdapter().get_rate("USD", "USD")
        mock_get.assert_not_called()

    def test_get_rate_calls_api_and_returns_rate(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"USD": 1.08}}
        mock_resp.raise_for_status.return_value = None
        with patch("httpx.get", return_value=mock_resp):
            result = FrankfurterCurrencyAdapter().get_rate("EUR", "USD")
        assert result == 1.08

    def test_get_rate_uses_correct_endpoint_and_params(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"JPY": 150.0}}
        mock_resp.raise_for_status.return_value = None
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            FrankfurterCurrencyAdapter(base_url="http://test-api").get_rate("EUR", "JPY")
        mock_get.assert_called_once_with(
            "http://test-api/latest",
            params={"from": "EUR", "to": "JPY"},
            timeout=5.0,
        )

    def test_get_rate_uses_default_base_url(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"USD": 1.1}}
        mock_resp.raise_for_status.return_value = None
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            FrankfurterCurrencyAdapter().get_rate("EUR", "USD")
        url = mock_get.call_args[0][0]
        assert url.startswith("https://api.frankfurter.app")

    def test_get_rate_raises_when_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )
        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(httpx.HTTPStatusError):
                FrankfurterCurrencyAdapter().get_rate("EUR", "USD")
