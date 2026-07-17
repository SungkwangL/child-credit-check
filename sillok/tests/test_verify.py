"""Network-independent tests for the 간지 arithmetic and verification gate."""

import pytest

from sillok_pipeline.constants import SEXAGENARY, SEXA_INDEX, sexa_index
from sillok_pipeline.verify import (
    ANCHOR_IDX,
    ganji_for_solar,
    jdn_from_gregorian,
    selfcheck_anchor,
)


def test_sexagenary_cycle_shape():
    assert len(SEXAGENARY) == 60
    assert SEXAGENARY[0] == "甲子"
    assert SEXAGENARY[59] == "癸亥"
    assert SEXA_INDEX["甲戌"] == 10
    # each entry is a valid stem+branch pair
    assert len(set(SEXAGENARY)) == 60


def test_sexa_index_korean_and_hanja():
    assert sexa_index("甲子") == 0
    assert sexa_index("갑자") == 0
    assert sexa_index("계해") == 59
    assert sexa_index("??") == -1


def test_jdn_known_values():
    # 2000-01-01 Gregorian == JDN 2451545 (well-known epoch reference)
    assert jdn_from_gregorian(2000, 1, 1) == 2451545


def test_anchor_calibration():
    assert ANCHOR_IDX == 10  # 甲戌
    # documented reference day-pillars, reproduced by pure arithmetic
    assert ganji_for_solar(1901, 1, 1) == "己卯"
    assert ganji_for_solar(1902, 1, 1) == "甲申"


def test_daily_cycle_increments_by_one():
    # consecutive days advance the sexagenary index by exactly 1 (mod 60)
    a = ganji_for_solar(1900, 1, 1)
    b = ganji_for_solar(1900, 1, 2)
    ia, ib = SEXA_INDEX[a], SEXA_INDEX[b]
    assert (ia + 1) % 60 == ib


def test_selfcheck_arithmetic_passes():
    r = selfcheck_anchor()
    assert r["arith_ok"] is True


korean_lunar = pytest.importorskip("korean_lunar_calendar")


def test_library_cross_check_agrees_with_anchor():
    # KLC computes the day pillar independently; it must agree at the anchor.
    r = selfcheck_anchor()
    assert r.get("library_ok") is True, r
    assert r.get("library_1900_01_01") == "甲戌"


def test_verify_article_roundtrip():
    from sillok_pipeline.verify import verify_article
    from korean_lunar_calendar import KoreanLunarCalendar

    # take a real lunar date, ask KLC for its true day pillar, then confirm the
    # gate returns verified=1 when the source 간지 matches, 0 when it doesn't.
    cal = KoreanLunarCalendar()
    cal.setLunarDate(1450, 2, 17, False)
    true_ganji = cal.getChineseGapJaString().split()[-1][:-1]

    v_ok, calc, iso = verify_article(1450, 2, 17, 0, true_ganji)
    assert v_ok == 1
    assert calc == true_ganji

    wrong = SEXAGENARY[(SEXA_INDEX[true_ganji] + 1) % 60]
    v_bad, _, _ = verify_article(1450, 2, 17, 0, wrong)
    assert v_bad == 0
