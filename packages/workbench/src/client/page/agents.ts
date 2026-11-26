/** 估值智能体配置 API。服务端 ~/.dsh-valuation/agents.json 是唯一配置源，每批开始时快照。 */

import { API_BASE } from './api'

export type AgentKey = 'comparable' | 'financial' | 'sentiment' | 'main'
export type ExpertKey = Exclude<AgentKey, 'main'>
export type ParamKey = 'comp_weight_pp' | 'sent_weight_pp' | 'wacc_pp' | 'tg_pp'
export type Severity = 'medium' | 'high' | 'critical'

export interface AgentRoleConfig {
  enabled: boolean
  confidence_gate?: number
  caps?: Partial<Record<ParamKey, Partial<Record<Severity, number>>>>
}

export interface AgentsConfig {
  version: number
  model: string
  concurrency: number
  timeout_s: number
  agents: Record<AgentKey, AgentRoleConfig>
}

export interface PromptParam {
  key: ParamKey
  label: string
  caps: Partial<Record<Severity, number | null>>
}

export interface PromptRole {
  code: string
  label: string
  enabled: boolean
  gate: number | null
  params: PromptParam[]
  system: string
  evidence: string[]
}

export interface PromptsPayload {
  version: number
  model: string
  generated: string
  roles: Record<AgentKey, PromptRole>
}

export interface AgentsPayload {
  config: AgentsConfig
  defaults: AgentsConfig
  labels: Record<AgentKey, string>
  path: string
  exists: boolean
  updated_at: string | null
  model_env: string
  llm_ready: boolean
  prompts?: PromptsPayload
  saved: boolean
}

export interface ParamMeta {
  label: string
  unit: string
  lo: number
  hi: number
  step: number
  sevs: Severity[]
}

export const SEV_LABEL: Record<Severity, string> = { medium: '中', high: '高', critical: '严重' }

export const PARAM_META: Record<ParamKey, ParamMeta> = {
  comp_weight_pp: { label: '可比权重', unit: 'pp', lo: 0.5, hi: 20, step: 0.5, sevs: ['medium', 'high', 'critical'] },
  sent_weight_pp: { label: '舆情权重', unit: 'pp', lo: 0.5, hi: 20, step: 0.5, sevs: ['medium', 'high'] },
  wacc_pp: { label: 'WACC / Ke', unit: 'pp', lo: 0.1, hi: 3, step: 0.05, sevs: ['medium', 'high'] },
  tg_pp: { label: '永续增速', unit: 'pp', lo: 0.1, hi: 1.5, step: 0.05, sevs: ['medium', 'high'] },
}

export const ROLE_META: Record<AgentKey, {
  code: string
  name: string
  tagline: string
  desc: string
  params: ParamKey[]
}> = {
  comparable: {
    code: 'CMP',
    name: '可比质量',
    tagline: '核对可比公司与估值倍数',
    desc: '复核可比池的行业归属、规模与盈利质量，对可比法权重提出调整建议。',
    params: ['comp_weight_pp'],
  },
  financial: {
    code: 'DCF',
    name: '折现参数',
    tagline: '复核 WACC 与永续增速',
    desc: '检查 β、CAPM、债务成本与资本结构，对 WACC / Ke 与永续增速提出调整建议。',
    params: ['wacc_pp', 'tg_pp'],
  },
  sentiment: {
    code: 'SNT',
    name: '舆情',
    tagline: '核对舆情方向与影响幅度',
    desc: '基于新闻与股吧语料复核情绪方向，对舆情权重提出调整建议。',
    params: ['sent_weight_pp'],
  },
  main: {
    code: 'REV',
    name: '主审',
    tagline: '收敛分歧并逐条裁决',
    desc: '汇总三专家建议，按证据强度与置信度裁决；所有调整受下方幅度上限约束。',
    params: [],
  },
}

const MODEL_RE = /^[A-Za-z0-9._:\-/]*$/

export function validateAgents(cfg: AgentsConfig): string | null {
  if (!MODEL_RE.test(cfg.model) || cfg.model.length > 64) {
    return '模型名仅允许字母、数字与 . _ : - /，且不超过 64 个字符'
  }
  if (!Number.isInteger(cfg.concurrency) || cfg.concurrency < 1 || cfg.concurrency > 12) {
    return '并发数需为 1~12 的整数'
  }
  if (!Number.isInteger(cfg.timeout_s) || cfg.timeout_s < 30 || cfg.timeout_s > 240) {
    return '单券超时需为 30~240 秒的整数'
  }
  for (const key of ['comparable', 'financial', 'sentiment'] as ExpertKey[]) {
    const role = cfg.agents[key]
    const gate = role.confidence_gate ?? 0.65
    if (gate < 0.5 || gate > 0.95) return `${ROLE_META[key].name} 的置信门槛需在 0.50~0.95`
    const caps = role.caps ?? {}
    for (const param of ROLE_META[key].params) {
      const meta = PARAM_META[param]
      const vals = meta.sevs.map(sev => caps[param]?.[sev])
      for (let i = 0; i < vals.length; i += 1) {
        const v = vals[i]
        if (v == null || !Number.isFinite(v) || v < meta.lo || v > meta.hi) {
          return `${meta.label} 的${SEV_LABEL[meta.sevs[i]]}档上限需在 ${meta.lo}~${meta.hi}pp`
        }
      }
      for (let i = 0; i < vals.length - 1; i += 1) {
        if ((vals[i] as number) > (vals[i + 1] as number)) {
          return `${meta.label} 的上限需按严重度递增（${meta.sevs.map(s => SEV_LABEL[s]).join(' ≤ ')}）`
        }
      }
    }
  }
  return null
}

export function cloneConfig(cfg: AgentsConfig): AgentsConfig {
  return JSON.parse(JSON.stringify(cfg)) as AgentsConfig
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

function detailOf(body: unknown): string {
  if (body && typeof body === 'object' && typeof (body as { error?: unknown }).error === 'string') {
    return (body as { error: string }).error
  }
  return ''
}

export async function fetchAgents(): Promise<AgentsPayload> {
  const res = await jfetch(`${API_BASE}/api/agents`)
  if (!res.ok) {
    let detail = ''
    try { detail = detailOf(await res.json()) } catch { /* 非 JSON 错误响应 */ }
    throw new Error(`HTTP ${res.status}${detail ? ` · ${detail}` : ''}`)
  }
  return res.json()
}

export async function saveAgents(config: AgentsConfig): Promise<AgentsPayload> {
  const res = await jfetch(`${API_BASE}/api/agents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config }),
  })
  if (!res.ok) {
    let detail = ''
    try { detail = detailOf(await res.json()) } catch { /* 非 JSON 错误响应 */ }
    throw new Error(`HTTP ${res.status}${detail ? ` · ${detail}` : ''}`)
  }
  return res.json()
}