from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import StreamingHttpResponse

import re
import requests
import json
import time
import os

from tours.models import Tour, Destination
from chatbot.context import build_account_status_context
from chatbot.ml.intent_service import get_intent_service, routing_enabled

OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b')
OLLAMA_TIMEOUT_CONNECT = 5    # Giây chờ kết nối đến Ollama
OLLAMA_TIMEOUT_READ = 120     # Giây chờ đọc response (model có thể chậm)
OLLAMA_MAX_RETRIES = 2        # Số lần thử lại tối đa

# Lớp phòng thủ cũ — GIỮ NGUYÊN (chạy trước cả bộ phân loại ý định)
SECURITY_KEYWORDS = [
    'database', 'password', 'mật khẩu', 'cấu trúc sql',
    'select *', 'delete from', 'drop table', 'backend code',
]
SECURITY_REFUSAL = 'Xin lỗi, tôi không thể hỗ trợ các thông tin liên quan đến kỹ thuật hoặc bảo mật hệ thống. 🙏'

# ── Prompt rút gọn theo nhãn ý định ────────────────────────────────────────────
CHITCHAT_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI du lịch TravelBaMia. Trả lời bằng tiếng Việt, thân thiện, ngắn gọn "
    "(tối đa 3 câu). Không liệt kê tour, không bịa thông tin. "
    "Nếu khách muốn tìm tour, mời khách nói điểm đến và ngân sách."
)

DESTINATION_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI du lịch TravelBaMia. Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào vấn đề.\n"
    "QUY TẮC:\n"
    "1. Chỉ dùng dữ liệu trong khối THÔNG TIN ĐỊA ĐIỂM được cung cấp.\n"
    "2. Không bịa thông tin ngoài dữ liệu; nếu thiếu dữ liệu, nói rõ là chưa có thông tin.\n"
    "3. Không liệt kê tour, không dùng thẻ [TOUR_CARD].\n"
    "4. Không trả lời về kỹ thuật/mã nguồn/database."
)

ACCOUNT_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI du lịch TravelBaMia. Trả lời bằng tiếng Việt, ngắn gọn.\n"
    "Dưới đây là TRẠNG THÁI TÀI KHOẢN của chính khách đang đăng nhập (dữ liệu thật từ hệ thống).\n"
    "QUY TẮC:\n"
    "1. Chỉ dùng dữ liệu trong khối TRẠNG THÁI TÀI KHOẢN, không bịa đơn hàng/giỏ hàng.\n"
    "2. Không tiết lộ thông tin của người dùng khác.\n"
    "3. Nêu rõ mã đơn, tên tour, ngày khởi hành, số người, tổng tiền, trạng thái khi có.\n"
    "4. Nếu không có đơn/giỏ hàng, nói rõ và gợi ý tìm tour phù hợp.\n"
    "5. Không dùng thẻ [TOUR_CARD] vì không có danh sách tour trong ngữ cảnh này.\n"
    "6. Không trả lời về kỹ thuật/mã nguồn/database."
)

COMPLAINT_SYSTEM_PROMPT = (
    "Bạn là trợ lý AI du lịch TravelBaMia. Khách đang gặp vấn đề cần hỗ trợ.\n"
    "QUY TẮC:\n"
    "1. Đồng cảm và xin lỗi chân thành, ngắn gọn (2-3 câu).\n"
    "2. Tóm tắt lại vấn đề khách vừa nêu.\n"
    "3. Mời khách gặp nhân viên hỗ trợ để xử lý; không hứa hoàn tiền, không cam kết cụ thể.\n"
    "4. Không bịa chính sách của công ty.\n"
    "5. Kết thúc câu trả lời bằng thẻ [ESCALATE].\n"
    "6. Không trả lời về kỹ thuật/mã nguồn/database."
)


class OllamaHealthView(APIView):
    """Kiểm tra Ollama có đang chạy không — không cần xác thực."""
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # Kiểm tra endpoint gốc của Ollama
            resp = requests.get(
                f"{OLLAMA_BASE_URL}/",
                timeout=(OLLAMA_TIMEOUT_CONNECT, 5)
            )
            if resp.status_code == 200:
                return Response({'status': 'ok', 'message': f'Ollama đang hoạt động ({OLLAMA_MODEL}).'})
            return Response({'status': 'error', 'message': 'Ollama phản hồi không hợp lệ.'}, status=503)
        except requests.exceptions.ConnectionError:
            return Response({'status': 'offline', 'message': 'Ollama chưa được khởi động.'}, status=503)
        except requests.exceptions.Timeout:
            return Response({'status': 'timeout', 'message': 'Ollama không phản hồi kịp thời.'}, status=503)


def _stream_ollama(ollama_messages):
    """Generator: gọi Ollama ở chế độ stream=True, yield từng chunk JSON."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": True,
        "options": {
            "temperature": 0.1,     # Thấp (0.1) → bám sát luật, không sáng tạo lung tung
            "num_predict": 1024,    # Model Qwen3:8b có thể trả lời chi tiết, mở rộng token limit
            "num_ctx": 8192,        # Context window 8k cho Qwen3:8b
            "top_k": 20,
            "top_p": 0.8,
            "repeat_last_n": 64,
        }
    }
    # Model nghĩ ra được chữ nào thì hiện ra chữ đó
    with requests.post(
        OLLAMA_URL,
        json=payload,
        stream=True,
        timeout=(OLLAMA_TIMEOUT_CONNECT, OLLAMA_TIMEOUT_READ)
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    done = chunk.get("done", False)
                    yield json.dumps({"token": token, "done": done}, ensure_ascii=False) + "\n" #yield từng chữ
                    if done:
                        break
                except json.JSONDecodeError:
                    continue


def _extract_budget(text: str):
    """
    Trích xuất ngân sách tối đa từ tin nhắn người dùng.
    Trả về số nguyên (VNĐ) hoặc None nếu không tìm thấy.
    Ví dụ: '2 triệu' → 2000000, 'dưới 500k' → 500000, '2.000.000' → 2000000
    """
    t = text.lower()

    # Dạng: 2.000.000 hoặc 2,000,000 hoặc 2000000
    m = re.search(r'(\d[\d.,]+)\s*(?:đồng|vnd|vnđ)?', t)
    if m:
        raw = m.group(1).replace('.', '').replace(',', '')
        try:
            val = int(raw)
            if val >= 10000:  # Bỏ qua số quá nhỏ (không phải tiền)
                return val
        except ValueError:
            pass

    # Dạng: X triệu / X tr
    m = re.search(r'([\d.,]+)\s*tri[eệ]u', t)
    if m:
        try:
            return int(float(m.group(1).replace(',', '.')) * 1_000_000)
        except ValueError:
            pass

    # Dạng: Xk / X nghìn / X ngàn
    m = re.search(r'([\d.,]+)\s*(?:k\b|nghìn|ngàn)', t)
    if m:
        try:
            return int(float(m.group(1).replace(',', '.')) * 1_000)
        except ValueError:
            pass

    return None


def _classify_intent(user_message: str):
    """
    Phân loại ý định nếu cờ bật VÀ mô hình sẵn sàng.
    Trả về None khi tắt/thiếu mô hình/lỗi → luồng cũ chạy y hệt trước đây.
    """
    if not routing_enabled():
        return None
    service = get_intent_service()
    if not service.is_ready:
        return None
    try:
        return service.predict(user_message)
    except Exception as exc:  # noqa: BLE001 - classifier không được làm sập chat
        print(f"[Intent] Lỗi phân loại, quay về luồng cũ: {exc}")
        return None


def _build_destination_context(user_message: str, loaded_destinations: list[str]):
    """RAG: chọn địa điểm (trực tiếp hoặc từ cache) và đọc file .txt (tối đa 3000 ký tự)."""
    destinations = Destination.objects.exclude(info_file__isnull=True).exclude(info_file='')
    rag_context = ""
    msg_lower = user_message.lower()

    # Bước 1: Quét xem người dùng có nhắc trực tiếp địa danh nào trong tin nhắn hiện tại không
    direct_matches = []
    for dest in destinations:
        match_found = False
        # Kiểm tra tên địa danh
        if dest.name.lower() in msg_lower:
            match_found = True
        # Kiểm tra từ khóa
        elif dest.keywords:
            kw_list = [k.strip().lower() for k in dest.keywords.split(',') if k.strip()]
            for kw in kw_list:
                if kw and kw in msg_lower:
                    match_found = True
                    break
        if match_found:
            direct_matches.append(dest)

    # Bước 2: Quyết định danh sách địa điểm sẽ nạp dữ liệu
    matched_destinations_to_load = []
    if len(direct_matches) > 0:
        # Người dùng chủ động nhắc địa danh mới -> ghi đè, xóa sạch cache cũ để tránh tràn context
        matched_destinations_to_load = direct_matches
    else:
        # Hỏi nối tiếp không nhắc tên -> Kích hoạt cache cũ từ loaded_destinations
        for dest in destinations:
            if dest.name.lower() in loaded_destinations:
                matched_destinations_to_load.append(dest)

    matched_dest_names = [dest.name for dest in matched_destinations_to_load]

    # Bước 3: Đọc file dữ liệu của các địa điểm được chọn
    for dest in matched_destinations_to_load:
        # Đọc dữ liệu file thực tế (BẮT BUỘC phải đọc để gửi kèm Prompt vì LLM stateless)
        try:
            file_path = dest.info_file.path
            if os.path.exists(file_path):
                print(f"[RAG] Đọc dữ liệu ngữ cảnh cho: {dest.name} -> {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Trim nội dung tối đa 3000 ký tự để tránh context quá lớn
                if len(content) > 3000:
                    content = content[:3000] + "\n...(còn tiếp)"
                rag_context += f"\n\n=== DỮ LIỆU ĐỊA ĐIỂM: {dest.name} ===\n{content}\n"
            else:
                print(f"[RAG] File không tồn tại: {file_path}")
        except Exception as e:
            print(f"[RAG] Lỗi đọc file {dest.name}: {e}")

    return rag_context, matched_dest_names


def _build_legacy_system_instruction(max_budget):
    """System prompt cũ + <DANH_SACH_TOUR> lọc theo ngân sách (giữ nguyên hành vi)."""
    print("[Chatbot] Khởi động bộ dựng System Prompt dự phòng tại Backend...")
    tours = Tour.objects.all()

    # Lọc theo ngân sách nếu có
    if max_budget:
        tours = tours.filter(price__lte=max_budget)

    tours_text = "\n<DANH_SACH_TOUR>\n"
    if not tours.exists():
        budget_note = f" trong ngân sách {max_budget:,} VNĐ" if max_budget else ""
        tours_text += f"Hiện chưa có tour nào{budget_note}.\n"
    else:
        for t in tours:
            loc = t.location.name if t.location else "N/A"
            tours_text += f'<TOUR id="{t.id}" ten="{t.title}" dia_diem="{loc}" gia="{int(t.price):,}" />\n'
    tours_text += "</DANH_SACH_TOUR>\n"

    budget_rule = (
        f"QUAN TRỌNG: Khách yêu cầu ngân sách tối đa {max_budget:,} VNĐ. "
        "CHỈ được gợi ý các tour có trong <DANH_SACH_TOUR> bên dưới (đã được lọc theo ngân sách).\n"
    ) if max_budget else ""

    return (
        "Bạn là trợ lý AI du lịch TravelBaMia. Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào vấn đề.\n\n"
        f"{budget_rule}"
        "QUY TẮC:\n"
        "1. Chỉ chào lại 1 câu khi khách chào hỏi. Không liệt kê tour.\n"
        "2. Khi khách hỏi danh sách tour: liệt kê tên tour bằng gạch đầu dòng. Không in 'id'. Không dùng [TOUR_CARD].\n"
        "3. Khi khách yêu cầu xem chi tiết 1 tour cụ thể: viết tên tour rồi gắn thẻ [TOUR_CARD:id] ngay sau.\n"
        "   Ví dụ: 'Đây là tour bạn chọn: Khám Phá Bản Cát Cát [TOUR_CARD:8]'\n"
        "   - Lấy id CHÍNH XÁC từ thuộc tính id= trong thẻ <TOUR> bên dưới.\n"
        "4. Không bịa tour, không dùng thông tin ngoài <DANH_SACH_TOUR>.\n"
        "5. Không dùng [TASK_COMPLETE], [DONE], [SUCCESS].\n"
        "6. Không trả lời về kỹ thuật/mã nguồn/database.\n\n"
        f"{tours_text}"
    )


def _build_messages(system_instruction, history, final_user_message, history_limit=10):
    """Ghép system prompt + history (giới hạn) + câu hỏi cuối."""
    ollama_messages = [{"role": "system", "content": system_instruction}]
    for msg in history[-history_limit:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            ollama_messages.append({"role": role, "content": content})
    ollama_messages.append({"role": "user", "content": final_user_message})
    return ollama_messages


def _build_routed_prompt(intent: str, user_message: str, rag_context: str, user):
    """
    Prompt rút gọn theo nhãn. Trả về (system_instruction, final_user_message, history_limit).
    `tour_search` không đi vào đây (dùng nguyên luồng cũ).
    """
    if intent == "chitchat":
        return CHITCHAT_SYSTEM_PROMPT, user_message, 4

    if intent == "destination_info":
        if rag_context:
            final_user_message = (
                f"1. THÔNG TIN ĐỊA ĐIỂM:\n{rag_context}\n\n"
                f"CÂU HỎI CỦA KHÁCH: {user_message}"
            )
        else:
            final_user_message = (
                "Hệ thống chưa có dữ liệu cho địa điểm khách hỏi. "
                "Hãy nói rõ là chưa có thông tin và mời khách nêu tên địa danh cụ thể.\n"
                f"CÂU HỎI CỦA KHÁCH: {user_message}"
            )
        return DESTINATION_SYSTEM_PROMPT, final_user_message, 10

    if intent == "account_status":
        account_context = build_account_status_context(user)
        final_user_message = (
            f"{account_context}\n\n"
            f"CÂU HỎI CỦA KHÁCH: {user_message}"
        )
        return ACCOUNT_SYSTEM_PROMPT, final_user_message, 6

    if intent == "complaint_support":
        return COMPLAINT_SYSTEM_PROMPT, user_message, 6

    # Không rơi vào đây trong luồng hiện tại
    return CHITCHAT_SYSTEM_PROMPT, user_message, 4


def _build_meta(matched_dest_names, intent_result=None, *, routed=False,
                escalate=False, log_id=None):
    """
    Meta chunk tương thích ngược: luôn có `meta` + `matched_destinations`.
    Chỉ thêm field mới khi bộ phân loại thực sự chạy (intent_result khác None).
    """
    meta = {"meta": True, "matched_destinations": matched_dest_names}
    if intent_result is not None:
        meta.update({
            "intent": intent_result.get("intent"),
            "intent_confidence": intent_result.get("confidence"),
            "routed": bool(routed),
            "escalate": bool(escalate),
            "log_id": log_id,
        })
    return meta


def _streaming_response(ollama_messages, meta):
    """Bọc generator stream + retry + meta chunk (giữ nguyên hợp đồng SSE cũ)."""
    def stream_with_retry():
        for attempt in range(OLLAMA_MAX_RETRIES + 1):
            try:
                yield from _stream_ollama(ollama_messages)
                # Sau khi stream xong → gửi meta chunk để Frontend cập nhật cache
                yield json.dumps(meta, ensure_ascii=False) + "\n"
                return
            except requests.exceptions.ConnectionError:
                if attempt < OLLAMA_MAX_RETRIES:
                    time.sleep(1)
                    continue
                error_msg = "⚠️ Không thể kết nối đến AI. Vui lòng đảm bảo Ollama đang chạy."
                yield json.dumps({"token": error_msg, "done": True, "error": "connection"}, ensure_ascii=False) + "\n"
            except Exception as e:
                yield json.dumps({"token": f"❌ Lỗi: {str(e)}", "done": True, "error": "unknown"}, ensure_ascii=False) + "\n"
            return

    response = StreamingHttpResponse(stream_with_retry(), content_type='text/event-stream; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


class ChatbotAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_message = request.data.get('message', '').strip()
        system_instruction = request.data.get('system_instruction', '')
        history = request.data.get('history', [])
        use_stream = request.data.get('stream', True)
        # Danh sách địa điểm đã được cache ở Frontend (tên lowercase)
        loaded_destinations = [d.lower() for d in request.data.get('loaded_destinations', [])]

        if not user_message:
            return Response({'error': 'Vui lòng nhập tin nhắn.'}, status=400)

        # ── Lớp 1: kiểm tra an ninh cơ bản (giữ nguyên, chạy trước router) ─────
        if any(kw in user_message.lower() for kw in SECURITY_KEYWORDS):
            safe_reply = SECURITY_REFUSAL
            if use_stream:
                def safe_gen():
                    yield json.dumps({"token": safe_reply, "done": True}, ensure_ascii=False) + "\n"
                return StreamingHttpResponse(safe_gen(), content_type='text/event-stream; charset=utf-8')
            return Response({'reply': safe_reply})

        # ── Lớp 2: router ý định (mới) ────────────────────────────────────────
        intent_result = _classify_intent(user_message)
        intent = intent_result.get('intent') if intent_result else None
        routed = bool(intent_result and intent_result.get('accepted'))
        escalate = bool(routed and intent == 'complaint_support')
        log_id = None  # Phase 3: ghi IntentLog và trả id về đây

        # blocked: từ chối cố định, KHÔNG gọi Ollama
        if routed and intent == 'blocked':
            meta = _build_meta([], intent_result, routed=True, escalate=False, log_id=log_id)
            if use_stream:
                def blocked_gen():
                    yield json.dumps({"token": SECURITY_REFUSAL, "done": True}, ensure_ascii=False) + "\n"
                    yield json.dumps(meta, ensure_ascii=False) + "\n"
                response = StreamingHttpResponse(
                    blocked_gen(), content_type='text/event-stream; charset=utf-8'
                )
                response['Cache-Control'] = 'no-cache'
                response['X-Accel-Buffering'] = 'no'
                return response
            return Response({'reply': SECURITY_REFUSAL, 'meta': meta})

        # ── RAG (chỉ nạp khi nhãn cần dùng) ───────────────────────────────────
        needs_rag = (not routed) or intent in ('tour_search', 'destination_info')
        if needs_rag:
            rag_context, matched_dest_names = _build_destination_context(
                user_message, loaded_destinations
            )
        else:
            rag_context, matched_dest_names = "", []

        if routed:
            # ── Lớp 2a: prompt rút gọn theo nhãn ──────────────────────────────
            routed_system, routed_user_message, history_limit = _build_routed_prompt(
                intent, user_message, rag_context, request.user
            )
            ollama_messages = _build_messages(
                routed_system, history, routed_user_message, history_limit
            )
        else:
            # ── Luồng cũ nguyên vẹn (ngân sách + RAG + danh sách tour) ────────
            # Phân tích ngân sách từ toàn bộ context (history + tin nhắn hiện tại)
            full_context_for_budget = " ".join(
                [msg.get("content", "") for msg in history[-6:]] + [user_message]
            )
            max_budget = _extract_budget(full_context_for_budget)
            if max_budget:
                print(f"[Budget] Phát hiện ngân sách tối đa: {max_budget:,} VNĐ")

            # Nếu system_instruction trống hoặc không chứa danh sách tour, dựng lại prompt trực tiếp từ Database ở Backend!
            if not system_instruction or "<DANH_SACH_TOUR>" not in system_instruction:
                system_instruction = _build_legacy_system_instruction(max_budget)

            final_user_message = user_message
            if rag_context:
                # Trích xuất danh sách tour từ system_instruction để nhét vào user_message (chống recency bias của model nhỏ)
                tours_in_system = ""
                start_idx = system_instruction.find("<DANH_SACH_TOUR>")
                end_idx = system_instruction.find("</DANH_SACH_TOUR>")
                if start_idx != -1 and end_idx != -1:
                    tours_in_system = system_instruction[start_idx:end_idx + len("</DANH_SACH_TOUR>")]

                final_user_message = (
                    f"1. THÔNG TIN ĐỊA ĐIỂM (Không phải tour):\n{rag_context}\n\n"
                    f"2. DANH SÁCH TOUR TRONG HỆ THỐNG:\n{tours_in_system}\n\n"
                    f"CÂU HỎI CỦA KHÁCH: {user_message}\n\n"
                    f"(Gợi ý cho AI: Nếu khách hỏi tour, HÃY TÌM TRONG DANH SÁCH TOUR TRONG HỆ THỐNG. KHÔNG lấy thông tin địa điểm làm tour. Tuân thủ định dạng thẻ [TOUR_CARD:ID] ở Quy tắc Bắt buộc.)"
                )

            ollama_messages = _build_messages(
                system_instruction, history, final_user_message, 10
            )

        meta = _build_meta(
            matched_dest_names, intent_result,
            routed=routed, escalate=escalate, log_id=log_id,
        )

        # --- CHẾ ĐỘ STREAMING ---
        if use_stream:
            return _streaming_response(ollama_messages, meta)

        # --- CHẾ ĐỘ KHÔNG STREAMING (fallback) ---
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "messages": ollama_messages,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1024}
            }
            resp = requests.post(OLLAMA_URL, json=payload, timeout=(OLLAMA_TIMEOUT_CONNECT, OLLAMA_TIMEOUT_READ))
            resp.raise_for_status()
            data = {'reply': resp.json().get('message', {}).get('content', '')}
            if intent_result is not None:
                data['meta'] = meta
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
