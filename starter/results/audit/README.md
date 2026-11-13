# Quy trình chấm thủ công

**Quy tắc chọn 10 vị trí coherence (chốt trước khi xem điểm):** sắp xếp các trang nội dung theo
(`source_id`, `page`), lấy chỉ số `floor((i+0.5)*n/10)` với i = 0..9; trong mỗi trang lấy đoạn chứa ký tự
ở giữa văn bản trang. Mỗi chiến lược chấm chunk chứa vị trí đó (A: cửa sổ bắt đầu tại `mid // 450`;
B: chunk chứa đoạn đó).

- P01: luat-anm-2018 trang 5
- P02: luat-anm-2018 trang 14
- P03: luat-anm-2018 trang 22
- P04: luat-anm-2018 trang 31
- P05: luat-gddt-2023 trang 8
- P06: luat-gddt-2023 trang 16
- P07: luat-gddt-2023 trang 25
- P08: nd-13-2023 trang 4
- P09: nd-13-2023 trang 12
- P10: nd-13-2023 trang 21

**Che nhãn:** các phiếu dùng X/Y(/Z) xáo ngẫu nhiên (seed 20261113); `key.json` chứa đáp án ánh xạ, chỉ mở sau khi
điền xong mọi nhãn. Phiếu grounding/coherence không hiển thị cờ hit hay điểm tự động.

**Người chấm:** tác giả bài lab (cũng là người viết câu hỏi và xây pipeline), nên có nguy cơ thiên lệch; dù đã
che nhãn, chunk B có tiêu đề "Điều N." nên người chấm có thể đoán được chiến lược.

**Hỗ trợ AI:** phiếu được sinh bằng script (`python -m src.audit`); script không gán điểm nào.
Nếu dùng AI để gợi ý nhãn, phải ghi rõ phương pháp và rà lại từng nhãn (RULES.md).
