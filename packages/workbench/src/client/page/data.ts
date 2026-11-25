/** Shared metadata, batch params and formatting for the workbench. */

export interface BatchParams {
  sentiment: number
  dcf: number
  comp: number
  sent: number
  sentimentMode: 'rule' | 'llm'
  statN: number
  /** WACC 覆盖（%），null = 逐券 CAPM 自动。 */
  waccPct: number | null
  /** 永续增速覆盖（%），null = 引擎行业底座逐券校准。 */
  terminalGrowthPct: number | null
}

/** 覆盖参数冲突校验：两者都显式给时，永续增速必须低于 WACC。 */
export function overrideError(p: BatchParams): string | null {
  if (p.waccPct != null && p.terminalGrowthPct != null && p.waccPct <= p.terminalGrowthPct) {
    return '参数冲突：WACC 覆盖需高于永续增速覆盖'
  }
  return null
}

export interface IndexMeta {
  id: string
  name: string
  code: string
  count: number
}

/** 四个可选指数：成分与权重全部来自 Mac 批跑服务（东财成分表）。 */
export const INDEXES: IndexMeta[] = [
  { id: 'sh50', name: '上证50', code: '000016.SH', count: 50 },
  { id: 'sh180', name: '上证180', code: '000010.SH', count: 180 },
  { id: 'kc50', name: '科创50', code: '000688.SH', count: 50 },
  { id: 'hs300', name: '沪深300', code: '000300.SH', count: 300 },
]

export function indexMeta(id: string): IndexMeta {
  return INDEXES.find(x => x.id === id) ?? { id, name: id, code: '—', count: 50 }
}

export const WEEK_CN = ['日', '一', '二', '三', '四', '五', '六']
export const WEEK_HEAD = ['一', '二', '三', '四', '五', '六', '日']
export const MON_EN = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

/** 差异展示：只表达偏离，不表达校正系数。 */
export function pctDiff(x: number): string {
  return `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(1)}%`
}

export function signedPoints(x: number): string {
  return `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(2)}`
}

export function fmtNum(x: number | null | undefined, digits = 2): string {
  return x == null || !Number.isFinite(x) ? '—' : x.toFixed(digits)
}

export function fmtDate(d: Date): string {
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`
}

export function fmtDateShort(d: Date): string {
  const m = d.getMonth() + 1
  const dd = d.getDate()
  return `${d.getFullYear()}-${m < 10 ? '0' + m : m}-${dd < 10 ? '0' + dd : dd}`
}

export function fmtMonthDay(d: Date): string {
  const m = d.getMonth() + 1
  const dd = d.getDate()
  return `${m < 10 ? '0' + m : m}-${dd < 10 ? '0' + dd : dd}`
}

/** "2026-11-17 14:03:53" → "11-17 14:03"。 */
export function shortTime(created: string): string {
  const m = /^\d{4}-(\d{2}-\d{2})[ T](\d{2}:\d{2})/.exec(created)
  return m ? `${m[1]} ${m[2]}` : created
}

export function medianOf(xs: number[]): number | null {
  if (xs.length === 0) return null
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 === 1 ? s[m] : (s[m - 1] + s[m]) / 2
}

export function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}
