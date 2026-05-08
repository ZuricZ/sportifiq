# Sportifiq

Automates Sportifiq court bookings, cancellations, and reminder emails via GitHub Actions.
Schedule weekly bookings per venue and day, receive an email digest with one-click cancel
links, or trigger a booking or cancellation manually from the Actions tab. Everything runs
in the cloud — local setup is only needed for development or ad-hoc runs.

## How it works

Three CLI runners live in `src/`:

| Runner | Entry point | What it does |
|--------|-------------|--------------|
| `book.py` | `python -m src.book` | Opens a headless Chrome session, logs in, navigates to the target day, and books the configured court (with backup fallback). Accepts terms/privacy if redirected on first login. |
| `remind.py` | `python -m src.remind` | Fetches all upcoming confirmed bookings and emails a digest with HMAC-signed cancel links. |
| `cancel.py` | `python -m src.cancel` | Logs in and cancels a specific booking by site ID. |

All shared logic lives in `src/libs/` — models, config loading, Selenium page object,
booking service, and session management. Tests live in `tests/`.

## Repo layout

```
sportifiq/
├── src/
│   ├── libs/                      # Library code (imported by runners and tests)
│   │   ├── models.py              # Dataclasses: VenueConfig, BookingRequest, SiteBooking, …
│   │   ├── config_loader.py       # Load venues.yaml, users.yaml, encrypted password
│   │   ├── page.py                # Selenium Page Object (SportifiqPage)
│   │   ├── booking_service.py     # book() — orchestrates slots, handles backup court
│   │   ├── scraper.py             # Pure parsing helpers (no I/O, fully unit-tested)
│   │   ├── session.py             # sportifiq_session() context manager
│   │   ├── driver.py              # create_driver() — headless Chrome setup
│   │   ├── exceptions.py          # SlotUnavailableError, LoginError
│   │   └── log.py                 # Logging setup
│   ├── book.py                    # CLI runner: book a court
│   ├── remind.py                  # CLI runner: send reminder emails
│   ├── cancel.py                  # CLI runner: cancel a booking
│   └── get_pwd.py                 # One-time setup: encrypt password for local runs
├── config/
│   ├── venues.yaml                # Venue URLs and court names
│   └── users.yaml                 # Per-user schedules, notify emails, gh_pages_url setting
├── tests/                         # pytest suite (unit tests, no browser)
└── .github/workflows/             # GitHub Actions (book, remind, cancel, tests)
```

## Adding yourself as a user

### 1. Add yourself to `config/users.yaml`

```yaml
users:
  XY:                              # your user key — 2–3 uppercase letters
    notify_emails:
      - you@example.com            # list — add more addresses to CC others
    venue: koseze                  # primary venue for the remind workflow
    schedules:
      - venue: koseze              # must match a key in config/venues.yaml
        day: monday
        hour: "13:00"
        court: BALON HC1
        backup_court: BALON HC2   # optional
```

Available venues: `tivoli`, `svoboda`, `koseze`. Days are lowercase English (`monday`,
`wednesday`, etc.). Open a PR with this change.

### 2. Add your secrets to the repository

You need four secrets, replacing `XY` with your user key:

| Secret name | Value |
|-------------|-------|
| `XY_SPORTIFIQ_EMAIL` | Your Sportifiq login email |
| `XY_SPORTIFIQ_PASSWORD` | Your Sportifiq login password |
| `XY_GMAIL_USER` | Gmail address used to send reminder emails |
| `XY_GMAIL_APP_PASSWORD` | Google Account → Security → 2-Step Verification → App passwords |

`CANCEL_SECRET` is a shared secret already in the repo — you do not need to add it.

**Option A — GitHub web UI**

Go to **Settings → Secrets and variables → Actions → New repository secret** and add each
one manually.

**Option B — GitHub CLI (faster)**

First, install the GitHub CLI if you don't have it:

```bash
# macOS
brew install gh

# Windows (winget)
winget install --id GitHub.cli -e

# Linux
sudo apt install gh        # Debian/Ubuntu
sudo dnf install gh        # Fedora
```

Then authenticate once:

```bash
gh auth login
# Choose: GitHub.com → HTTPS → Login with a web browser
```

Then set all four secrets in one go (replace values with your own):

```bash
gh secret set XY_SPORTIFIQ_EMAIL    --body "you@example.com"          -R <owner>/sportifiq
gh secret set XY_SPORTIFIQ_PASSWORD --body "your-sportifiq-password"  -R <owner>/sportifiq
gh secret set XY_GMAIL_USER         --body "sender@gmail.com"          -R <owner>/sportifiq
gh secret set XY_GMAIL_APP_PASSWORD --body "xxxx xxxx xxxx xxxx"       -R <owner>/sportifiq
```

Verify they were saved:

```bash
gh secret list -R <owner>/sportifiq
```

### 3. Create your booking workflow file(s)

Add one file per scheduled booking under `.github/workflows/`. Use this template:

```yaml
name: "XY: Book Koseze (Monday)"

on:
  schedule:
    - cron: '50 21 * * 1'   # Every Monday at 23:50 CEST — runner ready before midnight
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Dry run (log only, no browser)'
        type: boolean
        default: false

jobs:
  book:
    uses: ./.github/workflows/_book.yml
    with:
      user: XY
      venue: koseze
      day: monday
      execution_time: "00:00"
      dry_run: ${{ inputs.dry_run || false }}
    secrets: inherit
```

Cron day-of-week: `1`=Mon, `2`=Tue, `3`=Wed, `4`=Thu, `5`=Fri. The workflow fires at
23:50 CEST on the same weekday as the session and books 7 days out. The runner sleeps
until exactly midnight before submitting the booking.

Open a PR with the workflow file(s).

### 4. Add yourself to the reminder and cancel workflows

In `.github/workflows/remind.yml`, add your user key to the matrix and add a case block
for your credentials inside the "Resolve credentials" step:

```yaml
# remind.yml — matrix
strategy:
  matrix:
    user: [ZZ, GV, JJ, XY]   # add XY here

# remind.yml — Resolve credentials step
XY)
  echo "SPORTIFIQ_EMAIL=${{ secrets.XY_SPORTIFIQ_EMAIL }}" >> "$GITHUB_ENV"
  echo "SPORTIFIQ_PASSWORD=${{ secrets.XY_SPORTIFIQ_PASSWORD }}" >> "$GITHUB_ENV"
  echo "GMAIL_USER=${{ secrets.XY_GMAIL_USER }}" >> "$GITHUB_ENV"
  echo "GMAIL_APP_PASSWORD=${{ secrets.XY_GMAIL_APP_PASSWORD }}" >> "$GITHUB_ENV"
  ;;
```

In `.github/workflows/cancel.yml` and `.github/workflows/_book.yml`, add the same case
block (email + password only) inside their "Resolve credentials" steps:

```yaml
XY)
  echo "SPORTIFIQ_EMAIL=${{ secrets.XY_SPORTIFIQ_EMAIL }}" >> "$GITHUB_ENV"
  echo "SPORTIFIQ_PASSWORD=${{ secrets.XY_SPORTIFIQ_PASSWORD }}" >> "$GITHUB_ENV"
  ;;
```

Include all three workflow file changes in the same PR as step 3.

### 5. Verify

After your PR is merged, go to **Actions → Send booking reminders → Run workflow** and
trigger it manually. You should receive a reminder email, or see a log line saying there
are no upcoming bookings.

## Local development

**Requirements:** Python 3.12+, Chrome installed.

```bash
# Install dev dependencies (includes pytest)
pip install -r requirements-dev.txt

# Run all tests (from repo root)
python -m pytest tests/ -v

# Encrypt your Sportifiq password for local runs (writes key.key and password.dat — gitignored)
python -m src.get_pwd
```

Run a runner locally:

```bash
# Book a court
python -m src.book \
  --venue koseze \
  --day 2026-05-14 \
  --hour 13:00 \
  --num_sessions 1 \
  --court_name "BALON HC1" \
  --backup_court_name "BALON HC2" \
  --user_email you@example.com

# Dry run — logs params, skips browser entirely
DRY_RUN=true python -m src.book \
  --venue koseze \
  --day 2026-05-14 \
  --hour 13:00 \
  --num_sessions 1 \
  --court_name "BALON HC1" \
  --user_email you@example.com

# Send reminder email
GMAIL_USER=sender@gmail.com GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
CANCEL_SECRET=<your-cancel-secret> \
python -m src.remind \
  --user_email you@example.com \
  --user_key XY \
  --venue koseze

# Send reminder email (dry run — prints details, no email sent)
python -m src.remind \
  --user_email you@example.com \
  --user_key XY \
  --venue koseze \
  --dry_run

# Cancel a booking
python -m src.cancel \
  --venue koseze \
  --site_id 12345678 \
  --user_email you@example.com
```

`SPORTIFIQ_PASSWORD` must be set as an environment variable, or `key.key` + `password.dat`
must exist (generated via `python -m src.get_pwd`).

## GitHub Actions reference

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `test.yml` | Every push / PR | Runs the full pytest suite |
| `remind.yml` | Daily 08:00 UTC, manual | Sends booking digest email for each configured user |
| `book_<USER>_<VENUE>.yml` | Scheduled (per user), manual | Books a court 7 days out |
| `book_manual.yml` | Manual only | Ad-hoc booking for any user/venue/date |
| `cancel.yml` | Manual only | Cancels a booking by site ID (triggered via link in reminder email) |

All booking workflows delegate to `_book.yml` (reusable workflow).
