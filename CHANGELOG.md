# CHANGELOG & Hướng Dẫn Kiểm Thử

> Cập nhật gần nhất: 2026-08-02 · Commit `076436e`

## Tóm tắt thay đổi

### 1. Thêm test tự động (46 test) — trước đây là 0

| App | File test | Số test | Nội dung phủ |
|-----|-----------|---------|--------------|
| bookings | `travel-backend/bookings/tests.py` | 14 | Đặt tour (trừ/hoàn `available_slots`), không đủ chỗ → 400, soft-delete/trash/restore/cancel, permanent-delete/empty-trash, cô lập dữ liệu giữa các user, giỏ hàng, lịch trình |
| users | `travel-backend/users/tests.py` | 12 | Register, login (đúng/sai mật khẩu), forgot-password (không lộ email tồn tại), reset-password (token hợp lệ/không hợp lệ), change-password, profile |
| reviews | `travel-backend/reviews/tests.py` | 8 | Signal đồng bộ `Tour.rating` (tạo/xóa/average/reset về 0) + phân quyền owner/admin |
| payments | `travel-backend/payments/tests.py` | 7 | Luồng create-payment từ giỏ hàng, webhook chặn chữ ký sai, đánh dấu Paid, giữ Pending khi fail, **chống replay IPN**, transaction không tồn tại |
| chatbot | `travel-backend/chatbot/tests.py` | 5 | Logic `_extract_budget` (parse ngân sách: `2 triệu`, `500k`, `2.000.000`, ...) |

### 2. Fix bug parse ngân sách chatbot

- `travel-backend/chatbot/views.py` — sửa regex `[\d.]+` → `[\d.,]+` cho hai dạng `X triệu` và `Xk/nghìn`.
- **Trước:** `"2,5 triệu"` bị parse thành **5.000.000** (regex nhảy sang số `5` vì không cho dấu phẩy).
- **Sau:** `"2,5 triệu"` → **2.500.000** đúng.

### 3. Sửa mismatch model Ollama

- `travel-backend/chatbot/views.py:15` — đổi default `OLLAMA_MODEL` từ `glm-5.2:cloud` → `qwen2.5:1.5b`, khớp với README và `.env.example`.
- Nếu bạn vẫn muốn dùng `glm-5.2:cloud`, chỉ cần đặt `OLLAMA_MODEL=glm-5.2:cloud` trong `travel-backend/.env` (biến env luôn override default).

### 4. Tách webhook signature khỏi hardcode

- `travel-frontend/src/pages/Payments.jsx` — chữ ký sandbox giờ đọc từ biến môi trường:
  ```
  const webhookSignature = import.meta.env.VITE_PAYMENT_WEBHOOK_SECRET || 'mock_signature_12345';
  ```
- `travel-frontend/.env.example` (mới, giờ được track bởi git) và `travel-frontend/.env` — thêm:
  ```
  VITE_PAYMENT_WEBHOOK_SECRET=mock_signature_12345
  ```
  > Giá trị này phải **khớp** với `PAYMENT_WEBHOOK_SECRET` ở backend.
- `travel-frontend/.gitignore` — thêm `!.env.example` để file env mẫu không bị ignore.
- `README.md` — bổ sung `VITE_BACKEND_BASE_URL` và `VITE_PAYMENT_WEBHOOK_SECRET` vào block env frontend.

---

## Cách chạy kiểm thử

### Yêu cầu
- **Python 3.10+** với Django & các package trong `travel-backend/requirements.txt`
- **PostgreSQL đang chạy** (docker: `docker compose up -d` — trong repo đã có sẵn `docker-compose.yml`)

### Chạy toàn bộ test
```bash
cd travel-backend
source venv/bin/activate        # hoặc kích hoạt môi trường của bạn
python manage.py test
```
Kết quả mong đợi:
```
Ran 46 tests in ~25s
OK
```
> Test tự tạo database tạm (`test_bamia_db`) và xóa sau khi chạy xong — không ảnh hưởng dữ liệu thật.

### Chạy riêng từng app (nếu muốn debug nhanh)
```bash
python manage.py test bookings    # đặt tour / giỏ hàng / lịch trình
python manage.py test users       # đăng ký / đăng nhập / reset mật khẩu
python manage.py test reviews     # đồng bộ rating
python manage.py test payments    # thanh toán + webhook IPN
python manage.py test chatbot     # parse ngân sách AI
```

### Kiểm tra frontend build
```bash
cd travel-frontend
npm run build       # đảm bảo không lỗi cú pháp sau khi sửa Payments.jsx
```
hoặc `npm run dev` để chạy thử thanh toán mock: mở trang thanh toán → chọn VNPAY/MoMo/Stripe → bấm "Xác nhận Thanh toán" → đơn hàng chuyển sang Paid.

---

## Lưu ý về bản demo
- Module thanh toán là **mock/sandbox** (frontend tự gọi webhook IPN), không tích hợp cổng thật VNPAY/MoMo/Stripe.
- Chữ ký webhook vẫn là giá trị mặc định cho môi trường demo. Khi đưa lên production phải để backend nhận IPN thật từ nhà cung cấp và **không bao giờ** đặt secret thật vào frontend.
