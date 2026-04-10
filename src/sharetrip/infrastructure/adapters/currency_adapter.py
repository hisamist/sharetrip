import httpx

from sharetrip.domain.interfaces.currency_port import CurrencyPort

_DEFAULT_BASE_URL = "https://api.frankfurter.app"


class FrankfurterCurrencyAdapter(CurrencyPort):
    """Adapte l'API publique Frankfurter au port CurrencyPort du domaine.

    Pattern Adapter : le domaine ne connaît que CurrencyPort.get_rate().
    Cette classe traduit l'appel vers l'API externe et retourne
    uniquement le float attendu par le domaine.
    """

    def __init__(self, base_url: str = _DEFAULT_BASE_URL) -> None:
        self._base_url = base_url

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        if from_currency == to_currency:
            return 1.0

        response = httpx.get(
            f"{self._base_url}/latest",
            params={"from": from_currency, "to": to_currency},
            timeout=5.0,
        )
        response.raise_for_status()
        data = response.json()

        return data["rates"][to_currency]
