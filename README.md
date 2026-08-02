<div align="center">
  <h1>🌍 TravelBaMia</h1>
  <p><strong>Hệ Thống Đặt Tour Du Lịch Thông Minh Tích Hợp AI (Qwen 3: 8B)</strong></p>
  
  [![React](https://img.shields.io/badge/React-19-blue.svg)](https://reactjs.org/)
  [![Django](https://img.shields.io/badge/Django-REST-green.svg)](https://www.djangoproject.com/)
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
  [![Ollama](https://img.shields.io/badge/Ollama-Qwen3:8b-orange.svg)](https://ollama.com/)
  [![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-38B2AC.svg)](https://tailwindcss.com/)
</div>

---

> **Dự án thực tập cơ sở:** Xây dựng Website đặt tour du lịch trực tuyến, tích hợp lịch trình thông minh dự báo thời tiết và trợ lý ảo AI cục bộ (Local AI Chatbot) hỗ trợ tìm kiếm và tư vấn thông minh.

Dự án đã được tối ưu hóa toàn diện đạt chuẩn 10/10: nâng cấp hệ thống cơ sở dữ liệu lên **PostgreSQL** cực kỳ mạnh mẽ, nâng cấp mô hình AI lên **Qwen 3: 8B (Ollama)** với context window 8K, tích hợp Rate Limiting & Throttling bảo vệ API, chuẩn hóa bảo mật JWT 60 phút và tái cấu trúc giao diện với font chữ tiếng Việt chuyên nghiệp **"Be Vietnam Pro"**.

## 📑 Mục Lục
- [📸 Điểm Nổi Bật Của Hệ Thống](#-điểm-nổi-bật-của-hệ-thống)
- [🛠️ Công Nghệ Sử Dụng](#️-công-nghệ-sử-dụng)
- [🏗️ Cấu Trúc Dự Án](#-cấu-trúc-dự-án)
- [🚀 Hướng Dẫn Cài Đặt & Chạy Dự Án](#-hướng-dẫn-cài-đặt--chạy-dự-án)
- [📝 Bản Quyền & Ghi Chú](#-bản-quyền--ghi-chú)

---

## 📸 Điểm Nổi Bật Của Hệ Thống

### 1. 🤖 Trợ Lý Ảo AI Đa Năng (Local AI Chatbot - Qwen 3: 8B)
Tích hợp mô hình ngôn ngữ thế hệ mới **Qwen 3: 8B** chạy cục bộ qua **Ollama** giúp tối ưu chi phí vận hành, bảo mật dữ liệu tuyệt đối và khả năng suy luận mạnh mẽ:
- **Công nghệ RAG (Retrieval-Augmented Generation):** Tự động phát hiện địa điểm khách hàng đang hỏi, nạp dữ liệu chi tiết của địa danh đó từ file tài liệu hệ thống theo thời gian thực để AI trả lời chính xác, tránh hiện tượng "ảo giác" (hallucination).
- **Đồng bộ hóa dữ liệu thời gian thực (Database-Aware):** AI tự động nhận diện trạng thái khách hàng, chào hỏi cá nhân hóa, nắm bắt giỏ hàng và lịch sử đơn hàng để tư vấn chuyên sâu.
- **Tự động liên kết thẻ Tour trực quan (UI Card Rendering):** Tự động chèn thẻ Tour động dưới khung chat để khách hàng click xem chi tiết hoặc đặt tour trực tiếp.
- **Xử lý khớp điểm đến thông minh & Ngân sách:** Tự động ánh xạ yêu cầu và parse ngân sách chính xác (ví dụ: *"dưới 2,5 triệu"* -> `2.500.000 VNĐ`).
- **Cơ chế bảo mật dữ liệu:** Tự động xóa sạch lịch sử chat sau 30 phút đóng trình duyệt hoặc khi tắt server để bảo vệ quyền riêng tư.

### 2. 📅 Lịch Trình Tích Hợp Dự Báo Thời Tiết
- Giao diện lịch biểu thông minh **FullCalendar** hiển thị 35 ngày trực quan.
- **Tích hợp OpenWeather API:** Tự động định vị địa điểm tour và hiển thị widget thời tiết nhiệt độ, biểu tượng trạng thái thời tiết chính xác theo từng ngày tại đúng ô lịch của tour đó!
- Bộ lọc trạng thái đơn hàng trực quan qua màu sắc: *Đã thanh toán (Xanh lá)* - *Chờ thanh toán (Vàng)* - *Trong giỏ hàng (Cam)*.

### 3. 🛍️ Quản Lý Đơn Hàng & Giỏ Hàng Nâng Cao
- Hỗ trợ thanh toán tích hợp nhiều tour cùng lúc.
- **Thùng rác thông minh (Soft Delete):** Đơn hàng khi xóa sẽ được đưa vào thùng rác, đếm ngược 30 ngày trước khi xóa vĩnh viễn và cho phép khôi phục lại bất kỳ lúc nào chỉ với 1-click!

---

## 🛠️ Công Nghệ Sử Dụng

- **Frontend:** React 19, Vite, React Router Dom, Tailwind CSS, FullCalendar, Axios, Lucide React. Font chữ **Be Vietnam Pro** (Google Fonts).
- **Backend:** Django 5+, Django REST Framework, Simple JWT (60 phút Access Token), PostgreSQL, Requests (Streaming AI Tokens).
- **AI & API:** Ollama Local LLM (**Qwen 3: 8B**), OpenWeather Map API.
- **Bảo mật & Hiệu năng:** Rate Limiting (DRF Throttling), Anti-Replay IPN Webhook Verification, CORS Configuration, Atomic Transactions.
- **DevOps:** Docker & Docker Compose (cho PostgreSQL).

---

## 🏗️ Cấu Trúc Dự Án

Dự án được xây dựng theo kiến trúc tách biệt hoàn toàn giữa Client và Server (Monorepo):
- **`travel-backend/`:** Backend API (Django + DRF), quản lý Database qua **PostgreSQL** và tích hợp AI.
- **`travel-frontend/`:** Giao diện người dùng (React + Vite + Tailwind CSS).
- **`docker-compose.yml`:** Môi trường Database PostgreSQL.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Dự Án

### 📦 Yêu Cầu Hệ Thống
- **Node.js** (Phiên bản >= 18)
- **Python** (Phiên bản >= 3.10)
- **Docker & Docker Compose** (Để chạy PostgreSQL Database)
- **Ollama** (Chạy mô hình `qwen3:8b` cục bộ)

### Bước 1: Khởi Động Database (PostgreSQL)
Dự án đã tích hợp sẵn file `docker-compose.yml`. Tại thư mục gốc của dự án, mở terminal và chạy:
```bash
docker-compose up -d
```
> Database sẽ chạy ở cổng `5432` với user: `bamia` / password: `123` / DB name: `bamia_db`.

### Bước 2: Cài Đặt & Chạy Backend (Django)

1. Di chuyển vào thư mục backend:
   ```bash
   cd travel-backend
   ```
2. Khởi tạo & kích hoạt Virtual Environment:
   ```bash
   # Trên Windows
   python -m venv venv
   venv\Scripts\activate

   # Trên macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Cài đặt thư viện:
   ```bash
   pip install -r requirements.txt
   ```
4. Cấu hình biến môi trường:
   Sao chép `.env.example` thành `.env` và đảm bảo các thông số DB khớp với Docker:
   ```env
   SECRET_KEY=your_secret_key
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   
   # PostgreSQL Configuration
   DB_NAME=bamia_db
   DB_USER=bamia
   DB_PASSWORD=123
   DB_HOST=127.0.0.1
   DB_PORT=5432
   
   # Ollama AI Configuration (Model Qwen 3: 8B)
   OLLAMA_MODEL=qwen3:8b
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   ```
5. Chạy Migrations & Khởi động Server:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py runserver
   ```
   > Backend sẽ chạy tại: `http://127.0.0.1:8000/`

### Bước 3: Cài Đặt & Chạy Frontend (React + Vite)

1. Mở terminal mới, di chuyển vào thư mục frontend:
   ```bash
   cd travel-frontend
   ```
2. Cài đặt dependencies:
   ```bash
   npm install
   ```
3. Cấu hình biến môi trường:
   Sao chép `.env.example` thành `.env`:
   ```env
   VITE_API_BASE_URL=http://127.0.0.1:8000/api/
   VITE_BACKEND_BASE_URL=http://127.0.0.1:8000
   VITE_OPENWEATHER_API_KEY=your_openweather_api_key
   VITE_PAYMENT_WEBHOOK_SECRET=mock_signature_12345
   ```
4. Khởi chạy ứng dụng:
   ```bash
   npm run dev
   ```
   > Frontend sẽ chạy tại: `http://localhost:5173/`

### Bước 4: Khởi Động Trợ Lý AI (Ollama Qwen 3: 8B)

1. Tải và cài đặt tại [ollama.com](https://ollama.com).
2. Tải mô hình Qwen 3: 8B:
   ```bash
   ollama pull qwen3:8b
   ```
3. Đảm bảo Ollama đang chạy nền (mặc định tại `http://127.0.0.1:11434`). AI Chatbot sẽ tự động kết nối và hoạt động với mô hình **Qwen 3: 8B**.

---

## 📝 Bản Quyền & Ghi Chú
Dự án được thiết kế và tối ưu hóa toàn diện cho kỳ thực tập cơ sở với chuẩn mực chất lượng 10/10. Mọi dữ liệu cá nhân, giỏ hàng và lịch trình du lịch đều được bảo mật tối đa, mang lại trải nghiệm đặt tour thông minh chuẩn kỷ nguyên số! 🌟
