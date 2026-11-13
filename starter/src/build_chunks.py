"""Chunk the corpus with strategies A and B, save them and print statistics.
Run from starter/:  python -m src.build_chunks

Writes results/chunks_A.jsonl, results/chunks_B.jsonl, results/chunk_stats.json.
Strategy C reuses B's chunks, so it has no file of its own.
"""
import json
import statistics
import time
from collections import defaultdict
from dataclasses import asdict

from .benchmark import load_questions, squash
from .chunking import A_OVERLAP, A_SIZE, B_MAX_CHARS, by_paragraph, fixed_size
from .corpus import STARTER, load_all


def stats(chunks, seconds):
    lens = sorted(len(c.text) for c in chunks)
    q = lambda f: lens[min(len(lens) - 1, int(f * len(lens)))]
    return {
        "n_chunks": len(chunks), "total_chars": sum(lens),
        "min": lens[0], "p10": q(0.1), "median": int(statistics.median(lens)),
        "mean": round(statistics.mean(lens), 1), "p90": q(0.9), "max": lens[-1],
        "chunking_seconds": round(seconds, 3),
        "approx_tokens_chars_div_4": sum(lens) // 4,
    }


def main() -> None:
    pages, _, _ = load_all()
    by_doc = defaultdict(list)
    for p in pages:
        by_doc[p.document_id].append(p)
    out = {}
    for name, fn in (("A", fixed_size), ("B", by_paragraph)):
        t0 = time.perf_counter()
        chunks = [c for doc in by_doc.values() for c in fn(doc)]
        dt = time.perf_counter() - t0
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), f"duplicate chunk ids in {name}"
        out[name] = stats(chunks, dt)
        with open(STARTER / "results" / f"chunks_{name}.jsonl", "w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        # Diagnostic on DEV questions only: is every evidence quote fully inside one chunk?
        dev = [q for q in load_questions() if q["split"] == "dev"]
        whole = 0
        for q in dev:
            cs = [c for c in chunks if c.document_id == q["gold_source_id"]
                  and c.page <= q["gold_page"] <= c.metadata["page_end"]]
            whole += any(all(squash(e) in squash(c.text) for e in q["evidence_quotes"]) for c in cs)
        out[name]["dev_evidence_in_single_chunk"] = f"{whole}/{len(dev)}"
    out["params"] = {"A_size": A_SIZE, "A_overlap": A_OVERLAP, "B_max_chars": B_MAX_CHARS}
    (STARTER / "results" / "chunk_stats.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
