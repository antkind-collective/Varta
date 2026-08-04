from typing import Dict, List, Optional
from src.session import Session

class ConversationManager:
    """
    Manages in-memory chat session lifecycles without long-term history storage.
    Responsible for session creation, tracking active sessions, and closing sessions.
    """

    def __init__(self):
        self.sessions: Dict[str, Session] = {}

    def create_session(self, session_id: Optional[str] = None) -> Session:
        """Creates a new session and registers it in memory."""
        session = Session(session_id=session_id)
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieves a session by session_id if it exists."""
        return self.sessions.get(session_id)

    def end_session(self, session_id: str) -> Optional[Session]:
        """Closes the specified session and updates its status."""
        session = self.get_session(session_id)
        if session:
            session.close()
        return session

    def list_active_sessions(self) -> List[Session]:
        """Returns a list of all currently active sessions."""
        return [session for session in self.sessions.values() if session.is_active()]
