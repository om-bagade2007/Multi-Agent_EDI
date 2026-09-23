"""Live movement and seeded traffic on the real Pune road network."""
from __future__ import annotations

from itertools import pairwise
from typing import Any

import numpy as np

from app.core.models import LatLon
from app.routing.pune import PuneRouteService, haversine_m
from app.sim.base import EdgeState
from app.sim.pune_network import PuneNetwork


class PuneSim:
    """Simulation backend compatible with the dispatch agents and strategies."""
    def __init__(self, data_dir) -> None:
        self.network = PuneNetwork(data_dir)
        self.data = self.network.data
        self.graph = self.network.graph
        self.origin = LatLon(lat=18.5204, lon=73.8567)
        self.sim_time = 0.0
        self.rng = np.random.default_rng(0)
        self.edge_noise: dict[str, float] = {}
        self.vehicles: dict[str, dict[str, Any]] = {}
        self.unit_positions: dict[str, LatLon] = {}
        self.cleared_corridors: set[str] = set()
        self._hospitals: list[Any] = []
        self.routes = PuneRouteService(self)

    def reset(self, scenario: dict[str, object], rng: np.random.Generator) -> None:
        """Reset hour, vehicles, and deterministic per-edge variation."""
        del scenario
        self.rng, self.sim_time, self.vehicles, self.unit_positions = rng, 0.0, {}, {}
        self.edge_noise = {str(data["id"]): float(rng.uniform(.96, 1.04)) for _, _, _, data in self.graph.edges(keys=True, data=True)}
        self.cleared_corridors.clear()
        self.routes.clear_cache()

    def _node(self, point: LatLon) -> str:
        """Snap a geographic point to its closest OSM intersection."""
        return self.routes.nearest_node(point)

    def _coordinate(self, node: str) -> LatLon:
        """Return a graph node's WGS84 coordinate."""
        lat, lon = self.network.coordinates[node]
        return LatLon(lat=lat, lon=lon)

    def register_unit(self, unit_id: str, location: LatLon) -> None:
        """Register a responder's snapped initial position before its first dispatch."""
        self.unit_positions[unit_id] = location

    def sample_location(self, rng: np.random.Generator) -> LatLon:
        """Sample hotspots 60% of the time and uniform graph nodes otherwise."""
        if not hasattr(self, "_hotspots"):
            self._hotspots = [node for node in self.graph if self.graph.degree(node) >= 4 and any(str(data.get("road_class", "")).startswith(("primary", "secondary")) for _, _, data in self.graph.in_edges(node, data=True))]
            if not self._hotspots:
                self._hotspots = list(self.graph.nodes)
        candidates = self._hotspots if rng.random() < .6 else list(self.graph.nodes)
        return self._coordinate(str(candidates[int(rng.integers(0, len(candidates)))]))

    def _congestion(self, edge: dict[str, object]) -> float:
        """Get the seeded speed multiplier for current simulated hour."""
        return self.routes.factor(edge, int(self.sim_time // 3600) % 24)

    def travel_time(self, origin: LatLon, dest: LatLon, *, emergency: bool) -> tuple[float, float]:
        """Return route ETA and road distance."""
        route = self.routes.route(origin, dest, emergency=emergency)
        return route.eta_s, route.distance_m

    def set_corridor_cleared(self, unit_id: str, cleared: bool) -> None:
        """Track police corridor state used by emergency routing."""
        if cleared:
            self.cleared_corridors.add(unit_id)
        else:
            self.cleared_corridors.discard(unit_id)

    def dispatch_unit(self, unit_id: str, dest: LatLon, *, emergency: bool) -> None:
        """Start the unit moving over the selected directed route geometry."""
        start = self.unit_position(unit_id)
        route = self.routes.route(start, dest, emergency=emergency)
        legs = []
        emergency_speed = 1.3 * (1.2 if emergency and self.cleared_corridors else 1.0) if emergency else 1.0
        for a, b in zip(route.path, route.path[1:]):
            edge = self.network.edge(a, b)
            factor = self._congestion(edge) * emergency_speed
            legs.append({"points": edge["geometry"], "duration": float(edge["travel_time_s"]) / max(.01, factor)})
        self.vehicles[unit_id] = {"legs": legs, "elapsed": 0.0, "duration": route.eta_s, "start": start, "end": dest, "polyline": route.polyline}

    def step(self, dt: float = 1.0) -> None:
        """Advance simulation and vehicle route clocks."""
        self.sim_time += dt
        for vehicle in self.vehicles.values():
            vehicle["elapsed"] = min(float(vehicle["duration"]), float(vehicle["elapsed"]) + dt)

    @staticmethod
    def _point_on_leg(points: list[list[float]], fraction: float) -> LatLon:
        """Interpolate by route distance over the OSM edge geometry."""
        lengths = [haversine_m(LatLon(lat=float(a[1]), lon=float(a[0])), LatLon(lat=float(b[1]), lon=float(b[0]))) for a, b in pairwise(points)]
        total = sum(lengths)
        target = fraction * total
        for index, length in enumerate(lengths):
            if target <= length:
                ratio = target / max(length, .001)
                a, b = points[index], points[index + 1]
                return LatLon(lat=float(a[1] + (b[1] - a[1]) * ratio), lon=float(a[0] + (b[0] - a[0]) * ratio))
            target -= length
        return LatLon(lat=float(points[-1][1]), lon=float(points[-1][0]))

    def unit_position(self, unit_id: str) -> LatLon:
        """Return the current position interpolated along the real road polyline."""
        vehicle = self.vehicles.get(unit_id)
        if vehicle is None:
            return self.unit_positions.get(unit_id, self._coordinate(next(iter(self.network.coordinates))))
        elapsed = float(vehicle["elapsed"])
        if elapsed >= float(vehicle["duration"]):
            return vehicle["end"]
        for leg in vehicle["legs"]:
            if elapsed <= float(leg["duration"]):
                points = leg["points"]
                if len(points) >= 2:
                    return self._point_on_leg(points, elapsed / max(.001, float(leg["duration"])))
            elapsed -= float(leg["duration"])
        return vehicle["end"]

    def unit_arrived(self, unit_id: str) -> bool:
        """Check whether a route has completed."""
        item = self.vehicles.get(unit_id)
        return bool(item is not None and float(item["elapsed"]) >= float(item["duration"]))

    def traffic_snapshot(self) -> list[EdgeState]:
        """Keep static road geometry in the cacheable network endpoint."""
        return []

    def mean_traffic_delay(self) -> float:
        """Mean extra edge time compared with each road's free-flow ETA."""
        edges = list(self.graph.edges(data=True))
        return sum(float(edge["travel_time_s"]) * (1 / self._congestion(edge) - 1) for _, _, edge in edges) / max(1, len(edges))

    def active_routes(self) -> list[dict[str, object]]:
        """Current route polylines for map updates."""
        return [{"unit_id": unit_id, "polyline": vehicle["polyline"]} for unit_id, vehicle in self.vehicles.items() if not self.unit_arrived(unit_id)]
