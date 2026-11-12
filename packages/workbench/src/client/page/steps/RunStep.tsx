/** Step 6 运行与报告：演示跑批 + 逐券结果 + 拟合点位对比。 */

import { useEffect, useRef, useState } from 'react'
import {
  BASE_LEVEL,
  SKIP_INDEXES,
  fmtDateShort,
  synthLevel,
  valuationPair,
  type BatchParams,
  type Constituent,
  type ValuationResult,
} from '../data'
import css from '../ValuationPage.module.css'
import { ReportModal } from '../ReportModal'

interface LogLine {
  text: string
  kind: 'ok' | 'dim' | 'info'
}

export function RunStep(props: {
  params: BatchParams
  indexSel: string
  date: Date
  parallel: 3 | 10
  list: Constituent[]
}) {
  const { params, indexSel, date, parallel, list } = props
  const total = list.length
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(0)
  const [logs, setLogs] = useState<LogLine[]>([])
  const [results, setResults] = useState<ValuationResult[] | null>(null)
  const [modalIdx, setModalIdx] = useState<number | null>(null)
  const timerRef = useRef<number | null>(null)

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current)
  }, [])

  const push = (text: string, kind: LogLine['kind'] = 'info') =>
    setLogs(prev => [...prev, { text, kind }])

  const start = () => {
    setRunning(true)
    setDone(0)
    setResults(null)
    setLogs([])
    const all = list.map((c, i) => valuationPair(c, i))
    setResults(all)
    const batches = Math.ceil(total / parallel)
    push(
      `[准备] 成分券 ${total} 条 · 并行度 每批 ${parallel} 条 · 舆情轮数上限 ${params.sentiment} · 估值日期 ${fmtDateShort(date)}`,
      'dim',
    )
    let b = 0
    const tick = () => {
      b += 1
      const from = (b - 1) * parallel + 1
      const to = Math.min(b * parallel, total)
      setDone(to)
      push(`[批次 ${b}/${batches}] 估值完成 ${from}–${to}（用时示例 ${(18 + Math.random() * 14).toFixed(0)}s）`, 'ok')
      for (const i of SKIP_INDEXES) {
        if (i >= from - 1 && i < to) push(`[跳过] ${list[i].name} · β 无法计算 → 陈老师技能自动跳过`, 'dim')
      }
      if (to >= total) {
        setRunning(false)
        const vA = synthLevel(list, all.map(r => r.chen))
        const vB = synthLevel(list, all.map(r => r.shi))
        const pA = synthLevel(list, all.map(r => r.price))
        const idxA = (vA / pA) * BASE_LEVEL
        const idxB = (vB / pA) * BASE_LEVEL
        push(`[完成] ${total} 条处理完毕：估值 ${total - SKIP_INDEXES.size} 条 · 跳过 ${SKIP_INDEXES.size} 条`, 'ok')
        push(`[合成] 陈老师拟合点位 ${idxA.toFixed(2)} · 石总 ${idxB.toFixed(2)} · 参考 ${BASE_LEVEL.toFixed(2)}`, 'ok')
      } else {
        timerRef.current = window.setTimeout(tick, 320)
      }
    }
    timerRef.current = window.setTimeout(tick, 260)
  }

  const stop = () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    timerRef.current = null
    setRunning(false)
    push('[停止] 演示跑批已手动停止', 'dim')
  }

  const finished = results !== null && !running && done >= total
  const vA = finished ? synthLevel(list, results!.map(r => r.chen)) : 0
  const vB = finished ? synthLevel(list, results!.map(r => r.shi)) : 0
  const pA = finished ? synthLevel(list, results!.map(r => r.price)) : 1
  const idxA = finished ? (vA / pA) * BASE_LEVEL : 0
  const idxB = finished ? (vB / pA) * BASE_LEVEL : 0

  const noise = Array.from({ length: 10 }, (_, i) => 3445 + Math.sin(i * 1.9) * 12 + Math.cos(i * 0.8) * 9)
  const pts = finished ? noise.concat([idxB, idxA]) : noise
  const lo = Math.min(...pts) - 8
  const hi = Math.max(...pts) + 8
  const sx = (i: number) => 4 + (i / (pts.length - 1)) * 312
  const sy = (v: number) => 80 - ((v - lo) / (hi - lo)) * 74

  return (
    <section>
      <h2>运行与报告</h2>
      <p className={css.sub}>并行跑批，逐家生成报告，最后输出总结报告；两版拟合点位并排对比。</p>
      <div className={css.review}>
        <div className={css.chip}>指数 <b>{indexSel}</b></div>
        <div className={css.chip}>估值日期 <b>{fmtDateShort(date)}</b></div>
        <div className={css.chip}>方法加权 <b>DCF {params.dcf}% · 可比 {params.comp}% · 舆情 {params.sent}%</b></div>
        <div className={css.chip}>舆情轮数 <b>≤ {params.sentiment} 轮</b></div>
        <div className={css.chip}>并行度 <b>每批 {parallel} 条</b></div>
      </div>
      <div className={css.runbox}>
        <button className={css.btn} disabled={running} onClick={start}>
          {finished ? '重新演示跑批' : '开始演示跑批'}
        </button>
        {running && <button className={`${css.btn} ${css.btnGhost}`} style={{ marginLeft: 10 }} onClick={stop}>停止</button>}
        <div className={css.progress}><i style={{ width: `${(done / total) * 100}%` }} /></div>
        {logs.length > 0 && (
          <div className={css.log}>
            {logs.map((l, i) => (
              <div key={i} className={l.kind === 'ok' ? css.logLineOk : l.kind === 'dim' ? css.logLineDim : undefined}>{l.text}</div>
            ))}
          </div>
        )}
      </div>
      {finished && (
        <div className={css.result}>
          <div className={css.repGrid}>
            <div className={css.sumcard}>
              <h4>拟合点位 · 陈老师</h4>
              <p className={css.level}>{idxA.toFixed(2)} <small>（加权合成 · 示例）</small></p>
              <p className={css.delta}>石总 {idxB.toFixed(2)} · 参考点位 {BASE_LEVEL.toFixed(2)}</p>
              <svg className={css.spark} viewBox="0 0 320 84" aria-hidden>
                <polyline fill="none" stroke="#c6cfd8" strokeWidth="1.5" points={noise.map((v, i) => `${sx(i)},${sy(v)}`).join(' ')} />
                <circle cx={sx(10)} cy={sy(idxB)} r="3.5" fill="#f59e0b" />
                <circle cx={sx(11)} cy={sy(idxA)} r="3.5" fill="#0e7490" />
              </svg>
              <div className={css.legend}>
                <span><i style={{ background: '#0e7490' }} />陈老师</span>
                <span><i style={{ background: '#f59e0b' }} />石总</span>
                <span><i style={{ background: '#c6cfd8' }} />参考走势（示例）</span>
              </div>
            </div>
            <div className={css.cmp2}>
              <h4>两版对比</h4>
              <table>
                <tbody>
                  <tr><th>陈老师拟合点位</th><td>{idxA.toFixed(2)}</td></tr>
                  <tr><th>石总拟合点位</th><td>{idxB.toFixed(2)}</td></tr>
                  <tr><th>参考点位（示例）</th><td>{BASE_LEVEL.toFixed(2)}</td></tr>
                  <tr><th>样本</th><td>{total} 条</td></tr>
                  <tr><th>出估值 / 跳过</th><td>{total - SKIP_INDEXES.size} / {SKIP_INDEXES.size}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <div className={css.detailList} style={{ marginTop: 16 }}>
            <h4>逐券结果（点击查看明细）</h4>
            {list.map((c, i) => {
              const skipped = SKIP_INDEXES.has(i)
              const r = results![i]
              return (
                <button key={c.name} className={css.drow} onClick={() => setModalIdx(i)}>
                  <span className={css.drowNm}>
                    {c.name}
                    {skipped && <span className={`${css.tag} ${css.tagWarn}`} style={{ marginLeft: 8 }}>跳过</span>}
                  </span>
                  <span className={css.drowVals}>
                    <span>价 {r.price.toFixed(2)}</span>
                    <span>陈 <b>{skipped ? '跳过' : r.chen.toFixed(2)}</b></span>
                    <span>石 <b>{skipped ? '—' : r.shi.toFixed(2)}</b></span>
                  </span>
                </button>
              )
            })}
          </div>
          <div className={css.note}>
            <b>⚠ 不能直接等权平均：</b>等权结果与指数点位对不上；拟合点位 = Σ(估值×权重) / Σ(价格×权重) × 参考点位。当日权重盘中才出，可先用前一日因子计算；跳过券不计入分子分母。
          </div>
          {modalIdx !== null && (
            <ReportModal
              name={list[modalIdx].name}
              i={modalIdx}
              r={results![modalIdx]}
              w={list[modalIdx].w}
              onClose={() => setModalIdx(null)}
            />
          )}
        </div>
      )}
    </section>
  )
}
