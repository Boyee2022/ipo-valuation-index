/** 批跑服务 API 客户端（Mac 内网 3089）。服务不可达时由调用方回退演示数据。 */

export const API_BASE = 'http://10.200.103.86:3089'

export interface RealConstituent {
  code: string | null
  secucode: string
  name: string
  industry: string | null
  weight: number | null
  close: number | null
  pe: number | null
  eps: number | null
  roe: number | null
  total_shares: number | null
  free_cap: number | null
}

export type ShadowParam = 'comp_weight_pp' | 'wacc_pp' | 'tg_pp'
export type ShadowDecision = 'accept' | 'partial' | 'reject' | 'hold' | 'error'
export type ShadowAdoption = 'adopted' | 'rejected' | null

export interface ShadowItem {
  param: ShadowParam
  delta: number
  status: 'accept' | 'clamp' | 'reject'
}

export interface ShadowRow {
  decision: ShadowDecision | null
  confidence: number | null
  one_line: string
  adoption: ShadowAdoption
  base: { comp: number | null; wacc: number | null; tg: number | null }
  items: ShadowItem[]
  n_issue: number
  n_gated?: number
  error?: string | null
}

export interface ShadowDispersion {
  median: number | null
  iqr: [number | null, number | null]
  nonzero: number
  n: number
}

export interface ShadowMetrics {
  reviewed: number
  errors: number
  suggested: number
  accepted_items: number
  gated?: number
  decision_dist: Record<ShadowDecision, number>
  mean_confidence: number | null
  dispersion: Record<ShadowParam, ShadowDispersion>
  adoption: { adopted: number; rejected: number; pending: number; rate: number | null }
  wow: (null | { prev_job: string; prev_created: string; n: number } & Record<ShadowParam, number | null>)
  generated: string
}

export interface JobRow {
  idx: number
  code: string | null
  secucode: string
  name: string
  industry: string | null
  weight: number | null
  close: number | null
  pe: number | null
  total_shares?: number | null
  status: 'pending' | 'running' | 'ok' | 'skip'
  error?: string
  weighted_mid?: number
  per_share?: number
  interval?: [number, number]
  confidence_level?: string
  stage_label?: string
  basis?: string
  check_ok?: boolean
  warnings?: string[]
  report?: string
  shadow?: ShadowRow
}

export interface JobSummary {
  fitted_point: number | null
  index_close: number | null
  ok: number
  skip: number
  total: number
}

export interface JobStatus {
  id: string
  index: string
  created: string
  state: 'running' | 'done' | 'error'
  done: number
  total: number
  components_as_of?: string
  index_close?: number | null
  parallel?: number
  stat_n?: number
  weights?: { dcf: number; comp: number; sent: number }
  sentiment_rounds?: number
  sentiment_mode?: 'rule' | 'llm'
  wacc_pct?: number | null
  terminal_growth_pct?: number | null
  shadow_mode?: boolean
  shadow_metrics?: ShadowMetrics | null
  shadow_warning?: string
  rows: JobRow[]
  summary?: JobSummary
  error?: string | null
}

export interface ConstituentsPayload {
  index: string
  index_name: string
  as_of: string
  index_close: number | null
  weight_computed?: boolean
  rows: RealConstituent[]
}

export interface JobMeta {
  id: string
  index: string
  created: string
  state: 'running' | 'done' | 'error'
  done: number
  total: number
  components_as_of?: string | null
  fitted_point: number | null
  index_close: number | null
  ok: number | null
  skip: number | null
  sentiment_mode?: 'rule' | 'llm'
  shadow_mode?: boolean
}

async function jfetch(url: string, init?: RequestInit, ms = 15000): Promise<Response> {
  const ctl = new AbortController()
  const timer = window.setTimeout(() => ctl.abort(), ms)
  try {
    return await fetch(url, { ...init, signal: ctl.signal })
  } finally {
    window.clearTimeout(timer)
  }
}

export async function fetchConstituents(index = 'sh50'): Promise<ConstituentsPayload> {
  const res = await jfetch(`${API_BASE}/api/constituents?index=${encodeURIComponent(index)}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function runBatch(payload: {
  index: string
  parallel: 3 | 10
  stat_n: number
  weights: { dcf: number; comp: number; sent: number }
  sentiment_rounds: number
  sentiment_mode: 'rule' | 'llm'
  wacc_pct?: number | null
  terminal_growth_pct?: number | null
  shadow?: boolean
}): Promise<{ job_id: string }> {
  const res = await jfetch(`${API_BASE}/api/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, 20000)
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { error?: string }
      if (body.error) detail = ` · ${body.error}`
    } catch { /* 非 JSON 错误响应 */ }
    throw new Error(`HTTP ${res.status}${detail}`)
  }
  return res.json()
}

export async function pollJob(id: string): Promise<JobStatus> {
  const res = await jfetch(`${API_BASE}/api/jobs/${id}`, undefined, 12000)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

/** 人工采纳标记：adopted / rejected / clear（再次点击已选项 = 清除）。 */
export async function setShadowAdoption(
  jobId: string,
  code: string,
  action: 'adopted' | 'rejected' | 'clear',
): Promise<{ shadow: ShadowRow; shadow_metrics: ShadowMetrics | null }> {
  const res = await jfetch(`${API_BASE}/api/shadow/adopt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job: jobId, code, action }),
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { error?: string }
      if (body.error) detail = ` · ${body.error}`
    } catch { /* 非 JSON 错误响应 */ }
    throw new Error(`HTTP ${res.status}${detail}`)
  }
  return res.json()
}

/** 单券影子评审完整记录（含证据、专家原始建议、主审逐条意见）。 */
export function shadowRecordUrl(jobId: string, secucode: string): string {
  return `${API_BASE}/api/jobs/${jobId}/reports/${encodeURIComponent(`${secucode.replace(/\./g, '_')}.shadow.json`)}`
}

export async function fetchJobs(): Promise<JobMeta[]> {
  const res = await jfetch(`${API_BASE}/api/jobs`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = (await res.json()) as { jobs?: JobMeta[] }
  return data.jobs ?? []
}

/** 主页当前主题：外壳把深色标记在 body 上，作为报告主题的真源。 */
export function currentTheme(): 'dark' | 'light' {
  return document.body?.hasAttribute('data-ds-dark-theme') ? 'dark' : 'light'
}

export function reportUrl(jobId: string, file: string): string {
  const url = new URL(`${API_BASE}/api/jobs/${jobId}/reports/${encodeURIComponent(file)}`)
  url.hash = `theme=${currentTheme()}`
  return url.toString()
}

/** 链接渲染后主页仍可能切换主题，导航前按当前 body 标记刷新 #theme。 */
export function installReportThemeSync(): () => void {
  const syncAnchor = (a: HTMLAnchorElement): void => {
    try {
      const url = new URL(a.href)
      url.hash = `theme=${currentTheme()}`
      if (a.href !== url.toString()) a.href = url.toString()
    } catch { /* 非法链接不处理 */ }
  }
  const syncEvent = (e: Event): void => {
    if (!(e.target instanceof Element)) return
    const a = e.target.closest('a[href*="/reports/"]')
    if (a instanceof HTMLAnchorElement) syncAnchor(a)
  }
  const syncAll = (): void => {
    document.querySelectorAll<HTMLAnchorElement>('a[href*="/reports/"]').forEach(syncAnchor)
  }
  syncAll()
  const observer = new MutationObserver(syncAll)
  if (document.body) {
    observer.observe(document.body, { attributes: true, attributeFilter: ['data-ds-dark-theme'] })
  }
  document.addEventListener('click', syncEvent, true)
  document.addEventListener('pointerdown', syncEvent, true)
  document.addEventListener('auxclick', syncEvent, true)
  return () => {
    observer.disconnect()
    document.removeEventListener('click', syncEvent, true)
    document.removeEventListener('pointerdown', syncEvent, true)
    document.removeEventListener('auxclick', syncEvent, true)
  }
}
