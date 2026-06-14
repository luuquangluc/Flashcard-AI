"""
modules/guardrail/document_guardrail.py — Guardrail cho Document Upload.

Các lớp kiểm tra khi người dùng nạp tài liệu (PDF/TXT):
  Layer 1 — File Type Guard   : Chỉ chấp nhận PDF, TXT
  Layer 2 — File Size Guard   : Giới hạn kích thước file
  Layer 3 — Content Safety   : Phát hiện nội dung nguy hiểm trong text đã extract
  Layer 4 — PII Guard         : Cảnh báo nếu tài liệu có PII (không block, chỉ warn)
  Layer 5 — Language Guard    : Cảnh báo nếu tài liệu không phải Việt/Anh

Thiết kế:
  - Không phụ thuộc vào LLM → không thêm latency vào upload
  - Tích hợp vào api_routes/rag.py trước khi gọi rag_system.process_pdf()
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from modules.guardrail.base import (
    BaseGuardrail, GuardrailResult, GuardrailViolation,
    UNSAFE_CONTENT_PATTERNS, check_pii, mask_pii,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS   = {".pdf", ".txt", ".md"}
MAX_FILE_SIZE_MB     = 50           # Hard limit: 50MB
WARN_FILE_SIZE_MB    = 20           # Cảnh báo: 20MB
MAX_TEXT_CHARS       = 2_000_000    # 2M chars tối đa cho text scan
SAMPLE_SIZE_CHARS    = 50_000       # Chỉ scan 50K đầu để detect nhanh

# Ngôn ngữ hỗ trợ (detect đơn giản bằng script/char range)
_LATIN_RATIO_MIN = 0.3   # Ít nhất 30% Latin chars → có khả năng là Anh/Việt
_LANG_WHITELIST  = {"vi", "en"}

# Các filename pattern nguy hiểm (path traversal)
_DANGEROUS_FILENAME = re.compile(r"\.\./|\.\.\\|<|>|\||;|&|\$", re.IGNORECASE)


# ──────────────────────────────────────────────────────────────────────────────
# Layer Checkers
# ──────────────────────────────────────────────────────────────────────────────

def _check_file_type(filename: str) -> Optional[GuardrailResult]:
    """Layer 1: Kiểm tra extension file."""
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return GuardrailResult.block(
            GuardrailViolation.DOCUMENT_INVALID,
            reason=f"⛔ Định dạng file '{ext}' không được hỗ trợ. "
                   f"Vui lòng upload file: {', '.join(ALLOWED_EXTENSIONS)}.",
            detected_ext=ext,
        )

    # Path traversal guard
    if _DANGEROUS_FILENAME.search(filename):
        return GuardrailResult.block(
            GuardrailViolation.DOCUMENT_INVALID,
            reason="⛔ Tên file chứa ký tự không hợp lệ.",
        )

    return None


def _check_file_size(file_size_bytes: int) -> Optional[GuardrailResult]:
    """Layer 2: Kiểm tra kích thước file."""
    size_mb = file_size_bytes / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        return GuardrailResult.block(
            GuardrailViolation.DOCUMENT_INVALID,
            reason=f"⛔ File quá lớn ({size_mb:.1f}MB). Giới hạn tối đa là {MAX_FILE_SIZE_MB}MB.",
            size_mb=round(size_mb, 2),
        )

    # Warn nhưng không block
    if size_mb > WARN_FILE_SIZE_MB:
        logger.warning(f"[DocGuardrail] Large file: {size_mb:.1f}MB — processing may be slow")

    return None


def _check_content_safety(text_sample: str) -> Optional[GuardrailResult]:
    """Layer 3: Kiểm tra nội dung nguy hiểm trong text."""
    if not text_sample:
        return None

    sample = text_sample[:SAMPLE_SIZE_CHARS]

    if UNSAFE_CONTENT_PATTERNS.search(sample):
        matched = UNSAFE_CONTENT_PATTERNS.findall(sample)
        logger.warning(f"[DocGuardrail] Unsafe content: {matched}")
        return GuardrailResult.block(
            GuardrailViolation.UNSAFE_CONTENT,
            reason="⛔ Tài liệu chứa nội dung không phù hợp và không thể được xử lý.",
            matched_keywords=matched[:5],
        )

    return None


def _check_document_pii(text_sample: str) -> Optional[GuardrailResult]:
    """
    Layer 4: Cảnh báo PII trong tài liệu.
    Không block (tài liệu học tập hợp lệ có thể có số trang, mã SV...)
    Chỉ log cảnh báo và trả về metadata cho caller.
    """
    if not text_sample:
        return None

    sample = text_sample[:SAMPLE_SIZE_CHARS]
    has_pii, detected_types = check_pii(sample)

    if has_pii:
        logger.info(f"[DocGuardrail] PII found in document: {detected_types}")
        return GuardrailResult(
            allowed=True,
            violation=GuardrailViolation.PII_DETECTED,
            reason=f"ℹ️ Tài liệu có thể chứa thông tin nhạy cảm ({', '.join(detected_types)}). "
                   f"Thông tin này sẽ được xử lý bảo mật.",
            metadata={"pii_types": detected_types},
        )

    return None


def _check_language(text_sample: str) -> Optional[GuardrailResult]:
    """
    Layer 5: Kiểm tra ngôn ngữ (heuristic, không dùng langdetect).
    Tài liệu hoàn toàn không có Latin chars → có thể là ngôn ngữ không hỗ trợ.
    """
    if not text_sample or len(text_sample) < 100:
        return None

    sample = text_sample[:5000]
    # Đếm tỷ lệ Latin chars (a-z, A-Z, dấu tiếng Việt)
    latin_chars = sum(1 for c in sample if c.isalpha())
    if latin_chars == 0:
        return None  # Không có text alpha → không kết luận

    # Kiểm tra có phải toàn CJK không
    cjk_chars = sum(1 for c in sample if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
    cjk_ratio = cjk_chars / max(len(sample), 1)

    if cjk_ratio > 0.3:
        logger.info(f"[DocGuardrail] High CJK ratio: {cjk_ratio:.2%}")
        return GuardrailResult(
            allowed=True,  # Vẫn cho phép — người dùng có thể muốn học tiếng Trung
            violation=GuardrailViolation.LANGUAGE_MISMATCH,
            reason="ℹ️ Tài liệu có vẻ chứa nhiều ký tự CJK (Trung/Nhật/Hàn). "
                   "Hệ thống hỗ trợ tốt nhất cho tài liệu tiếng Việt và tiếng Anh.",
            metadata={"cjk_ratio": round(cjk_ratio, 3)},
        )

    return None


# ──────────────────────────────────────────────────────────────────────────────
# DocumentGuardrail — Pipeline
# ──────────────────────────────────────────────────────────────────────────────

class DocumentGuardrail(BaseGuardrail):
    """
    5-layer guardrail pipeline cho document uploads.

    Usage trong upload route:
        doc_guard = DocumentGuardrail()

        # Check file metadata trước (không cần đọc content)
        result = doc_guard.check_file(filename=file.filename, file_size=len(file_content))
        if not result.allowed:
            return jsonify({"error": result.reason}), 400

        # Sau khi extract text (optional, để check content safety)
        result = doc_guard.check_content(extracted_text)
        if not result.allowed:
            return jsonify({"error": result.reason}), 400

        # Lấy warnings để trả về cho frontend
        warnings = doc_guard.get_warnings()
    """

    def __init__(self):
        self._warnings: list[str] = []

    def check_file(self, filename: str, file_size: int) -> GuardrailResult:
        """
        Kiểm tra metadata file (không cần đọc nội dung).
        Gọi ngay sau khi nhận file từ request.

        Args:
            filename:  Tên file gốc
            file_size: Kích thước file tính bằng bytes
        """
        self._warnings = []

        # Layer 1: File type
        result = _check_file_type(filename)
        if result:
            return result

        # Layer 2: File size
        result = _check_file_size(file_size)
        if result and not result.allowed:
            return result
        if result and result.allowed:
            self._warnings.append(
                f"⚠️ File lớn ({file_size / 1024 / 1024:.1f}MB) — quá trình xử lý có thể chậm hơn bình thường."
            )

        logger.info(f"[DocGuardrail] File OK: {filename} ({file_size/1024:.1f}KB)")
        return GuardrailResult.ok()

    def check_content(self, text: str) -> GuardrailResult:
        """
        Kiểm tra nội dung text đã extract từ document.
        Gọi sau khi PDF processor trích xuất text (nếu muốn scan content).

        Args:
            text: Text đã extract từ document
        """
        if not text:
            return GuardrailResult.ok()

        # Layer 3: Content safety (block nếu nguy hiểm)
        result = _check_content_safety(text)
        if result:
            return result

        # Layer 4: PII warning (không block)
        result = _check_document_pii(text)
        if result and result.violation == GuardrailViolation.PII_DETECTED:
            self._warnings.append(result.reason)

        # Layer 5: Language warning (không block)
        result = _check_language(text)
        if result and result.violation == GuardrailViolation.LANGUAGE_MISMATCH:
            self._warnings.append(result.reason)

        return GuardrailResult.ok()

    def check(self, content: str, **kwargs) -> GuardrailResult:
        """Implement BaseGuardrail.check() — delegates to check_content()."""
        filename = kwargs.get("filename", "")
        file_size = kwargs.get("file_size", 0)

        if filename:
            result = self.check_file(filename, file_size)
            if not result.allowed:
                return result

        return self.check_content(content)

    def get_warnings(self) -> list[str]:
        """Lấy danh sách cảnh báo (non-blocking) để trả về cho frontend."""
        return list(self._warnings)

    def reset(self):
        """Reset warnings giữa các request."""
        self._warnings = []
