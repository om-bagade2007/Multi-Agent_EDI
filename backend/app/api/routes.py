"""REST endpoints and live WebSocket run stream."""
import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.api.schemas import RunRequest
from app.api.ws import send_snapshot
from app.core.bus import InMemoryBus
from app.db.repository import Repository
from app.sim.manager import SimulationManager

router = APIRouter()
_runs: dict[str, SimulationManager] = {}
_tasks: dict[str, asyncio.Task[dict[str, object]]] = {}
_repo = Repository()


@router.get("/scenario")
def scenario() -> dict[str, object]:
    """Return default scenario metadata."""
    return {"name": "Pune grid", "grid_size": 8, "incident_rate_per_minute": 2/3, "duration_s": 3600}


@router.get("/runs")
def runs() -> list[dict[str, object]]:
    """List saved simulation runs."""
    return _repo.list_runs()


@router.post("/runs")
async def start_run(request: RunRequest) -> dict[str, str]:
    """Start one live seeded run."""
    if request.strategy != "nearest":
        raise HTTPException(400, "Unknown strategy")
    if any(not task.done() for task in _tasks.values()):
        raise HTTPException(409, "A live run is already active")
    run_id = str(uuid4())
    manager = SimulationManager(request.seed, request.duration_s, request.incident_rate, InMemoryBus())
    _runs[run_id] = manager
    async def run() -> dict[str, object]:
        result = await manager.run_episode(realtime=True)
        _repo.save(result, run_id)
        return result
    _tasks[run_id] = asyncio.create_task(run())
    return {"id": run_id, "status": "running"}


@router.post("/runs/{run_id}/{action}")
def control_run(run_id: str, action: str) -> dict[str, str]:
    """Pause, resume or stop a live run."""
    manager = _runs.get(run_id)
    if manager is None:
        raise HTTPException(404, "Run not found")
    if action == "pause":
        manager.paused = True
    elif action == "resume":
        manager.paused = False
    elif action == "stop":
        manager.stopped = True
    else:
        raise HTTPException(404, "Unknown action")
    return {"id": run_id, "status": action}


@router.get("/runs/{run_id}/metrics")
def metrics(run_id: str) -> dict[str, object]:
    """Return current or completed run metrics."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    manager = _runs[run_id]
    return manager.metrics.summary(manager.duration_s, manager.sim.mean_traffic_delay(), {"ambulance": 4, "fire": 3, "police": 3})


@router.get("/runs/{run_id}/decisions")
def decisions(run_id: str) -> list[dict[str, object]]:
    """Return run decisions."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    return _runs[run_id].decisions


@router.websocket("/ws/runs/{run_id}")
async def run_socket(socket: WebSocket, run_id: str) -> None:
    """Stream snapshots and newly logged decisions to the dashboard."""
    await socket.accept()
    manager = _runs.get(run_id)
    if manager is None:
        await socket.close(code=4404)
        return
    sent = 0
    try:
        while run_id in _tasks and not _tasks[run_id].done():
            await send_snapshot(socket, manager)
            for decision in manager.decisions[sent:]:
                await socket.send_json({"type": "decision", **decision})
            sent = len(manager.decisions)
            await asyncio.sleep(.5)
        for decision in manager.decisions[sent:]:
            await socket.send_json({"type": "decision", **decision})
        await send_snapshot(socket, manager)
    except WebSocketDisconnect:
        return
