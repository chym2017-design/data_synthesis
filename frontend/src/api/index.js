import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export default {
  health: () => api.get('/health'),

  system: {
    me: () => api.get('/system/me'),
    queue: () => api.get('/system/queue'),
    limits: () => api.get('/system/limits'),
  },

  synthesis: {
    start: (data) => api.post('/synthesis/start', data),
    status: (runId) => api.get(`/synthesis/status/${runId}`),
    list: () => api.get('/synthesis/list'),
  },

  qc: {
    availableFiles: () => api.get('/qc/available_files'),
    preCheck: (data) => api.post('/qc/pre_check', data),
    postCheck: (data) => api.post('/qc/post_check', data),
    status: (runId) => api.get(`/qc/status/${runId}`),
    list: () => api.get('/qc/list'),
    cancel: (runId) => api.post(`/qc/cancel/${runId}`),
    retry: (runId) => api.post(`/qc/retry/${runId}`),
    stats: (runId) => api.get(`/qc/stats/${runId}`),
  },

  config: {
    list: () => api.get('/config/list'),
    getLlm: () => api.get('/config/llm'),
    updateLlm: (config) => api.put('/config/llm', { config }),
    getEmbedding: () => api.get('/config/embedding'),
    updateEmbedding: (config) => api.put('/config/embedding', { config }),
    parseYaml: (file) => {
      const fd = new FormData()
      fd.append('file', file)
      return api.post('/config/parse_yaml', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    },
    get: (templateName, configType) => api.get(`/config/${templateName}/${configType}`),
    update: (templateName, configType, data) => api.put(`/config/${templateName}/${configType}`, data),
    restoreDefault: (templateName, configType) => api.post(`/config/${templateName}/${configType}/restore_default`),
    generateSampleProfile: (templateName, csvOptions = {}) => api.post(`/config/${templateName}/generate_sample_profile`, csvOptions),
    listResources: () => api.get('/config/resources'),
    uploadCsv: (file) => {
      const fd = new FormData()
      fd.append('file', file)
      return api.post('/config/upload_csv', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    },
    csvPreview: (path, limit = 50) => api.get('/config/csv_preview', { params: { path, limit } }),
    testLlm: (config) => api.post('/config/test/llm', { config }),
    testEmbedding: (config) => api.post('/config/test/embedding', { config }),
  },

  templates: {
    list: () => api.get('/templates/list'),
    get: (name) => api.get(`/templates/${name}`),
    getPrompt: (name, promptName) => api.get(`/templates/${name}/prompt/${promptName}`),
    create: (name, source) => api.post('/templates/create', null, { params: { template_name: name, source } }),
    delete: (name) => api.delete(`/templates/${name}`),
  },

  files: {
    listRuns: () => api.get('/files/runs'),
    download: (runId, filename) => `/api/files/download/${runId}/${filename}`,
    preview: (runId, filename, limit = 50) => api.get(`/files/preview/${runId}/${filename}`, { params: { limit } }),
    deleteRun: (runId) => api.delete(`/files/runs/${runId}`),
  },
}
