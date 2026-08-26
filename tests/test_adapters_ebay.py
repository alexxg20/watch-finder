from unittest.mock import MagicMock, patch

from watch_hunter.adapters.ebay import EbayAdapter
from watch_hunter.models import SearchCriteria


def test_ebay_adapter_not_configured() -> None:
    adapter = EbayAdapter(client_id=None, client_secret=None)
    assert adapter.is_configured() is False
    assert adapter.fetch_listings(SearchCriteria()) == []


def test_ebay_adapter_search_flow() -> None:
    adapter = EbayAdapter(
        client_id="test_client_id",
        client_secret="test_client_secret",
        marketplace_id="EBAY_DE",
    )
    assert adapter.is_configured() is True

    mock_oauth_resp = MagicMock()
    mock_oauth_resp.status_code = 200
    mock_oauth_resp.json.return_value = {
        "access_token": "mocked_oauth_token_12345",
        "expires_in": 7200,
        "token_type": "Bearer",
    }

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.json.return_value = {
        "total": 1,
        "itemSummaries": [
            {
                "itemId": "v1|3948572819|0",
                "title": "Omega Seamaster Aqua Terra 150M 231.10.39.21.02.002 Full Set",
                "price": {
                    "value": "2950.00",
                    "currency": "EUR",
                },
                "condition": "Pre-Owned",
                "seller": {
                    "username": "german_watch_store",
                    "feedbackPercentage": "99.8",
                },
                "itemWebUrl": "https://www.ebay.de/itm/3948572819",
                "itemLocation": {
                    "country": "DE",
                    "city": "Munich",
                },
                "image": {
                    "imageUrl": "https://i.ebayimg.com/images/g/mock/s-l1600.jpg",
                },
            }
        ],
    }

    def fake_request(method: str, url: str, **kwargs: object) -> MagicMock:
        if "oauth2/token" in url:
            return mock_oauth_resp
        return mock_search_resp

    with patch.object(adapter, "_request_with_retry", side_effect=fake_request):
        criteria = SearchCriteria(references=["231.10.39.21.02.002"])
        listings = adapter.fetch_listings(criteria)

        assert len(listings) == 1
        item = listings[0]
        assert item.id == "ebay:v1|3948572819|0"
        assert item.price == 2950.0
        assert item.currency == "EUR"
        assert item.seller == "german_watch_store"
        assert item.location == "DE"
        assert item.source == "ebay"
        assert item.url == "https://www.ebay.de/itm/3948572819"
        assert item.image_url == "https://i.ebayimg.com/images/g/mock/s-l1600.jpg"
