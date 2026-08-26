from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from watch_hunter.models import ConditionGrade, SearchCriteria


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Notification Email
    notification_email: str = Field(default="2alex.garcia2@gmail.com")

    # Target Watch Search Configuration
    target_references: list[str] = Field(default=["231.10.39.21.02.002", "231.10.39.21.02.001"])
    min_price_eur: float = Field(default=2500.0)
    max_price_eur: float = Field(default=3500.0)
    min_condition: ConditionGrade = Field(default=ConditionGrade.GOOD)
    allow_unknown_condition: bool = Field(default=True)

    # eBay API Configuration (OAuth client credentials)
    ebay_client_id: str | None = Field(default=None)
    ebay_client_secret: str | None = Field(default=None)
    ebay_marketplace_id: str = Field(default="EBAY_DE")

    # Reddit API Configuration (OAuth script app)
    reddit_client_id: str | None = Field(default=None)
    reddit_client_secret: str | None = Field(default=None)
    reddit_user_agent: str = Field(
        default="python:watch_hunter:v0.1.0 (by /u/watch_hunter_notifier)"
    )

    # Resend API Configuration
    resend_api_key: str | None = Field(default=None)
    resend_from_email: str = Field(default="Watch Hunter <onboarding@resend.dev>")

    # SMTP Configuration (Fallback or alternative to Resend)
    smtp_host: str | None = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_user: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_from: str | None = Field(default=None)
    smtp_use_tls: bool = Field(default=True)
    smtp_use_ssl: bool = Field(default=False)

    # Persistent Storage & Deduplication
    state_file_path: str = Field(default="data/seen_listings.json")

    # Execution Options
    dry_run: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    def build_search_criteria(self) -> SearchCriteria:
        return SearchCriteria(
            references=self.target_references,
            min_price_eur=self.min_price_eur,
            max_price_eur=self.max_price_eur,
            min_condition=self.min_condition,
            allow_unknown_condition=self.allow_unknown_condition,
        )
