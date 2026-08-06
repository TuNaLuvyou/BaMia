<div align="center">

# 🌍 TravelBaMia

**Hệ Thống Đặt Tour Du Lịch Thông Minh Tích Hợp AI (Local LLM - Qwen 3: 8B)**

[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=for-the-badge&logo=vite)](https://vitejs.dev/)
[![Django](https://img.shields.io/badge/Django-5+-092E20?style=for-the-badge&logo=django)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css)](https://tailwindcss.com/)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen3:8B-FF6B35?style=for-the-badge)](https://ollama.com/)

[![Tests](https://img.shields.io/badge/Tests-46%20passing-brightgreen?style=for-the-badge&logo=checkmarx)](./travel-backend)
[![GitHub last commit](https://img.shields.io/github/last-commit/TuNaLuvyou/BaMia?style=for-the-badge&color=indigo)](https://github.com/TuNaLuvyou/BaMia/commits)

</div>

---

> **Dự án thực tập cơ sở** — Xây dựng nền tảng đặt tour du lịch trực tuyến, tích hợp **AI Chatbot chạy cục bộ (Local LLM)** với công nghệ RAG, dự báo thời tiết thời gian thực và luồng thanh toán hoàn chỉnh.

---

## ✨ Tính Năng Nổi Bật

### 🤖 Trợ Lý AI Đa Năng (Local AI Chatbot — Qwen 3: 8B)

Tính năng flagship của dự án: AI Chatbot chạy **hoàn toàn cục bộ** qua Ollama, không phụ thuộc cloud, bảo mật dữ liệu tuyệt đối.

- **RAG (Retrieval-Augmented Generation):** Tự động phát hiện địa điểm người dùng hỏi, nạp dữ liệu chi tiết từ tài liệu hệ thống để trả lời chính xác — loại bỏ hoàn toàn hiện tượng AI "bịa" (hallucination).
- **Database-Aware:** AI nhận diện trạng thái người dùng (giỏ hàng, lịch sử đơn hàng) để tư vấn cá nhân hóa.
- **Streaming Response:** Phản hồi AI hiển thị từng từ theo thời gian thực (token streaming).
- **UI Card Rendering:** Tự động chèn thẻ Tour động vào cuộc hội thoại để người dùng đặt tour ngay lập tức.
- **Smart Budget Parser:** Hiểu ngân sách tự nhiên — `"dưới 2,5 triệu"` → `2.500.000 VNĐ`, `"500k"` → `500.000 VNĐ`.
- **Tự bảo vệ quyền riêng tư:** Lịch sử chat tự xóa sau 30 phút không hoạt động.

### 📅 Lịch Trình & Dự Báo Thời Tiết

- Giao diện lịch **FullCalendar** hiển thị 35 ngày, đồng bộ với các tour đã đặt.
- **OpenWeather API:** Hiển thị widget nhiệt độ & biểu tượng thời tiết trực tiếp tại ô lịch của từng tour theo địa điểm thực tế.
- Bộ lọc đơn hàng trực quan qua màu sắc: Đã thanh toán / Chờ thanh toán / Trong giỏ hàng.

### 🛍️ Luồng Đặt Tour & Thanh Toán

- Đặt nhiều tour cùng lúc, quản lý số lượng chỗ trống tự động (`available_slots`).
- Hỗ trợ thanh toán mock qua VNPAY / MoMo / Stripe với IPN Webhook Signature Verification.
- **Soft Delete thông minh:** Đơn hàng xóa → vào thùng rác → đếm ngược 30 ngày → cho phép khôi phục bất kỳ lúc nào.

### 🔐 Bảo Mật & Hiệu Năng

- **JWT Authentication** (60 phút Access Token + Refresh Token).
- **Rate Limiting (DRF Throttling):** Bảo vệ tất cả endpoint khỏi brute-force.
- **Anti-Replay IPN:** Mỗi webhook chỉ được xử lý đúng một lần.
- **Atomic Transactions:** Đảm bảo tính toàn vẹn dữ liệu khi đặt tour (không bao giờ trừ slot khi thanh toán thất bại).

---

## 🛠️ Tech Stack

| Layer | Công nghệ |
|---|---|
| **Frontend** | React 19, Vite 5, Tailwind CSS, FullCalendar, Axios, Lucide React |
| **Backend** | Django 5+, Django REST Framework, Simple JWT |
| **Database** | PostgreSQL 15 (Docker) |
| **AI Engine** | Ollama Local LLM (**Qwen 3: 8B**), RAG Pipeline |
| **External APIs** | OpenWeather Map API |
| **Security** | JWT (60min), DRF Throttling, Anti-Replay IPN, Atomic Transactions |
| **Testing** | Django `unittest` — 46 test cases (bookings, users, reviews, payments, chatbot) |
| **DevOps** | Docker & Docker Compose |

---

## 📂 Cấu Trúc Dự Án

```text
.
├── travel-backend/         # Django REST API
│   ├── bookings/           # Đặt tour, giỏ hàng, lịch trình, soft delete
│   ├── payments/           # Thanh toán, IPN webhook, anti-replay
│   ├── reviews/            # Đánh giá tour, đồng bộ rating tự động
│   ├── chatbot/            # AI Chatbot: RAG + Budget Parser + Streaming
│   ├── tours/              # Quản lý tour & địa điểm
│   ├── users/              # Auth: Register, Login, JWT, Reset Password
│   └── core/               # Django settings, URL routing
├── travel-frontend/        # React + Vite SPA
│   └── src/
│       ├── pages/          # Trang: Home, Tours, Cart, Payment, Calendar, Chatbot
│       ├── components/     # UI Components tái sử dụng
│       └── context/        # Auth Context, Cart Context
└── docker-compose.yml      # PostgreSQL container
```

---

## 🚀 Hướng Dẫn Cài Đặt

### Yêu cầu hệ thống
- **Python** ≥ 3.10 | **Node.js** ≥ 18 | **Docker & Docker Compose** | **Ollama**

### 1. Khởi chạy Database (PostgreSQL)

```bash
docker-compose up -d
```

### 2. Cấu hình & Khởi chạy Backend

```bash
cd travel-backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Sao chép .env.example thành .env và điền thông tin
cp .env.example .env

python manage.py migrate
python manage.py runserver
```

**Nội dung `.env` backend:**
```env
SECRET_KEY=your_secret_key_here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=bamia_db
DB_USER=bamia
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=5432

OLLAMA_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://127.0.0.1:11434

OPENWEATHER_API_KEY=your_openweather_key
PAYMENT_WEBHOOK_SECRET=your_webhook_secret
```

### 3. Khởi chạy AI (Ollama + Qwen 3: 8B)

```bash
# Tải model (lần đầu, ~5GB)
ollama pull qwen3:8b
# Ollama tự chạy nền tại http://127.0.0.1:11434
```

### 4. Cấu hình & Khởi chạy Frontend

```bash
cd travel-frontend
npm install
cp .env.example .env  # Điền VITE_OPENWEATHER_API_KEY & VITE_PAYMENT_WEBHOOK_SECRET
npm run dev
```
> App: `http://localhost:5173/`

### 5. Chạy Kiểm Thử Tự Động

```bash
cd travel-backend
python manage.py test
# Expected: Ran 46 tests ... OK
```

---

*Phát triển bởi **TuNa** — Dự án Thực Tập Cơ Sở.*
