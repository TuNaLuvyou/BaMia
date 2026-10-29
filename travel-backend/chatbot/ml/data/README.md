# Dữ liệu cho bộ phân loại ý định

## `intents.csv` — dữ liệu huấn luyện

Định dạng: UTF-8, 2 cột `text,label`.

- 6 nhãn hợp lệ: `tour_search`, `destination_info`, `account_status`, `complaint_support`, `blocked`, `chitchat`.
- File hiện tại chỉ có **72 câu mẫu (12 câu/nhãn)** để chạy thử pipeline. Đây **không phải**
  dữ liệu đủ tốt để báo cáo. Mỗi nhãn cần **>= 100 câu do con người viết** (khuyến nghị 200+),
  đa dạng cách diễn đạt, có cả câu không dấu, viết tắt, sai chính tả nhẹ.

## `golden.csv` — tập đánh giá độc lập

Định dạng giống `intents.csv`, hiện **rỗng (chỉ có header)**.

Quy tắc bắt buộc:

1. **Con người viết tay**, không dùng LLM sinh, không copy từ `intents.csv`.
2. Mỗi nhãn tối thiểu 30–50 câu, càng cân bằng càng tốt.
3. Không sửa `golden.csv` sau khi đã dùng để chọn mô hình (tránh rò rỉ qua lặp lại đánh giá).
4. `validate_dataset.py` sẽ cảnh báo nếu một câu xuất hiện ở cả hai file.

## Vì sao phải tách train/golden?

`retrain_intent` so sánh mô hình cũ và ứng viên trên **cùng** `golden.csv`. Nếu golden trùng với
train, mô hình sẽ "học thuộc" và mọi con số đều vô nghĩa.
