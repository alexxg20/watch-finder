import logging
from dataclasses import dataclass, field
from typing import Any

from watch_hunter.adapters.base import BaseAdapter
from watch_hunter.adapters.chrono24 import Chrono24AdapterStub
from watch_hunter.adapters.ebay import EbayAdapter
from watch_hunter.adapters.reddit import RedditAdapter
from watch_hunter.config import Settings
from watch_hunter.currency import CurrencyConverter
from watch_hunter.filter import ListingFilter
from watch_hunter.models import Listing, SearchCriteria
from watch_hunter.notifier.base import BaseNotifier
from watch_hunter.notifier.console import ConsoleNotifier
from watch_hunter.notifier.email_resend import ResendNotifier
from watch_hunter.notifier.email_smtp import SmtpNotifier
from watch_hunter.storage.base import BaseStorage
from watch_hunter.storage.json_storage import JsonFileStorage

logger = logging.getLogger(__name__)


@dataclass
class HunterRunResult:
    total_fetched: int = 0
    total_matched: int = 0
    new_unseen: int = 0
    notified: bool = False
    listings_notified: list[Listing] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "total_fetched": self.total_fetched,
            "total_matched": self.total_matched,
            "new_unseen": self.new_unseen,
            "notified": self.notified,
            "notified_count": len(self.listings_notified),
            "errors_count": len(self.errors),
        }


class WatchHunterRunner:
    def __init__(
        self,
        settings: Settings | None = None,
        storage: BaseStorage | None = None,
        criteria: SearchCriteria | None = None,
        adapters: list[BaseAdapter] | None = None,
        notifiers: list[BaseNotifier] | None = None,
        converter: CurrencyConverter | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.criteria = criteria or self.settings.build_search_criteria()
        self.storage = storage or JsonFileStorage(file_path=self.settings.state_file_path)
        self.converter = converter or CurrencyConverter()
        self.filter_engine = ListingFilter(criteria=self.criteria, converter=self.converter)

        # Initialize default adapters if none injected
        if adapters is not None:
            self.adapters = adapters
        else:
            self.adapters = [
                EbayAdapter(
                    client_id=self.settings.ebay_client_id,
                    client_secret=self.settings.ebay_client_secret,
                    marketplace_id=self.settings.ebay_marketplace_id,
                ),
                RedditAdapter(
                    client_id=self.settings.reddit_client_id,
                    client_secret=self.settings.reddit_client_secret,
                    user_agent=self.settings.reddit_user_agent,
                ),
                Chrono24AdapterStub(),
            ]

        # Initialize default notifiers if none injected
        if notifiers is not None:
            self.notifiers = notifiers
        else:
            self.notifiers = self._build_notifiers()

    def _build_notifiers(self) -> list[BaseNotifier]:
        notifiers: list[BaseNotifier] = []

        # Resend email
        if self.settings.resend_api_key:
            notifiers.append(
                ResendNotifier(
                    api_key=self.settings.resend_api_key,
                    from_email=self.settings.resend_from_email,
                    criteria=self.criteria,
                )
            )

        # SMTP email
        if self.settings.smtp_host:
            notifiers.append(
                SmtpNotifier(
                    host=self.settings.smtp_host,
                    port=self.settings.smtp_port,
                    user=self.settings.smtp_user,
                    password=self.settings.smtp_password,
                    from_email=self.settings.smtp_from,
                    use_tls=self.settings.smtp_use_tls,
                    use_ssl=self.settings.smtp_use_ssl,
                    criteria=self.criteria,
                )
            )

        # Always add console notifier for dry run or fallback
        if not notifiers or self.settings.dry_run:
            notifiers.append(ConsoleNotifier(criteria=self.criteria))

        return notifiers

    def run(self, dry_run: bool | None = None) -> HunterRunResult:
        is_dry_run = self.settings.dry_run if dry_run is None else dry_run
        result = HunterRunResult()

        logger.info("=== Starting Watch Hunter Run ===")
        logger.info("Target References: %s", ", ".join(self.criteria.references))
        logger.info(
            "Price Target: €%.0f - €%.0f EUR",
            self.criteria.min_price_eur,
            self.criteria.max_price_eur,
        )
        logger.info("Recipient: %s", self.settings.notification_email)
        logger.info("Dry Run Mode: %s", is_dry_run)

        # 1. Fetch listings from all enabled adapters
        all_raw_listings: list[Listing] = []
        for adapter in self.adapters:
            logger.info("Fetching listings from adapter '%s'...", adapter.name)
            try:
                listings = adapter.fetch_listings(self.criteria)
                logger.info("Adapter '%s' returned %d listings", adapter.name, len(listings))
                all_raw_listings.extend(listings)
            except Exception as exc:
                err_msg = f"Adapter '{adapter.name}' failed: {exc}"
                logger.error(err_msg, exc_info=True)
                result.errors.append(err_msg)

        result.total_fetched = len(all_raw_listings)

        # 2. Filter listings by reference, condition, price range, and Europe shipping
        logger.info("Filtering %d raw listings...", len(all_raw_listings))
        matched_listings = self.filter_engine.filter_listings(all_raw_listings)
        result.total_matched = len(matched_listings)
        logger.info(
            "Filtered matching listings: %d / %d", len(matched_listings), len(all_raw_listings)
        )

        # 3. Deduplicate against persistent storage
        new_unseen_listings = self.storage.filter_unseen(matched_listings)
        result.new_unseen = len(new_unseen_listings)
        logger.info("New unseen listings to notify: %d", len(new_unseen_listings))

        # 4. Notify if there are new listings
        if new_unseen_listings:
            result.listings_notified = new_unseen_listings
            if is_dry_run:
                logger.info(
                    "[Dry Run] Would notify %d listings to %s",
                    len(new_unseen_listings),
                    self.settings.notification_email,
                )
                console = ConsoleNotifier(criteria=self.criteria)
                console.send_digest(new_unseen_listings, self.settings.notification_email)
                result.notified = True
            else:
                notification_success = False
                for notifier in self.notifiers:
                    if notifier.is_configured():
                        try:
                            sent = notifier.send_digest(
                                new_unseen_listings, self.settings.notification_email
                            )
                            if sent:
                                notification_success = True
                        except Exception as exc:
                            err_msg = f"Notifier failed: {exc}"
                            logger.error(err_msg, exc_info=True)
                            result.errors.append(err_msg)

                result.notified = notification_success

                # 5. Mark as seen in storage and save
                for item in new_unseen_listings:
                    self.storage.mark_seen(item)
                self.storage.save()
                logger.info(
                    "Persistent storage updated. Total tracked: %d", self.storage.get_seen_count()
                )
        else:
            logger.info("No new matching listings found today.")

        logger.info("=== Watch Hunter Run Completed ===")
        return result
