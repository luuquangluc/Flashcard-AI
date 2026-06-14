from flask import Blueprint, request, jsonify
import logging
from datetime import datetime
from .dependencies import _require_login, supabase

logger = logging.getLogger(__name__)

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/notifications', methods=['GET'])
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


@notifications_bp.route('/notifications', methods=['POST'])
def notifications_save():
    uid, err = _require_login()
    if err: return err
    data = request.json or {}
    notifs = data.get('notifications', [])
    if not notifs:
        return jsonify({"success": True})
    if supabase:
        import uuid
        from .dependencies import _is_valid_uuid
        try:
            payloads = []
            for n in notifs:
                raw_id = n.get('id')
                # Nếu ID không phải UUID hợp lệ (ví dụ 'welcome-1'), convert nó sang UUID định danh
                if raw_id and not _is_valid_uuid(raw_id):
                    # Dùng uuid3 với namespace Nil để tạo UUID từ chuỗi (deterministic)
                    notif_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, str(raw_id)))
                else:
                    notif_id = raw_id

                created = datetime.fromtimestamp(n['createdAt'] / 1000).isoformat() if 'createdAt' in n else datetime.utcnow().isoformat()
                payloads.append({
                    'id': notif_id,
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


@notifications_bp.route('/notifications/<nid>/read', methods=['PUT'])
def notification_read(nid):
    uid, err = _require_login()
    if err: return err
    if supabase:
        import uuid
        from .dependencies import _is_valid_uuid
        try:
            # Chuyển đổi nid nếu không phải UUID hợp lệ
            target_id = nid
            if nid and not _is_valid_uuid(nid):
                target_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, str(nid)))
            
            supabase.table('notifications').update({'is_read': True}).eq('id', target_id).eq('user_id', uid).execute()
        except Exception as e:
            logger.error(f"notification_read error: {e}")
    return jsonify({"success": True})


@notifications_bp.route('/notifications/read_all', methods=['PUT'])
def notification_read_all():
    uid, err = _require_login()
    if err: return err
    if supabase:
        try:
            supabase.table('notifications').update({'is_read': True}).eq('user_id', uid).execute()
        except Exception as e:
            logger.error(f"notification_read_all error: {e}")
    return jsonify({"success": True})


@notifications_bp.route('/notifications/<nid>', methods=['DELETE'])
def notification_delete(nid):
    uid, err = _require_login()
    if err: return err
    if supabase:
        import uuid
        from .dependencies import _is_valid_uuid
        try:
            # Chuyển đổi nid nếu không phải UUID hợp lệ
            target_id = nid
            if nid and not _is_valid_uuid(nid):
                target_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, str(nid)))
                
            supabase.table('notifications').delete().eq('id', target_id).eq('user_id', uid).execute()
        except Exception as e:
            logger.error(f"notification_delete error: {e}")
    return jsonify({"success": True})
