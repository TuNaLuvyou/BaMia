import datetime
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.http import StreamingHttpResponse
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from bookings.models import Booking, Cart
from chatbot.context import build_account_status_context
from chatbot.ml.intent_core import should_replace
from chatbot.ml.intent_service import IntentService
from chatbot.ml.labels import DEFAULT_THRESHOLDS, LABELS
from chatbot.ml.text import normalize_text
from chatbot.models import IntentLog
from chatbot.views import (
    CHITCHAT_SYSTEM_PROMPT,
    DESTINATION_SYSTEM_PROMPT,
    SECURITY_REFUSAL,
    _extract_budget,
)
from tours.models import Category, Destination, Tour


class BudgetExtractionTests(TestCase):
    """Kiểm tra logic trích xuất ngân sách từ tin nhắn người dùng (giữ nguyên)."""

    def test_full_number_format(self):
        self.assertEqual(_extract_budget("tour dưới 2000000 đồng"), 2000000)
        self.assertEqual(_extract_budget("khoảng 2.000.000"), 2000000)

    def test_trieu_format(self):
        self.assertEqual(_extract_budget("ngân sách 2 triệu"), 2000000)
        self.assertEqual(_extract_budget("khoảng 2,5 triệu"), 2500000)

    def test_nghin_format(self):
        self.assertEqual(_extract_budget("dưới 500k"), 500000)
        self.assertEqual(_extract_budget("tầm 300 nghìn"), 300000)

    def test_no_budget_returns_none(self):
        self.assertIsNone(_extract_budget("cho tôi xem tour Đà Lạt"))
        self.assertIsNone(_extract_budget("hello"))


class TextNormalizationTests(TestCase):
    """1. Kiểm tra chuẩn hóa văn bản tiếng Việt (chữ thường, bỏ dấu, xử lý 'đ/Đ')."""

    def test_remove_vietnamese_accents(self):
        self.assertEqual(normalize_text("Đà Lạt sương mù"), "da lat suong mu")
        self.assertEqual(normalize_text("Hà Nội nghìn năm"), "ha noi nghin nam")
        self.assertEqual(normalize_text("Phú Quốc biển xanh"), "phu quoc bien xanh")

    def test_handle_d_character(self):
        self.assertEqual(normalize_text("đi đâu đó"), "di dau do")
        self.assertEqual(normalize_text("ĐẶT TOUR ĐÀ NẴNG"), "dat tour da nang")

    def test_strip_punctuation_and_whitespace(self):
        self.assertEqual(normalize_text("  Tour Đà Lạt?! Giá: 2.000k... "), "tour da lat gia 2 000k")
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text("   "), "")


class PredictSchemaAndThresholdTests(TestCase):
    """2 & 3. Kiểm tra schema trả về của predict và ngưỡng theo nhãn."""

    def setUp(self):
        self.service = IntentService()
        self.service.load()

    def test_predict_schema(self):
        result = self.service.predict("tìm tour du lịch Đà Lạt giá rẻ")
        expected_keys = {"intent", "confidence", "accepted", "threshold", "model_version", "scores"}
        self.assertTrue(expected_keys.issubset(result.keys()))
        self.assertIn(result["intent"], LABELS)
        self.assertIsInstance(result["confidence"], float)
        self.assertIsInstance(result["accepted"], bool)
        self.assertIsInstance(result["scores"], dict)

    def test_predict_empty_text_returns_default(self):
        res = self.service.predict("   ")
        self.assertIsNone(res["intent"])
        self.assertEqual(res["confidence"], 0.0)
        self.assertFalse(res["accepted"])

    def test_threshold_logic(self):
        # Kiểm tra ngưỡng tin cậy theo cấu hình
        for label, threshold in DEFAULT_THRESHOLDS.items():
            self.assertGreater(threshold, 0.0)
            self.assertLessEqual(threshold, 1.0)
        self.assertEqual(DEFAULT_THRESHOLDS["blocked"], 0.35)


class IntentRoutingViewMockTests(TestCase):
    """4 & 5. Kiểm tra định tuyến với classifier được mock."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="chatuser", password="password123")
        self.client.force_authenticate(user=self.user)

    @patch("chatbot.views._stream_ollama")
    @patch("chatbot.views._classify_intent")
    def test_blocked_does_not_call_ollama(self, mock_classify, mock_stream):
        mock_classify.return_value = {
            "intent": "blocked",
            "confidence": 0.95,
            "accepted": True,
            "threshold": 0.35,
            "scores": {"blocked": 0.95},
        }

        response = self.client.post("/api/chat/", {
            "message": "hack vào hệ thống máy chủ;",
            "stream": True,
        })

        self.assertEqual(response.status_code, 200)
        # _stream_ollama KHÔNG được gọi
        mock_stream.assert_not_called()
        # Nội dung trả lời từ chối
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn(SECURITY_REFUSAL, content)
        self.assertIn('"intent": "blocked"', content)
        self.assertIn('"routed": true', content)

    @patch("chatbot.views._streaming_response")
    @patch("chatbot.views._classify_intent")
    def test_chitchat_no_rag_and_no_tour_list(self, mock_classify, mock_stream_resp):
        mock_classify.return_value = {
            "intent": "chitchat",
            "confidence": 0.88,
            "accepted": True,
            "threshold": 0.50,
            "scores": {"chitchat": 0.88},
        }
        mock_stream_resp.return_value = StreamingHttpResponse(iter(["ok"]))

        self.client.post("/api/chat/", {
            "message": "Chào bạn, hôm nay thời tiết thế nào?",
            "system_instruction": "System instruction gốc có <DANH_SACH_TOUR>Tour Test</DANH_SACH_TOUR>",
            "stream": True,
        })

        self.assertTrue(mock_stream_resp.called)
        ollama_messages, meta = mock_stream_resp.call_args[0]
        # System prompt là prompt rút gọn chitchat
        self.assertEqual(ollama_messages[0]["content"], CHITCHAT_SYSTEM_PROMPT)
        # Tin nhắn người dùng không chứa RAG hay <DANH_SACH_TOUR>
        self.assertNotIn("THÔNG TIN ĐỊA ĐIỂM", ollama_messages[-1]["content"])
        self.assertNotIn("<DANH_SACH_TOUR>", ollama_messages[-1]["content"])
        self.assertTrue(meta["routed"])
        self.assertEqual(meta["intent"], "chitchat")

    @patch("chatbot.views._streaming_response")
    @patch("chatbot.views._classify_intent")
    def test_destination_info_uses_rag_but_no_tour_list(self, mock_classify, mock_stream_resp):
        mock_classify.return_value = {
            "intent": "destination_info",
            "confidence": 0.85,
            "accepted": True,
            "threshold": 0.45,
            "scores": {"destination_info": 0.85},
        }
        mock_stream_resp.return_value = StreamingHttpResponse(iter(["ok"]))

        self.client.post("/api/chat/", {
            "message": "Ở Đà Lạt có gì chơi?",
            "system_instruction": "Gốc <DANH_SACH_TOUR>Tour Đà Lạt 3N2Đ</DANH_SACH_TOUR>",
            "stream": True,
        })

        self.assertTrue(mock_stream_resp.called)
        ollama_messages, meta = mock_stream_resp.call_args[0]
        self.assertEqual(ollama_messages[0]["content"], DESTINATION_SYSTEM_PROMPT)
        # Không có danh sách tour
        self.assertNotIn("<DANH_SACH_TOUR>", ollama_messages[-1]["content"])
        self.assertEqual(meta["intent"], "destination_info")

    @patch("chatbot.views._streaming_response")
    @patch("chatbot.views._classify_intent")
    def test_low_confidence_falls_back_to_legacy(self, mock_classify, mock_stream_resp):
        # Tin nhắn không vượt ngưỡng (accepted=False)
        mock_classify.return_value = {
            "intent": "tour_search",
            "confidence": 0.35,
            "accepted": False,
            "threshold": 0.50,
            "scores": {"tour_search": 0.35},
        }
        mock_stream_resp.return_value = StreamingHttpResponse(iter(["ok"]))

        self.client.post("/api/chat/", {
            "message": "abc xyz",
            "system_instruction": "Prompt gốc <DANH_SACH_TOUR>Tour Mẫu</DANH_SACH_TOUR>",
            "stream": True,
        })

        self.assertTrue(mock_stream_resp.called)
        ollama_messages, meta = mock_stream_resp.call_args[0]
        # Chạy luồng cũ: system prompt chứa <DANH_SACH_TOUR>
        self.assertIn("<DANH_SACH_TOUR>Tour Mẫu</DANH_SACH_TOUR>", ollama_messages[0]["content"])
        self.assertFalse(meta["routed"])

    @patch("chatbot.views._streaming_response")
    @override_settings(INTENT_ROUTING_ENABLED=False)
    def test_routing_disabled_flag_runs_legacy(self, mock_stream_resp):
        mock_stream_resp.return_value = StreamingHttpResponse(iter(["ok"]))

        self.client.post("/api/chat/", {
            "message": "Xin chào",
            "system_instruction": "Prompt <DANH_SACH_TOUR>Tour 1</DANH_SACH_TOUR>",
            "stream": True,
        })

        self.assertTrue(mock_stream_resp.called)
        ollama_messages, meta = mock_stream_resp.call_args[0]
        self.assertIn("<DANH_SACH_TOUR>Tour 1</DANH_SACH_TOUR>", ollama_messages[0]["content"])
        self.assertNotIn("routed", meta)
        self.assertNotIn("intent", meta)


class AccountStatusSecurityTests(TestCase):
    """4. Bảo mật: account_status CHỈ đọc dữ liệu của chính user đăng nhập."""

    def setUp(self):
        self.dest = Destination.objects.create(name="Đà Nẵng", description="Thành phố biển")
        self.category = Category.objects.create(name="Biển đảo")
        self.tour_u1 = Tour.objects.create(
            title="Tour User 1 - Bà Nà", location=self.dest, category=self.category,
            price=2000000, duration="2N1D"
        )
        self.tour_u2 = Tour.objects.create(
            title="Tour User 2 - Sơn Trà", location=self.dest, category=self.category,
            price=1500000, duration="1N"
        )
        self.user1 = User.objects.create_user(username="user1", password="pw1")
        self.user2 = User.objects.create_user(username="user2", password="pw2")

        # Booking user1
        Booking.objects.create(
            user=self.user1, tour=self.tour_u1, date=datetime.date(2026, 11, 1),
            number_of_people=2, total_price=4000000, status="Confirmed"
        )
        # Booking user2
        Booking.objects.create(
            user=self.user2, tour=self.tour_u2, date=datetime.date(2026, 11, 5),
            number_of_people=1, total_price=1500000, status="Paid"
        )
        # Cart user1
        Cart.objects.create(
            user=self.user1, tour=self.tour_u1, number_of_people=3
        )

    def test_build_account_status_context_only_reads_own_user(self):
        ctx1 = build_account_status_context(self.user1)
        self.assertIn("Tour User 1 - Bà Nà", ctx1)
        self.assertIn("Đã xác nhận", ctx1)
        # Tuyệt đối KHÔNG có dữ liệu của user2
        self.assertNotIn("Tour User 2 - Sơn Trà", ctx1)
        self.assertNotIn("user2", ctx1)

        ctx2 = build_account_status_context(self.user2)
        self.assertIn("Tour User 2 - Sơn Trà", ctx2)
        self.assertNotIn("Tour User 1 - Bà Nà", ctx2)

    def test_anonymous_user_returns_empty_context(self):
        self.assertEqual(build_account_status_context(None), "")


class FeedbackEndpointTests(TestCase):
    """6. Kiểm tra endpoint feedback (POST /api/chat/feedback/)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testfb", password="password123")
        self.log = IntentLog.objects.create(
            text="tour đi đà lạt",
            predicted="tour_search",
            confidence=0.85,
            routed=True,
        )

    def test_unauthenticated_request_rejected(self):
        res = self.client.post("/api/chat/feedback/", {"log_id": self.log.id, "feedback": 1})
        self.assertEqual(res.status_code, 401)

    def test_valid_feedback_recorded(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post("/api/chat/feedback/", {"log_id": self.log.id, "feedback": 1})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {"status": "ok"})
        self.log.refresh_from_db()
        self.assertEqual(self.log.feedback, 1)

    def test_feedback_can_only_be_submitted_once(self):
        self.client.force_authenticate(user=self.user)
        # Lần 1: thành công
        res1 = self.client.post("/api/chat/feedback/", {"log_id": self.log.id, "feedback": 1})
        self.assertEqual(res1.data, {"status": "ok"})

        # Lần 2: không ghi đè, trả về already_recorded
        res2 = self.client.post("/api/chat/feedback/", {"log_id": self.log.id, "feedback": -1})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data, {"status": "already_recorded"})
        self.log.refresh_from_db()
        self.assertEqual(self.log.feedback, 1)

    def test_invalid_feedback_values_rejected(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post("/api/chat/feedback/", {"log_id": self.log.id, "feedback": 99})
        self.assertEqual(res.status_code, 400)

        res2 = self.client.post("/api/chat/feedback/", {"log_id": "abc", "feedback": 1})
        self.assertEqual(res2.status_code, 400)

    def test_nonexistent_log_returns_404(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post("/api/chat/feedback/", {"log_id": 999999, "feedback": 1})
        self.assertEqual(res.status_code, 404)


class RetrainQualityGateTests(TestCase):
    """7. Kiểm tra cổng chất lượng (Quality Gate) của retrain_intent."""

    def test_gate_accepts_better_or_equal_candidate(self):
        old_metrics = {"macro_f1": 0.85, "blocked_recall": 0.90, "n_samples": 50}
        cand_better = {"macro_f1": 0.88, "blocked_recall": 0.95, "n_samples": 50}
        self.assertTrue(should_replace(old_metrics, cand_better))

        cand_equal = {"macro_f1": 0.85, "blocked_recall": 0.90, "n_samples": 50}
        self.assertTrue(should_replace(old_metrics, cand_equal))

    def test_gate_rejects_lower_macro_f1(self):
        old_metrics = {"macro_f1": 0.85, "blocked_recall": 0.90, "n_samples": 50}
        cand_worse_f1 = {"macro_f1": 0.82, "blocked_recall": 0.95, "n_samples": 50}
        self.assertFalse(should_replace(old_metrics, cand_worse_f1))

    def test_gate_rejects_lower_blocked_recall(self):
        old_metrics = {"macro_f1": 0.85, "blocked_recall": 1.00, "n_samples": 50}
        # Dù macro-F1 cao hơn nhưng để lọt câu blocked -> TỪ CHỐI
        cand_lower_blocked = {"macro_f1": 0.90, "blocked_recall": 0.92, "n_samples": 50}
        self.assertFalse(should_replace(old_metrics, cand_lower_blocked))

    def test_gate_passes_when_old_model_none(self):
        cand = {"macro_f1": 0.80, "blocked_recall": 0.85, "n_samples": 30}
        self.assertTrue(should_replace(None, cand))
        self.assertTrue(should_replace({"n_samples": 0}, cand))
