<template>
  <div style="display: flex; height: 100vh">
    <!-- 侧边栏 -->
    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapsed"
      router
      style="border-right: 1px solid #e4e7ed; overflow-y: auto"
      background-color="#1d39c4"
      text-color="#e8eaf6"
      active-text-color="#ffffff"
    >
      <!-- Logo / 标题 -->
      <div style="padding: 16px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.15)">
        <span v-if="!isCollapsed" style="color: #fff; font-size: 16px; font-weight: 600; white-space: nowrap">数据合成引擎</span>
        <span v-else style="color: #fff; font-size: 18px">DS</span>
      </div>

      <!-- 折叠按钮 -->
      <div style="padding: 8px; text-align: center; border-bottom: 1px solid rgba(255,255,255,0.15)">
        <el-button text @click="isCollapsed = !isCollapsed" style="color: #e8eaf6; font-size: 18px">
          <el-icon><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
        </el-button>
      </div>

      <!-- 导航菜单 -->
      <el-menu-item index="/guide">
        <el-icon><House /></el-icon>
        <template #title>使用指南</template>
      </el-menu-item>

      <el-sub-menu index="configs">
        <template #title>
          <el-icon><Setting /></el-icon>
          <span>模板配置</span>
        </template>
        <el-menu-item index="/dialogue-config">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>对话配置</template>
        </el-menu-item>
        <el-menu-item index="/intent-config">
          <el-icon><Grid /></el-icon>
          <template #title>意图配置</template>
        </el-menu-item>
        <el-menu-item index="/profile-control">
          <el-icon><User /></el-icon>
          <template #title>用户画像</template>
        </el-menu-item>
        <el-menu-item index="/prompt-preview">
          <el-icon><View /></el-icon>
          <template #title>Prompt 预览</template>
        </el-menu-item>
      </el-sub-menu>

      <el-menu-item index="/qc/pre">
        <el-icon><Checked /></el-icon>
        <template #title>合成前质检</template>
      </el-menu-item>

      <el-menu-item index="/synthesis">
        <el-icon><Promotion /></el-icon>
        <template #title>数据合成</template>
      </el-menu-item>

      <el-menu-item index="/qc/post">
        <el-icon><Checked /></el-icon>
        <template #title>合成后质检</template>
      </el-menu-item>

      <el-menu-item index="/queue">
        <el-icon><List /></el-icon>
        <template #title>任务队列</template>
      </el-menu-item>

      <el-menu-item index="/results">
        <el-icon><FolderOpened /></el-icon>
        <template #title>结果查看</template>
      </el-menu-item>

      <el-menu-item index="/config">
        <el-icon><Tools /></el-icon>
        <template #title>配置管理</template>
      </el-menu-item>

    </el-menu>

    <!-- 主内容区 -->
    <div style="flex: 1; display: flex; flex-direction: column; overflow: hidden">
      <!-- 面包屑 -->
      <div style="padding: 12px 20px; background: #fff; border-bottom: 1px solid #e4e7ed; flex-shrink: 0; display: flex; justify-content: space-between; align-items: center">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div style="display: flex; gap: 16px; color: #606266; font-size: 13px; align-items: center">
          <span>用户：{{ userInfo.username || '读取中' }}</span>
          <span v-if="userInfo.workspace_id">空间：{{ userInfo.workspace_id }}</span>
          <el-button text type="primary" size="small" @click="router.push('/queue')">
            运行 {{ queueInfo.running_count }}/{{ queueInfo.max_concurrent }} · 排队 {{ queueInfo.queued_count }}
          </el-button>
          <el-button text type="danger" size="small" @click="logout">
            <el-icon><SwitchButton /></el-icon>退出登录
          </el-button>
        </div>
      </div>

      <!-- 页面内容 -->
      <div style="flex: 1; overflow-y: auto; padding: 20px; background: #f5f7fa">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import api from './api/index.js'
import {
  Promotion, Checked, Setting, ChatDotRound, Grid, User, View,
  Tools, FolderOpened, Fold, Expand, House, List, SwitchButton
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const isCollapsed = ref(false)
const userInfo = ref({ username: '', workspace_id: '' })
const queueInfo = ref({ running_count: 0, queued_count: 0, max_concurrent: 0 })
let queueTimer = null

async function loadSystemInfo() {
  try {
    const [me, queue] = await Promise.all([api.system.me(), api.system.queue()])
    userInfo.value = me.data
    queueInfo.value = queue.data
  } catch (e) {
    console.error('读取用户或队列信息失败', e)
  }
}

onMounted(() => {
  loadSystemInfo()
  queueTimer = window.setInterval(loadSystemInfo, 3000)
})
onUnmounted(() => {
  if (queueTimer) window.clearInterval(queueTimer)
})

const activeMenu = computed(() => route.path.startsWith('/guide/') ? '/guide' : route.path)

async function logout() {
  try {
    await ElMessageBox.confirm(
      '退出后浏览器将尝试清除当前登录信息，并重新要求输入账号密码。',
      '退出登录',
      { confirmButtonText: '退出', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await fetch('/logout', { credentials: 'include', cache: 'no-store' })
  } finally {
    window.location.replace(`/synth/?logout=${Date.now()}`)
  }
}

const pageTitle = computed(() => {
  const map = {
    '/guide': '使用指南',
    '/guide/pre-qc': '合成前质检详情',
    '/guide/synthesis': '数据合成详情',
    '/guide/post-qc': '合成后质检详情',
    '/synthesis': '数据合成',
    '/qc/pre': '合成前质检',
    '/qc/post': '合成后质检',
    '/config': '配置管理',
    '/results': '结果查看',
    '/queue': '任务队列',
    '/dialogue-config': '对话配置',
    '/intent-config': '意图配置',
    '/profile-control': '用户画像',
    '/prompt-preview': 'Prompt 预览',
  }
  return map[route.path] || ''
})
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f7fa;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.el-menu {
  border-right: none !important;
}

.el-menu-item.is-active {
  background-color: rgba(255,255,255,0.15) !important;
}

.el-card {
  border-radius: 8px !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}

.el-card__header {
  padding: 14px 20px !important;
  border-bottom: 1px solid #ebeef5 !important;
}

.el-button--primary {
  background-color: #1d39c4 !important;
  border-color: #1d39c4 !important;
}

.el-button--primary:hover {
  background-color: #2b4ad4 !important;
  border-color: #2b4ad4 !important;
}
</style>
