"""Hospital resource agent type."""
from app.agents.base import ResponderAgent


class HospitalAgent(ResponderAgent):
    """Own and allocate finite hospital bed capacity."""
