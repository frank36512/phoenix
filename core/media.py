from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence

try:  # PIL may not be present until requirements are installed
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # noqa: BLE001
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]

try:  # numpy may not be present until requirements are installed
    import numpy as np
except Exception as exc:  # noqa: BLE001
    np = None  # type: ignore[assignment]

try:  # moviepy may not be present until requirements are installed
    # Try moviepy 2.x imports first (top level)
    try:
        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips, AudioClip, concatenate_audioclips
    except ImportError:
        # Fallback to moviepy 1.x imports
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, AudioClip, concatenate_audioclips
except Exception as exc:  # noqa: BLE001
    AudioFileClip = None  # type: ignore[assignment]
    ImageClip = None  # type: ignore[assignment]
    concatenate_videoclips = None  # type: ignore[assignment]
    AudioClip = None
    concatenate_audioclips = None
    _moviepy_error: Optional[Exception] = exc
else:
    _moviepy_error = None

try:  # pyttsx3 is optional for audio narration
    import pyttsx3
except Exception as exc:  # noqa: BLE001
    pyttsx3 = None  # type: ignore[assignment]
    _tts_error: Optional[Exception] = exc
else:
    _tts_error = None

try:  # edge-tts for better TTS quality
    import edge_tts
    import asyncio
except Exception as exc:  # noqa: BLE001
    edge_tts = None  # type: ignore[assignment]
    _edge_tts_error: Optional[Exception] = exc
else:
    _edge_tts_error = None

# Removed gTTS as requested

import sys
import httpx
import json
import ssl
try:
    from .utils import ensure_dir, slugify
except ImportError:
    PARENT_DIR = Path(__file__).resolve().parent
    if str(PARENT_DIR) not in sys.path:
        sys.path.append(str(PARENT_DIR))
    from utils import ensure_dir, slugify

def create_permissive_ssl_context():
    """创建宽松的SSL上下文，解决某些服务器握手失败的问题"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # 尝试降低安全级别以支持更多加密套件
        try:
            ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        except Exception:
            pass
        return ctx
    except Exception:
        return False  # Fallback to verify=False

async def generate_tts_audio_async(text: str, output_path: Path, voice: str = "zh-CN-XiaoxiaoNeural") -> bool:
    """使用Edge TTS异步生成高质量中文语音"""
    if edge_tts is None:
        return False
    
    try:
        text = text.strip()
        if not text:
            return False
        text = text.replace('\x00', '')
        if len(text) > 3000:
            text = text[:3000]
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用用户指定的语音
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate="+0%",
            pitch="+0Hz"
        )
        await communicate.save(str(output_path))
        
        return output_path.exists() and output_path.stat().st_size > 0
            
    except Exception as e:
        print(f"Edge TTS生成失败: {e}")
        return False


async def generate_tts_audio_xiaoai(text: str, output_path: Path, api_key: str, base_url: str, voice: str, model: str = "tts-1", speed: float = 1.0) -> bool:
    """使用Xiaoai TTS (OpenAI兼容接口)"""
    print(f"[TTS] Xiaoai Request: voice={voice}, model={model}, speed={speed}, base_url={base_url}")
    if not api_key:
        print("[TTS] Xiaoai TTS失败: 未提供API Key")
        return False
        
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 智能构造请求URL
        base_url = base_url.rstrip('/')
        if base_url.endswith("/audio/speech"):
            url = base_url
        else:
            url = f"{base_url}/audio/speech"
            
        print(f"[TTS] Xiaoai Final URL: {url}")
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 尝试带speed参数
        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "speed": speed
        }
        
        ssl_context = create_permissive_ssl_context()
        async with httpx.AsyncClient(verify=ssl_context, timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            # 如果因为参数错误失败（例如不支持speed），尝试不带speed重试
            if response.status_code == 400 and "speed" in response.text.lower():
                print(f"[TTS] Xiaoai 400 Error (possibly speed param), retrying without speed...")
                payload.pop("speed", None)
                response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"[TTS] Xiaoai TTS API错误: {response.status_code} - {response.text}")
                return False
            
            with open(output_path, "wb") as f:
                f.write(response.content)
        
        size = output_path.stat().st_size if output_path.exists() else 0
        print(f"[TTS] Xiaoai 生成成功: {output_path.name} ({size} bytes)")
        return output_path.exists() and size > 0
    except Exception as e:
        print(f"[TTS] Xiaoai TTS生成异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def generate_tts_audio_aliyun(text: str, output_path: Path, api_key: str, voice: str, model: str = "cosyvoice-v1", base_url: str = None, rate: float = 1.0, volume: int = 50) -> bool:
    """使用通义千问 (Aliyun CosyVoice) TTS - OpenAI Compatible Interface"""
    print(f"[TTS] Aliyun Request: voice={voice}, model={model}, rate={rate}, volume={volume}, base_url={base_url}")
    if not api_key:
        print("[TTS] Aliyun TTS失败: 未提供API Key")
        return False
        
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Default URLs
        openai_compatible_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/speech"
        dashscope_url = "https://dashscope.aliyuncs.com/api/v1/services/audio/text-to-speech/generation"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 构造 OpenAI 格式请求 payload
        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "speed": rate
        }
        
        # 特殊处理 qwen3-tts-flash
        if model == "qwen3-tts-flash":
             # Standard DashScope API
             # User reported correct URL: https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
             target_suffix = "/services/aigc/multimodal-generation/generation"
             
             if base_url:
                 # If user provided a base url, we assume it's the root API path (e.g. .../api/v1)
                 # We append the service path if not present
                 if "services/" not in base_url:
                     url = f"{base_url.rstrip('/')}{target_suffix}"
                 else:
                     url = base_url
             else:
                 url = f"https://dashscope.aliyuncs.com/api/v1{target_suffix}"

             payload = {
                "model": model,
                "input": {
                    "text": text
                },
                "parameters": {
                    "voice": voice,
                    "sample_rate": 24000,
                    "format": "mp3",
                    "volume": volume,
                    "speech_rate": int((rate - 1.0) * 500)
                }
            }
        else:
            # OpenAI Compatible
            if base_url:
                 if "audio/speech" not in base_url:
                     url = f"{base_url.rstrip('/')}/audio/speech"
                 else:
                     url = base_url
            else:
                 url = openai_compatible_url
        
        print(f"[TTS] Aliyun URL: {url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"[TTS] Aliyun TTS API错误: {response.status_code} - {response.text}")
                # 如果是 400 且包含 speed，尝试去掉 speed 重试 (兼容性处理)
                if response.status_code == 400 and "speed" in response.text.lower():
                     print(f"[TTS] Aliyun Retrying without speed param...")
                     payload.pop("speed", None)
                     response = await client.post(url, json=payload, headers=headers)
                     if response.status_code != 200:
                         print(f"[TTS] Aliyun Retry Failed: {response.status_code} - {response.text}")
                         return False

            if response.status_code == 200:
                # Check if response is JSON (for qwen3-tts-flash)
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type or (model == "qwen3-tts-flash" and response.content.strip().startswith(b"{")):
                    try:
                        data = response.json()
                        if "output" in data and "audio" in data["output"] and "url" in data["output"]["audio"]:
                            audio_url = data["output"]["audio"]["url"]
                            print(f"[TTS] Aliyun downloading audio from: {audio_url}")
                            # Download the audio
                            audio_response = await client.get(audio_url)
                            if audio_response.status_code == 200:
                                with open(output_path, "wb") as f:
                                    f.write(audio_response.content)
                            else:
                                print(f"[TTS] Failed to download audio from URL: {audio_response.status_code}")
                                return False
                        else:
                            # Fallback: maybe it's direct binary?
                            print(f"[TTS] Aliyun JSON response but no audio URL found: {data}")
                            return False
                    except Exception as e:
                        print(f"[TTS] Error parsing Aliyun JSON response: {e}")
                        return False
                else:
                    # Direct binary response (OpenAI compatible)
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                
        size = output_path.stat().st_size if output_path.exists() else 0
        return output_path.exists() and size > 0
    except Exception as e:
        print(f"[TTS] Aliyun TTS生成失败: {e}")
        return False


async def generate_tts_audio_qwen(text: str, output_path: Path, api_key: str, voice: str = "Cherry", language: str = "Chinese", base_url: str = "https://dashscope.aliyuncs.com/api/v1") -> bool:
    """使用阿里云Qwen3-TTS-Flash生成语音"""
    print(f"[TTS] Qwen Request: voice={voice}, language={language}, base_url={base_url}")
    if not api_key:
        print("[TTS] Qwen TTS失败: 未提供API Key")
        return False
    
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 构造API URL
        # 官方推荐 endpoint: https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
        target_path = "/services/aigc/multimodal-generation/generation"
        
        # 强制使用 dashscope.aliyuncs.com 的正确基础 URL
        # 如果用户错误配置了 base_url (例如指向 compatible-mode)，我们在这里进行修正
        if "dashscope.aliyuncs.com" in base_url:
             # 重置为标准 API 根路径
             base_url = "https://dashscope.aliyuncs.com/api/v1"
        
        base_url = base_url.rstrip('/')
        if "services/" not in base_url:
            url = f"{base_url}{target_path}"
        else:
            url = base_url
            
        print(f"[TTS] Qwen Final URL: {url}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Determine format from output path
        audio_format = "wav" if output_path.suffix.lower() == ".wav" else "mp3"
        
        payload = {
            "model": "qwen3-tts-flash",
            "input": {
                "text": text
            },
            "parameters": {
                "voice": voice,
                "format": audio_format,
                "sample_rate": 24000,
                "volume": 50,
                "speech_rate": 0
            }
        }
        
        ssl_context = create_permissive_ssl_context()
        async with httpx.AsyncClient(verify=ssl_context, timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                print(f"[TTS] Qwen TTS API错误: {response.status_code} - {response.text}")
                return False
            
            # 解析JSON响应
            try:
                data = response.json()
                if "output" in data and "audio" in data["output"]:
                    audio_data = data["output"]["audio"]
                    # audio_data可能是Base64编码或直接的URL
                    if isinstance(audio_data, dict) and "url" in audio_data:
                        # 下载URL中的音频
                        audio_url = audio_data["url"]
                        print(f"[TTS] Qwen downloading audio from: {audio_url}")
                        audio_response = await client.get(audio_url, timeout=30.0)
                        if audio_response.status_code == 200:
                            with open(output_path, "wb") as f:
                                f.write(audio_response.content)
                        else:
                            print(f"[TTS] Qwen failed to download audio: {audio_response.status_code}")
                            return False
                    elif isinstance(audio_data, str):
                        # Base64编码的音频数据
                        # 检查是否是URL
                        if audio_data.startswith("http"):
                             audio_url = audio_data
                             print(f"[TTS] Qwen downloading audio from: {audio_url}")
                             audio_response = await client.get(audio_url, timeout=30.0)
                             if audio_response.status_code == 200:
                                 with open(output_path, "wb") as f:
                                     f.write(audio_response.content)
                             else:
                                 print(f"[TTS] Qwen failed to download audio: {audio_response.status_code}")
                                 return False
                        else:
                            # Base64 decode
                            import base64
                            audio_bytes = base64.b64decode(audio_data)
                            with open(output_path, "wb") as f:
                                f.write(audio_bytes)
                    else:
                        print(f"[TTS] Qwen unexpected audio format: {type(audio_data)}")
                        return False
                else:
                    print(f"[TTS] Qwen no audio in response: {data}")
                    return False
            except Exception as e:
                print(f"[TTS] Qwen failed to parse response: {e}")
                return False
        
        size = output_path.stat().st_size if output_path.exists() else 0
        print(f"[TTS] Qwen生成成功: {output_path.name} ({size} bytes)")
        return output_path.exists() and size > 0
    except Exception as e:
        print(f"[TTS] Qwen TTS生成异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_tts_audio_pyttsx3(text: str, output_path: Path) -> bool:
    """使用pyttsx3生成本地TTS（离线，无需网络）
    
    Args:
        text: 要转换为语音的文字
        output_path: 输出音频文件路径（.wav或.mp3格式）
    
    Returns:
        bool: 成功返回True，失败返回False
    """
    if pyttsx3 is None:
        return False
    
    try:
        # 初始化引擎
        engine = pyttsx3.init()
        
        # 设置中文语音（如果可用）
        try:
            voices = engine.getProperty('voices')
            for voice in voices:
                voice_lang = getattr(voice, 'languages', [])
                if 'chinese' in voice.name.lower() or any('zh' in str(lang).lower() for lang in voice_lang):
                    engine.setProperty('voice', voice.id)
                    break
        except:
            pass
        
        # 设置语速和音量
        try:
            engine.setProperty('rate', 160)  # 稍快的语速
            engine.setProperty('volume', 0.9)
        except:
            pass
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存到文件
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        engine.stop()
        
        # 检查文件是否生成成功
        return output_path.exists() and output_path.stat().st_size > 0
            
    except Exception as e:
        return False


import threading

def run_sync(coro):
    """Helper to run async coroutine synchronously, handling nested loops"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        # Run in a separate thread to avoid "loop already running" error
        result = None
        exception = None
        def run():
            nonlocal result, exception
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result = new_loop.run_until_complete(coro)
            except Exception as e:
                exception = e
            finally:
                new_loop.close()
        
        t = threading.Thread(target=run)
        t.start()
        t.join()
        if exception:
            raise exception
        return result
    else:
        # No loop running, use asyncio.run
        return asyncio.run(coro)

def generate_tts_audio(text: str, output_path: Path, tts_engine: str = "edge_tts", voice: str = "zh-CN-XiaoxiaoNeural", tts_config: Dict[str, Any] = None) -> bool:
    """智能TTS生成：根据用户选择的引擎生成语音"""
    text = text.strip()
    if not text:
        return False
    
    tts_config = tts_config or {}
    
    # 显示当前使用的TTS引擎
    engine_display_names = {
        "xiaoai": "Xiaoai TTS",
        "aliyun": "阿里云Cosyvoice",
        "qwen3-tts-flash": "阿里云Qwen3-TTS-Flash",
        "edge_tts": "Microsoft Edge TTS",
        "custom": "自定义OpenAI兼容TTS"
    }
    
    print(f"[TTS使用] 优先引擎: {engine_display_names.get(tts_engine, tts_engine)}")
    print(f"[TTS参数] 语音: {voice}")
    
    # 优先级列表
    engines_to_try = []
    if tts_engine == "xiaoai":
        engines_to_try = ["xiaoai", "edge_tts"]
    elif tts_engine == "aliyun":
        engines_to_try = ["aliyun", "edge_tts"]
    elif tts_engine == "qwen3-tts-flash":
        engines_to_try = ["qwen3-tts-flash", "edge_tts"]
    elif tts_engine == "custom":
        engines_to_try = ["custom", "edge_tts"]
    elif tts_engine == "edge_tts":
        engines_to_try = ["edge_tts"]
    else:
        engines_to_try = ["edge_tts"]
    
    for engine in engines_to_try:
        print(f"[TTS] Trying engine: {engine}")
        if engine == "xiaoai":
            try:
                # 确保使用.mp3
                mp3_path = output_path.with_suffix('.mp3')
                api_key = tts_config.get("xiaoai_api_key", "")
                base_url = tts_config.get("xiaoai_base_url", "https://xiaoai.plus/v1")
                
                # 获取配置参数
                xiaoai_voice = tts_config.get("xiaoai_voice") or (voice if voice and "Neural" not in voice else "alloy")
                xiaoai_model = tts_config.get("xiaoai_model") or "tts-1"
                xiaoai_speed = float(tts_config.get("xiaoai_speed") or 1.0)
                
                result = run_sync(generate_tts_audio_xiaoai(text, mp3_path, api_key, base_url, xiaoai_voice, xiaoai_model, xiaoai_speed))
                if result:
                    print(f"[TTS] Xiaoai Success")
                    return True
            except Exception as e:
                print(f"[TTS] Xiaoai TTS尝试失败: {e}")
                pass

        elif engine == "aliyun":
            try:
                # 确保使用.mp3
                mp3_path = output_path.with_suffix('.mp3')
                api_key = tts_config.get("aliyun_api_key", "")
                
                # 获取配置参数
                aliyun_voice = tts_config.get("aliyun_voice") or (voice if voice and "Neural" not in voice else "longxiaochun")
                aliyun_model = tts_config.get("aliyun_model") or "cosyvoice-v1"
                aliyun_base_url = tts_config.get("aliyun_base_url")
                aliyun_rate = float(tts_config.get("aliyun_rate") or 1.0)
                aliyun_volume = int(tts_config.get("aliyun_volume") or 50)
                
                result = run_sync(generate_tts_audio_aliyun(text, mp3_path, api_key, aliyun_voice, aliyun_model, aliyun_base_url, aliyun_rate, aliyun_volume))
                if result:
                    print(f"[TTS成功] 阿里云Cosyvoice已生成语音")
                    return True
            except Exception as e:
                print(f"[TTS] Aliyun TTS尝试失败: {e}")
                pass

        elif engine == "qwen3-tts-flash":
            try:
                # 确保使用.wav
                wav_path = output_path.with_suffix('.wav')
                api_key = tts_config.get("qwen_api_key", "")
                
                # 获取配置参数
                qwen_voice = tts_config.get("qwen_voice") or voice or "Cherry"
                qwen_language = tts_config.get("qwen_language") or "Chinese"
                qwen_api_base = tts_config.get("qwen_api_base") or "https://dashscope.aliyuncs.com/api/v1"
                
                if not api_key:
                    print(f"[TTS] Qwen API Key未配置，跳过")
                else:
                    result = run_sync(generate_tts_audio_qwen(text, wav_path, api_key, qwen_voice, qwen_language, qwen_api_base))
                    if result:
                        print(f"[TTS成功] 阿里云Qwen3-TTS-Flash已生成语音 (语音: {qwen_voice}, 语言: {qwen_language})")
                        return True
            except Exception as e:
                print(f"[TTS] Qwen3-TTS-Flash TTS尝试失败: {e}")
                pass

        elif engine == "custom":
            try:
                # 确保使用.mp3
                mp3_path = output_path.with_suffix('.mp3')
                api_key = tts_config.get("custom_api_key", "")
                base_url = tts_config.get("custom_api_base", "")
                
                # 获取配置参数
                custom_voice = tts_config.get("custom_voice") or voice or "alloy"
                custom_model = tts_config.get("custom_model") or "tts-1"
                
                if not api_key:
                    print(f"[TTS] Custom API Key未配置，跳过")
                else:
                    # 复用 xiaoai (OpenAI兼容) 的实现
                    result = run_sync(generate_tts_audio_xiaoai(text, mp3_path, api_key, base_url, custom_voice, custom_model, 1.0))
                    if result:
                        print(f"[TTS成功] 自定义TTS已生成语音")
                        return True
            except Exception as e:
                print(f"[TTS] Custom TTS尝试失败: {e}")
                pass

        elif engine == "edge_tts" and edge_tts is not None:
            try:
                mp3_path = output_path.with_suffix('.mp3')
                # 确保使用Edge语音名称
                # 如果voice参数包含Neural，说明是Edge语音，直接使用
                # 否则（例如是alloy），则使用配置中的fallback edge_voice，或者默认值
                fallback_voice = tts_config.get("edge_voice") or "zh-CN-XiaoxiaoNeural"
                edge_voice = voice if "Neural" in voice else fallback_voice
                
                print(f"[TTS] Fallback to Edge TTS with voice: {edge_voice}")
                
                result = run_sync(generate_tts_audio_async(text, mp3_path, edge_voice))
                if result:
                    return True
            except Exception as e:
                pass
        
        elif engine == "pyttsx3" and pyttsx3 is not None:
            try:
                wav_path = output_path.with_suffix('.wav')
                result = generate_tts_audio_pyttsx3(text, wav_path)
                if result:
                    return True
            except Exception as e:
                print(f"pyttsx3生成失败: {e}")
    
    return False

if TYPE_CHECKING:  # pragma: no cover - used for static analysis only
    MoviepyImageClip = Any
    pyttsx3_typing = Any


_RESOLUTION_MAP = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


@dataclass
class VideoSettings:
    resolution: str = "1080p"
    include_audio: bool = True
    slide_duration: float = 6.0
    fps: int = 30
    voice: Optional[str] = None
    voice_provider: Optional[str] = "edge_tts"
    
    # Custom Resolution (overrides resolution string if set)
    width: Optional[int] = None
    height: Optional[int] = None
    
    # 背景音乐
    background_music: Optional[str] = None
    background_music_volume: float = 0.3
    
    # 水印设置
    watermark_enabled: bool = False
    watermark_type: str = "text"  # "text" or "image"
    watermark_content: str = ""
    watermark_position: str = "top_right"
    watermark_opacity: float = 0.8
    watermark_size: float = 0.15

    def size(self) -> tuple[int, int]:
        if self.width is not None and self.height is not None:
            return (self.width, self.height)
        key = (self.resolution or "").lower()
        return _RESOLUTION_MAP.get(key, _RESOLUTION_MAP["1080p"])


class MediaComposer:
    """Render storyboard-driven videos with optional narration."""

    def ensure_ready(self) -> None:
        if ImageClip is None or concatenate_videoclips is None:
            raise RuntimeError(
                "moviepy 未安装或未正确初始化，请先执行 pip install moviepy pillow pyttsx3"
            ) from _moviepy_error

    def export_animation_video(
        self,
        topic: str,
        storyboard: Sequence[Dict[str, str]],
        destination: Path,
        settings: VideoSettings,
        progress_callback = None
    ) -> Optional[Path]:
        """
        导出HTML动画为视频（使用playwright渲染真实动画）
        
        Returns:
            Path: 如果成功返回视频路径，失败返回None
        """
        try:
            from .video_renderer import render_animation_to_video, PLAYWRIGHT_AVAILABLE
            
            if not PLAYWRIGHT_AVAILABLE:
                print("[INFO] Playwright not available, cannot export animation video")
                return None
            
            # 查找HTML动画文件（使用相对路径而不是导入）
            from pathlib import Path
            current_dir = Path(__file__).parent
            resources_dir = current_dir.parent / "resources"
            animations_dir = resources_dir / "offline" / "animations"
            html_path = animations_dir / f"{topic}.html"
            
            if not html_path.exists():
                print(f"[INFO] Animation HTML not found: {html_path}")
                return None
            
            # 查找对应的音频文件
            audio_dir = resources_dir / "offline" / "audio"
            
            # 准备音频片段列表
            audio_clips = []
            
            # 检查 moviepy 组件
            if not AudioClip or not concatenate_audioclips:
                print("[ERROR] moviepy not properly loaded, audio export may fail")
            
            for idx, frame in enumerate(storyboard):
                audio_mp3 = audio_dir / f"{topic}_{idx}.mp3"
                audio_wav = audio_dir / f"{topic}_{idx}.wav"
                
                current_clip = None
                
                # 尝试加载存在的音频文件
                if audio_wav.exists() and audio_wav.stat().st_size > 0:
                    try:
                        current_clip = AudioFileClip(str(audio_wav))
                    except Exception as e:
                        print(f"[WARN] Failed to load wav (frame {idx}): {e}")
                        
                if not current_clip and audio_mp3.exists() and audio_mp3.stat().st_size > 0:
                    try:
                        current_clip = AudioFileClip(str(audio_mp3))
                    except Exception as e:
                        print(f"[WARN] Failed to load mp3 (frame {idx}): {e}")
                
                if current_clip:
                    audio_clips.append(current_clip)
                    print(f"[音频] 帧 {idx+1}: {current_clip.duration:.2f}s (文件)")
                else:
                    # 无音频，生成静音片段以保持时间轴同步
                    # 计算估算时长 (与 orchestrator.py 逻辑保持一致)
                    text = frame.get("narration") or frame.get("body") or ""
                    # 清除HTML标签
                    if text:
                        import re
                        text = re.sub(r'<[^>]+>', '', text)
                    
                    # 估算时长算法
                    char_count = len(text)
                    duration = max(3.0, char_count * 0.3 + 1.0)
                    
                    # 创建静音片段
                    if AudioClip and np is not None:
                        try:
                            # 创建静音片段 (stereo)
                            silence = AudioClip(lambda t: np.zeros((1, 2)), duration=duration, fps=44100)
                            audio_clips.append(silence)
                            print(f"[音频] 帧 {idx+1}: {duration:.2f}s (静音补全)")
                        except Exception as e:
                             print(f"[WARN] Failed to create silence clip: {e}")
                    else:
                         print(f"[WARN] Cannot create silence clip (missing numpy/AudioClip), sync may break")

            # 合并所有音频（如果有多个）
            combined_audio = None
            if audio_clips and concatenate_audioclips:
                try:
                    import tempfile
                    combined = concatenate_audioclips(audio_clips)
                    # 保存到临时文件
                    temp_audio = Path(tempfile.gettempdir()) / f"combined_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                    combined.write_audiofile(str(temp_audio), logger=None)
                    combined_audio = temp_audio
                    
                    # 清理内存中的clips (保留 combined 用于后续引用? 不，combined_audio 是路径)
                    for clip in audio_clips:
                        clip.close()
                    combined.close()
                    
                    print(f"[INFO] Combined {len(audio_clips)} audio clips into: {combined_audio}")
                except Exception as e:
                    print(f"[ERROR] Failed to combine audio clips: {e}")
            
            if audio_clips and not combined_audio:
                print("[WARNING] Failed to combine audio files. Will generate silent video.")
            
            # 渲染动画为视频
            ensure_dir(destination.parent)
            filename = self._build_filename(topic)
            output_path = destination.with_name(filename)
            
            width, height = settings.size()
            
            # 如果没有音频，使用默认时长
            duration = None
            if not combined_audio:
                # 智能估算时长
                total_est = 0
                for frame in storyboard:
                     text = frame.get("narration") or frame.get("body") or ""
                     # 清除HTML标签
                     if text:
                         import re
                         text = re.sub(r'<[^>]+>', '', text)
                     est = max(3.0, len(text) * 0.3 + 1.0)
                     total_est += est
                duration = total_est
                print(f"[INFO] No audio available, using calculated duration: {duration}s")
            
            # 构建水印配置
            watermark_config = {
                "enabled": settings.watermark_enabled,
                "type": settings.watermark_type,
                "content": settings.watermark_content,
                "position": settings.watermark_position,
                "opacity": settings.watermark_opacity,
                "size": settings.watermark_size
            }

            success = render_animation_to_video(
                str(html_path),
                str(combined_audio) if combined_audio else "",
                str(output_path),
                duration=duration,  # 自动从音频获取或使用计算时长
                fps=settings.fps,
                width=width,
                height=height,
                watermark_config=watermark_config,
                progress_callback=progress_callback,
                background_music=settings.background_music,
                background_music_volume=settings.background_music_volume
            )
            
            if success and output_path.exists():
                print(f"[SUCCESS] Animation video exported: {output_path}")
                return output_path
            else:
                print("[INFO] Animation video export failed")
                return None
                
        except Exception as e:
            print(f"[ERROR] Failed to export animation video: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _combine_audio_files(self, audio_files: List[Path]) -> Optional[Path]:
        """合并多个音频文件为一个"""
        if not audio_files:
            return None
        
        if len(audio_files) == 1:
            return audio_files[0]
        
        try:
            # Check global imports
            if AudioFileClip is None or concatenate_audioclips is None:
                raise ImportError("MoviePy not properly loaded")

            import tempfile
            
            # 加载所有音频片段
            clips = [AudioFileClip(str(f)) for f in audio_files]
            
            # 合并音频
            combined = concatenate_audioclips(clips)
            
            # 保存到临时文件
            temp_audio = Path(tempfile.gettempdir()) / f"combined_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            combined.write_audiofile(str(temp_audio), logger=None)
            
            # 清理
            for clip in clips:
                clip.close()
            combined.close()
            
            print(f"[INFO] Combined {len(audio_files)} audio files into: {temp_audio}")
            return temp_audio
            
        except Exception as e:
            print(f"[ERROR] Failed to combine audio files: {e}")
            return None

    def export_storyboard_video(
        self,
        topic: str,
        storyboard: Sequence[Dict[str, str]],
        narration: str,
        destination: Path,
        settings: VideoSettings,
    ) -> Path:
        self.ensure_ready()
        storyboard = list(storyboard) if storyboard else []
        if not storyboard:
            storyboard = [
                {
                    "heading": topic or "知识可视化",
                    "body": narration or "本地生成的动画演示",  # simple fallback
                }
            ]
        width, height = settings.size()
        ensure_dir(destination.parent)

        with tempfile.TemporaryDirectory(prefix="ksight_media_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_paths: List[Path] = []
            if settings.include_audio and storyboard:
                audio_paths = self._create_audio_segments(storyboard, tmp_path, settings)

            clips: List[Any] = []
            try:
                for idx, frame in enumerate(storyboard):
                    image = self._build_slide_image(frame, width, height)
                    # moviepy 2.x: duration is passed to constructor
                    duration = settings.slide_duration
                    if settings.include_audio and idx < len(audio_paths):
                        audio_clip = AudioFileClip(str(audio_paths[idx]))
                        duration = max(audio_clip.duration + 0.8, settings.slide_duration)
                        clip = ImageClip(np.array(image), duration=duration)
                        clip = clip.with_audio(audio_clip)
                    else:
                        clip = ImageClip(np.array(image), duration=duration)
                    clips.append(clip)

                final_clip = concatenate_videoclips(clips, method="compose")
                filename = self._build_filename(topic)
                output_path = destination.with_name(filename)
                final_clip.write_videofile(
                    str(output_path),
                    fps=settings.fps,
                    codec="libx264",
                    audio_codec="aac" if settings.include_audio and audio_paths else None,
                    temp_audiofile=str(tmp_path / "temp_audio.m4a"),
                    remove_temp=True,
                    preset="medium",
                    threads=2,
                )
                return output_path
            finally:
                for clip in clips:
                    clip.close()

    def _build_filename(self, topic: str) -> str:
        slug = slugify(topic or "知识可视化", "ksight")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"可视化_{slug}_{timestamp}.mp4"

    def _create_audio_segments(
        self,
        storyboard: Sequence[Dict[str, str]],
        workspace: Path,
        settings: VideoSettings,
    ) -> List[Path]:
        if settings.voice_provider and settings.voice_provider != "pyttsx3":
            return []
        if pyttsx3 is None:
            return []
        engine = pyttsx3.init()
        voice_id = settings.voice or self._pick_voice(engine)
        if voice_id:
            engine.setProperty("voice", voice_id)
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 0.85)

        targets: List[Path] = []
        for idx, frame in enumerate(storyboard):
            heading = frame.get("heading") or "要点"
            body = frame.get("body") or ""
            text = f"{heading}。{body}"
            path = workspace / f"segment_{idx}.wav"
            engine.save_to_file(text, str(path))
            targets.append(path)
        engine.runAndWait()
        engine.stop()
        return [path for path in targets if path.exists()]

    def _pick_voice(self, engine: Any) -> Optional[str]:
        try:
            voices = engine.getProperty("voices")
        except Exception:  # noqa: BLE001
            return None
        preferred = ["zh", "cn", "chinese"]
        for voice in voices:
            voice_id = getattr(voice, "id", "") or ""
            voice_name = getattr(voice, "name", "") or ""
            label = f"{voice_id} {voice_name}".lower()
            if any(token in label for token in preferred):
                return voice_id
        return voices[0].id if voices else None

    def list_voices(self) -> List[Dict[str, str]]:
        if pyttsx3 is None:
            return []
        engine = pyttsx3.init()
        voices: List[Dict[str, str]] = []
        try:
            for voice in engine.getProperty("voices"):
                raw_languages = getattr(voice, "languages", []) or []
                languages = []
                for item in raw_languages:
                    if isinstance(item, bytes):
                        try:
                            languages.append(item.decode("utf-8", errors="ignore"))
                        except Exception:
                            continue
                    else:
                        languages.append(str(item))
                voices.append(
                    {
                        "id": getattr(voice, "id", ""),
                        "name": getattr(voice, "name", ""),
                        "languages": ", ".join(languages),
                    }
                )
        finally:
            engine.stop()
        return voices

    def _build_slide_image(self, frame: Dict[str, str], width: int, height: int) -> Image.Image:
        background = self._gradient_background(width, height)
        draw = ImageDraw.Draw(background)
        margin = int(min(width, height) * 0.08)
        radius = int(min(width, height) * 0.06)
        card_box = [margin, margin, width - margin, height - margin]
        draw.rounded_rectangle(card_box, radius=radius, fill="#FFFFFF", outline="#E0E7FF", width=4)

        title_font = self._load_font(int(height * 0.058), bold=True)
        body_font = self._load_font(int(height * 0.037))

        title = frame.get("heading") or "瞬间"
        body = frame.get("body") or ""

        title_x = card_box[0] + int(margin * 0.6)
        title_y = card_box[1] + int(margin * 0.6)
        draw.text((title_x, title_y), title, font=title_font, fill="#1E1B4B")

        body_x = title_x
        body_y = title_y + title_font.size + int(margin * 0.4)
        max_width = card_box[2] - card_box[0] - int(margin * 1.2)
        lines = self._wrap_text(body, body_font, max_width, draw)
        line_height = int(body_font.size * 1.4)
        for offset, line in enumerate(lines):
            draw.text((body_x, body_y + offset * line_height), line, font=body_font, fill="#4C51BF")

        return background

    def _gradient_background(self, width: int, height: int) -> Image.Image:
        base = Image.new("RGB", (width, height), "#EEF2FF")
        overlay = Image.new("RGB", (width, height), "#C7D2FE")
        mask = Image.linear_gradient("L").resize((width, height))
        gradient = Image.composite(overlay, base, mask)
        return gradient

    def _load_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "msyhbd.ttc" if bold else "msyh.ttc",
            "Microsoft YaHei UI Bold.ttf" if bold else "Microsoft YaHei UI.ttf",
            "segoeuib.ttf" if bold else "segoeui.ttf",
            "arialbd.ttf" if bold else "arial.ttf",
        ]
        for name in candidates:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _wrap_text(
        self,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
        draw: ImageDraw.ImageDraw,
    ) -> List[str]:
        if not text:
            return [""]
        lines: List[str] = []
        buffer = ""
        for char in text:
            if char == "\n":
                lines.append(buffer)
                buffer = ""
                continue
            proposal = buffer + char
            if draw.textlength(proposal, font=font) <= max_width or not buffer:
                buffer = proposal
            else:
                lines.append(buffer)
                buffer = char
        if buffer:
            lines.append(buffer)
        return lines


def get_audio_duration(audio_path: Path) -> float:
    """获取音频文件的时长（秒）
    
    Args:
        audio_path: 音频文件路径
        
    Returns:
        音频时长（秒），如果失败返回6.0作为默认值
    """
    if not audio_path.exists():
        print(f"[警告] 音频文件不存在: {audio_path}")
        return 6.0
    
    if audio_path.stat().st_size == 0:
        print(f"[警告] 音频文件为空: {audio_path}")
        return 6.0
    
    try:
        if AudioFileClip is None:
            print("[警告] moviepy未安装，使用默认时长6秒")
            return 6.0
        
        clip = AudioFileClip(str(audio_path))
        duration = clip.duration
        clip.close()
        
        # 确保时长合理（至少1秒）
        if duration < 1.0:
            print(f"[警告] 音频时长过短({duration:.2f}s)，使用1秒")
            return 1.0
        
        return duration
    except Exception as e:
        print(f"[错误] 获取音频时长失败: {e}")
        return 6.0
