"""
In-memory session manager for multi-turn conversations.
Each session stores the full Claude message history so context is maintained.
"""
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Session:
    session_id: str
    messages: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


class SessionManager:
    """In-memory session store. For production, swap with Redis."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._ttl_seconds = settings.session_ttl_minutes * 60

    def create_session(self) -> str:
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = Session(session_id=session_id)
        logger.info(f"Created session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        # Check expiry
        if time.time() - session.last_active > self._ttl_seconds:
            logger.info(f"Session expired: {session_id}")
            del self._sessions[session_id]
            return None
        return session

    def get_or_create_session(self, session_id: str) -> Session:
        session = self.get_session(session_id)
        if session is None:
            self._sessions[session_id] = Session(session_id=session_id)
            session = self._sessions[session_id]
            logger.info(f"Auto-created session: {session_id}")
        return session

    def append_message(self, session_id: str, role: str, content: Any):
        session = self.get_or_create_session(session_id)
        session.messages.append({"role": role, "content": content})
        session.last_active = time.time()

    def get_messages(self, session_id: str) -> list[dict]:
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.messages

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    def cleanup_expired(self):
        """Remove all expired sessions."""
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_active > self._ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions.")


# Singleton
session_manager = SessionManager()
