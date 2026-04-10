from abc import ABC, abstractmethod


class CurrencyPort(ABC):
    """Port (interface) vers le service externe de taux de change.

    Isole le domaine de toute dépendance sur une API tierce.
    L'implémentation concrète vit dans infrastructure/adapters/.
    """

    @abstractmethod
    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Retourne le taux de change from_currency → to_currency."""
        ...
