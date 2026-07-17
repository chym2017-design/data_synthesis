<template>
  <div>
    <h2>{{ activeTab === 'pre' ? '合成前质检' : '合成后质检' }}</h2>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- 合成前质检 -->
      <el-tab-pane label="合成前质检" name="pre">
        <p style="color: #666; margin-bottom: 16px">检查意图配置的质量，在合成数据之前运行。</p>
        <el-form :model="preForm" label-width="160px">
          <el-form-item label="意图配置">
            <el-select v-model="preForm.intentFile" placeholder="选择意图配置文件" style="width: 100%">
              <el-option v-for="f in intentFiles" :key="f.path" :label="`${f.template} - ${f.path.split('/').pop() || f.path.split('\\').pop()}`" :value="f.path" />
            </el-select>
          </el-form-item>
          <el-form-item label="并行度">
            <el-input-number v-model="preForm.para" :min="1" :max="parallelismMax" />
          </el-form-item>
          <el-form-item label="质检数量">
            <el-input-number v-model="preForm.sampleSize" :min="1" :max="preQcMax" />
            <span style="color: #999; margin-left: 8px">最多检查 {{ preQcMax }} 条</span>
          </el-form-item>
          <el-form-item label="相似度阈值">
            <el-input-number v-model="preForm.similarityThreshold" :min="0.5" :max="1" :step="0.01" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="runPreQC" :loading="preLoading" :disabled="!systemLimits">启动质检</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 合成后质检 -->
      <el-tab-pane label="合成后质检" name="post">
        <p style="color: #666; margin-bottom: 16px">检查已生成数据的质量，需要选择运行输出文件。</p>
        <el-form :model="postForm" label-width="160px">
          <el-form-item label="数据文件">
            <el-select v-model="postForm.dataFile" placeholder="选择数据文件" style="width: 100%">
              <el-option v-for="f in dataFiles" :key="f.path" :label="`${f.run_id} - data.csv`" :value="f.path" />
            </el-select>
          </el-form-item>
          <el-form-item label="意图配置">
            <el-select v-model="postForm.intentFile" placeholder="选择意图配置文件" style="width: 100%">
              <el-option v-for="f in intentFiles" :key="f.path" :label="`${f.template} - ${f.path.split('/').pop() || f.path.split('\\').pop()}`" :value="f.path" />
            </el-select>
          </el-form-item>
          <el-form-item label="采样数量">
            <el-input-number v-model="postForm.sampleSize" :min="1" :max="postQcMax" style="width: 200px" />
            <span style="color: #999; margin-left: 8px">最多检查 {{ postQcMax }} 条</span>
          </el-form-item>
          <el-form-item label="相似度阈值">
            <el-input-number v-model="postForm.similarityThreshold" :min="0.5" :max="1" :step="0.01" />
          </el-form-item>
          <el-form-item label="跳过 Embedding">
            <el-switch v-model="postForm.skipEmbedding" />
          </el-form-item>
          <el-form-item label="跳过 LLM 质检">
            <el-switch v-model="postForm.skipLlm" />
          </el-form-item>
          <el-form-item label="并行度">
            <el-input-number v-model="postForm.para" :min="1" :max="parallelismMax" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="runPostQC" :loading="postLoading" :disabled="!systemLimits">启动质检</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <!-- 当前运行进度 -->
    <el-card v-if="activeQcRun" style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>当前质检: {{ activeQcRun.run_id || '...' }}</span>
          <el-button type="danger" size="small" @click="cancelQC" :loading="cancelling">取消任务</el-button>
        </div>
      </template>

      <!-- 质检步骤指示器 -->
      <div style="margin-bottom: 12px">
        <el-steps :active="qcStepIndex" :space="200" finish-status="success" simple>
          <el-step v-for="s in qcSteps" :key="s.key" :title="s.label" :status="getQcStepStatus(s.key)" />
        </el-steps>
      </div>

      <!-- 当前步骤进度条 -->
      <div style="display: flex; align-items: center; gap: 12px">
        <el-progress :percentage="qcStepPercent" :status="qcProgressStatus" :stroke-width="16" style="flex: 1" />
        <span style="color: #666; font-size: 13px; white-space: nowrap">{{ qcStepText }}</span>
      </div>
      <div style="margin-top: 8px; color: #909399; font-size: 13px">{{ activeQcRun.message }}</div>
      <el-alert v-if="activeQcRun.stage === 'queued'" :title="`排队中：当前位置 ${activeQcRun.queue_position || '-'}，全局等待 ${activeQcRun.queued_count || '-'} 个`" type="info" :closable="false" style="margin-top: 12px" />
    </el-card>

    <!-- 质检结果 -->
    <el-card v-if="showResults" style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>质检结果</span>
          <el-button size="small" @click="clearResults">清除结果</el-button>
        </div>
      </template>

      <!-- 统计摘要 - 环形进度图 -->
      <div style="display: flex; justify-content: center; gap: 40px; margin-bottom: 20px" v-if="qcStats">
        <div style="text-align: center">
          <el-progress type="circle" :percentage="Math.round(qcStats.l1Rate * 100)" :color="qcStats.l1Rate >= 0.9 ? '#67C23A' : '#E6A23C'" :width="100" />
          <div style="margin-top: 8px; font-size: 13px; color: #606266">一级通过率</div>
        </div>
        <div style="text-align: center">
          <el-progress type="circle" :percentage="Math.round(qcStats.l2Rate * 100)" :color="qcStats.l2Rate >= 0.9 ? '#67C23A' : '#E6A23C'" :width="100" />
          <div style="margin-top: 8px; font-size: 13px; color: #606266">二级通过率</div>
        </div>
        <div style="text-align: center">
          <el-progress type="circle" :percentage="Math.round(qcStats.overallRate * 100)" :color="qcStats.overallRate >= 0.9 ? '#67C23A' : '#F56C6C'" :width="100" />
          <div style="margin-top: 8px; font-size: 13px; color: #606266">总体通过率</div>
        </div>
        <div style="text-align: center" v-if="qcStats.preSeverity">
          <el-progress type="circle" :percentage="qcStats.preSeverity.passRate" color="#409EFF" :width="100" />
          <div style="margin-top: 8px; font-size: 13px; color: #606266">菜单通过率</div>
        </div>
      </div>

      <el-tabs v-model="resultTab">
        <el-tab-pane label="LLM 汇总" name="summary" v-if="hasFile('qc_summary_voting.csv')">
          <el-empty v-if="!previewData.qc_summary_voting?.length" description="暂无汇总数据" />
          <template v-else>
            <div style="margin-bottom: 12px">
              <el-input v-model="summaryFilter" placeholder="搜索 Query 或意图..." clearable style="width: 300px" />
            </div>
            <el-table :data="filteredSummary" border size="small" max-height="400">
              <el-table-column label="Query" prop="query" min-width="200" show-overflow-tooltip />
              <el-table-column label="真实一级" prop="true_level1" width="120" />
              <el-table-column label="真实二级" prop="true_level2" width="120" />
              <el-table-column label="一级通过" width="100">
                <template #default="{ row }"><el-tag :type="row.level1_pass ? 'success' : 'danger'" size="small">{{ row.level1_pass ? '通过' : '失败' }} ({{ row.level1_pass_votes }})</el-tag></template>
              </el-table-column>
              <el-table-column label="二级通过" width="100">
                <template #default="{ row }"><el-tag :type="row.level2_pass ? 'success' : 'danger'" size="small">{{ row.level2_pass ? '通过' : '失败' }} ({{ row.level2_pass_votes }})</el-tag></template>
              </el-table-column>
              <el-table-column label="总评" width="80">
                <template #default="{ row }"><el-tag :type="row.overall_pass ? 'success' : 'danger'" size="small">{{ row.overall_pass ? '通过' : '失败' }}</el-tag></template>
              </el-table-column>
              <el-table-column label="失败原因" prop="reason" min-width="180" show-overflow-tooltip />
            </el-table>
          </template>
        </el-tab-pane>

        <el-tab-pane label="LLM 详情" name="detail" v-if="hasFile('qc_detail_by_model.csv')">
          <el-empty v-if="!previewData.qc_detail_by_model?.length" description="暂无详细数据" />
          <el-table v-else :data="previewData.qc_detail_by_model" border size="small" max-height="400">
            <el-table-column label="模型" prop="model" width="120" />
            <el-table-column label="Query" prop="query" min-width="200" show-overflow-tooltip />
            <el-table-column label="真实一级" prop="true_level1" width="120" />
            <el-table-column label="真实二级" prop="true_level2" width="120" />
            <el-table-column label="预测一级" prop="pred_level1" min-width="150" show-overflow-tooltip />
            <el-table-column label="预测二级" prop="pred_level2" min-width="150" show-overflow-tooltip />
            <el-table-column label="一级正确" width="90">
              <template #default="{ row }"><el-tag :type="row.level1_correct ? 'success' : 'danger'" size="small">{{ row.level1_correct ? '是' : '否' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="二级正确" width="90">
              <template #default="{ row }"><el-tag :type="row.level2_correct ? 'success' : 'danger'" size="small">{{ row.level2_correct ? '是' : '否' }}</el-tag></template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="菜单质检" name="quality" v-if="hasFile('quality_check_results.csv')">
          <el-empty v-if="!previewData.quality_check_results?.length" description="暂无菜单质检数据" />
          <template v-else>
            <div style="margin-bottom: 12px">
              <el-select v-model="severityFilter" placeholder="严重度筛选" clearable style="width: 160px">
                <el-option label="无问题" value="none" />
                <el-option label="轻微" value="minor" />
                <el-option label="重要" value="major" />
                <el-option label="严重" value="critical" />
              </el-select>
            </div>
            <el-table :data="filteredQuality" border size="small" max-height="400">
              <el-table-column label="菜单" prop="menu_name" width="120" />
              <el-table-column label="子意图" prop="sub_intent_name" width="140" />
              <el-table-column label="严重度" width="100">
                <template #default="{ row }"><el-tag :type="severityTag(row.severity)" size="small">{{ row.severity }}</el-tag></template>
              </el-table-column>
              <el-table-column label="错别字" prop="typo_issues" min-width="120" show-overflow-tooltip />
              <el-table-column label="一致性" prop="consistency_issues" min-width="120" show-overflow-tooltip />
              <el-table-column label="质量问题" prop="quality_issues" min-width="120" show-overflow-tooltip />
              <el-table-column label="建议" prop="suggestion" min-width="200" show-overflow-tooltip />
            </el-table>
          </template>
        </el-tab-pane>

        <el-tab-pane label="相似菜单" name="similarity" v-if="hasFile('similarity_check_results.csv')">
          <el-empty v-if="!previewData.similarity_check_results?.length" description="未发现相似菜单" />
          <el-table v-else :data="previewData.similarity_check_results" border size="small" max-height="400">
            <el-table-column label="菜单A" prop="menu_a" width="160" />
            <el-table-column label="菜单B" prop="menu_b" width="160" />
            <el-table-column label="相似度" width="100"><template #default="{ row }">{{ row.similarity_score?.toFixed?.(4) || row.similarity_score }}</template></el-table-column>
            <el-table-column label="是否混淆" width="100">
              <template #default="{ row }"><el-tag :type="row.is_confusable ? 'danger' : 'info'" size="small">{{ row.is_confusable ? '是' : '否' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="原因" prop="reason" min-width="200" show-overflow-tooltip />
            <el-table-column label="建议" prop="suggestion" min-width="200" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Embedding 相似" name="embedding" v-if="hasFile('embedding_similarity_check.csv')">
          <el-empty v-if="!previewData.embedding_similarity_check?.length" description="未发现相似语料" />
          <el-table v-else :data="previewData.embedding_similarity_check" border size="small" max-height="400">
            <el-table-column label="Query A" prop="query_a" min-width="200" show-overflow-tooltip />
            <el-table-column label="Query B" prop="query_b" min-width="200" show-overflow-tooltip />
            <el-table-column label="意图 A" prop="intent_a" width="120" />
            <el-table-column label="意图 B" prop="intent_b" width="120" />
            <el-table-column label="相似度" width="100"><template #default="{ row }">{{ row.similarity?.toFixed?.(4) || row.similarity }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <!-- 下载按钮 -->
      <div style="margin-top: 12px">
        <el-button v-for="f in qcResultFiles" :key="f" size="small" @click="downloadFile(f)">下载 {{ f }}</el-button>
      </div>
    </el-card>

    <!-- 质检历史 -->
    <el-card v-if="qcHistory.length > 0" style="margin-top: 16px">
      <template #header><span>质检历史</span></template>
      <el-table :data="qcHistory" border>
        <el-table-column prop="run_id" label="ID" width="100" />
        <el-table-column prop="type" label="类型" width="130">
          <template #default="{ row }"><el-tag :type="row.type === 'pre' ? 'primary' : 'warning'" size="small">{{ qcTypeLabel(row.type) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="stage" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="qcStageTag(row.stage)" size="small">{{ qcStageLabel(row.stage) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="信息" min-width="150" show-overflow-tooltip />
        <el-table-column label="排队位置" width="90">
          <template #default="{ row }">{{ row.stage === 'queued' ? (row.queue_position || '-') : '-' }}</template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" width="160" />
        <el-table-column label="文件" min-width="120">
          <template #default="{ row }">
            <span v-if="row.files?.length">{{ row.files.join(', ') }}</span>
            <span v-else style="color: #999">无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button v-if="row.stage === 'done'" size="small" @click="viewQcResult(row)">查看</el-button>
            <el-button v-if="row.stage === 'error' || row.stage === 'cancelled' || row.stage === 'interrupted'" size="small" type="warning" @click="retryQC(row)">重试</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'
import { usePolling } from '../composables/usePolling.js'

// ========== 页面级状态 ==========
const route = useRoute()
const router = useRouter()
const activeTab = ref(route.meta.qcTab === 'post' ? 'post' : 'pre')
const resultTab = ref('summary')
const preLoading = ref(false)
const postLoading = ref(false)
const showResults = ref(false)
const previewData = ref({})
const qcResultFiles = ref([])
const qcStats = ref(null)
const intentFiles = ref([])
const dataFiles = ref([])
const cancelling = ref(false)
const summaryFilter = ref('')
const severityFilter = ref('')
const systemLimits = ref(null)
const preQcMax = computed(() => systemLimits.value?.task_items?.qc_pre || 1)
const postQcMax = computed(() => systemLimits.value?.task_items?.qc_post || 1)
const parallelismMax = computed(() => systemLimits.value?.model_parallelism?.max || 1)

// 当前 QC 类型: 'pre' | 'post'
const currentQcType = ref('')

const preForm = ref({
  intentFile: '',
  para: 1,
  sampleSize: 1,
  similarityThreshold: 0.7,
})

const postForm = ref({
  dataFile: '',
  intentFile: '',
  sampleSize: 1,
  similarityThreshold: 0.95,
  skipEmbedding: false,
  skipLlm: false,
  para: 1,
})

// ========== 质检历史 ==========
const qcHistory = ref([])

// ========== 轮询 ==========
const activeQcRun = ref(null)
const currentQcRunId = ref(null)

const { start: startPolling, stop: stopPolling } = usePolling(
  async (runId) => {
    const res = await api.qc.status(runId)
    activeQcRun.value = res.data
    await loadQcHistory()
    return res.data
  },
  {
    interval: 3000,
    onDone: async (result) => {
      if (result.stage === 'done' && result.files?.length) {
        currentQcRunId.value = result.run_id
        await loadQcResults(result.run_id, result.files)
      }
      await loadQcHistory()
    },
  }
)

async function loadQcHistory() {
  try {
    const res = await api.qc.list()
    qcHistory.value = res.data.runs || []
  } catch (e) {
    console.error(e)
  }
}

async function viewQcResult(row) {
  currentQcRunId.value = row.run_id
  if (row.files?.length) {
    await loadQcResults(row.run_id, row.files)
  }
}

async function loadQcResults(runId, files) {
  previewData.value = {}
  qcResultFiles.value = files || []
  currentQcRunId.value = runId
  showResults.value = true

  for (const f of files) {
    try {
      const base = f.replace('.csv', '')
      const res = await api.files.preview(runId, f)
      if (res.data?.preview) {
        previewData.value[base] = res.data.preview
      }
    } catch (e) {
      console.error(`Failed to preview ${f}:`, e)
    }
  }

  // Compute stats
  const summary = previewData.value.qc_summary_voting
  const quality = previewData.value.quality_check_results
  if (summary?.length) {
    qcStats.value = {
      total: summary.length,
      l1Rate: summary.filter(r => r.level1_pass === true || r.level1_pass === 'True').length / summary.length,
      l2Rate: summary.filter(r => r.level2_pass === true || r.level2_pass === 'True').length / summary.length,
      overallRate: summary.filter(r => r.overall_pass === true || r.overall_pass === 'True').length / summary.length,
    }
  } else if (quality?.length) {
    // 预检统计：严重度分布
    const sevMap = { none: 0, minor: 0, major: 0, critical: 0 }
    quality.forEach(r => { if (sevMap[r.severity] !== undefined) sevMap[r.severity]++ })
    const totalSev = Math.max(Object.values(sevMap).reduce((a, b) => a + b, 0), 1)
    qcStats.value = {
      total: quality.length,
      l1Rate: sevMap.none / totalSev,
      l2Rate: (sevMap.none + sevMap.minor) / totalSev,
      overallRate: sevMap.none / totalSev,
      preSeverity: { passRate: Math.round(sevMap.none / totalSev * 100) },
    }
  } else {
    qcStats.value = null
  }
}

function clearResults() {
  showResults.value = false
  previewData.value = {}
  qcResultFiles.value = []
  currentQcRunId.value = null
  resultTab.value = 'summary'
}

function onTabChange() {
  const target = activeTab.value === 'post' ? '/qc/post' : '/qc/pre'
  if (route.path !== target) router.replace(target)
  if (!activeQcRun.value) {
    clearResults()
  }
}

watch(() => route.meta.qcTab, (tab) => {
  activeTab.value = tab === 'post' ? 'post' : 'pre'
})

// ========== 质检步骤指示器 ==========
const postQcSteps = [
  { key: 'embedding', label: 'Embedding 相似度' },
  { key: 'llm_level1', label: '一级意图判断' },
  { key: 'llm_level2', label: '二级意图判断' },
  { key: 'llm_summary', label: '投票汇总' },
]
const preQcSteps = [
  { key: 'quality_check', label: '菜单质检' },
  { key: 'similarity_check', label: '相似菜单检测' },
]

const qcSteps = computed(() => {
  return currentQcType.value === 'pre' ? preQcSteps : postQcSteps
})

const qcStepIndex = computed(() => {
  if (!activeQcRun.value) return 0
  const stage = activeQcRun.value.stage
  const steps = qcSteps.value
  if (stage === 'starting') return 1
  const idx = steps.findIndex(s => s.key === stage)
  if (idx >= 0) return idx + 1
  if (stage === 'done') return steps.length
  if (stage === 'error' || stage === 'cancelled') return steps.length
  return 0
})

const qcStepPercent = computed(() => {
  if (!activeQcRun.value) return 0
  if (activeQcRun.value.stage === 'starting') return 0
  return Math.round((activeQcRun.value.progress || 0) * 100)
})

const qcStepText = computed(() => {
  if (!activeQcRun.value) return ''
  const s = activeQcRun.value.stage
  if (s === 'starting') return '准备中...'
  const total = activeQcRun.value.total || 0
  const current = activeQcRun.value.current || 0
  if (total > 0) return `${current}/${total}`
  return ''
})

function getQcStepStatus(key) {
  if (!activeQcRun.value) return 'wait'
  const stage = activeQcRun.value.stage
  if (stage === 'done') return 'success'
  if (stage === 'error' || stage === 'cancelled') return 'error'
  if (stage === 'starting') {
    const steps = qcSteps.value
    return key === steps[0]?.key ? 'process' : 'wait'
  }
  const steps = qcSteps.value
  const idx = steps.findIndex(s => s.key === stage)
  const keyIdx = steps.findIndex(s => s.key === key)
  if (keyIdx < idx) return 'success'
  if (keyIdx === idx) return 'process'
  return 'wait'
}

const qcProgressStatus = computed(() => {
  if (!activeQcRun.value) return ''
  const s = activeQcRun.value.stage
  if (s === 'done') return 'success'
  if (s === 'error' || s === 'cancelled') return 'exception'
  return ''
})

// ========== 过滤器 ==========
const filteredSummary = computed(() => {
  const data = previewData.value.qc_summary_voting || []
  if (!summaryFilter.value) return data
  const kw = summaryFilter.value.toLowerCase()
  return data.filter(r =>
    (r.query || '').toLowerCase().includes(kw) ||
    (r.true_level1 || '').toLowerCase().includes(kw) ||
    (r.true_level2 || '').toLowerCase().includes(kw)
  )
})

const filteredQuality = computed(() => {
  const data = previewData.value.quality_check_results || []
  if (!severityFilter.value) return data
  return data.filter(r => r.severity === severityFilter.value)
})

// ========== 工具函数 ==========
function hasFile(name) {
  return qcResultFiles.value.some(f => {
    const fbasename = f.split('/').pop().split('\\').pop()
    return fbasename === name
  })
}

function severityTag(severity) {
  const map = { none: 'success', minor: 'info', major: 'warning', critical: 'danger' }
  return map[severity] || 'info'
}

function qcStageTag(stage) {
  const map = { done: 'success', error: 'danger', cancelled: 'danger', queued: 'info', starting: 'warning', quality_check: 'warning', similarity_check: 'warning', embedding: 'warning', llm_qc: 'warning', llm_level1: 'warning', llm_level2: 'warning', llm_summary: 'warning' }
  return map[stage] || 'info'
}

function qcStageLabel(stage) {
  const map = { done: '完成', error: '失败', cancelled: '已取消', queued: '排队中', starting: '启动中', quality_check: '菜单质检', similarity_check: '相似检测', embedding: 'Embedding', llm_qc: 'LLM 质检', llm_level1: '一级意图', llm_level2: '二级意图', llm_summary: '投票汇总' }
  return map[stage] || stage
}

function qcTypeLabel(type) {
  const map = { pre: '合成前质检', post: '合成后质检' }
  return map[type] || '未知类型'
}

// ========== 生命周期 ==========
onMounted(async () => {
  showResults.value = false
  previewData.value = {}
  await loadSystemLimits()
  await loadAvailableFiles()
  await loadQcHistory()
  const running = qcHistory.value.find(r => !['done', 'error', 'cancelled'].includes(r.stage))
  if (running) {
    activeQcRun.value = running
    currentQcType.value = running.type || ''
    startPolling(running.run_id)
  }
})

async function loadSystemLimits() {
  try {
    const res = await api.system.limits()
    systemLimits.value = res.data
    preForm.value.sampleSize = res.data.task_items.qc_pre
    postForm.value.sampleSize = res.data.task_items.qc_post
    preForm.value.para = res.data.model_parallelism.default
    postForm.value.para = res.data.model_parallelism.default
  } catch (e) {
    console.error(e)
    ElMessage.error('读取系统任务限制失败，请刷新页面或联系管理员')
  }
}

async function loadAvailableFiles() {
  try {
    const res = await api.qc.availableFiles()
    intentFiles.value = res.data.intent_json || []
    dataFiles.value = res.data.data_csv || []
  } catch (e) {
    console.error(e)
  }
}

// ========== 启动质检 ==========
async function runPreQC() {
  if (!systemLimits.value) {
    ElMessage.warning('系统任务限制尚未加载')
    return
  }
  if (!preForm.value.intentFile) {
    ElMessage.warning('请选择意图配置文件')
    return
  }
  if (preForm.value.sampleSize > preQcMax.value) {
    ElMessage.warning(`质检数量不能超过 ${preQcMax.value} 条`)
    return
  }
  if (preForm.value.para > parallelismMax.value) {
    ElMessage.warning(`并行度不能超过 ${parallelismMax.value}`)
    return
  }
  preLoading.value = true
  try {
    const res = await api.qc.preCheck({
      intent_file: preForm.value.intentFile,
      para: preForm.value.para,
      sample_size: preForm.value.sampleSize,
      similarity_threshold: preForm.value.similarityThreshold,
    })
    currentQcType.value = 'pre'
    activeQcRun.value = { run_id: res.data.run_id, stage: res.data.status || 'queued', progress: 0, message: res.data.message }
    ElMessage.success('质检任务已提交')
    startPolling(res.data.run_id)
  } catch (e) {
    ElMessage.error('质检失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    preLoading.value = false
  }
}

async function runPostQC() {
  if (!systemLimits.value) {
    ElMessage.warning('系统任务限制尚未加载')
    return
  }
  if (!postForm.value.dataFile) {
    ElMessage.warning('请选择数据文件')
    return
  }
  if (!postForm.value.intentFile) {
    ElMessage.warning('请选择意图配置文件')
    return
  }
  if (postForm.value.sampleSize > postQcMax.value) {
    ElMessage.warning(`质检数量不能超过 ${postQcMax.value} 条`)
    return
  }
  if (postForm.value.para > parallelismMax.value) {
    ElMessage.warning(`并行度不能超过 ${parallelismMax.value}`)
    return
  }
  postLoading.value = true
  try {
    const params = {
      data_file: postForm.value.dataFile,
      intent_file: postForm.value.intentFile,
      skip_embedding: postForm.value.skipEmbedding,
      skip_llm: postForm.value.skipLlm,
      para: postForm.value.para,
      similarity_threshold: postForm.value.similarityThreshold,
    }
    if (postForm.value.sampleSize) {
      params.sample_size = postForm.value.sampleSize
    }
    const res = await api.qc.postCheck(params)
    currentQcType.value = 'post'
    activeQcRun.value = { run_id: res.data.run_id, stage: res.data.status || 'queued', progress: 0, message: res.data.message }
    ElMessage.success('质检任务已提交')
    startPolling(res.data.run_id)
  } catch (e) {
    ElMessage.error('质检失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    postLoading.value = false
  }
}

// ========== 取消 & 重试 ==========
async function cancelQC() {
  if (!activeQcRun.value?.run_id) return
  cancelling.value = true
  try {
    await api.qc.cancel(activeQcRun.value.run_id)
    stopPolling()
    ElMessage.success('已发送取消请求')
  } catch (e) {
    ElMessage.error('取消失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    cancelling.value = false
  }
}

async function retryQC(row) {
  clearResults()
  if (row.type === 'pre') {
    preLoading.value = true
    try {
      const res = await api.qc.retry(row.run_id)
      currentQcType.value = 'pre'
      activeQcRun.value = { run_id: res.data.run_id, stage: 'starting', progress: 0, message: res.data.message }
      ElMessage.success('重试任务已提交')
      startPolling(res.data.new_run_id)
    } catch (e) {
      ElMessage.error('重试失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      preLoading.value = false
    }
  } else {
    postLoading.value = true
    try {
      const res = await api.qc.retry(row.run_id)
      currentQcType.value = 'post'
      activeQcRun.value = { run_id: res.data.run_id, stage: 'starting', progress: 0, message: res.data.message }
      ElMessage.success('重试任务已提交')
      startPolling(res.data.new_run_id)
    } catch (e) {
      ElMessage.error('重试失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      postLoading.value = false
    }
  }
}

function downloadFile(filename) {
  const url = api.files.download(currentQcRunId.value || 'qc_results', filename)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}
</script>
