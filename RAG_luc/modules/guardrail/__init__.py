# modules/guardrail — Guardrail system cho RAG_luc
from modules.guardrail.base import GuardrailResult, GuardrailViolation, BaseGuardrail
from modules.guardrail.chat_guardrail import ChatGuardrail
from modules.guardrail.document_guardrail import DocumentGuardrail
from modules.guardrail.db_logger import guardrail_db_logger

# Singletons dùng chung toàn app
chat_guardrail     = ChatGuardrail()
document_guardrail = DocumentGuardrail()

__all__ = [
    "GuardrailResult",
    "GuardrailViolation",
    "BaseGuardrail",
    "ChatGuardrail",
    "DocumentGuardrail",
    "guardrail_db_logger",
    "chat_guardrail",
    "document_guardrail",
]
