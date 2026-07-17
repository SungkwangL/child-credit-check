"""Runtime structure probe — THE GATE.

Per the design doc's absolute rule: do NOT run a full parse until the probe
has confirmed the level4-id digit widths, the presence of the 간지 date type,
and the real 왕대코드 mapping. This module inspects a small sample of the bulk
XML and writes the findings to progress/schema_probe.json, which is then used
to correct the PROVISIONAL parts of the code (the level4-id regex and
KING_CODES).
"""

import glob
import json
import os
from collections import Counter

from lxml import etree

from .verify import selfcheck_anchor


def probe_bulk_structure(sample_xml: str, max_ids: int = 20) -> dict:
    """Inspect one bulk XML file: level4 id shapes and dateOccured types."""
    tree = etree.parse(sample_xml, etree.XMLParser(recover=True, huge_tree=True))
    ids, types = [], set()
    id_len_hist = Counter()
    for lv4 in tree.iter("level4"):
        lid = lv4.get("id")
        if lid:
            clean = lid.replace("2nd_", "")
            ids.append(lid)
            # digits after the "w?a_" / "k?a_" prefix
            tail = clean.split("_", 1)[-1] if "_" in clean else clean
            id_len_hist[len(tail)] += 1
        for d in lv4.findall(".//dateOccured"):
            if d.get("type"):
                types.add(d.get("type"))
        if len(ids) >= max_ids:
            break
    return {
        "file": os.path.basename(sample_xml),
        "sample_level4_ids": ids,
        "id_tail_digit_widths": dict(id_len_hist),
        "dateOccured_types": sorted(types),
        "has_ganji_type": "간지" in types,
    }


def probe_dir(xml_dir: str, out_path: str = "progress/schema_probe.json",
              n_files: int = 5) -> dict:
    """Probe several files across the corpus and persist the merged report.

    Also records the king-code letters actually seen (from file names) and the
    anchor self-check, so the PROVISIONAL parts of the code can be corrected.
    """
    files = sorted(glob.glob(os.path.join(xml_dir, "*.xml")))
    if not files:
        raise FileNotFoundError(f"no XML files under {xml_dir!r}")

    # spread the sample across the corpus (start, middle, end reigns)
    picks = files[:: max(1, len(files) // n_files)][:n_files] or files[:n_files]

    per_file = [probe_bulk_structure(f) for f in picks]

    king_letters = sorted(
        {os.path.basename(f).split("_")[1][1]
         for f in files
         if len(os.path.basename(f).split("_")) > 1
         and len(os.path.basename(f).split("_")[1]) >= 2}
    )

    report = {
        "n_files_total": len(files),
        "n_files_probed": len(picks),
        "king_code_letters_seen": king_letters,
        "anchor_selfcheck": selfcheck_anchor(),
        "per_file": per_file,
        "gate_passed": all(p["has_ganji_type"] for p in per_file),
    }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    return report
