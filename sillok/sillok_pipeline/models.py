"""Data model for a single 실록 article (기사)."""

from dataclasses import dataclass, field, asdict

__all__ = ["Article", "asdict"]


@dataclass
class Article:
    art_id: str
    king_code: str
    king: str
    reign_year: int
    month: int
    is_leap: int
    day: int
    ganji_raw: str          # 원문 일간지 (Hanja, from <dateOccured type="간지">)
    ganji_idx: int          # 0..59, or -1 if unparseable
    title: str
    body: str
    solar_iso: str = ""     # raw <dateOccured type="서기"> date attr, e.g. "1393-01-06L0"
    ganji_calc: str = ""    # 간지 recomputed from the calendar during verification
    verified: int = -1      # 1 = passed gate, 0 = mismatch, -1 = not yet checked
    event_types: str = ""   # comma-joined event labels from the classifier
