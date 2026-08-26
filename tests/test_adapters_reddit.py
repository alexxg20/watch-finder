from unittest.mock import MagicMock, patch

from watch_hunter.adapters.reddit import RedditAdapter
from watch_hunter.models import ConditionGrade, SearchCriteria


def test_reddit_price_and_currency_parsing() -> None:
    adapter = RedditAdapter()

    # Euro symbols
    p, c = adapter._parse_price_and_currency("Omega Aqua Terra 231.10.39.21.02.002 €2,850 shipped")
    assert p == 2850.0
    assert c == "EUR"

    # Euro words
    p, c = adapter._parse_price_and_currency("Selling for 2900 EUR negotiable")
    assert p == 2900.0
    assert c == "EUR"

    # GBP
    p, c = adapter._parse_price_and_currency("Priced at £2,600 including shipping")
    assert p == 2600.0
    assert c == "GBP"

    # CHF
    p, c = adapter._parse_price_and_currency("Omega Aqua Terra 2800 CHF located in Zurich")
    assert p == 2800.0
    assert c == "CHF"

    # USD
    p, c = adapter._parse_price_and_currency("Asking $3,150 wire or PayPal")
    assert p == 3150.0
    assert c == "USD"


def test_reddit_adapter_search_flow() -> None:
    adapter = RedditAdapter(
        client_id="mock_reddit_client",
        client_secret="mock_reddit_secret",
    )

    mock_oauth_resp = MagicMock()
    mock_oauth_resp.status_code = 200
    mock_oauth_resp.json.return_value = {
        "access_token": "mock_reddit_access_token",
        "expires_in": 3600,
    }

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.json.return_value = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc1234",
                        "title": (
                            "[WTS] Omega Aqua Terra 150M 231.10.39.21.02.002 "
                            "- Silver Dial / Orange Hand - €2,900 [EU]"
                        ),
                        "selftext": (
                            "Up for sale is my Omega Aqua Terra reference 231.10.39.21.02.002 "
                            "in excellent condition. Asking €2900 shipped in EU/CH."
                        ),
                        "author": "swiss_collector",
                        "permalink": "/r/Watchexchange/comments/abc1234/wts_omega_aqua_terra/",
                        "created_utc": 1724659200,
                        "link_flair_text": "Selling",
                        "thumbnail": "https://b.thumbs.redditmedia.com/thumb.jpg",
                    }
                },
                {
                    # Sold post (should be filtered out)
                    "data": {
                        "id": "sold999",
                        "title": "[WTS] [SOLD] Omega Aqua Terra 231.10.39.21.02.002",
                        "selftext": "Watch is now sold thanks!",
                        "author": "seller_old",
                        "link_flair_text": "SOLD",
                    }
                },
                {
                    # WTB post (should be filtered out)
                    "data": {
                        "id": "wtb888",
                        "title": "[WTB] Looking for Omega 231.10.39.21.02.001",
                        "selftext": "Want to buy an Aqua Terra",
                        "author": "buyer_1",
                    }
                },
            ]
        }
    }

    def fake_request(method: str, url: str, **kwargs: object) -> MagicMock:
        if "access_token" in url:
            return mock_oauth_resp
        return mock_search_resp

    with patch.object(adapter, "_request_with_retry", side_effect=fake_request):
        criteria = SearchCriteria(references=["231.10.39.21.02.002"])
        listings = adapter.fetch_listings(criteria)

        assert len(listings) == 1
        item = listings[0]
        assert item.id == "reddit:abc1234"
        assert item.price == 2900.0
        assert item.currency == "EUR"
        assert item.condition_grade == ConditionGrade.EXCELLENT
        assert item.seller == "u/swiss_collector"
        assert item.source == "reddit"
        assert item.location == "EU"
        assert (
            item.url == "https://reddit.com/r/Watchexchange/comments/abc1234/wts_omega_aqua_terra/"
        )
