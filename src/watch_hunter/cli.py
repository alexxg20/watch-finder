import argparse
import logging
import sys

from watch_hunter.config import Settings
from watch_hunter.runner import WatchHunterRunner


def configure_logging(level_name: str) -> None:
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch Hunter: Daily automated search for Omega Aqua Terra on eBay & Reddit."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run search and output digest to console without sending emails or updating state",
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Override recipient notification email",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        help="Path to JSON state file for deduplication",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=".env",
        help="Path to custom .env file",
    )

    args = parser.parse_args()

    # Load environment variables if custom env file provided
    from dotenv import load_dotenv

    if args.env_file:
        load_dotenv(args.env_file)

    # Load settings
    settings = Settings()
    if args.email:
        settings.notification_email = args.email
    if args.state_file:
        settings.state_file_path = args.state_file
    if args.dry_run:
        settings.dry_run = True

    configure_logging(args.log_level or settings.log_level)

    runner = WatchHunterRunner(settings=settings)
    result = runner.run()

    summary = result.summary()
    print(
        f"\n[Watch Hunter Run Complete] "
        f"Fetched: {summary['total_fetched']} | "
        f"Matched: {summary['total_matched']} | "
        f"New Unseen: {summary['new_unseen']} | "
        f"Notified: {summary['notified_count']}"
    )

    if result.errors:
        print(f"Warnings/Errors encountered: {len(result.errors)}", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
