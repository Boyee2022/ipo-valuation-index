/** Reusable parameter fields: weights, sentiment mode, dates and parallelism. */

import { useEffect, useState } from 'react'
import { WEEK_CN, WEEK_HEAD, fmtMonthDay, sameDay, type BatchParams } from '../data'
import css from '../ValuationPage.module.css'

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
const int = (v: string, fallback: number) => {
  const n = Number.parseInt(v, 10)
  return Number.isFinite(n) ? n : fallback
}

export function NumInput(props: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  width?: number
  label?: string
}) {
  const { value, onChange, min = 0, max = 99999, step = 1, width = 52, label } = props
  return (
    <input
      className={css.numInput}
      style={{ width }}
      type="number"
      min={min}
      max={max}
      step={step}
      value={value}
      aria-label={label}
      onChange={e => onChange(clamp(int(e.target.value, value), min, max))}
    />
  )
}

/** 方法加权比例：DCF / 可比 / 舆情，合计需等于 100%。 */
export function WeightsEditor(props: { params: BatchParams; onChange: (p: BatchParams) => void }) {
  const { params, onChange } = props
  const sum = params.dcf + params.comp + params.sent
  const pct = (v: number) => `${sum > 0 ? (v / sum) * 100 : 0}%`
  const set = (key: 'dcf' | 'comp' | 'sent', v: number) => onChange({ ...params, [key]: v })
  return (
    <div className={css.weightsCompact}>
      <div className={css.wmix}>
        <span style={{ width: pct(params.dcf), background: 'var(--red)' }} />
        <span style={{ width: pct(params.comp), background: 'var(--blue)' }} />
        <span style={{ width: pct(params.sent), background: 'var(--amber2)' }} />
      </div>
      <div className={css.wlegend}>
        <label><i style={{ background: 'var(--red)' }} />DCF<NumInput value={params.dcf} onChange={v => set('dcf', v)} min={0} max={100} width={44} label="DCF 权重" /></label>
        <label><i style={{ background: 'var(--blue)' }} />可比<NumInput value={params.comp} onChange={v => set('comp', v)} min={0} max={100} width={44} label="可比权重" /></label>
        <label><i style={{ background: 'var(--amber2)' }} />舆情<NumInput value={params.sent} onChange={v => set('sent', v)} min={0} max={100} width={44} label="舆情权重" /></label>
      </div>
      <div className={sum === 100 ? css.wsumOk : css.wsumBad}>
        方法合计 {sum}%{sum === 100 ? '' : ' · 需等于 100% 才能跑批'}
      </div>
    </div>
  )
}

/** 舆情口径：同一语料两种打分方式。 */
export function SentimentSeg(props: { value: 'rule' | 'llm'; onChange: (v: 'rule' | 'llm') => void }) {
  const { value, onChange } = props
  return (
    <div className={css.seg}>
      <button type="button" className={value === 'rule' ? css.segSel : ''} onClick={() => onChange('rule')}>
        规则打分<small>词频 · 免费</small>
      </button>
      <button type="button" className={value === 'llm' ? css.segSel : ''} onClick={() => onChange('llm')}>
        LLM 语义<small>DeepSeek · 需密钥</small>
      </button>
    </div>
  )
}

/** 今天 / 昨天快捷选择。 */
export function DateQuick(props: { date: Date; onDate: (d: Date) => void }) {
  const { date, onDate } = props
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  return (
    <div className={css.seg}>
      <button type="button" className={sameDay(date, today) ? css.segSel : ''} onClick={() => onDate(new Date())}>
        今天<small>{fmtMonthDay(today)} 周{WEEK_CN[today.getDay()]}</small>
      </button>
      <button type="button" className={sameDay(date, yesterday) ? css.segSel : ''} onClick={() => onDate(yesterday)}>
        昨天<small>{fmtMonthDay(yesterday)} 周{WEEK_CN[yesterday.getDay()]}</small>
      </button>
    </div>
  )
}

/** 紧凑日历：周一开头，周末与未来日期不可选。 */
export function MiniCalendar(props: { date: Date; onDate: (d: Date) => void }) {
  const { date, onDate } = props
  const [viewY, setViewY] = useState(() => date.getFullYear())
  const [viewM, setViewM] = useState(() => date.getMonth())

  useEffect(() => {
    setViewY(date.getFullYear())
    setViewM(date.getMonth())
  }, [date])

  const move = (delta: number) => {
    let m = viewM + delta
    let y = viewY
    if (m < 0) { m = 11; y -= 1 }
    if (m > 11) { m = 0; y += 1 }
    setViewY(y)
    setViewM(m)
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const daysInMonth = new Date(viewY, viewM + 1, 0).getDate()
  const offset = (new Date(viewY, viewM, 1).getDay() + 6) % 7
  const cells: (number | null)[] = []
  for (let k = 0; k < offset; k++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)

  return (
    <div className={css.minical}>
      <div className={css.calHead}>
        <button type="button" onClick={() => move(-1)} aria-label="上个月">‹</button>
        <span>{viewY} 年 {viewM + 1} 月</span>
        <button type="button" onClick={() => move(1)} aria-label="下个月">›</button>
      </div>
      <div className={css.calWeek}>{WEEK_HEAD.map(w => <span key={w}>{w}</span>)}</div>
      <div className={css.calGrid}>
        {cells.map((d, i) => {
          if (d === null) return <span key={`e${i}`} />
          const dt = new Date(viewY, viewM, d)
          const off = dt.getDay() === 0 || dt.getDay() === 6 || dt > today
          const cls = [
            css.calDay,
            off ? css.calDayOff : '',
            sameDay(dt, date) ? css.calDaySel : '',
            sameDay(dt, today) ? css.calDayToday : '',
          ].filter(Boolean).join(' ')
          return (
            <button key={d} type="button" className={cls} disabled={off} onClick={() => onDate(dt)}>
              {d}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/** 并行度紧凑分段（右侧参数卡）。 */
export function ParallelQuick(props: { parallel: 3 | 10; onParallel: (v: 3 | 10) => void }) {
  const { parallel, onParallel } = props
  return (
    <div className={css.seg}>
      <button type="button" className={parallel === 3 ? css.segSel : ''} onClick={() => onParallel(3)}>
        每批 3 条<small>稳妥</small>
      </button>
      <button type="button" className={parallel === 10 ? css.segSel : ''} onClick={() => onParallel(10)}>
        每批 10 条<small>激进</small>
      </button>
    </div>
  )
}
