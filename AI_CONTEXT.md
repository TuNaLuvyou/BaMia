# 🤖 TÀI LIỆU NGỮ CẢNH DÀNH CHO AI (AI CONTEXT)

**Mục đích của file này:** Cung cấp bức tranh toàn cảnh, kiến trúc cốt lõi và điểm mạnh của dự án **TravelBaMia** cho các mô hình AI khác (như ChatGPT, Claude, GitHub Copilot, Cursor...) đọc và hiểu. Từ đó, AI có thể hỗ trợ lập trình, gỡ lỗi, hoặc phát triển tính năng mới một cách chuẩn xác nhất mà không phá vỡ cấu trúc có sẵn.

---

## 1. 🎯 Tổng Quan Dự Án (Project Overview)
**TravelBaMia** là một nền tảng Web đặt tour du lịch trực tuyến hiện đại. Đây không phải là một ứng dụng CRUD (Thêm/Sửa/Xóa) cơ bản, mà là một hệ thống được tích hợp sâu Trí tuệ nhân tạo cục bộ (Local LLM) và các tiện ích thông minh nhằm cá nhân hóa trải nghiệm người dùng.

- **Frontend:** React 18, Vite, Tailwind CSS (Giao diện SPA).
- **Backend:** Django, Django REST Framework (Cung cấp API).
- **Cơ sở dữ liệu:** PostgreSQL (Triển khai qua Docker).
- **Lõi AI:** Ollama (Qwen 2.5: 1.5B/7B) chạy hoàn toàn Local.

---

## 2. 🚀 Hệ Thống Có Thể Làm Được Gì? (Core Features)
Hệ thống cung cấp cho người dùng cuối các tính năng:
1. **Tìm kiếm và Đặt Tour:** Xem chi tiết, hình ảnh, lịch trình và đặt tour du lịch.
2. **Tư vấn trực tiếp với AI:** Trò chuyện với một trợ lý ảo thông minh. AI này không chỉ biết chat cơ bản mà còn biết người dùng là ai, giỏ hàng đang có gì, và tư vấn tour khớp với yêu cầu theo thời gian thực.
3. **Lịch trình & Thời tiết thông minh:** Xem các tour đã đặt trên giao diện Lịch (Calendar 35 ngày). Đặc biệt, hệ thống tự động dự báo thời tiết (nắng, mưa, nhiệt độ) tương ứng với địa điểm và ngày đi của từng tour cụ thể.
4. **Quản lý Đơn hàng:** Gom nhiều tour vào giỏ hàng và thanh toán cùng lúc. Theo dõi trạng thái đơn hàng trực quan.
5. **Thùng rác thông minh:** Xóa đơn hàng an toàn (Soft Delete), lưu trữ trong 30 ngày trước khi xóa vĩnh viễn, hỗ trợ khôi phục bằng 1 cú click.

---

## 3. 🏆 Điểm Vượt Trội So Với Các Sản Phẩm Khác (Competitive Advantages)
Nếu phải so sánh với các nền tảng đặt tour thông thường, TravelBaMia có các "vũ khí" cốt lõi sau:

- **Bảo mật tuyệt đối (100% Local AI):** Không sử dụng API của OpenAI hay Google. Toàn bộ dữ liệu chat được xử lý cục bộ trên server qua mô hình Ollama, giúp doanh nghiệp tiết kiệm 100% chi phí API và bảo vệ tuyệt đối quyền riêng tư của khách hàng.
- **Tương tác UI động trong Chat (UI Card Rendering):** AI không chỉ trả lời bằng chữ khô khan. Khi tư vấn tour, AI tự động chèn các thẻ UI động (`[TOUR_CARD:ID]`) vào đoạn chat, giúp khách hàng thấy hình ảnh tour và có thể click "Đặt ngay" trực tiếp trong khung chat.
- **AI Hiểu Ngữ Cảnh Dữ Liệu (Database-Aware & RAG):** AI đọc được trạng thái đăng nhập, lịch sử mua hàng. Nó kết hợp công nghệ RAG để nạp tài liệu điểm đến, giúp câu trả lời cực kỳ chính xác và tránh hiện tượng "ảo giác" (hallucination - bịa ra tour không có thật).
- **Thời Tiết Theo Ngữ Cảnh Lịch Trình:** Không phải một Widget thời tiết chung chung. Hệ thống móc nối API OpenWeather vào từng sự kiện trên Lịch. Khách hàng đi Nha Trang ngày 15, lịch sẽ hiện chính xác thời tiết Nha Trang vào đúng ô ngày 15.
- **Xóa Dữ Liệu Chat Tự Động:** Đảm bảo quyền riêng tư bằng cơ chế tự động xóa lịch sử chat sau 30 phút hoặc khi tắt trình duyệt.

---

## 4. 🧩 Các Phân Hệ & Cấu Trúc Kỹ Thuật (Technical Breakdown)

### 🤖 Phân hệ AI Chatbot (Backend)
- Xử lý Token Streaming giúp AI trả lời mượt mà từng chữ (giống ChatGPT).
- Logic giới hạn: Ép AI chỉ đề xuất tối đa 3 tour nổi bật nhất (dựa trên Rating) để không làm rối mắt người dùng.
- Tự động ánh xạ từ khóa (VD: "Đà Lạt") sang đúng các ID tour liên quan trong Database.

### 📅 Phân hệ Lịch & Giao diện (Frontend)
- Sử dụng thư viện `FullCalendar`.
- Phân loại màu sắc thông minh: *Xanh lá* (Đã thanh toán), *Vàng* (Chờ thanh toán), *Cam* (Đang trong giỏ hàng).
- Sử dụng Font chữ cao cấp `Be Vietnam Pro` để tối ưu hiển thị tiếng Việt.

### 🛒 Phân hệ Database (PostgreSQL & Django)
- Áp dụng cơ chế **Soft Delete** ở tầng Model của Django.
- Quản lý xác thực bằng **JWT (JSON Web Tokens)**.
- Kiến trúc Monorepo chia tách rõ rệt giữa Backend và Frontend.

---

## 5. 🛠️ Chỉ Dẫn Cho Các AI Khác Khi Lập Trình Dự Án Này
Khi một hệ thống AI được yêu cầu đọc dự án này để viết code, sửa lỗi hoặc thêm tính năng, **BẮT BUỘC** phải tuân thủ các quy tắc sau:
1. **Tách biệt Client - Server:** Không viết giao diện trong Django Templates. Backend chỉ đóng vai trò cung cấp RESTful API (sử dụng Django REST Framework). Frontend (React) đảm nhận toàn bộ việc hiển thị.
2. **Xử lý Prompt AI:** Bất kỳ thay đổi nào liên quan đến Prompt của Chatbot phải đảm bảo không làm hỏng logic chèn thẻ `[TOUR_CARD:ID]`.
3. **Database:** Khi tạo Model mới, nếu là dữ liệu người dùng, hãy xem xét tích hợp cơ chế Soft Delete đang có sẵn của dự án.
4. **Style Guide:** Sử dụng class của Tailwind CSS. Không viết CSS thuần (trừ khi bất khả kháng). Tôn trọng font chữ `Be Vietnam Pro`.
5. **State & Auth:** Luôn xử lý token JWT cẩn thận ở Frontend qua Axios Interceptors.
