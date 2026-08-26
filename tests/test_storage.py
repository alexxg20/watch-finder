from datetime import datetime, timedelta, timezone
from pathlib import Path

from watch_hunter.models import ConditionGrade, Listing
from watch_hunter.storage.json_storage import JsonFileStorage


def test_storage_lifecycle(tmp_path: Path) -> None:
    state_file = tmp_path / "seen_listings.json"
    storage = JsonFileStorage(file_path=state_file)

    assert storage.get_seen_count() == 0

    l1 = Listing(
        id="ebay:1001",
        title="Omega Aqua Terra 231.10.39.21.02.002",
        price=2800.0,
        currency="EUR",
        condition="Excellent",
        condition_grade=ConditionGrade.EXCELLENT,
        seller="seller1",
        source="ebay",
        url="https://ebay.com/1001",
    )

    l2 = Listing(
        id="reddit:2002",
        title="Omega Aqua Terra 231.10.39.21.02.001",
        price=2900.0,
        currency="EUR",
        condition="Very Good",
        condition_grade=ConditionGrade.VERY_GOOD,
        seller="u/seller2",
        source="reddit",
        url="https://reddit.com/2002",
    )

    assert storage.has_seen("ebay:1001") is False
    assert len(storage.filter_unseen([l1, l2])) == 2

    # Mark l1 as seen and save
    storage.mark_seen(l1)
    storage.save()

    assert storage.has_seen("ebay:1001") is True
    assert storage.has_seen("reddit:2002") is False

    # Reload from disk in a fresh instance
    storage_reloaded = JsonFileStorage(file_path=state_file)
    assert storage_reloaded.get_seen_count() == 1
    assert storage_reloaded.has_seen("ebay:1001") is True

    # Filter unseen should now only return l2
    unseen = storage_reloaded.filter_unseen([l1, l2])
    assert len(unseen) == 1
    assert unseen[0].id == "reddit:2002"


def test_storage_pruning(tmp_path: Path) -> None:
    state_file = tmp_path / "seen_listings.json"
    storage = JsonFileStorage(file_path=state_file)

    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=100)).isoformat()
    recent_date = (now - timedelta(days=10)).isoformat()

    storage.seen_items["old:1"] = {
        "first_seen": old_date,
        "last_seen": old_date,
        "title": "Old listing",
    }
    storage.seen_items["recent:2"] = {
        "first_seen": recent_date,
        "last_seen": recent_date,
        "title": "Recent listing",
    }
    storage.save()

    pruned = storage.prune_old_entries(max_age_days=60)
    assert pruned == 1
    assert storage.has_seen("old:1") is False
    assert storage.has_seen("recent:2") is True
