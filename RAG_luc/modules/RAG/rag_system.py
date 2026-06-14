"""
rag_system.py - RAGSystem: Tổng hợp RAGCore + RAGRetrieval + RAGGeneration.
Đây là file duy nhất mà app_rag.py cần import.
"""
import os
import sys
import json
import logging

logger = logging.getLogger(__name__)

from config.settings import MODEL_NAME, ANSWER_MODEL_NAME, EMBEDDING_MODEL_NAME

try:
    from langsmith import traceable, get_current_run_tree
    HAS_LANGSMITH = True
except ImportError:
    HAS_LANGSMITH = False
    def traceable(name=None, run_type=None, **kwargs):
        def decorator(func): return func
        return decorator
    def get_current_run_tree(): return None

from modules.RAG.pdf_processor import chunk_pdf_auto
from modules.RAG.rag_core import RAGCore
from modules.RAG.rag_retrieval import RAGRetrieval
from modules.RAG.rag_generation import RAGGeneration
from modules.chat.chat_handler import ChatMixin


# ================================================================
# RAGSystem: Kết hợp 4 Mixin thành một class duy nhất
# ================================================================

class RAGSystem(RAGCore, RAGRetrieval, RAGGeneration, ChatMixin):
    """
    Hệ thống RAG đầy đủ - kế thừa từ:
    - RAGCore       : Khởi tạo, embedding, cache, log chi phí
    - RAGRetrieval  : Tìm kiếm ngữ cảnh, detect intent
    - RAGGeneration : Tạo flashcard, từ vựng
    - ChatMixin     : Chat with Card (AI hỏi đáp về thẻ)
    """

    def __init__(self, model_name=None, answer_model_name=None, embedding_model_name=None):
        RAGCore.__init__(self,
            model_name or MODEL_NAME,
            answer_model_name or ANSWER_MODEL_NAME,
            embedding_model_name or EMBEDDING_MODEL_NAME
        )

    # ------------------------------------------------------------------ #
    # Document processing & indexing
    # ------------------------------------------------------------------ #
    @traceable(name="Process PDF")
    def process_pdf(self, pdf_path, tesseract_cmd=None, dpi=150, max_chunk_size=800, min_chunk_size=300, overlap_size=100):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Không tìm thấy file: {pdf_path}")

        self.current_pdf_path = pdf_path
        file_hash = self.get_file_hash(pdf_path)

        # Tắt Cache hoàn toàn theo yêu cầu để tránh OOM / phình DB
        # print(f"  🔍 Đang kiểm tra cache ({file_hash[:8]})...")
        # cached_chunks = self.check_cache_supabase(file_hash)
        # if cached_chunks:
        #     print("  🚀 [HIT] Tìm thấy cache! Đang nạp từ Supabase...")
        #     self.chunks = cached_chunks
        #     return self.index_chunks(self.chunks, skip_embedding_if_cached=True)

        print("  ⏳ Bắt đầu xử lý PDF (Đã vô hiệu hóa Document Cache)...")
        chunks = chunk_pdf_auto(
            pdf_path,
            tesseract_cmd=tesseract_cmd, dpi=dpi,
            max_chunk_size=max_chunk_size, min_chunk_size=min_chunk_size,
            overlap_size=overlap_size, vision_processor=self.vision_processor
        )

        if chunks:
            success = self.index_chunks(chunks)
            # Không lưu cache nữa
            # if success:
            #     self.save_cache_supabase(file_hash, self.doc_name, self.chunks)
            return success

        return False

    def process_document(self, file_path, doc_name=None):
        """Nạp file văn bản thuần (.txt) vào hệ thống RAG (dùng cho video transcripts)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

        self.doc_name = doc_name or os.path.basename(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        chunks = []
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        for i, para in enumerate(paragraphs):
            chunks.append({
                "chunk_index": i,
                "breadcrumb": self.doc_name,
                "page": 1,
                "page_list": [1],
                "raw_text": para,
                "enriched_text": para,
                "bboxes": []
            })

        return self.index_chunks(chunks)

    def index_chunks(self, chunks, skip_embedding_if_cached=False):
        """Index chunks vào ChromaDB và khởi tạo BM25."""
        print("  🧹 Đang dọn dẹp dữ liệu cũ...")
        try:
            self.chroma_client.delete_collection("section_titles")
            self.chroma_client.delete_collection("section_content")
        except Exception:
            pass

        self._col_titles = None
        self._col_content = None
        self.bm25 = None

        if not chunks:
            print("  ⚠️ Không có chunk nào để index.")
            return False

        self.chunks = chunks
        enriched_texts = [c["enriched_text"] for c in self.chunks]
        breadcrumbs = [c.get("breadcrumb", "Không có tiêu đề") for c in self.chunks]

        has_cached = skip_embedding_if_cached and len(self.chunks) > 0 and "content_embedding" in self.chunks[0]
        if has_cached:
            print("  ✅ Sử dụng Vector nhúng từ Cache.")
        else:
            print("  ⏳ Đang tạo vector nhúng...")
            content_embeddings = self.embed_text(enriched_texts)
            title_embeddings   = self.embed_text(breadcrumbs)
            for i, c in enumerate(self.chunks):
                c["content_embedding"] = content_embeddings[i]
                c["title_embedding"]   = title_embeddings[i]
            # Xóa biến tạm để giải phóng RAM
            del content_embeddings
            del title_embeddings

        import gc
        batch_size = 50
        print(f"  📦 Đang nạp {len(self.chunks)} chunks vào ChromaDB (Batch={batch_size})...")
        for b_idx in range(0, len(self.chunks), batch_size):
            batch_chunks = self.chunks[b_idx:b_idx+batch_size]
            
            c_docs, c_metas, c_embs, c_ids = [], [], [], []
            t_docs, t_metas, t_embs, t_ids = [], [], [], []
            
            for j, item in enumerate(batch_chunks):
                idx = b_idx + j
                page_list_json = json.dumps(item.get("page_list", []))
                chunk_idx = item.get("chunk_index", idx)
                bc = item.get("breadcrumb", "Không có tiêu đề")
                raw = item.get("raw_text", item.get("enriched_text", ""))
                
                c_docs.append(item["enriched_text"])
                c_metas.append({"breadcrumb": bc, "page": item.get("page", 1), "page_list": page_list_json,
                               "chunk_index": chunk_idx, "raw": raw,
                               "bboxes": json.dumps(item.get("bboxes", []))})
                c_embs.append(item["content_embedding"])
                c_ids.append(f"content_{idx}")
                
                t_docs.append(bc)
                t_metas.append({"breadcrumb": bc, "page": item.get("page", 1), "page_list": page_list_json, "chunk_index": chunk_idx})
                t_embs.append(item["title_embedding"])
                t_ids.append(f"title_{idx}")
                
            self.col_content.add(documents=c_docs, metadatas=c_metas, embeddings=c_embs, ids=c_ids)
            self.col_titles.add(documents=t_docs, metadatas=t_metas, embeddings=t_embs, ids=t_ids)
            
            del c_docs, c_metas, c_embs, c_ids, t_docs, t_metas, t_embs, t_ids
            gc.collect() # Giải phóng RAM ngay lập tức sau mỗi batch

        try:
            from rank_bm25 import BM25Okapi
            print("\n  🔄 Đang khởi tạo BM25...")
            self.bm25 = BM25Okapi([c.get("raw_text", c.get("enriched_text", "")).lower().split() for c in self.chunks])
        except ImportError:
            print("\n  ⚠️ rank_bm25 chưa cài đặt, bỏ qua Hybrid Search.")

        unique_breadcrumbs = sorted(set(c["breadcrumb"] for c in self.chunks if c.get("breadcrumb")))
        structure_str = "\n".join(f"- {b}" for b in unique_breadcrumbs) or "Không có thông tin cấu trúc."
        print(f"\n📋 CẤU TRÚC TÀI LIỆU:\n{structure_str}\n")

        print("  🧠 Đang đánh giá chất lượng cấu trúc...")
        self.is_structure_good, in_eval, out_eval = self.evaluate_structure_quality(structure_str)
        print(f"    📈 Token đánh giá: Input={in_eval}, Output={out_eval}")

        return True

    # ------------------------------------------------------------------ #
    # Main query entry point
    # ------------------------------------------------------------------ #
    @traceable(name="RAG Query", run_type="chain")
    def query(self, query, num_flashcard=3, page_range=None, status_callback=None, user_desire="", user_id=None):
        def _log(msg):
            print(msg)
            if status_callback: status_callback(msg)

        run = get_current_run_tree()
        if run:
            run.metadata.update({
                "model_name": self.model_name,
                "num_flashcard_requested": num_flashcard,
                "page_range_filter": page_range,
                "embedding_model": self.embedding_model_name
            })

        if not query.strip():
            chunk_results = self.retrieve_context(query="", page_range=page_range, top_n=num_flashcard)
        else:
            intent = self.detect_intent(query)
            _log(f"  🧠 Intent detected: {intent}")
            chunk_results = self.retrieve_context(query, intent=intent, page_range=page_range)

        if not chunk_results:
            return json.dumps({"flashcards": [], "error": "Không tìm thấy ngữ cảnh phù hợp."}), ""

        combined_text = "\n\n".join([c["text"] for c in chunk_results])
        _log(f"\n📄 NGỮ CẢNH:\n{'-'*30}\n{combined_text[:300]}...\n{'-'*30}")
        _log("\n🧠 Đang tạo Flashcards...")

        flashcards_json = self.generate_flashcards(chunk_results, num_flashcard, status_callback, user_desire, user_id=user_id)
        return flashcards_json, combined_text


# ================================================================
# Main: Sandbox / Test
# ================================================================
if __name__ == "__main__":
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "B1.pdf")
    rag = RAGSystem()
    if rag.process_pdf(pdf_path):
        while True:
            try:
                print("\n" + "="*50)
                user_query = input("Nhập chủ đề ('exit' để thoát): ").strip()
                if user_query.lower() in ['exit', 'quit', 'q']: break
                p_range = input("Nhập dải trang (Enter để bỏ qua): ").strip() or None
                if not user_query and not p_range:
                    print("⚠️ Phải nhập ít nhất chủ đề hoặc dải trang!")
                    continue
                result, context = rag.query(user_query, page_range=p_range)
                print("\n✨ KẾT QUẢ FLASHCARDS:")
                print(result)
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"❌ Lỗi: {e}")
