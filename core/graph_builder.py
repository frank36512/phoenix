from __future__ import annotations

from typing import Any, Dict, List


class GraphBuilder:
    def __init__(self) -> None:
        self._fallback_edges = [
            {"from": "topic", "to": "concept", "label": "涵盖"},
            {"from": "topic", "to": "application", "label": "应用"},
            {"from": "topic", "to": "extension", "label": "延伸"},
        ]

    def default_graph(self, topic: str) -> Dict[str, Any]:
        return {
            "nodes": [
                {"id": "topic", "label": topic, "group": 1, "color": "#4F46E5"},
                {"id": "concept", "label": "核心概念", "group": 2, "color": "#818CF8"},
                {"id": "application", "label": "实践场景", "group": 3, "color": "#A5B4FC"},
                {"id": "extension", "label": "延伸知识", "group": 4, "color": "#C7D2FE"},
            ],
            "edges": list(self._fallback_edges),
        }

    def normalise(self, payload: Dict[str, Any], topic: str) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        raw_nodes = payload.get("nodes")
        if isinstance(raw_nodes, list):
            for index, item in enumerate(raw_nodes):
                if not isinstance(item, dict):
                    continue
                node_id = str(item.get("id") or index + 1)
                label = str(item.get("label") or (topic if index == 0 else f"节点{index+1}"))[:20]
                group = int(item.get("group") or (1 if index == 0 else 2))
                node = {
                    "id": node_id,
                    "label": label,
                    "group": group,
                }
                if "color" in item:
                    node["color"] = item["color"]
                nodes.append(node)

        edges: List[Dict[str, Any]] = []
        raw_edges = payload.get("edges")
        if isinstance(raw_edges, list):
            for item in raw_edges:
                if not isinstance(item, dict):
                    continue
                source = item.get("from")
                target = item.get("to")
                if not source or not target:
                    continue
                label = str(item.get("label") or "关联")[:12]
                edges.append({"from": str(source), "to": str(target), "label": label})

        if not nodes or not edges:
            default_graph = self.default_graph(topic)
            if not nodes:
                nodes = default_graph["nodes"]
            if not edges:
                edges = default_graph["edges"]

        return {"nodes": nodes, "edges": edges}
