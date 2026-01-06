from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Sequence
import sys

try:
    from .animation import default_storyboard, guard_animation_markup, storyboard_to_svg
    from .graph_builder import GraphBuilder
    from .local_generator import LocalGenerator
    from .media import generate_tts_audio
    from .utils import ensure_dir
except ImportError:
    PARENT_DIR = Path(__file__).resolve().parent
    if str(PARENT_DIR) not in sys.path:
        sys.path.append(str(PARENT_DIR))
    from animation import default_storyboard, guard_animation_markup, storyboard_to_svg
    from graph_builder import GraphBuilder
    from local_generator import LocalGenerator
    from media import generate_tts_audio
    from utils import ensure_dir


def get_audio_duration(file_path: Path) -> float:
    try:
        from moviepy.editor import AudioFileClip
        # 使用上下文管理器确保资源释放
        with AudioFileClip(str(file_path)) as clip:
            return clip.duration
    except Exception as e:
        print(f"[WARNING] 无法获取音频时长 {file_path}: {e}")
        # 尝试使用 mutagen 作为备选
        try:
            from mutagen.mp3 import MP3
            audio = MP3(file_path)
            return audio.info.length
        except:
            pass
        return 0.0


class VisualizationOrchestrator:
    def __init__(self, template_dir: Path, offline_dir: Path) -> None:
        self._templates = template_dir
        self.graph_builder = GraphBuilder()
        self.local_generator = LocalGenerator(offline_dir, self.graph_builder)
    
    @property
    def templates(self) -> Path:
        return self._templates
    
    def __dir__(self):
        """隐藏内部Path属性"""
        return ['build_online_bundle', 'build_offline_bundle']
    
    def __getstate__(self) -> Dict[str, Any]:
        """防止Path对象被pywebview序列化"""
        return {
            "templates_dir": str(self._templates),
        }

    async def build_online_bundle(
        self,
        topic: str,
        history: Sequence[Dict[str, str]],
        llm_client: "LLMClient",
        tts_engine: str = "edge_tts",
        voice: str = "zh-CN-XiaoxiaoNeural",
        tts_config: Dict[str, Any] = None,
        content: str = None,
        custom_prompt: str = None,
        review_callback: Any = None,
        language: str = "zh",
        frame_count: int = 8,
    ) -> Dict[str, Any]:
        animation_svg, storyboard, is_animation_online = await self._generate_animation_markup(topic, history, llm_client, content, custom_prompt, language, frame_count)
        
        # 人工复核步骤
        if review_callback:
            print(f"[Orchestrator] Waiting for manual review...")
            try:
                # review_callback 应该是一个 async 函数或者返回 future
                # 传入当前的 SVG 和 Storyboard
                new_svg, new_storyboard = await review_callback(animation_svg, storyboard)
                
                # 如果返回了新的内容，则更新
                if new_svg:
                    animation_svg = new_svg
                if new_storyboard:
                    storyboard = new_storyboard
                print(f"[Orchestrator] Manual review completed.")
            except Exception as e:
                print(f"[Orchestrator] Manual review callback failed: {e}")
                import traceback
                traceback.print_exc()

        local_meta = self.local_generator.derive_from_online(topic, None)
        
        # 使用AI生成的storyboard，而不是local_meta的
        # 强制重新生成音频，确保使用最新的TTS设置
        html_content = self._embed_animation(animation_svg, storyboard, topic, tts_engine, voice, tts_config, force_regenerate=True)
        
        # 保存动画HTML到文件
        animation_file_path = self._save_animation_html(html_content, topic, language)
        
        bundle = {
            "type": "animation",
            "topic": topic,  # 添加topic字段
            "animation_html": html_content,
            "animation_file": animation_file_path,  # 动画文件路径
            "animation_code": animation_svg,
            "storyboard": storyboard,  # 保存storyboard到bundle
            "is_online": is_animation_online,  # 是否在线生成
            "is_animation_online": is_animation_online,
        }
        bundle.update(local_meta)
        return bundle




    def _markdown_to_echarts_data(self, markdown: str) -> Dict[str, Any]:
        """Convert Markdown content to ECharts tree data structure"""
        lines = markdown.strip().split('\n')
        root = {"name": "Root", "children": []}
        # Stack of (level, node)
        stack = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Determine level and name
            level = 0
            name = line
            
            if line.startswith('#'):
                # Heading style: # Root, ## Child
                while level < len(line) and line[level] == '#':
                    level += 1
                name = line[level:].strip()
            elif line.startswith('-'):
                # List style: - Item,   - Subitem
                # This is tricky because indentation matters. 
                # For simplicity, let's assume standard Markdown headers for structure 
                # or mix of headers and lists where lists are deeper.
                # But the prompt asks for headers.
                # If we encounter list items, we treat them as children of the last header
                # We need to estimate level based on previous context or indentation
                # For now, let's stick to the prompt requirement: # for centers, ## for branches
                pass
            
            if not name:
                continue
                
            node = {"name": name, "children": []}
            
            if level == 1:
                root = node
                stack = [(1, node)]
            else:
                # Find parent
                while stack and stack[-1][0] >= level:
                    stack.pop()
                
                if stack:
                    parent = stack[-1][1]
                    parent["children"].append(node)
                    stack.append((level, node))
                else:
                    # Fallback if structure is weird, add to root
                    if root != node:
                        root["children"].append(node)
                        stack.append((1, root))
                        stack.append((level, node))
        
        return root

    def render_mindmap_file(self, topic: str, markdown_content: str | Dict[str, Any], language: str = "zh") -> str:
        """渲染并保存思维导图文件，返回相对路径"""
        # Get data: if markdown, convert; if dict, use directly
        if isinstance(markdown_content, str):
            data = self._markdown_to_echarts_data(markdown_content)
        else:
            data = markdown_content
            
        # Prepare ECharts Option
        option = {
            "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
            "series": [
                {
                    "type": "tree",
                    "data": [data],
                    "top": "1%",
                    "left": "7%",
                    "bottom": "1%",
                    "right": "20%",
                    "symbolSize": 10,
                    "label": {
                        "position": "left",
                        "verticalAlign": "middle",
                        "align": "right",
                        "fontSize": 16,
                        "fontWeight": "bold"
                    },
                    "leaves": {
                        "label": {
                            "position": "right",
                            "verticalAlign": "middle",
                            "align": "left",
                            "fontSize": 14,
                            "fontWeight": "normal"
                        }
                    },
                    "emphasis": {
                        "focus": "descendant"
                    },
                    "expandAndCollapse": True,
                    "animationDuration": 550,
                    "animationDurationUpdate": 750,
                    "roam": True,  # Enable drag/zoom
                    "initialTreeDepth": 2
                }
            ]
        }
        
        import json
        option_json = json.dumps(option, ensure_ascii=False)
        
        # 嵌入模板
        template_path = self.templates / "echarts_mindmap.html"
        html_content = ""
        if template_path.exists():
            shell = template_path.read_text(encoding="utf-8")
            html_content = shell.replace("{{OPTION_JSON}}", option_json)
            html_content = html_content.replace("{{TITLE}}", topic)
            html_content = html_content.replace("{{BG_COLOR}}", "#f4f4f4")
            html_content = html_content.replace("{{FONT}}", "Microsoft YaHei")
        else:
            # Fallback
            html_content = f"<html><body>Template not found</body></html>"
        
        # 保存文件
        mindmap_dir = self.local_generator.offline_dir / "mindmaps"
        ensure_dir(mindmap_dir)
        
        # 添加语言后缀
        suffix = "cn" if language == "zh" else "en"
        file_name = f"{topic}_{suffix}.html"
        file_path = mindmap_dir / file_name
        file_path.write_text(html_content, encoding="utf-8")
        
        return f"offline/mindmaps/{file_name}"

    async def build_mindmap_bundle(
        self,
        topic: str,
        history: Sequence[Dict[str, str]],
        llm_client: "LLMClient",
        content: str = None,
        language: str = "zh",
        max_node_length: int = 0,
    ) -> Dict[str, Any]:
        """生成思维导图包"""
        print(f"[思维导图] 开始生成: {topic} (模式: {'按内容' if content else '按主题'}, 语言: {language}, 节点字数: {max_node_length})")
        try:
            # 1. 调用LLM生成Markdown
            markdown_content = await llm_client.generate_mindmap(
                topic, 
                history, 
                content=content, 
                language=language, 
                max_node_length=max_node_length
            )
            
            # 简单清理
            if "```" in markdown_content:
                import re
                match = re.search(r'```(?:markdown)?(.*?)```', markdown_content, re.DOTALL)
                if match:
                    markdown_content = match.group(1).strip()
            
            # 2. 转换数据
            mindmap_data = self._markdown_to_echarts_data(markdown_content)
            
            # 3. 渲染并保存
            file_path = self.render_mindmap_file(topic, mindmap_data, language=language)
            
            return {
                "topic": topic,
                "mindmap_file": file_path,
                "mindmap_content": markdown_content,
                "mindmap_data": mindmap_data, # Return structured data
                "is_online": True
            }
            
        except Exception as e:
            print(f"[思维导图] 生成失败: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def render_animation_file(self, topic: str, storyboard: List[Dict[str, str]], 
                            animation_code: str = "", tts_engine: str = "edge_tts", 
                            voice: str = "zh-CN-XiaoxiaoNeural", tts_config: Dict[str, Any] = None, language: str = "zh") -> str:
        """渲染并保存动画文件，返回相对路径"""
        # 如果提供了animation_code，尝试使用它；否则使用storyboard生成
        # 注意：_embed_animation 内部会检查 animation_code 是否包含 SVG，如果不包含则使用 storyboard 生成
        
        html_content = self._embed_animation(
            animation_code, 
            storyboard, 
            topic, 
            tts_engine, 
            voice, 
            tts_config, 
            force_regenerate=True
        )
        
        return self._save_animation_html(html_content, topic, language)

    def _normalize_bar_race_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize bar race data: ensure continuous timeline and interpolate missing values"""
        try:
            timeline = data.get("timeline", [])
            series_data = data.get("data", [])
            categories = data.get("categories", [])
            
            if not timeline or not series_data or not categories:
                return data
                
            # Check if timeline is numeric (years or steps)
            try:
                # First try converting to float to handle "2020.0" or "1.5"
                # If they are all integers (e.g. 2020.0), we treat them as ints for better step=1 interpolation
                timeline_floats = [float(str(t).strip()) for t in timeline]
                
                # Check if all are effectively integers
                is_all_integers = all(x.is_integer() for x in timeline_floats)
                
                if is_all_integers:
                    timeline_ints = [int(x) for x in timeline_floats]
                else:
                    # If we have real floats (1.5, 2.2), skip Step-1 interpolation for now
                    # as we don't know the desired resolution.
                    # But we should still check if they are sorted?
                    # For now, let's just return original data to avoid breaking custom steps.
                    return data
            except ValueError:
                # Not numeric (maybe months?), skip optimization
                return data
                
            # Check if sorted
            if timeline_ints != sorted(timeline_ints):
                # If not sorted, we can't easily interpolate without reordering everything.
                # For now, let's assume LLM sorts them or we skip.
                # Sorting implies reordering series_data, which is doable but complex if unsorted.
                # Given prompt requirements, let's assume sorted but maybe gapped.
                # If strictly unsorted, let's just zip, sort, and unzip.
                combined = sorted(zip(timeline_ints, series_data), key=lambda x: x[0])
                timeline_ints = [x[0] for x in combined]
                series_data = [x[1] for x in combined]
            
            # Check for gaps
            if len(timeline_ints) < 2:
                return data
                
            min_year = timeline_ints[0]
            max_year = timeline_ints[-1]
            full_timeline = list(range(min_year, max_year + 1))
            
            if len(full_timeline) == len(timeline_ints):
                # No gaps
                data["timeline"] = [str(y) for y in timeline_ints]
                data["data"] = series_data
                return data
                
            # Perform interpolation
            new_data = []
            
            # Helper to find bounding indices
            def find_bounds(year, current_timeline):
                # We know current_timeline is sorted
                for i in range(len(current_timeline) - 1):
                    if current_timeline[i] <= year <= current_timeline[i+1]:
                        return i, i+1
                return 0, 0
            
            for year in full_timeline:
                if year in timeline_ints:
                    idx = timeline_ints.index(year)
                    new_data.append(series_data[idx])
                else:
                    # Interpolate
                    idx1, idx2 = find_bounds(year, timeline_ints)
                    y1 = timeline_ints[idx1]
                    y2 = timeline_ints[idx2]
                    
                    # Fraction
                    if y2 == y1:
                        frac = 0
                    else:
                        frac = (year - y1) / (y2 - y1)
                    
                    row1 = series_data[idx1]
                    row2 = series_data[idx2]
                    
                    new_row = []
                    for v1, v2 in zip(row1, row2):
                        # Ensure values are numbers
                        try:
                            val1 = float(v1)
                            val2 = float(v2)
                            interp_val = val1 + (val2 - val1) * frac
                            # Keep precision reasonable (e.g. 2 decimals)
                            new_row.append(round(interp_val, 2))
                        except (ValueError, TypeError):
                            # Non-numeric value, just take v1
                            new_row.append(v1)
                    new_data.append(new_row)
            
            print(f"[BarRace] Optimized timeline from {len(timeline_ints)} points to {len(full_timeline)} points (continuous years).")
            
            data["timeline"] = [str(y) for y in full_timeline]
            data["data"] = new_data
            
            return data
            
        except Exception as e:
            print(f"[BarRace] Data normalization failed: {e}")
            import traceback
            traceback.print_exc()
            return data

    async def build_bar_race_bundle(
        self,
        topic: str,
        history: Sequence[Dict[str, str]],
        llm_client: "LLMClient",
        content: str = None,
        language: str = "zh",
    ) -> Dict[str, Any]:
        """生成动态排序图包"""
        # 1. 调用LLM生成数据
        print(f"[BarRace] Generating data for: {topic} (Language: {language})")
        bar_race_data = await llm_client.generate_bar_race(topic, history, content)
        
        if not bar_race_data:
            print("[BarRace] Failed to generate data")
            return {"type": "bar_race", "error": "Failed to generate data"}
            
        # 1.5 数据标准化（插值补全缺失年份）
        bar_race_data = self._normalize_bar_race_data(bar_race_data)
            
        # 2. 读取模板
        template_path = self.templates / "bar_race_shell.html"
        if not template_path.exists():
            print("[BarRace] Template not found")
            return {"type": "bar_race", "error": "Template not found"}
            
        shell = template_path.read_text(encoding="utf-8")
        
        # 3. 注入数据
        import json
        data_json = json.dumps(bar_race_data, ensure_ascii=False)
        html_content = shell.replace("{{TITLE}}", f"{topic} - 动态排序图")
        html_content = html_content.replace("{{DATA_JSON}}", data_json)
        
        # 4. 保存文件
        file_path = self._save_bar_race_html(html_content, topic, language)
        
        return {
            "type": "bar_race",
            "topic": topic,
            "bar_race_file": file_path,
            "data": bar_race_data,
            "is_online": True
        }

    async def build_geo_map_bundle(
        self,
        topic: str,
        history: Sequence[Dict[str, str]],
        llm_client: "LLMClient",
        content: str = None,
        language: str = "zh",
        map_type: str = "default",
    ) -> Dict[str, Any]:
        """生成地理数据可视化包"""
        # 1. 调用LLM生成数据
        print(f"[GeoMap] Generating data for: {topic} (Language: {language}, Type: {map_type})")
        geo_data = await llm_client.generate_geo_map(topic, history, content)
        
        if not geo_data:
            print("[GeoMap] Failed to generate data")
            return {"type": "geo_map", "error": "Failed to generate data"}
            
        # 注入可视化类型
        geo_data["visualizationType"] = map_type
            
        # 2. 读取模板
        template_path = self.templates / "geo_map_shell.html"
        if not template_path.exists():
            print("[GeoMap] Template not found")
            return {"type": "geo_map", "error": "Template not found"}
            
        shell = template_path.read_text(encoding="utf-8")
        
        # 3. 注入数据
        import json
        data_json = json.dumps(geo_data, ensure_ascii=False)
        html_content = shell.replace("{{TITLE}}", f"{topic} - 地理可视化")
        html_content = html_content.replace("{{DATA_JSON}}", data_json)
        # 确保 CONFIG_JSON 被替换，防止 SyntaxError
        html_content = html_content.replace("{{CONFIG_JSON}}", "{}")
        
        # 注入地图加载逻辑
        map_loader_script = ""
        map_type_val = geo_data.get("mapType", "china")
        
        if map_type_val == "china":
            # 使用本地清洗过的地图数据
            clean_map_path = self.templates.parent / "maps" / "china_v2.js"
            if clean_map_path.exists():
                print(f"[GeoMap] Using local clean map: {clean_map_path}")
                map_content = clean_map_path.read_text(encoding="utf-8")
                map_loader_script = f"""
                // Local Clean Map Data
                {map_content}
                
                // Initialize
                // cleanGeoJSON(); 
                initGeoCoordMap();
                initChart();
                """
            else:
                print(f"[GeoMap] Local map not found at {clean_map_path}, falling back to CDN")
                map_loader_script = self._get_cdn_loader_script()
        else:
            map_loader_script = self._get_cdn_loader_script()
            
        html_content = html_content.replace("{{MAP_LOADER_SCRIPT}}", map_loader_script)
        
        # 4. 保存文件

        file_path = self._save_geo_map_html(html_content, topic, language)
        
        return {
            "type": "geo_map",
            "topic": topic,
            "geo_map_file": file_path,
            "data": geo_data,
            "is_online": True
        }

    def _get_cdn_loader_script(self) -> str:
        return """
        // Pyecharts assets URL pattern
        var mapUrl;
        if (mapPinyin === 'china') {
            mapUrl = '../../maps/china_v2.js';
        } else {
            mapUrl = 'https://assets.pyecharts.org/assets/maps/' + mapPinyin + '.js';
        }
        
        // Dynamic script loading
        var script = document.createElement('script');
        script.src = mapUrl;
        script.onload = function() {
            // cleanGeoJSON(); // Disabled: Corrupts encoded map data
            initGeoCoordMap(); // Extract coords after map load
            initChart();
        };
        script.onerror = function() {
            document.getElementById('container').innerHTML = '<div class="loading" style="color:red">地图加载失败: ' + mapUrl + '</div>';
        };
        document.head.appendChild(script);
        """

    def _save_bar_race_html(self, html_content: str, topic: str, language: str = "zh") -> str:
        """保存动态排序图HTML到文件，返回相对路径"""
        dir_path = self.local_generator.offline_dir / "bar_races"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        suffix = "cn" if language == "zh" else "en"
        file_name = f"{topic}_{suffix}_{int(asyncio.get_event_loop().time())}.html"
        file_path = dir_path / file_name
        file_path.write_text(html_content, encoding="utf-8")
        
        return str(file_path.relative_to(self.local_generator.offline_dir.parent))

    def _save_geo_map_html(self, html_content: str, topic: str, language: str = "zh") -> str:
        """保存地理数据可视化HTML到文件，返回相对路径"""
        dir_path = self.local_generator.offline_dir / "geo_maps"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        suffix = "cn" if language == "zh" else "en"
        file_name = f"{topic}_{suffix}_{int(asyncio.get_event_loop().time())}.html"
        file_path = dir_path / file_name
        file_path.write_text(html_content, encoding="utf-8")
        
        return str(file_path.relative_to(self.local_generator.offline_dir.parent))

    def build_offline_bundle(self, topic: str, animation_html: str | None, graph_data: Dict[str, Any] | None, 
                            tts_engine: str = "edge_tts", voice: str = "zh-CN-XiaoxiaoNeural",
                            tts_config: Dict[str, Any] = None, language: str = "zh") -> Dict[str, Any]:
        # 直接调用local_generator生成完整bundle（包含storyboard）
        generated = self.local_generator.build_bundle(topic, animation_html, graph_data)
        
        html_content = self._embed_animation(
            generated.get("animation_html", ""),
            generated.get("storyboard", []),
            topic,
            tts_engine,
            voice,
            tts_config,
            force_regenerate=False  # 离线模式使用缓存音频
        )
        
        # 保存动画HTML到文件
        animation_file_path = self._save_animation_html(html_content, topic, language)
        
        generated["animation_html"] = html_content
        generated["animation_file"] = animation_file_path
        return generated

    # 测量音频时长
    def get_audio_duration(file_path: Path) -> float:
        try:
            from moviepy.editor import AudioFileClip
            # 使用上下文管理器确保资源释放
            with AudioFileClip(str(file_path)) as clip:
                return clip.duration
        except Exception as e:
            print(f"[WARNING] 无法获取音频时长 {file_path}: {e}")
            # 尝试使用 mutagen 作为备选
            try:
                from mutagen.mp3 import MP3
                audio = MP3(file_path)
                return audio.info.length
            except:
                pass
            return 0.0

    async def _generate_animation_markup(
        self,
        topic: str,
        history: Sequence[Dict[str, str]],
        llm_client: "LLMClient",
        content: str = None,
        custom_prompt: str = None,
        language: str = "zh",
        frame_count: int = 8,
    ) -> tuple:
        """生成动画标记，返回 (svg_html, storyboard, is_online)"""
        try:
            print(f"[动画生成] 开始调用LLM API，主题: {topic}, 语言: {language}, 分镜数: {frame_count}")
            raw_markup = await llm_client.generate_animation(topic, history, content, custom_prompt, language, frame_count)
            print(f"[动画生成] API响应长度: {len(raw_markup) if raw_markup else 0}")
            print(f"[动画生成] API响应前300字符: {raw_markup[:300] if raw_markup else 'None'}")
            
            svg_html, storyboard = guard_animation_markup(raw_markup)
            print(f"[动画生成] guard_animation_markup返回: svg长度={len(svg_html) if svg_html else 0}, storyboard帧数={len(storyboard)}")
            
            # 只要有storyboard就认为成功（即使svg_html为空）
            if storyboard and len(storyboard) > 0:
                print(f"[动画生成] 在线生成成功！")
                return svg_html, storyboard, True  # 在线生成成功
            else:
                print(f"[动画生成] guard返回的storyboard为空，判定为失败")
        except Exception as exc:  # noqa: BLE001
            # 网络问题时静默回退到离线模式（不显示任何错误）
            error_msg = str(exc).lower()
            is_network_error = any(keyword in error_msg for keyword in 
                ['timeout', 'connect', 'connection', '网络', '超时'])
            print(f"[动画生成] 异常: {str(exc)}")
            if not is_network_error:
                import traceback
                traceback.print_exc()
        
        print(f"[动画生成] 使用默认动画")
        default_frames = default_storyboard(topic)
        return storyboard_to_svg(default_frames), default_frames, False  # 使用默认动画

    def _embed_animation(self, markup: str, storyboard: List[Dict[str, str]] | None = None, topic: str = "动画", 
                        tts_engine: str = "edge_tts", voice: str = "zh-CN-XiaoxiaoNeural",
                        tts_config: Dict[str, Any] = None, force_regenerate: bool = False) -> str:
        template_path = self.templates / "animation_shell.html"
        if not template_path.exists():
            return markup
        
        shell = template_path.read_text(encoding="utf-8")
        
        # 使用TTS生成音频（根据用户选择的引擎）
        audio_files = []
        audio_durations = []  # 记录每个音频的实际时长
        
        if storyboard:
            audio_dir = self.local_generator.offline_dir / "audio"
            ensure_dir(audio_dir)
            
            # 同步生成音频文件，确保HTML生成时音频已存在
            for idx, frame in enumerate(storyboard):
                narration = frame.get("narration") or frame.get("body") or ""
                if narration:
                    # 尝试两种格式（gTTS/Edge TTS用mp3，pyttsx3用wav）
                    audio_path_mp3 = audio_dir / f"{topic}_{idx}.mp3"
                    audio_path_wav = audio_dir / f"{topic}_{idx}.wav"
                    
                    # 检查是否已存在有效的音频文件
                    has_valid_audio = (
                        (audio_path_wav.exists() and audio_path_wav.stat().st_size > 0) or
                        (audio_path_mp3.exists() and audio_path_mp3.stat().st_size > 0)
                    )
                    
                    if force_regenerate or not has_valid_audio:
                        try:
                            # 生成音频（使用用户选择的TTS引擎和语音）
                            print(f"[生成] 音频文件: {audio_path_mp3.name}, 内容: {narration[:50]}...")
                            success = generate_tts_audio(narration, audio_path_mp3, tts_engine, voice, tts_config)
                            if success:
                                # 检查哪个文件真正生成了
                                if audio_path_mp3.exists() and audio_path_mp3.stat().st_size > 0:
                                    print(f"[OK] 音频已生成: {audio_path_mp3.name}")
                                elif audio_path_wav.exists() and audio_path_wav.stat().st_size > 0:
                                    print(f"[OK] 音频已生成: {audio_path_wav.name}")
                        except Exception as e:
                            print(f"生成音频失败: {e}")
                    else:
                        print(f"[缓存] 使用已存在的音频: {audio_path_mp3.name if audio_path_mp3.exists() else audio_path_wav.name}")
                    
                    # 添加音频文件路径（优先使用wav）
                    actual_audio_path = None
                    if audio_path_wav.exists() and audio_path_wav.stat().st_size > 0:
                        rel_path = f"../audio/{audio_path_wav.name}"
                        audio_files.append(rel_path)
                        actual_audio_path = audio_path_wav
                    elif audio_path_mp3.exists() and audio_path_mp3.stat().st_size > 0:
                        rel_path = f"../audio/{audio_path_mp3.name}"
                        audio_files.append(rel_path)
                        actual_audio_path = audio_path_mp3
                    else:
                        audio_files.append("")  # 如果生成失败，占位
                    
                    # 测量音频时长
                    if actual_audio_path:
                        duration = get_audio_duration(actual_audio_path)
                        audio_durations.append(duration)
                        print(f"[时长] {actual_audio_path.name}: {duration:.2f}秒")
                    else:
                        # 无音频时，根据字数估算时长
                        char_count = len(narration) if narration else 0
                        estimated = max(3.0, char_count * 0.3 + 1.0)
                        audio_durations.append(estimated)
                        print(f"[时长] 无音频，估算时长: {estimated:.2f}秒 (字数: {char_count})")
                else:
                    audio_files.append("")
                    # 无音频时，根据字数估算时长
                    char_count = len(narration) if narration else 0
                    estimated = max(3.0, char_count * 0.3 + 1.0)
                    audio_durations.append(estimated)
                    print(f"[时长] 无音频，估算时长: {estimated:.2f}秒 (字数: {char_count})")
        
        # 检查markup是否包含AI生成的SVG内容
        has_svg_content = "<svg" in markup.lower() and len(markup) > 500
        
        print(f"[调试] markup长度: {len(markup)}, 包含<svg>: {'<svg' in markup.lower()}, has_svg_content: {has_svg_content}")
        print(f"[调试] markup前200字符: {markup[:200]}")
        
        # 只有当markup不包含完整SVG内容时，才使用storyboard重新生成
        # 这样可以保留AI生成的图形，同时支持纯文本fallback
        if audio_durations and storyboard and not has_svg_content:
            print(f"[动画] markup无SVG内容，使用实际音频时长生成默认动画: {audio_durations}")
            markup = storyboard_to_svg(storyboard, frame_durations=audio_durations)
        elif has_svg_content:
            print(f"[动画] 保留AI生成的SVG内容（长度: {len(markup)}）")
        
        # 准备动画数据（包含storyboard、音频路径和时长）
        import json
        animation_data = {
            "storyboard": storyboard or [],
            "audioFiles": audio_files,
            "frameDurations": audio_durations  # 传递给前端使用
        }
        animation_data_json = json.dumps(animation_data, ensure_ascii=False)
        
        result = shell.replace("{{CONTENT}}", markup)
        result = result.replace("{{ANIMATION_DATA}}", animation_data_json)
        
        return result
    
    def _save_animation_html(self, html_content: str, topic: str, language: str = "zh") -> str:
        """保存动画HTML到文件，返回相对路径"""
        animations_dir = self.local_generator.offline_dir / "animations"
        ensure_dir(animations_dir)
        
        # 使用主题名作为文件名
        suffix = "cn" if language == "zh" else "en"
        file_name = f"{topic}_{suffix}.html"
        file_path = animations_dir / file_name
        
        # 调试：检查内容是否包含完整HTML结构
        has_doctype = "<!DOCTYPE" in html_content
        has_script = "<script>" in html_content
        print(f"[调试] 保存动画HTML: {file_name}, 长度={len(html_content)}, 包含DOCTYPE={has_doctype}, 包含script={has_script}")
        
        # 写入HTML内容
        file_path.write_text(html_content, encoding="utf-8")
        
        # 返回相对于offline目录的路径
        return f"offline/animations/{file_name}"


# Local import for type checking
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..llm.client import LLMClient
