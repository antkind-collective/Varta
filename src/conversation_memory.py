from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class ConversationMemory:
    """
    In-Memory Session History Storage for VARTA AI Assistant.
    Maintains a sliding window of recent conversation turns (user queries & assistant responses)
    strictly within the active session lifecycle. Does NOT store retrieved document chunks or persist to DB.
    """

    def __init__(self, max_history_turns: int = 10):
        self.max_history_turns: int = max_history_turns
        self.turns: List[Dict[str, Any]] = []
        self.turn_counter: int = 0

    def add_turn(self, user_query: str, assistant_response: str) -> Dict[str, Any]:
        """
        Appends a conversation turn and maintains history within max_history_turns limit.
        """
        self.turn_counter += 1
        turn = {
            "turn_number": self.turn_counter,
            "user_query": user_query.strip(),
            "assistant_response": assistant_response.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.turns.append(turn)

        # Sliding window trimming
        if len(self.turns) > self.max_history_turns:
            self.turns = self.turns[-self.max_history_turns:]

        return turn

    def get_history(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Returns a list of conversation turns. If last_n is specified, returns only the last_n turns.
        """
        if last_n is not None and last_n > 0:
            return list(self.turns[-last_n:])
        return list(self.turns)

    def get_last_turn(self) -> Optional[Dict[str, Any]]:
        """
        Returns the most recent conversation turn, or None if history is empty.
        """
        return self.turns[-1] if self.turns else None

    def clear(self) -> None:
        """
        Clears all conversation turns and resets turn counter.
        """
        self.turns = []
        self.turn_counter = 0

    def get_turn_count(self) -> int:
        """
        Returns the total number of turns processed in this memory session.
        """
        return self.turn_counter

    def to_dict(self) -> List[Dict[str, Any]]:
        """
        Returns serializable list representation of stored conversation history.
        """
        return list(self.turns)
