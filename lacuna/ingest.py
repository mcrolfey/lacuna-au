"""Stream the Open Australian Legal Corpus and keep the documents most relevant to the topic."""
import heapq
import json
import re
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm

CONSTITUTION_HINT = "commonwealth of australia constitution act"


def _matcher(keywords: list[str]):
    # Whole-word matching, so "rent" does not match "current" or "parent".
    pats = [re.compile(r"\b" + re.escape(k.lower()) + r"s?\b") for k in keywords]

    def score(text: str) -> tuple[int, int]:
        low = text.lower()
        counts = [len(p.findall(low)) for p in pats]
        return sum(c > 0 for c in counts), sum(counts)  # (distinct keywords, total hits)
    return score


def _record(doc: dict, is_constitution: bool) -> dict:
    return {
        "id": doc.get("version_id") or doc.get("id"),
        "citation": doc.get("citation"),
        "type": "constitution" if is_constitution else doc.get("type"),
        "jurisdiction": doc.get("jurisdiction"),
        "url": doc.get("url"),
        "date": doc.get("date"),
        "text": doc.get("text") or "",
    }


def _select(docs, cfg: dict, already_filtered: bool = False) -> list[dict]:
    """Keep the Constitution plus the `max_docs` highest-scoring topic documents."""
    c, t = cfg["corpus"], cfg["topic"]
    score = _matcher(t["keywords"])
    best: list = []      # min-heap of (distinct, total, counter, record)
    constitution: list[dict] = []
    for n, doc in enumerate(docs):
        if doc.get("jurisdiction") not in c["jurisdictions"]:
            continue
        is_const = (CONSTITUTION_HINT in (doc.get("citation") or "").lower()
                    or doc.get("type") == "constitution")
        if is_const:
            constitution.append(_record(doc, True))
            continue
        if doc.get("type") not in c["types"]:
            continue
        distinct, total = score(doc.get("text") or "")
        if distinct < t["min_hits"]:
            continue
        item = (distinct, total, n, doc if already_filtered else _record(doc, False))
        if len(best) < t["max_docs"]:
            heapq.heappush(best, item)
        else:
            heapq.heappushpop(best, item)
    ranked = [r for *_, r in sorted(best, reverse=True)]
    return constitution[:1] + ranked


def _write(records: list[dict], out: Path) -> None:
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    has_const = any(r["type"] == "constitution" for r in records)
    print(f"kept {len(records)} documents -> {out}"
          + ("" if has_const else "  (warning: Constitution not found)"))


def ingest(cfg: dict) -> Path:
    out = Path(cfg["paths"]["data_dir"]) / f"{cfg['topic']['name']}_docs.jsonl"
    ds = load_dataset(cfg["corpus"]["dataset"], split="corpus", streaming=True)
    _write(_select(tqdm(ds, desc="scanning corpus"), cfg), out)
    return out


def refilter(cfg: dict) -> Path:
    """Re-run selection on the existing jsonl without downloading again."""
    out = Path(cfg["paths"]["data_dir"]) / f"{cfg['topic']['name']}_docs.jsonl"
    with out.open(encoding="utf-8") as f:
        docs = [json.loads(line) for line in tqdm(f, desc="reading")]
    _write(_select(docs, cfg, already_filtered=True), out)
    return out
