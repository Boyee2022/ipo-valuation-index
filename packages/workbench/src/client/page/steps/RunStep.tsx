/** Step 6 运行与报告：真实跑批（Mac 批跑服务 3089）+ 服务不可达时回退演示跑批。 */

import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  fmtDateShort,
  indexMeta,
  pctDiff,
  skipIndexes,
  synthLevel,
  valuationPair,
  type BatchParams,
  type Constituent,
  type ValuationResult,
} from '../data'
import { fetchJobs, pollJob, reportUrl, runBatch, type JobMeta, type JobStatus } from '../api'
import css from '../ValuationPage.module.css'
import { ReportModal } from '../ReportModal'

interface LogLine {
  text: string
  kind: 'ok' | 'dim' | 'info'
}

const STAT_N = 1000

/** 近 N 次跑批走势（同指数）：拟合点位（金，实线）vs 指数收盘（青，虚线）。 */
function HistoryChart({ hist, indexSel }: { hist: JobMeta[]; indexSel: string }) {
  const meta = indexMeta(indexSel)
  const pts = hist
    .filter(h => h.index === indexSel && h.state === 'done' && h.fitted_point != null && h.index_close != null && h.index_close > 0)
    .reverse()
  if (pts.length < 2) return null
  const W = 720
  const H = 180
  const PAD = 34
  const fit = pts.map(h => h.fitted_point!)
  const idx = pts.map(h => h.index_close!)
  const min = Math.floor(Math.min(...fit, ...idx) - 4)
  const max = Math.ceil(Math.max(...fit, ...idx) + 4)
  const X = (i: number) => PAD + (i * (W - PAD * 2)) / (fit.length - 1)
  const Y = (v: number) => H - PAD - ((v - min) / (max - min)) * (H - PAD * 2)
  const path = (arr: number[]) =>
    arr.map((v, i) => `${i === 0 ? 'M' : 'L'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(' ')
  const grid = Array.from({ length: 5 }, (_, i) => min + ((max - min) * i) / 4)
  return (
    <div className={css.chart}>
      <div className={css.chartTitle}>
        近 {pts.length} 次跑批 · {meta.name} 拟合点位 vs 指数收盘
        <span className={css.clegend}>
          <i className={css.swGold} />拟合点位<i className={css.swCyan} />指数收盘
        </span>
      </div>
      <svg className={css.chartSvg} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-label="历史跑批走势图">
        {grid.map(gv => (
          <g key={gv}>
            <line className={css.chartGrid} x1={PAD} y1={Y(gv)} x2={W - PAD} y2={Y(gv)} strokeWidth="1" />
            <text className={css.chartLabel} x="6" y={Y(gv) + 4} fontSize="10" fontFamily="Consolas,monospace">{Math.round(gv)}</text>
          </g>
        ))}
        <path className={css.chartIdx} d={path(idx)} fill="none" strokeWidth="2" strokeDasharray="4 3" />
        <path className={css.chartFit} d={path(fit)} fill="none" strokeWidth="2" />
        {fit.map((v, i) => <circle key={i} className={css.chartFit} cx={X(i)} cy={Y(v)} r="2.6" />)}
      </svg>
    </div>
  )
}

function medianOf(xs: number[]): number | null {
  if (xs.length === 0) return null
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 === 1 ? s[m] : (s[m - 1] + s[m]) / 2
}

const diffOf = (per?: number | null, close?: number | null) =>
  per != null && close != null && close > 0 ? per / close - 1 : null

const tickText = (x: number) => (x === 0 ? '0' : `${x > 0 ? '+' : '−'}${Math.abs(Math.round(x * 100))}%`)

/** 逐券差异分布（海报图）：横轴 = 中枢/股相对现价的差异，点大小 = 当日权重。 */
function DiffStrip({ items }: { items: { name: string; diff: number; w: number }[] }) {
  if (items.length === 0) return <p className={css.hint}>无可用于差异展示的逐券结果。</p>
  const LANES = 6
  const ROW = 15
  const STEPS = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2]
  const absSorted = items.map(x => Math.abs(x.diff)).sort((a, b) => a - b)
  const p90 = absSorted[Math.min(absSorted.length - 1, Math.floor((absSorted.length - 1) * 0.9))]
  const step = STEPS.find(s => s * 2 >= p90) ?? 2
  const CLAMP = step * 2
  const pos = (d: number) => ((Math.min(Math.max(d, -CLAMP), CLAMP) + CLAMP) / (2 * CLAMP)) * 100
  const laneLast: number[] = Array(LANES).fill(-1e9)
  let over = 0
  const dots = [...items]
    .sort((a, b) => a.diff - b.diff)
    .map((it, i) => {
      let lane = 0
      for (let l = 1; l < LANES; l++) if (laneLast[l] < laneLast[lane]) lane = l
      const px = pos(it.diff)
      laneLast[lane] = px
      const dir = it.diff > CLAMP ? 1 : it.diff < -CLAMP ? -1 : 0
      if (dir !== 0) over += 1
      return { ...it, key: `${i}-${it.name}`, px, lane, dir }
    })
  const med = medianOf(items.map(x => x.diff))
  const up = items.filter(x => x.diff >= 0).length
  const ticks = [-CLAMP, -CLAMP / 2, 0, CLAMP / 2, CLAMP]
  return (
    <div className={css.strip}>
      <div className={css.stripPlot} style={{ height: LANES * ROW + 8 }}>
        {ticks.map(t => (
          <i key={t} className={`${css.stripGrid} ${t === 0 ? css.stripZero : ''}`} style={{ left: `${pos(t)}%` }} />
        ))}
        {med != null && <i className={css.stripMed} style={{ left: `${pos(med)}%` }} />}
        {dots.map(d => {
          const size = 6 + Math.min(Math.max(d.w, 0), 8) * 0.8
          return (
            <span
              key={d.key}
              className={`${css.sdot} ${d.diff >= 0 ? css.sdotUp : css.sdotDown} ${d.dir > 0 ? css.sdotR : d.dir < 0 ? css.sdotL : ''}`}
              style={{ left: `${d.px}%`, top: d.lane * ROW + 6, width: size, height: size }}
              title={`${d.name} ${pctDiff(d.diff)}`}
            />
          )
        })}
      </div>
      <div className={css.stripAxis}>
        {ticks.map(t => (
          <span
            key={t}
            style={{ left: `${pos(t)}%`, transform: t === -CLAMP ? 'none' : t === CLAMP ? 'translateX(-100%)' : 'translateX(-50%)' }}
          >
            {tickText(t)}
          </span>
        ))}
      </div>
      <div className={css.stripLegend}>
        <span><i className={`${css.lgDot} ${css.lgUp}`} />高于现价 {up} 只</span>
        <span><i className={`${css.lgDot} ${css.lgDown}`} />低于现价 {items.length - up} 只</span>
        <span>点大小 = 当日权重</span>
        {med != null && <span>虚线 = 中位差异 {pctDiff(med)}</span>}
        {over > 0 && <span>超出 ±{Math.round(CLAMP * 100)}% 的 {over} 只贴边显示</span>}
      </div>
    </div>
  )
}

export function RunStep(props: {
  params: BatchParams
  indexSel: string
  date: Date
  parallel: 3 | 10
  list: Constituent[]
  realMode: boolean
  realErr: string | null
  realAsOf: string
}) {
  const { params, indexSel, date, parallel, list, realMode, realErr, realAsOf } = props
  const meta = indexMeta(indexSel)
  const total = list.length
  const skip = useMemo(() => skipIndexes(total), [total])
  const [running, setRunning] = useState(false)
  const [mode, setMode] = useState<'demo' | 'real' | null>(null)
  const [done, setDone] = useState(0)
  const [logs, setLogs] = useState<LogLine[]>([])
  const [results, setResults] = useState<ValuationResult[] | null>(null)
  const [job, setJob] = useState<JobStatus | null>(null)
  const [modalIdx, setModalIdx] = useState<number | null>(null)
  const [hist, setHist] = useState<JobMeta[] | null>(null)
  const [histSel, setHistSel] = useState<string | null>(null)
  const [histJob, setHistJob] = useState<JobStatus | null>(null)
  const [histModalIdx, setHistModalIdx] = useState<number | null>(null)
  const timerRef = useRef<number | null>(null)
  const pollRef = useRef<number | null>(null)
  const seenRef = useRef<Set<number>>(new Set())
  const failRef = useRef(0)
  const jobIdRef = useRef<string | null>(null)

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    if (pollRef.current !== null) window.clearInterval(pollRef.current)
  }, [])

  const loadHist = async () => {
    try {
      setHist(await fetchJobs())
    } catch {
      setHist([])
    }
  }

  useEffect(() => {
    if (realMode) void loadHist()
  }, [realMode])

  const push = (text: string, kind: LogLine['kind'] = 'info') =>
    setLogs(prev => [...prev, { text, kind }])

  const stopPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const pollOnce = async (jobId: string) => {
    try {
      const st = await pollJob(jobId)
      failRef.current = 0
      setJob(st)
      setDone(st.done)
      for (const r of st.rows) {
        if (seenRef.current.has(r.idx)) continue
        if (r.status === 'ok') {
          seenRef.current.add(r.idx)
          push(`[完成] ${r.name} · 中枢/股 ${r.per_share?.toFixed(2) ?? '—'} · 置信度 ${r.confidence_level ?? '—'}`, 'ok')
        } else if (r.status === 'skip') {
          seenRef.current.add(r.idx)
          push(`[跳过] ${r.name} · ${r.error ?? '未产出结果'}`, 'dim')
        }
      }
      if (st.state === 'done') {
        stopPolling()
        setRunning(false)
        void loadHist()
        const s = st.summary
        push(`[完成] ${st.total} 条处理完毕：估值 ${s?.ok ?? 0} 条 · 跳过 ${s?.skip ?? 0} 条`, 'ok')
        push(`[合成] 拟合点位 ${s?.fitted_point?.toFixed(2) ?? '—'} · 指数收盘 ${s?.index_close?.toFixed(2) ?? '—'}`, 'ok')
      } else if (st.state === 'error') {
        stopPolling()
        setRunning(false)
        push(`[错误] 任务异常：${(st.error ?? '').split('\n')[0]}`, 'dim')
      }
    } catch {
      failRef.current += 1
      push(`[轮询] 第 ${failRef.current} 次查询失败，继续重试`, 'dim')
      if (failRef.current >= 6) {
        stopPolling()
        setRunning(false)
        push('[提示] 连续查询失败，已停止跟踪；任务仍在服务端继续，可点「恢复跟踪」续看', 'dim')
      }
    }
  }

  const startReal = async () => {
    stopPolling()
    setRunning(true)
    setMode('real')
    setDone(0)
    setResults(null)
    setJob(null)
    setLogs([])
    setHistSel(null)
    setHistJob(null)
    setHistModalIdx(null)
    seenRef.current = new Set()
    failRef.current = 0
    push(`[准备] ${meta.name} 成分券 ${total} 条 · 并行度 ${parallel} · 统计抽样 ${STAT_N} · 舆情口径 ${params.sentimentMode === 'llm' ? 'LLM 语义（DeepSeek）' : '规则打分（词频）'} · 数据时点 ${realAsOf} · 估值日期 ${fmtDateShort(date)}（参考口径）`, 'dim')
    try {
      const { job_id } = await runBatch({
        index: indexSel,
        parallel,
        stat_n: STAT_N,
        weights: { dcf: params.dcf / 100, comp: params.comp / 100, sent: params.sent / 100 },
        sentiment_rounds: params.sentiment,
        sentiment_mode: params.sentimentMode,
      })
      jobIdRef.current = job_id
      push(`[任务] ${job_id} 已提交，开始跟踪`, 'dim')
      pollOnce(job_id)
      pollRef.current = window.setInterval(() => pollOnce(job_id), 2500)
    } catch (e) {
      setRunning(false)
      push(`[错误] 提交任务失败：${e instanceof Error ? e.message : String(e)} · 批跑服务不可达`, 'dim')
    }
  }

  const stop = () => {
    stopPolling()
    if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    timerRef.current = null
    setRunning(false)
    push(mode === 'real' ? '[停止] 已停止跟踪；任务仍在服务端继续执行，可点「恢复跟踪」续看' : '[停止] 演示跑批已手动停止', 'dim')
  }

  const resume = () => {
    if (!jobIdRef.current) return
    const jobId = jobIdRef.current
    setRunning(true)
    push('[恢复] 继续跟踪任务进度', 'dim')
    pollOnce(jobId)
    pollRef.current = window.setInterval(() => pollOnce(jobId), 2500)
  }

  const startDemo = () => {
    stopPolling()
    setRunning(true)
    setMode('demo')
    setDone(0)
    setResults(null)
    setJob(null)
    setLogs([])
    const all = list.map((c, i) => valuationPair(c, i))
    setResults(all)
    const batches = Math.ceil(total / parallel)
    push(
      `[准备] ${meta.name} 成分券 ${total} 条 · 并行度 每批 ${parallel} 条 · 舆情轮数上限 ${params.sentiment} · 估值日期 ${fmtDateShort(date)}`,
      'dim',
    )
    let b = 0
    const tick = () => {
      b += 1
      const from = (b - 1) * parallel + 1
      const to = Math.min(b * parallel, total)
      setDone(to)
      push(`[批次 ${b}/${batches}] 估值完成 ${from}–${to}（用时示例 ${(18 + Math.random() * 14).toFixed(0)}s）`, 'ok')
      for (const i of skip) {
        if (i >= from - 1 && i < to) push(`[跳过] ${list[i].name} · β 无法计算 → 陈老师技能自动跳过`, 'dim')
      }
      if (to >= total) {
        setRunning(false)
        const vA = synthLevel(list, all.map(r => r.chen), skip)
        const vB = synthLevel(list, all.map(r => r.shi), skip)
        const pA = synthLevel(list, all.map(r => r.price), skip)
        const idxA = (vA / pA) * meta.baseLevel
        const idxB = (vB / pA) * meta.baseLevel
        push(`[完成] ${total} 条处理完毕：估值 ${total - skip.size} 条 · 跳过 ${skip.size} 条`, 'ok')
        push(`[合成] 陈老师拟合点位 ${idxA.toFixed(2)} · 石总 ${idxB.toFixed(2)} · 参考 ${meta.baseLevel.toFixed(2)}`, 'ok')
      } else {
        timerRef.current = window.setTimeout(tick, 320)
      }
    }
    timerRef.current = window.setTimeout(tick, 260)
  }

  const finished = mode === 'demo' && results !== null && !running && done >= total
  const realDone = mode === 'real' && job !== null && job.state === 'done'
  const realPartial = mode === 'real' && job !== null && job.state !== 'done'
  const vA = finished ? synthLevel(list, results!.map(r => r.chen), skip) : 0
  const vB = finished ? synthLevel(list, results!.map(r => r.shi), skip) : 0
  const pA = finished ? synthLevel(list, results!.map(r => r.price), skip) : 1
  const idxA = finished ? (vA / pA) * meta.baseLevel : 0
  const idxB = finished ? (vB / pA) * meta.baseLevel : 0

  const progTotal = mode === 'real' && job ? job.total : total
  const prog = progTotal > 0 ? (done / progTotal) * 100 : 0
  const summ = realDone && job && job.summary ? job.summary : null
  const overallDiff =
    summ && summ.fitted_point != null && summ.index_close ? summ.fitted_point / summ.index_close - 1 : null

  const demoRows = finished && results ? list.map((c, i) => ({ i, c, r: results[i], skipped: skip.has(i) })) : []
  const demoDiffItems = demoRows
    .filter(x => !x.skipped && x.r.price > 0)
    .map(x => ({ name: x.c.name, diff: x.r.chen / x.r.price - 1, w: x.c.w }))
  const demoUp = demoDiffItems.filter(x => x.diff >= 0).length
  const demoOverallDiff = finished ? idxA / meta.baseLevel - 1 : null

  const realDiffItems =
    realDone && job
      ? job.rows.flatMap(r => {
          const d = diffOf(r.per_share, r.close)
          return r.status === 'ok' && d != null ? [{ name: r.name, diff: d, w: r.weight ?? 0 }] : []
        })
      : []
  const realMed = medianOf(realDiffItems.map(x => x.diff))
  const realUp = realDiffItems.filter(x => x.diff >= 0).length
  const histChart =
    hist !== null &&
    hist.filter(h => h.index === indexSel && h.state === 'done' && h.fitted_point != null && h.index_close != null).length >= 2

  return (
    <section>
      <h2>运行与报告</h2>
      <p className={css.sub}>
        {realMode
          ? '真实跑批：批跑服务逐券执行「输入组装 → 估值引擎 → 统计校验 → HTML 报告 → 八项机检」，按权重合成拟合点位。'
          : '并行跑批，逐家生成报告，最后输出总结报告；两版拟合点位并排对比。'}
      </p>
      <div className={css.sumgrid}>
        <div className={css.sumbox}><div className={css.sk}>指数</div><div className={css.sv}>{meta.name}</div></div>
        <div className={css.sumbox}><div className={css.sk}>估值日期</div><div className={css.sv}>{fmtDateShort(date)}</div></div>
        <div className={css.sumbox}><div className={css.sk}>方法加权</div><div className={css.sv}>DCF {params.dcf}% · 可比 {params.comp}% · 舆情 {params.sent}%</div></div>
        <div className={css.sumbox}><div className={css.sk}>舆情口径</div><div className={css.sv}>{params.sentimentMode === 'llm' ? 'LLM 语义' : '规则打分'} · ≤ {params.sentiment} 轮</div></div>
        <div className={css.sumbox}><div className={css.sk}>并行度</div><div className={css.sv}>每批 {parallel} 条</div></div>
        <div className={css.sumbox}><div className={css.sk}>数据时点</div><div className={css.sv}>{realMode ? realAsOf : '演示（本地生成）'}</div></div>
      </div>
      <div className={css.runbox}>
        {realMode ? (
          <>
            <button className={`${css.btn} ${css.btnPrimary} ${css.btnBlock}`} disabled={running} onClick={startReal}>
              {realDone ? '重新跑批' : '开始跑批（真实执行）'}
            </button>
            {running && <button className={css.btn} style={{ marginLeft: 10 }} onClick={stop}>停止</button>}
            {!running && realPartial && <button className={css.btn} style={{ marginLeft: 10 }} onClick={resume}>恢复跟踪</button>}
          </>
        ) : (
          <>
            <button className={`${css.btn} ${css.btnPrimary} ${css.btnBlock}`} disabled={running} onClick={startDemo}>
              {finished ? '重新演示跑批' : '开始演示跑批'}
            </button>
            {running && <button className={css.btn} style={{ marginLeft: 10 }} onClick={stop}>停止</button>}
          </>
        )}
        {!realMode && (
          <p className={css.hint} style={{ margin: '10px 0 0' }}>
            批跑服务未连接（{realErr ?? '未知原因'}）→ 当前为演示模式，不请求真实服务。
          </p>
        )}
        <div className={css.progress}><i style={{ width: `${prog}%` }} /></div>
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
          <div className={css.poster}>
            <div className={css.posterKicker}>
              <i className={css.posterMark} />
              {meta.name} {meta.code} · 演示跑批（本地生成） · 估值日期 {fmtDateShort(date)} · 并行 每批 {parallel} 条 · 舆情 ≤ {params.sentiment} 轮
            </div>
            <div className={css.posterHead}>
              <div className={css.posterMain}>
                <div className={css.posterLbl}>拟合点位 · 陈老师口径（示例）</div>
                <div className={css.posterNum}>{idxA.toFixed(2)}</div>
                <div className={css.posterSub}>
                  参考点位 {meta.baseLevel.toFixed(2)}
                  <span className={css.posterSep}>·</span>
                  整体差异
                  <b className={demoOverallDiff != null && demoOverallDiff >= 0 ? css.up : css.down}>
                    {demoOverallDiff == null ? '—' : pctDiff(demoOverallDiff)}
                  </b>
                </div>
              </div>
              <div className={css.posterSide}>
                <div className={css.pcell}><span>石总拟合点位</span><b>{idxB.toFixed(2)}</b></div>
                <div className={css.pcell}><span>陈较石总</span><b>{idxB > 0 ? pctDiff(idxA / idxB - 1) : '—'}</b></div>
                <div className={css.pcell}><span>高于现价</span><b className={css.up}>{demoUp}<small>只</small></b></div>
                <div className={css.pcell}><span>低于现价</span><b className={css.down}>{demoDiffItems.length - demoUp}<small>只</small></b></div>
              </div>
            </div>
            <DiffStrip items={demoDiffItems} />
            <div className={css.posterNote}>
              <b>差异口径：</b>差异 = 估值中枢/股 ÷ 现价 − 1，只展示估值与现价的偏离，<b>不做反向校正</b>（不把估值改写成现价，也不把现价改写成估值）。演示数字为本地生成，仅示意展示结构。
            </div>
          </div>
          <h3>
            逐券重点结果
            <span className={css.h3sub}>共 {total} 条 · 出估值 {total - skip.size} 条 · 跳过 {skip.size} 条 · 点击看明细</span>
          </h3>
          <div className={css.resPanel}>
            <div className={css.resGrid}>
              {demoRows.map(({ i, c, r, skipped }) => {
                const d = skipped ? null : r.chen / r.price - 1
                const dShi = skipped ? null : r.shi / r.price - 1
                return (
                  <button key={i} className={`${css.resCard} ${skipped ? css.resCardSkip : ''}`} onClick={() => setModalIdx(i)}>
                    <div className={css.resTop}>
                      <span className={css.resNm}>{c.name}</span>
                      <span className={css.resCode}>№{String(i + 1).padStart(2, '0')}</span>
                      {skipped && <span className={`${css.tag} ${css.tagWarn}`} style={{ marginLeft: 'auto' }}>跳过</span>}
                    </div>
                    {skipped ? (
                      <div className={css.resSkipTxt}>跳过：β 无法计算，未产出估值</div>
                    ) : (
                      <div className={css.resMetrics}>
                        <div className={css.resM}><span>陈中枢</span><b>{r.chen.toFixed(2)}</b></div>
                        <div className={css.resM}><span>石中枢</span><b>{r.shi.toFixed(2)}</b></div>
                        <div className={`${css.resM} ${css.resMdiff}`}>
                          <span>差异（陈）</span>
                          <b className={d != null && d >= 0 ? css.up : css.down}>{d == null ? '—' : pctDiff(d)}</b>
                        </div>
                      </div>
                    )}
                    <div className={css.resMeta}>
                      <span>现价 {r.price.toFixed(2)}</span>
                      <span>权重 {c.w.toFixed(2)}%</span>
                      {dShi != null && <span>石差异 {pctDiff(dShi)}</span>}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
          <div className={css.note}>
            <b>不能直接等权平均：</b>拟合点位 = Σ(估值×权重) / Σ(价格×权重) × 参考点位。当日权重盘中才出，可先用前一日因子计算；跳过券不计入分子分母。演示数据仅用于流程演示，不代表真实估值结论。
          </div>
          {modalIdx !== null && (
            <ReportModal
              name={list[modalIdx].name}
              i={modalIdx}
              r={results![modalIdx]}
              w={list[modalIdx].w}
              skip={skip.has(modalIdx)}
              onClose={() => setModalIdx(null)}
            />
          )}
        </div>
      )}
      {realDone && summ && job && (
        <div className={css.result}>
          <div className={css.poster}>
            <div className={css.posterKicker}>
              <i className={css.posterMark} />
              {meta.name} {meta.code} · 估值日期 {fmtDateShort(date)} · 数据时点（权重） {realAsOf} ·{' '}
              {params.sentimentMode === 'llm' ? 'LLM 语义舆情' : '规则舆情'} ≤ {params.sentiment} 轮 · 并行 每批 {parallel} 条 · 任务{' '}
              <span className={css.posterJob}>{job.id}</span>
            </div>
            <div className={css.posterHead}>
              <div className={css.posterMain}>
                <div className={css.posterLbl}>拟合点位 · 加权合成 · 真实执行</div>
                <div className={css.posterNum}>{summ.fitted_point != null ? summ.fitted_point.toFixed(2) : '—'}</div>
                <div className={css.posterSub}>
                  指数收盘 {summ.index_close != null ? summ.index_close.toFixed(2) : '—'}
                  <span className={css.posterSep}>·</span>
                  整体差异
                  <b className={overallDiff == null ? '' : overallDiff >= 0 ? css.up : css.down}>
                    {overallDiff == null ? '—' : pctDiff(overallDiff)}
                  </b>
                </div>
              </div>
              <div className={css.posterSide}>
                <div className={css.pcell}><span>高于现价</span><b className={css.up}>{realUp}<small>只</small></b></div>
                <div className={css.pcell}><span>低于现价</span><b className={css.down}>{realDiffItems.length - realUp}<small>只</small></b></div>
                <div className={css.pcell}><span>中位差异</span><b>{realMed == null ? '—' : pctDiff(realMed)}</b></div>
                <div className={css.pcell}><span>出估值 / 跳过</span><b>{summ.ok}<small>/ {summ.skip}</small></b></div>
              </div>
            </div>
            <DiffStrip items={realDiffItems} />
            <div className={css.posterNote}>
              <b>差异口径：</b>差异 = 中枢/股 ÷ 现价 − 1，只展示估值与现价的偏离，<b>不做反向校正</b>（不把估值改写成现价，也不把现价改写成估值）。拟合点位 = 指数收盘 × Σ(权重×中枢/股) / Σ(权重×收盘价)。
            </div>
          </div>
          <h3>
            逐券重点结果
            <span className={css.h3sub}>共 {job.rows.length} 条 · 出估值 {summ.ok} 条 · 跳过 {summ.skip} 条 · 点击看明细 · 报告新窗口打开</span>
          </h3>
          <div className={css.resPanel}>
            <div className={css.resGrid}>
              {job.rows.map(r => {
                const ok = r.status === 'ok'
                const d = ok ? diffOf(r.per_share, r.close) : null
                return (
                  <button key={r.idx} className={`${css.resCard} ${ok ? '' : css.resCardSkip}`} onClick={() => setModalIdx(r.idx)}>
                    <div className={css.resTop}>
                      <span className={css.resNm}>{r.name}</span>
                      <span className={css.resCode}>{r.secucode}</span>
                      {!ok && <span className={`${css.tag} ${css.tagWarn}`}>跳过</span>}
                      {ok && r.warnings && r.warnings.length > 0 && <span className={`${css.tag} ${css.tagMut}`}>预警 {r.warnings.length}</span>}
                    </div>
                    {ok ? (
                      <div className={css.resMetrics}>
                        <div className={css.resM}><span>中枢/股</span><b>{r.per_share != null ? r.per_share.toFixed(2) : '—'}</b></div>
                        <div className={css.resM}><span>现价</span><b>{r.close != null ? r.close.toFixed(2) : '—'}</b></div>
                        <div className={`${css.resM} ${css.resMdiff}`}>
                          <span>差异</span>
                          <b className={d == null ? '' : d >= 0 ? css.up : css.down}>{d == null ? '—' : pctDiff(d)}</b>
                        </div>
                      </div>
                    ) : (
                      <div className={css.resSkipTxt}>跳过：{r.error ?? '未产出结果'}</div>
                    )}
                    <div className={css.resMeta}>
                      <span>{r.industry ?? '—'}</span>
                      <span>权重 {r.weight != null ? r.weight.toFixed(2) : '—'}%</span>
                      {ok && <span>置信度 {r.confidence_level ?? '—'}</span>}
                      {ok && r.interval && <span>区间 {Math.round(r.interval[0])} ~ {Math.round(r.interval[1])}</span>}
                    </div>
                    {ok && r.report && (
                      <div className={css.resFoot}>
                        <span
                          className={css.linkBtn}
                          onClick={e => {
                            e.stopPropagation()
                            window.open(reportUrl(job.id, r.report!), '_blank', 'noopener')
                          }}
                        >
                          打开完整报告 ↗
                        </span>
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
          <div className={css.note}>
            拟合点位 = 指数收盘 × Σ(权重×中枢/股) / Σ(权重×收盘价)，等价于按权重汇总逐券「中枢/现价−1」差异；跳过券不计入分子分母。估值中枢为引擎综合中枢（DCF/可比/舆情按 {params.dcf}/{params.comp}/{params.sent} 加权），逐券口径见各券报告。本结果为探索性研究参考，不构成投资建议。
          </div>
          {modalIdx !== null && (
            <ReportModal
              name={job.rows.find(r => r.idx === modalIdx)?.name ?? '—'}
              i={modalIdx}
              r={results?.[modalIdx] ?? { price: 0, chen: 0, shi: 0 }}
              w={job.rows.find(r => r.idx === modalIdx)?.weight ?? 0}
              real={job.rows.find(r => r.idx === modalIdx) ?? null}
              jobId={job.id}
              onClose={() => setModalIdx(null)}
            />
          )}
        </div>
      )}
      {realPartial && job && job.rows.length > 0 && (
        <div className={css.detailList} style={{ marginTop: 16 }}>
          <h4>逐券进度（已完成 {job.done}/{job.total}）</h4>
          {job.rows.map(r => {
            const ok = r.status === 'ok'
            const d = ok ? diffOf(r.per_share, r.close) : null
            return (
              <button key={r.idx} className={css.drow} onClick={() => setModalIdx(r.idx)}>
                <span className={css.drowNm}>
                  {r.name}
                  {r.status === 'skip' && <span className={`${css.tag} ${css.tagWarn}`} style={{ marginLeft: 8 }}>跳过</span>}
                  {(r.status === 'pending' || r.status === 'running') && <span className={css.tag} style={{ marginLeft: 8 }}>等待中</span>}
                </span>
                <span className={css.drowVals}>
                  <span>价 {r.close != null ? r.close.toFixed(2) : '—'}</span>
                  <span>中枢/股 <b>{ok && r.per_share != null ? r.per_share.toFixed(2) : '—'}</b></span>
                  {d != null && <span>差异 <b className={d >= 0 ? css.up : css.down}>{pctDiff(d)}</b></span>}
                </span>
              </button>
            )
          })}
          {modalIdx !== null && (
            <ReportModal
              name={job.rows.find(r => r.idx === modalIdx)?.name ?? '—'}
              i={modalIdx}
              r={results?.[modalIdx] ?? { price: 0, chen: 0, shi: 0 }}
              w={job.rows.find(r => r.idx === modalIdx)?.weight ?? 0}
              real={job.rows.find(r => r.idx === modalIdx) ?? null}
              jobId={job.id}
              onClose={() => setModalIdx(null)}
            />
          )}
        </div>
      )}
      {realMode && (
        <div style={{ marginTop: 22 }}>
          <h3>
            历史跑批（{hist === null ? '加载中…' : hist.length} 次 · 报告存于批跑服务，可随时回看）
            <span className={css.op} style={{ marginLeft: 'auto' }} onClick={() => void loadHist()}>刷新</span>
          </h3>
          {hist !== null && hist.length === 0 && <p className={css.hint}>暂无历史任务记录。</p>}
          {hist !== null && hist.length > 0 && (
            <div className={css.tblWrap}>
              <table className={css.clist}>
                <thead>
                  <tr><th>#</th><th>任务</th><th>指数</th><th>舆情</th><th>提交时间</th><th>状态</th><th className={css.numTd}>拟合点位</th><th className={css.numTd}>指数收盘</th><th className={css.numTd}>偏离</th><th className={css.numTd}>出估值/跳过</th><th>操作</th></tr>
                </thead>
                <tbody>
                  {hist.map((h, i) => {
                    const st = h.state === 'done' ? '完成' : h.state === 'running' ? '进行中' : '异常'
                    const stCls = h.state === 'done' ? css.tagOk : h.state === 'running' ? css.tagWarn : css.tagErr
                    const dev =
                      h.fitted_point != null && h.index_close
                        ? `${(((h.fitted_point / h.index_close) - 1) * 100).toFixed(2)}%`
                        : '—'
                    const expanded = histSel === h.id && histJob !== null && histJob.id === h.id
                    return (
                      <Fragment key={h.id}>
                        <tr>
                          <td className={css.mono}>{i + 1}</td>
                          <td className={`${css.mono} ${css.jobId}`}>{h.id}</td>
                          <td>{indexMeta(h.index).name}</td>
                          <td><span className={`${css.tag} ${h.sentiment_mode === 'llm' ? css.tagOk : css.tagMut}`}>{h.sentiment_mode === 'llm' ? 'LLM' : '规则'}</span></td>
                          <td className={css.timeCell}>{h.created}</td>
                          <td><span className={`${css.tag} ${stCls}`}>{st}</span></td>
                          <td className={`${css.mono} ${css.numTd}`}><b>{h.fitted_point != null ? h.fitted_point.toFixed(2) : '—'}</b></td>
                          <td className={`${css.mono} ${css.numTd}`}>{h.index_close != null ? h.index_close.toFixed(2) : '—'}</td>
                          <td className={`${css.mono} ${css.numTd}`}>{dev}</td>
                          <td className={`${css.mono} ${css.numTd}`}>{h.ok != null ? `${h.ok} / ${h.skip ?? 0}` : `${h.done}/${h.total}`}</td>
                          <td>
                            <span className={css.op} onClick={() => window.open(reportUrl(h.id, 'summary.html'), '_blank', 'noopener')}>汇总报告 ↗</span>
                            <span
                              className={css.op}
                              style={{ marginLeft: 10 }}
                              onClick={async () => {
                                if (expanded) {
                                  setHistSel(null)
                                  setHistJob(null)
                                  setHistModalIdx(null)
                                  return
                                }
                                setHistSel(h.id)
                                setHistJob(null)
                                try {
                                  setHistJob(await pollJob(h.id))
                                } catch {
                                  setHistJob(null)
                                }
                              }}
                            >
                              {expanded ? '收起' : '逐券'}
                            </span>
                          </td>
                        </tr>
                        {expanded && (
                          <tr>
                            <td colSpan={11} style={{ padding: 0, border: 0 }}>
                              <div className={css.detailList}>
                                {histJob!.rows.map(r => {
                                  const ok = r.status === 'ok'
                                  const d = ok ? diffOf(r.per_share, r.close) : null
                                  return (
                                    <button key={r.idx} className={css.drow} onClick={() => setHistModalIdx(r.idx)}>
                                      <span className={css.drowNm}>
                                        {r.name}
                                        {!ok && <span className={`${css.tag} ${css.tagWarn}`} style={{ marginLeft: 8 }}>跳过</span>}
                                        {ok && r.warnings && r.warnings.length > 0 && <span className={`${css.tag} ${css.tagMut}`} style={{ marginLeft: 8 }}>预警 {r.warnings.length}</span>}
                                      </span>
                                      <span className={css.drowVals}>
                                        <span>价 {r.close != null ? r.close.toFixed(2) : '—'}</span>
                                        <span>中枢/股 <b>{ok && r.per_share != null ? r.per_share.toFixed(2) : '—'}</b></span>
                                        <span>差异 <b className={d == null ? '' : d >= 0 ? css.up : css.down}>{d == null ? '—' : pctDiff(d)}</b></span>
                                        {ok && r.report && (
                                          <span className={css.linkBtn} onClick={e => { e.stopPropagation(); window.open(reportUrl(histJob!.id, r.report!), '_blank', 'noopener') }}>报告 ↗</span>
                                        )}
                                      </span>
                                    </button>
                                  )
                                })}
                              </div>
                              {histModalIdx !== null && (
                                <ReportModal
                                  name={histJob!.rows.find(r => r.idx === histModalIdx)?.name ?? '—'}
                                  i={histModalIdx}
                                  r={{ price: 0, chen: 0, shi: 0 }}
                                  w={histJob!.rows.find(r => r.idx === histModalIdx)?.weight ?? 0}
                                  real={histJob!.rows.find(r => r.idx === histModalIdx) ?? null}
                                  jobId={histJob!.id}
                                  onClose={() => setHistModalIdx(null)}
                                />
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {histChart && <HistoryChart hist={hist} indexSel={indexSel} />}
        </div>
      )}
    </section>
  )
}
