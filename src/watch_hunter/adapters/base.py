import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from watch_hunter.models import Listing, SearchCriteria

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    name: str = "base"

    def __init__(self, timeout: float = 15.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_resilient_session()

    def _create_resilient_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 * attempt))
                    logger.warning(
                        "[%s] Rate limited (429). Backing off for %ds (attempt %d/%d)",
                        self.name,
                        retry_after,
                        attempt,
                        self.max_retries,
                    )
                    time.sleep(retry_after)
                    continue
                return response
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    logger.error(
                        "[%s] Request failed after %d attempts: %s", self.name, attempt, exc
                    )
                    raise
                wait_time = 2**attempt
                logger.warning(
                    "[%s] Request error (%s). Retrying in %ds...", self.name, exc, wait_time
                )
                time.sleep(wait_time)
        raise RuntimeError(f"[{self.name}] Failed request to {url}")

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required credentials/configuration are present."""
        ...

    @abstractmethod
    def fetch_listings(self, criteria: SearchCriteria) -> list[Listing]:
        """Fetch matching listings from the source."""
        ...
