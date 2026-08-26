import json
from pathlib import Path

from watch_hunter.adapters.chrono24 import Chrono24AdapterStub
from watch_hunter.models import SearchCriteria


def test_chrono24_stub_unconfigured(tmp_path: Path) -> None:
    stub = Chrono24AdapterStub(import_dir=tmp_path / "empty_dir")
    assert stub.is_configured() is False
    assert stub.fetch_listings(SearchCriteria()) == []


def test_chrono24_saved_search_file_import(tmp_path: Path) -> None:
    import_dir = tmp_path / "imports"
    import_dir.mkdir(parents=True)

    sample_data = {
        "listings": [
            {
                "id": "c24_998877",
                "title": "Omega Seamaster Aqua Terra 231.10.39.21.02.002",
                "price": 3100.0,
                "currency": "EUR",
                "condition": "Very Good",
                "seller": "Swiss Luxury Watches AG",
                "url": "https://www.chrono24.com/omega/ref-23110392102002.htm",
                "country": "CH",
            }
        ]
    }

    file_path = import_dir / "c24_alert.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f)

    adapter = Chrono24AdapterStub(import_dir=import_dir)
    assert adapter.is_configured() is True

    listings = adapter.fetch_listings(SearchCriteria())
    assert len(listings) == 1
    item = listings[0]
    assert item.id == "chrono24:c24_998877"
    assert item.price == 3100.0
    assert item.source == "chrono24"
    assert item.seller == "Swiss Luxury Watches AG"
    assert item.location == "CH"


def test_chrono24_email_text_parser() -> None:
    adapter = Chrono24AdapterStub()
    email_text = """
    New watch alert from Chrono24:
    Omega Seamaster Aqua Terra 150M Co-Axial
    Condition: Very Good
    Price: 2,950 EUR
    Seller: Watchbox Europe
    https://www.chrono24.com/omega/aqua-terra-23110392102001-id123456.htm
    """
    listings = adapter.parse_saved_search_email_text(email_text)
    assert len(listings) == 1
    item = listings[0]
    assert item.price == 2950.0
    assert item.currency == "EUR"
    assert item.condition == "Very Good"
    assert item.seller == "Watchbox Europe"
