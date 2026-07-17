"""Sexagenary-cycle constants and Joseon dynasty king-code mapping.

The 60 간지 (sexagenary) cycle pairs a 천간 (heavenly stem, 10) with a
지지 (earthly branch, 12); index ``i`` in 0..59 has stem ``i % 10`` and
branch ``i % 12``.
"""

# 천간 (heavenly stems)
GANJI = list("甲乙丙丁戊己庚辛壬癸")
# 지지 (earthly branches)
JIJI = list("子丑寅卯辰巳午未申酉戌亥")

# 60 간지 as Hanja strings, index 0 == 甲子 .. index 59 == 癸亥
SEXAGENARY = [GANJI[i % 10] + JIJI[i % 12] for i in range(60)]
SEXA_INDEX = {g: i for i, g in enumerate(SEXAGENARY)}

# Korean readings, useful for reports / Korean-tagged source data.
GANJI_KO = list("갑을병정무기경신임계")
JIJI_KO = list("자축인묘진사오미신유술해")
SEXAGENARY_KO = [GANJI_KO[i % 10] + JIJI_KO[i % 12] for i in range(60)]
SEXA_INDEX_KO = {g: i for i, g in enumerate(SEXAGENARY_KO)}


def sexa_index(ganji: str) -> int:
    """Return 0..59 index for a 2-char 간지 string (Hanja or Korean), else -1."""
    if ganji in SEXA_INDEX:
        return SEXA_INDEX[ganji]
    return SEXA_INDEX_KO.get(ganji, -1)


# 왕대코드 → 왕명.
# Bulk XML ids are ``2nd_w?a_...``; web-service ids are ``k?a_...``; the middle
# letter is the reign order (a, b, c, ...).
#
# WARNING (per design doc): this mapping is PROVISIONAL and includes guesses,
# especially the ordering of the supplementary/revised veritable records
# (선조수정 / 현종개수 / 숙종보궐 / 경종수정 ...). It MUST be corrected from the
# runtime probe (see sillok_pipeline.probe) before a full parse is trusted.
KING_CODES = {
    "a": "태조", "b": "정종", "c": "태종", "d": "세종", "e": "문종", "f": "단종",
    "g": "세조", "h": "예종", "i": "성종", "j": "연산군", "k": "중종", "l": "인종",
    "m": "명종", "n": "선조", "o": "선조수정", "p": "광해군중초", "q": "광해군정초",
    "r": "인조", "s": "효종", "t": "현종", "u": "현종개수", "v": "숙종",
    "w": "숙종보궐", "x": "경종", "y": "경종수정", "z": "영조",
}

# The <dateOccured type="..."> attribute values seen in history.dtd data.
# '간지' at the <level4> (day) node is the 일진 (day pillar) we care about.
DATE_TYPES = ("서기", "간지", "재위연도", "개국연호", "중국연호", "단기", "일본연호", "display")
