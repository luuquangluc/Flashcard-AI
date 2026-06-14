from flask import Blueprint, request, jsonify, send_file, Response, stream_with_context
import logging
import os
import json
import tempfile
import traceback
import hashlib

from .dependencies import _require_login, supabase, current_dir, cleanup_local_assets, get_rag_system, get_video_handler

# Tạm thời vô hiệu hóa Guardrail để tiết kiệm RAM cho máy chủ Render
_DOC_GUARDRAIL = None
_GUARDRAIL_DB = None

logger = logging.getLogger(__name__)

rag_bp = Blueprint('rag', __name__)

@rag_bp.route('/text/update', methods=['POST'])
def update_text():
    data = request.json
    content = data.get('content')
    title = data.get('title', 'Edited Document')
    
    if not content:
        return jsonify({"error": "Nội dung trống"}), 400

    # Document guardrail: kiểm tra nội dung trước khi nạp vào RAG
    uid_for_log = request.json.get('user_id') if request.json else None
    if _DOC_GUARDRAIL:
        _DOC_GUARDRAIL.reset()
        guard_result = _DOC_GUARDRAIL.check_content(content)
        # Log vào DB (bất kể pass hay block, nếu có violation)
        if _GUARDRAIL_DB and guard_result.violation.value != "none":
            _GUARDRAIL_DB.log(result=guard_result, source="text_update",
                              raw_input=content[:200], user_id=uid_for_log)
        if not guard_result.allowed:
            return jsonify({"error": guard_result.reason}), 400
        warnings = _DOC_GUARDRAIL.get_warnings()
    else:
        warnings = []
        
    try:
        rag_system = get_rag_system()
        
        file_hash = hashlib.md5(content.encode()).hexdigest()
        temp_filename = f"edited_{file_hash}.txt"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        success = rag_system.process_document(temp_path)
        if success:
            rag_system.doc_name = title
            return jsonify({"success": True, "message": "Cập nhật nội dung thành công!", "warnings": warnings})
        else:
            return jsonify({"error": "Không thể xử lý nội dung mới"}), 500
    except Exception as e:
        logger.error(f"Error updating text: {e}")
        return jsonify({"error": str(e)}), 500

@rag_bp.route('/document/content', methods=['GET'])
def get_document_content():
    try:
        rag_system = get_rag_system()
        if not rag_system or not rag_system.chunks:
            return jsonify({"error": "No document loaded"}), 404
            
        content = "\n\n".join([chunk.get("raw_text", chunk.get("enriched_text", "")) for chunk in rag_system.chunks])
        return jsonify({"success": True, "title": rag_system.doc_name, "content": content})
    except Exception as e:
        logger.error(f"Error getting document content: {e}")
        return jsonify({"error": str(e)}), 500

@rag_bp.route('/clear_rag', methods=['POST'])
def clear_rag():
    rag_system = get_rag_system()
    if rag_system:
        rag_system.chunks = []
        rag_system.current_pdf_path = None
    cleanup_local_assets()
    logger.info("RAG state cleared manually by user.")
    return jsonify({"success": True, "message": "RAG state cleared"})

@rag_bp.route('/upload', methods=['POST'])
def upload_pdf():
    fallback_uid = request.form.get('user_id')
    uid, err = _require_login(fallback_uid)
    
    if 'file' not in request.files:
        logger.warning("Upload failed: No 'file' boundary in request.files")
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("Upload failed: Filename is empty")
        return jsonify({"error": "No file selected"}), 400

    # Document guardrail: kiểm tra file metadata trước khi đọc nội dung
    if _DOC_GUARDRAIL:
        _DOC_GUARDRAIL.reset()
        file_content_peek = file.read()
        file.seek(0)  # Reset stream sau khi đọc
        guard_result = _DOC_GUARDRAIL.check_file(
            filename=file.filename,
            file_size=len(file_content_peek)
        )
        if not guard_result.allowed:
            return jsonify({"error": guard_result.reason}), 400

    try:
        cleanup_local_assets()
        
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        file_content = file.read()
        file_size = len(file_content)
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        
        logger.info(f"Received file: {file.filename}, saved to {temp_path}")
        
        file_url = None
        if supabase and uid:
            try:
                bucket_name = 'documents'
                import unicodedata
                # Normalize unicode → ASCII để tránh Supabase "Invalid key" với tên tiếng Việt
                normalized = unicodedata.normalize('NFKD', file.filename).encode('ascii', 'ignore').decode('ascii')
                safe_filename = "".join([c if c.isalnum() or c in "._-" else "_" for c in normalized])
                if not safe_filename or safe_filename.startswith("."): safe_filename = "document.pdf"
                storage_path = f"{uid}/{safe_filename}"
                
                supabase.storage.from_(bucket_name).upload(
                    file=file_content,
                    path=storage_path,
                    file_options={"content-type": "application/pdf", "upsert": "true"}
                )
                
                file_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
            except Exception as sb_err:
                logger.error(f"Supabase storage upload error: {sb_err}")

        rag_system = get_rag_system()
        if supabase:
            rag_system.supabase = supabase
        
        rag_system.doc_name = file.filename
        
        try:
            success = rag_system.process_pdf(temp_path)
        except Exception as proc_err:
            logger.error(f"Error in process_pdf: {proc_err}")
            return jsonify({"error": f"Lỗi xử lý tài liệu: {str(proc_err)}"}), 500
        
        if success:
            doc_warnings = _DOC_GUARDRAIL.get_warnings() if _DOC_GUARDRAIL else []
            return jsonify({
                "success": True,
                "message": "File processed successfully", 
                "chunks": len(rag_system.chunks),
                "is_structure_good": rag_system.is_structure_good,
                "file_url": file_url,
                "file_size": file_size,
                "uid": uid,
                "warnings": doc_warnings,
            })
        else:
            return jsonify({"error": "Không thể xử lý file PDF này (Có thể file bị khóa hoặc lỗi định dạng)"}), 500
            
    except Exception as e:
        logger.error(f"Critical error in upload: {str(e)}")
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500

@rag_bp.route('/query', methods=['POST'])
def query_rag():
    uid, err = _require_login()
    if err: return err
    
    rag_system = get_rag_system()
    if supabase:
        rag_system.supabase = supabase
    
    data = request.json
    user_query = data.get('query', '').strip()
    num_cards = data.get('num_cards', 3)
    page_range = data.get('page_range', '').strip()
    user_desire = data.get('user_desire', '').strip()
    
    cleanup_local_assets()
    
    file_name = data.get('fileName')
    if rag_system and file_name:
        rag_system.doc_name = file_name
    
    if not user_query and not page_range and not rag_system.chunks:
        return jsonify({"error": "Vui lòng nhập chủ đề hoặc dải trang"}), 400
    
    try:
        logger.info(f"Querying RAG: {user_query} (requested {num_cards} cards, range: {page_range}, desire: {user_desire})")
        
        def generate():
            def sse_message(data):
                return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
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
                            
                        res_json = rag_system.generate_no_rag(
                            user_query, 
                            num_flashcard=num_cards, 
                            user_desire=user_desire,
                            status_callback=worker_status_callback,
                            user_id=uid
                        )
                        context_text = "Generated from AI general knowledge"
                    else:
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
                    q.put(None)

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

@rag_bp.route('/pdf')
def get_pdf():
    filename = request.args.get('filename', 'highlighted_context.pdf')
    pdf_path = os.path.join(current_dir, filename)
    
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)
    else:
        fallback_path = os.path.join(current_dir, "highlighted_context.pdf")
        if os.path.exists(fallback_path):
            return send_file(fallback_path, mimetype='application/pdf', as_attachment=False)
        return jsonify({"error": "PDF file not found"}), 404
@rag_bp.route('/transcript')
def get_transcript():
    url = request.args.get('url')
    if not url:
        return "Missing URL", 400
        
    try:
        import requests
        from flask import Response
        resp = requests.get(url)
        if resp.status_code != 200:
            return "Failed to fetch transcript from storage", 500
            
        return Response(
            resp.content,
            mimetype='text/plain',
            headers={"Content-Type": "text/plain; charset=utf-8"}
        )
    except Exception as e:
        return f"Error: {str(e)}", 500

@rag_bp.route('/audio')
def get_audio():
    filename = request.args.get('filename')
    if not filename or not filename.endswith('.mp3'):
        return jsonify({"error": "Invalid audio file"}), 400
    audio_path = os.path.join(current_dir, filename)
    if os.path.exists(audio_path):
        return send_file(audio_path, mimetype='audio/mpeg')
    return jsonify({"error": "Audio file not found"}), 404

@rag_bp.route('/export_anki', methods=['POST'])
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
                local_path = os.path.join(current_dir, local_audio)
                if os.path.exists(local_path):
                    audio_filename = local_audio
                    media_files.append(local_path)
                    audio_field = f"[sound:{audio_filename}]"

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

@rag_bp.route('/flashcard/chat', methods=['POST'])
def flashcard_chat():
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

    # ── Guardrail check TRƯỚC khi gọi LLM ──
    if _DOC_GUARDRAIL is not None:  # proxy check: guardrail module available
        try:
            from modules.guardrail.chat_guardrail import ChatGuardrail as _CG
            _chat_guard = _CG()
            guard_result = _chat_guard.check(user_message, card_question=question)

            # Log vào DB nếu có vi phạm
            if _GUARDRAIL_DB and guard_result.violation.value != "none":
                _GUARDRAIL_DB.log(
                    result=guard_result,
                    source="chat",
                    raw_input=user_message,
                    user_id=uid,
                )

            if not guard_result.allowed:
                logger.warning(f"[ChatRoute] Guardrail blocked: {guard_result.violation.value}")
                return jsonify({
                    "error": guard_result.reason,
                    "guardrail_blocked": True,
                    "violation": guard_result.violation.value,
                }), 400

            # Dùng phiên bản đã sanitize nếu có (PII masked / truncated)
            if guard_result.sanitized:
                user_message = guard_result.sanitized
        except Exception as guard_err:
            logger.error(f"[ChatRoute] Guardrail error (non-blocking): {guard_err}")

    rag_system = get_rag_system()
    if supabase:
        rag_system.supabase = supabase

    # Wire user_id vào rag_system để Mem0 và Guardrail dùng
    rag_system._current_user_id = uid

    try:
        response = rag_system.chat_with_card(card_context, question, answer, user_message, history)
        return jsonify({"success": True, "response": response, "mem0_enabled": getattr(rag_system, 'mem0_enabled', False)})
    except Exception as e:
        logger.error(f"Flashcard chat error: {e}")
        return jsonify({"error": str(e)}), 500

# ──────────────────────────────────────────────────────────────────────────────
# General Chatbot — không gắn với flashcard cụ thể
# ──────────────────────────────────────────────────────────────────────────────

@rag_bp.route('/general/chat', methods=['POST'])
def general_chat():
    """
    Chatbot chung cho toàn ứng dụng.
    Hỗ trợ: hỏi đáp về tài liệu đã upload, hướng dẫn sử dụng app, giải đáp chung về học tập.
    """
    uid, err = _require_login()
    if err: return err

    data = request.json or {}
    user_message = data.get('message', '')
    history = data.get('history', [])

    if not user_message:
        return jsonify({"error": "Vui lòng nhập tin nhắn"}), 400

    rag_system = get_rag_system()
    if supabase:
        rag_system.supabase = supabase
    rag_system._current_user_id = uid

    # Lấy context từ tài liệu đã upload (nếu có)
    doc_context = ""
    if hasattr(rag_system, 'chunks') and rag_system.chunks:
        try:
            # Tìm các đoạn liên quan nhất với câu hỏi
            from modules.RAG.rag_retrieval import RAGRetrieval
            if isinstance(rag_system, RAGRetrieval):
                results = rag_system.retrieve(user_message, top_n=3)
                if results:
                    doc_context = "\n\n".join([r.get("content", "") for r in results if r.get("content")])
        except Exception as e:
            logger.warning(f"General chat: Could not retrieve doc context: {e}")

    # Build system prompt
    system_prompt = (
        "Bạn là trợ lý AI thông minh của ứng dụng Flashcard AI — một hệ thống học tập sử dụng RAG.\n"
        "Nhiệm vụ:\n"
        "1. Giải đáp thắc mắc về nội dung tài liệu mà người dùng đã upload.\n"
        "2. Hướng dẫn cách sử dụng các tính năng của ứng dụng (tạo flashcard, ôn tập, trò chơi, thống kê).\n"
        "3. Hỗ trợ mẹo học tập, phương pháp ghi nhớ hiệu quả.\n"
        "4. Trả lời bằng tiếng Việt, ngắn gọn, thân thiện.\n"
        "5. [QUAN TRỌNG] Không trả lời các câu hỏi không liên quan đến học tập (nấu ăn, giá vàng, thời tiết, v.v.).\n"
    )
    if doc_context:
        system_prompt += f"\n--- NGỮ CẢNH TÀI LIỆU ---\n{doc_context}\n--- HẾT NGỮ CẢNH ---\n"

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_message})

    try:
        response = rag_system.client.chat.completions.create(
            model=rag_system.model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        reply = response.choices[0].message.content
        return jsonify({"success": True, "response": reply})
    except Exception as e:
        logger.error(f"General chat error: {e}")
        return jsonify({"error": str(e)}), 500


@rag_bp.route('/video/transcribe', methods=['POST'])
def video_transcribe():
    fallback_uid = request.json.get('user_id')
    uid, err = _require_login(fallback_uid)
    
    data = request.json
    video_url = data.get('url')
    if not video_url:
        return jsonify({"error": "Vui lòng cung cấp link video"}), 400

    def generate():
        def sse_message(data):
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
        yield sse_message({"type": "status", "content": "🎥 Đang bắt đầu xử lý video..."})
        
        from queue import Queue, Empty
        import threading
        
        q = Queue()
        
        def run_transcribe():
            try:
                rag_system = get_rag_system()
                video_handler = get_video_handler()
                
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                q.put({"type": "status", "content": "⏳ Đang trích xuất nội dung từ video (có thể mất vài phút)..."})
                transcript, summary, title = loop.run_until_complete(video_handler.get_transcript(video_url))
                
                if not transcript:
                    q.put({"type": "error", "content": "Không thể trích xuất nội dung từ video này"})
                    q.put(None)
                    return

                file_hash = hashlib.md5(video_url.encode()).hexdigest()
                temp_filename = f"video_{file_hash}.txt"
                temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
                
                with open(temp_path, 'w', encoding='utf-8') as f:
                    full_text = f"# TIÊU ĐỀ: {title}\n# LINK: {video_url}\n\n## BẢN TÓM TẮT NỘI DUNG\n{summary}\n\n## BẢN CHÉP LỜI CHI TIẾT\n{transcript}"
                    f.write(full_text)

                file_url = None
                file_size = len(full_text.encode('utf-8'))
                if supabase and uid:
                    try:
                        bucket_name = 'documents'
                        storage_path = f"{uid}/{temp_filename}"
                        
                        supabase.storage.from_(bucket_name).upload(
                            file=full_text.encode('utf-8'),
                            path=storage_path,
                            file_options={"content-type": "text/plain; charset=utf-8", "upsert": "true"}
                        )
                        file_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
                    except Exception as sb_err:
                        logger.error(f"Supabase storage upload error for video transcript: {sb_err}")

                q.put({"type": "status", "content": f"📑 Đang nạp transcript vào RAG: {title}"})
                success = rag_system.process_document(temp_path)
                
                if success:
                    rag_system.doc_name = title
                    q.put({
                        "type": "result",
                        "title": title, 
                        "file_url": file_url,
                        "file_size": file_size,
                        "message": f"Đã nạp nội dung video '{title}' vào hệ thống RAG thành công."
                    })
                else:
                    q.put({"type": "error", "content": "Nạp transcript vào RAG thất bại"})
            except Exception as e:
                logger.error(f"❌ Lỗi xử lý video: {traceback.format_exc()}")
                q.put({"type": "error", "content": f"Lỗi hệ thống: {str(e)}"})
            finally:
                q.put(None)

        thread = threading.Thread(target=run_transcribe)
        thread.start()
        
        while thread.is_alive():
            try:
                msg = q.get(timeout=10)
                if msg is None: break
                yield sse_message(msg)
            except Empty:
                yield sse_message({"type": "ping"})
                
        thread.join()

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@rag_bp.route('/video/upload', methods=['POST'])
def video_upload():
    fallback_uid = request.form.get('user_id')
    uid, err = _require_login(fallback_uid)
    
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    title = request.form.get('title', file.filename)

    try:
        rag_system = get_rag_system()
        video_handler = get_video_handler()

        logger.info(f"🎥 Đang bắt đầu xử lý file video upload: {file.filename}")
        
        fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
        os.close(fd)
        file.save(temp_path)

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        transcript, summary, title = loop.run_until_complete(video_handler.get_transcript_from_file(temp_path, title))
        
        try: os.remove(temp_path)
        except: pass

        if not transcript:
            return jsonify({"error": "Không thể trích xuất nội dung từ file này"}), 500

        file_hash = hashlib.md5(file.filename.encode()).hexdigest()
        temp_filename = f"video_{file_hash}.txt"
        temp_path_txt = os.path.join(tempfile.gettempdir(), temp_filename)
        
        with open(temp_path_txt, 'w', encoding='utf-8') as f:
            full_text = f"# TIÊU ĐỀ: {title}\n# NGUỒN: File Upload\n\n## BẢN TÓM TẮT NỘI DUNG\n{summary}\n\n## BẢN CHÉP LỜI CHI TIẾT\n{transcript}"
            f.write(full_text)

        file_url = None
        file_size = len(full_text.encode('utf-8'))
        if supabase and uid:
            try:
                bucket_name = 'documents'
                # Use hash-based filename to avoid Supabase invalid key errors
                storage_path = f"{uid}/{temp_filename}"
                
                supabase.storage.from_(bucket_name).upload(
                    file=full_text.encode('utf-8'),
                    path=storage_path,
                    file_options={"content-type": "text/plain; charset=utf-8", "upsert": "true"}
                )
                file_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
            except Exception as sb_err:
                logger.error(f"Supabase storage upload error for video transcript: {sb_err}")

        logger.info(f"📑 Đang nạp transcript vào RAG: {title}")
        success = rag_system.process_document(temp_path_txt)
        
        if success:
            rag_system.doc_name = title
            return jsonify({
                "success": True, 
                "title": title, 
                "full_text": full_text,
                "file_url": file_url,
                "file_size": file_size,
                "transcript_preview": transcript[:200] + "...",
                "message": f"Đã nạp nội dung file video '{title}' vào hệ thống RAG thành công."
            })
        else:
            return jsonify({"error": "Nạp transcript vào RAG thất bại"}), 500

    except Exception as e:
        logger.error(f"❌ Lỗi xử lý video upload: {traceback.format_exc()}")
        return jsonify({"error": f"Lỗi hệ thống: {str(e)}"}), 500


# ──────────────────────────────────────────────────────────────────────────────
# Mem0 Memory Management API Routes
# ──────────────────────────────────────────────────────────────────────────────

@rag_bp.route('/memory/list', methods=['GET'])
def memory_list():
    """
    Lấy toàn bộ long-term memories của user hiện tại.
    Response: {success, memories: [{id, memory, created_at}, ...]}
    """
    uid, err = _require_login()
    if err:
        return err

    rag_system = get_rag_system()
    memories = rag_system.get_user_memories(uid)
    return jsonify({"success": True, "memories": memories, "count": len(memories)})


@rag_bp.route('/memory/search', methods=['POST'])
def memory_search():
    """
    Tìm kiếm memories liên quan đến query.
    Body: {query: str, limit: int (default 5)}
    """
    uid, err = _require_login()
    if err:
        return err

    data = request.json or {}
    query = data.get('query', '')
    limit = data.get('limit', 5)

    if not query:
        return jsonify({"error": "Vui lòng nhập nội dung tìm kiếm"}), 400

    from modules.chat.chat_handler import mem0_search
    results = mem0_search(uid, query, limit=limit)
    return jsonify({"success": True, "query": query, "results": results})


@rag_bp.route('/memory/delete', methods=['DELETE'])
def memory_delete():
    """
    Xóa toàn bộ memories của user (GDPR / reset).
    """
    uid, err = _require_login()
    if err:
        return err

    rag_system = get_rag_system()
    success = rag_system.delete_user_memories(uid)
    if success:
        return jsonify({"success": True, "message": f"Đã xóa toàn bộ memories của bạn."})
    else:
        return jsonify({"error": "Không thể xóa memories (Mem0 có thể chưa được cài đặt)"}), 500


@rag_bp.route('/memory/status', methods=['GET'])
def memory_status():
    """
    Kiểm tra trạng thái Mem0 + cache stats.
    Response: {mem0_enabled, cache_stats, ...}
    """
    uid, err = _require_login()
    if err:
        return err

    rag_system = get_rag_system()
    from modules.chat.chat_memory import chat_memory_db
    return jsonify({
        "success": True,
        "mem0_enabled": getattr(rag_system, 'mem0_enabled', False),
        "supabase_memory_enabled": chat_memory_db.is_ready if chat_memory_db else False,
        "cache_stats": rag_system.get_chat_cache_stats(),
        "user_id": uid,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Learner Profile & Episode History (Supabase-backed)
# ──────────────────────────────────────────────────────────────────────────────

@rag_bp.route('/memory/profile', methods=['GET'])
def memory_profile():
    """
    Lấy learner profile của user hiện tại.
    Response: {profile_data: {total_chats, topic_frequency, intent_frequency, ...}}
    """
    uid, err = _require_login()
    if err:
        return err

    from modules.chat.chat_memory import chat_memory_db
    profile = chat_memory_db.get_profile(uid)
    return jsonify({"success": True, "profile": profile})


@rag_bp.route('/memory/episodes', methods=['GET'])
def memory_episodes():
    """
    Lấy lịch sử chat episodes của user.
    Query params: ?limit=20&card_scope=abc12345
    """
    uid, err = _require_login()
    if err:
        return err

    limit = request.args.get('limit', 20, type=int)
    card_scope = request.args.get('card_scope', None)

    from modules.chat.chat_memory import chat_memory_db
    episodes = chat_memory_db.get_episodes(uid, card_scope=card_scope, limit=limit)
    return jsonify({"success": True, "episodes": episodes, "count": len(episodes)})


@rag_bp.route('/memory/episode-stats', methods=['GET'])
def memory_episode_stats():
    """
    Thống kê học tập của user: số lượt chat, intent phổ biến, chủ đề thường hỏi.
    """
    uid, err = _require_login()
    if err:
        return err

    from modules.chat.chat_memory import chat_memory_db
    stats = chat_memory_db.get_episode_stats(uid)
    return jsonify({"success": True, "stats": stats})


@rag_bp.route('/memory/delete-all', methods=['DELETE'])
def memory_delete_all():
    """
    Xóa toàn bộ dữ liệu memory (episodes + profile + Mem0) của user.
    Tuân thủ GDPR — xóa sạch hoàn toàn.
    """
    uid, err = _require_login()
    if err:
        return err

    results = {}

    # Xóa Supabase data
    from modules.chat.chat_memory import chat_memory_db
    results["supabase"] = chat_memory_db.delete_user_data(uid)

    # Xóa Mem0 data
    rag_system = get_rag_system()
    results["mem0"] = rag_system.delete_user_memories(uid)

    all_ok = all(results.values())
    return jsonify({
        "success": all_ok,
        "details": results,
        "message": "Đã xóa toàn bộ dữ liệu memory." if all_ok else "Có lỗi khi xóa một số dữ liệu.",
    })
