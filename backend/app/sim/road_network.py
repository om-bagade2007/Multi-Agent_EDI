"""Validated, explicit GridSim road-network coordinates for dashboard clients."""
from math import isclose

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GridNode(BaseModel):
    """Intersection in grid-unit coordinates."""
    model_config = ConfigDict(extra='forbid')
    id: str
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class GridEdge(BaseModel):
    """Road segment endpoints in grid units."""
    model_config = ConfigDict(extra='forbid')
    id: str
    from_node: str
    to_node: str
    x1: float = Field(allow_inf_nan=False)
    y1: float = Field(allow_inf_nan=False)
    x2: float = Field(allow_inf_nan=False)
    y2: float = Field(allow_inf_nan=False)
    congestion: float = Field(ge=0, le=1, allow_inf_nan=False)


class GridRoadNetwork(BaseModel):
    """One coordinate system for every intersection and road endpoint."""
    model_config = ConfigDict(extra='forbid')
    size: int = Field(gt=1)
    origin_lat: float = Field(allow_inf_nan=False)
    origin_lon: float = Field(allow_inf_nan=False)
    block_m: float = Field(gt=0, allow_inf_nan=False)
    nodes: list[GridNode]
    edges: list[GridEdge]

    @model_validator(mode='after')
    def validate_edges(self) -> 'GridRoadNetwork':
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError('node identifiers must be unique')
        if any(not (0 <= node.x < self.size and 0 <= node.y < self.size) for node in self.nodes):
            raise ValueError('node coordinates must be inside the grid bounds')
        for edge in self.edges:
            if edge.from_node not in nodes or edge.to_node not in nodes:
                raise ValueError(f'edge {edge.id} references an unknown node')
            start, end = nodes[edge.from_node], nodes[edge.to_node]
            if not (isclose(edge.x1, start.x) and isclose(edge.y1, start.y) and isclose(edge.x2, end.x) and isclose(edge.y2, end.y)):
                raise ValueError(f'edge {edge.id} coordinates do not match endpoint nodes')
        return self
