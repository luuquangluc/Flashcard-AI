from flask import Blueprint, request, jsonify, session
import logging
from .dependencies import supabase, USERS, _hash_pw

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    if len(username) < 3:
        return jsonify({"success": False, "error": "Tên tài khoản phải có ít nhất 3 ký tự"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Mật khẩu phải có ít nhất 6 ký tự"}), 400

    if supabase:
        try:
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

    if username in USERS:
        return jsonify({"success": False, "error": "Tên tài khoản đã tồn tại"}), 409

    USERS[username] = {
        "password": _hash_pw(password),
        "role": "user",
        "name": username.capitalize()
    }
    logger.info(f"Local: new user registered — {username}")
    return jsonify({"success": True})


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')

    # Ưu tiên kiểm tra local USERS trước (đặc biệt cho admin)
    user = USERS.get(username)
    if user and user['password'] == _hash_pw(password):
        session['user_id'] = username
        session['role'] = user['role']
        session['name'] = user['name']
        return jsonify({"success": True, "role": user['role'], "name": user['name']})

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
                
                session['user_id'] = username
                session['supabase_uid'] = str(resp.user.id)
                session['role'] = role
                session['name'] = name
                return jsonify({"success": True, "role": role, "name": name})
        except Exception as e:
            logger.warning(f"Supabase login failed for {username}: {e}")

    return jsonify({"success": False, "error": "Sai tài khoản hoặc mật khẩu"}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})


@auth_bp.route('/me', methods=['GET'])
def get_me():
    if 'user_id' in session:
        return jsonify({
            "logged_in": True, 
            "username": session['user_id'],
            "user_id": session.get('supabase_uid', session['user_id']),
            "role": session['role'], 
            "name": session['name']
        })
    return jsonify({"logged_in": False})
