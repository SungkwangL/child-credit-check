"""Network-independent tests for sillok_pipeline (single module in src/)."""

import os

import pytest

import sillok_pipeline as sp

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "history_sample.xml")


# --------------------------- 60간지 산술 & 앵커 ---------------------------
def test_sexagenary_cycle_shape():
    assert len(sp.SEXAGENARY) == 60
    assert sp.SEXAGENARY[0] == "甲子"
    assert sp.SEXAGENARY[59] == "癸亥"
    assert sp.SEXA_INDEX["甲戌"] == 10
    assert len(set(sp.SEXAGENARY)) == 60


def test_sexa_index_korean_and_hanja():
    assert sp.sexa_index("甲子") == 0
    assert sp.sexa_index("갑자") == 0
    assert sp.sexa_index("계해") == 59
    assert sp.sexa_index("??") == -1


def test_jdn_known_value():
    assert sp.jdn_from_gregorian(2000, 1, 1) == 2451545  # well-known JDN epoch


def test_anchor_calibration():
    assert sp.ANCHOR_IDX == 10  # 甲戌
    assert sp.ganji_for_solar(1901, 1, 1) == "己卯"
    assert sp.ganji_for_solar(1902, 1, 1) == "甲申"


def test_daily_cycle_increments_by_one():
    a, b = sp.ganji_for_solar(1900, 1, 1), sp.ganji_for_solar(1900, 1, 2)
    assert (sp.SEXA_INDEX[a] + 1) % 60 == sp.SEXA_INDEX[b]


def test_selfcheck_arithmetic():
    assert sp.selfcheck_anchor()["arith_ok"] is True


# --------------------------- 사건분류 ---------------------------
def test_classify_title_based():
    # 제목(국역) 기반. 한문 본문은 무시(오탐 방지).
    assert sp.classify("영의정 아무개가 졸하다") == ["졸기"]
    assert "재변" in sp.classify("지진이 있었다")
    out = sp.classify("반정으로 즉위하다")
    assert "반정" in out and "즉위" in out
    assert sp.classify("경연을 열다") == []
    # 실제 태조 즉위 제목 — 붕어/처형 오탐 없이 즉위만
    assert sp.classify("태조가 백관의 추대를 받아 수창궁에서 왕위에 오르다") == ["즉위"]
    # 본문에 卒/崩 이 있어도 제목만 보므로 무시
    assert sp.classify("경연을 열다", "領議政 卒. 上崩.") == []


# --------------------------- 파서 ---------------------------
def test_parse_solar_attr():
    assert sp.parse_solar_attr("1393-01-06L0") == (1393, 1, 6, 0)
    assert sp.parse_solar_attr("1393-01-06L1") == (1393, 1, 6, 1)
    assert sp.parse_solar_attr("") is None


def test_parse_bulk_xml_fixture():
    pytest.importorskip("lxml")
    arts = sp.parse_bulk_xml(FIXTURE)
    assert len(arts) == 2
    a0 = arts[0]
    assert (a0.king_code, a0.king) == ("a", "태조")
    assert (a0.reign_year, a0.month, a0.is_leap, a0.day) == (1, 7, 0, 17)
    assert a0.ganji_raw == "丙申"          # day pillar, NOT year pillar (壬申)
    assert a0.ganji_idx == 32
    assert a0.solar_iso == "1392-07-17L0"
    assert a0.title == "영의정 아무개가 졸하다"  # title/mainTitle, not source/mainTitle
    assert "卒" in a0.body


def test_day_pillar_not_confused_with_year_pillar():
    pytest.importorskip("lxml")
    arts = sp.parse_bulk_xml(FIXTURE)
    assert all(a.ganji_raw == "丙申" for a in arts)  # never the 壬申 year pillar


def test_probe_reports_ganji_type():
    pytest.importorskip("lxml")
    report = sp.probe_bulk_structure(FIXTURE)
    assert report["has_ganji_type"] is True
    assert report["has_days"] is True
    assert "서기" in report["dateOccured_types"]
    assert report["sample_level4_ids"] == ["waa_10107017"]


def test_verify_real_historical_date():
    # 태조 1년 7월 17일(음력) 원문 간지 丙申 — JDN·라이브러리 모두 일치해야 함
    pytest.importorskip("korean_lunar_calendar")
    v, calc, iso = sp.verify_article(1392, 7, 17, 0, "丙申")
    assert v == 1 and calc == "丙申" and iso == "1392-08-13"


def test_verify_leap_month_date():
    # 윤달(태조 1년 윤12월 4일=庚辰): KLC가 문자열 끝에 ' (閏月)'을 붙이는데도
    # 일주 추출이 견고해야 함(회귀 방지).
    pytest.importorskip("korean_lunar_calendar")
    v, calc, _ = sp.verify_article(1392, 12, 4, 1, "庚辰")
    assert v == 1 and calc == "庚辰"


# --------------------------- 검증 게이트 (라이브러리 필요) ---------------------------
korean_lunar = pytest.importorskip("korean_lunar_calendar")


def test_library_cross_check():
    r = sp.selfcheck_anchor()
    assert r.get("library_ok") is True, r
    assert r.get("library_1900_01_01") == "甲戌"


def test_verify_article_roundtrip():
    from korean_lunar_calendar import KoreanLunarCalendar

    cal = KoreanLunarCalendar()
    cal.setLunarDate(1450, 2, 17, False)
    true_ganji = cal.getChineseGapJaString().split()[-1][:-1]

    v_ok, calc, _ = sp.verify_article(1450, 2, 17, 0, true_ganji)
    assert v_ok == 1 and calc == true_ganji

    wrong = sp.SEXAGENARY[(sp.SEXA_INDEX[true_ganji] + 1) % 60]
    v_bad, _, _ = sp.verify_article(1450, 2, 17, 0, wrong)
    assert v_bad == 0
