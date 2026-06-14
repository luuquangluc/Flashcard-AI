"""
rag_retrieval.py - Tìm kiếm ngữ cảnh, đánh giá cấu trúc, detect intent, export PDF.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable, get_current_run_tree
except ImportError:
    def traceable(name=None, run_type=None, **kwargs):
        def decorator(func): return func
        return decorator
    def get_current_run_tree(): return None


class RAGRetrieval:
    """Mixin: tìm kiếm & truy vấn ngữ cảnh."""

    # ------------------------------------------------------------------ #
    # Page range helpers
    # ------------------------------------------------------------------ #
    def parse_page_range(self, range_str):
        if not range_str or not range_str.strip():
            return None
        pages = set()
        try:
            for part in [p.strip() for p in range_str.split(',')]:
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    pages.update(range(start, end + 1))
                else:
                    pages.add(int(part))
            return pages
        except Exception as e:
            print(f"  ⚠️ Lỗi parse dải trang '{range_str}': {e}")
            return None

    def is_chunk_in_range(self, chunk_page_str, requested_pages):
        if not requested_pages:
            return True
        try:
            chunk_page_str = str(chunk_page_str)
            if "-" in chunk_page_str:
                start, end = map(int, chunk_page_str.split("-"))
                return not set(range(start, end + 1)).isdisjoint(requested_pages)
            return int(chunk_page_str) in requested_pages
        except Exception:
            return True

    # ------------------------------------------------------------------ #
    # Structure quality evaluation
    # ------------------------------------------------------------------ #
    @traceable(name="Evaluate Structure", run_type="llm")
    def evaluate_structure_quality(self, structure_str):
        if not structure_str or "Không có thông tin cấu trúc" in structure_str:
            return False, 0, 0

        prompt = f"""Dưới đây là cấu trúc mục lục được trích xuất từ một tài liệu PDF:
{structure_str}

Hãy đánh giá xem cấu trúc này có đủ chi tiết và rõ ràng để người dùng có thể đặt câu hỏi về các chủ đề cụ thể không?

Nếu cấu trúc quá chung chung hoặc ít hơn 3 tiêu đề, hãy trả về 'POOR'.
Nếu cấu trúc có phân cấp Chương/Mục rõ ràng, hãy trả về 'GOOD'.

Trả về DUY NHẤT một từ: GOOD hoặc POOR."""

        try:
            res = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            self.log_cost(self.model_name, res.usage.prompt_tokens, res.usage.completion_tokens, "Evaluate Structure")
            label = res.choices[0].message.content.strip().upper()
            is_good = "GOOD" in label
            if not is_good:
                print("  ⚠️ LLM đánh giá cấu trúc này KHÔNG ĐỦ TỐT.")
            else:
                print("  ✅ LLM đánh giá cấu trúc tài liệu TỐT.")
            return is_good, res.usage.prompt_tokens, res.usage.completion_tokens
        except Exception as e:
            print(f"  ❌ Lỗi evaluate_structure_quality: {e}")
            return True, 0, 0

    # ------------------------------------------------------------------ #
    # Intent detection
    # ------------------------------------------------------------------ #
    @traceable(name="Detect Intent", run_type="llm")
    def detect_intent(self, query):
        unique_breadcrumbs = sorted(set(c["breadcrumb"] for c in self.chunks if c.get("breadcrumb")))
        structure_str = "\n".join(f"- {b}" for b in unique_breadcrumbs) or "Không có thông tin cấu trúc."

        prompt = f"""Dựa trên cấu trúc văn bản sau đây:
{structure_str}

Phân loại câu hỏi của người dùng vào 1 trong 2 loại:
1. 'STRUCTURE': Hỏi về cấu trúc, mục lục, hoặc nội dung của một Chương/Mục/Phần.
2. 'DETAIL': Hỏi về chi tiết, định nghĩa, thông tin cụ thể bên trong văn bản.

Câu hỏi: '{query}'

Trả về DUY NHẤT một từ: STRUCTURE hoặc DETAIL."""

        try:
            res = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            self.log_cost(self.model_name, res.usage.prompt_tokens, res.usage.completion_tokens, "Detect Intent")
            label = res.choices[0].message.content.strip().upper()
            intent = "STRUCTURE" if "STRUCTURE" in label else "DETAIL"
            run = get_current_run_tree()
            if run: run.metadata["detected_intent"] = intent
            return intent
        except Exception as e:
            print(f"  ❌ Lỗi detect_intent: {e}")
            return "DETAIL"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def reciprocal_rank_fusion(self, dense_ranks, sparse_ranks, k=60):
        scores = {}
        for rank, item_id in enumerate(dense_ranks):
            scores[item_id] = scores.get(item_id, 0) + 1.0 / (rank + k)
        for rank, item_id in enumerate(sparse_ranks):
            scores[item_id] = scores.get(item_id, 0) + 1.0 / (rank + k)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def clean_context(self, text):
        if not text: return ""
        lines = text.split("\n")
        seen, cleaned = set(), []
        for l in lines:
            line = re.sub(r'^[#\*\-\•\+\s]+', '', l.strip()).strip()
            if not line: continue
            line = re.sub(r'\s+', ' ', line)
            normalized = line.lower()
            if normalized in seen: continue
            seen.add(normalized)
            noise_patterns = [r"PAGE:\s*\d+", r"CHINH PHỤC BÁCH KHOA", r"ĐỀ CƯƠNG ÔN TẬP", r"^\d+$"]
            if any(re.search(p, line, re.IGNORECASE) for p in noise_patterns): continue
            cleaned.append(line)
        return "\n".join(cleaned)

    # ------------------------------------------------------------------ #
    # Retrieve context
    # ------------------------------------------------------------------ #
    @traceable(name="Retrieval: User Query", run_type="retriever", tags=["rrf_search", "initial_retrieval"])
    def retrieve_context(self, query, intent="DETAIL", top_n=3, page_range=None):
        requested_pages = self.parse_page_range(page_range)
        chunk_results = []

        if requested_pages:
            print(f"  🔍 Ưu tiên lấy nội dung theo dải trang: {page_range}")
            all_c = self.col_content.get(include=["metadatas", "documents"], limit=9999)
            matched_metas = []
            for meta in all_c["metadatas"]:
                p_list = json.loads(meta.get("page_list", "[]"))
                if not set(p_list).isdisjoint(requested_pages):
                    matched_metas.append(meta)

            if matched_metas:
                matched_metas = sorted(matched_metas, key=lambda x: x.get("chunk_index", 0))
                MAX_CHUNKS = 12
                if len(matched_metas) > MAX_CHUNKS:
                    sampled = [matched_metas[int(i * (len(matched_metas) - 1) / (MAX_CHUNKS - 1))] for i in range(MAX_CHUNKS)]
                    matched_metas = sampled

                for meta in matched_metas:
                    text = f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}"
                    bboxes = json.loads(meta.get("bboxes", "[]"))
                    chunk_results.append({"text": text, "bboxes": bboxes})

                combined_text = "\n\n".join([c["text"] for c in chunk_results])
                if len(combined_text) < 300 and query:
                    print("  ⚠️ Nội dung trang quá ít, bổ sung thêm tìm kiếm theo chi tiết...")
                    intent = "DETAIL"
                else:
                    return chunk_results

        # Case: No query and no page range -> Whole document sampling
        if not query or not query.strip():
            print("  🔍 Không có chủ đề, tự động lấy mẫu từ toàn bộ tài liệu...")
            all_c = self.col_content.get(include=["metadatas", "documents"], limit=9999)
            if all_c["metadatas"]:
                matched_metas = sorted(all_c["metadatas"], key=lambda x: x.get("chunk_index", 0))
                MAX_CHUNKS = min(top_n, len(matched_metas))
                if len(matched_metas) > MAX_CHUNKS:
                    if MAX_CHUNKS > 1:
                        sampled = [matched_metas[int(i * (len(matched_metas) - 1) / (MAX_CHUNKS - 1))] for i in range(MAX_CHUNKS)]
                    else:
                        sampled = [matched_metas[0]]
                    matched_metas = sampled
                
                for meta in matched_metas:
                    text = f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}"
                    bboxes = json.loads(meta.get("bboxes", "[]"))
                    chunk_results.append({"text": text, "bboxes": bboxes})
                return chunk_results
            return []

        if intent == "STRUCTURE":
            print("  🔍 Đang tìm kiếm theo Cấu trúc (Titles)...")
            res_t = self.col_titles.query(query_embeddings=[self.embed_text(query)], n_results=5)
            if res_t["metadatas"][0]:
                for i, meta in enumerate(res_t["metadatas"][0]):
                    dist = res_t["distances"][0][i]
                    if dist > 0.6:
                        intent = "DETAIL"
                        break
                    best_breadcrumb = meta["breadcrumb"]
                    all_c = self.col_content.get(include=["metadatas", "documents"], limit=9999)
                    matched_raws, temp_bboxes = [], []
                    for meta_c in all_c["metadatas"]:
                        if meta_c["breadcrumb"] == best_breadcrumb or meta_c["breadcrumb"].startswith(best_breadcrumb + " >"):
                            matched_raws.append(meta_c["raw"])
                            temp_bboxes.extend(json.loads(meta_c.get("bboxes", "[]")))
                    if matched_raws:
                        temp_context = "\n\n".join(matched_raws)
                        if len(temp_context) < 300:
                            intent = "DETAIL"
                            break
                        chunk_results.append({"text": temp_context, "bboxes": temp_bboxes})
                        return chunk_results
            intent = "DETAIL"

        if intent == "DETAIL":
            print("  🔍 Đang tìm kiếm theo Chi tiết (Content)...")
            candidate_n = top_n * 2
            if self.bm25 is not None:
                bm25_scores = self.bm25.get_scores(query.lower().split())
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
                        chunk_results.append({"text": text, "bboxes": json.loads(meta.get("bboxes", "[]"))})
            else:
                res_c = self.col_content.query(query_embeddings=[self.embed_text(query)], n_results=top_n)
                for i in range(len(res_c["documents"][0])):
                    meta = res_c["metadatas"][0][i]
                    text = f"[{meta['breadcrumb']} - Trang {meta['page']}]:\n{meta['raw']}"
                    chunk_results.append({"text": text, "bboxes": json.loads(meta.get("bboxes", "[]"))})

        run = get_current_run_tree()
        if run:
            combined = "\n\n".join([c["text"] for c in chunk_results])
            run.metadata["intent_used"] = intent
            run.metadata["context_length"] = len(combined)

        return chunk_results

    # ------------------------------------------------------------------ #
    # Export highlighted PDF
    # ------------------------------------------------------------------ #
    def export_highlighted_pdf(self, bboxes, output_path):
        if not self.current_pdf_path or not bboxes:
            return None
        try:
            import fitz
            doc = fitz.open(self.current_pdf_path)
            for item in bboxes:
                p, bbox = item.get("p"), item.get("b")
                if p and bbox:
                    pi = p - 1
                    if 0 <= pi < len(doc):
                        r = fitz.Rect(bbox)
                        if not r.is_empty and not r.is_infinite:
                            doc[pi].add_highlight_annot(r)
            doc.save(output_path)
            doc.close()
            return output_path
        except Exception as e:
            print(f"  ❌ Lỗi export_highlighted_pdf: {e}")
            return None
