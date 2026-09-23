"""A* shortest path over a weighted graph."""
from collections.abc import Callable, Hashable, Iterable
from heapq import heappop, heappush
from typing import TypeVar

Node = TypeVar('Node', bound=Hashable)

def astar(start: Node, goal: Node, neighbors: Callable[[Node], Iterable[tuple[Node, float]]], heuristic: Callable[[Node, Node], float]) -> tuple[list[Node], float]:
    """Return a minimum-cost path and cost, using an admissible heuristic."""
    queue: list[tuple[float, float, Node]] = [(heuristic(start, goal), 0.0, start)]
    came_from: dict[Node, Node] = {}
    scores: dict[Node, float] = {start: 0.0}
    while queue:
        _, cost, node = heappop(queue)
        if cost != scores.get(node):
            continue
        if node == goal:
            path = [node]
            while node in came_from:
                node = came_from[node]
                path.append(node)
            return list(reversed(path)), cost
        for adjacent, weight in neighbors(node):
            candidate = cost + weight
            if candidate < scores.get(adjacent, float('inf')):
                came_from[adjacent] = node
                scores[adjacent] = candidate
                heappush(queue, (candidate + heuristic(adjacent, goal), candidate, adjacent))
    raise ValueError(f'No route from {start!r} to {goal!r}')
