<template>
  <div>
    <h2>Prompt 预览</h2>
    <p style="color: #666; margin-bottom: 20px">查看 Prompt 模板内容，模拟变量填充后预览最终 Prompt。</p>

    <el-tabs v-model="promptTab" @tab-change="loadPrompt">
      <el-tab-pane label="单轮对话" name="single_round" />
      <el-tab-pane label="多轮对话" name="multi_round" />
    </el-tabs>

    <!-- 模板原文 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>模板原文（变量用 {{}} 包裹）</span>
          <el-tag size="small">{{ promptFile }}</el-tag>
        </div>
      </template>
      <div style="margin-bottom: 8px">
        <span style="color: #999; font-size: 12px">
          可用变量:
          <el-tag v-for="v in availableVars" :key="v" size="small" style="margin: 2px">{{ v }}</el-tag>
        </span>
      </div>
      <el-input
        v-model="promptText"
        type="textarea"
        :rows="18"
        style="font-family: monospace; font-size: 13px"
      />
      <div v-if="loadError" style="color: #f56c6c; margin-top: 8px">{{ loadError }}</div>
    </el-card>

    <!-- 变量模拟值 -->
    <el-card style="margin-top: 16px">
      <template #header><span>模拟变量值（编辑后可实时预览）</span></template>
      <el-form label-width="180px" size="small">
        <el-form-item label="user_profile">
          <el-input v-model="mockVars.user_profile" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="intent_1 / intent_2">
          <el-row :gutter="8">
            <el-col :span="12"><el-input v-model="mockVars.intent_1" placeholder="起始意图" /></el-col>
            <el-col :span="12"><el-input v-model="mockVars.intent_2" placeholder="目标意图" /></el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="sub_intent_1 / sub_intent_2">
          <el-row :gutter="8">
            <el-col :span="12"><el-input v-model="mockVars.sub_intent_1" placeholder="起始子意图" /></el-col>
            <el-col :span="12"><el-input v-model="mockVars.sub_intent_2" placeholder="目标子意图" /></el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="sub_intent_desc_1 / desc_2">
          <el-row :gutter="8">
            <el-col :span="12"><el-input v-model="mockVars.sub_intent_desc_1" placeholder="起始描述" /></el-col>
            <el-col :span="12"><el-input v-model="mockVars.sub_intent_desc_2" placeholder="目标描述" /></el-col>
          </el-row>
        </el-form-item>
        <el-row :gutter="8">
          <el-col :span="8">
            <el-form-item label="round"><el-input v-model="mockVars.round" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="num_sen"><el-input v-model="mockVars.num_sen" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="yuqi"><el-input v-model="mockVars.yuqi" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="menu_list">
          <el-input v-model="mockVars.menu_list" type="textarea" :rows="2" placeholder="菜单列表（通常为空）" />
        </el-form-item>
        <el-form-item label="intent_transition_constraint">
          <el-input v-model="mockVars.intent_transition_constraint" type="textarea" :rows="2" placeholder="意图切换约束（通常为空）" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 预览结果 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>最终 Prompt 预览</span>
          <el-button size="small" @click="copyPreview">复制到剪贴板</el-button>
        </div>
      </template>
      <pre style="background: #f5f5f5; padding: 16px; border-radius: 4px; white-space: pre-wrap; word-break: break-word; max-height: 600px; overflow-y: auto; font-size: 13px; line-height: 1.6">{{ previewText }}</pre>
    </el-card>

    <!-- 变量统计 -->
    <el-card style="margin-top: 16px">
      <template #header><span>变量填充状态</span></template>
      <el-row :gutter="16">
        <el-col :span="8">
          <div style="text-align: center; padding: 12px; background: #f0f9ff; border-radius: 4px">
            <div style="color: #999">模板中变量数</div>
            <div style="font-size: 24px; font-weight: bold; color: #409eff">{{ varsInTemplate.length }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div style="text-align: center; padding: 12px; background: #f0f9ff; border-radius: 4px">
            <div style="color: #999">已填充</div>
            <div style="font-size: 24px; font-weight: bold; color: #67c23a">{{ filledVars.length }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div style="text-align: center; padding: 12px; background: #f0f9ff; border-radius: 4px">
            <div style="color: #999">未填充</div>
            <div style="font-size: 24px; font-weight: bold" :style="{ color: unfilledVars.length > 0 ? '#f56c6c' : '#67c23a' }">{{ unfilledVars.length }}</div>
          </div>
        </el-col>
      </el-row>
      <div v-if="unfilledVars.length > 0" style="margin-top: 12px; color: #f56c6c; font-size: 13px">
        未填充变量: {{ unfilledVars.join(', ') }}
      </div>
      <div v-if="varsInTemplate.length > 0 && unfilledVars.length === 0" style="margin-top: 12px; color: #67c23a; font-size: 13px">
        所有变量均已填充
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'

const promptTab = ref('multi_round')
const promptText = ref('')
const promptFile = ref('')
const loadError = ref('')

const mockVars = ref({
  user_profile: `### 用户基本信息
- 姓名：张三
- 性别：男
- 年龄：35岁
- 职业：IT工程师
- 常住城市：北京
- 客户层级：优质

### 资产总览
- 总资产：150,000.00元
- 总负债：30,000.00元
- 净资产：120,000.00元`,
  intent_1: 'i豆',
  intent_2: '理财',
  sub_intent_1: '查i豆',
  sub_intent_2: '理财产品推荐',
  sub_intent_desc_1: '查询当前i豆余额',
  sub_intent_desc_2: '根据用户风险偏好推荐理财产品',
  round: '三',
  num_sen: '六',
  yuqi: '祈使句，用户当前的心理状态为焦虑',
  menu_list: '',
  intent_transition_constraint: '',
})

const availableVars = [
  'user_profile', 'intent_1', 'intent_2', 'sub_intent_1', 'sub_intent_2',
  'sub_intent_desc_1', 'sub_intent_desc_2', 'round', 'num_sen', 'yuqi',
  'menu_list', 'intent_transition_constraint',
]

const varsInTemplate = computed(() => {
  const matches = promptText.value.match(/\{\{(\w+)\}\}/g) || []
  return [...new Set(matches.map(m => m.slice(2, -2)))]
})

const filledVars = computed(() => {
  return varsInTemplate.value.filter(v => mockVars.value[v]?.trim())
})

const unfilledVars = computed(() => {
  return varsInTemplate.value.filter(v => !mockVars.value[v]?.trim())
})

const previewText = computed(() => {
  let result = promptText.value
  for (const [key, value] of Object.entries(mockVars.value)) {
    result = result.replaceAll(`{{${key}}}`, value || '')
  }
  return result
})

onMounted(() => {
  loadPrompt()
})

async function loadPrompt() {
  loadError.value = ''
  promptText.value = '加载中...'
  try {
    const res = await api.templates.getPrompt('bank_intent', promptTab.value)
    promptText.value = res.data.content
    promptFile.value = res.data.file
  } catch (e) {
    loadError.value = '加载失败: ' + (e.response?.data?.detail || e.message)
    promptText.value = ''
  }
}

function copyPreview() {
  navigator.clipboard.writeText(previewText.value)
  ElMessage.success('已复制到剪贴板')
}
</script>
