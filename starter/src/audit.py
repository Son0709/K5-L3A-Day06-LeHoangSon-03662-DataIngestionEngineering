"""Generate blind manual-audit sheets (coherence, metadata, grounding).
Run from starter/ (after `python -m src.run`):  python -m src.audit

Output in results/audit/:
  README.md                  rules, rubric, pre-registered position rule
  coherence_sheet.md + coherence_labels.csv
  grounding_sheet.md + grounding_labels.csv
  metadata_sheet.md  + metadata_labels.csv
  key.json                   X/Y -> strategy mapping. DO NOT OPEN until all labels are filled in.
Labels are filled in by the human grader; nothing here assigns a score.
"""
import csv
import json
import random
from collections import defaultdict

from .benchmark import load_questions, squash
from .chunking import A_OVERLAP, A_SIZE, parse_paragraphs
from .corpus import STARTER, load_all

OUT = STARTER / "results" / "audit"
SEED = 20261113
N_POSITIONS = 10


def read_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def fence(t: str) -> str:
    return "```text\n" + t.strip() + "\n```"


def pick_positions(pages):
    """Pre-registered rule: sort content pages by (source_id, page), take 10 evenly spaced
    indices floor((i+0.5)*n/10); in each page use the paragraph holding the middle character."""
    pp = sorted(pages, key=lambda p: (p.document_id, p.page))
    n = len(pp)
    sel = [pp[int((i + 0.5) * n / N_POSITIONS)] for i in range(N_POSITIONS)]
    out = []
    for i, pg in enumerate(sel, start=1):
        paras = parse_paragraphs([pg], merge_across_pages=False)
        text, offs, pos = "", [], 0
        for p in paras:
            offs.append(pos)
            text += p.text + "\n"
            pos += len(p.text) + 1
        text = text.rstrip("\n")
        mid = len(text) // 2
        k = max(j for j, o in enumerate(offs) if o <= mid)
        out.append({"pid": f"P{i:02d}", "doc": pg.document_id, "page": pg.page, "title": pg.metadata["title"],
                    "para": paras[k].text, "mid": mid, "text_len": len(text)})
    return out


def a_chunk_for(pos, A):
    step = A_SIZE - A_OVERLAP
    cands = [c for c in A if c["document_id"] == pos["doc"] and c["page"] == pos["page"]]
    last = len(cands) - 1
    i = min(pos["mid"] // step, last)
    return next(c for c in cands if c["chunk_id"].endswith(f":p{pos['page']}:{i}"))


def b_chunk_for(pos, B):
    key = squash(pos["para"])[:60]
    cands = [c for c in B if c["document_id"] == pos["doc"]
             and c["page"] <= pos["page"] <= c["metadata"]["page_end"]]
    for c in cands:
        if key in squash(c["text"]):
            return c
    raise RuntimeError(f"no B chunk contains position {pos['pid']}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    pages, _, _ = load_all()
    A = read_jsonl(STARTER / "results" / "chunks_A.jsonl")
    B = read_jsonl(STARTER / "results" / "chunks_B.jsonl")
    traces = read_jsonl(STARTER / "results" / "traces.jsonl")
    tr = {(t["strategy"], t["id"]): t for t in traces}
    test_q = [q for q in load_questions() if q["split"] == "test"]
    key = {"coherence": {}, "grounding": {}}

    # ---------------- coherence ----------------
    pos = pick_positions(pages)
    md = ["# Phiếu chấm COHERENCE (che nhãn)\n",
          "Thang: **0** = bị cắt giữa ý / thiếu chủ thể nên không hiểu; **1** = hiểu một phần, thiếu ngữ cảnh; "
          "**2** = tự hiểu được và giữ trọn ý. Chấm *chunk chứa vị trí*, không chấm vị trí nguồn.\n"
          "Điền điểm và lý do vào `coherence_labels.csv` (mỗi vị trí 2 dòng: X và Y).\n"]
    rows = []
    for p in pos:
        a, b = a_chunk_for(p, A), b_chunk_for(p, B)
        pair = [("A", a), ("B", b)]
        rng.shuffle(pair)
        key["coherence"][p["pid"]] = {"X": pair[0][0], "Y": pair[1][0]}
        md.append(f"\n---\n## {p['pid']} — {p['title']} ({p['doc']}), trang {p['page']}\n")
        md.append("**Đoạn nguồn tại vị trí:**\n" + fence(p["para"][:500]))
        for lab, (_, c) in zip(("X", "Y"), pair):
            md.append(f"\n**Chunk {lab}** ({len(c['text'])} ký tự):\n" + fence(c["text"]))
            rows.append([p["pid"], lab, "", ""])
    (OUT / "coherence_sheet.md").write_text("\n".join(md), encoding="utf-8")
    _csv(OUT / "coherence_labels.csv", ["position", "chunk_label", "score_0_1_2", "reason"], rows)

    # ---------------- grounding ----------------
    same_c_b = all([r["chunk_id"] for r in tr[("C", q["id"])]["top3"]] ==
                   [r["chunk_id"] for r in tr[("B", q["id"])]["top3"]] for q in test_q)
    strategies = ["A", "B"] if same_c_b else ["A", "B", "C"]
    md = ["# Phiếu chấm GROUNDING (che nhãn)\n",
          "Chỉ đánh giá **bằng chứng truy xuất**, không phải chất lượng câu trả lời của LLM.\n"
          "Với mỗi câu và mỗi bộ top-3: **0** = không có bằng chứng; **1** = có nhưng thiếu điều kiện/ngữ cảnh cần thiết; "
          "**2** = đủ để trả lời và truy được nguồn. Có thể đọc đáp án mong đợi và evidence để đối chiếu.\n"
          + ("*(Cấu hình C có top-3 giống hệt B trên cả 5 câu test, nên dùng chung nhãn của B.)*\n" if same_c_b else "")]
    rows = []
    for q in test_q:
        labs = list(strategies)
        rng.shuffle(labs)
        key["grounding"][q["id"]] = {l: s for l, s in zip(("X", "Y", "Z"), labs)}
        md.append(f"\n---\n## {q['id']}: {q['question']}\n")
        md.append(f"**Đáp án mong đợi:** {q['expected_answer']}\n")
        md.append("**Evidence (nguồn %s, trang %s):**\n" % (q["gold_source_id"], q["gold_page"]) +
                  fence("\n".join(q["evidence_quotes"])))
        for lab, s in zip(("X", "Y", "Z"), labs):
            md.append(f"\n### Bộ {lab}\n")
            for r in tr[(s, q["id"])]["top3"]:
                m = r["metadata"]
                md.append(f"**#{r['rank']}** — {m['title']}, trang {m['page']}"
                          + (f"–{m['page_end']}" if m['page_end'] != m['page'] else "") + "\n" + fence(r["text"]))
            rows.append([q["id"], lab, "", ""])
    (OUT / "grounding_sheet.md").write_text("\n".join(md), encoding="utf-8")
    _csv(OUT / "grounding_labels.csv", ["question", "set_label", "score_0_1_2", "reason"], rows)

    # ---------------- metadata ----------------
    pg_text = {(p.document_id, p.page): squash(p.text) for p in pages}
    md = ["# Phiếu kiểm METADATA (5 câu test × top-3)\n",
          "Với mỗi bản ghi, đối chiếu với **PDF gốc** (mở đúng trang): `source` (văn bản) đúng? `page` đúng (chunk thật sự nằm "
          "trên trang đó)? Trường `document_type`/`year`/`article`/`chapter` đúng so với nguồn? Ghi `ok`=1 chỉ khi mọi trường "
          "đều đủ và đúng; ghi lỗi cụ thể vào `error`.\n"
          "Cột *auto-check* chỉ là gợi ý máy (đoạn đầu của chunk có xuất hiện trên trang khai báo không), không thay thế việc kiểm tra tay.\n"]
    rows = []
    for strat in strategies:
        md.append(f"\n---\n## Cấu hình {strat}\n")
        for q in test_q:
            for r in tr[(strat, q["id"])]["top3"]:
                m = r["metadata"]
                head = squash(r["text"])
                body = head.split(" ", 0)[0] and head[len(head) // 3: len(head) // 3 + 60]
                found = any(body in pg_text.get((m["document_id"], pg), "")
                            for pg in range(m["page"], m["page_end"] + 1))
                md.append(f"- **{q['id']} #{r['rank']}** `{r['chunk_id']}` | source=`{m['document_id']}` | page={m['page']}"
                          f"–{m['page_end']} | type={m['document_type']} | year={m['year']} | chapter={m.get('chapter')} | "
                          f"article={m.get('article')} | auto-check: {'trên trang khai báo' if found else 'KHÔNG THẤY'}")
                rows.append([strat, q["id"], r["rank"], r["chunk_id"], "", "", "", ""])
    (OUT / "metadata_sheet.md").write_text("\n".join(md), encoding="utf-8")
    _csv(OUT / "metadata_labels.csv",
         ["strategy", "question", "rank", "chunk_id", "source_ok", "page_ok", "other_fields_ok", "error"], rows)

    # filter compliance is objective (computed, not graded)
    comp = {}
    for strat in ("A", "B", "C"):
        fq = [q for q in test_q if q["filter"]]
        comp[strat] = {q["id"]: all(all(r["metadata"].get(k) == v for k, v in q["filter"].items())
                                    for r in tr[(strat, q["id"])]["top3"]) for q in fq}
    (OUT / "filter_compliance.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(_readme(pos), encoding="utf-8")
    print("positions:", [(p["pid"], p["doc"], p["page"]) for p in pos])
    print("C identical to B on test:", same_c_b, "| filter compliance:", comp)


def _csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _readme(pos) -> str:
    lines = "\n".join(f"- {p['pid']}: {p['doc']} trang {p['page']}" for p in pos)
    return f"""# Quy trình chấm thủ công

**Quy tắc chọn 10 vị trí coherence (chốt trước khi xem điểm):** sắp xếp các trang nội dung theo
(`source_id`, `page`), lấy chỉ số `floor((i+0.5)*n/10)` với i = 0..9; trong mỗi trang lấy đoạn chứa ký tự
ở giữa văn bản trang. Mỗi chiến lược chấm chunk chứa vị trí đó (A: cửa sổ bắt đầu tại `mid // 450`;
B: chunk chứa đoạn đó).

{lines}

**Che nhãn:** các phiếu dùng X/Y(/Z) xáo ngẫu nhiên (seed {SEED}); `key.json` chứa đáp án ánh xạ, chỉ mở sau khi
điền xong mọi nhãn. Phiếu grounding/coherence không hiển thị cờ hit hay điểm tự động.

**Người chấm:** tác giả bài lab (cũng là người viết câu hỏi và xây pipeline), nên có nguy cơ thiên lệch; dù đã
che nhãn, chunk B có tiêu đề "Điều N." nên người chấm có thể đoán được chiến lược.

**Hỗ trợ AI:** phiếu được sinh bằng script (`python -m src.audit`); script không gán điểm nào.
Nếu dùng AI để gợi ý nhãn, phải ghi rõ phương pháp và rà lại từng nhãn (RULES.md).
"""


if __name__ == "__main__":
    main()
