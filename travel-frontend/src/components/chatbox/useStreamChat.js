import { useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/";

const useStreamChat = () => {
  const streamChat = useCallback(async ({
    message,
    system_instruction,
    history,
    loaded_destinations = [],   // Cache danh sách địa điểm đang active
    onToken,
    onDone,
    onError
  }) => {
    const accessToken = localStorage.getItem("access_token");
    try {
      const response = await fetch(`${API_BASE}chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
          message,
          system_instruction,
          history: history.slice(-10),  // Gửi 10 tin nhắn gần nhất (5 lượt chat của AI và Khách) theo yêu cầu
          loaded_destinations,   // Gửi cache lên Backend
          stream: true,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        onError(errData.error || `Lỗi server: ${response.status}`);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let fullText = "";
      let matchedDestinations = [];  // Sẽ được điền từ meta chunk
      let meta = null;               // Meta đầy đủ (intent, escalate, log_id...)

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n").filter(Boolean);

        for (const line of lines) {
          try {
            const parsed = JSON.parse(line);

            // Xử lý meta chunk (không phải token)
            if (parsed.meta === true) {
              meta = parsed;
              matchedDestinations = parsed.matched_destinations || [];
              continue;
            }

            if (parsed.error) {
              onToken(parsed.token || "");
              onDone(fullText + (parsed.token || ""), parsed.error, [], meta);
              return;
            }
            if (parsed.token) {
              fullText += parsed.token;
              onToken(parsed.token);
            }
            // Đợi stream đóng tự nhiên để lấy trọn vẹn chunk meta cuối cùng
            if (parsed.done) {
              // Ghi nhận trạng thái hoàn thành nhưng không return sớm để đợi đọc meta chunk
            }
          } catch {
            // Bỏ qua JSON lỗi parse
          }
        }
      }
      onDone(fullText, null, matchedDestinations, meta);
    } catch (err) {
      if (err.name === "AbortError") return;
      const isOffline = !navigator.onLine || err.message?.includes("fetch");
      onError(isOffline
        ? "⚠️ Không có kết nối mạng hoặc server đang tắt."
        : `Lỗi kết nối: ${err.message}`
      );
    }
  }, []);

  return { streamChat };
};

export default useStreamChat;
