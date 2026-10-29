# Khung Kết quả Đánh giá Mô hình (Template Báo cáo Đồ án)

> **QUY TẮC BẮT BUỘC:** Không tự tiện bịa đặt số liệu hoặc điền số liệu giả.
> Các bảng dưới đây là khung chuẩn để nhóm sinh viên điền **SỐ LIỆU THỰC TẾ** sau khi đã thu thập đủ dữ liệu huấn luyện (>= 100 mẫu/nhãn) và viết tập `golden.csv` độc lập bằng tay.
> Các nguồn dữ liệu được tự động kết xuất từ các lệnh trong `docs/ml/02_how_to_run.md`.

---

## 1. Thông tin Tập dữ liệu Thực nghiệm

- **Ngày thực nghiệm**: `[YYYY-MM-DD]`
- **Tập huấn luyện (`intents.csv`)**: `[...]` mẫu
- **Tập kiểm thử độc lập (`golden.csv`)**: `[...]` mẫu (do người viết độc lập, không sinh bằng LLM)
- **Phương pháp phân chia**: Stratified 5-Fold Cross-Validation

| Nhãn ý định | Ý nghĩa thực tế trong TravelBaMia | Số mẫu Train (`intents.csv`) | Số mẫu Test (`golden.csv`) |
|---|---|:---:|:---:|
| `tour_search` | Tìm kiếm, hỏi giá, lịch trình tour | `[...]` | `[...]` |
| `destination_info` | Hỏi cẩm nang, thời tiết, kinh nghiệm địa điểm | `[...]` | `[...]` |
| `account_status` | Tra cứu đơn hàng, booking, giỏ hàng cá nhân | `[...]` | `[...]` |
| `complaint_support`| Khiếu nại, phản ánh sự cố, yêu cầu gặp nhân viên | `[...]` | `[...]` |
| `blocked` | Tấn công SQL, xem mật khẩu, can thiệp mã nguồn | `[...]` | `[...]` |
| `chitchat` | Chào hỏi, cảm ơn, trò chuyện thông thường | `[...]` | `[...]` |
| **Tổng cộng** | | `[...]` | `[...]` |

---

## 2. Bảng 1: So sánh 4 Thuật toán (Stratified 5-Fold Cross-Validation)

> *Nguồn số liệu: Lấy từ file `chatbot/ml/artifacts/intent_report.json` (mục `cv`) sau khi chạy:*  
> `python manage.py train_intent --data chatbot/ml/data/intents.csv --golden chatbot/ml/data/golden.csv`

| Thuật toán | Accuracy (Mean ± Std) | Macro-F1 (Mean ± Std) | Blocked Recall (Mean ± Std) | Đánh giá / Lựa chọn |
|---|:---:|:---:|:---:|---|
| **Multinomial Naive Bayes** | `... ± ...` | `... ± ...` | `... ± ...` | `[...]` |
| **k-Nearest Neighbors (cosine)** | `... ± ...` | `... ± ...` | `... ± ...` | `[...]` |
| **SVM (Linear Kernel + Calibrated)** | `... ± ...` | `... ± ...` | `... ± ...` | `[...]` |
| **Decision Tree** | `... ± ...` | `... ± ...` | `... ± ...` | `[...]` |

- **Thuật toán được hệ thống tự động chọn**: `[Tên thuật toán có Macro-F1 cao nhất]`

---

## 3. Bảng 2: Báo cáo Chi tiết từng Lớp (Thuật toán Tốt nhất trên Out-of-Fold)

> *Nguồn số liệu: Lấy từ `chatbot/ml/artifacts/intent_report.json` (mục `best_oof_per_class`).*

| Nhãn ý định | Precision | Recall | F1-Score | Support (Số mẫu) | Ngưỡng tin cậy áp dụng |
|---|:---:|:---:|:---:|:---:|:---:|
| `tour_search` | `...` | `...` | `...` | `...` | `0.45` |
| `destination_info` | `...` | `...` | `...` | `...` | `0.45` |
| `account_status` | `...` | `...` | `...` | `...` | `0.45` |
| `complaint_support`| `...` | `...` | `...` | `...` | `0.40` |
| `blocked` | `...` | `...` | `...` | `...` | `0.35` |
| `chitchat` | `...` | `...` | `...` | `...` | `0.50` |
| **Macro Average** | `...` | `...` | `...` | `...` | - |
| **Weighted Average** | `...` | `...` | `...` | `...` | - |

---

## 4. Bảng 3: Ma trận Nhầm lẫn (Confusion Matrix)

> *Nguồn số liệu: Lấy từ `chatbot/ml/artifacts/intent_report.json` (mục `best_oof_confusion_matrix`).*  
> *(Hàng: Nhãn thực tế | Cột: Nhãn mô hình dự đoán)*

| Thực tế \ Dự đoán | tour_search | destination_info | account_status | complaint_support | blocked | chitchat |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **tour_search** | `...` | `...` | `...` | `...` | `...` | `...` |
| **destination_info** | `...` | `...` | `...` | `...` | `...` | `...` |
| **account_status** | `...` | `...` | `...` | `...` | `...` | `...` |
| **complaint_support**| `...` | `...` | `...` | `...` | `...` | `...` |
| **blocked** | `...` | `...` | `...` | `...` | `...` | `...` |
| **chitchat** | `...` | `...` | `...` | `...` | `...` | `...` |

---

## 5. Bảng 4: So sánh Đối đầu Đường cơ sở (Baseline Luật cũ VS Mô hình Học máy)

> *Nguồn số liệu: Lấy từ `chatbot/ml/artifacts/baseline_report.json` sau khi chạy:*  
> `python -m chatbot.ml.evaluate_baseline --golden chatbot/ml/data/golden.csv --model chatbot/ml/artifacts/intent_model.pkl`

| Tiêu chí so sánh | Baseline (Luật cứng cũ) | Mô hình Học máy (Mới) | Chênh lệch (ML - Baseline) |
|---|:---:|:---:|:---:|
| **Overall Accuracy** | `...` | `...` | `+...` |
| **Macro-F1 Score** | `...` | `...` | `+...` |
| **Recall lớp `blocked`** | `...` | `...` | `+...` |
| **F1: `tour_search`** | `0.0000` *(không hỗ trợ)* | `...` | `+...` |
| **F1: `destination_info`** | `0.0000` *(không hỗ trợ)* | `...` | `+...` |
| **F1: `account_status`** | `...` *(chỉ bắt regex)* | `...` | `+...` |
| **F1: `complaint_support`** | `...` *(chỉ bắt từ khóa)* | `...` | `+...` |
| **F1: `blocked`** | `...` *(chỉ bắt 8 từ khóa)* | `...` | `+...` |
| **F1: `chitchat`** | `0.0000` *(không hỗ trợ)* | `...` | `+...` |
| **Tỉ lệ câu không phân loại được (`unknown`)** | `...%` | `0.0%` *(có xác suất)* | `-...%` |

---

## 6. Bảng 5: Đo lường Hiệu năng & Tối ưu hóa Tài nguyên LLM (Latency & Routing)

> *Nguồn số liệu: Lấy từ `chatbot/ml/artifacts/latency_report.json` sau khi chạy:*  
> `python -m chatbot.ml.benchmark_latency --iterations 50`

| Chỉ số đo lường độ trễ suy luận (Inference Latency) | Giá trị thực nghiệm |
|---|:---:|
| **Thời gian trung bình (Mean)** | `... ms` |
| **Trung vị (Median / p50)** | `... ms` |
| **Phân vị 90 (p90)** | `... ms` |
| **Phân vị 95 (p95)** | `... ms` |
| **Phân vị 99 (p99)** | `... ms` |
| **Khoảng trễ (Min - Max)** | `... ms - ... ms` |

### Hiệu quả giảm tải cho LLM Local (qwen3:8b)
- **Tỉ lệ yêu cầu được định tuyến thành công**: `...%`
- **Tỉ lệ yêu cầu hoàn toàn không cần gọi LLM (nhãn `blocked`)**: `...%`
- **Thời gian tiết kiệm được cho mỗi câu `blocked`**: Tiết kiệm ~1500ms – 3000ms thời gian suy luận của Ollama và giải phóng VRAM GPU/CPU cho các yêu cầu khác.
