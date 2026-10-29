# Đạo đức Dữ liệu, Quyền Riêng tư & Các Đánh đổi Kỹ thuật (Ethics & Trade-offs)

Tài liệu này phân tích các khía cạnh đạo đức, bảo vệ dữ liệu người dùng, quản trị rủi ro an toàn thông tin và các quyết định đánh đổi kỹ thuật (trade-offs) trong thiết kế bộ phân loại ý định của Chatbot TravelBaMia.

---

## 1. Quyền riêng tư & Bảo vệ Dữ liệu Người dùng (Privacy by Design)

### 1.1. Ẩn danh hóa Nhật ký Truy vấn (`IntentLog`)
- **Nguyên tắc không lưu định danh**: Bảng `IntentLog` được thiết kế có chủ đích **KHÔNG** chứa trường `user_id`, `ip_address`, `session_token` hay bất kỳ thông tin nhận dạng cá nhân nào (PII). Khi ghi nhận một lượt phân loại, hệ thống chỉ lưu:
  - `text`: Nội dung câu hỏi của người dùng (bị cắt ngắn tối đa 500 ký tự để hạn chế việc vô tình lưu trữ các đoạn văn bản nhạy cảm quá dài).
  - `predicted`: Nhãn dự đoán của mô hình.
  - `confidence`: Điểm tin cậy xác suất.
  - `routed`: Cờ xác nhận câu hỏi có vượt ngưỡng hay không.
- **Giới hạn thời gian lưu trữ (TTL - Time to Live)**: Dữ liệu nhật ký được định kỳ dọn dẹp bằng command `purge_intent_logs --days 90`. Mọi bản ghi cũ hơn 90 ngày sẽ được tự động xóa vĩnh viễn, tuân thủ nguyên tắc giảm thiểu dữ liệu (Data Minimization) theo GDPR và Luật Bảo vệ Dữ liệu Cá nhân.

### 1.2. Bảo vệ Tuyệt đối Dữ liệu Tài khoản (`account_status`)
- **Nguyên tắc Zero-Trust Client**: Client (Frontend) tuyệt đối không có quyền gửi danh sách mã đơn hàng, ID tour đã đặt hay số tiền lên API để nhờ chatbot đọc. Dữ liệu từ trình duyệt có thể bị giả mạo, can thiệp hoặc nghe lén.
- **Xác thực và phân quyền phía Server**:
  - Endpoint `/api/chat/` yêu cầu xác thực JWT (`IsAuthenticated`).
  - Khi ý định `account_status` được kích hoạt, hàm `build_account_status_context` **CHỈ** truy vấn các bản ghi `Booking` và `Cart` mà có khóa ngoại `user=request.user` (được giải mã từ chữ ký số JWT hợp lệ).
  - Không người dùng nào có thể xem được lịch trình, mã đơn hay chi tiêu của người dùng khác thông qua chatbot.

---

## 2. Quản trị Rủi ro An toàn & Toàn vẹn Dữ liệu (Data Poisoning Prevention)

### 2.1. Nguy cơ Đầu độc Dữ liệu qua Nút Phản hồi (👍/👎)
Trong các hệ thống AI mở, nếu cho phép người dùng tự do gắn nhãn và hệ thống tự động học lại (Auto-retrain) từ phản hồi đó, kẻ xấu có thể thực hiện tấn công đầu độc dữ liệu (Data Poisoning Attack):
- *Kịch bản*: Kẻ tấn công cố tình spam nút 👍 cho các câu lệnh chứa injection hoặc spam 👎 cho các câu hỏi tour hợp lệ, nhằm làm sai lệch trọng số mô hình hoặc mở ra "cửa sau" (backdoor).

### 2.2. Cơ chế Phòng ngừa: Kiểm duyệt Bắt buộc (Human-in-the-Loop)
Để loại trừ triệt để nguy cơ này:
1. **Phản hồi của người dùng chỉ là tín hiệu ưu tiên**: Nút 👍/👎 trên giao diện chỉ ghi giá trị `feedback` (`+1` hoặc `-1`) vào bản ghi `IntentLog`. Hệ thống **KHÔNG BAO GIỜ** tự động huấn luyện lại từ trường `feedback` này.
2. **Kiểm duyệt bởi Quản trị viên (Admin Review)**:
   - Trong Django Admin, Admin sử dụng bộ lọc `confidence_range` và `feedback = -1` để tìm các câu hỏi mà mô hình phân loại chưa tốt hoặc bị người dùng phàn nàn.
   - Admin đọc trực tiếp câu hỏi và thực hiện Action gán `corrected_label` một cách thủ công.
   - Command `export_intent_feedback` chỉ xuất các dòng **ĐÃ ĐƯỢC ADMIN GÁN `corrected_label`**.
3. **Giới hạn tần suất (Rate Limiting)**: Endpoint `/api/chat/feedback/` áp dụng `ScopedRateThrottle` (tối đa 30 lượt/phút) và ràng buộc một `log_id` chỉ được gửi phản hồi đúng 1 lần.

---

## 3. Phân tích Loại Lỗi & Chiến lược Ngưỡng Tin cậy (Threshold Strategy)

Trong bài toán phân loại ý định, hai loại sai lầm mang lại mức độ rủi ro hoàn toàn khác nhau:

| Loại lỗi | Biểu hiện thực tế | Hậu quả | Mức độ nghiêm trọng |
|---|---|---|:---:|
| **Sai lầm loại I (False Positive của `blocked`)** | Khách hỏi tour bình thường bị nhận diện nhầm là `blocked`. | Khách nhận câu từ chối an toàn và cần hỏi lại hoặc diễn đạt rõ ràng hơn. | **Thấp** (Chỉ ảnh hưởng tạm thời trải nghiệm) |
| **Sai lầm loại II (False Negative của `blocked`)** | Câu hỏi tấn công SQL / xem mã nguồn bị nhận diện nhầm thành `chitchat` hoặc `tour_search`. | Câu lệnh vượt qua bộ lọc và đi thẳng vào LLM, có nguy cơ gây rò rỉ prompt hoặc tốn tài nguyên. | **Rất cao** (Rủi ro an toàn hệ thống) |

### Chiến lược Thiết lập Ngưỡng Bất đối xứng (Asymmetric Thresholds)
Dựa trên phân tích rủi ro ở trên, hệ thống thiết lập bảng ngưỡng tin cậy phân hóa:

1. **`blocked` (Ngưỡng = 0.35 - Thấp nhất)**:
   - Ưu tiên tối đa hóa độ bao phủ (Recall). Chỉ cần mô hình có nghi ngờ (xác suất >= 35%), hệ thống sẽ kích hoạt phản hồi từ chối an toàn để bảo vệ LLM.
2. **`complaint_support` (Ngưỡng = 0.40)**:
   - Khách đang bức xúc cần được hỗ trợ kịp thời. Nhận diện sớm để kích hoạt cờ `escalate=true` và mời gặp nhân viên tư vấn.
3. **`tour_search`, `destination_info`, `account_status` (Ngưỡng = 0.45)**:
   - Đảm bảo độ tin cậy cân bằng giữa việc kích hoạt đúng nghiệp vụ và việc rơi về luồng xử lý đầy đủ.
4. **`chitchat` (Ngưỡng = 0.50 - Cao nhất)**:
   - Vì nhánh `chitchat` sẽ cắt bỏ toàn bộ RAG và danh sách tour, nên nếu một câu hỏi tìm tour bị nhận diện nhầm thành `chitchat`, khách sẽ không nhận được thông tin tour mong muốn. Do đó, nhãn này đòi hỏi độ tin cậy cao nhất mới được định tuyến.

---

## 4. Các Đánh đổi Kỹ thuật (Technical Trade-offs)

### 4.1. TF-IDF Ký tự + Thuật toán Cổ điển VS Mô hình Transformer / BERT
| Tiêu chí | TF-IDF (char n-grams) + SVM / Naive Bayes *(Được chọn)* | Fine-tuned PhoBERT / Multilingual BERT | Dùng thêm 1 LLM nhỏ làm Router |
|---|:---:|:---:|:---:|
| **Độ trễ suy luận** | **~4.2 ms** (cực nhanh) | ~80 ms – 150 ms | ~400 ms – 1200 ms |
| **Tài nguyên RAM/VRAM** | **~1.5 MB RAM** | ~500 MB – 1 GB RAM/VRAM | ~2 GB – 4 GB VRAM |
| **Phụ thuộc phần cứng** | Chạy tốt trên mọi CPU cơ bản | Cần GPU hoặc tối ưu ONNX | Cạnh tranh VRAM với Ollama qwen3:8b |
| **Xử lý tiếng Việt không dấu & Lỗi gõ** | **Rất tốt** (nhờ char n-grams 2..5) | Phụ thuộc tokenizer từ điển | Tốt |
| **Khả năng giải thích (Interpretability)** | Cao (trọng số TF-IDF, xác suất rõ ràng) | Hộp đen | Khó kiểm soát xác suất tuyệt đối |

**Kết luận đánh đổi**: Với bài toán phân loại 6 ý định trong phạm vi đồ án du lịch, việc sử dụng TF-IDF ký tự kết hợp SVM tuyến tính (hoặc Naive Bayes) mang lại tỷ suất hiệu năng trên chi phí (Performance/Cost Ratio) vượt trội: giảm tải hoàn toàn cho GPU, độ trễ chỉ 4ms, loại bỏ hiện tượng nghẽn cổ chai (bottleneck) trước LLM.

### 4.2. Cổng Chất lượng (Quality Gate) trong Huấn luyện lại
Hàm `should_replace` trong quy trình `retrain_intent` áp dụng 2 điều kiện tiên quyết:
$$\text{Macro-F1}_{\text{candidate}} \ge \text{Macro-F1}_{\text{old}} \quad \text{VÀ} \quad \text{Recall}(\text{blocked})_{\text{candidate}} \ge \text{Recall}(\text{blocked})_{\text{old}}$$
- **Đánh đổi**: Chấp nhận từ chối một mô hình ứng viên có thể có Macro-F1 tổng thể cao hơn một chút, nếu mô hình đó làm giảm khả năng nhận diện lớp `blocked`.
- **Lý do**: An toàn hệ thống luôn được đặt ưu tiên cao hơn sự gia tăng biên tế về độ chính xác tổng thể.
