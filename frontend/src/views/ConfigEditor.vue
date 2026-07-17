<template>
  <div>
    <h2>配置管理</h2>

    <!-- LLM 全局配置 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>LLM 配置</span>
          <div style="display: flex; gap: 8px">
            <el-upload accept=".yaml,.yml" :show-file-list="false" :before-upload="handleLlmImport">
              <el-button size="small">导入 YAML</el-button>
            </el-upload>
            <el-button size="small" @click="exportLlmYaml">导出 YAML</el-button>
            <el-button type="primary" size="small" @click="saveLlmConfig" :loading="llmSaving">保存</el-button>
          </div>
        </div>
      </template>
      <p style="color: #666; margin-bottom: 12px">配置合成和质检使用的 LLM API。支持多模型负载均衡，可添加多个模型。</p>
      <div v-for="(cfg, i) in llmConfig" :key="i" style="border: 1px solid #e4e7ed; padding: 12px; margin-bottom: 8px; border-radius: 4px">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px">
          <span style="font-weight: 500">模型 {{ i + 1 }}</span>
          <div>
            <el-button type="primary" size="small" plain @click="testLlm(cfg, i)" :loading="llmTestingIndex === i">测试连接</el-button>
            <el-button type="danger" size="small" text @click="llmConfig.splice(i, 1)">删除</el-button>
          </div>
        </div>
        <el-row :gutter="12">
          <el-col :span="8">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">模型名称<el-tooltip content="模型标识符，如 qwen3.5-plus、claude-sonnet-4-6 等" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-input v-model="cfg.model" placeholder="例: qwen3.5-plus" />
          </el-col>
          <el-col :span="8">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">API 地址<el-tooltip content="模型的 API 请求地址，如 https://api.openai.com/v1/chat/completions" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-input v-model="cfg.url" placeholder="例: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" />
          </el-col>
          <el-col :span="8">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">API Key<el-tooltip content="模型的访问密钥，用于身份验证" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-input v-model="cfg.api_key" placeholder="API Key" type="password" show-password />
          </el-col>
        </el-row>
        <el-row :gutter="12" style="margin-top: 8px">
          <el-col :span="4">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">Temperature<el-tooltip content="控制输出的随机性，0 为确定性输出，1 为最大随机性，通常 0.3-0.9" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-input-number v-model="cfg.temperature" :min="0" :max="2" :step="0.1" size="small" style="width: 100%" />
          </el-col>
          <el-col :span="4">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">Max Tokens<el-tooltip content="单次输出的最大 token 数量，影响生成内容的长度上限" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-input-number v-model="cfg.max_tokens" :min="1" :max="8192" size="small" style="width: 100%" />
          </el-col>
          <el-col :span="4">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">Timeout<el-tooltip content="单次 API 请求超时时间（秒），超时后自动重试" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-input-number v-model="cfg.timeout" :min="10" :max="300" size="small" style="width: 100%" />
          </el-col>
          <el-col :span="4">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">流式输出<el-tooltip content="开启后以 SSE 流式方式接收输出，可实时显示生成内容" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-switch v-model="cfg.stream" size="small" />
          </el-col>
          <el-col :span="4">
            <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">思考模式<el-tooltip content="开启后启用模型的思考链（Chain of Thought），提升复杂任务的表现" placement="top"><el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon></el-tooltip></div>
            <el-switch v-model="cfg.enable_thinking" size="small" />
          </el-col>
        </el-row>
      </div>
      <el-button size="small" @click="addLlmModel" style="margin-top: 8px">+ 添加模型</el-button>
    </el-card>

    <!-- Embedding 全局配置 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>Embedding 配置</span>
          <div style="display: flex; gap: 8px">
            <el-button size="small" @click="testEmbedding" :loading="embeddingTesting">测试连接</el-button>
            <el-button type="primary" size="small" @click="saveEmbeddingConfig" :loading="embeddingSaving">保存 Embedding 配置</el-button>
          </div>
        </div>
      </template>
      <p style="color: #666; margin-bottom: 12px">配置 Embedding 模型，用于合成后质检中的文本相似度检测。</p>
      <el-row :gutter="12">
        <el-col :span="8">
          <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">模型名称</div>
          <el-input v-model="embeddingConfig.model" placeholder="例: text-embedding-v3" />
        </el-col>
        <el-col :span="8">
          <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">API 地址</div>
          <el-input v-model="embeddingConfig.url" placeholder="例: https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings" />
        </el-col>
        <el-col :span="8">
          <div style="margin-bottom: 4px; font-size: 13px; font-weight: 500">API Key</div>
          <el-input v-model="embeddingConfig.api_key" placeholder="API Key" type="password" show-password />
        </el-col>
      </el-row>
    </el-card>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import api from '../api/index.js'

const llmConfig = ref([])
const llmSaving = ref(false)
const llmTestingIndex = ref(-1)
const embeddingConfig = ref({ model: '', url: '', api_key: '' })
const embeddingSaving = ref(false)
const embeddingTesting = ref(false)

onMounted(async () => {
  try {
    const llmRes = await api.config.getLlm()
    llmConfig.value = llmRes.data.config || []
    const embRes = await api.config.getEmbedding()
    embeddingConfig.value = embRes.data.config || { model: '', url: '', api_key: '' }
  } catch (e) {
    console.error(e)
  }
})

function addLlmModel() {
  llmConfig.value.push({
    model: '',
    url: '',
    api_key: '',
    temperature: 0.7,
    max_tokens: 512,
    timeout: 60,
    stream: false,
    enable_thinking: false,
  })
}

async function saveLlmConfig() {
  const invalid = llmConfig.value.some(c => !c.model || !c.url || !c.api_key)
  if (invalid) {
    ElMessage.warning('每个模型的名称、API 地址和 API Key 不能为空')
    return
  }
  llmSaving.value = true
  try {
    await api.config.updateLlm(llmConfig.value)
    ElMessage.success('LLM 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    llmSaving.value = false
  }
}

async function testLlm(config, index) {
  if (!config.model || !config.url || !config.api_key) {
    ElMessage.warning('请先填写模型名称、API 地址和 API Key')
    return
  }
  llmTestingIndex.value = index
  try {
    const res = await api.config.testLlm(config)
    const duration = res.data.duration ? `，耗时 ${res.data.duration}s` : ''
    const preview = res.data.response_preview ? `；回复：${res.data.response_preview}` : ''
    ElMessage.success(`LLM 连接成功${duration}${preview}`)
  } catch (e) {
    ElMessage.error('LLM 测试失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    llmTestingIndex.value = -1
  }
}

function exportLlmYaml() {
  const yamlContent = llmConfig.value.map(c => {
    const clean = {}
    for (const [k, v] of Object.entries(c)) {
      if (v !== '' && v !== undefined && v !== false) clean[k] = v
    }
    return clean
  })
  const blob = new Blob([
    yamlContent.map(c => {
      const lines = []
      for (const [k, v] of Object.entries(c)) {
        if (typeof v === 'string' && v.includes(':')) lines.push(`${k}: "${v}"`)
        else lines.push(`${k}: ${v}`)
      }
      return lines.join('\n') + '\n---'
    }).join('\n')
  ], { type: 'text/yaml' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'llm_config.yaml'
  a.click()
  URL.revokeObjectURL(a.href)
}

async function saveEmbeddingConfig() {
  embeddingSaving.value = true
  try {
    await api.config.updateEmbedding(embeddingConfig.value)
    ElMessage.success('Embedding 配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    embeddingSaving.value = false
  }
}

async function testEmbedding() {
  const config = embeddingConfig.value
  if (!config.model || !config.url || !config.api_key) {
    ElMessage.warning('请先填写模型名称、API 地址和 API Key')
    return
  }
  embeddingTesting.value = true
  try {
    const res = await api.config.testEmbedding(config)
    ElMessage.success(`Embedding 连接成功，向量维度 ${res.data.dimensions}`)
  } catch (e) {
    ElMessage.error('Embedding 测试失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    embeddingTesting.value = false
  }
}

async function handleLlmImport(file) {
  try {
    const res = await api.config.parseYaml(file)
    const data = res.data.data
    if (Array.isArray(data)) {
      llmConfig.value = data
      ElMessage.success(`已导入 ${data.length} 个模型配置`)
    } else if (data && Array.isArray(data.config)) {
      llmConfig.value = data.config
      ElMessage.success(`已导入 ${data.config.length} 个模型配置`)
    } else if (data && typeof data === 'object') {
      llmConfig.value = [data]
      ElMessage.success('已导入 1 个模型配置')
    } else {
      ElMessage.warning('YAML 文件格式不正确')
    }
  } catch (e) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail || e.message))
  }
  return false
}
</script>
