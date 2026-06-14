# Flashcard AI — System Architecture

## Mô tả kiến trúc cho ChatGPT vẽ sơ đồ

---

## Prompt gợi ý cho ChatGPT

> Draw a clean system architecture diagram for a web application called "Flashcard AI" with the following components and data flow. Use a horizontal layout with arrows between components. Style: dark navy background, white icons in circles, red accent arrows, similar to a professional tech diagram.

---

## Chi tiết kiến trúc

### Các thành phần chính (trái → phải)

```
User → Frontend (Next.js) → Backend/API (Flask) → Database (Supabase) → AI Agent/LLM (OpenAI) → External Services
                                    ↑
                              Vector DB (ChromaDB)
```

---

### 1. USER
- Người dùng truy cập qua trình duyệt web
- Hành động: upload PDF/Video, đặt câu hỏi, ôn tập thẻ, chơi game

---

### 2. FRONTEND — Next.js (Render Static)
- URL: `https://a20-app-041.onrender.com`
- Các màn hình chính:
  - **Generator**: Upload tài liệu & tạo flashcard
  - **Library**: Quản lý bộ thẻ đã lưu
  - **Study**: Ôn tập theo thuật toán FSRS
  - **Game**: Quiz, Matching game
  - **Analytics**: Thống kê tiến độ học tập
  - **Chat**: Trợ lý AI hỏi đáp về tài liệu
- Giao tiếp với Backend qua REST API + Server-Sent Events (SSE)

---

### 3. BACKEND / API — Flask + Gunicorn (Render Docker)
- URL: `https://flashcard-y5ml.onrender.com`
- Các module chính:
  - `api_routes/rag.py` — Upload, RAG query, Chat
  - `api_routes/library.py` — CRUD bộ thẻ
  - `api_routes/auth.py` — Xác thực người dùng
  - `modules/RAG/` — Core pipeline: chunk → embed → retrieve → generate
  - `modules/chat/` — Chat với thẻ, Semantic Cache
  - `modules/guardrail/` — Kiểm soát nội dung độc hại
  - `modules/image/` — OCR xử lý PDF ảnh

---

### 4. VECTOR DATABASE — ChromaDB (in-memory)
- Lưu trữ embedding của các đoạn văn bản (chunks) từ tài liệu
- Hỗ trợ tìm kiếm ngữ nghĩa (Dense Retrieval)
- Kết hợp BM25 (Sparse) + ChromaDB (Dense) → Reciprocal Rank Fusion (RRF)

---

### 5. DATABASE & AUTH — Supabase (PostgreSQL + Storage)
- **PostgreSQL tables**:
  - `users` — Tài khoản người dùng
  - `flashcard_sets` — Bộ thẻ đã lưu
  - `flashcard_sessions` — Lịch sử ôn tập
  - `document_cache` — Cache chunk đã xử lý (tránh re-embed)
  - `ai_feedback` — Dữ liệu feedback người dùng (Data Flywheel)
  - `game_stats` — Thống kê game
  - `notifications` — Thông báo nhắc học
- **Storage**: Lưu file PDF, audio MP3, PDF highlight

---

### 6. AI AGENT / LLM
- **OpenAI GPT-4o-mini**: Sinh câu hỏi, câu trả lời, chat
- **OpenAI text-embedding-3-small**: Tạo vector embedding
- **Groq Whisper**: Speech-to-text từ video/audio
- **LangSmith**: Tracing & monitoring LLM calls

---

### 7. EXTERNAL SERVICES
- **yt-dlp**: Tải transcript/audio từ YouTube
- **gTTS**: Text-to-speech cho từ vựng
- **deep-translator**: Dịch từ Anh → Việt
- **PyMuPDF + Tesseract**: Đọc PDF + OCR

---

## Luồng dữ liệu chính

### Luồng tạo Flashcard từ PDF:
```
User upload PDF
  → Backend nhận file, tính hash MD5
  → Kiểm tra document_cache (Supabase) → nếu HIT: dùng lại chunks
  → Nếu MISS: PyMuPDF/Tesseract → trích xuất text → chia chunk
  → OpenAI Embedding → lưu vào ChromaDB + document_cache
  → BM25 + ChromaDB RRF Retrieval → lấy top chunks
  → GPT-4o-mini → sinh câu hỏi + câu trả lời
  → Batch Embedding → ánh xạ thẻ → chunk → highlight PDF (BBox)
  → Trả về danh sách Flashcard kèm highlight_pdf_base64
  → Frontend hiển thị thẻ + PDF viewer
```

### Luồng Chat với tài liệu:
```
User gửi tin nhắn
  → Guardrail check (injection, toxic, PII, off-topic)
  → Semantic Cache lookup (Cosine Similarity)
  → Nếu HIT: trả về ngay (0 LLM call)
  → Nếu MISS: RAG Retrieval → build prompt → GPT-4o-mini
  → Lưu vào Semantic Cache → trả về response
```

### Luồng upload Video:
```
User nhập YouTube URL
  → yt-dlp tải transcript/audio
  → Groq Whisper transcribe (nếu không có transcript)
  → Lưu text → nạp vào RAG pipeline như PDF
```

---

## Sơ đồ tóm tắt để ChatGPT vẽ

```
Vẽ sơ đồ kiến trúc hệ thống với layout ngang, nền màu navy (#0D1B2A), icon trắng trong vòng tròn, mũi tên màu đỏ:

[USER] --→ [FRONTEND Next.js] --→ [BACKEND Flask API] --→ [SUPABASE DB]
                                          |                      |
                                    [ChromaDB]            [Supabase Storage]
                                          |
                               [OpenAI GPT-4o-mini]
                               [OpenAI Embedding]
                               [Groq Whisper]
                                          |
                               [External: yt-dlp, gTTS, Tesseract]

Phía dưới có mũi tên đứt nét hai chiều với chú thích "Luồng dữ liệu"
```
