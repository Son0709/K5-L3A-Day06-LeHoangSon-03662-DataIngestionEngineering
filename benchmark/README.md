# Benchmark

Tệp chính: [questions.jsonl](questions.jsonl) (20 câu, mỗi dòng một JSON). Kiểm chứng evidence:
`cd starter && python -m src.benchmark` → [verification.json](verification.json).

**Ghi nhận trước khi chạy thí nghiệm (pre-registration).** Nội dung dưới đây được chốt khi chưa có
bất kỳ kết quả truy xuất nào. Mọi thay đổi sau này phải được ghi thêm ở mục "Thay đổi" cuối file.

## Cấu trúc câu hỏi
`id, split, qtype, question, expected_answer, gold_source_id, gold_page, alt_gold, evidence_quotes, filter`

- `gold_page` = số trang PDF vật lý (đánh số từ 1), cùng hệ với `page` trong metadata chunk.
- `evidence_quotes`: các đoạn trích nguyên văn (sau chuẩn hóa, bỏ qua xuống dòng cứng). Câu cần nhiều
  điều kiện có nhiều quote; hit chỉ tính khi chunk chứa **đủ** các quote.
- `alt_gold`: nguồn/trang hợp lệ khác. Hiện rỗng: đã kiểm tra mỗi quote chỉ xuất hiện đúng 1 trang trong corpus.
- `filter`: giá trị do người dùng/ngữ cảnh cung cấp **trước khi truy xuất**; null = cấu hình C chạy không filter cho câu đó.

## Chia dev / test
| Split | Số câu | ND 13/2023 | Luật ANM 2018 | Luật GDĐT 2023 | Câu có filter |
|---|---:|---:|---:|---:|---:|
| dev | 15 | 8 | 3 | 4 | 3 (d05, d06, d07) |
| test | 5 | 2 | 2 | 1 | 1 (t01) |

Quy tắc chia: theo **Điều khoản** (không chia ngẫu nhiên), để câu test hỏi về các Điều mà không câu dev nào hỏi,
trừ ngoại lệ ghi ở mục rò rỉ. Việc chia được cố định lúc viết câu hỏi, trước khi chạy bất kỳ chiến lược nào.

## Chính sách filter
- Chỉ dùng trường `document_type` ("Luật" / "Nghị định"), lấy từ tiêu đề văn bản, không có giá trị tự đặt.
- Filter chỉ thu hẹp phạm vi (ví dụ "Luật" còn 2 văn bản), không chỉ thẳng gold source.
- Lý do chọn: hai nhóm chủ đề trùng nhau giữa Luật và Nghị định (trẻ em, thông báo sự cố dữ liệu),
  nên d05/d06 (lọc "Nghị định") và t01 (lọc "Luật") kiểm tra filter thật, theo hai chiều ngược nhau.

## Bẫy cố ý (hard negatives)
- "72 giờ" xuất hiện ở nhiều Điều của ND 13 (đồng ý/phản đối d15, chỉnh sửa d14, xóa d02, thông báo vi phạm d06).
- "60 ngày" xuất hiện ở cả Điều 24 (d04) và Điều 25 (chuyển dữ liệu ra nước ngoài).
- Trẻ em (d05 ↔ t01) và sự cố lộ dữ liệu (d06 ↔ t04) có nội dung ở cả Luật ANM lẫn ND 13.

## Tiêu chí chọn cấu hình (chốt trước khi xem test)
Chọn trên **dev** theo thứ tự ưu tiên: (1) Evidence Hit@3, (2) Hit@1, (3) chi phí tài nguyên
(số chunk, thời gian ingest). Test chỉ chạy sau khi đã chọn xong và không dùng để chỉnh lại.

## Nguy cơ rò rỉ / thiên lệch (ghi nhận)
- Người viết câu hỏi cũng là người xây pipeline; câu hỏi viết sau khi đọc nguồn nên diễn đạt có thể gần
  văn bản gốc (nguy cơ lạc quan cho retrieval).
- t01 cùng chủ đề "trẻ em" với d05 (khác Điều, khác văn bản); t05 (Điều 21 ND 13) nằm sát d05 (Điều 20) trong cùng trang 14.
- Test chỉ có 5 câu: chênh lệch 1 câu = 20 điểm phần trăm, chỉ mang tính minh họa.
- Câu hỏi được viết và kiểm chứng với sự hỗ trợ của AI (Claude); evidence được kiểm bằng so khớp chuỗi tự động
  trên văn bản đã chuẩn hóa, và tác giả cần tự rà lại đáp án mong đợi trước khi nộp.

## Thay đổi
(chưa có)
