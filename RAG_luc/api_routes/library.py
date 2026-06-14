from flask import Blueprint, request, jsonify
import logging
import os
import requests
import tempfile

from .dependencies import _require_login, _is_valid_uuid, supabase, current_dir, cleanup_local_assets, get_rag_system

logger = logging.getLogger(__name__)

library_bp = Blueprint('library', __name__)

# ================================================================
# LIBRARY API — Bộ thẻ per-user
# ================================================================

@library_bp.route('/library', methods=['GET'])
def library_get():
    uid, err = _require_login()
    if err: return err

    if supabase and _is_valid_uuid(uid):
        try:
            resp = supabase.table('flashcard_sets') \
                .select('id, title, cards, card_count, created_at') \
                .eq('user_id', uid) \
                .order('created_at', desc=True) \
                .execute()
            data_list = resp.data if resp.data else []
            formatted_sets = [{**s, "name": s.get("title")} for s in data_list]
            return jsonify({"success": True, "sets": formatted_sets})
        except Exception as e:
            logger.error(f"library_get Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "sets": []})

@library_bp.route('/library', methods=['POST'])
def library_save():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    title = data.get('name') or data.get('title') or 'Bộ thẻ không tên'
    cards = data.get('cards', [])

    if not cards:
        return jsonify({"error": "Không có thẻ nào để lưu"}), 400

    if supabase:
        try:
            bucket_name = 'documents'
            for card in cards:
                card_id = card.get('id')
                if not card_id: continue
                
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
                        public_url = supabase.storage.from_(bucket_name).get_public_url(f"{uid}/{pdf_file}")
                        card['pdf_url'] = public_url
                    except Exception as e:
                        logger.error(f"Failed to upload PDF {pdf_file}: {e}")
                
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

@library_bp.route('/library/<set_id>', methods=['PUT'])
def library_update(set_id):
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    title = data.get('name') or data.get('title') or 'Bộ thẻ không tên'
    cards = data.get('cards', [])

    if not cards:
        return jsonify({"error": "Không có thẻ nào để cập nhật"}), 400

    if supabase:
        try:
            # Verify ownership
            existing = supabase.table('flashcard_sets').select('id').eq('id', set_id).eq('user_id', uid).execute()
            if not existing.data:
                return jsonify({"error": "Không tìm thấy bộ thẻ hoặc bạn không có quyền"}), 404

            # Upload media assets (PDFs, audio) nếu còn trên local
            bucket_name = 'documents'
            for card in cards:
                card_id = card.get('id')
                if not card_id: continue

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
                        public_url = supabase.storage.from_(bucket_name).get_public_url(f"{uid}/{pdf_file}")
                        card['pdf_url'] = public_url
                    except Exception as e:
                        logger.error(f"Failed to upload PDF {pdf_file}: {e}")

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

            supabase.table('flashcard_sets').update({
                'title': title,
                'cards': cards
            }).eq('id', set_id).eq('user_id', uid).execute()

            return jsonify({"success": True, "id": set_id})
        except Exception as e:
            logger.error(f"library_update Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "id": set_id})

@library_bp.route('/library/<set_id>', methods=['DELETE'])
def library_delete(set_id):
    uid, err = _require_login()
    if err: return err

    if supabase:
        try:
            supabase.table('flashcard_sets').delete().eq('id', set_id).eq('user_id', uid).execute()
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"library_delete Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True})

# ================================================================
# DOCUMENTS API — PDF files per-user
# ================================================================

@library_bp.route('/documents', methods=['GET'])
def documents_get():
    uid, err = _require_login()
    if err: return err

    if supabase:
        try:
            resp = supabase.table('user_documents').select('*').eq('user_id', uid).order('created_at', desc=True).execute()
            return jsonify({"success": True, "documents": resp.data or []})
        except Exception as e:
            logger.error(f"documents_get Supabase error: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "documents": []})

@library_bp.route('/documents', methods=['POST'])
def document_save():
    data = request.json or {}
    fallback_uid = data.get('user_id')
    uid, err = _require_login(fallback_uid)
    if err: return err

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

@library_bp.route('/documents/reuse', methods=['POST'])
def document_reuse():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    doc_url = data.get('url')
    
    if not doc_url:
        return jsonify({"error": "No document URL provided"}), 400

    try:
        resp = requests.get(doc_url)
        if resp.status_code != 200:
            return jsonify({"error": "Failed to download document from storage"}), 500
        
        is_pdf = doc_url.lower().split('?')[0].endswith('.pdf')
        suffix = ".pdf" if is_pdf else ".txt"
        
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(temp_path, 'wb') as f:
            f.write(resp.content)
        
        cleanup_local_assets()
        
        rag_system = get_rag_system()
        rag_system.supabase = supabase
        
        # Lấy tên file từ URL để gán lại cho rag_system
        import urllib.parse
        parsed_url = urllib.parse.urlparse(doc_url)
        path = urllib.parse.unquote(parsed_url.path)
        file_name = os.path.basename(path)
        rag_system.doc_name = file_name

        if is_pdf:
            success = rag_system.process_pdf(temp_path)
        else:
            success = rag_system.process_document(temp_path)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Document '{file_name}' loaded for reuse", 
                "chunks": len(rag_system.chunks),
                "is_structure_good": rag_system.is_structure_good
            })
        else:
            return jsonify({"error": "Failed to process document"}), 500
            
    except Exception as e:
        logger.error(f"Error in document reuse: {str(e)}")
        return jsonify({"error": str(e)}), 500

@library_bp.route('/documents/<doc_id>', methods=['DELETE'])
def document_delete(doc_id):
    uid, err = _require_login()
    if err: return err

    if not supabase:
        return jsonify({"success": True})

    try:
        doc_res = supabase.table('user_documents').select('*').eq('id', doc_id).eq('user_id', uid).execute()
        if not doc_res.data:
            return jsonify({"error": "Document not found"}), 404
        
        file_url = doc_res.data[0].get('file_url')
        supabase.table('user_documents').delete().eq('id', doc_id).eq('user_id', uid).execute()
        
        if "documents/" in file_url:
            storage_path = file_url.split("documents/")[1]
            try:
                supabase.storage.from_('documents').remove([storage_path])
                logger.info(f"Deleted storage file from Supabase: {storage_path}")
            except Exception as se:
                logger.warning(f"Storage deletion warning: {se}")

        return jsonify({"success": True, "message": "Document deleted successfully"})
    except Exception as e:
        logger.error(f"document_delete error: {e}")
        return jsonify({"error": str(e)}), 500