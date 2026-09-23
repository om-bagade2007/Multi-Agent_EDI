"""Shared responder agent base."""
from app.core.bus import EventBus
from app.core.models import AgentKind, DispatchDecision, Incident, Unit
from app.sim.base import SimBackend
from app.strategies.base import DispatchStrategy


class ResponderAgent:
    """Agent owns a fixed kind of units and an event transport."""
    def __init__(self, kind: AgentKind, units: list[Unit], bus: EventBus) -> None:
        self.kind, self.units, self.bus = kind, units, bus
        self.last_action = "Standing by"

    def idle_units(self) -> list[Unit]:
        """Return currently available units."""
        from app.core.models import UnitStatus
        return [unit for unit in self.units if unit.status == UnitStatus.idle]

    def select_for_incident(self, incident: Incident, sim: SimBackend, strategy: DispatchStrategy, limit: int = 1) -> list[DispatchDecision]:
        """Choose up to ``limit`` distinct idle units using the shared strategy."""
        if self.kind not in incident.requires:
            return []
        candidates = self.idle_units()
        decisions: list[DispatchDecision] = []
        for _ in range(limit):
            decision = strategy.select_unit(incident, candidates, sim)
            if decision is None:
                break
            decisions.append(decision)
            candidates = [unit for unit in candidates if unit.id != decision.unit_id]
        return decisions
