"""
dependencies.py - Các dependency và hàm dùng chung cho tất cả các route.
"""
import os
import hashlib
import logging
from flask import request, jsonify, session

logger = logging.getLogger(__name__)
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY, DEFAULT_USERS
)

# ----------------------------------------------------------------
# Cấu hình Supabase & Auth
# ----------------------------------------------------------------
USERS = DEFAULT_USERS

try:
    from supabase import create_client, Client as SupabaseClient
    _sb_url = SUPABASE_URL
    _sb_key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    if _sb_url and _sb_key:
        import httpx
        from supabase.client import ClientOptions
        _httpx = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
        opts = ClientOptions(
            postgrest_client_timeout=30,
            storage_client_timeout=30,
            httpx_client=_httpx,
        )
        supabase: SupabaseClient = create_client(_sb_url, _sb_key, options=opts)
        logger.info("Supabase client initialized successfully (Timeout 30s).")
    else:
        supabase = None
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_KEY not set — using local auth fallback.")
except ImportError:
    supabase = None
    logger.warning("supabase-py not installed — using local auth fallback.")

def _get_uid(fallback_uid=None):
    uid = session.get('supabase_uid') or session.get('user_id')
    if not uid and fallback_uid:
        logger.info(f"Using fallback UID: {fallback_uid}")
        return fallback_uid
    return uid

def _is_valid_uuid(uid):
    """Kiểm tra uid có phải UUID hợp lệ (Supabase) hay không."""
    import re
    return bool(uid and re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', str(uid), re.I))

def _require_login(fallback_uid=None):
    """Trả về (uid, None) nếu OK, hoặc (None, error_response) nếu chưa login."""
    uid = _get_uid(fallback_uid)
    if not uid:
        return None, (jsonify({"error": "Chưa đăng nhập"}), 401)
    return uid, None

def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ----------------------------------------------------------------
# Global Services (RAG, FSRS, Video)
# ----------------------------------------------------------------
from modules.RAG.fsrs_logic import FSRS
fsrs = FSRS()

class Services:
    rag_system = None
    video_handler = None

def get_rag_system():
    if Services.rag_system is None:
        try:
            from modules.RAG.rag_system import RAGSystem
            Services.rag_system = RAGSystem()
        except Exception as e:
            logger.error(f"Failed to load RAGSystem: {e}")
            raise e
    return Services.rag_system

def get_video_handler():
    if Services.video_handler is None:
        try:
            from modules.video.video_handler import VideoHandler
            rag = get_rag_system()
            Services.video_handler = VideoHandler(model_size="base", cost_logger=rag.log_cost)
        except Exception as e:
            logger.error(f"Failed to load VideoHandler: {e}")
            raise e
    return Services.video_handler

def cleanup_local_assets():
    """Xóa các file audio và pdf tạm thời trong thư mục dự án."""
    try:
        count = 0
        for filename in os.listdir(current_dir):
            if (filename.startswith("audio_") and filename.endswith(".mp3")) or \
               (filename.startswith("card_highlight_") and filename.endswith(".pdf")) or \
               (filename.startswith("card_context_") and filename.endswith(".txt")) or \
               filename == "highlighted_context.pdf":
                file_path = os.path.join(current_dir, filename)
                try:
                    os.remove(file_path)
                    count += 1
                except Exception:
                    pass
        if count > 0:
            logger.info(f"🧹 Đã dọn dẹp {count} file tài nguyên tạm thời từ bộ thẻ trước.")
    except Exception as e:
        logger.error(f"Lỗi khi dọn dẹp file tạm: {e}")
