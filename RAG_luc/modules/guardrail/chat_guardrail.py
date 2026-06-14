"""
modules/guardrail/chat_guardrail.py — Guardrail cho Chat with Card.

Các lớp kiểm tra (theo thứ tự ưu tiên):
  Layer 1 — Injection Guard  : Phát hiện cố tình jailbreak / override system prompt
  Layer 2 — Toxic Guard      : Nội dung thù địch, xúc phạm, nguy hiểm
  Layer 3 — PII Guard        : Người dùng vô tình gửi thông tin nhạy cảm
  Layer 4 — Length Guard     : Tin nhắn quá dài → truncate thay vì block
  Layer 5 — Off-topic Guard  : 2 lớp:
              5a. Regex pre-filter  (0ms)    — chặn nhanh các câu rõ ràng off-topic
              5b. LLM Intent Router (~400ms) — gọi gpt-4o-mini phân loại on/off-topic

Thiết kế:
  - Layer 1-4: Rule-based thuần túy → 0ms latency
  - Layer 5a:  Regex pre-filter     → 0ms (chặn từ khóa hiển nhiên)
  - Layer 5b:  LLM-based router     → ~300-500ms (chỉ gọi khi regex không chắc)
  - Trả về GuardrailResult với reason tiếng Việt để hiển thị cho user
  - Sanitize thay vì block khi có thể (PII mask, truncate)
  - Graceful fallback: nếu không có OpenAI client → chỉ dùng regex
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

from modules.guardrail.base import (
    BaseGuardrail, GuardrailResult, GuardrailViolation,
    INJECTION_PATTERNS, TOXIC_PATTERNS, CODE_INJECTION_PATTERNS, 
    ADVICE_PATTERNS, POLITICS_PATTERNS, check_gibberish, check_pii, mask_pii
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

CHAT_MAX_CHARS      = 2000   # Độ dài tối đa một tin nhắn chat
CHAT_WARN_CHARS     = 1500   # Cảnh báo khi gần giới hạn
OFF_TOPIC_THRESHOLD = 0.15   # Tỷ lệ từ chung tối thiểu để coi là on-topic

# ── Layer 5a: Regex pre-filter — chặn nhanh các từ khóa rõ ràng off-topic ────
_CLEAR_OFF_TOPIC = re.compile(
    r"\b(viết\s+code|lập\s+trình\s+game|hướng\s+dẫn\s+hack|cách\s+làm\s+tiền\s+nhanh|"
    r"dự\s+đoán\s+xổ\s+số|kết\s+quả\s+bóng\s+đá|phim\s+sex|"
    r"write\s+me\s+a\s+(story|poem|song)|generate\s+image|"
    r"who\s+will\s+win\s+the\s+(game|match|election)|"
    # === Mở rộng: thêm các nhóm off-topic phổ biến ===
    # Ẩm thực / Nấu ăn
    r"công\s+thức|nguyên\s+liệu\s+nấu|cách\s+làm\s+bánh|cách\s+nấu|"
    r"recipe|how\s+to\s+cook|how\s+to\s+bake|"
    # Thời tiết / Thời sự
    r"thời\s+tiết\s+hôm\s+nay|dự\s+báo\s+thời\s+tiết|weather\s+today|"
    # Giá cả / Tài chính thực tế
    r"giá\s+vàng|giá\s+đô|giá\s+xăng|tỷ\s+giá|gold\s+price|"
    # Giải trí
    r"phim\s+hay|bài\s+hát|nhạc\s+gì|xem\s+phim|movie\s+recommend|"
    # Mua sắm / Thương mại
    r"mua\s+ở\s+đâu|giá\s+bao\s+nhiêu|shopee|lazada|tiki|"
    # Du lịch
    r"đi\s+du\s+lịch|chỗ\s+nào\s+vui|khách\s+sạn|travel\s+to)\b",
    re.IGNORECASE,
)

# ── Layer 5b: LLM Intent Router ──────────────────────────────────────────────
# Prompt ngắn gọn, tối ưu cho gpt-4o-mini (~100 input tokens, ~5 output tokens)
_LLM_OFFTOPIC_SYSTEM_PROMPT = (
    "You are a strict topic classifier for a Flashcard Study Assistant.\n"
    "The assistant ONLY helps users learn, study, and understand educational flashcard content.\n\n"
    "Your job: Decide if the user's message is ON-TOPIC or OFF-TOPIC.\n\n"
    "ON-TOPIC examples (allowed):\n"
    "- Questions about the flashcard content (explain, compare, examples)\n"
    "- Asking for more detail, context, or clarification\n"
    "- Study strategies, mnemonics, memory tips related to the card\n"
    "- Asking to rephrase or simplify the answer\n\n"
    "OFF-TOPIC examples (blocked):\n"
    "- Recipes, cooking, food preparation\n"
    "- Weather, news, current events, prices (gold, stocks, gas)\n"
    "- Entertainment (movies, songs, games)\n"
    "- Shopping, travel, directions\n"
    "- Personal advice unrelated to studying\n"
    "- Creative writing (stories, poems) unrelated to the card\n"
    "- Any request that has nothing to do with learning the flashcard\n\n"
    "Respond with EXACTLY one word: ON or OFF"
)


# ──────────────────────────────────────────────────────────────────────────────
# Individual Layer Checkers
# ──────────────────────────────────────────────────────────────────────────────

def _check_injection(message: str) -> Optional[GuardrailResult]:
    """Layer 1: Prompt injection / jailbreak detection."""
    if INJECTION_PATTERNS.search(message):
        logger.warning(f"[ChatGuardrail] Injection detected: '{message[:80]}'")
        return GuardrailResult.block(
            GuardrailViolation.PROMPT_INJECTION,
            reason="⛔ Yêu cầu của bạn chứa nội dung cố tình thay đổi hành vi AI. "
                   "Vui lòng đặt câu hỏi học tập thông thường.",
            matched=INJECTION_PATTERNS.findall(message)
        )
    return None


def _check_toxic(message: str) -> Optional[GuardrailResult]:
    """Layer 2: Toxic / harmful content."""
    if TOXIC_PATTERNS.search(message):
        logger.warning(f"[ChatGuardrail] Toxic content detected: '{message[:80]}'")
        return GuardrailResult.block(
            GuardrailViolation.TOXIC_CONTENT,
            reason="⛔ Tin nhắn của bạn chứa nội dung không phù hợp. "
                   "Hệ thống chỉ hỗ trợ các câu hỏi học tập.",
        )
    return None

def _check_gibberish(message: str) -> Optional[GuardrailResult]:
    """Layer: Phát hiện nội dung rác vô nghĩa."""
    if check_gibberish(message):
        logger.warning(f"[ChatGuardrail] Gibberish detected: '{message[:80]}'")
        return GuardrailResult.block(
            GuardrailViolation.GIBBERISH,
            reason="⛔ Tin nhắn có vẻ chứa nội dung không hợp lệ hoặc bị lỗi gõ. "
                   "Vui lòng nhập một câu hỏi rõ ràng hơn.",
        )
    return None

def _check_code_injection(message: str) -> Optional[GuardrailResult]:
    """Layer: Ngăn chặn shell execution / XSS injection."""
    if CODE_INJECTION_PATTERNS.search(message):
        logger.warning(f"[ChatGuardrail] Code injection detected: '{message[:80]}'")
        return GuardrailResult.block(
            GuardrailViolation.CODE_INJECTION,
            reason="⛔ Yêu cầu không được phép (Code Injection/Execution block). "
                   "Hệ thống chỉ giải đáp kiến thức, không chạy mã lệnh.",
        )
    return None

def _check_sensitive_topics(message: str) -> Optional[GuardrailResult]:
    """Layer: Chặn xin lời khuyên y tế/tài chính và bàn luận chính trị."""
    if ADVICE_PATTERNS.search(message):
        logger.warning(f"[ChatGuardrail] Advice request detected: '{message[:80]}'")
        return GuardrailResult.block(
            GuardrailViolation.ADVICE_REQUEST,
            reason="⛔ Xin lỗi, tôi là trợ lý học tập và không thể cung cấp lời khuyên "
                   "đầu tư tài chính hoặc chẩn đoán y tế.",
        )
    
    if POLITICS_PATTERNS.search(message):
        logger.warning(f"[ChatGuardrail] Political content detected: '{message[:80]}'")
        return GuardrailResult.block(
            GuardrailViolation.POLITICS,
            reason="⛔ Xin lỗi, hệ thống không hỗ trợ bàn luận về các chủ đề chính trị "
                   "hoặc tôn giáo. Vui lòng tập trung vào nội dung bài học.",
        )
    return None


def _check_pii(message: str) -> Optional[GuardrailResult]:
    """
    Layer 3: PII detection.
    Không block mà sanitize (mask) và cho phép đi qua với cảnh báo.
    """
    has_pii, detected_types = check_pii(message)
    if has_pii:
        sanitized = mask_pii(message)
        logger.info(f"[ChatGuardrail] PII masked: {detected_types}")
        # Cho phép đi qua nhưng dùng phiên bản đã mask
        return GuardrailResult(
            allowed=True,
            violation=GuardrailViolation.PII_DETECTED,
            reason=f"ℹ️ Tin nhắn của bạn chứa thông tin nhạy cảm ({', '.join(detected_types)}) "
                   f"và đã được ẩn tự động.",
            sanitized=sanitized,
            metadata={"pii_types": detected_types},
        )
    return None


def _check_length(message: str) -> Optional[GuardrailResult]:
    """
    Layer 4: Length check.
    Truncate thay vì block nếu quá dài.
    """
    if len(message) > CHAT_MAX_CHARS:
        truncated = message[:CHAT_MAX_CHARS] + "..."
        logger.info(f"[ChatGuardrail] Message truncated: {len(message)} → {CHAT_MAX_CHARS} chars")
        return GuardrailResult(
            allowed=True,
            violation=GuardrailViolation.TOO_LONG,
            reason=f"ℹ️ Tin nhắn quá dài ({len(message)} ký tự), đã tự động cắt bớt còn {CHAT_MAX_CHARS} ký tự.",
            sanitized=truncated,
            metadata={"original_length": len(message), "max_length": CHAT_MAX_CHARS},
        )
    return None


def _check_off_topic_regex(message: str) -> Optional[GuardrailResult]:
    """
    Layer 5a: Off-topic pre-filter (regex, 0ms).
    Chặn nhanh các câu hỏi rõ ràng không liên quan học tập.
    """
    if _CLEAR_OFF_TOPIC.search(message):
        logger.info(f"[ChatGuardrail] Off-topic (regex): '{message[:80]}'")
        return GuardrailResult.block(
            GuardrailViolation.OFF_TOPIC,
            reason="⛔ Câu hỏi của bạn không liên quan đến nội dung học tập. "
                   "Hệ thống chỉ hỗ trợ giải thích, mở rộng kiến thức từ flashcard và tài liệu.",
            method="regex",
        )
    return None


def _check_off_topic_llm(
    message: str,
    card_question: str,
    openai_client,
    model: str = "gpt-4o-mini",
) -> Optional[GuardrailResult]:
    """
    Layer 5b: LLM-based off-topic detection.
    Gọi gpt-4o-mini với prompt phân loại ON/OFF topic.
    Chi phí: ~0.001 USD / lần gọi. Latency: ~300-500ms.

    Args:
        message:        Tin nhắn user
        card_question:  Câu hỏi trên thẻ (để cung cấp context)
        openai_client:  OpenAI client instance
        model:          Model cho intent routing (mặc định gpt-4o-mini)

    Returns:
        GuardrailResult.block nếu OFF-TOPIC, None nếu ON-TOPIC hoặc lỗi
    """
    if not openai_client:
        return None

    try:
        t_start = time.perf_counter()

        user_prompt = f'Flashcard question: "{card_question}"\nUser message: "{message}"'

        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _LLM_OFFTOPIC_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=5,
        )

        verdict = response.choices[0].message.content.strip().upper()
        t_ms = round((time.perf_counter() - t_start) * 1000, 1)

        # Log token usage for cost tracking
        usage = response.usage
        logger.info(
            f"[ChatGuardrail] LLM off-topic check: verdict={verdict} "
            f"latency={t_ms}ms tokens_in={usage.prompt_tokens} tokens_out={usage.completion_tokens}"
        )

        if verdict == "OFF":
            return GuardrailResult.block(
                GuardrailViolation.OFF_TOPIC,
                reason="⛔ Câu hỏi của bạn không liên quan đến nội dung học tập. "
                       "Hệ thống chỉ hỗ trợ giải thích, mở rộng kiến thức từ flashcard và tài liệu.",
                method="llm_router",
                model=model,
                latency_ms=t_ms,
                tokens_in=usage.prompt_tokens,
                tokens_out=usage.completion_tokens,
            )
        return None

    except Exception as e:
        logger.warning(f"[ChatGuardrail] LLM off-topic check failed (graceful skip): {e}")
        # Graceful fallback: nếu LLM lỗi → cho phép đi qua (không block user)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# ChatGuardrail — Pipeline chạy tuần tự các layers
# ──────────────────────────────────────────────────────────────────────────────

class ChatGuardrail(BaseGuardrail):
    """
    Multi-layer guardrail pipeline cho chat messages.

    Usage:
        guardrail = ChatGuardrail()
        result = guardrail.check(user_message, card_question="...", openai_client=client)
        if not result.allowed:
            return jsonify({"error": result.reason, "guardrail_blocked": True}), 400
        # Dùng result.sanitized nếu có, ngược lại dùng user_message gốc
        clean_message = result.sanitized or user_message
    """

    def check(self, content: str, card_question: str = "", **kwargs) -> GuardrailResult:
        """
        Chạy tất cả các layer theo thứ tự ưu tiên.

        Args:
            content:        Tin nhắn chat từ user
            card_question:  Câu hỏi trên thẻ (dùng cho off-topic check)
            openai_client:  (optional, via kwargs) OpenAI client cho LLM off-topic check
            offtopic_model: (optional, via kwargs) Model name cho LLM router (default: gpt-4o-mini)

        Returns:
            GuardrailResult — allowed=True nếu qua, kèm sanitized nếu cần
        """
        if not content or not content.strip():
            return GuardrailResult.block(
                GuardrailViolation.NONE,
                reason="Vui lòng nhập câu hỏi.",
            )

        # Layer 1: Injection (block ngay)
        result = _check_injection(content)
        if result:
            return result

        # Layer Code Injection
        result = _check_code_injection(content)
        if result:
            return result

        # Layer 2: Toxic (block ngay)
        result = _check_toxic(content)
        if result:
            return result

        # Layer Sensitive Topics (Politics, Advice)
        result = _check_sensitive_topics(content)
        if result:
            return result

        # Layer Gibberish (block spam text)
        result = _check_gibberish(content)
        if result:
            return result

        # Layer 3: PII (sanitize, không block)
        result = _check_pii(content)
        if result:
            # Tiếp tục check các layer sau với content đã sanitize
            content = result.sanitized
            pii_result = result  # Giữ lại để merge metadata

        # Layer 4: Length (truncate, không block)
        result = _check_length(content)
        if result:
            content = result.sanitized

        # Layer 5a: Off-topic Regex pre-filter (0ms — chặn nhanh từ khóa hiển nhiên)
        result = _check_off_topic_regex(content)
        if result:
            return result

        # Layer 5b: LLM-based Intent Router (~400ms — phân loại thông minh)
        # Chỉ chạy nếu có openai_client được truyền vào
        openai_client = kwargs.get("openai_client")
        offtopic_model = kwargs.get("offtopic_model", "gpt-4o-mini")
        if openai_client:
            result = _check_off_topic_llm(
                content, card_question, openai_client, model=offtopic_model
            )
            if result:
                return result

        # Tất cả layers pass
        # Trả về sanitized content nếu đã bị modify
        return GuardrailResult.ok(sanitized=content if content != kwargs.get("_original", content) else None)

    def check_history(self, history: list) -> GuardrailResult:
        """
        Kiểm tra toàn bộ conversation history.
        Dùng khi load lại history từ frontend để đảm bảo không có nội dung xấu.
        """
        for turn in history:
            msg = turn.get("content", "")
            if not msg:
                continue
            result = _check_injection(msg)
            if result:
                return result
            result = _check_toxic(msg)
            if result:
                return result
        return GuardrailResult.ok()

