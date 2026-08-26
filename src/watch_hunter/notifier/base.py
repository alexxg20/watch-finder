from abc import ABC, abstractmethod

from watch_hunter.models import Listing


class BaseNotifier(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if notification channel credentials are present."""
        ...

    @abstractmethod
    def send_digest(self, listings: list[Listing], recipient: str) -> bool:
        """Send daily digest of new listings to recipient."""
        ...
