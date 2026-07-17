"""Bulk XML parser for the history.dtd hierarchy.

Hierarchy: level1 (왕대) > level2 (재위년) > level3 (월) > level4 (일)
           > level5 (기사) > level6.

The 일진 (day pillar) lives at <level4>/.../<dateOccured type="간지">. The
level2/level3 nodes also carry 간지 attributes (year/month pillars) — those
must NOT be mixed in.
"""

import re

from lxml import etree

from .constants import KING_CODES, sexa_index
from .models import Article

# level4 id like "waa_10201006" == 태조(a), section 1 (본문; appendices use
# 2/3/4, mirroring the _200/_300 file convention), reign-yr 02, month 01,
# leap 0, day 06. Decoded from the design doc's documented example
# (kaa_10201006_001 == 태조 2년 1월 6일).
# NOTE (per design doc): still confirm the digit widths from
# progress/schema_probe.json against real data before a trusted full parse.
_LV4_ID_RE = re.compile(r"([a-z])([a-z])a_(\d)(\d{2})(\d{2})(\d)(\d{2})")

_SOLAR_RE = re.compile(r"(\d+)-(\d+)-(\d+)L?(\d)?")


def parse_solar_attr(attr: str):
    """'1393-01-06L0' -> (y, m, d, is_leap). NOTE: y-m-d here is the LUNAR
    date as printed in the record, with L-suffix marking the leap month."""
    mm = _SOLAR_RE.match(attr or "")
    if not mm:
        return None
    return int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), int(mm.group(4) or 0)


def parse_bulk_xml(path: str) -> list[Article]:
    """Extract all articles from one history.dtd XML file."""
    out: list[Article] = []
    tree = etree.parse(path, etree.XMLParser(recover=True, huge_tree=True))
    root = tree.getroot()

    for lv4 in root.iter("level4"):
        ganji_raw, solar_attr = "", ""
        date_el = lv4.find(".//date")
        if date_el is None:
            continue
        for d in date_el.findall("dateOccured"):
            t = d.get("type")
            if t == "간지":
                ganji_raw = (d.text or "").strip()
            elif t == "서기":
                solar_attr = d.get("date", "")

        lv4id = (lv4.get("id") or "").replace("2nd_", "")
        m = _LV4_ID_RE.match(lv4id)
        if not m:
            continue
        king_code = m.group(2)
        # m.group(3) == section digit (1 = 본문), not needed downstream
        reign_year = int(m.group(4))
        month = int(m.group(5))
        is_leap = int(m.group(6))
        day = int(m.group(7))

        gidx = sexa_index(ganji_raw)

        for lv5 in lv4.iter("level5"):
            art_id = lv5.get("id", "")
            title_el = lv5.find(".//mainTitle")
            title = (title_el.text or "").strip() if title_el is not None else ""
            body = " ".join("".join(p.itertext()) for p in lv5.iter("paragraph"))
            out.append(
                Article(
                    art_id=art_id,
                    king_code=king_code,
                    king=KING_CODES.get(king_code, "?"),
                    reign_year=reign_year,
                    month=month,
                    is_leap=is_leap,
                    day=day,
                    ganji_raw=ganji_raw,
                    ganji_idx=gidx,
                    title=title,
                    body=body,
                    solar_iso=solar_attr,
                )
            )
    return out
