"""Pure Python deterministic grid routing and movement."""
import itertools
import math

import networkx as nx
import numpy as np

from app.core.models import LatLon
from app.sim.base import EdgeState


class GridSim:
    """Grid road graph with seeded traffic and interpolated unit movement."""
    def __init__(self, origin: LatLon | None = None, size: int = 8, block_m: float = 250.0) -> None:
        self.origin = origin or LatLon(lat=18.5204, lon=73.8567)
        self.size, self.block_m, self.sim_time = size, block_m, 0.0
        self.rng = np.random.default_rng(0)
        self.noise: dict[str, float] = {}
        self.vehicles: dict[str, dict[str, object]] = {}
        self.cleared_corridors: set[str] = set()
        self.graph = nx.grid_2d_graph(size, size)
        for a, b in self.graph.edges:
            key = self.edge_id(a, b)
            self.graph.edges[a, b].update(id=key, length=block_m)

    @staticmethod
    def edge_id(a: tuple[int, int], b: tuple[int, int]) -> str:
        """Create a stable edge identifier."""
        return f"{a[0]}_{a[1]}-{b[0]}_{b[1]}"

    def reset(self, scenario: dict[str, object], rng: np.random.Generator) -> None:
        """Reset traffic state using the explicitly supplied episode RNG."""
        self.rng = rng
        origin = scenario.get("origin")
        if isinstance(origin, dict):
            self.origin = LatLon.model_validate(origin)
        self.noise = {d["id"]: float(rng.uniform(0.85, 1.15)) for *_, d in self.graph.edges(data=True)}
        self.sim_time, self.vehicles = 0.0, {}
        self.cleared_corridors.clear()

    def _coordinate(self, node: tuple[int, int]) -> LatLon:
        """Map grid coordinates to geographic coordinates."""
        lat_delta = self.block_m / 111_320
        lon_delta = self.block_m / (111_320 * math.cos(math.radians(self.origin.lat)))
        return LatLon(lat=self.origin.lat + node[0] * lat_delta, lon=self.origin.lon + node[1] * lon_delta)

    def _node(self, loc: LatLon) -> tuple[int, int]:
        """Snap a coordinate to its nearest grid intersection."""
        lat_scale = self.block_m / 111_320
        lon_scale = self.block_m / (111_320 * math.cos(math.radians(self.origin.lat)))
        i = round((loc.lat - self.origin.lat) / lat_scale)
        j = round((loc.lon - self.origin.lon) / lon_scale)
        return min(self.size - 1, max(0, i)), min(self.size - 1, max(0, j))

    def _congestion(self, edge: dict[str, object]) -> float:
        """Return smooth time-varying edge congestion in [0.35, 1]."""
        rush = 0.78 + 0.14 * math.sin(2 * math.pi * self.sim_time / 3600)
        value = rush * self.noise.get(str(edge["id"]), 1.0)
        return min(1.0, max(0.35, value))

    def travel_time(self, origin: LatLon, dest: LatLon, *, emergency: bool) -> tuple[float, float]:
        """Estimate route time with Dijkstra using current edge congestion."""
        start, end = self._node(origin), self._node(dest)
        if start == end:
            return 0.0, 0.0
        for a, b, data in self.graph.edges(data=True):
            speed_factor = 1.3 * (1.2 if emergency and self.cleared_corridors else 1.0) if emergency else 1.0
            data["weight"] = data["length"] / (13.9 * self._congestion(data) * speed_factor)
        path = nx.shortest_path(self.graph, start, end, weight="weight")
        seconds = sum(self.graph.edges[a, b]["weight"] for a, b in itertools.pairwise(path))
        return seconds, (len(path) - 1) * self.block_m

    def set_corridor_cleared(self, unit_id: str, cleared: bool) -> None:
        """Track police corridor clearance while its unit is en route."""
        if cleared:
            self.cleared_corridors.add(unit_id)
        else:
            self.cleared_corridors.discard(unit_id)

    def dispatch_unit(self, unit_id: str, dest: LatLon, *, emergency: bool) -> None:
        """Start unit movement toward a snapped destination."""
        origin = self.unit_position(unit_id)
        path = nx.shortest_path(self.graph, self._node(origin), self._node(dest), weight="length")
        self.vehicles[unit_id] = {"path": path, "index": 0, "elapsed": 0.0, "duration": self.travel_time(origin, dest, emergency=emergency)[0], "start": origin, "end": dest}

    def step(self, dt: float = 1.0) -> None:
        """Advance simulation time and active vehicles."""
        self.sim_time += dt
        for vehicle in self.vehicles.values():
            vehicle["elapsed"] = min(float(vehicle["duration"]), float(vehicle["elapsed"]) + dt)

    def unit_position(self, unit_id: str) -> LatLon:
        """Return interpolated position along the active Dijkstra path."""
        vehicle = self.vehicles.get(unit_id)
        if vehicle is None:
            return self._coordinate((0, 0))
        ratio = 1.0 if not vehicle["duration"] else min(1.0, float(vehicle["elapsed"]) / float(vehicle["duration"]))
        start, end = vehicle["start"], vehicle["end"]
        if ratio >= 1.0:
            return end
        path = vehicle["path"]
        if len(path) < 2:
            return start
        route_position = ratio * (len(path) - 1)
        segment = min(len(path) - 2, int(route_position))
        fraction = route_position - segment
        a, b = self._coordinate(path[segment]), self._coordinate(path[segment + 1])
        return LatLon(lat=a.lat + (b.lat - a.lat) * fraction, lon=a.lon + (b.lon - a.lon) * fraction)

    def unit_arrived(self, unit_id: str) -> bool:
        """Check if an active vehicle reached its destination."""
        item = self.vehicles.get(unit_id)
        return bool(item is not None and float(item["elapsed"]) >= float(item["duration"]))

    def traffic_snapshot(self) -> list[EdgeState]:
        """Return road geometry and congestion for the dashboard."""
        result: list[EdgeState] = []
        for a, b, data in self.graph.edges(data=True):
            result.append(EdgeState(id=str(data["id"]), geometry=[self._coordinate(a), self._coordinate(b)], congestion=self._congestion(data)))
        return result

    def mean_traffic_delay(self) -> float:
        """Estimate mean extra travel time per road edge against free flow."""
        states = self.traffic_snapshot()
        return sum(self.block_m / 13.9 * (1 / s.congestion - 1) for s in states) / max(1, len(states))
