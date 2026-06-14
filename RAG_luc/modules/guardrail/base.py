"""
modules/guardrail/base.py — Base classes và shared utilities cho guardrail system.

Cung cấp:
  - GuardrailResult   : Data class cho kết quả kiểm tra
  - GuardrailViolation: Enum các loại vi phạm
  - BaseGuardrail     : Abstract base class
  - Shared patterns   : PII, toxic keywords, injection patterns
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Violation Types
# ──────────────────────────────────────────────────────────────────────────────

class GuardrailViolation(Enum):
    """Phân loại vi phạm để frontend hiển thị thông báo phù hợp."""
    NONE            = "none"
    TOXIC_CONTENT   = "toxic_content"       # Nội dung thù địch, xúc phạm
    PROMPT_INJECTION= "prompt_injection"    # Cố tình jailbreak AI
    OFF_TOPIC       = "off_topic"           # Không liên quan đến tài liệu/thẻ
    PII_DETECTED    = "pii_detected"        # Thông tin cá nhân nhạy cảm
    TOO_LONG        = "too_long"            # Input quá dài
    UNSAFE_CONTENT  = "unsafe_content"      # Nội dung không an toàn
    LANGUAGE_MISMATCH = "language_mismatch" # Ngôn ngữ không được hỗ trợ
    DOCUMENT_INVALID = "document_invalid"   # Tài liệu không hợp lệ
    GIBBERISH       = "gibberish"           # Nội dung rác, vô nghĩa
    CODE_INJECTION  = "code_injection"      # Cố tình thực thi mã độc hoặc lệnh shell
    ADVICE_REQUEST  = "advice_request"      # Xin lời khuyên y tế, tài chính
    POLITICS        = "politics"            # Bàn luận chính trị, tôn giáo nhạy cảm


# ──────────────────────────────────────────────────────────────────────────────
# GuardrailResult
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    """
    Kết quả sau khi chạy guardrail.

    Attributes:
        allowed     : True nếu input được phép đi qua
        violation   : Loại vi phạm nếu blocked
        reason      : Lý do blocked (hiển thị cho user)
        sanitized   : Input đã được làm sạch (nếu có thể salvage)
        metadata    : Thông tin thêm (matched_patterns, severity...)
    """
    allowed: bool = True
    violation: GuardrailViolation = GuardrailViolation.NONE
    reason: str = ""
    sanitized: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, sanitized: str = None) -> "GuardrailResult":
        return cls(allowed=True, sanitized=sanitized)

    @classmethod
    def block(cls, violation: GuardrailViolation, reason: str, **metadata) -> "GuardrailResult":
        return cls(allowed=False, violation=violation, reason=reason, metadata=metadata)


# ──────────────────────────────────────────────────────────────────────────────
# Shared Patterns (dùng chung cho cả chat và document guardrail)
# ──────────────────────────────────────────────────────────────────────────────

# PII — Thông tin cá nhân nhạy cảm
PII_PATTERNS = [
    (re.compile(r"\b\d{9,12}\b"), "CMND/CCCD/Số tài khoản"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "Số thẻ tín dụng"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "Email"),
    (re.compile(r"\b(0|\+84)[3-9]\d{8}\b"), "Số điện thoại"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN"),
    (re.compile(r"\b(password|mật\s*khẩu|passwd)\s*[:=]\s*\S+", re.IGNORECASE), "Password"),
]

# Prompt Injection — cố tình thay đổi hành vi AI
INJECTION_PATTERNS = re.compile(
    r"\b(ignore\s+(all\s+)?(previous|above|prior)\s+instructions?|"
    r"forget\s+(everything|your\s+instructions?)|"
    r"you\s+are\s+now\s+(a|an)\s+\w+|"
    r"act\s+as\s+(if\s+you\s+are\s+)?a?\s+\w+|"
    r"system\s*:\s*you\s+are|"
    r"<\s*/?system\s*>|"
    r"\[INST\]|\[SYS\]|###\s*System|"
    r"quên\s+đi\s+tất\s+cả|"
    r"bây\s+giờ\s+bạn\s+là|"
    r"bỏ\s+qua\s+(hướng\s+dẫn|lệnh)\s+trước)\b",
    re.IGNORECASE | re.DOTALL,
)

# Toxic — Nội dung thù địch / xúc phạm (cơ bản, không cần model)
TOXIC_PATTERNS = re.compile(
    r"\b(đ[ụù]m\s*mẹ|đ[ụù]m\s*cha|con\s*đĩ|thằng\s*chó|đồ\s*ngu|"
    r"chết\s*đi|địt|đ[éè]o\s*mẹ|"
    r"fuck\s*(you|off|this|that|ing)?|motherfuck|asshole|bitch|cunt|shit|stfu|damn\s+you|"
    r"kill\s+(yourself|myself)|suicide|tự\s*tử|"
    r"terrorist|bomb\s+how\s+to|how\s+to\s+make\s+(a\s+)?(bomb|weapon|drug))\b",
    re.IGNORECASE,
)

# Unsafe document content
UNSAFE_CONTENT_PATTERNS = re.compile(
    r"\b(bomb|explosive|weapon|drug\s+synthesis|child\s+porn|"
    r"vũ\s+khí|chế\s+tạo\s+bom|ma\s+túy|nội\s+dung\s+khiêu\s+dâm\s+trẻ\s+em)\b",
    re.IGNORECASE,
)

# Code Injection / XSS / Shell execution — cố gắng chèn mã độc
CODE_INJECTION_PATTERNS = re.compile(
    r"(rm\s+-rf|os\.system|subprocess\.|eval\(|exec\(|<script>|javascript:|onclick=|"
    r"DROP\s+TABLE|SELECT\s+\*\s+FROM|UNION\s+SELECT|/etc/passwd)",
    re.IGNORECASE,
)

# Financial / Medical Advice — Yêu cầu lời khuyên nhạy cảm
ADVICE_PATTERNS = re.compile(
    r"\b(cổ\s+phiếu|chứng\s+khoán|đầu\s+tư\s+gì|mua\s+mã\s+nào|tiền\s+ảo|crypto|"
    r"đau\s+đầu|uống\s+thuốc\s+gì|chữa\s+bệnh|chẩn\s+đoán|triệu\s+chứng)\b",
    re.IGNORECASE,
)

# Politics / Religion — Chính trị, tôn giáo nhạy cảm
POLITICS_PATTERNS = re.compile(
    r"\b(chính\s+trị|đảng\s+phái|bầu\s+cử|phản\s+động|biểu\s+tình|chống\s+phá|"
    r"đạo\s+chúa|đạo\s+phật|hồi\s+giáo|tôn\s+giáo\s+nào\s+tốt|xuyên\s+tạc)\b",
    re.IGNORECASE,
)

def check_gibberish(text: str) -> bool:
    """Phát hiện spam chữ cái (e.g. 'asdfghjk', 'aaaaaaa')."""
    if len(text) < 5:
        return False
    # Kiểm tra ký tự lặp lại liên tục (>5 lần)
    if re.search(r"(.)\1{5,}", text):
        return True
    # Kiểm tra tỷ lệ ký tự chữ/số so với tổng chiều dài (tránh spam toàn ký tự đặc biệt)
    alnum_count = sum(c.isalnum() for c in text)
    if alnum_count / len(text) < 0.2:
        return True
    return False


def check_pii(text: str) -> tuple[bool, list[str]]:
    """
    Kiểm tra text có chứa PII không.
    Returns: (has_pii, list of detected_types)
    """
    detected = []
    for pattern, label in PII_PATTERNS:
        if pattern.search(text):
            detected.append(label)
    return bool(detected), detected


def mask_pii(text: str) -> str:
    """Mask các PII trong text để sanitize (thay bằng [REDACTED])."""
    result = text
    for pattern, label in PII_PATTERNS:
        result = pattern.sub(f"[{label} ĐÃ ẨN]", result)
    return result


class BaseGuardrail:
    """Abstract base class cho tất cả guardrail."""

    def check(self, content: str, **kwargs) -> GuardrailResult:
        raise NotImplementedError

    def __call__(self, content: str, **kwargs) -> GuardrailResult:
        return self.check(content, **kwargs)
