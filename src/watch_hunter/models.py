from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConditionGrade(str, Enum):
    NEW = "new"
    MINT = "mint"
    EXCELLENT = "excellent"
    VERY_GOOD = "very_good"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"

    @classmethod
    def from_text(cls, text: str | None) -> "ConditionGrade":
        if not text:
            return cls.UNKNOWN
        t = text.lower().strip()
        if any(k in t for k in ["new with tags", "brand new", "unworn", "new in box", "bnib"]):
            return cls.NEW
        if any(k in t for k in ["mint", "like new", "near mint"]):
            return cls.MINT
        if any(k in t for k in ["excellent", "superb"]):
            return cls.EXCELLENT
        if any(k in t for k in ["very good", "great condition"]):
            return cls.VERY_GOOD
        if any(k in t for k in ["good", "used - good", "pre-owned"]):
            return cls.GOOD
        if any(k in t for k in ["fair", "moderate wear"]):
            return cls.FAIR
        if any(k in t for k in ["poor", "for parts", "not working", "broken", "damaged"]):
            return cls.POOR
        return cls.UNKNOWN

    def is_acceptable(
        self, minimum_grade: "ConditionGrade | None" = None, allow_unknown: bool = True
    ) -> bool:
        if self == self.UNKNOWN:
            return allow_unknown
        hierarchy = {
            self.POOR: 0,
            self.FAIR: 1,
            self.GOOD: 3,
            self.VERY_GOOD: 4,
            self.EXCELLENT: 5,
            self.MINT: 6,
            self.NEW: 7,
        }
        target_grade = minimum_grade or self.GOOD
        min_val = hierarchy.get(target_grade, 3)
        cur_val = hierarchy.get(self, 0)
        return cur_val >= min_val


class Listing(BaseModel):
    id: str = Field(..., description="Unique ID within the source adapter")
    title: str = Field(..., description="Listing title")
    price: float = Field(..., description="Listing price in original currency")
    currency: str = Field(..., description="ISO currency code (e.g., EUR, GBP, CHF, USD)")
    condition: str = Field(..., description="Normalized or raw condition string")
    condition_grade: ConditionGrade = Field(default=ConditionGrade.UNKNOWN)
    seller: str = Field(..., description="Seller username or name")
    source: str = Field(..., description="Source name (ebay, reddit, chrono24)")
    url: str = Field(..., description="URL to listing")
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when listing was discovered",
    )
    price_eur: float | None = Field(default=None, description="Calculated price in EUR")
    matched_reference: str | None = Field(default=None, description="Matched watch reference")
    location: str | None = Field(default=None, description="Item location or seller country")
    ships_to: list[str] = Field(
        default_factory=list, description="Shipping destination countries/regions"
    )
    image_url: str | None = Field(default=None, description="Thumbnail or main photo URL")
    description: str | None = Field(default=None, description="Listing summary or body text")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw source payload")

    def to_digest_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "price": self.price,
            "currency": self.currency,
            "price_eur": self.price_eur,
            "condition": self.condition,
            "condition_grade": self.condition_grade.value,
            "seller": self.seller,
            "source": self.source,
            "url": self.url,
            "discovered_at": self.discovered_at.isoformat(),
            "matched_reference": self.matched_reference,
            "location": self.location,
            "image_url": self.image_url,
        }


class SearchCriteria(BaseModel):
    references: list[str] = Field(
        default=["231.10.39.21.02.002", "231.10.39.21.02.001"],
        description="Target watch reference numbers",
    )
    min_price_eur: float = Field(default=2500.0, description="Minimum price in EUR")
    max_price_eur: float = Field(default=3500.0, description="Maximum price in EUR")
    min_condition: ConditionGrade = Field(default=ConditionGrade.GOOD)
    allow_unknown_condition: bool = Field(default=True)
    allowed_countries: list[str] = Field(
        default=[
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
            "EU",
            "EUROPE",
            "WORLDWIDE",
            "GLOBAL",
        ]
    )
