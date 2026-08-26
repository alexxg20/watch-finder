import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from watch_hunter.models import Listing, SearchCriteria
from watch_hunter.notifier.base import BaseNotifier
from watch_hunter.notifier.formatter import EmailFormatter

logger = logging.getLogger(__name__)


class SmtpNotifier(BaseNotifier):
    def __init__(
        self,
        host: str | None = None,
        port: int = 587,
        user: str | None = None,
        password: str | None = None,
        from_email: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        criteria: SearchCriteria | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email or user or "watch_hunter@localhost"
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.criteria = criteria or SearchCriteria()
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.host and self.host.strip())

    def send_digest(self, listings: list[Listing], recipient: str) -> bool:
        if not listings:
            logger.info("[smtp] No new listings to send. Skipping digest.")
            return True

        if not self.is_configured():
            logger.warning("[smtp] SMTP_HOST is not configured.")
            return False

        subject = EmailFormatter.format_subject(len(listings))
        text_content = EmailFormatter.format_text(listings, self.criteria)
        html_content = EmailFormatter.format_html(listings, self.criteria)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = recipient

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        logger.info(
            "[smtp] Sending digest with %d listing(s) to %s via %s:%d...",
            len(listings),
            recipient,
            self.host,
            self.port,
        )
        try:
            assert self.host is not None
            if self.use_ssl:
                server: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)

            with server:
                server.ehlo()
                if self.use_tls and not self.use_ssl:
                    server.starttls()
                    server.ehlo()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(self.from_email, [recipient], msg.as_string())

            logger.info("[smtp] Email sent successfully via SMTP")
            return True
        except Exception as exc:
            logger.error("[smtp] Failed to send email via SMTP: %s", exc)
            return False
