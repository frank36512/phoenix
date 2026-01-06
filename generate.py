"""
KnowledgeSight - Local Generation Tool
This script allows generating animations and other visualizations locally,
with options for both online (AI-powered) and offline (Template-based) modes.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from core.orchestrator import VisualizationOrchestrator
    from core.utils import ensure_dir
    from llm.client import LLMClient
except ImportError:
    print("Error: Could not import core modules. Make sure you are in the knowledgesight directory.")
    sys.exit(1)

async def main():
    parser = argparse.ArgumentParser(description="KnowledgeSight Local Generator")
    parser.add_argument("topic", help="The topic to generate content for")
    parser.add_argument("--mode", choices=["online", "offline"], default="online", 
                        help="Generation mode (online=AI, offline=Template)")
    parser.add_argument("--type", choices=["animation", "mindmap", "bar_race", "geo_map"], 
                        default="animation", help="Type of content to generate")
    parser.add_argument("--output", default="output", help="Directory to save output files")
    parser.add_argument("--language", default="zh", choices=["zh", "en"], help="Language (zh/en)")
    
    args = parser.parse_args()
    
    # Setup directories
    base_dir = Path(__file__).parent
    resource_dir = base_dir / "resources"
    offline_dir = resource_dir / "offline"
    output_dir = Path(args.output)
    ensure_dir(output_dir)
    
    # Initialize Orchestrator
    orchestrator = VisualizationOrchestrator(
        resource_dir / "templates",
        offline_dir
    )
    
    print(f"=== 小凤知识可视化系统 (Phoenix) Generator ===")
    print(f"Topic: {args.topic}")
    print(f"Mode: {args.mode}")
    print(f"Type: {args.type}")
    print(f"Language: {args.language}")
    print("================================")
    
    # Load credentials if needed
    client = None
    if args.mode == "online":
        config_path = Path.home() / ".knowledgesight" / "credentials.json"
        local_config = base_dir / "credentials.json"
        
        if local_config.exists():
            config_path = local_config
            
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            client = LLMClient(config)
            if not client.is_online:
                print("Warning: LLM Client reported offline. Switching to offline mode might be better.")
        else:
            print("Error: credentials.json not found. Cannot run in online mode.")
            print("Please create credentials.json or use --mode offline")
            return

    try:
        if args.mode == "offline":
            if args.type != "animation":
                print(f"Error: Offline mode only supports 'animation' type currently.")
                return
                
            print("Generating offline bundle...")
            # Offline mode doesn't use LLM, generates template-based content
            result = orchestrator.build_offline_bundle(
                topic=args.topic,
                animation_html=None,
                graph_data=None,
                tts_engine="edge_tts", # Will try to use TTS, might fail if no net
                voice="zh-CN-XiaoxiaoNeural" if args.language == "zh" else "en-US-JennyNeural"
            )
            
            # Copy file to output directory
            if result.get("animation_file"):
                src_file = resource_dir / result["animation_file"]
                dst_file = output_dir / f"{args.topic}_offline.html"
                if src_file.exists():
                    import shutil
                    shutil.copy2(src_file, dst_file)
                    print(f"\nSuccess! File saved to: {dst_file}")
                else:
                    print(f"\nError: Generated file not found at {src_file}")
            
        else: # Online mode
            print("Generating online bundle (this may take a minute)...")
            
            if args.type == "animation":
                result = await orchestrator.build_online_bundle(
                    topic=args.topic,
                    history=[],
                    llm_client=client,
                    tts_engine="edge_tts",
                    voice="zh-CN-XiaoxiaoNeural" if args.language == "zh" else "en-US-JennyNeural",
                    language=args.language
                )
                
                if result.get("animation_file"):
                    src_file = resource_dir / result["animation_file"]
                    dst_file = output_dir / f"{args.topic}_online.html"
                    if src_file.exists():
                        import shutil
                        shutil.copy2(src_file, dst_file)
                        print(f"\nSuccess! Animation saved to: {dst_file}")
            
            elif args.type == "mindmap":
                result = await orchestrator.build_mindmap_bundle(
                    topic=args.topic,
                    history=[],
                    llm_client=client
                )
                if result.get("mindmap_file"):
                     # Note: orchestrator returns relative path like "offline/mindmaps/..."
                    src_file = resource_dir / result["mindmap_file"] 
                    # Correcting path logic based on orchestrator implementation:
                    # render_mindmap_file returns "offline/mindmaps/{topic}.html"
                    # which is relative to resource_dir's parent? No, let's check.
                    # orchestrator: file_path = self.local_generator.offline_dir / "mindmaps" / ...
                    # return f"offline/mindmaps/{topic}.html"
                    
                    # If local_generator.offline_dir is "resources/offline"
                    # Then "offline/mindmaps/..." relative to "resources" folder? 
                    # actually orchestrator returns path relative to PARENT of offline_dir usually?
                    
                    # Let's trust the absolute path construction:
                    real_src = orchestrator.local_generator.offline_dir / "mindmaps" / f"{args.topic}.html"
                    
                    dst_file = output_dir / f"{args.topic}_mindmap.html"
                    if real_src.exists():
                        import shutil
                        shutil.copy2(real_src, dst_file)
                        print(f"\nSuccess! Mindmap saved to: {dst_file}")
                    else:
                        print(f"Error: Source file {real_src} not found")

            elif args.type == "bar_race":
                result = await orchestrator.build_bar_race_bundle(
                    topic=args.topic,
                    history=[],
                    llm_client=client
                )
                if result.get("bar_race_file"):
                    # orchestrator: returns relative to offline_dir.parent (resources)
                    real_src = resource_dir / result["bar_race_file"]
                    dst_file = output_dir / f"{args.topic}_bar_race.html"
                    if real_src.exists():
                        import shutil
                        shutil.copy2(real_src, dst_file)
                        print(f"\nSuccess! Bar Race saved to: {dst_file}")

            elif args.type == "geo_map":
                result = await orchestrator.build_geo_map_bundle(
                    topic=args.topic,
                    history=[],
                    llm_client=client
                )
                if result.get("geo_map_file"):
                    real_src = resource_dir / result["geo_map_file"]
                    dst_file = output_dir / f"{args.topic}_geo_map.html"
                    if real_src.exists():
                        import shutil
                        shutil.copy2(real_src, dst_file)
                        print(f"\nSuccess! Geo Map saved to: {dst_file}")

    except Exception as e:
        print(f"\nGeneration Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
