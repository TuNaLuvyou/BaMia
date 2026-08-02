import React, { useState, useRef, useEffect, useContext, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { MessageCircle, User } from "lucide-react";
import { AuthContext } from "../context/AuthContext";
import api from "../api/axios";

// Import modules mới
import { 
  CHAT_STORAGE_KEY, 
  CHAT_EXPIRY_MS, 
  buildSystemPrompt, 
  cleanBotReply,
  parseBudget,
  filterToursByBudget
} from "./chatbox/ChatbotUtils";
import useStreamChat from "./chatbox/useStreamChat";
import ChatbotHeader from "./chatbox/ChatbotHeader";
import ChatbotMessages from "./chatbox/ChatbotMessages";
import ChatbotInput from "./chatbox/ChatbotInput";
import StatusBanner from "./chatbox/StatusBanner";

const Chatbot = () => {
  const { user, loading: authLoading } = useContext(AuthContext);
  const navigate = useNavigate();
  const { streamChat } = useStreamChat();

  const initialMessage = {
    text: "Xin chào! Mình là trợ lý AI của TravelBaMia. Mình có thể giúp gì cho chuyến đi sắp tới của bạn? 🌍",
    isBot: true,
  };

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([initialMessage]);
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [toursData, setToursData] = useState([]);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [isFetchingData, setIsFetchingData] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState("unknown");
  const [streamingText, setStreamingText] = useState("");
  // Cache địa điểm đang active trong context AI (tên chính xác)
  const [loadedDestinations, setLoadedDestinations] = useState([]);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Tự động cuộn mượt mà xuống dưới đáy khung chat
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    // Đặt delay nhỏ để bảo đảm DOM đã hoàn tất vẽ giao diện trước khi cuộn
    const timer = setTimeout(scrollToBottom, 80);
    return () => clearTimeout(timer);
  }, [messages, streamingText, isOpen]);

  // ── Load history ──────────────────────────────────────────────────────────
  useEffect(() => {
    const saved = localStorage.getItem(CHAT_STORAGE_KEY);
    if (saved) {
      try {
        const { messages: sm, history: sh, timestamp } = JSON.parse(saved);
        if (Date.now() - timestamp < CHAT_EXPIRY_MS) {
          setMessages(sm);
          setHistory(sh);
        } else {
          localStorage.removeItem(CHAT_STORAGE_KEY);
        }
      } catch {
        localStorage.removeItem(CHAT_STORAGE_KEY);
      }
    }
  }, []);

  // ── Lưu history ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (messages.length > 1 || (messages.length === 1 && !messages[0].isBot)) {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify({ messages, history, timestamp: Date.now() }));
    }
  }, [messages, history]);

  // ── Reset khi logout ───────────────────────────────────────────────────────
  useEffect(() => {
    if (authLoading) return; // Chờ auth loading xong rồi mới kiểm tra, tránh race condition xóa sạch dữ liệu khi reload!
    if (!user) {
      setMessages([initialMessage]);
      setHistory([]);
      setIsOpen(false);
      setSystemPrompt("");
      setOllamaStatus("unknown");
      localStorage.removeItem(CHAT_STORAGE_KEY);
    }
  }, [user, authLoading]);

  // ── Hàm fetch dữ liệu ──────────────────────────────────────────────────────
  const fetchContextData = useCallback(async (silent = false) => {
    if (!user) return;
    if (!silent) setIsFetchingData(true);
    try {
      const [toursRes, healthRes, ...userResList] = await Promise.allSettled([
        api.get("tours/"),
        api.get("chat/health/"),
        ...(user ? [api.get("bookings/"), api.get("cart/")] : []),
      ]);

      const tours = toursRes.status === "fulfilled"
        ? (toursRes.value.data?.results ?? toursRes.value.data ?? [])
        : [];
      setToursData(tours);

      if (healthRes.status === "fulfilled") {
        setOllamaStatus(healthRes.value.data?.status === "ok" ? "ok" : "offline");
      } else {
        setOllamaStatus("offline");
      }

      let bookings = [], cart = [];
      if (user && userResList.length === 2) {
        if (userResList[0].status === "fulfilled")
          bookings = userResList[0].value.data?.results ?? userResList[0].value.data ?? [];
        if (userResList[1].status === "fulfilled")
          cart = userResList[1].value.data?.results ?? userResList[1].value.data ?? [];
      }

      const newPrompt = buildSystemPrompt(tours, bookings, cart, user);
      setSystemPrompt(newPrompt);
      return newPrompt;
    } catch (err) {
      console.error("Lỗi fetch chatbot context:", err);
    } finally {
      if (!silent) setIsFetchingData(false);
    }
  }, [user]);

  // ── Fetch dữ liệu khi mở chat ──────────────────────────────────────────────
  useEffect(() => {
    if (isOpen && user) {
      fetchContextData();
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, user, fetchContextData]);

  // ── Gửi tin nhắn ──────────────────────────────────────────────────────────
  const handleSendMessage = async (e) => {
    e.preventDefault();
    const userText = input.trim();
    if (!userText || isLoading || isFetchingData) return;

    const needsRefresh = /giỏ hàng|đơn hàng|booking|kiểm tra|cập nhật/i.test(userText);
    let currentPrompt = systemPrompt;
    let currentTours = toursData; // Tour hiện tại (có thể đã lọc theo ngân sách)
    
    // Phân tích ngân sách từ toàn bộ context (history + tin nhắn hiện tại)
    const fullContextText = [
      ...history.slice(-6).map((m) => m.content),
      userText,
    ].join(" ");
    const maxBudget = parseBudget(fullContextText);
    if (maxBudget) {
      currentTours = filterToursByBudget(toursData, maxBudget);
      currentPrompt = buildSystemPrompt(currentTours);
    }
    
    if (needsRefresh) {
      setIsLoading(true);
      currentPrompt = await fetchContextData(true) || systemPrompt;
    }

    setMessages((prev) => [...prev, { text: userText, isBot: false }]);
    setInput("");
    setIsLoading(true);
    setStreamingText("");

    const newHistory = [...history, { role: "user", content: userText }];
    let accumulatedText = "";

    streamChat({
      message: userText,
      system_instruction: currentPrompt,
      history,
      loaded_destinations: loadedDestinations,   // Gửi cache hiện tại
      onToken: (token) => {
        accumulatedText += token;
        setStreamingText(accumulatedText);
      },
      onDone: (fullText, errorType, matchedDestinations = []) => {
        setStreamingText("");
        setIsLoading(false);
        if (errorType === "connection") setOllamaStatus("offline");

        // Cập nhật cache: giữ những địa điểm vừa match, evict những cái cũ không match
        if (matchedDestinations.length > 0) {
          // Giữ lại địa điểm cũ nếu vẫn nằm trong matched list
          setLoadedDestinations(matchedDestinations);
        } else {
          // Câu hỏi không liên quan địa điểm → giữ nguyên cache
          // (vì user vẫn có thể hỏi tiếp về địa điểm cũ không cần nhắc tên)
        }

        const tourMatch = fullText.match(/\[TOUR_CARD:(\d+)\]/);
        let tourId = tourMatch ? tourMatch[1] : null;

        // Hàm tìm tour khớp tên tốt nhất trong đoạn văn bản (longest-match first)
        const findBestMatchingTour = (text) => {
          if (!text) return null;
          const textLower = text.toLowerCase();
          let best = null;
          let bestLen = 0;
          for (const t of toursData) {
            const titleLower = t.title.toLowerCase();
            if (textLower.includes(titleLower) && titleLower.length > bestLen) {
              best = t;
              bestLen = titleLower.length;
            }
          }
          return best;
        };

        // Kiểm tra xem touri theo ID có khớp với tên tour được đề cập trong reply không
        const tourFoundById = tourId ? toursData.find((t) => String(t.id) === tourId) : null;
        const tourFoundByNameInReply = findBestMatchingTour(fullText);
        const tourFoundByNameInUserMsg = findBestMatchingTour(userText);
        // Ưu tiên: tên trong reply > tên trong user msg > ID
        const tourByName = tourFoundByNameInReply || tourFoundByNameInUserMsg;

        if (tourByName) {
          if (!tourFoundById) {
            // ID không tồn tại → dùng tên
            console.warn(`[TourCard] ID ${tourId} không tồn tại → dùng "${tourByName.title}" (id=${tourByName.id})`);
            tourId = String(tourByName.id);
          } else if (String(tourByName.id) !== tourId) {
            // ID tồn tại nhưng khác tên trong reply → nhượng cho tên (model hay viết đúng tên nhưng sai ID)
            console.warn(`[TourCard] ID ${tourId} ("${tourFoundById.title}") khác tên reply "${tourByName.title}" → sửa thành id=${tourByName.id}`);
            tourId = String(tourByName.id);
          }
        } else if (!tourFoundById && tourId) {
          // Không tìm được theo tên lẫn ID → xóa tourId để tránh hiển thị sai
          console.warn(`[TourCard] Không tìm thấy tour nào phù hợp, ẩn TourCard`);
          tourId = null;
        }
        const isEscalated = fullText.includes("[ESCALATE]");
        const cleanReply = cleanBotReply(fullText);

        setHistory([...newHistory, { role: "assistant", content: fullText }]);
        setMessages((prev) => [...prev, { text: cleanReply, isBot: true, tourId, isEscalated }]);
      },
      onError: (errMsg) => {
        setStreamingText("");
        setIsLoading(false);
        setMessages((prev) => [...prev, { text: errMsg, isBot: true, isError: true }]);
      },
    });
  };

  const handleClearChat = () => {
    if (window.confirm("Bạn có chắc chắn muốn xóa toàn bộ lịch sử cuộc trò chuyện này?")) {
      setMessages([initialMessage]);
      setHistory([]);
      setLoadedDestinations([]); // Xóa sạch hoàn toàn cache địa danh đang hoạt động
      setStreamingText("");
      setIsLoading(false);
      setInput("");
      localStorage.removeItem(CHAT_STORAGE_KEY);
    }
  };

  const handleEscalate = (isEmployee) => {
    if (isEmployee) {
      navigate("/contact");
    } else {
      setMessages(prev => [...prev, { text: "Tôi muốn tiếp tục hỏi AI", isBot: false }]);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="w-14 h-14 bg-[#005555] text-white rounded-full flex items-center justify-center shadow-2xl hover:bg-[#f97316] hover:scale-110 transition-all animate-bounce"
        >
          <MessageCircle className="w-7 h-7" />
        </button>
      )}

      {isOpen && (
        <div className="bg-white w-80 sm:w-96 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[520px] animate-fade-in-up">
          <ChatbotHeader 
            ollamaStatus={ollamaStatus} 
            isFetchingData={isFetchingData} 
            onClearChat={handleClearChat} 
            onClose={() => setIsOpen(false)} 
          />

          {user ? (
            <>
              <StatusBanner 
                ollamaStatus={ollamaStatus} 
                isFetchingData={isFetchingData} 
                onRetry={fetchContextData} 
              />
              <ChatbotMessages 
                messages={messages} 
                isLoading={isLoading} 
                streamingText={streamingText} 
                toursData={toursData} 
                messagesEndRef={messagesEndRef} 
                onEscalate={handleEscalate} 
              />
              <ChatbotInput 
                input={input} 
                setInput={setInput} 
                isLoading={isLoading} 
                isFetchingData={isFetchingData} 
                ollamaStatus={ollamaStatus} 
                onSendMessage={handleSendMessage} 
                inputRef={inputRef} 
              />
            </>
          ) : (
            <div className="flex-grow flex flex-col items-center justify-center p-8 text-center bg-gray-50">
              <div className="w-20 h-20 bg-teal-50 text-[#005555] rounded-full flex items-center justify-center mb-4 shadow-inner">
                <User className="w-10 h-10" />
              </div>
              <h4 className="font-bold text-gray-800 mb-2">Bạn chưa đăng nhập</h4>
              <p className="text-sm text-gray-600 mb-6 leading-relaxed">
                Vui lòng đăng nhập để sử dụng tính năng chat với trợ lý AI của TravelBaMia.
              </p>
              <button
                onClick={() => { setIsOpen(false); navigate("/login"); }}
                className="px-8 py-3 bg-[#005555] text-white rounded-full font-bold shadow-lg hover:bg-[#f97316] hover:scale-105 transition-all text-sm"
              >
                Đăng nhập ngay
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Chatbot;
