from unittest.mock import MagicMock, patch

from watch_hunter.currency import CurrencyConverter


def test_currency_conversion_fallback_rates() -> None:
    converter = CurrencyConverter()
    converter._fetched = True  # Avoid network call in unit test

    # EUR to EUR
    assert converter.to_eur(3000.0, "EUR") == 3000.0

    # USD to EUR (at default rate 1.08)
    assert converter.to_eur(3240.0, "USD") == 3000.0

    # GBP to EUR (at default rate 0.85)
    assert converter.to_eur(2550.0, "GBP") == 3000.0

    # CHF to EUR (at default rate 0.95)
    assert converter.to_eur(2850.0, "CHF") == 3000.0


def test_currency_conversion_unknown_currency() -> None:
    converter = CurrencyConverter()
    converter._fetched = True
    assert converter.to_eur(2700.0, "XYZ") == 2700.0


def test_currency_fetch_live_rates() -> None:
    converter = CurrencyConverter()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "rates": {
            "USD": 1.10,
            "GBP": 0.86,
            "CHF": 0.96,
        }
    }

    with patch("requests.get", return_value=mock_resp):
        success = converter.fetch_live_rates()
        assert success is True
        assert converter.rates["USD"] == 1.10
        assert converter.to_eur(3300.0, "USD") == 3000.0


def test_currency_convert_between_currencies() -> None:
    converter = CurrencyConverter()
    converter._fetched = True
    converter.rates["USD"] = 1.10
    converter.rates["GBP"] = 0.88

    # 100 GBP -> EUR -> USD
    # 100 / 0.88 = 113.64 EUR -> 113.64 * 1.10 = 125.0 EUR
    usd_val = converter.convert(100.0, "GBP", "USD")
    assert usd_val > 120.0
