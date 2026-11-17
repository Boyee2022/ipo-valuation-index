/** Demo data and synthesis math for the six-step batch page. */

export interface Constituent {
  name: string
  factor: number
  cap: number
  w: number
}

export interface BatchParams {
  sentiment: number
  dcf: number
  comp: number
  sent: number
  sentimentMode: 'rule' | 'llm'
}

export interface IndexMeta {
  id: string
  name: string
  code: string
  count: number
  baseLevel: number
}

/** 四个可选指数：真实成分来自 Mac 批跑服务（东财成分表），演示数据按 count 本地生成。 */
export const INDEXES: IndexMeta[] = [
  { id: 'sh50', name: '上证50', code: '000016.SH', count: 50, baseLevel: 3475.0 },
  { id: 'sh180', name: '上证180', code: '000010.SH', count: 180, baseLevel: 8988.0 },
  { id: 'kc50', name: '科创50', code: '000688.SH', count: 50, baseLevel: 1213.0 },
  { id: 'hs300', name: '沪深300', code: '000300.SH', count: 300, baseLevel: 3979.0 },
]

export function indexMeta(id: string): IndexMeta {
  return INDEXES.find(x => x.id === id) ?? { id, name: id, code: '—', count: 50, baseLevel: 3000 }
}

/** β 无法计算 → 陈老师技能自动跳过的边界示例券（列表最后两条）。 */
export function skipIndexes(count: number): Set<number> {
  return new Set(count > 2 ? [count - 2, count - 1] : [])
}

export const WEEK_CN = ['日', '一', '二', '三', '四', '五', '六']

export function genConstituents(count = 50): Constituent[] {
  const firstW = [2.3, 1.8, 1.6, 1.1, 0.9]
  const nRest = Math.max(count - firstW.length, 0)
  let rest: number[] = []
  for (let j = 0; j < nRest; j++) rest.push(Math.pow(0.955, j) * 0.82)
  const sumR = rest.reduce((a, b) => a + b, 0)
  const target = 100 - firstW.reduce((a, b) => a + b, 0)
  rest = rest.map(x => (x / sumR) * target)
  const targetW = firstW.concat(rest)
  return targetW.map((w, i) => {
    const factor = +(0.92 + Math.random() * 0.16).toFixed(4)
    const cap = +((w / factor) * (10 + Math.random() * 2)).toFixed(0)
    const name = `示例券 ${String(i + 1).padStart(2, '0')}`
    return { name, factor, cap, w }
  })
}

export function priceOf(c: Constituent, i: number): number {
  return +Math.abs(8 + c.w * 3 + Math.sin(i * 1.7) * 5).toFixed(2)
}

export interface ValuationResult {
  price: number
  chen: number
  shi: number
}

export function valuationPair(c: Constituent, i: number): ValuationResult {
  const price = priceOf(c, i)
  return {
    price,
    chen: +(price * (0.96 + Math.random() * 0.18)).toFixed(2),
    shi: +(price * (0.97 + Math.random() * 0.14)).toFixed(2),
  }
}

/** 加权合成：个股估值 × 当日权重 → 加权求和（跳过券不计入分子分母）。 */
export function synthLevel(list: Constituent[], vals: number[], skip: Set<number> = new Set()): number {
  let num = 0
  let wSum = 0
  list.forEach((c, i) => {
    if (skip.has(i)) return
    num += vals[i] * c.w
    wSum += c.w
  })
  return wSum > 0 ? num / wSum : 0
}

export function fmtDate(d: Date): string {
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`
}

export function fmtDateShort(d: Date): string {
  const m = d.getMonth() + 1
  const dd = d.getDate()
  return `${d.getFullYear()}-${m < 10 ? '0' + m : m}-${dd < 10 ? '0' + dd : dd}`
}
