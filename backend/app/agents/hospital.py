"""Hospital resource agent type."""
from app.agents.base import ResponderAgent
from app.core.models import Hospital, Incident
from app.sim.base import SimBackend


class HospitalAgent(ResponderAgent):
    """Own and allocate finite hospital bed capacity."""

    def select_hospital(self, incident: Incident, hospitals: list[Hospital], sim: SimBackend) -> Hospital | None:
        """Reserve the nearest hospital with a bed and any required ICU bed."""
        ranked = sorted(hospitals, key=lambda hospital: sim.travel_time(incident.location, hospital.location, emergency=True)[0])
        for hospital in ranked:
            if hospital.beds_free > 0 and (incident.severity < 3 or hospital.icu_free > 0):
                hospital.beds_free -= 1
                if incident.severity >= 3:
                    hospital.icu_free -= 1
                return hospital
        return None
