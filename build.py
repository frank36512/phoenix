from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

# BASE_DIR is e:\knowledge_visualization\knowledgesight
BASE_DIR = Path(__file__).parent
DIST = BASE_DIR / "dist"
BUILD = BASE_DIR / "build"
SPEC = BASE_DIR / "Phoenix.spec"

def clean() -> None:
    for target in (DIST, BUILD, SPEC):
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

def build() -> None:
    clean()
    
    # Resources paths
    static_dir = (BASE_DIR / "resources" / "static").resolve()
    templates_dir = (BASE_DIR / "resources" / "templates").resolve()
    maps_dir = (BASE_DIR / "resources" / "maps").resolve()
    prompts_dir = (BASE_DIR / "llm" / "prompts").resolve()
    offline_dir = (BASE_DIR / "resources" / "offline").resolve()
    credentials_file = (BASE_DIR / "credentials.json").resolve()
    
    # Icon path: e:\knowledge_visualization\vslogo.ico
    # BASE_DIR is e:\knowledge_visualization
    icon_path = (BASE_DIR / "vslogo.ico").resolve()
    
    print(f"Start building...")
    print(f"Icon path: {icon_path}")
    
    params = [
        str(BASE_DIR / "main.py"),  # Entry point
        "--name=Phoenix",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        
        # Add data: source_path;dest_path
        f"--add-data={static_dir}{os.pathsep}resources/static",
        f"--add-data={templates_dir}{os.pathsep}resources/templates",
        f"--add-data={maps_dir}{os.pathsep}resources/maps",
        f"--add-data={prompts_dir}{os.pathsep}llm/prompts",
        f"--add-data={credentials_file}{os.pathsep}.",  # Put credentials in root of bundle
        f"--add-data={offline_dir}{os.pathsep}resources/offline",
        f"--add-data={icon_path}{os.pathsep}static", # Add icon to static folder in bundle
        
        # Hidden imports to ensure PyInstaller finds them
        "--hidden-import=llm.client",
        "--hidden-import=core.orchestrator",
        "--hidden-import=core.animation",
        "--hidden-import=core.graph_builder",
        "--hidden-import=core.media",
        "--hidden-import=core.utils",
        "--hidden-import=core.video_renderer",
        "--hidden-import=storage.cache",
        
        # PyQt6 specific hidden imports if needed (usually auto-detected, but good to be safe)
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtWebEngineWidgets",
        "--hidden-import=PyQt6.QtWebEngineCore",
        
        # Exclude unnecessary web frameworks if we are strictly PyQt
        "--exclude-module=uvicorn",
        "--exclude-module=fastapi",
        "--exclude-module=starlette",
    ]

    if icon_path.exists():
        params.append(f"--icon={icon_path}")
    else:
        print(f"Warning: Icon not found at {icon_path}")

    PyInstaller.__main__.run(params)
    print("打包完成，文件位于 dist/ 目录。")

if __name__ == "__main__":
    build()
