"""Turn readings into hourly external statistics. Pure logic is HA-free."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .api import Reading
from .const import VAT_RATE


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


@dataclass(frozen=True)
class RateSegment:
    """From this meter index (kWh) onwards, each kWh costs `rate` (ISK, final)."""

    from_index: float
    rate: float


@dataclass(frozen=True)
class CostStat:
    start: datetime  # tz-aware UTC, top of the hour
    sum: float  # ISK since the first segment started


def effective_rate(
    grid_rate: float | None, energy_rate: float | None, include_vat: bool
) -> float | None:
    """Final ISK/kWh, or None when no rate is configured (cost tracking off)."""
    if grid_rate is None and energy_rate is None:
        return None
    rate = (grid_rate or 0.0) + (energy_rate or 0.0)
    return round(rate * (1 + VAT_RATE) if include_vat else rate, 6)


def with_rate(
    segments: list[RateSegment], rate: float, at_index: float
) -> list[RateSegment]:
    """Return segments with `rate` in force from `at_index` onwards.

    Rates are tied to the cumulative meter index rather than to time, so cost is
    a pure function of the index: overlapping re-imports are idempotent and a
    rate change never rewrites hours that were already priced.
    """
    if segments and segments[-1].rate == rate:
        return segments
    if segments and at_index <= segments[-1].from_index:
        return [*segments[:-1], RateSegment(segments[-1].from_index, rate)]
    return [*segments, RateSegment(at_index, rate)]


def cost_at(index: float, segments: list[RateSegment]) -> float:
    """Cumulative cost (ISK) at a meter index."""
    total = 0.0
    for i, seg in enumerate(segments):
        end = segments[i + 1].from_index if i + 1 < len(segments) else index
        kwh = min(index, end) - seg.from_index
        if kwh > 0:
            total += kwh * seg.rate
    return round(total, 4)


def build_cost_stats(
    stats: list[HourlyStat], segments: list[RateSegment]
) -> list[CostStat]:
    return [CostStat(start=s.start, sum=cost_at(s.state, segments)) for s in stats]
