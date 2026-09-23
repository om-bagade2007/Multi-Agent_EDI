"""Core deterministic behavior and bus ordering tests."""
import numpy as np
import pytest

from app.core.bus import InMemoryBus
from app.core.events import make_event
from app.core.models import AgentKind, IncidentType, LatLon
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
