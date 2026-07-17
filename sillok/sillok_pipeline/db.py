"""SQLite persistence for parsed articles."""

import sqlite3

from .models import Article, asdict

_SCHEMA = """CREATE TABLE IF NOT EXISTS articles(
  art_id TEXT PRIMARY KEY, king_code TEXT, king TEXT,
  reign_year INT, month INT, is_leap INT, day INT,
  ganji_raw TEXT, ganji_idx INT, title TEXT, body TEXT,
  solar_iso TEXT, ganji_calc TEXT, verified INT, event_types TEXT)"""


def init_db(dbpath: str = "sillok.db") -> sqlite3.Connection:
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
        [asdict(a) for a in arts],
    )
    con.commit()
