<template>
  <div class="detail-page">
    <div class="back-row">
      <el-link type="primary" underline="never" @click="go('/guide')">← 返回使用指南</el-link>
    </div>

    <section class="detail-hero">
      <div>
        <div class="eyebrow">WORKFLOW DETAIL</div>
        <h1>{{ page.title }}</h1>
        <p>{{ page.intro }}</p>
      </div>
      <el-button type="primary" size="large" @click="go(page.entryPath)">{{ page.entryText }} →</el-button>
    </section>

    <el-card class="content-card">
      <template #header><h2>{{ page.stepsTitle }}</h2></template>
      <div class="step-list">
        <div v-for="(step, index) in page.steps" :key="step.title" class="step-item">
          <span class="step-number">{{ String(index + 1).padStart(2, '0') }}</span>
          <div>
            <h3>{{ step.title }}</h3>
            <p>{{ step.text }}</p>
          </div>
        </div>
      </div>
      <el-alert v-if="page.note" :title="page.note" type="info" :closable="false" show-icon />
      <p class="advice">{{ page.advice }}</p>
    </el-card>

    <el-card class="content-card">
      <template #header><h2>输入文件与配置</h2></template>
      <div class="info-grid">
        <div v-for="input in page.inputs" :key="input.name" class="info-item">
          <code>{{ input.name }}</code>
          <p>{{ input.text }}</p>
        </div>
      </div>
    </el-card>

    <el-card class="content-card">
      <template #header>
        <div class="section-heading">
          <h2>产物介绍</h2>
          <span>先看“数据范围”，再判断文件是否只包含问题数据。</span>
        </div>
      </template>
      <div class="output-list">
        <div v-for="output in page.outputs" :key="output.name" class="output-item">
          <div class="output-head">
            <code>{{ output.name }}</code>
            <el-tag :type="output.tagType" effect="light">{{ output.scope }}</el-tag>
          </div>
          <p>{{ output.text }}</p>
          <p v-if="output.how" class="how-to-read"><strong>如何判断：</strong>{{ output.how }}</p>
        </div>
      </div>
    </el-card>

    <div class="bottom-actions">
      <el-button @click="go('/guide')">返回使用指南</el-button>
      <el-button type="primary" @click="go(page.entryPath)">{{ page.entryText }} →</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const go = (path) => router.push(path)

const pages = {
  pre: {
    title: '合成前质检',
    intro: '用于在生成数据之前检查意图配置质量，提前发现描述不清、信息缺失、名称与描述不一致，以及不同子意图边界过于相似等问题，避免错误配置影响后续数据合成。',
    stepsTitle: '系统依次执行两类检查',
    steps: [
      { title: '菜单质量检查', text: '使用 LLM 逐条检查子意图的错别字、描述清晰度、名称与描述的一致性、判断依据是否充分，并给出严重程度和修改建议。' },
      { title: '相似菜单检查', text: '先使用 Embedding 计算不同子意图描述之间的语义相似度，再由 LLM 判断高相似度意图是否真的存在边界重叠或混淆风险。' },
    ],
    advice: '建议先根据产物修改意图描述，再重新运行合成前质检；确认意图定义和语义边界清晰后，再开始数据合成。',
    inputs: [
      { name: 'intent.json', text: '页面选择的意图配置文件，包含一级意图、子意图、描述、权重和示例。' },
      { name: 'LLM 配置', text: '用于逐条检查菜单质量，并判断高相似度菜单是否真的存在混淆。' },
      { name: 'Embedding 配置', text: '用于把子意图描述转换为向量并计算语义相似度。' },
      { name: '任务参数', text: '包括质检数量、并行度和相似度阈值。阈值越低，进入相似菜单候选的数据对越多。' },
    ],
    outputs: [
      { name: 'quality_check_results.csv', scope: '全部已检查数据', tagType: 'primary', text: '每个被检查的子意图对应一行，正常数据和问题数据都会写入。', how: 'severity 为 none 表示未发现明显问题；minor、major、critical 分别表示由轻到重的问题。' },
      { name: 'similarity_check_results.csv', scope: '高相似度候选组合', tagType: 'warning', text: '只记录 Embedding 相似度达到阈值的菜单组合，不是全部菜单组合，也不全是确认有问题的数据。', how: 'is_confusable=true 表示 LLM 认为存在混淆风险；false 表示相似度较高但边界仍可能清晰。' },
      { name: 'meta.json', scope: '任务信息', tagType: 'info', text: '记录任务 ID、状态、提交参数、开始时间和产物位置，不是业务质检数据。' },
    ],
    entryText: '开始合成前质检', entryPath: '/qc/pre',
  },
  synthesis: {
    title: '数据合成',
    intro: '用于根据意图配置、对话规则、用户画像和 Prompt 自动生成单轮或多轮对话数据，并将有效结果整理为适合人工检查、质量检查和模型训练的数据文件。',
    stepsTitle: '系统依次执行以下步骤',
    steps: [
      { title: '生成样本计划', text: '根据意图权重、意图跳转规则、对话轮数、语气和心情等配置，随机生成每条数据的目标意图和对话计划。' },
      { title: '生成用户画像', text: '根据画像配置生成虚拟用户的基础信息、账户、持仓、贷款和行为特征，使生成的对话具有不同的用户背景和业务条件。' },
      { title: '填充 Prompt 并调用 LLM', text: '将目标意图、子意图描述、对话计划和用户画像填入单轮或多轮 Prompt，再调用已配置的 LLM 生成用户与客服之间的对话。' },
      { title: '拆分与格式过滤', text: '单轮模型响应可能包含多条用户表达，系统会将其拆分为独立数据。随后过滤内容为空、格式错误或不符合模板规则的数据。' },
      { title: '整理并导出结果', text: '将通过格式检查的数据整理为结构化数据和训练数据，生成 data.csv、sft.jsonl 和模型调用日志。' },
    ],
    note: '“合成数量”是基础样本计划数，不是最终导出行数。单轮响应拆分会使数量增加，格式过滤也可能使数量减少。',
    advice: '建议先使用少量数据验证意图、画像和 Prompt 是否符合预期。合成完成后，应先预览结果，再运行合成后质检。',
    inputs: [
      { name: 'intent.json', text: '定义一级意图、子意图、描述、权重和示例，是生成目标标签的主要依据。' },
      { name: 'synth_config.yaml', text: '定义意图跳转、对话轮数、单轮比例、语气和心情等生成规则。' },
      { name: 'profile_config.yaml 与资源 CSV', text: '用于生成虚拟用户画像，以及基金、理财等产品信息。' },
      { name: 'single_round.md / multi_round.md', text: '单轮和多轮 Prompt 模板，系统会把意图计划和用户画像填入其中。' },
      { name: 'LLM 配置与任务参数', text: 'LLM 负责生成对话；任务参数包括模板、合成数量和并行度。' },
    ],
    outputs: [
      { name: 'data.csv', scope: '全部格式有效数据', tagType: 'primary', text: '保存拆分并通过格式过滤后的全部合成结果，调用失败或格式不合规的数据不会写入。', how: '这是有效数据全集，但不代表内容和标签一定正确，仍需合成后质检。' },
      { name: 'sft.jsonl', scope: '全部有效训练格式', tagType: 'primary', text: '由与 data.csv 相同的一批有效数据转换为逐行 JSON，便于监督微调或下游处理。', how: '它是格式转换产物，不是“只包含质检正确数据”的文件。' },
      { name: 'llm_log.jsonl', scope: '模型调用日志', tagType: 'info', text: '记录模型、调用状态、耗时和错误信息，可能同时包含成功和失败记录。', how: '用于排查接口和模型稳定性，不是最终合成数据。' },
    ],
    entryText: '开始数据合成', entryPath: '/synthesis',
  },
  post: {
    title: '合成后质检',
    intro: '用于检查已经生成的数据是否存在语义重复、标签冲突或意图判断不一致，帮助判断生成结果能否用于测试或训练。',
    stepsTitle: '系统提供两类检查',
    steps: [
      { title: 'Embedding 相似度检查', text: '将生成数据中的用户文本转换为向量，计算文本之间的语义相似度，找出语义高度接近但意图标签不同的数据。' },
      { title: 'LLM 意图质检', text: '让已配置的模型根据意图定义重新判断每条数据的一级意图和子意图，并与原始标签对比。配置多个模型时，系统会汇总判断结果和投票情况。' },
    ],
    advice: '对于问题候选，应结合原始对话和意图定义判断是生成内容偏离、标签错误，还是意图边界需要调整。',
    inputs: [
      { name: 'data.csv', text: '选择某次数据合成的结构化结果，系统从中读取用户文本和原始意图标签。' },
      { name: 'intent.json', text: '提供当前一级意图、子意图和描述，作为 LLM 重新判断标签时的依据。' },
      { name: 'Embedding 配置', text: '用于计算用户文本之间的语义相似度。' },
      { name: 'LLM 配置', text: '用于重新判断一级意图和子意图；最多选择三个已配置模型参与投票。' },
      { name: '任务参数', text: '包括采样数量、并行度、相似度阈值，以及是否跳过 Embedding 或 LLM 检查。' },
    ],
    outputs: [
      { name: 'embedding_similarity_check.csv', scope: '问题候选数据', tagType: 'warning', text: '只记录相似度达到阈值，并且一级意图或子意图标签不同的数据对。', how: '它不是全量数据，也不是已经确认的错误；需要人工判断标签冲突是否成立。' },
      { name: 'qc_detail_by_model.csv', scope: '全部判断明细', tagType: 'primary', text: '每条被检查数据按参与模型分别记录，正确和错误判断都会写入，同一条数据可能对应多行。', how: '通过 level1_correct 和 level2_correct 查看各模型判断是否正确。' },
      { name: 'qc_summary_voting.csv', scope: '全部汇总结果', tagType: 'primary', text: '每条被检查数据对应一行，包含通过数据和未通过数据。', how: 'overall_pass=true 表示一级和子意图均通过；false 表示未通过，可据此筛选问题数据。' },
      { name: 'meta.json', scope: '任务信息', tagType: 'info', text: '记录任务 ID、状态、执行参数、时间和产物位置，不是业务质检数据。' },
    ],
    entryText: '开始合成后质检', entryPath: '/qc/post',
  },
}

const page = computed(() => pages[route.meta.guideType] || pages.pre)
</script>

<style scoped>
.detail-page { max-width: 1120px; margin: 0 auto; color: #303133; }
.back-row { margin-bottom: 14px; }
.detail-hero { display: flex; justify-content: space-between; align-items: center; gap: 30px; padding: 34px 40px; color: white; border-radius: 16px; background: linear-gradient(135deg, #607bc8, #8ba1df); box-shadow: 0 12px 28px rgba(65,91,169,.12); }
.detail-hero h1 { margin: 8px 0 10px; font-size: 32px; }
.detail-hero p { max-width: 790px; margin: 0; line-height: 1.85; opacity: .94; }
.detail-hero .el-button { flex: none; color: #526db7; border-color: white; background: white; }
.eyebrow { font-size: 12px; letter-spacing: 3px; opacity: .72; }
.content-card { margin-top: 18px; }
.content-card h2 { margin: 0; }
.step-list { display: grid; gap: 14px; margin-bottom: 18px; }
.step-item { display: grid; grid-template-columns: 42px 1fr; gap: 12px; padding: 16px; border: 1px solid #e5eaf5; border-radius: 10px; background: #fafbfe; }
.step-number { color: #6d84c2; font-weight: 700; }
.step-item h3 { margin: 0 0 7px; font-size: 16px; }
.step-item p, .info-item p, .output-item p, .advice { margin: 0; line-height: 1.75; }
.advice { margin-top: 18px; color: #52637d; }
.info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.info-item { padding: 16px; border-radius: 9px; background: #f7f9fd; }
.info-item code, .output-head code { color: #4562ad; font-weight: 700; }
.info-item p { margin-top: 8px; color: #606266; }
.section-heading { display: flex; justify-content: space-between; align-items: center; gap: 20px; }
.section-heading span { color: #909399; font-size: 13px; }
.output-list { display: grid; gap: 14px; }
.output-item { padding: 17px 18px; border-left: 4px solid #aab9df; border-radius: 8px; background: #fafbfe; }
.output-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 9px; }
.how-to-read { margin-top: 7px !important; color: #606266; }
.bottom-actions { display: flex; justify-content: flex-end; gap: 10px; margin: 20px 0 8px; }
@media (max-width: 760px) { .detail-hero { align-items: flex-start; flex-direction: column; padding: 28px; } .info-grid { grid-template-columns: 1fr; } .section-heading { align-items: flex-start; flex-direction: column; gap: 6px; } }
</style>
