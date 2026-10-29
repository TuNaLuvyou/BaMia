import React from "react";
import { AlertTriangle, ThumbsDown, ThumbsUp } from "lucide-react";
import TourCard from "./TourCard";
import { cleanBotReply } from "./ChatbotUtils";

const ChatbotMessages = ({ 
  messages, 
  isLoading, 
  streamingText, 
  toursData, 
  messagesEndRef,
  onEscalate,
  onFeedback
}) => {
  return (
    <div className="flex-grow p-4 overflow-y-auto bg-gray-50 flex flex-col gap-3">
      {messages.map((msg, index) => (
        <div key={index} className={`flex ${msg.isBot ? "justify-start" : "justify-end"}`}>
          <div
            className={`max-w-[82%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm whitespace-pre-wrap ${
              msg.isBot
                ? msg.isError
                  ? "bg-red-50 text-red-700 border border-red-200 rounded-tl-none"
                  : "bg-white text-gray-800 border border-gray-100 rounded-tl-none"
                : "bg-[#005555] text-white rounded-tr-none"
            }`}
          >
            {msg.isError && <AlertTriangle className="w-3.5 h-3.5 inline mr-1 mb-0.5" />}
            {msg.text}
            {msg.isBot && msg.tourId && <TourCard id={msg.tourId} toursData={toursData} />}
            {msg.isBot && msg.isEscalated && (
              <div className="mt-3 flex flex-col gap-2 border-t border-gray-100 pt-3">
                <p className="text-[11px] text-gray-500 italic">Bạn cần hỗ trợ thêm?</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => onEscalate(false)}
                    className="flex-1 py-1 px-2 bg-gray-100 text-gray-700 rounded-lg text-xs hover:bg-gray-200 transition"
                  >
                    Tiếp tục với AI
                  </button>
                  <button
                    onClick={() => onEscalate(true)}
                    className="flex-1 py-1 px-2 bg-teal-600 text-white rounded-lg text-xs hover:bg-teal-700 transition"
                  >
                    Gặp nhân viên
                  </button>
                </div>
              </div>
            )}
            {msg.isBot && !msg.isError && msg.logId && (
              <div className="mt-2 flex items-center gap-1 border-t border-gray-50 pt-2">
                <span className="text-[10px] text-gray-400 mr-1">Câu trả lời này:</span>
                <button
                  type="button"
                  aria-label="Hữu ích"
                  title="Hữu ích"
                  disabled={typeof msg.feedback === "number"}
                  onClick={() => onFeedback?.(index, msg.logId, 1)}
                  className={`p-1 rounded-md transition disabled:cursor-default ${
                    msg.feedback === 1
                      ? "text-teal-600 bg-teal-50"
                      : "text-gray-400 hover:text-teal-600 hover:bg-gray-50"
                  }`}
                >
                  <ThumbsUp className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  aria-label="Không hữu ích"
                  title="Không hữu ích"
                  disabled={typeof msg.feedback === "number"}
                  onClick={() => onFeedback?.(index, msg.logId, -1)}
                  className={`p-1 rounded-md transition disabled:cursor-default ${
                    msg.feedback === -1
                      ? "text-orange-500 bg-orange-50"
                      : "text-gray-400 hover:text-orange-500 hover:bg-gray-50"
                  }`}
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Text đang stream */}
      {isLoading && streamingText && (
        <div className="flex justify-start">
          <div className="max-w-[82%] p-3 rounded-2xl rounded-tl-none text-sm leading-relaxed bg-white text-gray-800 border border-gray-100 shadow-sm whitespace-pre-wrap">
            {cleanBotReply(streamingText)}
            <span className="inline-block w-1 h-4 bg-teal-500 ml-0.5 animate-pulse align-text-bottom" />
          </div>
        </div>
      )}

      {/* Typing dots */}
      {isLoading && !streamingText && (
        <div className="flex justify-start">
          <div className="bg-white p-3 rounded-2xl rounded-tl-none shadow-sm flex gap-1 items-center">
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }} />
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};

export default ChatbotMessages;
