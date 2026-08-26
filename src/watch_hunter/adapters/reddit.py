import base64
import html
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from watch_hunter.adapters.base import BaseAdapter
from watch_hunter.models import ConditionGrade, Listing, SearchCriteria

logger = logging.getLogger(__name__)


class RedditAdapter(BaseAdapter):
    name: str = "reddit"

    OAUTH_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    OAUTH_SEARCH_URL = "https://oauth.reddit.com/r/Watchexchange/search"
    PUBLIC_SEARCH_URL = "https://www.reddit.com/r/Watchexchange/search.json"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str = "python:watch_hunter:v0.1.0 (by /u/watch_hunter_notifier)",
        timeout: float = 15.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def is_configured(self) -> bool:
        # Works with OAuth credentials OR public rate-limited JSON API
        return True

    def _get_oauth_token(self) -> str | None:
        if not (self.client_id and self.client_secret):
            return None

        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "User-Agent": self.user_agent,
        }
        data = {"grant_type": "client_credentials"}

        logger.info("[reddit] Requesting Reddit OAuth token...")
        try:
            response = self._request_with_retry(
                "POST", self.OAUTH_TOKEN_URL, headers=headers, data=data
            )
            if response.status_code == 200:
                payload = response.json()
                token = payload.get("access_token")
                if isinstance(token, str):
                    expires_in = int(payload.get("expires_in", 3600))
                    self._access_token = token
                    self._token_expires_at = time.time() + expires_in
                    logger.info("[reddit] Successfully acquired Reddit OAuth token")
                    return self._access_token
            logger.warning(
                "[reddit] OAuth token request failed (HTTP %d). Falling back to public API",
                response.status_code,
            )
        except Exception as exc:
            logger.warning("[reddit] OAuth token exception (%s). Falling back to public API", exc)
        return None

    def _parse_price_and_currency(self, text: str) -> tuple[float | None, str]:
        clean_text = html.unescape(text)

        # Euro patterns
        m = re.search(r"€\s*([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]+)", clean_text)
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "EUR"
            except ValueError:
                pass

        m = re.search(
            r"([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]{3,5})\s*(?:€|eur|euros)\b",
            clean_text,
            re.IGNORECASE,
        )
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "EUR"
            except ValueError:
                pass

        # British Pound patterns
        m = re.search(r"£\s*([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]+)", clean_text)
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "GBP"
            except ValueError:
                pass

        m = re.search(
            r"([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]{3,5})\s*(?:£|gbp|pounds)\b",
            clean_text,
            re.IGNORECASE,
        )
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "GBP"
            except ValueError:
                pass

        # Swiss Franc patterns
        m = re.search(
            r"(?:chf|francs?)\s*([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]+)",
            clean_text,
            re.IGNORECASE,
        )
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "CHF"
            except ValueError:
                pass

        m = re.search(
            r"([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]{3,5})\s*chf\b",
            clean_text,
            re.IGNORECASE,
        )
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "CHF"
            except ValueError:
                pass

        # US Dollar patterns
        m = re.search(r"\$\s*([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]+)", clean_text)
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "USD"
            except ValueError:
                pass

        m = re.search(
            r"([0-9]{1,2}(?:[.,\s][0-9]{3})*(?:[.,][0-9]{2})?|[0-9]{3,5})\s*(?:usd|dollars|\$)\b",
            clean_text,
            re.IGNORECASE,
        )
        if m:
            num = re.sub(r"[\s,.]", "", m.group(1))
            try:
                return float(num), "USD"
            except ValueError:
                pass

        # Generic asking price pattern e.g. "Price: 3200" or "Asking 2800"
        m = re.search(
            r"(?:price|asking|selling\s+for|priced\s+at)\s*[:\-]?\s*([0-9]{4,5})",
            clean_text,
            re.IGNORECASE,
        )
        if m:
            try:
                return float(m.group(1)), "EUR"
            except ValueError:
                pass

        return None, "EUR"

    def _extract_condition(self, text: str) -> tuple[str, ConditionGrade]:
        t = text.lower()
        if any(k in t for k in ["brand new", "unworn", "bnib", "new in box"]):
            return "Brand New", ConditionGrade.NEW
        if any(k in t for k in ["mint", "like new", "near mint", "lnib"]):
            return "Mint / Like New", ConditionGrade.MINT
        if any(k in t for k in ["excellent condition", "excellent shape", "superb condition"]):
            return "Excellent", ConditionGrade.EXCELLENT
        if any(k in t for k in ["very good condition", "great condition"]):
            return "Very Good", ConditionGrade.VERY_GOOD
        if any(k in t for k in ["good condition", "minor wear", "pre-owned", "used"]):
            return "Good", ConditionGrade.GOOD
        if any(k in t for k in ["fair condition", "heavy wear", "scratched"]):
            return "Fair", ConditionGrade.FAIR
        if any(k in t for k in ["for parts", "broken", "damaged", "repair"]):
            return "Poor", ConditionGrade.POOR
        return "Unknown", ConditionGrade.UNKNOWN

    def _extract_location(self, text: str) -> str | None:
        clean_text = text.upper()
        patterns = [
            r"\[(EU|UK|CH|GERMANY|SWITZERLAND|FRANCE|ITALY|SPAIN|NL|AT|EUROPE)\]",
            r"\bLOCATION:\s*([A-Z\s]{2,15})\b",
            r"\bSHIPS\s+FROM\s+([A-Z\s]{2,15})\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, clean_text)
            if m:
                return m.group(1).strip()
        return None

    def _map_post_to_listing(self, post_data: dict[str, Any], query_ref: str) -> Listing | None:
        title = post_data.get("title", "")
        selftext = post_data.get("selftext", "")
        flair = post_data.get("link_flair_text", "") or ""
        post_id = post_data.get("id", "")
        author = post_data.get("author", "unknown_user")
        permalink = post_data.get("permalink", "")
        created_utc = post_data.get("created_utc", time.time())

        # Ignore sold listings
        combined_text = f"{title} {flair}".lower()
        if "sold" in combined_text or "[sold]" in combined_text:
            logger.debug("[reddit] Post %s is marked as SOLD. Skipping.", post_id)
            return None

        # Ignore pure WTB (Want to Buy) or WTT (Want to Trade)
        if (title.startswith("[WTB]") or title.startswith("[WTT]")) and "[WTS]" not in title:
            logger.debug("[reddit] Post %s is WTB/WTT. Skipping.", post_id)
            return None

        price, currency = self._parse_price_and_currency(f"{title} {selftext}")
        if price is None:
            logger.debug("[reddit] Post %s: could not parse price, defaulting to 0.0", post_id)
            price = 0.0

        cond_str, cond_grade = self._extract_condition(f"{title} {selftext}")
        location = self._extract_location(f"{title} {selftext}")

        # Image extraction from thumbnail or preview
        image_url = None
        thumbnail = post_data.get("thumbnail")
        if thumbnail and thumbnail.startswith("http"):
            image_url = thumbnail
        preview = post_data.get("preview", {}).get("images", [])
        if preview and isinstance(preview, list) and len(preview) > 0:
            source_img = preview[0].get("source", {}).get("url")
            if source_img:
                image_url = html.unescape(source_img)

        url = (
            f"https://reddit.com{permalink}"
            if permalink
            else f"https://reddit.com/r/Watchexchange/comments/{post_id}"
        )

        return Listing(
            id=f"reddit:{post_id}",
            title=title,
            price=price,
            currency=currency,
            condition=cond_str,
            condition_grade=cond_grade,
            seller=f"u/{author}",
            source="reddit",
            url=url,
            discovered_at=datetime.fromtimestamp(created_utc, timezone.utc),
            matched_reference=query_ref,
            location=location,
            ships_to=["Europe", "Switzerland"] if location in {"EU", "CH", "UK"} else [],
            image_url=image_url,
            description=selftext[:500] if selftext else None,
            raw_data=post_data,
        )

    def search_reference(self, reference: str) -> list[Listing]:
        token = self._get_oauth_token()
        headers = {"User-Agent": self.user_agent}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            search_url = self.OAUTH_SEARCH_URL
        else:
            search_url = self.PUBLIC_SEARCH_URL

        params = {
            "q": reference,
            "restrict_sr": "1",
            "sort": "new",
            "limit": 50,
        }

        logger.info("[reddit] Searching r/Watchexchange for '%s'...", reference)
        response = self._request_with_retry("GET", search_url, headers=headers, params=params)

        if response.status_code != 200:
            logger.error(
                "[reddit] Search failed (HTTP %d): %s", response.status_code, response.text
            )
            return []

        payload = response.json()
        children = payload.get("data", {}).get("children", [])
        logger.info(
            "[reddit] Retrieved %d candidate posts for reference '%s'", len(children), reference
        )

        listings: list[Listing] = []
        for child in children:
            post_data = child.get("data", {})
            try:
                listing = self._map_post_to_listing(post_data, reference)
                if listing:
                    listings.append(listing)
            except Exception as exc:
                logger.warning("[reddit] Failed to parse post %s: %s", post_data.get("id"), exc)

        return listings

    def fetch_listings(self, criteria: SearchCriteria) -> list[Listing]:
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
                logger.error("[reddit] Error searching reference '%s': %s", ref, exc)

        logger.info(
            "[reddit] Total %d unique listings retrieved from Reddit r/Watchexchange",
            len(all_listings),
        )
        return all_listings
