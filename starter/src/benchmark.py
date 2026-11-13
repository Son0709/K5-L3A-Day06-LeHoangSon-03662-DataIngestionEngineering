"""Load the benchmark and verify every evidence quote against the gold page.
Run from starter/:  python -m src.benchmark   (writes ../benchmark/verification.json)
"""
import json
import re
from collections import Counter
from pathlib import Path

from .corpus import ROOT, load_all

BENCH = ROOT / "benchmark"
REQUIRED = ["id", "split", "question", "expected_answer", "gold_source_id", "gold_page",
            "evidence_quotes", "filter"]


def squash(s: str) -> str:
    """Collapse all whitespace so hard line wraps in the PDF do not break matching."""
    return re.sub(r"\s+", " ", s).strip()


def load_questions(path: Path = BENCH / "questions.jsonl") -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def verify() -> dict:
    pages, manifest, _ = load_all()
    text = {(p.document_id, p.page): squash(p.text) for p in pages}
    metas = {s["source_id"]: s for s in manifest.values()}
    qs = load_questions()
    problems, rows = [], []
    for q in qs:
        miss = [k for k in REQUIRED if k not in q]
        if miss:
            problems.append((q.get("id"), f"missing fields {miss}"))
            continue
        gold = [(q["gold_source_id"], q["gold_page"])] + [
            (a["source_id"], a["page"]) for a in q.get("alt_gold", [])]
        ok = True
        for quote in q["evidence_quotes"]:
            if not any(squash(quote) in text.get(g, "") for g in gold[:1]):
                ok = False
                problems.append((q["id"], f"quote not on gold page: {quote[:70]!r}"))
        if q["filter"]:
            src = metas[q["gold_source_id"]]
            for k, v in q["filter"].items():
                if src.get(k) != v:
                    ok = False
                    problems.append((q["id"], f"gold source violates its own filter {k}={v}"))
        rows.append({"id": q["id"], "split": q["split"], "evidence_verified": ok})
    c = Counter(q["split"] for q in qs)
    filt = Counter(q["split"] for q in qs if q["filter"])
    summary = {
        "n_questions": len(qs), "per_split": dict(c), "filter_questions_per_split": dict(filt),
        "ids_unique": len({q["id"] for q in qs}) == len(qs),
        "all_evidence_verified": not problems, "problems": problems, "rows": rows,
        "meets_minimums": c["dev"] >= 15 and c["test"] >= 5 and len(qs) >= 20
        and sum(filt.values()) >= 3 and filt["test"] >= 1,
    }
    (BENCH / "verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    s = verify()
    print({k: v for k, v in s.items() if k != "rows"})
