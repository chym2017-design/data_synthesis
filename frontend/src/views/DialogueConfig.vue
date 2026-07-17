<template>
  <div>
    <h2>对话配置</h2>
    <p style="color: #666; margin-bottom: 20px">控制语气分布、心情、情绪词池等对话风格参数。</p>

    <!-- 语气分布 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>语气分布</span>
          <el-button size="small" @click="redistributeTone">概率重分布</el-button>
        </div>
      </template>
      <el-table :data="toneList" border size="small">
        <el-table-column label="语气" width="160">
          <template #default="{ row }">{{ row.label }}</template>
        </el-table-column>
        <el-table-column label="概率">
          <template #default="{ row }">
            <el-tooltip :content="toneTooltips[row.key]" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-right: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
            <el-input-number v-model="tones[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" />
          </template>
        </el-table-column>
        <el-table-column label="占比">
          <template #default="{ row }">{{ tonePercent(row.key) }}</template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 8px">
        当前总和: <span :style="{ color: Math.abs(toneSum - 1) > 0.01 ? '#f56c6c' : '#67c23a' }">{{ toneSum.toFixed(4) }}</span>
        <span v-if="Math.abs(toneSum - 1) > 0.01" style="color: #999; margin-left: 8px; font-size: 12px">（非 1.0 不影响保存，点击概率重分布可归一化）</span>
      </div>
    </el-card>

    <!-- 心情控制 -->
    <el-card style="margin-top: 16px">
      <template #header><span>心情控制</span></template>
      <el-form label-width="140px" size="small">
        <el-form-item>
          <template #label>
            心情触发概率
            <el-tooltip content="多少比例的样本会附加用户心情描述" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <el-input-number v-model="moodProb" :min="0" :max="1" :step="0.01" size="small" />
          <span style="margin-left: 12px; color: #666">{{ (moodProb * 100).toFixed(1) }}% 的样本会附加用户心情</span>
        </el-form-item>
        <el-form-item>
          <template #label>
            情绪词池
            <el-tooltip content="可用于附加心情的情绪词列表，新增后参与随机选取" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <div style="margin-bottom: 8px">
            <el-tag v-for="(emo, i) in emotions" :key="i" closable @close="emotions.splice(i, 1)" style="margin: 4px">
              {{ emo }}
            </el-tag>
          </div>
          <el-input v-model="newEmotion" placeholder="输入新情绪词后回车" style="width: 200px; margin-right: 8px" @keyup.enter="addEmotion" />
          <el-button size="small" @click="addEmotion">添加</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 生成预览 -->
    <el-card style="margin-top: 16px">
      <template #header><span>生成预览</span></template>
      <p style="color: #666; margin-bottom: 12px; font-size: 13px">根据当前配置随机生成语气 + 心情组合的效果预览。</p>
      <el-button @click="generatePreview" size="small">重新生成</el-button>
      <div v-if="preview" style="margin-top: 12px; padding: 12px; background: #f5f5f5; border-radius: 4px">
        <div><strong>语气:</strong> {{ preview.tone }}</div>
        <div v-if="preview.mood"><strong>心情:</strong> {{ preview.mood }}</div>
        <div style="margin-top: 8px"><strong>最终注入文本:</strong></div>
        <div style="color: #409eff; font-family: monospace; margin-top: 4px">{{ preview.combined }}</div>
      </div>
    </el-card>

    <!-- 意图跳转概率 -->
    <el-card style="margin-top: 16px">
      <template #header><span>意图跳转概率</span></template>
      <el-form label-width="200px" size="small">
        <el-divider style="margin: 0 0 12px">一级分支</el-divider>
        <el-form-item>
          <template #label>
            单意图概率
            <el-tooltip content="对话只涉及一个意图，不发生跳转的绝对概率。修改后多意图概率自动联动（两者和为 1）" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <el-input-number v-model="transition.singleIntentProb" :min="0" :max="1" :step="0.01" size="small" style="width: 160px" @change="linkSingleToMulti" />
          <span style="margin-left: 12px; color: #666">{{ (transition.singleIntentProb * 100).toFixed(1) }}%</span>
        </el-form-item>
        <el-form-item>
          <template #label>
            多意图概率
            <el-tooltip content="对话涉及多个意图的绝对概率。修改后单意图概率自动联动（两者和为 1）" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <el-input-number v-model="transition.multiIntentProb" :min="0" :max="1" :step="0.01" size="small" style="width: 160px" @change="linkMultiToSingle" />
          <span style="margin-left: 12px; color: #666">{{ (transition.multiIntentProb * 100).toFixed(1) }}%</span>
        </el-form-item>

        <el-divider style="margin: 0 0 12px">多意图内细分</el-divider>
        <el-form-item>
          <template #label>
            同意图多子意图
            <el-tooltip content="多意图条件下，在同一意图内涉及多个子意图的条件概率。修改后跨意图概率自动联动（两者和为 1）" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <el-input-number v-model="transition.sameIntentMultiSubintent" :min="0" :max="1" :step="0.01" size="small" style="width: 160px" @change="linkSameToCross" />
          <span style="margin-left: 12px; color: #666">
            {{ (transition.sameIntentMultiSubintent * 100).toFixed(1) }}%（总概率 {{ (transition.multiIntentProb * transition.sameIntentMultiSubintent * 100).toFixed(1) }}%）
          </span>
        </el-form-item>
        <el-form-item>
          <template #label>
            跨意图跳转
            <el-tooltip content="多意图条件下，在不同意图之间跳转的条件概率。修改后同意图概率自动联动（两者和为 1）" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <el-input-number v-model="transition.crossIntentJump" :min="0" :max="1" :step="0.01" size="small" style="width: 160px" @change="linkCrossToSame" />
          <span style="margin-left: 12px; color: #666">
            {{ (transition.crossIntentJump * 100).toFixed(1) }}%（总概率 {{ (transition.multiIntentProb * transition.crossIntentJump * 100).toFixed(1) }}%）
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 对话轮数分布 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>对话轮数分布</span>
          <el-button size="small" @click="redistributeRound">概率重分布</el-button>
        </div>
      </template>
      <el-tabs v-model="roundTab">
        <el-tab-pane label="同意图" name="single">
          <el-table :data="rounds.singleIntentRound" border size="small">
            <el-table-column label="轮数" width="100">
              <template #default="{ row }">{{ row[0] }} 轮</template>
            </el-table-column>
            <el-table-column label="概率">
              <template #default="{ row }">
                <el-tooltip :content="`同意图场景下对话持续 ${row[0]} 轮的概率`" placement="top">
                  <el-icon style="cursor: pointer; color: #909399; margin-right: 4px"><QuestionFilled /></el-icon>
                </el-tooltip>
                <el-input-number v-model="row[1]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" />
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 8px">
            当前总和: <span :style="{ color: Math.abs(singleRoundSum - 1) > 0.01 ? '#f56c6c' : '#67c23a' }">{{ singleRoundSum.toFixed(4) }}</span>
          </div>
        </el-tab-pane>
        <el-tab-pane label="跨意图" name="multi">
          <el-table :data="rounds.multiIntentRound" border size="small">
            <el-table-column label="轮数" width="100">
              <template #default="{ row }">{{ row[0] }} 轮</template>
            </el-table-column>
            <el-table-column label="概率">
              <template #default="{ row }">
                <el-tooltip :content="`跨意图场景下对话持续 ${row[0]} 轮的概率`" placement="top">
                  <el-icon style="cursor: pointer; color: #909399; margin-right: 4px"><QuestionFilled /></el-icon>
                </el-tooltip>
                <el-input-number v-model="row[1]" :min="0" :max="1" :step="0.01" size="small" style="width: 140px" />
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 8px">
            当前总和: <span :style="{ color: Math.abs(multiRoundSum - 1) > 0.01 ? '#f56c6c' : '#67c23a' }">{{ multiRoundSum.toFixed(4) }}</span>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 意图切换约束 -->
    <el-card style="margin-top: 16px">
      <template #header><span>意图切换约束</span></template>
      <el-form label-width="200px">
        <el-form-item>
          <template #label>
            终止轮切换比例
            <el-tooltip content="起始与目标子意图不一致时，在最后一轮才切换意图的样本比例" placement="top">
              <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <el-input-number v-model="transitionConstraint.switchAtTerminalTurnRatio" :min="0" :max="1" :step="0.01" size="small" style="width: 160px" />
          <span style="margin-left: 12px; color: #666">{{ (transitionConstraint.switchAtTerminalTurnRatio * 100).toFixed(1) }}%</span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 单轮比例 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <span>单轮对话比例
          <el-tooltip content="多少比例的样本为单轮对话（只有一个回合）" placement="top">
            <el-icon style="cursor: pointer; color: #909399; margin-left: 4px"><QuestionFilled /></el-icon>
          </el-tooltip>
        </span>
      </template>
      <el-input-number v-model="singleRoundRatio" :min="0" :max="1" :step="0.01" size="small" />
      <span style="margin-left: 12px; color: #666">{{ (singleRoundRatio * 100).toFixed(1) }}% 的样本为单轮对话</span>
    </el-card>

    <div style="margin-top: 20px">
      <el-button type="primary" @click="saveAll" :loading="saving">保存所有配置</el-button>
      <el-button type="warning" plain @click="restoreDefault" :loading="restoring">恢复默认</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import api from '../api/index.js'

const tones = ref({
  '祈使句': 0.60,
  '问句': 0.15,
  '反问句': 0.10,
  '倒装句': 0.05,
  '长短复合句': 0.05,
  '带错别字的请求': 0.05,
})

const toneTooltips = {
  '祈使句': '以请求、命令语气发起对话的样本比例',
  '问句': '以疑问句形式发起对话的样本比例',
  '反问句': '使用反问句式表达肯定或否定态度的样本比例',
  '倒装句': '使用倒装语序（如宾语前置）的样本比例',
  '长短复合句': '包含长短句交替、多从句的复合句样本比例',
  '带错别字的请求': '用户输入中包含错别字的样本比例，模拟真实用户打字习惯',
}

const moodProb = ref(0.3)
const emotions = ref(['兴奋', '开心', '愉快', '平静', '沮丧', '悲伤', '愤怒', '焦虑'])
const newEmotion = ref('')
const singleRoundRatio = ref(0.05)
const preview = ref(null)
const saving = ref(false)
const restoring = ref(false)

const transition = ref({
  singleIntentProb: 0.3,
  multiIntentProb: 0.7,
  sameIntentMultiSubintent: 0.8,
  crossIntentJump: 0.2,
})

const transitionConstraint = ref({
  switchAtTerminalTurnRatio: 0.2,
})

const rounds = ref({
  singleIntentRound: [[1, 0.3], [2, 0.3], [3, 0.3], [4, 0.1]],
  multiIntentRound: [[2, 0.25], [3, 0.5], [4, 0.1], [5, 0.1], [6, 0.05]],
})

const roundTab = ref('single')

const singleRoundSum = computed(() => rounds.value.singleIntentRound.reduce((a, b) => a + b[1], 0))
const multiRoundSum = computed(() => rounds.value.multiIntentRound.reduce((a, b) => a + b[1], 0))

const toneList = computed(() => Object.keys(tones.value).map(key => ({ key, label: key })))

const toneSum = computed(() => Object.values(tones.value).reduce((a, b) => a + b, 0))

function tonePercent(key) {
  const total = toneSum.value
  if (total === 0) return '0.0%'
  return ((tones.value[key] / total) * 100).toFixed(1) + '%'
}

function redistributeTone() {
  const keys = Object.keys(tones.value)
  const total = Object.values(tones.value).reduce((a, b) => a + b, 0)
  if (total === 0) {
    const eq = 1 / keys.length
    keys.forEach(k => { tones.value[k] = eq })
  } else {
    keys.forEach(k => { tones.value[k] = tones.value[k] / total })
  }
  ElMessage.success('已重分布，总和=1.0')
}

function redistributeRound() {
  const tab = roundTab.value
  const items = tab === 'single' ? rounds.value.singleIntentRound : rounds.value.multiIntentRound
  const total = items.reduce((a, b) => a + b[1], 0)
  if (total === 0) {
    const eq = 1 / items.length
    items.forEach(item => { item[1] = eq })
  } else {
    items.forEach(item => { item[1] = item[1] / total })
  }
  ElMessage.success('已重分布轮数概率，总和=1.0')
}

function linkSingleToMulti() {
  transition.value.multiIntentProb = +(1 - transition.value.singleIntentProb).toFixed(10)
}

function linkMultiToSingle() {
  transition.value.singleIntentProb = +(1 - transition.value.multiIntentProb).toFixed(10)
}

function linkSameToCross() {
  transition.value.crossIntentJump = +(1 - transition.value.sameIntentMultiSubintent).toFixed(10)
}

function linkCrossToSame() {
  transition.value.sameIntentMultiSubintent = +(1 - transition.value.crossIntentJump).toFixed(10)
}

onMounted(async () => {
  try {
    const res = await api.config.get('bank_intent', 'synth_config')
    const sc = res.data.content
    if (sc.tone_distribution) tones.value = { ...sc.tone_distribution }
    if (sc.mood) {
      if (sc.mood.probability !== undefined) moodProb.value = sc.mood.probability
      if (sc.mood.emotions && sc.mood.emotions.length) emotions.value = [...sc.mood.emotions]
    }
    if (sc.single_round_ratio !== undefined) singleRoundRatio.value = sc.single_round_ratio
    transition.value.singleIntentProb = sc.intent_transition?.single_intent_prob ?? 0.3
    transition.value.multiIntentProb = 1 - transition.value.singleIntentProb
    transition.value.sameIntentMultiSubintent = sc.intent_transition?.same_intent_multi_subintent_ratio ?? 0.8
    transition.value.crossIntentJump = 1 - transition.value.sameIntentMultiSubintent
    transitionConstraint.value.switchAtTerminalTurnRatio = sc.intent_transition_constraint?.switch_at_terminal_turn_ratio ?? 0.2
    rounds.value.singleIntentRound = sc.round_distribution?.single_intent?.map(x => [...x]) ?? [[1, 0.3], [2, 0.3], [3, 0.3], [4, 0.1]]
    rounds.value.multiIntentRound = sc.round_distribution?.multi_intent?.map(x => [...x]) ?? [[2, 0.25], [3, 0.5], [4, 0.1], [5, 0.1], [6, 0.05]]
  } catch (e) {
    console.error(e)
  }
})

function addEmotion() {
  const v = newEmotion.value.trim()
  if (v && !emotions.value.includes(v)) {
    emotions.value.push(v)
    newEmotion.value = ''
  }
}

function generatePreview() {
  const toneKeys = Object.keys(tones.value)
  const toneVals = Object.values(tones.value)
  const total = toneVals.reduce((a, b) => a + b, 0)
  let rand = Math.random() * total
  let cumulative = 0
  let selectedTone = toneKeys[0]
  for (let i = 0; i < toneVals.length; i++) {
    cumulative += toneVals[i]
    if (rand < cumulative) {
      selectedTone = toneKeys[i]
      break
    }
  }

  let mood = ''
  if (Math.random() < moodProb.value) {
    mood = emotions.value[Math.floor(Math.random() * emotions.value.length)]
  }

  let combined = selectedTone
  if (mood) {
    combined = `${selectedTone}，用户当前的心理状态为${mood}`
  }

  preview.value = { tone: selectedTone, mood, combined }
}

async function saveAll() {
  saving.value = true
  try {
    const res = await api.config.get('bank_intent', 'synth_config')
    const sc = res.data.content
    sc.tone_distribution = { ...tones.value }
    sc.mood = { probability: moodProb.value, emotions: [...emotions.value] }
    sc.single_round_ratio = singleRoundRatio.value
    sc.intent_transition = {
      single_intent_prob: transition.value.singleIntentProb,
      same_intent_multi_subintent_ratio: transition.value.sameIntentMultiSubintent,
      cross_intent_jump: transition.value.crossIntentJump,
    }
    sc.intent_transition_constraint = {
      switch_at_terminal_turn_ratio: transitionConstraint.value.switchAtTerminalTurnRatio,
    }
    sc.round_distribution = {
      single_intent: rounds.value.singleIntentRound,
      multi_intent: rounds.value.multiIntentRound,
    }
    await api.config.update('bank_intent', 'synth_config', sc)
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function restoreDefault() {
  try {
    await ElMessageBox.confirm(
      '将清除当前用户保存的对话配置，并恢复内置默认值。此操作不能撤销。是否继续？',
      '恢复默认对话配置',
      { confirmButtonText: '恢复默认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  restoring.value = true
  try {
    await api.config.restoreDefault('bank_intent', 'synth_config')
    ElMessage.success('对话配置已恢复默认')
    window.location.reload()
  } catch (e) {
    ElMessage.error('恢复失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    restoring.value = false
  }
}
</script>
