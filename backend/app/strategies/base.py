"""Extension interfaces for dispatch and hospital selection."""
from typing import Protocol

from app.core.models import DispatchDecision, Incident, Unit
from app.sim.base import SimBackend


class DispatchStrategy(Protocol):
    """Select a resource; future A* and Hungarian strategies plug in here."""
    name: str
    def select_unit(self, incident: Incident, idle_units: list[Unit], sim: SimBackend) -> DispatchDecision | None: ...


class HospitalSelector(Protocol):
    """Choose a hospital with capacity; replaceable independently of dispatch."""
    def select_hospital(self, incident: Incident, hospitals: list[object], sim: SimBackend) -> object | None: ...
