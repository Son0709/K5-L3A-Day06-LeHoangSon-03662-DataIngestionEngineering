# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

---

# Bài nộp của học viên — Lê Hoàng Sơn (2A202603662)

Corpus: Luật An ninh mạng 2018, Luật Giao dịch điện tử 2023, Nghị định 13/2023/NĐ-CP (87 trang nội dung). Embedding local `intfloat/multilingual-e5-small` + ChromaDB (không cần Docker, không cần API key, chi phí 0). Báo cáo: [report/individual/2A202603662_LeHoangSon.md](report/individual/2A202603662_LeHoangSon.md).

## Cấu trúc và đường dẫn

| Nội dung | Đường dẫn |
|---|---|
| PDF nguồn | `starter/data/raw/` |
| Manifest (nguồn, quyền, trang, ký tự) | `data/manifest.json` |
| Benchmark (20 câu, split, gold, kiểm chứng) | `benchmark/` |
| Mã nguồn | `starter/src/` |
| Chunk, trace top-3, chỉ số, log | `starter/results/` |
| Nhãn chấm tay và tổng hợp | `starter/results/audit/` |
| Nhật ký thí nghiệm A/B/C | `artifacts/experiment_log.csv` |

## Cách chạy (Python 3.12, Windows/macOS/Linux)

```bash
cd starter
python -m venv .venv            # Windows: .venv\Scripts\Activate.ps1 ; macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.corpus            # đọc PDF, chuẩn hóa, sinh data/manifest.json + results/ingest_log.json
python -m src.benchmark         # kiểm chứng evidence của 20 câu -> benchmark/verification.json
python -m src.build_chunks      # chunk A và B -> results/chunks_*.jsonl, chunk_stats.json
python -m src.index             # embed + lưu vào Chroma (idempotent) -> results/ingest_report.json
python -m src.run               # top-3 cho A/B/C trên 20 câu -> results/traces.jsonl, metrics.json
python -m src.audit_summary     # tổng hợp nhãn chấm tay đã điền -> results/audit/summary.json
```

Lần đầu `src.index` tải model từ Hugging Face (cần mạng, vài trăm MB). Mọi bước đều báo lỗi nếu thiếu model/index, không fallback sang vector giả.

**Cảnh báo:** không chạy lại `python -m src.audit`; lệnh này sinh lại phiếu chấm trống và sẽ ghi đè các file `*_labels.csv` đã chấm (nhãn nằm trong git, có thể khôi phục bằng `git checkout`).

## Ghi chú môi trường và tái lập
- Phiên bản đã dùng: Python 3.12.10, torch 2.15.0, transformers 5.22.2, chromadb 1.5.9, numpy 2.5.4 (xem `starter/results/ingest_report.json`).
- Máy phát triển chặn một số DLL (scikit-learn, grpc); vì vậy dùng `transformers` thay `sentence-transformers` và chặn module telemetry gRPC của Chroma (`starter/src/store.py`). Máy không bị chặn không bị ảnh hưởng.
- Thư mục `starter/results/chroma/` không được commit; dựng lại bằng `python -m src.index`.
- Luật Bảo vệ dữ liệu cá nhân 2025 không nằm trong corpus (chỉ có bản scan, chưa OCR).
- Kết quả chạy lại có thể lệch rất nhỏ ở điểm tương đồng do HNSW xấp xỉ và phiên bản thư viện.
