from datetime import UTC, datetime

from hsveitur.statistics import (
    HourlyStat,
    RateSegment,
    build_cost_stats,
    cost_at,
    effective_rate,
    with_rate,
)


def test_effective_rate_includes_vat_and_sums_parts():
    # Rates from real bills: grid 4.83 + 3.41 + 1.01, energy 7.92 (ex VAT)
    assert effective_rate(9.25, 7.92, True) == 21.2908
    assert effective_rate(9.25, 7.92, False) == 17.17


def test_effective_rate_one_part_or_none():
    assert effective_rate(None, 7.92, False) == 7.92
    assert effective_rate(9.25, None, False) == 9.25
    assert effective_rate(None, None, True) is None


def test_cost_single_segment():
    segs = [RateSegment(100.0, 20.0)]
    assert cost_at(100.0, segs) == 0.0
    assert cost_at(90.0, segs) == 0.0  # below the anchor: clipped
    assert cost_at(101.5, segs) == 30.0


def test_cost_rate_change_keeps_history():
    segs = with_rate([], 20.0, 100.0)
    segs = with_rate(segs, 25.0, 110.0)
    assert cost_at(110.0, segs) == 200.0
    assert cost_at(112.0, segs) == 250.0  # 10 kWh @ 20 + 2 kWh @ 25


def test_with_rate_unchanged_and_superseded():
    segs = with_rate([], 20.0, 100.0)
    assert with_rate(segs, 20.0, 150.0) is segs
    # changed twice before any new data: last segment is replaced, not stacked
    segs = with_rate(with_rate(segs, 25.0, 110.0), 30.0, 110.0)
    assert segs == [RateSegment(100.0, 20.0), RateSegment(110.0, 30.0)]


def test_cost_stats_idempotent_on_overlap():
    segs = [RateSegment(100.0, 10.0)]
    hours = [
        HourlyStat(datetime(2026, 11, 20, h, tzinfo=UTC), 100.0 + h, float(h))
        for h in (1, 2, 3)
    ]
    once = build_cost_stats(hours, segs)
    again = build_cost_stats(hours[1:], segs)
    assert [c.sum for c in once] == [10.0, 20.0, 30.0]
    assert again == once[1:]
