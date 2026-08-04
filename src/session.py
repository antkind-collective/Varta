import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.conversation_memory import ConversationMemory

class Session:
    """
    Represents an active or closed conversational AI assistant session.
    Tracks session metadata and manages active session conversation memory.
    Memory exists strictly during the active session lifecycle (no persistent DB storage).
    """

    def __init__(self, session_id: Optional[str] = None, max_memory_turns: int = 10):
        self.session_id: str = session_id if session_id else uuid.uuid4().hex[:12]
        now_str = datetime.now(timezone.utc).isoformat()
        self.created_at: str = now_str
        self.last_activity: str = now_str
        self.message_count: int = 0
        self.status: str = "active"
        self.memory: ConversationMemory = ConversationMemory(max_history_turns=max_memory_turns)

    def update_activity(self) -> None:
        """Updates the last_activity timestamp to current UTC time."""
        self.last_activity = datetime.now(timezone.utc).isoformat()

    def increment_message_count(self) -> None:
        """Increments message count by 1 and updates last activity."""
        self.message_count += 1
        self.update_activity()

    def close(self) -> None:
        """Closes the session, clears memory, and updates last activity."""
        self.status = "closed"
        self.memory.clear()
        self.update_activity()

    def reset_memory(self) -> None:
        """Resets session memory while keeping session metadata active."""
        self.memory.clear()

    def is_active(self) -> bool:
        """Returns True if the session status is active."""
        return self.status == "active"

    def to_dict(self) -> Dict[str, Any]:
        """Returns a dictionary representation of session metadata."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "message_count": self.message_count,
            "status": self.status,
            "memory_turns_count": len(self.memory.turns)
        }
