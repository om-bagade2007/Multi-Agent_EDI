"""Cached A* routing over the Pune OSM graph with time-of-day congestion."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from time import perf_counter

from scipy.spatial import cKDTree

from app.core.models import LatLon
from app.routing.astar import astar
from app.sim.pune_network import PuneNetwork


@dataclass(frozen=True)
class PuneRouteResult:
    """Travel-time route and its geometry for dispatch and animation."""
    path: list[str]
    polyline: list[LatLon]
    distance_m: float
    eta_s: float
    turns: int
    elapsed_ms: float


def haversine_m(a: LatLon, b: LatLon) -> float:
    """Great-circle distance between WGS84 points."""
    radius = 6_371_000
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat, dlon = lat2 - lat1, math.radians(b.lon - a.lon)
    term = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(term))


class PuneRouteService:
    """Compute congestion-aware A* routes and cache paths per hour bucket."""
    def __init__(self, sim: object) -> None:
        self.sim = sim
        self.network: PuneNetwork = sim.network
        self.nodes = list(self.network.coordinates)
        points = [(lon * math.cos(math.radians(lat)), lat) for lat, lon in self.network.coordinates.values()]
        self.tree = cKDTree(points)
        self.max_speed_mps = max(float(edge["speed_kph"]) for edge in self.network.data["edges"]) / 3.6

    def nearest_node(self, point: LatLon) -> str:
        """Snap a live coordinate to its nearest road intersection."""
        _, index = self.tree.query((point.lon * math.cos(math.radians(point.lat)), point.lat))
        return self.nodes[int(index)]

    def factor(self, edge: dict[str, object], hour_bucket: int) -> float:
        """Return an edge-class speed multiplier for the simulated hour."""
        hour = hour_bucket % 24
        road = str(edge.get("road_class", "tertiary")).removesuffix("_link")
        if 8 <= hour < 11 or 17 <= hour < 20:
            base = {"motorway": .70, "trunk": .62, "primary": .50, "secondary": .54, "tertiary": .62}.get(road, .62)
        elif hour < 6 or hour >= 23:
            base = .96
        else:
            base = .83
        return base * self.sim.edge_noise.get(str(edge["id"]), 1.0)

    def route(self, origin: LatLon, dest: LatLon, *, emergency: bool = False) -> PuneRouteResult:
        """Route between snapped nodes, returning path geometry, distance, ETA, turns."""
        start, goal = self.nearest_node(origin), self.nearest_node(dest)
        bucket = int(self.sim.sim_time // 3600) % 24
        corridor = bool(self.sim.cleared_corridors)
        started = perf_counter()
        path, eta = self._cached_path(start, goal, bucket, emergency, corridor)
        distance, polyline = 0.0, []
        for index, (a, b) in enumerate(pairwise(path)):
            edge = self.network.edge(a, b)
            distance += float(edge["length_m"])
            points = edge["geometry"]
            if index and polyline and points and polyline[-1] == points[0]:
                points = points[1:]
            polyline.extend(points)
        if not polyline:
            lat, lon = self.network.coordinates[start]
            polyline = [[lon, lat]]
        turns = 0
        vectors = [(b[1] - a[1], b[0] - a[0]) for a, b in pairwise(polyline)]
        for first, second in pairwise(vectors):
            denom = math.hypot(*first) * math.hypot(*second)
            if denom and (first[0] * second[0] + first[1] * second[1]) / denom < .999:
                turns += 1
        return PuneRouteResult(path, [LatLon(lat=float(lat), lon=float(lon)) for lon, lat in polyline], distance, eta, turns, (perf_counter() - started) * 1000)

    @lru_cache(maxsize=30_000)
    def _cached_path(self, start: str, goal: str, bucket: int, emergency: bool, corridor: bool) -> tuple[tuple[str, ...], float]:
        """Cache deterministic route paths per endpoints and traffic hour."""
        emergency_factor = 1.3 * (1.2 if emergency and corridor else 1.0) if emergency else 1.0
        def neighbors(node: str):
            for adjacent in self.network.neighbors(node):
                edge = self.network.edge(node, adjacent)
                yield adjacent, float(edge["travel_time_s"]) / max(.01, self.factor(edge, bucket) * emergency_factor)
        def heuristic(a: str, b: str) -> float:
            p1 = self.network.coordinates[a]
            p2 = self.network.coordinates[b]
            return haversine_m(LatLon(lat=p1[0], lon=p1[1]), LatLon(lat=p2[0], lon=p2[1])) / (self.max_speed_mps * emergency_factor)
        path, eta = astar(start, goal, neighbors, heuristic)
        return tuple(path), eta

    def clear_cache(self) -> None:
        """Drop paths when a fresh seed changes edge traffic noise."""
        self._cached_path.cache_clear()
