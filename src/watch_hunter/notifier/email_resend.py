import logging

import requests

from watch_hunter.models import Listing, SearchCriteria
from watch_hunter.notifier.base import BaseNotifier
from watch_hunter.notifier.formatter import EmailFormatter

logger = logging.getLogger(__name__)


class ResendNotifier(BaseNotifier):
    API_URL = "https://api.resend.com/emails"

    def __init__(
        self,
        api_key: str | None = None,
        from_email: str = "Watch Hunter <onboarding@resend.dev>",
        criteria: SearchCriteria | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self.criteria = criteria or SearchCriteria()
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def send_digest(self, listings: list[Listing], recipient: str) -> bool:
        if not listings:
            logger.info("[resend] No new listings to send. Skipping digest.")
            return True

        if not self.is_configured():
            logger.warning("[resend] RESEND_API_KEY is not configured.")
            return False

        subject = EmailFormatter.format_subject(len(listings))
        text_content = EmailFormatter.format_text(listings, self.criteria)
        html_content = EmailFormatter.format_html(listings, self.criteria)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "from": self.from_email,
            "to": [recipient],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        }

        logger.info(
            "[resend] Sending email digest with %d listing(s) to %s...", len(listings), recipient
        )
        try:
            response = requests.post(
                self.API_URL, json=payload, headers=headers, timeout=self.timeout
            )
            if response.status_code in {200, 201, 202}:
                data = response.json()
                logger.info("[resend] Email sent successfully! ID: %s", data.get("id"))
                return True
            logger.error(
                "[resend] Failed to send email (HTTP %d): %s", response.status_code, response.text
            )
            return False
        except Exception as exc:
            logger.error("[resend] Exception sending email via Resend: %s", exc)
            return False
