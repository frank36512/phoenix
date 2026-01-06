"""快速配置向导 - 支持国内可访问的API"""
import json
from pathlib import Path

def setup_api():
    print("=" * 60)
    print("KnowledgeSight API 配置向导")
    print("=" * 60)
    
    print("\n请选择API提供商：")
    print("1. 离线模式（使用本地缓存，无需API）")
    print("2. 硅基流动 (siliconflow.cn) - 兼容OpenAI接口")
    print("3. 智谱AI (bigmodel.cn) - 国内可访问")
    print("4. OpenAI (需要能访问api.openai.com)")
    print("5. Google Gemini (需要能访问googleapis.com)")
    print("6. 302.AI / OpenAI兼容接口")
    
    choice = input("\n请输入选项 (1-6): ").strip()
    
    config = {}
    
    if choice == "1":
        print("\n✓ 将使用离线模式")
        config = {
            "provider": "offline",
            "model": "local"
        }
    
    elif choice == "2":
        print("\n配置硅基流动API")
        print("获取API密钥: https://cloud.siliconflow.cn/account/ak")
        api_key = input("请输入API Key: ").strip()
        
        config = {
            "provider": "openai",
            "model": "deepseek-ai/DeepSeek-V2.5",
            "openai": {
                "api_key": api_key,
                "base_url": "https://api.siliconflow.cn/v1",
                "model": "deepseek-ai/DeepSeek-V2.5"
            }
        }
    
    elif choice == "3":
        print("\n配置智谱AI")
        print("获取API密钥: https://open.bigmodel.cn/usercenter/apikeys")
        api_key = input("请输入API Key: ").strip()
        
        config = {
            "provider": "openai",
            "model": "glm-4-flash",
            "openai": {
                "api_key": api_key,
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4-flash"
            }
        }
    
    elif choice == "4":
        print("\n配置OpenAI")
        api_key = input("请输入API Key: ").strip()
        
        config = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "openai": {
                "api_key": api_key,
                "model": "gpt-4o-mini"
            }
        }
    
    elif choice == "5":
        print("\n配置Google Gemini")
        print("获取API密钥: https://aistudio.google.com/app/apikey")
        api_key = input("请输入API Key: ").strip()
        
        config = {
            "provider": "google",
            "model": "models/gemini-1.5-flash",
            "google": {
                "api_key": api_key,
                "model": "models/gemini-1.5-flash"
            }
        }

    elif choice == "6":
        print("\n配置 302.AI / OpenAI兼容接口")
        print("302.AI Base URL: https://api.302.ai/v1")
        base_url = input("请输入Base URL (默认 https://api.302.ai/v1): ").strip() or "https://api.302.ai/v1"
        api_key = input("请输入API Key: ").strip()
        model = input("请输入模型名称 (例如 gemini-1.5-pro): ").strip() or "gemini-1.5-pro"
        
        config = {
            "provider": "openai-compatible",
            "model": model,
            "openai-compatible": {
                "api_key": api_key,
                "base_url": base_url,
                "model": model
            }
        }
    
    else:
        print("无效选项，将使用离线模式")
        config = {
            "provider": "offline",
            "model": "local"
        }
    
    # 保存配置
    config_dir = Path.home() / ".knowledgesight"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "credentials.json"
    
    config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print("\n" + "=" * 60)
    print("✅ 配置已保存！")
    print(f"配置文件: {config_file}")
    print("\n现在可以启动程序了：")
    print("python knowledgesight/main.py")
    print("=" * 60)

if __name__ == "__main__":
    setup_api()
