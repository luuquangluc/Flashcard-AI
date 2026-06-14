import os
import sys
import tempfile
import json
import logging
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file, Response, stream_with_context
from flask_cors import CORS
import requests
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from fsrs_logic import FSRS
fsrs = FSRS()

try:
    from rag_system import RAGSystem
except ImportError as e:
    logger.error(f"Failed to import RAGSystem from rag_system.py: {e}")
    sys.exit(1)

app = Flask(__name__, static_folder='frontend')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'rag_flashcard_secret_key_123')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
CORS(app, supports_credentials=True)

# ----------------------------------------------------------------
# Supabase client (optional — graceful fallback if not configured)
# ----------------------------------------------------------------
try:
    from supabase import create_client, Client as SupabaseClient
    _sb_url = os.environ.get('SUPABASE_URL', '')
    _sb_key = os.environ.get('SUPABASE_SERVICE_KEY', '') or os.environ.get('SUPABASE_ANON_KEY', '')
    if _sb_url and _sb_key:
        supabase: SupabaseClient = create_client(_sb_url, _sb_key)
        logger.info("Supabase client initialized successfully.")
    else:
        supabase = None
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_KEY not set — using local auth fallback.")
except ImportError:
    supabase = None
    logger.warning("supabase-py not installed — using local auth fallback. Run: pip install supabase")

# Global RAG and Video Handler Instances
rag_system = None
video_handler = None

@app.route('/')
def index():
    response = send_from_directory(app.static_folder, 'index.html')
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@app.route('/<path:path>')
def static_proxy(path):
    response = send_from_directory(app.static_folder, path)
    # Ensure UTF-8 charset for text-based files (HTML, JS, CSS)
    if path.endswith(('.html', '.js', '.css')):
        ct = response.headers.get('Content-Type', '')
        if 'charset' not in ct:
            if path.endswith('.html'):
                response.headers['Content-Type'] = 'text/html; charset=utf-8'
            elif path.endswith('.js'):
                response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
            elif path.endswith('.css'):
                response.headers['Content-Type'] = 'text/css; charset=utf-8'
    return response

# --- Authentication API ---
# Local fallback users (used when Supabase is not configured)
USERS = {
    "admin": {"password": hashlib.sha256("admin123".encode()).hexdigest(), "role": "admin", "name": "System Administrator"},
    "user":  {"password": hashlib.sha256("user123".encode()).hexdigest(),  "role": "user",  "name": "Student User"}
}

def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

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

@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user. Uses Supabase if configured, otherwise stores in local dict."""
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    # Basic validation
    if len(username) < 3:
        return jsonify({"success": False, "error": "Tên tài khoản phải có ít nhất 3 ký tự"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Mật khẩu phải có ít nhất 6 ký tự"}), 400

    # --- Supabase path ---
    if supabase:
        try:
            # Supabase requires email; we derive a fake email from username
            fake_email = f"{username}@flashcardai.app"
            resp = supabase.auth.sign_up({
                "email": fake_email,
                "password": password,
                "options": {"data": {"username": username, "role": "user"}}
            })
            if resp.user:
                logger.info(f"Supabase: new user registered — {username}")
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Không thể tạo tài khoản"}), 400
        except Exception as e:
            err_str = str(e)
            logger.error(f"Supabase register error: {err_str}")
            if 'already registered' in err_str or 'already exists' in err_str:
                return jsonify({"success": False, "error": "Tên tài khoản đã tồn tại"}), 409
            return jsonify({"success": False, "error": "Lỗi đăng ký. Vui lòng thử lại."}), 500

    # --- Local fallback path ---
    if username in USERS:
        return jsonify({"success": False, "error": "Tên tài khoản đã tồn tại"}), 409

    USERS[username] = {
        "password": _hash_pw(password),
        "role": "user",
        "name": username.capitalize()
    }
    logger.info(f"Local: new user registered — {username}")
    return jsonify({"success": True})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    # --- Supabase path ---
    if supabase:
        try:
            fake_email = f"{username}@flashcardai.app"
            resp = supabase.auth.sign_in_with_password({
                "email": fake_email,
                "password": password
            })
            if resp.user:
                user_meta = resp.user.user_metadata or {}
                role = user_meta.get('role', 'user')
                name = user_meta.get('username', username).capitalize()
                from flask import session
                session['user_id'] = username
                session['supabase_uid'] = str(resp.user.id)  # UUID từ Supabase
                session['role'] = role
                session['name'] = name
                return jsonify({"success": True, "role": role, "name": name})
        except Exception as e:
            logger.warning(f"Supabase login failed for {username}: {e}")
            # Fall through to local auth

    # --- Local fallback path ---
    user = USERS.get(username)
    if user and user['password'] == _hash_pw(password):
        from flask import session
        session['user_id'] = username
        session['role'] = user['role']
        session['name'] = user['name']
        return jsonify({"success": True, "role": user['role'], "name": user['name']})

    return jsonify({"success": False, "error": "Sai tài khoản hoặc mật khẩu"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    from flask import session
    session.clear()
    return jsonify({"success": True})

@app.route('/api/me', methods=['GET'])
def get_me():
    from flask import session
    if 'user_id' in session:
        return jsonify({
            "logged_in": True, 
            "username": session['user_id'],
            "user_id": session.get('supabase_uid', session['user_id']),
            "role": session['role'], 
            "name": session['name']
        })
    return jsonify({"logged_in": False})

# ----------------------------------------------------------------
# Helper: lấy user_id từ session (Supabase UID hoặc username)
# ----------------------------------------------------------------
def _get_uid(fallback_uid=None):
    from flask import session
    uid = session.get('supabase_uid') or session.get('user_id')
    if not uid and fallback_uid:
        logger.info(f"Using fallback UID: {fallback_uid}")
        return fallback_uid
    return uid

def _require_login(fallback_uid=None):
    """Trả về (uid, None) nếu OK, hoặc (None, error_response) nếu chưa login."""
    uid = _get_uid(fallback_uid)
    if not uid:
        return None, (jsonify({"error": "Chưa đăng nhập"}), 401)
    return uid, None

# ================================================================
# LIBRARY API — Bộ thẻ per-user
# ================================================================

@app.route('/api/library', methods=['GET'])
def library_get():
    uid, err = _require_login()
    if err: return err

    if supabase:
        try:
            resp = supabase.table('flashcard_sets') \
                .select('id, title, cards, card_count, created_at') \
                .eq('user_id', uid) \
                .order('created_at', desc=True) \
                .execute()
            # Đảm bảo field 'name' tồn tại cho Frontend (map từ 'title' trong DB)
            data_list = resp.data if resp.data else []
            formatted_sets = [{**s, "name": s.get("title")} for s in data_list]
            return jsonify({"success": True, "sets": formatted_sets})
        except Exception as e:
            logger.error(f"library_get Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    # Local fallback (in-memory — không persistent qua restart)
    return jsonify({"success": True, "sets": []})


import mimetypes
import os

@app.route('/api/library', methods=['POST'])
def library_save():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    # Chấp nhận cả 'name' hoặc 'title' từ Frontend
    title = data.get('name') or data.get('title') or 'Bộ thẻ không tên'
    cards = data.get('cards', [])

    if not cards:
        return jsonify({"error": "Không có thẻ nào để lưu"}), 400

    if supabase:
        try:
            # Tự động upload file PDF và Audio của từng thẻ lên Supabase Storage
            bucket_name = 'documents'
            for card in cards:
                card_id = card.get('id')
                if not card_id: continue
                
                # Upload PDF
                pdf_file = f"card_highlight_{card_id}.pdf"
                pdf_path = os.path.join(current_dir, pdf_file)
                if os.path.exists(pdf_path):
                    try:
                        with open(pdf_path, 'rb') as f:
                            supabase.storage.from_(bucket_name).upload(
                                file=f.read(),
                                path=f"{uid}/{pdf_file}",
                                file_options={"content-type": "application/pdf", "upsert": "true"}
                            )
                        # Lưu lại URL vào card object
                        public_url = supabase.storage.from_(bucket_name).get_public_url(f"{uid}/{pdf_file}")
                        card['pdf_url'] = public_url
                    except Exception as e:
                        logger.error(f"Failed to upload PDF {pdf_file}: {e}")
                
                # Upload Audio
                audio_file = f"audio_{card_id}.mp3"
                audio_path = os.path.join(current_dir, audio_file)
                if os.path.exists(audio_path):
                    try:
                        with open(audio_path, 'rb') as f:
                            supabase.storage.from_(bucket_name).upload(
                                file=f.read(),
                                path=f"{uid}/{audio_file}",
                                file_options={"content-type": "audio/mpeg", "upsert": "true"}
                            )
                        public_url = supabase.storage.from_(bucket_name).get_public_url(f"{uid}/{audio_file}")
                        card['audio_url'] = public_url
                    except Exception as e:
                        logger.error(f"Failed to upload Audio {audio_file}: {e}")

            # Lưu vào database sau khi đã đính kèm URL
            resp = supabase.table('flashcard_sets').insert({
                'user_id': uid,
                'title': title,
                'cards': cards
            }).execute()
            return jsonify({"success": True, "id": resp.data[0]['id'] if resp.data else None})
        except Exception as e:
            logger.error(f"library_save Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "id": None})


@app.route('/api/library/<set_id>', methods=['DELETE'])
def library_delete(set_id):
    uid, err = _require_login()
    if err: return err

    if supabase:
        try:
            supabase.table('flashcard_sets') \
                .delete() \
                .eq('id', set_id) \
                .eq('user_id', uid) \
                .execute()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"library_delete Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True})


# ================================================================
# DOCUMENTS API — PDF files per-user
# ================================================================

@app.route('/api/documents', methods=['GET'])
def documents_get():
    uid, err = _require_login()
    if err: return err

    if supabase:
        try:
            resp = supabase.table('user_documents') \
                .select('*') \
                .eq('user_id', uid) \
                .order('created_at', desc=True) \
                .execute()
            return jsonify({"success": True, "documents": resp.data or []})
        except Exception as e:
            logger.error(f"documents_get Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "documents": []})

@app.route('/api/documents', methods=['POST'])
def document_save():
    data = request.json or {}
    fallback_uid = data.get('user_id')
    uid, err = _require_login(fallback_uid)
    if err: return err

    data = request.json or {}
    file_name = data.get('file_name')
    file_url = data.get('file_url')
    file_size = data.get('file_size', 0)

    if not file_name or not file_url:
        return jsonify({"error": "Thiếu thông tin tài liệu"}), 400

    if supabase:
        try:
            resp = supabase.table('user_documents').insert({
                'user_id': uid,
                'file_name': file_name,
                'file_url': file_url,
                'file_size': file_size
            }).execute()
            return jsonify({"success": True, "id": resp.data[0]['id'] if resp.data else None})
        except Exception as e:
            logger.error(f"document_save Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True})

@app.route('/api/documents/reuse', methods=['POST'])
def document_reuse():
    global rag_system
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    doc_url = data.get('url')
    
    if not doc_url:
        return jsonify({"error": "No document URL provided"}), 400

    try:
        # Download file from Supabase URL
        resp = requests.get(doc_url)
        if resp.status_code != 200:
            return jsonify({"error": "Failed to download document from storage"}), 500
        
        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        with open(temp_path, 'wb') as f:
            f.write(resp.content)
        
        # Cleanup old local assets
        cleanup_local_assets()
        
        # Initialize RAG
        if rag_system is None:
            rag_system = RAGSystem()
            rag_system.supabase = supabase # Data Flywheel support
        
        success = rag_system.process_pdf(temp_path)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Document loaded for reuse", 
                "chunks": len(rag_system.chunks),
                "is_structure_good": rag_system.is_structure_good
            })
        else:
            return jsonify({"error": "Failed to process document"}), 500
            
    except Exception as e:
        logger.error(f"Error in document reuse: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def document_delete(doc_id):
    uid, err = _require_login()
    if err: return err

    try:
        # 1. Lấy thông tin tài liệu để lấy URL file
        doc_res = supabase.table('user_documents').select('*').eq('id', doc_id).eq('user_id', uid).execute()
        if not doc_res.data:
            return jsonify({"error": "Document not found"}), 404
        
        file_url = doc_res.data[0].get('file_url')
        
        # 2. Xóa khỏi Database
        supabase.table('user_documents').delete().eq('id', doc_id).eq('user_id', uid).execute()
        
        # 3. Xóa khỏi Storage (nếu file nằm trong bucket documents)
        if "documents/" in file_url:
            # Trích xuất path từ URL: user_id/filename
            storage_path = file_url.split("documents/")[1]
            try:
                supabase.storage.from_('documents').remove([storage_path])
                logger.info(f"Deleted storage file from Supabase: {storage_path}")
            except Exception as se:
                logger.warning(f"Storage deletion warning: {se}")

        return jsonify({"success": True, "message": "Document deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return jsonify({"error": str(e)}), 500


# ================================================================
# GAME STATS API — XP, Level, Streak per-user
# ================================================================

@app.route('/api/stats', methods=['GET'])
def stats_get():
    uid, err = _require_login()
    if err: return err

    if supabase:
        try:
            resp = supabase.table('game_stats') \
                .select('*') \
                .eq('user_id', uid) \
                .execute()
            if resp.data:
                return jsonify({"success": True, "stats": resp.data[0]})
            else:
                # User chưa có stats row → trả về defaults
                return jsonify({"success": True, "stats": {
                    "xp": 0, "level": 1, "streak": 0, "last_date": None
                }})
        except Exception as e:
            logger.error(f"stats_get Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "stats": {"xp": 0, "level": 1, "streak": 0, "last_date": None}})


@app.route('/api/stats', methods=['POST'])
def stats_save():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    payload = {
        'user_id': uid,
        'xp':      data.get('xp', 0),
        'level':   data.get('level', 1),
        'streak':  data.get('streak', 0),
        'last_date': data.get('last_date'),
        'updated_at': 'now()'
    }

    if supabase:
        try:
            supabase.table('game_stats') \
                .upsert(payload, on_conflict='user_id') \
                .execute()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"stats_save Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True})


# ================================================================
# ANALYTICS API — Lịch sử tạo thẻ per-user
# ================================================================

@app.route('/api/analytics', methods=['GET'])
def analytics_get():
    uid, err = _require_login()
    if err: return err

    if supabase:
        try:
            resp = supabase.table('flashcard_sessions') \
                .select('*') \
                .eq('user_id', uid) \
                .order('created_at', desc=True) \
                .limit(50) \
                .execute()
            return jsonify({"success": True, "history": resp.data})
        except Exception as e:
            logger.error(f"analytics_get Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "history": []})


@app.route('/api/analytics', methods=['POST'])
def analytics_log():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    if supabase:
        try:
            supabase.table('flashcard_sessions').insert({
                'user_id':     uid,
                'query':       data.get('query', ''),
                'mode':        data.get('mode', 'content'),
                'card_count':  data.get('cardCount', 0),
                'level_stats': data.get('levelStats', {}),
                'tokens':      data.get('tokens', 0),
                'is_rag':      data.get('isRAG', True),
            }).execute()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"analytics_log Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True})



# ================================================================
# FSRS LOGIC & API
# ================================================================

def update_card_fsrs(card, quality):
    """
    Cập nhật thẻ theo thuật toán FSRS v4.
    quality: 1: Again, 2: Hard, 3: Good, 4: Easy
    """
    # Lấy các chỉ số FSRS cũ hoặc khởi tạo
    stability = card.get('stability', 0)
    difficulty = card.get('difficulty', 5.0)
    reps = card.get('reps', 0)
    
    # Tính toán số ngày đã trôi qua kể từ lần review cuối
    last_review_str = card.get('last_review')
    if last_review_str:
        last_review = datetime.fromisoformat(last_review_str.replace('Z', '+00:00'))
        elapsed_days = (datetime.now(last_review.tzinfo) - last_review).days
        elapsed_days = max(0, elapsed_days)
    else:
        elapsed_days = 0

    if reps == 0:
        # Lần đầu tiên học
        new_stability = fsrs.init_stability(quality)
        new_difficulty = fsrs.init_difficulty(quality)
    else:
        # Các lần ôn tập tiếp theo
        new_stability, new_difficulty = fsrs.step(quality, stability, difficulty, elapsed_days)

    # Tính ngày ôn tập tiếp theo từ FSRS stability
    next_days = fsrs.next_interval(new_stability)
    next_review = datetime.now() + timedelta(days=next_days)
    
    # Cập nhật thông tin thẻ — chỉ dùng FSRS fields
    card['stability'] = new_stability
    card['difficulty'] = new_difficulty
    card['reps'] = reps + 1
    card['last_review'] = datetime.now().isoformat()
    card['next_review'] = next_review.isoformat()
    
    return card

@app.route('/api/review/submit', methods=['POST'])
def review_card():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    set_id = data.get('set_id')
    card_id = data.get('card_id')
    quality = data.get('quality')

    if set_id is None or card_id is None or quality is None:
        return jsonify({"error": "Thiếu thông tin review"}), 400

    if not supabase:
        return jsonify({"error": "Cần kết nối Supabase để lưu tiến trình"}), 500

    try:
        # 1. Lấy bộ thẻ từ DB
        resp = supabase.table('flashcard_sets').select('*').eq('id', set_id).eq('user_id', uid).execute()
        if not resp.data:
            return jsonify({"error": "Không tìm thấy bộ thẻ"}), 404
        
        flashcard_set = resp.data[0]
        cards = flashcard_set.get('cards', [])
        
        # 2. Tìm thẻ cụ thể và tính toán FSRS
        card_found = False
        new_int, new_due_date = 0, None
        
        # Mapping quality từ UI mới (1-4) hoặc fallback từ UI cũ (0, 3, 4, 5)
        if quality in [1, 2, 3, 4]:
            fsrs_quality = quality
        else:
            # 0->Again, 3->Hard, 4->Good, 5->Easy
            mapping = {0: 1, 3: 2, 4: 3, 5: 4}
            fsrs_quality = mapping.get(quality, 3)

        for card in cards:
            if card.get('id') == card_id:
                srs = card.get('srs', {})
                
                # Lấy các chỉ số FSRS cũ
                stability = srs.get('stability', 0)
                difficulty = srs.get('difficulty', 5.0)
                reps = srs.get('reps', 0)
                
                last_review_str = srs.get('last_review')
                if last_review_str:
                    try:
                        last_review = datetime.fromisoformat(last_review_str.replace('Z', '+00:00'))
                        elapsed_days = (datetime.now(last_review.tzinfo) - last_review).days
                        elapsed_days = max(0, elapsed_days)
                    except:
                        elapsed_days = 0
                else:
                    elapsed_days = 0

                if reps == 0:
                    new_stability = fsrs.init_stability(fsrs_quality)
                    new_difficulty = fsrs.init_difficulty(fsrs_quality)
                else:
                    new_stability, new_difficulty = fsrs.step(fsrs_quality, stability, difficulty, elapsed_days)

                next_days = fsrs.next_interval(new_stability)
                new_due_date = (datetime.now() + timedelta(days=next_days)).isoformat()
                
                card['srs'] = {
                    'stability': new_stability,
                    'difficulty': new_difficulty,
                    'reps': reps + 1,
                    'last_review': datetime.now().isoformat(),
                    'due_date': new_due_date
                }
                card_found = True
                break
        
        if not card_found:
            return jsonify({"error": "Không tìm thấy thẻ trong bộ"}), 404

        # 3. Lưu ngược lại vào database
        supabase.table('flashcard_sets').update({'cards': cards}).eq('id', set_id).execute()
        
        return jsonify({
            "success": True, 
            "next_review": new_due_date,
            "stability": new_stability
        })
    except Exception as e:
        logger.error(f"Review error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/review/batch', methods=['POST'])
def review_batch():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    set_id = data.get('set_id')
    reviews = data.get('reviews', []) # List of {card_id, quality}

    if not set_id or not reviews:
        return jsonify({"error": "Thiếu thông tin batch review"}), 400

    if not supabase:
        return jsonify({"error": "Cần kết nối Supabase"}), 500

    try:
        # 1. Lấy bộ thẻ
        resp = supabase.table('flashcard_sets').select('*').eq('id', set_id).eq('user_id', uid).execute()
        if not resp.data:
            return jsonify({"error": "Không tìm thấy bộ thẻ"}), 404
        
        flashcard_set = resp.data[0]
        cards = flashcard_set.get('cards', [])
        
        # 2. Tạo bản đồ review để tra cứu nhanh
        review_map = {r['card_id']: r['quality'] for r in reviews}
        
        updated_count = 0
        for card in cards:
            c_id = card.get('id')
            if c_id in review_map:
                quality = review_map[c_id]
                srs = card.get('srs', {})
                
                # Mapping quality từ UI mới (1-4) hoặc fallback từ UI cũ (0, 3, 4, 5)
                if quality in [1, 2, 3, 4]:
                    fsrs_quality = quality
                else:
                    mapping = {0: 1, 3: 2, 4: 3, 5: 4}
                    fsrs_quality = mapping.get(quality, 3)

                # Lấy các chỉ số FSRS cũ
                stability = srs.get('stability', 0)
                difficulty = srs.get('difficulty', 5.0)
                reps = srs.get('reps', 0)
                
                last_review_str = srs.get('last_review')
                if last_review_str:
                    try:
                        last_review = datetime.fromisoformat(last_review_str.replace('Z', '+00:00'))
                        elapsed_days = (datetime.now(last_review.tzinfo) - last_review).days
                        elapsed_days = max(0, elapsed_days)
                    except:
                        elapsed_days = 0
                else:
                    elapsed_days = 0

                if reps == 0:
                    new_stability = fsrs.init_stability(fsrs_quality)
                    new_difficulty = fsrs.init_difficulty(fsrs_quality)
                else:
                    new_stability, new_difficulty = fsrs.step(fsrs_quality, stability, difficulty, elapsed_days)

                next_days = fsrs.next_interval(new_stability)
                new_due_date = (datetime.now() + timedelta(days=next_days)).isoformat()
                
                card['srs'] = {
                    'stability': new_stability,
                    'difficulty': new_difficulty,
                    'reps': reps + 1,
                    'last_review': datetime.now().isoformat(),
                    'due_date': new_due_date
                }
                updated_count += 1
        
        # 3. Lưu
        supabase.table('flashcard_sets').update({'cards': cards}).eq('id', set_id).execute()
        
        return jsonify({"success": True, "updated": updated_count})
    except Exception as e:
        logger.error(f"Batch review error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/flashcard/update', methods=['POST'])
def update_flashcard():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    set_id = data.get('set_id')
    card_id = data.get('card_id')
    new_question = data.get('question')
    new_answer = data.get('answer')
    new_note = data.get('note', '')

    if not all([set_id, card_id, new_question, new_answer]):
        return jsonify({"error": "Thiếu dữ liệu cập nhật"}), 400

    try:
        resp = supabase.table('flashcard_sets').select('*').eq('id', set_id).eq('user_id', uid).execute()
        if not resp.data:
            return jsonify({"error": "Không tìm thấy bộ thẻ"}), 404
        
        flashcard_set = resp.data[0]
        cards = flashcard_set.get('cards', [])
        
        updated = False
        original_card_data = None
        card_level = "AI Generated"
        for card in cards:
            if card.get('id') == card_id:
                original_card_data = {
                    'question': card.get('question'),
                    'answer': card.get('answer'),
                    'note': card.get('note', '')
                }
                card['question'] = new_question
                card['answer'] = new_answer
                card['note'] = new_note
                card_level = card.get('level', "AI Generated")
                updated = True
                break
        
        if not updated:
            return jsonify({"error": "Không tìm thấy thẻ trong bộ"}), 404
            
        # --- DATA FLYWHEEL: Lưu feedback EDIT ---
        try:
            # Tự động nhận diện mode dựa trên level của thẻ
            mode = "vocabulary" if card_level == "Từ vựng" else "content"
            
            doc_name = rag_system.doc_name if rag_system else None
            
            supabase.table('ai_feedback').insert({
                'user_id': uid,
                'original_card': original_card_data,
                'corrected_card': {'question': new_question, 'answer': new_answer, 'note': new_note},
                'feedback_type': 'EDIT',
                'document_name': doc_name,
                'mode': mode
            }).execute()
        except Exception as fe:
            logger.warning(f"Failed to log feedback: {fe}")

        supabase.table('flashcard_sets').update({'cards': cards}).eq('id', set_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/flashcard/delete', methods=['POST'])
def delete_flashcard():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    set_id = data.get('set_id')
    card_id = data.get('card_id')

    if not set_id or not card_id:
        return jsonify({"error": "Thiếu thông tin xóa"}), 400

    try:
        resp = supabase.table('flashcard_sets').select('*').eq('id', set_id).eq('user_id', uid).execute()
        if not resp.data:
            return jsonify({"error": "Không tìm thấy bộ thẻ"}), 404
        
        flashcard_set = resp.data[0]
        cards = flashcard_set.get('cards', [])
        
        new_cards = [c for c in cards if c.get('id') != card_id]
        
        if len(new_cards) == len(cards):
            return jsonify({"error": "Không tìm thấy thẻ để xóa"}), 404
            
        # --- DATA FLYWHEEL: Lưu feedback DELETE ---
        try:
            deleted_card = next((c for c in cards if c.get('id') == card_id), None)
            if deleted_card:
                # Tự động nhận diện mode
                card_level = deleted_card.get('level', '')
                mode = "vocabulary" if card_level == "Từ vựng" else "content"
                
                doc_name = rag_system.doc_name if rag_system else None
                supabase.table('ai_feedback').insert({
                    'user_id': uid,
                    'original_card': {'question': deleted_card.get('question'), 'answer': deleted_card.get('answer')},
                    'feedback_type': 'DELETE',
                    'document_name': doc_name,
                    'mode': mode
                }).execute()
        except Exception as fe:
            logger.warning(f"Failed to log delete feedback: {fe}")

        supabase.table('flashcard_sets').update({'cards': new_cards}).eq('id', set_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/feedback/log', methods=['POST'])
def log_ai_feedback():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    # Hỗ trợ cả gửi 1 object hoặc 1 list các objects
    events = data.get('events', [])
    if not events and 'feedback_type' in data:
        events = [data]

    if not events:
        return jsonify({"success": True, "message": "No events to log"})

    try:
        feedback_to_insert = []
        for ev in events:
            # Ưu tiên lấy doc_name từ Frontend gửi lên, nếu không có mới lấy từ rag_system
            doc_name = ev.get('document_name') or (rag_system.doc_name if rag_system else None)
            
            feedback_to_insert.append({
                'user_id': uid,
                'original_card': ev.get('original_card'),
                'corrected_card': ev.get('corrected_card'),
                'feedback_type': ev.get('feedback_type'),
                'document_name': doc_name,
                'mode': ev.get('mode', 'content')
            })
        
        if feedback_to_insert:
            supabase.table('ai_feedback').insert(feedback_to_insert).execute()
            
        return jsonify({"success": True, "count": len(feedback_to_insert)})
    except Exception as e:
        logger.error(f"Feedback log error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear_rag', methods=['POST'])
def clear_rag():
    global rag_system
    if rag_system:
        rag_system.chunks = []
        rag_system.current_pdf_path = None
    cleanup_local_assets()
    logger.info("RAG state cleared manually by user.")
    return jsonify({"success": True, "message": "RAG state cleared"})


@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    global rag_system
    
    # Check for user_id in form data as fallback
    fallback_uid = request.form.get('user_id')
    uid, err = _require_login(fallback_uid)
    # Note: we don't strictly return err here to allow anonymous processing, 
    # but we now have a better chance of getting uid.
    
    if 'file' not in request.files:
        logger.warning("Upload failed: No 'file' boundary in request.files")
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("Upload failed: Filename is empty")
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        logger.warning(f"Upload failed: Invalid file type ({file.filename})")
        return jsonify({"error": "Only PDF files are supported"}), 400

    try:
        # Cleanup old temporary assets before processing a new file
        cleanup_local_assets()
        
        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        file_content = file.read()
        file_size = len(file_content)
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        
        logger.info(f"Received file: {file.filename}, saved to {temp_path}")
        
        # --- Supabase Storage ONLY (No auto-save to DB) ---
        file_url = None
        logger.info(f"Checking for Supabase upload: supabase={'OK' if supabase else 'None'}, uid={uid}")
        if supabase and uid:
            try:
                bucket_name = 'documents'
                safe_filename = "".join([c if c.isalnum() or c in "._-" else "_" for c in file.filename])
                storage_path = f"{uid}/{safe_filename}"
                
                # Upload to Supabase Storage
                supabase.storage.from_(bucket_name).upload(
                    file=file_content,
                    path=storage_path,
                    file_options={"content-type": "application/pdf", "upsert": "true"}
                )
                
                file_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
                logger.info(f"File {file.filename} is in Storage: {file_url}. Ready for manual save.")
            except Exception as sb_err:
                logger.error(f"Supabase storage upload error: {sb_err}")

        # Initialize RAG System
        if rag_system is None:
            try:
                rag_system = RAGSystem()
            except Exception as init_err:
                logger.error(f"Failed to init RAGSystem: {init_err}")
                return jsonify({"error": f"Lỗi khởi tạo hệ thống RAG: {str(init_err)}"}), 500
        
        # Kích hoạt Data Flywheel
        if supabase:
            rag_system.supabase = supabase
        
        rag_system.doc_name = file.filename
        
        # Process PDF (This might take long for 77 pages)
        try:
            success = rag_system.process_pdf(temp_path)
        except Exception as proc_err:
            logger.error(f"Error in process_pdf: {proc_err}")
            traceback.print_exc()
            return jsonify({"error": f"Lỗi xử lý tài liệu: {str(proc_err)}"}), 500
        
        if success:
            return jsonify({
                "success": True,
                "message": "File processed successfully", 
                "chunks": len(rag_system.chunks),
                "is_structure_good": rag_system.is_structure_good,
                "file_url": file_url,
                "file_size": file_size,
                "uid": uid
            })
        else:
            return jsonify({"error": "Không thể xử lý file PDF này (Có thể file bị khóa hoặc lỗi định dạng)"}), 500
            
    except Exception as e:
        logger.error(f"Critical error in upload: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500

@app.route('/api/query', methods=['POST'])
def query_rag():
    global rag_system
    uid, err = _require_login()
    if err: return err
    
    if rag_system is None:
        try:
            rag_system = RAGSystem()
        except Exception as e:
            return jsonify({"error": f"Failed to initialize RAG system: {str(e)}"}), 500
    
    # Kích hoạt Data Flywheel
    if supabase:
        rag_system.supabase = supabase
    
    data = request.json
    user_query = data.get('query', '').strip()
    num_cards = data.get('num_cards', 3)
    page_range = data.get('page_range', '').strip()
    user_desire = data.get('user_desire', '').strip()
    
    # Cleanup old temporary assets before generating new ones
    cleanup_local_assets()
    
    # Lấy tên tài liệu từ request để đồng bộ Data Flywheel
    file_name = data.get('fileName')
    if rag_system and file_name:
        rag_system.doc_name = file_name
    
    if not user_query and not page_range:
        return jsonify({"error": "Vui lòng nhập chủ đề hoặc dải trang"}), 400
    
    try:
        logger.info(f"Querying RAG (Streaming): {user_query} (requested {num_cards} cards, range: {page_range}, desire: {user_desire})")
        
        def generate():
            # Helper to format SSE data
            def sse_message(data):
                return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            # Callback for the RAG system to report status
            def status_callback(msg):
                # Using a wrapper to yield from the callback is tricky in non-async python, 
                # but in Flask's stream context we can just use a queue or directly yield from the generator.
                # Here we'll use a local list to collect messages if needed, but the best way 
                # is to pass the generator's send/yield mechanism.
                pass 
            
            # Since rag_system.query is synchronous, we'll try a simpler approach where 
            # we wrap the print/log logic to be accessible. 
            # Actually, we can use a custom logger that yields messages.
            
            messages = []
            def collect_status(msg):
                messages.append(msg)

            # We'll run the query and yield any messages that were caught
            # To make it truly "real-time" without extra threads, we'll update RAG to 
            # accept a callback that we can iterate. 
            
            # Revised approach: Use a queue to capture messages from the synchronous RAG call
            from queue import Queue
            import threading

            q = Queue()
            def worker_status_callback(msg):
                q.put({"type": "status", "content": msg})

            def run_query():
                try:
                    if not rag_system.chunks:
                        if page_range:
                            worker_status_callback("❌ Lỗi: Bạn không thể chọn dải trang khi chưa tải tài liệu PDF.")
                            q.put({"type": "error", "content": "Vui lòng tải tài liệu lên trước khi sử dụng tính năng chọn dải trang."})
                            q.put(None)
                            return
                            
                        # No PDF processed, use direct generation
                        res_json = rag_system.generate_no_rag(
                            user_query, 
                            num_flashcard=num_cards, 
                            user_desire=user_desire,
                            status_callback=worker_status_callback,
                            user_id=uid
                        )
                        context_text = "Generated from AI general knowledge"
                    else:
                        # PDF processed, use normal RAG
                        res_json, context_text = rag_system.query(
                            user_query, 
                            num_flashcard=num_cards, 
                            page_range=page_range, 
                            status_callback=worker_status_callback,
                            user_desire=user_desire,
                            user_id=uid
                        )
                    
                    data_out = json.loads(res_json)
                    q.put({"type": "result", "flashcards": data_out.get("flashcards", []), "context": context_text[:500]})
                except Exception as e:
                    q.put({"type": "error", "content": str(e)})
                finally:
                    q.put(None) # Signal end

            thread = threading.Thread(target=run_query)
            thread.start()

            while True:
                msg = q.get()
                if msg is None: break
                yield sse_message(msg)
            
            thread.join()

        return Response(stream_with_context(generate()), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error in query: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pdf')
def get_pdf():
    # Served highlighted PDF (can be card_highlight_X.pdf or highlighted_context.pdf)
    filename = request.args.get('filename', 'highlighted_context.pdf')
    pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)
    else:
        # Fallback to general highlight if requested card highlight doesn't exist
        fallback_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highlighted_context.pdf")
        if os.path.exists(fallback_path):
            return send_file(fallback_path, mimetype='application/pdf', as_attachment=False)
        return jsonify({"error": "PDF file not found"}), 404

@app.route('/api/audio')
def get_audio():
    filename = request.args.get('filename')
    if not filename or not filename.endswith('.mp3'):
        return jsonify({"error": "Invalid audio file"}), 400
    audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if os.path.exists(audio_path):
        return send_file(audio_path, mimetype='audio/mpeg')
    return jsonify({"error": "Audio file not found"}), 404

@app.route('/api/export_anki', methods=['POST'])
def export_anki():
    try:
        import genanki
        import random
        import uuid
        import httpx
        
        data = request.json or {}
        cards = data.get('cards', [])
        deck_name = data.get('deck_name', 'Flashcard AI Deck')
        
        if not cards:
            return jsonify({"error": "No cards to export"}), 400

        model_id = random.randrange(1 << 30, 1 << 31)
        deck_id = random.randrange(1 << 30, 1 << 31)

        my_model = genanki.Model(
            model_id,
            'Flashcard AI Model',
            fields=[
                {'name': 'Question'},
                {'name': 'Answer'},
                {'name': 'Audio'},
            ],
            templates=[
                {
                    'name': 'Card 1',
                    'qfmt': '{{Question}}<br>{{Audio}}',
                    'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
                },
            ],
            css='.card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; }'
        )

        my_deck = genanki.Deck(deck_id, deck_name)
        my_package = genanki.Package(my_deck)
        media_files = []

        temp_dir = tempfile.mkdtemp()

        for card in cards:
            q = (card.get('question') or '').replace('\n', '<br>')
            a = (card.get('answer') or '').replace('\n', '<br>')
            audio_field = ""
            
            audio_url = card.get('audio_url')
            local_audio = card.get('audio')
            audio_filename = None
            
            if audio_url:
                try:
                    resp = httpx.get(audio_url, timeout=10.0)
                    if resp.status_code == 200:
                        audio_filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
                        filepath = os.path.join(temp_dir, audio_filename)
                        with open(filepath, 'wb') as f:
                            f.write(resp.content)
                        media_files.append(filepath)
                        audio_field = f"[sound:{audio_filename}]"
                except Exception as e:
                    logger.error(f"Failed to download audio from {audio_url}: {e}")
            
            if not audio_filename and local_audio:
                local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), local_audio)
                if os.path.exists(local_path):
                    audio_filename = local_audio
                    media_files.append(local_path)
                    audio_field = f"[sound:{audio_filename}]"

            # Use level as tag
            tag = card.get('level', 'Flashcard').replace(' ', '_').replace(',', '')
            
            my_note = genanki.Note(
                model=my_model,
                fields=[q, a, audio_field],
                tags=[tag]
            )
            my_deck.add_note(my_note)

        my_package.media_files = media_files
        
        fd, temp_apkg_path = tempfile.mkstemp(suffix=".apkg")
        os.close(fd)
        
        my_package.write_to_file(temp_apkg_path)
        
        # Cleanup downloaded media files
        for mf in media_files:
            if mf.startswith(temp_dir):
                try: os.remove(mf)
                except: pass
        try: os.rmdir(temp_dir)
        except: pass

        return send_file(temp_apkg_path, as_attachment=True, download_name=f"{deck_name}.apkg", mimetype='application/octet-stream')
        
    except Exception as e:
        logger.error(f"Anki export error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/flashcard/chat', methods=['POST'])
def flashcard_chat():
    global rag_system
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    card_context = data.get('context', '')
    question = data.get('question', '')
    answer = data.get('answer', '')
    user_message = data.get('message', '')
    history = data.get('history', [])

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if rag_system is None:
        rag_system = RAGSystem()
    
    # Kích hoạt Data Flywheel
    if supabase:
        rag_system.supabase = supabase

    try:
        response = rag_system.chat_with_card(card_context, question, answer, user_message, history)
        return jsonify({"success": True, "response": response})
    except Exception as e:
        logger.error(f"Flashcard chat error: {e}")
        return jsonify({"error": str(e)}), 500


# ================================================================
# NOTIFICATIONS API — per-user
# ================================================================

@app.route('/api/notifications', methods=['GET'])
def notifications_get():
    uid, err = _require_login()
    if err: return err
    if supabase:
        try:
            resp = supabase.table('notifications') \
                .select('*') \
                .eq('user_id', uid) \
                .order('created_at', desc=True) \
                .limit(20) \
                .execute()
            return jsonify({"success": True, "notifications": resp.data})
        except Exception as e:
            logger.error(f"notifications_get error: {e}")
            return jsonify({"error": str(e)}), 500
    return jsonify({"success": True, "notifications": []})


@app.route('/api/notifications', methods=['POST'])
def notifications_save():
    uid, err = _require_login()
    if err: return err
    data = request.json or {}
    notifs = data.get('notifications', [])
    if not notifs:
        return jsonify({"success": True})
    if supabase:
        try:
            payloads = []
            for n in notifs:
                created = datetime.fromtimestamp(n['createdAt'] / 1000).isoformat() if 'createdAt' in n else datetime.utcnow().isoformat()
                payloads.append({
                    'id': n['id'],
                    'user_id': uid,
                    'title': n['title'],
                    'description': n['description'],
                    'type': n.get('type', 'info'),
                    'is_read': n.get('isRead', False),
                    'created_at': created
                })
            supabase.table('notifications').upsert(payloads).execute()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"notifications_save error: {e}")
            return jsonify({"error": str(e)}), 500
    return jsonify({"success": True})


@app.route('/api/notifications/<nid>/read', methods=['PUT'])
def notification_read(nid):
    uid, err = _require_login()
    if err: return err
    if supabase:
        try:
            supabase.table('notifications').update({'is_read': True}).eq('id', nid).eq('user_id', uid).execute()
        except Exception as e:
            logger.error(f"notification_read error: {e}")
    return jsonify({"success": True})


@app.route('/api/notifications/read_all', methods=['PUT'])
def notification_read_all():
    uid, err = _require_login()
    if err: return err
    if supabase:
        try:
            supabase.table('notifications').update({'is_read': True}).eq('user_id', uid).execute()
        except Exception as e:
            logger.error(f"notification_read_all error: {e}")
    return jsonify({"success": True})


@app.route('/api/notifications/<nid>', methods=['DELETE'])
def notification_delete(nid):
    uid, err = _require_login()
    if err: return err
    if supabase:
        try:
            supabase.table('notifications').delete().eq('id', nid).eq('user_id', uid).execute()
        except Exception as e:
            logger.error(f"notification_delete error: {e}")
    return jsonify({"success": True})


@app.route('/api/video/transcribe', methods=['POST'])
def video_transcribe():
    global rag_system, video_handler
    
    # Khởi tạo nếu chưa có
    if rag_system is None:
        try:
            from rag_system import RAGSystem
            rag_system = RAGSystem()
        except Exception as e:
            return jsonify({"error": f"Failed to initialize RAG system: {str(e)}"}), 500
            
    if video_handler is None:
        try:
            from video_handler import VideoHandler
            video_handler = VideoHandler(model_size="base", cost_logger=rag_system.log_cost)
        except Exception as e:
            return jsonify({"error": f"Failed to initialize Video Handler: {str(e)}"}), 500

    data = request.json
    video_url = data.get('url')
    if not video_url:
        return jsonify({"error": "Vui lòng cung cấp link video"}), 400

    try:
        logger.info(f"🎥 Đang bắt đầu xử lý video: {video_url}")
        
        # Sử dụng asyncio để chạy transcribe (vì nó là async)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        transcript, summary, title = loop.run_until_complete(video_handler.get_transcript(video_url))
        
        if not transcript:
            return jsonify({"error": "Không thể trích xuất nội dung từ video này"}), 500

        # Lưu transcript và summary vào file tạm để nạp vào RAG
        file_hash = hashlib.md5(video_url.encode()).hexdigest()
        temp_filename = f"video_{file_hash}.txt"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(f"# TIÊU ĐỀ: {title}\n")
            f.write(f"# LINK: {video_url}\n\n")
            f.write(f"## BẢN TÓM TẮT NỘI DUNG\n{summary}\n\n")
            f.write(f"## BẢN CHÉP LỜI CHI TIẾT\n{transcript}")

        # Nạp vào RAG
        logger.info(f"📑 Đang nạp transcript vào RAG: {title}")
        success = rag_system.process_document(temp_path)
        
        if success:
            # Gán tên tài liệu hiện tại để người dùng có thể đặt câu hỏi ngay
            rag_system.doc_name = title
            return jsonify({
                "success": True, 
                "title": title, 
                "transcript_preview": transcript[:200] + "...",
                "message": f"Đã nạp nội dung video '{title}' vào hệ thống RAG thành công."
            })
        else:
            return jsonify({"error": "Nạp transcript vào RAG thất bại"}), 500

    except Exception as e:
        logger.error(f"❌ Lỗi xử lý video: {traceback.format_exc()}")
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500

if __name__ == '__main__':
    # Ensure frontend directory exists
    frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend')
    if not os.path.exists(frontend_dir):
        os.makedirs(frontend_dir)
        
    logger.info("Starting Flask server on http://localhost:5000")
    # use_reloader=False: tắt auto-restart khi file thay đổi
    # (tránh torch/_dynamo tự reload giữa SSE stream → network error)
    app.run(debug=True, port=5000, use_reloader=False)

