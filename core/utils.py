from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Union

_SAFE_NAME = re.compile(r"[^0-9A-Za-z\u4e00-\u9fa5\-_]+")


def slugify(label: str, fallback: str = "topic") -> str:
    if not label:
        return fallback
    cleaned = _SAFE_NAME.sub("_", label).strip("._")
    return cleaned or fallback


def ensure_dir(path: Union[str, Path]) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_text(destination: Union[str, Path], payload: str) -> None:
    target = Path(destination)
    ensure_dir(target.parent)
    target.write_text(payload, encoding="utf-8")


def write_json(destination: Union[str, Path], payload: Any) -> None:
    target = Path(destination)
    ensure_dir(target.parent)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(source: Union[str, Path]) -> Any:
    path = Path(source)
    return json.loads(path.read_text(encoding="utf-8"))
