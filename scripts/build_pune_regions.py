"""Download and cache named places, water features, and parks for Pune."""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from typing import Any

from build_pune_network import BBOX, DATA_DIR, MIRRORS

QUERY = f"""[out:json][timeout:45];(node[place~\"^(suburb|neighbourhood|quarter)$\"]({BBOX[0]},{BBOX[2]},{BBOX[1]},{BBOX[3]});way[place~\"^(suburb|neighbourhood|quarter)$\"]({BBOX[0]},{BBOX[2]},{BBOX[1]},{BBOX[3]});way[natural=water]({BBOX[0]},{BBOX[2]},{BBOX[1]},{BBOX[3]});way[waterway~\"^(river|stream)$\"]({BBOX[0]},{BBOX[2]},{BBOX[1]},{BBOX[3]});way[leisure~\"^(park|garden)$\"]({BBOX[0]},{BBOX[2]},{BBOX[1]},{BBOX[3]}););out center geom;"""
OUTPUT = DATA_DIR / "regions.geojson"


def query_overpass() -> list[dict[str, Any]]:
    """Fetch from the same Overpass endpoints as the road network builder."""
    failures: list[str] = []
    for endpoint in MIRRORS:
        for attempt in range(2):
            try:
                body = urllib.parse.urlencode({"data": QUERY}).encode()
                request = urllib.request.Request(endpoint + "/interpreter", data=body, headers={"User-Agent": "UrbanEmergencySimulation/1.0"})
                with urllib.request.urlopen(request, timeout=55) as response:
                    return json.loads(response.read())["elements"]
            except Exception as error:  # noqa: BLE001 - try each configured public mirror
                failures.append(f"{endpoint} attempt {attempt + 1}: {error}")
                if attempt == 0:
                    time.sleep(1)
    raise RuntimeError("Could not download Pune region data. " + " | ".join(failures))


def as_geojson(elements: list[dict[str, Any]]) -> dict[str, object]:
    """Convert Overpass geometry directly to GeoJSON features, skipping bad geometry."""
    features: list[dict[str, object]] = []
    for element in elements:
        tags = element.get("tags", {})
        place, name = tags.get("place"), tags.get("name")
        if place in {"suburb", "neighbourhood", "quarter"} and name:
            center = element if element.get("type") == "node" else element.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                features.append({"type": "Feature", "id": f"place-{element['id']}", "properties": {"name": name, "kind": place}, "geometry": {"type": "Point", "coordinates": [lon, lat]}})
            continue
        waterway = tags.get("waterway") in {"river", "stream"}
        park = tags.get("leisure") in {"park", "garden"}
        water = tags.get("natural") == "water"
        if not (waterway or park or water):
            continue
        geometry = element.get("geometry", [])
        coords = [[point["lon"], point["lat"]] for point in geometry if isinstance(point.get("lon"), (int, float)) and isinstance(point.get("lat"), (int, float))]
        if len(coords) < 2:
            continue
        polygon = (park or water) and coords[0] == coords[-1] and len(coords) >= 4
        shape = {"type": "Polygon", "coordinates": [coords]} if polygon else {"type": "LineString", "coordinates": coords}
        features.append({"type": "Feature", "id": f"osm-{element['type']}-{element['id']}", "properties": {"name": name or "", "kind": "park" if park else "water"}, "geometry": shape})
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.is_file() and not args.force:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if data.get("type") == "FeatureCollection" and isinstance(data.get("features"), list):
            print(f"Using committed Pune region data: {len(data['features'])} features")
            return
    cache = DATA_DIR / "cache" / "regions.geojson"
    try:
        result = as_geojson(query_overpass())
        if result["features"]:
            cache.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    except (RuntimeError, OSError, json.JSONDecodeError) as error:
        if not cache.is_file():
            raise SystemExit(str(error)) from error
        result = json.loads(cache.read_text(encoding="utf-8"))
        print(f"Using cached Pune region data after Overpass failure: {error}")
    encoded = json.dumps(result, separators=(",", ":"))
    if len(encoded.encode("utf-8")) >= 1_500_000:
        raise SystemExit("Pune regions GeoJSON exceeds 1.5 MB; simplify geometry before committing.")
    OUTPUT.write_text(encoded, encoding="utf-8")
    print(f"Wrote {len(result['features'])} OSM region features to {OUTPUT} ({len(encoded):,} bytes)")


if __name__ == "__main__":
    main()
