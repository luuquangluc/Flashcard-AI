from flask import Blueprint, request, jsonify
import logging
from .dependencies import _require_login, _is_valid_uuid, supabase

logger = logging.getLogger(__name__)

stats_bp = Blueprint('stats', __name__)

# ================================================================
# GAME STATS API — XP, Level, Streak per-user
# ================================================================

@stats_bp.route('/stats', methods=['GET'])
def stats_get():
    uid, err = _require_login()
    if err: return err

    if supabase and _is_valid_uuid(uid):
        try:
            resp = supabase.table('game_stats') \
                .select('*') \
                .eq('user_id', uid) \
                .execute()
            if resp.data:
                return jsonify({"success": True, "stats": resp.data[0]})
            else:
                return jsonify({"success": True, "stats": {
                    "xp": 0, "level": 1, "streak": 0, "last_date": None
                }})
        except Exception as e:
            logger.error(f"stats_get Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "stats": {"xp": 0, "level": 1, "streak": 0, "last_date": None}})

@stats_bp.route('/stats', methods=['POST'])
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

@stats_bp.route('/analytics', methods=['GET'])
def analytics_get():
    uid, err = _require_login()
    if err: return err

    if supabase and _is_valid_uuid(uid):
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


@stats_bp.route('/analytics', methods=['POST'])
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
