from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence
import sys

try:
    from .animation import storyboard_to_svg
    from .graph_builder import GraphBuilder
    from .utils import slugify
except ImportError:
    PARENT_DIR = Path(__file__).resolve().parent
    if str(PARENT_DIR) not in sys.path:
        sys.path.append(str(PARENT_DIR))
    from animation import storyboard_to_svg
    from graph_builder import GraphBuilder
    from utils import slugify


@dataclass
class LocalStorySettings:
    max_keywords: int = 5
    min_frames: int = 4


class LocalGenerator:
    """Produce offline-friendly animation, graph and narration content."""

    def __init__(self, offline_dir: Path, graph_builder: GraphBuilder | None = None) -> None:
        self._offline_dir = offline_dir
        self.graph_builder = graph_builder or GraphBuilder()
        self.settings = LocalStorySettings()
    
    @property
    def offline_dir(self) -> Path:
        return self._offline_dir
    
    def __dir__(self):
        """隐藏内部Path属性"""
        return ['build_bundle', 'derive_from_online']
    
    def __getstate__(self) -> Dict[str, Any]:
        """防止Path对象被pywebview序列化"""
        return {
            "offline_dir": str(self._offline_dir),
        }

    def build_bundle(
        self,
        topic: str,
        cached_animation: str | None = None,
        cached_graph: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        storyboard = self._build_storyboard(topic)
        graph_data = cached_graph or self._build_graph(topic, storyboard)
        animation_markup = cached_animation or storyboard_to_svg(storyboard)
        narration = self._compose_narration(topic, storyboard)
        return {
            "animation_html": animation_markup,
            "animation_code": animation_markup,
            "graph_data": graph_data,
            "storyboard": storyboard,
            "narration": narration,
            "source": "local",
        }

    def derive_from_online(self, topic: str, graph_data: Dict[str, Any] | None) -> Dict[str, Any]:
        storyboard = self._build_storyboard(topic, graph_data)
        narration = self._compose_narration(topic, storyboard)
        return {
            "storyboard": storyboard,
            "narration": narration,
        }

    def _build_storyboard(
        self,
        topic: str,
        graph_data: Dict[str, Any] | None = None,
    ) -> List[Dict[str, str]]:
        topic = topic.strip() or "主题"
        keywords = self._extract_keywords(topic, graph_data)
        frames: List[Dict[str, str]] = []

        # 分镜1：引入 (Title Scene)
        overview = {
            "heading": topic,
            "body": f"【全景概览】让我们通过可视化的方式，直观理解 {topic} 的核心机制。",
            "narration": f"欢迎来到知识可视化。今天，我们将一起深入探索{topic}的奥秘。"
        }
        frames.append(overview)

        # 分镜2：核心要素 (Fallback if no keywords)
        if not keywords:
            keywords = ["关键概念A", "关键概念B", "关键概念C"]
            
        focus = keywords[: min(self.settings.max_keywords, max(3, len(keywords)))]
        frames.append(
            {
                "heading": "核心要素",
                "body": f"{topic} 主要包含以下关键概念：" + "、".join(focus) + "。这些要素构成了理解的基础。",
                "narration": f"{topic}的核心要素包括：{focus[0]}、{focus[1] if len(focus) > 1 else ''}等关键概念。"
            }
        )

        # 分镜3：关系与机制
        relations = self._derive_relations(keywords)
        if not relations:
             relations = [f"{keywords[0]} 支撑了整体结构", "各要素之间紧密协作"]
             
        frames.append(
            {
                "heading": "工作原理",
                "body": f"这些要素之间存在重要的关联：{relations[0]}。",
                "narration": f"让我们看看这些概念是如何相互关联的。{relations[0]}"
            }
        )

        # 分镜4：实际应用
        frames.append(
            {
                "heading": "实际应用",
                "body": f"{topic} 在实践中有广泛应用。你可以结合具体场景，深入探索各个节点的细节。",
                "narration": f"了解了基本概念后，我们可以将{topic}应用到实际场景中。"
            }
        )

        # 分镜5：总结回顾
        frames.append(
            {
                "heading": "知识回顾",
                "body": f"通过知识图谱和多分镜动画，我们系统地学习了{topic}的要点。继续探索可以获得更深入的理解。",
                "narration": f"今天我们学习了{topic}的核心内容，希望这次可视化学习对你有所帮助。"
            }
        )

        if len(frames) < self.settings.min_frames:
            frames.extend(self._padding_frames(topic, len(frames)))

        return frames

    def _extract_keywords(self, topic: str, graph_data: Dict[str, Any] | None) -> List[str]:
        keywords: List[str] = []
        if isinstance(graph_data, dict):
            nodes = graph_data.get("nodes")
            if isinstance(nodes, Sequence):
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    label = str(node.get("label") or "").strip()
                    if not label or label == topic:
                        continue
                    if label not in keywords:
                        keywords.append(label)
        if not keywords:
            tokens = self._split_topic(topic)
            keywords.extend(tokens[: self.settings.max_keywords])
        return keywords[: self.settings.max_keywords]

    def _split_topic(self, topic: str) -> List[str]:
        cleaned = re.sub(r"[：:，,。；;、\s]+", " ", topic)
        tokens = [token.strip() for token in cleaned.split(" ") if token.strip()]
        if not tokens and topic:
            tokens = list(topic)
        return tokens

    def _derive_relations(self, keywords: Sequence[str]) -> List[str]:
        relations: List[str] = []
        for a, b in itertools.pairwise(keywords):
            relations.append(f"{a} 与 {b} 之间存在互相支撑的关系")
        return relations[:3]

    def _padding_frames(self, topic: str, existing: int) -> List[Dict[str, str]]:
        extras: List[Dict[str, str]] = []
        templates = [
            {
                "heading": "知识延展",
                "body": f"围绕 {topic} 查找跨学科的参考资料，可以丰富图谱的上下游节点。",
            },
            {
                "heading": "行动建议",
                "body": "挑一个节点作为起点，将其拆解为问题、解决方案和证据，能更快沉淀成报告。",
            },
        ]
        needed = max(0, self.settings.min_frames - existing)
        for item in templates:
            if len(extras) >= needed:
                break
            extras.append(item)
        return extras

    def _build_graph(self, topic: str, storyboard: Iterable[Dict[str, str]]) -> Dict[str, Any]:
        # 获取默认图谱结构作为基础
        default_graph = self.graph_builder.default_graph(topic)
        nodes = default_graph["nodes"].copy()
        edges = default_graph["edges"].copy()
        
        # 从故事板中提取关键词，丰富图谱内容
        keywords = []
        for frame in storyboard:
            if "body" in frame:
                body_text = frame["body"]
                # 简单提取关键词
                words = re.findall(r'[\u4e00-\u9fa5]+', body_text)  # 匹配中文字符
                keywords.extend([word for word in words if len(word) > 1 and word != topic])
        
        # 去重并取前几个关键词
        unique_keywords = list(dict.fromkeys(keywords))[:8]
        
        # 添加关键词节点
        keyword_group = 5
        for i, keyword in enumerate(unique_keywords):
            node_id = f"keyword_{i+1}"
            # 确保节点ID唯一
            suffix = 1
            original_id = node_id
            while any(node["id"] == node_id for node in nodes):
                node_id = f"{original_id}_{suffix}"
                suffix += 1
            
            nodes.append({
                "id": node_id,
                "label": keyword,
                "group": keyword_group,
                "color": "#8B5CF6"
            })
            
            # 随机连接到主题或核心节点
            if i % 2 == 0:
                edges.append({"from": "topic", "to": node_id, "label": "包含"})
            else:
                # 随机选择一个核心节点连接
                core_nodes = [node["id"] for node in nodes if node["id"] in ["concept", "application", "extension"]]
                if core_nodes:
                    target_node = core_nodes[i % len(core_nodes)]
                    edges.append({"from": target_node, "to": node_id, "label": "相关"})
        
        return {"nodes": nodes, "edges": edges}

    def _compose_narration(self, topic: str, storyboard: Sequence[Dict[str, str]]) -> str:
        segments: List[str] = []
        intro = f"现在带你快速浏览 {topic} 的知识图景。"
        segments.append(intro)
        for frame in storyboard:
            heading = frame.get("heading") or "要点"
            body = frame.get("body") or ""
            sentence = f"【{heading}】{body}"
            segments.append(sentence)
        outro = "以上内容可以作为进一步拓展的起点，欢迎继续探索。"
        segments.append(outro)
        return "\n".join(segments)
