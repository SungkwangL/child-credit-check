"""Verification gate: recompute the 일진 from the calendar and cross-check
it against the 원문 태그.

Two independent computations must agree with the source tag for an article
to enter the statistics:

  1. JDN arithmetic  : lunar → solar (korean_lunar_calendar) → JDN → (mod 60)
  2. library day-pillar: korean_lunar_calendar's own 干支 string

Anchor calibration: 1900-01-01 (Gregorian) == 甲戌 (index 10). This is
internally consistent with the two documented reference points
1901-01-01 == 己卯 and 1902-01-01 == 甲申, and is re-confirmed at runtime
against korean_lunar_calendar via ``selfcheck_anchor``.
"""

from .constants import SEXAGENARY, SEXA_INDEX


def jdn_from_gregorian(y: int, m: int, d: int) -> int:
    """Julian Day Number for a proleptic-Gregorian calendar date."""
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def ganji_from_jdn(jdn: int, anchor_jdn: int, anchor_idx: int) -> int:
    """Sexagenary index (0..59) for a JDN, given a calibrated anchor."""
    return (anchor_idx + (jdn - anchor_jdn)) % 60


# Anchor: 1900-01-01 == 甲戌 (index 10).
ANCHOR_JDN = jdn_from_gregorian(1900, 1, 1)
ANCHOR_IDX = SEXA_INDEX["甲戌"]  # 10


def ganji_for_solar(y: int, m: int, d: int) -> str:
    """Day-pillar 간지 (Hanja) for a Gregorian date via JDN arithmetic."""
    idx = ganji_from_jdn(jdn_from_gregorian(y, m, d), ANCHOR_JDN, ANCHOR_IDX)
    return SEXAGENARY[idx]


def selfcheck_anchor() -> dict:
    """Re-confirm the anchor at runtime.

    Checks the two documented reference dates by pure arithmetic, and — if
    korean_lunar_calendar is installed — cross-checks 1900-01-01 against the
    library's own (independent) day-pillar computation.
    """
    result = {
        "anchor": "1900-01-01=甲戌",
        "ref_1901_01_01": ganji_for_solar(1901, 1, 1),   # expect 己卯
        "ref_1902_01_01": ganji_for_solar(1902, 1, 1),   # expect 甲申
        "arith_ok": ganji_for_solar(1901, 1, 1) == "己卯"
        and ganji_for_solar(1902, 1, 1) == "甲申",
        "library_ok": None,
    }
    try:
        from korean_lunar_calendar import KoreanLunarCalendar

        cal = KoreanLunarCalendar()
        cal.setSolarDate(1900, 1, 1)
        lib_day = cal.getChineseGapJaString().split()[-1][:-1]  # e.g. "甲戌日" -> "甲戌"
        result["library_1900_01_01"] = lib_day
        result["library_ok"] = (lib_day == "甲戌")
    except Exception as exc:  # library missing or API drift — arithmetic still stands
        result["library_error"] = repr(exc)
    return result


def verify_article(lunar_y: int, lunar_m: int, lunar_d: int, is_leap, ganji_raw: str):
    """Lunar date + source 간지 -> (verified, ganji_calc, solar_iso_or_reason).

    verified: 1 (JDN, library, and source all agree), 0 (mismatch), -1 (range error).
    """
    from korean_lunar_calendar import KoreanLunarCalendar

    cal = KoreanLunarCalendar()
    ok = cal.setLunarDate(lunar_y, lunar_m, lunar_d, bool(is_leap))
    if not ok:
        return -1, "", "range_error"
    iso = cal.SolarIsoFormat()               # 'YYYY-MM-DD'
    y, m, d = map(int, iso.split("-"))
    calc = ganji_for_solar(y, m, d)
    lib_gapja = cal.getChineseGapJaString().split()[-1][:-1]  # day pillar, 2 Hanja
    match = (calc == ganji_raw) and (lib_gapja == ganji_raw)
    return (1 if match else 0), calc, iso
