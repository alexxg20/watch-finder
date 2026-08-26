import logging
import re
from typing import ClassVar

from watch_hunter.currency import CurrencyConverter
from watch_hunter.models import ConditionGrade, Listing, SearchCriteria

logger = logging.getLogger(__name__)


class ListingFilter:
    EUROPEAN_COUNTRY_CODES: ClassVar[set[str]] = {
        "CH",
        "DE",
        "FR",
        "IT",
        "ES",
        "GB",
        "UK",
        "NL",
        "BE",
        "AT",
        "SE",
        "DK",
        "FI",
        "IE",
        "PT",
        "PL",
        "CZ",
        "NO",
        "LU",
        "GR",
        "RO",
        "HU",
        "BG",
        "HR",
        "SK",
        "SI",
        "LT",
        "LV",
        "EE",
        "CY",
        "MT",
        "IS",
        "LI",
        "MC",
        "SM",
        "AD",
        "VA",
    }

    EUROPEAN_KEYWORDS: ClassVar[set[str]] = {
        "europe",
        "european",
        "eu",
        "eea",
        "uk",
        "britain",
        "england",
        "scotland",
        "switzerland",
        "swiss",
        "schweiz",
        "suisse",
        "svizzera",
        "germany",
        "deutschland",
        "france",
        "italy",
        "italia",
        "spain",
        "españa",
        "netherlands",
        "holland",
        "austria",
        "österreich",
        "belgium",
        "sweden",
        "sverige",
        "denmark",
        "norway",
        "finland",
        "poland",
        "polska",
        "ireland",
        "portugal",
        "czech",
        "worldwide",
        "international",
        "global",
        "ww",
    }

    NON_EUROPE_RESTRICTIONS: ClassVar[list[str]] = [
        r"\bconus\s+only\b",
        r"\bus\s+only\b",
        r"\busa\s+only\b",
        r"\bcanada\s+only\b",
        r"\bships?\s+to\s+us\s+only\b",
        r"\bno\s+international\b",
        r"\bdomestic\s+only\b",
        r"\bconus\b(?!\s*(?:or|and|/)\s*(?:eu|europe|worldwide|international|ww))",
    ]

    def __init__(
        self, criteria: SearchCriteria | None = None, converter: CurrencyConverter | None = None
    ) -> None:
        self.criteria = criteria or SearchCriteria()
        self.converter = converter or CurrencyConverter()

    def normalize_reference(self, text: str) -> str:
        return re.sub(r"[\s.\-_]", "", text.lower())

    def match_reference(self, listing: Listing) -> tuple[bool, str | None]:
        search_corpus = (
            f"{listing.title} {listing.description or ''} {listing.matched_reference or ''}"
        )
        corpus_clean = self.normalize_reference(search_corpus)

        for ref in self.criteria.references:
            ref_clean = self.normalize_reference(ref)
            if ref_clean in corpus_clean:
                return True, ref
            # Dotted regex match on original corpus
            pattern = re.escape(ref).replace(r"\.", r"[\s.\-_]?")
            if re.search(pattern, search_corpus, re.IGNORECASE):
                return True, ref

        return False, None

    def match_condition(self, listing: Listing) -> bool:
        grade = listing.condition_grade
        if grade == ConditionGrade.UNKNOWN and listing.condition:
            grade = ConditionGrade.from_text(listing.condition)
            listing.condition_grade = grade

        return grade.is_acceptable(
            minimum_grade=self.criteria.min_condition,
            allow_unknown=self.criteria.allow_unknown_condition,
        )

    def match_price(self, listing: Listing) -> tuple[bool, float]:
        price_eur = self.converter.to_eur(listing.price, listing.currency)
        listing.price_eur = price_eur

        matches = self.criteria.min_price_eur <= price_eur <= self.criteria.max_price_eur
        return matches, price_eur

    def match_location_and_shipping(self, listing: Listing) -> bool:
        text_to_check = (
            f"{listing.title} {listing.description or ''} {listing.location or ''}".lower()
        )

        # Reject explicitly restricted non-Europe shipping
        for pattern in self.NON_EUROPE_RESTRICTIONS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                # Check if it also mentions EU/worldwide override
                if not any(
                    k in text_to_check
                    for k in ["ships to eu", "ships worldwide", "ww shipping", "eu shipping"]
                ):
                    logger.debug(
                        "Listing %s rejected: restricted non-Europe shipping pattern '%s'",
                        listing.id,
                        pattern,
                    )
                    return False

        # Check item location if present
        if listing.location:
            loc_upper = listing.location.upper().strip()
            if loc_upper in self.EUROPEAN_COUNTRY_CODES:
                return True
            loc_lower = listing.location.lower()
            if any(k in loc_lower for k in self.EUROPEAN_KEYWORDS):
                return True

        # Check ships_to list
        if listing.ships_to:
            for country in listing.ships_to:
                c_up = country.upper().strip()
                if c_up in self.EUROPEAN_COUNTRY_CODES:
                    return True
                c_low = country.lower()
                if any(k in c_low for k in self.EUROPEAN_KEYWORDS):
                    return True

        # Check keywords in title/body
        if any(k in text_to_check for k in self.EUROPEAN_KEYWORDS):
            return True

        # If location is explicitly non-European and no worldwide shipping is indicated
        non_eu_codes = {"US", "USA", "CA", "AU", "JP", "CN", "SG", "HK", "IN"}
        if listing.location and listing.location.upper().strip() in non_eu_codes:
            if not any(
                k in text_to_check for k in ["worldwide", "international", "ww", "ships to eu"]
            ):
                logger.debug(
                    "Listing %s rejected: non-EU location %s with no EU shipping",
                    listing.id,
                    listing.location,
                )
                return False

        # If no restrictive indicators are found, allow
        return True

    def evaluate(self, listing: Listing) -> tuple[bool, str]:
        ref_match, matched_ref = self.match_reference(listing)
        if not ref_match:
            return False, "Reference mismatch"
        listing.matched_reference = matched_ref

        if not self.match_condition(listing):
            return False, f"Condition rejected: {listing.condition_grade.value}"

        price_match, price_eur = self.match_price(listing)
        if not price_match:
            min_p = self.criteria.min_price_eur
            max_p = self.criteria.max_price_eur
            return False, f"Price EUR {price_eur} outside range [{min_p}, {max_p}]"

        if not self.match_location_and_shipping(listing):
            return False, "Location / shipping not available to Europe / Switzerland"

        return True, "Accepted"

    def filter_listings(self, listings: list[Listing]) -> list[Listing]:
        accepted: list[Listing] = []
        for listing in listings:
            ok, reason = self.evaluate(listing)
            if ok:
                logger.info(
                    "Accepted listing: %s [%s] €%.2f (%s)",
                    listing.title,
                    listing.source,
                    listing.price_eur or 0.0,
                    listing.url,
                )
                accepted.append(listing)
            else:
                logger.debug("Filtered out listing %s: %s", listing.id, reason)
        return accepted
