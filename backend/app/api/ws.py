"""WebSocket helpers for simulation state streaming."""
from fastapi import WebSocket


async def send_snapshot(socket: WebSocket, manager: object) -> None:
    """Send one dashboard state snapshot."""
    await socket.send_json({"type": "snapshot", "sim_time": manager.sim.sim_time, "units": [u.model_dump(mode="json") for u in manager.units], "incidents": [i.model_dump(mode="json") for i in manager.incidents], "stations": [s.model_dump(mode="json") for s in manager.stations], "hospitals": [h.model_dump(mode="json") for h in manager.hospitals], "agents": manager.agent_snapshot(), "traffic": [e.model_dump(mode="json") for e in manager.sim.traffic_snapshot()], "road_network": manager.sim.road_network_snapshot().model_dump(mode="json"), "metrics": manager.dashboard_metrics()})
