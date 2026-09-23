"""Fire and rescue agent type."""
from app.agents.base import ResponderAgent


class FireAgent(ResponderAgent):
    """Own fire units; major incidents request two resources."""
