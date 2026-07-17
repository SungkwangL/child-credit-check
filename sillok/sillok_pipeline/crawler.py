"""Crawler FALLBACK — for individual-article verification only.

Prefer the bulk XML (download.py). Use this only to cross-check specific
articles the bulk cannot supply. sillok.history.go.kr has historically served
``User-agent: * / Disallow: /`` and blocks automated access to /id/ pages;
re-check robots.txt and honour a 1-2s request interval before any use.

DOM selectors below are PROVISIONAL — confirm them with a runtime fetch of one
real page before relying on parse_article_html.
"""

import json
import os
import random
import re
import time

BASE = "https://sillok.history.go.kr/id/"
HEADERS = {"User-Agent": "research-bot/1.0 (contact: set-me@example.com)"}
CKPT = "crawl_ckpt.json"


def polite_get(url: str, tries: int = 4):
    import requests

    for t in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 ** t + random.uniform(0.5, 1.5))  # exponential backoff
    return None


def parse_article_html(html: str):
    """(간지, title, body) from a web article page. Selectors PROVISIONAL."""
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


def crawl(id_list, sink=None):
    """Fetch each id politely, resumably. ``sink(aid, ganji, title, body)`` is
    called per fetched article; supply it to persist."""
    done = set(json.load(open(CKPT))) if os.path.exists(CKPT) else set()
    for i, aid in enumerate(id_list):
        if aid in done:
            continue
        html = polite_get(BASE + aid)
        if html:
            ganji, title, body = parse_article_html(html)
            if sink:
                sink(aid, ganji, title, body)
            done.add(aid)
        if i % 25 == 0:
            json.dump(list(done), open(CKPT, "w"))
        time.sleep(random.uniform(1.0, 2.0))  # 1-2s courtesy interval
    json.dump(list(done), open(CKPT, "w"))
    return done
