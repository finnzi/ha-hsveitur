"""Constants for the HS Veitur integration."""

from datetime import timedelta

DOMAIN = "hsveitur"

CONF_PUBLIC_KEY = "public_key"
CONF_PRIVATE_KEY = "private_key"
CONF_CUSTOMER_ID = "customer_id"
CONF_BACKFILL_MONTHS = "backfill_months"

DEFAULT_BACKFILL_MONTHS = 12
UPDATE_INTERVAL = timedelta(hours=6)
# Re-read this much already-imported data on every poll (imports are idempotent).
OVERLAP = timedelta(days=2)
# Largest date range requested in a single call during backfill.
MAX_CHUNK = timedelta(days=365)
# Delay between sequential backfill calls, to be polite to HS Veitur.
CHUNK_DELAY_SECONDS = 5

API_URL = "https://www.hsveitur.is/umbraco/api/Expectus/UsageData"
# Every successful call takes 40-200 s, so be generous.
API_TIMEOUT_SECONDS = 300
PAGE_SIZE = 10000

STATISTICS_SOURCE = DOMAIN
