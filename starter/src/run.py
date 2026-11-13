"""Run the benchmark: top-3 retrieval for strategies A, B, C on every question.
Run from starter/ (after `python -m src.index`):  python -m src.run

A = fixed chunks, no filter | B = structure chunks, no filter | C = B chunks + metadata filter,
applied only when the question itself supplies one (otherwise C runs unfiltered, as documented).

Writes results/traces.jsonl (full top-3 per question/strategy) and results/metrics.json.
"""
import json

from .benchmark import load_questions
from .corpus import STARTER
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .store import ChromaStore

# strategy -> (collection, use question filter?)
STRATEGIES = {"A": ("A", False), "B": ("B", False), "C": ("B", True)}


def main() -> None:
    emb = MyEmbedder()
    store = ChromaStore(dimensions=emb.dimensions)
    for coll in ("A", "B"):
        if store.count(coll) == 0:
            raise RuntimeError(f"collection lab_{coll} is empty - run `python -m src.index` first")
    questions = load_questions()
    qvecs = {q["id"]: emb.embed_query(q["question"]) for q in questions}  # same vector for all strategies
    traces = []
    for strat, (coll, use_filter) in STRATEGIES.items():
        for q in questions:
            flt = q["filter"] if use_filter else None
            hits = store.search(coll, qvecs[q["id"]], top_k=3, filters=flt)
            traces.append({"strategy": strat, "filter_applied": flt, **evaluate_query(q, hits)})
    with open(STARTER / "results" / "traces.jsonl", "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    metrics = summarize(traces)
    (STARTER / "results" / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in metrics.items():
        print(k, v)


if __name__ == "__main__":
    main()
