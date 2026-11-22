"""Turn readings into hourly external statistics. Pure logic is HA-free."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .api import Reading


@dataclass(frozen=True)
class HourlyStat:
    start: datetime  # tz-aware UTC, top of the hour
    state: float  # meter index (kWh)
    sum: float  # kWh since the baseline


def initial_baseline(first: Reading) -> float:
    """Baseline such that the first reading's own delta is counted."""
    return round(first.index_value - first.delta_value, 4)


def build_hourly_stats(
    readings: list[Reading], baseline: float, automatic_only: bool = True
) -> list[HourlyStat]:
    """One stat per hour, from the last reading in that hour.

    Based on the cumulative index, so irregular or missing rows are harmless
    and re-importing overlapping ranges is idempotent.
    """
    by_hour: dict[datetime, Reading] = {}
    for reading in sorted(readings, key=lambda r: r.time):
        if automatic_only and not reading.is_automatic:
            continue
        hour = reading.time.replace(minute=0, second=0, microsecond=0, tzinfo=UTC)
        by_hour[hour] = reading
    return [
        HourlyStat(
            start=hour,
            state=r.index_value,
            sum=round(r.index_value - baseline, 4),
        )
        for hour, r in sorted(by_hour.items())
    ]
