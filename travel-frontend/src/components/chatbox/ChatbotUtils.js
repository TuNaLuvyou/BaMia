export const CHAT_STORAGE_KEY = "travel_bamia_chat_history";
export const CHAT_EXPIRY_MS = 30 * 60 * 1000; // 30 phút (Tự động xóa sau 30p đóng web)

/**
 * Trích xuất ngân sách tối đa từ đoạn văn bản.
 * Ví dụ: '2 triệu' → 2000000, 'dưới 500k' → 500000
 */
export const parseBudget = (text) => {
  const t = text.toLowerCase();
  let m;

  // Dạng: 2.000.000 / 2,000,000 / 2000000 đồng
  m = t.match(/(\d[\d.,]+)\s*(?:đồng|vnd|vnđ)?/);
  if (m) {
    const raw = parseInt(m[1].replace(/[.,]/g, ''), 10);
    if (raw >= 10000) return raw;
  }

  // Dạng: X triệu
  m = t.match(/([\d.]+)\s*tri[ệe]u/);
  if (m) return Math.round(parseFloat(m[1]) * 1_000_000);

  // Dạng: Xk / X nghìn / X ngàn
  m = t.match(/([\d.]+)\s*(?:k\b|nghìn|ngàn)/);
  if (m) return Math.round(parseFloat(m[1]) * 1_000);

  return null;
};

/**
 * Lọc danh sách tour theo ngân sách tối đa.
 * maxBudget = null thì trả về toàn bộ.
 */
export const filterToursByBudget = (tours, maxBudget) => {
  if (!maxBudget) return tours;
  return tours.filter((t) => Number(t.price) <= maxBudget);
};

export const buildSystemPrompt = (tours = []) => {
  let toursText = "\n<DANH_SACH_TOUR>\n";
  if (tours.length === 0) {
    toursText += "Hiện chưa có tour nào.\n";
  } else {
    tours.forEach((t) => {
      const loc = t.location_detail?.name || "N/A";
      toursText += `<TOUR id="${t.id}" ten="${t.title}" dia_diem="${loc}" gia="${Number(t.price).toLocaleString('vi-VN')}" />\n`;
    });
  }
  toursText += "</DANH_SACH_TOUR>\n";

  return `Bạn là trợ lý AI du lịch TravelBaMia. Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào vấn đề.

QUY TẮC:
1. Chỉ chào lại 1 câu khi khách chào hỏi. Không liệt kê tour.
2. Khi khách hỏi danh sách tour: liệt kê tên tour bằng gạch đầu dòng. Không in 'id'. Không dùng [TOUR_CARD].
3. Khi khách yêu cầu xem chi tiết 1 tour cụ thể: viết tên tour rồi gắn thẻ [TOUR_CARD:id] ngay sau.
   Ví dụ: 'Đây là tour bạn chọn: Khám Phá Bản Cát Cát [TOUR_CARD:8]'
   - Lấy id CHÍNH XÁC từ thuộc tính id= trong thẻ <TOUR> bên dưới.
4. Không bịa tour, không dùng thông tin ngoài <DANH_SACH_TOUR>.
5. Không dùng [TASK_COMPLETE], [DONE], [SUCCESS].
6. Không trả lời về kỹ thuật/mã nguồn/database.

${toursText}`;
};

export const cleanBotReply = (text) =>
  text
    .replace(/\[TOUR_CARD:\d+\]/g, "")
    .replace(/\[ESCALATE\]/g, "")
    .replace(/\[TASK_COMPLETE\]/g, "")
    .replace(/\[.*?\]/g, "")
    .trim();
