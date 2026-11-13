"""Aggregate the human audit labels into per-strategy tables (and cross-check metadata objectively).
Run from starter/ after the three *_labels.csv are filled in:  python -m src.audit_summary
Writes results/audit/summary.json.  Decodes key.json (blind X/Y labels) only here.
"""
import csv
import json
import re
from collections import Counter, defaultdict
from statistics import mean

from .audit import OUT, read_jsonl
from .benchmark import squash
from .corpus import STARTER, load_all


def rows(name):
    return list(csv.DictReader(open(OUT / name, encoding="utf-8")))


def score(v, where):
    if v not in ("0", "1", "2"):
        raise ValueError(f"{where}: score must be 0/1/2, got {v!r}")
    return int(v)


def main() -> None:
    key = json.loads((OUT / "key.json").read_text(encoding="utf-8"))
    res: dict = {}

    # ---- coherence ----
    by = defaultdict(list)
    detail = []
    for r in rows("coherence_labels.csv"):
        s = key["coherence"][r["position"]][r["chunk_label"]]
        sc = score(r["score_0_1_2"], r["position"])
        by[s].append(sc)
        detail.append((r["position"], s, sc))
    res["coherence"] = {s: {"n": len(v), "mean_of_2": round(mean(v), 2), "dist": dict(sorted(Counter(v).items()))}
                        for s, v in sorted(by.items())}
    res["coherence_detail"] = detail

    # ---- grounding ----
    by = defaultdict(list)
    detail = []
    for r in rows("grounding_labels.csv"):
        s = key["grounding"][r["question"]][r["set_label"]]
        sc = score(r["score_0_1_2"], r["question"])
        by[s].append(sc)
        detail.append((r["question"], s, sc))
    res["grounding"] = {s: {"n": len(v), "mean_of_2": round(mean(v), 2), "dist": dict(sorted(Counter(v).items()))}
                        for s, v in sorted(by.items())}
    res["grounding_detail"] = detail
    res["grounding_note"] = "C top-3 identical to B on all 5 test questions, so C shares B's labels."

    # ---- metadata (human labels) + objective cross-check ----
    pages, _, _ = load_all()
    pg_text = {(p.document_id, p.page): squash(p.text) for p in pages}
    chunks = {c["chunk_id"]: c for s in "AB" for c in read_jsonl(STARTER / "results" / f"chunks_{s}.jsonl")}
    tot, ok, fld = Counter(), Counter(), defaultdict(Counter)
    disagreements = []
    for r in rows("metadata_labels.csv"):
        st = r["strategy"]
        vals = {k: r[k] for k in ("source_ok", "page_ok", "other_fields_ok")}
        for k, v in vals.items():
            if v not in ("0", "1"):
                raise ValueError(f"metadata {r['chunk_id']}: {k} must be 0/1, got {v!r}")
        tot[st] += 1
        ok[st] += all(v == "1" for v in vals.values())
        for k, v in vals.items():
            fld[st][k] += v == "1"
        c = chunks[r["chunk_id"]]
        m = c["metadata"]
        # objective cross-check: every line of the chunk occurs in the text of pages [page, page_end].
        # B continuation chunks start with a synthetic heading line and a repeated lead-in line
        # (copied from an earlier page), so those first two lines are skipped for them.
        lines = [l for l in c["text"].split("\n") if l.strip()]
        is_cont = r["chunk_id"].startswith("B:") and not r["chunk_id"].endswith(":0")
        check = lines[2:] if is_cont else lines
        span = " ".join(pg_text[(c["document_id"], p)] for p in range(c["page"], m["page_end"] + 1))
        obj_ok = all(squash(l) in span for l in check)
        if (r["page_ok"] == "1") != bool(obj_ok):
            disagreements.append({"chunk_id": r["chunk_id"], "page": c["page"], "page_end": m["page_end"],
                                  "your_page_ok": r["page_ok"], "objective_page_consistent": bool(obj_ok),
                                  "your_note": r["error"]})
    res["metadata"] = {s: {"records_all_correct": f"{ok[s]}/{tot[s]}",
                           **{k: f"{fld[s][k]}/{tot[s]}" for k in ("source_ok", "page_ok", "other_fields_ok")}}
                       for s in sorted(tot)}
    res["metadata_disagreements_with_objective_check"] = disagreements
    fc = json.loads((OUT / "filter_compliance.json").read_text(encoding="utf-8"))
    res["filter_compliance_test"] = {s: f"{sum(v.values())}/{len(v)}" for s, v in fc.items()}

    (OUT / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
