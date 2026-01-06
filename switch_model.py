"""切换Google Gemini模型"""
import json
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path.home() / ".knowledgesight"
CONFIG_FILE = CONFIG_DIR / "credentials.json"

# 可用的Gemini模型列表
MODELS = {
    "1": {
        "name": "gemini-1.5-flash",
        "full": "models/gemini-1.5-flash",
        "desc": "快速模型（当前使用），适合快速生成，免费额度高"
    },
    "2": {
        "name": "gemini-1.5-pro",
        "full": "models/gemini-1.5-pro",
        "desc": "专业模型，质量更高，理解能力更强，但速度较慢"
    },
    "3": {
        "name": "gemini-2.0-flash-exp",
        "full": "models/gemini-2.0-flash-exp",
        "desc": "实验性2.0模型（最新），速度快，可能有更好的创作能力"
    }
}

def load_config():
    """加载当前配置"""
    if not CONFIG_FILE.exists():
        print(f"❌ 配置文件不存在: {CONFIG_FILE}")
        print("请先运行 setup_api.py 配置Google API")
        return None
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    """保存配置"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def main():
    print("=" * 60)
    print("Google Gemini 模型切换工具")
    print("=" * 60)
    
    # 加载当前配置
    config = load_config()
    if not config:
        return
    
    # 显示当前模型
    current_model = config.get('google', {}).get('model', 'models/gemini-1.5-flash')
    print(f"\n当前模型: {current_model}")
    
    # 显示可用模型
    print("\n可用模型:")
    print("-" * 60)
    for key, model in MODELS.items():
        current_mark = "✓ " if model['full'] == current_model else "  "
        print(f"{current_mark}{key}. {model['name']}")
        print(f"   {model['desc']}")
        print()
    
    # 选择新模型
    choice = input("请选择模型编号 (1-3, 回车取消): ").strip()
    
    if not choice:
        print("\n已取消")
        return
    
    if choice not in MODELS:
        print(f"\n❌ 无效选择: {choice}")
        return
    
    # 更新配置
    new_model = MODELS[choice]
    if 'google' not in config:
        config['google'] = {}
    
    config['google']['model'] = new_model['full']
    
    # 保存配置
    save_config(config)
    
    print(f"\n✅ 已切换到: {new_model['name']}")
    print(f"   完整名称: {new_model['full']}")
    print(f"\n⚠️  请重启应用以使更改生效")
    print("   运行: python knowledgesight/main.py")

if __name__ == "__main__":
    main()
