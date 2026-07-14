# 数据合成引擎整体执行流程

## 总览

整个系统围绕"**银行智能客服意图识别训练数据**"的生成与质量控制，分为 **4 个阶段 + 1 个前置环节**：

```
┌─────────────────┐
│  ① 领域模板配置  │  ← 前置：定义"造什么数据"（intent.json + synth_config.yaml + profile_config.yaml + prompts/）
└────────┬────────┘
         ▼
┌─────────────────┐
│  ② 合成前质检    │  ← 校验①的意图定义是否合理、无歧义
│  (Pre-Check QC) │      产物：quality_check_results.csv + similarity_check_results.csv
└────────┬────────┘
         ▼
┌─────────────────┐
│  ③ 数据合成      │  ← 核心：画像生成 → 意图采样 → LLM 对话生成 → 格式过滤 → 导出
│  (Synthesis)    │      产物：data.csv + sft.jsonl + llm_log.jsonl
└────────┬────────┘
         ▼
┌─────────────────┐
│  ④ 合成后质检    │  ← 校验③生成的数据是否有标注错误、近似重复
│  (Post-Check QC) │      产物：embedding_similarity_check.csv + qc_detail_by_model.csv + qc_summary_voting.csv
└─────────────────┘
```

**设计理念核心**：用 LLM 做数据生成，再用 LLM 做数据校验（LLM-as-Judge），通过"多模型投票 + Embedding 相似度检测"的双保险机制确保最终产出数据的高质量。

---

## ① 领域模板配置（前置环节）

### 设计思路

系统采用**模板化架构**，不同领域的数据合成只需提供一套配置文件即可复用整个引擎。当前内置领域为 `bank_intent`（工行手机银行意图识别），配置结构如下：

### 配置文件清单

| 文件 | 作用 |
|------|------|
| `intent.json` | 定义所有意图类别（一级意图 + 二级子意图），含名称、描述、权重 |
| `synth_config.yaml` | 合成策略：对话轮次分布、意图跳转概率、语气分布、心情概率等 |
| `profile_config.yaml` | 用户画像生成规则：资产概率、卡片等级、持仓分布、资金池等 |
| `prompts/multi_round.md` | 多轮对话生成的 Prompt 模板 |
| `prompts/single_round.md` | 单轮 query 生成的 Prompt 模板 |

### intent.json 结构示例

```json
{
  "intent": {
    "i豆": {
      "weight": 1,
      "description": "工行i豆积分相关业务",
      "sub_intent": [
        {"name": "查i豆", "description": "查询当前i豆余额，注意与i豆明细区分..."},
        {"name": "赚i豆", "description": "客户参加工银i豆营销活动达标后..."},
        {"name": "花i豆", "description": "客户使用i豆兑换相关产品、权益"}
      ]
    },
    "理财": { ... }
  }
}
```

每个子意图的 `description` 是**后续所有质检的锚点**——合成前用它做相似度检测，合成后用它做意图判定 Prompt 中的分类依据。

---

## ② 合成前质检（Pre-Check QC）

### 设计思路

数据合成的上限由意图定义的质量决定。如果意图菜单本身存在错别字、描述模糊、边界重叠等问题，LLM 生成的对话必然存在标注偏差。因此，在合成前先对 `intent.json` 做两方面的自动化审查。

### 检查项

#### 任务一：菜单质量评审（LLM-as-Judge）

对每个子意图条目，LLM 以 `MENU_QUALITY_PROMPT` 为 Prompt 从四个维度评审：

| 维度 | 检查内容 |
|------|----------|
| 错别字检查 | 拼写错误、标点不规范、语法错误 |
| 一致性检查 | 菜单名与描述是否匹配，同级子意图间是否有重叠 |
| 描述质量检查 | 清晰度评分（1~5），是否对非专业人员友好，是否过于冗长或过于简略 |
| 判断可行性检查 | 用户仅凭此描述能否正确归类？缺少什么关键区分信息？ |

#### 任务二：相似菜单检测（Embedding + LLM）

1. 对所有子意图的 `description` 计算 `text-embedding-v3` 向量
2. 计算 pairwise cosine similarity，找出 >= 0.7 的相似对
3. 将相似对提交 LLM，判断这两个菜单是否真的"可混淆"

> **为什么用 0.7 而非更严格的阈值？** 此处目标是找"潜在风险"，宁可误报少许也要尽量不漏掉有问题的菜单定义，最终由 LLM 二次确认。

### 产物

#### `quality_check_results.csv`

| 字段 | 含义 |
|------|------|
| `menu_name` | 一级意图名称 |
| `sub_intent_name` | 二级子意图名称 |
| `description` | 子意图描述原文 |
| `model` | 执行评审的 LLM 模型名 |
| `reasoning` | LLM 的综合评审分析文本 |
| `typo_issues` | 错别字问题列表（`|` 分隔） |
| `consistency_issues` | 一致性问题列表（`|` 分隔） |
| `quality_issues` | 描述质量缺陷列表（`|` 分隔） |
| `clarity_score` | 清晰度评分（1~5，5 为最优） |
| `judgment_issues` | 判断可行性问题列表（`|` 分隔） |
| `can_judge_user_intent` | 用户能否凭此描述正确归类（True/False） |
| `missing_info` | 缺失的关键区分信息说明 |
| `severity` | 严重等级：`none` / `minor` / `major` / `critical` |
| `suggestion` | 修改建议文本 |

**示例：**

| menu_name | sub_intent_name | severity | clarity_score | can_judge_user_intent | missing_info | suggestion |
|---|---|---|---|---|---|---|
| 理财 | 查收益 | minor | 4 | True | | 建议补充"累计收益"和"昨日收益"的区分说明 |
| 快速转账 | 转账 | major | 2 | False | 未区分"行内转账"与"跨行转账" | 建议拆分为两个独立子意图 |

#### `similarity_check_results.csv`

| 字段 | 含义 |
|------|------|
| `menu_a` | 菜单 A（格式：`一级意图/二级子意图`） |
| `menu_b` | 菜单 B（格式：`一级意图/二级子意图`） |
| `similarity_score` | Embedding 余弦相似度（0~1） |
| `is_confusable` | LLM 判断是否真的易混淆（True/False） |
| `confusion_score` | LLM 给出的混淆度评分（0~1） |
| `reason` | 混淆原因分析 |
| `suggestion` | 修改建议 |

**示例：**

| menu_a | menu_b | similarity_score | is_confusable | confusion_score | reason | suggestion |
|---|---|---|---|---|---|---|
| 理财/查收益 | 理财/查明细 | 0.82 | True | 0.7 | 两者都涉及理财持仓信息查询 | 在描述中增加"仅查询金额"和"含交易记录"的区分 |

> 如果该文件为空（无可疑菜单对），说明所有意图定义的独立性良好。

---

## ③ 数据合成（Synthesis Pipeline）

### 设计思路

数据合成的核心思想是**"多样化种子 + LLM 演绎"**：

1. **多样性来自随机采样**：意图、轮数、语气、心情、用户画像都用概率分布随机采样，确保生成数据的覆盖面
2. **真实性来自 LLM**：由 LLM 根据结构化采样结果，结合详细的用户画像（资产、卡片、贷款、投资偏好等），演绎出贴近真实用户行为的银行客服对话
3. **单轮/多轮混合**：5% 单轮样本用于意图识别测试，95% 多轮样本用于上下文理解训练

### 子流程

#### Step 1：生成用户画像（Profile Generation）

`ConfigDrivenProfileGenerator` 根据 `profile_config.yaml` 的概率配置，用 `Faker` 库 + 随机采样生成一份完整的虚拟银行用户画像，包含：

- **基本信息**：姓名、性别、年龄、职业、城市、客户层级、风险偏好
- **借记卡**：1~4 张，含 I 类户/II 类户/III 类户、普卡/金卡/白金卡/钻石卡等级、余额
- **信用卡**：若有 (prob=0.7)，含额度、已用额度、账单日、还款日、积分
- **持仓**：基金、理财、存款（大额存单+定期）、保险、国债、贵金属
- **贷款**：信用贷款、购房贷款，含月供、剩余本金
- **其他**：收款人、转账限额、U 盾、安全认证方式、权益（i豆/星级/绿色能量）、数字人民币钱包、薪资信息、支付代扣、近 30 天交易记录

#### Step 2：意图样本计划生成（Intent Sampling）

为每条样本随机采样以下参数：

| 参数 | 来源 | 示例 |
|------|------|------|
| 起始意图 + 终止意图 | `intent.json` 权重 + `synth_config.yaml` 跳转概率 | 快速转账 → 理财 |
| 对话轮数 | `synth_config.yaml` 轮数分布（单意图/多意图分别采样） | 3 轮 |
| 语气 | `synth_config.yaml` 语气分布（祈使句 60%、问句 15% 等） | 祈使句 |
| 心情 | 30% 概率附加心情（兴奋/沮丧/愤怒/焦虑等） | 焦虑 |
| 意图转换约束 | 20% 概率启用"仅最后一轮切换意图"约束 | 已启用 |

#### Step 3：LLM 对话生成（LLM Calling）

将每条样本计划与用户画像拼入 Prompt 模板，分别调用 LLM：

- **多轮样本** → `multi_round.md`：生成多轮"用户↔客服"对话，要求口语化、每句 ≤20 字
- **单轮样本** → `single_round.md`：一次生成 5 条独立的用户 query

调用日志写入 `llm_log.jsonl`。

#### Step 4：后处理与过滤（Post-process & Filter）

1. **单轮拆分**：将单轮 LLM 响应中的多行 `用户：...` 拆分为独立样本
2. **格式过滤**：`template.validate_response()` 过滤掉格式不合规的 LLM 输出（如未以"用户："开头的行）
3. **Query 提取**：`template.extract_query()` 提取最终的用户 query 文本（即最后一轮"用户："后的内容），作为下游意图分类的训练样本

#### Step 5：导出

| 文件 | 内容 |
|------|------|
| `data.csv` | 所有有效样本的完整字段（29+ 列），含意图标签 `target`（如 `{"意图":"理财","子意图":"查收益"}`）、用户画像、原始 LLM 响应、提取的 query |
| `sft.jsonl` | SFT 格式的训练数据，每行一个 JSON 对象，格式由 `template.gen_controller_data()` 定义 |
| `llm_log.jsonl` | 每次 LLM 调用的元数据（耗时、状态码、Token 用量等） |

> `data.csv` 是后续合成后质检的输入文件。

---

## ④ 合成后质检（Post-Check QC）

### 设计思路

LLM 生成的数据难免存在两类问题：
1. **标注不一致**：LLM 对 query 的归类可能与预设标签不符
2. **近似重复**：语义几乎相同的 query 被标为不同意图，会混淆下游分类器

因此设计了两套互补的检查机制，用户可独立开关（`skip_embedding` / `skip_llm`）。

### 检查项

#### 检查一：Embedding 相似度检测

对 `data.csv` 中每条 `query` 计算 `text-embedding-v3` 向量，两两对比余弦相似度。满足两个条件即标记为问题样本对：

1. `similarity >= 0.95`（语义几乎相同）
2. 两条样本的**意图标签不同**（`intent` 或 `sub_intent` 任一不同）

> **设计要点**：这里使用 0.95 的严格阈值（远高于合成前 QC 的 0.7），因为目标是消除真正的"重复样本+错误标注"，而非检测意图定义边界模糊。

#### 检查二：多模型投票 LLM 质检

对每条样本，用**最多 3 个 LLM 模型**独立做两级意图判定，多数投票通过才算合格：

1. **一级意图判定**：判断 query 属于哪个一级意图（如"理财"、"快速转账"）
2. **二级意图判定**：一级正确的前提下，判断属于哪个二级子意图（如"查收益"）
3. **投票规则**：通过票数 > 总票数/2 即为通过
4. **总体合格**：一级和二级都多票通过

> **为什么不用 2/3 绝对多数而用 >50%？** 因为实际情况可能只配置了 2 个模型，100%（2/2）通过过于严格，且单个模型判错不影响最终结论。此设计容忍度更高，减少因单一模型偏好造成的误杀。

### 产物

#### `embedding_similarity_check.csv`

| 字段 | 含义 |
|------|------|
| `index_a` / `index_b` | 两条样本在 data.csv 中的行号 |
| `query_a` / `query_b` | 两条样本的用户查询文本 |
| `intent_a` / `intent_b` | 两条样本标注的一级意图 |
| `sub_intent_a` / `sub_intent_b` | 两条样本标注的二级子意图 |
| `similarity` | 两条 query 的余弦相似度（0~1） |

**示例：**

| index_a | index_b | query_a | query_b | intent_a | intent_b | sub_intent_a | sub_intent_b | similarity |
|---|---|---|---|---|---|---|---|---|
| 3 | 17 | 我想查一下余额 | 帮我看看账户里还有多少钱 | 快速转账 | FAQ | 余额查询 | 账户咨询 | 0.973 |

> 含义：两条 query 语义几乎相同（0.973），但分别被标为"快速转账/余额查询"和"FAQ/账户咨询"——这组标注存在冲突，需要人工复核。

#### `qc_detail_by_model.csv`

每个模型对每条样本的独立判定记录，一条样本对应 3 行（3 个模型）。

| 字段 | 含义 |
|------|------|
| `idx` | 样本在 data.csv 中的行号 |
| `model` | 执行判定的 LLM 模型名（如 qwen-plus） |
| `query` | 被质检的用户查询文本 |
| `true_level1` / `true_level2` | 数据集中标注的真实一级/二级意图 |
| `pred_level1` / `pred_level2` | 该模型预测的原始 JSON（含意图名和置信度） |
| `level1_correct` / `level2_correct` | 该模型一级/二级判定是否正确（True/False） |
| `overall_correct` | 该模型总判断是否正确（两级都对才为 True） |
| `prompt_lvl_1` / `prompt_lvl_2` | 发送给该模型的完整 Prompt 文本（可复现调试） |

**示例：**

| idx | model | query | true_level1 | true_level2 | pred_level1 | level1_correct | level2_correct | overall_correct |
|---|---|---|---|---|---|---|---|---|
| 5 | qwen-plus | 工资什么时候到 | 薪资服务 | 工资到账查询 | `{"一级意图":"薪资服务","置信度":0.92}` | True | True | True |
| 5 | glm-5 | 工资什么时候到 | 薪资服务 | 工资到账查询 | `{"一级意图":"薪资服务","置信度":0.85}` | True | False | False |
| 5 | kimi-k2.5 | 工资什么时候到 | 薪资服务 | 工资到账查询 | `{"一级意图":"薪资服务","置信度":0.90}` | True | True | True |

#### `qc_summary_voting.csv`

以样本为单位的投票汇总结果，一个样本一行。

| 字段 | 含义 |
|------|------|
| `idx` | 样本在 data.csv 中的行号 |
| `query` | 被质检的用户查询文本 |
| `true_level1` / `true_level2` | 真实的标注意图 |
| `level1_pass_votes` | 一级意图投票结果（格式 `正确数/总模型数`，如 `3/3`） |
| `level1_pass` | 一级多数通过（True/False） |
| `level2_pass_votes` | 二级意图投票结果（一级未通过时显示 `0/0`） |
| `level2_pass` | 二级多数通过（True/False） |
| `overall_pass` | 该样本总是否合格（一、二级均通过） |
| `reason` | 不合格时说明原因，如 `一级意图判定失败(1/3)` 或 `二级意图判定失败(1/3)` |

**示例 — 合格样本：**

| idx | query | true_level1 | true_level2 | level1_pass_votes | level1_pass | level2_pass_votes | level2_pass | overall_pass | reason |
|---|---|---|---|---|---|---|---|---|---|
| 5 | 工资什么时候到 | 薪资服务 | 工资到账查询 | 3/3 | True | 2/3 | True | True | |

**示例 — 不合格样本：**

| idx | query | true_level1 | true_level2 | level1_pass_votes | level1_pass | level2_pass_votes | level2_pass | overall_pass | reason |
|---|---|---|---|---|---|---|---|---|---|
| 12 | 我转的钱怎么还没到 | 快速转账 | 转账进度查询 | 3/3 | True | 1/3 | False | False | 二级意图判定失败(1/3) |

> 含义：3 个模型一致认为一级意图是"快速转账"（通过），但在二级子意图上只有 1 个模型判为"转账进度查询"，另外 2 个可能判为"转账失败咨询"等，多数不通过，该样本视为不合格。

---

## 关键设计决策总结

| 决策 | 说明 |
|------|------|
| **先质检配置，再合成数据** | 意图定义的错误会被 LLM 放大到上万条数据中，及早发现可避免浪费 LLM 调用成本 |
| **Embedding 双阈值** | 合成前用 0.7（宽进严出，怕漏），合成后用 0.95（严格去重，怕误杀） |
| **多模型投票而非单模型判定** | 避免单一 LLM 的系统性偏差，投票机制更鲁棒 |
| **两级意图独立投票** | 一级和二级分开判定并独立投票，因为一级错误意味着整条样本标注有问题，不应继续二级判定 |
| **单轮/多轮混合 5:95** | 5% 单轮样本用于意图识别冷启动测试，95% 多轮用于上下文理解训练 |
| **用户画像随机化** | 用概率分布和 Faker 而非固定模板生成画像，确保数据多样性覆盖不同用户群体 |
