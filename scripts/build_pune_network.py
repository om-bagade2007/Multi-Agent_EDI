"""Download, simplify, validate, and serialize the Pune OSM driving network."""
from __future__ import annotations

import json
import math
import argparse
import gzip
from pathlib import Path
import sys
import shutil

import networkx as nx

BBOX = (18.47, 18.58, 73.79, 73.93)  # south, north, west, east
CLASSES = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"}
DEFAULT_SPEED = {"motorway": 80, "trunk": 60, "primary": 40, "secondary": 30, "tertiary": 25}
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "pune"
MIRRORS = ("https://overpass-api.de/api", "https://overpass.kumi.systems/api", "https://overpass.private.coffee/api")


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


def distance_m(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    """Return haversine distance without optional scikit-learn dependencies."""
    radius = 6_371_000
    lat1, lat2 = math.radians(lat_a), math.radians(lat_b)
    dlat, dlon = lat2 - lat1, math.radians(lon_b - lon_a)
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(arc))


def graph_from_osm(bbox: tuple[float, float, float, float], ox) -> nx.MultiDiGraph:
    """Try the primary Overpass endpoint and mirrors, then an OSMnx extract cache."""
    cache = DATA_DIR / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    ox.settings.cache_folder = str(cache)
    ox.settings.use_cache = True
    ox.settings.overpass_rate_limit = False
    ox.settings.requests_timeout = 45
    failures = []
    for endpoint in MIRRORS:
        try:
            ox.settings.overpass_url = endpoint
            graph = ox.graph_from_bbox(bbox, network_type="drive", simplify=True, retain_all=True)
            graph_path = cache / "pune_drive.graphml"
            ox.save_graphml(graph, filepath=graph_path)
            return graph
        except Exception as error:  # noqa: BLE001 - retry each mirror for every Overpass failure
            failures.append(f"{endpoint}: {error}")
    cached = cache / "pune_drive.graphml.gz"
    if cached.exists():
        print(f"Overpass endpoints failed; using cached extract {cached}")
        return ox.load_graphml(cached)
    raise RuntimeError("Could not download the Pune OSM road network and no cached extract exists. " + " | ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild from OSM even when committed network outputs validate")
    args = parser.parse_args()
    fixture_path = ROOT / "backend" / "tests" / "fixtures" / "pune_mini.json"
    if not args.force and (DATA_DIR / "network.json").exists() and (DATA_DIR / "roads.geojson").exists() and fixture_path.exists():
        sys.path.insert(0, str(ROOT / "backend"))
        try:
            from app.sim.pune_network import PuneNetwork
            verified = PuneNetwork(DATA_DIR)
            print(f"Using committed Pune OSM data: {verified.graph.number_of_nodes()} nodes, {verified.graph.number_of_edges()} directed edges, {len(verified.data['pois'])} facilities.")
            return
        except (ImportError, OSError, ValueError, KeyError, TypeError) as error:
            print(f"Existing Pune outputs are incomplete or invalid; rebuilding: {error}")
    try:
        import osmnx as ox
    except ImportError as error:
        raise SystemExit("Pune data needs rebuilding, but OSMnx is not installed. Run `python -m pip install -e 'backend[dev]'` first.") from error
    south, north, west, east = BBOX
    bbox = (west, south, east, north)
    graph = graph_from_osm(bbox, ox)
    raw_cache = DATA_DIR / "cache" / "pune_drive.graphml"
    compact_cache = DATA_DIR / "cache" / "pune_drive.graphml.gz"
    if raw_cache.exists():
        with raw_cache.open("rb") as source, gzip.open(compact_cache, "wb", compresslevel=9) as target:
            shutil.copyfileobj(source, target)
        raw_cache.unlink()
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
        features = None
        errors = []
        for endpoint in MIRRORS:
            try:
                ox.settings.overpass_url = endpoint
                features = ox.features_from_bbox(bbox, tags={"amenity": amenity})
                break
            except Exception as error:
                errors.append(str(error))
        if features is None:
            print(f"OSM facility query unavailable for {amenity}; will add disclosed simulation facilities only if below minimum. {' | '.join(errors)}")
            continue
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
            node, distance = min(((node, distance_m(lon, lat, attrs["x"], attrs["y"])) for node, attrs in graph.nodes(data=True)), key=lambda result: result[1])
            if distance > 300:
                continue
            pois.append({"id": f"{kind}:{osm_id}", "kind": kind, "name": name or f"Unnamed {kind.replace('_', ' ')}", "lat": lat, "lon": lon, "node": str(node), "snap_distance_m": float(distance)})
    for kind, minimum in {"hospital": 3, "fire_station": 2, "police": 3}.items():
        synthetic = {
            "hospital": [("Synthetic Sassoon General", 18.5289, 73.8744), ("Synthetic KEM Hospital", 18.5039, 73.8602), ("Synthetic Jehangir Hospital", 18.5297, 73.8750)],
            "fire_station": [("Synthetic Shivajinagar Fire Station", 18.5308, 73.8475), ("Synthetic Hadapsar Fire Station", 18.5018, 73.9270)],
            "police": [("Synthetic Shivajinagar Police Station", 18.5314, 73.8478), ("Synthetic Deccan Police Station", 18.5158, 73.8412), ("Synthetic Swargate Police Station", 18.5018, 73.8636)],
        }[kind]
        existing = sum(poi["kind"] == kind for poi in pois)
        for index, (name, lat, lon) in enumerate(synthetic[:max(0, minimum - existing)]):
            node, snap_distance = min(((node, distance_m(lon, lat, attrs["x"], attrs["y"])) for node, attrs in graph.nodes(data=True)), key=lambda result: result[1])
            if snap_distance <= 300:
                pois.append({"id": f"synthetic:{kind}:{index + 1}", "kind": kind, "name": name, "lat": lat, "lon": lon, "node": str(node), "snap_distance_m": snap_distance, "synthetic": True})
                print(f"Added disclosed synthetic facility at Pune landmark: {name} (snap {snap_distance:.0f} m)")
    print("POIs:", {kind: sum(p["kind"] == kind for p in pois) for kind in found})

    data = {"bbox": {"south": south, "north": north, "west": west, "east": east}, "nodes": nodes, "edges": edges, "pois": pois, "attribution": "© OpenStreetMap contributors"}
    out = DATA_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "network.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    features = [{"type": "Feature", "id": edge["id"], "properties": {"road_class": edge["road_class"]}, "geometry": {"type": "LineString", "coordinates": edge["geometry"]}} for edge in edges]
    (out / "roads.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")), encoding="utf-8")
    undirected = graph.to_undirected()
    mini_nodes = []
    queue = [next(iter(graph.nodes))]
    seen = set(queue)
    while queue and len(mini_nodes) < 50:
        node = queue.pop(0)
        mini_nodes.append(node)
        for adjacent in undirected.neighbors(node):
            if adjacent not in seen:
                seen.add(adjacent)
                queue.append(adjacent)
    mini_graph = graph.subgraph(mini_nodes).copy()
    if not nx.is_strongly_connected(mini_graph):
        component = max(nx.strongly_connected_components(mini_graph), key=len)
        mini_graph = graph.subgraph(component).copy()
    mini_ids = {str(n) for n in mini_graph.nodes}
    mini = {**data, "nodes": [n for n in nodes if n["id"] in mini_ids], "edges": [e for e in edges if e["from"] in mini_ids and e["to"] in mini_ids], "pois": [poi for poi in pois if poi["node"] in mini_ids]}
    fixture = ROOT / "backend" / "tests" / "fixtures" / "pune_mini.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(json.dumps(mini, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
