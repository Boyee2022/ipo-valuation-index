/** 批跑服务 API 客户端（Mac 内网 3089）。服务不可达时由调用方回退演示数据。 */

export const API_BASE = 'http://10.200.100.68:3089'

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

export interface JobRow {
  idx: number
  code: string | null
  secucode: string
  name: string
  industry: string | null
  weight: number | null
  close: number | null
  pe: number | null
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
  rows: JobRow[]
  summary?: JobSummary
  error?: string | null
}

export interface ConstituentsPayload {
  index: string
  index_name: string
  as_of: string
  index_close: number | null
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

export async function fetchConstituents(): Promise<ConstituentsPayload> {
  const res = await jfetch(`${API_BASE}/api/constituents?index=sh50`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function runBatch(payload: {
  index: string
  parallel: 3 | 10
  stat_n: number
  weights: { dcf: number; comp: number; sent: number }
  sentiment_rounds: number
}): Promise<{ job_id: string }> {
  const res = await jfetch(`${API_BASE}/api/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, 20000)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function pollJob(id: string): Promise<JobStatus> {
  const res = await jfetch(`${API_BASE}/api/jobs/${id}`, undefined, 12000)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchJobs(): Promise<JobMeta[]> {
  const res = await jfetch(`${API_BASE}/api/jobs`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = (await res.json()) as { jobs?: JobMeta[] }
  return data.jobs ?? []
}

export function reportUrl(jobId: string, file: string): string {
  return `${API_BASE}/api/jobs/${jobId}/reports/${encodeURIComponent(file)}`
}
