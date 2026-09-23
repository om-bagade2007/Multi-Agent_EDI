"""REST endpoints and live WebSocket run stream."""
import asyncio
import json
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.api.schemas import RunRequest
from app.api.ws import send_snapshot
from app.config import Settings
from app.core.bus import InMemoryBus, RedisStreamsBus
from app.db.repository import Repository
from app.sim.grid_sim import GridSim
from app.sim.manager import SimulationManager
from app.sim.pune_network import BBOX, PuneNetwork
from app.strategies.registry import STRATEGIES

router = APIRouter()
_runs: dict[str, SimulationManager] = {}
_tasks: dict[str, asyncio.Task[dict[str, object]]] = {}
_repo = Repository()
_settings = Settings()


@lru_cache(maxsize=2)
def _load_pune_network(data_dir: str) -> PuneNetwork:
    """Read and validate the selected Pune dataset once per server process."""
    return PuneNetwork(Path(data_dir))


def _pune_network() -> PuneNetwork:
    """Return current Pune network or a descriptive API error."""
    try:
        return _load_pune_network(str(_settings.pune_data_dir.resolve()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=503, detail=f"Pune network data is unavailable: {error}") from error


@router.get("/scenario")
def scenario() -> dict[str, object]:
    """Return default scenario metadata."""
    mode = _settings.simulation_mode.lower()
    return {"name": "Pune" if mode == "pune" else "GridSim", "title": "Pune Emergency Response Simulation" if mode == "pune" else "Emergency Response Simulation", "mode": mode, "bbox": BBOX if mode == "pune" else None, "speeds": [1, 5, 10, 30], "dispatch_strategy": _settings.dispatch_strategy, "incident_rate_per_minute": 2/3, "duration_s": 3600}


@router.get("/scenario/network")
def scenario_network() -> dict[str, object]:
    """Provide the static GridSim road network before a run is started."""
    if _settings.simulation_mode.lower() == "pune":
        network = _pune_network()
        roads_path = network.data_dir / "roads.geojson"
        if roads_path.stat().st_size > 3_000_000:
            raise HTTPException(status_code=503, detail="Pune roads GeoJSON exceeds the 3 MB API limit; rebuild with simplified geometry.")
        return {"mode": "pune", "bbox": network.data["bbox"], "roads": network.roads}
    return GridSim().road_network_snapshot().model_dump(mode="json")


@router.get("/scenario/facilities")
def scenario_facilities() -> list[dict[str, object]]:
    """Return the static health, fire, and police facilities before a run."""
    if _settings.simulation_mode.lower() != "pune":
        return []
    network = _pune_network()
    return [{key: poi[key] for key in ("id", "kind", "name", "lat", "lon")} for poi in network.data["pois"]]


@router.get("/experiments/latest")
def latest_comparison() -> dict[str, object] | None:
    """Return the latest paired comparison, if one was exported."""
    path = Path(__file__).resolve().parents[2] / "experiments" / "results" / "latest_comparison.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@router.get("/runs")
def runs() -> list[dict[str, object]]:
    """List saved simulation runs."""
    return _repo.list_runs()


@router.post("/runs")
async def start_run(request: RunRequest) -> dict[str, str]:
    """Start one live seeded run."""
    strategy_type = STRATEGIES.get(request.strategy or _settings.dispatch_strategy)
    if strategy_type is None:
        raise HTTPException(400, "Unknown strategy")
    if any(not task.done() for task in _tasks.values()):
        raise HTTPException(409, "A live run is already active")
    run_id = str(uuid4())
    event_bus = RedisStreamsBus(_settings.redis_url) if _settings.bus == "redis" else InMemoryBus()
    mode = _settings.simulation_mode.lower()
    if mode == "pune":
        _pune_network()
    manager = SimulationManager(request.seed, request.duration_s, request.incident_rate, event_bus, strategy_type(), simulation_mode=mode, data_dir=_settings.pune_data_dir)
    _runs[run_id] = manager
    async def run() -> dict[str, object]:
        result = await manager.run_episode(realtime=True, speed=request.speed)
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
    return manager.metrics.summary(manager.duration_s, manager.sim.mean_traffic_delay(), manager.resource_counts())


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
