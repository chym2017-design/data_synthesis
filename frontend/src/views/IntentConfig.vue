<template>
  <div>
    <h2>意图配置</h2>
    <p style="color: #666; margin-bottom: 20px">基于 intent.json 管理意图定义、子意图、权重和示例对话。</p>

    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>意图列表</span>
          <div>
            <el-button size="small" @click="exportJson">导出 JSON</el-button>
            <el-button size="small" type="warning" @click="showImportDialog = true">导入 JSON</el-button>
            <el-button size="small" type="primary" @click="addIntent">新增意图</el-button>
          </div>
        </div>
      </template>

      <el-collapse v-model="expandedIntents">
        <el-collapse-item v-for="(intent, name) in intents" :key="name" :name="name">
          <template #title>
            <div style="display: flex; align-items: center; width: 100%; gap: 12px" @click.stop>
              <strong style="min-width: 100px">{{ name }}</strong>
              <span style="color: #999; font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
                {{ intent.description || '暂无描述' }}
              </span>
              <el-tag size="small" type="info">权重: {{ intent.weight ?? 1 }}</el-tag>
              <el-tag size="small">子意图: {{ intent.sub_intent?.length || 0 }}</el-tag>
              <el-tag v-if="intent.true_sub_intent" size="small" type="success">真子意图</el-tag>
            </div>
          </template>

          <!-- 意图编辑表单 -->
          <el-form label-width="120px" size="small">
            <el-form-item label="意图名称">
              <el-input v-model="intent.name_cache" :disabled="true" />
              <span style="color: #999; font-size: 12px; margin-left: 8px">名称不可修改</span>
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="intent.description" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="权重">
              <el-tooltip content="意图被选中的相对权重，值越大越容易被选中" placement="top">
                <el-icon style="cursor: pointer; color: #909399"><QuestionFilled /></el-icon>
              </el-tooltip>
              <el-input-number v-model="intent.weight" :min="0" :max="10" :step="0.1" style="margin-left: 8px" />
            </el-form-item>
            <el-form-item label="真子意图">
              <el-tooltip content="开启后子意图会作为独立意图参与跳转，否则仅在父意图内部流转" placement="top">
                <el-icon style="cursor: pointer; color: #909399"><QuestionFilled /></el-icon>
              </el-tooltip>
              <el-switch v-model="intent.true_sub_intent" style="margin-left: 8px" />
            </el-form-item>
          </el-form>

          <!-- 子意图列表 -->
          <div style="margin-top: 8px">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
              <strong>子意图</strong>
              <el-button size="small" @click="addSubIntent(name)">新增子意图</el-button>
            </div>
            <el-table :data="intent.sub_intent" border size="small">
              <el-table-column label="名称" min-width="140">
                <template #default="{ row }">
                  <el-input v-model="row.name" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="描述" min-width="300">
                <template #default="{ row }">
                  <el-input v-model="row.description" size="small" type="textarea" :rows="2" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button size="small" type="danger" text @click="removeSubIntent(name, $index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 示例对话 -->
          <div style="margin-top: 16px">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
              <strong>示例对话</strong>
              <el-button size="small" @click="addExample(name)">新增示例</el-button>
            </div>
            <el-table :data="intent.example" border size="small">
              <el-table-column label="关联子意图" width="160">
                <template #default="{ row }">
                  <el-select v-model="row['子意图']" size="small" style="width: 100%">
                    <el-option v-for="si in intent.sub_intent" :key="si.name" :label="si.name" :value="si.name" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="示例内容" min-width="300">
                <template #default="{ row }">
                  <el-input v-model="row['示例']" size="small" type="textarea" :rows="4" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button size="small" type="danger" text @click="removeExample(name, $index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <div style="margin-top: 20px">
      <el-button type="primary" @click="saveAll" :loading="saving">保存所有配置</el-button>
      <el-button type="warning" plain @click="restoreDefault" :loading="restoring">恢复默认</el-button>
    </div>

    <!-- JSON 导入对话框 -->
    <el-dialog v-model="showImportDialog" title="导入 JSON" width="700px" :close-on-click-modal="false">
      <div style="margin-bottom: 12px; color: #666; font-size: 13px">
        粘贴 intent.json 格式内容，支持两种格式：<br>
        1. 完整格式 <code style="color: #409eff">{ "intent": { ... } }</code><br>
        2. 纯 intent 对象 <code style="color: #409eff">{ "i豆": { ... }, "理财": { ... } }</code>
      </div>
      <el-input
        v-model="importText"
        type="textarea"
        :rows="18"
        placeholder='{"i豆": {"weight": 1, "description": "...", "true_sub_intent": true, "sub_intent": [...], "example": [...]}}'
        style="font-family: monospace; font-size: 13px"
      />
      <div v-if="importError" style="color: #f56c6c; margin-top: 8px">{{ importError }}</div>
      <template #footer>
        <el-button @click="showImportDialog = false; importError = ''">取消</el-button>
        <el-button type="warning" @click="importJson">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import api from '../api/index.js'

const intents = ref({})
const expandedIntents = ref([])
const saving = ref(false)
const restoring = ref(false)
const showImportDialog = ref(false)
const importText = ref('')
const importError = ref('')

onMounted(async () => {
  try {
    const res = await api.config.get('bank_intent', 'intent')
    const data = res.data.content

    if (data.intent) {
      for (const [name, cfg] of Object.entries(data.intent)) {
        intents.value[name] = {
          ...cfg,
          name_cache: name,
          sub_intent: (cfg.sub_intent || []).map(si => ({ ...si })),
          example: (cfg.example || []).map(ex => ({ ...ex })),
        }
      }
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载配置失败')
  }
})

function parseIntentData(raw) {
  // Support both {"intent": {...}} and direct intent object
  let intentMap = raw
  if (raw.intent) {
    intentMap = raw.intent
  }
  const result = {}
  for (const [name, cfg] of Object.entries(intentMap)) {
    result[name] = {
      name_cache: name,
      weight: cfg.weight ?? 1,
      description: cfg.description || '',
      true_sub_intent: cfg.true_sub_intent ?? false,
      sub_intent: (cfg.sub_intent || []).map(si => ({ ...si })),
      example: (cfg.example || []).map(ex => ({ ...ex })),
    }
  }
  return result
}

function importJson() {
  importError.value = ''
  const text = importText.value.trim()
  if (!text) {
    importError.value = '请输入 JSON 内容'
    return
  }
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      importError.value = 'JSON 格式不正确，需要是一个对象'
      return
    }
    const data = parseIntentData(parsed)
    const count = Object.keys(data).length
    if (count === 0) {
      importError.value = '未解析到任何意图'
      return
    }
    intents.value = data
    expandedIntents.value = Object.keys(data)
    showImportDialog.value = false
    importText.value = ''
    ElMessage.success(`已导入 ${count} 个意图`)
  } catch (e) {
    importError.value = 'JSON 解析失败: ' + e.message
  }
}

function exportJson() {
  const output = { intent: {} }
  for (const [name, cfg] of Object.entries(intents.value)) {
    const { name_cache, ...rest } = cfg
    output.intent[name] = {
      ...rest,
      sub_intent: cfg.sub_intent.map(si => ({ ...si })),
      example: cfg.example.map(ex => ({ ...ex })),
    }
  }
  const json = JSON.stringify(output, null, 4)
  navigator.clipboard.writeText(json)
  const count = Object.keys(intents.value).length
  ElMessage.success(`已复制 ${count} 个意图的 JSON 到剪贴板`)
}

function addIntent() {
  ElMessageBox.prompt('请输入新意图名称', '新增意图', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /.+/,
    inputErrorMessage: '名称不能为空',
  }).then(({ value }) => {
    if (intents.value[value]) {
      ElMessage.warning('该意图已存在')
      return
    }
    intents.value[value] = {
      name_cache: value,
      description: '',
      weight: 1,
      true_sub_intent: false,
      sub_intent: [],
      example: [],
    }
    expandedIntents.value = [...expandedIntents.value, value]
    ElMessage.success('已添加意图')
  }).catch(() => {})
}

function addSubIntent(intentName) {
  intents.value[intentName].sub_intent.push({ name: '', description: '' })
}

function removeSubIntent(intentName, index) {
  intents.value[intentName].sub_intent.splice(index, 1)
}

function addExample(intentName) {
  intents.value[intentName].example.push({ '子意图': '', '示例': '' })
}

function removeExample(intentName, index) {
  intents.value[intentName].example.splice(index, 1)
}

async function saveAll() {
  saving.value = true
  try {
    const intentData = { intent: {} }
    for (const [name, cfg] of Object.entries(intents.value)) {
      const { name_cache, ...rest } = cfg
      intentData.intent[name] = {
        ...rest,
        sub_intent: cfg.sub_intent.map(si => ({ ...si })),
        example: cfg.example.map(ex => ({ ...ex })),
      }
    }
    await api.config.update('bank_intent', 'intent', intentData)
    ElMessage.success('意图配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function restoreDefault() {
  try {
    await ElMessageBox.confirm(
      '将使用内置 intent.json 覆盖当前用户的全部意图修改，此操作不能撤销。是否继续？',
      '恢复默认意图配置',
      { confirmButtonText: '恢复默认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  restoring.value = true
  try {
    await api.config.restoreDefault('bank_intent', 'intent')
    ElMessage.success('意图配置已恢复默认')
    window.location.reload()
  } catch (e) {
    ElMessage.error('恢复失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    restoring.value = false
  }
}
</script>
