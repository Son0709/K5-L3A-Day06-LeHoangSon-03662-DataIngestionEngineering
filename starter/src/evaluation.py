"""Automatic retrieval scoring + full top-3 traces.

Strict hit (the metric reported as Hit@1 / Evidence Hit@3): the chunk belongs to the gold source,
its page range [page, page_end] contains the gold page, and its text contains EVERY evidence quote.
Supplementary (labelled, never replacing the strict metric):
  page_hit   - gold source + gold page only (evidence may be incomplete)
  union_hit3 - evidence quotes jointly covered by the top-3 chunks (evidence split across chunks)
Chunk coherence and grounding are manual labels, not computed here.
"""
from typing import Any

from .benchmark import squash


def _is_gold_place(q: dict, meta: dict) -> bool:
    places = [(q["gold_source_id"], q["gold_page"])] + [
        (a["source_id"], a["page"]) for a in q.get("alt_gold", [])]
    return any(meta["document_id"] == s and meta["page"] <= pg <= meta.get("page_end", meta["page"])
               for s, pg in places)


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    quotes = [squash(e) for e in question["evidence_quotes"]]
    rows, strict = [], []
    for rank, h in enumerate(hits, start=1):
        text = squash(h["text"])
        place = _is_gold_place(question, h["metadata"])
        has_all = all(e in text for e in quotes)
        strict.append(place and has_all)
        rows.append({"rank": rank, "chunk_id": h["chunk_id"], "score": round(h["score"], 4),
                     "gold_place": place, "has_all_evidence": has_all, "strict_hit": place and has_all,
                     "metadata": h["metadata"], "text": h["text"]})
    union = all(any(e in squash(h["text"]) and _is_gold_place(question, h["metadata"]) for h in hits)
                for e in quotes)
    return {
        "id": question["id"], "split": question["split"], "question": question["question"],
        "filter": question["filter"], "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"], "evidence_quotes": question["evidence_quotes"],
        "hit1": bool(strict and strict[0]), "hit3": any(strict),
        "page_hit1": bool(rows and rows[0]["gold_place"]), "page_hit3": any(r["gold_place"] for r in rows),
        "union_hit3": union, "top3": rows,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """traces: list of {'strategy', **evaluate_query output}. Counts as numerator/denominator."""
    out: dict[str, Any] = {}
    for strat in sorted({t["strategy"] for t in traces}):
        for split in ("dev", "test", "all"):
            ts = [t for t in traces if t["strategy"] == strat and (split == "all" or t["split"] == split)]
            n = len(ts)
            f = lambda k: f"{sum(t[k] for t in ts)}/{n}"
            fts = [t for t in ts if t["filter"]]
            out[f"{strat}/{split}"] = {
                "n": n, "hit1": f("hit1"), "hit3": f("hit3"), "page_hit1": f("page_hit1"),
                "page_hit3": f("page_hit3"), "union_hit3": f("union_hit3"),
                "filter_questions_hit3": f"{sum(t['hit3'] for t in fts)}/{len(fts)}" if fts else "N/A",
            }
    return out
