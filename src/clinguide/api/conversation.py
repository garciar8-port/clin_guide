"""Multi-turn conversation support with session context."""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("clinguide.api.conversation")


@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add_user_message(self, content: str) -> None:
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(Message(role="assistant", content=content))

    def get_context_window(self, max_turns: int = 5) -> list[dict[str, str]]:
        """Get recent conversation history for Claude context."""
        recent = self.messages[-(max_turns * 2):]
        return [{"role": m.role, "content": m.content} for m in recent]

    def format_contextual_query(self, new_query: str, max_turns: int = 3) -> str:
        """Enrich a follow-up query with conversation context.

        Example:
          Turn 1: "What is the dosage of osimertinib?"
          Turn 2: "What about pediatric dosing?"
          → "What about pediatric dosing of osimertinib?"
        """
        if len(self.messages) < 2:
            return new_query

        recent = self.messages[-(max_turns * 2):]
        context_parts = []
        for msg in recent:
            if msg.role == "user":
                context_parts.append(f"Previous question: {msg.content}")
            else:
                context_parts.append(f"Previous answer (summary): {msg.content[:200]}")

        context = "\n".join(context_parts)
        return (
            f"Conversation context:\n{context}\n\n"
            f"Current question: {new_query}"
        )


class SessionStore:
    """In-memory session store for multi-turn conversations."""

    def __init__(self, max_sessions: int = 1000) -> None:
        self._sessions: dict[str, Session] = {}
        self._max_sessions = max_sessions

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            if len(self._sessions) >= self._max_sessions:
                self._evict_oldest()
            self._sessions[session_id] = Session(session_id=session_id)
            logger.info("Created new session: %s", session_id)
        return self._sessions[session_id]

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _evict_oldest(self) -> None:
        if not self._sessions:
            return
        oldest_id = min(self._sessions, key=lambda k: self._sessions[k].created_at)
        del self._sessions[oldest_id]
        logger.info("Evicted oldest session: %s", oldest_id)

    @property
    def size(self) -> int:
        return len(self._sessions)
