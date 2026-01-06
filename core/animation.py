from __future__ import annotations

import html
import math
from typing import Dict, Iterable, List

_DEFAULT_THEME = {
    "background": "linear-gradient(160deg, #E9ECFF 0%, #C7D2FE 100%)",
    "card": "#FFFFFF",
    "title": "#1E1B4B",
    "text": "#4338CA",
}


def default_storyboard(topic: str) -> List[Dict[str, str]]:
    return [
        {"heading": topic, "body": "生成中，当前展示离线预览。"},
        {"heading": "理解重点", "body": "联网后将出现 AI 驱动的互动动画。"},
        {"heading": "下一步", "body": "填写密钥或导入离线资源即可体验完整效果。"},
    ]


def storyboard_to_svg(frames: Iterable[Dict[str, str]], frame_durations: List[float] | None = None) -> str:
    slides: List[str] = []
    frame_list = list(frames)
    total_frames = len(frame_list)
    
    # 使用传入的实际音频时长，或默认6秒每帧
    if frame_durations is None:
        # 尝试从frame数据中获取时长
        computed_durations = []
        for frame in frame_list:
            # 支持 'duration' 或 'seconds' 字段
            d = float(frame.get("duration", frame.get("seconds", 6.0)))
            computed_durations.append(d)
        frame_durations = computed_durations
    elif len(frame_durations) < total_frames:
        # 如果时长列表不够，补齐到帧数
        frame_durations = list(frame_durations) + [6.0] * (total_frames - len(frame_durations))
    
    total_duration = sum(frame_durations)
    
    # 定义多种动画效果样式
    animation_styles = [
        "slide-zoom",   # 缩放入场
        "slide-rotate", # 旋转入场
        "slide-flip",   # 翻转入场
        "slide-bounce", # 弹跳入场
        "slide-blur"    # 模糊入场
    ]
    
    # 定义多种运镜效果 (Camera Moves)
    camera_moves = [
        "move-zoom-slow",
        "move-pan-h",
        "move-float"
    ]
    
    cumulative_delay = 0.0  # 累计延迟时间
    for index, frame in enumerate(frame_list):
        delay = cumulative_delay
        current_duration = frame_durations[index]
        title = html.escape(frame.get("heading", "瞬间"))
        body = html.escape(frame.get("body", ""))
        narration = html.escape(frame.get("narration", body))
        
        # 为不同帧选择不同的动画效果
        animation_class = animation_styles[index % len(animation_styles)]
        # 为不同帧选择不同的运镜效果
        camera_class = camera_moves[index % len(camera_moves)]
        
        # 添加进度指示器
        progress_dots = ""
        for i in range(total_frames):
            opacity = "1" if i == index else "0.3"
            # Center at 800. Offset = (i - (total_frames - 1) / 2) * spacing
            cx = 800 + (i - (total_frames - 1) / 2) * 50
            progress_dots += f'<circle cx="{cx}" cy="820" r="8" fill="#4F46E5" opacity="{opacity}" />'
        
        # 生成粒子效果（每帧30个粒子）
        particles = []
        for p in range(30):
            import random
            angle_rad = math.radians((360 / 30) * p)
            distance = 450 + random.randint(-100, 250)
            # Calculate delta (offset) from center (800, 450)
            dx = distance * math.cos(angle_rad)
            dy = distance * math.sin(angle_rad) * 0.8  # Elliptical distribution
            particle_delay = (p * 0.08)
            color = ["#4F46E5", "#10B981", "#F59E0B", "#EF4444"][p % 4]
            r = random.randint(4, 9)
            particles.append(
                f'<circle class="particle" cx="800" cy="450" r="{r}" fill="{color}" '
                f'style="--tx:{dx}px; --ty:{dy}px; animation-delay:{particle_delay}s;" />'
            )
        
        # 添加发光效果的装饰元素
        glow_circles = []
        for g in range(3):
            gr = 200 + g * 100  # Larger radius
            glow_delay = (g * 0.3)
            glow_circles.append(
                f'<circle class="glow-ring" cx="800" cy="450" r="{gr}" '
                f'fill="none" stroke="#4F46E5" stroke-width="3" opacity="0" '
                f'style="animation-delay:{glow_delay}s;" />'
            )
        
        slide = f"""
        <g id="slide-{index}" class="slide-group {animation_class}" data-animation="{animation_class}">
            <!-- 运镜层：包裹视觉元素以实现独立运镜 -->
            <g class="camera-layer {camera_class}">
                <!-- 粒子效果 -->
                <g class="particle-system">
                    {''.join(particles)}
                </g>
                
                <!-- 发光圆环 -->
                <g class="glow-system">
                    {''.join(glow_circles)}
                </g>
                
                <!-- 主卡片 -->
                <g class="card-container">
                    <defs>
                        <filter id="card-glow-{index}">
                            <feGaussianBlur in="SourceGraphic" stdDeviation="12" result="blur"/>
                            <feComposite in="blur" in2="SourceGraphic" operator="over"/>
                        </filter>
                        <linearGradient id="card-grad-{index}" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#FFFFFF; stop-opacity:1" />
                            <stop offset="100%" style="stop-color:#F0F4FF; stop-opacity:1" />
                        </linearGradient>
                    </defs>
                    <!-- 1600x900 Layout: Card centered -->
                    <rect class="card" x="200" y="150" width="1200" height="500" rx="40" 
                          fill="url(#card-grad-{index})" filter="url(#card-glow-{index})" />
                    
                    <!-- 装饰性的光效条纹 -->
                    <line class="shine-line" x1="200" y1="200" x2="1400" y2="200" 
                          stroke="url(#shine-grad)" stroke-width="4" opacity="0.6" 
                          style="animation-delay:0.5s;" />
                    
                    <text class="title" x="280" y="260">{title}</text>
                    <foreignObject x="280" y="300" width="1040" height="280">
                        <div xmlns="http://www.w3.org/1999/xhtml" class="copy">{body}</div>
                    </foreignObject>
                    <foreignObject x="200" y="680" width="1200" height="80">
                        <div xmlns="http://www.w3.org/1999/xhtml" class="subtitle">{narration}</div>
                    </foreignObject>
                </g>
            </g>
            
            <!-- 进度指示器 (不受运镜影响) -->
            <g class="progress-indicator">
                {progress_dots}
            </g>
        </g>
        """
        slides.append(slide.strip())
        
        # 累加当前帧的时长
        cumulative_delay += current_duration

    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" class="viz-canvas">
        <defs>
            <!-- 全局渐变定义 -->
            <linearGradient id="shine-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:#4F46E5; stop-opacity:0">
                    <animate attributeName="offset" values="0;1;0" dur="3s" repeatCount="indefinite"/>
                </stop>
                <stop offset="50%" style="stop-color:#10B981; stop-opacity:0.8">
                    <animate attributeName="offset" values="0.5;1;0.5" dur="3s" repeatCount="indefinite"/>
                </stop>
                <stop offset="100%" style="stop-color:#F59E0B; stop-opacity:0">
                    <animate attributeName="offset" values="1;0;1" dur="3s" repeatCount="indefinite"/>
                </stop>
            </linearGradient>
        </defs>
        
        <style>
            .viz-canvas {{ 
                background: {_DEFAULT_THEME['background']}; 
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
            
            /* 卡片样式 */
            .card {{ 
                filter: drop-shadow(0 30px 60px rgba(79,70,229,0.25));
                transition: all 0.3s ease;
            }}
            .card-container {{ 
                transform-origin: center center;
            }}
            
            /* 文字样式 */
            .title {{ 
                font: 700 64px 'Segoe UI', 'Microsoft YaHei', sans-serif; 
                fill: {_DEFAULT_THEME['title']};
            }}
            .copy {{ 
                font: 400 36px 'Segoe UI', 'Microsoft YaHei', sans-serif; 
                color: {_DEFAULT_THEME['text']}; 
                line-height: 1.6;
            }}
            .subtitle {{ 
                font: 500 28px 'Segoe UI', 'Microsoft YaHei', sans-serif; 
                color: #6366F1; 
                text-align: center; 
                line-height: 1.5;
                padding: 16px 40px;
                background: rgba(255,255,255,0.8);
                border-radius: 20px;
                box-shadow: 0 8px 24px rgba(99,102,241,0.15);
            }}
            
            /* 粒子动画 */
            .particle {{
                animation: particle-fly 3s ease-out infinite;
                transform-origin: center;
            }}
            @keyframes particle-fly {{
                0% {{ opacity: 0; transform: translate(0, 0) scale(0); }}
                20% {{ opacity: 1; }}
                100% {{ opacity: 0; transform: translate(var(--tx), var(--ty)) scale(2); }}
            }}
            
            /* 发光圆环动画 */
            .glow-ring {{
                animation: glow-expand 2s ease-out infinite;
            }}
            @keyframes glow-expand {{
                0% {{ opacity: 0; r: 50; }}
                30% {{ opacity: 0.6; }}
                100% {{ opacity: 0; r: 250; }}
            }}
            
            /* 光效线条动画 */
            .shine-line {{
                animation: shine-sweep 2s ease-in-out infinite;
            }}
            @keyframes shine-sweep {{
                0%, 100% {{ opacity: 0; }}
                50% {{ opacity: 0.8; }}
            }}
            
            /* === 基础滑入动画 === */
            .slide-group {{
                opacity: 0;
                display: none;
                transform-origin: 50% 50%;
            }}
            
            .slide-active {{
                display: block !important;
                animation-duration: 0.8s; /* 延长到 0.8s */
                animation-timing-function: cubic-bezier(0.2, 0.8, 0.2, 1);
                animation-fill-mode: forwards;
            }}
            
            /* === 离场动画 (新) === */
            .slide-exit {{
                display: block !important;
                animation: slide-out-blur 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards;
                pointer-events: none;
            }}
            @keyframes slide-out-blur {{
                0% {{ opacity: 1; filter: blur(0px); transform: scale(1); }}
                100% {{ opacity: 0; filter: blur(10px); transform: scale(1.1); }}
            }}
            
            /* === 运镜动画 (新) === */
            .camera-layer {{
                transform-origin: center center;
            }}
            .move-zoom-slow {{ animation: cam-zoom-s 12s linear infinite alternate; }}
            .move-pan-h {{ animation: cam-pan-h 15s ease-in-out infinite alternate; }}
            .move-float {{ animation: cam-float 20s ease-in-out infinite; }}
            
            /* High Energy Camera Moves (Consistent with _merge_svg_frames) */
            .camera-zoom-in {{ animation: camZoomIn 20s linear forwards; transform-origin: 800px 450px; }}
            .camera-zoom-out {{ animation: camZoomOut 20s linear forwards; transform-origin: 800px 450px; }}
            .camera-pan-right {{ animation: camPanRight 20s linear forwards; }}
            .camera-pan-left {{ animation: camPanLeft 20s linear forwards; }}
            .camera-pan-up {{ animation: camPanUp 20s linear forwards; }}
            .camera-float {{ animation: cam-float 20s ease-in-out infinite; }}

            @keyframes cam-zoom-s {{ 0% {{ transform: scale(1); }} 100% {{ transform: scale(1.08); }} }}
            @keyframes cam-pan-h {{ 0% {{ transform: translateX(-15px); }} 100% {{ transform: translateX(15px); }} }}
            @keyframes cam-float {{ 
                0% {{ transform: translate(0,0) rotate(0deg); }} 
                33% {{ transform: translate(10px, -10px) rotate(1deg); }} 
                66% {{ transform: translate(-5px, 10px) rotate(-1deg); }} 
                100% {{ transform: translate(0,0) rotate(0deg); }} 
            }}
            
            @keyframes camZoomIn {{ from {{ transform: scale(1); }} to {{ transform: scale(1.4); }} }}
            @keyframes camZoomOut {{ from {{ transform: scale(1.4); }} to {{ transform: scale(1); }} }}
            @keyframes camPanRight {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-100px); }} }}
            @keyframes camPanLeft {{ from {{ transform: translateX(-100px); }} to {{ transform: translateX(0); }} }}
            @keyframes camPanUp {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-80px); }} }}
            
            /* === 入场动画库 === */
            
            /* 缩放入场 */
            .slide-zoom {{
                animation-name: slide-zoom-anim;
            }}
            @keyframes slide-zoom-anim {{
                0% {{ opacity: 0; transform: scale(0.6) translateY(30px); filter: blur(5px); }}
                100% {{ opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }}
            }}
            
            /* 旋转入场 */
            .slide-rotate {{
                animation-name: slide-rotate-anim;
            }}
            @keyframes slide-rotate-anim {{
                0% {{ opacity: 0; transform: perspective(800px) rotateY(60deg) scale(0.8); }}
                100% {{ opacity: 1; transform: perspective(800px) rotateY(0deg) scale(1); }}
            }}
            
            /* 翻转入场 */
            .slide-flip {{
                animation-name: slide-flip-anim;
            }}
            @keyframes slide-flip-anim {{
                0% {{ opacity: 0; transform: perspective(800px) rotateX(-60deg) translateZ(-100px); }}
                100% {{ opacity: 1; transform: perspective(800px) rotateX(0deg) translateZ(0); }}
            }}
            
            /* 弹跳入场 */
            .slide-bounce {{
                animation-name: slide-bounce-anim;
            }}
            @keyframes slide-bounce-anim {{
                0% {{ opacity: 0; transform: translateY(100px) scale(0.8); }}
                60% {{ transform: translateY(-10px) scale(1.05); }}
                100% {{ opacity: 1; transform: translateY(0) scale(1); }}
            }}
            
            /* 模糊入场 (新) */
            .slide-blur {{
                animation-name: slide-blur-anim;
            }}
            @keyframes slide-blur-anim {{
                0% {{ opacity: 0; filter: blur(20px); transform: scale(1.1); }}
                100% {{ opacity: 1; filter: blur(0); transform: scale(1); }}
            }}

            /* 高级动画库 (Fallback Support) */
            .anim-shiver {{ animation: shiver 0.2s linear infinite; }}
            @keyframes shiver {{ 0% {{ transform: translate(1px, 1px); }} 100% {{ transform: translate(-1px, -1px); }} }}

            .anim-slide-right {{ animation: slideRight 1s ease-out forwards; opacity: 0; transform: translateX(-50px); }}
            @keyframes slideRight {{ to {{ opacity: 1; transform: translateX(0); }} }}

            @keyframes magneticFlow {{ to {{ stroke-dashoffset: -20; }} }}
            .anim-magnetic-flow {{ stroke-dasharray: 10, 5; animation: magneticFlow 1s linear infinite; }}
        </style>
        {''.join(slides)}
    </svg>
    """.strip()


def guard_animation_markup(markup: str) -> tuple:
    """处理AI生成的动画内容，返回 (svg_html, storyboard)"""
    print(f"[DEBUG] guard_animation_markup 接收内容长度: {len(markup)}")
    lowered = markup.lower()
    if "<script" in lowered or "javascript:" in lowered:
        print(f"[DEBUG] 检测到脚本内容，使用默认动画")
        default_frames = default_storyboard("主题")
        return storyboard_to_svg(default_frames), default_frames
    
    # 清理AI的元说明文本
    cleaned = _clean_ai_metadata(markup)
    print(f"[DEBUG] 清理元数据后长度: {len(cleaned)}")
    
    # 优先提取 SVG 代码（这才是我们想要的可视化效果）
    if "<svg" in cleaned.lower():
        print(f"[DEBUG] 检测到SVG内容，开始提取")
        svg_content, storyboard = _extract_svg(cleaned)
        if svg_content:
            print(f"[DEBUG] SVG提取成功，长度: {len(svg_content)}, storyboard帧数: {len(storyboard)}")
            return svg_content, storyboard
        else:
            print(f"[DEBUG] SVG提取失败")
    
    # 如果 AI 返回了 JSON 幻灯片数据（作为降级方案）
    print(f"[DEBUG] 尝试解析JSON幻灯片")
    frames = _parse_json_slides(cleaned)
    if frames:
        print(f"[DEBUG] JSON解析成功，帧数: {len(frames)}")
        return storyboard_to_svg(frames), frames
    
    # 最后尝试解析纯文本描述
    print(f"[DEBUG] 尝试解析纯文本描述")
    frames = _parse_text_to_frames(cleaned)
    if frames:
        print(f"[DEBUG] 文本解析成功，帧数: {len(frames)}")
        return storyboard_to_svg(frames), frames
    
    print(f"[DEBUG] 所有解析方法都失败，返回清理后的内容")
    return cleaned.strip(), []


def _parse_json_slides(text: str) -> List[Dict[str, str]]:
    """从 JSON 格式中提取幻灯片数据"""
    import json
    import re
    
    try:
        # 1. 尝试提取 JSON 代码块 (支持 list [...] 或 object {...})
        json_match = re.search(r'```json\s*([\[\{].*?[\]\}])\s*```', text, re.DOTALL)
        json_str = ""
        
        if json_match:
            json_str = json_match.group(1)
        else:
            # 2. 直接查找 JSON 数组 [...]
            json_match = re.search(r'^\s*\[\s*\{.*?\}\s*\]', text, re.DOTALL | re.MULTILINE)
            if json_match:
                json_str = json_match.group(0)
            else:
                # 3. 直接查找包含 "slides" 的 JSON 对象
                json_match = re.search(r'\{[^{}]*"slides"[^{}]*\[.*?\]\s*\}', text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
        
        if not json_str:
            return []

        data = json.loads(json_str)
        
        # 如果是列表，直接作为 slides
        if isinstance(data, list):
            slides = data
        else:
            slides = data.get("slides", [])
        
        # 转换为标准格式
        frames = []
        for slide in slides:
            frames.append({
                "heading": slide.get("heading", ""),
                "body": slide.get("body", ""),
                "narration": slide.get("narration", "")
            })
        
        return frames if frames else []
    except Exception as e:
        print(f"[WARN] JSON解析失败: {e}")
        return []


def _clean_ai_metadata(text: str) -> str:
    """移除AI的元说明和指令文本"""
    import re
    
    # 移除常见的AI开场白
    patterns = [
        r'^好的[，,].*?(?=<svg|$)',  # "好的，作为..."
        r'^作为.*?(?=<svg|$)',  # "作为一名..."
        r'###\s*SVG\s*代码.*?```html',  # "### SVG 代码 ```html"
        r'###\s*[^\n]*',  # 其他 ### 标题
        r'```html\s*',  # ```html 标记
        r'```\s*$',  # 结尾的 ```
        r'^这段代码.*$',  # "这段代码可以..."
        r'^\*\*.*?\*\*[:：]',  # **粗体标题**:
    ]
    
    result = text
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.MULTILINE | re.DOTALL)
    
    return result.strip()


def _extract_svg(text: str) -> tuple:
    """从文本中提取多个SVG分镜，合并为序列动画，并提取storyboard数据
    
    返回: (merged_svg, storyboard)
    storyboard格式: [{"heading": "标题", "body": "", "narration": "配音文字"}, ...]
    """
    import re
    
    print(f"[DEBUG] _extract_svg 开始提取，文本长度: {len(text)}")
    
    # 0. 尝试优先解析 JSON Storyboard
    parsed_storyboard = _parse_json_slides(text)
    if parsed_storyboard:
        print(f"[DEBUG] 成功解析到 JSON Storyboard，共 {len(parsed_storyboard)} 帧")
    
    # 查找所有 SVG 代码块（支持多分镜）
    # 使用非贪婪匹配，但如果遇到截断（只有开始没有结束），findall会漏掉最后一个
    # 所以我们手动遍历查找
    svg_matches = []
    
    # 查找所有 <svg 标签的起始位置
    start_indices = [m.start() for m in re.finditer(r'<svg[^>]*?>', text, re.IGNORECASE)]
    
    for i, start in enumerate(start_indices):
        # 确定搜索范围：从当前 <svg 开始，到下一个 <svg 之前（或文本末尾）
        search_end = start_indices[i+1] if i + 1 < len(start_indices) else len(text)
        chunk = text[start:search_end]
        
        # 在这个范围内查找结束标签 </svg>
        end_match = re.search(r'</svg>', chunk, re.IGNORECASE)
        
        if end_match:
            # 完整闭合的 SVG
            svg_content = chunk[:end_match.end()]
            svg_matches.append(svg_content)
        elif i == len(start_indices) - 1:
            # 最后一个 SVG 且没有闭合 -> 判定为截断
            print(f"[WARNING] 检测到最后一个 SVG 被截断，尝试自动修复闭合")
            # 移除末尾可能的垃圾字符（如 `<` 或 `</`）
            cleaned_chunk = chunk.rstrip()
            if cleaned_chunk.endswith("</"):
                cleaned_chunk = cleaned_chunk[:-2]
            elif cleaned_chunk.endswith("<"):
                cleaned_chunk = cleaned_chunk[:-1]
                
            # 强制闭合
            svg_matches.append(cleaned_chunk + "</g></svg>")
        else:
            # 中间的 SVG 没有闭合？这通常是不正常的，可能是嵌套或格式错误
            # 尝试提取到下一个 <svg 之前
            print(f"[WARNING] 中间的 SVG (索引 {i}) 似乎未闭合，尝试提取")
            svg_matches.append(chunk + "</svg>")

    if not svg_matches:
        print(f"[DEBUG] 未找到SVG代码块")
        return "", []
    
    print(f"[DEBUG] 找到 {len(svg_matches)} 个SVG代码块")
    
    # 提取每个分镜的标题、配音和SVG内容
    frames = []
    storyboard = []
    
    for idx, svg in enumerate(svg_matches):
        # 获取当前SVG之前的文本（可能包含注释）
        svg_start_pos = text.find(svg)
        # 找到上一个SVG结束位置（如果存在）
        prev_svg_end = 0
        if idx > 0:
            prev_svg_end = text.find(svg_matches[idx-1]) + len(svg_matches[idx-1])
        
        # 提取当前SVG之前的注释区域
        comment_section = text[prev_svg_end:svg_start_pos]
        
        # 查找分镜标题 <!-- 分镜X：标题 --> 或 <!-- 标题：... -->
        # 优化正则：支持更多格式，且不强求"分镜"字样
        title_match = re.search(r'<!--\s*(?:分镜\s*\d+|画面\s*\d+|Scene\s*\d+|Part\s*\d+|标题)\s*[：:]\s*([^-]+?)\s*-->', comment_section, re.IGNORECASE)
        # 如果找不到特定格式，尝试查找任意 "标题：xxx"
        if not title_match:
             title_match = re.search(r'<!--\s*Title\s*[：:]\s*([^-]+?)\s*-->', comment_section, re.IGNORECASE)
             
        # 默认标题为空，避免出现"分镜"字样
        title = title_match.group(1).strip() if title_match else ""
        
        # 查找配音文字 <!-- 配音：文字 --> 或 <!-- Voiceover: Text -->
        narration_match = re.search(r'<!--\s*(?:配音|Voiceover|Narration|Audio)\s*[：:]\s*([^-]+?)\s*-->', comment_section, re.IGNORECASE)
        narration = narration_match.group(1).strip() if narration_match else ""
        
        # 优化：移除字幕开头和结尾的标点符号
        narration = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', narration)
        
        # 优先使用 JSON Storyboard 中的数据 (如果匹配)
        if parsed_storyboard and idx < len(parsed_storyboard):
            json_frame = parsed_storyboard[idx]
            if json_frame.get("heading"):
                title = json_frame["heading"]
            if json_frame.get("narration"):
                narration = json_frame["narration"]
                # Clean narration from JSON too just in case
                narration = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', narration)
        
        print(f"[DEBUG] 分镜 {idx+1}: 标题={title}, 配音={narration[:30]}..., SVG长度={len(svg)}")
        
        frames.append({
            "svg": svg.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', ''),
            "title": title
        })
        
        storyboard.append({
            "heading": title,
            "body": "",  # SVG内容不需要body
            "narration": narration
        })
    
    # 如果只有一个SVG，也通过合并逻辑处理，以确保添加 frame-id 和标准化结构
    # if len(svg_matches) == 1:
    #    svg_code = svg_matches[0].replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '')
    #    print(f"[DEBUG] 单个SVG，长度: {len(svg_code)}")
    #    return svg_code, storyboard
    
    # 合并多个SVG为序列动画
    print(f"[DEBUG] 开始合并 {len(frames)} 个SVG分镜")
    merged = _merge_svg_frames(frames)
    print(f"[DEBUG] 合并后SVG长度: {len(merged)}")
    return merged, storyboard


def _merge_svg_frames(frames: List[Dict[str, str]], frame_durations: List[float] | None = None) -> str:
    """将多个SVG分镜合并为电影级序列动画"""
    print(f"[DEBUG] _merge_svg_frames 开始合并，帧数: {len(frames)}")
    if not frames:
        print(f"[DEBUG] 帧列表为空，返回空字符串")
        return ""
    
    total_frames = len(frames)
    
    # 使用传入的实际音频时长，或默认8秒每帧
    if frame_durations is None:
        frame_durations = [8.0] * total_frames
    elif len(frame_durations) < total_frames:
        frame_durations = list(frame_durations) + [8.0] * (total_frames - len(frame_durations))
    
    total_duration = sum(frame_durations)
    print(f"[DEBUG] 总时长: {total_duration}秒")
    
    # 构建包含所有分镜的SVG (1600x900 HD Standard)
    # Using Standard Coordinate System: (0,0) Top-Left, (800,450) Center
    merged_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" class="storyboard">
    <defs>
        <filter id="blur-transition">
            <feGaussianBlur in="SourceGraphic" stdDeviation="0">
                <animate attributeName="stdDeviation" values="0;8;0" dur="1.5s" repeatCount="indefinite" />
            </feGaussianBlur>
        </filter>
        <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>
        
        <!-- 逼真特效滤镜库 -->
        <!-- 1. 真实投影：带有扩散感的柔和阴影 -->
        <filter id="realistic-shadow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="4" result="blur"/>
            <feOffset in="blur" dx="4" dy="4" result="offsetBlur"/>
            <feFlood flood-color="#000000" flood-opacity="0.3" result="shadowColor"/>
            <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>
            <feMerge>
                <feMergeNode in="shadow"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>

        <!-- 2. 柔和发光：用于高光物体 -->
        <filter id="soft-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="blur"/>
            <feColorMatrix in="blur" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7" result="glow"/>
            <feMerge>
                <feMergeNode in="glow"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>

        <!-- 3. 内发光：增加体积感 -->
        <filter id="inner-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="4" result="blur"/>
            <feOffset dx="0" dy="0"/>
            <feComposite in2="SourceAlpha" operator="arithmetic" k2="-1" k3="1" result="shadowDiff"/>
            <feFlood flood-color="white" flood-opacity="0.5"/>
            <feComposite in2="shadowDiff" operator="in"/>
            <feComposite in2="SourceGraphic" operator="over"/>
        </filter>

        <!-- 4. 纹理噪点：防止矢量图过于平滑 -->
        <filter id="texture-noise">
            <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" result="noise"/>
            <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.1 0" in="noise" result="coloredNoise"/>
            <feComposite operator="in" in="coloredNoise" in2="SourceGraphic" result="compositeNoise"/>
            <feMerge>
                <feMergeNode in="SourceGraphic"/>
                <feMergeNode in="compositeNoise"/>
            </feMerge>
        </filter>

        <!-- 5. 玻璃光泽：模拟反光材质 -->
        <filter id="glass-shine">
            <feSpecularLighting in="SourceGraphic" surfaceScale="5" specularConstant="0.75" specularExponent="20" lighting-color="#white" result="specular">
                <fePointLight x="-5000" y="-10000" z="20000"/>
            </feSpecularLighting>
            <feComposite in="specular" in2="SourceAlpha" operator="in" result="specular"/>
            <feComposite in="SourceGraphic" in2="specular" operator="arithmetic" k1="0" k2="1" k3="1" k4="0"/>
        </filter>

        <!-- 6. 3D立体光照：自动给平面图形增加体积感 -->
        <filter id="3d-light" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="2" result="blur"/>
            <feOffset in="blur" dx="2" dy="2" result="offsetBlur"/>
            <feSpecularLighting in="blur" surfaceScale="5" specularConstant="1" specularExponent="15" lighting-color="white" result="specular">
                <fePointLight x="-5000" y="-10000" z="10000"/>
            </feSpecularLighting>
            <feComposite in="specular" in2="SourceAlpha" operator="in" result="specular"/>
            <feComposite in="SourceGraphic" in2="offsetBlur" operator="over" result="withShadow"/>
            <feComposite in="specular" in2="withShadow" operator="arithmetic" k2="1" k3="1" result="final"/>
        </filter>

        <!-- 7. 科普网格背景：增加科学严谨感 -->
        <pattern id="science-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#4F46E5" stroke-width="0.5" opacity="0.1"/>
        </pattern>
        
        <!-- 8. 通用箭头标记：保证指示符号标准统一 -->
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill="#4F46E5" />
        </marker>

        <!-- 9. 文字易读描边：防止背景干扰文字 -->
        <filter id="text-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feFlood flood-color="#000000" flood-opacity="0.9" result="flood"/>
            <feComposite in="flood" in2="SourceGraphic" operator="in" result="mask"/>
            <feMorphology in="mask" operator="dilate" radius="1.2" result="dilated"/>
            <feGaussianBlur in="dilated" stdDeviation="0.8" result="blurred"/>
            <feMerge>
                <feMergeNode in="blurred"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>
    </defs>
    <style>
        .storyboard { background: transparent; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; }
        .frame { display: none; }
        .frame.active { display: block; animation: fadeIn 0.5s ease; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        /* 通用动画库 */
        .anim-float { animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }

        .anim-pulse { animation: pulse 2s ease-in-out infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.05); opacity: 0.8; } }

        .anim-spin { animation: spin 10s linear infinite; transform-origin: center; }
        @keyframes spin { 100% { transform: rotate(360deg); } }

        .anim-spin-fast { animation: spin 2s linear infinite; transform-origin: center; }
        .anim-spin-slow { animation: spin 30s linear infinite; transform-origin: center; }

        .anim-drift { animation: drift 5s ease-in-out infinite alternate; }
        @keyframes drift { from { transform: translateX(-5px); } to { transform: translateX(5px); } }
        
        .anim-shake { animation: shake 0.5s linear infinite; }
        @keyframes shake { 0% { transform: translate(1px, 1px) rotate(0deg); } 10% { transform: translate(-1px, -2px) rotate(-1deg); } 20% { transform: translate(-3px, 0px) rotate(1deg); } 30% { transform: translate(3px, 2px) rotate(0deg); } 40% { transform: translate(1px, -1px) rotate(1deg); } 50% { transform: translate(-1px, 2px) rotate(-1deg); } 60% { transform: translate(-3px, 1px) rotate(0deg); } 70% { transform: translate(3px, 1px) rotate(-1deg); } 80% { transform: translate(-1px, -1px) rotate(1deg); } 90% { transform: translate(1px, 2px) rotate(0deg); } 100% { transform: translate(1px, -2px) rotate(-1deg); } }

        .anim-bounce { animation: bounce 2s infinite; }
        @keyframes bounce { 0%, 20%, 50%, 80%, 100% {transform: translateY(0);} 40% {transform: translateY(-30px);} 60% {transform: translateY(-15px);} }
        
        .anim-flash { animation: flash 1s infinite; }
        @keyframes flash { 0%, 50%, 100% { opacity: 1; } 25%, 75% { opacity: 0; } }

        .anim-fade-up { animation: fadeUp 0.8s ease-out forwards; opacity: 0; transform: translateY(20px); }
        @keyframes fadeUp { to { opacity: 1; transform: translateY(0); } }

        .anim-scale-in { animation: scaleIn 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; opacity: 0; transform: scale(0.5); transform-origin: center; }
        @keyframes scaleIn { to { opacity: 1; transform: scale(1); } }
        
        .anim-draw { stroke-dasharray: 1000; stroke-dashoffset: 1000; animation: drawStroke 2s ease-out forwards; }
        @keyframes drawStroke { to { stroke-dashoffset: 0; } }

        /* 新增高级动画 */
        .anim-shiver { animation: shiver 0.2s linear infinite; }
        @keyframes shiver { 0% { transform: translate(1px, 1px); } 100% { transform: translate(-1px, -1px); } }

        .anim-slide-right { animation: slideRight 1s ease-out forwards; opacity: 0; transform: translateX(-50px); }
        @keyframes slideRight { to { opacity: 1; transform: translateX(0); } }

        @keyframes magneticFlow { to { stroke-dashoffset: -20; } }
        .anim-magnetic-flow { stroke-dasharray: 10, 5; animation: magneticFlow 1s linear infinite; }

        /* 电影级运镜系统 - 增强版 (Faster & More Intense) */
        /* transform-box: fill-box ensures we zoom into the CONTENT, not the empty canvas */
        /* Center is (800,450) in Standard Coordinate System */
        .camera-zoom-in { animation: camZoomIn 20s linear forwards; transform-origin: center center; transform-box: fill-box; }
        @keyframes camZoomIn { from { transform: scale(1); } to { transform: scale(1.4); } }

        .camera-zoom-out { animation: camZoomOut 20s linear forwards; transform-origin: center center; transform-box: fill-box; }
        @keyframes camZoomOut { from { transform: scale(1.4); } to { transform: scale(1); } }

        .camera-pan-right { animation: camPanRight 20s linear forwards; transform-origin: center center; transform-box: fill-box; }
        @keyframes camPanRight { from { transform: translateX(0); } to { transform: translateX(-100px); } }
        
        .camera-pan-left { animation: camPanLeft 20s linear forwards; transform-origin: center center; transform-box: fill-box; }
        @keyframes camPanLeft { from { transform: translateX(-100px); } to { transform: translateX(0); } }

        .camera-pan-up { animation: camPanUp 20s linear forwards; transform-origin: center center; transform-box: fill-box; }
        @keyframes camPanUp { from { transform: translateY(0); } to { transform: translateY(-80px); } }

        .camera-float { animation: cam-float 20s ease-in-out infinite; transform-origin: center center; transform-box: fill-box; }
        @keyframes cam-float { 
            0% { transform: translate(0,0) rotate(0deg); } 
            33% { transform: translate(10px, -10px) rotate(1deg); } 
            66% { transform: translate(-5px, 10px) rotate(-1deg); } 
            100% { transform: translate(0,0) rotate(0deg); } 
        }

            /* Object Action Utility Classes */
            .anim-spin-slow { animation: spin 30s linear infinite; transform-origin: center center; transform-box: fill-box; }
            .anim-spin-fast { animation: spin 2s linear infinite; transform-origin: center center; transform-box: fill-box; }
            .anim-bounce { animation: bounce 1s ease-in-out infinite; transform-origin: center center; transform-box: fill-box; }
            .anim-shake { animation: shake 0.5s linear infinite; transform-origin: center center; transform-box: fill-box; }
            .anim-pulse { animation: pulse 2s ease-in-out infinite; transform-origin: center center; transform-box: fill-box; }
            .anim-float { animation: floatObj 3s ease-in-out infinite; transform-origin: center center; transform-box: fill-box; }

            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
            @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
            @keyframes shake { 
                0% { transform: translate(1px, 1px) rotate(0deg); }
                10% { transform: translate(-1px, -2px) rotate(-1deg); }
                20% { transform: translate(-3px, 0px) rotate(1deg); }
                30% { transform: translate(3px, 2px) rotate(0deg); }
                40% { transform: translate(1px, -1px) rotate(1deg); }
                50% { transform: translate(-1px, 2px) rotate(-1deg); }
                60% { transform: translate(-3px, 1px) rotate(0deg); }
                70% { transform: translate(3px, 1px) rotate(-1deg); }
                80% { transform: translate(-1px, -1px) rotate(1deg); }
                90% { transform: translate(1px, 2px) rotate(0deg); }
                100% { transform: translate(1px, -2px) rotate(-1deg); }
            }
            @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }
            @keyframes floatObj { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }

        /* 延迟辅助类 */
        .delay-200 { animation-delay: 0.2s; }
        .delay-500 { animation-delay: 0.5s; }
        .delay-1000 { animation-delay: 1s; }
        .delay-1500 { animation-delay: 1.5s; }
        .delay-2000 { animation-delay: 2s; }
    </style>
"""
    
    cumulative_delay = 0
    for index, frame_data in enumerate(frames):
        delay = cumulative_delay
        current_duration = frame_durations[index]
        svg_content = frame_data["svg"]
        title = frame_data.get("title", f"第{index+1}帧")
        
        # 提取SVG内容（去除外层svg标签）
        import re
        
        # 1. 尝试提取 viewBox 以进行坐标标准化
        viewbox_match = re.search(r'viewBox=["\']([\d\s\.\-,]+)["\']', svg_content, re.IGNORECASE)
        normalization_transform = ""
        
        if viewbox_match:
            try:
                vb_values = [float(x) for x in re.split(r'[\s,]+', viewbox_match.group(1).strip()) if x]
                if len(vb_values) == 4:
                    vx, vy, vw, vh = vb_values
                    target_w, target_h = 1600, 900
                    
                    # 如果 viewBox 与目标尺寸差异较大，或者有偏移，则应用归一化变换
                    # Target is Standard 1600x900 (0,0 to 1600,900)
                    if abs(vw - target_w) > 1 or abs(vh - target_h) > 1 or abs(vx - 0) > 1 or abs(vy - 0) > 1:
                        # 计算缩放比例 (保持纵横比，'meet' 模式，确保内容完整显示)
                        scale_x = target_w / vw
                        scale_y = target_h / vh
                        scale = min(scale_x, scale_y)
                        
                        # 计算居中偏移
                        # We want the visual center of the content to land at (800, 450)
                        # Center of source viewBox: cx = vx + vw/2, cy = vy + vh/2
                        # We map (cx, cy) to (800, 450)
                        # transform = translate(tx, ty) scale(s)
                        # 800 = s * cx + tx  => tx = 800 - s * cx
                        
                        src_cx = vx + vw / 2
                        src_cy = vy + vh / 2
                        
                        tx = 800 - scale * src_cx
                        ty = 450 - scale * src_cy
                        
                        normalization_transform = f'transform="translate({tx:.2f}, {ty:.2f}) scale({scale:.2f})"'
                        print(f"[DEBUG] 帧 {index+1} 坐标标准化: viewBox={vx},{vy},{vw},{vh} -> scale={scale:.3f}, offset=({tx:.1f},{ty:.1f})")
            except Exception as e:
                print(f"[WARN] viewBox 解析失败: {e}")

        content_match = re.search(r'<svg[^>]*?>(.*)</svg>', svg_content, re.DOTALL | re.IGNORECASE)
        if content_match:
            inner_content = content_match.group(1)
        else:
            inner_content = svg_content
            
        # 如果需要标准化，包裹一层 Group
        if normalization_transform:
            inner_content = f'<g class="normalization-wrapper" {normalization_transform}>{inner_content}</g>'
        
        # 智能运镜系统：如果内容中没有检测到运镜类，自动添加
        # 这确保了画面永远不会静止
        camera_class = ""
        if "camera-" not in inner_content:
            # 简单的伪随机选择
            cam_types = ["camera-zoom-in", "camera-zoom-out", "camera-pan-right", "camera-pan-left"]
            camera_class = cam_types[index % len(cam_types)]
            # 包装一层Group来应用运镜
            inner_content = f'<g class="{camera_class}">{inner_content}</g>'
        
        # 为每个分镜添加ID，供JS控制显示
        merged_svg += f"""
        <g class="frame" id="frame-{index}">
            <!-- 分镜内容 -->
            <g>
                {inner_content}
            </g>
        </g>
        """
        
        # 累加当前帧的时长
        cumulative_delay += current_duration
    
    merged_svg += "\n    </svg>"
    return merged_svg.strip()


def _parse_text_to_frames(text: str) -> List[Dict[str, str]]:
    """将 AI 返回的文本描述解析为幻灯片帧"""
    frames = []
    
    # 尝试按数字编号分割（1. 2. 3. 或 一、二、三、等）
    import re
    # 匹配 "1." "2." 或 "一、" "二、" 等格式
    sections = re.split(r'(?:\d+\.|[一二三四五六七八九十]+、)', text)
    sections = [s.strip() for s in sections if s.strip()]
    
    if len(sections) >= 2:
        for i, section in enumerate(sections[:20]):  # 最多20个幻灯片
            lines = section.split('\n', 1)
            heading = lines[0][:30] if lines else f"步骤 {i+1}"
            body = lines[1][:150] if len(lines) > 1 else lines[0][:150]
            frames.append({"heading": heading.strip(), "body": body.strip()})
    
    # 如果解析失败，按段落分割
    if not frames:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        for i, para in enumerate(paragraphs[:15]):
            lines = para.split('\n', 1)
            heading = lines[0][:30] if lines else f"要点 {i+1}"
            body = lines[1][:150] if len(lines) > 1 else para[:150]
            frames.append({"heading": heading.strip(), "body": body.strip()})
    
    return frames if frames else [{"heading": "内容概览", "body": text[:200]}]