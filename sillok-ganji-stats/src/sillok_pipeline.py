"""조선왕조실록 일진(일간지) 전수 추출 & 60간지 통계 검정 — 단일 모듈.

파서 · 사건분류 · 검증 게이트 · 통계를 한 파일에 담는다.

Stages (each gated; see README):
  1. download  — 벌크 XML from data.go.kr (scripts/download_data.sh, no crawling)
  2. probe     — 스키마 확정; 전수 파싱 전 THE GATE
  3. parse     — 전수 추출 → out/sillok.db
  4. verify    — JDN + korean_lunar_calendar 이중 교차검증 게이트
  5. stats     — 균등분포 대비 카이제곱 적합도, Bonferroni 보정

CLI:  python src/sillok_pipeline.py <selfcheck|download|probe|parse|verify|stats> ...
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import sqlite3
import sys
import time
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# 60간지 상수
# ---------------------------------------------------------------------------
GANJI = list("甲乙丙丁戊己庚辛壬癸")            # 천간
JIJI = list("子丑寅卯辰巳午未申酉戌亥")           # 지지
SEXAGENARY = [GANJI[i % 10] + JIJI[i % 12] for i in range(60)]
SEXA_INDEX = {g: i for i, g in enumerate(SEXAGENARY)}

GANJI_KO = list("갑을병정무기경신임계")
JIJI_KO = list("자축인묘진사오미신유술해")
SEXAGENARY_KO = [GANJI_KO[i % 10] + JIJI_KO[i % 12] for i in range(60)]
SEXA_INDEX_KO = {g: i for i, g in enumerate(SEXAGENARY_KO)}


def sexa_index(ganji: str) -> int:
    """0..59 index for a 2-char 간지 (Hanja or Korean), else -1."""
    if ganji in SEXA_INDEX:
        return SEXA_INDEX[ganji]
    return SEXA_INDEX_KO.get(ganji, -1)


# 왕대코드 → 왕명. 벌크 id는 2nd_w?a, 웹 id는 k?a; 가운데 글자가 순서(a,b,c...).
# WARNING (설계서): PROVISIONAL — 중복 실록(선조수정/현종개수/숙종보궐/경종수정)의
# 순서는 추측. probe로 progress/schema_probe.json에서 실측 교정할 것.
KING_CODES = {
    "a": "태조", "b": "정종", "c": "태종", "d": "세종", "e": "문종", "f": "단종",
    "g": "세조", "h": "예종", "i": "성종", "j": "연산군", "k": "중종", "l": "인종",
    "m": "명종", "n": "선조", "o": "선조수정", "p": "광해군중초", "q": "광해군정초",
    "r": "인조", "s": "효종", "t": "현종", "u": "현종개수", "v": "숙종",
    "w": "숙종보궐", "x": "경종", "y": "경종수정", "z": "영조",
}


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------
@dataclass
class Article:
    art_id: str
    king_code: str
    king: str
    reign_year: int
    month: int
    is_leap: int
    day: int
    ganji_raw: str          # 원문 일간지 (Hanja)
    ganji_idx: int          # 0..59, or -1
    title: str
    body: str
    solar_iso: str = ""     # raw <dateOccured type="서기"> attr, e.g. "1393-01-06L0"
    ganji_calc: str = ""
    verified: int = -1      # 1 pass, 0 mismatch, -1 unchecked
    event_types: str = ""


# ---------------------------------------------------------------------------
# 사건유형 분류
# ---------------------------------------------------------------------------
EVENT_LEXICON = {
    "붕어": ["훙", "薨", "昇遐", "승하", "崩", "붕어", "禮陟", "훙서", "薨逝"],
    "졸기": ["卒", "졸하", "졸기"],
    "처형": ["伏誅", "복주", "賜死", "사사", "斬", "참형", "梟首", "효수",
             "轘裂", "환열", "誅", "능지", "처참"],
    "재변": ["日食", "日蝕", "일식", "月食", "월식", "地震", "지진", "地動",
             "彗星", "혜성", "客星", "객성", "星變", "雷震", "벼락"],
    "즉위": ["卽位", "즉위", "禪位", "선위", "內禪", "내선", "受禪"],
    "반정": ["反正", "반정", "謀反", "모반", "靖難", "정난", "廢位", "폐위"],
}


def classify(title: str, body: str = "") -> list[str]:
    text = (title or "") + " " + (body or "")
    return [ev for ev, kws in EVENT_LEXICON.items() if any(k in text for k in kws)]


# ---------------------------------------------------------------------------
# 검증 산술 (JDN + 앵커)
# ---------------------------------------------------------------------------
def jdn_from_gregorian(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def ganji_from_jdn(jdn: int, anchor_jdn: int, anchor_idx: int) -> int:
    return (anchor_idx + (jdn - anchor_jdn)) % 60


# 앵커: 1900-01-01(양력) == 甲戌 (index 10). 1901-01-01=己卯, 1902-01-01=甲申과 일치.
ANCHOR_JDN = jdn_from_gregorian(1900, 1, 1)
ANCHOR_IDX = SEXA_INDEX["甲戌"]  # 10


def ganji_for_solar(y: int, m: int, d: int) -> str:
    return SEXAGENARY[ganji_from_jdn(jdn_from_gregorian(y, m, d), ANCHOR_JDN, ANCHOR_IDX)]


def selfcheck_anchor() -> dict:
    """앵커를 런타임에 재확인: 산술 + (설치 시) korean_lunar_calendar 독립 교차검증."""
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
        lib_day = cal.getChineseGapJaString().split()[-1][:-1]
        result["library_1900_01_01"] = lib_day
        result["library_ok"] = (lib_day == "甲戌")
    except Exception as exc:
        result["library_error"] = repr(exc)
    return result


def verify_article(lunar_y: int, lunar_m: int, lunar_d: int, is_leap, ganji_raw: str):
    """음력 date + 원문 간지 -> (verified, ganji_calc, iso|reason)."""
    from korean_lunar_calendar import KoreanLunarCalendar

    cal = KoreanLunarCalendar()
    if not cal.setLunarDate(lunar_y, lunar_m, lunar_d, bool(is_leap)):
        return -1, "", "range_error"
    iso = cal.SolarIsoFormat()
    y, m, d = map(int, iso.split("-"))
    calc = ganji_for_solar(y, m, d)
    lib_gapja = cal.getChineseGapJaString().split()[-1][:-1]
    match = (calc == ganji_raw) and (lib_gapja == ganji_raw)
    return (1 if match else 0), calc, iso


# ---------------------------------------------------------------------------
# 파서 (history.dtd)
# ---------------------------------------------------------------------------
# level4 id "waa_10201006" == 태조(a), section 1(본문; 부록 2/3/4), 재위년 02,
# 월 01, 윤 0, 일 06. 설계서 예시 kaa_10201006_001(태조 2년 1월 6일) 기준 디코드.
# NOTE(설계서): 자리수는 여전히 probe로 실데이터에서 재확인할 것.
_LV4_ID_RE = re.compile(r"([a-z])([a-z])a_(\d)(\d{2})(\d{2})(\d)(\d{2})")
_SOLAR_RE = re.compile(r"(\d+)-(\d+)-(\d+)L?(\d)?")


def parse_solar_attr(attr: str):
    """'1393-01-06L0' -> (y, m, d, is_leap). y-m-d는 원문의 음력 표기."""
    mm = _SOLAR_RE.match(attr or "")
    if not mm:
        return None
    return int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), int(mm.group(4) or 0)


def parse_bulk_xml(path: str) -> list[Article]:
    """history.dtd XML 1개에서 기사 리스트 추출."""
    from lxml import etree

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
        # m.group(3) == section digit(1=본문), 미사용
        reign_year, month, is_leap, day = (int(m.group(4)), int(m.group(5)),
                                           int(m.group(6)), int(m.group(7)))
        gidx = sexa_index(ganji_raw)

        for lv5 in lv4.iter("level5"):
            art_id = lv5.get("id", "")
            title_el = lv5.find(".//mainTitle")
            title = (title_el.text or "").strip() if title_el is not None else ""
            body = " ".join("".join(p.itertext()) for p in lv5.iter("paragraph"))
            out.append(Article(
                art_id=art_id, king_code=king_code,
                king=KING_CODES.get(king_code, "?"),
                reign_year=reign_year, month=month, is_leap=is_leap, day=day,
                ganji_raw=ganji_raw, ganji_idx=gidx,
                title=title, body=body, solar_iso=solar_attr))
    return out


# ---------------------------------------------------------------------------
# 프로브 (THE GATE)
# ---------------------------------------------------------------------------
def probe_bulk_structure(sample_xml: str, max_ids: int = 20) -> dict:
    from lxml import etree

    tree = etree.parse(sample_xml, etree.XMLParser(recover=True, huge_tree=True))
    ids, types, id_len_hist = [], set(), Counter()
    for lv4 in tree.iter("level4"):
        lid = lv4.get("id")
        if lid:
            clean = lid.replace("2nd_", "")
            ids.append(lid)
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
    files = sorted(glob.glob(os.path.join(xml_dir, "*.xml")))
    if not files:
        raise FileNotFoundError(f"no XML files under {xml_dir!r}")
    picks = files[:: max(1, len(files) // n_files)][:n_files] or files[:n_files]
    per_file = [probe_bulk_structure(f) for f in picks]
    king_letters = sorted(
        {os.path.basename(f).split("_")[1][1]
         for f in files
         if len(os.path.basename(f).split("_")) > 1
         and len(os.path.basename(f).split("_")[1]) >= 2})
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


# ---------------------------------------------------------------------------
# 저장소 (SQLite)
# ---------------------------------------------------------------------------
_SCHEMA = """CREATE TABLE IF NOT EXISTS articles(
  art_id TEXT PRIMARY KEY, king_code TEXT, king TEXT,
  reign_year INT, month INT, is_leap INT, day INT,
  ganji_raw TEXT, ganji_idx INT, title TEXT, body TEXT,
  solar_iso TEXT, ganji_calc TEXT, verified INT, event_types TEXT)"""


def init_db(dbpath: str = "out/sillok.db") -> sqlite3.Connection:
    os.makedirs(os.path.dirname(dbpath) or ".", exist_ok=True)
    con = sqlite3.connect(dbpath)
    con.execute(_SCHEMA)
    con.execute("CREATE INDEX IF NOT EXISTS idx_event ON articles(event_types)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_verified ON articles(verified)")
    con.commit()
    return con


def save(con: sqlite3.Connection, arts: list[Article]) -> None:
    con.executemany(
        """INSERT OR REPLACE INTO articles VALUES
        (:art_id,:king_code,:king,:reign_year,:month,:is_leap,:day,
         :ganji_raw,:ganji_idx,:title,:body,:solar_iso,:ganji_calc,:verified,:event_types)""",
        [asdict(a) for a in arts])
    con.commit()


# ---------------------------------------------------------------------------
# 전수 파싱 / 검증 패스 (프로브 게이트 통과 후에만)
# ---------------------------------------------------------------------------
def run_bulk(xml_dir: str, dbpath: str = "out/sillok.db") -> int:
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


def run_verify(dbpath: str = "out/sillok.db") -> dict:
    con = init_db(dbpath)
    rows = con.execute("SELECT art_id, solar_iso, ganji_raw FROM articles").fetchall()
    stats = {"total": 0, "verified": 0, "mismatch": 0, "range_error": 0, "no_date": 0}
    for art_id, solar_iso, ganji_raw in rows:
        stats["total"] += 1
        parsed = parse_solar_attr(solar_iso)
        if not parsed or not ganji_raw:
            stats["no_date"] += 1
            continue
        y, m, d, is_leap = parsed
        v, calc, _ = verify_article(y, m, d, is_leap, ganji_raw)
        con.execute("UPDATE articles SET verified=?, ganji_calc=? WHERE art_id=?",
                    (v, calc, art_id))
        stats["verified" if v == 1 else "mismatch" if v == 0 else "range_error"] += 1
    con.commit()
    con.close()
    passrate = stats["verified"] / stats["total"] if stats["total"] else 0.0
    stats["pass_rate"] = round(passrate, 4)
    print("verification:", stats)
    if stats["total"] and passrate < 0.98:
        print("WARNING: pass rate < 98% — suspect id-width / leap-month parsing; "
              "re-run the probe before trusting statistics.")
    return stats


# ---------------------------------------------------------------------------
# 통계 (카이제곱 적합도, Bonferroni)
# ---------------------------------------------------------------------------
LEVELS = ("cheongan", "jiji", "ganji")
_K = {"cheongan": 10, "jiji": 12, "ganji": 60}


def counts_for_event(con: sqlite3.Connection, event: str, level: str = "ganji"):
    import numpy as np

    rows = con.execute(
        "SELECT ganji_idx FROM articles WHERE verified=1 AND event_types LIKE ?",
        (f"%{event}%",)).fetchall()
    idxs = [r[0] for r in rows if r[0] is not None and r[0] >= 0]
    if level == "ganji":
        obs = np.bincount(idxs, minlength=60)
    elif level == "cheongan":
        obs = np.bincount([i % 10 for i in idxs], minlength=10)
    elif level == "jiji":
        obs = np.bincount([i % 12 for i in idxs], minlength=12)
    else:
        raise ValueError(f"unknown level {level!r}")
    return obs, _K[level]


def test_event(con, event: str, level: str, alpha: float = 0.05, n_tests: int = 1):
    import numpy as np
    from scipy.stats import chisquare

    obs, k = counts_for_event(con, event, level)
    N = int(obs.sum())
    if N == 0:
        return None
    exp = np.full(k, N / k)
    chi2, p = chisquare(obs, exp)            # df = k - 1
    bonf = alpha / n_tests
    min_exp = N / k
    return {
        "event": event, "level": level, "N": N,
        "chi2": round(float(chi2), 2), "p": float(p),
        "sig": bool(p < bonf), "bonf_alpha": round(bonf, 5),
        "min_exp": round(min_exp, 2),
        "warn": "LOW_POWER(기대도수<5)" if min_exp < 5 else "",
    }


def run_all(dbpath: str = "out/sillok.db"):
    con = sqlite3.connect(dbpath)
    try:
        events = list(EVENT_LEXICON.keys())
        n_tests = len(events) * len(LEVELS)
        results = []
        for ev in events:
            for lv in LEVELS:
                r = test_event(con, ev, lv, n_tests=n_tests)
                if r:
                    results.append(r)
        for r in sorted(results, key=lambda x: x["p"]):
            print(r)
        return results
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 다운로드 / 언집 (primary: scripts/download_data.sh)
# ---------------------------------------------------------------------------
DATASET_PAGE = "https://www.data.go.kr/data/15053647/fileData.do"
DATASET_PAGE_GOJONG = "https://www.data.go.kr/data/15053646/fileData.do"


def unzip(zip_path: str, dest: str = "data") -> int:
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        zf.extractall(dest)
    xml = [m for m in members if m.lower().endswith(".xml")]
    print(f"extracted {len(members)} entries ({len(xml)} xml) -> {dest}/")
    return len(xml)


def download(url: str, dest_zip: str, tries: int = 4) -> str:
    import requests

    ca = os.environ.get("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
    last = None
    for t in range(tries):
        try:
            with requests.get(url, stream=True, timeout=60,
                              verify=ca if os.path.exists(ca) else True) as r:
                r.raise_for_status()
                with open(dest_zip, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            print(f"downloaded {url} -> {dest_zip} ({os.path.getsize(dest_zip):,} bytes)")
            return dest_zip
        except Exception as exc:
            last = exc
            wait = 2 ** t
            print(f"[try {t + 1}/{tries}] failed: {exc!r}; retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError(
        f"could not download {url!r}: {last!r}. If the host is blocked by egress "
        f"policy, stage the zip manually. Portal: {DATASET_PAGE}")


def run_download(urls=None, dest_zip="data/sillok_raw_xml.zip", dest_dir="data"):
    os.makedirs(dest_dir, exist_ok=True)
    if not urls:
        env = os.environ.get("SILLOK_BULK_URL", "")
        urls = [u for u in env.replace(",", " ").split() if u]
    if not urls:
        raise SystemExit(
            f"No download URL. Set SILLOK_BULK_URL or use scripts/download_data.sh, "
            f"or stage a zip and use --zip. Source: {DATASET_PAGE}")
    total = 0
    for i, url in enumerate(urls):
        z = dest_zip if len(urls) == 1 else f"{dest_zip}.{i}"
        download(url, z)
        total += unzip(z, dest_dir)
    print(f"total xml files staged: {total}")
    return total


# ---------------------------------------------------------------------------
# 크롤러 폴백 (개별 기사 대조 전용; robots.txt 재확인 + 1~2s 예절)
# ---------------------------------------------------------------------------
CRAWL_BASE = "https://sillok.history.go.kr/id/"
CRAWL_HEADERS = {"User-Agent": "research-bot/1.0 (contact: set-me@example.com)"}


def polite_get(url: str, tries: int = 4):
    import requests

    for t in range(tries):
        try:
            r = requests.get(url, headers=CRAWL_HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 ** t + random.uniform(0.5, 1.5))
    return None


def parse_article_html(html: str):
    """(간지, title, body). DOM 셀렉터는 PROVISIONAL — 실페이지로 확정할 것."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    header = soup.find(string=re.compile(r"\d+년 \d+월 \d+일"))
    ganji = None
    if header:
        mm = re.search(r"\d+일\s*([甲-癸][子-亥]|[가-힣]{2})", header)
        if mm:
            ganji = mm.group(1)
    title_el = soup.select_one("h2, .ins_view_tit, .title")
    title = title_el.get_text(strip=True) if title_el else ""
    body_el = soup.select_one(".ins_view_pd, .paragraph, #cont_view")
    body = body_el.get_text(" ", strip=True) if body_el else ""
    return ganji, title, body


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _gate_ok(probe_path: str) -> bool:
    if not os.path.exists(probe_path):
        return False
    try:
        with open(probe_path, encoding="utf-8") as fh:
            return bool(json.load(fh).get("gate_passed"))
    except Exception:
        return False


def main(argv=None):
    p = argparse.ArgumentParser(prog="sillok_pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selfcheck", help="간지 앵커 캘리브레이션 재확인")

    d = sub.add_parser("download", help="stage 1: 벌크 XML 다운로드+해제")
    d.add_argument("--url", nargs="*", default=None)
    d.add_argument("--zip", default=None)
    d.add_argument("--dir", default="data")

    pr = sub.add_parser("probe", help="stage 2 (GATE): 스키마 확정")
    pr.add_argument("--dir", default="data")
    pr.add_argument("--out", default="progress/schema_probe.json")

    pa = sub.add_parser("parse", help="stage 3: 전수 파싱 (게이트 필요)")
    pa.add_argument("--dir", default="data")
    pa.add_argument("--db", default="out/sillok.db")
    pa.add_argument("--probe", default="progress/schema_probe.json")
    pa.add_argument("--force", action="store_true")

    ve = sub.add_parser("verify", help="stage 4: 검증 게이트")
    ve.add_argument("--db", default="out/sillok.db")

    st = sub.add_parser("stats", help="stage 5: 카이제곱 검정")
    st.add_argument("--db", default="out/sillok.db")

    args = p.parse_args(argv)

    if args.cmd == "selfcheck":
        print(json.dumps(selfcheck_anchor(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "download":
        if args.zip:
            unzip(args.zip, args.dir)
        else:
            run_download(urls=args.url, dest_dir=args.dir)
        return 0
    if args.cmd == "probe":
        report = probe_dir(args.dir, out_path=args.out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("\nGATE:", "PASSED" if report["gate_passed"] else "NOT PASSED")
        return 0 if report["gate_passed"] else 2
    if args.cmd == "parse":
        if not args.force and not _gate_ok(args.probe):
            print(f"REFUSING to parse: probe gate not passed ({args.probe}). "
                  f"Run `probe` first (or --force).", file=sys.stderr)
            return 2
        run_bulk(args.dir, args.db)
        return 0
    if args.cmd == "verify":
        run_verify(args.db)
        return 0
    if args.cmd == "stats":
        run_all(args.db)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
