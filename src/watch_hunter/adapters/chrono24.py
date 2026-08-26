import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from watch_hunter.adapters.base import BaseAdapter
from watch_hunter.models import ConditionGrade, Listing, SearchCriteria

logger = logging.getLogger(__name__)


class Chrono24AdapterStub(BaseAdapter):
    """
    Isolated adapter stub and saved-search importer for Chrono24.

    Compliance Notice:
    Chrono24 does not provide an open public search API without an enterprise commercial agreement.
    Direct web scraping of Chrono24 is strictly disallowed under their Terms of Service.
    This adapter functions as an isolated stub and provides an import pipeline for user-forwarded
    Chrono24 saved-search email notifications or JSON alert exports.
    """

    name: str = "chrono24"

    def __init__(
        self, import_dir: str | Path = "data/chrono24_imports", timeout: float = 15.0
    ) -> None:
        super().__init__(timeout=timeout)
        self.import_dir = Path(import_dir)

    def is_configured(self) -> bool:
        return self.import_dir.exists() and any(self.import_dir.glob("*.json"))

    def fetch_listings(self, criteria: SearchCriteria) -> list[Listing]:
        if not self.is_configured():
            logger.info(
                "[chrono24] Chrono24 direct scraping is disabled per Terms of Service. "
                "To ingest listings, place saved-search JSON exports into '%s'.",
                self.import_dir,
            )
            return []

        listings: list[Listing] = []
        for file_path in self.import_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    items = data if isinstance(data, list) else data.get("listings", [])
                    for item in items:
                        listing = self._parse_json_item(item)
                        if listing:
                            listings.append(listing)
            except Exception as exc:
                logger.error("[chrono24] Failed to read import file %s: %s", file_path, exc)

        logger.info("[chrono24] Ingested %d listings from saved search imports", len(listings))
        return listings

    def _parse_json_item(self, item: dict[str, Any]) -> Listing | None:
        item_id = str(item.get("id") or item.get("article_id") or item.get("url", ""))
        title = item.get("title", "Omega Seamaster Aqua Terra")
        price = float(item.get("price", 0.0))
        currency = str(item.get("currency", "EUR")).upper()
        condition_str = item.get("condition", "Good")
        condition_grade = ConditionGrade.from_text(condition_str)
        seller = item.get("seller", "Chrono24 Dealer/Private")
        url = item.get("url", f"https://www.chrono24.com/omega/{item_id}.htm")
        location = item.get("country") or item.get("location")

        return Listing(
            id=f"chrono24:{item_id}",
            title=title,
            price=price,
            currency=currency,
            condition=condition_str,
            condition_grade=condition_grade,
            seller=seller,
            source="chrono24",
            url=url,
            discovered_at=datetime.now(timezone.utc),
            location=location,
            ships_to=[location] if location else ["Europe"],
            image_url=item.get("image_url"),
            description=item.get("description"),
            raw_data=item,
        )

    def parse_saved_search_email_text(self, email_body: str) -> list[Listing]:
        """
        Helper to parse forwarded Chrono24 'New search results' email alert plaintext.
        """
        listings: list[Listing] = []
        pattern = re.compile(
            r"Omega\s+(?:Seamaster\s+)?Aqua\s+Terra[^\n]*\s+"
            r"(?:Condition:\s*([^\n]+)\s+)?"
            r"Price:\s*([0-9.,]+)\s*([A-Z]{3}|€|\$|£|CHF)\s+"
            r"(?:Seller:\s*([^\n]+)\s+)?"
            r"(https://www\.chrono24\.[a-z]+/omega/[^\s]+)",
            re.IGNORECASE,
        )

        for match in pattern.finditer(email_body):
            cond_str = (match.group(1) or "Good").strip()
            price_str = match.group(2).replace(",", "").replace(".", "")
            curr_sym = match.group(3).strip()
            curr = "EUR"
            if "CHF" in curr_sym.upper():
                curr = "CHF"
            elif "£" in curr_sym or "GBP" in curr_sym.upper():
                curr = "GBP"
            elif "$" in curr_sym or "USD" in curr_sym.upper():
                curr = "USD"

            seller = (match.group(4) or "Chrono24 Seller").strip()
            url = match.group(5).strip()

            try:
                price = float(price_str)
                listing = Listing(
                    id=f"chrono24:email_{abs(hash(url))}",
                    title="Omega Seamaster Aqua Terra",
                    price=price,
                    currency=curr,
                    condition=cond_str,
                    condition_grade=ConditionGrade.from_text(cond_str),
                    seller=seller,
                    source="chrono24",
                    url=url,
                    discovered_at=datetime.now(timezone.utc),
                )
                listings.append(listing)
            except ValueError:
                continue

        return listings
