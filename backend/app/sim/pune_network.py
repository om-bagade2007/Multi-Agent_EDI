"""Validated access to the committed Pune road network and facilities."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import networkx as nx

BBOX = {"south": 18.47, "north": 18.58, "west": 73.79, "east": 73.93}


class PuneNetwork:
    """Road graph with snapped OSM nodes, directed edges, and cached GeoJSON."""
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.resolve()
        network_path = self.data_dir / "network.json"
        roads_path = self.data_dir / "roads.geojson"
        if not network_path.is_file() or not roads_path.is_file():
            raise ValueError(f"Pune data is missing in {self.data_dir}; run `make pune-data`.")
        try:
            self.data: dict[str, Any] = json.loads(network_path.read_text(encoding="utf-8"))
            self.roads: dict[str, Any] = json.loads(roads_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Pune data is unreadable or corrupt in {self.data_dir}: {error}") from error
        if self.data.get("bbox") != BBOX:
            raise ValueError("Pune dataset bbox does not match the supported bounds.")
        nodes = self.data.get("nodes")
        edges = self.data.get("edges")
        pois = self.data.get("pois")
        if not isinstance(nodes, list) or len(nodes) < 1500 or not isinstance(edges, list) or not edges or not isinstance(pois, list):
            raise ValueError("Pune network data has no valid node, edge, or facility arrays.")
        self.graph = nx.MultiDiGraph()
        self.coordinates: dict[str, tuple[float, float]] = {}
        for node in nodes:
            lat, lon = float(node["lat"]), float(node["lon"])
            if not self.valid(lat, lon):
                raise ValueError(f"Pune graph node {node.get('id')} is outside the configured bbox.")
            node_id = str(node["id"])
            self.coordinates[node_id] = (lat, lon)
            self.graph.add_node(node_id, lat=lat, lon=lon)
        for edge in edges:
            source, target = str(edge["from"]), str(edge["to"])
            if source not in self.coordinates or target not in self.coordinates:
                raise ValueError(f"Pune edge {edge.get('id')} references an unknown node.")
            length, speed, travel = float(edge["length_m"]), float(edge["speed_kph"]), float(edge["travel_time_s"])
            geometry = edge["geometry"]
            if not all(math.isfinite(value) for value in (length, speed, travel)) or min(length, speed, travel) <= 0 or len(geometry) < 2:
                raise ValueError(f"Pune edge {edge.get('id')} has invalid length, speed, time, or geometry.")
            if any(not self.valid(float(lat), float(lon)) for lon, lat in geometry):
                raise ValueError(f"Pune edge {edge.get('id')} has geometry outside the configured bbox.")
            self.graph.add_edge(source, target, **edge)
        if not nx.is_strongly_connected(self.graph):
            raise ValueError("Pune network must be one strongly connected component.")
        for poi in pois:
            if str(poi.get("node")) not in self.coordinates or not self.valid(float(poi["lat"]), float(poi["lon"])):
                raise ValueError(f"Facility {poi.get('id')} is invalid or unsnapped.")
            if float(poi["snap_distance_m"]) > 300:
                raise ValueError(f"Facility {poi.get('id')} is more than 300 m from the graph.")
        if not self.roads.get("type") == "FeatureCollection" or not isinstance(self.roads.get("features"), list):
            raise ValueError("Pune roads GeoJSON must be a FeatureCollection.")

    @staticmethod
    def valid(lat: float, lon: float) -> bool:
        """Check finite coordinates against the contracted central Pune bbox."""
        return math.isfinite(lat) and math.isfinite(lon) and BBOX["south"] <= lat <= BBOX["north"] and BBOX["west"] <= lon <= BBOX["east"]

    def neighbors(self, node_id: str) -> list[str]:
        """Return all directed outgoing road neighbors."""
        return list(self.graph.successors(node_id))

    def edge(self, source: str, target: str) -> dict[str, Any]:
        """Choose the fastest stored parallel road segment for an endpoint pair."""
        options = self.graph.get_edge_data(source, target)
        return min(options.values(), key=lambda edge: edge["travel_time_s"])
