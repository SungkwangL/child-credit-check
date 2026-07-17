"""Stage-1 bulk download + unzip (reproducibility, no crawling).

Primary source: 공공데이터포털 (data.go.kr) dataset 15053647 — the full 실록
원문 XML (태조~철종), licence "이용허락범위 제한 없음". Gojong/Sunjong is a
separate dataset (15053646). These files are hundreds of MB and are NEVER
committed (see .gitignore); this script reproduces them from the portal.

The portal's file-data download typically requires going through the dataset
page. Provide the resolved download URL(s) via the ``SILLOK_BULK_URL`` env var
(space/comma separated) or ``--url``. A locally staged zip can be passed with
``--zip`` to skip the network entirely.
"""

import os
import zipfile

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
    """Download a bulk zip with exponential-backoff retries.

    Uses requests; TLS goes through the session proxy which trusts the
    pre-configured CA bundle. Raises on repeated failure.
    """
    import time
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
            print(f"downloaded {url} -> {dest_zip} "
                  f"({os.path.getsize(dest_zip):,} bytes)")
            return dest_zip
        except Exception as exc:  # network / policy error
            last = exc
            wait = 2 ** t
            print(f"[try {t + 1}/{tries}] failed: {exc!r}; retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(
        f"could not download {url!r}: {last!r}. If the host is blocked by the "
        f"egress policy, stage the zip manually and pass it with --zip. "
        f"Portal pages: {DATASET_PAGE} / {DATASET_PAGE_GOJONG}"
    )


def run_download(urls=None, dest_zip="data/sillok_raw_xml.zip", dest_dir="data"):
    os.makedirs(dest_dir, exist_ok=True)
    if not urls:
        env = os.environ.get("SILLOK_BULK_URL", "")
        urls = [u for u in env.replace(",", " ").split() if u]
    if not urls:
        raise SystemExit(
            "No download URL. Set SILLOK_BULK_URL or pass --url, or stage a zip "
            f"and use --zip. Get the file from {DATASET_PAGE}"
        )
    total = 0
    for i, url in enumerate(urls):
        z = dest_zip if len(urls) == 1 else f"{dest_zip}.{i}"
        download(url, z)
        total += unzip(z, dest_dir)
    print(f"total xml files staged: {total}")
    return total
