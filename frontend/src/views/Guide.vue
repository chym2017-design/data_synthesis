<template>
  <div class="guide-page">
    <section class="hero">
      <div>
        <div class="eyebrow">SYNTH ENGINE</div>
        <h1>数据合成引擎</h1>
        <p class="subtitle">从模板配置、质量检查到数据生成和结果导出的完整工作台</p>
        <p class="intro">Synth Engine 用于配置意图体系、生成测试与训练数据，并通过合成前质检和合成后质检，发现定义模糊、语义重复和标签不一致等问题。</p>
      </div>
      <div class="hero-mark">数据<br>合成</div>
    </section>

    <el-card class="section-card">
      <template #header><h2>首次使用准备</h2></template>
      <p>第一次使用前，请先到“配置管理”填写 LLM 和 Embedding 模型，并点击“测试连接”。</p>
      <p>LLM 用于数据合成和意图判断，Embedding 用于文本相似度检查。模型测试成功后，再进入正式业务流程。</p>
      <el-link type="primary" underline="never" @click="go('/config')">前往配置管理 →</el-link>
    </el-card>

    <section class="flow-section">
      <h2>整体业务流程</h2>
      <p class="section-note">点击流程中的步骤，可以直接进入对应功能。</p>
      <div class="flow-row">
        <template v-for="(step, index) in flowSteps" :key="step.title">
          <button class="flow-step" @click="go(step.path)">
            <span class="flow-number">{{ index + 1 }}</span>
            <strong>{{ step.title }}</strong>
            <small>{{ step.desc }}</small>
          </button>
          <div v-if="index < flowSteps.length - 1" class="flow-arrow">→</div>
        </template>
      </div>
    </section>

    <section class="detail-grid">
      <el-card v-for="(item, index) in details" :key="item.title" class="detail-card" shadow="hover" @click="go(item.path)">
        <div class="detail-heading">
          <span>{{ String(index + 1).padStart(2, '0') }}</span>
          <h3>{{ item.title }}</h3>
        </div>
        <p>{{ item.text }}</p>
        <ul v-if="item.points">
          <li v-for="point in item.points" :key="point">{{ point }}</li>
        </ul>
        <p v-if="item.tip" class="tip">{{ item.tip }}</p>
        <div class="detail-actions">
          <el-link type="primary" underline="never" @click.stop="go(item.path)">{{ item.action }} →</el-link>
          <el-link v-if="item.detailPath" type="info" underline="never" @click.stop="go(item.detailPath)">查看详情 →</el-link>
        </div>
      </el-card>
    </section>

    <el-card class="queue-card">
      <div class="queue-flow">
        <div><strong>提交任务</strong></div><span>→</span>
        <div><strong>排队等待</strong></div><span>→</span>
        <div><strong>开始执行</strong></div><span>→</span>
        <div><strong>任务完成</strong></div><span>→</span>
        <div><strong>查看结果</strong></div>
      </div>
      <div class="queue-action">
        <span>可以在“任务队列”中查看当前正在运行和等待执行的任务。</span>
        <el-button type="primary" plain @click="go('/queue')">查看任务队列</el-button>
      </div>
    </el-card>

    <el-alert class="final-notice" title="当前为测试环境，测试账号仅支持小批次数据合成与质检。" type="warning" :closable="false" show-icon />
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
const go = (path) => router.push(path)

const flowSteps = [
  { title: '模板配置', desc: '定义生成规则', path: '/intent-config' },
  { title: '合成前质检', desc: '检查意图定义', path: '/qc/pre' },
  { title: '数据合成', desc: '生成对话数据', path: '/synthesis' },
  { title: '合成后质检', desc: '检查生成结果', path: '/qc/post' },
  { title: '结果查看', desc: '预览与下载', path: '/results' },
]

const details = [
  {
    title: '模板配置',
    text: '模板配置决定“生成什么数据”和“按照什么规则生成”。',
    points: ['意图和子意图', '对话轮数、语气和心情', '虚拟用户画像', '单轮和多轮 Prompt'],
    tip: '修改配置后，建议先预览 Prompt，确认变量均已正确填充。',
    action: '进入模板配置', path: '/intent-config',
  },
  {
    title: '合成前质检',
    text: '在生成数据之前发现意图描述不清、示例不足、名称不一致，以及不同意图语义边界过于相似等问题。',
    tip: '发现问题后，可以返回意图配置修改描述和示例，再重新执行检查。',
    action: '开始合成前质检', path: '/qc/pre', detailPath: '/guide/pre-qc',
  },
  {
    title: '数据合成',
    text: '根据模板生成意图计划和虚拟用户画像，填入 Prompt 后调用 LLM 生成对话，并导出 CSV 和 SFT JSONL。',
    tip: '单轮模型响应可能拆分成多条数据，因此最终导出行数可能高于填写的合成数量。',
    action: '开始数据合成', path: '/synthesis', detailPath: '/guide/synthesis',
  },
  {
    title: '合成后质检',
    text: '检查生成数据中是否存在语义重复、标签冲突或意图判断不一致。',
    points: ['Embedding 相似度检查', 'LLM 意图质检'],
    action: '开始合成后质检', path: '/qc/post', detailPath: '/guide/post-qc',
  },
  {
    title: '结果查看',
    text: '在线预览 CSV、JSON 和 JSONL，下载完整文件，或删除不再需要的任务结果。',
    tip: '删除操作不会进入回收站，重要结果请先下载或联系管理员备份。',
    action: '查看任务结果', path: '/results',
  },
]
</script>

<style scoped>
.guide-page { max-width: 1280px; margin: 0 auto; color: #303133; }
.hero { display: grid; grid-template-columns: 1fr 220px; gap: 32px; padding: 42px 48px; color: white; border-radius: 18px; background: linear-gradient(135deg, #536fc2, #7892df); box-shadow: 0 14px 30px rgba(65,91,169,.14); }
.eyebrow { font-size: 12px; letter-spacing: 4px; opacity: .72; }
.hero h1 { margin: 10px 0 6px; font-size: 38px; }
.subtitle { margin: 0 0 20px; font-size: 20px; opacity: .92; }
.intro { max-width: 820px; line-height: 1.8; opacity: .86; }
.hero-mark { align-self: center; justify-self: end; width: 150px; height: 150px; display: grid; place-items: center; text-align: center; font-size: 30px; font-weight: 700; line-height: 1.25; border: 1px solid rgba(255,255,255,.3); border-radius: 50%; background: rgba(255,255,255,.1); }
.section-card, .flow-section, .queue-card, .final-notice { margin-top: 20px; }
.section-card h2, .flow-section h2 { margin: 0; }
.section-card p { line-height: 1.8; }
.flow-section { padding: 24px; background: white; border-radius: 12px; }
.section-note { color: #909399; }
.flow-row { display: flex; align-items: stretch; gap: 10px; margin-top: 22px; }
.flow-step { flex: 1; min-width: 0; padding: 18px 12px; border: 1px solid #dfe6f7; border-radius: 10px; color: #303133; background: #f8faff; cursor: pointer; transition: .2s; }
.flow-step:hover { transform: translateY(-3px); border-color: #7892d4; box-shadow: 0 8px 20px rgba(75,103,174,.09); }
.flow-number { display: block; color: #5874be; font-size: 12px; }
.flow-step strong, .flow-step small { display: block; margin-top: 6px; }
.flow-step small { color: #909399; }
.flow-arrow { align-self: center; color: #b6c1df; font-size: 24px; }
.detail-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-top: 20px; }
.detail-card { cursor: pointer; }
.detail-heading { display: flex; gap: 12px; align-items: center; }
.detail-heading span { color: #5874be; font-weight: 700; }
.detail-heading h3 { margin: 0; }
.detail-card p, .detail-card li { line-height: 1.75; }
.detail-actions { display: flex; align-items: center; gap: 22px; margin-top: 12px; }
.tip { color: #606266; background: #f5f7fa; padding: 10px 12px; border-radius: 6px; }
.queue-flow { display: flex; align-items: center; justify-content: center; gap: 14px; flex-wrap: wrap; }
.queue-flow div { padding: 12px 18px; color: #5874be; border-radius: 8px; background: #f5f7fd; }
.queue-flow span { color: #bdc6dd; }
.queue-action { display: flex; justify-content: space-between; align-items: center; margin-top: 20px; color: #606266; }
@media (max-width: 900px) { .hero { grid-template-columns: 1fr; } .hero-mark { display: none; } .flow-row { flex-direction: column; } .flow-arrow { transform: rotate(90deg); } .detail-grid { grid-template-columns: 1fr; } }
</style>
