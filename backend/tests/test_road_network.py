"""GridSim road snapshots are explicit, finite, and topologically connected."""
import math

import numpy as np
import pytest
from pydantic import ValidationError

from app.sim.grid_sim import GridSim
from app.sim.road_network import GridRoadNetwork


def test_seed_one_network_has_valid_grid_coordinates() -> None:
    sim = GridSim()
    sim.reset({}, np.random.default_rng(1))
    network = sim.road_network_snapshot()
    assert len(network.nodes) == 64
    assert len(network.edges) == 112
    node_ids = {node.id for node in network.nodes}
    assert all(math.isfinite(node.x) and math.isfinite(node.y) for node in network.nodes)
    assert all(edge.from_node in node_ids and edge.to_node in node_ids for edge in network.edges)
    assert all(math.isfinite(coord) for edge in network.edges for coord in (edge.x1, edge.y1, edge.x2, edge.y2))


def test_network_schema_rejects_nonfinite_and_unknown_endpoint() -> None:
    sim = GridSim(size=2)
    payload = sim.road_network_snapshot().model_dump()
    payload['edges'][0]['x1'] = float('nan')
    with pytest.raises(ValidationError):
        GridRoadNetwork.model_validate(payload)
    payload = sim.road_network_snapshot().model_dump()
    payload['edges'][0]['from_node'] = 'missing'
    with pytest.raises(ValidationError, match='unknown node'):
        GridRoadNetwork.model_validate(payload)
