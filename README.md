# 🎓 Flashcard AI - Intelligent RAG Learning System

Flashcard AI là một hệ thống học tập thông minh sử dụng công nghệ **RAG (Retrieval-Augmented Generation)** để tự động chuyển đổi tài liệu từ nhiều định dạng (PDF, Video YouTube, Văn bản) thành các bộ thẻ ghi nhớ (Flashcards) chất lượng cao.

[![Frontend](https://img.shields.io/badge/Frontend-Live-blue?style=for-the-badge&logo=next.js)](https://a20-app-041.onrender.com/)
[![Backend](https://img.shields.io/badge/Backend-Live-green?style=for-the-badge&logo=flask)](https://flashcard-y5ml.onrender.com/)

---

## 🚀 Tính năng nổi bật

- **Tạo Flashcard bằng AI**: Tự động trích xuất kiến thức và tạo thẻ ghi nhớ từ tài liệu.
- **Hỗ trợ đa phương tiện**:
  - **PDF**: Đọc và trích xuất nội dung, hỗ trợ OCR cho tài liệu dạng ảnh.
  - **YouTube / Video**: Tự động tải transcript hoặc trích xuất âm thanh → văn bản.
- **Highlight tài liệu**: Ánh xạ mỗi thẻ về đúng đoạn PDF tương ứng.
- **Trợ lý Chat AI**: Trò chuyện với tài liệu, hỗ trợ Guardrails kiểm soát nội dung.
- **Study Mode & Game**: Ôn tập theo thuật toán FSRS, Quiz Game, Matching.
- **Lịch học & Thông báo**: Nhắc nhở ôn tập đúng thời điểm.
- **Thống kê Analytics**: Theo dõi tiến độ, điểm số, lịch sử học tập.
- **Xuất sang Anki**: Xuất bộ thẻ định dạng `.apkg`.
- **Quản lý thư viện**: Lưu, chỉnh sửa, tổ chức bộ thẻ cá nhân.

---

## Link demo: https://www.youtube.com/watch?v=rm6SrcOMfec

## 🛠️ Công nghệ sử dụng

### Backend
- **Core**: Python 3.10+, Flask
- **LLM & AI**: OpenAI (GPT-4o-mini), Groq (Whisper)
- **Vector Database**: ChromaDB (in-memory, ephemeral)
- **Database & Auth**: Supabase (PostgreSQL + Storage)
- **Xử lý tài liệu**: PyMuPDF, Tesseract OCR, yt-dlp, gTTS
- **Triển khai**: Gunicorn, Docker, Render

### Frontend
- **Framework**: Next.js (App Router)
- **UI**: React, Tailwind CSS, Shadcn/UI, Lucide Icons
- **Triển khai**: Render Static Site

---

## 📋 Yêu cầu hệ thống (Local)

| Phần mềm | Phiên bản | Ghi chú |
|----------|-----------|---------|
| Python | 3.10+ | Bắt buộc |
| Node.js | 18+ | Cho frontend |
| Tesseract OCR | 5.x | Nếu dùng OCR PDF |
| FFmpeg | 6.x | Nếu xử lý video |
| Git | bất kỳ | Clone repo |

**Cài Tesseract (Windows)**: Tải tại [tesseract-ocr.github.io](https://tesseract-ocr.github.io/tessdoc/Installation.html), cài vào `C:\Program Files\Tesseract-OCR\`.

**Cài FFmpeg (Windows)**: Tải tại [ffmpeg.org](https://ffmpeg.org/download.html), thêm vào PATH.

---

## 🔑 Các API Key cần có

Tạo tài khoản và lấy key tại các dịch vụ sau:

| Biến môi trường | Dịch vụ | Link |
|----------------|---------|------|
| `OPENAI_API_KEY` | OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) |
| `GROQ_API_KEY` | Groq (Whisper transcription) | [console.groq.com](https://console.groq.com/) |
| `SUPABASE_URL` | Supabase | [supabase.com](https://supabase.com/) |
| `SUPABASE_ANON_KEY` | Supabase | Dashboard → Project Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase | Dashboard → Project Settings → API |
| `LANGCHAIN_API_KEY` | LangSmith (optional) | [smith.langchain.com](https://smith.langchain.com/) |

---

## 💻 Hướng dẫn cài đặt & Chạy Local

### 1. Clone repo

```bash
git clone https://github.com/a20-ai-thuc-chien/A20-App-041.git
cd Flashcard AI/RAG_luc
```

### 2. Cấu hình Backend

```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt môi trường ảo
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

Tạo file `.env` ở thư mục gốc từ file mẫu (nếu dùng Windows CMD thì dùng lệnh copy):

```bash
# Mac/Linux hoặc PowerShell/Git Bash:
cp ../.env.example ../.env

# Windows CMD:
copy ..\.env.example ..\.env

# Sau đó mở file .env (ở thư mục gốc) và điền các API Key vào
```

Nội dung `.env` tối thiểu cần có:

```env
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...

# Windows only (bỏ dòng này nếu chạy trên Linux/Mac)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Chạy backend:

```bash
python app_rag.py
# Backend chạy tại: http://localhost:5000
```

### 3. Cấu hình Frontend

```bash
cd frontend

# Cài đặt dependencies
npm install

# Chạy development server
npm run dev
# Frontend chạy tại: http://localhost:3000
---

## 🐳 Chạy bằng Docker (tùy chọn)

```bash
# Đảm bảo bạn đang đứng ở thư mục RAG_luc (nếu đang ở frontend thì dùng lệnh cd ..)
# cd ..

# Build image
docker build -t flashcard-ai .

# Chạy container (truyền .env vào)
docker run -p 5000:5000 --env-file ../.env flashcard-ai
```
---

## 🌐 Triển khai trên Render

Dự án đang chạy live tại:
- **Frontend**: [https://a20-app-041.onrender.com/](https://a20-app-041.onrender.com/)
- **Backend API**: [https://flashcard-y5ml.onrender.com/](https://flashcard-y5ml.onrender.com/)

> Cần cả 2 service đang chạy để ứng dụng hoạt động đầy đủ do việc khởi động trên render cần mất 1 chút thời gian.

---

## 📁 Cấu trúc thư mục

```
RAG_luc/
├── app_rag.py          # Entry point Flask
├── api_routes/         # Các route API (rag, library, auth, ...)
├── modules/
│   ├── RAG/            # Core: rag_core, retrieval, generation
│   ├── chat/           # Chat handler, semantic cache
│   ├── image/          # Vision processor (OCR)
│   └── guardrail/      # Content safety
├── config/             # Settings, constants
├── frontend/           # Next.js frontend
├── Dockerfile
├── requirements.txt
└── .env.example
```
---

## 📝 Giấy phép

Dự án được thực hiện cho mục đích học tập và nghiên cứu công nghệ AI.
