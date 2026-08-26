import logging

from watch_hunter.models import Listing, SearchCriteria
from watch_hunter.notifier.base import BaseNotifier
from watch_hunter.notifier.formatter import EmailFormatter

logger = logging.getLogger(__name__)


class ConsoleNotifier(BaseNotifier):
    def __init__(self, criteria: SearchCriteria | None = None) -> None:
        self.criteria = criteria or SearchCriteria()

    def is_configured(self) -> bool:
        return True

    def send_digest(self, listings: list[Listing], recipient: str) -> bool:
        formatted_text = EmailFormatter.format_text(listings, self.criteria)
        print(f"\n[ConsoleNotifier] Daily Digest for {recipient}:\n")
        print(formatted_text)
        return True
