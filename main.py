# -*- coding: utf-8 -*-
"""
小凤知识可视化系统 (Phoenix) - 纯Python桌面GUI版本
使用PyQt6构建原生桌面应用
"""

from __future__ import annotations

import sys
import os
import tempfile
import json
import re
import math
import asyncio
import threading
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QTabWidget,
    QDialog, QFormLayout, QComboBox, QCheckBox, QSpinBox,
    QMessageBox, QProgressBar, QGroupBox, QSplitter, QTextBrowser,
    QSizePolicy, QScrollArea, QDialogButtonBox, QListView,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QSlider,
    QFileDialog, QDoubleSpinBox, QStackedWidget, QAbstractItemView,
    QFrame, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QDesktopServices, QFontDatabase
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    print("[警告] PyQt6-WebEngine未安装，将使用浏览器打开预览")

try:
    from .core.orchestrator import VisualizationOrchestrator
    from .core.media import MediaComposer, VideoSettings
    from .core.utils import ensure_dir
    from .llm.client import LLMClient
    from .storage.cache import ResourceCache
except ImportError:
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.append(str(CURRENT_DIR))
    from core.orchestrator import VisualizationOrchestrator
    from core.media import MediaComposer, VideoSettings
    from core.utils import ensure_dir
    from llm.client import LLMClient
    from storage.cache import ResourceCache


BASE_DIR = Path(__file__).parent
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)

RESOURCE_DIR = BASE_DIR / "resources"
OFFLINE_DIR = RESOURCE_DIR / "offline"
CREDENTIALS = BASE_DIR / "credentials.json"
SETTINGS_FILE = BASE_DIR / "settings.json"


class Logger(object):
    """日志重定向器"""
    def __init__(self, filename="phoenix.log"):
        self.terminal = sys.stdout
        self.log_path = BASE_DIR / filename
        self.log = open(self.log_path, "w", encoding="utf-8", buffering=1) # Line buffered

    def write(self, message):
        try:
            # 写入终端
            if self.terminal:
                self.terminal.write(message)
                self.terminal.flush()
            # 写入文件
            if self.log:
                self.log.write(message)
                self.log.flush()
        except Exception:
            pass

    def flush(self):
        try:
            if self.terminal:
                self.terminal.flush()
            if self.log:
                self.log.flush()
        except Exception:
            pass

    def close(self):
        if self.log:
            self.log.close()


@dataclass
class AppSettings:
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    api_model: str = "gpt-4o-mini"
    api_is_default: bool = True  # 是否为默认API
    video_resolution: str = "1080p"
    include_audio: bool = True
    slide_duration: int = 6
    fps: int = 30
    tts_engine: str = "edge_tts"  # 默认TTS接口: Microsoft Edge TTS
    tts_is_default: bool = True  # 是否为默认TTS引擎
    edge_voice_zh: str = "zh-CN-XiaoxiaoNeural"  # Edge默认中文语音
    edge_voice_en: str = "en-US-JennyNeural"     # Edge默认英文语音
    edge_rate: str = "+0%"
    edge_pitch: str = "+0Hz"
    edge_volume: str = "+0%"
    tts_model: str = ""  # qwen3-tts-flash等自定义TTS模型
    # qwen3-tts-flash专用配置
    qwen_api_key: str = ""
    qwen_api_base: str = "https://dashscope.aliyuncs.com/api/v1"
    qwen_voice_zh: str = "Cherry"  # Qwen默认中文语音
    qwen_voice_en: str = "Sophia"  # Qwen默认英文语音
    qwen_language: str = "Chinese"

    # 自定义TTS配置 (OpenAI兼容接口)
    custom_api_key: str = ""
    custom_api_base: str = ""
    custom_model: str = ""
    custom_voice_zh: str = "alloy"  # Custom默认中文
    custom_voice_en: str = "alloy"  # Custom默认英文

    # 水印设置
    watermark_enabled: bool = False
    watermark_type: str = "text"  # "text" or "image"
    watermark_content: str = ""  # 文字内容或图片路径
    watermark_position: str = "top_right"  # "top_left", "top_right", "bottom_left", "bottom_right", "center"
    watermark_opacity: float = 0.8
    watermark_size: float = 0.15  # 相对高度(图片)或字体大小因子(文字)

    @classmethod
    def load(cls):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return cls(**data)
            except:
                pass
        return cls()
    
    def to_video_settings(self) -> "VideoSettings":
        from core.media import VideoSettings
        
        # 确定使用的语音
        selected_voice = ""
        if self.tts_engine == "edge_tts":
             selected_voice = self.edge_voice_zh
        elif self.tts_engine == "qwen3-tts-flash":
             selected_voice = self.qwen_voice_zh # 默认用中文语音
        elif self.tts_engine == "custom":
             selected_voice = self.custom_voice_zh
        
        return VideoSettings(
            resolution=self.video_resolution,
            include_audio=self.include_audio,
            fps=self.fps,
            slide_duration=float(self.slide_duration),
            voice=selected_voice,
            voice_provider=self.tts_engine,
            watermark_enabled=self.watermark_enabled,
            watermark_type=self.watermark_type,
            watermark_content=self.watermark_content,
            watermark_position=self.watermark_position,
            watermark_opacity=self.watermark_opacity,
            watermark_size=self.watermark_size
        )

    def save(self):
        ensure_dir(SETTINGS_FILE.parent)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.__dict__, f, indent=2, ensure_ascii=False)


class GenerationThread(QThread):
    """后台生成线程"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    # 用于请求人工复核: (svg_code, storyboard, event_object)
    review_requested = pyqtSignal(str, object, object)
    
    def __init__(self, orchestrator, llm_client, topic, settings, mode="animation", content=None, custom_prompt=None, manual_review=False, language="zh", frame_count=8, text_length=0):
        super().__init__()
        self.orchestrator = orchestrator
        self.llm_client = llm_client
        self.topic = topic
        self.settings = settings
        self.mode = mode
        self.content = content
        self.custom_prompt = custom_prompt
        self.manual_review = manual_review
        self.language = language
        self.frame_count = frame_count
        self.text_length = text_length
        self.review_results = None
    
    async def _handle_review(self, svg, storyboard):
        """处理复核回调"""
        self.progress.emit("等待人工复核生成内容...")
        event = threading.Event()
        self.review_results = None
        
        # 发送信号到主线程显示对话框
        self.review_requested.emit(svg, storyboard, event)
        
        # 阻塞等待主线程处理完毕
        event.wait()
        
        if self.review_results:
             self.progress.emit("人工复核完成，继续生成...")
             return self.review_results
        else:
             self.progress.emit("人工复核未修改或取消，继续使用原内容...")
             return None, None

    def run(self):
        try:
            self.progress.emit(f"正在生成 '{self.topic}' 的{'思维导图' if self.mode == 'mindmap' else '可视化'}...")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if self.mode == "mindmap":
                result = loop.run_until_complete(
                    self.orchestrator.build_mindmap_bundle(
                        topic=self.topic,
                        history=[],
                        llm_client=self.llm_client,
                        content=self.content,
                        language=self.language,
                        max_node_length=self.text_length
                    )
                )
                # 标记结果类型
                if result:
                    result["type"] = "mindmap"
            elif self.mode == "bar_race":
                self.progress.emit(f"正在生成 '{self.topic}' 的动态排序图...")
                result = loop.run_until_complete(
                    self.orchestrator.build_bar_race_bundle(
                        topic=self.topic,
                        history=[],
                        llm_client=self.llm_client,
                        content=self.content,
                        language=self.language
                    )
                )
                if result:
                    result["type"] = "bar_race"
            elif self.mode == "geo_map":
                self.progress.emit(f"正在生成 '{self.topic}' 的地理数据可视化...")
                result = loop.run_until_complete(
                    self.orchestrator.build_geo_map_bundle(
                        topic=self.topic,
                        history=[],
                        llm_client=self.llm_client,
                        content=self.content,
                        language=self.language
                    )
                )
                if result:
                    result["type"] = "geo_map"
            else:
                # 默认动画模式
                # 显示当前使用的TTS引擎
                tts_engine = self.settings.tts_engine
                
                # 根据语言和设置自动选择合适的语音
                selected_voice = ""
                
                if tts_engine == "edge_tts":
                    if self.language == "en":
                        selected_voice = self.settings.edge_voice_en
                        if not selected_voice: selected_voice = "en-US-JennyNeural"
                        msg = f"检测到英文生成模式，使用Edge英文配音: {selected_voice}"
                    else:
                        selected_voice = self.settings.edge_voice_zh
                        if not selected_voice: selected_voice = "zh-CN-XiaoxiaoNeural"
                        msg = f"检测到中文生成模式，使用Edge中文配音: {selected_voice}"
                    self.progress.emit(msg)
                        
                elif tts_engine == "qwen3-tts-flash":
                    if self.language == "en":
                        selected_voice = self.settings.qwen_voice_en
                        if not selected_voice: selected_voice = "Sophia"
                        msg = f"检测到英文生成模式，使用Qwen英文配音: {selected_voice}"
                    else:
                        selected_voice = self.settings.qwen_voice_zh
                        if not selected_voice: selected_voice = "Cherry"
                        msg = f"检测到中文生成模式，使用Qwen中文配音: {selected_voice}"
                    self.progress.emit(msg)

                elif tts_engine == "custom":
                    if self.language == "en":
                        selected_voice = self.settings.custom_voice_en
                        if not selected_voice: selected_voice = "alloy"
                        msg = f"检测到英文生成模式，使用自定义TTS英文配音: {selected_voice}"
                    else:
                        selected_voice = self.settings.custom_voice_zh
                        if not selected_voice: selected_voice = "alloy"
                        msg = f"检测到中文生成模式，使用自定义TTS中文配音: {selected_voice}"
                    self.progress.emit(msg)

                if tts_engine == "qwen3-tts-flash":
                    print(f"[TTS配置] 当前使用: Qwen3-TTS-Flash (API: {self.settings.qwen_api_base}, 语音: {selected_voice})")
                elif tts_engine == "edge_tts":
                    print(f"[TTS配置] 当前使用: Microsoft Edge TTS (语音: {selected_voice})")
                elif tts_engine == "custom":
                    print(f"[TTS配置] 当前使用: 自定义TTS (API: {self.settings.custom_api_base}, Model: {self.settings.custom_model})")
                
                # 如果开启了人工复核，传入回调函数
                review_callback = self._handle_review if self.manual_review else None
                
                # 准备TTS配置
                qwen_lang = "Chinese" # Default
                if self.language == "en":
                    qwen_lang = "English"
                elif self.language == "zh":
                    qwen_lang = "Chinese"
                
                tts_config = {
                    "edge_voice": selected_voice if tts_engine == "edge_tts" else self.settings.edge_voice_zh,
                    "edge_rate": self.settings.edge_rate,
                    "edge_pitch": self.settings.edge_pitch,
                    "edge_volume": self.settings.edge_volume,
                    "qwen_api_key": self.settings.qwen_api_key,
                    "qwen_api_base": self.settings.qwen_api_base,
                    "qwen_voice": selected_voice if tts_engine == "qwen3-tts-flash" else self.settings.qwen_voice_zh,
                    "qwen_language": qwen_lang,
                    "custom_api_key": self.settings.custom_api_key,
                    "custom_api_base": self.settings.custom_api_base,
                    "custom_model": self.settings.custom_model,
                    "custom_voice": selected_voice if tts_engine == "custom" else self.settings.custom_voice_zh,
                }
                
                result = loop.run_until_complete(
                    self.orchestrator.build_online_bundle(
                        topic=self.topic,
                        history=[],  # 对话历史
                        llm_client=self.llm_client,
                        tts_engine=self.settings.tts_engine,
                        voice=selected_voice,
                        tts_config=tts_config,
                        content=self.content,
                        custom_prompt=self.custom_prompt,
                        review_callback=review_callback,
                        language=self.language,
                        frame_count=self.frame_count
                    )
                )
                if result:
                    result["type"] = "animation"
            
            loop.close()
            
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("生成失败: 未返回结果")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"生成线程错误:\n{error_details}")
            self.error.emit(f"生成失败: {str(e)}")




class ContentReviewDialog(QDialog):
    """生成内容人工复核对话框"""
    def __init__(self, svg_code, storyboard, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成内容人工复核")
        self.resize(1000, 800)
        
        layout = QVBoxLayout(self)
        
        # 提示信息
        tip = QLabel("AI已生成动画源码和分镜脚本，请在生成语音前进行复核和修改：")
        tip.setStyleSheet("color: #666; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(tip)
        
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab 1: SVG Source
        self.svg_editor = QTextEdit()
        self.svg_editor.setPlainText(svg_code)
        self.svg_editor.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 14px;")
        tabs.addTab(self.svg_editor, "SVG 动画源码")
        
        # Tab 2: Storyboard (JSON)
        self.storyboard_editor = QTextEdit()
        import json
        # 格式化JSON以便阅读
        try:
            json_str = json.dumps(storyboard, indent=2, ensure_ascii=False)
        except:
            json_str = str(storyboard)
            
        self.storyboard_editor.setPlainText(json_str)
        self.storyboard_editor.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 14px;")
        tabs.addTab(self.storyboard_editor, "分镜脚本 (字幕/旁白)")
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def accept(self):
        """确认前验证JSON"""
        import json
        try:
            json.loads(self.storyboard_editor.toPlainText())
            super().accept()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "格式错误", f"分镜脚本JSON格式不正确，请检查:\n{str(e)}")

    def get_data(self):
        import json
        svg_code = self.svg_editor.toPlainText()
        try:
            storyboard = json.loads(self.storyboard_editor.toPlainText())
        except Exception as e:
            print(f"JSON解析失败: {e}")
            storyboard = None 
        return svg_code, storyboard


class VideoExportDialog(QDialog):
    """导出视频配置对话框"""
    SETTINGS_FILE = "video_export_settings.json"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出视频配置")
        self.resize(450, 600)
        self.setStyleSheet("""
            QDialog { background-color: white; }
            QGroupBox { font-weight: bold; border: 1px solid #D1D5DB; border-radius: 6px; margin-top: 10px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; color: #4F46E5; }
        """)
        
        layout = QVBoxLayout(self)
        
        # Audio Settings
        audio_group = QGroupBox("🎵 背景音乐")
        audio_layout = QVBoxLayout(audio_group)
        self.audio_check = QCheckBox("添加背景音乐")
        
        audio_path_layout = QHBoxLayout()
        self.audio_path = ClickableLineEdit()
        self.audio_path.setPlaceholderText("点击选择音乐文件...")
        self.audio_path.setEnabled(False)
        self.audio_path.clicked.connect(self.choose_audio)
        self.audio_check.toggled.connect(self.audio_path.setEnabled)
        audio_path_layout.addWidget(self.audio_path)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self.choose_audio)
        browse_btn.setEnabled(False)
        self.audio_check.toggled.connect(browse_btn.setEnabled)
        audio_path_layout.addWidget(browse_btn)
        
        audio_layout.addWidget(self.audio_check)
        audio_layout.addLayout(audio_path_layout)
        layout.addWidget(audio_group)
        
        # Watermark Settings
        wm_group = QGroupBox("🏷️ 水印设置")
        wm_layout = QVBoxLayout(wm_group)
        self.wm_check = QCheckBox("添加水印")
        
        self.wm_tabs = QTabWidget()
        self.wm_tabs.setEnabled(False)
        self.wm_check.toggled.connect(self.wm_tabs.setEnabled)
        
        # Text Watermark
        text_tab = QWidget()
        text_layout = QFormLayout(text_tab)
        self.wm_text = QLineEdit()
        self.wm_text.setPlaceholderText("请输入水印文字")
        self.wm_font_size = QSpinBox()
        self.wm_font_size.setRange(10, 200)
        self.wm_font_size.setValue(40)
        
        self.wm_opacity = QSlider(Qt.Orientation.Horizontal)
        self.wm_opacity.setRange(0, 100)
        self.wm_opacity.setValue(50)
        
        self.wm_position = QComboBox()
        self.wm_position.addItems(["Bottom Right", "Bottom Left", "Top Right", "Top Left", "Center"])
        
        text_layout.addRow("文字内容:", self.wm_text)
        text_layout.addRow("字体大小:", self.wm_font_size)
        text_layout.addRow("透明度:", self.wm_opacity)
        text_layout.addRow("位置:", self.wm_position)
        self.wm_tabs.addTab(text_tab, "文字水印")
        
        # Image Watermark
        img_tab = QWidget()
        img_layout = QVBoxLayout(img_tab)
        
        img_path_layout = QHBoxLayout()
        self.wm_img_path = ClickableLineEdit()
        self.wm_img_path.setPlaceholderText("点击选择图片...")
        self.wm_img_path.clicked.connect(self.choose_wm_image)
        img_path_layout.addWidget(self.wm_img_path)
        
        img_browse = QPushButton("...")
        img_browse.setFixedWidth(30)
        img_browse.clicked.connect(self.choose_wm_image)
        img_path_layout.addWidget(img_browse)
        
        img_layout.addLayout(img_path_layout)
        self.wm_tabs.addTab(img_tab, "图片水印")
        
        wm_layout.addWidget(self.wm_check)
        wm_layout.addWidget(self.wm_tabs)
        layout.addWidget(wm_group)
        
        # Video Settings
        video_group = QGroupBox("🎥 视频参数")
        video_layout = QFormLayout(video_group)
        self.video_width = QSpinBox()
        self.video_width.setRange(100, 3840)
        self.video_width.setValue(1920)
        self.video_height = QSpinBox()
        self.video_height.setRange(100, 2160)
        self.video_height.setValue(1080)
        self.video_fps = QSpinBox()
        self.video_fps.setRange(10, 60)
        self.video_fps.setValue(30)
        
        video_layout.addRow("宽度:", self.video_width)
        video_layout.addRow("高度:", self.video_height)
        video_layout.addRow("帧率 (FPS):", self.video_fps)
        layout.addWidget(video_group)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        self.load_settings()
        
    def choose_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择音乐文件", "", "Audio (*.mp3 *.wav *.aac)")
        if path:
            self.audio_path.setText(path)
            
    def choose_wm_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择水印图片", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.wm_img_path.setText(path)
            
    def get_config(self):
        return {
            "audio": {
                "enabled": self.audio_check.isChecked(),
                "path": self.audio_path.text()
            },
            "watermark": {
                "enabled": self.wm_check.isChecked(),
                "type": "text" if self.wm_tabs.currentIndex() == 0 else "image",
                "text": self.wm_text.text(),
                "fontSize": self.wm_font_size.value(),
                "opacity": self.wm_opacity.value() / 100.0,
                "position": self.wm_position.currentText(),
                "imagePath": self.wm_img_path.text()
            },
            "video": {
                "width": self.video_width.value(),
                "height": self.video_height.value(),
                "fps": self.video_fps.value()
            }
        }

    def load_settings(self):
        if not os.path.exists(self.SETTINGS_FILE):
            return
            
        try:
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                
            # Audio settings
            audio = settings.get("audio", {})
            self.audio_check.setChecked(audio.get("enabled", False))
            self.audio_path.setText(audio.get("path", ""))
            
            # Watermark settings
            wm = settings.get("watermark", {})
            self.wm_check.setChecked(wm.get("enabled", False))
            self.wm_tabs.setCurrentIndex(0 if wm.get("type", "text") == "text" else 1)
            self.wm_text.setText(wm.get("text", ""))
            self.wm_font_size.setValue(wm.get("fontSize", 40))
            self.wm_opacity.setValue(int(wm.get("opacity", 0.5) * 100))
            
            pos_text = wm.get("position", "Bottom Right")
            idx = self.wm_position.findText(pos_text)
            if idx >= 0:
                self.wm_position.setCurrentIndex(idx)
                
            self.wm_img_path.setText(wm.get("imagePath", ""))
            
            # Video settings
            video = settings.get("video", {})
            self.video_width.setValue(video.get("width", 1920))
            self.video_height.setValue(video.get("height", 1080))
            self.video_fps.setValue(video.get("fps", 30))
            
        except Exception as e:
            print(f"Error loading video export settings: {e}")

    def save_settings(self):
        settings = self.get_config()
        try:
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving video export settings: {e}")

    def accept(self):
        self.save_settings()
        super().accept()


class PromptReviewDialog(QDialog):
    """提示词复核对话框"""
    def __init__(self, prompt, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提示词人工复核")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        tip = QLabel("这是即将发送给AI的提示词，您可以根据需要进行修改：")
        tip.setStyleSheet("color: #666; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(tip)
        
        self.editor = QTextEdit()
        self.editor.setPlainText(prompt)
        self.editor.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'Courier New', monospace; 
                font-size: 14px; 
                line-height: 1.5;
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.editor)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_prompt(self):
        return self.editor.toPlainText()


class UniversalInputDialog(QDialog):
    """通用生成选项对话框"""
    def __init__(self, mode="animation", default_topic="", parent=None):
        super().__init__(parent)
        self.mode = mode
        
        mode_titles = {
            "animation": "生成动画",
            "mindmap": "生成思维导图",
            "bar_race": "生成动态排序图",
            "geo_map": "生成地理数据可视化"
        }
        self.setWindowTitle(mode_titles.get(mode, "生成任务"))
        self.resize(600, 450)
        self.setup_ui(default_topic)
        self.result_data = None # (mode, topic, content, manual_review)

    def setup_ui(self, default_topic):
        # 设置统一样式
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EEF2FF, stop:0.5 #E0E7FF, stop:1 #F8FAFF);
            }
            QLabel {
                color: #1F2937;
                font-size: 14px;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                padding: 10px;
                background: white;
                selection-background-color: #4F46E5;
                font-size: 14px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #4F46E5;
            }
            QTabWidget::pane {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #E0E7FF;
                color: #4F46E5;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #4F46E5;
                color: white;
            }
            QPushButton {
                background-color: white;
                border: 1px solid #C7D2FE;
                border-radius: 6px;
                padding: 8px 16px;
                color: #4F46E5;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EEF2FF;
                border-color: #4F46E5;
            }
            QCheckBox {
                spacing: 8px;
                color: #374151;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #C7D2FE;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4F46E5;
                border: 1px solid #4F46E5;
            }
        """)

        layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        
        # Tab 1: 按主题
        tab1 = QWidget()
        layout1 = QVBoxLayout()
        layout1.setContentsMargins(20, 30, 20, 30)
        layout1.setSpacing(15)
        
        icon_label = QLabel("💡")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px; margin-bottom: 10px;")
        layout1.addWidget(icon_label)
        
        # 根据模式显示不同的描述
        desc_map = {
            "animation": "AI将根据您输入的主题自动构思剧本、分镜和画面，\n生成完整的解说动画。",
            "mindmap": "AI将根据您输入的主题自动构思结构、扩展子节点，\n适合快速头脑风暴或知识梳理。",
            "bar_race": "AI将根据您输入的主题查找历史数据，\n生成随时间变化的动态排序图。",
            "geo_map": "AI将根据您输入的主题查找地理分布数据，\n生成中国地图数据可视化。"
        }
        
        desc1 = QLabel(desc_map.get(self.mode, "AI将根据主题自动生成内容。"))
        desc1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc1.setStyleSheet("color: #6B7280; font-size: 14px; margin-bottom: 20px;")
        layout1.addWidget(desc1)
        
        self.topic_input = QLineEdit(default_topic)
        self.topic_input.setPlaceholderText("请输入主题，例如: 人工智能发展史")
        # remove inline style to use global style
        layout1.addWidget(QLabel("主题名称:"))
        layout1.addWidget(self.topic_input)

        layout1.addStretch()
        tab1.setLayout(layout1)
        
        # Tab 2: 按内容
        tab2 = QWidget()
        layout2 = QVBoxLayout()
        layout2.setContentsMargins(20, 20, 20, 20)
        
        content_desc_map = {
            "animation": "AI将深度分析您提供的文本内容，提炼核心要点，\n生成动画脚本和分镜。",
            "mindmap": "AI将深度分析您提供的文本内容，提炼核心要点，\n生成结构化的思维导图。",
            "bar_race": "AI将从您提供的文本内容中提取时间序列数据，\n生成动态排序图。",
            "geo_map": "AI将从您提供的文本内容中提取地理分布数据，\n生成地图可视化。"
        }
        
        desc2 = QLabel(content_desc_map.get(self.mode, "AI将根据您提供的内容生成结果。"))
        desc2.setStyleSheet("color: #6B7280; margin-bottom: 15px;")
        desc2.setWordWrap(True)
        layout2.addWidget(desc2)
        
        # 主题(即使按内容也需要一个标题)
        self.content_topic_input = QLineEdit(default_topic)
        self.content_topic_input.setPlaceholderText("请输入生成的标题")
        layout2.addWidget(QLabel("标题:"))
        layout2.addWidget(self.content_topic_input)
        
        layout2.addWidget(QLabel("内容文本:"))
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("在此粘贴文章内容、会议记录或数据文本...\n\n也可以点击下方按钮导入文件。")
        layout2.addWidget(self.content_edit)
        
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("📂 导入文件...")
        import_btn.clicked.connect(self.import_file)
        import_btn.setStyleSheet("padding: 5px 10px;")
        btn_layout.addWidget(import_btn)
        btn_layout.addStretch()
        layout2.addLayout(btn_layout)
        
        tab2.setLayout(layout2)
        
        self.tab_widget.addTab(tab1, "按主题生成")
        self.tab_widget.addTab(tab2, "按内容生成")
        
        layout.addWidget(self.tab_widget)
        
        # 底部按钮
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 10, 0, 0)
        
        # 统一的语言选择
        self.language_combo = QComboBox()
        self.language_combo.addItems(["中文", "English"])
        self.language_combo.setCurrentIndex(0)
        self.language_combo.setToolTip("选择生成内容的语言")

        # 统一的字数设置
        self.text_length_spin = QSpinBox()
        self.text_length_spin.setRange(10, 200)
        self.text_length_spin.setValue(50)
        self.text_length_spin.setSingleStep(10)
        self.text_length_spin.setSuffix(" 字")
        self.text_length_spin.setToolTip("设置每个主题节点的字数限制")
        
        if self.mode == "animation":
            # 人工复核选项
            self.manual_review_check = QCheckBox("人工复核")
            self.manual_review_check.setToolTip("勾选后，将在生成语音前显示动画源码和分镜脚本，供您确认和修改")
            buttons.addWidget(self.manual_review_check)
            
            # 分镜数设置
            self.frame_count_spin = QSpinBox()
            self.frame_count_spin.setRange(1, 15)
            self.frame_count_spin.setValue(8)
            self.frame_count_spin.setToolTip("设置生成的动画分镜数量 (最大15)")
            self.frame_count_spin.setFixedWidth(60)
            
            buttons.addWidget(QLabel("分镜数:"))
            buttons.addWidget(self.frame_count_spin)
            
            buttons.addWidget(QLabel("语言:"))
            buttons.addWidget(self.language_combo)

        elif self.mode == "mindmap":
            buttons.addWidget(QLabel("语言:"))
            buttons.addWidget(self.language_combo)
            buttons.addSpacing(15)
            buttons.addWidget(QLabel("节点字数:"))
            buttons.addWidget(self.text_length_spin)

        elif self.mode in ["bar_race", "geo_map"]:
            buttons.addWidget(QLabel("语言:"))
            buttons.addWidget(self.language_combo)
        
        buttons.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedWidth(100)
        
        self.generate_btn = QPushButton("开始生成")
        self.generate_btn.setFixedWidth(120)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5; 
                color: white; 
                font-weight: bold; 
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.generate_btn.clicked.connect(self.on_generate)
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(self.generate_btn)
        
        layout.addLayout(buttons)
        self.setLayout(layout)

    def import_file(self):
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "Text Files (*.txt *.md);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.content_edit.setText(content)
                    # 如果标题为空，尝试用文件名填充
                    if not self.content_topic_input.text():
                        self.content_topic_input.setText(Path(file_path).stem)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法读取文件: {e}")

    def on_generate(self):
        manual_review = self.manual_review_check.isChecked() if self.mode == "animation" else False
        language = "zh" if self.language_combo.currentText() == "中文" else "en"
        frame_count = self.frame_count_spin.value() if self.mode == "animation" else 8
        
        if self.tab_widget.currentIndex() == 0:
            # 按主题
            topic = self.topic_input.text().strip()
            if not topic:
                QMessageBox.warning(self, "提示", "请输入主题")
                return
            
            # 获取个性化设置
            lang = "zh" if self.language_combo.currentText() == "中文" else "en"
            length = self.text_length_spin.value()
            
            self.result_data = ("topic", topic, None, manual_review, lang, frame_count, length)
        else:
            # 按内容
            topic = self.content_topic_input.text().strip()
            content = self.content_edit.toPlainText().strip()
            if not topic:
                QMessageBox.warning(self, "提示", "请输入导图标题")
                return
            if not content:
                QMessageBox.warning(self, "提示", "请输入内容或导入文件")
                return
            # 内容模式暂不使用长度配置
            self.result_data = ("content", topic, content, manual_review, language, frame_count, 0)
        
        self.accept()


class HelpDialog(QDialog):
    """帮助对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("帮助与支持")
        self.setMinimumWidth(600)
        self.setMinimumHeight(450)
        self.setup_ui()

    def setup_ui(self):
        # 复用SettingsDialog的样式
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EEF2FF, stop:0.5 #E0E7FF, stop:1 #F8FAFF);
            }
            QLabel {
                color: #1F2937;
                font-size: 14px;
            }
            QPushButton {
                background-color: white;
                border: 1px solid #C7D2FE;
                border-radius: 6px;
                padding: 8px 20px;
                color: #4F46E5;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EEF2FF;
                border-color: #4F46E5;
            }
            QTabWidget::pane {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #EEF2FF;
                color: #4F46E5;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border: 1px solid #C7D2FE;
                border-bottom: none;
            }
        """)

        layout = QVBoxLayout()

        # 创建选项卡
        tab_widget = QTabWidget()

        # 关于页
        about_widget = QWidget()
        about_layout = QVBoxLayout()
        about_label = QLabel(
            "<h2>KnowledgeSight 知识可视化工具</h2>"
            "<p>版本: v1.0.0</p>"
            "<p>基于大语言模型的全能知识可视化助手。</p>"
            "<p>Copyright © 2025 KnowledgeSight Team</p>"
        )
        about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addStretch()
        about_layout.addWidget(about_label)
        about_layout.addStretch()
        about_widget.setLayout(about_layout)

        # 帮助页
        help_widget = QWidget()
        help_layout = QVBoxLayout()
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
            <h3>快速入门指南</h3>
            <p><b>1. 选择功能模式</b><br>在左侧导航栏选择您需要的功能：动画演示、思维导图、动态排序图或地理可视化。</p>
            <p><b>2. 输入内容</b><br>点击生成按钮，输入主题关键词，或选择“导入内容”直接粘贴文本。</p>
            <p><b>3. 配置参数</b><br>在右侧设置面板调整颜色、字体、背景图等外观选项。</p>
            <p><b>4. 生成与导出</b><br>等待生成完成后，可直接预览或导出为视频/图片。</p>
            <p><b>5. 历史记录</b><br>所有生成结果都会自动保存在历史记录中，随时可以回看。</p>
        """)
        help_layout.addWidget(help_text)
        help_widget.setLayout(help_layout)

        # 注册页
        register_widget = QWidget()
        register_layout = QFormLayout()
        reg_key_input = QLineEdit()
        reg_key_input.setPlaceholderText("请输入您的激活码")
        register_layout.addRow("激活码:", reg_key_input)
        
        activate_btn = QPushButton("激活")
        activate_btn.clicked.connect(lambda: QMessageBox.information(self, "提示", "注册功能开发中..."))
        
        register_container_layout = QVBoxLayout()
        register_container_layout.addLayout(register_layout)
        register_container_layout.addWidget(activate_btn)
        register_container_layout.addStretch()
        register_widget.setLayout(register_container_layout)
        
        # 运行日志页 (新增)
        log_widget = QWidget()
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; border: 1px solid #C7D2FE; border-radius: 4px;")
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap) # 不换行，方便查看日志
        
        log_layout.addWidget(self.log_text)
        
        # 日志操作按钮
        log_btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新日志")
        refresh_btn.clicked.connect(self.refresh_log)
        open_log_btn = QPushButton("打开日志文件")
        open_log_btn.clicked.connect(self.open_log_file)
        
        log_btn_layout.addWidget(refresh_btn)
        log_btn_layout.addWidget(open_log_btn)
        log_layout.addLayout(log_btn_layout)
        
        log_widget.setLayout(log_layout)

        tab_widget.addTab(about_widget, "关于")
        tab_widget.addTab(help_widget, "帮助")
        tab_widget.addTab(register_widget, "注册")
        tab_widget.addTab(log_widget, "运行日志") # 添加标签

        layout.addWidget(tab_widget)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # 初始加载日志
        QTimer.singleShot(100, self.refresh_log)

    def refresh_log(self):
        """刷新日志内容"""
        log_path = BASE_DIR / "knowledgesight.log"
        if log_path.exists():
            try:
                # 只读取最后 100KB 防止卡顿
                file_size = log_path.stat().st_size
                with open(log_path, "r", encoding="utf-8") as f:
                    if file_size > 100 * 1024:
                        f.seek(file_size - 100 * 1024)
                        content = "...(Previous logs truncated)...\n" + f.read()
                    else:
                        content = f.read()
                    
                    self.log_text.setPlainText(content)
                    # 滚动到底部
                    sb = self.log_text.verticalScrollBar()
                    sb.setValue(sb.maximum())
            except Exception as e:
                self.log_text.setPlainText(f"读取日志失败: {e}")
        else:
            self.log_text.setPlainText("暂无日志记录 (日志文件不存在)")

    def open_log_file(self):
        """调用系统默认程序打开日志文件"""
        log_path = BASE_DIR / "knowledgesight.log"
        if log_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        else:
            QMessageBox.warning(self, "提示", "日志文件不存在")


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.setup_ui()
    
    def setup_ui(self):
        # 设置统一样式
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EEF2FF, stop:0.5 #E0E7FF, stop:1 #F8FAFF);
            }
            QLabel {
                color: #1F2937;
                font-size: 14px;
            }
            QLineEdit, QComboBox, QSpinBox {
                border: 1px solid #C7D2FE;
                border-radius: 6px;
                padding: 6px;
                background: white;
                selection-background-color: #4F46E5;
                min-height: 20px;
                color: #374151;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 2px solid #4F46E5;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                outline: 0px;
            }
            QComboBox QAbstractItemView::item {
                color: #374151;
                padding: 8px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #4F46E5;
                color: white;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #4F46E5;
                color: white;
            }
            QCheckBox {
                spacing: 8px;
                color: #374151;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #C7D2FE;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4F46E5;
                border: 1px solid #4F46E5;
            }
            QPushButton {
                background-color: white;
                border: 1px solid #C7D2FE;
                border-radius: 6px;
                padding: 8px 20px;
                color: #4F46E5;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EEF2FF;
                border-color: #4F46E5;
            }
            QTabWidget::pane {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #EEF2FF;
                color: #4F46E5;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                border: 1px solid #C7D2FE;
                border-bottom: none;
            }
        """)

        layout = QVBoxLayout()
        
        # 辅助函数: 优化下拉框样式
        def setup_combo_view(combo):
            view = QListView()
            combo.setView(view)
            view.setStyleSheet("""
                QListView {
                    background-color: #FFFFFF;
                    border: 1px solid #D1D5DB;
                    outline: 0px;
                }
                QListView::item {
                    color: #374151;
                    padding: 8px;
                    min-height: 24px;
                }
                QListView::item:hover {
                    background-color: #4F46E5;
                    color: white;
                }
                QListView::item:selected {
                    background-color: #4F46E5;
                    color: white;
                }
            """)

        # 创建选项卡
        tab_widget = QTabWidget()

        # API设置页
        api_widget = QWidget()
        api_layout = QFormLayout()
        api_layout.setContentsMargins(20, 20, 20, 20)
        api_layout.setSpacing(15)
        
        self.api_key_input = QLineEdit(self.settings.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("API Key:", self.api_key_input)
        
        self.api_base_input = QLineEdit(self.settings.api_base)
        api_layout.addRow("Base URL:", self.api_base_input)
        
        self.api_model_input = QLineEdit(self.settings.api_model)
        api_layout.addRow("模型:", self.api_model_input)
        
        self.api_is_default_check = QCheckBox("设为默认API")
        self.api_is_default_check.setChecked(self.settings.api_is_default)
        api_layout.addRow("", self.api_is_default_check)
        
        api_widget.setLayout(api_layout)
        tab_widget.addTab(api_widget, "基础设置")

        # 视频设置页
        video_widget = QWidget()
        video_layout = QFormLayout()
        video_layout.setContentsMargins(20, 20, 20, 20)
        video_layout.setSpacing(15)
        
        self.resolution_combo = QComboBox()
        setup_combo_view(self.resolution_combo)
        self.resolution_combo.addItems(["720p", "1080p", "4k"])
        self.resolution_combo.setCurrentText(self.settings.video_resolution)
        video_layout.addRow("分辨率:", self.resolution_combo)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(24, 60)
        self.fps_spin.setValue(self.settings.fps)
        video_layout.addRow("帧率:", self.fps_spin)
        
        self.audio_check = QCheckBox("包含配音")
        self.audio_check.setChecked(self.settings.include_audio)
        video_layout.addRow("", self.audio_check)
        
        video_widget.setLayout(video_layout)
        tab_widget.addTab(video_widget, "视频设置")
        
        # TTS设置页
        tts_widget = QWidget()
        tts_main_layout = QVBoxLayout()
        tts_widget.setLayout(tts_main_layout)
        
        # 顶部通用设置
        common_form = QFormLayout()
        common_form.setContentsMargins(20, 20, 20, 0)
        
        self.tts_engine_combo = QComboBox()
        setup_combo_view(self.tts_engine_combo)
        self.tts_engine_combo.addItems(["edge_tts", "qwen3-tts-flash", "custom"])
        self.tts_engine_combo.setCurrentText(self.settings.tts_engine)
        common_form.addRow("TTS引擎:", self.tts_engine_combo)
        
        self.tts_is_default_check = QCheckBox("设为默认TTS引擎")
        self.tts_is_default_check.setChecked(self.settings.tts_is_default)
        common_form.addRow("", self.tts_is_default_check)
        
        tts_main_layout.addLayout(common_form)
        
        # 堆叠区域
        self.tts_stack = QStackedWidget()
        tts_main_layout.addWidget(self.tts_stack)
        
        # --- 1. Edge TTS Page ---
        self.page_edge = QWidget()
        edge_layout = QFormLayout()
        edge_layout.setContentsMargins(20, 10, 20, 20)
        edge_layout.setSpacing(15)
        
        self.edge_voice_zh_combo = QComboBox()
        setup_combo_view(self.edge_voice_zh_combo)
        self.edge_voice_zh_combo.addItems([
            "zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunjianNeural", "zh-CN-XiaoyiNeural"
        ])
        self.edge_voice_zh_combo.setCurrentText(self.settings.edge_voice_zh)
        edge_layout.addRow("Edge默认中文:", self.edge_voice_zh_combo)
        
        self.edge_voice_en_combo = QComboBox()
        setup_combo_view(self.edge_voice_en_combo)
        self.edge_voice_en_combo.addItems([
            "en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural"
        ])
        self.edge_voice_en_combo.setCurrentText(self.settings.edge_voice_en)
        edge_layout.addRow("Edge默认英文:", self.edge_voice_en_combo)
        
        self.page_edge.setLayout(edge_layout)
        self.tts_stack.addWidget(self.page_edge)
        
        # --- 2. Qwen Page ---
        self.page_qwen = QWidget()
        qwen_layout = QFormLayout()
        qwen_layout.setContentsMargins(20, 10, 20, 20)
        qwen_layout.setSpacing(15)
        
        self.qwen_api_key_input = QLineEdit()
        self.qwen_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.qwen_api_key_input.setText(self.settings.qwen_api_key)
        qwen_layout.addRow("Qwen API Key:", self.qwen_api_key_input)
        
        self.qwen_api_base_input = QLineEdit()
        self.qwen_api_base_input.setText(self.settings.qwen_api_base)
        qwen_layout.addRow("Qwen Base URL:", self.qwen_api_base_input)
        
        self.qwen_voice_zh_combo = QComboBox()
        setup_combo_view(self.qwen_voice_zh_combo)
        # 预设Qwen语音列表
        qwen_voices = [
            "Cherry", "Daisy", "Davit", "Ellis", "Liam", "Leo", "Luna",
            "Maciej", "Marco", "Marie", "Maria", "Mark", "Mathias",
            "Mila", "Milo", "Mingxuan", "Mitsuki", "Mixue", "Mizhen",
            "Nora", "Oleg", "Paisley", "Palina", "Piyush", "Rachel",
            "Renzhi", "Rocky", "Roxanne", "Rufina", "Sachiko", "Sophia",
            "Theresa", "Titania", "Tomoki", "Usha", "Veena", "Vikas",
            "Xuanxuan", "Yun", "Yunxi", "Yupan", "Zhen"
        ]
        self.qwen_voice_zh_combo.addItems(qwen_voices)
        self.qwen_voice_zh_combo.setCurrentText(self.settings.qwen_voice_zh)
        qwen_layout.addRow("Qwen默认中文:", self.qwen_voice_zh_combo)
        
        self.qwen_voice_en_combo = QComboBox()
        setup_combo_view(self.qwen_voice_en_combo)
        self.qwen_voice_en_combo.addItems(qwen_voices)
        self.qwen_voice_en_combo.setCurrentText(self.settings.qwen_voice_en)
        qwen_layout.addRow("Qwen默认英文:", self.qwen_voice_en_combo)
        
        self.page_qwen.setLayout(qwen_layout)
        self.tts_stack.addWidget(self.page_qwen)
        
        # --- 3. Custom Page ---
        self.page_custom = QWidget()
        custom_layout = QFormLayout()
        custom_layout.setContentsMargins(20, 10, 20, 20)
        custom_layout.setSpacing(15)
        
        self.custom_api_key_input = QLineEdit(self.settings.custom_api_key)
        self.custom_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.custom_api_key_input.setPlaceholderText("sk-...")
        custom_layout.addRow("API Key:", self.custom_api_key_input)
        
        self.custom_api_base_input = QLineEdit(self.settings.custom_api_base)
        self.custom_api_base_input.setPlaceholderText("https://api.openai.com/v1")
        custom_layout.addRow("Base URL:", self.custom_api_base_input)
        
        self.custom_model_input = QLineEdit(self.settings.custom_model)
        self.custom_model_input.setPlaceholderText("tts-1")
        custom_layout.addRow("Model:", self.custom_model_input)

        # 预设OpenAI标准语音列表
        openai_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "ash", "coral", "sage"]

        self.custom_voice_zh_combo = QComboBox()
        # setup_combo_view(self.custom_voice_zh_combo)  # 移除自定义视图以修复编辑模式下的下拉列表显示问题
        self.custom_voice_zh_combo.setEditable(True)
        self.custom_voice_zh_combo.addItems(openai_voices)
        # 如果配置为空，默认选中alloy
        current_zh = self.settings.custom_voice_zh if self.settings.custom_voice_zh else "alloy"
        self.custom_voice_zh_combo.setCurrentText(current_zh)
        self.custom_voice_zh_combo.lineEdit().setPlaceholderText("选择或输入语音ID (如 alloy)")
        custom_layout.addRow("Custom默认中文:", self.custom_voice_zh_combo)
        
        self.custom_voice_en_combo = QComboBox()
        # setup_combo_view(self.custom_voice_en_combo)  # 移除自定义视图以修复编辑模式下的下拉列表显示问题
        self.custom_voice_en_combo.setEditable(True)
        self.custom_voice_en_combo.addItems(openai_voices)
        # 如果配置为空，默认选中alloy
        current_en = self.settings.custom_voice_en if self.settings.custom_voice_en else "alloy"
        self.custom_voice_en_combo.setCurrentText(current_en)
        self.custom_voice_en_combo.lineEdit().setPlaceholderText("选择或输入语音ID (如 alloy)")
        custom_layout.addRow("Custom默认英文:", self.custom_voice_en_combo)
        
        custom_tips = QLabel("说明: 支持所有兼容OpenAI格式的TTS接口 (如 OpenAI, Azure OpenAI, Groq, DeepSeek等)。<br>点击下拉框可选择预置的OpenAI标准语音，也可直接输入自定义语音ID。")
        custom_tips.setWordWrap(True)
        custom_tips.setStyleSheet("color: #666; font-size: 12px; margin-top: 10px;")
        custom_layout.addRow(custom_tips)

        self.page_custom.setLayout(custom_layout)
        self.tts_stack.addWidget(self.page_custom)

        # 切换逻辑
        def on_tts_engine_changed(text):
            if text == "edge_tts":
                self.tts_stack.setCurrentWidget(self.page_edge)
            elif text == "qwen3-tts-flash":
                self.tts_stack.setCurrentWidget(self.page_qwen)
            elif text == "custom":
                self.tts_stack.setCurrentWidget(self.page_custom)
        
        self.tts_engine_combo.currentTextChanged.connect(on_tts_engine_changed)
        on_tts_engine_changed(self.tts_engine_combo.currentText())
        
        tab_widget.addTab(tts_widget, "语音设置")
        
        # 水印设置Tab
        watermark_widget = QWidget()
        watermark_layout = QFormLayout()
        
        self.watermark_enabled_check = QCheckBox("启用水印")
        self.watermark_enabled_check.setChecked(self.settings.watermark_enabled)
        watermark_layout.addRow("", self.watermark_enabled_check)
        
        self.watermark_type_combo = QComboBox()
        setup_combo_view(self.watermark_type_combo)
        self.watermark_type_combo.addItems(["文字", "图片"])
        self.watermark_type_combo.setCurrentText("文字" if self.settings.watermark_type == "text" else "图片")
        watermark_layout.addRow("水印类型:", self.watermark_type_combo)
        
        self.watermark_content_input = QLineEdit()
        self.watermark_content_input.setText(self.settings.watermark_content)
        self.watermark_content_input.setPlaceholderText("输入文字或选择图片路径")
        
        content_layout = QHBoxLayout()
        content_layout.addWidget(self.watermark_content_input)
        self.browse_watermark_btn = QPushButton("浏览...")
        self.browse_watermark_btn.clicked.connect(self.browse_watermark_file)
        content_layout.addWidget(self.browse_watermark_btn)
        
        watermark_layout.addRow("水印内容:", content_layout)
        
        self.watermark_position_combo = QComboBox()
        setup_combo_view(self.watermark_position_combo)
        self.watermark_position_combo.addItems(["左上角", "右上角", "左下角", "右下角", "居中"])
        pos_map = {
            "top_left": "左上角", "top_right": "右上角", 
            "bottom_left": "左下角", "bottom_right": "右下角", 
            "center": "居中"
        }
        current_pos = pos_map.get(self.settings.watermark_position, "右下角")
        self.watermark_position_combo.setCurrentText(current_pos)
        watermark_layout.addRow("位置:", self.watermark_position_combo)
        
        self.watermark_opacity_spin = QDoubleSpinBox()
        self.watermark_opacity_spin.setRange(0.0, 1.0)
        self.watermark_opacity_spin.setSingleStep(0.1)
        self.watermark_opacity_spin.setValue(self.settings.watermark_opacity)
        watermark_layout.addRow("不透明度 (0-1):", self.watermark_opacity_spin)
        
        self.watermark_size_spin = QDoubleSpinBox()
        self.watermark_size_spin.setRange(0.01, 1.0)
        self.watermark_size_spin.setSingleStep(0.05)
        self.watermark_size_spin.setValue(self.settings.watermark_size)
        watermark_layout.addRow("大小比例 (0-1):", self.watermark_size_spin)
        
        watermark_widget.setLayout(watermark_layout)
        tab_widget.addTab(watermark_widget, "水印设置")
        
        # 初始化浏览按钮状态
        self.toggle_watermark_browse(self.watermark_type_combo.currentText())
        self.watermark_type_combo.currentTextChanged.connect(self.toggle_watermark_browse)
        
        layout.addWidget(tab_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5; 
                color: white; 
                font-weight: bold; 
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def toggle_watermark_browse(self, type_text):
        self.browse_watermark_btn.setVisible(type_text == "图片")
        
    def browse_watermark_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择水印图片", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.watermark_content_input.setText(file_path)

    def save_settings(self):
        self.settings.api_key = self.api_key_input.text()
        self.settings.api_base = self.api_base_input.text()
        self.settings.api_model = self.api_model_input.text()
        self.settings.api_is_default = self.api_is_default_check.isChecked()
        self.settings.video_resolution = self.resolution_combo.currentText()
        # self.settings.slide_duration removed from UI
        self.settings.fps = self.fps_spin.value()
        self.settings.include_audio = self.audio_check.isChecked()
        self.settings.tts_engine = self.tts_engine_combo.currentText()
        self.settings.tts_is_default = self.tts_is_default_check.isChecked()
        # self.settings.edge_voice removed from UI
        self.settings.edge_voice_zh = self.edge_voice_zh_combo.currentText()
        self.settings.edge_voice_en = self.edge_voice_en_combo.currentText()
        # self.settings.tts_model removed as it was ambiguous
        self.settings.qwen_api_key = self.qwen_api_key_input.text()
        self.settings.qwen_api_base = self.qwen_api_base_input.text()
        self.settings.qwen_voice_zh = self.qwen_voice_zh_combo.currentText()
        self.settings.qwen_voice_en = self.qwen_voice_en_combo.currentText()
        # self.settings.qwen_voice/language removed from UI, keeping defaults or existing
        
        # 自定义TTS设置保存
        self.settings.custom_api_key = self.custom_api_key_input.text()
        self.settings.custom_api_base = self.custom_api_base_input.text()
        self.settings.custom_model = self.custom_model_input.text()
        self.settings.custom_voice_zh = self.custom_voice_zh_combo.currentText()
        self.settings.custom_voice_en = self.custom_voice_en_combo.currentText()
        
        # 水印设置保存
        self.settings.watermark_enabled = self.watermark_enabled_check.isChecked()
        self.settings.watermark_type = "text" if self.watermark_type_combo.currentText() == "文字" else "image"
        self.settings.watermark_content = self.watermark_content_input.text()
        
        pos_map_rev = {
            "左上角": "top_left", "右上角": "top_right", 
            "左下角": "bottom_left", "右下角": "bottom_right", 
            "居中": "center"
        }
        self.settings.watermark_position = pos_map_rev.get(self.watermark_position_combo.currentText(), "bottom_right")
        self.settings.watermark_opacity = self.watermark_opacity_spin.value()
        self.settings.watermark_size = self.watermark_size_spin.value()
        
        self.settings.save()
        self.accept()


class MindMapContentEditorDialog(QDialog):
    """思维导图内容编辑器对话框"""
    def __init__(self, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑思维导图内容")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        
        self.info_label = QLabel("提示: 可以在节点文本前添加 <关系> 来定义连接线上的文字。\n例如: - <导致> 结果")
        self.info_label.setStyleSheet("color: #666; background: #f0f0f0; padding: 8px; border-radius: 4px; margin-bottom: 5px;")
        layout.addWidget(self.info_label)
        
        self.editor = QTextEdit()
        self.editor.setPlainText(content)
        self.editor.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 14px; line-height: 1.5;")
        layout.addWidget(self.editor)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_content(self):
        return self.editor.toPlainText()

class MindMapTreeEditorDialog(QDialog):
    """思维导图 简易编辑器(不需要Markdown)"""
    def __init__(self, root_dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑思维导图(简易模式)")
        self.resize(900, 600)
        
        self.root_dict = root_dict or {"name": "主题", "children": []}
        
        layout = QVBoxLayout(self)
        tip = QLabel("无需Markdown，直接编辑结构。可在“关系”中填写连接线文字。")
        tip.setStyleSheet("color:#4B5563; background:#EEF2FF; padding:8px; border-radius:6px;")
        layout.addWidget(tip)
        
        body = QHBoxLayout()
        layout.addLayout(body)
        
        # 左侧树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["节点", "关系"])
        self.tree.setColumnWidth(0, 300)
        # Enable Drag and Drop
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        body.addWidget(self.tree, 2)
        
        # 右侧编辑区
        right = QVBoxLayout()
        body.addLayout(right, 1)
        
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.edge_edit = QLineEdit()
        form.addRow("节点名称:", self.name_edit)
        form.addRow("关系文字:", self.edge_edit)
        right.addLayout(form)
        
        btns_layout = QHBoxLayout()
        self.btn_apply = QPushButton("保存修改")
        self.btn_add_child = QPushButton("添加子节点")
        self.btn_add_sibling = QPushButton("添加同级")
        self.btn_delete = QPushButton("删除节点")
        self.btn_up = QPushButton("上移")
        self.btn_down = QPushButton("下移")
        for b in [self.btn_apply, self.btn_add_child, self.btn_add_sibling, self.btn_delete, self.btn_up, self.btn_down]:
            btns_layout.addWidget(b)
        right.addLayout(btns_layout)
        
        # 底部确认
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)
        
        # 事件绑定
        self.tree.currentItemChanged.connect(self.on_select_item)
        self.btn_apply.clicked.connect(self.apply_item_changes)
        self.btn_add_child.clicked.connect(self.add_child)
        self.btn_add_sibling.clicked.connect(self.add_sibling)
        self.btn_delete.clicked.connect(self.delete_item)
        self.btn_up.clicked.connect(self.move_up)
        self.btn_down.clicked.connect(self.move_down)
        
        self.populate_tree()
        self.tree.expandAll()
        # 选中根节点
        self.tree.setCurrentItem(self.tree.topLevelItem(0))
    
    def populate_tree(self):
        self.tree.clear()
        def add_items(parent_item, node):
            name = node.get("name", "")
            edge = node.get("edge_label", "")
            item = QTreeWidgetItem([name, edge])
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            for child in node.get("children", []):
                add_items(item, child)
        add_items(None, self.root_dict)
    
    def on_select_item(self, item, prev):
        if item:
            self.name_edit.setText(item.text(0))
            self.edge_edit.setText(item.text(1))
    
    def apply_item_changes(self):
        item = self.tree.currentItem()
        if not item:
            return
        item.setText(0, self.name_edit.text().strip())
        item.setText(1, self.edge_edit.text().strip())
    
    def add_child(self):
        item = self.tree.currentItem()
        if not item:
            return
        child = QTreeWidgetItem(["新节点", ""])
        item.addChild(child)
        self.tree.setCurrentItem(child)
    
    def add_sibling(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent()
        sibling = QTreeWidgetItem(["新节点", ""])
        if parent:
            parent.addChild(sibling)
        else:
            self.tree.addTopLevelItem(sibling)
        self.tree.setCurrentItem(sibling)
    
    def delete_item(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            idx = self.tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self.tree.takeTopLevelItem(idx)
    
    def move_up(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent()
        if parent:
            idx = parent.indexOfChild(item)
            if idx > 0:
                parent.takeChild(idx)
                parent.insertChild(idx - 1, item)
        else:
            idx = self.tree.indexOfTopLevelItem(item)
            if idx > 0:
                self.tree.takeTopLevelItem(idx)
                self.tree.insertTopLevelItem(idx - 1, item)
    
    def move_down(self):
        item = self.tree.currentItem()
        if not item:
            return
        parent = item.parent()
        if parent:
            idx = parent.indexOfChild(item)
            if idx < parent.childCount() - 1:
                parent.takeChild(idx)
                parent.insertChild(idx + 1, item)
        else:
            idx = self.tree.indexOfTopLevelItem(item)
            if idx < self.tree.topLevelItemCount() - 1:
                self.tree.takeTopLevelItem(idx)
                self.tree.insertTopLevelItem(idx + 1, item)
    
    def to_markdown(self):
        lines = []
        def traverse(item, depth):
            name = item.text(0).strip()
            edge = item.text(1).strip()
            prefix = f"<{edge}> " if edge else ""
            # 使用标题层级，保证结构清晰
            lines.append(f"{'#' * max(1, depth)} {prefix}{name}")
            for i in range(item.childCount()):
                traverse(item.child(i), depth + 1)
        root_item = self.tree.topLevelItem(0)
        if root_item:
            traverse(root_item, 1)
        return "\n".join(lines)

class ClickableLineEdit(QLineEdit):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class VideoExportThread(QThread):
    """视频导出线程，防止阻塞主界面并控制资源使用"""
    progress = pyqtSignal(int) # 目前未使用，moviepy难以获取精确进度回调
    finished = pyqtSignal(bool, str) # success, message
    
    def __init__(self, frames, output_path, fps, config=None):
        super().__init__()
        self.frames = frames
        self.output_path = output_path
        self.fps = fps
        self.config = config or {}
        
    def run(self):
        print(f"[VideoExportThread] Starting export to {self.output_path}")
        print(f"[VideoExportThread] FPS: {self.fps}, Frames: {len(self.frames)}")
        print(f"[VideoExportThread] Config: {self.config}")
        
        clip = None
        audio = None
        wm_clip = None
        final_clip = None
        
        try:
            # Import inside run to avoid top-level issues
            import os
            
            # MoviePy Compatibility Layer (v1 vs v2)
            try:
                # Try MoviePy 2.x imports first
                from moviepy import ImageSequenceClip, AudioFileClip, ImageClip, CompositeVideoClip
                import moviepy.audio.fx as afx
                import moviepy.video.fx as vfx
                is_v2 = True
                print("[VideoExportThread] Using MoviePy 2.x")
            except ImportError:
                # Fallback to MoviePy 1.x
                from moviepy.editor import ImageSequenceClip, AudioFileClip, ImageClip, CompositeVideoClip
                import moviepy.audio.fx.all as afx
                vfx = None
                is_v2 = False
                print("[VideoExportThread] Using MoviePy 1.x")

            # Use preset='medium' and threads=4 for balance
            clip = ImageSequenceClip(self.frames, fps=self.fps)
            
            # 1. Resize Video
            video_conf = self.config.get("video", {})
            if video_conf.get("width") and video_conf.get("height"):
                target_w = int(video_conf["width"])
                target_h = int(video_conf["height"])
                print(f"[VideoExportThread] Resizing video to {target_w}x{target_h}")
                # Resize if dimensions differ significantly
                if abs(clip.w - target_w) > 1 or abs(clip.h - target_h) > 1:
                    if is_v2:
                        # v2 uses resized()
                        clip = clip.resized((target_w, target_h))
                    else:
                        # v1 uses resize()
                        clip = clip.resize((target_w, target_h))
            
            # 2. Add Watermark
            wm_conf = self.config.get("watermark", {})
            if wm_conf.get("enabled"):
                print("[VideoExportThread] Adding watermark...")
                
                if wm_conf.get("type") == "image":
                    img_path = wm_conf.get("imagePath")
                    print(f"[VideoExportThread] Watermark image path: {img_path}")
                    if img_path and os.path.exists(img_path):
                        wm_clip = ImageClip(img_path)
                    else:
                        print("[VideoExportThread] Watermark image not found")
                
                elif wm_conf.get("type") == "text":
                    text = wm_conf.get("text", "")
                    print(f"[VideoExportThread] Watermark text: {text}")
                    if text:
                        # Use PIL to generate text image to avoid ImageMagick dependency
                        from PIL import Image, ImageDraw, ImageFont
                        import numpy as np
                        
                        fontsize = int(wm_conf.get("fontSize", 40))
                        try:
                            # Try standard fonts
                            font = ImageFont.truetype("arial.ttf", fontsize)
                        except:
                            try:
                                font = ImageFont.truetype("msyh.ttc", fontsize) # Microsoft YaHei
                            except:
                                font = ImageFont.load_default()
                            
                        # Get text size
                        try:
                            # Pillow >= 9.2.0
                            left, top, right, bottom = font.getbbox(text)
                            text_w, text_h = right - left, bottom - top
                        except:
                            # Older Pillow
                            try:
                                text_w, text_h = font.getsize(text)
                            except:
                                text_w, text_h = len(text) * fontsize * 0.6, fontsize * 1.2
                            
                        # Create image with padding
                        img_w, img_h = int(text_w + 20), int(text_h + 20)
                        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
                        draw = ImageDraw.Draw(img)
                        # Draw text (white) with black outline for better visibility
                        try:
                            # Try using stroke parameters (Pillow >= 4.1.0)
                            draw.text((10, 10), text, font=font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
                        except:
                            # Fallback for older Pillow
                            x, y = 10, 10
                            shadow_color = (0, 0, 0, 255)
                            # Draw shadow/outline manually
                            draw.text((x-1, y-1), text, font=font, fill=shadow_color)
                            draw.text((x+1, y-1), text, font=font, fill=shadow_color)
                            draw.text((x-1, y+1), text, font=font, fill=shadow_color)
                            draw.text((x+1, y+1), text, font=font, fill=shadow_color)
                            draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
                        
                        # Convert to numpy for moviepy
                        wm_clip = ImageClip(np.array(img))

                if wm_clip:
                    print(f"[VideoExportThread] Watermark clip created. Size: {wm_clip.size}")
                    if is_v2:
                        wm_clip = wm_clip.with_duration(clip.duration)
                        opacity = float(wm_conf.get("opacity", 0.5))
                        wm_clip = wm_clip.with_opacity(opacity)
                    else:
                        wm_clip = wm_clip.set_duration(clip.duration)
                        opacity = float(wm_conf.get("opacity", 0.5))
                        wm_clip = wm_clip.set_opacity(opacity)
                    
                    # Position
                    pos_text = wm_conf.get("position", "Bottom Right")
                    pos_map = {
                        "Bottom Right": ("right", "bottom"),
                        "Bottom Left": ("left", "bottom"),
                        "Top Right": ("right", "top"),
                        "Top Left": ("left", "top"),
                        "Center": ("center", "center")
                    }
                    pos = pos_map.get(pos_text, ("right", "bottom"))
                    print(f"[VideoExportThread] Watermark position: {pos}")
                    
                    # Add margin if corner (move away from edge)
                    # Note: margin adds transparent pixels around the clip
                    if pos != ("center", "center"):
                        margin = 20
                        if is_v2:
                            wm_clip = wm_clip.with_effects([vfx.Margin(right=margin, bottom=margin, left=margin, top=margin, opacity=0)])
                        else:
                            wm_clip = wm_clip.margin(right=margin, bottom=margin, left=margin, top=margin, opacity=0)
                        
                    if is_v2:
                        wm_clip = wm_clip.with_position(pos)
                    else:
                        wm_clip = wm_clip.set_position(pos)
                    
                    clip = CompositeVideoClip([clip, wm_clip], size=clip.size)
                    print("[VideoExportThread] Watermark composited")

            # 3. Add Background Music
            audio_conf = self.config.get("audio", {})
            if audio_conf.get("enabled"):
                audio_path = audio_conf.get("path")
                print(f"[VideoExportThread] Adding audio: {audio_path}")
                if audio_path and os.path.exists(audio_path):
                    audio = AudioFileClip(audio_path)
                    
                    # Loop or cut
                    if audio.duration < clip.duration:
                        print("[VideoExportThread] Looping audio")
                        if is_v2:
                             # MoviePy 2.x Effect Class
                             audio = audio.with_effects([afx.AudioLoop(duration=clip.duration)])
                        else:
                             # MoviePy 1.x Function
                             audio = afx.audio_loop(audio, duration=clip.duration)
                    else:
                        print("[VideoExportThread] Cutting audio")
                        if is_v2:
                            audio = audio.subclipped(0, clip.duration)
                        else:
                            audio = audio.subclip(0, clip.duration)
                        
                    if is_v2:
                        clip = clip.with_audio(audio)
                    else:
                        clip = clip.set_audio(audio)
            
            print(f"[VideoExportThread] Writing video file: {self.output_path}")
            
            # Use a temporary file for writing to avoid locking the target file if writing fails
            # and to ensure we can rename it on success.
            # However, MoviePy writes directly to the path.
            # We will use verbose=True and logger='bar' to see progress in console.
            
            clip.write_videofile(
                self.output_path, 
                fps=self.fps,
                codec='libx264', 
                audio_codec='aac' if clip.audio else None,
                audio=True if clip.audio else False, 
                logger='bar', 
                preset='medium',  # Changed from ultrafast to medium for better compatibility
                threads=4 if is_v2 else 1 # Reduce threads for v1 stability, v2 might handle it better
            )
            
            # Explicitly close clip after writing
            clip.close()
            if audio: audio.close()
            if wm_clip: wm_clip.close()
            
            print("[VideoExportThread] Export finished successfully")
            self.finished.emit(True, self.output_path)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[VideoExportThread] Export failed: {e}")
            self.finished.emit(False, str(e))
            
        finally:
            # Explicitly close resources to release file lock
            print("[VideoExportThread] Cleaning up resources...")
            try:
                if 'clip' in locals() and clip:
                    try: clip.close() 
                    except: pass
                if 'audio' in locals() and audio:
                    try: audio.close()
                    except: pass
                if 'wm_clip' in locals() and wm_clip:
                    try: wm_clip.close()
                    except: pass
                
                # Try to clean up any other open handles if possible
                # In MoviePy 1.x, sometimes we need to close the reader explicitly
                if 'clip' in locals() and clip and hasattr(clip, 'reader') and clip.reader:
                    try: clip.reader.close()
                    except: pass
                    
            except Exception as close_err:
                print(f"[VideoExportThread] Error closing resources: {close_err}")

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.settings = AppSettings.load()
        self.current_result = None
        self.generation_thread = None
        
        # 初始化后端
        self.init_backend()
        
        # 设置窗口
        self.setWindowTitle("小凤知识可视化系统 (Phoenix)")
        self.setGeometry(100, 100, 1400, 900)
        
        # 设置应用图标
        try:
            from PyQt6.QtGui import QIcon
            icon_path = BASE_DIR / "static" / "vslogo.ico"
            if not icon_path.exists():
                # 尝试在上级目录查找(开发模式)
                icon_path = BASE_DIR / "vslogo.ico"
            
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            print(f"Error loading icon: {e}")
        
        # 设置主题
        self.setup_theme()
        
        # 创建UI
        self.setup_ui()
    
    def init_backend(self):
        """初始化后端服务"""
        try:
            # 确保settings文件存在
            self.settings.save()
            
            # 如果没有有效的API key，使用现有的credentials文件或创建默认配置
            if not self.settings.api_key or self.settings.api_key.strip() == "":
                # 尝试读取现有文件
                creds = None
                if CREDENTIALS.exists():
                    print(f"[初始化] 使用现有的credentials文件: {CREDENTIALS}")
                    try:
                        with open(CREDENTIALS, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:
                                creds = json.loads(content)
                            else:
                                print(f"[警告] credentials文件为空")
                    except Exception as e:
                        print(f"[警告] credentials文件损坏，将重新创建: {e}")
                
                # 如果没有读取到（文件不存在或损坏），创建默认配置
                if creds is None:
                    # 创建默认配置(需要用户后续配置)
                    print(f"[初始化] 创建默认credentials文件，请配置API Key")
                    creds = {
                        "provider": "openai-compatible",
                        "openai-compatible": {
                            "api_key": "",
                            "base_url": self.settings.api_base,
                            "model": self.settings.api_model
                        }
                    }
                    ensure_dir(CREDENTIALS.parent)
                    with open(CREDENTIALS, 'w', encoding='utf-8') as f:
                        json.dump(creds, f, indent=2)
            else:
                # 只在有有效API key时才更新credentials文件
                print(f"[初始化] 使用settings中的API配置更新credentials文件")
                ensure_dir(CREDENTIALS.parent)
                creds = {
                    "provider": "openai-compatible",
                    "openai-compatible": {
                        "api_key": self.settings.api_key,
                        "base_url": self.settings.api_base,
                        "model": self.settings.api_model
                    }
                }
                with open(CREDENTIALS, 'w', encoding='utf-8') as f:
                    json.dump(creds, f, indent=2)
            
            # 初始化LLM客户端
            from llm.client import LLMClient
            self.llm_client = LLMClient(creds)
            
            self.cache = ResourceCache(OFFLINE_DIR)
            self.orchestrator = VisualizationOrchestrator(
                RESOURCE_DIR / "templates",
                OFFLINE_DIR
            )
            self.media_composer = MediaComposer()
            
        except Exception as e:
            print(f"初始化后端失败: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_theme(self):
        """设置应用主题"""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 242, 255))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(17, 24, 39))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(79, 70, 229))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        self.setPalette(palette)
        
        # 设置样式表
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #EEF2FF, stop:0.5 #E0E7FF, stop:1 #F8FAFF);
            }
            QPushButton {
                background-color: #4F46E5;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4338CA;
            }
            QPushButton:pressed {
                background-color: #3730A3;
            }
            QPushButton:disabled {
                background-color: #9CA3AF;
            }
            QLineEdit {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                padding: 10px;
                background: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #4F46E5;
            }
            QTabWidget::pane {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                background: white;
            }
            QTabBar::tab {
                background: #E0E7FF;
                color: #4F46E5;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #4F46E5;
                color: white;
            }
            QProgressBar {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                text-align: center;
                background: white;
            }
            QProgressBar::chunk {
                background-color: #4F46E5;
                border-radius: 7px;
            }
        """)
    
    def setup_ui(self):
        """创建用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 左侧控制面板
        left_panel = self.create_left_panel()
        
        # 右侧内容区
        right_panel = self.create_right_panel()
        
        # 添加到分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 1050])
        
        main_layout.addWidget(splitter)
    
    def create_left_panel(self):
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 标题区域
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 20, 0, 20)
        
        # Logo
        logo_label = QLabel()
        try:
            # 尝试加载logo
            icon_path = BASE_DIR / "static" / "vslogo.ico"
            if not icon_path.exists():
                icon_path = BASE_DIR / "vslogo.ico"
            
            if icon_path.exists():
                pixmap = QPixmap(str(icon_path))
                logo_label.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception as e:
            print(f"Error loading logo for header: {e}")
            
        title_layout.addWidget(logo_label)
        
        # Text
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(10, 0, 0, 0)
        text_layout.setSpacing(5)
        
        title = QLabel("小凤知识可视化系统\n(Phoenix)")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #4F46E5;")
        
        subtitle = QLabel("把知识转化为动画和思维导图")
        subtitle.setStyleSheet("color: #4C51BF;")
        
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        
        title_layout.addWidget(text_container)
        title_layout.addStretch()
        
        layout.addWidget(title_container)
        
        # 输入框
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("输入主题，例如: 量子纠缠")
        self.topic_input.returnPressed.connect(self.generate_visualization)
        layout.addWidget(self.topic_input)
        
        # 生成按钮
        self.generate_btn = QPushButton("生成动画")
        self.generate_btn.clicked.connect(lambda: self.show_input_dialog("animation"))
        layout.addWidget(self.generate_btn)

        # 生成思维导图按钮
        self.mindmap_btn = QPushButton("生成导图")
        self.mindmap_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;  /* 绿色系 */
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065F46;
            }
            QPushButton:disabled {
                background-color: #9CA3AF;
            }
        """)
        self.mindmap_btn.clicked.connect(lambda: self.show_input_dialog("mindmap"))
        layout.addWidget(self.mindmap_btn)

        # 生成动态排序图按钮
        self.bar_race_btn = QPushButton("生成动态排序图")
        self.bar_race_btn.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;  /* 紫色系 */
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #6D28D9;
            }
            QPushButton:pressed {
                background-color: #5B21B6;
            }
            QPushButton:disabled {
                background-color: #C4B5FD;
            }
        """)
        self.bar_race_btn.clicked.connect(lambda: self.show_input_dialog("bar_race"))
        layout.addWidget(self.bar_race_btn)

        # 生成地理数据可视化按钮
        self.geo_map_btn = QPushButton("生成地理数据可视化")
        self.geo_map_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;  /* 蓝色系 */
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
            QPushButton:disabled {
                background-color: #93C5FD;
            }
        """)
        self.geo_map_btn.clicked.connect(lambda: self.show_input_dialog("geo_map"))
        layout.addWidget(self.geo_map_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定模式
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #4C51BF; margin-top: 10px;")
        layout.addWidget(self.status_label)
        
        # 历史记录按钮
        history_btn = QPushButton("📜 生成历史")
        history_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(79, 70, 229, 0.1);
                color: #4F46E5;
                margin-top: 20px;
            }
            QPushButton:hover {
                background-color: rgba(79, 70, 229, 0.2);
            }
        """)
        history_btn.clicked.connect(self.toggle_history_list)
        layout.addWidget(history_btn)
        
        # 历史记录列表(默认显示)
        from PyQt6.QtWidgets import QListWidget
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #C7D2FE;
                border-radius: 8px;
                background: white;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #EEF2FF;
            }
            QListWidget::item:selected {
                background-color: #4F46E5;
                color: white;
            }
        """)
        self.history_list.itemClicked.connect(self.load_history_item)
        # 移除隐藏，默认显示
        layout.addWidget(self.history_list)
        # 初始化列表
        self.refresh_history_list()

        layout.addStretch()

        # 底部按钮区 (设置 + 帮助)
        bottom_box = QWidget()
        bottom_layout = QHBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)

        # 设置按钮
        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6B7280;
                text-align: left;
                padding: 10px;
                border: 1px solid transparent;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                color: #4F46E5;
                border: 1px solid #E5E7EB;
            }
        """)
        settings_btn.clicked.connect(self.show_settings)
        
        # 帮助按钮
        help_btn = QPushButton("❓ 帮助")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6B7280;
                text-align: left;
                padding: 10px;
                border: 1px solid transparent;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                color: #4F46E5;
                border: 1px solid #E5E7EB;
            }
        """)
        help_btn.clicked.connect(self.show_help)

        bottom_layout.addWidget(settings_btn)
        bottom_layout.addWidget(help_btn)
        
        layout.addWidget(bottom_box)
        return panel

    def create_bar_race_settings_panel(self):
        """创建动态排序图设置面板"""
        container = QWidget()
        container.setMinimumWidth(320)
        container.setStyleSheet("""
            QWidget { background-color: #FFFFFF; border-right: 1px solid #E5E7EB; }
            QLabel { color: #374151; }
            QComboBox, QSpinBox, QCheckBox {
                border: 1px solid #D1D5DB; border-radius: 4px; padding: 5px;
                background: #F9FAFB; min-height: 20px;
                color: #374151;
            }
            QComboBox::drop-down { border: 0px; }
            QComboBox:hover, QSpinBox:hover { border-color: #4F46E5; }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #374151;
                selection-background-color: #E0E7FF;
                selection-color: #1F2937;
                border: 1px solid #D1D5DB;
            }
            QPushButton {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 4px 8px;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
                border-color: #9CA3AF;
            }
            QPushButton:pressed {
                background-color: #D1D5DB;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #EEF2FF; border-bottom: 1px solid #E0E7FF;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 15, 15, 15)
        h_layout.addWidget(QLabel("⚙️"))
        title = QLabel("动态排序图设置")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #4F46E5;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        layout.addWidget(header)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(15, 10, 15, 10)
        form.setSpacing(15)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Controls
        self.br_font_combo = QComboBox()
        self.br_font_combo.addItems(["Microsoft YaHei", "SimHei", "SimSun", "Arial", "Times New Roman"])
        form.addRow("字体:", self.br_font_combo)
        
        self.br_font_size_spin = QSpinBox()
        self.br_font_size_spin.setRange(12, 48)
        self.br_font_size_spin.setValue(24)
        form.addRow("标题字号:", self.br_font_size_spin)
        
        self.br_bg_color_combo = QComboBox()
        self.br_bg_color_combo.addItems([
            "默认 (#f0f2f5)", 
            "纯白 (#ffffff)", 
            "暗黑 (#1a1a1a)", 
            "护眼 (#f5f5dc)",
            "绚丽渐变 (Blue-Purple)",
            "温暖夕阳 (Orange-Red)",
            "清凉海洋 (Blue-Cyan)",
            "彩虹光谱 (Rainbow)"
        ])
        form.addRow("背景颜色:", self.br_bg_color_combo)

        # Background Image
        bg_img_layout = QHBoxLayout()
        self.br_bg_image_path = ClickableLineEdit()
        self.br_bg_image_path.setPlaceholderText("选择背景图片...")
        self.br_bg_image_path.setReadOnly(True)
        self.br_bg_image_path.clicked.connect(self.choose_bar_race_bg_image)
        bg_img_layout.addWidget(self.br_bg_image_path)
        form.addRow("背景图片:", bg_img_layout)
        
        # Image Buttons (New Row)
        img_btns_layout = QHBoxLayout()
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self.choose_bar_race_bg_image)
        
        clear_btn = QPushButton("x")
        clear_btn.setFixedWidth(40)
        clear_btn.clicked.connect(lambda: self.br_bg_image_path.clear())
        
        img_btns_layout.addWidget(browse_btn)
        img_btns_layout.addWidget(clear_btn)
        img_btns_layout.addStretch()
        form.addRow("", img_btns_layout)
        
        # Background Opacity
        self.br_bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.br_bg_opacity_slider.setRange(0, 100)
        self.br_bg_opacity_slider.setValue(100)
        form.addRow("背景透明度:", self.br_bg_opacity_slider)

        # Separator for Bar Style
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        form.addRow(sep)
        
        bar_label = QLabel("条形图样式")
        bar_label.setStyleSheet("font-weight: bold; color: #4F46E5;")
        form.addRow(bar_label)

        # Bar Color Mode
        self.br_bar_color_mode = QComboBox()
        self.br_bar_color_mode.addItems(["默认分类色", "单色 (蓝色)", "单色 (红色)", "渐变 (蓝青)", "渐变 (红黄)"])
        form.addRow("颜色模式:", self.br_bar_color_mode)
        
        # Bar Radius
        self.br_bar_radius = QSlider(Qt.Orientation.Horizontal)
        self.br_bar_radius.setRange(0, 20)
        self.br_bar_radius.setValue(5)
        form.addRow("圆角半径:", self.br_bar_radius)
        
        # Bar Opacity
        self.br_bar_opacity = QSlider(Qt.Orientation.Horizontal)
        self.br_bar_opacity.setRange(10, 100)
        self.br_bar_opacity.setValue(100)
        form.addRow("条形透明度:", self.br_bar_opacity)

        self.br_font_combo = QComboBox()
        self.br_font_combo.addItems(["Microsoft YaHei", "SimHei", "Arial"])
        form.addRow("字体:", self.br_font_combo)
        
        self.br_font_size_spin = QSpinBox()
        self.br_font_size_spin.setRange(8, 72)
        self.br_font_size_spin.setValue(16)
        form.addRow("字体大小:", self.br_font_size_spin)
        
        self.br_font_color_combo = QComboBox()
        self.br_font_color_combo.addItems(["默认 (#333)", "黑色 (#000)", "白色 (#fff)", "灰色 (#666)"])
        form.addRow("字体颜色:", self.br_font_color_combo)

        self.br_show_label_check = QCheckBox("显示数值标签")
        self.br_show_label_check.setChecked(True)
        form.addRow("", self.br_show_label_check)

        self.br_data_source_input = QLineEdit()
        self.br_data_source_input.setPlaceholderText("例如：国家统计局")
        form.addRow("数据来源:", self.br_data_source_input)
        
        # Apply Button
        btn_box = QWidget()
        btn_layout = QHBoxLayout(btn_box)
        apply_btn = QPushButton("应用设置")
        apply_btn.setStyleSheet("background-color: #4F46E5; color: white; padding: 8px; border-radius: 4px;")
        apply_btn.clicked.connect(self.apply_bar_race_settings)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(lambda: container.hide())
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(apply_btn)
        layout.addWidget(btn_box)
        
        return container

    def create_geo_map_settings_panel(self):
        """创建地理可视化设置面板"""
        container = QWidget()
        container.setMinimumWidth(320)
        container.setStyleSheet("""
            QWidget { background-color: #FFFFFF; border-right: 1px solid #E5E7EB; }
            QLabel { color: #374151; }
            QComboBox, QSpinBox, QCheckBox {
                border: 1px solid #D1D5DB; border-radius: 4px; padding: 5px;
                background: #F9FAFB; min-height: 20px;
                color: #374151;
            }
            QComboBox::drop-down { border: 0px; }
            QComboBox:hover, QSpinBox:hover { border-color: #4F46E5; }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #374151;
                selection-background-color: #E0E7FF;
                selection-color: #1F2937;
                border: 1px solid #D1D5DB;
            }
            QPushButton {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 4px 8px;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
                border-color: #9CA3AF;
            }
            QPushButton:pressed {
                background-color: #D1D5DB;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #EEF2FF; border-bottom: 1px solid #E0E7FF;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 15, 15, 15)
        h_layout.addWidget(QLabel("⚙️"))
        title = QLabel("地理可视化设置")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #4F46E5;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        layout.addWidget(header)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")
        
        content = QWidget()
        content.setStyleSheet(".QWidget { background-color: transparent; }")
        main_form_layout = QVBoxLayout(content)
        main_form_layout.setContentsMargins(10, 10, 10, 10)
        main_form_layout.setSpacing(15)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # --- Group 1: 基础设置 (Basic Settings) ---
        group_basic = QGroupBox("基础设置")
        group_basic.setStyleSheet("QGroupBox { font-weight: bold; color: #4F46E5; border: 1px solid #E5E7EB; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        form_basic = QFormLayout(group_basic)
        form_basic.setContentsMargins(10, 15, 10, 10)
        form_basic.setSpacing(10)

        self.geo_theme_combo = QComboBox()
        self.geo_theme_combo.addItems(["默认 (红黄)", "蓝色系", "绿色系", "紫色系", "热力红", "森林绿", "海洋蓝", "经典 (红黄蓝)", "复古 (Vintage)", "暗黑 (Dark)", "马卡龙 (Macarons)", "罗马 (Roma)", "Shine"])
        form_basic.addRow("配色方案:", self.geo_theme_combo)

        self.geo_viz_type_combo = QComboBox()
        self.geo_viz_type_combo.addItems(["默认 (平面地图)", "3D 柱状地图", "涟漪散点地图", "高亮发光地图", "立体渐变地图"])
        form_basic.addRow("可视化类型:", self.geo_viz_type_combo)

        # Bar Shape (Hidden by default, shown for 3D Bar Map)
        self.geo_bar_shape_combo = QComboBox()
        self.geo_bar_shape_combo.addItems(["长方体 (Cuboid)", "圆柱体 (Cylinder)", "圆锥体 (Cone)", "三角锥 (Pyramid)", "三棱柱 (Prism)"])
        self.geo_bar_shape_label = QLabel("柱状形状:")
        form_basic.addRow(self.geo_bar_shape_label, self.geo_bar_shape_combo)
        
        # Initial visibility
        self.geo_bar_shape_combo.setVisible(False)
        self.geo_bar_shape_label.setVisible(False)
        
        # Connect signal
        self.geo_viz_type_combo.currentTextChanged.connect(self.on_geo_viz_type_changed)
        
        self.geo_bg_color_combo = QComboBox()
        self.geo_bg_color_combo.addItems(["默认 (灰白)", "纯白", "暗黑", "米黄", "淡蓝", "淡紫"])
        form_basic.addRow("背景颜色:", self.geo_bg_color_combo)
        
        # Background Image
        bg_img_layout = QHBoxLayout()
        self.geo_bg_image_path = ClickableLineEdit()
        self.geo_bg_image_path.setPlaceholderText("选择背景图片...")
        self.geo_bg_image_path.setReadOnly(True)
        self.geo_bg_image_path.clicked.connect(self.choose_geo_map_bg_image)
        bg_img_layout.addWidget(self.geo_bg_image_path)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self.choose_geo_map_bg_image)
        
        clear_btn = QPushButton("x")
        clear_btn.setFixedWidth(30)
        clear_btn.clicked.connect(lambda: self.geo_bg_image_path.clear())
        
        bg_img_layout.addWidget(browse_btn)
        bg_img_layout.addWidget(clear_btn)
        form_basic.addRow("背景图片:", bg_img_layout)
        
        self.geo_bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.geo_bg_opacity_slider.setRange(0, 100)
        self.geo_bg_opacity_slider.setValue(100)
        form_basic.addRow("背景透明度:", self.geo_bg_opacity_slider)
        
        main_form_layout.addWidget(group_basic)

        # --- Group 2: 文字设置 (Text Settings) ---
        group_text = QGroupBox("文字设置")
        group_text.setStyleSheet("QGroupBox { font-weight: bold; color: #4F46E5; border: 1px solid #E5E7EB; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        form_text = QFormLayout(group_text)
        form_text.setContentsMargins(10, 15, 10, 10)
        form_text.setSpacing(10)

        self.geo_font_combo = QComboBox()
        self.geo_font_combo.addItems(["Microsoft YaHei", "SimHei", "Arial"])
        form_text.addRow("字体:", self.geo_font_combo)
        
        # Title Settings Row
        title_row = QHBoxLayout()
        self.geo_font_size_spin = QSpinBox()
        self.geo_font_size_spin.setRange(8, 72)
        self.geo_font_size_spin.setValue(24)
        self.geo_font_size_spin.setSuffix(" px")
        
        self.geo_font_color_combo = QComboBox()
        self.geo_font_color_combo.addItems(["默认 (黑)", "黑色", "白色", "灰色", "红色", "蓝色", "绿色", "橙色"])
        
        title_row.addWidget(self.geo_font_size_spin)
        title_row.addWidget(self.geo_font_color_combo)
        form_text.addRow("标题样式:", title_row)

        # Label Settings Row
        label_row = QHBoxLayout()
        self.geo_label_size_spin = QSpinBox()
        self.geo_label_size_spin.setRange(8, 72)
        self.geo_label_size_spin.setValue(12)
        self.geo_label_size_spin.setSuffix(" px")

        self.geo_label_color_combo = QComboBox()
        self.geo_label_color_combo.addItems(["默认 (黑)", "黑色", "白色", "灰色", "红色", "蓝色", "绿色", "橙色"])
        
        label_row.addWidget(self.geo_label_size_spin)
        label_row.addWidget(self.geo_label_color_combo)
        form_text.addRow("文字样式:", label_row)
        
        main_form_layout.addWidget(group_text)

        # --- Group 3: 样式与效果 (Styles & Effects) ---
        group_style = QGroupBox("样式与效果")
        group_style.setStyleSheet("QGroupBox { font-weight: bold; color: #4F46E5; border: 1px solid #E5E7EB; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        form_style = QFormLayout(group_style)
        form_style.setContentsMargins(10, 15, 10, 10)
        form_style.setSpacing(10)
        
        self.geo_border_color_combo = QComboBox()
        self.geo_border_color_combo.addItems(["默认 (黑)", "白色", "灰色", "深灰", "浅灰", "蓝色", "无描边", "发光蓝", "发光金", "发光绿", "发光红"])
        form_style.addRow("边界描边:", self.geo_border_color_combo)
        
        check_row = QHBoxLayout()
        self.geo_show_label_check = QCheckBox("显示标签")
        self.geo_show_label_check.setChecked(True)
        self.geo_show_3d_check = QCheckBox("立体感")
        self.geo_show_3d_check.setChecked(False)
        check_row.addWidget(self.geo_show_label_check)
        check_row.addWidget(self.geo_show_3d_check)
        check_row.addStretch()
        form_style.addRow("显示选项:", check_row)
        
        main_form_layout.addWidget(group_style)
        
        # --- Group 4: 信息标注 (Information) ---
        group_info = QGroupBox("信息标注")
        group_info.setStyleSheet("QGroupBox { font-weight: bold; color: #4F46E5; border: 1px solid #E5E7EB; border-radius: 6px; margin-top: 6px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        form_info = QFormLayout(group_info)
        form_info.setContentsMargins(10, 15, 10, 10)
        form_info.setSpacing(10)

        self.geo_data_source_input = QLineEdit()
        self.geo_data_source_input.setPlaceholderText("例如：国家统计局")
        form_info.addRow("数据来源:", self.geo_data_source_input)

        self.geo_author_input = QLineEdit()
        self.geo_author_input.setPlaceholderText("例如：张三")
        form_info.addRow("制图人:", self.geo_author_input)
        
        self.geo_note_input = QLineEdit()
        self.geo_note_input.setPlaceholderText("底部居中备注信息")
        form_info.addRow("备注:", self.geo_note_input)
        
        main_form_layout.addWidget(group_info)
        
        # Add Stretch
        main_form_layout.addStretch()

        
        # Apply Button
        btn_box = QWidget()
        btn_layout = QHBoxLayout(btn_box)
        apply_btn = QPushButton("应用设置")
        apply_btn.setStyleSheet("background-color: #4F46E5; color: white; padding: 8px; border-radius: 4px;")
        apply_btn.clicked.connect(self.apply_geo_map_settings)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(lambda: container.hide())
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(apply_btn)
        layout.addWidget(btn_box)
        
        # Connect signals for auto-save
        self.geo_theme_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_viz_type_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_bar_shape_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_bg_color_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_bg_image_path.textChanged.connect(self.save_geo_settings)
        self.geo_bg_opacity_slider.valueChanged.connect(self.save_geo_settings)
        self.geo_font_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_font_size_spin.valueChanged.connect(self.save_geo_settings)
        self.geo_font_color_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_label_size_spin.valueChanged.connect(self.save_geo_settings)
        self.geo_label_color_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_border_color_combo.currentTextChanged.connect(self.save_geo_settings)
        self.geo_show_label_check.toggled.connect(self.save_geo_settings)
        self.geo_show_3d_check.toggled.connect(self.save_geo_settings)
        self.geo_data_source_input.textChanged.connect(self.save_geo_settings)
        self.geo_author_input.textChanged.connect(self.save_geo_settings)
        self.geo_note_input.textChanged.connect(self.save_geo_settings)

        # Auto-load settings
        self.load_geo_settings()
        
        return container

    def choose_bar_race_bg_image(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.br_bg_image_path.setText(path)

    def choose_geo_map_bg_image(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.geo_bg_image_path.setText(path)

    def apply_bar_race_settings(self):
        """应用动态排序图设置"""
        font = self.br_font_combo.currentText()
        size = self.br_font_size_spin.value()
        
        font_color_map = {"默认 (#333)": "#333", "黑色 (#000)": "#000", "白色 (#fff)": "#fff", "灰色 (#666)": "#666"}
        font_color = font_color_map.get(self.br_font_color_combo.currentText(), "#333")
        
        bg_text = self.br_bg_color_combo.currentText()
        bg_style = "#f0f2f5"
        if "默认" in bg_text: bg_style = "#f0f2f5"
        elif "纯白" in bg_text: bg_style = "#ffffff"
        elif "暗黑" in bg_text: bg_style = "#1a1a1a"
        elif "护眼" in bg_text: bg_style = "#f5f5dc"
        elif "Blue-Purple" in bg_text: bg_style = "linear-gradient(120deg, #e0c3fc 0%, #8ec5fc 100%)"
        elif "Orange-Red" in bg_text: bg_style = "linear-gradient(120deg, #f6d365 0%, #fda085 100%)"
        elif "Blue-Cyan" in bg_text: bg_style = "linear-gradient(120deg, #89f7fe 0%, #66a6ff 100%)"
        elif "Rainbow" in bg_text: bg_style = "linear-gradient(to right, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3)"

        # Bar Style
        bar_mode_text = self.br_bar_color_mode.currentText()
        bar_color_mode = 'category'
        bar_single_color = '#5470c6'
        bar_gradient = None
        
        if "单色 (蓝色)" in bar_mode_text:
            bar_color_mode = 'single'
            bar_single_color = '#5470c6'
        elif "单色 (红色)" in bar_mode_text:
            bar_color_mode = 'single'
            bar_single_color = '#ee6666'
        elif "渐变 (蓝青)" in bar_mode_text:
            bar_color_mode = 'gradient'
            bar_gradient = {
                "type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
                "colorStops": [{"offset": 0, "color": "#89f7fe"}, {"offset": 1, "color": "#66a6ff"}]
            }
        elif "渐变 (红黄)" in bar_mode_text:
            bar_color_mode = 'gradient'
            bar_gradient = {
                "type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
                "colorStops": [{"offset": 0, "color": "#f6d365"}, {"offset": 1, "color": "#fda085"}]
            }
            
        bar_radius = self.br_bar_radius.value()
        bar_opacity = self.br_bar_opacity.value() / 100.0

        show_label = self.br_show_label_check.isChecked()
        data_source = self.br_data_source_input.text()
        bg_opacity = self.br_bg_opacity_slider.value() / 100.0
        
        # Handle background image
        bg_image = self.br_bg_image_path.text()
        bg_image_css = ""
        if bg_image:
            # Convert backslashes to forward slashes for JS
            bg_image = bg_image.replace("\\", "/")
            bg_image_css = f"url('file:///{bg_image}')"
        
        import json
        config_data = {
            "fontFamily": font,
            "fontSize": size,
            "fontColor": font_color,
            "backgroundStyle": bg_style,
            "backgroundImage": bg_image_css,
            "bgOpacity": bg_opacity,
            "showLabel": True if show_label else False,
            "dataSource": data_source,
            "barColorMode": bar_color_mode,
            "barSingleColor": bar_single_color,
            "barGradient": bar_gradient,
            "barBorderRadius": bar_radius,
            "barOpacity": bar_opacity
        }
        
        js = f"updateConfig({json.dumps(config_data)});"
        
        if hasattr(self, 'bar_race_view'):
            self.bar_race_view.page().runJavaScript(js)

    def replay_bar_race(self):
        """重播动态排序图动画"""
        if hasattr(self, 'bar_race_view'):
            self.bar_race_view.page().runJavaScript("if(typeof runAnimation === 'function') { runAnimation(); }")
            
    def export_bar_race_video(self):
        """导出动态排序图视频"""
        if not self.current_result or self.current_result.get("type") != "bar_race":
            QMessageBox.warning(self, "错误", "没有可导出的动态排序图内容")
            return

        # Check moviepy
        try:
            # Try moviepy 2.x imports first
            try:
                from moviepy import ImageSequenceClip
            except ImportError:
                # Fallback to moviepy 1.x imports
                from moviepy.editor import ImageSequenceClip
        except ImportError:
            QMessageBox.warning(self, "错误", "未安装 moviepy 库，无法导出视频")
            return

        # Configuration Dialog
        dialog = VideoExportDialog(self)
        if not dialog.exec():
            return
            
        self.export_config = dialog.get_config()

        # 尝试从文件名获取带后缀的主题名
        default_name = f"{self.topic_input.text()}.mp4"
        bar_race_file = self.current_result.get("bar_race_file", "")
        if bar_race_file:
             stem = Path(bar_race_file).stem
             default_name = f"{stem}.mp4"

        file_path, _ = QFileDialog.getSaveFileName(self, "保存视频", default_name, "MP4 Video (*.mp4)")
        if not file_path:
            return

        # Progress Dialog
        self.export_progress = QProgressDialog("正在导出视频 (导出期间请勿操作窗口)...", "取消", 0, 100, self)
        self.export_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.export_progress.setMinimumDuration(0)
        self.export_progress.setValue(0)
        
        # Setup recording state
        self.recording_frames = []
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self._capture_frame)
        self.export_file_path = file_path
        self.temp_frame_dir = tempfile.mkdtemp()
        
        # Reset and prepare
        # Stop existing animation
        self.bar_race_view.page().runJavaScript("if(timer) clearInterval(timer);")
        
        # Get duration and start
        # Use runJavaScript with callback to get the duration
        self.bar_race_view.page().runJavaScript("rawData.timeline.length * config.updateFrequency", self._start_recording)

    def _start_recording(self, duration_ms):
        print(f"[_start_recording] duration_ms: {duration_ms}")
        if duration_ms is None:
            self.export_progress.cancel()
            QMessageBox.warning(self, "错误", "无法获取动画时长")
            return
            
        # Add buffer for start/end
        self.total_duration = float(duration_ms) + 1000 
        self.frame_interval = 66 # ~15 FPS (Reduced load for stability)
        self.total_frames = int(self.total_duration / self.frame_interval)
        self.current_frame_count = 0
        
        print(f"[_start_recording] total_duration: {self.total_duration}, total_frames: {self.total_frames}")
        
        self.export_progress.setRange(0, self.total_frames)
        
        # Restart animation
        self.bar_race_view.page().runJavaScript("runAnimation();")
        
        # Start capture
        self.recording_timer.start(self.frame_interval)
        
    def _capture_frame(self):
        if self.export_progress.wasCanceled():
            self._stop_recording(save=False)
            return

        pixmap = self.bar_race_view.grab()
        if not pixmap.isNull():
            filename = os.path.join(self.temp_frame_dir, f"frame_{self.current_frame_count:05d}.png")
            pixmap.save(filename, "PNG")
            self.recording_frames.append(filename)
            
        self.current_frame_count += 1
        self.export_progress.setValue(self.current_frame_count)
        
        if self.current_frame_count >= self.total_frames:
            print("[_capture_frame] Reached total frames, stopping recording")
            self._stop_recording(save=True)

    def _stop_recording(self, save=True):
        print(f"[_stop_recording] save={save}, frames captured={len(self.recording_frames)}")
        self.recording_timer.stop()
        
        if save and self.recording_frames:
            # Recreate progress dialog for export phase
            if self.export_progress:
                self.export_progress.close()
                
            self.export_progress = QProgressDialog("正在合成视频 (可能需要一些时间，请耐心等待)...", None, 0, 0, self)
            self.export_progress.setWindowTitle("视频导出中")
            self.export_progress.setWindowModality(Qt.WindowModality.WindowModal)
            self.export_progress.setMinimumDuration(0)
            self.export_progress.setCancelButton(None) # Disable cancel during encoding
            self.export_progress.show()
            
            fps = 1000 / self.frame_interval
            
            # Run export in background thread
            config = getattr(self, 'export_config', {})
            # Override FPS if specified in config
            if config.get("video", {}).get("fps"):
                fps = config["video"]["fps"]
                
            print(f"[_stop_recording] Starting export thread with FPS: {fps}")
            self.video_export_thread = VideoExportThread(self.recording_frames, self.export_file_path, fps, config)
            self.video_export_thread.finished.connect(self._on_video_export_finished)
            self.video_export_thread.start()
        else:
            self._cleanup_temp_frames()
            if self.export_progress:
                self.export_progress.close()

    def _on_video_export_finished(self, success, message):
        print(f"[_on_video_export_finished] success={success}, message={message}")
        self._cleanup_temp_frames()
        self.export_progress.close()
        
        if success:
            QMessageBox.information(self, "导出成功", f"视频已成功导出并保存至:\n{message}")
        else:
            QMessageBox.critical(self, "导出失败", f"视频合成失败: {message}\n请确保已安装 ffmpeg。")

    def _cleanup_temp_frames(self):
        try:
            import shutil
            if hasattr(self, 'temp_frame_dir') and os.path.exists(self.temp_frame_dir):
                shutil.rmtree(self.temp_frame_dir)
        except:
            pass

    def on_geo_viz_type_changed(self, text):
        """当可视化类型改变时，显示/隐藏特定选项"""
        is_bar_3d = "3D 柱状地图" in text
        if hasattr(self, 'geo_bar_shape_combo'):
            self.geo_bar_shape_combo.setVisible(is_bar_3d)
            self.geo_bar_shape_label.setVisible(is_bar_3d)

    def save_geo_settings(self):
        """保存地理可视化设置到文件"""
        settings = {
            "theme": self.geo_theme_combo.currentText(),
            "viz_type": self.geo_viz_type_combo.currentText(),
            "bar_shape": self.geo_bar_shape_combo.currentText(),
            "bg_color": self.geo_bg_color_combo.currentText(),
            "bg_image": self.geo_bg_image_path.text(),
            "bg_opacity": self.geo_bg_opacity_slider.value(),
            "font": self.geo_font_combo.currentText(),
            "font_size": self.geo_font_size_spin.value(),
            "font_color": self.geo_font_color_combo.currentText(),
            "label_size": self.geo_label_size_spin.value(),
            "label_color": self.geo_label_color_combo.currentText(),
            "border_color": self.geo_border_color_combo.currentText(),
            "show_label": self.geo_show_label_check.isChecked(),
            "show_3d": self.geo_show_3d_check.isChecked(),
            "data_source": self.geo_data_source_input.text(),
            "author": self.geo_author_input.text(),
            "note": self.geo_note_input.text()
        }
        
        try:
            settings_file = OFFLINE_DIR / "geo_settings.json"
            import json
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            print(f"[GUI] Geo settings saved to {settings_file}")
            
            # Apply settings immediately to the view
            self.apply_geo_map_settings()
            
        except Exception as e:
            print(f"[GUI] Failed to save geo settings: {e}")

    def load_geo_settings(self):
        """从文件加载地理可视化设置"""
        settings_file = OFFLINE_DIR / "geo_settings.json"
        if not settings_file.exists():
            return
            
        try:
            import json
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            # Helper to safely set combo box text
            def set_combo(combo, text):
                index = combo.findText(text)
                if index >= 0:
                    combo.setCurrentIndex(index)
            
            if "theme" in settings: set_combo(self.geo_theme_combo, settings["theme"])
            if "viz_type" in settings: 
                set_combo(self.geo_viz_type_combo, settings["viz_type"])
                self.on_geo_viz_type_changed(settings["viz_type"])
                
            if "bar_shape" in settings: set_combo(self.geo_bar_shape_combo, settings["bar_shape"])
            if "bg_color" in settings: set_combo(self.geo_bg_color_combo, settings["bg_color"])
            if "bg_image" in settings: self.geo_bg_image_path.setText(settings["bg_image"])
            if "bg_opacity" in settings: self.geo_bg_opacity_slider.setValue(settings["bg_opacity"])
            if "font" in settings: set_combo(self.geo_font_combo, settings["font"])
            if "font_size" in settings: self.geo_font_size_spin.setValue(settings["font_size"])
            if "font_color" in settings: set_combo(self.geo_font_color_combo, settings["font_color"])
            if "label_size" in settings: self.geo_label_size_spin.setValue(settings["label_size"])
            if "label_color" in settings: set_combo(self.geo_label_color_combo, settings["label_color"])
            if "border_color" in settings: set_combo(self.geo_border_color_combo, settings["border_color"])
            if "show_label" in settings: self.geo_show_label_check.setChecked(settings["show_label"])
            if "show_3d" in settings: self.geo_show_3d_check.setChecked(settings["show_3d"])
            if "data_source" in settings: self.geo_data_source_input.setText(settings["data_source"])
            if "author" in settings: self.geo_author_input.setText(settings["author"])
            if "note" in settings: self.geo_note_input.setText(settings["note"])
            
            print(f"[GUI] Geo settings loaded from {settings_file}")
        except Exception as e:
            print(f"[GUI] Failed to load geo settings: {e}")

    def apply_geo_map_settings(self):
        """应用地理可视化设置"""
        theme = self.geo_theme_combo.currentText()
        bg_color_map = {
            "默认 (灰白)": "#f0f2f5", "默认 (#f0f2f5)": "#f0f2f5", 
            "纯白": "#ffffff", "纯白 (#ffffff)": "#ffffff",
            "暗黑": "#1a1a1a", "暗黑 (#1a1a1a)": "#1a1a1a",
            "米黄": "#f5f5dc", "淡蓝": "#e6f7ff", "淡紫": "#f9f0ff"
        }
        bg_color = bg_color_map.get(self.geo_bg_color_combo.currentText(), "#f0f2f5")
        
        # Visualization Type
        viz_type_map = {
            "默认 (平面地图)": "default",
            "3D 柱状地图": "bar3d",
            "涟漪散点地图": "ripple",
            "高亮发光地图": "glow",
            "地域流向地图": "flow",
            "立体渐变地图": "gradient"
        }
        viz_type = viz_type_map.get(self.geo_viz_type_combo.currentText(), "default")
        
        # Bar Shape
        bar_shape_map = {
            "长方体 (Cuboid)": "cuboid",
            "圆柱体 (Cylinder)": "cylinder",
            "圆锥体 (Cone)": "cone",
            "三角锥 (Pyramid)": "pyramid",
            "三棱柱 (Prism)": "prism"
        }
        bar_shape = "cuboid"
        if hasattr(self, 'geo_bar_shape_combo'):
            bar_shape = bar_shape_map.get(self.geo_bar_shape_combo.currentText(), "cuboid")

        font = self.geo_font_combo.currentText()
        font_size = self.geo_font_size_spin.value()
        label_size = self.geo_label_size_spin.value()
        
        font_color_map = {
            "默认 (#333)": "#333", "默认 (黑)": "#333",
            "黑色 (#000)": "#000", "黑色": "#000",
            "白色 (#fff)": "#fff", "白色": "#fff",
            "灰色 (#666)": "#666", "灰色": "#666",
            "红色 (#d73027)": "#d73027", "红色": "#d73027",
            "蓝色": "#1E90FF", "绿色": "#28a745", "橙色": "#fd7e14"
        }
        font_color = font_color_map.get(self.geo_font_color_combo.currentText(), "#333")
        label_color = font_color_map.get(self.geo_label_color_combo.currentText(), "#333")
        
        border_color_map = {
            "默认 (#000)": "#000", "默认 (黑)": "#000",
            "白色 (#fff)": "#fff", "白色": "#fff",
            "灰色 (#ccc)": "#ccc", "灰色": "#ccc",
            "深灰": "#666", "浅灰": "#eee", "蓝色": "#1E90FF",
            "无描边 (transparent)": "transparent", "无描边": "transparent"
        }
        border_text = self.geo_border_color_combo.currentText()
        border_color = border_color_map.get(border_text, "#000")
        
        border_shadow_blur = 0
        border_shadow_color = 'transparent'
        
        if "发光" in border_text:
            border_shadow_blur = 10
            if "蓝" in border_text:
                border_color = "#00ffff"
                border_shadow_color = "#00ffff"
            elif "金" in border_text:
                border_color = "#ffd700"
                border_shadow_color = "#ffd700"
            elif "绿" in border_text:
                border_color = "#00ff00"
                border_shadow_color = "#00ff00"
            elif "红" in border_text:
                border_color = "#ff4d4f"
                border_shadow_color = "#ff4d4f"
        
        show_label = self.geo_show_label_check.isChecked()
        show_3d = self.geo_show_3d_check.isChecked()
        data_source = self.geo_data_source_input.text()
        author = self.geo_author_input.text()
        note = self.geo_note_input.text()
        bg_opacity = self.geo_bg_opacity_slider.value() / 100.0
        
        # Define colors for themes
        area_color = "#eee" # Default map base color
        
        colors = ['#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'] # Default
        if "蓝色" in theme and "海洋" not in theme:
            colors = ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#084594']
            area_color = "#f7fbff"
        elif "绿色" in theme and "森林" not in theme:
            colors = ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32']
            area_color = "#f7fcf5"
        elif "紫色" in theme:
            colors = ['#fcfbfd', '#efedf5', '#dadaeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#4a1486']
            area_color = "#fcfbfd"
        elif "热力红" in theme:
            colors = ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#99000d']
            area_color = "#fff5f0"
        elif "森林绿" in theme:
            colors = ['#f7fcfd', '#e5f5f9', '#ccece6', '#99d8c9', '#66c2a4', '#41ae76', '#238b45', '#005824']
            area_color = "#f7fcfd"
        elif "海洋蓝" in theme:
            colors = ['#ffffd9', '#edf8b1', '#c7e9b4', '#7fcdbb', '#41b6c4', '#1d91c0', '#225ea8', '#0c2c84']
            area_color = "#ffffd9"
        elif "经典" in theme:
            colors = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
        elif "复古" in theme:
            colors = ['#d87c7c','#919e8b','#d7ab82','#6e7074','#61a0a8','#efa18d','#787464','#cc7e63','#724e58','#4b565b']
            area_color = "#f4e9d5"
        elif "暗黑" in theme:
            colors = ['#dd6b66','#759aa0','#e69d87','#8dc1a9','#ea7e53','#eedd78','#73a373','#73b9bc','#7289ab','#91ca8c','#f49f42']
            area_color = "#333"
            if border_text == "默认 (黑)":
                border_color = "#666" # Auto adjust border for dark theme
        elif "马卡龙" in theme:
            colors = ['#2ec7c9','#b6a2de','#5ab1ef','#ffb980','#d87a80','#8d98b3','#e5cf0d','#97b552','#95706d','#dc69aa']
            area_color = "#f9f9f9"
        elif "罗马" in theme:
            colors = ['#E01F54','#001852','#f5e8c8','#b8d2c7','#c6b38e','#a4d8c2','#f3d999','#d3758f','#dcc392','#2e4783']
            area_color = "#f5e8c8"
        elif "Shine" in theme:
            colors = ['#c1232b','#27727b','#fcce10','#e87c25','#b5c334','#fe8463','#9bca63','#fad860','#f3a43b','#60c0dd']
            
        import json
        colors_json = json.dumps(colors)

        # Handle background image
        bg_image = self.geo_bg_image_path.text()
        bg_image_css = ""
        if bg_image:
            # Convert backslashes to forward slashes for JS
            bg_image = bg_image.replace("\\", "/")
            bg_image_css = f"url('file:///{bg_image}')"
        
        js = f"""
        (function() {{
            try {{
                updateConfig({{
                    visualizationType: '{viz_type}',
                    barShape: '{bar_shape}',
                    visualMapColors: {colors_json},
                    areaColor: '{area_color}',
                    backgroundColor: '{bg_color}',
                    backgroundImage: "{bg_image_css}",
                    bgOpacity: {bg_opacity},
                    fontFamily: '{font}',
                    fontSize: {font_size},
                    fontColor: '{font_color}',
                    labelSize: {label_size},
                    labelColor: '{label_color}',
                    borderColor: '{border_color}',
                    borderShadowBlur: {border_shadow_blur},
                    borderShadowColor: '{border_shadow_color}',
                    showLabel: {'true' if show_label else 'false'},
                    show3D: {'true' if show_3d else 'false'},
                    dataSource: '{data_source}',
                    author: '{author}',
                    note: '{note}'
                }});
            }} catch (e) {{}}

            try {{
                if ('{viz_type}' !== 'glow') return;
                if (typeof myChart === 'undefined' || !myChart || typeof myChart.getOption !== 'function') return;

                var opt = myChart.getOption();
                var show = {'true' if show_label else 'false'};
                var c = '{label_color}';
                var fs = {label_size};
                var ff = '{font}';
                var borderC = '{border_color}';
                var blur = {border_shadow_blur};
                var glowC = '{border_shadow_color}';
                var finalGlow = (glowC && glowC !== 'transparent') ? glowC : borderC;

                if (opt && opt.series && opt.series.length) {{
                    for (var i = 0; i < opt.series.length; i++) {{
                        var s = opt.series[i];
                        if (!s || s.type !== 'map') continue;
                        s.label = s.label || {{}};
                        s.label.show = show;
                        s.label.color = c;
                        s.label.fontSize = fs;
                        s.label.fontFamily = ff;
                        s.label.fontWeight = 'normal';
                        s.label.position = 'inside';
                        s.label.formatter = function(params) {{
                            var nm = (params && params.name) ? params.name : '';
                            try {{
                                if (typeof getShortName === 'function') nm = getShortName(nm);
                            }} catch (e) {{}}
                            var val = params ? params.value : '';
                            if (val === undefined || val === null || val === '') return nm;
                            return nm + '\\n' + val;
                        }};
                        s.labelLayout = s.labelLayout || {{}};
                        if (s.labelLayout.hideOverlap === undefined) s.labelLayout.hideOverlap = false;
                        if (s.labelLayout.moveOverlap === undefined) s.labelLayout.moveOverlap = 'shiftY';

                        s.itemStyle = s.itemStyle || {{}};
                        s.itemStyle.borderColor = borderC;
                        if (blur && blur > 0) {{
                            s.itemStyle.shadowColor = finalGlow;
                            s.itemStyle.shadowBlur = blur;
                        }}
                    }}
                    myChart.setOption(opt, true);
                }}
            }} catch (e) {{}}

            try {{
                if ('{viz_type}' !== 'bar3d' && '{viz_type}' !== 'gradient') return;
                if (typeof myChart === 'undefined' || !myChart || typeof myChart.getOption !== 'function') return;

                var opt3d = myChart.getOption();
                var show3d = {'true' if show_label else 'false'};
                var c3d = '{label_color}';
                var fs3d = {label_size};
                var ff3d = '{font}';
                var lh3d = Math.round(fs3d * 1.3);

                function parseHexColor(hex) {{
                    if (!hex) return null;
                    var s = (hex + '').trim();
                    if (s.indexOf('#') !== 0) return null;
                    s = s.slice(1);
                    if (s.length === 3) s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
                    if (s.length !== 6) return null;
                    var r = parseInt(s.slice(0, 2), 16);
                    var g = parseInt(s.slice(2, 4), 16);
                    var b = parseInt(s.slice(4, 6), 16);
                    if (isNaN(r) || isNaN(g) || isNaN(b)) return null;
                    return {{ r: r, g: g, b: b }};
                }}

                function getOutlineColor() {{
                    var bg = parseHexColor('{bg_color}');
                    if (!bg) return 'rgba(0,0,0,0.75)';
                    var luminance = (0.2126 * bg.r + 0.7152 * bg.g + 0.0722 * bg.b) / 255;
                    return luminance < 0.5 ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.75)';
                }}

                var outline3d = getOutlineColor();
                var pos3d = ('{viz_type}' === 'bar3d') ? 'top' : 'inside';
                var dist3d = ('{viz_type}' === 'bar3d') ? 6 : 0;

                if (opt3d && opt3d.series && opt3d.series.length) {{
                    var seriesPatch = new Array(opt3d.series.length);
                    for (var j = 0; j < opt3d.series.length; j++) {{
                        seriesPatch[j] = {{}};
                        var s3d = opt3d.series[j];
                        if (!s3d || s3d.type !== 'scatter3D') continue;

                        var isLabelLayer = (s3d.silent === true && (s3d.symbolSize === 1 || s3d.symbolSize === '1'));
                        if (!isLabelLayer && s3d.itemStyle) {{
                            if (s3d.itemStyle.opacity === 0) isLabelLayer = true;
                            if (s3d.itemStyle.color === 'rgba(0,0,0,0)') isLabelLayer = true;
                        }}
                        if (!isLabelLayer) continue;

                        seriesPatch[j] = {{
                            label: {{
                                show: show3d,
                                position: pos3d,
                                distance: dist3d,
                                color: c3d,
                                fontSize: fs3d,
                                fontFamily: ff3d,
                                fontWeight: 'normal',
                                align: 'center',
                                verticalAlign: 'middle',
                                textAlign: 'center',
                                textVerticalAlign: 'middle',
                                backgroundColor: 'transparent',
                                padding: 0,
                                lineHeight: lh3d,
                                textBorderColor: outline3d,
                                textBorderWidth: 4,
                                textShadowColor: outline3d,
                                textShadowBlur: 6,
                                textShadowOffsetX: 0,
                                textShadowOffsetY: 0,
                                formatter: function(params) {{
                                    var nm = (params && params.name) ? params.name : '';
                                    try {{
                                        if (typeof getShortName === 'function') nm = getShortName(nm);
                                    }} catch (e) {{}}
                                    var val = '';
                                    try {{
                                        if (params && params.data && params.data.value && params.data.value.length > 3) val = params.data.value[3];
                                        else if (params && params.value && params.value.length > 3) val = params.value[3];
                                    }} catch (e) {{}}
                                    if (val === undefined || val === null || val === '') return nm;
                                    return nm + '\\n' + val;
                                }}
                            }}
                        }};
                    }}
                    myChart.setOption({{ series: seriesPatch }}, false);
                }}
            }} catch (e) {{}}
        }})();
        """
        if hasattr(self, 'geo_map_view'):
            self.geo_map_view.page().runJavaScript(js)
        
    def export_geo_map_image(self):
        """导出地理可视化图片"""
        if not hasattr(self, 'geo_map_view'):
            return
            
        # Get default filename from topic or timestamp
        default_name = f"{self.topic_input.text()}_map.png"
        if not self.topic_input.text():
             import time
             default_name = f"geo_map_{int(time.time())}.png"
             
        file_path, _ = QFileDialog.getSaveFileName(self, "保存图片", default_name, "Images (*.png *.jpg *.bmp)")
        if not file_path:
            return
            
        # Capture the web view
        pixmap = self.geo_map_view.grab()
        if not pixmap.isNull():
            pixmap.save(file_path)
            QMessageBox.information(self, "导出成功", f"图片已保存至:\n{file_path}")
        else:
            QMessageBox.warning(self, "导出失败", "无法捕获地图画面")

    def toggle_bar_race_settings(self):
        if self.bar_race_settings_container.isVisible():
            self.bar_race_settings_container.hide()
        else:
            self.bar_race_settings_container.show()
            
    def toggle_geo_map_settings(self):
        if self.geo_map_settings_container.isVisible():
            self.geo_map_settings_container.hide()
        else:
            self.geo_map_settings_container.show()

    def create_right_panel(self):
        """创建右侧内容区"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 标签页
        self.tabs = QTabWidget()
        
        # 动画标签页
        animation_widget = QWidget()
        animation_layout = QVBoxLayout()
        animation_layout.setContentsMargins(0, 0, 0, 0)
        animation_widget.setLayout(animation_layout)
        
        if WEBENGINE_AVAILABLE:
            # WebEngineView 显示动画
            self.animation_view = QWebEngineView()
            # 允许自动播放音频
            self.animation_view.settings().setAttribute(
                QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
            )
            animation_layout.addWidget(self.animation_view)
            
            # 初始显示欢迎页
            self.animation_view.setHtml("""
            <html>
            <body style="margin: 0; display: flex; justify-content: center; align-items: center; 
                         height: 100vh; background: linear-gradient(140deg, #EEF2FF 0%, #E0E7FF 100%); 
                         font-family: 'Microsoft YaHei', sans-serif;">
                <div style="text-align: center; color: #4F46E5;">
                    <h2 style="font-size: 2em; margin-bottom: 20px;">🎬 动画演示</h2>
                    <p style="font-size: 1.2em; color: #6B7280;">请在左侧输入主题，点击"生成动画"来创建动态且带讲解的动画</p>
                </div>
            </body>
            </html>
            """)
        else:
            # 降级方案: 显示提示和浏览器打开按钮
            info_label = QLabel("动画已生成，点击下方按钮在浏览器中查看: ")
            animation_layout.addWidget(info_label)
            self.open_animation_btn = QPushButton("在浏览器中打开动画")
            self.open_animation_btn.clicked.connect(lambda: self.open_in_browser_tab(0))
            self.open_animation_btn.setEnabled(False)
            animation_layout.addWidget(self.open_animation_btn)
            animation_layout.addStretch()

        # 导出按钮(移动到动画标签页内部底部)
        export_layout = QHBoxLayout()
        export_layout.addStretch()  # 左侧弹性空间
        export_layout.setContentsMargins(10, 10, 10, 10)
        
        export_html_btn = QPushButton("导出动画 (HTML)")
        export_html_btn.clicked.connect(self.export_html)
        export_layout.addWidget(export_html_btn)
        
        export_video_btn = QPushButton("导出动画 (视频)")
        export_video_btn.clicked.connect(self.export_video)
        export_layout.addWidget(export_video_btn)
        
        export_layout.addStretch()  # 右侧弹性空间
        animation_layout.addLayout(export_layout)
        
        self.tabs.addTab(animation_widget, "动画演示")
        
        # 思维导图标签页
        mindmap_widget = QWidget()
        mindmap_layout = QVBoxLayout()
        mindmap_layout.setContentsMargins(0, 0, 0, 0)
        mindmap_widget.setLayout(mindmap_layout)
        
        # 创建分割器
        self.mindmap_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧设置面板(默认隐藏)
        self.mindmap_settings_container = QWidget()
        self.mindmap_settings_container.setMinimumWidth(320)
        self.mindmap_settings_container.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-right: 1px solid #E5E7EB;
            }
            QLabel {
                color: #374151;
            }
            QComboBox, QSpinBox {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 5px;
                background: #F9FAFB;
                min-height: 20px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox:hover, QSpinBox:hover {
                border-color: #4F46E5;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                outline: 0px;
            }
            QComboBox QAbstractItemView::item {
                color: #374151;
                padding: 8px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #4F46E5;
                color: white;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #4F46E5;
                color: white;
            }
        """)
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(0, 0, 0, 0)
        self.mindmap_settings_container.setLayout(settings_layout)
        
        # 标题栏
        header_container = QWidget()
        header_container.setStyleSheet("background-color: #EEF2FF; border-bottom: 1px solid #E0E7FF;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(15, 15, 15, 15)
        
        header_icon = QLabel("⚙️")
        header_icon.setStyleSheet("font-size: 18px; background: transparent; border: none;")
        header_layout.addWidget(header_icon)
        
        header = QLabel("思维导图设置")
        header.setStyleSheet("font-weight: bold; font-size: 16px; color: #4F46E5; background: transparent; border: none;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        settings_layout.addWidget(header_container)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(15, 10, 15, 10)
        content_layout.setSpacing(10)
        scroll_content.setLayout(content_layout)
        scroll.setWidget(scroll_content)
        settings_layout.addWidget(scroll)
        
        # 辅助函数: 优化下拉框样式 (强制使用 QListView 以支持 QSS)
        def setup_combo_view(combo):
            view = QListView()
            combo.setView(view)
            view.setStyleSheet("""
                QListView {
                    background-color: #FFFFFF;
                    border: 1px solid #D1D5DB;
                    outline: 0px;
                }
                QListView::item {
                    color: #374151;
                    padding: 8px;
                    min-height: 24px;
                }
                QListView::item:hover {
                    background-color: #4F46E5;
                    color: white;
                }
                QListView::item:selected {
                    background-color: #4F46E5;
                    color: white;
                }
            """)
            
        def setup_spin_view(spin):
            spin.setStyleSheet("""
                QSpinBox {
                    border: 1px solid #D1D5DB;
                    padding: 4px;
                    border-radius: 4px;
                    min-height: 24px;
                    background-color: #FFFFFF;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    width: 20px;
                    border-width: 1px;
                }
            """)

        # 辅助函数：添加设置行 (Label + Widget)
        def add_setting_row(layout, label_text, widget):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #4B5563; min-width: 80px; font-weight: 500;")
            row.addWidget(lbl)
            
            # Make widget expand
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(widget)
            
            layout.addLayout(row)

        # --- Section 1: Structure & Line ---
        lbl_struct = QLabel("结构与线条")
        lbl_struct.setStyleSheet("font-weight: bold; color: #4F46E5; margin-top: 5px; margin-bottom: 5px; font-size: 13px;")
        content_layout.addWidget(lbl_struct)

        self.mm_structure_combo = QComboBox()
        setup_combo_view(self.mm_structure_combo)
        self.mm_structure_combo.addItems([
            "经典思维导图 (默认)", "逻辑结构图 (向右)", "逻辑结构图 (向左)", "双向思维导图 (左右扩散)",
            "圆形辐射图 (Radial)", "扇形图 (Sunburst)", "流程图 (Flowchart)", "泳道图 (Swimlane)",
            "甘特图 (Gantt)", "韦恩图 (Venn)", "拓扑图 (Topology)", "玫瑰图 (Rose)", "人物关系图 (Relationship)"
        ])
        self.mm_structure_combo.currentTextChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_structure_combo.setToolTip("图形结构")
        add_setting_row(content_layout, "🕸️ 结构布局", self.mm_structure_combo)

        self.mm_line_style_combo = QComboBox()
        setup_combo_view(self.mm_line_style_combo)
        self.mm_line_style_combo.addItems(["默认 (Bezier)", "直线 (Straight)", "折线 (Polyline)", "渐变 (Gradient)", "多彩 (Colorful)", "渐细 (Tapered)"])
        self.mm_line_style_combo.currentTextChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_line_style_combo.setToolTip("连接线样式")
        add_setting_row(content_layout, "〰️ 线条样式", self.mm_line_style_combo)
        
        self.mm_line_width_spin = QSpinBox()
        setup_spin_view(self.mm_line_width_spin)
        self.mm_line_width_spin.setRange(1, 10)
        self.mm_line_width_spin.setValue(2)
        self.mm_line_width_spin.setSuffix("px")
        self.mm_line_width_spin.valueChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_line_width_spin.setToolTip("连接线粗细")
        add_setting_row(content_layout, "📏 线条粗细", self.mm_line_width_spin)

        # --- Section 2: Appearance (Theme & BG) ---
        lbl_appear = QLabel("外观风格")
        lbl_appear.setStyleSheet("font-weight: bold; color: #4F46E5; margin-top: 15px; margin-bottom: 5px; font-size: 13px;")
        content_layout.addWidget(lbl_appear)

        self.mm_theme_combo = QComboBox()
        setup_combo_view(self.mm_theme_combo)
        self.mm_theme_combo.addItems(["默认 (浅色)", "深色模式", "护眼模式"])
        self.mm_theme_combo.currentTextChanged.connect(self.on_mm_theme_changed)
        self.mm_theme_combo.setToolTip("主题模式")
        add_setting_row(content_layout, "🌓 主题模式", self.mm_theme_combo)

        self.mm_palette_combo = QComboBox()
        setup_combo_view(self.mm_palette_combo)
        self.mm_palette_combo.addItems(["默认 (Markmap)", "多彩 (Vivid)", "冷色 (Cool)", "暖色 (Warm)", "莫兰迪 (Morandi)", "复古 (Retro)", "清新 (Fresh)", "暗黑 (Dark)", "马卡龙 (Macaron)", "彩虹 (Rainbow)", "商务 (Business)", "高雅 (Elegant)"])
        self.mm_palette_combo.currentTextChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_palette_combo.setToolTip("配色方案")
        add_setting_row(content_layout, "🎨 配色方案", self.mm_palette_combo)

        self.mm_bg_color_combo = QComboBox()
        setup_combo_view(self.mm_bg_color_combo)
        self.bg_presets = {
            "默认 (浅蓝灰)": "#f0f2ff",
            "纯净白 (White)": "#ffffff",
            "极简灰 (Gray)": "#f3f4f6",
            "护眼黄 (Beige)": "#f5f5dc",
            "复古纸 (Paper)": "#fdf6e3",
            "清新绿 (Mint)": "#ecfdf5",
            "浪漫粉 (Pink)": "#fff1f2",
            "深邃黑 (Dark)": "#1a1a1a",
            "午夜蓝 (Midnight)": "#1e293b",
            "自定义...": "custom"
        }
        self.mm_bg_color_combo.addItems(list(self.bg_presets.keys()))
        self.mm_bg_color_combo.currentIndexChanged.connect(self.on_bg_combo_changed)
        
        self.mm_bg_color = "#f0f2ff" # 默认浅蓝灰
        self.mm_bg_color_combo.setToolTip("背景颜色")
        add_setting_row(content_layout, "🌈 背景颜色", self.mm_bg_color_combo)

        # --- Section 3: Text (Font & Color) ---
        lbl_text = QLabel("文字设置")
        lbl_text.setStyleSheet("font-weight: bold; color: #4F46E5; margin-top: 15px; margin-bottom: 5px; font-size: 13px;")
        content_layout.addWidget(lbl_text)

        self.mm_font_combo = QComboBox()
        setup_combo_view(self.mm_font_combo)
        
        # Load system fonts
        system_fonts = QFontDatabase.families()
        common_fonts = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi", "Arial", "Segoe UI", "Times New Roman"]
        sorted_fonts = sorted(list(set(system_fonts)))
        
        # Move common fonts to top
        for f in reversed(common_fonts):
            if f in sorted_fonts:
                sorted_fonts.remove(f)
                sorted_fonts.insert(0, f)
                
        self.mm_font_combo.addItems(sorted_fonts)
        self.mm_font_combo.currentTextChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_font_combo.setToolTip("字体")
        add_setting_row(content_layout, "🅰️ 字体选择", self.mm_font_combo)

        self.mm_font_size_spin = QSpinBox()
        setup_spin_view(self.mm_font_size_spin)
        self.mm_font_size_spin.setRange(10, 36)
        self.mm_font_size_spin.setValue(16)
        self.mm_font_size_spin.setSuffix("px")
        self.mm_font_size_spin.valueChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_font_size_spin.setToolTip("字体大小")
        add_setting_row(content_layout, "🔡 字体大小", self.mm_font_size_spin)
        
        self.mm_text_color_combo = QComboBox()
        setup_combo_view(self.mm_text_color_combo)
        self.text_presets = {
            "默认 (深灰)": "#1f2937",
            "纯黑 (Black)": "#000000",
            "纯白 (White)": "#ffffff",
            "深蓝 (Dark Blue)": "#1e3a8a",
            "深红 (Dark Red)": "#7f1d1d",
            "深绿 (Dark Green)": "#14532d",
            "自定义...": "custom"
        }
        self.mm_text_color_combo.addItems(list(self.text_presets.keys()))
        self.mm_text_color_combo.currentIndexChanged.connect(self.on_text_combo_changed)
        self.mm_text_color = "#1f2937"
        self.mm_text_color_combo.setToolTip("字体颜色")
        add_setting_row(content_layout, "🖍️ 字体颜色", self.mm_text_color_combo)

        self.mm_text_outline_combo = QComboBox()
        setup_combo_view(self.mm_text_outline_combo)
        self.text_outline_presets = {
            "无 (None)": "transparent",
            "纯白 (White)": "#ffffff",
            "纯黑 (Black)": "#000000",
            "浅灰 (Light Gray)": "#f3f4f6",
            "自定义...": "custom"
        }
        self.mm_text_outline_combo.addItems(list(self.text_outline_presets.keys()))
        self.mm_text_outline_combo.currentIndexChanged.connect(self.on_text_outline_combo_changed)
        self.mm_text_outline_color = "transparent"
        self.mm_text_outline_combo.setToolTip("字体描边")
        add_setting_row(content_layout, "🔲 字体描边", self.mm_text_outline_combo)

        # --- Section 4: Advanced (Expand, Freeze, Width, Icon) ---
        lbl_adv = QLabel("高级选项")
        lbl_adv.setStyleSheet("font-weight: bold; color: #4F46E5; margin-top: 15px; margin-bottom: 5px; font-size: 13px;")
        content_layout.addWidget(lbl_adv)

        self.mm_expand_spin = QSpinBox()
        setup_spin_view(self.mm_expand_spin)
        self.mm_expand_spin.setRange(1, 10)
        self.mm_expand_spin.setValue(2)
        self.mm_expand_spin.setPrefix("展开:")
        self.mm_expand_spin.valueChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_expand_spin.setToolTip("初始展开层级")
        add_setting_row(content_layout, "📂 展开层级", self.mm_expand_spin)
        
        self.mm_freeze_spin = QSpinBox()
        setup_spin_view(self.mm_freeze_spin)
        self.mm_freeze_spin.setRange(0, 10)
        self.mm_freeze_spin.setValue(0)
        self.mm_freeze_spin.setPrefix("冻结:")
        self.mm_freeze_spin.valueChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_freeze_spin.setToolTip("颜色冻结层级")
        add_setting_row(content_layout, "❄️ 颜色冻结", self.mm_freeze_spin)
        
        self.mm_max_width_spin = QSpinBox()
        setup_spin_view(self.mm_max_width_spin)
        self.mm_max_width_spin.setRange(100, 1000)
        self.mm_max_width_spin.setValue(300)
        self.mm_max_width_spin.setSuffix("px")
        self.mm_max_width_spin.setPrefix("宽:")
        self.mm_max_width_spin.valueChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_max_width_spin.setToolTip("节点最大宽度")
        add_setting_row(content_layout, "↔️ 节点宽度", self.mm_max_width_spin)
        
        self.mm_icon_combo = QComboBox()
        setup_combo_view(self.mm_icon_combo)
        self.mm_icon_combo.addItems(["无 (None)", "自动匹配 (Auto)", "商务 (Business)", "创意 (Creative)", "简约 (Minimal)", "自然 (Nature)", "科技 (Tech)", "教育 (Education)", "生活 (Life)"])
        self.mm_icon_combo.currentTextChanged.connect(lambda: self.apply_mindmap_settings(silent=True))
        self.mm_icon_combo.setToolTip("图标主题")
        add_setting_row(content_layout, "🧩 图标主题", self.mm_icon_combo)
        
        content_layout.addStretch()
        
        # 底部按钮
        btn_container = QWidget()
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(15, 10, 15, 15)
        
        apply_btn = QPushButton("应用设置")
        apply_btn.clicked.connect(self.apply_mindmap_settings)
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5; 
                color: white; 
                font-weight: bold; 
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(lambda: self.mindmap_settings_container.hide())
        close_btn.setStyleSheet("background: transparent; color: #6B7280; border: 1px solid #D1D5DB;")
        
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(apply_btn)
        btn_container.setLayout(btn_layout)
        
        settings_layout.addWidget(btn_container)
        
        self.mindmap_settings_container.hide() # 默认隐藏
        self.mindmap_splitter.addWidget(self.mindmap_settings_container)

        # 右侧预览容器
        preview_container = QWidget()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0,0,0,0)
        preview_container.setLayout(preview_layout)
        
        if WEBENGINE_AVAILABLE:
            self.mindmap_view = QWebEngineView()
            # 初始化时即启用所有必要权限
            settings = self.mindmap_view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            
            preview_layout.addWidget(self.mindmap_view)
            self.mindmap_view.setHtml("""
            <html>
            <body style="margin: 0; display: flex; justify-content: center; align-items: center; 
                         height: 100vh; background: #f0f2ff; font-family: 'Microsoft YaHei', sans-serif;">
                <div style="text-align: center; color: #059669;">
                    <h2 style="font-size: 2em; margin-bottom: 20px;">✳️ 思维导图</h2>
                    <p style="font-size: 1.2em; color: #6B7280;">请在左侧输入主题，点击"生成思维导图"</p>
                </div>
            </body>
            </html>
            """)
        else:
            self.mindmap_label = QLabel("思维导图功能需要 WebEngine 支持")
            self.mindmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(self.mindmap_label)
            
        self.mindmap_splitter.addWidget(preview_container)
        
        # 设置分割比例 (编辑器:预览 = 1:2)
        self.mindmap_splitter.setStretchFactor(0, 1)
        self.mindmap_splitter.setStretchFactor(1, 2)
        
        mindmap_layout.addWidget(self.mindmap_splitter)
            
        # 底部工具栏
        mm_tools = QHBoxLayout()
        mm_tools.setContentsMargins(10, 5, 10, 5)
        
        self.edit_mindmap_btn = QPushButton("🎨 外观设置")
        self.edit_mindmap_btn.clicked.connect(self.toggle_mindmap_settings)
        self.edit_mindmap_btn.setEnabled(False)
        mm_tools.addWidget(self.edit_mindmap_btn)
        
        self.edit_content_btn = QPushButton("✏️ 编辑内容")
        self.edit_content_btn.clicked.connect(self.edit_mindmap_content)
        self.edit_content_btn.setEnabled(False)
        mm_tools.addWidget(self.edit_content_btn)
        
        mm_tools.addStretch()
        
        self.open_mindmap_btn = QPushButton("在浏览器中打开")
        self.open_mindmap_btn.clicked.connect(self.open_mindmap_in_browser)
        self.open_mindmap_btn.setEnabled(False)
        mm_tools.addWidget(self.open_mindmap_btn)

        self.export_mindmap_btn = QPushButton("导出HTML")
        self.export_mindmap_btn.clicked.connect(self.export_mindmap)
        self.export_mindmap_btn.setEnabled(False)
        mm_tools.addWidget(self.export_mindmap_btn)
        
        self.export_image_btn = QPushButton("导出图片")
        self.export_image_btn.clicked.connect(self.export_mindmap_image)
        self.export_image_btn.setEnabled(False)
        mm_tools.addWidget(self.export_image_btn)
        
        mindmap_layout.addLayout(mm_tools)
            
        self.tabs.addTab(mindmap_widget, "思维导图")
        
        # 动态排序图标签页
        bar_race_widget = QWidget()
        bar_race_layout = QVBoxLayout()
        bar_race_layout.setContentsMargins(0, 0, 0, 0)
        bar_race_widget.setLayout(bar_race_layout)

        # Create Splitter
        self.bar_race_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Settings Panel
        self.bar_race_settings_container = self.create_bar_race_settings_panel()
        self.bar_race_settings_container.hide()
        self.bar_race_splitter.addWidget(self.bar_race_settings_container)

        # Preview Container
        br_preview_container = QWidget()
        br_preview_layout = QVBoxLayout()
        br_preview_layout.setContentsMargins(0,0,0,0)
        br_preview_container.setLayout(br_preview_layout)

        if WEBENGINE_AVAILABLE:
            self.bar_race_view = QWebEngineView()
            self.bar_race_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            self.bar_race_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            self.bar_race_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            
            br_preview_layout.addWidget(self.bar_race_view)
            self.bar_race_view.setHtml("""
            <html>
            <body style="margin: 0; display: flex; justify-content: center; align-items: center; 
                         height: 100vh; background: #f0f2f5; font-family: 'Microsoft YaHei', sans-serif;">
                <div style="text-align: center; color: #7C3AED;">
                    <h2 style="font-size: 2em; margin-bottom: 20px;">📊 动态排序图</h2>
                    <p style="font-size: 1.2em; color: #6B7280;">展示数据随时间的变化趋势</p>
                </div>
            </body>
            </html>
            """)
        else:
             info_label = QLabel("WebEngine不可用")
             br_preview_layout.addWidget(info_label)
        
        self.bar_race_splitter.addWidget(br_preview_container)
        self.bar_race_splitter.setStretchFactor(0, 1)
        self.bar_race_splitter.setStretchFactor(1, 3)
        
        bar_race_layout.addWidget(self.bar_race_splitter)
        
        # Toolbar
        br_tools = QHBoxLayout()
        br_tools.setContentsMargins(10, 5, 10, 5)
        
        self.br_settings_btn = QPushButton("🎨 外观设置")
        self.br_settings_btn.clicked.connect(self.toggle_bar_race_settings)
        br_tools.addWidget(self.br_settings_btn)
        
        br_tools.addStretch()

        # 重播按钮
        self.br_replay_btn = QPushButton("🔄 重播动画")
        self.br_replay_btn.setStyleSheet("QPushButton { background-color: #4F46E5; color: white; border: none; border-radius: 4px; padding: 6px 12px; } QPushButton:hover { background-color: #4338CA; }")
        self.br_replay_btn.clicked.connect(self.replay_bar_race)
        br_tools.addWidget(self.br_replay_btn)

        # 导出视频按钮
        self.br_export_video_btn = QPushButton("🎬 导出视频")
        self.br_export_video_btn.setStyleSheet("QPushButton { background-color: #EF4444; color: white; border: none; border-radius: 4px; padding: 6px 12px; } QPushButton:hover { background-color: #DC2626; }")
        self.br_export_video_btn.clicked.connect(self.export_bar_race_video)
        br_tools.addWidget(self.br_export_video_btn)

        bar_race_layout.addLayout(br_tools)

        self.tabs.addTab(bar_race_widget, "动态排序图")

        # 地理可视化标签页
        geo_map_widget = QWidget()
        geo_map_layout = QVBoxLayout()
        geo_map_layout.setContentsMargins(0, 0, 0, 0)
        geo_map_widget.setLayout(geo_map_layout)

        # Create Splitter
        self.geo_map_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Settings Panel
        self.geo_map_settings_container = self.create_geo_map_settings_panel()
        self.geo_map_settings_container.hide()
        self.geo_map_splitter.addWidget(self.geo_map_settings_container)
        
        # Preview Container
        geo_preview_container = QWidget()
        geo_preview_layout = QVBoxLayout()
        geo_preview_layout.setContentsMargins(0,0,0,0)
        geo_preview_container.setLayout(geo_preview_layout)

        if WEBENGINE_AVAILABLE:
            self.geo_map_view = QWebEngineView()
            self.geo_map_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            self.geo_map_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            self.geo_map_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            
            geo_preview_layout.addWidget(self.geo_map_view)
            self.geo_map_view.setHtml("""
            <html>
            <body style="margin: 0; display: flex; justify-content: center; align-items: center; 
                         height: 100vh; background: #f0f2f5; font-family: 'Microsoft YaHei', sans-serif;">
                <div style="text-align: center; color: #2563EB;">
                    <h2 style="font-size: 2em; margin-bottom: 20px;">🗺️ 地理数据可视化</h2>
                    <p style="font-size: 1.2em; color: #6B7280;">展示中国各省份数据分布情况</p>
                </div>
            </body>
            </html>
            """)
        else:
             info_label = QLabel("WebEngine不可用")
             geo_preview_layout.addWidget(info_label)
        
        self.geo_map_splitter.addWidget(geo_preview_container)
        self.geo_map_splitter.setStretchFactor(0, 1)
        self.geo_map_splitter.setStretchFactor(1, 3)
        
        geo_map_layout.addWidget(self.geo_map_splitter)
        
        # Toolbar
        geo_tools = QHBoxLayout()
        geo_tools.setContentsMargins(10, 5, 10, 5)
        
        self.geo_settings_btn = QPushButton("🎨 外观设置")
        self.geo_settings_btn.clicked.connect(self.toggle_geo_map_settings)
        geo_tools.addWidget(self.geo_settings_btn)
        
        geo_tools.addStretch()
        
        # Export Image Button (Moved to right side)
        self.geo_export_btn = QPushButton("📷 导出图片")
        self.geo_export_btn.setStyleSheet("QPushButton { background-color: #EF4444; color: white; border: none; border-radius: 4px; padding: 6px 12px; } QPushButton:hover { background-color: #DC2626; }")
        self.geo_export_btn.clicked.connect(self.export_geo_map_image)
        geo_tools.addWidget(self.geo_export_btn)
        
        geo_map_layout.addLayout(geo_tools)

        self.tabs.addTab(geo_map_widget, "地理可视化")
        

        # 设置 tabs 的大小策略，确保其尽可能填充空间
        size_policy = self.tabs.sizePolicy()
        size_policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
        size_policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        self.tabs.setSizePolicy(size_policy)
        
        layout.addWidget(self.tabs)
        
        return panel
    
    def show_input_dialog(self, mode):
        """显示通用输入对话框"""
        # 获取当前输入框的内容作为默认主题
        default_topic = self.topic_input.text().strip()
        
        dialog = UniversalInputDialog(mode, default_topic, self)
        if dialog.exec():
            # 兼容旧代码，如果没有manual_review则默认为False
            text_length = 0
            if len(dialog.result_data) == 7:
                type_, topic, content, manual_review, language, frame_count, text_length = dialog.result_data
            elif len(dialog.result_data) == 6:
                type_, topic, content, manual_review, language, frame_count = dialog.result_data
            elif len(dialog.result_data) == 5:
                type_, topic, content, manual_review, language = dialog.result_data
                frame_count = 8
            elif len(dialog.result_data) == 4:
                type_, topic, content, manual_review = dialog.result_data
                language = "zh"
                frame_count = 8
            else:
                type_, topic, content = dialog.result_data
                manual_review = False
                language = "zh"
                frame_count = 8
            
            # 更新主界面输入框，确保generate_visualization能获取到正确的主题
            self.topic_input.setText(topic)
            
            if type_ == "topic":
                self.generate_visualization(mode, content=None, manual_review=manual_review, language=language, frame_count=frame_count, text_length=text_length)
            else:
                # 按内容生成
                self.generate_visualization(mode, content=content, manual_review=manual_review, language=language, frame_count=frame_count, text_length=text_length)

    def show_content_review_dialog(self, svg_code, storyboard, event):
        """显示内容复核对话框"""
        try:
            # 在主线程创建并显示对话框
            dialog = ContentReviewDialog(svg_code, storyboard, self)
            if dialog.exec():
                new_svg, new_storyboard = dialog.get_data()
                # 更新GenerationThread中的结果
                if self.generation_thread:
                     self.generation_thread.review_results = (new_svg, new_storyboard)
            else:
                if self.generation_thread:
                     self.generation_thread.review_results = None
        except Exception as e:
            print(f"显示复核对话框出错: {e}")
            import traceback
            traceback.print_exc()
            if self.generation_thread:
                 self.generation_thread.review_results = None
        finally:
            # 必须设置事件，否则线程会永久阻塞
            event.set()

    def generate_visualization(self, mode="animation", content=None, manual_review=False, language="zh", frame_count=8, text_length=0):
        """生成可视化"""
        topic = self.topic_input.text().strip()
        if not topic:
            QMessageBox.warning(self, "提示", "请输入主题")
            return
        
        custom_prompt = None
        
        # 如果需要人工复核，先获取提示词
        if manual_review and mode == "animation":
            try:
                # 提示用户正在获取提示词
                self.status_label.setText("正在获取提示词以供复核...")
                QApplication.processEvents()
                
                # 获取提示词 (这里需要同步调用，或者使用run_until_complete)
                # 由于是在主线程，简单的直接构造提示词即可，不需要调用LLM
                # LLMClient.get_animation_prompt 只是读取模版并填充，不涉及网络请求
                
                # 注意：LLMClient.get_animation_prompt 是同步方法还是异步方法？
                # 根据之前的修改，get_animation_prompt 只是 self._load_prompt(...).format(...)，应该是同步的。
                # 让我们确认一下 LLMClient 的定义。如果之前修改为异步了，这里需要注意。
                # 但通常 get_prompt 只是准备文本，应该是同步的。
                
                prompt = self.llm_client.get_animation_prompt(topic, content, language=language, frame_count=frame_count)
                
                review_dialog = PromptReviewDialog(prompt, self)
                if review_dialog.exec():
                    custom_prompt = review_dialog.get_prompt()
                else:
                    self.status_label.setText("已取消生成")
                    return
            except Exception as e:
                QMessageBox.warning(self, "错误", f"获取提示词失败: {e}")
                self.status_label.setText("")
                return
        
        # 禁用按钮，显示进度
        self.generate_btn.setEnabled(False)
        self.mindmap_btn.setEnabled(False)
        if hasattr(self, 'bar_race_btn'):
            self.bar_race_btn.setEnabled(False)
        if hasattr(self, 'geo_map_btn'):
            self.geo_map_btn.setEnabled(False)
        self.progress_bar.show()
        
        # 启动后台线程
        self.generation_thread = GenerationThread(
            self.orchestrator, 
            self.llm_client,
            topic,
            self.settings,
            mode=mode,
            content=content,
            custom_prompt=custom_prompt,
            manual_review=manual_review,
            language=language,
            frame_count=frame_count,
            text_length=text_length
        )
        self.generation_thread.progress.connect(self.on_progress)
        self.generation_thread.finished.connect(self.on_generation_finished)
        self.generation_thread.error.connect(self.on_generation_error)
        self.generation_thread.review_requested.connect(self.show_content_review_dialog)
        self.generation_thread.start()

    def on_progress(self, message):
        """更新进度"""
        self.status_label.setText(message)
    
    def on_generation_finished(self, result):
        """生成完成"""
        self.generate_btn.setEnabled(True)
        self.mindmap_btn.setEnabled(True)
        if hasattr(self, 'bar_race_btn'):
            self.bar_race_btn.setEnabled(True)
        if hasattr(self, 'geo_map_btn'):
            self.geo_map_btn.setEnabled(True)
        self.progress_bar.hide()
        
        
        self.current_result = result
        
        result_type = result.get("type", "animation")
        
        # 根据是否在线生成显示不同的状态
        is_online = result.get("is_online", False)
        
        if is_online:
            self.status_label.setText("生成完成！")
            self.status_label.setStyleSheet("color: #4C51BF; margin-top: 10px;")
        else:
            # 使用离线模式
            self.status_label.setText("生成完成！(使用默认内容)")
            self.status_label.setStyleSheet("color: #FFA500; margin-top: 10px;")
        
        # 刷新历史记录
        self.refresh_history_list()
        
        # 如果是思维导图，强制应用一次本地渲染设置，以确保获得最新的交互功能(菜单等)
        if result_type == "mindmap":
            # 确保 current_result 已设置
            self.current_result = result
            self.apply_mindmap_settings(silent=True)
        else:
            # 显示结果
            self.display_results(result)

    def on_generation_error(self, error_msg):
        """生成错误"""
        self.generate_btn.setEnabled(True)
        self.mindmap_btn.setEnabled(True)
        if hasattr(self, 'bar_race_btn'):
            self.bar_race_btn.setEnabled(True)
        if hasattr(self, 'geo_map_btn'):
            self.geo_map_btn.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText("")
        QMessageBox.critical(self, "错误", error_msg)
    
    def display_results(self, result):
        """显示生成结果"""
        topic = result.get("topic", "")
        self.current_topic = topic
        result_type = result.get("type", "animation")
        
        if result_type == "animation":
            # 加载动画
            animation_file = result.get("animation_file", "")
            if animation_file:
                animation_path = RESOURCE_DIR / animation_file
                if animation_path.exists():
                    if WEBENGINE_AVAILABLE and hasattr(self, 'animation_view'):
                        url = QUrl.fromLocalFile(str(animation_path.absolute()))
                        self.animation_view.load(url)
                        print(f"[GUI] 加载动画: {url.toString()}")
                    elif hasattr(self, 'open_animation_btn'):
                        self.open_animation_btn.setEnabled(True)
                else:
                    print(f"[GUI] 动画文件不存在: {animation_path}")
            
            # 切换到动画标签
            self.tabs.setCurrentIndex(0)
            
        elif result_type == "bar_race":
            # 加载动态排序图
            bar_race_file = result.get("bar_race_file", "")
            if bar_race_file:
                bar_race_path = RESOURCE_DIR / bar_race_file
                print(f"[GUI] 尝试加载动态排序图: {bar_race_path}")
                
                if bar_race_path.exists():
                    if WEBENGINE_AVAILABLE and hasattr(self, 'bar_race_view'):
                        url = QUrl.fromLocalFile(str(bar_race_path.absolute()))
                        self.bar_race_view.load(url)
                else:
                    print(f"[GUI] 动态排序图文件不存在: {bar_race_path}")
            
            # 切换到动态排序图标签
            self.tabs.setCurrentIndex(2)

        elif result_type == "mindmap":
            # 加载思维导图
            mindmap_file = result.get("mindmap_file", "")
            if mindmap_file:
                mindmap_path = RESOURCE_DIR / mindmap_file
                print(f"[GUI] 尝试加载思维导图: {mindmap_path}")
                
                if mindmap_path.exists():
                    # 启用按钮
                    if hasattr(self, 'open_mindmap_btn'):
                        self.open_mindmap_btn.setEnabled(True)
                    if hasattr(self, 'edit_mindmap_btn'):
                        self.edit_mindmap_btn.setEnabled(True)
                    if hasattr(self, 'edit_content_btn'):
                        self.edit_content_btn.setEnabled(True)
                    if hasattr(self, 'export_mindmap_btn'):
                        self.export_mindmap_btn.setEnabled(True)
                    if hasattr(self, 'export_image_btn'):
                        self.export_image_btn.setEnabled(True)
                    
                    # 如果设置面板是打开的，可能需要更新状态(此处暂不处理)
                    pass
                        
                    if WEBENGINE_AVAILABLE and hasattr(self, 'mindmap_view'):
                        try:
                            # 再次确认权限开启
                            self.mindmap_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
                            
                            # 读取内容并直接设置
                            html_content = mindmap_path.read_text(encoding="utf-8")
                            print(f"[GUI] 读取HTML内容长度: {len(html_content)}")
                            print(f"[GUI] HTML前100字符: {html_content[:100]}")
                            
                            # 构建正确的 BaseURL (以目录为基准)
                            base_url = QUrl.fromLocalFile(str(mindmap_path.parent.absolute()) + "/")
                            self.mindmap_view.setHtml(html_content, baseUrl=base_url)
                            print(f"[GUI] WebEngine加载思维导图成功, BaseURL: {base_url.toString()}")
                        except Exception as e:
                            print(f"[GUI] 加载思维导图出错: {e}")
                            # 降级方案
                            url = QUrl.fromLocalFile(str(mindmap_path.absolute()))
                            self.mindmap_view.load(url)
                else:
                    print(f"[GUI] 思维导图文件不存在: {mindmap_path}")
            
            # 切换到思维导图标签
            self.tabs.setCurrentIndex(1)

        elif result_type == "geo_map":
            # 加载地理数据可视化
            geo_map_file = result.get("geo_map_file", "")
            if geo_map_file:
                geo_map_path = RESOURCE_DIR / geo_map_file
                print(f"[GUI] 尝试加载地理数据可视化: {geo_map_path}")
                
                if geo_map_path.exists():
                    if WEBENGINE_AVAILABLE and hasattr(self, 'geo_map_view'):
                        try:
                            # 修复相对路径问题：使用base URL指向maps目录
                            # 注意：QWebEngineView需要绝对路径的base URL才能正确加载相对路径引用的资源
                            html_content = geo_map_path.read_text(encoding="utf-8")
                            
                            # 确定base URL
                            if getattr(sys, 'frozen', False):
                                # 打包环境下
                                base_dir = RESOURCE_DIR / "maps"
                            else:
                                # 开发环境下
                                base_dir = RESOURCE_DIR / "maps"
                                
                            # 确保base_dir以/结尾
                            base_url_str = str(base_dir.absolute()).replace("\\", "/")
                            if not base_url_str.endswith("/"):
                                base_url_str += "/"
                            
                            base_url = QUrl(f"file:///{base_url_str}")
                            
                            print(f"[GUI] 加载地理数据可视化: base URL = {base_url.toString()}")
                            self.geo_map_view.setHtml(html_content, baseUrl=base_url)
                        except Exception as e:
                            print(f"[GUI] 加载地图失败: {e}")
                            # 回退到直接加载文件
                            url = QUrl.fromLocalFile(str(geo_map_path.absolute()))
                            self.geo_map_view.load(url)
                else:
                    print(f"[GUI] 地理数据可视化文件不存在: {geo_map_path}")
            
            # 切换到地理可视化标签
            self.tabs.setCurrentIndex(3)

    

    def on_bg_combo_changed(self, index):
        """背景颜色下拉框变化"""
        text = self.mm_bg_color_combo.currentText()
        color_code = self.bg_presets.get(text)
        
        if color_code == "custom":
             self.choose_mm_bg_color()
        elif color_code:
             self.mm_bg_color = color_code
             
    def on_text_combo_changed(self, index):
        """字体颜色下拉框变化"""
        text = self.mm_text_color_combo.currentText()
        color_code = self.text_presets.get(text)
        
        if color_code == "custom":
             self.choose_mm_text_color()
        elif color_code:
             self.mm_text_color = color_code

    def on_mm_theme_changed(self, text):
        """当主题改变时，自动更新背景色和字体色选择"""
        target_bg = "默认 (浅蓝灰)"
        target_text = "默认 (深灰)"
        
        if text == "深色模式":
            target_bg = "深邃黑 (Dark)"
            target_text = "纯白 (White)"
        elif text == "护眼模式":
            target_bg = "护眼黄 (Beige)"
            target_text = "默认 (深灰)"
            
        # Update BG
        index = self.mm_bg_color_combo.findText(target_bg)
        if index >= 0:
            self.mm_bg_color_combo.blockSignals(True)
            self.mm_bg_color_combo.setCurrentIndex(index)
            self.mm_bg_color_combo.blockSignals(False)
            color_code = self.bg_presets.get(target_bg)
            if color_code:
                self.mm_bg_color = color_code
                
        # Update Text
        index = self.mm_text_color_combo.findText(target_text)
        if index >= 0:
            self.mm_text_color_combo.blockSignals(True)
            self.mm_text_color_combo.setCurrentIndex(index)
            self.mm_text_color_combo.blockSignals(False)
            color_code = self.text_presets.get(target_text)
            if color_code:
                self.mm_text_color = color_code

    def choose_mm_text_color(self):
        """选择字体颜色 (自定义)"""
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(self.mm_text_color), self, "选择字体颜色")
        if color.isValid():
            self.mm_text_color = color.name()
            
            idx = self.mm_text_color_combo.findText("自定义...")
            if idx >= 0:
                self.mm_text_color_combo.blockSignals(True)
                self.mm_text_color_combo.setCurrentIndex(idx)
                self.mm_text_color_combo.blockSignals(False)
            
            if self.mm_theme_combo.currentText() != "默认 (浅色)":
                self.mm_theme_combo.blockSignals(True)
                self.mm_theme_combo.setCurrentIndex(0)
                self.mm_theme_combo.blockSignals(False)

    def choose_mm_bg_color(self):
        """选择背景颜色 (自定义)"""
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(self.mm_bg_color), self, "选择背景颜色")
        if color.isValid():
            self.mm_bg_color = color.name()
            
            # 临时把 Combo 设为 "自定义..."
            idx = self.mm_bg_color_combo.findText("自定义...")
            if idx >= 0:
                self.mm_bg_color_combo.blockSignals(True)
                self.mm_bg_color_combo.setCurrentIndex(idx)
                self.mm_bg_color_combo.blockSignals(False)
            
            # 如果自定义了颜色，将主题选为默认 (防止冲突)
            if self.mm_theme_combo.currentText() != "默认 (浅色)":
                self.mm_theme_combo.blockSignals(True)
                self.mm_theme_combo.setCurrentIndex(0)
                self.mm_theme_combo.blockSignals(False)

    def on_text_outline_combo_changed(self, index):
        """当字体描边选择改变时"""
        text = self.mm_text_outline_combo.currentText()
        if text == "自定义...":
            self.choose_mm_text_outline_color()
        else:
            self.mm_text_outline_color = self.text_outline_presets.get(text, "transparent")
            
    def choose_mm_text_outline_color(self):
        """选择字体描边颜色 (自定义)"""
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(self.mm_text_outline_color), self, "选择字体描边颜色")
        if color.isValid():
            self.mm_text_outline_color = color.name()
            
            idx = self.mm_text_outline_combo.findText("自定义...")
            if idx >= 0:
                self.mm_text_outline_combo.blockSignals(True)
                self.mm_text_outline_combo.setCurrentIndex(idx)
                self.mm_text_outline_combo.blockSignals(False)

    def apply_mindmap_settings(self, silent=False):
        """应用思维导图设置"""
        if not self.current_result:
            return
            
        topic = self.current_result.get("topic", "mindmap")
        original_content = self.current_result.get("mindmap_content", "")
        
        # 1. 准备Frontmatter
        palette_map = {
            "默认 (Markmap)": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"],
            "多彩 (Vivid)": ["#2980b9", "#e74c3c", "#f1c40f", "#27ae60", "#8e44ad", "#2c3e50"],
            "冷色 (Cool)": ["#2980b9", "#3498db", "#1abc9c", "#16a085", "#2c3e50"],
            "暖色 (Warm)": ["#c0392b", "#e74c3c", "#d35400", "#e67e22", "#f39c12"],
            "莫兰迪 (Morandi)": ["#7B8D8E", "#D0C9C0", "#A89B9D", "#C8B4BA", "#F0E4D4"],
            "复古 (Retro)": ["#A94442", "#8A6D3B", "#3C763D", "#31708F", "#8a8a8a"],
            "清新 (Fresh)": ["#a8e6cf", "#dcedc1", "#ffd3b6", "#ffaaa5", "#ff8b94"],
            "暗黑 (Dark)": ["#4b5563", "#6b7280", "#9ca3af", "#d1d5db", "#f3f4f6"],
            "马卡龙 (Macaron)": ["#ff9999", "#99ff99", "#9999ff", "#ffff99", "#ff99ff"],
            "彩虹 (Rainbow)": ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0000FF", "#4B0082", "#9400D3"],
            "商务 (Business)": ["#2c3e50", "#34495e", "#7f8c8d", "#bdc3c7", "#95a5a6"],
            "高雅 (Elegant)": ["#d4af37", "#2c3e50", "#e74c3c", "#ecf0f1", "#95a5a6"]
        }
        
        selected_palette = self.mm_palette_combo.currentText()
        colors = palette_map.get(selected_palette)
        
        options = {
            "initialExpandLevel": self.mm_expand_spin.value(),
            "colorFreezeLevel": self.mm_freeze_spin.value(),
            "maxWidth": self.mm_max_width_spin.value(),
        }
        
        if colors:
            options["color"] = colors
            
        # 构建YAML Frontmatter
        frontmatter = "---\nmarkmap:\n"
        for k, v in options.items():
            if v is not None:
                if isinstance(v, list):
                    frontmatter += f"  {k}: {json.dumps(v)}\n"
                else:
                    frontmatter += f"  {k}: {v}\n"
        frontmatter += "---\n\n"
        
        # 2. 准备CSS
        theme = self.mm_theme_combo.currentText()
        font = self.mm_font_combo.currentText()
        
        bg_color = self.mm_bg_color
        text_color = self.mm_text_color
            
        css = f"""
        body, html {{ background-color: {bg_color} !important; margin: 0; padding: 0; height: 100%; width: 100%; }}
        .markmap {{ width: 100%; height: 100vh; font-family: '{font}', sans-serif !important; color: {text_color} !important; }}
        svg {{ background-color: {bg_color} !important; }}
        text {{ fill: {text_color} !important; }}
        /* 让节点与连线可点击 */
        svg text, svg g, svg path {{ pointer-events: auto !important; cursor: pointer; }}
        """
        
        # 3. 组合HTML
        # 清除已有的frontmatter (更健壮的正则)
        import re
        # 匹配 --- markmap: ... --- (允许空白和换行变化)
        content_body = re.sub(r'^---\s*\nmarkmap:.*?\n---\s*\n*', '', original_content, flags=re.DOTALL)
        
        print(f"[GUI] 原始内容长度: {len(original_content)}")
        print(f"[GUI] 去除Frontmatter后长度: {len(content_body)}")
        if len(content_body) < 100:
            print(f"[GUI] 内容预览: {content_body!r}")

        if not content_body.strip():
            print("[GUI] 内容为空，使用默认模板")
            content_body = f"# {topic}\n\n## 概述\n- 要点1\n- 要点2\n- 要点3\n"
        
        # 处理图标主题
        icon_theme = self.mm_icon_combo.currentText()
        if icon_theme == "自动匹配 (Auto)":
            # 关键词匹配图标
            keyword_icons = {
                "目标": "🎯", "计划": "📅", "注意": "⚠️", "重要": "⭐", "核心": "⚛️",
                "问题": "❓", "回答": "✅", "解决": "🔧", "想法": "💡", "创新": "✨",
                "总结": "📝", "结论": "🏁", "背景": "🖼️", "历史": "📜", "原因": "🔍", 
                "影响": "🌊", "结果": "🍎", "建议": "💬", "行动": "🏃", "步骤": "👣",
                "优点": "👍", "优势": "💪", "缺点": "👎", "挑战": "🧗", "风险": "💣", 
                "机会": "🚀", "趋势": "📈", "技术": "💻", "数据": "📊", "分析": "🧠",
                "用户": "👥", "客户": "🤝", "市场": "🌍", "竞品": "🆚", "产品": "📦",
                "时间": "⏰", "金钱": "💰", "成本": "📉", "收益": "💹", "资源": "🧱"
            }
            
            new_lines = []
            lines = content_body.split('\n')
            for line in lines:
                match = re.match(r'^(#+)\s+(.*)', line)
                if match:
                    level_hashes = match.group(1)
                    text = match.group(2)
                    # 查找匹配的图标
                    icon = ""
                    for key, val in keyword_icons.items():
                        if key in text:
                            icon = val
                            break
                    # 如果没有匹配到，随机分配一个通用图标给高层级节点
                    if not icon and len(level_hashes) <= 2:
                        icon = "📌"
                    
                    if icon:
                        new_lines.append(f"{level_hashes} {icon} {text}")
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            content_body = "\n".join(new_lines)
            
        elif icon_theme != "无 (None)":
            # 定义图标集
            icon_sets = {
                "商务 (Business)": ["🎯", "📊", "📌", "📍", "📎", "📁"],
                "创意 (Creative)": ["✨", "💡", "🎨", "🖌️", "🎭", "🎪"],
                "简约 (Minimal)": ["🔹", "🔸", "▪️", "▫️", "🔺", "🔻"],
                "自然 (Nature)": ["🌱", "🌿", "🍀", "🌻", "🍂", "🌲"],
                "科技 (Tech)": ["💻", "🤖", "🚀", "🛰️", "🔌", "🔋"],
                "教育 (Education)": ["📚", "🎓", "✏️", "📝", "🏫", "🎒"],
                "生活 (Life)": ["🏠", "☕", "🎵", "🎮", "🍔", "🚗"]
            }
            # 提取括号前的中文名称作为 key 的一部分，或者直接匹配
            # 下拉框是 "自然 (Nature)"，字典key也是 "自然 (Nature)"，所以直接 get 即可
            icons = icon_sets.get(icon_theme, [])
            
            # 逐行处理Markdown，为标题和列表项添加图标
            new_lines = []
            lines = content_body.split('\n')
            for line in lines:
                # 匹配标题行 (e.g., "## Title") 或 列表项 (e.g. "  - Item")
                # Group 1: Indent
                # Group 2: Marker
                # Group 3: Text
                match = re.match(r'^(\s*)([#\-*+]+)\s+(.*)', line)
                if match and icons:
                    indent = match.group(1)
                    marker = match.group(2)
                    text = match.group(3)
                    
                    # 确定层级
                    if '#' in marker:
                        level = len(marker)
                    else:
                        # 列表项层级估算
                        level = (len(indent) // 2) + 2
                        
                    # 根据层级选择图标 (循环使用)
                    icon = icons[(level - 1) % len(icons)]
                    new_lines.append(f"{indent}{marker} {icon} {text}")
                else:
                    new_lines.append(line)
            content_body = "\n".join(new_lines)

        final_markdown = frontmatter + content_body
        
        # 3. 构造 HTML (强制使用离线 SVG 方案，不再使用模板/CDN)
        # 解析Markdown为树结构
        tree_data = self.parse_markdown_to_dict(content_body)
        
        # 获取样式参数
        line_style = self.mm_line_style_combo.currentText()
        max_width = self.mm_max_width_spin.value()
        structure = self.mm_structure_combo.currentText()
        line_width = self.mm_line_width_spin.value()
        initial_depth = self.mm_expand_spin.value()
        font_size = self.mm_font_size_spin.value()
        color_freeze_level = self.mm_freeze_spin.value()
        text_outline_color = getattr(self, "mm_text_outline_color", "transparent")
        
        # 生成离线HTML
        print(f"[GUI] Calling _build_offline_mindmap_html with data size: {len(str(tree_data))}")
        html_content = self._build_offline_mindmap_html(
            tree_data, css, line_style, colors, font, bg_color, text_color, max_width, structure,
            line_width=line_width, initial_depth=initial_depth, font_size=font_size,
            color_freeze_level=color_freeze_level, text_outline_color=text_outline_color
        )
        print(f"[GUI] Generated HTML content length: {len(html_content)}")
        
        try:
            # 保存到文件
            mindmap_file = self.current_result.get("mindmap_file", "")
            save_path = RESOURCE_DIR / mindmap_file
            save_path.write_text(html_content, encoding="utf-8")
            
            # 刷新显示
            self.display_results(self.current_result)
            
            if not silent:
                QMessageBox.information(self, "成功", "外观设置已应用")
            
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "错误", f"应用设置失败: {e}")
            else:
                print(f"[GUI] 应用设置失败: {e}")

    def export_mindmap(self):
        """导出思维导图"""
        if not self.current_result:
            return
            
        mindmap_file = self.current_result.get("mindmap_file", "")
        if not mindmap_file:
            return

        source_path = RESOURCE_DIR / mindmap_file
        if not source_path.exists():
            QMessageBox.warning(self, "错误", "思维导图文件不存在")
            return
            
        from PyQt6.QtWidgets import QFileDialog
        topic = self.current_result.get("topic", "mindmap")
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出思维导图",
            f"{topic}.html",
            "HTML文件 (*.html)"
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(source_path, save_path)
                QMessageBox.information(self, "成功", f"思维导图已导出到: {save_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def toggle_mindmap_settings(self):
        """切换思维导图设置面板显示"""
        if self.mindmap_settings_container.isVisible():
            self.mindmap_settings_container.hide()
            self.edit_mindmap_btn.setText("✳️ 外观设置")
        else:
            self.mindmap_settings_container.show()
            self.edit_mindmap_btn.setText("收起设置")


    def parse_markdown_to_dict(self, markdown_text):
        """解析Markdown文本为树形字典结构 (支持缩进和标题混合)"""
        if not markdown_text or not isinstance(markdown_text, str):
            print(f"[GUI] Markdown解析失败: 输入为空或非字符串 (类型: {type(markdown_text)})")
            return {"name": "解析失败: 内容为空", "children": []}
            
        lines = [line for line in markdown_text.split('\n') if line.strip()]
        
        # Fallback: 如果没有行，或者只有一行且很长，尝试按句子分割
        if len(lines) == 0:
             print(f"[GUI] Markdown解析警告: 有效行数为0 (原始长度: {len(markdown_text)})")
             return {"name": "解析失败: 无有效内容", "children": []}
             
        if len(lines) == 1 and len(lines[0]) > 50:
            # 尝试按标点分割
            import re
            parts = re.split(r'[。！？.!?]', lines[0])
            lines = [p.strip() for p in parts if p.strip()]
            if not lines:
                lines = [markdown_text]

        root = {"name": "Root", "children": []}
        
        # 栈结构: [(level, node)]
        # 虚拟根节点 level = 0
        stack = [(0, root)]
        
        for line in lines:
            # 计算缩进 (空格数)
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()
            
            if not stripped: continue
            # 忽略 Frontmatter 分隔符和代码块
            if stripped.startswith('---') or stripped.startswith('```'): continue
            # 忽略 Frontmatter 内容 (简单的 key: value)
            if ':' in stripped and not stripped.startswith(('- ', '* ', '#')):
                if len(stack) == 1:
                    continue
            
            level = 0
            name = ""
            is_header = False
            edge_label = ""
            
            # 1. 标题 (#)
            if stripped.startswith('#'):
                level = 0
                while level < len(stripped) and stripped[level] == '#':
                    level += 1
                name = stripped[level:].strip()
                is_header = True
            
            # 2. 列表项 (-, *, +)
            elif stripped.startswith(('-', '*', '+')):
                name = stripped.lstrip('-*+ ').strip()
                
                # 检查连接线标签
                import re
                edge_match = re.match(r'^<([^>]+)>\s*(.*)', name)
                if edge_match:
                    edge_label = edge_match.group(1)
                    name = edge_match.group(2)
                
                list_indent_level = indent // 2
                
                last_header_level = 0
                for lvl, node in reversed(stack):
                    if node.get('type') == 'header':
                        last_header_level = lvl
                        break
                
                level = last_header_level + 1 + list_indent_level
                
            else:
                # 3. 普通文本
                name = stripped
                import re
                edge_match = re.match(r'^<([^>]+)>\s*(.*)', name)
                if edge_match:
                    edge_label = edge_match.group(1)
                    name = edge_match.group(2)
                
                level = (indent // 2) + 1
                
                last_header_level = 0
                for lvl, node in reversed(stack):
                    if node.get('type') == 'header':
                        last_header_level = lvl
                        break
                
                if last_header_level > 0:
                    level += last_header_level
                
                if stack and level > stack[-1][0] + 1:
                    level = stack[-1][0] + 1
            
            node = {"name": name, "children": []}
            if edge_label:
                node["edge_label"] = edge_label
                
            if is_header:
                node['type'] = 'header'
            else:
                node['type'] = 'list'
            
            while stack and stack[-1][0] >= level:
                stack.pop()
            
            if stack:
                stack[-1][1]["children"].append(node)
                stack.append((level, node))
            else:
                root["children"].append(node)
                stack = [(0, root), (level, node)]
                
        # Post-processing / Fallback logic
        # 如果解析结果为空，尝试Fallback策略(将所有非空行视为节点)
        if not root["children"]:
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('---') and not stripped.startswith('```'):
                    root["children"].append({"name": stripped, "children": []})

        if len(root["children"]) == 0:
            return {"name": "No Content", "children": []}
            
        # 清理结果
        # 如果 Root 只有一个子节点，且该子节点是 H1 (通常情况)，则返回该子节点作为根
        if len(root["children"]) == 1:
            return root["children"][0]
            
        # 如果有多个顶级节点，检查是否第一个节点看起来像标题
        first_child = root["children"][0]
        if first_child.get('type') == 'header' or (not first_child['children'] and len(first_child['name']) < 30):
            new_root = first_child
            for sibling in root["children"][1:]:
                new_root["children"].append(sibling)
            return new_root
            
        return root

    def _apply_markmap_settings(self, topic, original_content):
        # 此方法已废弃，直接重定向到新的 apply_mindmap_settings 实现
        # 但由于逻辑结构问题，我们直接在这里调用正确的离线渲染逻辑
        # 或者更彻底地，直接删除这个方法和旧的 apply_mindmap_settings
        pass


    def _build_offline_mindmap_html(self, tree_data, css, line_style, colors, font, bg_color, text_color, max_width, structure="经典思维导图 (默认)", line_width=2, initial_depth=2, font_size=16, color_freeze_level=0, text_outline_color="transparent"):
        import json
        import copy
        
        # ECharts CDN
        echarts_script = '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>'
        
        # Determine layout configuration
        layout_config = {
            "经典思维导图 (默认)": {"type": "tree", "layout": "orthogonal", "orient": "LR", "split": True},
            "双向思维导图 (左右扩散)": {"type": "tree", "layout": "orthogonal", "orient": "LR", "split": True},
            "逻辑结构图 (向右)": {"type": "tree", "layout": "orthogonal", "orient": "LR", "split": False},
            "逻辑结构图 (向左)": {"type": "tree", "layout": "orthogonal", "orient": "RL", "split": False},
            "圆形辐射图 (Radial)": {"type": "tree", "layout": "radial", "orient": "", "split": False},
            "扇形图 (Sunburst)": {"type": "sunburst", "split": False},
            "韦恩图 (Venn)": {"type": "venn", "split": False},
            "流程图 (Flowchart)": {"type": "graph", "layout": "force", "edgeSymbol": ["circle", "arrow"], "split": False},
            "泳道图 (Swimlane)": {"type": "swimlane", "split": False},
            "甘特图 (Gantt)": {"type": "gantt", "split": False},
            "拓扑图 (Topology)": {"type": "graph", "layout": "circular", "split": False},
            "玫瑰图 (Rose)": {"type": "pie", "roseType": "area", "split": False},
            "人物关系图 (Relationship)": {"type": "relationship", "split": False},
        }
        
        config = layout_config.get(structure, layout_config["经典思维导图 (默认)"])
        
        # Process Line Style
        curveness = 0.5
        edge_shape = "curve"
        line_color_source = False
        is_tapered = False
        apply_line_color = False # Default to Grey lines for "Default", "Straight", "Polyline"

        if line_style:
            if "Straight" in line_style or "直线" in line_style:
                curveness = 0
            elif "Polyline" in line_style or "折线" in line_style:
                edge_shape = "polyline"
                curveness = 0
            elif "Gradient" in line_style or "渐变" in line_style:
                line_color_source = True
                apply_line_color = True
            elif "Colorful" in line_style or "多彩" in line_style:
                line_color_source = False
                apply_line_color = True
            elif "Tapered" in line_style or "渐细" in line_style:
                # Use source color and vary width
                line_color_source = True
                is_tapered = True
                apply_line_color = True
            
        # Helper for coloring
        
        # Ensure colors is valid
        if not colors or not isinstance(colors, list):
            # Fallback to default palette
            colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

        # Boost start_width for Tapered mode to make it more visible
        if is_tapered:
            start_width = max(start_width, 6) # Increased from 4 to 6 for visibility

        def colorize_tree_by_branch(node, colors, depth=0, branch_color=None, freeze_level=0, use_source_line=False, is_tapered=False, start_width=2, parent_color=None, apply_line_color=False):
            if not node: return
            
            current_color = branch_color
            if depth == 0 and colors:
                current_color = colors[0] # Root color
            
            if current_color:
                node.setdefault("itemStyle", {})
                node["itemStyle"]["color"] = current_color
                node["itemStyle"]["borderColor"] = current_color
                
                # Handle Line Style
                node.setdefault("lineStyle", {})
                
                # 1. Tapered Width (Make it more visible)
                if is_tapered:
                    # Decrease width significantly per level
                    # e.g. 6 -> 4.5 -> 3 -> 1.5
                    w = max(1.0, start_width - (depth * 1.5))
                    node["lineStyle"]["width"] = w
                
                # 2. Line Color
                if apply_line_color:
                    # If use_source_line is True, use parent's color (source-based coloring / Gradient effect)
                    # Otherwise use current node's color (target-based coloring / Colorful effect)
                    line_c = current_color
                    if use_source_line and parent_color:
                        line_c = parent_color
                    
                    # For Root, no line leading to it, but set anyway
                    if line_c:
                        node["lineStyle"]["color"] = line_c
                        # Force opacity to 1 to avoid grey lines
                        node["lineStyle"]["opacity"] = 1.0
                else:
                    # Reset/Ensure grey if not applying color (for switching back to Default)
                    node["lineStyle"]["color"] = "#ccc"

            if "children" in node:
                for i, child in enumerate(node["children"]):
                    next_color = current_color
                    
                    # Determine if we should change color
                    should_change = False
                    if freeze_level > 0:
                        if depth < freeze_level:
                            should_change = True
                    else:
                        if depth == 0:
                            should_change = True
                            
                    if should_change and colors:
                        color_idx = (i + depth) % len(colors)
                        next_color = colors[color_idx]
                    
                    colorize_tree_by_branch(child, colors, depth + 1, next_color, freeze_level, use_source_line, is_tapered, start_width, current_color, apply_line_color)
        
        # Helper for calculating values (for Treemap/Sunburst)
        def add_values_to_tree(node):
            if not node: return 0
            
            # If leaf node, value is 1 (or length of name)
            if not node.get("children"):
                node["value"] = 1
                return 1
            
            total = 0
            for child in node["children"]:
                total += add_values_to_tree(child)
            
            node["value"] = total
            return total

        # Helper for text wrapping to prevent overlap
        def process_node_labels(node, max_chars=20):
            if not node: return
            
            # Store full name for tooltip and wrap display name
            if "name" in node:
                # Save original full name if not already saved
                if "full_name" not in node:
                    node["full_name"] = node["name"]
                
                text = node["name"]
                
                # Remove English translations in parentheses (e.g. "Name (English Name)")
                # Only if text contains Chinese to avoid deleting pure English notes
                if any('\u4e00' <= char <= '\u9fa5' for char in text):
                    text = re.sub(r'\s*\([a-zA-Z\s]+\)', '', text).strip()
                
                # Wrap the text
                node["name"] = '\n'.join([text[i:i+max_chars] for i in range(0, len(text), max_chars)])
            
            if "children" in node:
                for child in node["children"]:
                    process_node_labels(child, max_chars)

        # Helper to convert tree to graph nodes/links
        def tree_to_graph(node, nodes=None, links=None, category=0, parent_id=None):
            if nodes is None: nodes = []
            if links is None: links = []
            
            node_id = str(len(nodes))
            val = node.get("value", 1)
            
            # Simple category logic: depth based
            cat_idx = category % 10 
            
            n = {
                "id": node_id,
                "name": node.get("name", ""),
                "value": val,
                "symbolSize": min(60, max(10, val * 3)) if "value" in node else 20,
                "category": cat_idx,
                "draggable": True,
                "label": {"show": True, "position": "right"}
            }
            if node.get("itemStyle"):
                n["itemStyle"] = node["itemStyle"]
            
            nodes.append(n)
            
            if parent_id is not None:
                links.append({
                    "source": parent_id,
                    "target": node_id
                })
            
            if "children" in node:
                for child in node["children"]:
                    tree_to_graph(child, nodes, links, category + 1, node_id)
            return nodes, links

        # Series generation
        series_json = []
        
        # Calculate values for all types (harmless for tree, needed for treemap/sunburst)
        add_values_to_tree(tree_data)

        # Apply coloring if available (generic coloring)
        if colors:
             colorize_tree_by_branch(tree_data, colors, freeze_level=color_freeze_level, use_source_line=line_color_source, is_tapered=is_tapered, start_width=line_width, apply_line_color=apply_line_color)

        if config["type"] == "tree":
            # Apply text wrapping
            # Estimate max chars based on font size and max_width (px)
            # Assume 1em ~ font_size px. 
            max_chars = max(5, int(max_width / font_size))
            process_node_labels(tree_data, max_chars=max_chars)

            # Root Node Styling (Highlight & Block Background)
            # Re-wrap root text to max 5 chars per line
            root_full_name = tree_data.get("full_name", tree_data.get("name", ""))
            tree_data["name"] = '\n'.join([root_full_name[i:i+5] for i in range(0, len(root_full_name), 5)])
            
            root_bg_color = tree_data.get("itemStyle", {}).get("color", colors[0] if colors else "#4F46E5")
            
            tree_data["symbolSize"] = 1 # Hide actual dot, use label as block
            tree_data["label"] = {
                "show": True,
                "rotate": 0, # Force horizontal for root
                "fontSize": font_size + 6,
                "fontWeight": "bold",
                "color": "#fff",
                "backgroundColor": root_bg_color,
                "padding": [12, 16],
                "borderRadius": 6,
                "shadowBlur": 10,
                "shadowColor": "rgba(0,0,0,0.2)",
                "position": "inside" # Center on the node position
            }
                
            base_series = {
                "type": "tree",
                "symbolSize": 9,
                "edgeShape": edge_shape,
                "roam": True, # Enable Zoom/Drag
                "lineStyle": {
                    "color": "#ccc", # Default fallback, but overridden by node style
                    "curveness": curveness, 
                    "width": line_width
                },
                "label": {
                    "position": "left", 
                    "verticalAlign": "middle", 
                    "align": "right", 
                    "fontSize": font_size, 
                    "color": text_color,
                    "fontFamily": font
                },
                "leaves": {
                    "label": {
                        "position": "right", 
                        "verticalAlign": "middle", 
                        "align": "left"
                    }
                },
                "emphasis": {"focus": "descendant"},
                "expandAndCollapse": True,
                "animationDuration": 550,
                "animationDurationUpdate": 750,
                "initialTreeDepth": initial_depth, 
            }
            
            # Apply Text Outline if set
            if text_outline_color and text_outline_color != "transparent":
                base_series["label"]["textBorderColor"] = text_outline_color
                base_series["label"]["textBorderWidth"] = 2
                base_series["leaves"]["label"]["textBorderColor"] = text_outline_color
                base_series["leaves"]["label"]["textBorderWidth"] = 2
            
            if not colors:
                 base_series["itemStyle"] = {"color": "#4F46E5", "borderColor": "#4F46E5"}

            if config["split"] and tree_data.get("children"):
                children = tree_data["children"]
                mid = (len(children) + 1) // 2
                
                # Right
                data_right = copy.deepcopy(tree_data)
                data_right["children"] = children[:mid]
                
                # Left
                data_left = copy.deepcopy(tree_data)
                data_left["children"] = children[mid:]
                # Hide root of left tree to avoid visual duplication/clutter
                data_left["label"] = {"show": False}
                data_left["symbolSize"] = 0
                
                # Series Right
                s1 = copy.deepcopy(base_series)
                s1["data"] = [data_right]
                s1["left"] = "50%"
                s1["right"] = "20%"
                s1["orient"] = "LR"
                s1["label"]["position"] = "left"
                s1["label"]["align"] = "right"
                s1["leaves"]["label"]["position"] = "right"
                s1["leaves"]["label"]["align"] = "left"
                series_json.append(s1)
                
                # Series Left
                s2 = copy.deepcopy(base_series)
                s2["data"] = [data_left]
                s2["left"] = "20%"
                s2["right"] = "50%"
                s2["orient"] = "RL"
                s2["label"]["position"] = "right"
                s2["label"]["align"] = "left"
                s2["leaves"]["label"]["position"] = "left"
                s2["leaves"]["label"]["align"] = "right"
                series_json.append(s2)
                
            else:
                s = copy.deepcopy(base_series)
                s["data"] = [tree_data]
                s["layout"] = config["layout"]
                if config.get("orient"):
                    s["orient"] = config["orient"]
                
                # Adjust Layout
                if config["layout"] == "radial":
                    s["top"] = "15%"; s["bottom"] = "15%"; s["left"] = "15%"; s["right"] = "15%"
                    # Optimize radial label direction (heuristic to avoid overlap)
                    s["label"]["position"] = "top" 
                    s["label"]["align"] = "center"
                    # Force horizontal labels for Root and others if requested
                    s["label"]["rotate"] = 0 
                    
                    s["leaves"]["label"]["position"] = "top"
                    s["leaves"]["label"]["align"] = "center"
                    s["leaves"]["label"]["rotate"] = 0
                    
                elif s.get("orient") == "TB":
                    s["top"] = "10%"; s["bottom"] = "10%"; s["left"] = "5%"; s["right"] = "5%"
                    s["label"]["rotate"] = -90
                    s["label"]["position"] = "top"
                    s["label"]["align"] = "center"
                    s["leaves"]["label"]["rotate"] = -90
                    s["leaves"]["label"]["position"] = "bottom"
                    s["leaves"]["label"]["align"] = "center"
                elif s.get("orient") == "BT":
                    s["top"] = "10%"; s["bottom"] = "10%"; s["left"] = "5%"; s["right"] = "5%"
                    s["label"]["rotate"] = 90
                    s["label"]["position"] = "bottom"
                    s["leaves"]["label"]["rotate"] = 90
                    s["leaves"]["label"]["position"] = "top"
                elif s.get("orient") == "RL":
                     s["top"] = "5%"; s["bottom"] = "5%"; s["left"] = "15%"; s["right"] = "15%"
                     # Invert labels for RL
                     s["label"]["position"] = "right"
                     s["label"]["align"] = "left"
                     s["leaves"]["label"]["position"] = "left"
                     s["leaves"]["label"]["align"] = "right"
                else: # LR
                    s["top"] = "5%"; s["bottom"] = "5%"; s["left"] = "15%"; s["right"] = "15%"
                
                series_json.append(s)

        elif config["type"] == "sunburst":
             # Configure Root Node for Center Display
             # 1. Ensure label is horizontal and visible
             tree_data["label"] = {
                 "rotate": 0,
                 "fontWeight": "bold",
                 "fontSize": 14,
                 "color": "#fff"
             }
             # 2. Wrap root text for better fit in center
             root_name = tree_data.get("name", "")
             if len(root_name) > 4:
                 tree_data["name"] = '\n'.join([root_name[i:i+4] for i in range(0, len(root_name), 4)])

             s = {
                 "type": "sunburst",
                 "data": [tree_data],
                 "radius": [0, '95%'],
                 "label": {
                     "rotate": "radial",
                     "align": "center"
                 },
                 "emphasis": {
                     "focus": "descendant"
                 }
             }
             if colors:
                 s["color"] = colors
             series_json.append(s)

        elif config["type"] == "pie":
             # Rose Chart (Multi-level via Nested Pies)
             level1_data = tree_data.get("children", [])
             level2_data = []
             
             for node in level1_data:
                 # Flatten children for the second ring
                 children = node.get("children", [])
                 if children:
                     level2_data.extend(children)
                 else:
                     # If no children, repeat the node itself to maintain angular alignment in the outer ring
                     # Create a copy to avoid modifying the original node structure if reused
                     node_copy = node.copy()
                     if "children" in node_copy: del node_copy["children"]
                     level2_data.append(node_copy)
             
             # Inner Series: Level 1 (Standard Pie for Category)
             s1 = {
                 "type": "pie",
                 "radius": [0, '30%'],
                 "center": ['50%', '50%'],
                 "data": level1_data,
                 "label": {
                     "position": "inner", 
                     "rotate": "tangential",
                     "fontSize": 10,
                     "formatter": "{b}"
                 },
                 "itemStyle": {
                     "borderColor": "#fff",
                     "borderWidth": 1
                 }
             }
             
             # Outer Series: Level 2 (Rose Chart for Details)
             s2 = {
                 "type": "pie",
                 "radius": ['35%', '80%'],
                 "center": ['50%', '50%'],
                 "roseType": config.get("roseType", "area"),
                 "data": level2_data,
                 "label": {
                     "show": True,
                     "formatter": "{b}" 
                 },
                 "itemStyle": {
                     "borderRadius": 5,
                     "borderColor": "#fff",
                     "borderWidth": 1
                 }
             }
             
             if colors:
                 s1["color"] = colors
                 s2["color"] = colors
             
             series_json.append(s1)
             series_json.append(s2)

        elif config["type"] == "venn":
             nodes, links = tree_to_graph(tree_data)
             
             # User Request: Center the Theme Node (Root) and circle others around it
             if nodes:
                 # 1. Setup Root Node (Center)
                 root_node = nodes[0]
                 root_node["x"] = 0
                 root_node["y"] = 0
                 root_node["fixed"] = True
                 root_node["symbolSize"] = 100
                 root_node["itemStyle"] = {
                     "color": colors[0] if colors else "#d63031", 
                     "opacity": 1,
                     "shadowBlur": 20,
                     "shadowColor": "rgba(0,0,0,0.5)"
                 }
                 root_node["label"] = {
                     "show": True, 
                     "position": "inside", 
                     "formatter": "{b}",
                     "fontWeight": "bold",
                     "fontSize": 14,
                     "width": 80,
                     "overflow": "break"
                 }
                 
                 # 2. Setup Children (Circle Layout)
                 others = nodes[1:]
                 count = len(others)
                 if count > 0:
                     radius = 300
                     for i, n in enumerate(others):
                         angle = 2 * math.pi * i / count
                         n["x"] = radius * math.cos(angle)
                         n["y"] = radius * math.sin(angle)
                         n["symbolSize"] = 70
                         n["itemStyle"] = {
                             "opacity": 0.7,
                             "color": colors[(i + 1) % len(colors)] if colors else None
                         }
                         n["label"] = {
                             "show": True, 
                             "position": "inside", 
                             "formatter": "{b}",
                             "width": 60,
                             "overflow": "break",
                             "fontSize": 10
                         }
             
             s = {
                 "type": "graph",
                 "layout": "none", # Manual layout to enforce center position
                 "data": nodes,
                 "links": links,
                 "roam": True,
                 "label": {"show": True, "position": "inside", "formatter": "{b}"},
                 "lineStyle": {"curveness": 0.3, "opacity": 0.3}
             }
             if colors: s["color"] = colors
             series_json.append(s)

        elif config["type"] == "swimlane":
             nodes = []
             links = []
             root_children = tree_data.get("children", [])
             lane_height = 120
             start_y = 0
             
             # Root label
             nodes.append({
                 "id": "root", 
                 "name": tree_data.get("name", ""), 
                 "x": 50, 
                 "y": (len(root_children) * lane_height) / 2 if root_children else 0,
                 "symbolSize": 1,
                 "label": {"show": True, "fontSize": 16, "fontWeight": "bold", "position": "top"}
             })

             for i, lane_node in enumerate(root_children):
                 lane_y = start_y + i * lane_height
                 lane_id = f"lane_{i}"
                 color = colors[i % len(colors)] if colors else "#5470c6"
                 
                 # Lane Header
                 nodes.append({
                     "id": lane_id,
                     "name": lane_node.get("name", ""),
                     "x": 150,
                     "y": lane_y,
                     "symbol": "rect",
                     "symbolSize": [120, 40],
                     "itemStyle": {"color": color},
                     "label": {"show": True, "color": "#fff"}
                 })
                 
                 # Lane Items (Level 2)
                 items = lane_node.get("children", [])
                 for j, item in enumerate(items):
                     item_x = 300 + j * 160
                     item_id = f"item_{i}_{j}"
                     nodes.append({
                         "id": item_id,
                         "name": item.get("name", ""),
                         "x": item_x,
                         "y": lane_y,
                         "symbol": "roundRect",
                         "symbolSize": [140, 30],
                         "itemStyle": {"color": "#fff", "borderColor": color, "borderWidth": 2},
                         "label": {"show": True, "color": "#333"}
                     })
                     links.append({"source": lane_id, "target": item_id})
                     
             s = {
                 "type": "graph",
                 "layout": "none",
                 "data": nodes,
                 "links": links,
                 "roam": True,
                 "lineStyle": {"curveness": 0}
             }
             series_json.append(s)

        elif config["type"] == "gantt":
             nodes = []
             links = []
             y_cursor = 0
             
             # Flatten tree to list for Gantt steps
             # We use a simple iterative approach or recursive with nonlocal
             stack = [(tree_data, None, 0, 0)] # node, parent_id, depth, x_start
             
             # We need to process in order to assign Y correctly
             # So we use a recursive helper instead of manual stack loop to maintain order easily
             def process_gantt(node, parent_id=None, depth=0, x_start=0):
                 nonlocal y_cursor
                 
                 # Safety check: prevent infinite recursion or excessive nodes causing crash
                 if len(nodes) > 2000:
                     return

                 node_id = f"n_{len(nodes)}"
                 
                 # Duration simulation
                 duration = max(80, len(node.get("name","")) * 12)
                 color = colors[depth % len(colors)] if colors else "#5470c6"
                 
                 n = {
                     "id": node_id,
                     "name": node.get("name", ""),
                     "x": x_start + duration/2,
                     "y": y_cursor,
                     "symbol": "rect",
                     "symbolSize": [duration, 24],
                     "itemStyle": {"color": color},
                     "label": {"show": True, "color": "#fff"}
                 }
                 nodes.append(n)
                 
                 if parent_id:
                     links.append({
                         "source": parent_id, 
                         "target": node_id,
                         "lineStyle": {"type": "dotted"}
                     })
                 
                 # Increased vertical spacing to reduce crowding (User feedback)
                 y_cursor += 60
                
                 if "children" in node:
                     for child in node["children"]:
                         process_gantt(child, node_id, depth+1, x_start + 20)

             process_gantt(tree_data)
             
             s = {
                 "type": "graph",
                 "layout": "none",
                 "data": nodes,
                 "links": links,
                 "roam": True,
                 "lineStyle": {"curveness": 0.5}
             }
             series_json.append(s)

        elif config["type"] == "relationship":
            # Relationship Diagram (Character Relationship)
            # Similar to Graph but with stronger emphasis on edge labels and central node
            nodes, links = tree_to_graph(tree_data)
            
            # Customize nodes
            for i, n in enumerate(nodes):
                if i == 0: # Root (Center Character)
                    n["symbolSize"] = 80
                    n["itemStyle"] = {"color": colors[0] if colors else "#d63031", "shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}
                    n["label"] = {"show": True, "fontSize": 18, "fontWeight": "bold", "position": "inside"}
                else:
                    n["symbolSize"] = 40
                    n["itemStyle"] = {"color": colors[i % len(colors)] if colors else "#0984e3"}
                    n["label"] = {"show": True, "position": "inside", "color": "#fff"}

            # Customize links
            for link in links:
                # Add arrow
                link["symbol"] = ["none", "arrow"]
                link["symbolSize"] = 10
                
                # Check for edge label in target node name (parsed earlier)
                # We need to find the target node to get the edge label if it was stored
                # But tree_to_graph doesn't carry edge_label to link directly easily unless we modify it
                # However, the parser stores edge_label in node dict. 
                # tree_to_graph logic:
                # if parent_id is not None: links.append({"source": parent_id, "target": node_id})
                # We can enhance tree_to_graph or just post-process here if we can map IDs back to nodes
                pass 
                
            # Re-build links with labels properly
            # Since tree_to_graph is simple, let's just redo links logic here specifically for this chart type
            # or rely on the fact that nodes are created in order.
            # Actually, let's use a modified traversal or just update links if we can access the node data.
            # The 'nodes' list has 'id' which corresponds to index. 
            # We can traverse the tree again to build specific links with labels
            
            r_links = []
            def build_relationship_links(node, parent_id=None):
                node_id = next(n["id"] for n in nodes if n["name"] == node.get("name")) # Simple name matching might be risky if duplicates
                # Better: tree_to_graph assigns IDs based on traversal order. 
                # Let's just trust tree_to_graph output and enhance it? 
                # No, tree_to_graph is stateless.
                # Let's re-traverse to match IDs correctly.
                pass

            # Simpler approach: Modify tree_to_graph to include edge_label in links if present?
            # Or just inline the logic here since it's specific.
            
            r_nodes = []
            r_links = []
            
            def process_rel_node(node, parent_id=None):
                node_id = str(len(r_nodes))
                
                # Extract label from name if format is "Label: Name" or similar?
                # The user input is likely Markdown list: "- <Label> Name" or just "- Name"
                # Our parser supports <Label> prefix.
                
                name = node.get("name", "")
                edge_label = node.get("edge_label", "")
                
                n = {
                    "id": node_id,
                    "name": name,
                    "symbolSize": 80 if parent_id is None else 45,
                    "draggable": True,
                    "label": {"show": True, "position": "inside" if parent_id is None else "bottom"},
                    "itemStyle": {"color": colors[len(r_nodes) % len(colors)] if colors else None}
                }
                
                # Special style for root
                if parent_id is None:
                     n["itemStyle"] = {"color": colors[0] if colors else "#d63031"}
                     n["label"] = {"show": True, "fontSize": 16, "fontWeight": "bold", "position": "inside"}
                
                r_nodes.append(n)
                
                if parent_id is not None:
                    link = {
                        "source": parent_id,
                        "target": node_id,
                        "symbol": ["none", "arrow"],
                        "symbolSize": 10,
                        "lineStyle": {"curveness": 0.2, "width": 2}
                    }
                    if edge_label:
                        link["label"] = {
                            "show": True,
                            "formatter": edge_label,
                            "fontSize": 12,
                            "color": "#333",
                            "backgroundColor": "#fff",
                            "padding": [2, 4],
                            "borderRadius": 4
                        }
                    r_links.append(link)
                
                if "children" in node:
                    for child in node["children"]:
                        process_rel_node(child, node_id)
            
            process_rel_node(tree_data)
            
            s = {
                "type": "graph",
                "layout": "force",
                "force": {
                    "repulsion": 500,
                    "edgeLength": 150,
                    "gravity": 0.1
                },
                "data": r_nodes,
                "links": r_links,
                "roam": True,
                "lineStyle": {"color": "source", "curveness": 0.2}
            }
            series_json.append(s)

        elif config["type"] == "graph":
             nodes, links = tree_to_graph(tree_data)
             
             # User Request: Center Root for Topology (Circular layout)
             # If layout is 'circular', ECharts puts everything on ring. We want Root in Center.
             layout_mode = config.get("layout", "force")
             
             if layout_mode == "circular" and nodes:
                 # 1. Setup Root Node (Center)
                 root_node = nodes[0]
                 root_node["x"] = 0
                 root_node["y"] = 0
                 root_node["fixed"] = True
                 root_node["symbolSize"] = 60
                 root_node["itemStyle"] = {
                     "color": colors[0] if colors else "#d63031",
                     "opacity": 1,
                     "shadowBlur": 10
                 }
                 root_node["label"] = {
                     "show": True,
                     "position": "inside",
                     "fontWeight": "bold",
                     "fontSize": 14,
                     "formatter": "{b}"
                 }
                 
                 # 2. Circle others
                 others = nodes[1:]
                 count = len(others)
                 if count > 0:
                     radius = 350
                     for i, n in enumerate(others):
                         angle = 2 * math.pi * i / count
                         n["x"] = radius * math.cos(angle)
                         n["y"] = radius * math.sin(angle)
                         # Rotate label to align with radial direction for better readability
                         # Angle in degrees for rotation: (angle * 180 / math.pi)
                         # But 'rotate' in label is usually absolute.
                         # Let's keep it simple first.
                         
                 # Override layout to 'none' to use manual x/y
                 layout_mode = "none"

             categories = [{"name": f"Level {i}"} for i in range(10)]
             
             s = {
                 "type": "graph",
                 "layout": layout_mode,
                 "data": nodes,
                 "links": links,
                 "categories": categories,
                 "roam": True,
                 "label": {
                     "show": True,
                     "position": "right",
                     "formatter": "{b}"
                 },
                 "lineStyle": {
                     "color": "source",
                     "curveness": 0.3
                 }
             }
             if config.get("edgeSymbol"):
                 s["edgeSymbol"] = config["edgeSymbol"]
                 s["edgeSymbolSize"] = [4, 10]
             
             if config.get("symbol"):
                 s["symbol"] = config["symbol"]

             if config["layout"] == "force":
                 s["force"] = {
                     "repulsion": 100,
                     "edgeLength": 50
                 }
             
             if colors:
                 s["color"] = colors
                 
             series_json.append(s)

        # Build Option Object
        option = {
            "backgroundColor": bg_color,
            "tooltip": { "trigger": 'item', "triggerOn": 'mousemove' },
            "toolbox": {
                "show": True,
                "feature": {
                    "saveAsImage": { "show": True, "title": '保存图片', "pixelRatio": 2 },
                    "restore": { "show": True, "title": '恢复' },
                }
            },
            "series": series_json
        }
        
        option_json = json.dumps(option, ensure_ascii=False)
        
        # Load Template
        template_path = RESOURCE_DIR / "templates" / "echarts_mindmap.html"
        html = ""
        
        if template_path.exists():
            try:
                template_content = template_path.read_text(encoding="utf-8")
                html = template_content.replace("{{TITLE}}", "Mindmap") \
                                     .replace("{{BG_COLOR}}", bg_color) \
                                     .replace("{{FONT}}", font) \
                                     .replace("{{OPTION_JSON}}", option_json)
            except Exception as e:
                print(f"[GUI] Error loading template: {e}")
        
        # Fallback if template fails or missing
        if not html:
            html = f"""<!DOCTYPE html>
<html style="height: 100%">
<head>
    <meta charset="utf-8">
    <title>Mindmap</title>
    {echarts_script}
</head>
<body style="height: 100%; margin: 0; background-color: {bg_color}; font-family: '{font}', sans-serif;">
    <div id="container" style="height: 100%"></div>
    <script type="text/javascript">
        var dom = document.getElementById('container');
        var myChart = echarts.init(dom);
        var app = {{}};
        
        var option = {option_json};
        
        // Inject tooltip formatter for full text display
        option.tooltip = option.tooltip || {{}};
        option.tooltip.formatter = function(params) {{
            var data = params.data || {{}};
            var content = data.full_name || params.name;
            if (params.value && !isNaN(params.value)) {{
                 content += ': ' + params.value;
            }}
            return content ? content.replace(/\\n/g, '<br/>') : '';
        }};
        
        // Add edgeLabel formatter
        if (option.series) {{
            option.series.forEach(function(s) {{
            if (s.type === 'tree') {{
                s.edgeLabel = {{
                    show: true,
                    formatter: function (params) {{
                        return params.data.edge_label || '';
                    }},
                    fontSize: 10,
                    color: '#666',
                    backgroundColor: 'white',
                    padding: [2, 4],
                    borderRadius: 4
                }};
            }}
        }});
        
        if (option && typeof option === 'object') {{
            myChart.setOption(option);
        }}
        
        window.addEventListener('resize', myChart.resize);
    </script>
</body>
</html>"""
        return html



    def _save_and_display_mindmap(self, html_content):
        """保存并显示思维导图HTML"""
        try:
            mindmap_file = self.current_result.get("mindmap_file", "")
            save_path = RESOURCE_DIR / mindmap_file
            save_path.write_text(html_content, encoding="utf-8")
            self.display_results(self.current_result)
            QMessageBox.information(self, "成功", "外观设置已应用")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")
            
    # 原方法改名或删除，这里选择直接替换整个方法
    def export_mindmap(self):
        """导出思维导图"""
        if not self.current_result:
            return
            
        mindmap_file = self.current_result.get("mindmap_file", "")
        if not mindmap_file:
            return

        source_path = RESOURCE_DIR / mindmap_file
        if not source_path.exists():
            QMessageBox.warning(self, "错误", "思维导图文件不存在")
            return
            
        from PyQt6.QtWidgets import QFileDialog
        topic = self.current_result.get("topic", "mindmap")
        
        # 使用生成的文件名作为默认导出文件名（包含语言后缀）
        default_name = Path(mindmap_file).name
        
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出思维导图",
            default_name,
            "HTML文件 (*.html)"
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(source_path, save_path)
                QMessageBox.information(self, "成功", f"思维导图已导出到: {save_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def export_mindmap_image(self):
        """导出思维导图为图片 (高清)"""
        if not self.current_result:
            return
            
        topic = self.current_result.get("topic", "mindmap")
        
        # 尝试从文件名获取带后缀的主题名
        default_name = f"{topic}.png"
        mindmap_file = self.current_result.get("mindmap_file", "")
        if mindmap_file:
             stem = Path(mindmap_file).stem
             default_name = f"{stem}.png"
             
        from PyQt6.QtWidgets import QFileDialog
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出图片",
            default_name,
            "PNG图片 (*.png)"
        )
        
        if save_path:
            # 构造JS代码获取ECharts的Base64图片数据
            # pixelRatio: 4 保证高清
            # backgroundColor: '#fff' 保证背景不透明
            js = """
            (function() {
                var dom = document.getElementById('container');
                if (!dom) return null;
                var chart = echarts.getInstanceByDom(dom);
                if (chart) {
                    return chart.getDataURL({
                        type: 'png',
                        pixelRatio: 4,
                        backgroundColor: '#fff',
                        excludeComponents: ['toolbox']
                    });
                }
                return null;
            })();
            """
            
            def callback(result):
                success = False
                if result and isinstance(result, str) and result.startswith('data:image'):
                    try:
                        import base64
                        # result format: "data:image/png;base64,....."
                        header, encoded = result.split(",", 1)
                        data = base64.b64decode(encoded)
                        with open(save_path, "wb") as f:
                            f.write(data)
                        success = True
                        QMessageBox.information(self, "成功", f"高清图片已导出到: {save_path}")
                    except Exception as e:
                        print(f"ECharts export failed: {e}")
                
                if not success:
                    # Fallback to grab()
                    try:
                        if hasattr(self, 'mindmap_view'):
                            pixmap = self.mindmap_view.grab()
                            pixmap.save(save_path)
                            QMessageBox.information(self, "成功", f"图片已保存到: {save_path} (截图模式)")
                    except Exception as e:
                        QMessageBox.critical(self, "错误", f"导出图片失败: {e}")

            if hasattr(self, 'mindmap_view'):
                self.mindmap_view.page().runJavaScript(js, callback)
            else:
                QMessageBox.warning(self, "错误", "视图未初始化")

    def edit_mindmap_content(self):
        """编辑思维导图内容"""
        if not self.current_result:
            return
            
        content = self.current_result.get("mindmap_content", "")
        # 解析为树结构，进入简易编辑器
        try:
            tree_dict = self.parse_markdown_to_dict(content)
        except Exception:
            tree_dict = {"name": self.current_result.get("topic", "主题"), "children": []}
        dialog = MindMapTreeEditorDialog(tree_dict, self)
        
        if dialog.exec():
            new_content = dialog.to_markdown()
            self.current_result["mindmap_content"] = new_content
            
            # 保存到文件 (覆盖原文件)
            mindmap_file = self.current_result.get("mindmap_file", "")
            # 注意: 这里我们只更新了内存中的 content，并未持久化到 markdown 文件
            # 实际上我们主要是为了重绘。如果需要持久化，可以 overwrite 原始文件
            # 但原始文件通常是 html? 不，原始文件是 .md 吗？
            # 检查 current_result 结构，mindmap_file 指向 .html
            # 我们没有 .md 文件的路径引用，但我们可以重新生成 HTML
            
            self.apply_mindmap_settings()
            QMessageBox.information(self, "成功", "内容已更新，正在重新渲染...")

    def open_mindmap_in_browser(self):
        """在浏览器中打开思维导图"""
        if not self.current_result:
            return
            
        mindmap_file = self.current_result.get("mindmap_file", "")
        if mindmap_file:
            path = RESOURCE_DIR / mindmap_file
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute())))
            else:
                QMessageBox.warning(self, "提示", f"文件不存在: {path}")

    def export_html(self):
        """导出HTML"""
        if not self.current_result:
            QMessageBox.warning(self, "提示", "请先生成动画内容")
            return
        
        topic = self.current_result.get("topic", "")
        
        # 优先使用result中的文件路径
        animation_file_rel = self.current_result.get("animation_file", "")
        if animation_file_rel:
            animation_file = RESOURCE_DIR / animation_file_rel
        else:
            animation_file = OFFLINE_DIR / "animations" / f"{topic}.html"
        
        if animation_file.exists():
            QMessageBox.information(
                self, "成功", 
                f"动画已保存到:\n{animation_file}"
            )
        else:
            QMessageBox.warning(self, "提示", "动画文件不存在")
    
    def export_video(self):
        """导出视频(异步执行)"""
        if not self.current_result:
            QMessageBox.warning(self, "提示", "请先生成可视化内容")
            return
        
        topic = self.current_result.get("topic", "")
        storyboard = self.current_result.get("storyboard", [])
        
        if not storyboard:
            QMessageBox.warning(self, "提示", "没有可导出的动画数据")
            return
        
        # 先检查依赖
        try:
            from core.video_renderer import PLAYWRIGHT_AVAILABLE
            if not PLAYWRIGHT_AVAILABLE:
                reply = QMessageBox.question(
                    self, "缺少依赖",
                    "视频导出需要安装 playwright 和浏览器驱动。\n\n安装命令: \n1. pip install playwright\n2. playwright install chromium\n\n是否在浏览器中打开安装说明？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                return
        except Exception as e:
            QMessageBox.warning(self, "错误", f"检查依赖失败: {e}")
            return
        
        # 选择保存路径
        from PyQt6.QtWidgets import QFileDialog
        import os
        
        # 尝试从文件名获取带后缀的主题名
        default_name = f"{topic}.mp4"
        animation_file_rel = self.current_result.get("animation_file", "")
        if animation_file_rel:
             stem = Path(animation_file_rel).stem
             default_name = f"{stem}.mp4"
             
        default_path = os.path.join(str(Path.home()), default_name)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存视频",
            default_path,
            "MP4视频 (*.mp4);;所有文件 (*.*)"
        )
        
        if not save_path:
            return  # 用户取消
        
        # 创建导出线程
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class ExportThread(QThread):
            finished = pyqtSignal(object)  # 成功时发送路径，失败时发送None
            error = pyqtSignal(str)  # 错误信息
            progress = pyqtSignal(int, str)  # 进度百分比和状态文本
            
            def __init__(self, media_composer, topic, storyboard, save_path, settings):
                super().__init__()
                self.media_composer = media_composer
                self.topic = topic
                self.storyboard = storyboard
                self.save_path = save_path
                self.settings = settings
            
            def run(self):
                try:
                    import time
                    self.progress.emit(5, "检查文件...")
                    time.sleep(0.3)
                    
                    self.progress.emit(15, "启动浏览器...")
                    time.sleep(0.3)
                    
                    self.progress.emit(25, "加载动画页面...")
                    time.sleep(0.3)
                    
                    self.progress.emit(35, "开始捕获帧...")
                    
                    # 转换设置为VideoSettings
                    video_settings = self.settings.to_video_settings()
                    
                    def progress_callback(percent, msg):
                        self.progress.emit(percent, msg)

                    result = self.media_composer.export_animation_video(
                        topic=self.topic,
                        storyboard=self.storyboard,
                        destination=Path(self.save_path),
                        settings=video_settings,
                        progress_callback=progress_callback
                    )
                    
                    self.progress.emit(90, "合成视频...")
                    time.sleep(0.5)
                    
                    self.progress.emit(100, "导出完成！")
                    self.finished.emit(result)
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    print(f"视频导出错误:\n{error_details}")
                    self.error.emit(str(e))
        
        # 创建并启动线程
        self.export_thread = ExportThread(
            self.media_composer,
            topic,
            storyboard,
            save_path,
            self.settings
        )
        
        # 创建进度对话框
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog("正在准备导出...", None, 0, 100, self)
        progress.setWindowTitle("导出视频")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)  # 禁用取消按钮，因为取消后台进程比较复杂
        
        def on_progress(value, text):
            progress.setValue(value)
            # 如果文本包含"进度:", 则直接显示该文本，否则添加后缀
            if "进度:" in text:
                 progress.setLabelText(text)
            else:
                 progress.setLabelText(f"{text}\n这可能需要几分钟时间...")
        
        def on_finished(result):
            progress.close()
            if result and result.exists():
                QMessageBox.information(
                    self, "成功",
                    f"视频已导出到:\n{result}"
                )
            else:
                QMessageBox.warning(
                    self, "失败",
                    "视频导出失败！\n\n可能原因: \n1. 动画HTML文件不存在\n2. 音频文件缺失\n3. Playwright浏览器未安装\n\n请查看控制台获取详细信息"
                )
        
        def on_error(error_msg):
            progress.close()
            QMessageBox.critical(
                self, "错误",
                f"视频导出出错: \n{error_msg}\n\n请查看控制台获取详细信息"
            )
        
        self.export_thread.progress.connect(on_progress)
        self.export_thread.finished.connect(on_finished)
        self.export_thread.error.connect(on_error)
        self.export_thread.start()
        
        progress.show()
    
    def show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            # 设置已保存，重新初始化后端
            self.init_backend()

    def show_help(self):
        """显示帮助对话框"""
        dialog = HelpDialog(self)
        dialog.exec()
    
    def toggle_history_list(self):
        """切换历史记录列表的显示/隐藏"""
        if self.history_list.isVisible():
            self.history_list.hide()
        else:
            self.refresh_history_list()
            self.history_list.show()
    
    def refresh_history_list(self):
        """刷新历史记录列表"""
        self.history_list.clear()
        
        items = []
        import time

        def get_display_info(stem):
            clean_topic = stem
            lang_text = ""
            if stem.endswith("_cn"):
                clean_topic = stem[:-3]
                lang_text = "[中文]"
            elif stem.endswith("_en"):
                clean_topic = stem[:-3]
                lang_text = "[English]"
            return clean_topic, lang_text
        
        # 扫描动画文件
        animations_dir = OFFLINE_DIR / "animations"
        if animations_dir.exists():
            for f in animations_dir.glob("*.html"):
                if not f.stem.endswith('_viewer'):
                    clean_topic, lang_text = get_display_info(f.stem)
                    items.append({
                        "type": "animation",
                        "path": f,
                        "topic": clean_topic,
                        "file_stem": f.stem,
                        "lang_text": lang_text,
                        "time": f.stat().st_mtime
                    })
        
        # 扫描思维导图文件
        mindmaps_dir = OFFLINE_DIR / "mindmaps"
        if mindmaps_dir.exists():
            for f in mindmaps_dir.glob("*.html"):
                clean_topic, lang_text = get_display_info(f.stem)
                items.append({
                    "type": "mindmap",
                    "path": f,
                    "topic": clean_topic,
                    "file_stem": f.stem,
                    "lang_text": lang_text,
                    "time": f.stat().st_mtime
                })

        # 扫描动态排序图文件
        bar_races_dir = OFFLINE_DIR / "bar_races"
        if bar_races_dir.exists():
            for f in bar_races_dir.glob("*.html"):
                clean_topic, lang_text = get_display_info(f.stem)
                items.append({
                    "type": "bar_race",
                    "path": f,
                    "topic": clean_topic,
                    "file_stem": f.stem,
                    "lang_text": lang_text,
                    "time": f.stat().st_mtime
                })

        # 扫描地理可视化文件
        geo_maps_dir = OFFLINE_DIR / "geo_maps"
        if geo_maps_dir.exists():
            for f in geo_maps_dir.glob("*.html"):
                clean_topic, lang_text = get_display_info(f.stem)
                items.append({
                    "type": "geo_map",
                    "path": f,
                    "topic": clean_topic,
                    "file_stem": f.stem,
                    "lang_text": lang_text,
                    "time": f.stat().st_mtime
                })
        
        # 按时间倒序排序
        items.sort(key=lambda x: x["time"], reverse=True)
        
        for item in items:
            mtime = item["time"]
            time_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            topic = item["topic"]
            lang = item["lang_text"]
            lang_prefix = f"{lang} " if lang else ""
            
            if item["type"] == "animation":
                display_text = f"{lang_prefix}{topic} - 动画 ({time_str})"
            elif item["type"] == "mindmap":
                display_text = f"{lang_prefix}{topic} - 思维导图 ({time_str})"
            elif item["type"] == "bar_race":
                display_text = f"{lang_prefix}{topic} - 动态排序图 ({time_str})"
            else:
                display_text = f"{lang_prefix}{topic} - 地理可视化 ({time_str})"
            
            from PyQt6.QtWidgets import QListWidgetItem
            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.ItemDataRole.UserRole, item)  # 存储完整item数据
            self.history_list.addItem(list_item)
        
        if self.history_list.count() == 0:
            from PyQt6.QtWidgets import QListWidgetItem
            item = QListWidgetItem("暂无历史记录")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.history_list.addItem(item)
    
    def load_history_item(self, list_item):
        """加载选中的历史记录"""
        if list_item is None:
            return
        item_data = list_item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return
            
        topic = item_data["topic"]
        item_type = item_data["type"]
        file_path = item_data["path"]
        file_name = file_path.name
        
        # 更新主题输入框
        self.topic_input.setText(topic)
        self.current_topic = topic
        
        if item_type == "animation":
            # 重建current_result
            storyboard = []
            try:
                import json
                animation_file = file_path
                if animation_file.exists():
                    with open(animation_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                        import re
                        match = re.search(r'const animationData = (\{.*?\});', html_content, re.DOTALL)
                        if match:
                            animation_data = json.loads(match.group(1))
                            storyboard = animation_data.get("storyboard", [])
            except Exception as e:
                print(f"解析历史记录失败: {e}")

            self.current_result = {
                "type": "animation",
                "topic": topic,
                "animation_file": f"offline/animations/{file_name}",
                "storyboard": storyboard,
                "is_online": False,
            }
            self.display_results(self.current_result)
            
        elif item_type == "mindmap":
            self.current_result = {
                "type": "mindmap",
                "topic": topic,
                "mindmap_file": f"offline/mindmaps/{file_name}",
                "is_online": False,
            }
            self.display_results(self.current_result)
        
        elif item_type == "bar_race":
            self.current_result = {
                "type": "bar_race",
                "topic": topic,
                "bar_race_file": f"offline/bar_races/{file_name}",
                "is_online": False,
            }
            self.display_results(self.current_result)

        elif item_type == "geo_map":
            try:
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    if "{{CONFIG_JSON}}" in html_content:
                        html_content = html_content.replace("{{CONFIG_JSON}}", "{}")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(html_content)
            except Exception as e:
                print(f"修复地理可视化HTML失败: {e}")
            self.current_result = {
                "type": "geo_map",
                "topic": topic,
                "geo_map_file": f"offline/geo_maps/{file_name}",
                "is_online": False,
            }
            self.display_results(self.current_result)
        
        # 隐藏历史记录列表
        self.history_list.hide()


def main():
    """主函数"""
    # 初始化日志重定向
    try:
        sys.stdout = Logger()
        sys.stderr = sys.stdout # 将错误也重定向到同一个日志
        print(f"[System] Log initialized at {sys.stdout.log_path}")
    except Exception as e:
        print(f"[System] Failed to initialize logger: {e}")

    # 允许WebEngine自动播放音频
    sys.argv.append("--autoplay-policy=no-user-gesture-required")
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
