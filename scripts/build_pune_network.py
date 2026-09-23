"""Download, simplify, validate, and serialize the Pune OSM driving network."""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import osmnx as ox

BBOX = (18.47, 18.58, 73.79, 73.93)  # south, north, west, east
CLASSES = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}
DEFAULT_SPEED = {"motorway": 80, "trunk": 60, "primary": 40, "secondary": 30, "tertiary": 25}
ROOT = Path(__file__).resolve().parents[1]


def speed_for(tags: object, road_class: str) -> float:
    """Parse OSM maxspeed tags, with documented urban fallback speeds."""
    value = tags if isinstance(tags, str) else (tags[0] if isinstance(tags, list) and tags else None)
    if value:
        try:
            number = float(str(value).split()[0])
            return number * (1.60934 if "mph" in str(value).lower() else 1.0)
        except ValueError:
            pass
    base = road_class.removesuffix("_link")
    return float(DEFAULT_SPEED.get(base, 25))


def main() -> None:
    south, north, west, east = BBOX
    tags = {"amenity": ["hospital", "fire_station", "police"]}
    bbox = (west, south, east, north)
    graph = ox.graph_from_bbox(bbox, network_type="drive", simplify=True, retain_all=True)
    graph = ox.project_graph(graph, to_crs="EPSG:4326")
    for node, data in list(graph.nodes(data=True)):
        if not (south <= data["y"] <= north and west <= data["x"] <= east):
            graph.remove_node(node)
    graph = nx.MultiDiGraph(graph)
    def classes(value: object) -> set[str]:
        return {value} if isinstance(value, str) else set(value or [])
    graph.remove_edges_from([(u, v, k) for u, v, k, d in graph.edges(keys=True, data=True) if not classes(d.get("highway")) & CLASSES])
    components = list(nx.strongly_connected_components(graph))
    if not components:
        raise RuntimeError("OSM returned no connected Pune driving graph")
    graph = graph.subgraph(max(components, key=len)).copy()
    print(f"Pune road graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} directed edges")
    if graph.number_of_nodes() < 1500:
        raise RuntimeError(f"Pune graph has only {graph.number_of_nodes()} nodes; expected at least 1,500")

    nodes = [{"id": str(n), "lat": d["y"], "lon": d["x"]} for n, d in graph.nodes(data=True)]
    edges = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        raw_class = data.get("highway", "tertiary")
        road_class = raw_class[0] if isinstance(raw_class, list) else raw_class
        speed = speed_for(data.get("maxspeed"), road_class)
        geometry = data.get("geometry")
        coords = [[float(lon), float(lat)] for lon, lat in (geometry.coords if geometry is not None else [(graph.nodes[u]["x"], graph.nodes[u]["y"]), (graph.nodes[v]["x"], graph.nodes[v]["y"])])]
        length = float(data.get("length", 0))
        edges.append({"id": f"{u}:{v}:{key}", "from": str(u), "to": str(v), "length_m": length, "speed_kph": speed, "travel_time_s": length / (speed / 3.6), "road_class": road_class, "geometry": coords})

    pois = []
    found = {"hospital": [], "fire_station": [], "police": []}
    for amenity in found:
        features = ox.features_from_bbox(bbox, tags={"amenity": amenity})
        for osm_id, row in features.iterrows():
            geom = row.geometry
            point = geom if geom.geom_type == "Point" else geom.representative_point()
            name = str(row.get("name", "") or "").strip()
            found[amenity].append((name, str(osm_id[-1]), float(point.y), float(point.x)))
    limits = {"hospital": 10, "fire_station": 6, "police": 10}
    preferred = ("Sassoon", "Ruby Hall", "KEM", "Jehangir", "Deenanath", "Sahyadri", "Noble")
    for kind, items in found.items():
        if kind == "hospital":
            items.sort(key=lambda item: (not any(x.lower() in item[0].lower() for x in preferred), not bool(item[0]), item[0].lower()))
        else:
            items.sort(key=lambda item: (not bool(item[0]), item[0].lower()))
        for name, osm_id, lat, lon in items[:limits[kind]]:
            node, distance = ox.distance.nearest_nodes(graph, lon, lat, return_dist=True)
            if distance > 300:
                continue
            pois.append({"id": f"{kind}:{osm_id}", "kind": kind, "name": name or f"Unnamed {kind.replace('_', ' ')}", "lat": lat, "lon": lon, "node": str(node), "snap_distance_m": float(distance)})
    print("POIs:", {kind: sum(p["kind"] == kind for p in pois) for kind in found})

    data = {"bbox": {"south": south, "north": north, "west": west, "east": east}, "nodes": nodes, "edges": edges, "pois": pois, "attribution": "© OpenStreetMap contributors"}
    out = ROOT / "data" / "pune"
    out.mkdir(parents=True, exist_ok=True)
    (out / "network.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    features = [{"type": "Feature", "id": edge["id"], "properties": {"road_class": edge["road_class"]}, "geometry": {"type": "LineString", "coordinates": edge["geometry"]}} for edge in edges]
    (out / "roads.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")), encoding="utf-8")
    mini_nodes = list(graph.nodes)[:50]
    mini_graph = graph.subgraph(mini_nodes).copy()
    if not nx.is_strongly_connected(mini_graph):
        component = max(nx.strongly_connected_components(mini_graph), key=len)
        mini_graph = graph.subgraph(component).copy()
    mini_ids = {str(n) for n in mini_graph.nodes}
    mini = {**data, "nodes": [n for n in nodes if n["id"] in mini_ids], "edges": [e for e in edges if e["from"] in mini_ids and e["to"] in mini_ids]}
    fixture = ROOT / "backend" / "tests" / "fixtures" / "pune_mini.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(json.dumps(mini, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
