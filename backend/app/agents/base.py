"""Shared responder agent base."""
from app.core.bus import EventBus
from app.core.models import AgentKind, Unit


class ResponderAgent:
    """Agent owns a fixed kind of units and an event transport."""
    def __init__(self, kind: AgentKind, units: list[Unit], bus: EventBus) -> None:
        self.kind, self.units, self.bus = kind, units, bus
        self.last_action = "Standing by"

    def idle_units(self) -> list[Unit]:
        """Return currently available units."""
        from app.core.models import UnitStatus
        return [unit for unit in self.units if unit.status == UnitStatus.idle]
