"""
Nhãn ý định và ngưỡng tin cậy mặc định.

File này cố tình KHÔNG import scikit-learn/pandas để có thể import an toàn từ
`chatbot/models.py` (Django nạp model lúc khởi động) mà không kéo theo thư viện ML.
"""

LABELS = (
    "tour_search",
    "destination_info",
    "account_status",
    "complaint_support",
    "blocked",
    "chitchat",
)

# Nhãn hiển thị trong Django admin
LABEL_CHOICES = tuple((label, label) for label in LABELS)

# Ngưỡng tin cậy theo từng nhãn.
# - `blocked` đặt thấp hơn: chặn nhầm một câu hỏi bình thường chỉ làm khách phải hỏi lại,
#   còn để lọt câu tấn công sẽ đi thẳng vào LLM/RAG (xem docs/ml/04_ethics_tradeoffs.md).
# - `chitchat` đặt cao hơn: nếu nhầm sang chitchat thì mất ngữ cảnh RAG/tour.
DEFAULT_THRESHOLDS = {
    "tour_search": 0.45,
    "destination_info": 0.45,
    "account_status": 0.45,
    "complaint_support": 0.40,
    "blocked": 0.35,
    "chitchat": 0.50,
}

# Nhãn dùng khi luồng cũ (luật cứng) không phân loại được — chỉ dùng cho đánh giá baseline.
UNKNOWN_LABEL = "unknown"
