from datetime import datetime, timezone

from watch_hunter.models import ConditionGrade, Listing, SearchCriteria


def test_condition_grade_parsing() -> None:
    assert ConditionGrade.from_text("Brand New in Box") == ConditionGrade.NEW
    assert ConditionGrade.from_text("Mint Condition") == ConditionGrade.MINT
    assert ConditionGrade.from_text("Excellent, barely worn") == ConditionGrade.EXCELLENT
    assert ConditionGrade.from_text("Very good condition") == ConditionGrade.VERY_GOOD
    assert ConditionGrade.from_text("Pre-owned - Good") == ConditionGrade.GOOD
    assert ConditionGrade.from_text("Fair / heavy scratches") == ConditionGrade.FAIR
    assert ConditionGrade.from_text("For parts or not working") == ConditionGrade.POOR
    assert ConditionGrade.from_text("Unknown condition string") == ConditionGrade.UNKNOWN
    assert ConditionGrade.from_text(None) == ConditionGrade.UNKNOWN


def test_condition_is_acceptable() -> None:
    assert ConditionGrade.NEW.is_acceptable(ConditionGrade.GOOD) is True
    assert ConditionGrade.EXCELLENT.is_acceptable(ConditionGrade.GOOD) is True
    assert ConditionGrade.GOOD.is_acceptable(ConditionGrade.GOOD) is True
    assert ConditionGrade.FAIR.is_acceptable(ConditionGrade.GOOD) is False
    assert ConditionGrade.POOR.is_acceptable(ConditionGrade.GOOD) is False
    assert ConditionGrade.UNKNOWN.is_acceptable(ConditionGrade.GOOD, allow_unknown=True) is True
    assert ConditionGrade.UNKNOWN.is_acceptable(ConditionGrade.GOOD, allow_unknown=False) is False


def test_listing_model_creation() -> None:
    now = datetime.now(timezone.utc)
    listing = Listing(
        id="ebay:123456",
        title="Omega Aqua Terra 150M 231.10.39.21.02.002",
        price=2950.0,
        currency="EUR",
        condition="Pre-Owned",
        condition_grade=ConditionGrade.GOOD,
        seller="watch_dealer_eu",
        source="ebay",
        url="https://ebay.de/itm/123456",
        discovered_at=now,
    )
    assert listing.id == "ebay:123456"
    assert listing.price == 2950.0
    assert listing.currency == "EUR"
    d = listing.to_digest_dict()
    assert d["id"] == "ebay:123456"
    assert d["source"] == "ebay"


def test_search_criteria_defaults() -> None:
    criteria = SearchCriteria()
    assert "231.10.39.21.02.002" in criteria.references
    assert "231.10.39.21.02.001" in criteria.references
    assert criteria.min_price_eur == 2500.0
    assert criteria.max_price_eur == 3500.0
    assert criteria.min_condition == ConditionGrade.GOOD
