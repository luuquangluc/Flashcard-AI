from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta
from .dependencies import _require_login, supabase, fsrs, get_rag_system

logger = logging.getLogger(__name__)

flashcards_bp = Blueprint('flashcards', __name__)

@flashcards_bp.route('/review/submit', methods=['POST'])
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
        resp = supabase.table('flashcard_sets').select('*').eq('id', set_id).eq('user_id', uid).execute()
        if not resp.data:
            return jsonify({"error": "Không tìm thấy bộ thẻ"}), 404
        
        flashcard_set = resp.data[0]
        cards = flashcard_set.get('cards', [])
        
        card_found = False
        new_int, new_due_date = 0, None
        
        if quality in [1, 2, 3, 4]:
            fsrs_quality = quality
        else:
            mapping = {0: 1, 3: 2, 4: 3, 5: 4}
            fsrs_quality = mapping.get(quality, 3)

        for card in cards:
            if card.get('id') == card_id:
                srs = card.get('srs', {})
                
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

        supabase.table('flashcard_sets').update({'cards': cards}).eq('id', set_id).execute()
        
        return jsonify({
            "success": True, 
            "next_review": new_due_date,
            "stability": new_stability
        })
    except Exception as e:
        logger.error(f"Review error: {e}")
        return jsonify({"error": str(e)}), 500

@flashcards_bp.route('/review/batch', methods=['POST'])
def review_batch():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    set_id = data.get('set_id')
    reviews = data.get('reviews', [])

    if not set_id or not reviews:
        return jsonify({"error": "Thiếu thông tin batch review"}), 400

    if not supabase:
        return jsonify({"error": "Cần kết nối Supabase"}), 500

    try:
        resp = supabase.table('flashcard_sets').select('*').eq('id', set_id).eq('user_id', uid).execute()
        if not resp.data:
            return jsonify({"error": "Không tìm thấy bộ thẻ"}), 404
        
        flashcard_set = resp.data[0]
        cards = flashcard_set.get('cards', [])
        
        review_map = {r['card_id']: r['quality'] for r in reviews}
        
        updated_count = 0
        for card in cards:
            c_id = card.get('id')
            if c_id in review_map:
                quality = review_map[c_id]
                srs = card.get('srs', {})
                
                if quality in [1, 2, 3, 4]:
                    fsrs_quality = quality
                else:
                    mapping = {0: 1, 3: 2, 4: 3, 5: 4}
                    fsrs_quality = mapping.get(quality, 3)

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
        
        supabase.table('flashcard_sets').update({'cards': cards}).eq('id', set_id).execute()
        
        return jsonify({"success": True, "updated": updated_count})
    except Exception as e:
        logger.error(f"Batch review error: {e}")
        return jsonify({"error": str(e)}), 500

@flashcards_bp.route('/flashcard/update', methods=['POST'])
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
            
        try:
            mode = "vocabulary" if card_level == "Từ vựng" else "content"
            rag_system = get_rag_system()
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

@flashcards_bp.route('/flashcard/delete', methods=['POST'])
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
            
        try:
            deleted_card = next((c for c in cards if c.get('id') == card_id), None)
            if deleted_card:
                card_level = deleted_card.get('level', '')
                mode = "vocabulary" if card_level == "Từ vựng" else "content"
                rag_system = get_rag_system()
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

@flashcards_bp.route('/feedback/log', methods=['POST'])
def log_ai_feedback():
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    events = data.get('events', [])
    if not events and 'feedback_type' in data:
        events = [data]

    if not events:
        return jsonify({"success": True, "message": "No events to log"})

    try:
        feedback_to_insert = []
        rag_system = get_rag_system()
        for ev in events:
            doc_name = ev.get('document_name') or (rag_system.doc_name if rag_system else None)
            feedback_to_insert.append({
                'user_id': uid,
                'original_card': ev.get('original_card'),
                'corrected_card': ev.get('corrected_card'),
                'feedback_type': ev.get('feedback_type'),
                'document_name': doc_name,
                'mode': ev.get('mode', 'content')
            })

        if supabase and feedback_to_insert:
            supabase.table('ai_feedback').insert(feedback_to_insert).execute()
            
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Feedback log error: {e}")
        return jsonify({"error": str(e)}), 500
