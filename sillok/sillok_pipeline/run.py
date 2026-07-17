"""Full-parse and verification passes (run only AFTER the probe gate passes)."""

import glob
import os

from .classify import classify
from .db import init_db, save
from .parse import parse_bulk_xml, parse_solar_attr
from .verify import verify_article


def run_bulk(xml_dir: str, dbpath: str = "sillok.db") -> int:
    """Parse every XML file in ``xml_dir`` into the DB, with event tags."""
    con = init_db(dbpath)
    files = sorted(glob.glob(os.path.join(xml_dir, "*.xml")))
    if not files:
        raise FileNotFoundError(f"no XML under {xml_dir!r}")
    total = 0
    for i, f in enumerate(files):
        arts = parse_bulk_xml(f)
        for a in arts:
            a.event_types = ",".join(classify(a.title, a.body))
        save(con, arts)
        total += len(arts)
        print(f"[{i + 1}/{len(files)}] {os.path.basename(f)} -> "
              f"{len(arts)} arts (cumulative {total})")
    con.close()
    print("total articles (measured):", total)
    return total


def run_verify(dbpath: str = "sillok.db") -> dict:
    """Apply the verification gate to every stored article; update rows.

    Uses the LUNAR date parsed from the <dateOccured type='서기'> attr
    (design-doc recommendation) rather than re-deriving from the reign year.
    """
    con = init_db(dbpath)
    rows = con.execute(
        "SELECT art_id, solar_iso, ganji_raw FROM articles"
    ).fetchall()
    stats = {"total": 0, "verified": 0, "mismatch": 0, "range_error": 0, "no_date": 0}
    for art_id, solar_iso, ganji_raw in rows:
        stats["total"] += 1
        parsed = parse_solar_attr(solar_iso)
        if not parsed or not ganji_raw:
            stats["no_date"] += 1
            continue
        y, m, d, is_leap = parsed
        v, calc, iso = verify_article(y, m, d, is_leap, ganji_raw)
        con.execute(
            "UPDATE articles SET verified=?, ganji_calc=? WHERE art_id=?",
            (v, calc, art_id),
        )
        if v == 1:
            stats["verified"] += 1
        elif v == 0:
            stats["mismatch"] += 1
        else:
            stats["range_error"] += 1
    con.commit()
    con.close()
    passrate = stats["verified"] / stats["total"] if stats["total"] else 0.0
    stats["pass_rate"] = round(passrate, 4)
    print("verification:", stats)
    if stats["total"] and passrate < 0.98:
        print("WARNING: pass rate < 98% — suspect id-width / leap-month parsing; "
              "re-run the probe before trusting statistics.")
    return stats
