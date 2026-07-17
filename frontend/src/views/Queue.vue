<template>
  <div>
    <div class="page-head">
      <div>
        <h2>任务队列</h2>
        <p>查看当前所有账号正在运行和等待执行的任务。</p>
      </div>
      <el-button @click="loadQueue" :loading="loading">刷新</el-button>
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col :span="8"><el-statistic title="正在运行" :value="queue.running_count" /></el-col>
      <el-col :span="8"><el-statistic title="排队等待" :value="queue.queued_count" /></el-col>
      <el-col :span="8"><el-statistic title="最大同时任务" :value="queue.max_concurrent" /></el-col>
    </el-row>

    <el-card>
      <el-table :data="queue.jobs" border empty-text="当前没有运行或排队任务">
        <el-table-column label="任务 ID" min-width="360">
          <template #default="{ row }">
            <el-tooltip :content="row.job_id" placement="top">
              <span class="task-id">{{ row.job_id }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column label="任务类型" width="130">
          <template #default="{ row }">{{ typeLabel(row.task_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.state === 'running' ? 'warning' : 'info'">{{ row.state === 'running' ? '运行中' : '排队中' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="排队位置" width="100">
          <template #default="{ row }">{{ row.state === 'queued' ? row.queue_position : '-' }}</template>
        </el-table-column>
        <el-table-column prop="submitted_at" label="提交时间" width="170" />
        <el-table-column prop="started_at" label="开始时间" width="170">
          <template #default="{ row }">{{ row.started_at || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import api from '../api/index.js'

const loading = ref(false)
const queue = ref({ running_count: 0, queued_count: 0, max_concurrent: 0, jobs: [] })
let timer = null

const typeLabel = (type) => ({ synthesis: '数据合成', qc_pre: '合成前质检', qc_post: '合成后质检' }[type] || type)

async function loadQueue() {
  loading.value = true
  try {
    const response = await api.system.queue()
    queue.value = response.data
  } catch (error) {
    console.error('读取任务队列失败', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadQueue()
  timer = window.setInterval(loadQueue, 3000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-head h2 { margin: 0 0 6px; }
.page-head p { margin: 0; color: #909399; }
.summary-row { margin-bottom: 16px; }
.summary-row .el-col { padding-top: 16px; padding-bottom: 16px; text-align: center; background: white; border-radius: 8px; }
.task-id { font-family: Consolas, monospace; font-size: 12px; white-space: nowrap; }
</style>
