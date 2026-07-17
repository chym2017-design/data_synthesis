import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/guide' },
  { path: '/guide', component: () => import('../views/Guide.vue') },
  { path: '/guide/pre-qc', component: () => import('../views/GuideDetail.vue'), meta: { guideType: 'pre' } },
  { path: '/guide/synthesis', component: () => import('../views/GuideDetail.vue'), meta: { guideType: 'synthesis' } },
  { path: '/guide/post-qc', component: () => import('../views/GuideDetail.vue'), meta: { guideType: 'post' } },
  { path: '/synthesis', component: () => import('../views/Synthesis.vue') },
  { path: '/qc', redirect: '/qc/pre' },
  { path: '/qc/pre', component: () => import('../views/QC.vue'), meta: { qcTab: 'pre' } },
  { path: '/qc/post', component: () => import('../views/QC.vue'), meta: { qcTab: 'post' } },
  { path: '/config', component: () => import('../views/ConfigEditor.vue') },
  { path: '/dialogue-config', component: () => import('../views/DialogueConfig.vue') },
  { path: '/intent-config', component: () => import('../views/IntentConfig.vue') },
  { path: '/profile-control', component: () => import('../views/ProfileControl.vue') },
  { path: '/prompt-preview', component: () => import('../views/PromptPreview.vue') },
  { path: '/results', component: () => import('../views/Results.vue') },
  { path: '/queue', component: () => import('../views/Queue.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
