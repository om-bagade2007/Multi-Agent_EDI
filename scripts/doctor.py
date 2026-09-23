"""Print a compact local demo readiness report."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings  # noqa: E402


def port_open(port: int) -> bool:
    """Return whether a local TCP listener currently owns the port."""
    with socket.socket() as client:
        client.settimeout(.25)
        return client.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    settings = Settings()
    root = settings.pune_data_dir
    print(f"Backend mode: {settings.simulation_mode}")
    for name in ("network.json", "roads.geojson"):
        path = root / name
        print(f"{name}: {'present' if path.is_file() else 'MISSING'} ({path})")
    fixture = ROOT / "backend/tests/fixtures/pune_mini.json"
    print(f"pune_mini.json: {'present' if fixture.is_file() else 'MISSING'}")
    if (root / "network.json").is_file():
        try:
            from app.sim.pune_network import PuneNetwork
            network = PuneNetwork(root)
            print(f"Network: {network.graph.number_of_nodes()} nodes, {network.graph.number_of_edges()} directed edges")
            counts = {kind: sum(poi["kind"] == kind for poi in network.data["pois"]) for kind in ("hospital", "fire_station", "police")}
            print(f"Facilities: {counts}")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"Network validation: ERROR ({error})")
    print(f"Frontend mode: {os.getenv('VITE_SIMULATION_MODE', 'pune')}")
    for port in (8000, 5173):
        print(f"Port {port}: {'in use' if port_open(port) else 'available'}")


if __name__ == "__main__":
    main()
