"""Coordinator: polls HS Veitur, imports statistics, tracks the latest reading."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthError, HsVeiturClient, HsVeiturError, Reading
from .const import (
    CHUNK_DELAY_SECONDS,
    CONF_BACKFILL_MONTHS,
    CONF_ENERGY_RATE,
    CONF_GRID_RATE,
    CONF_INCLUDE_VAT,
    CURRENCY,
    DEFAULT_BACKFILL_MONTHS,
    DOMAIN,
    MAX_CHUNK,
    OVERLAP,
    STATISTICS_SOURCE,
    UPDATE_INTERVAL,
)
from .statistics import (
    RateSegment,
    build_cost_stats,
    build_hourly_stats,
    effective_rate,
    initial_baseline,
    with_rate,
)

_LOGGER = logging.getLogger(__name__)

type HsVeiturConfigEntry = ConfigEntry[HsVeiturCoordinator]


class HsVeiturCoordinator(DataUpdateCoordinator[dict[str, Reading]]):
    """data: meter_id -> latest reading."""

    config_entry: HsVeiturConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: HsVeiturConfigEntry, client: HsVeiturClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client
        self._store: Store[dict] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._state: dict | None = None  # {"cursor": iso | None, "baselines": {}}

    async def _async_update_data(self) -> dict[str, Reading]:
        if self._state is None:
            self._state = await self._store.async_load() or {
                "cursor": None,
                "baselines": {},
            }
        now = datetime.now(UTC).replace(tzinfo=None)
        months = self.config_entry.data.get(
            CONF_BACKFILL_MONTHS, DEFAULT_BACKFILL_MONTHS
        )
        if self._state["cursor"]:
            start = datetime.fromisoformat(self._state["cursor"]) - OVERLAP
        else:
            start = now - timedelta(days=30 * months)

        latest: dict[str, Reading] = dict(self.data or {})
        first = True
        while start < now:
            if not first:
                await asyncio.sleep(CHUNK_DELAY_SECONDS)
            first = False
            end = min(start + MAX_CHUNK, now)
            try:
                readings = await self._client.get_readings(start, end)
            except AuthError as err:
                raise ConfigEntryAuthFailed from err
            except HsVeiturError as err:
                raise UpdateFailed(str(err)) from err
            self._import(readings)
            for meter_id, meter_readings in _by_meter(readings).items():
                newest = max(meter_readings, key=lambda r: r.time)
                if meter_id not in latest or newest.time >= latest[meter_id].time:
                    latest[meter_id] = newest
            if readings:
                newest_time = max(r.time for r in readings)
                cursor = self._state["cursor"]
                if not cursor or newest_time > datetime.fromisoformat(cursor):
                    self._state["cursor"] = newest_time.isoformat()
            await self._store.async_save(self._state)
            start = end
        return latest

    def _import(self, readings: list[Reading]) -> None:
        assert self._state is not None
        for meter_id, meter_readings in _by_meter(readings).items():
            automatic = sorted(
                (r for r in meter_readings if r.is_automatic), key=lambda r: r.time
            )
            if not automatic:
                continue
            baseline = self._state["baselines"].get(meter_id)
            if baseline is None:
                baseline = initial_baseline(automatic[0])
                self._state["baselines"][meter_id] = baseline
            stats = build_hourly_stats(automatic, baseline)
            name = automatic[0].delivery_point_name or meter_id
            async_add_external_statistics(
                self.hass,
                StatisticMetaData(
                    has_sum=True,
                    mean_type=StatisticMeanType.NONE,
                    name=f"HS Veitur {name}",
                    source=STATISTICS_SOURCE,
                    statistic_id=f"{STATISTICS_SOURCE}:energy_{meter_id}",
                    unit_class="energy",
                    unit_of_measurement="kWh",
                ),
                [StatisticData(start=s.start, state=s.state, sum=s.sum) for s in stats],
            )
            self._import_cost(meter_id, name, automatic, stats)

    def _rate(self) -> float | None:
        opts = self.config_entry.options
        return effective_rate(
            opts.get(CONF_GRID_RATE),
            opts.get(CONF_ENERGY_RATE),
            opts.get(CONF_INCLUDE_VAT, True),
        )

    def _import_cost(
        self, meter_id: str, name: str, automatic: list[Reading], stats: list
    ) -> None:
        """Import a cumulative ISK statistic priced from the user's own rates."""
        assert self._state is not None
        rate = self._rate()
        if rate is None:
            return
        cost = self._state.setdefault("cost", {}).setdefault(
            meter_id, {"segments": [], "last_index": None}
        )
        segments = [RateSegment(*seg) for seg in cost["segments"]]
        # A new rate applies from the newest index already priced onwards.
        at_index = cost["last_index"]
        if at_index is None:
            at_index = initial_baseline(automatic[0])
        segments = with_rate(segments, rate, at_index)
        cost["segments"] = [[seg.from_index, seg.rate] for seg in segments]
        cost["last_index"] = max(at_index, stats[-1].state)
        async_add_external_statistics(
            self.hass,
            StatisticMetaData(
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name=f"HS Veitur {name} cost",
                source=STATISTICS_SOURCE,
                statistic_id=f"{STATISTICS_SOURCE}:cost_{meter_id}",
                unit_class=None,
                unit_of_measurement=CURRENCY,
            ),
            [
                StatisticData(start=c.start, state=c.sum, sum=c.sum)
                for c in build_cost_stats(stats, segments)
            ],
        )


def _by_meter(readings: list[Reading]) -> dict[str, list[Reading]]:
    grouped: dict[str, list[Reading]] = defaultdict(list)
    for reading in readings:
        grouped[reading.meter_id].append(reading)
    return grouped
