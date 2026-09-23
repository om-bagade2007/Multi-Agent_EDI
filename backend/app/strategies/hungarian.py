"""Global minimum-cost assignment for a tick's responder demand."""
import numpy as np
from scipy.optimize import linear_sum_assignment

from app.core.models import Candidate, DispatchDecision, Incident, Unit
from app.sim.base import SimBackend


class HungarianStrategy:
    """Minimize total route ETA, with capacity and corridor adjustments."""
    name = 'hungarian'

    def select_unit(self, incident: Incident, idle_units: list[Unit], sim: SimBackend) -> DispatchDecision | None:
        return self.select_batch([incident], idle_units, sim)[0] if idle_units else None

    def select_batch(self, demands: list[Incident], idle_units: list[Unit], sim: SimBackend) -> list[DispatchDecision]:
        if not demands or not idle_units:
            return []
        costs = np.zeros((len(demands), len(idle_units)))
        routes = {}
        for row, incident in enumerate(demands):
            for col, unit in enumerate(idle_units):
                route = sim.routes.route(unit.location, incident.location, emergency=True)
                routes[row, col] = route
                factor = 1.0
                if unit.kind.value == 'ambulance' and incident.severity >= 4:
                    free_icu = sum(h.icu_free for h in getattr(sim, '_hospitals', []))
                    factor += 0.5 if free_icu == 0 else 0.0
                if unit.kind.value == 'police' and getattr(sim, 'cleared_corridors', set()):
                    factor *= 0.95
                costs[row, col] = route.eta_s * factor
        rows, cols = linear_sum_assignment(costs)
        result = []
        for row, col in zip(rows, cols):
            incident, unit = demands[row], idle_units[col]
            route = routes[row, col]
            alternatives = sorted((Candidate(unit_id=candidate.id, eta_s=sim.routes.route(candidate.location, incident.location, emergency=True).eta_s, distance_m=sim.routes.route(candidate.location, incident.location, emergency=True).distance_m) for candidate in idle_units), key=lambda item: (item.eta_s, item.unit_id))
            nearest = alternatives[0]
            tradeoff = '; global assignment trades local nearest for lower total batch cost' if nearest.unit_id != unit.id else '; also locally nearest'
            reason = f'{unit.id} assigned to {incident.id}: ETA {route.eta_s / 60:.1f} min, route distance {route.distance_m / 1000:.1f} km via {route.turns} turns{tradeoff}.'
            result.append(DispatchDecision(id=f'{incident.id}:{unit.id}:{sim.sim_time:.3f}', incident_id=incident.id, unit_id=unit.id, eta_s=route.eta_s, chosen_reason=reason, candidates=alternatives, strategy=self.name, sim_time=sim.sim_time))
        return result
