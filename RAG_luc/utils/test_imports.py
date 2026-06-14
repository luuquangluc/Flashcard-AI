"""
utils/test_imports.py — Kiểm tra tất cả imports sau khi refactor.
Chạy: python utils/test_imports.py
"""
import sys
import os
import traceback

# Đảm bảo root project nằm trong sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TESTS = [
    # (Tên module, câu lệnh import)
    ("config.settings",               "from config.settings import MODEL_NAME, FLASK_SECRET_KEY, ROOT_DIR"),
    ("modules.RAG.rag_core",          "from modules.RAG.rag_core import RAGCore"),
    ("modules.RAG.rag_retrieval",     "from modules.RAG.rag_retrieval import RAGRetrieval"),
    ("modules.RAG.rag_generation",    "from modules.RAG.rag_generation import RAGGeneration"),
    ("modules.RAG.rag_system",        "from modules.RAG.rag_system import RAGSystem"),
    ("modules.RAG.pdf_processor",     "from modules.RAG.pdf_processor import chunk_pdf_auto"),
    ("modules.RAG.validators",        "from modules.RAG.validators import json_guard"),
    ("modules.RAG.fsrs_logic",        "from modules.RAG.fsrs_logic import FSRS"),
    ("modules.chat.chat_handler",     "from modules.chat.chat_handler import ChatMixin"),
    ("modules.video.video_handler",   "from modules.video.video_handler import VideoHandler"),
    ("modules.image.vision_processor","from modules.image.vision_processor import VisionProcessor"),
    ("api_routes.dependencies",       "from api_routes.dependencies import get_rag_system, fsrs"),
    ("monitoring.evaluator (check)",  "import monitoring.evaluator"),
]


def main():
    print("=" * 60)
    print("  IMPORT TEST — RAG_luc Refactored Structure")
    print("=" * 60)

    passed = failed = 0
    for name, stmt in TESTS:
        try:
            exec(stmt)
            print(f"  [OK]   {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  Result: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
