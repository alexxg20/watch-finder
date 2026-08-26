import logging
from typing import ClassVar

import requests

logger = logging.getLogger(__name__)


class CurrencyConverter:
    # Fallback rates if external API is unreachable (base: EUR)
    DEFAULT_RATES: ClassVar[dict[str, float]] = {
        "EUR": 1.0,
        "CHF": 0.95,
        "GBP": 0.85,
        "USD": 1.08,
        "CAD": 1.48,
        "AUD": 1.65,
        "JPY": 165.0,
        "SEK": 11.4,
        "NOK": 11.6,
        "DKK": 7.46,
        "PLN": 4.30,
        "CZK": 25.2,
    }

    def __init__(self, api_url: str = "https://api.frankfurter.app/latest?from=EUR") -> None:
        self.api_url = api_url
        self.rates: dict[str, float] = dict(self.DEFAULT_RATES)
        self._fetched = False

    def fetch_live_rates(self, timeout_seconds: float = 5.0) -> bool:
        if self._fetched:
            return True
        try:
            response = requests.get(self.api_url, timeout=timeout_seconds)
            if response.status_code == 200:
                data = response.json()
                live_rates = data.get("rates", {})
                self.rates["EUR"] = 1.0
                for curr, rate in live_rates.items():
                    self.rates[curr.upper()] = float(rate)
                self._fetched = True
                logger.info("Successfully fetched %d live exchange rates", len(live_rates))
                return True
            logger.warning(
                "Currency API returned HTTP %d, using fallback rates", response.status_code
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch live exchange rates: %s. Using default fallback rates", exc
            )
        return False

    def to_eur(self, amount: float, currency: str) -> float:
        curr = currency.upper().strip()
        if curr == "EUR":
            return round(amount, 2)
        if not self._fetched:
            self.fetch_live_rates()
        rate = self.rates.get(curr)
        if not rate or rate <= 0:
            logger.warning("Unknown currency '%s', assuming 1:1 parity with EUR", curr)
            return round(amount, 2)
        # amount in foreign currency / (foreign currency per EUR) = amount in EUR
        return round(amount / rate, 2)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        eur_amount = self.to_eur(amount, from_currency)
        if to_currency.upper() == "EUR":
            return eur_amount
        if not self._fetched:
            self.fetch_live_rates()
        to_rate = self.rates.get(to_currency.upper(), 1.0)
        return round(eur_amount * to_rate, 2)
