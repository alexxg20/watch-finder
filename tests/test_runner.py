from pathlib import Path

from watch_hunter.adapters.base import BaseAdapter
from watch_hunter.config import Settings
from watch_hunter.currency import CurrencyConverter
from watch_hunter.models import ConditionGrade, Listing, SearchCriteria
from watch_hunter.notifier.base import BaseNotifier
from watch_hunter.runner import WatchHunterRunner
from watch_hunter.storage.json_storage import JsonFileStorage


class MockAdapter(BaseAdapter):
    name = "mock_adapter"

    def __init__(self, listings: list[Listing]) -> None:
        super().__init__()
        self._listings = listings

    def is_configured(self) -> bool:
        return True

    def fetch_listings(self, criteria: SearchCriteria) -> list[Listing]:
        return self._listings


class MockNotifier(BaseNotifier):
    def __init__(self) -> None:
        self.sent_digests: list[tuple[list[Listing], str]] = []

    def is_configured(self) -> bool:
        return True

    def send_digest(self, listings: list[Listing], recipient: str) -> bool:
        self.sent_digests.append((listings, recipient))
        return True


def test_runner_full_cycle(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    storage = JsonFileStorage(file_path=state_file)

    converter = CurrencyConverter()
    converter._fetched = True

    matching_listing_1 = Listing(
        id="ebay:111",
        title="Omega Aqua Terra 150M 231.10.39.21.02.002",
        price=2800.0,
        currency="EUR",
        condition="Excellent",
        condition_grade=ConditionGrade.EXCELLENT,
        seller="seller_de",
        source="ebay",
        url="https://ebay.de/111",
        location="DE",
    )

    matching_listing_2 = Listing(
        id="reddit:222",
        title="Omega Aqua Terra 231.10.39.21.02.001 - £2,500 [UK]",
        price=2500.0,
        currency="GBP",
        condition="Very Good",
        condition_grade=ConditionGrade.VERY_GOOD,
        seller="u/seller_uk",
        source="reddit",
        url="https://reddit.com/222",
        location="UK",
    )

    non_matching_expensive = Listing(
        id="ebay:333",
        title="Omega Aqua Terra 231.10.39.21.02.002",
        price=4500.0,  # > 3500 EUR
        currency="EUR",
        condition="New",
        seller="expensive_seller",
        source="ebay",
        url="https://ebay.de/333",
        location="DE",
    )

    adapter = MockAdapter([matching_listing_1, matching_listing_2, non_matching_expensive])
    notifier = MockNotifier()

    settings = Settings(
        notification_email="2alex.garcia2@gmail.com",
        state_file_path=str(state_file),
    )

    runner = WatchHunterRunner(
        settings=settings,
        storage=storage,
        adapters=[adapter],
        notifiers=[notifier],
        converter=converter,
    )

    # 1. First run: should find and notify 2 listings
    result1 = runner.run(dry_run=False)
    assert result1.total_fetched == 3
    assert result1.total_matched == 2
    assert result1.new_unseen == 2
    assert result1.notified is True
    assert len(notifier.sent_digests) == 1
    assert len(notifier.sent_digests[0][0]) == 2
    assert notifier.sent_digests[0][1] == "2alex.garcia2@gmail.com"

    # State file should now have 2 items
    assert storage.get_seen_count() == 2
    assert storage.has_seen("ebay:111") is True
    assert storage.has_seen("reddit:222") is True

    # 2. Second run: same listings fetched, should deduplicate and NOT send another notification
    result2 = runner.run(dry_run=False)
    assert result2.total_fetched == 3
    assert result2.total_matched == 2
    assert result2.new_unseen == 0
    assert result2.notified is False
    assert len(notifier.sent_digests) == 1  # No new digest sent


def test_runner_dry_run_does_not_mutate_state(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    storage = JsonFileStorage(file_path=state_file)

    converter = CurrencyConverter()
    converter._fetched = True

    matching_listing = Listing(
        id="ebay:999",
        title="Omega Aqua Terra 150M 231.10.39.21.02.002",
        price=3000.0,
        currency="EUR",
        condition="Good",
        condition_grade=ConditionGrade.GOOD,
        seller="seller_ch",
        source="ebay",
        url="https://ebay.ch/999",
        location="CH",
    )

    adapter = MockAdapter([matching_listing])
    notifier = MockNotifier()

    settings = Settings(
        notification_email="2alex.garcia2@gmail.com",
        state_file_path=str(state_file),
        dry_run=True,
    )

    runner = WatchHunterRunner(
        settings=settings,
        storage=storage,
        adapters=[adapter],
        notifiers=[notifier],
        converter=converter,
    )

    result = runner.run(dry_run=True)
    assert result.new_unseen == 1
    # State should NOT be updated in dry-run mode
    assert storage.has_seen("ebay:999") is False
    assert storage.get_seen_count() == 0
