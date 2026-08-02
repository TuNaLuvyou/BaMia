import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { CreditCard, QrCode, Building, Lock, CheckCircle, XCircle } from 'lucide-react';
import PageBanner from "../components/PageBanner";

const Payments = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const state = location.state || {};
    const { selectedCartItems = [], pendingBookings = [], totalAmount = 0 } = state;

    // isRetryMode = true khi thanh toán lại từ booking Pending
    const isRetryMode = pendingBookings.length > 0;

    const [paymentMethod, setPaymentMethod] = useState('vnpay');
    const [isProcessing, setIsProcessing] = useState(false);
    
    // Sandbox UI States
    const [sandboxOpen, setSandboxOpen] = useState(false);
    const [sandboxType, setSandboxType] = useState('');
    const [transactionId, setTransactionId] = useState(null);
    const [sandboxActionLoading, setSandboxActionLoading] = useState(false);

    useEffect(() => {
        // Chỉ redirect nếu không có dữ liệu nào cả
        if (selectedCartItems.length === 0 && pendingBookings.length === 0) {
            navigate('/my-bookings');
        }
    }, [selectedCartItems, pendingBookings, navigate]);

    // 1. Gửi request tạo transaction
    const handleInitiatePayment = async () => {
        // Nếu đã có transaction đang chờ, mở lại modal
        if (transactionId) {
            setSandboxType(paymentMethod);
            setSandboxOpen(true);
            return;
        }
        setIsProcessing(true);
        try {
            let res;
            if (isRetryMode) {
                // Thanh toán lại Pending bookings
                res = await api.post('payments/retry/', {
                    booking_ids: pendingBookings.map(b => b.id),
                    payment_method: paymentMethod
                });
            } else {
                // Thanh toán từ giỏ hàng
                res = await api.post('payments/create/', {
                    cart_item_ids: selectedCartItems.map(item => item.id),
                    payment_method: paymentMethod
                });
            }
            setTransactionId(res.data.transaction_id);
            setSandboxType(paymentMethod);
            setSandboxOpen(true);
        } catch (error) {
            console.error(error);
            alert("Lỗi khi khởi tạo thanh toán.");
        } finally {
            setIsProcessing(false);
        }
    };

    // Đóng modal mà KHÔNG hủy giao dịch - transaction vẫn Pending, giỏ hàng vẫn còn
    const handleCloseModal = () => {
        setSandboxOpen(false);
        // Không reset transactionId - user có thể mở lại modal bằng cách bấm "Thanh toán ngay"
    };

    // 2. Giả lập Server của Sandbox IPN gọi Webhook về Backend
    const simulateSandboxIPN = async (statusCode) => {
        setSandboxActionLoading(true);
        try {
            // Chữ ký sandbox đọc từ biến môi trường (mặc định 'mock_signature_12345' cho bản demo).
            // LƯU Ý: chữ ký này CHỈ dùng cho mô phỏng thanh toán, KHÔNG phải secret thật.
            const webhookSignature = import.meta.env.VITE_PAYMENT_WEBHOOK_SECRET || 'mock_signature_12345';
            await api.post('payments/webhook/', {
                transaction_id: transactionId,
                status: statusCode,
                signature: webhookSignature
            });
            
            await new Promise(r => setTimeout(r, 1500));

            setSandboxOpen(false);
            setTransactionId(null); // Reset sau khi giao dịch kết thúc
            if (statusCode === 'success') {
                alert("Đơn hàng đã thanh toán thành công!");
                navigate('/my-bookings');
            } else {
                alert("Giao dịch bị hủy. Giỏ hàng của bạn vẫn còn nguyên, bạn có thể thử lại.");
                navigate('/my-bookings');
            }
        } catch (error) {
            console.error("Lỗi IPN:", error);
            alert("Lỗi kết nối Webhook IPN.");
        } finally {
            setSandboxActionLoading(false);
        }
    };

    if (selectedCartItems.length === 0 && pendingBookings.length === 0) return null;

    // Dữ liệu hiển thị trong ô Tóm tắt đơn hàng (hỗ trợ cả 2 mode)
    const displayItems = isRetryMode
        ? pendingBookings.map(b => ({
            id: b.id,
            label: `Đơn #${b.id}`,
            price: Number(b.total_price),
            number_of_people: b.number_of_people
          }))
        : selectedCartItems.map(item => ({
            id: item.id,
            label: item.tour_detail.title,
            price: item.tour_detail.price * item.number_of_people,
            number_of_people: item.number_of_people
          }));

    return (
        <div className="bg-gray-50 min-h-screen pb-20">
            <PageBanner 
                title="Thanh Toán An Toàn"
                subtitle="Cổng thanh toán bảo mật, hỗ trợ đa dạng phương thức thanh toán trong và ngoài nước."
                image="https://images.unsplash.com/photo-1516738901171-8eb4fc13bd20?auto=format&fit=crop&q=80&w=2000"
            />
            
            <div className="max-w-4xl mx-auto px-4 py-8 relative z-10">
                <div className="mt-2 md:mt-4 flex flex-col md:flex-row gap-8">
                    {/* Chọn phương thức thanh toán */}
                    <div className="md:w-2/3 space-y-6">
                        <h2 className="text-xl font-bold text-gray-800">Chọn phương thức thanh toán</h2>
                    
                    {/* VNPAY */}
                    <div 
                        className={`border-2 rounded-xl p-4 cursor-pointer transition-all flex items-center gap-4 ${paymentMethod === 'vnpay' ? 'border-[#007777] bg-[#007777]/5' : 'border-gray-200 hover:border-[#007777]/30'}`}
                        onClick={() => setPaymentMethod('vnpay')}
                    >
                        <div className="w-12 h-12 bg-white border rounded-lg flex items-center justify-center">
                            <Building className="text-[#007777] font-bold" />
                        </div>
                        <div className="flex-grow">
                            <h3 className="font-bold text-gray-800 mb-1">VNPAY (ATM Nội địa)</h3>
                            <p className="text-sm text-gray-500">Hỗ trợ tất cả thẻ ATM ngân hàng trong nước</p>
                        </div>
                        {paymentMethod === 'vnpay' && <CheckCircle className="text-[#007777]" />}
                    </div>

                    {/* MOMO */}
                    <div 
                        className={`border-2 rounded-xl p-4 cursor-pointer transition-all flex items-center gap-4 ${paymentMethod === 'momo' ? 'border-[#A50064] bg-pink-50' : 'border-gray-200 hover:border-pink-300'}`}
                        onClick={() => setPaymentMethod('momo')}
                    >
                        <div className="w-12 h-12 bg-[#A50064] rounded-lg flex items-center justify-center text-white font-bold text-xl">
                            M
                        </div>
                        <div className="flex-grow">
                            <h3 className="font-bold text-gray-800 mb-1">Ví điện tử MoMo</h3>
                            <p className="text-sm text-gray-500">Quét mã QR bằng ứng dụng MoMo</p>
                        </div>
                        {paymentMethod === 'momo' && <CheckCircle className="text-[#A50064]" />}
                    </div>

                    {/* STRIPE */}
                    <div 
                        className={`border-2 rounded-xl p-4 cursor-pointer transition-all flex items-center gap-4 ${paymentMethod === 'stripe' ? 'border-[#007777] bg-[#007777]/5' : 'border-gray-200 hover:border-[#007777]/30'}`}
                        onClick={() => setPaymentMethod('stripe')}
                    >
                        <div className="w-12 h-12 bg-[#007777] rounded-lg flex items-center justify-center">
                            <CreditCard className="text-white" />
                        </div>
                        <div className="flex-grow">
                            <h3 className="font-bold text-gray-800 mb-1">Thẻ Quốc Tế (Stripe)</h3>
                            <p className="text-sm text-gray-500">Thanh toán bằng thẻ Visa, MasterCard, Amex</p>
                        </div>
                        {paymentMethod === 'stripe' && <CheckCircle className="text-[#007777]" />}
                    </div>
                </div>

                {/* Tổng quan đơn hàng */}
                <div className="md:w-1/3">
                    <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-100">
                        <h3 className="text-lg font-bold text-gray-800 mb-4 border-b pb-2">Đơn hàng của bạn</h3>
                        <div className="space-y-3 mb-6 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
                            {displayItems.map(item => (
                                <div key={item.id} className="flex justify-between items-start text-sm">
                                    <span className="text-gray-600 w-2/3 line-clamp-2">{item.label} (x{item.number_of_people})</span>
                                    <span className="font-medium">{item.price.toLocaleString('vi-VN')} đ</span>
                                </div>
                            ))}
                        </div>
                        <div className="flex justify-between items-center text-xl font-bold border-t pt-4 mb-6">
                            <span>Tổng thanh toán</span>
                            <span className="text-[#007777]">{totalAmount.toLocaleString('vi-VN')} đ</span>
                        </div>

                        <button 
                            onClick={handleInitiatePayment}
                            disabled={isProcessing}
                            className={`w-full font-bold py-3.5 rounded-lg text-white shadow-md transition-all flex justify-center items-center gap-2
                                ${paymentMethod === 'vnpay' ? 'bg-[#007777] hover:bg-[#005555]' : 
                                  paymentMethod === 'momo' ? 'bg-[#A50064] hover:bg-[#80004d]' : 
                                  'bg-[#007777] hover:bg-[#005555]'}
                                ${isProcessing ? 'opacity-70 cursor-wait' : ''}
                            `}
                        >
                            <Lock className="w-4 h-4" /> 
                            {isProcessing ? 'Đang chuyển hướng...' : 'Thanh toán ngay'}
                        </button>
                    </div>
                </div>
            </div>

            {/* SANDBOX OVERLAY MOCK */}
            {sandboxOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70 backdrop-blur-sm p-4">
                    <div className="bg-white max-w-md w-full rounded-2xl shadow-2xl overflow-hidden shadow-black">
                        
                        {/* VNPAY SANDBOX */}
                        {sandboxType === 'vnpay' && (
                            <div className="p-6">
                                <div className="flex justify-between items-center mb-6 border-b pb-4">
                                    <h2 className="text-xl font-bold text-blue-800 flex items-center gap-2"><Building /> VNPAY Sandbox</h2>
                                    <button onClick={handleCloseModal} className="text-gray-400 hover:text-gray-800" title="Đóng (không hủy giao dịch)"><XCircle /></button>
                                </div>
                                <p className="text-sm text-gray-600 mb-6 bg-blue-50 p-3 rounded-lg border border-blue-100">
                                    Đây là môi trường kiểm thử (Sandbox). Sử dụng thẻ test do VNPAY cung cấp (Ngân hàng NCB).
                                </p>
                                <div className="space-y-4 mb-8">
                                    <div>
                                        <label className="text-xs font-semibold text-gray-500 uppercase">Số Thẻ</label>
                                        <input type="text" readOnly value="9704198526191432198" className="w-full bg-gray-100 border border-gray-300 px-3 py-2 rounded-md font-mono mt-1 text-gray-700" />
                                    </div>
                                    <div>
                                        <label className="text-xs font-semibold text-gray-500 uppercase">Tên Chủ Thẻ</label>
                                        <input type="text" readOnly value="NGUYEN VAN A" className="w-full bg-gray-100 border border-gray-300 px-3 py-2 rounded-md font-mono mt-1 text-gray-700" />
                                    </div>
                                    <div className="flex gap-4">
                                        <div className="w-1/2">
                                            <label className="text-xs font-semibold text-gray-500 uppercase">Ngày Phát Hành</label>
                                            <input type="text" readOnly value="07/15" className="w-full bg-gray-100 border border-gray-300 px-3 py-2 rounded-md mt-1 text-gray-700" />
                                        </div>
                                        <div className="w-1/2">
                                            <label className="text-xs font-semibold text-gray-500 uppercase">Mã OTP</label>
                                            <input type="text" readOnly value="123456" className="w-full bg-gray-100 border border-gray-300 px-3 py-2 rounded-md font-mono mt-1 text-gray-700 font-bold tracking-widest text-center" />
                                        </div>
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button 
                                        disabled={sandboxActionLoading}
                                        onClick={() => simulateSandboxIPN('success')} 
                                        className="flex-1 bg-green-600 hover:bg-green-700 text-white py-1.5 rounded-lg font-bold flex items-center justify-center gap-1 whitespace-nowrap text-sm"
                                    >
                                        {sandboxActionLoading ? 'Đang xử lý...' : 'Xác nhận Thanh toán'}
                                    </button>
                                    <button 
                                        disabled={sandboxActionLoading}
                                        onClick={() => simulateSandboxIPN('failed')} 
                                        className="bg-red-100 hover:bg-red-200 text-red-700 px-3 py-1.5 rounded-lg font-medium whitespace-nowrap text-sm"
                                    >
                                        Hủy giao dịch
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* MOMO SANDBOX */}
                        {sandboxType === 'momo' && (
                            <div className="p-6 text-center">
                                <div className="flex justify-between items-center mb-4">
                                    <div className="w-8"></div>
                                    <h2 className="text-xl font-bold text-[#A50064]">MoMo Developer</h2>
                                    <button onClick={handleCloseModal} className="text-gray-400 hover:text-gray-800" title="Đóng (không hủy giao dịch)"><XCircle /></button>
                                </div>
                                <p className="text-gray-600 text-sm mb-6">Môi trường Test. Vui lòng quét mã bên dưới bằng app MoMo Dev.</p>
                                
                                <div className="w-48 h-48 bg-white border-4 border-[#A50064] p-2 mx-auto rounded-xl flex items-center justify-center mb-6">
                                    <QrCode className="w-32 h-32 text-gray-800" />
                                </div>
                                <p className="text-2xl font-bold text-[#A50064] mb-8">{totalAmount.toLocaleString('vi-VN')} đ</p>
                                
                                <button 
                                    disabled={sandboxActionLoading}
                                    onClick={() => simulateSandboxIPN('success')} 
                                    className="w-full bg-[#A50064] hover:bg-[#80004d] text-white py-3 rounded-lg font-bold shadow-lg"
                                >
                                    {sandboxActionLoading ? 'Đang xử lý...' : 'Tôi đã quét mã (Mô phỏng)'}
                                </button>
                            </div>
                        )}

                        {/* STRIPE SANDBOX */}
                        {sandboxType === 'stripe' && (
                            <div className="p-6">
                                <div className="flex justify-between items-center mb-6 border-b pb-4">
                                    <h2 className="text-xl font-bold text-indigo-700 flex items-center gap-2"><CreditCard /> Stripe Checkout Mock</h2>
                                    <button onClick={handleCloseModal} className="text-gray-400 hover:text-gray-800" title="Đóng (không hủy giao dịch)"><XCircle /></button>
                                </div>
                                <div className="bg-yellow-50 text-yellow-800 text-xs p-3 rounded-md mb-6 border border-yellow-200">
                                    TEST MODE Giao dịch sẽ không trừ tiền thực tế. Sử dụng thẻ 4242.
                                </div>
                                <div className="space-y-4 mb-8">
                                    <div>
                                        <label className="text-xs font-semibold text-gray-500 uppercase">Card number</label>
                                        <input type="text" readOnly value="4242 4242 4242 4242" className="w-full bg-white border-2 border-indigo-100 px-3 py-2.5 rounded-md font-mono mt-1 text-gray-700 shadow-sm" />
                                    </div>
                                    <div className="flex gap-4">
                                        <div className="w-1/2">
                                            <label className="text-xs font-semibold text-gray-500 uppercase">Expiry (MM/YY)</label>
                                            <input type="text" readOnly value="12/30" className="w-full bg-white border-2 border-indigo-100 px-3 py-2.5 rounded-md mt-1 text-gray-700 shadow-sm" />
                                        </div>
                                        <div className="w-1/2">
                                            <label className="text-xs font-semibold text-gray-500 uppercase">CVC</label>
                                            <input type="text" readOnly value="123" className="w-full bg-white border-2 border-indigo-100 px-3 py-2.5 rounded-md font-mono mt-1 text-gray-700 shadow-sm" />
                                        </div>
                                    </div>
                                </div>
                                <button 
                                    disabled={sandboxActionLoading}
                                    onClick={() => simulateSandboxIPN('success')} 
                                    className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-md font-bold shadow-md"
                                >
                                    {sandboxActionLoading ? 'Processing...' : `Pay ${totalAmount.toLocaleString('vi-VN')} đ`}
                                </button>
                                <div className="text-center mt-3">
                                    <button onClick={() => simulateSandboxIPN('failed')} className="text-xs text-gray-400 hover:text-red-500 underline">
                                        Test Declined Card (Simulate Error)
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
        </div>
    );
};

export default Payments;
