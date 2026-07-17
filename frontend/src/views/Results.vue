<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <div>
        <el-input v-model="searchQuery" placeholder="搜索 run_id..." clearable style="width: 240px" />
      </div>
      <el-button @click="loadRuns" :loading="loadingRuns">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <div v-if="filteredRuns.length === 0" style="margin-top: 40px">
      <el-empty description="暂无结果文件，请先运行合成或质检任务" />
    </div>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreview" :title="previewTitle" width="95%" top="3vh">
      <div v-if="previewLoading" style="text-align: center; padding: 40px">
        <el-icon size="40" class="is-loading"><Loading /></el-icon>
        <p style="color: #999; margin-top: 12px">加载中...</p>
      </div>
      <div v-else-if="previewData.type === 'csv'">
        <div style="margin-bottom: 8px; color: #909399; font-size: 13px">
          共 {{ previewData.total_rows }} 行，当前显示前 {{ previewData.preview.length }} 行
        </div>
        <el-table :data="previewData.preview" border size="small" max-height="70vh" style="width: 100%">
          <el-table-column v-for="col in previewData.columns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
      <div v-else-if="previewData.type === 'jsonl'">
        <div style="margin-bottom: 8px; color: #909399; font-size: 13px">
          共 {{ previewData.total_rows }} 条，当前显示前 {{ previewData.preview.length }} 条
        </div>
        <div v-for="(item, idx) in previewData.preview" :key="idx" style="border: 1px solid #e4e7ed; border-radius: 4px; padding: 12px; margin-bottom: 8px; background: #fafafa">
          <div style="font-size: 12px; color: #909399; margin-bottom: 4px">#{{ idx + 1 }}</div>
          <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 13px; font-family: 'Courier New', monospace; max-height: 300px; overflow-y: auto">{{ formatJsonLine(item) }}</pre>
        </div>
      </div>
      <div v-else-if="previewData.type === 'json'">
        <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 13px; font-family: 'Courier New', monospace; max-height: 70vh; overflow-y: auto">{{ JSON.stringify(previewData.preview, null, 2) }}</pre>
      </div>
      <template #footer>
        <el-button type="primary" @click="downloadFile(previewRunId, previewFilename)">下载完整文件</el-button>
        <el-button @click="showPreview = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-card v-for="run in filteredRuns" :key="run.run_id + run.task_type" style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>
            <el-tag :type="run.task_type === 'qc' ? 'warning' : 'primary'" size="small" style="margin-right: 8px">{{ run.task_type === 'qc' ? '质检' : '合成' }}</el-tag>
            运行 {{ run.run_id }}
          </span>
          <div style="display: flex; gap: 8px; align-items: center">
            <el-tag size="small">{{ run.files.length }} 个文件</el-tag>
            <el-button type="danger" size="small" text @click="deleteRun(run)">删除</el-button>
          </div>
        </div>
      </template>

      <el-table v-if="run.files.length > 0" :data="run.files" border>
        <el-table-column prop="name" label="文件名" />
        <el-table-column prop="type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag(row.type)">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="size" label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button v-if="canPreview(row.type)" size="small" @click="openPreview(run.run_id, row.name)">预览</el-button>
            <el-button size="small" @click="downloadFile(run.run_id, row.name)">下载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Loading, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index.js'

const runs = ref([])
const searchQuery = ref('')
const loadingRuns = ref(false)
const showPreview = ref(false)
const previewLoading = ref(false)
const previewTitle = ref('')
const previewData = ref({})
const previewRunId = ref('')
const previewFilename = ref('')

const filteredRuns = computed(() => {
  if (!searchQuery.value) return runs.value
  return runs.value.filter(r => r.run_id.includes(searchQuery.value))
})

onMounted(loadRuns)

async function loadRuns() {
  loadingRuns.value = true
  try {
    const res = await api.files.listRuns()
    const rawRuns = res.data.runs || []
    runs.value = rawRuns.map(r => ({
      ...r,
      task_type: r.dir?.startsWith('qc_results') ? 'qc' : 'synthesis',
    }))
  } catch (e) {
    console.error(e)
  } finally {
    loadingRuns.value = false
  }
}

async function deleteRun(run) {
  try {
    await ElMessageBox.confirm(`确定删除运行 "${run.run_id}" 的所有文件？`, '确认删除', { type: 'warning' })
    await api.files.deleteRun(run.run_id)
    ElMessage.success('已删除')
    await loadRuns()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

function canPreview(type) {
  return ['csv', 'jsonl', 'json'].includes(type)
}

async function openPreview(runId, filename) {
  previewRunId.value = runId
  previewFilename.value = filename
  previewTitle.value = `${filename}`
  showPreview.value = true
  previewLoading.value = true
  try {
    const res = await api.files.preview(runId, filename)
    previewData.value = res.data
  } catch (e) {
    ElMessage.error('预览失败: ' + (e.response?.data?.detail || e.message))
    previewData.value = {}
  } finally {
    previewLoading.value = false
  }
}

function downloadFile(runId, filename) {
  const url = api.files.download(runId, filename)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function typeTag(type) {
  const map = { csv: 'success', jsonl: '', json: 'warning', yaml: 'info' }
  return map[type] || 'info'
}

function formatJsonLine(item) {
  if (typeof item === 'string') return item
  return JSON.stringify(item, null, 2)
}
</script>
