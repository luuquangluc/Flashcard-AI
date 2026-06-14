"""
Admin API routes - Thống kê dành cho quản trị viên.
"""
import os
import json
import logging
from flask import Blueprint, request, jsonify, session
from .dependencies import supabase

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def require_admin(f):
    """Decorator: chỉ cho phép admin truy cập."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        role = session.get("role", "user")
        if role != "admin":
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/api/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    """Trả về thống kê tổng quan cho admin."""
    try:
        if not supabase:
            return jsonify({"error": "Supabase not configured"}), 500
        # 1. Tổng số users (từ Supabase Auth)
        users = []
        try:
            auth_users = supabase.auth.admin.list_users()
            for u in auth_users:
                meta = u.user_metadata or {}
                users.append({
                    "id": str(u.id),
                    "username": meta.get("username", u.email or "unknown"),
                    "name": meta.get("username", "").capitalize(),
                    "role": meta.get("role", "user"),
                    "created_at": str(u.created_at) if u.created_at else None
                })
        except Exception as e:
            logger.warning(f"Could not list auth users: {e}")
        total_users = len(users)
        
        # 2. Tổng bộ thẻ & thẻ
        sets_resp = supabase.table("flashcard_sets").select("id,user_id,title,card_count,created_at").execute()
        all_sets = sets_resp.data or []
        total_sets = len(all_sets)
        total_cards = sum(s.get("card_count", 0) for s in all_sets)
        
        # 3. Token usage từ api_costs.json
        cost_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "api_costs.json")
        token_stats = {
            "total_input": 0,
            "total_output": 0,
            "total_cost_usd": 0,
            "by_feature": {},
            "by_model": {},
            "recent": []
        }
        
        if os.path.exists(cost_file):
            try:
                with open(cost_file, "r", encoding="utf-8") as f:
                    costs = json.load(f)
                
                for entry in costs:
                    inp = entry.get("input_tokens", 0) or 0
                    out = entry.get("output_tokens", 0) or 0
                    cost = entry.get("cost_usd", 0) or 0
                    feature = entry.get("feature", "Unknown")
                    model = entry.get("model", "Unknown")
                    
                    token_stats["total_input"] += inp
                    token_stats["total_output"] += out
                    token_stats["total_cost_usd"] += cost
                    
                    # By feature
                    if feature not in token_stats["by_feature"]:
                        token_stats["by_feature"][feature] = {"input": 0, "output": 0, "cost": 0, "count": 0}
                    token_stats["by_feature"][feature]["input"] += inp
                    token_stats["by_feature"][feature]["output"] += out
                    token_stats["by_feature"][feature]["cost"] += cost
                    token_stats["by_feature"][feature]["count"] += 1
                    
                    # By model
                    if model not in token_stats["by_model"]:
                        token_stats["by_model"][model] = {"input": 0, "output": 0, "cost": 0, "count": 0}
                    token_stats["by_model"][model]["input"] += inp
                    token_stats["by_model"][model]["output"] += out
                    token_stats["by_model"][model]["cost"] += cost
                    token_stats["by_model"][model]["count"] += 1
                
                # Last 20 entries
                token_stats["recent"] = costs[-20:]
                token_stats["total_cost_usd"] = round(token_stats["total_cost_usd"], 6)
                token_stats["total_entries"] = len(costs)
            except Exception as e:
                logger.error(f"Error reading cost file: {e}")
        
        # 4. Analytics history (sessions gần đây)
        try:
            analytics_resp = supabase.table("flashcard_sessions") \
                .select("*") \
                .order("created_at", desc=True) \
                .limit(50).execute()
            recent_sessions = analytics_resp.data or []
        except Exception:
            recent_sessions = []
        
        # 5. Top users by card count
        user_card_counts = {}
        for s in all_sets:
            uid = s.get("user_id", "unknown")
            user_card_counts[uid] = user_card_counts.get(uid, 0) + s.get("card_count", 0)
        
        top_users = []
        for uid, count in sorted(user_card_counts.items(), key=lambda x: -x[1])[:10]:
            u = next((u for u in users if u["id"] == uid), None)
            top_users.append({
                "user_id": uid,
                "username": u["username"] if u else "unknown",
                "name": u.get("name", "") if u else "",
                "total_cards": count
            })
        
        return jsonify({
            "total_users": total_users,
            "total_sets": total_sets,
            "total_cards": total_cards,
            "tokens": token_stats,
            "top_users": top_users,
            "recent_sessions": recent_sessions[:20]
        })
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        return jsonify({"error": str(e)}), 500
