"""Chunking strategies for Vietnamese legal text.

A = fixed-size windows (500 chars, overlap 50), cut per page, no structure awareness.
B = structure-aware: one chunk per "Điều" (article), packed by paragraph up to MAX_CHARS,
    long articles split on paragraph (khoản/điểm) boundaries, each continuation chunk is
    prefixed with its article heading so it stays self-explanatory.
C reuses B's chunks unchanged; only retrieval differs (metadata filter), see store.py.

Both strategies get the same metadata schema, and both use the same line-unwrapping, so
the only differences between A and B are the cut points (and B's heading prefix).
"""
import re
from collections import defaultdict
from dataclasses import dataclass

from .models import Chunk, DocumentPage

# ---- parameters (recorded in artifacts/experiment_log.csv) -------------------------------
A_SIZE, A_OVERLAP = 500, 50
B_MAX_CHARS = 1200

_ITEM = re.compile(r"^(Điều \d+\.|Chương [IVXLC]+\b|Mục \d+\b|\d+\.\s|[a-zđ]\)\s|-\s|•)")
_TERMINAL = (".", ";", ":")
_ARTICLE = re.compile(r"^Điều (\d+)\.\s*(.*)$")
_CHAPTER = re.compile(r"^Chương ([IVXLC]+)\b")


@dataclass
class Para:
    text: str
    page_start: int
    page_end: int
    chapter: str | None
    article: str | None
    article_title: str | None


def _is_structural(text: str) -> bool:
    """Chương / Mục headings and ALL-CAPS title lines (not legal text to retrieve)."""
    return bool(_CHAPTER.match(text) or re.match(r"^Mục \d+", text) or text.isupper())


def _is_new_item(prev: str | None, line: str) -> bool:
    if prev is None or _ITEM.match(line):
        return True
    if _ARTICLE.match(prev):  # an article title wraps only onto lowercase continuation lines
        return not line[0].islower()
    if _is_structural(prev):  # "Chương I" + its ALL-CAPS title lines form one heading
        return not line.isupper()
    # ordinary hard-wrapped line: continues unless the previous line closed a sentence
    # and this one starts a new one
    return prev.endswith(_TERMINAL) and not line[0].islower()


def parse_paragraphs(pages: list[DocumentPage], merge_across_pages: bool) -> list[Para]:
    """Rebuild paragraphs from hard-wrapped lines and tag each with chapter/article state."""
    paras: list[Para] = []
    chapter = article = title = None
    cur: list[str] = []
    cur_ps = cur_pe = 0

    def flush():
        nonlocal cur, chapter, article, title
        if not cur:
            return
        text = " ".join(cur)
        if (m := _ARTICLE.match(text)):
            article, title = f"Điều {m.group(1)}", m.group(2).strip()
        elif (m := _CHAPTER.match(text)):
            chapter = text  # "Chương I NHỮNG QUY ĐỊNH CHUNG"
            article = title = None
        paras.append(Para(text, cur_ps, cur_pe, chapter, article, title))
        cur = []

    for pg in pages:
        if not merge_across_pages:
            flush()
        for line in pg.text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if cur and not _is_new_item(cur[-1], line):
                cur[-1] = f"{cur[-1]} {line}"
                cur_pe = pg.page
            else:
                flush()
                cur = [line]
                cur_ps = cur_pe = pg.page
    flush()
    return paras


def _meta(pages: list[DocumentPage], page_start, page_end, chapter, article, article_title) -> dict:
    base = pages[0].metadata
    return {
        "title": base["title"], "doc_number": base["doc_number"],
        "document_type": base["document_type"], "year": base["year"],
        "page_end": page_end, "chapter": chapter, "article": article,
        "article_title": article_title,
    }


def fixed_size(pages: list[DocumentPage], size: int = A_SIZE, overlap: int = A_OVERLAP) -> list[Chunk]:
    """Strategy A: sliding window over each page's (unwrapped) text; never crosses pages."""
    assert 0 <= overlap < size
    out: list[Chunk] = []
    paras = parse_paragraphs(pages, merge_across_pages=False)
    by_page: dict[int, list[Para]] = defaultdict(list)
    for p in paras:
        by_page[p.page_start].append(p)
    for pg in pages:
        pp = by_page.get(pg.page, [])
        if not pp:
            continue
        # page text + char offset of each paragraph, to look up chapter/article at a window start
        text, offs, pos = "", [], 0
        for p in pp:
            offs.append(pos)
            text += p.text + "\n"
            pos += len(p.text) + 1
        text = text.rstrip("\n")
        step = size - overlap
        for i, start in enumerate(range(0, max(1, len(text) - overlap), step)):
            piece = text[start:start + size]
            if not piece.strip():
                continue
            k = max(j for j, o in enumerate(offs) if o <= start)
            ref = pp[k]
            m = _meta(pages, pg.page, pg.page, ref.chapter, ref.article, ref.article_title)
            out.append(Chunk(f"A:{pg.document_id}:p{pg.page}:{i}", pg.document_id, pg.source,
                             pg.page, piece, m))
    return out


def by_paragraph(pages: list[DocumentPage], max_size: int = B_MAX_CHARS) -> list[Chunk]:
    """Strategy B: article-bounded chunks packed from whole paragraphs (<= max_size chars)."""
    out: list[Chunk] = []
    paras = parse_paragraphs(pages, merge_across_pages=True)
    groups: list[list[Para]] = []
    for p in paras:
        if _is_structural(p.text):
            # Chương/Mục/ALL-CAPS headings are kept as metadata only, out of chunk text
            continue
        if _ARTICLE.match(p.text) or not groups:  # each Điều starts a new group
            groups.append([])
        groups[-1].append(p)
    doc, source = pages[0].document_id, pages[0].source
    for grp in groups:
        grp = [p for p in grp if p.text.strip()]
        if not grp:
            continue
        head = grp[0]
        art = head.article or "preamble"
        prefix = f"{head.article}. {head.article_title}" if head.article else ""
        ci = 0

        def emit(texts: list[str], ps: list[Para]) -> None:
            nonlocal ci
            if not texts or not ps:
                return
            body = "\n".join(texts)
            if ci > 0 and prefix and not body.startswith(prefix):
                body = f"{prefix}\n{body}"  # later chunks keep their article heading
            m = _meta(pages, ps[0].page_start, max(p.page_end for p in ps), head.chapter,
                      head.article, head.article_title)
            out.append(Chunk(f"B:{doc}:{art.replace(' ', '')}:{ci}", doc, source,
                             ps[0].page_start, body, m))
            ci += 1

        cur_t: list[str] = []
        cur_p: list[Para] = []
        size = 0
        for unit in _units(grp):
            utext = "\n".join(p.text for p in unit)
            if len(utext) <= max_size:  # whole khoản fits: pack greedily, never split it
                if cur_t and size + len(utext) + 1 > max_size:
                    emit(cur_t, cur_p)
                    cur_t, cur_p, size = [], [], 0
                cur_t.append(utext)
                cur_p.extend(unit)
                size += len(utext) + 1
                continue
            # oversized khoản: own chunks, split at điểm boundaries, lead-in repeated
            emit(cur_t, cur_p)
            cur_t, cur_p, size = [], [], 0
            lead = next((p.text for p in unit if not _ARTICLE.match(p.text)), "")
            if len(lead) > 300:
                lead = lead[:300].rsplit(" ", 1)[0] + " …"
            seg_t: list[str] = []
            seg_p: list[Para] = []
            s_len, first = 0, True
            for p in unit:
                for sub in _split_long(p.text, max_size):
                    if seg_t and s_len + len(sub) + 1 > max_size:
                        emit(seg_t, seg_p)
                        seg_t, seg_p, s_len, first = [], [], 0, False
                    if not seg_t and not first and lead:
                        seg_t.append(lead)
                        s_len += len(lead) + 1
                    seg_t.append(sub)
                    seg_p.append(p)
                    s_len += len(sub) + 1
            emit(seg_t, seg_p)
        emit(cur_t, cur_p)
    return out


def _units(grp: list[Para]) -> list[list[Para]]:
    """Group paragraphs into khoản units: a "N." line opens a unit, điểm lines attach to it,
    and the article heading travels with the first khoản."""
    units: list[list[Para]] = [[]]
    for p in grp:
        if re.match(r"^\d+\.\s", p.text) and any(not _ARTICLE.match(q.text) for q in units[-1]):
            units.append([])
        units[-1].append(p)
    return units


def _split_long(text: str, max_size: int) -> list[str]:
    """Split a paragraph longer than max_size at sentence/clause boundaries."""
    if len(text) <= max_size:
        return [text]
    parts, cur = [], ""
    for seg in re.split(r"(?<=[.;])\s+", text):
        if cur and len(cur) + len(seg) + 1 > max_size:
            parts.append(cur)
            cur = seg
        else:
            cur = f"{cur} {seg}".strip()
    if cur:
        parts.append(cur)
    return parts
