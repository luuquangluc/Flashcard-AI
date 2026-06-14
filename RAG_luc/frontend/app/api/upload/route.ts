import { NextRequest, NextResponse } from 'next/server';

// Cho phép route chạy tối đa 10 phút (PDF processing rất nặng)
export const maxDuration = 600;

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    
    // Đẩy tiếp sang Flask (dùng BACKEND_URL)
    // Timeout 10 phút vì backend cần thời gian xử lý OCR + Vision + Embedding
    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000); // 10 phút

    const response = await fetch(`${backendUrl}/api/upload`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.indexOf("application/json") !== -1) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    } else {
      const text = await response.text();
      console.error('Backend không trả về JSON:', text.substring(0, 200));
      return NextResponse.json(
        { error: 'Server backend hiện đang quá tải hoặc khởi động lại. Vui lòng thử lại sau.' },
        { status: 502 }
      );
    }
  } catch (error: any) {
    console.error('Manual Proxy Error:', error);
    return NextResponse.json(
      { error: error.message || 'Lỗi truyền tải file qua Proxy' },
      { status: 500 }
    );
  }
}
