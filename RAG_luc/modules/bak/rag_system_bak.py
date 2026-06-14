import os
import sys
import json
import uuid
import logging
import hashlib

logger = logging.getLogger(__name__)
# RAG Flashcard System v2.1 - Added Page Range Filtering and Flashcard Editing
import chromadb
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file up one directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

try:
    from langsmith import traceable, wrap_openai, get_current_run_tree
    HAS_LANGSMITH = True
except ImportError:
    HAS_LANGSMITH = False
    # Fallback dummies if langsmith is not installed
    def traceable(name=None, run_type=None, **kwargs):
        def decorator(func):
            return func
        return decorator
    def wrap_openai(client):
        return client
    def get_current_run_tree():
        return None

# Import Argos Translate for offline vocabulary translation (fallback)
try:
    import argostranslate.package
    import argostranslate.translate as argos_translate
    HAS_ARGOS = True
except ImportError:
    HAS_ARGOS = False

# Import deep-translator for accurate online translation (primary)
try:
    from deep_translator import GoogleTranslator
    HAS_DEEP_TRANSLATOR = True
except ImportError:
    HAS_DEEP_TRANSLATOR = False

# Import eng_to_ipa for phonetic transcription
try:
    import eng_to_ipa
    HAS_IPA = True
except ImportError:
    HAS_IPA = False

# Import wordfreq for rare word extraction
try:
    from wordfreq import zipf_frequency, tokenize as wordfreq_tokenize
    HAS_WORDFREQ = True
except ImportError:
    HAS_WORDFREQ = False

# Import NLTK for POS tagging
try:
    import nltk
    from nltk import pos_tag, word_tokenize
    # Tải dữ liệu cần thiết (âm thầm)
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False

def map_pos_to_vn(tag):
    """Chuyển đổi tag NLTK sang tiếng Việt"""
    if tag.startswith('NN'): return "danh từ"
    if tag.startswith('VB'): return "động từ"
    if tag.startswith('JJ'): return "tính từ"
    if tag.startswith('RB'): return "trạng từ"
    if tag.startswith('PR'): return "đại từ"
    if tag.startswith('IN'): return "giới từ"
    if tag.startswith('CC'): return "liên từ"
    if tag.startswith('CD'): return "số từ"
    return "từ"

# Import modularized PDF processing logic
from pdf_processor import chunk_pdf_auto
from vision_processor import VisionProcessor

# Đảm bảo terminal Windows hỗ trợ tiếng Việt
if sys.platform == "win32":
    import io
    sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='utf-8', errors='replace')
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')


# ================================================================
# RAG SYSTEM CLASS
# ================================================================

class RAGSystem:
    def __init__(self, model_name="gpt-4o-mini", answer_model_name="gpt-4o-mini", embedding_model_name="text-embedding-3-small"):
        self.model_name = model_name
        self.answer_model_name = answer_model_name
        self.embedding_model_name = embedding_model_name
        
        # Check API key explicitly
        has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        self.use_openai_embeddings = has_openai_key
        
        # Tự động hóa tracing OpenAI qua LangSmith
        try:
            self.client = wrap_openai(OpenAI())
        except Exception:
            self.client = wrap_openai(OpenAI(api_key="dummy-key"))
            
        if self.use_openai_embeddings:
            print(f"  🔄 Đang cấu hình sử dụng OpenAI Embedding ({self.embedding_model_name})...")
            self.embedding_model = None
        else:
            self.embedding_model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            print(f"  🔄 Không có OPENAI_API_KEY, đang tải mô hình Embedding cục bộ ({self.embedding_model_name})...")
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
        self.bm25 = None
        self.chunks = []
        self.is_structure_good = True
        self.current_pdf_path = None
        self.doc_name = None # Tên file gốc người dùng tải lên
        self.supabase = None # Will be set by app_rag.py
        
        # Lazy initialization for ChromaDB
        self._chroma_client = None
        self._col_titles = None
        self._col_content = None
        
        # Initialize VisionProcessor
        self.vision_processor = VisionProcessor(api_key=os.environ.get("OPENAI_API_KEY"))
        
        self.cost_file = os.path.join(os.path.dirname(__file__), "api_costs.json")

    def log_cost(self, model, prompt_tokens, completion_tokens, feature_name="General"):
        """Tính toán và lưu chi phí API vào file JSON."""
        prices = {
            "gpt-4o-mini": {"in": 0.15 / 1_000_000, "out": 0.60 / 1_000_000},
            "gpt-4o": {"in": 5.00 / 1_000_000, "out": 15.00 / 1_000_000},
            "text-embedding-3-small": {"in": 0.02 / 1_000_000, "out": 0}
        }
        
        p = prices.get(model.lower(), {"in": 0, "out": 0})
        # Embeddings don't have completion tokens
        comp_tokens = completion_tokens if completion_tokens is not None else 0
        cost = (prompt_tokens * p["in"]) + (comp_tokens * p["out"])
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_entry = {
            "timestamp": timestamp,
            "feature": feature_name,
            "model": model,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "cost_usd": round(cost, 8)
        }
        
        try:
            logs = []
            if os.path.exists(self.cost_file):
                with open(self.cost_file, "r", encoding="utf-8") as f:
                    try:
                        logs = json.load(f)
                    except:
                        logs = []
            
            logs.append(new_entry)
            
            with open(self.cost_file, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error logging cost to JSON: {e}")
        
        return cost

    @property
    def chroma_client(self):
        if self._chroma_client is None:
            try:
                self._chroma_client = chromadb.EphemeralClient()
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB EphemeralClient: {e}")
                # Fallback or re-raise if absolutely necessary
                raise
        return self._chroma_client

    @property
    def col_titles(self):
        if self._col_titles is None:
            self._col_titles = self.chroma_client.get_or_create_collection(name="section_titles")
        return self._col_titles

    @property
    def col_content(self):
        if self._col_content is None:
            self._col_content = self.chroma_client.get_or_create_collection(name="section_content")
        return self._col_content

    def get_smart_feedback(self, user_id, current_mode):
        """
        Lấy tối đa 3 feedback thông minh:
        1. Ưu tiên PDF hiện tại + đúng Mode
        2. Nếu không có, lấy 3 cái mới nhất của đúng Mode
        """
        if not self.supabase:
            logger.warning("  ⚠️ Data Flywheel: Chưa cấu hình Supabase Client.")
            return ""
            
        if not user_id:
            logger.warning("  ⚠️ Data Flywheel: Thiếu User ID để lấy feedback.")
            return ""

        current_doc = self.doc_name
        feedback_data = []
        
        logger.info(f"  🔍 Đang tìm kiếm bài học cũ (Doc: {current_doc}, Mode: {current_mode})...")

        try:
            # BƯỚC 1: Tìm feedback của CHÍNH PDF này + ĐÚNG Mode này
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

            # BƯỚC 2: Nếu không đủ 3 cái, lấy thêm từ các PDF khác nhưng cùng Mode
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
                orig = fb['original_card']
                corr = fb['corrected_card']
                prompt_msg += f"- Tránh tạo: Q: {orig['question']} | A: {orig['answer']}\n"
                prompt_msg += f"- Hãy tạo kiểu: Q: {corr['question']} | A: {corr['answer']}\n"
            prompt_msg += "--------------------------------------------------\n"
            return prompt_msg
        except Exception as e:
            print(f"  ⚠️ Lỗi lấy feedback: {e}")
            return ""

    def get_file_hash(self, file_path):
        """Tính mã MD5 của file để nhận diện cache."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def check_cache_supabase(self, file_hash):
        """Kiểm tra xem file đã được xử lý chưa trên Supabase."""
        if not self.supabase: return None
        try:
            resp = self.supabase.table('document_cache').select('chunks_json').eq('file_hash', file_hash).execute()
            if resp.data and len(resp.data) > 0:
                return resp.data[0]['chunks_json']
        except Exception as e:
            print(f"  ⚠️ Lỗi kiểm tra cache Supabase: {e}")
        return None

    def save_cache_supabase(self, file_hash, doc_name, chunks):
        """Lưu kết quả xử lý lên Supabase."""
        if not self.supabase: return
        try:
            data = {
                "file_hash": file_hash,
                "document_name": doc_name,
                "chunks_json": chunks
            }
            self.supabase.table('document_cache').upsert(data).execute()
            print(f"  ✅ Đã lưu cache tài liệu lên Supabase ({file_hash[:8]}).")
        except Exception as e:
            print(f"  ⚠️ Lỗi lưu cache Supabase: {e}")

    def parse_page_range(self, range_str):
        """Chuyển chuỗi '1-3, 5' thành set {1, 2, 3, 5}"""
        if not range_str or not range_str.strip():
            return None
        pages = set()
        try:
            parts = [p.strip() for p in range_str.split(',')]
            for part in parts:
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    for p in range(start, end + 1):
                        pages.add(p)
                else:
                    pages.add(int(part))
            return pages
        except Exception as e:
            print(f"  ⚠️ Lỗi parse dải trang '{range_str}': {e}")
            return None

    def is_chunk_in_range(self, chunk_page_str, requested_pages):
        """Kiểm tra xem chunk có thuộc dải trang yêu cầu không"""
        if not requested_pages:
            return True
        try:
            chunk_page_str = str(chunk_page_str)
            if "-" in chunk_page_str:
                start, end = map(int, chunk_page_str.split("-"))
                chunk_range = set(range(start, end + 1))
                return not chunk_range.isdisjoint(requested_pages)
            else:
                return int(chunk_page_str) in requested_pages
        except:
            return True # Mặc định cho phép nếu dữ liệu trang bị lỗi

    def embed_text(self, text_or_texts):
        is_list = isinstance(text_or_texts, list)
        inputs = text_or_texts if is_list else [text_or_texts]
        # Xử lý text rỗng để tránh lỗi API
        safe_inputs = [t if t and t.strip() else "empty" for t in inputs]
        
        if self.use_openai_embeddings:
            try:
                all_embeddings = []
                batch_size = 100
                for i in range(0, len(safe_inputs), batch_size):
                    batch = safe_inputs[i:i+batch_size]
                    response = self.client.embeddings.create(
                        model=self.embedding_model_name,
                        input=batch
                    )
                    prompt_tokens = response.usage.prompt_tokens
                    self.log_cost(self.embedding_model_name, prompt_tokens, 0, "Embedding")
                    all_embeddings.extend([data.embedding for data in response.data])
                return all_embeddings if is_list else all_embeddings[0]
            except Exception as e:
                print(f"  ⚠️ Lỗi gọi OpenAI Embedding, chuyển sang chạy cục bộ: {e}")
                self.use_openai_embeddings = False
                
        # Fallback local
        from sentence_transformers import SentenceTransformer
        if getattr(self, "embedding_model", None) is None:
            self.embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        embeddings = self.embedding_model.encode(safe_inputs, normalize_embeddings=True).tolist()
        return embeddings if is_list else embeddings[0]

    @traceable(name="Process PDF")
    def process_pdf(self, pdf_path, tesseract_cmd=None, dpi=150, max_chunk_size=800, min_chunk_size=300, overlap_size=100):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Không tìm thấy file: {pdf_path}")
            
        self.current_pdf_path = pdf_path
        file_hash = self.get_file_hash(pdf_path)
        
        # --- BƯỚC 1: KIỂM TRA CACHE SUPABASE ---
        print(f"  🔍 Đang kiểm tra cache cho tài liệu ({file_hash[:8]})...")
        cached_chunks = self.check_cache_supabase(file_hash)
        
        if cached_chunks:
            print("  🚀 [HIT] Tìm thấy cache! Đang nạp dữ liệu từ Supabase...")
            self.chunks = cached_chunks
            return self.index_chunks(self.chunks, skip_embedding_if_cached=True)

        # --- BƯỚC 2: XỬ LÝ MỚI NẾU KHÔNG CÓ CACHE ---
        print("  ⏳ [MISS] Không có cache. Bắt đầu xử lý OCR + Vision (Hybrid)...")
        chunks = chunk_pdf_auto(pdf_path, tesseract_cmd=tesseract_cmd, dpi=dpi, max_chunk_size=max_chunk_size, min_chunk_size=min_chunk_size, overlap_size=overlap_size, vision_processor=self.vision_processor)
        
        if chunks:
            # Index trước để có embeddings, sau đó mới lưu cache
            success = self.index_chunks(chunks)
            if success:
                self.save_cache_supabase(file_hash, self.doc_name, self.chunks)
            return success
            
        return False

    def index_chunks(self, chunks, skip_embedding_if_cached=False):
        """Indexes a list of chunks into ChromaDB and initializes BM25."""
        # --- Clear existing state for new document ---
        print("  🧹 Đang dọn dẹp dữ liệu cũ để nạp tài liệu mới...")
        try:
            self.chroma_client.delete_collection("section_titles")
            self.chroma_client.delete_collection("section_content")
        except Exception:
            pass
        
        # Re-fetch collection handles (reset to force lazy re-init)
        self._col_titles = None
        self._col_content = None
        self.bm25 = None
        
        if not chunks:
            print("  ⚠️ Không có chunk nào để index.")
            return False
        self.chunks = chunks
        
        # --- BATCH EMBEDDINGS ---
        enriched_texts = [item["enriched_text"] for item in self.chunks]
        breadcrumbs = [item.get("breadcrumb", "Không có tiêu đề") for item in self.chunks]
        
        # Kiểm tra xem đã có sẵn embedding trong cache chưa
        has_cached_embeddings = skip_embedding_if_cached and len(self.chunks) > 0 and "content_embedding" in self.chunks[0]

        if has_cached_embeddings:
            print("  ✅ Sử dụng Vector nhúng từ Cache (Supabase).")
            content_embeddings = [c["content_embedding"] for c in self.chunks]
            title_embeddings = [c["title_embedding"] for c in self.chunks]
        else:
            print("  ⏳ Đang tạo vector nhúng (batch embeddings)...")
            content_embeddings = self.embed_text(enriched_texts)
            title_embeddings = self.embed_text(breadcrumbs)
            # Gắn vào chunks để lưu cache sau này
            for i, c in enumerate(self.chunks):
                c["content_embedding"] = content_embeddings[i]
                c["title_embedding"] = title_embeddings[i]

        content_docs, content_metas, content_ids = [], [], []
        title_docs, title_metas, title_ids = [], [], []
        
        for i, item in enumerate(self.chunks):
            page_list_json = json.dumps(item.get("page_list", []))
            chunk_idx = item.get("chunk_index", i)
            bc = item.get("breadcrumb", "Không có tiêu đề")

            content_docs.append(item["enriched_text"])
            content_metas.append({
                "breadcrumb": bc, 
                "page": item["page"], 
                "page_list": page_list_json,
                "chunk_index": chunk_idx,
                "raw": item["raw_text"],
                "bboxes": json.dumps(item.get("bboxes", []))
            })
            content_ids.append(f"content_{i}")
            
            title_docs.append(bc)
            title_metas.append({
                "breadcrumb": bc,
                "page": item["page"],
                "page_list": page_list_json,
                "chunk_index": chunk_idx
            })
            title_ids.append(f"title_{i}")
            
        if content_docs:
            self.col_content.add(
                documents=content_docs,
                metadatas=content_metas,
                embeddings=content_embeddings,
                ids=content_ids
            )
            self.col_titles.add(
                documents=title_docs,
                metadatas=title_metas,
                embeddings=title_embeddings,
                ids=title_ids
            )
        # Initialize BM25
        try:
            from rank_bm25 import BM25Okapi
            print("\n  🔄 Đang khởi tạo BM25 cho Hybrid Search...")
            tokenized_corpus = [doc["raw_text"].lower().split(" ") for doc in self.chunks]
            self.bm25 = BM25Okapi(tokenized_corpus)
        except ImportError:
            print("\n  ⚠️ rank_bm25 chưa được cài đặt, bỏ qua Hybrid Search.")
        
        unique_breadcrumbs = sorted(list(set(c["breadcrumb"] for c in self.chunks if c.get("breadcrumb"))))
        structure_str = "\n".join([f"- {b}" for b in unique_breadcrumbs]) if unique_breadcrumbs else "Không có thông tin cấu trúc."
        
        print(f"\n📋 CẤU TRÚC TÀI LIỆU ĐANG CÓ:\n{structure_str}\n")            
        
        # Đánh giá chất lượng cấu trúc bằng LLM
        print("  🧠 Đang đánh giá chất lượng cấu trúc tài liệu...")
        self.is_structure_good, in_eval, out_eval = self.evaluate_structure_quality(structure_str)
        print(f"    📈 Token đánh giá cấu trúc: Input={in_eval}, Output={out_eval}")
        
        return True

    @traceable(name="Evaluate Structure", run_type="llm")
    def evaluate_structure_quality(self, structure_str):
        if not structure_str or "Không có thông tin cấu trúc" in structure_str:
            return False
            
        prompt = f"""Dưới đây là cấu trúc mục lục được trích xuất từ một tài liệu PDF:
{structure_str}

Hãy đánh giá xem cấu trúc này có đủ chi tiết và rõ ràng để người dùng có thể đặt câu hỏi về các chủ đề cụ thể (có phân cấp Chương/Mục rõ ràng) hay không?

Nếu cấu trúc chỉ có những thông tin chung chung như 'Noi dung chung', 'Mục lục', hoặc quá ít tiêu đề (dưới 3 tiêu đề thực thụ), hoặc các tiêu đề không mang ý nghĩa nội dung, hãy trả về 'POOR'.
Nếu cấu trúc có các tiêu đề chương/mục rõ ràng, mang tính nội dung, hãy trả về 'GOOD'.

Trả về DUY NHẤT một từ: GOOD hoặc POOR."""
        try:
            res = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Ghi log chi phí
            self.log_cost(
                model=self.model_name,
                prompt_tokens=res.usage.prompt_tokens,
                completion_tokens=res.usage.completion_tokens,
                feature_name="Evaluate Structure"
            )
            
            label = res.choices[0].message.content.strip().upper()
            is_good = "GOOD" in label
            
            in_tokens = res.usage.prompt_tokens
            out_tokens = res.usage.completion_tokens
            
            if not is_good:
                print("  ⚠️ LLM đánh giá cấu trúc này KHÔNG ĐỦ TỐT để truy vấn theo chủ đề.")
            else:
                print("  ✅ LLM đánh giá cấu trúc tài liệu TỐT.")
            return is_good, in_tokens, out_tokens
        except Exception as e:
            print(f"  ❌ Lỗi evaluate_structure_quality: {e}")
            return True, 0, 0 # Dự phòng: cho phép nếu lỗi API

    @traceable(name="Detect Intent", run_type="llm")
    def detect_intent(self, query):
        unique_breadcrumbs = sorted(list(set(c["breadcrumb"] for c in self.chunks if c.get("breadcrumb"))))
        structure_str = "\n".join([f"- {b}" for b in unique_breadcrumbs]) if unique_breadcrumbs else "Không có thông tin cấu trúc."
        
        prompt = f"""Dựa trên cấu trúc văn bản sau đây:
{structure_str}

Phân loại câu hỏi của người dùng vào 1 trong 2 loại:
1. 'STRUCTURE': Hỏi về cấu trúc, mục lục, hoặc nội dung của một Chương/Mục/Phần.
2. 'DETAIL': Hỏi về chi tiết, định nghĩa, thông tin cụ thể bên trong văn bản hoặc toàn bộ nội dung.

Câu hỏi: '{query}'

Trả về DUY NHẤT một từ: STRUCTURE hoặc DETAIL."""
        
        try:
            res = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            
            self.log_cost(
                model=self.model_name,
                prompt_tokens=res.usage.prompt_tokens,
                completion_tokens=res.usage.completion_tokens,
                feature_name="Detect Intent"
            )
            
            label = res.choices[0].message.content.strip().upper()
            intent = "STRUCTURE" if "STRUCTURE" in label else "DETAIL"
            
            # Log intent to LangSmith metadata
            run = get_current_run_tree()
            if run: run.metadata["detected_intent"] = intent
                
            return intent
        except Exception as e:
            print(f"  ❌ Lỗi detect_intent: {e}")
            return "DETAIL"

    def reciprocal_rank_fusion(self, dense_ranks, sparse_ranks, k=60):
        scores = {}
        for rank, item_id in enumerate(dense_ranks):
            scores[item_id] = scores.get(item_id, 0) + 1.0 / (rank + k)
        for rank, item_id in enumerate(sparse_ranks):
            scores[item_id] = scores.get(item_id, 0) + 1.0 / (rank + k)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
    def clean_context(self, text):
        if not text:
            return ""
        import re
        lines = text.split("\n")
        
        seen = set()
        cleaned = []
        
        for l in lines:
            # 1. Làm sạch cơ bản và loại bỏ khoảng trắng thừa
            line = l.strip()
            if not line:
                continue
                
            # 2. Loại bỏ tổ hợp các ký tự đánh dấu ở đầu dòng (###, *, -, •, + và khoảng trắng)
            # Regex: ^[#\*\-\•\+\s]+
            line = re.sub(r'^[#\*\-\•\+\s]+', '', line).strip()
            
            if not line:
                continue
            
            # 3. Chuẩn hóa khoảng trắng nội bộ (biến nhiều space thành 1 space)
            line = re.sub(r'\s+', ' ', line)
            
            # 4. Bỏ trùng lặp
            normalized_l = line.lower()
            if normalized_l in seen:
                continue
            seen.add(normalized_l)
            
            # 5. Loại bỏ noise đặc thù (Header/Footer/Page numbers)
            noise_patterns = [
                r"PAGE:\s*\d+", 
                r"CHINH PHỤC BÁCH KHOA", 
                r"ĐỀ CƯƠNG ÔN TẬP",
                r"^\d+$" # Chỉ có số (thường là số trang)
            ]
            if any(re.search(p, line, re.IGNORECASE) for p in noise_patterns):
                continue
            
            cleaned.append(line)
        
        return "\n".join(cleaned)
    @traceable(name="Retrieve Context")
    def retrieve_context(self, query, intent="DETAIL", top_n=3, page_range=None):
        requested_pages = self.parse_page_range(page_range)
        chunk_results = [] # List of {"text": str, "bboxes": list}
        
        # --- CASE 1: Page Range is provided (Highest Priority) ---
        if requested_pages:
            print(f"  🔍 Ưu tiên lấy nội dung theo dải trang: {page_range}")
            # Lấy tất cả các chunk thuộc các trang yêu cầu (Xử lý giới hạn ChromaDB)
            all_c = self.col_content.get(include=["metadatas", "documents"], limit=9999)
            matched_metas = []
            for meta in all_c["metadatas"]:
                # Parse page_list back from JSON string
                p_list = json.loads(meta.get("page_list", "[]"))
                chunk_range = set(p_list)
                if not chunk_range.isdisjoint(requested_pages):
                    matched_metas.append(meta)
            
            if matched_metas:
                # Sắp xếp theo vị trí vật lý (chunk_index) để rải đều chính xác
                matched_metas = sorted(matched_metas, key=lambda x: x.get("chunk_index", 0))
                
                # Logic rải đều kiến thức (Distributed Sampling)
                MAX_CHUNKS = 12
                if len(matched_metas) > MAX_CHUNKS:
                    print(f"  ℹ️ Dải trang rộng ({len(matched_metas)} chunks), đang thực hiện lấy mẫu rải đều...")
                    # Sử dụng công thức đảm bảo lấy được cả phần tử đầu và cuối
                    sampled = []
                    for i in range(MAX_CHUNKS):
                        idx = int(i * (len(matched_metas) - 1) / (MAX_CHUNKS - 1))
                        sampled.append(matched_metas[idx])
                    matched_metas = sampled
                
                for meta in matched_metas:
                    text = f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}"
                    bboxes = json.loads(meta.get("bboxes", "[]"))
                    chunk_results.append({"text": text, "bboxes": bboxes})
                
                # Check if we need detail fallback
                combined_text = "\n\n".join([c["text"] for c in chunk_results])
                if len(combined_text) < 300 and query:
                    print("  ⚠️ Nội dung trang quá ít, bổ sung thêm tìm kiếm theo chi tiết...")
                    intent = "DETAIL"
                else:
                    return chunk_results # Return list of chunk objects

        # --- CASE 2: No Page Range or Fallback to intent search ---
        if intent == "STRUCTURE":
            print(f"  🔍 Đang tìm kiếm theo Cấu trúc (Titles)...")
            res_t = self.col_titles.query(query_embeddings=[self.embed_text(query)], n_results=5)
            
            best_breadcrumb = None
            if res_t["metadatas"][0]:
                for i, meta in enumerate(res_t["metadatas"][0]):
                    dist = res_t["distances"][0][i]
                    if dist > 0.6: # Ngưỡng tin cậy thấp
                        print(f"  ⚠️ Tiêu đề khớp không đủ tốt (distance: {dist:.2f} > 0.6), chuyển sang tìm chi tiết...")
                        intent = "DETAIL"
                        break
                    
                    best_breadcrumb = meta["breadcrumb"]
                    print(f"  🎯 Khớp tiêu đề: {best_breadcrumb} (distance: {dist:.2f})")
                    # Lấy tất cả nội dung thuộc breadcrumb này (Xử lý giới hạn mặc định của ChromaDB)
                    all_c = self.col_content.get(include=["metadatas", "documents"], limit=9999)
                    matched_raws = []
                    temp_bboxes = []
                    for meta_c in all_c["metadatas"]:
                        if meta_c["breadcrumb"] == best_breadcrumb or meta_c["breadcrumb"].startswith(best_breadcrumb + " >"):
                            matched_raws.append(meta_c["raw"])
                            temp_bboxes.extend(json.loads(meta_c.get("bboxes", "[]")))
                            
                    if matched_raws:
                        temp_context = "\n\n".join(matched_raws)
                        if len(temp_context) < 300:
                            print(f"  ⚠️ Nội dung chương này quá ngắn, tìm chi tiết để có kết quả tốt hơn...")
                            intent = "DETAIL"
                            break
                        
                        chunk_results.append({"text": temp_context, "bboxes": temp_bboxes})
                        return chunk_results
            
            # Fallback if no crumbs found or distance too high
            intent = "DETAIL"

        if intent == "DETAIL":
            print(f"  🔍 Đang tìm kiếm theo Chi tiết (Content)...")
            candidate_n = top_n * 2
            
            if self.bm25 is not None:
                tokenized_query = query.lower().split(" ")
                bm25_scores = self.bm25.get_scores(tokenized_query)
                sparse_top_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:candidate_n]
                sparse_ranks = [f"content_{i}" for i in sparse_top_idx]
                
                res_dense = self.col_content.query(query_embeddings=[self.embed_text(query)], n_results=candidate_n)
                dense_ranks = res_dense["ids"][0]
                
                fused = self.reciprocal_rank_fusion(dense_ranks, sparse_ranks)
                best_ids = [x[0] for x in fused[:top_n]]
                
                res_c = self.col_content.get(ids=best_ids)
                id_to_meta = {id_: meta for id_, meta in zip(res_c["ids"], res_c["metadatas"])}
                
                for chunk_id in best_ids:
                    if chunk_id in id_to_meta:
                        meta = id_to_meta[chunk_id]
                        text = f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}"
                        bboxes = json.loads(meta.get("bboxes", "[]"))
                        chunk_results.append({"text": text, "bboxes": bboxes})
            else:
                res_c = self.col_content.query(query_embeddings=[self.embed_text(query)], n_results=top_n)
                for i in range(len(res_c["documents"][0])):
                    meta = res_c["metadatas"][0][i]
                    text = f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}"
                    bboxes = json.loads(meta.get("bboxes", "[]"))
                    chunk_results.append({"text": text, "bboxes": bboxes})
        
        # Log retrieval stats to LangSmith
        combined_text = "\n\n".join([c["text"] for c in chunk_results])
        run = get_current_run_tree()
        if run:
            run.metadata["intent_used"] = intent
            run.metadata["context_length"] = len(combined_text)
            
        return chunk_results

    def export_highlighted_pdf(self, bboxes, output_path):
        """Highlight bboxes in the PDF, crop to focus area, and save to output_path"""
        if not self.current_pdf_path or not bboxes:
            if not bboxes:
                # Tránh log gây nhiễu nếu log ở đây, chỉ âm thầm return nhưng đảm bảo bboxes đầy đủ ở caller
                pass
            return None
            
        try:
            import fitz
            doc = fitz.open(self.current_pdf_path)
            
            highlight_count = 0
            for item in bboxes:
                page_num = item.get("p")
                bbox = item.get("b")
                if page_num and bbox:
                    page_idx = page_num - 1
                    if 0 <= page_idx < len(doc):
                        page = doc[page_idx]
                        rect = fitz.Rect(bbox)
                        if rect.is_empty or rect.is_infinite: continue
                        page.add_highlight_annot(rect)
                        highlight_count += 1
            
            doc.save(output_path)
            doc.close()
            print(f"  ✨ Đã lưu file highlight ngữ cảnh tại: {output_path} ({highlight_count} highlights)")
            return output_path
        except Exception as e:
            print(f"  ❌ Lỗi export_highlighted_pdf: {e}")
            return None

    @traceable(name="Generate Questions", run_type="llm")
    def generate_questions(self, context, num_questions=3, user_desire="", target_level=None, feedback_str=""):
        # Optimize prompt for Language Mode (Vocabulary Extraction)
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
<definitions>
<Nhận biết>
Nhắc lại hoặc nhận diện các thông tin, dữ liệu, định nghĩa, quy tắc đã học mà không cần giải thích thêm.
</Nhận biết>
<Thông hiểu>
Khả năng hiểu ý nghĩa tài liệu, có thể tóm tắt, diễn giải hoặc giải thích dữ liệu theo cách hiểu cá nhân.
</Thông hiểu>
<Vận dụng>
Sử dụng kiến thức đã học để giải quyết một vấn đề trong tình huống mới hoặc cụ thể.
</Vận dụng> 
</definitions>
- Chỉ dùng nội dung trong context.
- Trả về JSON: {json_format}
- Luôn trả về JSON tương tự mẫu.
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
            parsed = json.loads(content)
            in_tokens = response.usage.prompt_tokens
            out_tokens = response.usage.completion_tokens
            self.log_cost(self.model_name, in_tokens, out_tokens, "Generate Questions")
            return parsed.get("questions", []), in_tokens, out_tokens
        except Exception as e:
            print(f"    ❌ Lỗi generate_questions: {e}")
            return [], 0, 0

    @traceable(name="Generate Answers", run_type="llm")
    def generate_answers(self, context, questions, user_desire=""):
        if not questions: return [], 0, 0
        
        system_prompt = f"""Bạn là AI tạo Flashcard chuyên nghiệp. Nhiệm vụ của bạn là tạo câu trả lời ĐẦY ĐỦ VÀ CHI TIẾT NHẤT dựa trên <context>.

QUY TẮC SẮT ĐÁ (UNBREAKABLE RULES):
1. CHỈ DÙNG CONTEXT: Tuyệt đối không tự bịa, không dùng kiến thức ngoài. Nếu không thấy trong Context, ghi "Không tìm thấy thông tin trong tài liệu".
2. TRẢ LỜI ĐẦY ĐỦ: Liệt kê tất cả các ý chính/bullet points tìm thấy. Thà dài mà đủ còn hơn ngắn mà thiếu.
3. TỰ PHẢN TƯ: Đối soát kỹ câu trả lời với context trước khi xuất JSON.

{f"ĐỊNH HƯỚNG NGƯỜI DÙNG: {user_desire}" if user_desire else ""}
TRẢ VỀ JSON: {{"answers": ["...", "...", ...]}} theo đúng thứ tự câu hỏi."""

        # Thêm chỉ dẫn chi tiết về cấu trúc câu hỏi để AI đối chiếu
        questions_list = "\n".join([f"Q{i+1}: {q.get('question', '')} (Level: {q.get('level', 'N/A')})" for i, q in enumerate(questions)])
        user_prompt = f"<context>\n{context}\n</context>\n\n<questions>\n{questions_list}\n</questions>\n\nHãy kiểm tra kỹ từng câu hỏi và tạo câu trả lời đầy đủ, chính xác nhất."

        # Detection for Language Mode using Argos Translate
        if "[MODE_LANGUAGE]" in user_desire and HAS_ARGOS:
            print("    🌍 Chế độ Học ngoại ngữ: Sử dụng Argos Translate để dịch...")
            argos_answers = []
            for q in questions:
                word = q.get('question', '')
                try:
                    # Detect if word is English (default) or Vietnamese to translate accordingly
                    # For simplicity, we assume English -> Vietnamese if not specified
                    # Argos translate usage: argos_translate.translate(text, from_code, to_code)
                    translated = argos_translate.translate(word, "en", "vi")
                    argos_answers.append(translated)
                except Exception as e:
                    print(f"    ⚠️ Lỗi dịch Argos cho '{word}': {e}")
                    argos_answers.append(f"Chưa có bản dịch ({word})")
            return argos_answers, 0, 0

        try:
            response = self.client.chat.completions.create(
                model=self.answer_model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            in_tokens = response.usage.prompt_tokens
            out_tokens = response.usage.completion_tokens
            self.log_cost(self.answer_model_name, in_tokens, out_tokens, "Generate Answers")
            return parsed.get("answers", []), in_tokens, out_tokens
        except Exception as e:
            print(f"    ❌ Lỗi generate_answers: {e}")
            return [], 0, 0

    @traceable(name="Generate Flashcards", run_type="chain")
    def generate_flashcards(self, chunk_results, num_flashcard=3, status_callback=None, user_desire="", user_id=None):
        def _log(msg):
            print(msg)
            if status_callback: status_callback(msg)

        if not chunk_results: 
            _log("⚠️ Ngữ cảnh trống.")
            return "Ngữ cảnh trống."

        # 1. XÁC ĐỊNH SỐ LƯỢNG THẺ THỰC TẾ
        num_flashcard = int(num_flashcard) if isinstance(num_flashcard, (int, str)) and str(num_flashcard).isdigit() else 3
        num_chunks = len(chunk_results)
        
        # Nếu số chunk ít hơn số thẻ yêu cầu -> chỉ tạo tối đa bằng số chunk
        final_num_cards = min(num_chunks, num_flashcard)
        _log(f"  🎯 Mục tiêu: Tạo {final_num_cards} thẻ từ {num_chunks} chunks (Tỷ lệ 1 chunk = 1 thẻ)")

        # --- DATA FLYWHEEL: Lấy feedback thông minh ---
        current_mode = "vocabulary" if "[MODE_LANGUAGE]" in user_desire else "content"
        feedback_str = ""
        if user_id:
            feedback_str = self.get_smart_feedback(user_id, current_mode)
            if feedback_str:
                _log("  💡 Đã tích hợp 3 bài học từ lịch sử sửa đổi (Data Flywheel).")

        # 2. CHỌN CHUNKS RẢI ĐỀU (DISTRIBUTED SAMPLING)
        # Thay vì gộp, chúng ta chọn ra đúng N chunks từ danh sách kết quả
        selected_chunks = []
        if final_num_cards > 0:
            if final_num_cards == 1:
                selected_chunks = [chunk_results[0]]
            else:
                for i in range(final_num_cards):
                    # Công thức lấy mẫu rải đều từ đầu đến cuối danh sách
                    idx = int(i * (num_chunks - 1) / (final_num_cards - 1))
                    selected_chunks.append(chunk_results[idx])

        # 3. ĐÓNG GÓI CHUNKS THÀNH CÁC NHÓM (BATCHES) - TIẾT KIỆM CHI PHÍ
        batch_size = 5
        merged_parts = []
        for i in range(0, len(selected_chunks), batch_size):
            batch = selected_chunks[i:i + batch_size]
            cur_tagged_text = ""
            for sub_idx, chunk in enumerate(batch):
                cur_tagged_text += f"<chunk id=\"{sub_idx}\">\n{chunk['text']}\n</chunk>\n\n"
            
            merged_parts.append({
                "tagged_text": cur_tagged_text, 
                "chunks_meta": batch,
                "num_to_gen": len(batch)
            })

        num_parts = len(merged_parts)
        allocations = [p["num_to_gen"] for p in merged_parts]
        all_flashcards = []
        total_in = 0
        total_out = 0

        # --- SPECIAL MODE: LLM-FREE VOCABULARY EXTRACTION ---
        if "[MODE_LANGUAGE]" in user_desire and HAS_WORDFREQ and (HAS_DEEP_TRANSLATOR or HAS_ARGOS):
            _log(f"    🌍 Chế độ Thuật toán: Trích xuất {num_flashcard} từ vựng hiếm nhất...")
            
            # 1. Collect all unique words from all chunks
            all_text = " ".join([c['text'] for c in chunk_results])
            words = wordfreq_tokenize(all_text, "en")
            
            # Detect proper nouns: words that appear capitalized in original text
            import re
            capitalized_words = set(w.lower() for w in re.findall(r'\b[A-Z][a-z]+\b', all_text))
            
            # 2. Score unique words by Zipf frequency (lower is rarer)
            unique_words = set(words)
            word_scores = []
            for w in unique_words:
                if len(w) < 3 or not w.isalpha(): continue  # Skip very short or non-alpha
                if w.lower() in capitalized_words: continue  # Skip proper nouns (tên riêng)
                freq = zipf_frequency(w, 'en')
                if freq > 5.0 or freq == 0: continue # Skip very common words (Zipf > 5)
                word_scores.append((w, freq))
            
            # 3. Sort by frequency (ascending = rarest first)
            # Lấy dư gấp đôi để có dự phòng sau khi lọc
            word_scores.sort(key=lambda x: x[1])
            candidates = word_scores[:num_flashcard * 3]
            
            # 4. Batch translate all candidates at once
            _log(f"    🔄 Đang dịch {len(candidates)} từ ứng viên...")
            candidate_words = [w for w, _ in candidates]
            translations = {}
            try:
                if HAS_DEEP_TRANSLATOR:
                    translator = GoogleTranslator(source='en', target='vi')
                    for w in candidate_words:
                        try:
                            translations[w] = translator.translate(w)
                        except:
                            translations[w] = "N/A"
                elif HAS_ARGOS:
                    for w in candidate_words:
                        try:
                            translations[w] = argos_translate.translate(w, "en", "vi")
                        except:
                            translations[w] = "N/A"
            except Exception as e:
                _log(f"    ⚠️ Lỗi dịch batch: {e}")
            
            # Final flashcard list
            candidate_words = [w for w, _ in candidates]
            all_flashcards = self._process_vocabulary_flashcards(candidate_words, chunk_results, _log, num_limit=num_flashcard)
            return json.dumps({"flashcards": all_flashcards, "usage": {"input": 0, "output": 0}}, ensure_ascii=False, indent=2)

        # --- NORMAL MODE: LLM-BASED ---
        levels_cycle = ["Nhận biết", "Thông hiểu", "Vận dụng"]
        
        for idx, (part_data, sub_num) in enumerate(zip(merged_parts, allocations)):
            if sub_num <= 0: continue
            
            # Ở chế độ Batch, chúng ta để AI tự đan xen các cấp độ để đa dạng hơn
            _log(f"    ⏳ Đang tạo {sub_num} câu hỏi (Phần {idx + 1}/{num_parts}) với các cấp độ đan xen...")
            tagged_text = part_data["tagged_text"]
            questions, in_q, out_q = self.generate_questions(tagged_text, sub_num, user_desire, target_level=None, feedback_str=feedback_str)
            
            # Khống chế số lượng câu hỏi đúng bằng sub_num
            if len(questions) > sub_num:
                _log(f"    ⚠️ AI tạo dư {len(questions)} câu, tiến hành cắt bớt còn {sub_num}...")
                questions = questions[:sub_num]
             
            if questions:
                _log(f"    ⏳ Đang sinh câu trả lời cho {len(questions)} câu hỏi...")
                # Still use tagged text/context for answer generation
                answers, in_a, out_a = self.generate_answers(tagged_text, questions, user_desire)
                
                for i, q_obj in enumerate(questions):
                    ans_text = answers[i] if i < len(answers) else "Không có câu trả lời."
                    
                    # Map back to specific chunk's bboxes using chunk_id
                    try:
                        c_id = int(q_obj.get("chunk_id", 0))
                        if 0 <= c_id < len(part_data["chunks_meta"]):
                            target_bboxes = part_data["chunks_meta"][c_id].get("bboxes", [])
                        else:
                            target_bboxes = []
                    except:
                        target_bboxes = []

                    all_flashcards.append({
                        "id": uuid.uuid4().hex,
                        "level": q_obj.get("level", "N/A"),
                        "question": q_obj.get("question", ""),
                        "phonetic": q_obj.get("phonetic", ""),
                        "part_of_speech": q_obj.get("part_of_speech", ""),
                        "answer": ans_text,
                        "bboxes": target_bboxes,
                        "context": part_data["chunks_meta"][c_id].get("text", "") if 0 <= c_id < len(part_data["chunks_meta"]) else ""
                    })
                
                total_in += (in_q + in_a)
                total_out += (out_q + out_a)

        _log(f"\n📈 TỔNG CỘNG TOKEN SỬ DỤNG: Input={total_in}, Output={total_out}")
        
        # Pre-generate individual highlighted PDFs for each card
        if self.current_pdf_path and all_flashcards:
            _log(f"\n📄 Đang tạo nhanh file highlight cho {len(all_flashcards)} thẻ...")
            try:
                import fitz
                # Mở tài liệu gốc một lần duy nhất
                src_doc = fitz.open(self.current_pdf_path)
                
                for card in all_flashcards:
                    if not card.get("bboxes"):
                        continue
                        
                    fname = f"card_highlight_{card['id']}.pdf"
                    txt_fname = f"card_context_{card['id']}.txt"
                    
                    # Tạo bản sao từ tài liệu gốc
                    doc = fitz.open()
                    doc.insert_pdf(src_doc)
                    
                    new_bboxes = []
                    pages_with_highlights = set()
                    
                    for item in card["bboxes"]:
                        p = item.get("p")
                        bbox = item.get("b")
                        if p and bbox:
                            pi = p - 1
                            if 0 <= pi < len(doc):
                                r = fitz.Rect(bbox)
                                if not r.is_empty and not r.is_infinite:
                                    doc[pi].add_highlight_annot(r)
                                    new_bboxes.append(item)
                                    pages_with_highlights.add(pi)
                    
                    if pages_with_highlights:
                        pages_list = sorted(list(pages_with_highlights))
                        doc.select(pages_list)
                        page_map = {old_pi: new_pi for new_pi, old_pi in enumerate(pages_list)}
                        for item in new_bboxes:
                            item["p"] = page_map[item["p"] - 1] + 1
                        
                        doc.save(fname, garbage=3, deflate=True)
                    
                    doc.close()
                    card["bboxes"] = new_bboxes
                    
                    # Lưu context text
                    try:
                        with open(txt_fname, "w", encoding="utf-8") as tf:
                            tf.write(f"QUESTION: {card.get('question', '')}\n")
                            tf.write(f"ANSWER: {card.get('answer', '')}\n")
                            tf.write("-" * 50 + "\n")
                            tf.write(f"CONTEXT:\n{card.get('context', '')}\n")
                    except:
                        pass
                
                src_doc.close()
                _log("  ✅ Đã hoàn tất tạo tài liệu bổ trợ cho các thẻ.")
            except Exception as e:
                _log(f"  ⚠️ Lỗi khi tạo file highlight: {e}")

        return json.dumps({"flashcards": all_flashcards, "usage": {"input": total_in, "output": total_out}}, ensure_ascii=False, indent=2)


    def _process_vocabulary_flashcards(self, words, chunk_results=None, _log_func=None, num_limit=999):
        """Helper to translate, transcribe, and generate audio for a list of words."""
        def _log(msg):
            if _log_func: _log_func(msg)
            else: print(msg)

        # 1. Parallel Translation & Processing
        from concurrent.futures import ThreadPoolExecutor
        _log(f"    🚀 Đang xử lý song song {len(words)} từ vựng (Dịch + TTS + IPA)...")
        
        translations = {}
        all_flashcards = []
        
        def process_single_word(word):
            try:
                # Translation
                translated = "N/A"
                if HAS_DEEP_TRANSLATOR:
                    translated = GoogleTranslator(source='en', target='vi').translate(word)
                elif HAS_ARGOS:
                    translated = argos_translate.translate(word, "en", "vi")
                
                # IPA
                ipa = ""
                if HAS_IPA:
                    ipa = eng_to_ipa.convert(word)
                    ipa = f"/{ipa}/" if ipa and '*' not in ipa else ""
                
                if not ipa:
                    try:
                        resp = self.client.chat.completions.create(
                            model=self.model_name,
                            messages=[{"role": "user", "content": f"Chỉ trả về phiên âm IPA của từ \"{word}\". Ví dụ: /ˈæp.əl/."}],
                            temperature=0, max_tokens=20
                        )
                        ipa = resp.choices[0].message.content.strip()
                    except: pass

                # POS
                pos = "từ"
                if HAS_NLTK:
                    tokens = word_tokenize(word)
                    tags = pos_tag(tokens)
                    if tags: pos = map_pos_to_vn(tags[0][1])
                
                # Audio
                card_id = uuid.uuid4().hex
                audio_file = f"audio_{card_id}.mp3"
                try:
                    from gtts import gTTS
                    audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), audio_file)
                    tts = gTTS(text=word, lang='en', slow=False)
                    tts.save(audio_path)
                except: audio_file = ""

                return {
                    "id": card_id,
                    "level": "Từ vựng",
                    "question": word,
                    "phonetic": ipa,
                    "part_of_speech": pos,
                    "answer": translated,
                    "audio": audio_file,
                    "bboxes": []
                }
            except Exception as e:
                print(f"    ⚠️ Lỗi xử lý từ '{word}': {e}")
                return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_single_word, words))
        
        all_flashcards = [r for r in results if r is not None][:num_limit]

        # 2. Optimized PDF Highlighting (If needed)
        if chunk_results and self.current_pdf_path and all_flashcards:
            _log(f"    🔍 Đang tìm vị trí từ vựng trong PDF...")
            try:
                import fitz
                doc = fitz.open(self.current_pdf_path)
                for card in all_flashcards:
                    word = card["question"]
                    fname = f"card_highlight_{card['id']}.pdf"
                    
                    found = False
                    for page in doc:
                        rects = page.search_for(word)
                        if rects:
                            for r in rects: page.add_highlight_annot(r)
                            found = True
                    
                    if found:
                        # Clone and save subset
                        temp_doc = fitz.open()
                        temp_doc.insert_pdf(doc) # This is a bit heavy, but better than re-opening
                        temp_doc.save(fname, garbage=3, deflate=True)
                        temp_doc.close()
                doc.close()
            except Exception as e:
                _log(f"    ⚠️ Lỗi highlight PDF: {e}")

        return all_flashcards




    @traceable(name="Generate No-RAG", run_type="chain")
    def generate_no_rag(self, topic, num_flashcard=3, status_callback=None, user_desire="", user_id=None):
        """Generates flashcards from general knowledge without any document context."""
        def _log(msg):
            print(msg)
            if status_callback: status_callback(msg)

        _log(f"  🧠 Đang tạo flashcard từ kiến thức hệ thống cho chủ đề: {topic}")
        
        is_vocab = "[MODE_LANGUAGE]" in user_desire
        
        # --- DATA FLYWHEEL ---
        current_mode = "vocabulary" if is_vocab else "content"
        feedback_str = ""
        if user_id:
            feedback_str = self.get_smart_feedback(user_id, current_mode)
        
        if is_vocab:
            system_prompt = f"""Bạn là AI chuyên gia ngôn ngữ.
Hãy liệt kê danh sách CHÍNH XÁC {num_flashcard} từ vựng hoặc thuật ngữ tiếng Anh quan trọng/phổ biến nhất liên quan đến chủ đề: "{topic}".
Chỉ cần liệt kê từ gốc.

Trả về JSON: 
{{
  "flashcards": [
    {{ "question": "Word 1" }},
    {{ "question": "Word 2" }}
  ]
}}"""
        else:
            system_prompt = f"""Bạn là AI tạo Flashcard chuyên nghiệp.
Hãy sử dụng kiến thức của bạn để tạo CHÍNH XÁC {num_flashcard} câu hỏi và câu trả lời flashcard về chủ đề: "{topic}".
Các câu hỏi nên bao gồm nhiều cấp độ: Nhận biết, Thông hiểu, Vận dụng.
{f"Định hướng bổ sung: {user_desire}" if user_desire else ""}

Trả về JSON duy nhất: 
{{
  "flashcards": [
    {{
      "id": 0,
      "level": "Nhận biết",
      "question": "...",
      "answer": "..."
    }}
  ]
}}"""
        
        system_prompt += f"\nLưu ý: Luôn trả về đúng số lượng {num_flashcard} thẻ."
        
        try:
            all_flashcards = []
            total_in = 0
            total_out = 0
            
            # Chia làm các đợt (batch) 10 thẻ để đảm bảo tốc độ và độ ổn định
            batch_size = 10
            num_batches = (num_flashcard + batch_size - 1) // batch_size
            
            for i in range(num_batches):
                current_batch_size = min(batch_size, num_flashcard - len(all_flashcards))
                _log(f"    ⏳ Đang tạo đợt {i+1}/{num_batches} ({current_batch_size} thẻ)...")
                
                batch_system_prompt = system_prompt + f"\nLưu ý: Trong đợt này, hãy tạo ĐÚNG {current_batch_size} thẻ. Không trùng lặp với các thẻ đã tạo trước đó."
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": batch_system_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                
                content = response.choices[0].message.content
                parsed = json.loads(content)
                batch_cards = parsed.get("flashcards", [])
                
                # Giới hạn đúng số lượng yêu cầu cho batch này
                if len(batch_cards) > current_batch_size:
                    batch_cards = batch_cards[:current_batch_size]
                
                # Xử lý theo từng chế độ
                is_vocab = "[MODE_LANGUAGE]" in user_desire
                if is_vocab:
                    batch_words = [card["question"] for card in batch_cards]
                    # Xử lý từ vựng (Dịch, TTS, IPA song song)
                    processed_cards = self._process_vocabulary_flashcards(batch_words, _log_func=_log, num_limit=current_batch_size)
                    all_flashcards.extend(processed_cards)
                else:
                    # Chế độ Nội dung: Trả về kết quả từ LLM trực tiếp
                    for card in batch_cards:
                        card["id"] = uuid.uuid4().hex
                        if "bboxes" not in card:
                            card["bboxes"] = []
                        all_flashcards.append(card)
                
                total_in += response.usage.prompt_tokens
                total_out += response.usage.completion_tokens
                
                if len(all_flashcards) >= num_flashcard:
                    break

            usage = {"input": total_in, "output": total_out}
            _log(f"\n📈 TỔNG CỘNG TOKEN SỬ DỤNG: Input={total_in}, Output={total_out}")
            
            return json.dumps({"flashcards": all_flashcards, "usage": usage}, ensure_ascii=False, indent=2)
            
        except Exception as e:
            _log(f"    ❌ Lỗi generate_no_rag: {e}")
            return json.dumps({"flashcards": [], "error": str(e)}, ensure_ascii=False)

    @traceable(name="RAG Query", run_type="chain")
    def query(self, query, num_flashcard=3, page_range=None, status_callback=None, user_desire="", user_id=None):
        def _log(msg):
            print(msg)
            if status_callback: status_callback(msg)
        # Set top-level metadata
        run = get_current_run_tree()
        if run:
            run.metadata.update({
                "model_name": self.model_name,
                "num_flashcard_requested": num_flashcard,
                "page_range_filter": page_range,
                "embedding_model": self.embedding_model_name
            })
            
        # Trường hợp không có query và có page_range
        if not query.strip() and page_range:
            chunk_results = self.retrieve_context(query="", page_range=page_range)
            intent = "PAGE_ONLY"
        else:
            intent = self.detect_intent(query)
            _log(f"  🧠 Intent detected: {intent}")
            chunk_results = self.retrieve_context(query, intent=intent, page_range=page_range)

        if not chunk_results:
            return json.dumps({"flashcards": [], "error": "Không tìm thấy ngữ cảnh phù hợp cho yêu cầu của bạn."}), ""
        
        combined_text = "\n\n".join([c["text"] for c in chunk_results])
        all_bboxes = []
        for c in chunk_results: all_bboxes.extend(c["bboxes"])

        _log(f"\n📄 NGỮ CẢNH ({intent}):\n" + "-"*30 + f"\n{combined_text[:300]}..." + "\n" + "-"*30)
        
        _log("\n🧠 Đang tạo Flashcards...")
                    # 2. Sinh Flashcard
        flashcards_json = self.generate_flashcards(chunk_results, num_flashcard, status_callback, user_desire, user_id=user_id)
        return flashcards_json, combined_text

    @traceable(name="Chat with Card", run_type="llm")
    def chat_with_card(self, card_context, question, answer, user_message, history=None):
        """
        Trao đổi với AI về nội dung một thẻ cụ thể.
        """
        system_prompt = f"""Bạn là một chuyên gia hỗ trợ học tập. 
Người dùng đang học một thẻ Flashcard và muốn thảo luận thêm về nó.

<CARD_CONTEXT_FROM_PDF>
{card_context}
</CARD_CONTEXT_FROM_PDF>

<FLASHCARD_INFO>
Câu hỏi: {question}
Câu trả lời: {answer}
</FLASHCARD_INFO>

Nhiệm vụ của bạn:
1. Giải thích, mở rộng hoặc làm rõ các thắc mắc của người dùng dựa trên ngữ cảnh trích xuất từ PDF.
2. Nếu thông tin không có trong ngữ cảnh, hãy sử dụng kiến thức chung của bạn nhưng phải ghi rõ là "theo kiến thức chung ngoài tài liệu".
3. Giữ câu trả lời ngắn gọn, thân thiện và tập trung vào việc giúp người dùng hiểu sâu hơn về nội dung thẻ.
4. Trả lời bằng ngôn ngữ mà người dùng sử dụng (mặc định là tiếng Việt)."""

        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            for msg in history:
                messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in chat_with_card: {e}")
            return f"Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu: {str(e)}"


# ================================================================
# Main: Sandbox / Test
# ================================================================
if __name__ == "__main__":
    pdf_path = os.path.join(os.path.dirname(__file__), "B1.pdf")
    
    rag = RAGSystem()
    if rag.process_pdf(pdf_path):
        while True:
            try:
                print("\n" + "="*50)
                if not rag.is_structure_good:
                    print("⚠️ CẢNH BÁO: Cấu trúc tài liệu không rõ ràng. Bạn KHÔNG THỂ nhập chủ đề.")
                    print("Vui lòng nhập dải trang để hệ thống lấy dữ liệu chính xác.")
                    user_query = ""
                    p_range = ""
                    while not p_range:
                        p_range = input("👉 Nhập dải trang (Ví dụ: 1-3, 5): ").strip()
                        if not p_range: print("  ⚠️ Bạn bắt buộc phải nhập dải trang!")
                else:
                    print("Hệ thống RAG sẵn sàng: Nhập chủ đề HOẶC dải trang.")
                    user_query = input("1. Nhập chủ đề (Bỏ qua nếu chỉ muốn lọc theo trang, 'exit' để thoát): ").strip()
                    if user_query.lower() in ['exit', 'quit', 'q']: break
                    
                    p_range = input("2. Nhập dải trang (Ví dụ: 1-3, 'enter' để bỏ qua): ").strip()
                
                p_range = p_range if p_range else None
                
                if not user_query and not p_range:
                    print("⚠️ Bạn phải nhập ít nhất một trong hai: Chủ đề hoặc Dải trang!")
                    continue

                result, context = rag.query(user_query, page_range=p_range)
                print("\n✨ KẾT QUẢ FLASHCARDS:")
                print(result)
            except EOFError: break
            except Exception as e:
                print(f"❌ Lỗi: {e}")

