-- ================================================================
-- Flashcard AI — Supabase Schema
-- Chạy file này trong: Supabase Dashboard → SQL Editor → New query
-- ================================================================

-- 1. Bộ thẻ flashcard của từng user
CREATE TABLE IF NOT EXISTS flashcard_sets (
    id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     TEXT        NOT NULL,   -- Flask session user_id (username hoặc UUID)
    title       TEXT        NOT NULL DEFAULT 'Bộ thẻ không tên',
    cards       JSONB       NOT NULL DEFAULT '[]',
    card_count  INTEGER     DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flashcard_sets_user ON flashcard_sets(user_id);

-- Backend tự xử lý auth → tắt RLS
ALTER TABLE flashcard_sets DISABLE ROW LEVEL SECURITY;


-- 2. Tiến trình học (XP, Level, Streak) per-user
CREATE TABLE IF NOT EXISTS game_stats (
    user_id     TEXT        PRIMARY KEY,  -- Flask session user_id
    xp          INTEGER     DEFAULT 0,
    level       INTEGER     DEFAULT 1,
    streak      INTEGER     DEFAULT 0,
    last_date   DATE,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE game_stats DISABLE ROW LEVEL SECURITY;


-- 3. Lịch sử tạo thẻ / analytics
CREATE TABLE IF NOT EXISTS flashcard_sessions (
    id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     TEXT        NOT NULL,   -- Flask session user_id
    query       TEXT,
    mode        TEXT,       -- 'content' hoặc 'vocabulary'
    card_count  INTEGER     DEFAULT 0,
    level_stats JSONB       DEFAULT '{}',
    tokens      INTEGER     DEFAULT 0,
    is_rag      BOOLEAN     DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON flashcard_sessions(user_id);

ALTER TABLE flashcard_sessions DISABLE ROW LEVEL SECURITY;

-- 4. Storage Bucket for RAG Assets
INSERT INTO storage.buckets (id, name, public) 
VALUES ('rag_assets', 'rag_assets', true) 
ON CONFLICT (id) DO NOTHING;

-- Cho phép upload file (vì app tự handle việc ai được upload)
CREATE POLICY "Allow public uploads to rag_assets" 
ON storage.objects FOR INSERT TO public 
WITH CHECK (bucket_id = 'rag_assets');

-- Cho phép đọc file
CREATE POLICY "Allow public select from rag_assets" 
ON storage.objects FOR SELECT TO public 
USING (bucket_id = 'rag_assets');

-- 5. Quản lý tài liệu PDF đã upload
CREATE TABLE IF NOT EXISTS user_documents (
    id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    file_name   TEXT        NOT NULL,
    file_url    TEXT        NOT NULL,
    file_size   INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_documents_user ON user_documents(user_id);
ALTER TABLE user_documents DISABLE ROW LEVEL SECURITY;

-- 6. Storage Bucket for PDF Documents
INSERT INTO storage.buckets (id, name, public) 
VALUES ('documents', 'documents', true) 
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Allow public uploads to documents" 
ON storage.objects FOR INSERT TO public 
WITH CHECK (bucket_id = 'documents');

CREATE POLICY "Allow public select from documents" 
ON storage.objects FOR SELECT TO public 
USING (bucket_id = 'documents');

-- 7. Bảng Feedback cho Data Flywheel
CREATE TABLE IF NOT EXISTS ai_feedback (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         TEXT        NOT NULL,
    original_card   JSONB       NOT NULL, -- Dữ liệu AI tạo ban đầu
    corrected_card  JSONB,      -- Dữ liệu sau khi người dùng sửa (NULL nếu là DELETE)
    feedback_type   TEXT        NOT NULL, -- 'EDIT' hoặc 'DELETE'
    document_name   TEXT,       -- Tên file PDF để ưu tiên khi tái sử dụng
    mode            TEXT,       -- 'content' hoặc 'vocabulary'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON ai_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_doc ON ai_feedback(document_name);
ALTER TABLE ai_feedback DISABLE ROW LEVEL SECURITY;


-- 8. Guardrail Logs — Ghi lại toàn bộ sự kiện kiểm duyệt
CREATE TABLE IF NOT EXISTS guardrail_logs (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    -- Context
    user_id         TEXT,                   -- NULL nếu chưa đăng nhập
    source          TEXT        NOT NULL,   -- 'chat' | 'document_upload' | 'text_update'
    -- Guardrail result
    allowed         BOOLEAN     NOT NULL,   -- TRUE = pass, FALSE = blocked
    violation       TEXT        NOT NULL,   -- GuardrailViolation.value (e.g. 'prompt_injection')
    severity        TEXT        NOT NULL DEFAULT 'info',  -- 'info' | 'warning' | 'critical'
    reason          TEXT,                   -- Lý do block/warn hiển thị cho user
    -- Input info (truncated, không lưu full content để bảo mật)
    input_preview   TEXT,                   -- 100 ký tự đầu của input
    input_length    INTEGER,
    -- Extra metadata
    metadata        JSONB       DEFAULT '{}',  -- matched_patterns, pii_types, etc.
    -- Timing
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guardrail_logs_user      ON guardrail_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_guardrail_logs_source    ON guardrail_logs(source);
CREATE INDEX IF NOT EXISTS idx_guardrail_logs_violation ON guardrail_logs(violation);
CREATE INDEX IF NOT EXISTS idx_guardrail_logs_allowed   ON guardrail_logs(allowed);
CREATE INDEX IF NOT EXISTS idx_guardrail_logs_created   ON guardrail_logs(created_at DESC);

ALTER TABLE guardrail_logs DISABLE ROW LEVEL SECURITY;


-- 9. Chat Episodes — Lưu từng lượt hội thoại để phân tích học tập
-- Code ghi: modules/chat/chat_memory.py → save_episode()
CREATE TABLE IF NOT EXISTS chat_episodes (
    id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    card_scope  TEXT        NOT NULL,   -- MD5 8-char hash của card question (scope per-card)
    summary     TEXT        NOT NULL,   -- Câu hỏi của user (tối đa 500 ký tự)
    outcome     TEXT        NOT NULL,   -- Câu trả lời của AI (tối đa 1000 ký tự)
    tags        JSONB       DEFAULT '{}',  -- {intent, card_question, ...metadata}
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_episodes_user  ON chat_episodes(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_episodes_card  ON chat_episodes(card_scope);
CREATE INDEX IF NOT EXISTS idx_chat_episodes_time  ON chat_episodes(created_at DESC);
ALTER TABLE chat_episodes DISABLE ROW LEVEL SECURITY;


-- 10. Learner Profiles — Profile người học dài hạn (upsert per-user)
-- Code ghi: modules/chat/chat_memory.py → update_profile()
-- profile_data chứa: {total_chats, topic_frequency, intent_frequency, preferences, last_active}
CREATE TABLE IF NOT EXISTS learner_profiles (
    user_id         TEXT        PRIMARY KEY,
    profile_data    JSONB       DEFAULT '{}',   -- Aggregated learning stats
    conflict_log    JSONB       DEFAULT '[]',   -- Log các lần overwrite fact (reserved)
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE learner_profiles DISABLE ROW LEVEL SECURITY;


-- 11. Document Cache — Lưu kết quả xử lý PDF để tái sử dụng (tránh re-process)
-- Code ghi: modules/RAG/rag_core.py → save_cache_supabase()
CREATE TABLE IF NOT EXISTS document_cache (
    file_hash       TEXT        PRIMARY KEY,
    document_name   TEXT,
    chunks_json     JSONB       NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE document_cache DISABLE ROW LEVEL SECURITY;


-- 12. Notifications — Hệ thống thông báo cho user
CREATE TABLE IF NOT EXISTS notifications (
    id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     TEXT        NOT NULL,
    title       TEXT        NOT NULL,
    description TEXT,
    type        TEXT        DEFAULT 'info',
    is_read     BOOLEAN     DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;
