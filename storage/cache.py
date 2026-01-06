from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import sys

try:
    from ..core.utils import ensure_dir, read_json, slugify, write_json, write_text
except ImportError:
    # 支持打包后的执行
    PARENT_DIR = Path(__file__).resolve().parent.parent
    if str(PARENT_DIR) not in sys.path:
        sys.path.append(str(PARENT_DIR))
    from core.utils import ensure_dir, read_json, slugify, write_json, write_text


class ResourceCache:
    def __init__(self, base_dir: Path) -> None:
        self._base = ensure_dir(base_dir)
        self._animations = ensure_dir(self._base / "animations")
        self._graphs = ensure_dir(self._base / "graphs")
    
    @property
    def base(self) -> Path:
        return self._base
    
    @property
    def animations(self) -> Path:
        return self._animations
    
    @property
    def graphs(self) -> Path:
        return self._graphs
    
    def __dir__(self):
        """隐藏内部Path属性，防止pywebview序列化"""
        return ['animation_path', 'graph_path', 'load_animation', 'save_animation', 'load_graph', 'save_graph']
    
    def __getstate__(self) -> Dict[str, Any]:
        """防止Path对象被pywebview序列化"""
        return {
            "base_dir": str(self._base),
            "animations_dir": str(self._animations),
            "graphs_dir": str(self._graphs),
        }

    def animation_path(self, topic: str) -> Path:
        return self.animations / f"{slugify(topic)}.html"

    def graph_path(self, topic: str) -> Path:
        return self.graphs / f"{slugify(topic)}.json"

    def load_animation(self, topic: str) -> Optional[str]:
        path = self.animation_path(topic)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def save_animation(self, topic: str, markup: str) -> None:
        write_text(self.animation_path(topic), markup)

    def load_graph(self, topic: str) -> Optional[Dict[str, Any]]:
        path = self.graph_path(topic)
        if not path.exists():
            return None
        try:
            data = read_json(path)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def save_graph(self, topic: str, payload: Dict[str, Any]) -> None:
        write_json(self.graph_path(topic), payload)
