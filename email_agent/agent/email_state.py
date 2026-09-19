from typing import List, Dict, Any
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    """
    The state for the Email Agent graph.
    It tracks the list of messages in the conversation, appending new messages to the existing list.
    """
    revision_count: int
    emails: List[Dict[str, Any]]
    email_draft: Dict[str, Any]
