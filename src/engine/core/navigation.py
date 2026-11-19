import heapq
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class NavNode:
    id: str
    position: Tuple[float, float, float]


class NavMesh:
    def __init__(self):
        self.nodes: Dict[str, NavNode] = {}
        self.edges: Dict[str, Dict[str, float]] = {}

    def add_node(self, node: NavNode):
        self.nodes[node.id] = node
        self.edges.setdefault(node.id, {})

    def add_edge(self, first: str, second: str, cost: Optional[float] = None):
        if first not in self.nodes or second not in self.nodes:
            raise KeyError("Both navigation nodes must exist")
        if cost is None:
            a = self.nodes[first].position
            b = self.nodes[second].position
            cost = math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))
        self.edges[first][second] = cost
        self.edges.setdefault(second, {})[first] = cost

    def find_path(self, start: str, goal: str) -> List[str]:
        if start not in self.nodes or goal not in self.nodes:
            return []
        queue = [(0.0, start)]
        distances = {start: 0.0}
        previous = {}
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances[node]:
                continue
            if node == goal:
                break
            for neighbor, cost in self.edges.get(node, {}).items():
                candidate = distance + cost
                if candidate < distances.get(neighbor, float("inf")):
                    distances[neighbor] = candidate
                    previous[neighbor] = node
                    heapq.heappush(queue, (candidate, neighbor))
        if goal not in distances:
            return []
        path = [goal]
        while path[-1] != start:
            path.append(previous[path[-1]])
        path.reverse()
        return path
