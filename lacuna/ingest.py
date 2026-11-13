"""Stream the Open Australian Legal Corpus and keep documents relevant to the topic."""
import json
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm

CONSTITUTION_HINT = "commonwealth of australia constitution act"


def ingest(cfg: dict) -> Path:
    c, t = cfg["corpus"], cfg["topic"]
    out = Path(cfg["paths"]["data_dir"]) / f"{t['name']}_docs.jsonl"
    keywords = [k.lower() for k in t["keywords"]]
    ds = load_dataset(c["dataset"], split="corpus", streaming=True)

    kept, seen_constitution = 0, False
    with out.open("w") as f:
        for doc in tqdm(ds, desc="scanning corpus"):
            if doc.get("jurisdiction") not in c["jurisdictions"]:
                continue
            text = doc.get("text") or ""
            low_cite = (doc.get("citation") or "").lower()
            is_constitution = CONSTITUTION_HINT in low_cite
            if not is_constitution:
                if doc.get("type") not in c["types"]:
                    continue
                low = text.lower()
                if sum(k in low for k in keywords) < t["min_hits"]:
                    continue
            seen_constitution |= is_constitution
            f.write(json.dumps({
                "id": doc.get("version_id"),
                "citation": doc.get("citation"),
                "type": "constitution" if is_constitution else doc.get("type"),
                "jurisdiction": doc.get("jurisdiction"),
                "url": doc.get("url"),
                "date": doc.get("date"),
                "text": text,
            }) + "\n")
            kept += 1
            if kept >= t["max_docs"] and seen_constitution:
                break
    print(f"kept {kept} documents -> {out}"
          + ("" if seen_constitution else "  (warning: Constitution not found in corpus)"))
    return out
