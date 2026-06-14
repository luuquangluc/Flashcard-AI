"""
modules/chat/chat_handler.py — Enhanced AI Chat with Flashcard cho RAG_luc.

Cải tiến so với phiên bản gốc:
  1. RAG-Augmented Context  : Tự động retrieve thêm ngữ cảnh từ document (BM25 + Vector fusion)
                              khi user hỏi, thay vì chỉ dùng card_context truyền vào.
  2. Intent Detection       : Phân loại câu hỏi thành 5 loại (explain/example/compare/apply/expand)
                              → điều chỉnh system prompt phù hợp từng loại.
  3. Cost Logging           : Gọi self.log_cost() sau mỗi lần generate → giữ tương thích RAG_luc.
  4. Streaming              : Phương thức chat_with_card_stream() dùng SSE nếu frontend muốn.
  5. Source Citation        : Đính kèm breadcrumb + page của chunk vào response metadata.
  6. Graceful Fallback      : Nếu retrieve_context không khả dụng → dùng card_context gốc.
  7. Semantic Cache         : In-memory TTL cache với similarity matching (ý tưởng từ Day25):
                              - Tránh gọi LLM cho các câu hỏi tương đồng đã hỏi trước đó
                              - Privacy guard: không cache câu chứa thông tin nhạy cảm
                              - False-hit guard: tránh trả sai khi số 4 chữ số khác nhau
                              - Cache key = "{card_id}|{user_message}" (per-card scope)
  8. Guardrail              : 4-layer input validation trước khi gọi LLM:
                              - Injection detection (block)
                              - Toxic content (block)
                              - PII detection (sanitize/mask)
                              - Length limit (truncate)
                              - Off-topic detection (block)
  9. Mem0 Long-term Memory  : Lưu lịch sử hội thoại theo user_id vào Mem0:
                              - Tự động retrieve memories liên quan trước khi gọi LLM
                              - Inject vào system prompt dưới dạng [USER_MEMORY]
                              - Lưu lượt chat vừa xong vào Mem0 sau khi generate
                              - Graceful fallback nếu mem0ai chưa được cài
                              - Hỗ trợ cả chat_with_card() và chat_with_card_stream()

Architecture:
  - ChatMixin được kế thừa bởi RAGSystem(RAGCore, RAGRetrieval, RAGGeneration, ChatMixin)
  - Host class cần: self.client, self.model_name, self.log_cost(), self.retrieve_context()
"""

import hashlib
import logging
import re
import time
import math
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable
except ImportError:
    def traceable(name=None, run_type=None, **kwargs):
        def decorator(func): return func
        return decorator

# Guardrail import (lazy để tránh circular import)
# Tạm thời vô hiệu hóa Guardrail để tiết kiệm bộ nhớ trên Render
HAS_GUARDRAIL = False
_CHAT_GUARDRAIL = None
_GUARDRAIL_DB = None

# ──────────────────────────────────────────────────────────────────────────────
# Supabase Chat Memory — persistent episode & profile storage
# ──────────────────────────────────────────────────────────────────────────────
# TẮT CHAT MEMORY ĐỂ TIẾT KIỆM RAM TRÊN RENDER
HAS_CHAT_MEMORY_DB = False
chat_memory_db = None

# ──────────────────────────────────────────────────────────────────────────────
# Mem0 — Long-term user memory (Vô hiệu hóa hoàn toàn)
# ──────────────────────────────────────────────────────────────────────────────
HAS_MEM0 = False
_MEM0_INSTANCE = None

# ──────────────────────────────────────────────────────────────────────────────
# Intent Classification
# ──────────────────────────────────────────────────────────────────────────────

INTENT_EXPLAIN = "explain"
INTENT_EXAMPLE = "example"
INTENT_COMPARE = "compare"
INTENT_APPLY   = "apply"
INTENT_EXPAND  = "expand"
INTENT_GENERAL = "general"

_INTENT_KEYWORDS = {
    INTENT_EXPLAIN: ["tại sao", "giải thích", "nghĩa là gì", "có nghĩa", "why", "explain", "what is", "định nghĩa", "là gì"],
    INTENT_EXAMPLE: ["ví dụ", "minh họa", "cho thấy", "example", "instance", "demonstrate", "cụ thể"],
    INTENT_COMPARE: ["so sánh", "khác nhau", "giống", "compare", "difference", "versus", "vs", "phân biệt"],
    INTENT_APPLY:   ["ứng dụng", "dùng khi", "thực tế", "thực hành", "apply", "use case", "khi nào dùng"],
    INTENT_EXPAND:  ["thêm", "chi tiết", "liên quan", "expand", "more", "detail", "deeper", "nói thêm", "mở rộng"],
}

_INTENT_INSTRUCTIONS = {
    INTENT_EXPLAIN: "Hãy GIẢI THÍCH rõ ràng, đơn giản như đang nói chuyện với học sinh.",
    INTENT_EXAMPLE: "Hãy đưa ra VÍ DỤ cụ thể, thực tế và dễ nhớ.",
    INTENT_COMPARE: "Hãy SO SÁNH điểm giống và khác nhau một cách có cấu trúc.",
    INTENT_APPLY:   "Hãy trình bày ỨNG DỤNG thực tế và cho biết khi nào nên dùng.",
    INTENT_EXPAND:  "Hãy MỞ RỘNG và cung cấp thêm thông tin liên quan chi tiết hơn.",
    INTENT_GENERAL: "Hãy trả lời trực tiếp, ngắn gọn và chính xác.",
}


def _detect_intent(message: str) -> str:
    msg_lower = message.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return intent
    return INTENT_GENERAL


def _build_system_prompt(card_context: str, question: str, answer: str,
                          intent_instruction: str, sources: list,
                          user_memories: str = "") -> str:
    ctx = card_context[:4000] if len(card_context) > 4000 else card_context
    source_note = ""
    if sources:
        breadcrumbs = list({s["breadcrumb"] for s in sources if s.get("breadcrumb")})
        pages = list({str(s["page"]) for s in sources if s.get("page")})
        parts = []
        if breadcrumbs:
            parts.append("Mục: " + " | ".join(breadcrumbs[:3]))
        if pages:
            parts.append("Trang: " + ", ".join(pages[:5]))
        if parts:
            source_note = f"\n\n[Nguồn trích dẫn từ tài liệu]: {' — '.join(parts)}"

    memory_block = ""
    if user_memories:
        memory_block = f"""

<USER_MEMORY>
Những điều bạn đã biết về người dùng này từ các buổi học trước:
{user_memories}
</USER_MEMORY>"""

    return f"""Bạn là chuyên gia hỗ trợ học tập thông minh.
Người dùng đang học Flashcard và muốn hiểu sâu hơn.

<CARD_CONTEXT>
{ctx}
</CARD_CONTEXT>

<FLASHCARD>
Câu hỏi: {question}
Câu trả lời: {answer}
</FLASHCARD>{memory_block}

Nhiệm vụ:
1. {intent_instruction}
2. Dựa chủ yếu vào ngữ cảnh tài liệu. Nếu vượt ngoài tài liệu, ghi rõ "(kiến thức chung)".
3. Câu trả lời ngắn gọn, súc tích, dễ hiểu.
4. Nếu USER_MEMORY có thông tin liên quan, cá nhân hóa câu trả lời cho phù hợp.
5. Trả lời bằng tiếng Việt.
6. [QUY TẮC NGHIÊM NGẶT] Nếu người dùng hỏi về công thức nấu ăn, giá vàng, thời tiết, phim ảnh, mua sắm, du lịch, hoặc BẤT KỲ chủ đề nào KHÔNG liên quan đến flashcard/tài liệu đang học, bạn PHẢI từ chối lịch sự và nhắc nhở rằng bạn chỉ là trợ lý học tập.{source_note}"""


# ──────────────────────────────────────────────────────────────────────────────
# Semantic Cache (ý tưởng từ Day25 - reliability_lab/cache.py)
# ──────────────────────────────────────────────────────────────────────────────

# Privacy guard: không cache các câu hỏi chứa thông tin nhạy cảm
_PRIVACY_PATTERNS = re.compile(
    r"\b(mật\s*khẩu|password|tài\s*khoản|account|credit.card|ssn|số\s*thẻ|pin\s*\d+|user\s*\d+)\b",
    re.IGNORECASE,
)


def _is_uncacheable(query: str) -> bool:
    """True nếu câu hỏi chứa thông tin nhạy cảm → không cache."""
    return bool(_PRIVACY_PATTERNS.search(query))


def _looks_like_false_hit(query: str, cached_key: str) -> bool:
    """
    True nếu query và cached_key chứa các số 4 chữ số KHÁC NHAU.
    Ví dụ: "năm 2023" vs "năm 2024" → tuy similar nhưng khác nhau về năm → không trả cache.
    Lấy từ Day25/cache.py._looks_like_false_hit()
    """
    nums_q = set(re.findall(r"\b\d{4}\b", query))
    nums_c = set(re.findall(r"\b\d{4}\b", cached_key))
    return bool(nums_q and nums_c and nums_q != nums_c)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


@dataclass
class _CacheEntry:
    key: str          # câu hỏi gốc (user_message)
    scope: str        # card_id hoặc question hash → scope cache per-card
    value: str        # AI response
    intent: str       # intent đã detect
    vector: list[float] = None # vector embedding của câu hỏi
    created_at: float = field(default_factory=time.time)
    hits: int = 0


class ChatSemanticCache:
    """
    In-memory semantic cache cho chat responses.

    Đặc điểm (từ Day25 + mở rộng):
      - TTL-based expiry: entries tự xóa sau ttl_seconds
      - Scope per-card: mỗi thẻ có không gian cache riêng (scope = card hash)
      - Similarity matching: token Jaccard + char n-gram (không cần vector embedding)
      - Privacy guard: không cache câu chứa thông tin nhạy cảm
      - False-hit guard: không trả cache nếu số 4 chữ số khác nhau
      - Intent scope: chỉ match cache nếu cùng intent

    Args:
        ttl_seconds:          Thời gian sống mỗi entry (mặc định 30 phút)
        similarity_threshold: Ngưỡng similarity để coi là cache hit (mặc định 0.82)
        max_entries:          Tối đa số entry để tránh memory leak
    """

    def __init__(
        self,
        ttl_seconds: int = 1800,
        similarity_threshold: float = 0.82,
        max_entries: int = 500,
    ):
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self._entries: list[_CacheEntry] = []
        self.stats = {"hits": 0, "misses": 0, "skipped_privacy": 0, "false_hits_blocked": 0}

    def _evict_expired(self):
        now = time.time()
        self._entries = [e for e in self._entries if now - e.created_at <= self.ttl_seconds]

    def get(self, user_message: str, user_vector: list[float] = None, scope: str = "", intent: str = "") -> Optional[str]:
        """
        Tìm cached response cho user_message bằng Cosine Similarity.

        Args:
            user_message: Câu hỏi của user
            user_vector:  Vector embedding của user_message
            scope:        Card scope (thường là hash của card question)
            intent:       Intent đã detect — chỉ match nếu cùng intent

        Returns:
            Cached response string hoặc None nếu miss
        """
        if _is_uncacheable(user_message):
            self.stats["skipped_privacy"] += 1
            return None

        self._evict_expired()

        best_entry = None
        best_score = 0.0

        for entry in self._entries:
            # Scope filter: chỉ xét entries cùng card
            if scope and entry.scope != scope:
                continue
            # Intent filter: không trả explain khi user hỏi example
            if intent and entry.intent and entry.intent != intent:
                continue

            score = 0.0
            if user_vector and entry.vector:
                score = _cosine_similarity(user_vector, entry.vector)
            else:
                # Fallback to exact match if vectors are missing
                if user_message.lower().strip() == entry.key.lower().strip():
                    score = 1.0

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= self.similarity_threshold and best_entry:
            # False-hit guard
            if _looks_like_false_hit(user_message, best_entry.key):
                self.stats["false_hits_blocked"] += 1
                logger.debug(f"[Cache] False-hit blocked: '{user_message}' vs '{best_entry.key}'")
                self.stats["misses"] += 1
                return None

            best_entry.hits += 1
            self.stats["hits"] += 1
            logger.info(f"[Cache] HIT (score={best_score:.3f}, hits={best_entry.hits}) | '{user_message[:50]}'")
            return best_entry.value

        self.stats["misses"] += 1
        return None

    def set(self, user_message: str, response: str, user_vector: list[float] = None, scope: str = "", intent: str = "") -> None:
        """
        Lưu response vào cache kèm theo vector.

        Args:
            user_message: Câu hỏi của user (cache key)
            response:     AI response (cache value)
            user_vector:  Vector embedding của câu hỏi
            scope:        Card scope
            intent:       Intent đã detect
        """
        if _is_uncacheable(user_message):
            return

        self._evict_expired()

        # LRU-like eviction khi đầy: xóa entry cũ nhất và ít hit nhất
        if len(self._entries) >= self.max_entries:
            self._entries.sort(key=lambda e: (e.hits, e.created_at))
            self._entries = self._entries[self.max_entries // 4:]

        self._entries.append(_CacheEntry(
            key=user_message,
            scope=scope,
            value=response,
            intent=intent,
            vector=user_vector,
        ))
        logger.debug(f"[Cache] SET scope={scope} | '{user_message[:50]}'")

    def invalidate_scope(self, scope: str) -> int:
        """Xóa toàn bộ cache của một card cụ thể (dùng khi card bị sửa/xóa)."""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.scope != scope]
        removed = before - len(self._entries)
        logger.info(f"[Cache] Invalidated scope='{scope}': removed {removed} entries")
        return removed

    def clear(self) -> None:
        """Xóa toàn bộ cache."""
        self._entries.clear()
        logger.info("[Cache] Cleared all entries")

    def get_stats(self) -> dict:
        """Trả về thống kê cache để monitoring."""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = round(self.stats["hits"] / total, 3) if total > 0 else 0.0
        return {
            **self.stats,
            "total_requests": total,
            "hit_rate": hit_rate,
            "active_entries": len(self._entries),
            "ttl_seconds": self.ttl_seconds,
            "similarity_threshold": self.similarity_threshold,
        }

    @staticmethod
    def make_card_scope(question: str) -> str:
        """Tạo scope string từ câu hỏi trên thẻ (dùng MD5 8 ký tự)."""
        return hashlib.md5(question.strip().lower().encode()).hexdigest()[:8]


# Singleton cache instance toàn bộ ứng dụng (shared across all RAGSystem instances)
_GLOBAL_CHAT_CACHE = ChatSemanticCache(
    ttl_seconds=1800,           # 30 phút
    similarity_threshold=0.82,  # ngưỡng similarity
    max_entries=500,
)


# ──────────────────────────────────────────────────────────────────────────────
# Mem0 Helpers — lưu & truy xuất long-term memory theo user_id
# ──────────────────────────────────────────────────────────────────────────────

def mem0_add(user_id: str, messages: list[dict], metadata: dict = None) -> None:
    """
    Lưu lượt hội thoại vào Mem0 long-term memory.

    Args:
        user_id:  ID người dùng (dùng để phân tách memory giữa các user)
        messages: Danh sách messages [{role, content}] của lượt hội thoại vừa xong
        metadata: Metadata tuỳ chọn (vd: {"card_id": "...", "topic": "..."})
    """
    if not HAS_MEM0 or not _MEM0_INSTANCE or not user_id:
        return
    try:
        _MEM0_INSTANCE.add(messages, user_id=user_id, metadata=metadata or {})
        logger.debug(f"[Mem0] Saved {len(messages)} messages for user={user_id}")
    except Exception as e:
        logger.warning(f"[Mem0] Failed to save memory: {e}")


def mem0_search(user_id: str, query: str, limit: int = 5) -> str:
    """
    Truy xuất long-term memory liên quan đến query của user.

    Returns:
        Chuỗi text tóm tắt các memory liên quan, hoặc "" nếu không có.
    """
    if not HAS_MEM0 or not _MEM0_INSTANCE or not user_id:
        return ""
    try:
        results = _MEM0_INSTANCE.search(query, user_id=user_id, limit=limit)
        if not results or not results.get("results"):
            return ""
        memories = [r.get("memory", "") for r in results["results"] if r.get("memory")]
        if not memories:
            return ""
        return "\n".join(f"- {m}" for m in memories)
    except Exception as e:
        logger.warning(f"[Mem0] Search failed: {e}")
        return ""


def mem0_get_all(user_id: str) -> list[dict]:
    """Lấy toàn bộ memories của một user (dùng cho admin / debug)."""
    if not HAS_MEM0 or not _MEM0_INSTANCE or not user_id:
        return []
    try:
        result = _MEM0_INSTANCE.get_all(user_id=user_id)
        return result.get("results", [])
    except Exception as e:
        logger.warning(f"[Mem0] get_all failed: {e}")
        return []


def mem0_delete_all(user_id: str) -> bool:
    """Xóa toàn bộ memories của một user (GDPR / reset)."""
    if not HAS_MEM0 or not _MEM0_INSTANCE or not user_id:
        return False
    try:
        _MEM0_INSTANCE.delete_all(user_id=user_id)
        logger.info(f"[Mem0] Deleted all memories for user={user_id}")
        return True
    except Exception as e:
        logger.warning(f"[Mem0] delete_all failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# ChatMixin — kế thừa bởi RAGSystem
# ──────────────────────────────────────────────────────────────────────────────

class ChatMixin:
    """
    Enhanced Mixin cung cấp tính năng Chat with Card cho RAGSystem.

    Yêu cầu host class có:
      - self.client          : OpenAI client
      - self.model_name      : tên model (e.g., "gpt-4o-mini")
      - self.log_cost()      : hàm log chi phí API
      - self.retrieve_context() (optional): hàm tìm kiếm ngữ cảnh từ RAGRetrieval
    """

    @property
    def chat_cache(self) -> ChatSemanticCache:
        """Lazy singleton cache — dùng chung global instance."""
        return _GLOBAL_CHAT_CACHE

    def _chat_retrieve_extra_context(self, question: str, user_message: str, top_n: int = 3):
        """
        Retrieve thêm ngữ cảnh từ document dựa trên câu hỏi của user.
        Dùng retrieve_context() có sẵn trong RAGRetrieval.
        """
        if not hasattr(self, "retrieve_context") or not hasattr(self, "chunks") or not self.chunks:
            return "", []

        try:
            combined_query = f"{question} {user_message}".strip()
            chunk_results = self.retrieve_context(
                query=combined_query,
                intent="DETAIL",
                top_n=top_n
            )
            if not chunk_results:
                return "", []

            sources = []
            extra_texts = []
            for c in chunk_results:
                text = c.get("text", "")
                if not text:
                    continue
                breadcrumb, page = "", ""
                if text.startswith("[") and "]:" in text:
                    header = text.split("]:")[0][1:]
                    if " - Trang " in header:
                        breadcrumb, page = header.rsplit(" - Trang ", 1)
                    else:
                        breadcrumb = header
                raw_text = text.split("]:\n", 1)[-1] if "]:\n" in text else text
                extra_texts.append(raw_text.strip())
                sources.append({"breadcrumb": breadcrumb, "page": page})

            return "\n---\n".join(extra_texts), sources

        except Exception as e:
            logger.warning(f"[ChatMixin] retrieve extra context failed: {e}")
            return "", []

    @traceable(name="Chat with Card (Enhanced + Cache)", run_type="llm")
    def chat_with_card(self, card_context, question, answer, user_message, history=None):
        """
        Chat về một thẻ Flashcard cụ thể với Semantic Cache.

        Flow:
          1. Detect intent (keyword-based, 0 LLM call)
          2. Check semantic cache → trả về ngay nếu hit (bỏ qua bước 3-5)
          3. RAG Augmentation: retrieve thêm context từ document
          4. Build prompt + gọi LLM
          5. Log cost + store vào cache

        Args:
            card_context: Ngữ cảnh PDF gốc của thẻ (truyền từ frontend)
            question:     Câu hỏi trên thẻ
            answer:       Câu trả lời trên thẻ
            user_message: Tin nhắn mới từ người dùng
            history:      Lịch sử chat [{role, content}, ...]

        Returns:
            str: Phản hồi từ AI
        """
        t_start = time.perf_counter()
        history = history or []

        # Step 0: Guardrail check — validate input trước tất cả
        if HAS_GUARDRAIL and _CHAT_GUARDRAIL:
            guard_result = _CHAT_GUARDRAIL.check(
                user_message,
                card_question=question,
                openai_client=getattr(self, 'client', None),  # Truyền client cho LLM off-topic router
            )

            # Lấy user_id từ host class nếu có (RAGSystem có session_user_id không? tuỳ impl)
            _uid = getattr(self, "_current_user_id", None) or getattr(self, "session_user_id", None)

            # Log vào Supabase DB (background thread, non-blocking)
            if _GUARDRAIL_DB and guard_result.violation.value != "none":
                _GUARDRAIL_DB.log(
                    result=guard_result,
                    source="chat",
                    raw_input=user_message,
                    user_id=_uid,
                )

            if not guard_result.allowed:
                logger.warning(f"[ChatMixin] Guardrail blocked: {guard_result.violation.value}")
                return f"[Guardrail] {guard_result.reason}"
            # Dùng phiên bản đã sanitize (PII masked / truncated) nếu có
            if guard_result.sanitized:
                logger.info(f"[ChatMixin] Guardrail sanitized message ({guard_result.violation.value})")
                user_message = guard_result.sanitized

        # Step 1: Detect intent
        intent = _detect_intent(user_message)
        intent_instruction = _INTENT_INSTRUCTIONS[intent]
        logger.info(f"[ChatMixin] intent={intent}")

        # Step 1b: Generate Vector Embedding for Cache (text-embedding-3-small)
        user_vector = None
        if not _is_uncacheable(user_message):
            try:
                from config.settings import EMBEDDING_MODEL_NAME
                emb_res = self.client.embeddings.create(input=user_message.strip(), model=EMBEDDING_MODEL_NAME)
                user_vector = emb_res.data[0].embedding
            except Exception as e:
                logger.warning(f"[ChatMixin] Failed to generate embedding for cache: {e}")

        # Step 2: Check semantic cache (per-card scope)
        card_scope = ChatSemanticCache.make_card_scope(question)
        cached = self.chat_cache.get(user_message, user_vector=user_vector, scope=card_scope, intent=intent)
        if cached is not None:
            t_ms = round((time.perf_counter() - t_start) * 1000, 1)
            logger.info(f"[ChatMixin] Cache HIT — returned in {t_ms}ms")
            return cached

        # Step 3: RAG Augmentation
        augmented_context = card_context or ""
        sources = []

        extra_text, extra_sources = self._chat_retrieve_extra_context(question, user_message, top_n=3)
        if extra_text:
            augmented_context = (
                f"[Ngữ cảnh từ thẻ]\n{augmented_context}\n\n"
                f"[Ngữ cảnh bổ sung từ tài liệu]\n{extra_text}"
            )
            sources = extra_sources
            logger.info(f"[ChatMixin] Augmented with {len(extra_sources)} extra chunks")

        # Step 3b: Mem0 — retrieve long-term memory của user
        user_memories = ""
        _uid = getattr(self, "_current_user_id", None) or getattr(self, "session_user_id", None)
        if _uid and HAS_MEM0:
            user_memories = mem0_search(_uid, query=f"{question} {user_message}", limit=5)
            if user_memories:
                logger.info(f"[Mem0] Retrieved memories for user={_uid}")

        # Step 4: Build prompt
        system_prompt = _build_system_prompt(
            card_context=augmented_context,
            question=question,
            answer=answer,
            intent_instruction=intent_instruction,
            sources=sources,
            user_memories=user_memories,
        )

        # Step 5: Build messages (limit history to last 6 turns)
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": user_message})

        # Step 6: Generate response
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7
            )

            self.log_cost(
                self.model_name,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                "Chat with Card"
            )

            result_text = response.choices[0].message.content

            # Step 7: Store in cache (chỉ cache nếu không có history dài — history = conversational, khó reuse)
            if len(history) <= 2:
                self.chat_cache.set(user_message, result_text, user_vector=user_vector, scope=card_scope, intent=intent)

            # Step 8: Lưu lượt hội thoại vào Mem0 long-term memory
            if _uid and HAS_MEM0:
                mem0_add(
                    user_id=_uid,
                    messages=[
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": result_text},
                    ],
                    metadata={"card_question": question, "intent": intent},
                )

            # Step 9: Lưu episode + cập nhật profile vào Supabase
            if _uid and HAS_CHAT_MEMORY_DB and chat_memory_db and chat_memory_db.is_ready:
                chat_memory_db.save_episode(
                    user_id=_uid,
                    card_scope=card_scope,
                    user_message=user_message,
                    ai_response=result_text,
                    intent=intent,
                    card_question=question,
                )
                chat_memory_db.update_profile(
                    user_id=_uid,
                    topic=question[:100] if question else "",
                    intent=intent,
                )

            t_ms = round((time.perf_counter() - t_start) * 1000, 1)
            cache_stats = self.chat_cache.get_stats()
            logger.info(
                f"[ChatMixin] Generated in {t_ms}ms | intent={intent} | "
                f"augmented={bool(extra_text)} | "
                f"cache hit_rate={cache_stats['hit_rate']:.1%}"
            )

            return result_text

        except Exception as e:
            logger.error(f"[ChatMixin] Error in chat_with_card: {e}")
            return f"Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu: {str(e)}"

    def chat_with_card_stream(self, card_context, question, answer, user_message, history=None):
        """
        Streaming version của chat_with_card — dùng cho SSE (text/event-stream).
        Lưu ý: streaming không dùng cache vì không biết trước full response.
        Sau khi stream xong, response được accumulate và store vào cache.

        Yields:
            str: token từng phần
        """
        history = history or []

        intent = _detect_intent(user_message)
        intent_instruction = _INTENT_INSTRUCTIONS[intent]
        card_scope = ChatSemanticCache.make_card_scope(question)

        # Generate Vector Embedding for Cache
        user_vector = None
        if not _is_uncacheable(user_message):
            try:
                from config.settings import EMBEDDING_MODEL_NAME
                emb_res = self.client.embeddings.create(input=user_message.strip(), model=EMBEDDING_MODEL_NAME)
                user_vector = emb_res.data[0].embedding
            except Exception as e:
                pass

        # Check cache trước (trả về từng char để giả lập stream)
        cached = self.chat_cache.get(user_message, user_vector=user_vector, scope=card_scope, intent=intent)
        if cached is not None:
            logger.info("[ChatMixin] Cache HIT (stream mode) — streaming cached response")
            # Giả lập streaming từ cache với delay nhỏ
            chunk_size = 5
            for i in range(0, len(cached), chunk_size):
                yield cached[i:i+chunk_size]
            return

        # RAG Augmentation
        augmented_context = card_context or ""
        sources = []
        extra_text, extra_sources = self._chat_retrieve_extra_context(question, user_message, top_n=3)
        if extra_text:
            augmented_context = (
                f"[Ngữ cảnh từ thẻ]\n{augmented_context}\n\n"
                f"[Ngữ cảnh bổ sung từ tài liệu]\n{extra_text}"
            )
            sources = extra_sources

        # Mem0 — retrieve long-term memory
        user_memories = ""
        _uid = getattr(self, "_current_user_id", None) or getattr(self, "session_user_id", None)
        if _uid and HAS_MEM0:
            user_memories = mem0_search(_uid, query=f"{question} {user_message}", limit=5)

        system_prompt = _build_system_prompt(
            card_context=augmented_context,
            question=question,
            answer=answer,
            intent_instruction=intent_instruction,
            sources=sources,
            user_memories=user_memories,
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": user_message})

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                stream=True
            )
            full_response = []
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_response.append(delta.content)
                    yield delta.content

            # Store accumulated response vào cache
            if len(history) <= 2:
                complete_text = "".join(full_response)
                if complete_text:
                    self.chat_cache.set(user_message, complete_text, user_vector=user_vector, scope=card_scope, intent=intent)
                    # Lưu vào Mem0 long-term memory
                    if _uid and HAS_MEM0:
                        mem0_add(
                            user_id=_uid,
                            messages=[
                                {"role": "user", "content": user_message},
                                {"role": "assistant", "content": complete_text},
                            ],
                            metadata={"card_question": question, "intent": intent},
                        )
                    # Lưu episode + profile vào Supabase
                    if _uid and HAS_CHAT_MEMORY_DB and chat_memory_db and chat_memory_db.is_ready:
                        chat_memory_db.save_episode(
                            user_id=_uid,
                            card_scope=card_scope,
                            user_message=user_message,
                            ai_response=complete_text,
                            intent=intent,
                            card_question=question,
                        )
                        chat_memory_db.update_profile(
                            user_id=_uid,
                            topic=question[:100] if question else "",
                            intent=intent,
                        )

        except Exception as e:
            logger.error(f"[ChatMixin] Streaming error: {e}")
            yield f"\n[Lỗi streaming: {str(e)}]"

    def get_chat_cache_stats(self) -> dict:
        """Trả về thống kê cache — dùng cho admin dashboard / monitoring."""
        return self.chat_cache.get_stats()

    def invalidate_card_cache(self, question: str) -> int:
        """Xóa cache của một thẻ cụ thể — gọi khi thẻ bị sửa/xóa."""
        scope = ChatSemanticCache.make_card_scope(question)
        return self.chat_cache.invalidate_scope(scope)

    # ── Mem0 public helpers ────────────────────────────────────────────────────

    def get_user_memories(self, user_id: str) -> list[dict]:
        """
        Lấy toàn bộ long-term memories của user.
        Dùng cho trang profile / admin dashboard.

        Returns:
            List[dict] với các trường: id, memory, created_at, ...
        """
        return mem0_get_all(user_id)

    def delete_user_memories(self, user_id: str) -> bool:
        """
        Xóa toàn bộ memories của user (GDPR / user reset).

        Returns:
            True nếu thành công, False nếu lỗi hoặc Mem0 không khả dụng.
        """
        return mem0_delete_all(user_id)

    @property
    def mem0_enabled(self) -> bool:
        """Kiểm tra Mem0 có đang hoạt động không."""
        return HAS_MEM0