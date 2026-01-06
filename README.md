# 小凤知识可视化系统 (Phoenix)

## 简介 (Introduction)

小凤知识可视化系统 (Phoenix) 是一个纯 Python 编写的桌面 GUI 应用程序，旨在帮助用户将复杂的知识转化为直观的可视化图表和动画。它集成了 LLM (大语言模型) 能力，能够自动分析文本内容并生成思维导图、地理地图、动画视频等多种形式的可视化内容。

Phoenix is a pure Python desktop GUI application designed to help users transform complex knowledge into intuitive visualizations and animations. Integrated with LLM capabilities, it can automatically analyze text content and generate various forms of visualizations including mind maps, geographic maps, and animated videos.

## 功能特点 (Features)

- **文本分析**: 自动分析输入文本，提取关键信息。
- **思维导图**: 生成层级清晰的思维导图。
- **地理可视化**: 自动识别地理位置信息并生成交互式地图。
- **动画生成**: 将知识点转化为生动的动画视频。
- **本地化**: 支持离线运行 (部分功能)，保护用户隐私。

## 安装与运行 (Installation & Usage)

### 环境要求 (Requirements)
- Python 3.8+
- 依赖库见 `requirements.txt`

### 安装 (Installation)
1. 克隆本仓库:
   ```bash
   git clone https://github.com/yourusername/Phoenix.git
   cd Phoenix
   ```
2. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```

### 配置 (Configuration)
复制 `credentials.example.json` 为 `credentials.json`，并填入您的 API Key (如果使用 LLM 功能):
```bash
cp credentials.example.json credentials.json
# 编辑 credentials.json 填入密钥
```

### 运行 (Run)
```bash
python main.py
```

## 构建 (Build)

如果需要打包为 Windows 可执行文件:
```bash
python build.py
```

## 许可证 (License)

本项目采用 Apache 2.0 许可证。详情请参阅 [LICENSE](LICENSE) 文件。
