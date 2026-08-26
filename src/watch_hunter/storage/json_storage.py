import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from watch_hunter.models import Listing
from watch_hunter.storage.base import BaseStorage

logger = logging.getLogger(__name__)


class JsonFileStorage(BaseStorage):
    def __init__(self, file_path: str | Path = "data/seen_listings.json") -> None:
        self.file_path = Path(file_path)
        self.seen_items: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        if not self.file_path.exists():
            logger.info(
                "Storage file %s does not exist yet. Initializing empty state", self.file_path
            )
            self.seen_items = {}
            return

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
                self.seen_items = data.get("seen_items", {})
            logger.info(
                "Loaded %d previously seen listings from %s", len(self.seen_items), self.file_path
            )
        except Exception as exc:
            logger.error(
                "Failed to load state from %s: %s. Starting with empty state", self.file_path, exc
            )
            self.seen_items = {}

    def save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_seen": len(self.seen_items),
            "seen_items": self.seen_items,
        }

        # Atomic write using temporary file in the same directory
        temp_dir = self.file_path.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(payload, tf, indent=2)
            temp_name = tf.name

        os.replace(temp_name, self.file_path)
        logger.info("Saved %d seen listings to %s", len(self.seen_items), self.file_path)

    def has_seen(self, item_id: str) -> bool:
        return item_id in self.seen_items

    def mark_seen(self, listing: Listing) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        if listing.id in self.seen_items:
            self.seen_items[listing.id]["last_seen"] = now_str
        else:
            self.seen_items[listing.id] = {
                "first_seen": now_str,
                "last_seen": now_str,
                "title": listing.title,
                "price": listing.price,
                "currency": listing.currency,
                "price_eur": listing.price_eur,
                "source": listing.source,
                "url": listing.url,
                "seller": listing.seller,
                "condition": listing.condition,
                "matched_reference": listing.matched_reference,
            }

    def filter_unseen(self, listings: list[Listing]) -> list[Listing]:
        unseen: list[Listing] = []
        for listing in listings:
            if not self.has_seen(listing.id):
                unseen.append(listing)
            else:
                logger.debug("Listing %s already seen, skipping", listing.id)
        return unseen

    def get_seen_count(self) -> int:
        return len(self.seen_items)

    def get_all_seen(self) -> dict[str, dict[str, Any]]:
        return dict(self.seen_items)

    def prune_old_entries(self, max_age_days: int = 90) -> int:
        now = datetime.now(timezone.utc)
        to_delete: list[str] = []
        for item_id, item_data in self.seen_items.items():
            last_seen_str = item_data.get("last_seen") or item_data.get("first_seen")
            if last_seen_str:
                try:
                    dt = datetime.fromisoformat(last_seen_str)
                    if (now - dt).days > max_age_days:
                        to_delete.append(item_id)
                except ValueError:
                    pass

        for item_id in to_delete:
            del self.seen_items[item_id]

        if to_delete:
            logger.info(
                "Pruned %d expired entries older than %d days", len(to_delete), max_age_days
            )
            self.save()
        return len(to_delete)
