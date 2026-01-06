let graphInstance = null;
let graph3dInstance = null;
let currentGraphData = null; // Store current graph data for re-rendering
let nodeColor = "#4F46E5";
let nodeBorder = "#818CF8";
let edgeColor = "#CBD5F5";
let currentBundle = null;
let currentSettings = {
    video_resolution: "1080p",
    include_audio: true,
    slide_duration: 6,
    fps: 30,
    voice: null,
    voice_provider: "pyttsx3",
};
let isVideoExporting = false;
let credentialState = {
    provider: "openai",
    model: "",
    system_prompt: "",
    openai: {
        api_key: "",
        base_url: "",
        model: "",
    },
    deepseek: {
        api_key: "",
        base_url: "https://api.deepseek.com",
        model: "deepseek-chat",
    },
    claude: {
        api_key: "",
        base_url: "https://api.anthropic.com/v1",
        model: "claude-3-5-sonnet-20241022",
    },
    google: {
        api_key: "",
        model: "",
    },
    "openai-compatible": {
        api_key: "",
        base_url: "",
        model: "gpt-4o-mini",
    },
    custom: {
        api_key: "",
        base_url: "",
        model: "",
    },
};
let availableVoices = [];
let settingsCurrentTab = "video";
let expandedNodes = new Set(); // 记录已展开的节点
let isExpanding = false; // 防止重复展开

const aliyunVoices = {
    "qwen3-tts-flash": [
        { value: "Cherry", label: "芊悦 (阳光积极小姐姐)" },
        { value: "Serena", label: "苏瑶 (温柔小姐姐)" },
        { value: "Ethan", label: "晨煦 (阳光温暖男声)" },
        { value: "Chelsie", label: "千雪 (二次元虚拟女友)" },
        { value: "Momo", label: "茉兔 (撒娇搞怪)" },
        { value: "Vivian", label: "十三 (拽拽的小暴躁)" },
        { value: "Moon", label: "月白 (率性帅气)" },
        { value: "Maia", label: "四月 (知性温柔)" },
        { value: "Kai", label: "凯 (耳朵SPA)" },
        { value: "Nofish", label: "不吃鱼 (设计师)" },
        { value: "Bella", label: "萌宝 (小萝莉)" },
        { value: "Jennifer", label: "詹妮弗 (电影质感美语)" },
        { value: "Ryan", label: "甜茶 (戏感炸裂)" },
        { value: "Katerina", label: "卡捷琳娜 (御姐音)" },
        { value: "Aiden", label: "艾登 (美语大男孩)" },
        { value: "Eldric Sage", label: "沧明子 (沉稳老者)" },
        { value: "Mia", label: "乖小妹 (温顺如春水)" },
        { value: "Mochi", label: "沙小弥 (聪明小大人)" },
        { value: "Bellona", label: "燕铮莺 (声音洪亮)" },
        { value: "Vincent", label: "田叔 (沙哑烟嗓)" },
        { value: "Bunny", label: "萌小姬 (萌属性爆棚)" },
        { value: "Neil", label: "阿闻 (新闻主持人)" },
        { value: "Elias", label: "墨讲师 (严谨讲师)" },
        { value: "Arthur", label: "徐大爷 (质朴嗓音)" },
        { value: "Nini", label: "邻家妹妹 (软糯嗓音)" },
        { value: "Ebona", label: "诡婆婆 (幽暗低语)" },
        { value: "Seren", label: "小婉 (温和助眠)" },
        { value: "Pip", label: "顽屁小孩 (调皮捣蛋)" },
        { value: "Stella", label: "少女阿月 (迷糊/正义少女)" },
        // 方言
        { value: "Jada", label: "上海-阿珍" },
        { value: "Dylan", label: "北京-晓东" },
        { value: "Li", label: "南京-老李" },
        { value: "Marcus", label: "陕西-秦川" },
        { value: "Roy", label: "闽南-阿杰" },
        { value: "Peter", label: "天津-李彼得" },
        { value: "Sunny", label: "四川-晴儿" },
        { value: "Eric", label: "四川-程川" },
        { value: "Rocky", label: "粤语-阿强" },
        { value: "Kiki", label: "粤语-阿清" }
    ]
};

function updateAliyunVoices() {
    const modelSelect = document.getElementById("setting-aliyun-model");
    const voiceSelect = document.getElementById("setting-aliyun-voice");
    if (!modelSelect || !voiceSelect) return;

    const model = modelSelect.value;
    const voices = aliyunVoices[model] || aliyunVoices["qwen3-tts-flash"];

    // Save current selection if possible
    const currentVoice = voiceSelect.value;

    voiceSelect.innerHTML = "";
    voices.forEach(v => {
        const option = document.createElement("option");
        option.value = v.value;
        option.textContent = v.label;
        voiceSelect.appendChild(option);
    });
    
    // Default to first one
    voiceSelect.value = voices[0].value;
}

function getApi() {
    return window.pywebview?.api ?? null;
}

function resolveTheme() {
    const styles = getComputedStyle(document.documentElement);
    nodeColor = styles.getPropertyValue("--primary").trim() || nodeColor;
    nodeBorder = styles.getPropertyValue("--primary-soft").trim() || nodeBorder;
    edgeColor = styles.getPropertyValue("--edge-color").trim() || edgeColor;
}

async function requestVisualization(topic) {
    const api = getApi();
    if (!api || !api.generate_visualization) {
        return mockVisualization(topic);
    }
    return api.generate_visualization(topic);
}

function mockVisualization(topic) {
    const svg = `
        <svg viewBox="0 0 900 480" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#6366F1" stop-opacity="0.95" />
                    <stop offset="100%" stop-color="#A5B4FC" stop-opacity="0.95" />
                </linearGradient>
            </defs>
            <rect x="0" y="0" width="900" height="480" rx="36" fill="url(#bg)" />
            <text x="450" y="210" text-anchor="middle" font-size="40" fill="#FFFFFF" font-weight="600" font-family="Segoe UI">${topic}</text>
            <text x="450" y="260" text-anchor="middle" font-size="18" fill="#E0E7FF" font-family="Segoe UI">示例预览 —— 连接网络生成真实动画</text>
        </svg>
    `;
    return {
        animation_html: svg,
        animation_code: svg,
        graph_data: {
            nodes: [
                { id: "topic", label: topic, group: 1 },
                { id: "ideas", label: "关键要点", group: 2 },
                { id: "use", label: "应用场景", group: 3 },
            ],
            edges: [
                { from: "topic", to: "ideas", label: "包含" },
                { from: "topic", to: "use", label: "延伸" },
            ],
        },
    };
}

function initialiseGraph(graphData) {
    currentGraphData = graphData; // 保存数据以便重新渲染
    resolveTheme();
    const container = document.getElementById("graph-surface");
    if (!container || typeof vis === "undefined") {
        console.warn("Graph surface not ready.");
        return;
    }
    
    // 重置展开状态
    expandedNodes.clear();
    isExpanding = false;

    const nodes = (graphData?.nodes ?? []).map((node, index) => {
        // 扩展形状列表，移除database，保留其他形状并调整文字位置
        const shapes = ['circle', 'box', 'ellipse', 'hexagon', 'diamond', 'triangle', 'star', 'square'];
        let shape = node.shape || shapes[node.group % shapes.length] || 'circle';
        
        // 强制替换 database 形状为 box
        if (shape === 'database') {
            shape = 'box';
        }
        
        // 根据节点重要性（group）动态调整大小
        const sizeMultiplier = node.group === 0 ? 1.5 : node.group === 1 ? 1.2 : 1.0;
        
        const nodeData = {
            ...node,
            shape: shape,
            size: (node.size || 40) * sizeMultiplier,
            color: node.color || {
                background: nodeColor,
                border: nodeBorder,
                highlight: {
                    background: '#FCD34D',
                    border: '#F59E0B'
                },
                hover: {
                    background: nodeBorder,
                    border: '#FBBF24'
                }
            },
            label: node.label || String(node.id),
            // 增强阴影效果 - 多层阴影模拟光照
            shadow: {
                enabled: true,
                color: 'rgba(79, 70, 229, 0.4)',
                size: 15,
                x: 2,
                y: 3
            },
            // 边框光晕效果
            borderWidth: 3,
            borderWidthSelected: 5,
            // 节点缩放配置
            scaling: {
                min: 10,
                max: 60,
                label: {
                    enabled: true,
                    min: 14,
                    max: 30
                }
            }
        };
        
        // 计算最佳文字颜色，确保与节点背景色有足够对比度
        const bgColor = typeof nodeData.color === 'string' ? nodeData.color : nodeData.color.background;
        const textColor = getBestTextColor(bgColor);
        
        nodeData.font = nodeData.font || {};
        nodeData.font.color = textColor;
        
        // 针对默认文字在外部的形状，调整文字位置到内部
        // 注意：vis.js 中，这些形状默认不支持内部文字，必须通过 font.vadjust 强行移上去
        const externalLabelShapes = ['diamond', 'triangle', 'star', 'hexagon', 'square'];
        if (externalLabelShapes.includes(shape)) {
            // 增大尺寸以容纳文字
            const baseSize = (nodeData.size || 40);
            nodeData.size = baseSize * 2.5; // 进一步增大尺寸
            
            // 动态计算 vadjust，确保文字在中心
            // 增加偏移量，确保文字更靠上
            let vadjust = -1.2 * nodeData.size; 
            
            // 针对不同形状的微调
            if (shape === 'triangle') vadjust = -1 * nodeData.size * 0.8; 
            if (shape === 'star') vadjust = -1 * nodeData.size * 1.1;
            if (shape === 'diamond') vadjust = -1 * nodeData.size * 1.2;
            if (shape === 'hexagon') vadjust = -1 * nodeData.size * 1.1;
            
            // 确保 font 对象存在
            nodeData.font = nodeData.font || {};
            
            // 强制应用样式
            Object.assign(nodeData.font, {
                vadjust: vadjust,
                size: 18, // 稍微加大字体
                color: textColor, // 使用外部计算的颜色
                face: "Segoe UI, Microsoft YaHei"
            });
            
            nodeData.shapeProperties = {
                borderDashes: false,
                borderRadius: 6
            };
        }

        // 核心节点（起点）特殊样式：字号更大、加粗
        const isCore = node.group === 0 || node.group === 1 || index === 0;
        if (isCore) {
            nodeData.font = nodeData.font || {};
            Object.assign(nodeData.font, {
                size: 28, // 更大的字号
                face: "Segoe UI, Microsoft YaHei",
                multi: 'md', // 启用 Markdown 支持以实现加粗
                color: textColor // 保持对比度颜色
            });
            // 核心节点尺寸也稍微加大
            nodeData.size = (nodeData.size || 40) * 1.3;
            
            // 确保标签被加粗符号包裹
            if (nodeData.label && !nodeData.label.startsWith('*')) {
                nodeData.label = `*${nodeData.label}*`;
            }
        }
        
        return nodeData;
    });
    const edges = graphData?.edges ?? [];

    const options = {
        nodes: {
            shape: "box",
            size: 40,
            borderWidth: 3,
            margin: 12,
            font: {
                size: 18,
                color: "#1F2937",  // 深色文字确保可见性
                face: "Segoe UI, Microsoft YaHei",
                bold: {
                    color: "#111827",
                },
                // 移除背景色，让文字直接显示在节点颜色上
                // background: "rgba(255, 255, 255, 0.9)",
                // strokeWidth: 2,
                // strokeColor: "#FFFFFF"
            },
            widthConstraint: {
                minimum: 100,
                maximum: 250,
            },
            heightConstraint: {
                minimum: 50,
            },
            // 悬停效果
            chosen: {
                node: function(values, id, selected, hovering) {
                    if (hovering) {
                        values.borderWidth = 5;
                        values.shadowSize = 15;
                        values.shadowX = 0;
                        values.shadowY = 0;
                        values.shadowColor = 'rgba(251, 191, 36, 0.5)';
                    }
                }
            }
        },
        edges: {
            width: 2,
            color: { 
                color: edgeColor, 
                highlight: nodeBorder,
                hover: '#FBBF24',
                opacity: 0.8
            },
            smooth: {
                enabled: true,
                type: "dynamic",
                roundness: 0.6,
                forceDirection: 'none'
            },
            font: {
                size: 14,
                face: "Segoe UI",
                color: "#1F2937",
                background: "rgba(255,255,255,0.95)",
                strokeWidth: 0,
                align: 'middle'
            },
            arrows: {
                to: {
                    enabled: true,
                    scaleFactor: 0.8,
                    type: 'arrow'
                },
            },
            // 连线阴影
            shadow: {
                enabled: true,
                color: 'rgba(99, 102, 241, 0.2)',
                size: 5,
                x: 0,
                y: 0
            },
            length: 250,
            // 悬停时加粗
            chosen: {
                edge: function(values, id, selected, hovering) {
                    if (hovering) {
                        values.width = 4;
                        values.shadowSize = 8;
                    }
                }
            }
        },
        physics: {
            enabled: true,
            solver: "forceAtlas2Based",
            stabilization: {
                enabled: true,
                iterations: 300,
                updateInterval: 10,
                fit: true
            },
            forceAtlas2Based: {
                gravitationalConstant: -50,
                centralGravity: 0.01,
                springLength: 200,
                springConstant: 0.08,
                damping: 0.4,
                avoidOverlap: 0.5
            },
            adaptiveTimestep: true,
            timestep: 0.5,
            maxVelocity: 50,
            minVelocity: 0.1
        },
        layout: {
            improvedLayout: true,
            randomSeed: 42,
        },
        interaction: {
            tooltipDelay: 200,
            hover: true,
            navigationButtons: true,
            keyboard: true,
        },
    };

    // 检查是否开启动态图谱
    const isDynamic = document.getElementById('dynamic-graph-toggle')?.checked;

    if (isDynamic) {
        // 创建空图谱，然后逐步添加节点（动画效果）
        graphInstance = new vis.Network(container, { nodes: [], edges: [] }, options);
        // 动画效果：节点逐个出现，连线逐条绘制
        animateGraphCreation(nodes, edges);
    } else {
        // 静态直接显示
        const data = {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(edges),
        };
        graphInstance = new vis.Network(container, data, options);
    }
    
    // 监听稳定完成事件，确保居中
    graphInstance.on("stabilizationIterationsDone", () => {
        graphInstance.fit({
            animation: {
                duration: 600,
                easingFunction: "easeInOutQuad"
            }
        });
    });
    
    // 初始化完成后立即居中
    graphInstance.once("afterDrawing", () => {
        setTimeout(() => {
            graphInstance.fit({
                animation: {
                    duration: 400,
                    easingFunction: "easeInOutQuad"
                }
            });
        }, 200);
    });

}

// 动态图谱动画：节点逐个出现，连线逐条绘制
function animateGraphCreation(nodes, edges) {
    if (!graphInstance) return;
    
    const nodeDelay = 400; // 每个节点间隔400ms，更明显的逐个效果
    const edgeDelay = 200; // 每条连线间隔200ms
    
    // 先清空图谱，然后逐个添加节点
    graphInstance.body.data.nodes.clear();
    graphInstance.body.data.edges.clear();
    
    console.log(`[动画] 开始逐个添加 ${nodes.length} 个节点...`);
    
    // 逐个添加节点（真正的逐个出现效果）
    nodes.forEach((node, index) => {
        setTimeout(() => {
            console.log(`[动画] 添加第 ${index + 1}/${nodes.length} 个节点: ${node.label}`);
            
            // 初始时节点为透明且极小
            const nodeWithOpacity = {
                ...node,
                opacity: 0,
                size: 5,
                shadow: {
                    enabled: true,
                    color: 'rgba(251, 191, 36, 0.8)',
                    size: 30,
                    x: 0,
                    y: 0
                },
                scaling: {
                    min: 10,
                    max: 60
                }
            };
            
            graphInstance.body.data.nodes.add(nodeWithOpacity);
            
            // 第一阶段：快速放大 + 强光晕
            setTimeout(() => {
                graphInstance.body.data.nodes.update({
                    ...node,
                    opacity: 0.7,
                    size: (node.size || 40) * 1.4,
                    shadow: {
                        enabled: true,
                        color: 'rgba(251, 191, 36, 0.6)',
                        size: 25,
                        x: 2,
                        y: 3
                    }
                });
            }, 80);
            
            // 第二阶段：回弹到正常大小 + 光晕减弱
            setTimeout(() => {
                graphInstance.body.data.nodes.update({
                    ...node,
                    opacity: 1,
                    size: node.size || 40,
                    shadow: {
                        enabled: true,
                        color: 'rgba(79, 70, 229, 0.4)',
                        size: 15,
                        x: 2,
                        y: 3
                    }
                });
            }, 250);
            
            // 添加持续脉冲效果（仅对重要节点）
            if (node.group === 0) {
                startNodePulse(node.id, node.size || 40);
            }
        }, index * nodeDelay);
    });
    
    // 等所有节点加载完成后，再添加连线
    const totalNodeTime = nodes.length * nodeDelay + 200;
    
    edges.forEach((edge, index) => {
        setTimeout(() => {
            graphInstance.body.data.edges.add(edge);
        }, totalNodeTime + index * edgeDelay);
    });
    
    // 所有动画完成后，调整视图并启动高亮邻居功能
    const totalTime = totalNodeTime + edges.length * edgeDelay + 500;
    setTimeout(() => {
        setupNodeHoverHighlight();
        graphInstance.fit({
            animation: {
                duration: 800,
                easingFunction: "easeInOutQuad"
            }
        });
    }, totalTime);
}

// 节点脉冲动画
function startNodePulse(nodeId, baseSize) {
    if (!graphInstance) return;
    
    let growing = true;
    let currentSize = baseSize;
    const maxSize = baseSize * 1.2;
    const minSize = baseSize * 0.95;
    const step = baseSize * 0.02;
    
    const pulseInterval = setInterval(() => {
        if (!graphInstance) {
            clearInterval(pulseInterval);
            return;
        }
        
        if (growing) {
            currentSize += step;
            if (currentSize >= maxSize) growing = false;
        } else {
            currentSize -= step;
            if (currentSize <= minSize) growing = true;
        }
        
        try {
            graphInstance.body.data.nodes.update({
                id: nodeId,
                size: currentSize
            });
        } catch (e) {
            clearInterval(pulseInterval);
        }
    }, 50);
    
    // 10秒后停止脉冲
    setTimeout(() => clearInterval(pulseInterval), 10000);
}

// 悬停高亮邻居节点
function setupNodeHoverHighlight() {
    if (!graphInstance) return;
    
    let hoveredNodeId = null;
    
    graphInstance.on("hoverNode", function(params) {
        hoveredNodeId = params.node;
        highlightNeighbors(params.node);
    });
    
    graphInstance.on("blurNode", function() {
        hoveredNodeId = null;
        resetHighlight();
    });
}

function highlightNeighbors(nodeId) {
    if (!graphInstance) return;
    
    // 获取所有连接的节点
    const connectedNodes = graphInstance.getConnectedNodes(nodeId);
    const allNodes = graphInstance.body.data.nodes.get();
    const allEdges = graphInstance.body.data.edges.get();
    
    // 更新节点样式
    allNodes.forEach(node => {
        const isConnected = connectedNodes.includes(node.id) || node.id === nodeId;
        graphInstance.body.data.nodes.update({
            id: node.id,
            opacity: isConnected ? 1 : 0.3
        });
    });
    
    // 更新连线样式
    allEdges.forEach(edge => {
        const isConnected = edge.from === nodeId || edge.to === nodeId;
        graphInstance.body.data.edges.update({
            id: edge.id,
            opacity: isConnected ? 1 : 0.15,
            width: isConnected ? 4 : 2
        });
    });
}

function resetHighlight() {
    if (!graphInstance) return;
    
    const allNodes = graphInstance.body.data.nodes.get();
    const allEdges = graphInstance.body.data.edges.get();
    
    allNodes.forEach(node => {
        graphInstance.body.data.nodes.update({
            id: node.id,
            opacity: 1
        });
    });
    
    allEdges.forEach(edge => {
        graphInstance.body.data.edges.update({
            id: edge.id,
            opacity: 0.8,
            width: 2
        });
    });
}

function zoomGraph(delta) {
    if (!graphInstance) return;
    const scale = graphInstance.getScale();
    graphInstance.moveTo({ scale: scale * delta });
}

function resetGraph() {
    graphInstance?.fit({ animation: { duration: 400, easingFunction: "easeInOutQuad" } });
}

// 动态图谱：展开节点功能（暂时不使用，保留以备后用）
async function expandGraphNode(nodeId, nodeLabel) {
    if (!graphInstance || isExpanding) return;
    
    // 检查是否已展开
    if (expandedNodes.has(nodeId)) {
        console.log(`节点 ${nodeLabel} 已展开`);
        return;
    }
    
    const api = getApi();
    if (!api?.expand_node) {
        alert("动态展开功能需要在线模式");
        return;
    }
    
    try {
        isExpanding = true;
        
        // 显示加载状态
        const currentData = graphInstance.body.data;
        const allNodes = currentData.nodes.get();
        const allEdges = currentData.edges.get();
        
        // 获取当前图谱数据
        const currentGraph = {
            nodes: allNodes,
            edges: allEdges
        };
        
        console.log(`正在展开节点: ${nodeLabel}...`);
        
        // 调用后端API
        const result = await api.expand_node(nodeId, nodeLabel, currentGraph);
        
        if (result.error) {
            alert(`展开失败: ${result.error}`);
            return;
        }
        
        const newNodes = result.nodes || [];
        const newEdges = result.edges || [];
        
        if (newNodes.length === 0) {
            console.log("没有新节点生成");
            return;
        }
        
        // 应用当前颜色主题到新节点
        const themeConfig = COLOR_THEMES[currentColorTheme] || COLOR_THEMES.default;
        newNodes.forEach((node, index) => {
            if (themeConfig.colors) {
                const colorIndex = index % themeConfig.colors.length;
                const nodeColor = themeConfig.colors[colorIndex];
                const nodeBorder = adjustBrightness(nodeColor, -30);
                node.color = {
                    background: nodeColor,
                    border: nodeBorder,
                    highlight: {
                        background: nodeColor,
                        border: '#F59E0B'
                    },
                    hover: {
                        background: adjustBrightness(nodeColor, 10),
                        border: '#F59E0B'
                    }
                };
            } else {
                const levelConfig = themeConfig.level2 || { node: "#A5B4FC", border: "#6366F1" };
                node.color = {
                    background: levelConfig.node,
                    border: levelConfig.border,
                    highlight: {
                        background: levelConfig.node,
                        border: '#F59E0B'
                    }
                };
            }
            node.shape = getShapeByGroup(node.group || 3);
            node.size = 20;
            node.borderWidth = 2;
            node.font = { 
                size: 14, 
                color: getBestTextColor(node.color.background), 
                face: "Segoe UI, Microsoft YaHei"
            };
        });
        
        // 添加新节点和边
        currentData.nodes.add(newNodes);
        currentData.edges.add(newEdges);
        
        // 标记节点已展开
        expandedNodes.add(nodeId);
        
        console.log(`✓ 已展开节点 ${nodeLabel}，新增 ${newNodes.length} 个子节点`);
        
        // 稳定后居中显示
        setTimeout(() => {
            graphInstance.fit({
                animation: {
                    duration: 500,
                    easingFunction: "easeInOutQuad"
                }
            });
        }, 300);
        
    } catch (error) {
        console.error("展开节点失败:", error);
        alert(`展开失败: ${error.message || error}`);
    } finally {
        isExpanding = false;
    }
}

const COLOR_THEMES = {
    default: { 
        core: { node: "#4F46E5", border: "#312E81", shape: "star" },
        level1: { node: "#818CF8", border: "#4F46E5" },
        level2: { node: "#A5B4FC", border: "#6366F1" },
        edge: { color: "#CBD5F5", highlight: "#818CF8" }
    },
    rainbow: { 
        core: { node: "#EF4444", border: "#991B1B", shape: "hexagon" },
        colors: ["#F59E0B", "#10B981", "#06B6D4", "#6366F1", "#A855F7", "#EC4899"],
        edge: { color: "#9CA3AF", highlight: "#EC4899", gradient: true, gradientColors: ["#EF4444", "#F59E0B", "#10B981", "#06B6D4", "#6366F1", "#A855F7", "#EC4899"] }
    },
    ocean: { 
        core: { node: "#0284C7", border: "#075985", shape: "diamond" },
        level1: { node: "#0EA5E9", border: "#0284C7" },
        level2: { node: "#38BDF8", border: "#0EA5E9" },
        edge: { color: "#BAE6FD", highlight: "#0EA5E9", gradient: true, gradientColors: ["#0284C7", "#06B6D4", "#38BDF8"] }
    },
    forest: { 
        core: { node: "#047857", border: "#065F46", shape: "star" },
        level1: { node: "#10B981", border: "#047857" },
        level2: { node: "#34D399", border: "#10B981" },
        edge: { color: "#A7F3D0", highlight: "#10B981", gradient: true, gradientColors: ["#047857", "#10B981", "#34D399"] }
    },
    sunset: { 
        core: { node: "#DC2626", border: "#991B1B", shape: "hexagon" },
        level1: { node: "#F59E0B", border: "#DC2626" },
        level2: { node: "#FBBF24", border: "#F59E0B" },
        edge: { color: "#FDE68A", highlight: "#F59E0B", gradient: true, gradientColors: ["#DC2626", "#F59E0B", "#FBBF24"] }
    },
    purple: { 
        core: { node: "#7C3AED", border: "#5B21B6", shape: "diamond" },
        level1: { node: "#A855F7", border: "#7C3AED" },
        level2: { node: "#C084FC", border: "#A855F7" },
        edge: { color: "#E9D5FF", highlight: "#A855F7", gradient: true, gradientColors: ["#7C3AED", "#A855F7", "#C084FC"] }
    },
    tech: { 
        core: { node: "#0891B2", border: "#155E75", shape: "box" },
        level1: { node: "#06B6D4", border: "#0891B2" },
        level2: { node: "#22D3EE", border: "#06B6D4" },
        edge: { color: "#CFFAFE", highlight: "#06B6D4", gradient: true, gradientColors: ["#0891B2", "#06B6D4", "#22D3EE"] }
    },
    warm: { 
        core: { node: "#DC2626", border: "#991B1B", shape: "star" },
        level1: { node: "#EF4444", border: "#DC2626" },
        level2: { node: "#F87171", border: "#EF4444" },
        edge: { color: "#FECACA", highlight: "#EF4444", gradient: true, gradientColors: ["#DC2626", "#EF4444", "#F87171"] }
    },
    cool: { 
        core: { node: "#4338CA", border: "#312E81", shape: "diamond" },
        level1: { node: "#6366F1", border: "#4338CA" },
        level2: { node: "#818CF8", border: "#6366F1" },
        edge: { color: "#C7D2FE", highlight: "#6366F1", gradient: true, gradientColors: ["#4338CA", "#6366F1", "#818CF8"] }
    },
    monochrome: { 
        core: { node: "#374151", border: "#1F2937", shape: "box" },
        level1: { node: "#6B7280", border: "#374151" },
        level2: { node: "#9CA3AF", border: "#6B7280" },
        edge: { color: "#E5E7EB", highlight: "#6B7280" }
    },
    gradient: {
        core: { node: "#8B5CF6", border: "#6D28D9", shape: "star" },
        colors: ["#EC4899", "#8B5CF6", "#3B82F6", "#06B6D4", "#10B981"],
        edge: { color: "#DDD6FE", highlight: "#8B5CF6", gradient: true, gradientColors: ["#EC4899", "#8B5CF6", "#3B82F6", "#06B6D4", "#10B981"] }
    },
    neon: {
        core: { node: "#FF00FF", border: "#9D174D", shape: "hexagon" },
        colors: ["#FF1493", "#00CED1", "#00FF00", "#FFD700", "#FF4500"],
        edge: { color: "#4B5563", highlight: "#FF1493", gradient: true, gradientColors: ["#FF1493", "#00CED1", "#00FF00", "#FFD700", "#FF4500"] }
    },
    candy: {
        core: { node: "#FF6B9D", border: "#C2185B", shape: "star" },
        colors: ["#FFB3E6", "#FF69B4", "#87CEEB", "#FFD700", "#98FB98", "#DDA0DD"],
        edge: { color: "#FFE4F0", highlight: "#FF69B4", gradient: true, gradientColors: ["#FFB3E6", "#FF69B4", "#87CEEB", "#FFD700", "#98FB98", "#DDA0DD"] }
    },
    autumn: {
        core: { node: "#D97706", border: "#92400E", shape: "hexagon" },
        level1: { node: "#F59E0B", border: "#D97706" },
        level2: { node: "#FCD34D", border: "#F59E0B" },
        edge: { color: "#FEF3C7", highlight: "#F59E0B", gradient: true, gradientColors: ["#D97706", "#F59E0B", "#FCD34D"] }
    },
    spring: {
        core: { node: "#EC4899", border: "#BE185D", shape: "diamond" },
        colors: ["#FDE68A", "#FB7185", "#86EFAC", "#A5F3FC", "#FBCFE8", "#DDD6FE"],
        edge: { color: "#FDF2F8", highlight: "#FB7185", gradient: true, gradientColors: ["#FDE68A", "#FB7185", "#86EFAC", "#A5F3FC", "#FBCFE8", "#DDD6FE"] }
    },
    galaxy: {
        core: { node: "#8B5CF6", border: "#6D28D9", shape: "star" },
        colors: ["#7C3AED", "#2563EB", "#06B6D4", "#8B5CF6", "#EC4899", "#F59E0B"],
        edge: { color: "#6B7280", highlight: "#8B5CF6", gradient: true, gradientColors: ["#7C3AED", "#2563EB", "#06B6D4", "#8B5CF6", "#EC4899", "#F59E0B"] }
    },
    vintage: {
        core: { node: "#92400E", border: "#78350F", shape: "box" },
        level1: { node: "#B45309", border: "#92400E" },
        level2: { node: "#D97706", border: "#B45309" },
        edge: { color: "#FDE68A", highlight: "#D97706" }
    },
    emerald: {
        core: { node: "#059669", border: "#047857", shape: "diamond" },
        level1: { node: "#10B981", border: "#059669" },
        level2: { node: "#34D399", border: "#10B981" },
        edge: { color: "#D1FAE5", highlight: "#10B981", gradient: true, gradientColors: ["#059669", "#10B981", "#34D399"] }
    },
    fire: {
        core: { node: "#DC2626", border: "#991B1B", shape: "star" },
        colors: ["#EF4444", "#F97316", "#FBBF24", "#FB923C", "#F59E0B"],
        edge: { color: "#FEE2E2", highlight: "#EF4444", gradient: true, gradientColors: ["#DC2626", "#EF4444", "#F97316", "#FBBF24", "#FB923C", "#F59E0B"] }
    },
    ice: {
        core: { node: "#0891B2", border: "#155E75", shape: "hexagon" },
        colors: ["#06B6D4", "#22D3EE", "#67E8F9", "#A5F3FC", "#BAE6FD"],
        edge: { color: "#F0F9FF", highlight: "#06B6D4", gradient: true, gradientColors: ["#0891B2", "#06B6D4", "#22D3EE", "#67E8F9", "#A5F3FC", "#BAE6FD"] }
    },
    aurora: {
        core: { node: "#10B981", border: "#065F46", shape: "star" },
        colors: ["#34D399", "#6EE7B7", "#A7F3D0", "#818CF8", "#6366F1", "#4F46E5"],
        edge: { color: "#E0E7FF", highlight: "#34D399", gradient: true, gradientColors: ["#10B981", "#34D399", "#6366F1"] }
    },
    cyberpunk: {
        core: { node: "#F472B6", border: "#DB2777", shape: "hexagon" },
        colors: ["#F472B6", "#22D3EE", "#FACC15", "#A855F7", "#FB7185"],
        edge: { color: "#1F2937", highlight: "#F472B6", gradient: true, gradientColors: ["#F472B6", "#22D3EE", "#FACC15"] }
    },
    pastel: {
        core: { node: "#FCA5A5", border: "#F87171", shape: "circle" },
        colors: ["#FCA5A5", "#FDBA74", "#FDE047", "#86EFAC", "#93C5FD", "#C4B5FD", "#F9A8D4"],
        edge: { color: "#F3F4F6", highlight: "#FCA5A5", gradient: true, gradientColors: ["#FCA5A5", "#93C5FD", "#F9A8D4"] }
    }
};

let currentColorTheme = "default";

const GRAPH_BG_THEMES = {
    default: "#FFFFFF",
    dark: "#111827", // Gray-900
    midnight: "#1E1B4B", // Indigo-950
    cream: "#FFFBEB", // Amber-50
    mint: "#ECFDF5", // Emerald-50
    lavender: "#F5F3FF", // Violet-50
    "gradient-blue": "linear-gradient(135deg, #E0E7FF 0%, #EEF2FF 100%)",
    "gradient-purple": "linear-gradient(135deg, #F3E8FF 0%, #F5F3FF 100%)",
    "gradient-dark": "linear-gradient(135deg, #1F2937 0%, #111827 100%)"
};

function changeGraphBg(bgName) {
    const container = document.getElementById("graph-surface");
    if (!container) return;
    
    const bgColor = GRAPH_BG_THEMES[bgName] || GRAPH_BG_THEMES.default;
    // Use 'background' to support both solid colors and gradients
    container.style.background = bgColor;
    
    // 如果背景是深色，可能需要调整连线颜色使其更亮
    if (['dark', 'midnight', 'gradient-dark'].includes(bgName)) {
        if (graphInstance) {
            graphInstance.setOptions({
                edges: { color: { color: '#E0E7FF', opacity: 0.6 } } // 浅色连线
            });
        }
    } else {
        if (graphInstance) {
            graphInstance.setOptions({
                edges: { color: { color: edgeColor, opacity: 0.8 } } // 恢复默认
            });
        }
    }
}

function changeGraphColor(theme) {
    if (!graphInstance) return;
    
    currentColorTheme = theme;
    const themeConfig = COLOR_THEMES[theme] || COLOR_THEMES.default;
    
    const currentData = graphInstance.body.data;
    const nodes = currentData.nodes.get();
    const edges = currentData.edges.get();
    
    // 找出核心节点（通常是第一个节点或group=1）
    const coreNodeIds = nodes.filter(n => n.group === 1 || nodes.indexOf(n) === 0).map(n => n.id);
    
    // 更新节点颜色和形状
    nodes.forEach((node, index) => {
        const isCoreNode = coreNodeIds.includes(node.id);
        
        // 确保每个节点都有 label
        if (!node.label && node.id) {
            node.label = String(node.id);
        }
        
        // 清理可能存在的旧 Markdown 标记，防止重复包裹
        if (node.label && node.label.startsWith('*') && node.label.endsWith('*')) {
             node.label = node.label.substring(1, node.label.length - 1);
        }

        let textColor;
        let shape;
        let size;

        if (isCoreNode) {
            // 核心节点使用特殊样式
            const coreColor = themeConfig.core.node;
            textColor = getBestTextColor(coreColor);
            shape = themeConfig.core.shape || "box";
            size = 45;

            node.color = {
                background: coreColor,
                border: themeConfig.core.border,
                highlight: { background: coreColor, border: '#FBBF24' },
                hover: { background: adjustBrightness(coreColor, 10), border: '#FBBF24' }
            };
            node.shape = shape;
            node.size = size;
            node.borderWidth = 4;
            
            // 核心节点字体样式
            node.font = { 
                size: 28, 
                color: textColor, 
                face: "Segoe UI, Microsoft YaHei",
                multi: 'md'
            };
            
            // 加粗标签
            node.label = `*${node.label}*`;

        } else if (themeConfig.colors) {
            // 彩虹/渐变主题
            const colorIndex = (index - coreNodeIds.length) % themeConfig.colors.length;
            const nodeColor = themeConfig.colors[colorIndex];
            const nodeBorder = adjustBrightness(nodeColor, -30);
            textColor = getBestTextColor(nodeColor);
            shape = getShapeByGroup(node.group || 2);
            size = 25;

            node.color = {
                background: nodeColor,
                border: nodeBorder,
                highlight: { background: nodeColor, border: '#F59E0B' },
                hover: { background: adjustBrightness(nodeColor, 10), border: '#F59E0B' }
            };
            node.shape = shape;
            node.size = size;
            node.borderWidth = 3;
            
            node.font = { 
                size: 16, 
                color: textColor, 
                face: "Segoe UI, Microsoft YaHei"
            };

        } else {
            // 分层主题
            const level = node.group === 2 ? "level1" : "level2";
            const levelConfig = themeConfig[level] || themeConfig.level1;
            const levelColor = levelConfig.node;
            textColor = getBestTextColor(levelColor);
            shape = getShapeByGroup(node.group || 2);
            size = 25;

            node.color = {
                background: levelColor,
                border: levelConfig.border,
                highlight: { background: levelColor, border: '#F59E0B' },
                hover: { background: adjustBrightness(levelColor, 10), border: '#F59E0B' }
            };
            node.shape = shape;
            node.size = size;
            node.borderWidth = 3;
            
            node.font = { 
                size: 16, 
                color: textColor, 
                face: "Segoe UI, Microsoft YaHei"
            };
        }

        // 通用：针对特殊形状调整文字位置 (vadjust)
        const externalLabelShapes = ['diamond', 'triangle', 'star', 'hexagon', 'square'];
        if (externalLabelShapes.includes(node.shape)) {
            // 增大尺寸以容纳文字
            const baseSize = (node.size || size);
            node.size = baseSize * 2.5; 
            
            // 动态计算 vadjust
            // 增加偏移量，确保文字更靠上
            let vadjust = -1.2 * node.size;
            
            if (node.shape === 'triangle') vadjust = -1 * node.size * 0.8; 
            if (node.shape === 'star') vadjust = -1 * node.size * 1.1;
            if (node.shape === 'diamond') vadjust = -1 * node.size * 1.2;
            if (node.shape === 'hexagon') vadjust = -1 * node.size * 1.1;
            
            node.font.vadjust = vadjust;
            node.font.size = 18; // 稍微加大字体
            
            node.shapeProperties = {
                borderDashes: false,
                borderRadius: 6,
                interpolation: false
            };
        }
        
        // 确保 labelHighlightBold 开启
        node.labelHighlightBold = true;
    });
    
    // 更新边颜色
    edges.forEach((edge, edgeIndex) => {
        const edgeConfig = themeConfig.edge;
        
        if (typeof edgeConfig === 'object' && edgeConfig.gradient && edgeConfig.gradientColors) {
            // 渐变模式：为每条边分配不同颜色
            const colorIndex = edgeIndex % edgeConfig.gradientColors.length;
            edge.color = {
                color: edgeConfig.gradientColors[colorIndex],
                highlight: edgeConfig.highlight || edgeConfig.gradientColors[colorIndex],
                opacity: 0.8
            };
            edge.width = 3;
        } else {
            // 普通模式
            const edgeColor = typeof edgeConfig === 'object' ? edgeConfig.color : edgeConfig;
            const highlightColor = typeof edgeConfig === 'object' ? edgeConfig.highlight : themeConfig.core.border;
            edge.color = {
                color: edgeColor,
                highlight: highlightColor,
                opacity: 0.8
            };
        }
    });
    
    graphInstance.setData({ nodes, edges });
}

// 辅助函数：根据背景色计算最佳字体颜色（黑或白）
function getBestTextColor(bgColor) {
    // 移除 # 号
    const hex = bgColor.replace('#', '');
    
    // 转换为 RGB
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    
    // 计算相对亮度 (使用 WCAG 标准)
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    
    // 亮度大于 0.5 使用深色文字，否则使用浅色
    return luminance > 0.5 ? '#1F2937' : '#FFFFFF';
}

// 辅助函数：调整颜色亮度
function adjustBrightness(color, percent) {
    const num = parseInt(color.replace("#",""), 16);
    const amt = Math.round(2.55 * percent);
    const R = (num >> 16) + amt;
    const G = (num >> 8 & 0x00FF) + amt;
    const B = (num & 0x0000FF) + amt;
    return "#" + (0x1000000 + (R<255?R<1?0:R:255)*0x10000 + 
                  (G<255?G<1?0:G:255)*0x100 + 
                  (B<255?B<1?0:B:255)).toString(16).slice(1);
}

// 辅助函数：根据组别返回形状（优先使用能显示文字的形状）
function getShapeByGroup(group) {
    // 所有形状都强制显示文字
    const shapes = [
        "box",          // 方形
        "ellipse",      // 椭圆形
        "circle",       // 圆形
        "hexagon",      // 六边形
        "star",         // 星形
        "triangle",     // 三角形
        "diamond",      // 菱形
        "square",       // 正方形
        "dot"           // 圆点
    ];
    return shapes[(group - 1) % shapes.length] || "box";
}

function changeGraphLayout(style) {
    if (!graphInstance) return;
    
    const currentData = graphInstance.body.data;
    const nodes = currentData.nodes.get();
    const edges = currentData.edges.get();
    
    let newOptions = {};
    
    switch (style) {
        case "hierarchical-ud":
            newOptions = {
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'UD',
                        sortMethod: 'directed',
                        nodeSpacing: 200,
                        levelSeparation: 180,
                    }
                },
                physics: { enabled: false }
            };
            break;
        case "hierarchical-lr":
            newOptions = {
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'LR',
                        sortMethod: 'directed',
                        nodeSpacing: 150,
                        levelSeparation: 250,
                    }
                },
                physics: { enabled: false }
            };
            break;
        case "hierarchical-rl":
            newOptions = {
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'RL',
                        sortMethod: 'directed',
                        nodeSpacing: 150,
                        levelSeparation: 250,
                    }
                },
                physics: { enabled: false }
            };
            break;
        case "tree":
            newOptions = {
                layout: {
                    hierarchical: {
                        enabled: true,
                        direction: 'UD',
                        sortMethod: 'directed',
                        nodeSpacing: 120,
                        levelSeparation: 150,
                        treeSpacing: 200,
                        blockShifting: true,
                        edgeMinimization: true,
                    }
                },
                physics: { enabled: false }
            };
            break;
        case "grid":
            newOptions = {
                layout: { hierarchical: false },
                physics: { enabled: false }
            };
            // 网格布局
            const gridCols = Math.ceil(Math.sqrt(nodes.length));
            const gridSpacing = 200;
            nodes.forEach((node, idx) => {
                const row = Math.floor(idx / gridCols);
                const col = idx % gridCols;
                node.x = (col - gridCols / 2) * gridSpacing;
                node.y = (row - Math.ceil(nodes.length / gridCols) / 2) * gridSpacing;
                node.fixed = { x: true, y: true };
            });
            break;
        case "concentric":
            newOptions = {
                layout: { hierarchical: false },
                physics: { enabled: false }
            };
            // 同心圆布局
            const levels = Math.ceil(nodes.length / 6);
            let nodeIdx = 0;
            for (let level = 0; level < levels; level++) {
                const radius = 100 + level * 120;
                const nodesInLevel = Math.min(6 + level * 4, nodes.length - nodeIdx);
                const angleStep = (2 * Math.PI) / nodesInLevel;
                for (let i = 0; i < nodesInLevel && nodeIdx < nodes.length; i++, nodeIdx++) {
                    nodes[nodeIdx].x = Math.cos(angleStep * i) * radius;
                    nodes[nodeIdx].y = Math.sin(angleStep * i) * radius;
                    nodes[nodeIdx].fixed = { x: true, y: true };
                }
            }
            break;
        case "circular":
            newOptions = {
                layout: {
                    hierarchical: false,
                    improvedLayout: true,
                },
                physics: {
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -26,
                        centralGravity: 0.005,
                        springLength: 230,
                        springConstant: 0.18,
                    },
                    stabilization: { iterations: 150 }
                }
            };
            // 将节点排列成圆形
            const radius = 200;
            const angleStep = (2 * Math.PI) / nodes.length;
            nodes.forEach((node, idx) => {
                node.x = Math.cos(angleStep * idx) * radius;
                node.y = Math.sin(angleStep * idx) * radius;
                node.fixed = { x: true, y: true };
            });
            break;
        case "radial":
            newOptions = {
                layout: { hierarchical: false },
                physics: {
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -50,
                        centralGravity: 0.01,
                        springLength: 200,
                        springConstant: 0.08,
                    },
                    stabilization: { iterations: 200 }
                }
            };
            break;
        case "spiral":
            newOptions = {
                layout: { hierarchical: false },
                physics: { enabled: false }
            };
            // 螺旋布局
            const spiralSpacing = 30;
            const spiralGrowth = 15;
            nodes.forEach((node, idx) => {
                const angle = idx * 0.5;
                const r = spiralSpacing + angle * spiralGrowth;
                node.x = Math.cos(angle) * r;
                node.y = Math.sin(angle) * r;
                node.fixed = { x: true, y: true };
            });
            break;
        case "star":
            newOptions = {
                layout: { hierarchical: false },
                physics: { enabled: false }
            };
            // 星形布局：中心节点 + 外围节点
            if (nodes.length > 0) {
                nodes[0].x = 0;
                nodes[0].y = 0;
                nodes[0].fixed = { x: true, y: true };
                
                const starRadius = 250;
                const starAngleStep = (2 * Math.PI) / (nodes.length - 1);
                for (let i = 1; i < nodes.length; i++) {
                    nodes[i].x = Math.cos(starAngleStep * (i - 1)) * starRadius;
                    nodes[i].y = Math.sin(starAngleStep * (i - 1)) * starRadius;
                    nodes[i].fixed = { x: true, y: true };
                }
            }
            break;
        case "cluster":
            newOptions = {
                layout: { hierarchical: false },
                physics: {
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -100,
                        centralGravity: 0.02,
                        springLength: 180,
                        springConstant: 0.15,
                    },
                    stabilization: { iterations: 250 }
                }
            };
            // 聚类布局：按 group 分组
            const groups = {};
            nodes.forEach(node => {
                const g = node.group || 1;
                if (!groups[g]) groups[g] = [];
                groups[g].push(node);
            });
            
            const groupKeys = Object.keys(groups);
            const clusterAngleStep = (2 * Math.PI) / groupKeys.length;
            const clusterRadius = 200;
            
            groupKeys.forEach((key, gIdx) => {
                const clusterNodes = groups[key];
                const centerX = Math.cos(clusterAngleStep * gIdx) * clusterRadius;
                const centerY = Math.sin(clusterAngleStep * gIdx) * clusterRadius;
                
                clusterNodes.forEach((node, nIdx) => {
                    const localAngle = (2 * Math.PI * nIdx) / clusterNodes.length;
                    const localRadius = 80;
                    node.x = centerX + Math.cos(localAngle) * localRadius;
                    node.y = centerY + Math.sin(localAngle) * localRadius;
                });
            });
            break;
        case "force":
        default:
            newOptions = {
                layout: {
                    hierarchical: false,
                    improvedLayout: true,
                    randomSeed: 42,
                },
                physics: {
                    enabled: true,
                    solver: "barnesHut",
                    stabilization: {
                        enabled: true,
                        iterations: 200,
                        fit: true,
                    },
                    barnesHut: {
                        gravitationalConstant: -8000,
                        centralGravity: 0.3,
                        springLength: 250,
                        springConstant: 0.04,
                        damping: 0.09,
                        avoidOverlap: 1,
                    },
                }
            };
            break;
    }
    
    graphInstance.setOptions(newOptions);
    graphInstance.setData({ nodes, edges });
    
    setTimeout(() => {
        graphInstance.fit({
            animation: {
                duration: 500,
                easingFunction: "easeInOutQuad"
            }
        });
    }, 300);
}

// ============= 3D 图谱功能 =============

const COLOR_3D_THEMES = {
    default: { node: "#4F46E5", edge: "#818CF8", highlight: "#6366F1" },
    rainbow: { 
        colors: ["#FF6B9D", "#FFB84D", "#FFE66D", "#4ECDC4", "#44A8F5", "#A78BFA", "#F472B6"],
        edge: "#666", 
        highlight: "#FFD700" 
    },
    galaxy: { 
        colors: ["#7C3AED", "#2563EB", "#06B6D4", "#8B5CF6", "#EC4899", "#F59E0B"],
        edge: "#4B5563", 
        highlight: "#8B5CF6" 
    },
    neon: { 
        colors: ["#FF1493", "#00CED1", "#00FF00", "#FFD700", "#FF4500"],
        edge: "#333", 
        highlight: "#FF1493" 
    },
    fire: { 
        colors: ["#DC2626", "#EA580C", "#F59E0B", "#FBBF24"],
        edge: "#7C2D12", 
        highlight: "#F59E0B" 
    },
    ocean: { 
        colors: ["#0284C7", "#06B6D4", "#38BDF8", "#7DD3FC"],
        edge: "#164E63", 
        highlight: "#06B6D4" 
    },
    forest: { 
        colors: ["#047857", "#10B981", "#34D399", "#6EE7B7"],
        edge: "#064E3B", 
        highlight: "#10B981" 
    },
    sunset: { 
        colors: ["#DC2626", "#F59E0B", "#FBBF24", "#FDE68A"],
        edge: "#78350F", 
        highlight: "#F59E0B" 
    }
};

function initialise3DGraph(graphData) {
    console.log("Initializing 3D graph...", graphData);
    
    // 检查库是否加载
    if (typeof ForceGraph3D === 'undefined') {
        console.error("3D Force Graph library not loaded. Window.ForceGraph3D:", window.ForceGraph3D);
        alert("加载 3D 图谱库失败，请检查网络连接。");
        return;
    }
    
    const container = document.getElementById("graph3d-surface");
    if (!container) {
        console.error("3D graph container not found");
        return;
    }
    
    console.log("3D graph container found, proceeding with initialization...");
    
    // 清理旧实例
    if (graph3dInstance) {
        container.innerHTML = "";
    }
    
    const nodes = graphData.nodes || [];
    const edges = graphData.edges || [];
    
    if (nodes.length === 0) {
        console.warn("No nodes to display in 3D graph");
        return;
    }
    
    // 转换数据格式，使用丰富的3D形状
    const shapes3D = ['sphere', 'box', 'cone', 'cylinder', 'torus', 'octahedron', 'dodecahedron'];
    const graph3dData = {
        nodes: nodes.map((n, index) => ({
            id: n.id,
            label: n.label || n.id,
            group: n.group || 0,
            val: (n.group === 0 ? 40 : n.group === 1 ? 25 : 15),
            // 使用多种3D形状：球体、立方体、圆锥、圆柱、圆环、八面体、十二面体
            shape: shapes3D[index % shapes3D.length],
            // 节点旋转速度
            rotationSpeed: (n.group === 0 ? 0.01 : 0.005),
            // 节点脉冲
            pulse: n.group === 0
        })),
        links: edges.map(e => ({
            source: e.from || e.source,
            target: e.to || e.target,
            label: e.label || "",
            // 连线粒子数量
            particles: e.label ? 3 : 2
        }))
    };
    
    try {
        console.log("Creating 3D graph instance with", graph3dData.nodes.length, "nodes and", graph3dData.links.length, "links");
        
        // 创建增强版 3D 图谱
        graph3dInstance = ForceGraph3D()
            (container)
            .graphData(graph3dData)
            .nodeLabel('label')
            .nodeColor(node => {
                const theme = COLOR_3D_THEMES.default;
                return theme.node;
            })
            .nodeVal('val')
            .nodeOpacity(0.95)
            .nodeResolution(20)
            // 连线配置 - 增强视觉效果
            .linkColor(() => COLOR_3D_THEMES.default.edge)
            .linkOpacity(0.7)
            .linkWidth(2.5)
            .linkDirectionalArrowLength(8)
            .linkDirectionalArrowRelPos(1)
            .linkDirectionalParticles(node => node.particles || 2)
            .linkDirectionalParticleSpeed(0.006)
            .linkDirectionalParticleWidth(2.5)
            .linkDirectionalParticleColor(() => '#FBBF24')
            // 环境配置
            .backgroundColor("#F5F6FF")
            .showNavInfo(false)
            .enableNodeDrag(true)
            .enableNavigationControls(true)
            // 力导向配置
            .d3Force('charge').strength(-300)
            .d3Force('link').distance(100)
            .warmupTicks(100)
            .cooldownTicks(200);
        
        console.log("3D graph instance created successfully:", graph3dInstance);
        
        // 添加更好的光照系统
        if (typeof THREE !== 'undefined' && graph3dInstance.scene) {
            const scene = graph3dInstance.scene();
            
            // 环境光 - 提供基础照明
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene.add(ambientLight);
            
            // 主光源 - 模拟太阳光
            const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
            mainLight.position.set(100, 200, 100);
            mainLight.castShadow = true;
            scene.add(mainLight);
            
            // 补光 - 填充阴影区域
            const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
            fillLight.position.set(-100, -50, -100);
            scene.add(fillLight);
            
            // 背景光 - 轮廓光
            const backLight = new THREE.DirectionalLight(0x6366F1, 0.4);
            backLight.position.set(0, 50, -200);
            scene.add(backLight);
        }
        
        // 自定义节点3D形状和材质
        if (typeof THREE !== 'undefined') {
            graph3dInstance.nodeThreeObject(node => {
                const group = new THREE.Group();
                
                // 支持多种3D形状：球体、立方体、圆锥、圆柱、圆环、八面体、十二面体
                let geometry;
                const size = Math.cbrt(node.val) * 2;
                const radius = size / 2;
                
                switch (node.shape) {
                    case 'box':
                        // 立方体
                        geometry = new THREE.BoxGeometry(size * 0.9, size * 0.9, size * 0.9);
                        break;
                    case 'cone':
                        // 圆锥体
                        geometry = new THREE.ConeGeometry(radius, size * 1.2, 32);
                        break;
                    case 'cylinder':
                        // 圆柱体
                        geometry = new THREE.CylinderGeometry(radius * 0.7, radius * 0.7, size * 1.1, 32);
                        break;
                    case 'torus':
                        // 圆环体
                        geometry = new THREE.TorusGeometry(radius * 0.8, radius * 0.3, 16, 32);
                        break;
                    case 'octahedron':
                        // 八面体
                        geometry = new THREE.OctahedronGeometry(radius * 0.9);
                        break;
                    case 'dodecahedron':
                        // 十二面体
                        geometry = new THREE.DodecahedronGeometry(radius * 0.8);
                        break;
                    default:
                        // 球体（默认）
                        geometry = new THREE.SphereGeometry(radius, 32, 32);
                }
                
                // 创建高质量光照材质 - 增强光影效果
                const material = new THREE.MeshStandardMaterial({
                    color: COLOR_3D_THEMES.default.node,
                    emissive: COLOR_3D_THEMES.default.node,
                    emissiveIntensity: 0.2,
                    metalness: 0.3,
                    roughness: 0.4,
                    // 环境光遮蔽
                    aoMapIntensity: 1.0
                });
                
                const mesh = new THREE.Mesh(geometry, material);
                
                // 添加脉冲动画（重要节点）
                if (node.pulse) {
                    mesh.userData.pulsePhase = Math.random() * Math.PI * 2;
                }
                
                // 添加旋转动画
                if (node.rotationSpeed) {
                    mesh.userData.rotationSpeed = node.rotationSpeed;
                }
                
                group.add(mesh);
                
                // 添加文字标签
                if (typeof SpriteText !== 'undefined') {
                    const sprite = new SpriteText(node.label);
                    sprite.color = '#1F2937';
                    sprite.textHeight = 8;
                    sprite.position.y = size * 0.8;
                    group.add(sprite);
                }
                
                return group;
            });
            
            // 启动节点动画循环
            animate3DNodes();
        }
    } catch (error) {
        console.error("Failed to initialize 3D graph:", error);
    }
    
    // 启动自动旋转和相机动画
    let angle = 0;
    let cameraDistance = 400;
    let cameraHeight = 100;
    const autoRotateCheckbox = document.getElementById("graph3d-auto-rotate");
    const shouldRotate = () => autoRotateCheckbox && autoRotateCheckbox.checked;
    
    function animate() {
        if (shouldRotate() && graph3dInstance) {
            angle += 0.004;
            // 添加垂直波动效果
            cameraHeight = 100 + Math.sin(angle * 2) * 50;
            graph3dInstance.cameraPosition({
                x: cameraDistance * Math.sin(angle),
                y: cameraHeight,
                z: cameraDistance * Math.cos(angle)
            });
        }
        requestAnimationFrame(animate);
    }
    animate();
    
    // 初始相机位置 - 更流畅的进入动画
    setTimeout(() => {
        if (graph3dInstance) {
            graph3dInstance.cameraPosition(
                { x: 0, y: 150, z: 400 },
                { x: 0, y: 0, z: 0 },
                1500
            );
        }
    }, 100);
}

// 3D节点动画循环
function animate3DNodes() {
    if (!graph3dInstance || typeof THREE === 'undefined') return;
    
    function updateNodes() {
        if (!graph3dInstance) return;
        
        const scene = graph3dInstance.scene();
        if (!scene) return;
        
        scene.children.forEach(obj => {
            if (obj.children && obj.children.length > 0) {
                const mesh = obj.children[0];
                
                // 旋转动画
                if (mesh.userData && mesh.userData.rotationSpeed) {
                    mesh.rotation.y += mesh.userData.rotationSpeed;
                    mesh.rotation.x += mesh.userData.rotationSpeed * 0.5;
                }
                
                // 脉冲动画
                if (mesh.userData && mesh.userData.pulsePhase !== undefined) {
                    mesh.userData.pulsePhase += 0.05;
                    const scale = 1 + Math.sin(mesh.userData.pulsePhase) * 0.15;
                    mesh.scale.set(scale, scale, scale);
                    
                    // 发光强度脉冲
                    if (mesh.material && mesh.material.emissiveIntensity !== undefined) {
                        mesh.material.emissiveIntensity = 0.2 + Math.sin(mesh.userData.pulsePhase) * 0.2;
                    }
                }
            }
        });
        
        requestAnimationFrame(updateNodes);
    }
    
    updateNodes();
}

function change3DGraphColor(theme) {
    console.log("Changing 3D graph color to:", theme, "Instance exists:", !!graph3dInstance);
    if (!graph3dInstance) {
        console.warn("3D graph instance not found, cannot change color");
        return;
    }
    
    const colorTheme = COLOR_3D_THEMES[theme] || COLOR_3D_THEMES.default;
    console.log("Using color theme:", colorTheme);
    
    if (colorTheme.colors) {
        // 多色主题
        graph3dInstance.nodeColor(node => {
            const index = node.group % colorTheme.colors.length;
            return colorTheme.colors[index];
        });
    } else {
        // 单色主题
        graph3dInstance.nodeColor(() => colorTheme.node);
    }
    
    graph3dInstance.linkColor(() => colorTheme.edge);
}

function toggle3DAutoRotate(enabled) {
    // 自动旋转由 animate 函数中的检查控制
}

function toggle3DLabels(enabled) {
    console.log("Toggling 3D labels:", enabled, "Instance exists:", !!graph3dInstance);
    if (!graph3dInstance) return;
    
    if (enabled && typeof SpriteText !== 'undefined') {
        graph3dInstance.nodeThreeObject(node => {
            const sprite = new SpriteText(node.label);
            sprite.color = '#1F2937';
            sprite.textHeight = 8;
            return sprite;
        });
    } else {
        graph3dInstance.nodeThreeObject(() => null);
    }
}

function reset3DView() {
    if (!graph3dInstance) return;
    
    graph3dInstance.cameraPosition(
        { x: 0, y: 0, z: 300 },
        { x: 0, y: 0, z: 0 },
        1000
    );
}

function export3DGraph() {
    if (!graph3dInstance) {
        alert("请先生成 3D 知识图谱");
        return;
    }
    
    // 获取 canvas 截图
    const renderer = graph3dInstance.renderer();
    const canvas = renderer.domElement;
    
    canvas.toBlob((blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.download = `3D知识图谱_${Date.now()}.png`;
        link.href = url;
        link.click();
        URL.revokeObjectURL(url);
    });
}

// ============= 2D 图谱功能 =============

function exportGraph(format) {
    if (!graphInstance) {
        alert("请先生成知识图谱");
        return;
    }
    
    const canvas = graphInstance.canvas.frame.canvas;
    const context = canvas.getContext('2d');
    
    if (format === "png") {
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.download = `知识图谱_${Date.now()}.png`;
            link.href = url;
            link.click();
            URL.revokeObjectURL(url);
        });
    } else if (format === "svg") {
        // SVG 导出需要通过后端实现
        const api = getApi();
        if (api && api.export_graph_svg) {
            const data = graphInstance.body.data;
            api.export_graph_svg({
                nodes: data.nodes.get(),
                edges: data.edges.get()
            }).then(result => {
                if (result?.path) {
                    alert(`SVG 已保存到: ${result.path}`);
                }
            });
        } else {
            alert("SVG 导出功能需要在桌面应用中使用");
        }
    }
}

function saveAnimationFile(markup, topic) {
    const api = getApi();
    const name = `可视化_${topic || "未命名"}.html`;
    if (!api || !api.export_animation) {
        const blob = new Blob([markup], { type: "text/html;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        triggerDownload(url, name, "text/html");
        setTimeout(() => URL.revokeObjectURL(url), 0);
        return;
    }
    api.export_animation(markup, name).then((info) => {
        if (info?.path) {
            alert(`动画已保存到: ${info.path}`);
        }
    });
}

function triggerDownload(url, filename, type) {
    const link = document.createElement("a");
    link.href = url;
    if (type) link.type = type;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function applyCredentialsToUi() {
    const systemPrompt = document.getElementById("setting-system-prompt");
    
    // 统一的API配置字段
    const apiKey = document.getElementById("setting-api-key");
    const apiBase = document.getElementById("setting-api-base");
    const apiModel = document.getElementById("setting-api-model");
    
    // Xiaoai TTS
    const xiaoaiTtsKey = document.getElementById("setting-xiaoai-tts-key");
    const xiaoaiTtsBase = document.getElementById("setting-xiaoai-tts-base");
    
    // Aliyun TTS
    const aliyunTtsKey = document.getElementById("setting-aliyun-tts-key");
    
    // Load API values
    if (credentialState["openai-compatible"]) {
        if (apiKey) apiKey.value = credentialState["openai-compatible"].api_key ?? "";
        if (apiBase) apiBase.value = credentialState["openai-compatible"].base_url ?? "https://api.openai.com/v1";
        if (apiModel) apiModel.value = credentialState["openai-compatible"].model ?? "gpt-4o-mini";
    }
    
    // Load TTS values
    if (xiaoaiTtsKey && credentialState.xiaoai_tts) {
        xiaoaiTtsKey.value = credentialState.xiaoai_tts.api_key ?? "";
    }
    if (xiaoaiTtsBase && credentialState.xiaoai_tts) {
        xiaoaiTtsBase.value = credentialState.xiaoai_tts.base_url ?? "https://api.302.ai/v1";
    }
    if (aliyunTtsKey && credentialState.aliyun_tts) {
        aliyunTtsKey.value = credentialState.aliyun_tts.api_key ?? "";
    }
    
    if (systemPrompt) systemPrompt.value = credentialState.system_prompt ?? "";
}

function collectCredentialsFromUi() {
    const systemPrompt = document.getElementById("setting-system-prompt");
    
    // 获取统一的API配置
    const apiKey = document.getElementById("setting-api-key");
    const apiBase = document.getElementById("setting-api-base");
    const apiModel = document.getElementById("setting-api-model");
    
    const compatibleConfig = {
        api_key: apiKey ? apiKey.value : "",
        base_url: apiBase ? apiBase.value : "https://api.openai.com/v1",
        model: apiModel ? apiModel.value : "gpt-4o-mini",
    };
    
    // Xiaoai TTS
    const xiaoaiTtsKey = document.getElementById("setting-xiaoai-tts-key");
    const xiaoaiTtsBase = document.getElementById("setting-xiaoai-tts-base");
    
    // Aliyun TTS
    const aliyunTtsKey = document.getElementById("setting-aliyun-tts-key");
    
    return {
        provider: "openai-compatible",  // 统一使用OpenAI兼容模式
        system_prompt: systemPrompt ? systemPrompt.value : credentialState.system_prompt,
        model: compatibleConfig.model,
        
        "openai-compatible": compatibleConfig,
        
        // TTS Credentials
        xiaoai_tts: {
            api_key: xiaoaiTtsKey ? xiaoaiTtsKey.value : (credentialState.xiaoai_tts?.api_key || ""),
            base_url: xiaoaiTtsBase ? xiaoaiTtsBase.value : (credentialState.xiaoai_tts?.base_url || "https://api.302.ai/v1"),
        },
        aliyun_tts: {
            api_key: aliyunTtsKey ? aliyunTtsKey.value : (credentialState.aliyun_tts?.api_key || ""),
        },
        
        // Preserve other states
        google: credentialState.google,
        openai: credentialState.openai,
        deepseek: credentialState.deepseek,
        claude: credentialState.claude,
        custom: credentialState.custom
    };
}

function populateVoiceOptions(selectedVoice) {
    const voiceSelect = document.getElementById("setting-voice");
    if (!voiceSelect) return;
    const previous = voiceSelect.value || selectedVoice || "";
    voiceSelect.innerHTML = "";
    const autoOption = document.createElement("option");
    autoOption.value = "";
    autoOption.textContent = "自动选择";
    voiceSelect.appendChild(autoOption);
    availableVoices.forEach((voice) => {
        const option = document.createElement("option");
        option.value = voice.id || "";
        const details = voice.languages ? ` (${voice.languages})` : "";
        option.textContent = `${voice.name || voice.id}${details}`;
        voiceSelect.appendChild(option);
    });
    voiceSelect.value = previous;
}

function applyVoiceSelection() {
    const providerSelect = document.getElementById("setting-voice-provider");
    const voiceSelect = document.getElementById("setting-voice");
    if (providerSelect) {
        providerSelect.value = currentSettings.voice_provider || "pyttsx3";
    }
    populateVoiceOptions(currentSettings.voice || "");
    if (voiceSelect) {
        voiceSelect.value = currentSettings.voice || "";
        const providerValue = providerSelect ? providerSelect.value : "pyttsx3";
        voiceSelect.disabled = providerValue !== "pyttsx3";
    }
}

function applySettingsToUi() {
    const resolution = document.getElementById("setting-resolution");
    const duration = document.getElementById("setting-duration");
    const fpsInput = document.getElementById("setting-fps");
    const audio = document.getElementById("setting-audio");
    const ttsEngine = document.getElementById("setting-tts-engine");
    
    if (resolution) resolution.value = currentSettings.video_resolution;
    if (duration) duration.value = currentSettings.slide_duration;
    if (fpsInput) fpsInput.value = currentSettings.fps;
    if (audio) audio.checked = Boolean(currentSettings.include_audio);
    if (ttsEngine) {
        ttsEngine.value = currentSettings.tts_engine || "edge_tts";
        updateTtsEngineDisplay(currentSettings.tts_engine || "edge_tts");
    }
    
    // 应用TTS配置参数
    const edgeVoice = document.getElementById("edge-voice");
    const edgeRate = document.getElementById("edge-rate");
    const edgeVolume = document.getElementById("edge-volume");
    const edgePitch = document.getElementById("edge-pitch");
    
    const xiaoaiVoice = document.getElementById("setting-xiaoai-voice");
    const xiaoaiModel = document.getElementById("setting-xiaoai-tts-model");
    const xiaoaiSpeed = document.getElementById("setting-xiaoai-speed");
    
    const aliyunVoice = document.getElementById("setting-aliyun-voice");
    const aliyunModel = document.getElementById("setting-aliyun-model");
    const aliyunRate = document.getElementById("setting-aliyun-rate");
    const aliyunVolume = document.getElementById("setting-aliyun-volume");
    
    const pyttsx3Rate = document.getElementById("pyttsx3-rate");
    const pyttsx3Volume = document.getElementById("pyttsx3-volume");
    
    if (edgeVoice) edgeVoice.value = currentSettings.edge_voice || "zh-CN-XiaoxiaoNeural";
    if (edgeRate) edgeRate.value = currentSettings.edge_rate || "+0%";
    if (edgeVolume) {
        edgeVolume.value = currentSettings.edge_volume || 100;
        const volumeValue = document.getElementById("edge-volume-value");
        if (volumeValue) volumeValue.textContent = `${edgeVolume.value}%`;
    }
    if (edgePitch) edgePitch.value = currentSettings.edge_pitch || "+0%";
    
    // Xiaoai TTS
    if (xiaoaiVoice) xiaoaiVoice.value = currentSettings.xiaoai_voice || "alloy";
    if (xiaoaiModel) xiaoaiModel.value = currentSettings.xiaoai_model || "tts-1";
    if (xiaoaiSpeed) {
        xiaoaiSpeed.value = currentSettings.xiaoai_speed || 1.0;
        const speedValue = document.getElementById("xiaoai-speed-value");
        if (speedValue) speedValue.textContent = `${xiaoaiSpeed.value}x`;
    }

    // Aliyun TTS
    const aliyunBase = document.getElementById("setting-aliyun-base");
    if (aliyunBase) aliyunBase.value = currentSettings.aliyun_base_url || "https://dashscope.aliyuncs.com/api/v1";
    if (aliyunModel) {
        aliyunModel.value = currentSettings.aliyun_model || "qwen3-tts-flash";
        // updateAliyunVoices(); // No longer needed as model is input
    }
    if (aliyunVoice) {
        aliyunVoice.value = currentSettings.aliyun_voice || "Cherry";
    }
    if (aliyunRate) {
        aliyunRate.value = currentSettings.aliyun_rate || 1.0;
        const rateValue = document.getElementById("aliyun-rate-value");
        if (rateValue) rateValue.textContent = `${aliyunRate.value}x`;
    }
    if (aliyunVolume) {
        aliyunVolume.value = currentSettings.aliyun_volume || 50;
        const volumeValue = document.getElementById("aliyun-volume-value");
        if (volumeValue) volumeValue.textContent = `${aliyunVolume.value}`;
    }

    if (pyttsx3Rate) {
        pyttsx3Rate.value = currentSettings.pyttsx3_rate || 200;
        const rateValue = document.getElementById("pyttsx3-rate-value");
        if (rateValue) rateValue.textContent = `${pyttsx3Rate.value} 词/分钟`;
    }
    if (pyttsx3Volume) {
        pyttsx3Volume.value = currentSettings.pyttsx3_volume || 100;
        const volumeValue = document.getElementById("pyttsx3-volume-value");
        if (volumeValue) volumeValue.textContent = `${pyttsx3Volume.value}%`;
    }
    
    applyVoiceSelection();
}

function collectSettingsFromUi() {
    const resolution = document.getElementById("setting-resolution");
    const duration = document.getElementById("setting-duration");
    const fpsInput = document.getElementById("setting-fps");
    const audio = document.getElementById("setting-audio");
    const ttsEngine = document.getElementById("setting-tts-engine");
    
    // 收集所有TTS配置参数
    const edgeVoice = document.getElementById("edge-voice");
    const edgeRate = document.getElementById("edge-rate");
    const edgeVolume = document.getElementById("edge-volume");
    const edgePitch = document.getElementById("edge-pitch");
    
    const xiaoaiVoice = document.getElementById("setting-xiaoai-voice");
    const xiaoaiModel = document.getElementById("setting-xiaoai-tts-model");
    const xiaoaiSpeed = document.getElementById("setting-xiaoai-speed");
    
    const aliyunVoice = document.getElementById("setting-aliyun-voice");
    const aliyunModel = document.getElementById("setting-aliyun-model");
    const aliyunBase = document.getElementById("setting-aliyun-base");
    const aliyunRate = document.getElementById("setting-aliyun-rate");
    const aliyunVolume = document.getElementById("setting-aliyun-volume");
    
    const pyttsx3Rate = document.getElementById("pyttsx3-rate");
    const pyttsx3Volume = document.getElementById("pyttsx3-volume");
    
    return {
        video_resolution: resolution ? resolution.value : currentSettings.video_resolution,
        slide_duration: duration ? Number(duration.value) || currentSettings.slide_duration : currentSettings.slide_duration,
        fps: fpsInput ? Number(fpsInput.value) || currentSettings.fps : currentSettings.fps,
        include_audio: audio ? audio.checked : currentSettings.include_audio,
        tts_engine: ttsEngine ? ttsEngine.value : (currentSettings.tts_engine || "edge_tts"),
        // Edge TTS
        edge_voice: edgeVoice ? edgeVoice.value : (currentSettings.edge_voice || "zh-CN-XiaoxiaoNeural"),
        edge_rate: edgeRate ? edgeRate.value : (currentSettings.edge_rate || "+0%"),
        edge_volume: edgeVolume ? parseInt(edgeVolume.value) : (currentSettings.edge_volume || 100),
        edge_pitch: edgePitch ? edgePitch.value : (currentSettings.edge_pitch || "+0%"),
        // Xiaoai TTS
        xiaoai_voice: xiaoaiVoice ? xiaoaiVoice.value : (currentSettings.xiaoai_voice || "alloy"),
        xiaoai_model: xiaoaiModel ? xiaoaiModel.value : (currentSettings.xiaoai_model || "tts-1"),
        xiaoai_speed: xiaoaiSpeed ? parseFloat(xiaoaiSpeed.value) : (currentSettings.xiaoai_speed || 1.0),
        // Aliyun TTS
        aliyun_voice: aliyunVoice ? aliyunVoice.value : (currentSettings.aliyun_voice || "Cherry"),
        aliyun_model: aliyunModel ? aliyunModel.value : (currentSettings.aliyun_model || "qwen3-tts-flash"),
        aliyun_base_url: aliyunBase ? aliyunBase.value : (currentSettings.aliyun_base_url || "https://dashscope.aliyuncs.com/api/v1"),
        aliyun_rate: aliyunRate ? parseFloat(aliyunRate.value) : (currentSettings.aliyun_rate || 1.0),
        aliyun_volume: aliyunVolume ? parseInt(aliyunVolume.value) : (currentSettings.aliyun_volume || 50),
        // pyttsx3
        pyttsx3_rate: pyttsx3Rate ? parseInt(pyttsx3Rate.value) : (currentSettings.pyttsx3_rate || 200),
        pyttsx3_volume: pyttsx3Volume ? parseInt(pyttsx3Volume.value) : (currentSettings.pyttsx3_volume || 100),
    };
}

async function openSettingsModal() {
    const modal = document.getElementById("settings-modal");
    if (!modal) return;
    
    // 每次打开时重新加载最新的配置（内部会自动应用到UI）
    await loadSettings();
    await loadCredentials();
    
    // 加载并显示默认API配置
    const defaultApiConfig = await loadDefaultApiConfig();
    if (defaultApiConfig && defaultApiConfig.provider) {
        console.log(`✓ 默认API: ${defaultApiConfig.provider} (Model: ${defaultApiConfig.api_model || 'default'})`);
        // 高亮显示当前默认的API provider
        const apiTabButtons = document.querySelectorAll('.modal-tabs button[data-tab]');
        apiTabButtons.forEach(btn => {
            const tabName = btn.getAttribute('data-tab');
            if (tabName === defaultApiConfig.provider) {
                btn.setAttribute('data-is-default', 'true');
                btn.title = '✓ 这是当前默认API';
            } else {
                btn.removeAttribute('data-is-default');
            }
        });
    }
    
    // 加载并显示默认TTS配置
    const defaultTtsConfig = await loadDefaultTtsConfig();
    if (defaultTtsConfig && defaultTtsConfig.tts_engine) {
        console.log(`✓ 默认TTS: ${defaultTtsConfig.tts_engine} (Voice: ${defaultTtsConfig.edge_voice || 'default'})`);
    }
    
    await loadVoices();
    
    setSettingsTab(settingsCurrentTab || "video");
    
    modal.classList.remove("is-hidden");
    modal.setAttribute("aria-hidden", "false");
}

function closeSettingsModal() {
    const modal = document.getElementById("settings-modal");
    if (!modal) return;
    modal.classList.add("is-hidden");
    modal.setAttribute("aria-hidden", "true");
}

function setSettingsTab(tabId = "video") {
    const tabButtons = document.querySelectorAll(".modal-tabs button");
    const panes = document.querySelectorAll(".settings-pane");
    if (!tabButtons.length || !panes.length) {
        return;
    }
    const paneIds = Array.from(panes).map((pane) => pane.dataset.pane);
    const targetId = paneIds.includes(tabId) ? tabId : paneIds[0];
    settingsCurrentTab = targetId;
    tabButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.tab === targetId);
    });
    panes.forEach((pane) => {
        pane.classList.toggle("active", pane.dataset.pane === targetId);
    });
}

async function saveSettings() {
    const api = getApi();
    const settingsPayload = collectSettingsFromUi();
    const credentialsPayload = collectCredentialsFromUi();
    currentSettings = { ...currentSettings, ...settingsPayload };
    credentialState = {
        ...credentialState,
        provider: credentialsPayload.provider,
        system_prompt: credentialsPayload.system_prompt,
        model: credentialsPayload.model,
        openai: { ...(credentialState.openai || {}), ...(credentialsPayload.openai || {}) },
        deepseek: { ...(credentialState.deepseek || {}), ...(credentialsPayload.deepseek || {}) },
        claude: { ...(credentialState.claude || {}), ...(credentialsPayload.claude || {}) },
        google: { ...(credentialState.google || {}), ...(credentialsPayload.google || {}) },
        "openai-compatible": { ...(credentialState["openai-compatible"] || {}), ...(credentialsPayload["openai-compatible"] || {}) },
        custom: { ...(credentialState.custom || {}), ...(credentialsPayload.custom || {}) },
    };
    let hasError = false;
    try {
        if (api?.update_settings) {
            const updatedSettings = await api.update_settings(settingsPayload);
            if (updatedSettings) {
                currentSettings = { ...currentSettings, ...updatedSettings };
            }
        }
        if (api?.update_credentials) {
            const updatedCreds = await api.update_credentials(credentialsPayload);
            if (updatedCreds) {
                credentialState = {
                    provider: updatedCreds.provider || "openai",
                    model: updatedCreds.model || "",
                    system_prompt: updatedCreds.system_prompt || "",
                    openai: { ...(updatedCreds.openai || {}) },
                    deepseek: { ...(updatedCreds.deepseek || {}) },
                    claude: { ...(updatedCreds.claude || {}) },
                    google: { ...(updatedCreds.google || {}) },
                    "openai-compatible": { ...(updatedCreds["openai-compatible"] || {}) },
                    custom: { ...(updatedCreds.custom || {}) },
                    xiaoai_tts: { ...(updatedCreds.xiaoai_tts || {}) },
                    aliyun_tts: { ...(updatedCreds.aliyun_tts || {}) },
                };
            }
        }
    } catch (err) {
        console.warn("更新设置失败", err);
        hasError = true;
        alert(`保存设置失败：${err.message || err}`);
    }
    if (!hasError) {
        await loadCredentials();
        await loadVoices();
        applyCredentialsToUi();
        applySettingsToUi();
        closeSettingsModal();
    }
}

async function loadSettings() {
    const api = getApi();
    if (!api?.get_settings) return;
    try {
        const settings = await api.get_settings();
        if (settings) {
            currentSettings = { ...currentSettings, ...settings };
            applySettingsToUi();
        }
    } catch (err) {
        console.warn("加载设置失败", err);
    }
}

async function loadCredentials() {
    const api = getApi();
    if (!api?.get_credentials) return;
    try {
        const result = await api.get_credentials();
        if (result) {
            credentialState = {
                provider: result.provider || "openai",
                model: result.model || "",
                system_prompt: result.system_prompt || "",
                openai: { ...(result.openai || {}) },
                deepseek: { ...(result.deepseek || {}) },
                claude: { ...(result.claude || {}) },
                google: { ...(result.google || {}) },
                "openai-compatible": { ...(result["openai-compatible"] || {}) },
                custom: { ...(result.custom || {}) },
                xiaoai_tts: { ...(result.xiaoai_tts || {}) },
                aliyun_tts: { ...(result.aliyun_tts || {}) },
            };
            applyCredentialsToUi();
            
            // 如果已有配置，显示提示信息
            const hasConfig = (result.openai?.api_key || result.google?.api_key || result["openai-compatible"]?.api_key);
            if (hasConfig) {
                console.log("✓ 已加载保存的API配置");
            }

            // 检查连接状态
            if (result.status === "offline" && result.error) {
                console.error("API Connection Error:", result.error);
                showError(`API 连接失败: ${result.error}`);
                // 如果是在设置模态框打开的情况下，也可以在模态框内显示提示
                const apiTab = document.querySelector('.modal-tabs button[data-tab="api"]');
                if (apiTab) apiTab.classList.add("error-indicator");
            } else {
                hideError();
                const apiTab = document.querySelector('.modal-tabs button[data-tab="api"]');
                if (apiTab) apiTab.classList.remove("error-indicator");
            }
        }
    } catch (err) {
        console.warn("加载凭据失败", err);
    }
}

async function loadDefaultApiConfig() {
    const api = getApi();
    if (!api?.get_default_api_config) return null;
    try {
        const defaultConfig = await api.get_default_api_config();
        return defaultConfig;
    } catch (err) {
        console.warn("加载默认API配置失败", err);
        return null;
    }
}

async function loadDefaultTtsConfig() {
    const api = getApi();
    if (!api?.get_default_tts_config) return null;
    try {
        const defaultConfig = await api.get_default_tts_config();
        return defaultConfig;
    } catch (err) {
        console.warn("加载默认TTS配置失败", err);
        return null;
    }
}

async function loadVoices() {
    const api = getApi();
    if (!api?.list_voices) return;
    try {
        const result = await api.list_voices();
        if (result?.error) {
            console.warn("语音引擎不可用", result.error);
        }
        if (result && Array.isArray(result.voices)) {
            availableVoices = result.voices;
            if (result.provider) {
                currentSettings.voice_provider = result.provider;
            }
            if (typeof result.selected !== "undefined") {
                currentSettings.voice = result.selected || null;
            }
        }
    } catch (err) {
        console.warn("加载语音列表失败", err);
    }
    applyVoiceSelection();
}

function setVideoExportState(state) {
    isVideoExporting = state;
    const button = document.getElementById("export-video-btn");
    if (button) button.disabled = state;
}

async function exportVideo() {
    const api = getApi();
    if (!api?.export_video) {
        alert("当前环境不支持视频导出。请在桌面应用内使用该功能。");
        return;
    }
    if (!currentBundle || !currentBundle.storyboard) {
        alert("请先生成动画内容，再尝试导出视频。");
        return;
    }
    setVideoExportState(true);
    try {
        const payload = {
            topic: currentBundle.topic || document.getElementById("topic-input")?.value?.trim() || "未命名主题",
            storyboard: currentBundle.storyboard,
            narration: currentBundle.narration,
            settings: currentSettings,
        };
        const result = await api.export_video(payload);
        if (result?.error) {
            throw new Error(result.error);
        }
        if (result?.path) {
            alert(`视频已保存到: ${result.path}`);
        }
    } catch (err) {
        showError(`导出失败：${err.message || err}`);
    } finally {
        setVideoExportState(false);
    }
}

function switchTab(id) {
    document.querySelectorAll(".tabs button").forEach((btn) => btn.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((pane) => (pane.style.display = "none"));

    const trigger = document.querySelector(`.tabs button[data-tab="${id}"]`);
    const pane = document.getElementById(`${id}-pane`);
    if (trigger) trigger.classList.add("active");
    if (pane) pane.style.display = "block";
    
    // 切换到 3D 图谱时刷新视图
    if (id === "graph3d" && graph3dInstance) {
        setTimeout(() => {
            graph3dInstance.refresh();
        }, 100);
    }
    
    // 切换到 2D 图谱时适应视图并重新绘制
    if (id === "graph" && graphInstance) {
        setTimeout(() => {
            graphInstance.fit();
            graphInstance.redraw();
        }, 100);
    }
}

function setLoading(state) {
    const loader = document.getElementById("loader");
    const button = document.getElementById("generate-btn");
    if (!loader || !button) return;
    loader.hidden = !state;
    button.disabled = state;
}

function showError(message) {
    const panel = document.getElementById("error-box");
    if (!panel) return;
    panel.textContent = message;
    panel.hidden = false;
}

function hideError() {
    const panel = document.getElementById("error-box");
    if (!panel) return;
    panel.hidden = true;
}

function initUi() {
    console.log("Initializing UI...");
    const topicInput = document.getElementById("topic-input");
    const generateBtn = document.getElementById("generate-btn");
    const exportBtn = document.getElementById("export-btn");
    const settingsBtn = document.getElementById("settings-btn");
    const settingsClose = document.getElementById("settings-close");
    const settingsSave = document.getElementById("settings-save");
    const exportVideoBtn = document.getElementById("export-video-btn");
    const settingsModal = document.getElementById("settings-modal");
    const modalTabButtons = document.querySelectorAll(".modal-tabs button");
    const voiceProviderSelect = document.getElementById("setting-voice-provider");
    const voiceSelect = document.getElementById("setting-voice");
    const systemPromptInput = document.getElementById("setting-system-prompt");
    const ttsEngineSelect = document.getElementById("setting-tts-engine");
    const edgeVoiceLabel = document.getElementById("edge-voice-label");
    
    // 监听TTS引擎选择，显示/隐藏Edge TTS语音选项
    if (ttsEngineSelect && edgeVoiceLabel) {
        ttsEngineSelect.addEventListener("change", () => {
            const isEdgeTTS = ttsEngineSelect.value === "edge_tts";
            edgeVoiceLabel.style.display = isEdgeTTS ? "block" : "none";
        });
    }

    console.log("Generate button:", generateBtn);
    console.log("Settings button:", settingsBtn);
    console.log("Export button:", exportBtn);
    console.log("Export video button:", exportVideoBtn);

    if (!generateBtn) {
        console.error("Generate button not found!");
        return;
    }
    if (!settingsBtn) {
        console.error("Settings button not found!");
        return;
    }

    generateBtn.addEventListener("click", () => {
        console.log("Generate button clicked!");
        const topic = topicInput.value.trim();
        console.log("Topic:", topic);
        runGeneration(topic);
    });
    topicInput.addEventListener("keypress", (event) => {
        if (event.key === "Enter") {
            runGeneration(topicInput.value.trim());
        }
    });
    exportBtn.addEventListener("click", () => {
        const topic = topicInput.value.trim();
        const markup = document.getElementById("animation-stage").innerHTML;
        saveAnimationFile(markup, topic);
    });
    if (exportVideoBtn) {
        exportVideoBtn.addEventListener("click", exportVideo);
    }

    if (settingsBtn) {
        console.log("Setting up settings button click event...");
        settingsBtn.addEventListener("click", () => {
            console.log("Settings button clicked!");
            openSettingsModal();
        });
    } else {
        console.error("Settings button not found in DOM!");
    }
    if (settingsClose) {
        settingsClose.addEventListener("click", closeSettingsModal);
    }
    if (settingsSave) {
        settingsSave.addEventListener("click", saveSettings);
    }
    if (modalTabButtons.length) {
        modalTabButtons.forEach((button) => {
            button.addEventListener("click", () => {
                const tabId = button.dataset.tab || "video";
                setSettingsTab(tabId);
            });
        });
    }
    if (settingsModal) {
        settingsModal.addEventListener("click", (event) => {
            if (event.target === event.currentTarget) {
                closeSettingsModal();
            }
        });
    }
    if (voiceProviderSelect) {
        voiceProviderSelect.addEventListener("change", (event) => {
            currentSettings.voice_provider = event.target.value;
            applyVoiceSelection();
        });
    }
    if (voiceSelect) {
        voiceSelect.addEventListener("change", (event) => {
            currentSettings.voice = event.target.value || null;
        });
    }
    if (systemPromptInput) {
        systemPromptInput.addEventListener("input", (event) => {
            credentialState.system_prompt = event.target.value;
        });
    }

    document.getElementById("zoom-in").addEventListener("click", () => zoomGraph(1.2));
    document.getElementById("zoom-out").addEventListener("click", () => zoomGraph(0.8));
    document.getElementById("reset-view").addEventListener("click", resetGraph);
    
    const graphLayoutSelect = document.getElementById("graph-layout-select");
    if (graphLayoutSelect) {
        graphLayoutSelect.addEventListener("change", (e) => changeGraphLayout(e.target.value));
    }
    
    const graphColorSelect = document.getElementById("graph-color-select");
    if (graphColorSelect) {
        graphColorSelect.addEventListener("change", (e) => changeGraphColor(e.target.value));
    }
    
    const graphBgSelect = document.getElementById("graph-bg-select");
    if (graphBgSelect) {
        graphBgSelect.addEventListener("change", (e) => changeGraphBg(e.target.value));
    }

    const dynamicGraphToggle = document.getElementById("dynamic-graph-toggle");
    if (dynamicGraphToggle) {
        dynamicGraphToggle.addEventListener("change", () => {
            if (currentGraphData) {
                initialiseGraph(currentGraphData);
            }
        });
    }
    
    const exportGraphImage = document.getElementById("export-graph-image");
    if (exportGraphImage) {
        exportGraphImage.addEventListener("click", () => {
            // 确保图谱已完全渲染
            if (!graphInstance) return;
            
            // 临时调整 canvas 大小以获得更高分辨率
            const canvas = document.querySelector('#graph-surface canvas');
            if (!canvas) return;
            
            // 获取数据 URL
            const dataUrl = canvas.toDataURL("image/png");
            
            // 创建下载链接
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = `knowledge-graph-${new Date().getTime()}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }
    
    const exportGraphSvg = document.getElementById("export-graph-svg");
    if (exportGraphSvg) {
        exportGraphSvg.addEventListener("click", () => {
            alert("SVG 导出功能暂未实现，请使用 PNG 导出。");
        });
    }

    document.getElementById("tab-animation").addEventListener("click", () => switchTab("animation"));
    document.getElementById("tab-graph").addEventListener("click", () => switchTab("graph"));
    document.getElementById("tab-graph3d").addEventListener("click", () => switchTab("graph3d"));

    // 3D 图谱控件
    const graph3dColorSelect = document.getElementById("graph3d-color-select");
    if (graph3dColorSelect) {
        graph3dColorSelect.addEventListener("change", (e) => change3DGraphColor(e.target.value));
    }
    
    const graph3dAutoRotate = document.getElementById("graph3d-auto-rotate");
    if (graph3dAutoRotate) {
        graph3dAutoRotate.addEventListener("change", (e) => toggle3DAutoRotate(e.target.checked));
    }
    
    const graph3dShowLabels = document.getElementById("graph3d-show-labels");
    if (graph3dShowLabels) {
        graph3dShowLabels.addEventListener("change", (e) => toggle3DLabels(e.target.checked));
    }
    
    const graph3dReset = document.getElementById("graph3d-reset");
    if (graph3dReset) {
        graph3dReset.addEventListener("click", () => reset3DView());
    }
    
    const exportGraph3dImage = document.getElementById("export-graph3d-image");
    if (exportGraph3dImage) {
        exportGraph3dImage.addEventListener("click", () => export3DGraph());
    }
}

async function runGeneration(topic) {
    if (!topic) {
        showError("请输入可视化主题");
        return;
    }
    setLoading(true);
    hideError();
    
    // Hide previous results while generating
    const viewer = document.getElementById("viewer");
    if (viewer) viewer.hidden = true;

    try {
        const result = await requestVisualization(topic);
        if (result.error) {
            showError(result.error);
            return;
        }
        currentBundle = result;
        if (result.settings) {
            currentSettings = { ...currentSettings, ...result.settings };
            applySettingsToUi();
        }
        document.getElementById("viewer").hidden = false;
        
        // 清理并插入动画内容
        const animationStage = document.getElementById("animation-stage");
        const animationContent = result.animation_html || "";
        const animationFile = result.animation_file;  // 动画文件路径
        
        // 如果有动画文件路径，使用iframe的src加载（这样资源路径才能正确解析）
        if (animationFile && (animationContent.includes("<!DOCTYPE") || animationContent.includes("<html"))) {
            animationStage.innerHTML = '';
            const iframe = document.createElement('iframe');
            iframe.style.width = '100%';
            iframe.style.height = '600px';
            iframe.style.border = 'none';
            iframe.style.borderRadius = '16px';
            // 使用src加载文件，这样base URL是正确的，音频等资源可以正确加载
            // 确保路径以/开头，使其相对于服务器根目录而不是当前页面
            iframe.src = animationFile.startsWith('/') ? animationFile : '/' + animationFile;
            animationStage.appendChild(iframe);
        } else if (animationContent.includes("<!DOCTYPE") || animationContent.includes("<html")) {
            // 回退方案：如果没有文件路径，使用contentDocument.write
            animationStage.innerHTML = '';
            const iframe = document.createElement('iframe');
            iframe.style.width = '100%';
            iframe.style.height = '600px';
            iframe.style.border = 'none';
            iframe.style.borderRadius = '16px';
            animationStage.appendChild(iframe);
            iframe.contentDocument.open();
            iframe.contentDocument.write(animationContent);
            iframe.contentDocument.close();
        } else if (animationContent.includes("<svg")) {
            // 纯SVG内容
            animationStage.innerHTML = animationContent;
        } else {
            // 如果是纯文本或其他格式，包装为可读格式
            animationStage.innerHTML = `<div style="padding: 20px; background: #f3f4f6; border-radius: 8px; font-family: 'Segoe UI', sans-serif; line-height: 1.6;">${animationContent}</div>`;
        }
        
        initialiseGraph(result.graph_data || {});
        initialise3DGraph(result.graph_data || {});
        switchTab("animation");
    } catch (err) {
        showError(`生成失败：${err.message || err}`);
    } finally {
        setLoading(false);
    }
}

// TTS引擎切换显示逻辑
function updateTtsEngineDisplay(engine) {
    const edgeTtsConfig = document.getElementById("edge-tts-config");
    const xiaoaiTtsConfig = document.getElementById("xiaoai-tts-config");
    const aliyunTtsConfig = document.getElementById("aliyun-tts-config");
    const pyttsx3Config = document.getElementById("pyttsx3-config");
    const ttsEngineSelect = document.getElementById("setting-tts-engine");
    
    // 隐藏所有配置面板
    if (edgeTtsConfig) edgeTtsConfig.style.display = "none";
    if (xiaoaiTtsConfig) xiaoaiTtsConfig.style.display = "none";
    if (aliyunTtsConfig) aliyunTtsConfig.style.display = "none";
    if (pyttsx3Config) pyttsx3Config.style.display = "none";
    
    // 显示对应的配置面板
    if (engine === "edge_tts" && edgeTtsConfig) {
        edgeTtsConfig.style.display = "block";
    } else if (engine === "xiaoai" && xiaoaiTtsConfig) {
        xiaoaiTtsConfig.style.display = "block";
    } else if (engine === "aliyun" && aliyunTtsConfig) {
        aliyunTtsConfig.style.display = "block";
    } else if (engine === "pyttsx3" && pyttsx3Config) {
        pyttsx3Config.style.display = "block";
    }
    
    // 更新选择器显示状态
    if (ttsEngineSelect) {
        const options = ttsEngineSelect.querySelectorAll("option");
        options.forEach(opt => {
            if (opt.value === engine) {
                opt.textContent = opt.textContent.replace(/^[✓\s]*/, "✓ ").replace(/\s*\(当前使用\)/, " (当前使用)");
            } else {
                opt.textContent = opt.textContent.replace(/^[✓\s]*/, "").replace(/\s*\(当前使用\)/, "");
            }
        });
    }
}

DocumentReady(() => {
    console.log("KnowledgeSight JavaScript loaded successfully!");
    try {
        // 确保viewer初始隐藏
        const viewer = document.getElementById("viewer");
        if (viewer) {
            viewer.hidden = true;
            console.log("Viewer hidden on init");
        }
        
        initUi();
        resolveTheme();
        loadSettings();
        loadCredentials();
        loadVoices();
        setSettingsTab(settingsCurrentTab);
        window.switchTab = switchTab;
        
        // TTS引擎切换事件
        const ttsEngineSelect = document.getElementById("setting-tts-engine");
        if (ttsEngineSelect) {
            ttsEngineSelect.addEventListener("change", (e) => {
                updateTtsEngineDisplay(e.target.value);
            });
        }
        
        // 滑块实时更新显示
        const edgeVolume = document.getElementById("edge-volume");
        if (edgeVolume) {
            edgeVolume.addEventListener("input", (e) => {
                const value = document.getElementById("edge-volume-value");
                if (value) value.textContent = `${e.target.value}%`;
            });
        }
        
        const xiaoaiSpeed = document.getElementById("setting-xiaoai-speed");
        if (xiaoaiSpeed) {
            xiaoaiSpeed.addEventListener("input", (e) => {
                const value = document.getElementById("xiaoai-speed-value");
                if (value) value.textContent = `${e.target.value}x`;
            });
        }

        const aliyunRate = document.getElementById("setting-aliyun-rate");
        if (aliyunRate) {
            aliyunRate.addEventListener("input", (e) => {
                const value = document.getElementById("aliyun-rate-value");
                if (value) value.textContent = `${e.target.value}x`;
            });
        }

        const aliyunVolume = document.getElementById("setting-aliyun-volume");
        if (aliyunVolume) {
            aliyunVolume.addEventListener("input", (e) => {
                const value = document.getElementById("aliyun-volume-value");
                if (value) value.textContent = `${e.target.value}`;
            });
        }
        
        const pyttsx3Rate = document.getElementById("pyttsx3-rate");
        if (pyttsx3Rate) {
            pyttsx3Rate.addEventListener("input", (e) => {
                const value = document.getElementById("pyttsx3-rate-value");
                if (value) value.textContent = `${e.target.value} 词/分钟`;
            });
        }
        
        const pyttsx3Volume = document.getElementById("pyttsx3-volume");
        if (pyttsx3Volume) {
            pyttsx3Volume.addEventListener("input", (e) => {
                const value = document.getElementById("pyttsx3-volume-value");
                if (value) value.textContent = `${e.target.value}%`;
            });
        }
        
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeSettingsModal();
            }
        });
        console.log("Initialization complete!");
    } catch (error) {
        console.error("Initialization error:", error);
    }
});

function DocumentReady(cb) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", cb);
    } else {
        cb();
    }
}
