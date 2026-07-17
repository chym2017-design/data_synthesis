<template>
  <div>
    <h2>合成任务</h2>

    <el-card style="margin-top: 16px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="选择模板">
          <el-select v-model="form.templateName" placeholder="请选择模板" style="width: 300px">
            <el-option v-for="t in templates" :key="t.name" :label="t.name" :value="t.name" />
          </el-select>
          <span v-if="!templates.length" style="color: #999; margin-left: 12px">
            暂无可用模板
          </span>
          <el-link type="primary" href="#/intent-config" style="margin-left: 12px">意图配置</el-link>
          <el-link type="primary" href="#/dialogue-config" style="margin-left: 12px">对话配置</el-link>
          <el-link type="primary" href="#/profile-control" style="margin-left: 12px">用户画像</el-link>
        </el-form-item>

        <el-form-item label="样本数量">
          <el-input-number v-model="form.numSamples" :min="1" :max="synthesisMax" style="width: 200px" />
          <span style="color: #909399; margin-left: 8px">每次最多 {{ synthesisMax }} 条</span>
        </el-form-item>

        <el-form-item label="并行度">
          <el-input-number v-model="form.para" :min="1" :max="parallelismMax" style="width: 200px" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="startSynthesis" :loading="submitting" :disabled="!form.templateName || !systemLimits">
            启动合成
          </el-button>
          <span v-if="llmNotConfigured" style="color: #f56c6c; margin-left: 12px">
            未配置 LLM，请先在「配置管理」设置 LLM API
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 当前运行进度 -->
    <el-card v-if="activeRun" style="margin-top: 16px">
      <template #header>
        <span>当前运行: {{ activeRun.run_id || '...' }}</span>
      </template>

      <!-- 流水线步骤指示器 -->
      <div style="margin-bottom: 12px">
        <el-steps :active="currentStepIndex" :space="200" finish-status="success" simple>
          <el-step v-for="s in pipelineSteps" :key="s.key" :title="s.label" :status="getStepStatus(s.key)" />
        </el-steps>
      </div>

      <!-- 当前步骤进度条 -->
      <div style="display: flex; align-items: center; gap: 12px">
        <el-progress :percentage="stepProgressPercent" :status="progressStatus" :stroke-width="16" style="flex: 1" />
        <span style="color: #666; font-size: 13px; white-space: nowrap">{{ stepProgressText }}</span>
      </div>
      <div style="margin-top: 8px; color: #909399; font-size: 13px">{{ activeRun.message }}</div>
      <el-alert v-if="activeRun.stage === 'queued'" :title="`排队中：当前位置 ${activeRun.queue_position || '-'}，全局等待 ${activeRun.queued_count || '-'} 个`" type="info" :closable="false" style="margin-top: 12px" />
    </el-card>

    <!-- 历史任务 -->
    <el-card v-if="runHistory.length > 0" style="margin-top: 16px">
      <template #header><span>历史任务</span></template>
      <el-table :data="runHistory" border>
        <el-table-column prop="run_id" label="ID" width="100" />
        <el-table-column prop="stage" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="stageTag(row.stage)" size="small">{{ stageLabel(row.stage) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="信息" min-width="200" show-overflow-tooltip />
        <el-table-column label="排队位置" width="90">
          <template #default="{ row }">{{ row.stage === 'queued' ? (row.queue_position || '-') : '-' }}</template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" width="160" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button v-if="row.has_files" size="small" @click="$router.push('/results')">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'

// ========== 轮询状态 ==========
import { usePolling } from '../composables/usePolling.js'

const activeRun = ref(null)
const runHistory = ref([])

const { start: startPolling } = usePolling(
  async (runId) => {
    const res = await api.synthesis.status(runId)
    activeRun.value = res.data
    await loadHistory()
    return res.data
  },
  {
    interval: 3000,
    onDone: () => loadHistory(),
  }
)

async function loadHistory() {
  try {
    const res = await api.synthesis.list()
    runHistory.value = res.data.runs || []
    const running = runHistory.value.find(r => ['queued', 'starting', 'generating', 'calling_llm', 'filtering', 'exporting'].includes(r.stage))
    if (running && !activeRun.value) {
      activeRun.value = running
      startPolling(running.run_id)
    }
  } catch (e) {
    console.error(e)
  }
}

// ========== 页面级状态 ==========
const templates = ref([])
const submitting = ref(false)
const llmNotConfigured = ref(false)
const systemLimits = ref(null)
const synthesisMax = computed(() => systemLimits.value?.task_items?.synthesis || 1)
const parallelismMax = computed(() => systemLimits.value?.model_parallelism?.max || 1)

const form = ref({
  templateName: '',
  numSamples: 1,
  para: 1,
})

// ========== 流水线步骤 ==========
const pipelineSteps = [
  { key: 'generating', label: '生成样本' },
  { key: 'calling_llm', label: 'LLM 调用' },
  { key: 'filtering', label: '格式过滤' },
  { key: 'exporting', label: '数据导出' },
]

const progressStatus = computed(() => {
  if (!activeRun.value) return ''
  const s = activeRun.value.stage
  if (s === 'done') return 'success'
  if (s === 'error' || s === 'interrupted') return 'exception'
  return ''
})

const currentStepIndex = computed(() => {
  if (!activeRun.value) return 0
  const stage = activeRun.value.stage
  const idx = pipelineSteps.findIndex(s => s.key === stage)
  if (idx >= 0) return idx + 1
  if (stage === 'done' || stage === 'exporting') return pipelineSteps.length
  if (stage === 'error' || stage === 'interrupted') return pipelineSteps.length
  // starting / initializing: 第 0 步正在准备中
  if (stage === 'starting' || stage === 'initialized') return 1
  return 0
})

const stepProgressPercent = computed(() => {
  if (!activeRun.value) return 0
  const stage = activeRun.value.stage
  if (stage === 'starting' || stage === 'initialized') return 0
  const p = activeRun.value.progress || 0
  return Math.round(p * 100)
})

const stepProgressText = computed(() => {
  if (!activeRun.value) return ''
  const stage = activeRun.value.stage
  if (stage === 'starting' || stage === 'initialized') return '准备中...'
  const total = activeRun.value.total || 0
  const current = activeRun.value.current || 0
  if (total > 0) return `${current}/${total}`
  return ''
})

function getStepStatus(key) {
  if (!activeRun.value) return 'wait'
  const stage = activeRun.value.stage
  if (stage === 'done') return 'success'
  if (stage === 'error' || stage === 'interrupted') return 'error'
  // starting 阶段：第一步显示 process，其余 wait
  if (stage === 'starting' || stage === 'initialized') {
    return key === 'generating' ? 'process' : 'wait'
  }
  const idx = pipelineSteps.findIndex(s => s.key === stage)
  const keyIdx = pipelineSteps.findIndex(s => s.key === key)
  if (keyIdx < idx) return 'success'
  if (keyIdx === idx) return 'process'
  return 'wait'
}

function stageTag(stage) {
  const map = { done: 'success', error: 'danger', interrupted: 'danger', queued: 'info', starting: 'warning', generating: 'warning', calling_llm: 'warning', filtering: 'info', exporting: 'info' }
  return map[stage] || 'info'
}

function stageLabel(stage) {
  const map = { done: '完成', error: '失败', interrupted: '中断', queued: '排队中', starting: '准备中', generating: '生成中', calling_llm: 'LLM调用中', filtering: '过滤中', exporting: '导出中' }
  return map[stage] || stage
}

onMounted(async () => {
  await loadSystemLimits()
  await loadTemplates()
  await checkLlmConfig()
  await loadHistory()
  const running = runHistory.value.find(r => ['queued', 'starting', 'generating', 'calling_llm', 'filtering', 'exporting'].includes(r.stage))
  if (running) {
    activeRun.value = running
  }
})

async function loadSystemLimits() {
  try {
    const res = await api.system.limits()
    systemLimits.value = res.data
    form.value.numSamples = res.data.task_items.synthesis
    form.value.para = res.data.model_parallelism.default
  } catch (e) {
    console.error(e)
    ElMessage.error('读取系统任务限制失败，请刷新页面或联系管理员')
  }
}

async function loadTemplates() {
  try {
    const res = await api.templates.list()
    templates.value = res.data || []
    if (templates.value.length > 0 && !form.value.templateName) {
      form.value.templateName = templates.value[0].name
    }
  } catch (e) {
    console.error(e)
  }
}

async function checkLlmConfig() {
  try {
    const res = await api.config.getLlm()
    llmNotConfigured.value = !res.data.config || res.data.config.length === 0
  } catch {
    llmNotConfigured.value = true
  }
}

async function startSynthesis() {
  if (!systemLimits.value) {
    ElMessage.warning('系统任务限制尚未加载')
    return
  }
  if (!form.value.templateName) {
    ElMessage.warning('请选择模板')
    return
  }
  if (form.value.numSamples > synthesisMax.value) {
    ElMessage.warning(`合成数量不能超过 ${synthesisMax.value} 条`)
    return
  }
  if (form.value.para > parallelismMax.value) {
    ElMessage.warning(`并行度不能超过 ${parallelismMax.value}`)
    return
  }
  submitting.value = true
  try {
    const res = await api.synthesis.start({
      template_name: form.value.templateName,
      num_samples: form.value.numSamples,
      para: form.value.para,
    })
    // 立即设置 activeRun，显示 run_id 和进度
    activeRun.value = {
      run_id: res.data.run_id,
      stage: res.data.status || 'queued',
      total: form.value.numSamples,
      current: 0,
      progress: 0,
      message: res.data.message,
    }
    ElMessage.success('合成任务已提交')
    startPolling(res.data.run_id)
  } catch (e) {
    ElMessage.error('启动失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}
</script>
