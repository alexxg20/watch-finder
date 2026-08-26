from abc import ABC, abstractmethod
from typing import Any

from watch_hunter.models import Listing


class BaseStorage(ABC):
    @abstractmethod
    def has_seen(self, item_id: str) -> bool:
        """Check if an item ID has already been notified."""
        ...

    @abstractmethod
    def mark_seen(self, listing: Listing) -> None:
        """Record that a listing has been notified."""
        ...

    @abstractmethod
    def filter_unseen(self, listings: list[Listing]) -> list[Listing]:
        """Filter out listings that have already been notified."""
        ...

    @abstractmethod
    def save(self) -> None:
        """Persist storage state to disk or backend."""
        ...

    @abstractmethod
    def load(self) -> None:
        """Load storage state from disk or backend."""
        ...

    @abstractmethod
    def get_seen_count(self) -> int:
        """Return total number of tracked seen listings."""
        ...

    @abstractmethod
    def get_all_seen(self) -> dict[str, dict[str, Any]]:
        """Return dictionary of all seen listing records."""
        ...
