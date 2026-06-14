"""
config/settings.py — Cấu hình tập trung cho toàn bộ hệ thống RAG Flashcard AI.
Tất cả env vars, model names, API prices, paths đều được quản lý tại đây.
"""
import os
from pathlib import Path

# ================================================================
# Paths
# ================================================================
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
DOC_DIR = DATA_DIR  # alias cho backward compat
TEMP_OCR_DIR = ROOT_DIR / "temp_ocr"
TEMP_VIDEO_DIR = ROOT_DIR / "temp_video"
FRONTEND_DIR = ROOT_DIR / "FE_for_backend"

# ================================================================
# Environment — Load .env từ thư mục cha (A20-App-041)
# ================================================================
from dotenv import load_dotenv
_env_path = ROOT_DIR.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=str(_env_path))
else:
    # fallback: .env cùng cấp
    load_dotenv(dotenv_path=str(ROOT_DIR / ".env"))

# ================================================================
# LLM Models
# ================================================================
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
ANSWER_MODEL_NAME = os.getenv("ANSWER_MODEL_NAME", "gpt-4o-mini")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
LOCAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# ================================================================
# API Keys
# ================================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ================================================================
# Supabase
# ================================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# ================================================================
# Flask
# ================================================================
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "rag_flashcard_secret_key_123")
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
FLASK_PORT = int(os.getenv("PORT", 5000))

# ================================================================
# API Pricing (USD per token)
# ================================================================
API_PRICES = {
    "gpt-4o-mini":            {"in": 0.15  / 1_000_000, "out": 0.60  / 1_000_000},
    "gpt-4o":                 {"in": 5.00  / 1_000_000, "out": 15.00 / 1_000_000},
    "text-embedding-3-small": {"in": 0.02  / 1_000_000, "out": 0},
}

# ================================================================
# Cost logging
# ================================================================
COST_FILE = str(ROOT_DIR / "api_costs.json")

# ================================================================
# Default Auth Users (fallback khi không có Supabase)
# ================================================================
import hashlib
DEFAULT_USERS = {
    "admin": {"password": hashlib.sha256("admin123".encode()).hexdigest(), "role": "admin", "name": "System Administrator"},
    "user":  {"password": hashlib.sha256("user123".encode()).hexdigest(),  "role": "user",  "name": "Student User"}
}

# ================================================================
# Logging
# ================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ================================================================
# Mem0 — Long-term Chat Memory
# Tự động cấu hình Mem0 Memory() dùng OpenAI embeddings.
# Nếu OPENAI_API_KEY đã set → Mem0 sẽ dùng OpenAI embeddings mặc định.
# Có thể override bằng MEM0_LLM_PROVIDER, MEM0_LLM_MODEL nếu muốn dùng model khác.
# ================================================================
MEM0_ENABLED = os.getenv("MEM0_ENABLED", "true").lower() in ("true", "1", "yes")
MEM0_LLM_PROVIDER = os.getenv("MEM0_LLM_PROVIDER", "openai")  # openai | groq | ...
MEM0_LLM_MODEL = os.getenv("MEM0_LLM_MODEL", MODEL_NAME)      # dùng model chính
MEM0_EMBEDDER_PROVIDER = os.getenv("MEM0_EMBEDDER_PROVIDER", "openai")
MEM0_EMBEDDER_MODEL = os.getenv("MEM0_EMBEDDER_MODEL", EMBEDDING_MODEL_NAME)

MEM0_CONFIG = {
    "llm": {
        "provider": MEM0_LLM_PROVIDER,
        "config": {
            "model": MEM0_LLM_MODEL,
            "temperature": 0.1,
            "max_tokens": 2000,
        },
    },
    "embedder": {
        "provider": MEM0_EMBEDDER_PROVIDER,
        "config": {
            "model": MEM0_EMBEDDER_MODEL,
        },
    },
    "version": "v1.1",
}
