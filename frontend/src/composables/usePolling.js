import { ref, onUnmounted } from 'vue'

export function usePolling(fetchFn, { interval = 3000, onDone = null } = {}) {
  const data = ref(null)
  const isPolling = ref(false)
  let timer = null

  function start(id) {
    stop()
    isPolling.value = true
    let inFlight = false
    const tick = async () => {
      if (inFlight || !isPolling.value) return
      inFlight = true
      try {
        const result = await fetchFn(id)
        data.value = result
        if (result.stage === 'done' || result.stage === 'error' || result.stage === 'interrupted' || result.stage === 'cancelled') {
          stop()
          onDone?.(result)
        }
      } catch {
        stop()
      } finally {
        inFlight = false
      }
    }
    tick()
    timer = setInterval(tick, interval)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    isPolling.value = false
  }

  onUnmounted(stop)

  return { data, isPolling, start, stop }
}
