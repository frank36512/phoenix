from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class ClientConfigError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.provider = (self.config.get("provider") or "openai").lower()
        self.model = self.config.get("model") or "gpt-4o-mini"
        self.system_prompt = self.config.get(
            "system_prompt",
            "You are a helpful assistant who explains complex topics with short, visual-ready descriptions.",
        )
        self._client = None
        self._online = False
        self._init_client()

    @property
    def is_online(self) -> bool:
        return self._online

    def _init_client(self) -> None:
        try:
            # OpenAI、Deepseek、Claude都使用OpenAI SDK（兼容接口）
            if self.provider in {"openai", "deepseek", "claude", "openai-compatible", "custom"}:
                from openai import AsyncOpenAI  # type: ignore

                # 根据provider获取对应的配置
                if self.provider == "deepseek":
                    settings = self.config.get("deepseek", {}) if isinstance(self.config.get("deepseek"), dict) else {}
                    api_key = settings.get("api_key")
                    base_url = settings.get("base_url") or "https://api.deepseek.com"
                    self.model = settings.get("model") or "deepseek-chat"
                elif self.provider == "claude":
                    settings = self.config.get("claude", {}) if isinstance(self.config.get("claude"), dict) else {}
                    api_key = settings.get("api_key")
                    base_url = settings.get("base_url") or "https://api.anthropic.com/v1"
                    self.model = settings.get("model") or "claude-3-5-sonnet-20241022"
                elif self.provider == "openai-compatible":
                    settings = self.config.get("openai-compatible", {}) if isinstance(self.config.get("openai-compatible"), dict) else {}
                    api_key = settings.get("api_key")
                    base_url = settings.get("base_url")  # 必须提供
                    self.model = settings.get("model") or "gpt-4o-mini"
                elif self.provider == "custom":
                    # 自定义API接口 - 用户完全自定义所有参数
                    settings = self.config.get("custom", {}) if isinstance(self.config.get("custom"), dict) else {}
                    api_key = settings.get("api_key")
                    base_url = settings.get("base_url")  # 必须提供
                    self.model = settings.get("model")  # 必须提供
                    
                    if not base_url:
                        raise ClientConfigError("自定义API必须提供base_url")
                    if not self.model:
                        raise ClientConfigError("自定义API必须提供model")
                else:  # openai
                    settings = self.config.get("openai", {}) if isinstance(self.config.get("openai"), dict) else {}
                    api_key = settings.get("api_key") or self.config.get("openai_api_key")
                    base_url = settings.get("base_url") or self.config.get("openai_base_url")
                    self.model = settings.get("model") or self.model
                
                if not api_key:
                    raise ClientConfigError(f"Missing {self.provider} api_key")
                
                print(f"正在初始化{self.provider.upper()} API，模型: {self.model}")
                if base_url:
                    print(f"  API地址: {base_url}")
                if api_key:
                    masked_key = api_key[:8] + "..." if len(api_key) > 8 else "***"
                    print(f"  API Key: {masked_key}")
                
                # 设置240秒超时，给网络更多时间
                import httpx
                # 创建自定义http_client以支持更多配置
                http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(240.0, connect=60.0),
                    follow_redirects=True,
                    verify=True  # 保持SSL验证
                )
                
                self._client = AsyncOpenAI(
                    api_key=api_key, 
                    base_url=base_url,
                    http_client=http_client
                )
                self._online = True
                print(f"{self.provider.upper()} API初始化成功")
            elif self.provider in {"google", "gemini"}:
                import os
                import google.generativeai as genai  # type: ignore

                # Fix proxy format: ensure http:// or https:// prefix
                for proxy_var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
                    proxy_val = os.environ.get(proxy_var, "")
                    if proxy_val and not proxy_val.startswith(("http://", "https://", "socks")):
                        # Add http:// prefix for bare IP:PORT format
                        os.environ[proxy_var] = f"http://{proxy_val}"

                settings = self.config.get("google", {}) if isinstance(self.config.get("google"), dict) else {}
                api_key = settings.get("api_key") or self.config.get("google_api_key")
                if not api_key:
                    raise ClientConfigError("Missing Google api_key")
                
                # Use the exact model name - default to models/gemini-1.5-flash (higher free tier quota)
                model_name = settings.get("model") or self.model or "models/gemini-1.5-flash"
                # Ensure models/ prefix for new API
                if not model_name.startswith("models/"):
                    model_name = f"models/{model_name}"
                self.model = model_name
                
                # Configure API key and create model instance
                print(f"正在初始化Google API，模型: {self.model}")
                genai.configure(api_key=api_key, transport='rest')
                
                # 创建带超时配置的生成设置
                generation_config = {
                    "temperature": 0.7,
                }
                
                self._client = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config=generation_config
                )
                self._online = True
                print("Google API初始化成功")
            else:
                raise ClientConfigError(f"Unsupported provider: {self.provider}")
        except Exception as exc:  # noqa: BLE001
            print(f"LLM initialisation failed: {exc}")
            self._client = None
            self._online = False

    def get_animation_prompt(self, topic: str, content: str = None, language: str = "zh", frame_count: int = 8) -> str:
        """获取动画生成提示词（用于人工复核）"""
        suffix = "_en.txt" if language == "en" else "_zh.txt"
        if content:
            return self._load_prompt(f"animation_from_content_prompt{suffix}").format(topic=topic, content=content, frame_count=frame_count)
        else:
            return self._load_prompt(f"animation_prompt{suffix}").format(topic=topic, frame_count=frame_count)

    async def generate_animation(self, topic: str, history: Sequence[Dict[str, str]], content: str = None, custom_prompt: str = None, language: str = "zh", frame_count: int = 8) -> str:
        if not self.is_online:
            return ""
        
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = self.get_animation_prompt(topic, content, language, frame_count)
            
        response = await self._request(prompt, history)
        return response.strip()

    async def generate_mindmap(self, topic: str, history: Sequence[Dict[str, str]], content: str = None, language: str = "zh", max_node_length: int = 0) -> str:
        if not self.is_online:
            return ""
            
        # 构造语言要求
        lang_req = ""
        if language == "en":
            lang_req = "\nPlease generate the content in English."
        else:
            lang_req = "\n请使用中文生成内容。"
            
        # 构造节点字数要求
        len_req = ""
        if max_node_length > 0:
            if language == "en":
                len_req = f"\nPlease keep the text of each node concise, not exceeding {max_node_length} words/characters."
            else:
                len_req = f"\n请确保每个节点的文本内容简洁，不超过 {max_node_length} 个字。"
            
        if content:
            # 按内容生成
            prompt_template = self._load_prompt("mindmap_from_content_prompt.txt")
            # 如果没找到文件，使用内置默认Prompt
            if prompt_template == "{topic}":
                prompt_template = """
You are an expert at summarizing content into mind maps.
Please create a comprehensive mind map based on the provided content.
The output format must be a Markdown code block compatible with Markmap (using # for headers, - for lists).

Topic: {topic}

Content:
{content}

Requirements:
1. Identify the main concepts and structure them hierarchically.
2. Use concise labels for nodes.
3. Ensure the structure is logical and balanced.
4. Output ONLY the markdown code block.
"""
            prompt = prompt_template.format(topic=topic, content=content)
            # Append additional requirements
            prompt += f"{lang_req}{len_req}"
        else:
            # 按主题生成
            prompt = self._load_prompt("mindmap_prompt.txt").format(topic=topic)
            # Append additional requirements
            prompt += f"{lang_req}{len_req}"
            
        response = await self._request(prompt, history)
        return response.strip()

    async def generate_graph(self, topic: str, animation_markup: str, history: Sequence[Dict[str, str]]) -> Dict[str, Any]:
        if not self.is_online:
            return {}
        prompt = self._load_prompt("graph_prompt.txt").format(
            topic=topic,
            animation_slice=animation_markup[:6000],
        )
        response = await self._request(prompt, history)
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end <= 0:
                raise ValueError("no json payload")
            payload = json.loads(response[start:end])
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:  # noqa: BLE001
            print(f"Graph JSON parsing failed: {exc}")
            return {}

    async def generate_bar_race(self, topic: str, history: Sequence[Dict[str, str]], content: str = None) -> Dict[str, Any]:
        """生成动态排序柱状图数据"""
        if not self.is_online:
            return {}
            
        if content:
            prompt = self._load_prompt("bar_race_from_content_prompt.txt").format(topic=topic, content=content)
        else:
            prompt = self._load_prompt("bar_race_prompt.txt").format(topic=topic)
            
        response = await self._request(prompt, history)
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end <= 0:
                raise ValueError("no json payload")
            payload = json.loads(response[start:end])
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            print(f"Bar Race JSON parsing failed: {exc}")
            return {}

    async def generate_geo_map(self, topic: str, history: Sequence[Dict[str, str]], content: str = None) -> Dict[str, Any]:
        """生成地理数据可视化数据"""
        if not self.is_online:
            return {}
            
        # Check for dynamic keywords
        dynamic_keywords = ["历史", "变迁", "变化", "趋势", "演变", "history", "evolution", "change", "trend", "timeline"]
        is_dynamic = any(k in topic.lower() for k in dynamic_keywords)
        if content and any(k in content.lower() for k in dynamic_keywords):
            is_dynamic = True
            
        prompt_file = "geo_map_dynamic_prompt.txt" if is_dynamic else "geo_map_prompt.txt"
        
        if content:
            # Note: We might need a geo_map_dynamic_from_content_prompt.txt if we want to be perfect,
            # but for now let's stick to standard flow or just use the prompt based on dynamic flag.
            # If content is present, usually we use _from_content prompts.
            # Let's check if we have dynamic content prompt. We don't.
            # So if content is present, we default to static for now unless we create that file too.
            # Or we can just use the dynamic prompt and append content.
            # Let's keep it simple: if content is present, use static from content (safer).
            # OR create geo_map_dynamic_from_content_prompt.txt.
            # Let's create it.
            pass

        if content:
             prompt_name = "geo_map_from_content_prompt.txt" # Default static
             # If we want dynamic from content, we need that file. 
             # For now, let's prioritize topic-based dynamic generation which uses the main prompt.
             prompt = self._load_prompt(prompt_name).format(topic=topic, content=content)
        else:
            prompt = self._load_prompt(prompt_file).format(topic=topic)
            
        response = await self._request(prompt, history)
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end <= 0:
                raise ValueError("no json payload")
            payload = json.loads(response[start:end])
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            print(f"Geo Map JSON parsing failed: {exc}")
            return {}

    def _load_prompt(self, name: str) -> str:
        prompt_path = Path(__file__).parent / "prompts" / name
        if not prompt_path.exists():
            return "{topic}"
        return prompt_path.read_text(encoding="utf-8")

    async def _request(self, prompt: str, history: Sequence[Dict[str, str]]) -> str:
        if not self._client:
            return ""

        # OpenAI兼容接口（OpenAI、Deepseek、Claude、自定义等）
        if self.provider in {"openai", "deepseek", "claude", "openai-compatible", "custom"}:
            return await self._request_openai(prompt, history)
        # Google Gemini
        if self.provider in {"google", "gemini"}:
            return await self._request_gemini(prompt)
        return ""

    async def _request_openai(self, prompt: str, history: Sequence[Dict[str, str]]) -> str:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        for message in history[-10:]:
            messages.append({
                "role": message.get("role", "user"),
                "content": message.get("content", "")
            })
        messages.append({"role": "user", "content": prompt})
        
        try:
            print(f"发起OpenAI请求: model={self.model}")
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7
            )
            content = response.choices[0].message.content or ""
            print(f"OpenAI请求成功，响应长度: {len(content)}")
            return content
        except Exception as e:
            import traceback
            print(f"OpenAI API Request Failed: {e}")
            traceback.print_exc()
            raise

    async def _request_gemini(self, prompt: str) -> str:
        def _call() -> str:
            response = self._client.generate_content(prompt)
            if hasattr(response, "text") and response.text:
                return response.text
            return ""

        # 使用asyncio.wait_for添加超时保护
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_call),
                timeout=240  # 240秒超时，给网络充足时间
            )
            return result.strip()
        except asyncio.TimeoutError:
            raise ConnectionError("网络连接超时")
        except Exception as e:
            print(f"API调用出错: {type(e).__name__}: {str(e)[:100]}")
            raise
