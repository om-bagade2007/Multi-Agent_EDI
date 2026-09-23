"""Core deterministic behavior and bus ordering tests."""
import numpy as np
import pytest

from app.core.bus import InMemoryBus
from app.core.events import make_event
from app.core.models import AgentKind, Incident, IncidentType, LatLon, UnitStatus
from app.sim.grid_sim import GridSim
from app.sim.incidents import requirements
from app.sim.manager import SimulationManager


@pytest.mark.asyncio
async def test_bus_drains_in_order_including_nested_publish() -> None:
    bus = InMemoryBus()
    seen: list[str] = []
    async def handler(event: object) -> None:
        seen.append(event.type)
        if event.type == "first":
            await bus.publish("events", make_event("second", 0, "test"))
    await bus.subscribe("events", "g", "c", handler)
    await bus.publish("events", make_event("first", 0, "test"))
    await bus.drain()
    assert seen == ["first", "second"]


def test_incident_requirements() -> None:
    assert requirements(IncidentType.accident, 4, False) == {AgentKind.police, AgentKind.ambulance, AgentKind.fire}
    assert requirements(IncidentType.fire, 3, True) == {AgentKind.fire, AgentKind.police, AgentKind.ambulance}
    assert requirements(IncidentType.medical, 1, False) == {AgentKind.ambulance}


def test_grid_routing_and_emergency_faster() -> None:
    sim = GridSim(size=8)
    sim.reset({}, np.random.default_rng(4))
    a, b = LatLon(lat=18.5204, lon=73.8567), LatLon(lat=18.536, lon=73.875)
    normal, distance = sim.travel_time(a, b, emergency=False)
    emergency, _ = sim.travel_time(a, b, emergency=True)
    assert distance > 0
    assert emergency < normal
    sim.dispatch_unit("A1", b, emergency=True)
    for _ in range(1000):
        sim.step(1)
    assert sim.unit_arrived("A1")


@pytest.mark.asyncio
async def test_seeded_episode_is_deterministic() -> None:
    first = await SimulationManager(seed=12, duration_s=600).run_episode()
    second = await SimulationManager(seed=12, duration_s=600).run_episode()
    assert first == second


@pytest.mark.asyncio
async def test_hospital_selector_falls_back_when_nearest_is_full() -> None:
    manager = SimulationManager(seed=1, duration_s=1)
    incident = Incident(id="I1", type=IncidentType.medical, severity=3, location=manager.sim.origin, created_at=0, injuries=True)
    nearest = min(manager.hospitals, key=lambda h: manager.sim.travel_time(incident.location, h.location, emergency=True)[0])
    nearest.beds_free = 0
    nearest.icu_free = 0
    selected = await manager._allocate_hospital(incident)
    assert selected is not None
    assert selected.id != nearest.id
    assert selected.beds_free == selected.beds_total - 1


@pytest.mark.asyncio
async def test_episode_reports_only_pending_incidents_as_queued() -> None:
    manager = SimulationManager(seed=2, duration_s=600)
    result = await manager.run_episode()
    pending = sum(incident.status.value == "pending" for incident in manager.incidents)
    assert result["metrics"]["queued_end"] == pending


@pytest.mark.asyncio
async def test_dispatch_waits_when_all_ambulances_are_busy() -> None:
    manager = SimulationManager(seed=3, duration_s=10)
    incident = Incident(id="I-test", type=IncidentType.medical, severity=2, location=manager.sim.origin, created_at=0, requires={AgentKind.ambulance})
    for unit in manager.units:
        if unit.kind == AgentKind.ambulance:
            unit.status = UnitStatus.en_route
    await manager._dispatch(incident)
    assert not manager.decisions
    next(unit for unit in manager.units if unit.kind == AgentKind.ambulance).status = UnitStatus.idle
    await manager._dispatch(incident)
    assert len(manager.decisions) == 1


@pytest.mark.asyncio
async def test_explanation_includes_chosen_and_runner_up_eta() -> None:
    manager = SimulationManager(seed=4, duration_s=10)
    incident = Incident(id="I-test", type=IncidentType.medical, severity=2, location=manager.sim.origin, created_at=0, requires={AgentKind.ambulance})
    await manager._dispatch(incident)
    reason = str(manager.decisions[0]["explanation"])
    assert "selected: ETA" in reason
    assert "next best" in reason
