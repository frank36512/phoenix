"""
使用 Playwright 渲染 HTML 动画并生成视频

这个模块负责：
1. 启动无头浏览器
2. 加载 HTML 动画页面
3. 按帧捕获动画截图
4. 组合成视频（带音频）
"""

from __future__ import annotations

import os
import time
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARNING] PIL (Pillow) not installed. Text watermark may have font issues.")

try:  # moviepy may not be present until requirements are installed
    # Try moviepy 2.x imports first (top level)
    try:
        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips, AudioClip, concatenate_audioclips, CompositeAudioClip
    except ImportError:
        # Fallback to moviepy 1.x imports
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, AudioClip, concatenate_audioclips, CompositeAudioClip
except Exception as exc:  # noqa: BLE001
    AudioFileClip = None  # type: ignore[assignment]
    ImageClip = None  # type: ignore[assignment]
    concatenate_videoclips = None  # type: ignore[assignment]
    AudioClip = None
    concatenate_audioclips = None
    CompositeAudioClip = None
    _moviepy_error: Optional[Exception] = exc
else:
    _moviepy_error = None

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[WARNING] Playwright not available. Video export will use fallback method.")


def _text_to_image_watermark(config: dict) -> dict:
    """
    将文字水印转换为图片水印，以解决浏览器字体渲染问题 (Mojibake)
    """
    if not PIL_AVAILABLE or config.get("type") != "text" or not config.get("content"):
        return config
        
    try:
        text = config["content"]
        # 估算字体大小: 这里的 size 是相对于屏幕高度的比例
        # 为了保证高清屏下的清晰度，我们使用 4K 分辨率作为基准 (2160p)
        # 这样生成的图片足够大，缩小时会很清晰
        base_height = 2160 
        font_size = int(config.get("size", 0.15) * base_height * 0.3) # 保持原有比例系数
        if font_size < 40: font_size = 40
        
        # 尝试加载中文字体
        font = None
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # Microsoft YaHei
            "C:/Windows/Fonts/msyh.ttf",
            "C:/Windows/Fonts/simhei.ttf", # SimHei
            "C:/Windows/Fonts/simsun.ttc", # SimSun
            "C:/Windows/Fonts/arial.ttf",  # Arial
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except Exception:
                    continue
                    
        if font is None:
            font = ImageFont.load_default()
            print("[WARNING] No suitable font found, using default")
            
        # 计算文本尺寸
        dummy_img = Image.new('RGBA', (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 创建图片 (增加一点 padding)
        padding = 20
        img = Image.new('RGBA', (text_width + padding*2, text_height + padding*2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制文字 (白色，带阴影效果模拟)
        # Shadow
        shadow_color = (0, 0, 0, 150)
        draw.text((padding + 2, padding + 2), text, font=font, fill=shadow_color)
        
        # Main text
        text_color = (255, 255, 255, int(255 * 0.9)) # 0.9 opacity handled by CSS usually, but here baked in
        draw.text((padding, padding), text, font=font, fill=text_color)
        
        # 裁剪图片，去除多余空白，防止显示时比例失调
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        
        # 保存临时文件
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(path)
        
        print(f"[INFO] Converted text watermark to image: {path}")
        
        new_config = config.copy()
        new_config["type"] = "image"
        new_config["content"] = Path(path).absolute().as_uri()
        # 标记这是自动转换的水印，前端注入时需要特殊处理尺寸
        new_config["_is_converted_text"] = True
        return new_config
        
    except Exception as e:
        print(f"[WARNING] Failed to convert text to image: {e}")
        return config


def render_animation_to_video(
    html_path: str,
    audio_path: str,
    output_path: str,
    duration: float = None,
    fps: int = 60,
    width: int = 1920,
    height: int = 1080,
    watermark_config: dict = None,
    background_music: str = None,
    background_music_volume: float = 0.5,
    progress_callback = None
) -> bool:
    """
    渲染 HTML 动画为视频文件（精确同步版）
    
    Args:
        html_path: HTML 动画文件路径
        audio_path: 音频文件路径（MP3）
        output_path: 输出视频路径
        duration: 视频时长（秒），如果为 None 则从音频获取
        fps: 帧率（建议60fps以获得最佳流畅度）
        width: 视频宽度
        height: 视频高度
        watermark_config: 水印配置字典
        background_music: 背景音乐路径
        background_music_volume: 背景音乐音量 (0.0-1.0)
        progress_callback: 进度回调函数 function(percentage: float, message: str)
    
    Returns:
        bool: 是否成功
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[ERROR] Playwright not installed. Cannot render animation.")
        return False
    
    # 获取音频时长
    if duration is None:
        duration = _get_audio_duration(audio_path)
        if duration is None:
            print(f"[WARNING] Cannot get audio duration from {audio_path}, using default 30s")
            duration = 30.0
    
    print(f"[INFO] ===== 视频导出（精确同步模式） =====")
    print(f"[INFO] 动画文件: {html_path}")
    print(f"[INFO] 音频文件: {audio_path}")
    print(f"[INFO] 时长: {duration:.2f}s, FPS: {fps}, 分辨率: {width}x{height}")
    
    # 创建临时帧目录
    temp_dir = Path(output_path).parent / "temp_frames"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 转换文字水印为图片水印
    if watermark_config and watermark_config.get("type") == "text":
        watermark_config = _text_to_image_watermark(watermark_config)
    
    try:
        if "bar_race" in html_path or "mind_map" in html_path or "geo_map" in html_path:
            # 使用慢速平滑录制模式 (适用于 ECharts 动画)
            # 只要是 Bar Race, Mind Map 或 Geo Map，都优先尝试慢速模式
            # 这样可以获得最佳的平滑度
            frame_paths = _capture_frames_slow_motion(
                html_path, temp_dir, fps, width, height, watermark_config, progress_callback, duration
            )
        else:
            # 其他动画使用确定性渲染 (High Quality)
            frame_paths = _capture_frames_deterministic(
                html_path, temp_dir, fps, width, height, watermark_config, progress_callback
            )
        
        if not frame_paths:
            print("[ERROR] 未能捕获帧")
            return False
        
        print(f"[INFO] 已捕获 {len(frame_paths)} 个帧")
        
        # 合成视频和音频
        # 注意：slow_motion 模式下，帧数 = 视频时长 * FPS
        actual_duration = len(frame_paths) / fps
        success = _compose_video_optimized(
            frame_paths, 
            audio_path, 
            output_path, 
            actual_duration,
            background_music,
            background_music_volume,
            progress_callback,
            fps=fps
        )
        
        # 清理临时文件
        _cleanup_temp_frames(temp_dir)
        
        return success
        
    except Exception as e:
        print(f"[ERROR] 视频导出失败: {e}")
        import traceback
        traceback.print_exc()
        _cleanup_temp_frames(temp_dir)
        return False


def _capture_frames_slow_motion(
    html_path: str,
    output_dir: Path,
    fps: int,
    width: int,
    height: int,
    watermark_config: dict = None,
    progress_callback = None,
    duration: float = None
) -> List[Path]:
    """
    慢速录制模式（Smooth Mode）
    
    原理：
    1. 将 HTML 动画速度放慢 N 倍（例如 10 倍）
    2. 在播放过程中高频截图
    3. 这样可以捕获到 ECharts 的平滑过渡动画（Ranking 交换动画）
    4. 最后以正常 FPS 合成视频，实际上起到了“加速回放”的效果，还原了正常速度
    """
    frame_paths = []
    
    # 速度比率：0.05 表示放慢 20 倍 (更慢以确保每帧都足够稳定)
    # 假设目标视频 FPS=60，每帧间隔 16.6ms
    # 在 0.05 倍速下，这 16.6ms 对应现实时间的 333ms
    # Playwright 截图一张约需 100-200ms，所以 333ms 是非常安全的，可以保证绝对流畅
    speed_ratio = 0.05
    
    # 使用传入的 FPS 进行渲染
    render_fps = fps
    
    print(f"[INFO] 启动浏览器进行高帧率慢速平滑录制 (Target FPS={render_fps}, Speed={speed_ratio}x)...")
    
    # 转换文字水印为图片水印
    if watermark_config and watermark_config.get("type") == "text":
        watermark_config = _text_to_image_watermark(watermark_config)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-gpu', '--disable-dev-shm-usage', '--no-sandbox']
        )
        context = browser.new_context(
            viewport={'width': width, 'height': height},
            device_scale_factor=2
        )
        page = context.new_page()
        
        # 加载 HTML 文件
        html_file_url = f"file:///{os.path.abspath(html_path).replace(os.sep, '/')}"
        print(f"[INFO] 加载动画: {os.path.basename(html_path)}")
        page.goto(html_file_url, wait_until='networkidle')
        
        # 注入水印 (复用逻辑)
        if watermark_config and watermark_config.get("enabled"):
            try:
                # 预处理配置
                config = watermark_config.copy()
                if config.get("type") == "image":
                    img_path = config.get("content")
                    if img_path and os.path.exists(img_path):
                        config["content"] = Path(img_path).absolute().as_uri()
                    else:
                        print(f"[WARNING] 水印图片不存在: {img_path}")
                        config["enabled"] = False
                
                if config["enabled"]:
                    print(f"[INFO] 应用水印: {config.get('type')} - {config.get('position')}")
                    page.evaluate("""(config) => {
                        const div = document.createElement('div');
                        div.style.position = 'fixed';
                        div.style.zIndex = '10000';
                        div.style.opacity = config.opacity;
                        div.style.pointerEvents = 'none';
                        
                        // Position
                        const margin = '2%';
                        const pos = config.position;
                        if (pos.includes('top')) div.style.top = margin;
                        if (pos.includes('bottom')) div.style.bottom = margin;
                        if (pos.includes('left')) div.style.left = margin;
                        if (pos.includes('right')) div.style.right = margin;
                        if (pos === 'center') {
                            div.style.top = '50%';
                            div.style.left = '50%';
                            div.style.transform = 'translate(-50%, -50%)';
                        }
                        
                        if (config.type === 'image') {
                            const img = document.createElement('img');
                            img.src = config.content;
                            
                            if (config._is_converted_text) {
                                // 自动转换的文字水印：使用与文字模式一致的缩放逻辑
                                // 文字模式: fontSize = config.size * 30 vh
                                // 图片模式: 高度略大于文字高度 (1.2倍左右)
                                img.style.height = (config.size * 35) + 'vh';
                            } else {
                                // 普通图片水印：维持原有的缩放逻辑 (全屏高度比例)
                                img.style.height = (config.size * 100) + 'vh';
                            }
                            
                            img.style.width = 'auto';
                            img.style.maxWidth = '100vw'; // 防止过宽
                            img.style.objectFit = 'contain'; // 保持纵横比
                            div.appendChild(img);
                        } else {
                            div.textContent = config.content;
                            div.style.fontSize = (config.size * 30) + 'vh';
                            div.style.color = 'rgba(255, 255, 255, 0.9)';
                            div.style.textShadow = '2px 2px 4px rgba(0,0,0,0.6)';
                            div.style.fontFamily = "'Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Arial', sans-serif";
                            div.style.fontWeight = 'bold';
                            div.style.whiteSpace = 'nowrap';
                        }
                        
                        document.body.appendChild(div);
                    }""", config)
            except Exception as e:
                print(f"[WARNING] 添加水印失败: {e}")

        # 等待页面脚本初始化
        time.sleep(1.0)
        
        # 优化页面布局
        page.evaluate("""
            document.body.style.overflow = 'hidden';
            
            // 移除多余的外层容器样式
            const shell = document.querySelector('.shell');
            const panel = document.querySelector('.panel');
            const body = document.body;
            
            if (body) {
                body.style.margin = '0';
                body.style.padding = '0';
                body.style.width = '100vw';
                body.style.height = '100vh';
                body.style.background = 'white'; 
            }
            
            if (shell) {
                shell.style.padding = '0';
                shell.style.margin = '0';
                shell.style.width = '100%';
                shell.style.height = '100%';
                shell.style.display = 'flex';
                shell.style.justifyContent = 'center';
                shell.style.alignItems = 'center';
            }
            
            if (panel) {
                panel.style.margin = '0';
                panel.style.padding = '0';
                panel.style.width = '100%';
                panel.style.height = '100%';
                panel.style.maxWidth = 'none';
                panel.style.borderRadius = '0';
                panel.style.boxShadow = 'none';
                panel.style.background = 'transparent';
            }

            const svg = document.querySelector('svg');
            if (svg) {
                // 移除强制的 maxHeight/maxWidth，防止 ECharts 内容被拉伸
                svg.style.maxHeight = '';
                svg.style.maxWidth = '';
                // 确保 svg 容器铺满，但比例由 ECharts 控制
                svg.style.width = '100%';
                svg.style.height = '100%';
            }
            
            // 触发 ECharts resize，让图表适应新的全屏容器
            if (window.myChart) {
                window.myChart.resize();
            }
        """)
        
        # 1. 启动慢速动画
        print("[INFO] 启动慢速动画...")
        
        # 检查是否支持 startSlowMotionAnimation
        has_function = page.evaluate("typeof window.startSlowMotionAnimation === 'function'")
        
        real_duration_ms = 0
        
        if has_function:
            info = page.evaluate(f"window.startSlowMotionAnimation({speed_ratio})")
            real_duration_ms = info['totalDuration']
        elif duration is not None:
             print("[INFO] 使用指定时长进行录制 (无 startSlowMotionAnimation)")
             # 如果手动指定了 duration，且没有 slow motion 函数，我们假设
             # 页面已经被配置为慢速播放 (例如通过 playInterval / speed_ratio)
             # 或者我们只是进行普通时长的录制（如果是静态页面）
             # 这里我们按照慢速逻辑计算：需录制时长 = duration / speed_ratio
             real_duration_ms = (duration / speed_ratio) * 1000
        else:
            print("[WARNING] 模板不支持慢速录制且未指定时长。回退到确定性渲染。")
            browser.close()
            return _capture_frames_deterministic(html_path, output_dir, fps, width, height, watermark_config, progress_callback)
            
        # 预估总帧数 = 视频时长 * FPS
        # 视频时长 = 真实时长 * speed_ratio
        video_duration_s = (real_duration_ms / 1000.0) * speed_ratio
        total_frames = int(video_duration_s * render_fps)
        
        print(f"[INFO] 预估视频时长: {video_duration_s:.2f}s, 需录制: {real_duration_ms/1000:.1f}s, 总帧数: {total_frames}")
        
        start_time = time.time()
        
        # 计算每一帧的间隔
        # 视频帧间隔 = 1.0 / fps (例如 0.016s @ 60fps)
        # 真实录制间隔 = 视频帧间隔 / speed_ratio (例如 0.016 / 0.05 = 0.33s)
        video_frame_interval = 1.0 / render_fps
        real_frame_interval = video_frame_interval / speed_ratio
        
        next_snapshot_time = start_time + real_frame_interval
        
        for i in range(total_frames + 120): # 多录一点缓冲
            # 等待下一帧时间点
            now = time.time()
            sleep_time = next_snapshot_time - now
            if sleep_time > 0:
                time.sleep(sleep_time)
                
            # 检查动画是否结束
            if has_function and page.evaluate("window.animationFinished"):
                print("[INFO] 动画播放结束")
                break
                
            # 截图
            frame_path = output_dir / f"frame_{i:05d}.png"
            page.screenshot(path=str(frame_path), type='png')
            frame_paths.append(frame_path)
            
            # 更新下一次截图时间
            next_snapshot_time += real_frame_interval
            
            # 进度报告
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                # 录制速度 (Real FPS)
                real_fps = (i + 1) / elapsed
                # 估算剩余时间
                remaining_frames = total_frames - (i + 1)
                remaining_time = remaining_frames / real_fps if real_fps > 0 else 0
                
                # 映射进度 35% - 90%
                base_progress = 35
                total_range = 90 - 35
                progress_ratio = min(1.0, (i + 1) / total_frames)
                current_percent = base_progress + (progress_ratio * total_range)
                
                msg = f"进度: {int(current_percent)}% (录制: {i+1}/{total_frames}), 速度: {real_fps:.1f}fps (x{speed_ratio}), 剩余: {remaining_time:.0f}s"
                print(f"[INFO] {msg}")
                if progress_callback:
                    progress_callback(int(current_percent), msg)
            
        browser.close()
        
    return frame_paths


def _capture_frames_deterministic(
    html_path: str,
    output_dir: Path,
    fps: int,
    width: int,
    height: int,
    watermark_config: dict = None,
    progress_callback = None
) -> List[Path]:
    """
    确定性帧捕获（High Quality）
    
    原理：
    不依赖实时播放，而是通过 window.seekTo(time) 精确控制每一帧的状态。
    这保证了：
    1. 零掉帧
    2. 完美的音画同步
    3. CSS/SVG 动画精确对齐
    4. 不受机器性能影响（渲染慢只会导致导出慢，不会导致视频卡顿）
    """
    frame_paths = []
    
    print(f"[INFO] 启动浏览器进行高精度渲染 (FPS={fps})...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-gpu', '--disable-dev-shm-usage', '--no-sandbox']
        )
        context = browser.new_context(
            viewport={'width': width, 'height': height},
            device_scale_factor=2
        )
        page = context.new_page()
        
        # 加载 HTML 文件
        html_file_url = f"file:///{os.path.abspath(html_path).replace(os.sep, '/')}"
        print(f"[INFO] 加载动画: {os.path.basename(html_path)}")
        page.goto(html_file_url, wait_until='networkidle')
        
        # 注入水印
        if watermark_config and watermark_config.get("enabled"):
            try:
                # 预处理配置
                config = watermark_config.copy()
                if config.get("type") == "image":
                    img_path = config.get("content")
                    if img_path and os.path.exists(img_path):
                        config["content"] = Path(img_path).absolute().as_uri()
                    else:
                        print(f"[WARNING] 水印图片不存在: {img_path}")
                        config["enabled"] = False
                
                if config["enabled"]:
                    print(f"[INFO] 应用水印: {config.get('type')} - {config.get('position')}")
                    page.evaluate("""(config) => {
                        const div = document.createElement('div');
                        div.style.position = 'fixed';
                        div.style.zIndex = '10000';
                        div.style.opacity = config.opacity;
                        div.style.pointerEvents = 'none';
                        
                        // Position
                        const margin = '2%';
                        const pos = config.position;
                        if (pos.includes('top')) div.style.top = margin;
                        if (pos.includes('bottom')) div.style.bottom = margin;
                        if (pos.includes('left')) div.style.left = margin;
                        if (pos.includes('right')) div.style.right = margin;
                        if (pos === 'center') {
                            div.style.top = '50%';
                            div.style.left = '50%';
                            div.style.transform = 'translate(-50%, -50%)';
                        }
                        
                        if (config.type === 'image') {
                            const img = document.createElement('img');
                            img.src = config.content;
                            
                            if (config._is_converted_text) {
                                img.style.height = (config.size * 35) + 'vh';
                            } else {
                                img.style.height = (config.size * 100) + 'vh';
                            }
                            
                            img.style.width = 'auto';
                            img.style.maxWidth = '100vw';
                            img.style.objectFit = 'contain';
                            div.appendChild(img);
                        } else {
                            div.textContent = config.content;
                            // 文字大小: size * 30 (vh) - 0.15 -> 4.5vh (~48px)
                            div.style.fontSize = (config.size * 30) + 'vh';
                            div.style.color = 'rgba(255, 255, 255, 0.9)';
                            div.style.textShadow = '2px 2px 4px rgba(0,0,0,0.6)';
                            div.style.fontFamily = "'Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Arial', sans-serif";
                            div.style.fontWeight = 'bold';
                            div.style.whiteSpace = 'nowrap';
                        }
                        
                        document.body.appendChild(div);
                    }""", config)
            except Exception as e:
                print(f"[WARNING] 添加水印失败: {e}")

        # 等待页面脚本初始化
        time.sleep(1.0)
        
        # 1. 准备时间轴
        print("[INFO] 正在预计算时间轴...")
        timeline_data = page.evaluate("""
            async () => {
                if (window.prepareTimeline) {
                    return await window.prepareTimeline();
                }
                return null;
            }
        """)
        
        if not timeline_data:
            print("[ERROR] 页面未实现 window.prepareTimeline，无法使用确定性渲染")
            browser.close()
            return []
            
        total_duration_ms = timeline_data['totalDuration'];
        total_frames = int((total_duration_ms / 1000.0) * fps);
        
        print(f"[INFO] 时间轴准备完成: 总时长 {total_duration_ms/1000:.2f}s, 预计帧数 {total_frames}")
        
        # 优化页面布局
        page.evaluate("""
            document.body.style.overflow = 'hidden';
            
            // 移除多余的外层容器样式，让.panel填满视口
            const shell = document.querySelector('.shell');
            const panel = document.querySelector('.panel');
            const body = document.body;
            
            if (body) {
                    body.style.margin = '0';
                    body.style.padding = '0';
                    body.style.width = '100vw';
                    body.style.height = '100vh';
                    body.style.overflow = 'hidden';
                    body.style.boxSizing = 'border-box';
                    body.style.background = 'white'; // 视频背景设为白色
                }
            
            if (shell) {
                shell.style.padding = '20px'; // 增加内边距，防止内容贴边
                shell.style.margin = '0';
                shell.style.width = '100%';
                shell.style.height = '100%';
                shell.style.display = 'flex';
                shell.style.justifyContent = 'center';
                shell.style.alignItems = 'center';
                shell.style.boxSizing = 'border-box';
            }
            
            if (panel) {
                panel.style.margin = '0';
                panel.style.padding = '0';
                panel.style.width = '100%';
                panel.style.height = '100%';
                panel.style.maxWidth = 'none';
                panel.style.borderRadius = '0';
                panel.style.boxShadow = 'none';
                panel.style.background = 'transparent'; // 透明背景，显示body的黑色或SVG背景
            }

            // 确保SVG填满但不过分拉伸
            const svg = document.querySelector('svg');
            if (svg) {
                // 移除强制的 maxHeight/maxWidth，防止 ECharts 内容被拉伸
                svg.style.maxHeight = '';
                svg.style.maxWidth = '';
                svg.style.width = '100%';
                svg.style.height = '100%';
            }
            
            // 触发 ECharts resize
            if (window.myChart) {
                window.myChart.resize();
            }
        """)
        
        start_time = time.time()
        
        # 2. 逐帧渲染
        for i in range(total_frames):
            time_ms = (i / fps) * 1000;
            
            # 跳转到指定时间点
            page.evaluate(f"window.seekTo({time_ms})")
            
            # 截图
            frame_path = output_dir / f"frame_{i:05d}.png"
            # 使用 jpeg 稍微快一点，且质量尚可 (quality=90) -> 但 PNG 更清晰，这里追求质量用 PNG
            page.screenshot(path=str(frame_path), type='png')
            frame_paths.append(frame_path)
            
            if (i + 1) % 30 == 0:
                elapsed = time.time() - start_time
                speed = (i + 1) / elapsed
                remaining = (total_frames - (i + 1)) / speed
                
                # 将进度映射到 35% - 90% 的区间
                base_progress = 35
                total_range = 90 - 35
                current_percent = base_progress + ((i+1)/total_frames * total_range)
                
                # 优化提示信息：显示总进度与渲染进度的关系，避免混淆
                # 之前是: 进度: 54.9% (渲染进度) ... 但进度条是 37% (全局进度)
                msg = f"进度: {int(current_percent)}% (渲染: {(i+1)/total_frames*100:.1f}%, {i+1}/{total_frames}), 速度: {speed:.1f}fps, 剩余: {remaining:.0f}s"
                print(f"[INFO] {msg}")
                
                if progress_callback:
                    progress_callback(int(current_percent), msg)
                
        browser.close()
        
    return frame_paths


def _capture_keyframes_fast(
    html_path: str,
    output_dir: Path,
    duration: float,
    width: int,
    height: int
) -> List[Path]:
    """
    快速捕获关键帧（优化版：暂停CSS动画，直接跳转到关键时间点）
    
    策略：
    - 暂停所有CSS动画
    - 使用animation-delay直接跳转到目标时间点
    - 每个关键帧只需0.2秒（不需要等待真实动画时长）
    """
    frame_paths = []
    keyframe_interval = 0.1  # 每0.1秒一个关键帧，确保流畅过渡 (10 FPS)
    num_keyframes = max(5, int(duration / keyframe_interval) + 1)
    
    print(f"[INFO] 启动浏览器进行快速截图（{num_keyframes} 个关键帧）...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-gpu', '--disable-dev-shm-usage', '--no-sandbox']
        )
        context = browser.new_context(
            viewport={'width': width, 'height': height},
            device_scale_factor=2
        )
        page = context.new_page()
        
        # 加载 HTML 文件
        html_file_url = f"file:///{os.path.abspath(html_path).replace(os.sep, '/')}"
        print(f"[INFO] 加载动画: {os.path.basename(html_path)}")
        page.goto(html_file_url, wait_until='networkidle')
        time.sleep(0.3)  # 等待动画初始化
        
        # 优化页面布局，使动画内容填满视口
        page.evaluate("""
            (function() {
                // 移除多余的外层容器样式，让.panel填满视口
                const shell = document.querySelector('.shell');
                const panel = document.querySelector('.panel');
                const body = document.body;
                
                if (body) {
                    body.style.margin = '0';
                    body.style.padding = '0';
                    body.style.width = '100vw';
                    body.style.height = '100vh';
                    body.style.overflow = 'hidden';
                    body.style.boxSizing = 'border-box';
                    body.style.background = 'white'; // 统一使用白色背景
                }
                
                if (shell) {
                    shell.style.padding = '20px'; // 增加内边距
                    shell.style.margin = '0';
                    shell.style.width = '100%';
                    shell.style.height = '100%';
                    shell.style.display = 'flex';
                    shell.style.justifyContent = 'center';
                    shell.style.alignItems = 'center';
                    shell.style.boxSizing = 'border-box';
                }
                
                if (panel) {
                    panel.style.margin = '0';
                    panel.style.padding = '0';
                    panel.style.width = '100%';
                    panel.style.height = '100%';
                    panel.style.maxWidth = 'none';
                    panel.style.borderRadius = '0';
                    panel.style.boxShadow = 'none';
                    panel.style.background = 'transparent'; // 透明背景
                }
                
                // 确保字幕容器位于可见区域底部
                const subtitleContainer = document.querySelector('.subtitle-container');
                if (subtitleContainer) {
                    subtitleContainer.style.position = 'absolute';
                    subtitleContainer.style.bottom = '8%'; // 稍微下调至 8%
                    subtitleContainer.style.left = '50%';
                    subtitleContainer.style.transform = 'translateX(-50%)';
                    subtitleContainer.style.width = '85%';
                    subtitleContainer.style.maxWidth = '900px';
                    subtitleContainer.style.zIndex = '10000';
                }
            })();
        """)
        
        time.sleep(0.2)  # 等待布局调整
        
        print(f"[INFO] 开始快速截图（控制CSS动画时间轴）...")
        start_time = time.time()
        
        # 在关键时间点截图
        for i in range(num_keyframes):
            target_time = i * keyframe_interval
            
            # 使用JavaScript控制CSS动画时间
            # 暂停所有动画并设置到目标时间点
            page.evaluate(f"""
                (function() {{
                    const allElements = document.querySelectorAll('*');
                    allElements.forEach(el => {{
                        const style = window.getComputedStyle(el);
                        if (style.animationName && style.animationName !== 'none') {{
                            el.style.animationPlayState = 'paused';
                            el.style.animationDelay = '-{target_time}s';
                        }}
                    }});
                }})();
            """)
            
            # 等待渲染稳定
            time.sleep(0.15)
            
            # 截图整个视口（已经调整为只显示动画内容）
            frame_path = output_dir / f"keyframe_{i:04d}.png"
            page.screenshot(path=str(frame_path), type='png', full_page=False)
            frame_paths.append(frame_path)
            
            if (i + 1) % 3 == 0 or i == num_keyframes - 1:
                progress = (i + 1) / num_keyframes * 100
                elapsed = time.time() - start_time
                print(f"[INFO] 截图进度: {progress:.0f}% ({i + 1}/{num_keyframes}), 已耗时: {elapsed:.1f}秒")
        
        actual_time = time.time() - start_time
        print(f"[INFO] 截图完成，总耗时: {actual_time:.1f}秒")
        
        browser.close()
    
    return frame_paths


def _capture_animation_frames(
    html_path: str,
    output_dir: Path,
    duration: float,
    fps: int,
    width: int,
    height: int
) -> List[Path]:
    """
    使用 Playwright 精确捕获动画帧
    
    改进：
    1. 使用固定时间间隔而不是实时捕获
    2. 每帧之间严格等待，避免漂移
    3. 确保捕获的帧数精确匹配目标
    """
    frame_paths = []
    target_fps = 30  # 使用固定30fps
    total_frames = int(duration * target_fps)
    frame_interval = 1.0 / target_fps  # 秒
    
    print(f"[INFO] 开始捕获 {total_frames} 帧 @ {target_fps}fps...")
    print(f"[INFO] 帧间隔: {frame_interval*1000:.1f}ms")
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-sandbox',
                '--disable-web-security'  # 避免CORS问题
            ]
        )
        context = browser.new_context(
            viewport={'width': width, 'height': height},
            device_scale_factor=2
        )
        page = context.new_page()
        
        # 加载 HTML 文件
        html_file_url = f"file:///{os.path.abspath(html_path).replace(os.sep, '/')}"
        print(f"[INFO] 加载动画: {html_file_url}")
        page.goto(html_file_url)
        
        # 等待页面完全加载
        page.wait_for_load_state('networkidle')
        page.wait_for_load_state('domcontentloaded')
        time.sleep(1.5)  # 额外等待以确保CSS动画初始化
        
        # 查找动画容器元素（.panel）
        try:
            # 注入样式以确保全屏录制
            page.evaluate("""
                document.body.style.margin = '0';
                document.body.style.padding = '0';
                document.body.style.background = 'white';
                const panel = document.querySelector('.panel');
                if (panel) {
                    panel.style.margin = '0';
                    panel.style.padding = '0';
                    panel.style.width = '100vw';
                    panel.style.height = '100vh';
                    panel.style.maxWidth = 'none';
                    panel.style.borderRadius = '0';
                    panel.style.background = 'white';
                    panel.style.boxShadow = 'none';
                }
            """)
            
            panel_element = page.query_selector('.panel')
            if not panel_element:
                print("[WARNING] 未找到 .panel 元素，将截取整个页面")
                panel_element = None
        except:
            panel_element = None
        
        print(f"[INFO] 页面加载完成，开始捕获帧...")
        
        start_time = time.time()
        
        # 按固定时间间隔捕获帧
        for frame_idx in range(total_frames):
            # 截图（只截取动画容器）
            frame_path = output_dir / f"frame_{frame_idx:06d}.png"
            if panel_element:
                panel_element.screenshot(path=str(frame_path), type='png')
            else:
                page.screenshot(path=str(frame_path), type='png')
            frame_paths.append(frame_path)
            
            # 进度显示
            if (frame_idx + 1) % 30 == 0 or frame_idx == total_frames - 1:
                progress = (frame_idx + 1) / total_frames * 100
                elapsed = time.time() - start_time
                print(f"[INFO] 进度: {progress:.1f}% ({frame_idx + 1}/{total_frames}), 耗时: {elapsed:.2f}s")
            
            # 等待到下一帧的时间点（精确控制）
            if frame_idx < total_frames - 1:
                target_time = start_time + (frame_idx + 1) * frame_interval
                current_time = time.time()
                wait_time = target_time - current_time
                if wait_time > 0:
                    time.sleep(wait_time)
        
        actual_time = time.time() - start_time
        print(f"[INFO] 捕获完成，总耗时: {actual_time:.1f}s")
        
        browser.close()
    
    print(f"[INFO] 已捕获 {len(frame_paths)} 帧")
    return frame_paths


def _compose_video_optimized(
    frame_paths: List[Path],
    audio_path: str,
    output_path: str,
    duration: float,
    background_music: str = None,
    background_music_volume: float = 0.3,
    progress_callback = None,
    fps: int = 30
) -> bool:
    """
    优化的视频合成（精确同步模式）
    
    关键改进：
    1. 使用固定FPS（30fps）确保时间基准一致
    2. 严格按照音频时长设置视频时长
    3. 避免帧率不匹配导致的累积误差
    """
    try:
        # MoviePy Compatibility
        try:
            from moviepy import ImageSequenceClip, AudioFileClip
            is_v2 = True
        except ImportError:
            from moviepy.editor import ImageSequenceClip, AudioFileClip
            is_v2 = False
        
        print(f"[INFO] 合成视频（{len(frame_paths)} 帧）...")
        
        # 使用传入的FPS
        target_fps = fps
        
        # 如果有音频，优先使用音频时长，但如果视频帧更多，则保留视频帧
        audio_clip = None
        actual_duration = duration
        
        # 计算捕获的视频帧对应的时长
        captured_video_duration = len(frame_paths) / target_fps
        
        if os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            print(f"[INFO] 音频时长: {audio_clip.duration:.2f}s, 捕获视频时长: {captured_video_duration:.2f}s")
            
            # 策略：取两者中较长的那个作为最终时长
            # 这样可以防止：
            # 1. 音频比视频短时，视频被截断（当前问题）
            # 2. 视频比音频短时，音频被截断（虽然较少见，但也应防止）
            actual_duration = max(audio_clip.duration, captured_video_duration)
        else:
            print(f"[WARNING] 音频文件不存在: {audio_path}")
            actual_duration = captured_video_duration
        
        # 计算需要的总帧数
        required_frames = int(actual_duration * target_fps)
        
        # 如果捕获的帧数不足（且差距较大），补充帧
        if len(frame_paths) < required_frames - 5: # 允许5帧误差
            print(f"[INFO] 补充帧: {len(frame_paths)} -> {required_frames}")
            last_frame = frame_paths[-1]
            frame_paths.extend([last_frame] * (required_frames - len(frame_paths)))
        # 如果帧数过多（且差距较大），裁剪
        elif len(frame_paths) > required_frames + 5:
            print(f"[INFO] 裁剪帧: {len(frame_paths)} -> {required_frames}")
            frame_paths = frame_paths[:required_frames]
        
        # 创建视频片段，使用固定fps
        video_clip = ImageSequenceClip(
            [str(p) for p in frame_paths],
            fps=target_fps
        )
        
        # 处理背景音乐
        bg_music_clip = None
        if background_music and os.path.exists(background_music):
            try:
                bg_music_clip = AudioFileClip(background_music)
                
                # 简单循环逻辑：如果音乐比视频短，则重复
                if bg_music_clip.duration < actual_duration:
                    loop_count = int(actual_duration / bg_music_clip.duration) + 1
                    # 需要 concatenate_audioclips
                    if concatenate_audioclips:
                        bg_music_clip = concatenate_audioclips([bg_music_clip] * loop_count)
                
                # 裁剪到视频长度
                if is_v2:
                    bg_music_clip = bg_music_clip.subclipped(0, actual_duration)
                    bg_music_clip = bg_music_clip.with_volume_scaled(background_music_volume)
                else:
                    bg_music_clip = bg_music_clip.subclip(0, actual_duration)
                    bg_music_clip = bg_music_clip.volumex(background_music_volume)
                
                print(f"[INFO] 已添加背景音乐: {os.path.basename(background_music)} (音量: {background_music_volume})")
            except Exception as e:
                print(f"[WARNING] 加载背景音乐失败: {e}")
                bg_music_clip = None

        # 混合音频
        final_audio = None
        if audio_clip and bg_music_clip:
            # 混合两者 (TTS + BGM)
            if CompositeAudioClip:
                final_audio = CompositeAudioClip([bg_music_clip, audio_clip])
            else:
                print("[WARNING] CompositeAudioClip不可用，仅使用主音频")
                final_audio = audio_clip
        elif audio_clip:
            final_audio = audio_clip
        elif bg_music_clip:
            final_audio = bg_music_clip

        # 设置最终视频时长
        if is_v2:
            video_clip = video_clip.with_duration(actual_duration)
            if final_audio:
                final_clip = video_clip.with_audio(final_audio)
            else:
                final_clip = video_clip
        else:
            video_clip = video_clip.set_duration(actual_duration)
            if final_audio:
                final_clip = video_clip.set_audio(final_audio)
            else:
                final_clip = video_clip
                
        print(f"[INFO] 最终视频时长: {video_clip.duration:.2f}s")
        
        # 输出视频，使用固定参数确保同步
        print(f"[INFO] 写入视频文件...")
        
        if progress_callback:
            progress_callback(92, "正在合成视频 (这可能需要几分钟)...")
            
        final_clip.write_videofile(
            output_path,
            fps=target_fps,  # 输出也使用30fps
            codec='libx264',
            audio_codec='aac',
            preset='slow',  # 使用慢速预设以获得更好压缩率
            threads=4,
            ffmpeg_params=['-crf', '18'],  # 使用 CRF 18 (视觉无损) 代替固定码率
            logger=None
        )
        
        # 清理资源
        final_clip.close()
        if audio_clip:
            audio_clip.close()
        if bg_music_clip:
            bg_music_clip.close()
        video_clip.close()
        
        print(f"[SUCCESS] 视频导出成功: {output_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 视频合成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def _compose_video(
    frame_paths: List[Path],
    audio_path: str,
    output_path: str,
    fps: int
) -> bool:
    """组合帧和音频为视频"""
    try:
        # MoviePy Compatibility
        try:
            from moviepy import ImageSequenceClip, AudioFileClip
            is_v2 = True
        except ImportError:
            from moviepy.editor import ImageSequenceClip, AudioFileClip
            is_v2 = False
        
        print(f"[INFO] Composing video from {len(frame_paths)} frames...")
        
        # 创建视频片段
        video_clip = ImageSequenceClip([str(p) for p in frame_paths], fps=fps)
        
        # 加载音频
        if os.path.exists(audio_path):
            audio_clip = AudioFileClip(audio_path)
            
            # 确保视频和音频时长匹配
            if video_clip.duration > audio_clip.duration:
                if is_v2:
                    video_clip = video_clip.subclipped(0, audio_clip.duration)
                else:
                    video_clip = video_clip.subclip(0, audio_clip.duration)
            elif video_clip.duration < audio_clip.duration:
                if is_v2:
                    audio_clip = audio_clip.subclipped(0, video_clip.duration)
                else:
                    audio_clip = audio_clip.subclip(0, video_clip.duration)
            
            # 合并音频
            if is_v2:
                final_clip = video_clip.with_audio(audio_clip)
            else:
                final_clip = video_clip.set_audio(audio_clip)
        else:
            print(f"[WARNING] Audio file not found: {audio_path}, creating video without audio")
            final_clip = video_clip
        
        # 输出视频
        output_path = str(output_path)
        print(f"[INFO] Writing video to: {output_path}")
        
        final_clip.write_videofile(
            output_path,
            fps=fps,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            preset='slow',
            ffmpeg_params=['-crf', '18'],
            logger=None  # 减少日志输出
        )
        
        print(f"[INFO] Video created successfully: {output_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to compose video: {e}")
        import traceback
        traceback.print_exc()
        return False


def _get_audio_duration(audio_path: str) -> float:
    """获取音频时长（秒）"""
    try:
        try:
            from moviepy import AudioFileClip
        except ImportError:
            from moviepy.editor import AudioFileClip
            
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        audio.close()
        return duration
    except Exception as e:
        print(f"[WARNING] Cannot get audio duration: {e}")
        return None


def _cleanup_temp_frames(temp_dir: Path):
    """清理临时帧文件"""
    try:
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"[INFO] Cleaned up temporary frames: {temp_dir}")
    except Exception as e:
        print(f"[WARNING] Failed to cleanup temp frames: {e}")
