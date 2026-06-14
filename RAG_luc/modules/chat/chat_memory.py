"""
modules/chat/chat_memory.py — Supabase Chat Memory System.

Lưu trữ dữ liệu memory người dùng vào Supabase (cloud PostgreSQL),
đảm bảo dữ liệu tồn tại vĩnh viễn và có thể dùng cho Dashboard/Analytics.

2 bảng chính:
  - chat_episodes:    Lưu từng lượt hội thoại (user hỏi gì, AI trả lời gì, chủ đề gì)
  - learner_profiles: Lưu profile người học dài hạn (chủ đề yếu, phong cách ưa thích)

Tất cả ghi DB đều chạy fire-and-forget (daemon thread) để không block request.

Usage:
    from modules.chat.chat_memory import chat_memory_db
    chat_memory_db.set_client(supabase_client)  # 1 lần khi khởi động

    # Sau mỗi lượt chat:
    chat_memory_db.save_episode(
        user_id="user123",
        card_scope="abc12345",
        user_message="Tại sao bầu trời có màu xanh?",
        ai_response="Vì hiện tượng tán xạ Rayleigh...",
        intent="explain",
        card_question="Bầu trời màu gì?",
    )

    # Cập nhật profile:
    chat_memory_db.update_profile(
        user_id="user123",
        topic="Quang học",
        intent="explain",
    )
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class SupabaseChatMemory:
    """
    Fire-and-forget Supabase writer cho chat memory.

    Thread-safe. Không block request chính.
    Tự động fallback về console nếu Supabase chưa set.
    """

    EPISODES_TABLE = "chat_episodes"
    PROFILES_TABLE = "learner_profiles"

    def __init__(self):
        self._client = None
        self._lock = threading.Lock()

    def set_client(self, supabase_client) -> None:
        """Gắn Supabase client. Gọi 1 lần trong app init."""
        with self._lock:
            self._client = supabase_client
        logger.info("[ChatMemoryDB] Supabase client set — chat memory sẽ được lưu vào DB.")

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    # ──────────────────────────────────────────────────────────────────────
    # Chat Episodes — Lưu từng lượt hội thoại
    # ──────────────────────────────────────────────────────────────────────

    def save_episode(
        self,
        user_id: str,
        card_scope: str,
        user_message: str,
        ai_response: str,
        intent: str = "general",
        card_question: str = "",
        metadata: dict = None,
    ) -> None:
        """
        Lưu 1 episode (lượt hội thoại) vào Supabase.
        Chạy fire-and-forget trong daemon thread.

        Args:
            user_id:       ID người dùng
            card_scope:    MD5 8-char hash của card question
            user_message:  Câu hỏi của user
            ai_response:   Câu trả lời của AI
            intent:        Intent đã detect (explain/example/compare/apply/expand/general)
            card_question: Câu hỏi gốc trên thẻ Flashcard
            metadata:      Metadata bổ sung (tùy chọn)
        """
        if not user_id:
            return

        row = {
            "user_id": user_id,
            "card_scope": card_scope or "unknown",
            "summary": user_message[:500],  # Giới hạn 500 ký tự
            "outcome": ai_response[:1000],  # Giới hạn 1000 ký tự
            "tags": {
                "intent": intent,
                "card_question": card_question[:200] if card_question else "",
                **(metadata or {}),
            },
        }

        t = threading.Thread(target=self._insert_episode, args=(row,), daemon=True)
        t.start()

    def _insert_episode(self, row: dict) -> None:
        """Insert episode row vào Supabase (background thread)."""
        client = self._client
        if not client:
            logger.debug(
                f"[ChatMemoryDB] No Supabase client — episode logged to console: "
                f"user={row['user_id']} scope={row['card_scope']}"
            )
            return

        try:
            client.table(self.EPISODES_TABLE).insert(row).execute()
            logger.debug(
                f"[ChatMemoryDB] Episode saved: user={row['user_id']} "
                f"scope={row['card_scope']} intent={row['tags'].get('intent')}"
            )
        except Exception as e:
            logger.error(f"[ChatMemoryDB] Insert episode failed: {e}")

    def get_episodes(
        self,
        user_id: str,
        card_scope: str = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        Lấy danh sách episodes của user (dùng cho dashboard hoặc context injection).

        Args:
            user_id:    ID người dùng
            card_scope: (optional) Chỉ lấy episodes của 1 card cụ thể
            limit:      Số episodes tối đa

        Returns:
            List of episode dicts [{id, user_id, card_scope, summary, outcome, tags, created_at}]
        """
        if not self._client or not user_id:
            return []
        try:
            q = (
                self._client.table(self.EPISODES_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if card_scope:
                q = q.eq("card_scope", card_scope)
            resp = q.execute()
            return resp.data or []
        except Exception as e:
            logger.error(f"[ChatMemoryDB] Get episodes failed: {e}")
            return []

    def get_episode_stats(self, user_id: str) -> dict:
        """
        Thống kê học tập của user: số lượt chat, intent phổ biến nhất, chủ đề thường hỏi.
        """
        if not self._client or not user_id:
            return {}
        try:
            resp = (
                self._client.table(self.EPISODES_TABLE)
                .select("card_scope, tags, created_at")
                .eq("user_id", user_id)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return {"total_episodes": 0}

            intent_counts = {}
            card_counts = {}
            for r in rows:
                tags = r.get("tags", {}) or {}
                intent = tags.get("intent", "general")
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

                cq = tags.get("card_question", "")
                if cq:
                    card_counts[cq] = card_counts.get(cq, 0) + 1

            # Top 5 câu hỏi được hỏi nhiều nhất
            top_cards = sorted(card_counts.items(), key=lambda x: -x[1])[:5]

            return {
                "total_episodes": len(rows),
                "intent_distribution": intent_counts,
                "top_questions": [{"question": q, "count": c} for q, c in top_cards],
                "first_activity": rows[-1].get("created_at") if rows else None,
                "last_activity": rows[0].get("created_at") if rows else None,
            }
        except Exception as e:
            logger.error(f"[ChatMemoryDB] Episode stats failed: {e}")
            return {}

    # ──────────────────────────────────────────────────────────────────────
    # Learner Profiles — Profile người học dài hạn
    # ──────────────────────────────────────────────────────────────────────

    def update_profile(
        self,
        user_id: str,
        topic: str = "",
        intent: str = "",
        preference: dict = None,
    ) -> None:
        """
        Cập nhật learner profile sau mỗi lượt chat.
        Tự động tạo profile mới nếu chưa tồn tại (upsert).

        Cập nhật:
          - total_chats += 1
          - topic_frequency[topic] += 1
          - intent_frequency[intent] += 1
          - preferences (nếu có)

        Chạy fire-and-forget trong daemon thread.
        """
        if not user_id:
            return

        t = threading.Thread(
            target=self._upsert_profile,
            args=(user_id, topic, intent, preference or {}),
            daemon=True,
        )
        t.start()

    def _upsert_profile(self, user_id: str, topic: str, intent: str, preference: dict) -> None:
        """Upsert learner profile (background thread)."""
        client = self._client
        if not client:
            logger.debug(f"[ChatMemoryDB] No Supabase — profile update skipped for {user_id}")
            return

        try:
            # Đọc profile hiện tại
            resp = (
                client.table(self.PROFILES_TABLE)
                .select("profile_data")
                .eq("user_id", user_id)
                .execute()
            )
            existing = resp.data[0]["profile_data"] if resp.data else {}

            # Merge data
            profile = existing or {}
            profile["total_chats"] = profile.get("total_chats", 0) + 1
            profile["last_active"] = datetime.now(timezone.utc).isoformat()

            # Topic frequency
            if topic:
                topics = profile.get("topic_frequency", {})
                topics[topic] = topics.get(topic, 0) + 1
                profile["topic_frequency"] = topics

            # Intent frequency
            if intent:
                intents = profile.get("intent_frequency", {})
                intents[intent] = intents.get(intent, 0) + 1
                profile["intent_frequency"] = intents

            # Preferences (merge, không overwrite)
            if preference:
                prefs = profile.get("preferences", {})
                prefs.update(preference)
                profile["preferences"] = prefs

            # Upsert
            client.table(self.PROFILES_TABLE).upsert({
                "user_id": user_id,
                "profile_data": profile,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).execute()

            logger.debug(f"[ChatMemoryDB] Profile updated: user={user_id} total_chats={profile['total_chats']}")

        except Exception as e:
            logger.error(f"[ChatMemoryDB] Profile upsert failed: {e}")

    def get_profile(self, user_id: str) -> dict:
        """Lấy learner profile của user."""
        if not self._client or not user_id:
            return {}
        try:
            resp = (
                self._client.table(self.PROFILES_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            if resp.data:
                return resp.data[0]
            return {}
        except Exception as e:
            logger.error(f"[ChatMemoryDB] Get profile failed: {e}")
            return {}

    def delete_user_data(self, user_id: str) -> bool:
        """
        Xóa toàn bộ dữ liệu memory của user (GDPR compliance).
        Xóa cả episodes lẫn profile.
        """
        if not self._client or not user_id:
            return False
        try:
            self._client.table(self.EPISODES_TABLE).delete().eq("user_id", user_id).execute()
            self._client.table(self.PROFILES_TABLE).delete().eq("user_id", user_id).execute()
            logger.info(f"[ChatMemoryDB] Deleted all data for user={user_id}")
            return True
        except Exception as e:
            logger.error(f"[ChatMemoryDB] Delete user data failed: {e}")
            return False


# ──────────────────────────────────────────────────────────────────────────────
# Singleton — dùng chung toàn app
# ──────────────────────────────────────────────────────────────────────────────
chat_memory_db = SupabaseChatMemory()
