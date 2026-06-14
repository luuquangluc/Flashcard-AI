"""
modules/guardrail/db_logger.py — Supabase Logger cho Guardrail events.

Cách hoạt động:
  - SupabaseGuardrailLogger.log() được gọi từ ChatGuardrail và DocumentGuardrail
    sau mỗi lần check() → insert 1 row vào bảng `guardrail_logs`
  - Fire-and-forget: dùng threading để không block request chính
  - Graceful fallback: nếu Supabase không khả dụng → chỉ log ra console

Schema của bảng `guardrail_logs`:
    id, user_id, source, allowed, violation, severity, reason,
    input_preview, input_length, metadata, created_at

Usage:
    from modules.guardrail.db_logger import guardrail_db_logger
    guardrail_db_logger.set_client(supabase_client)  # gọi 1 lần khi khởi động

    # Trong guardrail check:
    guardrail_db_logger.log(
        result=guard_result,
        source="chat",
        user_id=uid,
        raw_input=user_message,
    )
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Optional

from modules.guardrail.base import GuardrailResult, GuardrailViolation

logger = logging.getLogger(__name__)

# Mức severity dựa trên violation type
_SEVERITY_MAP = {
    GuardrailViolation.NONE:              "info",
    GuardrailViolation.PII_DETECTED:      "warning",
    GuardrailViolation.TOO_LONG:          "info",
    GuardrailViolation.LANGUAGE_MISMATCH: "info",
    GuardrailViolation.OFF_TOPIC:         "warning",
    GuardrailViolation.TOXIC_CONTENT:     "critical",
    GuardrailViolation.PROMPT_INJECTION:  "critical",
    GuardrailViolation.UNSAFE_CONTENT:    "critical",
    GuardrailViolation.DOCUMENT_INVALID:  "warning",
}


class SupabaseGuardrailLogger:
    """
    Fire-and-forget logger: ghi guardrail events vào Supabase `guardrail_logs`.

    Thread-safe. Không block request chính.
    Tự động fallback về console nếu Supabase chưa được set hoặc lỗi mạng.
    """

    TABLE = "guardrail_logs"

    def __init__(self):
        self._client = None   # Supabase client, set sau khi app khởi động
        self._lock = threading.Lock()

    def set_client(self, supabase_client) -> None:
        """Gắn Supabase client vào logger. Gọi 1 lần trong app init."""
        with self._lock:
            self._client = supabase_client
        logger.info("[GuardrailDB] Supabase client set — guardrail logs sẽ được lưu vào DB.")

    def log(
        self,
        result: GuardrailResult,
        source: str,
        raw_input: str = "",
        user_id: Optional[str] = None,
    ) -> None:
        """
        Ghi một guardrail event vào DB (non-blocking, chạy trong background thread).

        Args:
            result:    GuardrailResult từ guardrail.check()
            source:    'chat' | 'document_upload' | 'text_update'
            raw_input: Input gốc của user (chỉ lưu 100 ký tự đầu để bảo mật)
            user_id:   User ID từ session
        """
        # Chỉ log nếu có vi phạm (pass hoàn toàn thì bỏ qua để tiết kiệm writes)
        if result.allowed and result.violation == GuardrailViolation.NONE:
            return

        row = self._build_row(result, source, raw_input, user_id)

        # Fire-and-forget: chạy trong daemon thread
        t = threading.Thread(target=self._insert, args=(row,), daemon=True)
        t.start()

    def _build_row(self, result: GuardrailResult, source: str,
                   raw_input: str, user_id: Optional[str]) -> dict:
        """Tạo dict row để insert vào Supabase."""
        severity = _SEVERITY_MAP.get(result.violation, "info")
        # Nếu bị block → nâng severity lên ít nhất warning
        if not result.allowed and severity == "info":
            severity = "warning"

        # Sanitize input_preview: không lưu PII đã mask, chỉ lưu 100 chars
        preview = ""
        if raw_input:
            preview = raw_input[:100] + ("..." if len(raw_input) > 100 else "")

        # Serialize metadata (đảm bảo JSON-safe)
        meta = {}
        for k, v in result.metadata.items():
            try:
                json.dumps(v)
                meta[k] = v
            except (TypeError, ValueError):
                meta[k] = str(v)

        return {
            "user_id":       user_id,
            "source":        source,
            "allowed":       result.allowed,
            "violation":     result.violation.value,
            "severity":      severity,
            "reason":        result.reason or "",
            "input_preview": preview,
            "input_length":  len(raw_input) if raw_input else 0,
            "metadata":      meta,
        }

    def _insert(self, row: dict) -> None:
        """Thực sự insert vào Supabase (chạy trong background thread)."""
        client = self._client
        if not client:
            # Fallback: log ra console
            logger.warning(
                f"[GuardrailDB] No Supabase client — logging to console only: "
                f"source={row['source']} violation={row['violation']} allowed={row['allowed']}"
            )
            return

        try:
            client.table(self.TABLE).insert(row).execute()
            logger.debug(
                f"[GuardrailDB] Logged: source={row['source']} "
                f"violation={row['violation']} severity={row['severity']}"
            )
        except Exception as e:
            # Không raise — guardrail log lỗi không được ảnh hưởng request chính
            logger.error(f"[GuardrailDB] Insert failed: {e} | row={row}")

    def get_recent(self, limit: int = 50, source: str = None,
                   violation: str = None, severity: str = None) -> list:
        """
        Query recent guardrail events (dùng cho admin dashboard).

        Args:
            limit:     Số rows tối đa
            source:    Filter theo source ('chat', 'document_upload'...)
            violation: Filter theo violation type
            severity:  Filter theo severity ('info', 'warning', 'critical')

        Returns:
            list of dicts
        """
        if not self._client:
            return []
        try:
            q = self._client.table(self.TABLE).select("*").order("created_at", desc=True).limit(limit)
            if source:
                q = q.eq("source", source)
            if violation:
                q = q.eq("violation", violation)
            if severity:
                q = q.eq("severity", severity)
            resp = q.execute()
            return resp.data or []
        except Exception as e:
            logger.error(f"[GuardrailDB] Query failed: {e}")
            return []

    def get_stats(self) -> dict:
        """
        Thống kê tổng hợp cho admin dashboard.

        Returns:
            {total, blocked, by_violation, by_source, by_severity, critical_last_24h}
        """
        if not self._client:
            return {}
        try:
            resp = self._client.table(self.TABLE).select(
                "allowed, violation, source, severity, created_at"
            ).execute()
            rows = resp.data or []

            total = len(rows)
            blocked = sum(1 for r in rows if not r["allowed"])
            by_violation: dict = {}
            by_source: dict = {}
            by_severity: dict = {}

            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            critical_24h = 0
            for r in rows:
                by_violation[r["violation"]] = by_violation.get(r["violation"], 0) + 1
                by_source[r["source"]] = by_source.get(r["source"], 0) + 1
                by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1

                if r["severity"] == "critical":
                    try:
                        ts = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                        if ts >= cutoff:
                            critical_24h += 1
                    except Exception:
                        pass

            return {
                "total":             total,
                "blocked":           blocked,
                "pass_rate":         round((total - blocked) / max(total, 1), 3),
                "by_violation":      by_violation,
                "by_source":         by_source,
                "by_severity":       by_severity,
                "critical_last_24h": critical_24h,
            }
        except Exception as e:
            logger.error(f"[GuardrailDB] Stats failed: {e}")
            return {}


# ──────────────────────────────────────────────────────────────────────────────
# Singleton — dùng chung toàn app
# ──────────────────────────────────────────────────────────────────────────────
guardrail_db_logger = SupabaseGuardrailLogger()
