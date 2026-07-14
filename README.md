# synth_engine — 通用数据合成引擎

基于 LLM 的数据合成引擎，采用模板插件架构，支持多领域训练数据生成与质量校验。目前内置**银行意图识别**（ICBC 手机银行）场景的完整合成流水线。

---

## 项目结构

```
synth_engine/
├── configs/                          # 全局配置文件
│   ├── llm_config.yaml               #   多模型 API 配置（qwen/glm/kimi）
│   └── embedding_config.yaml         #   向量嵌入 API 配置
│
├── synth_engine/                     # 主 Python 包
│   ├── __init__.py                   #   包元信息，版本 0.1.0
│   ├── api/
│   │   ├── main.py                   #   FastAPI 应用入口，挂载路由 & 静态前端
│   │   └── routes/
│   │       ├── synthesis.py          #   合成任务 API（启动/查询）
│   │       ├── qc.py                 #   质量检查 API（合成前/后）
│   │       ├── config.py             #   配置管理 API（YAML/JSON 读写）
│   │       ├── template.py           #   模板管理 API（列表/创建/删除）
│   │       └── files.py              #   输出文件 API（列表/下载/预览/删除）
│   │
│   ├── core/                         # 核心引擎
│   │   ├── config.py                 #   Pydantic 配置模型 + ConfigLoader
│   │   ├── models.py                 #   数据类：SynthSample, LLMResult, QCResult, RunStatus
│   │   ├── pipeline.py               #   SynthesisPipeline：生成→LLM→过滤→导出
│   │   ├── profile_gen.py            #   用户画像生成器（银行卡/理财/贷款/保险等）
│   │   └── utils.py                  #   工具函数：加权随机、JSON 提取、YAML 格式化
│   │
│   ├── llm/                          # LLM 调用层
│   │   ├── client.py                 #   HTTP 客户端（流式/非流式）
│   │   ├── parallel.py               #   线程池并行调用 + 重试 + 进度条
│   │   └── embedding.py              #   OpenAI 兼容的向量嵌入 + 余弦相似度
│   │
│   ├── templates/                    # 模板系统（插件化）
│   │   ├── __init__.py               #   自动导入 bank_intent，导出 TemplateRegistry
│   │   ├── base.py                   #   SynthTemplate 抽象基类
│   │   ├── registry.py               #   TemplateRegistry 单例注册中心
│   │   └── bank_intent/              #   银行意图模板（内置实现）
│   │       ├── __init__.py           #     BankIntentTemplate 实现，自动注册
│   │       ├── intent.json           #     意图定义（8 大类，40+ 子意图）
│   │       ├── synth_config.yaml     #     合成参数（轮次分布/意图转移/语气/情绪）
│   │       ├── profile_config.yaml   #     用户画像生成配置（卡/理财/贷款/数字人民币）
│   │       └── prompts/
│   │           ├── multi_round.md    #       多轮对话生成 prompt 模板
│   │           └── single_round.md   #       单轮查询生成 prompt 模板
│   │
│   ├── qc/                           # 质量校验模块
│   │   ├── pre_check.py              #   合成前校验：意图菜单质量评估 + 相似度检测
│   │   └── post_check.py             #   合成后校验：语义去重 + 多模型投票分类
│   │
│   └── resources/                    # 数据资源文件
│       ├── fund.csv                  #   基金产品库（25034 条）
│       └── financial_product.csv     #   理财产品库（1385 条）
│
├── frontend/dist/                    # Vue/Vite 前端构建产物（SPA）
├── wheels/                           # 离线 pip wheel 包（45 个，支持无网安装）
├── runs/                             # 运行时输出
│   ├── outputs/                      #   合成任务输出目录
│   └── qc_results/                   #   质检任务输出目录
├── requirements.txt                  # Python 依赖清单
├── start.bat                         # Windows 一键启动脚本
└── README.md                         # 本文件
```

---

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Vue SPA)                   │
│                 StaticFiles served by FastAPI            │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP REST
┌──────────────────────────▼──────────────────────────────┐
│                    FastAPI (api/main.py)                  │
│  ┌──────────┬──────────┬──────────┬──────────┬────────┐ │
│  │synthesis │    qc    │  config  │ template │ files  │ │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬───┘ │
└───────┼──────────┼──────────┼──────────┼──────────┼─────┘
        │          │          │          │          │
┌───────▼──────────▼──────────▼──────────▼──────────▼─────┐
│                     Core Layer                           │
│  ┌──────────────────┐  ┌──────────────────────────────┐ │
│  │ SynthesisPipeline │  │ ConfigDrivenProfileGenerator │ │
│  │ 生成→LLM→过滤→导出│  │ 用户画像（概率驱动）         │ │
│  └────────┬─────────┘  └────────────┬─────────────────┘ │
│           │                         │                    │
│  ┌────────▼─────────┐  ┌────────────▼─────────────────┐ │
│  │   LLM Parallel    │  │       QC Module               │ │
│  │   (线程池并行)    │  │  pre_check / post_check       │ │
│  └────────┬─────────┘  └────────────┬─────────────────┘ │
│           │                         │                    │
│  ┌────────▼─────────────────────────▼─────────────────┐ │
│  │              Template Registry (插件注册)          │ │
│  │          bank_intent / [可扩展其他领域]            │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 核心流程

### 1. 数据合成流水线 (`core/pipeline.py`)

```
输入: template + 合成参数
  │
  ├─ ① 生成样本计划 ─── 根据 synth_config 概率分布确定轮次、意图、语气、情绪
  │     └─ 调用 ConfigDrivenProfileGenerator 为每条样本生成虚拟用户画像
  │
  ├─ ② LLM 对话生成 ─── 多轮对话 + 单轮查询，并行调用 LLM
  │     └─ 多轮：prompt 注入用户画像、意图、历史对话上下文
  │     └─ 单轮：每次生成 5 条不同表述的用户 utterance
  │
  ├─ ③ 后处理 ─── 拆分单轮结果，解析 JSON 响应
  │
  └─ ④ 过滤导出 ─── 过滤无效响应，输出 CSV + JSONL 到 runs/outputs/
```

### 2. 质量校验

| 阶段 | 脚本 | 功能 |
|------|------|------|
| **合成前** | `qc/pre_check.py` | 检查意图菜单的文字错误、一致性、评判可行性；检测相似/易混淆菜单 |
| **合成后** | `qc/post_check.py` | 向量相似度去重；多模型投票判断意图分类准确率（一级 + 二级） |

---

## 脚本功能与依赖关系

### 入口脚本

| 脚本 | 功能 | 依赖 |
|------|------|------|
| `start.bat` | Windows 一键启动：检查 Python 版本 → 安装离线 wheel 包 → 启动 Uvicorn | Python 3.10+, `wheels/`, `requirements.txt` |

### API 层

| 脚本 | 功能 | 内部依赖 |
|------|------|----------|
| `api/main.py` | FastAPI 应用入口，挂载 5 个路由并托管前端 | → `api/routes/*` |
| `api/routes/synthesis.py` | `POST /api/synthesis/create` 启动合成，`GET /api/synthesis/status` 查进度 | → `core.pipeline`, `core.config`, `core.models`, `templates.registry` |
| `api/routes/qc.py` | `POST /api/qc/pre` / `POST /api/qc/post` 执行质检 | → `qc.pre_check`, `qc.post_check` |
| `api/routes/config.py` | CRUD 模板配置 / LLM 配置 / Embedding 配置 / CSV 资源 | → `core.config`, `core.profile_gen` |
| `api/routes/template.py` | 模板列表、创建（带默认文件）、删除、prompt 读取 | → `templates.registry` |
| `api/routes/files.py` | 列出/下载/预览合成输出、删除运行结果 | — |

### 核心引擎

| 脚本 | 功能 | 内部依赖 |
|------|------|----------|
| `core/config.py` | Pydantic 模型验证合成/画像配置，`ConfigLoader` 加载 YAML | `pyyaml`, `pydantic` |
| `core/models.py` | 数据类定义（`SynthSample`、`LLMResult`、`QCResult`、`RunStatus`） | `dataclasses` |
| `core/pipeline.py` | 四步合成流水线：生成→LLM→过滤→导出 | → `core.config`, `core.models`, `core.profile_gen`, `core.utils`, `llm.parallel`, `templates.*` |
| `core/profile_gen.py` | 概率驱动的中国银行用户画像生成器（1147 行） | → `core.config`, `core.utils`, `faker`, `cn2an`, `pandas`, `numpy` |
| `core/utils.py` | `weighted_choice`、JSON 提取、YAML 格式化 | `json`, `pyyaml`, `random` |

### LLM 层

| 脚本 | 功能 | 内部依赖 |
|------|------|----------|
| `llm/client.py` | HTTP 调用 LLM（流式 SSE / 非流式 JSON） | `requests`, `json` |
| `llm/parallel.py` | 线程池并行调用，round-robin 选模型，自动重试（最多 5 次，指数退避），tqdm 进度 | → `llm.client` |
| `llm/embedding.py` | 文本向量嵌入（OpenAI 兼容 API），余弦相似度矩阵 | `openai`, `numpy` |

### 模板系统

| 脚本 | 功能 | 内部依赖 |
|------|------|----------|
| `templates/base.py` | `SynthTemplate` 抽象基类（6 个抽象方法） | — |
| `templates/registry.py` | `TemplateRegistry` 单例：注册/获取/列表/检查 | — |
| `templates/__init__.py` | 自动导入 `bank_intent` 触发注册，导出 `TemplateRegistry` | → `templates.bank_intent`, `templates.registry` |
| `templates/bank_intent/__init__.py` | `BankIntentTemplate` 实现类，实例化时自动注册为 `"bank_intent"` | → `templates.base`, `templates.registry`, `core.models` |

### 质检模块

| 脚本 | 功能 | 内部依赖 |
|------|------|----------|
| `qc/pre_check.py` | LLM-as-Judge 评估意图菜单质量 + 向量相似度检测易混淆菜单 | → `core.models`, `llm.parallel`, `llm.embedding` |
| `qc/post_check.py` | 语义去重 + 多模型投票判定意图分类准确率 | → `core.models`, `llm.parallel`, `llm.embedding` |

### 数据资源

| 文件 | 内容 |
|------|------|
| `resources/fund.csv` | 中国公募基金目录（代码、名称、类型、拼音），用于持仓画像生成 |
| `resources/financial_product.csv` | 银行理财产品目录（名称、收益率），用于理财持仓画像生成 |

---

## 配置文件说明

### `configs/llm_config.yaml`

定义可用 LLM 后端列表，每个模型包含：

```yaml
- name: qwen3.5-plus           # 模型标识名
  api_key: sk-xxx              # API 密钥
  base_url: https://...        # API 端点（DashScope）
  temperature: 0.8             # 生成温度
  max_tokens: 4096             # 最大 Token 数
```

### `configs/embedding_config.yaml`

```yaml
model: text-embedding-v3
api_key: sk-xxx
base_url: https://dashscope.aliyuncs.com/...
```

### 模板内置配置（`templates/bank_intent/`）

| 文件 | 说明 |
|------|------|
| `intent.json` | 意图分类体系定义（层级树 + 示例） |
| `synth_config.yaml` | 合成策略：轮次分布概率、意图转移规则、语气/情绪分布 |
| `profile_config.yaml` | 用户画像生成规则：信用卡/借记卡、基金/理财持仓、贷款、保险、社保/公积金、数字人民币、交易行为等 |
| `prompts/multi_round.md` | 多轮对话 prompt 模板（`{{variable}}` 占位符） |
| `prompts/single_round.md` | 单轮查询 prompt 模板 |

---

## 启动方式

### Windows

双击 `start.bat` 或在终端执行：

```cmd
start.bat
```

脚本会自动：
1. 检查 Python 3.10+
2. 从 `wheels/` 离线安装依赖（无网络环境可用），失败则在线安装
3. 启动 Uvicorn，监听 `0.0.0.0:8080`
4. 浏览器访问 `http://localhost:8080` 打开前端界面

### 手动启动

```bash
# 安装依赖
pip install -r requirements.txt --find-links=wheels --no-index

# 启动服务
python -m uvicorn synth_engine.api.main:app --host 0.0.0.0 --port 8080
```

---

## 扩展新领域

通过实现 `SynthTemplate` 抽象基类即可添加新的合成场景：

1. 在 `templates/` 下创建新目录（如 `templates/my_domain/`）
2. 实现 `__init__.py`，继承 `SynthTemplate` 并实例化（自动注册）
3. 添加对应的 `intent.json`、`synth_config.yaml`、`profile_config.yaml`、`prompts/`
4. 在 `templates/__init__.py` 中 `import` 新模块

```python
# templates/my_domain/__init__.py
from synth_engine.templates.base import SynthTemplate
from synth_engine.templates.registry import TemplateRegistry

class MyDomainTemplate(SynthTemplate):
    @property
    def name(self) -> str:
        return "my_domain"
    # ... 实现全部抽象方法

TemplateRegistry.register(MyDomainTemplate())  # 自动注册
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Uvicorn |
| 配置验证 | Pydantic v2 |
| LLM 调用 | HTTP 客户端（DashScope API），支持流式 SSE |
| 并行执行 | `concurrent.futures.ThreadPoolExecutor` |
| 嵌入模型 | OpenAI 兼容 API（`text-embedding-v3`） |
| 数据生成 | Faker（用户画像）、cn2an（中文数字） |
| 数据处理 | Pandas、NumPy |
| 前端 | Vue 3 + Vite（构建产物在 `frontend/dist/`） |
