# AGENTS.md

Instructions for AI agents (and humans) working in this repo. See `README.md` for what the
project is, and `docs/development.md` for the dev workflow.

## Transparency

This project is openly AI-built ("vibe-coded"), and the README says so. Keep that
disclosure in place; never remove or soften it. Don't add wording that implies the code was
hand-written or fully human-reviewed.

## Hard rules

1. **Never print or commit secrets.** `.env` holds `PUBLIC_KEY`, `PRIVATE_KEY` and
   `CUSTOMER_ID` (a kennitala = personal ID). It is git-ignored; keep it that way. To inspect it,
   show key names only: `sed -E 's/=.*/=<redacted>/' .env`. Never `cat .env`.
2. **API responses contain secrets too.** `Info.NextPage` embeds the tokens and the
   kennitala, and every row has `customer_id`. Redact before printing or saving fixtures
   (use `"0000000000"` and `"Example 1"`, as in `tests/fixtures/`). Don't assume the
   response shape when redacting: check keys first.
3. **Never log request URLs** (tokens are in the query string). `api.py` reports only
   exception types for connection errors; keep it that way.
4. **Don't hammer the live API.** Every successful call takes 40-200 s. Use the live API
   only when needed, one narrow range, large `page_size` (small pages multiply the cost
   since each page is a separate slow call). Run long calls in the background.
5. Don't push, open PRs, or change repo visibility unless asked. The repo is public.
   Commit messages end with the co-author line the harness specifies.

## Layout

```
custom_components/hsveitur/   the integration (api.py and statistics.py are HA-free)
tests/                        pytest; conftest stubs the package so HA-free modules import
docker-compose.yml            dev Home Assistant + test runner
dev/config/                   dev HA config; only configuration.yaml is tracked
docs/development.md           dev workflow
```

## Commands

```bash
# Tests
.venv/bin/pytest                      # HA-free tests, fast, local (Python 3.15 venv)
docker compose run --rm tests         # full suite on Python 3.14 + HA test plugin
.venv/bin/ruff check .                # lint

# Dev Home Assistant (http://localhost:8123)
docker compose up -d
docker compose restart homeassistant  # after changing integration code (live-mounted)
docker compose logs -f homeassistant
docker compose down
```

Notes:
- Local Python is 3.12/3.15 only; **Home Assistant needs 3.13+/3.14**, so anything importing
  `homeassistant` runs in the `tests` container, not the local venv.
- The containers run as root. `dev/config/` will be root-owned (expected, git-ignored).
  The test service disables bytecode/cache writes so it doesn't litter the repo; don't
  undo that. Delete root-owned strays with a throwaway container, not `sudo`:
  `docker run --rm -v "$PWD":/repo:z alpine sh -c 'find /repo -user 0 -type f -name "*.pyc" -delete'`.
- Adding the integration in the dev HA UI needs the user's keys and an onboarded HA
  account; ask the user rather than doing it with their credentials unattended.
- ha-mcp tools may be connected to *some* Home Assistant; confirm it's the dev instance
  (localhost:8123) before using them, never a real home.

## Conventions

- Keep `api.py` and `statistics.py` free of Home Assistant imports so they stay testable
  locally. Put HA-specific code in `coordinator.py`, `sensor.py`, `config_flow.py`.
- Statistics derive from the cumulative `index_value`, never summed `delta_value`.
  Imports must stay idempotent (keyed by hour; overlapping fetches are normal).
- API timestamps are Iceland local time = UTC all year; treat as UTC.
- Handle both response shapes (real: top-level `Info`/`UsageData`; documented: wrapped in
  `values`).
- New behaviour gets a test. HA-free logic: add to `tests/test_api_and_stats.py` style with
  redacted fixtures. HA-side logic: `pytest-homeassistant-custom-component` in the container.
- Python 3.14 target, `ruff` clean, type hints, async everywhere in the HA side.

## Status / known gaps

The HA side (config flow, coordinator, sensor, statistics import via
`async_add_external_statistics` and `StatisticMetaData` fields) was written without a
running Home Assistant and is **unverified**. Treat it as suspect until exercised in the
dev instance or in container tests. See the README roadmap for the open items.
