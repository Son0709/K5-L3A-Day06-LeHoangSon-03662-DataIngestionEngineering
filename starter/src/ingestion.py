"""Read and normalize source PDFs (text-layer PDFs only; scans are reported, not OCR'd)."""
import re
import unicodedata
from pathlib import Path

import pymupdf

from .models import DocumentPage

# Invisible characters found in the Vietnamese legal PDFs (zero-width space, soft hyphen, BOM...).
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
# Running headers / digital-signature stamps repeated on pages; not part of the legal text.
_BOILERPLATE = [
    re.compile(r"^CÔNG BÁO/Số .*$"),
    re.compile(r"^Thời gian ký:.*$"),
]
_PAGE_NUMBER = re.compile(r"^\d{1,3}$")
# A bare number is only treated as a printed page number when it sits at a page edge.
_EDGE_LINES = 3
MIN_TEXT_CHARS = 50  # below this a page is considered empty / unreadable


def normalize_text(text: str) -> str:
    """NFC-normalize, drop invisible chars, running headers and printed page numbers.

    Line breaks are kept (structure such as "Điều 5." / "a)" is needed for chunking);
    only whitespace inside a line is collapsed and runs of blank lines become one.
    """
    text = unicodedata.normalize("NFC", text).translate(_INVISIBLE).replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    nonblank = [i for i, ln in enumerate(lines) if ln]
    edge = set(nonblank[:_EDGE_LINES]) | set(nonblank[-_EDGE_LINES:])
    kept: list[str] = []
    for i, ln in enumerate(lines):
        if ln and any(p.match(ln) for p in _BOILERPLATE):
            continue
        if ln and i in edge and _PAGE_NUMBER.match(ln):
            continue
        kept.append(ln)
    out = "\n".join(kept)
    out = re.sub(r"\n{2,}", "\n", out)  # blank lines carry no information in these sources
    return out.strip()


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract every physical page (1-based). Empty/unreadable pages are kept with
    metadata['empty']=True so callers can log them instead of silently losing them."""
    pages: list[DocumentPage] = []
    with pymupdf.open(path) as doc:
        for idx, page in enumerate(doc, start=1):
            raw = page.get_text()
            text = normalize_text(raw)
            pages.append(
                DocumentPage(
                    document_id=document_id,
                    source=source,
                    page=idx,
                    text=text,
                    metadata={
                        "raw_chars": len(raw),
                        "chars": len(text),
                        "empty": len(text) < MIN_TEXT_CHARS,
                        "n_images": len(page.get_images()),
                    },
                )
            )
    return pages
