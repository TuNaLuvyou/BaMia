# Phase 0 — Khảo sát mã nguồn hiện trạng

> Mục đích: ghi lại **chính xác** những gì đang có trước khi thêm bộ phân loại ý định, làm mốc so sánh
> "trước / sau" cho báo cáo. Mọi tham chiếu dưới đây là `file:dòng` tại thời điểm khảo sát
> (commit nền `2c7b733`).

## 1. Phiên bản môi trường

| Thành phần | Phiên bản ghi nhận | Cách xác nhận |
|---|---|---|
| Python | 3.14.3 | `python --version` |
| Django | 6.0.4 | `python -c "import django; print(django.get_version())"` |
| Django REST Framework | 3.17.1 | `python -c "import rest_framework; print(rest_framework.VERSION)"` |
| scikit-learn / pandas | **chưa cài** trước Phase 1 | `python -c "import sklearn"` → `ModuleNotFoundError` |
| Node.js | v24.14.0 | `node --version` |
| npm | 11.9.0 | `npm --version` |
| React | ^19.2.4 | `travel-frontend/package.json:19` |
| Vite | ^8.0.0 (build thực tế 8.0.16) | `package.json:35`, log `npm run build` |
| axios | ^1.13.6 | `package.json:16` |
| react-router-dom | ^7.13.1 | `package.json:21` |
| PostgreSQL | không chạy trên máy khảo sát | `Get-Service *postgres*` → rỗng; `manage.py test` báo `connection refused 127.0.0.1:5432` |
| Docker | 29.7.2 nhưng daemon không chạy | `docker ps` → `cannot find ... dockerDesktopLinuxEngine` |

Cấu hình DB: `travel-backend/core/settings.py:103-112` (PostgreSQL, đọc từ biến môi trường
`DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT`).

**Cách chạy test của dự án:** `python manage.py test` (từ `travel-backend/`). Do PostgreSQL không
chạy trên máy khảo sát, kết quả nền bên dưới được chạy với một `settings` tạm **nằm ngoài repo**
(`%TEMP%/bamia_test_settings/test_settings_sqlite.py`, kế thừa `core.settings` và trỏ
`DATABASES` sang SQLite in-memory). Không thêm file này vào repo.

## 2. Xác nhận cấu hình

- `chatbot` đã có trong `INSTALLED_APPS`: `travel-backend/core/settings.py:55`.
- Django admin đang bật: `django.contrib.admin` tại `settings.py:40`; `admin/` được route tại
  `core/urls.py:36` (`CustomAdminDashboardView`), `admin/login/` tại `core/urls.py:33`.
- `chatbot` **không có** `urls.py` riêng; route chatbot nằm ở `core/urls.py:70-71`:
  - `/api/chat/` → `ChatbotAPIView`
  - `/api/chat/health/` → `OllamaHealthView`
- `chatbot/migrations/` chỉ có `__init__.py` → model mới cần migration đầu tiên của app.
- `chatbot/models.py` và `chatbot/admin.py` hiện là file trống (chỉ import + comment).
- `chatbot/tests.py` chỉ có `BudgetExtractionTests` (4 test), `chatbot/tests.py:1-23`.

## 3. Bản đồ các điểm sẽ can thiệp

### 3.1. Backend `travel-backend/chatbot/views.py`

| Nội dung | Vị trí |
|---|---|
| Hằng số Ollama (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, timeout, retries) | `views.py:14-19` |
| `OllamaHealthView` (AllowAny, 3 trạng thái ok/offline/timeout) | `views.py:22-39` |
| `_stream_ollama()` — generator yield `{"token","done"}` | `views.py:42-75` |
| `_extract_budget()` — regex ngân sách | `views.py:78-113` |
| `ChatbotAPIView` (`IsAuthenticated`) | `views.py:116-311` |
| Đọc `message`, `system_instruction`, `history`, `stream`, `loaded_destinations` | `views.py:120-125` |
| **`security_keywords` + trả lời từ chối cố định** | `views.py:131-138` |
| Quét `Destination` theo tên/keywords | `views.py:141-160` |
| Chọn địa điểm nạp: direct match hay `loaded_destinations` | `views.py:162-173` |
| Đọc file `.txt`, cắt 3000 ký tự, dựng `rag_context` | `views.py:176-192` |
| Ngân sách đa lượt (history[-6:] + câu hiện tại) | `views.py:195-200` |
| Dựng system prompt dự phòng + `<DANH_SACH_TOUR>` | `views.py:203-239` |
| Ghép history (10 tin) | `views.py:248-252` |
| Nhét RAG + tour list vào **user message cuối** (chống recency bias) | `views.py:254-270` |
| Stream + retry + **yield meta chunk** | `views.py:273-297`, meta tại `views.py:279-282` |
| Nhánh không stream | `views.py:299-311` |

Hợp đồng SSE hiện tại (phải giữ tương thích ngược):
```json
{"token": "...", "done": false}
{"token": "", "done": true}
{"meta": true, "matched_destinations": ["Đà Lạt"]}
```

### 3.2. Frontend

| Nội dung | Vị trí |
|---|---|
| **Regex `needsRefresh`** (làm mới giỏ hàng/booking trước khi gửi) | `travel-frontend/src/components/Chatbot.jsx:151`, dùng tại `Chatbot.jsx:166-169` |
| `fetchContextData` — gọi `tours/`, `chat/health/`, `bookings/`, `cart/` | `Chatbot.jsx:98-135` |
| Gọi `buildSystemPrompt(tours, bookings, cart, user)` | `Chatbot.jsx:127` |
| `handleSendMessage` — parseBudget + filter tour + gọi `streamChat` | `Chatbot.jsx:146-255` |
| Xử lý `[ESCALATE]` (fallback văn bản) | `Chatbot.jsx:243` (`fullText.includes("[ESCALATE]")`), lưu `isEscalated` tại `Chatbot.jsx:247` |
| Nút "Tiếp tục với AI / Gặp nhân viên" | `travel-frontend/src/components/chatbox/ChatbotMessages.jsx:30-48`; handler `Chatbot.jsx:269-275` (điều hướng `/contact`) |
| `cleanBotReply` (bóc `[TOUR_CARD]`, `[ESCALATE]`, `[TASK_COMPLETE]`, mọi `[...]`) | `travel-frontend/src/components/chatbox/ChatbotUtils.js:66-72` |
| `buildSystemPrompt` (dựng prompt + `<DANH_SACH_TOUR>`) | `ChatbotUtils.js:39-64` |
| `parseBudget`, `filterToursByBudget` | `ChatbotUtils.js:8-37` |
| SSE reader, nhận meta chunk | `travel-frontend/src/components/chatbox/useStreamChat.js:43-78` (meta tại `:55-58`) |
| Gọi API có JWT + refresh | `travel-frontend/src/api/axios.js:34-92` |

**Phát hiện quan trọng:** `buildSystemPrompt` chỉ khai báo **một** tham số `tours`
(`ChatbotUtils.js:39`) nhưng `Chatbot.jsx:127` truyền 4 tham số `(tours, bookings, cart, user)`.
Nghĩa là hiện tại frontend **không** đưa dữ liệu booking/cart vào prompt. Vì vậy khối
"TRẠNG THÁI TÀI KHOẢN" ở Phase 2 sẽ do **backend đọc DB của chính `request.user`**, không phụ thuộc
dữ liệu frontend gửi lên (đúng yêu cầu bảo mật).

### 3.3. Model dữ liệu thật dùng cho `account_status`

`travel-backend/bookings/models.py`:

- `Booking` (`:5-20`): `user` FK → `auth.User` (`related_name='bookings'`), `tour` FK, `date` (DateField),
  `number_of_people`, `total_price` (Decimal 10,2), `status` ∈ `Pending/Confirmed/Paid/Cancelled`,
  `created_at`, `deleted_at` (soft delete), `show_on_calendar`.
- `Cart` (`:22-28`): `user` FK (`related_name='cart'`), `tour` FK, `date` (nullable), `number_of_people`,
  `added_at`, `show_on_calendar`.
- `Tour` (`tours/models.py:19-29`): `title`, `location` FK → `Destination`, `price` (Decimal 10,2), `duration`…
- `Transaction` (`payments/models.py:5-16`): `user`, `bookings` M2M, `amount`, `payment_method`, `status`
  (`Pending/Success/Failed`) — **không** dùng ở Phase 2 để giữ phạm vi nhỏ; `Booking.status` đã đủ.

Quy ước hiện có khi truy vấn booking của người dùng (dùng lại để nhất quán):
`Booking.objects.filter(user=request.user, deleted_at__isnull=True)` (`bookings/views.py:22-27`);
`Cart.objects.filter(user=request.user)` (`bookings/views.py:170-171`).

## 4. Kết quả chạy NỀN trước khi sửa

### 4.1. Backend

```powershell
cd travel-backend
python manage.py test chatbot
# Không có PostgreSQL → django.db.utils.OperationalError: connection to server at "127.0.0.1",
# port 5432 failed: Connection refused
```

Chạy với settings SQLite tạm (ngoài repo):

```powershell
cd travel-backend
$env:PYTHONPATH="$env:TEMP\bamia_test_settings"; $env:DJANGO_SETTINGS_MODULE="test_settings_sqlite"
python manage.py test chatbot
```

Kết quả:
```
Found 4 test(s).
System check identified no issues (0 silenced).
Ran 4 tests in 0.002s
OK
```

### 4.2. Frontend

```powershell
cd travel-frontend
npm install          # node_modules chưa có; cài 1 lần
npm run lint
npm run build
```

`npm run build`: **THÀNH CÔNG** — `✓ 1826 modules transformed`, `✓ built in 1.70s`
(cảnh báo chunk > 500 kB, không phải lỗi).

`npm run lint`: **THẤT BẠI từ trước khi sửa** — `✖ 21 problems (17 errors, 4 warnings)`.
Đây là nợ kỹ thuật có sẵn, tập trung ở các file ngoài phạm vi chatbot:

| File | Lỗi |
|---|---|
| `src/api/axios.js:28,72` | `no-unused-vars` |
| `src/components/Chatbot.jsx:66,88,150` | `react-hooks/set-state-in-effect`, unused var |
| `src/context/AuthContext.jsx` | `no-unused-vars`, hooks |
| `src/pages/Home.jsx`, `ItineraryPage.jsx`, `Login.jsx`, `MyBookings.jsx`, `Profile.jsx`, `Register.jsx`, `TourDetails.jsx`, `Tours.jsx` | `no-unused-vars`, `set-state-in-effect`, `exhaustive-deps` |

Không file nào thuộc `src/components/chatbox/`. Vì quy tắc "không sửa ngoài phạm vi chatbot", Phase 5
sẽ (a) chạy `npx eslint src/components/chatbox` cho phần mới và (b) ghi nhận `npm run lint` toàn repo
vẫn đỏ do lỗi có sẵn — **không** sửa các trang không liên quan.

## 5. Kết luận khảo sát

1. Chatbot hiện là **luật cứng**: `security_keywords` (regex/từ khóa) + `needsRefresh` + `[ESCALATE]`,
   không có mô hình học máy, không có log, không có đánh giá.
2. Điểm chèn router hợp lý: ngay sau kiểm tra `user_message` và **trước** khối `security_keywords`
   trong `ChatbotAPIView.post`, vì router cần biết `blocked` để bỏ qua Ollama.
3. Meta chunk chỉ cần **thêm** field → `useStreamChat.js` cũ vẫn chạy (nó chỉ đọc
   `parsed.meta`, `matched_destinations`, `token`, `error`, `done`).
4. Frontend không gửi booking/cart trong prompt ⇒ `account_status` phải đọc DB ở backend.
5. Không có `intent_classifier/` ở gốc repo tại thời điểm khảo sát
   (`Get-ChildItem -Recurse -Filter intent_core.py` → rỗng). Vì vậy Phase 1 **tạo mới** mô-đun
   `chatbot/ml/` theo đúng thiết kế đã mô tả trong đề bài (TF-IDF ký tự + 4 thuật toán + stratified
   k-fold), không sửa lại mã có sẵn.
