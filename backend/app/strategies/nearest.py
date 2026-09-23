"""Nearest-resource baseline using route-time estimates."""

from app.core.models import Candidate, DispatchDecision, Incident, Unit
from app.sim.base import SimBackend


class NearestStrategy:
    """Choose the idle responder with the smallest network ETA."""
    name = "nearest"

    def select_unit(self, incident: Incident, idle_units: list[Unit], sim: SimBackend) -> DispatchDecision | None:
        """Return a decision with every idle candidate ranked by travel time."""
        candidates: list[Candidate] = []
        for unit in idle_units:
            eta, distance = sim.travel_time(unit.location, incident.location, emergency=True)
            candidates.append(Candidate(unit_id=unit.id, eta_s=eta, distance_m=distance))
        candidates.sort(key=lambda candidate: (candidate.eta_s, candidate.unit_id))
        if not candidates:
            return None
        chosen = candidates[0]
        unit = next(unit for unit in idle_units if unit.id == chosen.unit_id)
        route = sim.routes.route(unit.location, incident.location, emergency=True)
        runner = f"; next best {candidates[1].unit_id}: {candidates[1].eta_s / 60:.1f} min" if len(candidates) > 1 else ""
        reason = f"{chosen.unit_id} selected: ETA {chosen.eta_s / 60:.1f} min, route distance {route.distance_m/1000:.1f} km via {route.turns} turns, fastest of {len(candidates)} idle units{runner}."
        return DispatchDecision(id=f"{incident.id}:{chosen.unit_id}:{sim.sim_time:.3f}", incident_id=incident.id, unit_id=chosen.unit_id, eta_s=chosen.eta_s, chosen_reason=reason, candidates=candidates, sim_time=sim.sim_time)

    def select_batch(self, demands: list[Incident], idle_units: list[Unit], sim: SimBackend) -> list[DispatchDecision]:
        """Preserve request ordering while preventing duplicate unit assignment."""
        available = list(idle_units)
        decisions = []
        for incident in demands:
            decision = self.select_unit(incident, available, sim)
            if decision:
                decisions.append(decision)
                available = [unit for unit in available if unit.id != decision.unit_id]
        return decisions
