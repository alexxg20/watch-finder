import base64
import logging
import time
from datetime import datetime, timezone
from typing import Any

from watch_hunter.adapters.base import BaseAdapter
from watch_hunter.models import ConditionGrade, Listing, SearchCriteria

logger = logging.getLogger(__name__)


class EbayAdapter(BaseAdapter):
    name: str = "ebay"

    OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    # Default European marketplaces to query for optimal regional coverage
    DEFAULT_MARKETPLACES = ["EBAY_DE", "EBAY_GB", "EBAY_IT", "EBAY_FR", "EBAY_ES"]

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        marketplace_id: str = "EBAY_DE",
        timeout: float = 15.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.client_id = client_id
        self.client_secret = client_secret
        self.marketplace_id = marketplace_id
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token

        if not self.client_id or not self.client_secret:
            raise ValueError("eBay client_id and client_secret must be configured.")

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        }

        logger.info("[ebay] Requesting OAuth client credentials token...")
        response = self._request_with_retry("POST", self.OAUTH_URL, headers=headers, data=data)
        if response.status_code != 200:
            logger.error(
                "[ebay] OAuth token request failed (HTTP %d): %s",
                response.status_code,
                response.text,
            )
            response.raise_for_status()

        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str):
            raise ValueError("Invalid OAuth response: access_token missing or not a string")
        expires_in = int(payload.get("expires_in", 7200))
        self._access_token = token
        self._token_expires_at = time.time() + expires_in
        logger.info("[ebay] Successfully acquired access token (valid for %ds)", expires_in)
        return self._access_token

    def _map_item_to_listing(self, item: dict[str, Any], query_ref: str) -> Listing:
        item_id = str(item.get("itemId", ""))
        title = item.get("title", "")
        price_data = item.get("price", {})
        price_val = float(price_data.get("value", 0.0))
        currency = price_data.get("currency", "EUR")

        condition_str = item.get("condition", "Pre-Owned")
        condition_grade = ConditionGrade.from_text(condition_str)

        seller_info = item.get("seller", {})
        seller_name = seller_info.get("username", "Unknown seller")

        url = item.get("itemWebUrl", f"https://www.ebay.com/itm/{item_id}")

        location_info = item.get("itemLocation", {})
        location_country = location_info.get("country", "")

        ships_to: list[str] = []
        for opt in item.get("shippingOptions", []):
            ships_to.extend(opt.get("shipToLocations", {}).get("regionIncluded", []))

        image_data = item.get("image", {})
        image_url = image_data.get("imageUrl")
        if not image_url and item.get("thumbnailImages"):
            image_url = item["thumbnailImages"][0].get("imageUrl")

        return Listing(
            id=f"ebay:{item_id}",
            title=title,
            price=price_val,
            currency=currency,
            condition=condition_str,
            condition_grade=condition_grade,
            seller=seller_name,
            source="ebay",
            url=url,
            discovered_at=datetime.now(timezone.utc),
            matched_reference=query_ref,
            location=location_country or None,
            ships_to=ships_to,
            image_url=image_url,
            description=item.get("shortDescription"),
            raw_data=item,
        )

    def search_reference(self, reference: str) -> list[Listing]:
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Search queries: exact reference
        query = f"Omega {reference}"
        params: dict[str, Any] = {
            "q": query,
            "limit": 50,
        }

        logger.info(
            "[ebay] Searching reference '%s' on marketplace %s...", reference, self.marketplace_id
        )
        response = self._request_with_retry(
            "GET", self.BROWSE_SEARCH_URL, headers=headers, params=params
        )

        if response.status_code != 200:
            logger.error(
                "[ebay] Browse search error (HTTP %d): %s", response.status_code, response.text
            )
            return []

        data = response.json()
        item_summaries = data.get("itemSummaries", [])
        logger.info("[ebay] Retrieved %d raw items for query '%s'", len(item_summaries), query)

        listings: list[Listing] = []
        for item in item_summaries:
            try:
                listing = self._map_item_to_listing(item, reference)
                listings.append(listing)
            except Exception as exc:
                logger.warning(
                    "[ebay] Failed to parse item summary %s: %s", item.get("itemId"), exc
                )

        return listings

    def fetch_listings(self, criteria: SearchCriteria) -> list[Listing]:
        if not self.is_configured():
            logger.warning(
                "[ebay] eBay adapter missing credentials (EBAY_CLIENT_ID / SECRET). Skipping."
            )
            return []

        all_listings: list[Listing] = []
        seen_ids: set[str] = set()

        for ref in criteria.references:
            try:
                listings = self.search_reference(ref)
                for listing in listings:
                    if listing.id not in seen_ids:
                        seen_ids.add(listing.id)
                        all_listings.append(listing)
            except Exception as exc:
                logger.error("[ebay] Error searching for reference '%s': %s", ref, exc)

        logger.info("[ebay] Total %d unique listings retrieved from eBay", len(all_listings))
        return all_listings
