import json
from datetime import UTC, datetime
from pathlib import Path

from hsveitur.api import parse_response
from hsveitur.statistics import build_hourly_stats, initial_baseline

PAGE = json.loads((Path(__file__).parent / "fixtures" / "usage_page.json").read_text())


def test_parse_real_shape():
    total, on_page, readings = parse_response(PAGE)
    assert (total, on_page, len(readings)) == (3, 3, 3)
    assert readings[0].meter_id == "7021613"
    assert readings[0].delivery_point_name == "Example 1"


def test_parse_documented_wrapped_shape():
    total, _, readings = parse_response({"success": True, "values": PAGE})
    assert total == 3 and len(readings) == 3


def test_parse_skips_non_import_rows():
    page = json.loads(json.dumps(PAGE))
    page["UsageData"][0]["type"] = "A-"
    _, on_page, readings = parse_response(page)
    assert on_page == 3 and len(readings) == 2


def test_stats_use_index_and_skip_manual():
    _, _, readings = parse_response(PAGE)
    base = initial_baseline(readings[0])
    assert base == 50048.4
    stats = build_hourly_stats(readings, base)
    assert [s.start.hour for s in stats] == [0, 1]  # manual row skipped
    assert stats[0].sum == 0.77 and stats[1].sum == 1.39
    assert stats[0].start == datetime(2026, 11, 20, 0, tzinfo=UTC)


def test_stats_idempotent_on_overlap():
    _, _, readings = parse_response(PAGE)
    base = initial_baseline(readings[0])
    once = build_hourly_stats(readings, base)
    twice = build_hourly_stats(readings + readings[:2], base)
    assert once == twice
