"""Collect council local laws listed in local_laws.yaml (URLs and/or local files)."""
import hashlib
import json
import re
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

import requests
import yaml
from pypdf import PdfReader

USER_AGENT = "lacuna-au/0.1 (law reform research tool)"
MIN_CHARS = 500  # less text than this usually means a scanned PDF (needs OCR) or a bad link


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section"}

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        self._skip += tag in self.SKIP
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        self._skip -= tag in self.SKIP and self._skip > 0
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def pdf_to_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()


def bytes_to_text(data: bytes, hint: str = "") -> str:
    if data[:5] == b"%PDF-" or hint.lower().endswith(".pdf"):
        return pdf_to_text(data)
    if hint.lower().endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    return html_to_text(data.decode("utf-8", errors="replace"))


def _fetch(url: str, cache_dir: Path) -> bytes:
    cache = cache_dir / hashlib.sha1(url.encode()).hexdigest()
    if cache.exists():
        return cache.read_bytes()
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    cache.write_bytes(r.content)
    return r.content


def _record(council: dict, title: str, url: str, text: str) -> dict:
    state = council.get("state", "")
    return {
        "id": "local::" + hashlib.sha1(f"{council['name']}|{title}|{url}".encode()).hexdigest()[:16],
        "citation": f"{title} ({council['name']})",
        "type": "local_law",
        "jurisdiction": f"{state} / {council['name']}" if state else council["name"],
        "url": url,
        "date": "",
        "text": text,
    }


def collect_local_laws(cfg: dict, list_path: str = "local_laws.yaml") -> Path | None:
    path = Path(list_path)
    if not path.exists():
        print(f"{list_path} not found - copy local_laws.example.yaml to {list_path} and fill it in.")
        return None
    councils = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("councils") or []
    data_dir = Path(cfg["paths"]["data_dir"])
    cache_dir = data_dir / "local_laws_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / f"{cfg['topic']['name']}_local.jsonl"

    records, problems = [], []
    for council in councils:
        items = []
        for src in council.get("sources") or []:
            url = src["url"] if isinstance(src, dict) else src
            title = (src.get("title") if isinstance(src, dict) else None) or url.rsplit("/", 1)[-1]
            try:
                items.append((title, url, bytes_to_text(_fetch(url, cache_dir), url)))
            except Exception as e:  # keep going; report at the end
                problems.append(f"{council['name']}: {url} -> {e}")
        folder = council.get("folder")
        if folder:
            for f in sorted(Path(folder).glob("*")):
                if f.suffix.lower() in (".pdf", ".txt", ".html", ".htm"):
                    try:
                        items.append((f.stem, f.resolve().as_uri(), bytes_to_text(f.read_bytes(), f.name)))
                    except Exception as e:
                        problems.append(f"{council['name']}: {f} -> {e}")
        before = len(records)
        for title, url, text in items:
            if len(text) < MIN_CHARS:
                problems.append(f"{council['name']}: '{title}' has almost no text "
                                "(scanned PDF or not the law itself?) - skipped")
                continue
            records.append(_record(council, title, url, text))
        print(f"{council['name']}: {len(records) - before} laws")

    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"saved {len(records)} local laws -> {out}")
    for p in problems:
        print("  warning:", p)
    return out
