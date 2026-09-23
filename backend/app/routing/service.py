"""GridSim route results, including congestion-aware ETA and distance."""
import time
from dataclasses import dataclass
from itertools import pairwise

from app.core.models import LatLon
from app.routing.astar import astar


@dataclass(frozen=True)
class RouteResult:
    path: list[tuple[int, int]]
    distance_m: float
    eta_s: float
    turns: int
    elapsed_ms: float

class RouteService:
    """Compute GridSim routes from current edge congestion."""
    def __init__(self, sim: object) -> None:
        self.sim = sim

    def route(self, origin: LatLon, dest: LatLon, *, emergency: bool = False) -> RouteResult:
        sim = self.sim
        start, goal = sim._node(origin), sim._node(dest)
        speed_factor = 1.3 * (1.2 if emergency and sim.cleared_corridors else 1.0) if emergency else 1.0
        def edges(node: tuple[int, int]):
            for neighbor in sim.graph.neighbors(node):
                data = sim.graph.edges[node, neighbor]
                seconds = float(data['length']) / (13.9 * sim._congestion(data) * speed_factor)
                yield neighbor, seconds
        min_edge = sim.block_m / (13.9 * speed_factor)
        def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
            return (abs(a[0] - b[0]) + abs(a[1] - b[1])) * min_edge
        started = time.perf_counter()
        path, eta = astar(start, goal, edges, heuristic)
        elapsed = (time.perf_counter() - started) * 1000
        directions = [(b[0] - a[0], b[1] - a[1]) for a, b in pairwise(path)]
        turns = sum(first != second for first, second in pairwise(directions))
        return RouteResult(path, (len(path) - 1) * sim.block_m, eta, turns, elapsed)
