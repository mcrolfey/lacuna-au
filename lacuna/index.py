"""Chunk documents, embed them with LM Studio and store in a local Chroma DB."""
import json
import re
from pathlib import Path

import chromadb
from tqdm import tqdm

from .llm import LMStudio


def chunk(text: str, size: int, overlap: int) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        # Prefer to break at a paragraph boundary.
        cut = text.rfind("\n\n", start + size // 2, end)
        if cut != -1 and end < len(text):
            end = cut
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def collection(cfg: dict):
    client = chromadb.PersistentClient(path=str(Path(cfg["paths"]["data_dir"]) / "chroma"))
    # Chroma names allow only letters, digits, . _ - (3-512 chars), so "parking rules" -> "parking_rules".
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", cfg["topic"]["name"]).strip("._-")
    name = (name + "_topic")[:512] if len(name) < 3 else name[:512]
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def build_index(cfg: dict, llm: LMStudio, batch: int = 32) -> None:
    src = Path(cfg["paths"]["data_dir"]) / f"{cfg['topic']['name']}_docs.jsonl"
    col = collection(cfg)
    ck = cfg["chunking"]
    ids, docs, metas = [], [], []

    def flush():
        if ids:
            col.upsert(ids=list(ids), documents=list(docs), metadatas=list(metas),
                       embeddings=llm.embed(docs))
            ids.clear(); docs.clear(); metas.clear()

    for line in tqdm(src.open(encoding="utf-8"), desc="indexing"):
        d = json.loads(line)
        for i, piece in enumerate(chunk(d["text"], ck["chunk_chars"], ck["overlap_chars"])):
            ids.append(f"{d['id']}::{i}")
            docs.append(piece)
            metas.append({k: (d[k] or "") for k in ("citation", "type", "jurisdiction", "url", "date")})
            if len(ids) >= batch:
                flush()
    flush()
    print(f"index has {col.count()} chunks")


def retrieve(cfg: dict, llm: LMStudio, query: str, k: int, where: dict | None = None) -> list[dict]:
    res = collection(cfg).query(query_embeddings=llm.embed([query]), n_results=k, where=where)
    return [{"text": t, **m} for t, m in zip(res["documents"][0], res["metadatas"][0])]


def format_sources(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[S{i}] {c['citation']} ({c['jurisdiction']}, {c['type']})\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    )
