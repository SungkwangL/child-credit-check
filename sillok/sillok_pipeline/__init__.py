"""조선왕조실록 일진(일간지) 전수 추출 & 60간지 통계 검정 파이프라인.

Stages (each gated; see README):
  1. download  — bulk XML from data.go.kr (no crawling)
  2. probe     — confirm schema; THE GATE before any full parse
  3. parse     — full extraction into SQLite
  4. verify    — JDN + korean_lunar_calendar cross-check gate
  5. stats     — chi-square goodness-of-fit vs uniform, Bonferroni-corrected
"""

__version__ = "0.1.0"
