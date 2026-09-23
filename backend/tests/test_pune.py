"""Real Pune dataset, routing, optimization, and seeded determinism checks."""
import asyncio
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from app.core.models import AgentKind, Incident, IncidentType, LatLon, Unit
from app.sim.manager import SimulationManager
from app.sim.pune_network import PuneNetwork
from app.sim.pune_sim import PuneSim
from app.strategies.hungarian import HungarianStrategy
from app.strategies.nearest import NearestStrategy

DATA = Path(__file__).resolve().parents[2] / "data" / "pune"


@pytest.fixture(scope="module")
def network() -> PuneNetwork:
    return PuneNetwork(DATA)


def test_pune_network_is_strong_and_facilities_are_snapped(network: PuneNetwork) -> None:
    assert 1500 <= network.graph.number_of_nodes() <= 8000
    assert nx.is_strongly_connected(network.graph)
    assert all(float(facility["snap_distance_m"]) <= 300 for facility in network.data["pois"])
    assert sum(item["kind"] == "hospital" for item in network.data["pois"]) >= 3
    assert sum(item["kind"] == "fire_station" for item in network.data["pois"]) >= 2
    assert sum(item["kind"] == "police" for item in network.data["pois"]) >= 3
    assert (DATA / "roads.geojson").stat().st_size < 3_000_000


def test_first_unit_route_begins_at_its_registered_station(network: PuneNetwork) -> None:
    sim = PuneSim(DATA)
    sim.reset({}, np.random.default_rng(7))
    start_id = next(iter(network.coordinates))
    start = LatLon(lat=network.coordinates[start_id][0], lon=network.coordinates[start_id][1])
    poi = network.data["pois"][0]
    destination = LatLon(lat=poi["lat"], lon=poi["lon"])
    sim.register_unit("A1", start)
    sim.dispatch_unit("A1", destination, emergency=True)
    assert sim.vehicles["A1"]["start"] == start


def test_pune_astar_matches_networkx_dijkstra_on_random_pairs(network: PuneNetwork) -> None:
    sim = PuneSim(DATA)
    sim.reset({}, np.random.default_rng(24))
    simple = nx.DiGraph()
    simple.add_nodes_from(network.graph.nodes)
    for source, target, _, data in network.graph.edges(keys=True, data=True):
        weight = float(data["travel_time_s"]) / sim.routes.factor(data, 0)
        if not simple.has_edge(source, target) or weight < simple[source][target]["weight"]:
            simple.add_edge(source, target, weight=weight)
    rng = np.random.default_rng(41)
    nodes = list(network.graph.nodes)
    for _ in range(20):
        start, goal = rng.choice(nodes, 2, replace=False)
        source = LatLon(lat=network.coordinates[str(start)][0], lon=network.coordinates[str(start)][1])
        target = LatLon(lat=network.coordinates[str(goal)][0], lon=network.coordinates[str(goal)][1])
        result = sim.routes.route(source, target)
        expected = nx.shortest_path_length(simple, str(start), str(goal), weight="weight")
        assert abs(result.eta_s - expected) <= expected * .01
        assert len(result.polyline) >= 1 and result.distance_m >= 0


def test_hungarian_cost_is_no_worse_than_greedy_for_50_pune_batches(network: PuneNetwork) -> None:
    sim = PuneSim(DATA)
    sim.reset({}, np.random.default_rng(12))
    rng = np.random.default_rng(73)
    nodes = list(network.graph.nodes)
    greedy = NearestStrategy()
    optimal = HungarianStrategy()
    for batch in range(50):
        unit_nodes = rng.choice(nodes, 2, replace=False)
        incident_nodes = rng.choice(nodes, 2, replace=False)
        units = [Unit(id=f"A{batch}-{i}", kind=AgentKind.ambulance, station_id="H", location=LatLon(lat=network.coordinates[str(node)][0], lon=network.coordinates[str(node)][1])) for i, node in enumerate(unit_nodes)]
        incidents = [Incident(id=f"I{batch}-{i}", type=IncidentType.medical, severity=int(rng.integers(1, 3)), location=LatLon(lat=network.coordinates[str(node)][0], lon=network.coordinates[str(node)][1]), created_at=0, requires={AgentKind.ambulance}) for i, node in enumerate(incident_nodes)]
        base = sum(item.eta_s for item in greedy.select_batch(incidents, units, sim))
        assigned = sum(item.eta_s for item in optimal.select_batch(incidents, units, sim))
        assert assigned <= base + 1e-6


def test_pune_metrics_are_deterministic_for_same_seed() -> None:
    async def run():
        first = await SimulationManager(seed=29, duration_s=300, rate_per_minute=.67, simulation_mode="pune", data_dir=DATA).run_episode()
        second = await SimulationManager(seed=29, duration_s=300, rate_per_minute=.67, simulation_mode="pune", data_dir=DATA).run_episode()
        return first, second
    first, second = asyncio.run(run())
    assert first["metrics"] == second["metrics"]
