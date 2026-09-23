"""WebSocket helpers for simulation state streaming."""
from fastapi import WebSocket

from app.api.schemas import PuneCoordinatePayload


async def send_snapshot(socket: WebSocket, manager: object) -> None:
    """Send one dashboard state snapshot."""
    snapshot = {"type": "snapshot", "sim_time": manager.sim.sim_time, "units": [u.model_dump(mode="json") for u in manager.units], "incidents": [i.model_dump(mode="json") for i in manager.incidents], "stations": [s.model_dump(mode="json") for s in manager.stations], "hospitals": [h.model_dump(mode="json") for h in manager.hospitals], "agents": manager.agent_snapshot(), "metrics": manager.dashboard_metrics()}
    if manager.simulation_mode == "pune":
        routes = manager.sim.active_routes()
        points = [entity["location"] for entity in snapshot["units"] + snapshot["incidents"] + snapshot["stations"] + snapshot["hospitals"]]
        points.extend(point.model_dump() for route in routes for point in route["polyline"])
        PuneCoordinatePayload(coordinates=points)
        snapshot["routes"] = [{"unit_id": route["unit_id"], "polyline": [point.model_dump(mode="json") for point in route["polyline"]]} for route in routes]
        snapshot["traffic"] = []
    else:
        snapshot["traffic"] = [edge.model_dump(mode="json") for edge in manager.sim.traffic_snapshot()]
        snapshot["road_network"] = manager.sim.road_network_snapshot().model_dump(mode="json")
    await socket.send_json(snapshot)
