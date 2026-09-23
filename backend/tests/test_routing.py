"""A* correctness and default-grid performance checks."""
import time

import networkx as nx
import numpy as np

from app.sim.grid_sim import GridSim


def test_astar_matches_dijkstra_on_fixture_grid() -> None:
    sim = GridSim(size=5, block_m=100)
    sim.reset({}, np.random.default_rng(19))
    origin, dest = sim._coordinate((0, 0)), sim._coordinate((4, 4))
    result = sim.routes.route(origin, dest, emergency=True)
    start, goal = sim._node(origin), sim._node(dest)
    reference = nx.shortest_path_length(sim.graph, start, goal, weight=lambda a, b, d: sim.block_m / (13.9 * sim._congestion(d) * 1.3))
    assert abs(result.eta_s - reference) < 1e-9
    assert result.distance_m == 800
    assert result.turns == 1

def test_default_grid_route_is_under_50ms() -> None:
    sim = GridSim()
    a, b = sim._coordinate((0, 0)), sim._coordinate((7, 7))
    timings = []
    for _ in range(20):
        started = time.perf_counter()
        sim.routes.route(a, b)
        timings.append((time.perf_counter() - started) * 1000)
    assert max(timings) < 50
