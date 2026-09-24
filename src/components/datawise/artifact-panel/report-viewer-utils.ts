import type { DownloadedFile } from '@/lib/api'

export function formatBytes(bytes?: number): string | undefined {
  if (bytes === undefined || Number.isNaN(bytes)) return undefined
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

// ─── Zoom level utilities ───
export const ZOOM_STEPS = [50, 75, 90, 100, 110, 120, 135, 150, 175, 200, 250, 300]
export const DEFAULT_EMBED_ZOOM = 100
export const DEFAULT_FULLSCREEN_ZOOM = 120

export function zoomIn(current: number) {
  const next = ZOOM_STEPS.find((s) => s > current)
  return next ?? 300
}

export function zoomOut(current: number) {
  const prev = [...ZOOM_STEPS].reverse().find((s) => s < current)
  return prev ?? 50
}

export function buildIframeSrc(url: string, zoom: number, fitMode: 'width' | 'page' | 'zoom') {
  const params = 'toolbar=1&navpanes=0&scrollbar=1'
  if (fitMode === 'width') return `${url}#${params}&view=FitH`
  if (fitMode === 'page') return `${url}#${params}&view=Fit`
  return `${url}#${params}&zoom=${zoom}`
}