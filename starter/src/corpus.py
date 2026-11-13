"""Corpus definition + manifest builder.  Run from starter/:  python -m src.corpus

Writes ../data/manifest.json and results/ingest_log.json.
Only facts present in the source files are recorded; nothing is guessed.
"""
import json
from datetime import datetime
from pathlib import Path

from .ingestion import load_pdf

STARTER = Path(__file__).resolve().parent.parent
ROOT = STARTER.parent
RAW = STARTER / "data" / "raw"

LICENSE = (
    "Văn bản quy phạm pháp luật của Nhà nước, không thuộc đối tượng bảo hộ quyền tác giả "
    "(Luật Sở hữu trí tuệ, Điều 15). Học viên tự xác minh; xem ghi chú trong báo cáo."
)

# document_type / year / doc_number are copied from the header of each document.
# exclude: {page: reason} for physical pages not counted as content pages.
SOURCES = [
    {
        "source_id": "luat-anm-2018",
        "title": "Luật An ninh mạng",
        "file": "luat-anm-2018.pdf",
        "document_type": "Luật",
        "doc_number": "24/2018/QH14",
        "year": 2018,
        "exclude": {},
    },
    {
        "source_id": "luat-gddt-2023",
        "title": "Luật Giao dịch điện tử",
        "file": "luat-gdđt-2023.pdf",
        "document_type": "Luật",
        "doc_number": "20/2023/QH15",
        "year": 2023,
        "exclude": {},
    },
    {
        "source_id": "nd-13-2023",
        "title": "Nghị định về bảo vệ dữ liệu cá nhân",
        "file": "nd-13-2023.pdf",
        "document_type": "Nghị định",
        "doc_number": "13/2023/NĐ-CP",
        "year": 2023,
        "exclude": {p: "Phụ lục: biểu mẫu điền thông tin, không phải quy phạm" for p in range(26, 37)},
    },
    {
        "source_id": "luat-dlcn-2025",
        "title": "Luật Bảo vệ dữ liệu cá nhân",
        "file": "luat-dlcn-2025.pdf",
        "document_type": "Luật",
        "doc_number": None,
        "year": 2025,
        "exclude": {},
    },
]

PAGE_RULE = (
    "Đơn vị trang = trang PDF vật lý (đánh số từ 1). Trang nội dung = trang có >= 50 ký tự "
    "sau chuẩn hóa và không nằm trong danh sách exclude (phụ lục biểu mẫu). Trang bìa riêng, "
    "mục lục: không có trong các file này (văn bản bắt đầu ngay trang 1)."
)


def load_all() -> tuple[list, dict, list]:
    """Return (content_pages, manifest_by_source, errors)."""
    content, manifest, errors = [], {}, []
    for s in SOURCES:
        path = RAW / s["file"]
        if not path.exists():
            errors.append({"source_id": s["source_id"], "error": f"file not found: {s['file']}"})
            manifest[s["source_id"]] = {
                "source_id": s["source_id"], "title": s["title"], "status": "missing_file",
                "source_path_or_url": path.relative_to(ROOT).as_posix(),
                "physical_pages": None, "content_pages": [], "n_content_pages": 0, "total_chars": 0,
                "note": "Không có file trong data/raw (bản scan, chưa có bản text); không nằm trong corpus.",
            }
            continue
        entry = {
            "source_id": s["source_id"],
            "title": s["title"],
            "source_path_or_url": path.relative_to(ROOT).as_posix(),
            "original_url": None,
            "license_or_permission": LICENSE,
            "accessed_at": datetime.fromtimestamp(path.stat().st_mtime).date().isoformat(),
            "accessed_at_note": "Ngày sửa đổi file cục bộ; chưa ghi nhận URL/ngày tải gốc.",
            "snapshot_version": None,
            "document_type": s["document_type"],
            "doc_number": s["doc_number"],
            "year": s["year"],
        }
        try:
            pages = load_pdf(path, s["source_id"], s["file"])
        except Exception as exc:  # report, never fall back silently
            errors.append({"source_id": s["source_id"], "error": repr(exc)})
            entry.update(status="error", physical_pages=None, content_pages=[], total_chars=0)
            manifest[s["source_id"]] = entry
            continue

        counted, excluded, empty = [], {}, []
        for p in pages:
            if p.metadata["empty"]:
                empty.append(p.page)
            elif p.page in s["exclude"]:
                excluded[p.page] = s["exclude"][p.page]
            else:
                counted.append(p)
        status = "ok" if counted else "excluded_no_text_layer"
        entry.update(
            status=status,
            physical_pages=len(pages),
            content_pages=[p.page for p in counted],
            n_content_pages=len(counted),
            excluded_pages=excluded,
            empty_or_unreadable_pages=empty,
            page_chars={p.page: p.metadata["chars"] for p in counted},
            total_chars=sum(p.metadata["chars"] for p in counted),
        )
        if status != "ok":
            entry["note"] = (
                "PDF là ảnh scan, không có text layer; chưa OCR nên không đưa vào corpus."
            )
        for p in counted:
            p.metadata.update(
                document_type=s["document_type"], year=s["year"], title=s["title"],
                doc_number=s["doc_number"],
            )
        content.extend(counted)
        manifest[s["source_id"]] = entry
    return content, manifest, errors


def main() -> None:
    content, manifest, errors = load_all()
    total_pages = sum(m.get("n_content_pages", 0) for m in manifest.values())
    total_chars = sum(m["total_chars"] for m in manifest.values())
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "page_counting_rule": PAGE_RULE,
        "total_content_pages": total_pages,
        "total_chars": total_chars,
        "meets_30_page_minimum": total_pages >= 30,
        "sources": list(manifest.values()),
    }
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "manifest.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (STARTER / "results").mkdir(exist_ok=True)
    log = {
        "errors": errors,
        "per_source": {
            k: {"status": v["status"], "empty_or_unreadable_pages": v.get("empty_or_unreadable_pages"),
                "excluded_pages": v.get("excluded_pages")} for k, v in manifest.items()},
    }
    (STARTER / "results" / "ingest_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    for m in manifest.values():
        print(f"{m['source_id']:16} {m['status']:24} pages={m.get('n_content_pages')} chars={m['total_chars']}")
    print(f"TOTAL content pages={total_pages} chars={total_chars} (>=30: {total_pages >= 30})")


if __name__ == "__main__":
    main()
