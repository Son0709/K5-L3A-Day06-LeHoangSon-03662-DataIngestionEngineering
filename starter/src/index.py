"""Embed and store the chunks of strategies A and B (C reuses B's collection).
Run from starter/:  python -m src.index        (re-running is idempotent)

Writes results/ingest_report.json: counts, timings, model/library versions, re-ingest check.
"""
import json
import platform
import time
from collections import defaultdict
from importlib.metadata import version

from .chunking import by_paragraph, fixed_size
from .corpus import STARTER, load_all
from .embeddings import MODEL_NAME, MyEmbedder
from .store import ChromaStore


def build_chunks() -> dict:
    pages, _, _ = load_all()
    by_doc = defaultdict(list)
    for p in pages:
        by_doc[p.document_id].append(p)
    return {
        "A": [c for d in by_doc.values() for c in fixed_size(d)],
        "B": [c for d in by_doc.values() for c in by_paragraph(d)],
    }


def main() -> None:
    chunks = build_chunks()
    emb = MyEmbedder()
    store = ChromaStore(dimensions=emb.dimensions)
    store.create_schema()
    report = {
        "model": MODEL_NAME, "dimensions": emb.dimensions, "metric": "cosine",
        "vector_store": f"chromadb {version('chromadb')} (PersistentClient, HNSW approximate)",
        "store_path": "starter/results/chroma",
        "doc_prefix": "passage: ", "query_prefix": "query: ",
        "versions": {k: version(k) for k in ("torch", "transformers", "chromadb", "numpy")},
        "python": platform.python_version(), "device": "cpu", "cost_usd": 0,
        "strategies": {},
    }
    for name, cs in chunks.items():
        t0 = time.perf_counter()
        emb.truncated_count = 0
        vecs = emb.embed_documents([c.text for c in cs])
        embed_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        first = store.upsert(name, cs, vecs)
        store_s = time.perf_counter() - t1
        again = store.upsert(name, cs, vecs)  # re-ingest check: count must not change
        report["strategies"][name] = {
            "n_chunks": len(cs), "embed_seconds": round(embed_s, 2), "store_seconds": round(store_s, 2),
            "truncated_chunks_over_512_tokens": emb.truncated_count,
            "count_after_first_ingest": first["count"], "count_after_reingest": again["count"],
            "reingest_no_duplicates": first["count"] == again["count"] == len(cs),
        }
        print(name, report["strategies"][name])
    (STARTER / "results" / "ingest_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
