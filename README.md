# HS Veitur for Home Assistant

A [HACS](https://hacs.xyz) custom integration that reads electricity usage from
[HS Veitur](https://www.hsveitur.is) (Iceland) into Home Assistant, including
the **Energy dashboard**.

> **Not affiliated with HS Veitur.** This is an independent, community-made project. It is
> **not** created, endorsed, sponsored, supported or approved by HS Veitur hf. in any way,
> and has no official connection to the company. "HS Veitur" and its logo are trademarks of
> their respective owner; the name and logo are used here only to identify the service this
> integration connects to. It uses HS Veitur's public customer API with your own
> credentials. For help with your account or the API itself, contact HS Veitur, not this
> project.

> **Vibe-coded with AI.** This integration was built mostly by an AI coding assistant
> (Claude Code) working from the human maintainer's direction, not hand-written line by
> line. It has had limited human review. Read the code before trusting it with your
> credentials, and expect rough edges. Issues and pull requests are welcome.
>
> **Status: early / experimental (v0.2.0).** The API client and statistics logic are
> tested, including a live call against the real API. The Home Assistant side (config
> flow, coordinator, sensor, statistics import) is written but has not yet been
> verified end to end in a running instance. Unofficial; not affiliated with HS Veitur.

## What it does

- Polls HS Veitur's `UsageData` API every 6 hours (the data is about a day behind real
  time, and each API call is slow: 40-200 s).
- Imports hourly **external statistics** (`hsveitur:energy_<meter_id>`) built from the
  meter's cumulative reading, so the Energy dashboard shows correct hourly history.
- On first setup it backfills history (default 12 months, 0-30 configurable) in the
  background, in sequential chunks, resumable after a restart.
- Creates one device per meter with a `total_increasing` kWh sensor holding the latest
  meter reading.
- Re-authentication flow if the keys stop working.
- Optional **cost tracking** with your own prices (see below).

## Cost tracking (custom pricing)

HS Veitur's API has no prices, and HS Veitur only transports the electricity; the
energy itself is billed by your retailer. So you enter your own rates: open the
integration's **Configure** dialog and set, in ISK per kWh **excluding VAT**:

- **Grid rate**: on your HS Veitur bill, distribution + transmission + equalization
  (*orkugjald dreifingar* + *flutningur* + *jöfnunargjald*) added together.
- **Energy rate**: the per-kWh price on your retailer's bill.
- **Include VAT**: adds 24% (on by default).

Either rate can be left empty; leave both empty to keep cost tracking off. This adds a
cumulative `hsveitur:cost_<meter_id>` statistic (ISK) that you can pick as the cost
statistic in the Energy dashboard's grid consumption settings.

Notes: fixed monthly fees are not included, only per-kWh charges. Rates are fixed
values, so spot-price tariffs are not supported. When you change a rate it applies from
the newest data onwards; hours already priced keep their old rate. Cost starts when you
first set a rate and is not back-filled for earlier history.

## Requirements

- HS Veitur API credentials: a **public key**, a **private key**, and your **customer ID
  (kennitala)**. See [Getting API credentials](#getting-api-credentials).
- Home Assistant with the recorder enabled (default).
- Home Assistant 2026.3 or newer to show the bundled HS Veitur icon (shipped in
  `custom_components/hsveitur/brand/`). Older versions work but show a placeholder icon.

## Getting API credentials

The keys are issued by HS Veitur through *Mínar síður* (My pages):

1. Open <https://www.hsveitur.is/minar-sidur/stillingar/vefthjonusta>
   (Mínar síður > Stillingar > Vefþjónusta; *vefþjónusta* is Icelandic for web service/API).
2. Log in with your **Auðkenni** (Icelandic electronic ID).
3. Request API access there. You get a public key and a private key.
4. Use those two keys plus your kennitala as the customer ID when adding the integration.

Treat the private key like a password: anyone with both keys and your kennitala can read
your usage data.

## Installation

Not yet published in the HACS default list. Add this repository as a custom
repository in HACS (type: Integration), install **HS Veitur**, restart Home Assistant,
then Settings > Devices & services > Add integration > **HS Veitur**.

Setup validates the keys with one live API call, which can take a few minutes.
The first history import runs in the background afterwards.

Then add the statistic(s) under Settings > Dashboards > Energy > Electricity grid >
Add consumption.

## How it works

```
HS Veitur API --(aiohttp, api.py)--> readings
readings --(statistics.py)--> hourly stats from the cumulative index_value
coordinator.py --> async_add_external_statistics (Energy dashboard)
               --> latest reading per meter --> sensor.py
```

| File (`custom_components/hsveitur/`) | Role |
|---|---|
| `api.py` | Async client + response parsing. No Home Assistant imports. |
| `statistics.py` | Pure logic: readings -> hourly statistics. No Home Assistant imports. |
| `coordinator.py` | Polling, backfill chunks, persistent cursor/baselines, statistics import |
| `sensor.py` | Per-meter latest-reading sensor (added dynamically once data arrives) |
| `config_flow.py` | Setup + reauth |

Design notes:

- Statistics are based on the cumulative `index_value`, not summed deltas, so missing
  or irregular rows (early history was manual readings) are harmless.
- Every poll re-reads the last 2 days; imports are keyed by hour, so overlap is idempotent.
- Only rows with `data_source == "Sjálfvirkar mælingar"` (automatic smart-meter readings)
  and type `A+` (import) are used.
- Iceland is UTC all year, so the API's timestamps are treated as UTC.

## API quirks (measured, not documented)

The official spec is at <https://app.swaggerhub.com/apis-docs/pajdak3/HSVeitur/1.0.1>.
Reality differs:

- Endpoint: `POST https://www.hsveitur.is/umbraco/api/Expectus/UsageData`, with **all
  parameters (including the keys) in the query string**.
- The response has no `success`/`values` wrapper: top level is `Info` and `UsageData`.
- Every successful call takes 40-200 s regardless of range or page size, so use large
  pages (10 000 worked) and few calls. Bad credentials fail instantly with HTTP 400.
- `Info.NextPage` is broken (points at the water endpoint) and leaks credentials; ignored.
- History starts 2023-03-01; hourly data only since smart meters were installed.

## Development

See [docs/development.md](docs/development.md) and [AGENTS.md](AGENTS.md).

```bash
docker compose up -d                 # dev Home Assistant at http://localhost:8123
docker compose run --rm tests        # Python 3.14 + pytest-homeassistant-custom-component
.venv/bin/pytest                     # HA-free tests, local
```

## Roadmap

- [ ] Verify the Home Assistant side end to end in the dev instance
- [ ] Config flow / coordinator tests with `pytest-homeassistant-custom-component`
- [ ] Backfill: retry with a smaller chunk on timeout
- [ ] CI: ruff, pytest, hassfest, HACS validation
