"""Global assignment must beat sequential nearest on shared demand."""
import numpy as np

from app.core.models import AgentKind, Incident, IncidentType, Unit
from app.sim.grid_sim import GridSim
from app.strategies.hungarian import HungarianStrategy
from app.strategies.nearest import NearestStrategy


def test_hungarian_beats_nearest_for_three_simultaneous_incidents() -> None:
    sim = GridSim(size=10, block_m=250)
    sim.reset({}, np.random.default_rng(32))
    sim.noise = {str(edge['id']): 1.0 for _, _, edge in sim.graph.edges(data=True)}
    units = [Unit(id=f'A{i}', kind=AgentKind.ambulance, station_id='S', location=sim._coordinate((0, col))) for i, col in enumerate((0, 4, 8))]
    incidents = [Incident(id=f'I{i}', type=IncidentType.medical, severity=2, location=sim._coordinate((0, col)), created_at=0, requires={AgentKind.ambulance}) for i, col in enumerate((2, 0, 8))]
    nearest = NearestStrategy().select_batch(incidents, units, sim)
    optimized = HungarianStrategy().select_batch(incidents, units, sim)
    assert sum(item.eta_s for item in optimized) < sum(item.eta_s for item in nearest)
