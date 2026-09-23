"""Optional TraCI backend interface; runtime requires SUMO and SUMO_HOME."""
from app.core.models import LatLon
from app.sim.grid_sim import GridSim


class SumoBackend(GridSim):
    """Best-effort SUMO adapter boundary; raises clearly when SUMO is unavailable."""
    def __init__(self, *args: object, **kwargs: object) -> None:
        """Check TraCI availability before constructing the optional backend."""
        try:
            import traci  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("SUMO backend requires SUMO_HOME and TraCI") from exc
        super().__init__(*args, **kwargs)

    def dispatch_unit(self, unit_id: str, dest: LatLon, *, emergency: bool) -> None:
        """SUMO adapter currently shares deterministic routing pending a net file."""
        super().dispatch_unit(unit_id, dest, emergency=emergency)
