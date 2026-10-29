# Hướng dẫn Vận hành & Thực thi Mô-đun Học máy (TravelBaMia ML)

Tài liệu này cung cấp các câu lệnh chuẩn xác từng bước để kiểm tra, huấn luyện, đánh giá đường cơ sở, đo lường hiệu năng và huấn luyện lại bộ phân loại ý định chatbot.

---

## 1. Yêu cầu môi trường & Cài đặt thư viện

### 1.1. Cài đặt Python Dependencies
Các thư viện bổ sung đã được ghim phiên bản trong `travel-backend/requirements.txt`:
- `scikit-learn==1.9.1`
- `pandas==3.1.0`

Cài đặt bằng pip (từ thư mục `travel-backend/`):
```bash
cd travel-backend
pip install -r requirements.txt
```

### 1.2. Biến môi trường hỗ trợ (trong `core/settings.py`)
| Tên biến | Mặc định | Ý nghĩa |
|---|---|---|
| `INTENT_ROUTING_ENABLED` | `True` | Bật/tắt router ý định trước LLM (nếu `False`, chatbot chạy luồng cũ 100%) |
| `INTENT_MODEL_PATH` | `chatbot/ml/artifacts/intent_model.pkl` | Đường dẫn file mô hình đã huấn luyện |
| `INTENT_DATA_PATH` | `chatbot/ml/data/intents.csv` | File dữ liệu huấn luyện gốc |
| `INTENT_GOLDEN_PATH` | `chatbot/ml/data/golden.csv` | File tập kiểm thử độc lập (do người viết) |
| `INTENT_LOG_RETENTION_DAYS`| `90` | Số ngày lưu trữ log ý định trước khi dọn dẹp |

---

## 2. Quy trình thực thi từng bước (Step-by-Step Workflow)

Tất cả các lệnh dưới đây thực hiện từ thư mục `travel-backend/`.

### Bước 1: Kiểm tra và chuẩn hóa dữ liệu (`validate_dataset`)
Kiểm tra số lượng mẫu từng nhãn, phát hiện trùng lặp sau chuẩn hóa, kiểm tra rò rỉ dữ liệu giữa tập huấn luyện và tập golden:
```bash
python -m chatbot.ml.validate_dataset --data chatbot/ml/data/intents.csv --golden chatbot/ml/data/golden.csv
```
*Lưu ý: Hệ thống sẽ in cảnh báo nếu có nhãn dưới 100 mẫu (đảm bảo tính trung thực trong đồ án).*

---

### Bước 2: Huấn luyện mô hình lần đầu (`train_intent`)
Chạy so sánh 4 thuật toán (Multinomial Naive Bayes, kNN, SVM linear, Decision Tree) qua Stratified 5-Fold, tự động chọn thuật toán có Macro-F1 cao nhất, fit mô hình cuối và lưu `.pkl`:
```bash
# Cách 1: Qua Django Management Command
python manage.py train_intent --data chatbot/ml/data/intents.csv --golden chatbot/ml/data/golden.csv

# Cách 2: Chạy trực tiếp module Python
python -m chatbot.ml.train_intent --data chatbot/ml/data/intents.csv --golden chatbot/ml/data/golden.csv
```
*Đầu ra:*
- Mô hình: `chatbot/ml/artifacts/intent_model.pkl`
- Báo cáo chi tiết: `chatbot/ml/artifacts/intent_report.json`

---

### Bước 3: Đánh giá đường cơ sở (Baseline Luật cũ VS Mô hình ML)
Chạy bộ phân loại luật cũ (kết hợp `security_keywords` + regex `needsRefresh` + từ khóa hỗ trợ/`[ESCALATE]`) đối đầu với mô hình học máy trên cùng tập dữ liệu:
```bash
python -m chatbot.ml.evaluate_baseline --golden chatbot/ml/data/intents.csv --model chatbot/ml/artifacts/intent_model.pkl
```
*(Khi nhóm đã viết xong `golden.csv` đầy đủ, thay thế bằng `--golden chatbot/ml/data/golden.csv`).*

*Đầu ra:* Báo cáo so sánh `chatbot/ml/artifacts/baseline_report.json` và bảng console đối chiếu độ chính xác từng lớp.

---

### Bước 4: Đo lường độ trễ & hiệu quả định tuyến (Benchmark)
Đo thời gian phản hồi của mô hình (trung bình, median, p95) và tỉ lệ câu hỏi hoàn toàn không cần gọi LLM:
```bash
python -m chatbot.ml.benchmark_latency --iterations 50
```
*Đầu ra:* `chatbot/ml/artifacts/latency_report.json`.

---

### Bước 5: Quản trị log & Vòng phản hồi (Admin & Feedback)

1. **Dọn dẹp log quá hạn (TTL 90 ngày)**:
   ```bash
   python manage.py purge_intent_logs --days 90
   ```
2. **Xuất các mẫu đã được admin duyệt nhãn ra CSV**:
   ```bash
   python manage.py export_intent_feedback --output chatbot/ml/artifacts/intent_feedback_export.csv
   ```

---

### Bước 6: Huấn luyện lại có kiểm soát (Retrain with Quality Gate)

Quy trình tự động gộp dữ liệu gốc + phản hồi đã duyệt, huấn luyện ứng viên mới và đánh giá đối đầu trên `golden.csv`. Chỉ thay thế mô hình khi Macro-F1 >= mô hình cũ VÀ recall của `blocked` không giảm.

1. **Chạy thử nghiệm (Dry-Run - không ghi đè mô hình)**:
   ```bash
   python manage.py retrain_intent --dry-run
   ```
2. **Chạy thực tế (Tự động sao lưu mô hình cũ và cập nhật mô hình mới nếu đạt)**:
   ```bash
   python manage.py retrain_intent
   ```
*Đầu ra:*
- Bản sao lưu mô hình cũ (nếu đạt): `chatbot/ml/artifacts/backup/intent_model_<timestamp>.pkl`
- Báo cáo so sánh: `chatbot/ml/artifacts/retrain_report_<timestamp>.json` và `.md`.

---

## 3. Chạy kiểm thử tự động (Unit Tests)

Bộ kiểm thử bao gồm 26 test cases kiểm tra chuẩn hóa tiếng Việt, schema `predict`, ngưỡng nhãn, định tuyến mock, bảo mật `account_status`, endpoint feedback và cổng chất lượng.

```bash
# Chạy với PostgreSQL (nếu DB đang chạy)
python manage.py test chatbot

# Chạy với SQLite in-memory (khi không bật PostgreSQL)
# Trên Windows PowerShell:
$env:PYTHONPATH="$env:TEMP\bamia_test_settings"; $env:DJANGO_SETTINGS_MODULE="test_settings_sqlite"; python manage.py test chatbot
```

Frontend Lint & Build:
```bash
cd travel-frontend
npm run build
npx eslint src/components/chatbox/
```

---

## 4. Chạy trong môi trường Docker

`docker-compose.yml` ở gốc repo quản lý service PostgreSQL:
```yaml
version: '3.8'
services:
  db:
    image: postgres:15-alpine
    container_name: bamia_postgres
    restart: always
    environment:
      POSTGRES_DB: bamia_db
      POSTGRES_USER: bamia
      POSTGRES_PASSWORD: 123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

Khởi động database:
```bash
docker compose up -d db
```

Sau khi database chạy, tiến hành chạy migration và các management commands như bình thường:
```bash
cd travel-backend
python manage.py migrate
python manage.py train_intent
```
*(Nếu đóng gói backend thành container Docker, cần thêm `scikit-learn` và `pandas` vào image và rebuild image: `docker compose build backend`).*
