# Sử dụng ảnh Python chính thức
FROM python:3.10-slim

# Cài đặt FFmpeg + Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y onnxruntime onnxruntime-gpu 2>/dev/null; true

# Copy toàn bộ mã nguồn vào
COPY . .

# Tạo thư mục cần thiết
RUN mkdir -p data temp_ocr temp_video FE_for_backend

# Khai báo port (Render sẽ dùng biến PORT)
EXPOSE 5000

# Tắt Telemetry của ChromaDB và các công cụ AI khác để tiết kiệm RAM & tránh lỗi log
ENV CHROMA_USER_TELEMETRY_DISABLED=1
ENV ANONYMIZED_TELEMETRY=False

# Lệnh chạy ứng dụng với Gunicorn (production) - Giảm threads xuống 1 để tránh OOM
CMD gunicorn --bind 0.0.0.0:${PORT:-5000} --timeout 600 --workers 1 --threads 1 --max-requests 30 --max-requests-jitter 5 app_rag:app
