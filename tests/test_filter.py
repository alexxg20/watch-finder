from watch_hunter.currency import CurrencyConverter
from watch_hunter.filter import ListingFilter
from watch_hunter.models import ConditionGrade, Listing


def create_sample_listing(
    title: str = "Omega Aqua Terra 231.10.39.21.02.002",
    price: float = 2900.0,
    currency: str = "EUR",
    condition: str = "Excellent",
    condition_grade: ConditionGrade = ConditionGrade.EXCELLENT,
    location: str = "Germany",
    description: str = "",
) -> Listing:
    return Listing(
        id="test:1",
        title=title,
        price=price,
        currency=currency,
        condition=condition,
        condition_grade=condition_grade,
        seller="seller1",
        source="ebay",
        url="https://example.com/item/1",
        location=location,
        description=description,
    )


def test_filter_matching_reference() -> None:
    converter = CurrencyConverter()
    converter._fetched = True
    f = ListingFilter(converter=converter)

    # Direct dotted match
    l1 = create_sample_listing(title="Omega Seamaster Aqua Terra 231.10.39.21.02.002 150M")
    ok, reason = f.evaluate(l1)
    assert ok is True
    assert l1.matched_reference == "231.10.39.21.02.002"

    # Second reference
    l2 = create_sample_listing(title="Omega Aqua Terra 150m 38.5mm 231.10.39.21.02.001")
    ok, _ = f.evaluate(l2)
    assert ok is True
    assert l2.matched_reference == "231.10.39.21.02.001"

    # Undotted reference in description
    l3 = create_sample_listing(
        title="Omega Aqua Terra Silver Dial 38.5mm",
        description="Reference number 23110392102002 full set",
    )
    ok, _ = f.evaluate(l3)
    assert ok is True
    assert l3.matched_reference == "231.10.39.21.02.002"

    # Unrelated reference (e.g. 220.10.38.20.02.001)
    l4 = create_sample_listing(title="Omega Seamaster Aqua Terra 220.10.38.20.02.001")
    ok, reason = f.evaluate(l4)
    assert ok is False
    assert "Reference mismatch" in reason


def test_filter_price_bounds() -> None:
    converter = CurrencyConverter()
    converter._fetched = True
    f = ListingFilter(converter=converter)

    # In range (2900 EUR)
    l1 = create_sample_listing(price=2900.0, currency="EUR")
    assert f.evaluate(l1)[0] is True

    # Too cheap (< 2500 EUR)
    l2 = create_sample_listing(price=2200.0, currency="EUR")
    ok, reason = f.evaluate(l2)
    assert ok is False
    assert "Price EUR 2200.0 outside range" in reason

    # Too expensive (> 3500 EUR)
    l3 = create_sample_listing(price=3800.0, currency="EUR")
    ok, reason = f.evaluate(l3)
    assert ok is False
    assert "Price EUR 3800.0 outside range" in reason

    # In range with GBP conversion (2550 GBP / 0.85 = 3000 EUR)
    l4 = create_sample_listing(price=2550.0, currency="GBP")
    assert f.evaluate(l4)[0] is True

    # In range with CHF conversion (2850 CHF / 0.95 = 3000 EUR)
    l5 = create_sample_listing(price=2850.0, currency="CHF", location="Switzerland")
    assert f.evaluate(l5)[0] is True


def test_filter_condition() -> None:
    converter = CurrencyConverter()
    converter._fetched = True
    f = ListingFilter(converter=converter)

    # Good condition
    l1 = create_sample_listing(condition="Good", condition_grade=ConditionGrade.GOOD)
    assert f.evaluate(l1)[0] is True

    # Very Good / Excellent
    l2 = create_sample_listing(condition="Excellent", condition_grade=ConditionGrade.EXCELLENT)
    assert f.evaluate(l2)[0] is True

    # Poor / For parts
    l3 = create_sample_listing(
        condition="For parts or not working", condition_grade=ConditionGrade.POOR
    )
    ok, reason = f.evaluate(l3)
    assert ok is False
    assert "Condition rejected" in reason

    # Fair
    l4 = create_sample_listing(condition="Fair condition", condition_grade=ConditionGrade.FAIR)
    ok, reason = f.evaluate(l4)
    assert ok is False
    assert "Condition rejected" in reason


def test_filter_location_and_shipping() -> None:
    converter = CurrencyConverter()
    converter._fetched = True
    f = ListingFilter(converter=converter)

    # Switzerland
    l_ch = create_sample_listing(location="Switzerland")
    assert f.evaluate(l_ch)[0] is True

    # Germany / UK / France
    l_de = create_sample_listing(location="DE")
    assert f.evaluate(l_de)[0] is True

    # Explicit CONUS only (should be rejected)
    l_conus = create_sample_listing(
        title="[WTS] Omega Aqua Terra 231.10.39.21.02.002 - CONUS only",
        location="US",
    )
    ok, reason = f.evaluate(l_conus)
    assert ok is False

    # US seller with Worldwide / EU shipping (should be accepted)
    l_us_ww = create_sample_listing(
        title="[WTS] Omega Aqua Terra 231.10.39.21.02.002 [Worldwide]",
        location="US",
        description="Ships to EU and worldwide via DHL Express",
    )
    ok, _ = f.evaluate(l_us_ww)
    assert ok is True
