/** Step 6 运行与报告：真实跑批（Mac 批跑服务 3089）+ 服务不可达时回退演示跑批。 */

import { Fragment, useEffect, useRef, useState } from 'react'
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
import { fetchJobs, pollJob, reportUrl, runBatch, type JobMeta, type JobStatus } from '../api'
import css from '../ValuationPage.module.css'
import { ReportModal } from '../ReportModal'

interface LogLine {
  text: string
  kind: 'ok' | 'dim' | 'info'
}

const STAT_N = 1000

/** 近 N 次跑批走势：拟合点位（金，实线）vs 指数收盘（青，虚线）。 */
function HistoryChart({ hist }: { hist: JobMeta[] }) {
  const pts = hist
    .filter(h => h.state === 'done' && h.fitted_point != null && h.index_close != null && h.index_close > 0)
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
        近 {pts.length} 次跑批 · 拟合点位 vs 指数收盘
        <span className={css.clegend}>
          <i style={{ background: '#F5C24B' }} />拟合点位<i style={{ background: '#38BDF8' }} />指数收盘
        </span>
      </div>
      <svg className={css.chartSvg} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-label="历史跑批走势图">
        {grid.map(gv => (
          <g key={gv}>
            <line x1={PAD} y1={Y(gv)} x2={W - PAD} y2={Y(gv)} stroke="#1F2E4A" strokeWidth="1" />
            <text x="6" y={Y(gv) + 4} fill="#5A6B8C" fontSize="10" fontFamily="Consolas,monospace">{Math.round(gv)}</text>
          </g>
        ))}
        <path d={path(idx)} fill="none" stroke="#38BDF8" strokeWidth="2" strokeDasharray="4 3" />
        <path d={path(fit)} fill="none" stroke="#F5C24B" strokeWidth="2" />
        {fit.map((v, i) => <circle key={i} cx={X(i)} cy={Y(v)} r="2.6" fill="#F5C24B" />)}
      </svg>
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
  const total = list.length
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
    push(`[准备] 上证50 成分券 ${total} 条 · 并行度 ${parallel} · 统计抽样 ${STAT_N} · 数据时点 ${realAsOf} · 估值日期 ${fmtDateShort(date)}（参考口径）`, 'dim')
    try {
      const { job_id } = await runBatch({
        index: 'sh50',
        parallel,
        stat_n: STAT_N,
        weights: { dcf: params.dcf / 100, comp: params.comp / 100, sent: params.sent / 100 },
        sentiment_rounds: params.sentiment,
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

  const finished = mode === 'demo' && results !== null && !running && done >= total
  const realDone = mode === 'real' && job !== null && job.state === 'done'
  const realPartial = mode === 'real' && job !== null && job.state !== 'done'
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

  const progTotal = mode === 'real' && job ? job.total : total
  const prog = progTotal > 0 ? (done / progTotal) * 100 : 0
  const summ = realDone && job && job.summary ? job.summary : null
  const diffPct =
    summ && summ.fitted_point != null && summ.index_close
      ? `${(((summ.fitted_point / summ.index_close) - 1) * 100).toFixed(2)}%`
      : '—'
  const histChart =
    hist !== null &&
    hist.filter(h => h.state === 'done' && h.fitted_point != null && h.index_close != null).length >= 2

  return (
    <section>
      <h2>运行与报告</h2>
      <p className={css.sub}>
        {realMode
          ? '真实跑批：批跑服务逐券执行「输入组装 → 估值引擎 → 统计校验 → HTML 报告 → 八项机检」，按权重合成拟合点位。'
          : '并行跑批，逐家生成报告，最后输出总结报告；两版拟合点位并排对比。'}
      </p>
      <div className={css.sumgrid}>
        <div className={css.sumbox}><div className={css.sk}>指数</div><div className={css.sv}>{indexSel}</div></div>
        <div className={css.sumbox}><div className={css.sk}>估值日期</div><div className={css.sv}>{fmtDateShort(date)}</div></div>
        <div className={css.sumbox}><div className={css.sk}>方法加权</div><div className={css.sv}>DCF {params.dcf}% · 可比 {params.comp}% · 舆情 {params.sent}%</div></div>
        <div className={css.sumbox}><div className={css.sk}>舆情轮数</div><div className={css.sv}>≤ {params.sentiment} 轮</div></div>
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
          <div className={css.repGrid}>
            <div className={css.sumcard}>
              <h4>拟合点位 · 陈老师</h4>
              <p className={css.level}>{idxA.toFixed(2)} <small>（加权合成 · 示例）</small></p>
              <p className={css.delta}>石总 {idxB.toFixed(2)} · 参考点位 {BASE_LEVEL.toFixed(2)}</p>
              <svg className={css.spark} viewBox="0 0 320 84" aria-hidden>
                <polyline fill="none" stroke="#2A3D60" strokeWidth="1.5" points={noise.map((v, i) => `${sx(i)},${sy(v)}`).join(' ')} />
                <circle cx={sx(10)} cy={sy(idxB)} r="3.5" fill="#F5C24B" />
                <circle cx={sx(11)} cy={sy(idxA)} r="3.5" fill="#38BDF8" />
              </svg>
              <div className={css.legend}>
                <span><i style={{ background: '#38BDF8' }} />陈老师</span>
                <span><i style={{ background: '#F5C24B' }} />石总</span>
                <span><i style={{ background: '#2A3D60' }} />参考走势（示例）</span>
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
            <b>不能直接等权平均：</b>等权结果与指数点位对不上；拟合点位 = Σ(估值×权重) / Σ(价格×权重) × 参考点位。当日权重盘中才出，可先用前一日因子计算；跳过券不计入分子分母。
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
      {realDone && summ && job && (
        <div className={css.result}>
          <div className={css.repGrid}>
            <div className={css.sumcard}>
              <h4>拟合点位 · 陈老师口径</h4>
              <p className={css.level}>{summ.fitted_point != null ? summ.fitted_point.toFixed(2) : '—'} <small>（加权合成 · 真实执行）</small></p>
              <p className={css.delta}>指数收盘 {summ.index_close != null ? summ.index_close.toFixed(2) : '—'} · 偏离 {diffPct}</p>
            </div>
            <div className={css.cmp2}>
              <h4>本次跑批</h4>
              <table>
                <tbody>
                  <tr><th>拟合点位</th><td>{summ.fitted_point != null ? summ.fitted_point.toFixed(2) : '—'}</td></tr>
                  <tr><th>指数收盘</th><td>{summ.index_close != null ? summ.index_close.toFixed(2) : '—'}</td></tr>
                  <tr><th>样本</th><td>{summ.total} 条</td></tr>
                  <tr><th>出估值 / 跳过</th><td>{summ.ok} / {summ.skip}</td></tr>
                  <tr><th>数据时点（权重）</th><td>{realAsOf}</td></tr>
                  <tr><th>任务</th><td className={css.mono}>{job.id}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <div className={css.detailList} style={{ marginTop: 16 }}>
            <h4>逐券结果（点击查看明细 · 报告新窗口打开）</h4>
            {job.rows.map(r => {
              const ok = r.status === 'ok'
              const ratio = ok && r.per_share != null && r.close ? (r.per_share / r.close).toFixed(2) : null
              return (
                <button key={r.idx} className={css.drow} onClick={() => setModalIdx(r.idx)}>
                  <span className={css.drowNm}>
                    {r.name}
                    {!ok && <span className={`${css.tag} ${css.tagWarn}`} style={{ marginLeft: 8 }}>跳过</span>}
                    {ok && r.warnings && r.warnings.length > 0 && <span className={`${css.tag} ${css.tagMut}`} style={{ marginLeft: 8 }}>预警 {r.warnings.length}</span>}
                  </span>
                  <span className={css.drowVals}>
                    <span>价 {r.close != null ? r.close.toFixed(2) : '—'}</span>
                    <span>中枢/股 <b>{ok && r.per_share != null ? r.per_share.toFixed(2) : '—'}</b></span>
                    <span>估值/价 <b>{ratio ?? '—'}</b></span>
                    {ok && r.report && (
                      <span className={css.linkBtn} onClick={e => { e.stopPropagation(); window.open(reportUrl(job.id, r.report!), '_blank', 'noopener') }}>报告 ↗</span>
                    )}
                  </span>
                </button>
              )
            })}
          </div>
          <div className={css.note}>
            拟合点位 = 指数收盘 × Σ(权重×每股估值) / Σ(权重×收盘价)；跳过券不计入分子分母。估值中枢为引擎综合中枢（DCF/可比/舆情按 {params.dcf}/{params.comp}/{params.sent} 加权），逐券口径见各券报告。本结果为探索性研究参考，不构成投资建议。
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
                  <tr><th>#</th><th>任务</th><th>提交时间</th><th>状态</th><th className={css.numTd}>拟合点位</th><th className={css.numTd}>指数收盘</th><th className={css.numTd}>偏离</th><th className={css.numTd}>出估值/跳过</th><th>操作</th></tr>
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
                          <td className={css.mono}>{h.id}</td>
                          <td>{h.created}</td>
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
                            <td colSpan={9} style={{ padding: 0, border: 0 }}>
                              <div className={css.detailList}>
                                {histJob!.rows.map(r => {
                                  const ok = r.status === 'ok'
                                  const ratio = ok && r.per_share != null && r.close ? (r.per_share / r.close).toFixed(2) : null
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
                                        <span>估值/价 <b>{ratio ?? '—'}</b></span>
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
          {histChart && <HistoryChart hist={hist} />}
        </div>
      )}
    </section>
  )
}
