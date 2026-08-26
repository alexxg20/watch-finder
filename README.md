# Watch Hunter

[![Daily Watch Hunter](https://github.com/alexgarciasilva/watch-hunter/actions/workflows/daily_watch_hunter.yml/badge.svg)](https://github.com/alexgarciasilva/watch-hunter/actions/workflows/daily_watch_hunter.yml)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](pyproject.toml)

Automated production-ready search and alert engine for luxury watch listings across **eBay** and **Reddit r/Watchexchange**, running daily via GitHub Actions with rich HTML email digests.

---

## Target Watch Specifications

- **Watch References:**
  - `231.10.39.21.02.002` (Omega Seamaster Aqua Terra 150M Master Co-Axial 38.5mm, silver/white dial, orange seconds hand)
  - `231.10.39.21.02.001` (Omega Seamaster Aqua Terra 150M Co-Axial 38.5mm, opaline silver dial)
- **Condition:** Minimum **Good** condition (*Mint*, *Excellent*, *Very Good* preferred; rejects *Fair*, *Poor*, *For parts*).
- **Price Range:** **€2,500 – €3,500 EUR** (or equivalent in CHF, GBP, USD via live FX rates).
- **Regions:** Europe, European Union, United Kingdom, and Switzerland.
- **Alert Recipient:** `2alex.garcia2@gmail.com` (configurable).

---

## Architecture & Design

```
watch-hunter/
├── src/
│   └── watch_hunter/
│       ├── adapters/          # Pluggable source adapters
│       │   ├── base.py        # Base adapter with exponential backoff & rate-limit handling
│       │   ├── ebay.py        # Official eBay Browse API (OAuth2 Client Credentials)
│       │   ├── reddit.py      # Reddit r/Watchexchange API (OAuth2 & public fallback)
│       │   └── chrono24.py    # Isolated Chrono24 stub & saved-search email/JSON parser
│       ├── storage/           # Persistent deduplication storage
│       │   ├── base.py        # Abstract storage interface
│       │   └── json_storage.py# Atomic JSON file storage with entry expiration
│       ├── notifier/          # Multi-channel notification engine
│       │   ├── base.py        # Abstract notifier interface
│       │   ├── email_resend.py# Resend REST API email client
│       │   ├── email_smtp.py  # SMTP client (STARTTLS / SSL support)
│       │   ├── console.py     # Console output for local dry-runs
│       │   └── formatter.py   # HTML + Plaintext responsive digest generator
│       ├── currency.py        # Live exchange rate converter (EUR base) with offline fallback
│       ├── filter.py          # Multi-criteria filter engine (Ref, Price EUR, Condition, EU/CH)
│       ├── models.py          # Normalized Pydantic v2 data models
│       ├── config.py          # Environment settings loader via pydantic-settings
│       ├── runner.py          # Orchestration pipeline
│       └── cli.py             # CLI command runner
├── tests/                     # Comprehensive test suite with mocked APIs
├── .github/workflows/         # Daily GitHub Actions workflow
├── .env.example               # Secret template documentation
└── pyproject.toml             # Project metadata & tool config
```

### 1. Source Adapters
- **eBay Adapter (`EbayAdapter`):** Uses the official eBay Browse REST API with OAuth2 Client Credentials grant (`https://api.ebay.com/buy/browse/v1/item_summary/search`). Caches tokens, respects rate limits (`Retry-After`), and queries European marketplaces (`EBAY_DE`, `EBAY_GB`, `EBAY_IT`, etc.).
- **Reddit Adapter (`RedditAdapter`):** Uses Reddit's OAuth API to search `r/Watchexchange` for active `[WTS]` listings, filtering out sold (`[SOLD]`) and buy-only (`[WTB]`) posts. Extracts prices and currencies (`€`, `£`, `CHF`, `$`), conditions, and locations using resilient regex.
- **Chrono24 Adapter Stub (`Chrono24AdapterStub`):** In compliance with Chrono24 Terms of Service, direct scraping without an approved commercial API is disabled. Instead, an isolated import pipeline is provided for saved-search JSON exports and user-forwarded Chrono24 email alerts.

### 2. Normalized Listing Schema
Every listing from any source is normalized into a unified model:
- `title: str`
- `price: float`
- `currency: str`
- `condition: str` (and mapped `condition_grade: ConditionGrade`)
- `seller: str`
- `source: str` (`"ebay"`, `"reddit"`, `"chrono24"`)
- `url: str`
- `discovered_at: datetime` (UTC)
- `price_eur: float | None` (computed normalized EUR price)
- `matched_reference: str | None`
- `location: str | None`
- `image_url: str | None`

### 3. Deduplication & Persistent Storage Choice
**Why File-Based JSON Storage (`JsonFileStorage`) with GitHub Actions Cache:**
- **Zero External Infrastructure:** Does not require provisioning cloud databases (Redis, DynamoDB, PostgreSQL) or managing external database credentials that can expire.
- **Auditability & Simplicity:** State is stored in a clean, human-readable JSON file (`data/seen_listings.json`), recording first-seen/last-seen timestamps and listing metadata.
- **Atomic File Operations:** Writes use temporary files with atomic directory replacement (`os.replace`) to eliminate the risk of state corruption.
- **Native GitHub Actions Integration:** Cached between workflow runs using `actions/cache` and retained in GitHub Actions Artifacts.
- **Automatic Pruning:** Built-in pruning removes records older than 90 days to keep file size minimal over years of operation.

---

## Setup & Configuration

### Prerequisites
- Python 3.10+ (tested on Python 3.10 through 3.14)

### Local Installation
```bash
# Clone the repository
git clone https://github.com/alexgarciasilva/watch-hunter.git
cd watch-hunter

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Environment Variables & Secrets
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Description | Required? | Example |
|---|---|---|---|
| `NOTIFICATION_EMAIL` | Target email address | Yes | `2alex.garcia2@gmail.com` |
| `EBAY_CLIENT_ID` | eBay Developer Application Client ID | Recommended | `your_ebay_app_id` |
| `EBAY_CLIENT_SECRET` | eBay Developer Application Secret | Recommended | `your_ebay_cert_id` |
| `EBAY_MARKETPLACE_ID` | Default marketplace ID | No (default `EBAY_DE`) | `EBAY_DE` / `EBAY_GB` |
| `REDDIT_CLIENT_ID` | Reddit Developer App ID (script) | Optional (fallback to public API) | `your_reddit_client_id` |
| `REDDIT_CLIENT_SECRET`| Reddit Developer App Secret | Optional | `your_reddit_client_secret` |
| `REDDIT_USER_AGENT` | Reddit User Agent header | No | `python:watch_hunter:v0.1.0` |
| `RESEND_API_KEY` | Resend Email API Key | Required if using Resend | `re_123456789` |
| `RESEND_FROM_EMAIL` | Sender address | No | `Watch Hunter <onboarding@resend.dev>` |
| `SMTP_HOST` | SMTP Server Hostname | Required if using SMTP | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP Port | No (default `587`) | `587` |
| `SMTP_USER` | SMTP Username | For SMTP auth | `user@gmail.com` |
| `SMTP_PASSWORD` | SMTP Password / App Password | For SMTP auth | `app_password_here` |
| `DRY_RUN` | Dry run flag (logs without sending) | No | `false` |

---

## How to Run

### Run Locally in Dry-Run Mode
```bash
python -m watch_hunter.cli --dry-run
```

### Run Live Local Search
```bash
python -m watch_hunter.cli
```

### Ingest Chrono24 Saved Search File
Place JSON files into `data/chrono24_imports/` and run:
```bash
python -m watch_hunter.cli
```

---

## GitHub Actions Deployment

The workflow `.github/workflows/daily_watch_hunter.yml` runs automatically:
- **Schedule:** Daily at **08:00 UTC** (`0 8 * * *`).
- **Manual Trigger:** Supports manual triggering under the **Actions** tab with an optional `dry_run` checkbox.

### Setting up GitHub Secrets:
In your GitHub repository, navigate to **Settings > Secrets and variables > Actions** and add:
- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`
- `REDDIT_CLIENT_ID` (optional)
- `REDDIT_CLIENT_SECRET` (optional)
- `RESEND_API_KEY` (or SMTP secrets: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`)
- `NOTIFICATION_EMAIL` (optional, defaults to `2alex.garcia2@gmail.com`)

---

## Verification & Testing

### Running Tests
```bash
pytest -v
```

### Running Formatter & Linter
```bash
ruff format --check
ruff check
```

### Running Type Checker
```bash
mypy src tests
```
