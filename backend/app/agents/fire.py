"""Fire and rescue agent type."""
from app.agents.base import ResponderAgent
from app.core.models import Incident


class FireAgent(ResponderAgent):
    """Own fire units; major incidents request two resources."""

    @staticmethod
    def required_units(incident: Incident) -> int:
        """Request a second crew for high-severity incidents."""
        return 2 if incident.severity >= 4 else 1
