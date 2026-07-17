"""Chi-square goodness-of-fit of 간지 distributions vs. uniform.

Three strata per event type: 천간 (10), 지지 (12), 60간지. Multiple event
types x strata are tested, so Bonferroni-correct. Cells with expected count
< 5 make the 60간지 chi-square approximation unreliable — flagged LOW_POWER;
prefer the 천간/지지 strata as the primary conclusion.
"""

import sqlite3

import numpy as np
from scipy.stats import chisquare

from .classify import EVENT_LEXICON

LEVELS = ("cheongan", "jiji", "ganji")
_K = {"cheongan": 10, "jiji": 12, "ganji": 60}


def counts_for_event(con: sqlite3.Connection, event: str, level: str = "ganji"):
    rows = con.execute(
        "SELECT ganji_idx FROM articles WHERE verified=1 AND event_types LIKE ?",
        (f"%{event}%",),
    ).fetchall()
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
    obs, k = counts_for_event(con, event, level)
    N = int(obs.sum())
    if N == 0:
        return None
    exp = np.full(k, N / k)
    chi2, p = chisquare(obs, exp)                 # df = k - 1
    bonf = alpha / n_tests
    min_exp = N / k
    return {
        "event": event,
        "level": level,
        "N": N,
        "chi2": round(float(chi2), 2),
        "p": float(p),
        "sig": bool(p < bonf),
        "bonf_alpha": round(bonf, 5),
        "min_exp": round(min_exp, 2),
        "warn": "LOW_POWER(기대도수<5)" if min_exp < 5 else "",
    }


def run_all(dbpath: str = "sillok.db"):
    con = sqlite3.connect(dbpath)
    try:
        events = list(EVENT_LEXICON.keys())
        n_tests = len(events) * len(LEVELS)   # Bonferroni denominator
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
