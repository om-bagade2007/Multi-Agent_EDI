"""Agent class registry."""
from app.agents.ambulance import AmbulanceAgent
from app.agents.fire import FireAgent
from app.agents.hospital import HospitalAgent
from app.agents.police import PoliceAgent
from app.core.models import AgentKind

AGENTS = {AgentKind.ambulance: AmbulanceAgent, AgentKind.fire: FireAgent, AgentKind.police: PoliceAgent, AgentKind.hospital: HospitalAgent}
