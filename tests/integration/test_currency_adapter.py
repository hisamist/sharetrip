from unittest.mock import MagicMock, patch

import pytest
from sharetrip.infrastructure.adapters.currency_adapter import (
    FrankfurterCurrencyAdapter,
)


@pytest.fixture
def adapter() -> FrankfurterCurrencyAdapter:
    return FrankfurterCurrencyAdapter()


def _mock_response(rates: dict) -> MagicMock:
    """Construit une fausse réponse httpx avec les taux fournis."""
    mock = MagicMock()
    mock.json.return_value = {"rates": rates}
    mock.raise_for_status.return_value = None
    return mock


# ─── Cas normaux ──────────────────────────────────────────────────────────────


class TestGetRate:
    @patch("sharetrip.infrastructure.adapters.currency_adapter.httpx.get")
    def test_jpy_to_eur(self, mock_get, adapter):
        mock_get.return_value = _mock_response({"EUR": 0.0061})

        rate = adapter.get_rate("JPY", "EUR")

        assert rate == pytest.approx(0.0061)
        mock_get.assert_called_once_with(
            "https://api.frankfurter.app/latest",
            params={"from": "JPY", "to": "EUR"},
            timeout=5.0,
        )

    @patch("sharetrip.infrastructure.adapters.currency_adapter.httpx.get")
    def test_usd_to_eur(self, mock_get, adapter):
        mock_get.return_value = _mock_response({"EUR": 0.92})

        rate = adapter.get_rate("USD", "EUR")

        assert rate == pytest.approx(0.92)

    def test_same_currency_returns_one(self, adapter):
        """Aucun appel HTTP si from == to."""
        rate = adapter.get_rate("EUR", "EUR")
        assert rate == 1.0

    @patch("sharetrip.infrastructure.adapters.currency_adapter.httpx.get")
    def test_amount_conversion(self, mock_get, adapter):
        """Vérifie que le taux retourné donne le bon montant converti."""
        mock_get.return_value = _mock_response({"EUR": 0.0061})

        rate = adapter.get_rate("JPY", "EUR")
        converted = round(5000 * rate, 2)

        assert converted == pytest.approx(30.5)


# ─── Cas d'erreur ─────────────────────────────────────────────────────────────


class TestGetRateErrors:
    @patch("sharetrip.infrastructure.adapters.currency_adapter.httpx.get")
    def test_http_error_propagates(self, mock_get, adapter):
        """Une erreur HTTP (ex: 422) doit remonter au Use Case."""
        import httpx

        mock_get.return_value = MagicMock(
            raise_for_status=MagicMock(
                side_effect=httpx.HTTPStatusError("422", request=MagicMock(), response=MagicMock())
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            adapter.get_rate("JPY", "EUR")

    @patch("sharetrip.infrastructure.adapters.currency_adapter.httpx.get")
    def test_timeout_propagates(self, mock_get, adapter):
        """Un timeout réseau doit remonter au Use Case."""
        import httpx

        mock_get.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(httpx.TimeoutException):
            adapter.get_rate("JPY", "EUR")
