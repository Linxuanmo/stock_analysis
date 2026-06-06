1.文档总框架：
stock_analysis/
├── README.md                     # 项目说明与迁移指南
├── data/
│   ├── raw/          # 原始下载数据
│   └── processed/    # 清洗后、中间数据
├── requirements.txt
├── setup.py / pyproject.toml
├── config/
│   ├── default.yaml              # 默认配置（数据源、模型路径、参数）
│   ├── oriental_sec.yaml         # 东方证券特定配置（API、账号等）
│   └── model_registry.yaml       # 模型注册表（名称→框架/路径映射）
├── core/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetcher.py            # 抽象数据获取接口
│   │   ├── oriental_fetcher.py   # 东方证券具体实现
│   │   └── cache.py              # 数据缓存与本地存储
│   ├── features/
│   │   ├── __init__.py
│   │   ├── base_analyzer.py      # 特征分析抽象基类
│   │   ├── image_peak_analyzer.py # 模式1：基于图像高峰的向量切割分析
│   │   ├── sequential_analyzer.py # 模式1：时序升降规律分析
│   │   └── feature_vector.py     # 特征向量数据结构定义
│   ├── models/
│   │   ├── __init__.py
│   │   ├── model_loader.py       # 模型加载器，根据注册表动态加载TF/PyTorch/Jittor
│   │   └── custom_handwritten.py # 手写模型模板（模式2）
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── formula_generator.py  # 策略公式生成（模式3-1）
│   │   ├── function_fitter.py    # 函数拟合与预测（模式3-2）
│   │   └── strategy_executor.py  # 策略执行器，对接模拟盘
│   └── evaluation/
│       ├── __init__.py
│       ├── backtest.py           # 模拟盘比对与评估引擎
│       └── metrics.py            # 评估指标（夏普、最大回撤等）
├── services/
│   ├── __init__.py
│   ├── analysis_service.py       # 整合特征分析流程（板块/个股模式调度）
│   ├── strategy_service.py       # 策略生成与拟合服务
│   └── evaluation_service.py     # 模拟盘评估服务
├── visualization/
│   ├── __init__.py
│   ├── feature_plot.py           # 特征向量图绘制（模式2）
│   ├── prediction_plot.py        # 未来函数图像绘制（模式3-2）
│   └── performance_chart.py      # 模拟盘绩效图表
├── utils/
│   ├── __init__.py
│   ├── config_loader.py          # 配置加载与合并
│   ├── logger.py                 # 统一日志
│   └── platform_adapter.py       # 平台迁移适配器（切换券商）
├── tests/
│   ├── test_fetcher.py
│   ├── test_features.py
│   ├── test_strategies.py
    ├── test_load.py
    ├── test_training.py          #数据代码测试
    ├── test_peak_visual.py       #特征--高峰向量切割测试
    ├── 
    ├── 
    ├── 
    ├── 
│   └── test_evaluation.py
├── notebooks/                    # 探索性分析Notebook（边缘）
│   └── demo.ipynb
└── outputs/                      # 输出目录（图表、报告、模型）
    ├── features/
    ├── strategies/
    └── reports/

2.分析思路与模块
# 科创板股票分析系统
## 1. 数据获取与处理
- 数据源：东方通信达金融终端 / AKShare
- 粒度：日线、月线
- 格式：csv（通达信导出的 .xls 实际上是制表符分隔的文本文件，不是二进制 Excel）
- 复权：前复权
- 板块：科创板成分股+指数
- 清洗：缺失值、除权校准
## 2. 特征工程
- 视角A：峰值向量切割
  - 高峰识别 (find_peaks)
  - 片段切割与最大长度自适应
  - 片段特征：周期、斜率、波动率、支撑线
- 视角B：整体时序规律
  - 上升/下降波段统计
  - 反转形态频率
  - 长周期动量指标
  - 顺势和逆势状态分析
## 3. 模型构建与加载
- 模型注册表 (model_registry.yaml)
- 动态加载：PyTorch / TensorFlow / Jittor
- 手写特征提取模型
- 输入shape适配
## 4. 策略生成与评估
- 策略公式生成
  - 通达信公式输出
  - Python函数输出
- 模拟盘回测
  - 净值曲线
  - 夏普比率、最大回撤
- 未来走势拟合与预测
## 5. 监控与纠偏
- 实时信号质量监控
- 自适应参数调整
- 置信区间检验
- 反馈闭环


# 科创板股票分析系统 – 需求说明与开发使用流程

## 1. 项目背景与目标
本项目构建一个基于东方证券数据（东方财富/通达信导出 + AKShare）的科创板股票分析系统，以 Python 为核心开发语言。  
系统支持两种分析模式（板块分析、个股分析），并输出以下四类成果：
1. 特征分析报告（高峰切割向量 + 整体时序规律）  
2. 可视化特征向量图  
3. 选股策略（通达信公式 / Python 函数）  
4. 模拟盘回测评估报告  

系统架构区分为核心模块与边缘应用，保证易于迁移至其他券商数据源。

## 2. 核心需求回顾

### 2.1 数据获取
- **数据来源**：东方财富金融终端导出的 `.xls`（实际为制表符分隔文本）或 AKShare 在线接口  
- **数据粒度**：日线、月线，默认**前复权**  
- **板块范围**：科创板成分股（如科创机器人概念），支持批量导出  
- **清洗规则**：剔除成交量 ≤0、价格 ≤0、缺失核心价格列的行；列名中文化→英文标准化  

### 2.2 特征工程
#### 视角 A：基于高峰的向量切割
- 使用 `scipy.signal.find_peaks` 识别显著局部高峰  
- 按高峰将价格序列切分为若干片段，可设定最大片段长度  
- 每个片段提取：长度、价格变化率、波动率、趋势斜率、平均成交量  

#### 视角 B：整体时序规律
- 不切割序列，全局统计上升/下降波段（数量、平均天数、平均幅度）  
- 计算长周期动量（价格相对于 N 日均线偏离）、顺势/逆势状态  
- 成交量变化趋势  

### 2.3 模型支持
- 可加载外部预训练模型（TensorFlow / PyTorch / Jittor）对特征向量进行深层特征提取  
- 支持手写特征提取模型，生成可视化向量图  

### 2.4 策略生成与评估
- 基于特征自动生成两种形式的策略：  
  - 通达信公式（可直接粘贴至终端）  
  - Python 函数（用于本地模拟与拟合）  
- 模拟盘回测：计算净值曲线、夏普比率、最大回撤等指标  

### 2.5 可视化
- 特征向量图、高峰标记图  
- 未来走势拟合曲线与置信区间  
- 模拟盘绩效图（净值、回撤、月度收益热力图）  

## 3. 开发使用流程

### 3.1 环境准备
1. 安装 Conda，创建虚拟环境：
   ```bash
   conda create -n stock_analysis python=3.10
   conda activate stock_analysis
   ```
2. 安装核心依赖：
   ```bash
   pip install pandas numpy scipy matplotlib openpyxl xlrd
   # 可选：pip install akshare
   ```
3. 用 VS Code 打开项目根目录 `stock_analysis/`，选择 `stock_analysis` 解释器。

### 3.2 数据准备
1. 将通达信导出的所有 `.xls` 文件放入 `data/raw/` 的子文件夹中（如 `2026_5_29__688__50__total/`）。  
   文件名格式：`序号_股票代码.xls`（例如 `1_688469.xls`）。
2. 或运行以下脚本通过 AKShare 自动下载：
   ```bash
   python download_data.py   # 需提前安装 akshare
   ```

### 3.3 数据加载验证
运行测试脚本检查数据完整性：
```bash
python tests/test_load.py
```
预期输出：成功加载 50 只股票，并显示每只股票的数据行数和日期范围。  
内部已自动识别文件为制表符分隔文本（GBK 编码），完成列名映射、日期解析和基础清洗。

### 3.4 特征提取
#### 视角 A：高峰切割特征
1. 根据需要修改 `core/features/image_peak_analyzer.py` 顶部配置区的参数：
   - `PROMINENCE`：高峰显著程度（越小峰越多）
   - `MAX_SEGMENT_LEN`：片段最大长度（交易日数）
2. 运行特征提取脚本：
   ```bash
   python tests/test_features.py
   ```
3. 输出文件：`data/processed/peak_features.csv`（每个片段一行，含长度、涨跌幅、波动率等）。

#### 视角 B：整体时序特征
1. 修改 `core/features/sequential_analyzer.py` 配置区参数：
   - `MIN_WAVE_PCT`：波段最小变化阈值
   - `MOMENTUM_MA_PERIOD`：动量均线周期
2. 运行同一脚本，输出 `data/processed/sequential_features.csv`（每只股票一行，含波段统计、动量状态等）。

### 3.5 模型训练（下季度计划）
1. 通过 `services/training_service.py` 选择模型（PyTorch/TF/手写）和数据范围。
2. 训练两类目标：
   - 切割参数最优值（`PROMINENCE`、`MAX_SEGMENT_LEN` 等）
   - 特征权重最优值（各特征在评分中的加权系数）
3. 训练结果自动存入 `trained_models/`，按时间戳组织，支持历史版本回溯。

### 3.6 策略生成与回测（开发中）
1. 调用 `core/strategies/formula_generator.py` 生成选股公式（通达信语法 + Python 函数）。
2. 使用 `core/evaluation/backtest.py` 进行模拟盘回测，输出评估报告和绩效图表。

## 4. 当前完成进度
- ✅ 数据读取器 `oriental_fetcher.py`：稳定读取 50 只科创板股票，支持自动格式识别和清洗  
- ✅ 高峰切割分析器 `image_peak_analyzer.py`：可批量生成片段特征表  
- ✅ 时序规律分析器 `sequential_analyzer.py`：可批量生成全局特征表  
- ✅ 测试脚本 `test_load.py`、`test_features.py` 验证通过  

## 5. 下一步计划
- 实现参数管理模块（手动配置 + 自动加载训练结果）  
- 开发参数/权重训练器，集成回测引擎进行优化  
- 完成策略生成、函数拟合与完整回测闭环  
- 可视化模块落地（特征图、预测图、绩效图）