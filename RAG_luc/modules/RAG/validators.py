"""
validators.py - Custom Guardrails AI validators for RAG_luc
"""
import re
import json
import logging

try:
    from guardrails import Guard
    from guardrails.validators import Validator, register_validator, PassResult, FailResult
    from guardrails.validator_base import OnFailAction
    HAS_GUARDRAILS = True
except ImportError:
    HAS_GUARDRAILS = False

logger = logging.getLogger(__name__)

if HAS_GUARDRAILS:
    @register_validator(name="json-formatter", data_type="string")
    class JSONFormatter(Validator):
        """
        Validates and auto-repairs malformed JSON strings.
        """
        @staticmethod
        def _repair(text: str) -> str:
            text = text.strip()
            # Remove markdown fences
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            text = text.strip()
            # Single quotes -> double quotes
            text = text.replace("'", '"')
            # Remove trailing commas
            text = re.sub(r',\s*([}\]])', r'\1', text)
            return text

        def validate(self, value: str, metadata: dict):
            try:
                parsed = json.loads(value)
                repaired = json.dumps(parsed, indent=2)
                return PassResult(value_override=repaired)
            except json.JSONDecodeError:
                pass

            # Try repair
            try:
                repaired_text = self._repair(value)
                parsed = json.loads(repaired_text)
                repaired = json.dumps(parsed, indent=2)
                logger.info("  🔧 JSON repaired successfully by Guardrails")
                return PassResult(value_override=repaired)
            except json.JSONDecodeError as e:
                return FailResult(error_message=f"Invalid JSON after repair attempt: {e}")

    @register_validator(name="pii-detector", data_type="string")
    class PIIDetector(Validator):
        PII_PATTERNS = {
            "EMAIL":       r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "PHONE":       r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
            "SSN":         r"\b\d{3}-\d{2}-\d{4}\b",
            "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        }

        def validate(self, value: str, metadata: dict):
            redacted_text = value
            found_pii = []
            for pii_type, pattern in self.PII_PATTERNS.items():
                matches = re.findall(pattern, value)
                for match in matches:
                    redacted_text = redacted_text.replace(match, f"[{pii_type}_REDACTED]")
                    found_pii.append((pii_type, match))
            if found_pii:
                logger.warning(f"  ⚠️ Redacted {len(found_pii)} PII items.")
                return PassResult(value_override=redacted_text)
            return PassResult(value_override=value)

    json_guard = Guard().use(JSONFormatter(on_fail=OnFailAction.FIX))
    pii_guard = Guard().use(PIIDetector(on_fail=OnFailAction.FIX))

else:
    # Fallback if guardrails-ai is not installed
    class DummyGuard:
        def validate(self, text):
            class DummyResult:
                def __init__(self, t):
                    self.validated_output = t
            
            # Basic manual repair for JSON fallback
            t = text.strip()
            t = re.sub(r'^```(?:json)?\s*', '', t)
            t = re.sub(r'\s*```$', '', t)
            return DummyResult(t.strip())

    json_guard = DummyGuard()
    pii_guard = DummyGuard()
