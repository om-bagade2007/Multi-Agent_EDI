"""WebSocket helpers for simulation state streaming."""
from fastapi import WebSocket


async def send_snapshot(socket: WebSocket, manager: object) -> None:
    """Send one dashboard state snapshot."""
    await socket.send_json({"type": "snapshot", "sim_time": manager.sim.sim_time, "units": [u.model_dump(mode="json") for u in manager.units], "incidents": [i.model_dump(mode="json") for i in manager.incidents], "hospitals": [h.model_dump(mode="json") for h in manager.hospitals], "traffic": [e.model_dump(mode="json") for e in manager.sim.traffic_snapshot()], "metrics": manager.metrics.snapshot(manager.sim.sim_time, manager.sim.mean_traffic_delay())})
