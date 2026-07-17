import os

import pytest

pytest.importorskip("lxml")

from sillok_pipeline.parse import parse_bulk_xml, parse_solar_attr
from sillok_pipeline.probe import probe_bulk_structure

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "history_sample.xml")


def test_parse_solar_attr():
    assert parse_solar_attr("1393-01-06L0") == (1393, 1, 6, 0)
    assert parse_solar_attr("1393-01-06L1") == (1393, 1, 6, 1)
    assert parse_solar_attr("") is None


def test_parse_bulk_xml_fixture():
    arts = parse_bulk_xml(FIXTURE)
    assert len(arts) == 2  # two level5 articles under one day

    a0 = arts[0]
    assert a0.king_code == "a"
    assert a0.king == "태조"
    assert a0.reign_year == 2
    assert a0.month == 1
    assert a0.is_leap == 0
    assert a0.day == 6
    assert a0.ganji_raw == "壬子"          # day pillar, NOT the year/month pillar
    assert a0.ganji_idx == 48              # 壬子
    assert a0.solar_iso == "1393-01-06L0"
    assert "卒" in a0.body


def test_day_pillar_not_confused_with_year_or_month():
    # the fixture's level2/level3 carry 간지 attrs (계유/갑자); the parser must
    # pick the level4 day pillar (壬子), never those.
    arts = parse_bulk_xml(FIXTURE)
    assert all(a.ganji_raw == "壬子" for a in arts)


def test_probe_reports_ganji_type():
    report = probe_bulk_structure(FIXTURE)
    assert report["has_ganji_type"] is True
    assert "서기" in report["dateOccured_types"]
    assert report["sample_level4_ids"] == ["2nd_waa_10201006"]
