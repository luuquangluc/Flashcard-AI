"""
rag_core.py - Khởi tạo, cấu hình, nhúng vector, cache và ghi log chi phí API.
"""
import os
import json
import hashlib
import logging
import datetime
from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)
from config.settings import (
    OPENAI_API_KEY, API_PRICES, COST_FILE, LOCAL_EMBEDDING_MODEL
)

try:
    from langsmith import wrap_openai
    HAS_LANGSMITH = True
except ImportError:
    HAS_LANGSMITH = False
    def wrap_openai(client): return client


class RAGCore:
    """Phần lõi: Khởi tạo, client, embedding, cache, log chi phí."""

    def __init__(self, model_name="gpt-4o-mini", answer_model_name="gpt-4o-mini", embedding_model_name="text-embedding-3-small"):
        self.model_name = model_name
        self.answer_model_name = answer_model_name
        self.embedding_model_name = embedding_model_name

        has_openai_key = bool(OPENAI_API_KEY)
        self.use_openai_embeddings = has_openai_key

        try:
            self.client = wrap_openai(OpenAI())
        except Exception:
            self.client = wrap_openai(OpenAI(api_key="dummy-key"))

        if self.use_openai_embeddings:
            print(f"  🔄 Đang cấu hình sử dụng OpenAI Embedding ({self.embedding_model_name})...")
            self.embedding_model = None
        else:
            self.embedding_model_name = LOCAL_EMBEDDING_MODEL
            print(f"  🔄 Không có OPENAI_API_KEY, đang tải mô hình Embedding cục bộ ({self.embedding_model_name})...")
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(self.embedding_model_name)

        self.bm25 = None
        self.chunks = []
        self.is_structure_good = True
        self.current_pdf_path = None
        self.doc_name = None
        self.supabase = None

        self._chroma_client = None
        self._col_titles = None
        self._col_content = None

        from modules.image.vision_processor import VisionProcessor
        self.vision_processor = VisionProcessor(api_key=OPENAI_API_KEY)

        self.cost_file = COST_FILE

    # ------------------------------------------------------------------ #
    # ChromaDB lazy properties
    # ------------------------------------------------------------------ #
    @property
    def chroma_client(self):
        if self._chroma_client is None:
            import chromadb
            from chromadb.config import Settings
            # Tắt telemetry để tránh lỗi capture() làm rác log và tiết kiệm tài nguyên
            self._chroma_client = chromadb.EphemeralClient(
                settings=Settings(anonymized_telemetry=False)
            )
        return self._chroma_client

    @property
    def col_titles(self):
        if self._col_titles is None:
            # Ép ChromaDB không tải model mặc định để tiết kiệm RAM
            self._col_titles = self.chroma_client.get_or_create_collection(
                name="section_titles", 
                embedding_function=None
            )
        return self._col_titles

    @property
    def col_content(self):
        if self._col_content is None:
            # Ép ChromaDB không tải model mặc định để tiết kiệm RAM
            self._col_content = self.chroma_client.get_or_create_collection(
                name="section_content", 
                embedding_function=None
            )
        return self._col_content

    # ------------------------------------------------------------------ #
    # Cost logging
    # ------------------------------------------------------------------ #
    def log_cost(self, model, prompt_tokens, completion_tokens, feature_name="General"):
        """Tính toán và lưu chi phí API vào file JSON."""
        prices = API_PRICES
        p = prices.get(model.lower(), {"in": 0, "out": 0})
        comp_tokens = completion_tokens if completion_tokens is not None else 0
        cost = (prompt_tokens * p["in"]) + (comp_tokens * p["out"])

        new_entry = {
            "timestamp":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feature":      feature_name,
            "model":        model,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "cost_usd":     round(cost, 8),
        }

        try:
            logs = []
            if os.path.exists(self.cost_file):
                with open(self.cost_file, "r", encoding="utf-8") as f:
                    try:
                        logs = json.load(f)
                    except Exception:
                        logs = []
            logs.append(new_entry)
            with open(self.cost_file, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error logging cost to JSON: {e}")

        return cost

    # ------------------------------------------------------------------ #
    # Embedding
    # ------------------------------------------------------------------ #
    def embed_text(self, text_or_texts):
        is_list = isinstance(text_or_texts, list)
        inputs = text_or_texts if is_list else [text_or_texts]
        safe_inputs = [t if t and t.strip() else "empty" for t in inputs]

        if self.use_openai_embeddings:
            try:
                all_embeddings = []
                for i in range(0, len(safe_inputs), 100):
                    batch = safe_inputs[i:i + 100]
                    
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            current_batch = batch
                            # Chỉ thực hiện cắt ngắn ở lần thử cuối cùng (khi các lần thử nguyên bản đã thất bại)
                            if attempt == max_retries - 1:
                                current_batch = [t[:30000] for t in batch]
                                print(f"  ⚠️ Lần thử cuối (lần {attempt+1}): Đã tự động cắt ngắn văn bản để tránh lỗi token limit.")
                            elif attempt > 0:
                                print(f"  ⚠️ Retry OpenAI Embedding (lần {attempt+1}): Giữ nguyên văn bản...")
                                
                            response = self.client.embeddings.create(
                                model=self.embedding_model_name,
                                input=current_batch
                            )
                            self.log_cost(self.embedding_model_name, response.usage.prompt_tokens, 0, "Embedding")
                            all_embeddings.extend([d.embedding for d in response.data])
                            break  # Thành công thì thoát vòng lặp retry
                        except Exception as batch_err:
                            if attempt == max_retries - 1:
                                raise batch_err  # Hết lượt retry -> ném lỗi ra ngoài để fallback cục bộ
                            else:
                                logger.warning(f"  ⚠️ Lỗi OpenAI Embedding batch (lần {attempt+1}): {batch_err}")

                return all_embeddings if is_list else all_embeddings[0]
            except Exception as e:
                print(f"  ⚠️ Lỗi gọi OpenAI Embedding sau khi retry, chuyển sang chạy cục bộ: {e}")
                self.use_openai_embeddings = False

        from sentence_transformers import SentenceTransformer
        if getattr(self, "embedding_model", None) is None:
            self.embedding_model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
        embeddings = self.embedding_model.encode(safe_inputs, normalize_embeddings=True).tolist()
        return embeddings if is_list else embeddings[0]

    # ------------------------------------------------------------------ #
    # File hash & Supabase cache
    # ------------------------------------------------------------------ #
    def get_file_hash(self, file_path):
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def check_cache_supabase(self, file_hash):
        if not self.supabase: return None
        try:
            resp = self.supabase.table('document_cache').select('chunks_json').eq('file_hash', file_hash).execute()
            if resp.data:
                return resp.data[0]['chunks_json']
        except Exception as e:
            print(f"  ⚠️ Lỗi kiểm tra cache Supabase: {e}")
        return None

    def save_cache_supabase(self, file_hash, doc_name, chunks):
        if not self.supabase: return
        try:
            self.supabase.table('document_cache').upsert({
                "file_hash": file_hash,
                "document_name": doc_name,
                "chunks_json": chunks
            }).execute()
            print(f"  ✅ Đã lưu cache tài liệu lên Supabase ({file_hash[:8]}).")
        except Exception as e:
            print(f"  ⚠️ Lỗi lưu cache Supabase: {e}")

    # ------------------------------------------------------------------ #
    # Data Flywheel: Smart feedback
    # ------------------------------------------------------------------ #
    def get_smart_feedback(self, user_id, current_mode):
        if not self.supabase or not user_id:
            return ""
        current_doc = self.doc_name
        feedback_data = []
        try:
            if current_doc:
                resp = self.supabase.table('ai_feedback') \
                    .select('*') \
                    .eq('user_id', user_id) \
                    .eq('document_name', current_doc) \
                    .eq('mode', current_mode) \
                    .eq('feedback_type', 'EDIT') \
                    .order('created_at', desc=True) \
                    .limit(3).execute()
                feedback_data = resp.data if resp.data else []

            if len(feedback_data) < 3:
                needed = 3 - len(feedback_data)
                exclude_ids = [f['id'] for f in feedback_data]
                query = self.supabase.table('ai_feedback') \
                    .select('*') \
                    .eq('user_id', user_id) \
                    .eq('mode', current_mode) \
                    .eq('feedback_type', 'EDIT')
                if exclude_ids:
                    query = query.not_.in_('id', exclude_ids)
                resp_global = query.order('created_at', desc=True).limit(needed).execute()
                if resp_global.data:
                    feedback_data.extend(resp_global.data)

            if not feedback_data:
                return ""

            logger.info(f"  💡 Đã tích hợp {len(feedback_data)} bài học từ lịch sử sửa đổi (Data Flywheel).")
            prompt_msg = "\n--- BÀI HỌC TỪ CÁC LẦN SỬA ĐỔI TRƯỚC (FEW-SHOT) ---\n"
            for fb in feedback_data:
                orig, corr = fb['original_card'], fb['corrected_card']
                prompt_msg += f"- Tránh tạo: Q: {orig['question']} | A: {orig['answer']}\n"
                prompt_msg += f"- Hãy tạo kiểu: Q: {corr['question']} | A: {corr['answer']}\n"
            prompt_msg += "--------------------------------------------------\n"
            return prompt_msg
        except Exception as e:
            print(f"  ⚠️ Lỗi lấy feedback: {e}")
            return ""
