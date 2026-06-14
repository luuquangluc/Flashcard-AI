"""
rag_generation.py - Tạo flashcard, xử lý từ vựng, generate no-RAG.
Chat with Card đã được tách sang modules/chat/chat_handler.py
"""
import os
import json
import uuid
import logging

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable, get_current_run_tree
except ImportError:
    def traceable(name=None, run_type=None, **kwargs):
        def decorator(func): return func
        return decorator
    def get_current_run_tree(): return None

try:
    from deep_translator import GoogleTranslator
    HAS_DEEP_TRANSLATOR = True
except ImportError:
    HAS_DEEP_TRANSLATOR = False

try:
    import argostranslate.translate as argos_translate
    HAS_ARGOS = True
except ImportError:
    HAS_ARGOS = False

try:
    import eng_to_ipa
    HAS_IPA = True
except ImportError:
    HAS_IPA = False

try:
    from wordfreq import zipf_frequency, tokenize as wordfreq_tokenize
    HAS_WORDFREQ = True
except ImportError:
    HAS_WORDFREQ = False

try:
    import nltk
    from nltk import pos_tag, word_tokenize
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False


def map_pos_to_vn(tag):
    if tag.startswith('NN'): return "danh từ"
    if tag.startswith('VB'): return "động từ"
    if tag.startswith('JJ'): return "tính từ"
    if tag.startswith('RB'): return "trạng từ"
    if tag.startswith('PR'): return "đại từ"
    if tag.startswith('IN'): return "giới từ"
    if tag.startswith('CC'): return "liên từ"
    if tag.startswith('CD'): return "số từ"
    return "từ"


import re as _re_module
import numpy as np

try:
    from modules.RAG.validators import json_guard
except ImportError:
    try:
        from validators import json_guard
    except ImportError:
        class DummyGuard:
            def validate(self, text):
                class DummyResult:
                    def __init__(self, t): self.validated_output = t
                return DummyResult(text)
        json_guard = DummyGuard()


class RAGGeneration:
    """Mixin: tạo câu hỏi, câu trả lời, flashcard, và chat."""

    @traceable(name="Retrieval: Highlight Mapping", run_type="retriever", tags=["rrf_search", "highlight_mapping"])
    def _find_best_chunk_for_card(self, text, chunks_meta, chunk_embeddings, qa_embedding=None):
        """Tìm chunk phù hợp nhất bằng embedding similarity.
        
        Args:
            qa_embedding: Pre-computed embedding của text (list[float]) — nếu None sẽ tự compute (tốn API call).
        """
        if not chunks_meta or len(chunks_meta) == 1:
            return 0
        
        try:
            qa_text = text
            # Dùng embedding truyền vào nếu có, tránh gọi API thêm
            if qa_embedding is not None:
                qa_emb = np.array(qa_embedding)
            else:
                qa_emb = np.array(self.embed_text(qa_text))
            
            dense_scores = []
            for idx, c_emb in enumerate(chunk_embeddings):
                c_emb = np.array(c_emb)
                sim = np.dot(qa_emb, c_emb) / (np.linalg.norm(qa_emb) * np.linalg.norm(c_emb) + 1e-8)
                dense_scores.append((idx, float(sim)))
            
            # Sparse: Keyword overlap
            qa_words = set(w for w in _re_module.findall(r'\w+', qa_text.lower()) if len(w) >= 3)
            sparse_scores = []
            for idx, chunk in enumerate(chunks_meta):
                chunk_words = set(_re_module.findall(r'\w+', chunk.get("text", "").lower()))
                overlap = len(qa_words & chunk_words) / max(len(qa_words), 1)
                sparse_scores.append((idx, overlap))
            
            # Reciprocal Rank Fusion
            dense_ranked = sorted(dense_scores, key=lambda x: -x[1])
            sparse_ranked = sorted(sparse_scores, key=lambda x: -x[1])
            
            k = 60
            fused = {}
            for rank, (idx, _) in enumerate(dense_ranked):
                fused[idx] = fused.get(idx, 0) + 1.0 / (rank + k)
            for rank, (idx, _) in enumerate(sparse_ranked):
                fused[idx] = fused.get(idx, 0) + 1.0 / (rank + k)
            
            best_idx = max(fused, key=fused.get)
            return best_idx
        except Exception as e:
            logger.warning(f"Embedding chunk match failed, fallback to keyword: {e}")
            qa_words = set(w for w in _re_module.findall(r'\w+', text.lower()) if len(w) >= 3)
            best_idx, best_score = 0, 0
            for idx, chunk in enumerate(chunks_meta):
                chunk_words = set(_re_module.findall(r'\w+', chunk.get("text", "").lower()))
                score = len(qa_words & chunk_words)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            return best_idx


    # ------------------------------------------------------------------ #
    # Generate Questions
    # ------------------------------------------------------------------ #
    @traceable(name="Generation: Questions", run_type="llm", tags=["gen_questions"])
    def generate_questions(self, context, num_questions=3, user_desire="", target_level=None, feedback_str=""):
        is_language_mode = "[MODE_LANGUAGE]" in user_desire

        if is_language_mode:
            system_prompt = f"""Bạn là AI trích xuất từ vựng.
Dựa vào <context>, hãy trích xuất CHÍNH XÁC {num_questions} từ vựng, thuật ngữ hoặc cụm từ quan trọng/mới.
- Chỉ lấy từ/cụm từ gốc cho trường `question`.
- Trả về JSON: {{"questions": [{{"level": "Từ vựng", "question": "Từ gốc", "phonetic": "phiên âm", "part_of_speech": "loại từ", "chunk_id": 0}}]}}
- `chunk_id` phải khớp chính xác với `id` trong thẻ <chunk> chứa từ đó.
{feedback_str}
{f"ĐỊNH HƯỚNG: {user_desire}" if user_desire else ""}"""
        else:
            if target_level:
                level_instruction = f"BẮT BUỘC TẠO CÂU HỎI Ở CẤP ĐỘ: {target_level}."
                json_format = f'{{"questions": [{{"level": "{target_level}", "question": "...", "chunk_id": 0}}]}}'
            else:
                level_instruction = 'Thông thường hãy tạo đan xen các cấp độ (Nhận biết/Thông hiểu/Vận dụng).'
                json_format = '{"questions": [{"level": "Nhận biết", "question": "...", "chunk_id": 0}]}'

            system_prompt = f"""Bạn là AI tạo Flashcard.
Dựa vào <context>, hãy tạo CHÍNH XÁC {num_questions} flashcards ngắn gọn. {level_instruction}
NẾU có "Định hướng người dùng" bên dưới, hãy ƯU TIÊN thực hiện theo định hướng đó.
- Tuyệt đối CHỈ ĐƯỢC tạo câu hỏi và câu trả lời dựa trên những thông tin CÓ SẴN TRONG ĐOẠN VĂN ĐƯỢC CUNG CẤP. Không dùng kiến thức bên ngoài đoạn văn. Nếu đoạn văn không đủ thông tin để tạo thẻ chất lượng, hãy bỏ qua đoạn văn đó.
- Trả về JSON: {json_format}
- `chunk_id` phải khớp chính xác với `id` trong thẻ <chunk> mà bạn lấy thông tin.
{feedback_str}
{f"ĐỊNH HƯỚNG NGƯỜI DÙNG: {user_desire}" if user_desire else ""}"""

        user_prompt = f"<context>\n{context}\n</context>"

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            content = response.choices[0].message.content
            validated_content = json_guard.validate(content).validated_output
            parsed = json.loads(validated_content)
            in_t, out_t = response.usage.prompt_tokens, response.usage.completion_tokens
            self.log_cost(self.model_name, in_t, out_t, "Generate Questions")
            
            run = get_current_run_tree()
            if run:
                run.add_metadata({"prompt_tokens": in_t, "completion_tokens": out_t})
            return parsed.get("questions", []), in_t, out_t
        except Exception as e:
            print(f"    ❌ Lỗi generate_questions: {e}")
            return [], 0, 0

    # ------------------------------------------------------------------ #
    # Generate Answers
    # ------------------------------------------------------------------ #
    @traceable(name="Generation: Answers", run_type="llm", tags=["gen_answers"])
    def generate_answers(self, context, questions, user_desire=""):
        if not questions: return [], 0, 0

        system_prompt = f"""Bạn là AI tạo Flashcard chuyên nghiệp. Nhiệm vụ của bạn là tạo câu trả lời ĐẦY ĐỦ VÀ CHI TIẾT NHẤT dựa trên <context>.

QUY TẮC SẮT ĐÁ:
1. CHỈ DÙNG CONTEXT: Tuyệt đối không tự bịa. Nếu không thấy trong Context, ghi "Không tìm thấy thông tin trong tài liệu".
2. TRẢ LỜI ĐẦY ĐỦ: Liệt kê tất cả các ý chính/bullet points tìm thấy.
3. TỰ PHẢN TƯ: Đối soát kỹ câu trả lời với context trước khi xuất JSON.

{f"ĐỊNH HƯỚNG NGƯỜI DÙNG: {user_desire}" if user_desire else ""}
TRẢ VỀ JSON: {{"answers": ["...", "...", ...]}} theo đúng thứ tự câu hỏi."""

        questions_list = "\n".join([f"Q{i+1}: {q.get('question', '')} (Level: {q.get('level', 'N/A')})" for i, q in enumerate(questions)])
        user_prompt = f"<context>\n{context}\n</context>\n\n<questions>\n{questions_list}\n</questions>"

        # Language mode: use Argos
        if "[MODE_LANGUAGE]" in user_desire and HAS_ARGOS:
            answers = []
            for q in questions:
                try:
                    answers.append(argos_translate.translate(q.get('question', ''), "en", "vi"))
                except Exception:
                    answers.append("N/A")
            return answers, 0, 0

        try:
            response = self.client.chat.completions.create(
                model=self.answer_model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content
            validated_content = json_guard.validate(content).validated_output
            parsed = json.loads(validated_content)
            in_t, out_t = response.usage.prompt_tokens, response.usage.completion_tokens
            self.log_cost(self.answer_model_name, in_t, out_t, "Generate Answers")
            
            run = get_current_run_tree()
            if run:
                run.add_metadata({"prompt_tokens": in_t, "completion_tokens": out_t})
            return parsed.get("answers", []), in_t, out_t
        except Exception as e:
            print(f"    ❌ Lỗi generate_answers: {e}")
            return [], 0, 0

    # ------------------------------------------------------------------ #
    # Vocabulary helper
    # ------------------------------------------------------------------ #
    def _process_vocabulary_flashcards(self, words, chunk_results=None, _log_func=None, num_limit=999):
        def _log(msg):
            if _log_func: _log_func(msg)
            else: print(msg)

        from concurrent.futures import ThreadPoolExecutor

        def process_single_word(word):
            try:
                translated = "N/A"
                if HAS_DEEP_TRANSLATOR:
                    translated = GoogleTranslator(source='en', target='vi').translate(word)
                elif HAS_ARGOS:
                    translated = argos_translate.translate(word, "en", "vi")

                ipa = ""
                if HAS_IPA:
                    raw = eng_to_ipa.convert(word)
                    ipa = f"/{raw}/" if raw and '*' not in raw else ""
                if not ipa:
                    try:
                        resp = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=[{"role": "user", "content": f"Chỉ trả về phiên âm IPA của từ \"{word}\". Ví dụ: /ˈæp.əl/."}],
                            temperature=0, max_tokens=20
                        )
                        ipa = resp.choices[0].message.content.strip()
                        self.log_cost(self.model_name, resp.usage.prompt_tokens, resp.usage.completion_tokens, "IPA Lookup")
                    except Exception: pass

                pos = "từ"
                if HAS_NLTK:
                    tags = pos_tag(word_tokenize(word))
                    if tags: pos = map_pos_to_vn(tags[0][1])

                card_id = uuid.uuid4().hex
                audio_file = ""
                try:
                    from gtts import gTTS
                    audio_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), f"audio_{card_id}.mp3")
                    gTTS(text=word, lang='en', slow=False).save(audio_path)
                    audio_file = f"audio_{card_id}.mp3"
                except Exception: pass

                word_lower = word.lower()
                chunk_bboxes = []
                context_text = ""
                if chunk_results:
                    for chunk in chunk_results:
                        if word_lower in chunk.get("text", "").lower():
                            chunk_bboxes = chunk.get("bboxes", [])
                            context_text = chunk.get("text", "")
                            break
                            
                return {"id": card_id, "level": "Từ vựng", "question": word,
                        "phonetic": ipa, "part_of_speech": pos, "answer": translated,
                        "audio": audio_file, "bboxes": chunk_bboxes, "context": context_text}
            except Exception as e:
                print(f"    ⚠️ Lỗi xử lý từ '{word}': {e}")
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:  # Giảm từ 10 → 2 để tránh OOM trên Render 512MB
            results = list(executor.map(process_single_word, words))

        return [r for r in results if r is not None][:num_limit]

    # ------------------------------------------------------------------ #
    # Generate Flashcards (RAG-based)
    # ------------------------------------------------------------------ #
    @traceable(name="Pipeline: Generate Flashcards", run_type="chain", tags=["pipeline_flashcards"])
    def generate_flashcards(self, chunk_results, num_flashcard=3, status_callback=None, user_desire="", user_id=None):
        def _log(msg):
            print(msg)
            if status_callback: status_callback(msg)

        if not chunk_results:
            _log("⚠️ Ngữ cảnh trống.")
            return "Ngữ cảnh trống."

        num_flashcard = int(num_flashcard) if str(num_flashcard).isdigit() else 3
        num_chunks = len(chunk_results)
        
        # MLOps: Giới hạn số thẻ tạo ra dựa trên số chunk để tránh AI bịa chuyện (Hallucination)
        # Mỗi chunk chỉ nên gánh tối đa 3 thẻ. Đảm bảo tối thiểu vẫn cho tạo 5 thẻ.
        max_allowed_cards = max(num_chunks * 3, 5)
        if num_flashcard > max_allowed_cards:
            _log(f"  ⚠️ CẢNH BÁO: Số thẻ yêu cầu ({num_flashcard}) quá lớn so với ngữ cảnh ({num_chunks} chunks).")
            _log(f"  🔄 Tự động điều chỉnh số thẻ xuống mức an toàn: {max_allowed_cards} thẻ để đảm bảo chất lượng.")
            num_flashcard = max_allowed_cards
            
        _log(f"  🎯 Mục tiêu: Tạo {num_flashcard} thẻ từ {num_chunks} chunks")

        current_mode = "vocabulary" if "[MODE_LANGUAGE]" in user_desire else "content"
        feedback_str = self.get_smart_feedback(user_id, current_mode) if user_id else ""
        if feedback_str:
            _log("  💡 Đã tích hợp 3 bài học từ lịch sử sửa đổi (Data Flywheel).")

        # Select chunks to process (sample evenly if too many chunks)
        selected_chunks = []
        chunks_to_pick = min(num_chunks, max(num_flashcard, 5))
        if chunks_to_pick <= 1:
            selected_chunks = chunk_results[:1]
        else:
            for i in range(chunks_to_pick):
                idx = int(i * (num_chunks - 1) / (chunks_to_pick - 1))
                if chunk_results[idx] not in selected_chunks:
                    selected_chunks.append(chunk_results[idx])
        
        if not selected_chunks:
            selected_chunks = chunk_results

        # Batch into groups of 5
        batch_size = 5
        merged_parts = []
        total_parts = (len(selected_chunks) + batch_size - 1) // batch_size
        
        cards_per_part = num_flashcard // total_parts if total_parts > 0 else num_flashcard
        remainder = num_flashcard % total_parts if total_parts > 0 else 0

        for i in range(0, len(selected_chunks), batch_size):
            batch = selected_chunks[i:i + batch_size]
            tagged_text = "".join(f"<chunk id=\"{j}\">\n{c['text']}\n</chunk>\n\n" for j, c in enumerate(batch))
            
            num_to_gen = cards_per_part + (1 if remainder > 0 else 0)
            remainder -= 1
            
            merged_parts.append({"tagged_text": tagged_text, "chunks_meta": batch, "num_to_gen": num_to_gen})

        all_flashcards = []
        total_in = total_out = 0

        # --- Vocabulary mode (no LLM) ---
        if "[MODE_LANGUAGE]" in user_desire and HAS_WORDFREQ and (HAS_DEEP_TRANSLATOR or HAS_ARGOS):
            import re
            all_text = " ".join([c['text'] for c in chunk_results])
            words = wordfreq_tokenize(all_text, "en")
            capitalized = set(w.lower() for w in re.findall(r'\b[A-Z][a-z]+\b', all_text))
            word_scores = [(w, zipf_frequency(w, 'en')) for w in set(words)
                          if len(w) >= 3 and w.isalpha() and w.lower() not in capitalized
                          and 0 < zipf_frequency(w, 'en') <= 5.0]
            word_scores.sort(key=lambda x: x[1])
            candidates = [w for w, _ in word_scores[:num_flashcard * 3]]
            all_flashcards = self._process_vocabulary_flashcards(candidates, chunk_results, _log, num_limit=num_flashcard)
            merged_parts = [] # Đặt rỗng để bỏ qua phần sinh thẻ bằng LLM bên dưới, tiến thẳng tới tạo PDF Highlight

        # --- Normal LLM mode ---
        for idx, part_data in enumerate(merged_parts):
            sub_num = part_data["num_to_gen"]
            if sub_num <= 0: continue
            _log(f"    ⏳ Đang tạo {sub_num} câu hỏi (Phần {idx + 1}/{len(merged_parts)})...")
            questions, in_q, out_q = self.generate_questions(part_data["tagged_text"], sub_num, user_desire, feedback_str=feedback_str)
            if len(questions) > sub_num:
                questions = questions[:sub_num]

            if questions:
                answers, in_a, out_a = self.generate_answers(part_data["tagged_text"], questions, user_desire)
                
                # Pre-compute chunk embeddings: batch 1 lần duy nhất thay vì N lần trong loop
                chunk_texts = [cm.get("text", "") or "empty" for cm in part_data["chunks_meta"]]
                try:
                    chunk_embeddings = self.embed_text(chunk_texts)  # 1 API call cho toàn bộ batch
                except Exception as e:
                    logger.warning(f"Batch embedding failed, fallback to empty: {e}")
                    chunk_embeddings = [[] for _ in chunk_texts]

                # Pre-compute Q & A embeddings: 2 batch calls thay vì 2×N sequential calls
                q_texts = [q_obj.get("question", "") or "empty" for q_obj in questions]
                a_texts = [answers[i] if i < len(answers) else "empty" for i in range(len(questions))]
                try:
                    all_qa_texts = q_texts + a_texts  # Ghép lại → 1 API call duy nhất
                    all_qa_embs = self.embed_text(all_qa_texts)
                    q_embeddings = all_qa_embs[:len(q_texts)]
                    a_embeddings = all_qa_embs[len(q_texts):]
                    logger.info(f"[Gen] Batch embedded {len(all_qa_texts)} Q+A texts in 1 API call")
                except Exception as e:
                    logger.warning(f"Batch Q+A embedding failed, will fallback per-card: {e}")
                    q_embeddings = [None] * len(questions)
                    a_embeddings = [None] * len(questions)
                
                for i, q_obj in enumerate(questions):
                    ans_text = answers[i] if i < len(answers) else "Không có câu trả lời."
                    try:
                        llm_c_id = int(q_obj.get("chunk_id", 0))
                        # Tìm chunk bằng Câu hỏi (dùng pre-computed embedding)
                        q_text = q_obj.get("question", "")
                        id_cau_hoi = self._find_best_chunk_for_card(
                            q_text, part_data["chunks_meta"], chunk_embeddings,
                            qa_embedding=q_embeddings[i]
                        )
                        
                        # Tìm chunk bằng Câu trả lời (dùng pre-computed embedding)
                        id_cau_tra_loi = self._find_best_chunk_for_card(
                            ans_text, part_data["chunks_meta"], chunk_embeddings,
                            qa_embedding=a_embeddings[i]
                        )
                        
                        # Với thẻ từ vựng, câu trả lời là tiếng Việt nên sẽ không match được với PDF tiếng Anh.
                        # Do đó phải dùng id_cau_hoi (từ tiếng Anh) để làm Highlight.
                        if q_obj.get("level", "") == "Từ vựng":
                            chunk_meta = part_data["chunks_meta"][id_cau_hoi]
                        else:
                            # Dùng id_cau_tra_loi để làm Highlight cho các thẻ thông thường
                            chunk_meta = part_data["chunks_meta"][id_cau_tra_loi]
                        
                        target_bboxes = chunk_meta.get("bboxes", [])
                    except Exception:
                        target_bboxes = []
                        chunk_meta = {}
                        id_cau_hoi = 0
                        id_cau_tra_loi = 0
                        
                    context_text = chunk_meta.get("text", "")
                    if q_obj.get("level", "") == "Từ vựng" and q_obj.get("question"):
                        import re
                        word = q_obj.get("question")
                        # Highlight từ vựng trong văn bản gốc bằng thẻ <mark> (chỉ highlight 1 lần đầu tiên)
                        context_text = re.sub(rf'(?i)\b({re.escape(word)})\b', r'<mark>\1</mark>', context_text, count=1)

                    all_flashcards.append({
                        "id": uuid.uuid4().hex, "level": q_obj.get("level", "N/A"),
                        "question": q_obj.get("question", ""), "phonetic": q_obj.get("phonetic", ""),
                        "part_of_speech": q_obj.get("part_of_speech", ""), "answer": ans_text,
                        "bboxes": target_bboxes,
                        "context": context_text,
                        "llm_chunk_id": llm_c_id,
                        "id_cau_hoi": id_cau_hoi,
                        "id_cau_tra_loi": id_cau_tra_loi
                    })
                total_in += (in_q + in_a)
                total_out += (out_q + out_a)

        _log(f"\n📈 TỔNG CỘNG TOKEN SỬ DỤNG: Input={total_in}, Output={total_out}")

        # Pre-generate PDF highlights
        if self.current_pdf_path and all_flashcards:
            _log(f"\n📄 Đang tạo file highlight cho {len(all_flashcards)} thẻ...")
            try:
                import fitz
                src_doc = fitz.open(self.current_pdf_path)
                for idx_card, card in enumerate(all_flashcards):
                    if not card.get("bboxes"): continue
                    
                    # Thêm log tiến độ để giữ kết nối (keep-alive SSE) tránh Render timeout
                    _log(f"  ... Đang highlight thẻ {idx_card + 1}/{len(all_flashcards)} ...")
                    
                    fname = f"card_highlight_{card['id']}.pdf"
                    # Lưu vào thư mục gốc project để library.py có thể tìm và upload lên Supabase
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    fpath = os.path.join(project_root, fname)
                        
                    # Thu thập các trang cần trích xuất
                    pages_set = set()
                    for item in card["bboxes"]:
                        p = item.get("p")
                        if p: pages_set.add(p - 1)
                    pages_list = sorted(list(pages_set))
                    
                    if not pages_list: continue
                    
                    # Tạo file PDF mới chỉ chứa các trang này
                    doc = fitz.open()
                    page_map = {}
                    for new_pi, old_pi in enumerate(pages_list):
                        doc.insert_pdf(src_doc, from_page=old_pi, to_page=old_pi)
                        page_map[old_pi] = new_pi
                    
                    # Vẽ highlight lên file PDF mới
                    new_bboxes = []
                    is_vocab = (card.get("level", "") == "Từ vựng")
                    
                    if is_vocab and card.get("question"):
                        word_to_find = card.get("question", "")
                        found_highlight = False
                        for old_pi, new_pi in page_map.items():
                            if found_highlight: break
                            page = doc[new_pi]
                            rects = page.search_for(word_to_find)
                            if rects:
                                r = rects[0] # Chỉ lấy kết quả đầu tiên
                                page.add_highlight_annot(r)
                                new_bboxes.append({
                                    "p": new_pi + 1,
                                    "b": [r.x0, r.y0, r.x1, r.y1]
                                })
                                found_highlight = True
                                
                    # Fallback: Nếu không phải thẻ từ vựng hoặc tìm từ vựng không ra, highlight cả đoạn
                    if not new_bboxes:
                        for item in card["bboxes"]:
                            p, bbox = item.get("p"), item.get("b")
                            if p and bbox:
                                old_pi = p - 1
                                new_pi = page_map.get(old_pi)
                                if new_pi is not None:
                                    r = fitz.Rect(bbox)
                                    if not r.is_empty and not r.is_infinite:
                                        doc[new_pi].add_highlight_annot(r)
                                        # Cập nhật lại số trang mới cho bboxes để frontend hiển thị đúng
                                        item_copy = dict(item)
                                        item_copy["p"] = new_pi + 1
                                        new_bboxes.append(item_copy)
                                    
                    doc.save(fpath, garbage=3, deflate=True)
                    doc.close()
                    card["bboxes"] = new_bboxes
                    
                    # Chuyển file PDF highlight thành base64 để trả về cho frontend (xem/edit ngay)
                    # GIỮ file trên server để library.py upload lên Supabase khi user nhấn "Lưu bộ thẻ"
                    # File sẽ được dọn bởi cleanup_local_assets() khi tạo bộ thẻ mới
                    try:
                        import base64
                        with open(fpath, "rb") as f:
                            card["highlight_pdf_base64"] = base64.b64encode(f.read()).decode('utf-8')
                    except Exception as e_b64:
                        _log(f"  ⚠️ Lỗi mã hóa base64 cho file highlight: {e_b64}")
                src_doc.close()
                _log("  ✅ Đã hoàn tất tạo tài liệu bổ trợ.")
            except Exception as e:
                _log(f"  ⚠️ Lỗi khi tạo file highlight: {e}")

        return json.dumps({"flashcards": all_flashcards, "usage": {"input": total_in, "output": total_out}}, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ #
    # Generate No-RAG
    # ------------------------------------------------------------------ #
    @traceable(name="Generate No-RAG", run_type="chain")
    def generate_no_rag(self, topic, num_flashcard=3, status_callback=None, user_desire="", user_id=None):
        def _log(msg):
            print(msg)
            if status_callback: status_callback(msg)

        _log(f"  🧠 Đang tạo flashcard từ kiến thức hệ thống cho chủ đề: {topic}")
        is_vocab = "[MODE_LANGUAGE]" in user_desire
        feedback_str = self.get_smart_feedback(user_id, "vocabulary" if is_vocab else "content") if user_id else ""

        if is_vocab:
            system_prompt = f"""Bạn là AI chuyên gia ngôn ngữ.
Hãy liệt kê danh sách CHÍNH XÁC {num_flashcard} từ vựng tiếng Anh quan trọng liên quan đến: "{topic}".
Trả về JSON: {{"flashcards": [{{"question": "Word 1"}}, ...]}}"""
        else:
            system_prompt = f"""Bạn là AI tạo Flashcard chuyên nghiệp.
Hãy tạo CHÍNH XÁC {num_flashcard} câu hỏi và câu trả lời flashcard về chủ đề: "{topic}".
Các câu hỏi nên bao gồm: Nhận biết, Thông hiểu, Vận dụng.
{f"Định hướng bổ sung: {user_desire}" if user_desire else ""}
Trả về JSON: {{"flashcards": [{{"id": 0, "level": "Nhận biết", "question": "...", "answer": "..."}}]}}"""

        system_prompt += f"\nLưu ý: Luôn trả về đúng số lượng {num_flashcard} thẻ."

        try:
            all_flashcards, total_in, total_out = [], 0, 0
            batch_size = 10
            num_batches = (num_flashcard + batch_size - 1) // batch_size

            for i in range(num_batches):
                current_batch_size = min(batch_size, num_flashcard - len(all_flashcards))
                _log(f"    ⏳ Đang tạo đợt {i+1}/{num_batches} ({current_batch_size} thẻ)...")
                batch_prompt = system_prompt + f"\nLưu ý: Trong đợt này, hãy tạo ĐÚNG {current_batch_size} thẻ."

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": batch_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                content = response.choices[0].message.content
                validated_content = json_guard.validate(content).validated_output
                batch_cards = json.loads(validated_content).get("flashcards", [])[:current_batch_size]

                if is_vocab:
                    words = [c.get("question", c.get("word", c.get("term", ""))) for c in batch_cards]
                    words = [w for w in words if w]
                    all_flashcards.extend(self._process_vocabulary_flashcards(words, _log_func=_log, num_limit=current_batch_size))
                else:
                    for card in batch_cards:
                        card["id"] = uuid.uuid4().hex
                        card.setdefault("bboxes", [])
                        all_flashcards.append(card)

                total_in += response.usage.prompt_tokens
                total_out += response.usage.completion_tokens
                self.log_cost(self.model_name, response.usage.prompt_tokens, response.usage.completion_tokens, "Generate No-RAG")
                if len(all_flashcards) >= num_flashcard: break

            _log(f"\n📈 TỔNG CỘNG TOKEN: Input={total_in}, Output={total_out}")
            return json.dumps({"flashcards": all_flashcards, "usage": {"input": total_in, "output": total_out}}, ensure_ascii=False, indent=2)
        except Exception as e:
            _log(f"    ❌ Lỗi generate_no_rag: {e}")
            return json.dumps({"flashcards": [], "error": str(e)}, ensure_ascii=False)

