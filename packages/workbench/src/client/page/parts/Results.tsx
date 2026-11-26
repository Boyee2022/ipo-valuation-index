/** 逐券结果：差异分布、方向占比、逐券重点结果与报告入口。 */

import { useState } from 'react'
import { fmtNum, medianOf, pctDiff, type BatchParams } from '../data'
import { reportUrl, type JobStatus, type JobRow } from '../api'
import { ReportModal } from '../ReportModal'
import { ShadowCard } from './Shadow'
import css from '../ValuationPage.module.css'

const diffOf = (per?: number | null, close?: number | null) =>
  per != null && close != null && close > 0 ? per / close - 1 : null

const isExtreme = (d: number | null) => d != null && (d >= 4 || d <= -0.8)

const tickText = (x: number) => (x === 0 ? '0' : `${x > 0 ? '+' : '−'}${Math.abs(Math.round(x * 100))}%`)

interface DiffItem {
  name: string
  diff: number
  w: number
}

/** 逐券差异分布（点带）：横轴 = 中枢/股相对现价的差异，点大小 = 当日权重。 */
function DiffStrip({ items }: { items: DiffItem[] }) {
  if (items.length === 0) return <p className={css.empty}>无可用于差异展示的逐券结果。</p>
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

const HIST_BINS: { label: string; test: (d: number) => boolean; neg: boolean }[] = [
  { label: '≤−100%', test: d => d < -1, neg: true },
  { label: '−100~−50', test: d => d >= -1 && d < -0.5, neg: true },
  { label: '−50~−20', test: d => d >= -0.5 && d < -0.2, neg: true },
  { label: '−20~0', test: d => d >= -0.2 && d < 0, neg: true },
  { label: '0~+20', test: d => d >= 0 && d < 0.2, neg: false },
  { label: '+20~+50', test: d => d >= 0.2 && d < 0.5, neg: false },
  { label: '+50~+100', test: d => d >= 0.5 && d < 1, neg: false },
  { label: '≥+100%', test: d => d >= 1, neg: false },
]

/** 逐券差异直方图：红 = 高于现价，绿 = 低于现价（A 股红涨绿跌口径）。 */
function DiffHistogram({ items }: { items: DiffItem[] }) {
  if (items.length === 0) return <p className={css.empty}>无可用于差异分布的逐券结果。</p>
  const counts = HIST_BINS.map(b => items.filter(x => b.test(x.diff)).length)
  const max = Math.max(1, ...counts)
  return (
    <div>
      <div className={css.hist}>
        {counts.map((n, i) => (
          <div className={css.histCol} key={HIST_BINS[i].label}>
            <span className={css.histN}>{n}</span>
            <i
              className={`${css.histBar} ${HIST_BINS[i].neg ? css.histBarDown : css.histBarUp}`}
              style={{ height: `${n > 0 ? Math.max(2, (n / max) * 88) : 0}%` }}
            />
          </div>
        ))}
      </div>
      <div className={css.histX}>
        {HIST_BINS.map(b => <span key={b.label}>{b.label}</span>)}
      </div>
    </div>
  )
}

function DirectionDonut({ up, down }: { up: number; down: number }) {
  const total = up + down
  const R = 54
  const CIRC = 2 * Math.PI * R
  const upLen = total > 0 ? (up / total) * CIRC : 0
  const downLen = total > 0 ? (down / total) * CIRC : 0
  return (
    <div className={css.donutWrap}>
      <svg className={css.donutSvg} viewBox="0 0 132 132" aria-label="估值方向占比环图">
        <circle className={css.donutTrack} cx="66" cy="66" r={R} fill="none" strokeWidth="12" />
        <circle className={css.donutUp} cx="66" cy="66" r={R} fill="none" strokeWidth="12" strokeDasharray={`${upLen} ${CIRC - upLen}`} />
        <circle className={css.donutDown} cx="66" cy="66" r={R} fill="none" strokeWidth="12" strokeDasharray={`${downLen} ${CIRC - downLen}`} strokeDashoffset={-upLen} />
      </svg>
      <div className={css.donutCenter}>
        <b>{total > 0 ? `${Math.round((up / total) * 100)}%` : '—'}</b>
        <span>高于现价占比</span>
      </div>
    </div>
  )
}

export function Results(props: {
  job: JobStatus | null
  params: BatchParams
  loading: boolean
  onAdoption: (code: string, action: 'adopted' | 'rejected' | 'clear') => Promise<void>
}) {
  const { job, params, loading, onAdoption } = props
  const [sel, setSel] = useState<JobRow | null>(null)

  if (!job) {
    return (
      <div className={css.card}>
        <div className={css.cardHd}>逐券结果 <span className={css.cardHdR}>RESULTS</span></div>
        <div className={css.cardBd}>
          <p className={css.empty}>{loading ? '正在读取逐券结果…' : '尚无逐券结果。提交一次跑批，或在左栏点击历史任务回看。'}</p>
        </div>
      </div>
    )
  }

  const s = job.summary
  const done = job.state === 'done' && s?.fitted_point != null
  const close = s?.index_close ?? job.index_close ?? null
  const diff = done && s?.fitted_point != null && close ? s.fitted_point / close - 1 : null
  const items: DiffItem[] = job.rows.flatMap(r => {
    const d = diffOf(r.per_share, r.close)
    return r.status === 'ok' && d != null ? [{ name: r.name, diff: d, w: r.weight ?? 0 }] : []
  })
  const up = items.filter(x => x.diff >= 0).length
  const med = medianOf(items.map(x => x.diff))
  const weights = job.weights ? `${Math.round(job.weights.dcf * 100)}/${Math.round(job.weights.comp * 100)}/${Math.round(job.weights.sent * 100)}` : `${params.dcf}/${params.comp}/${params.sent}`
  const mode = (job.sentiment_mode ?? params.sentimentMode) === 'llm' ? 'LLM 语义' : '规则打分'
  const agentMode = job.agent_mode ?? (job.shadow_mode ? 'shadow' : 'off')

  return (
    <div className={css.resultWrap}>
      <div className={css.resultBar}>
        <div className={css.resultBarL}>
          <b>逐券结果</b>
          <span className={css.mono}>{job.id}</span>
          <span>数据时点 <b>{job.components_as_of ?? '—'}</b> · 舆情 {mode} ≤ {job.sentiment_rounds ?? params.sentiment} 轮 · 加权 {weights} · 并行 {job.parallel ?? '—'} · 抽样 {job.stat_n ?? params.statN}</span>
        </div>
        <div className={css.resultBarR}>
          <span>拟合 <b className={css.mono}>{done ? fmtNum(s?.fitted_point) : '—'}</b></span>
          <span>收盘 <b className={css.mono}>{fmtNum(close)}</b></span>
          <span>偏离 <b className={`${css.mono} ${diff == null ? '' : diff >= 0 ? css.up : css.down}`}>{diff == null ? '—' : pctDiff(diff)}</b></span>
        </div>
      </div>

      {agentMode !== 'off' && <ShadowCard job={job} onAdoption={onAdoption} />}

      {!done && (
        <div className={css.card}>
          <div className={css.cardHd}>
            逐券进度 <span className={css.cardHdR}>{job.state === 'error' ? '任务异常' : `${job.done}/${job.total}`}</span>
          </div>
          <div className={css.cardBd}>
            {job.state === 'error' && <p className={css.errNote}>{job.error ?? '任务异常'}</p>}
            <div className={css.progList}>
              {job.rows.map(r => {
                const ok = r.status === 'ok'
                const d = ok ? diffOf(r.per_share, r.close) : null
                return (
                  <button type="button" key={r.idx} className={css.drow} onClick={() => setSel(r)}>
                    <span className={css.drowNm}>
                      {r.name}
                      {r.status === 'skip' && <span className={`${css.tag} ${css.tagWarn}`}>跳过</span>}
                      {(r.status === 'pending' || r.status === 'running') && <span className={css.tag}>等待中</span>}
                    </span>
                    <span className={css.drowVals}>
                      <span>价 {fmtNum(r.close)}</span>
                      <span>中枢 <b>{ok ? fmtNum(r.per_share) : '—'}</b></span>
                      <span>差异 <b className={d == null ? '' : d >= 0 ? css.up : css.down}>{d == null ? '—' : pctDiff(d)}</b></span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {done && (
        <>
          <div className={css.insightGrid}>
            <div className={css.card}>
              <div className={css.cardHd}>
                逐券差异分布 <span className={css.cardHdR}>横轴 = 中枢/股相对现价 − 1 · 柱高 = 券数</span>
              </div>
              <div className={css.cardBd}>
                <DiffHistogram items={items} />
                <DiffStrip items={items} />
              </div>
            </div>
            <div className={css.card}>
              <div className={css.cardHd}>
                估值方向占比 <span className={css.cardHdR}>共 {items.length} 只有效估值</span>
              </div>
              <div className={css.cardBd}>
                <div className={css.dirWrap}>
                  <DirectionDonut up={up} down={items.length - up} />
                  <div className={css.donutLegend}>
                    <div><i style={{ background: 'var(--up)' }} />高于现价<b>{up} 只</b></div>
                    <div><i style={{ background: 'var(--down)' }} />低于现价<b>{items.length - up} 只</b></div>
                    <div>中位差异<b>{med == null ? '—' : pctDiff(med)}</b></div>
                    <div>出估值 / 跳过<b>{s?.ok ?? 0} / {s?.skip ?? 0}</b></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className={css.card}>
            <div className={css.cardHd}>
              逐券重点结果（{job.rows.length}）<span className={css.cardHdR}>出估值 {s?.ok ?? 0} · 跳过 {s?.skip ?? 0} · 点击看明细 · 报告新窗口打开</span>
            </div>
            <div className={css.cardBd}>
              <div className={css.resGrid}>
                {job.rows.map(r => {
                  const ok = r.status === 'ok'
                  const d = ok ? diffOf(r.per_share, r.close) : null
                  return (
                    <button type="button" key={r.idx} className={`${css.resCard} ${ok ? '' : css.resCardSkip}`} onClick={() => setSel(r)}>
                      <div className={css.resTop}>
                        <span className={css.resNm}>{r.name}</span>
                        <span className={`${css.resCode} ${css.mono}`}>{r.secucode}</span>
                        {!ok && <span className={`${css.tag} ${css.tagWarn}`}>跳过</span>}
                        {ok && isExtreme(d) && (
                          <span className={`${css.tag} ${css.tagWarn}`} title="估值/价 ≥5× 或 ≤0.2×（展示层提示，不改变估值）">极端</span>
                        )}
                        {ok && r.apply?.changed && <span className={`${css.tag} ${css.tagOk}`}>已回写</span>}
                        {ok && r.warnings && r.warnings.length > 0 && <span className={`${css.tag} ${css.tagMut}`}>预警 {r.warnings.length}</span>}
                      </div>
                      {ok ? (
                        <div className={css.resMetrics}>
                          <div className={css.resM}><span>中枢/股</span><b className={css.mono}>{fmtNum(r.per_share)}</b></div>
                          <div className={css.resM}><span>现价</span><b className={css.mono}>{fmtNum(r.close)}</b></div>
                          <div className={css.resM}><span>差异</span><b className={`${css.mono} ${d == null ? '' : d >= 0 ? css.up : css.down}`}>{d == null ? '—' : pctDiff(d)}</b></div>
                        </div>
                      ) : (
                        <div className={css.resSkipTxt}>跳过：{r.error ?? '未产出结果'}</div>
                      )}
                      <div className={css.resMeta}>
                        <span>{r.industry ?? '—'}</span>
                        <span>权重 {fmtNum(r.weight)}%</span>
                        {ok && <span>置信度 {r.confidence_level ?? '—'}</span>}
                        {ok && r.interval && <span>区间 {Math.round(r.interval[0])} ~ {Math.round(r.interval[1])} 亿</span>}
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
          </div>
          <p className={css.resultNote}>
            <b>差异口径：</b>差异 = 中枢/股 ÷ 现价 − 1，只展示估值与现价的偏离，<b>不做反向校正</b>。拟合点位 = 指数收盘 × Σ(权重×中枢/股÷现价) / Σ权重（指数加权），跳过券不计入分子分母。估值中枢为引擎综合中枢（DCF / 可比 / 舆情按 {weights} 加权），逐券口径见各券报告。标注「极端」的个股满足 估值/价 ≥5× 或 ≤0.2×，仅提示偏离，不改变估值与拟合。探索性研究，不构成投资建议。
          </p>
        </>
      )}

      {sel && (
        <ReportModal
          name={sel.name}
          i={sel.idx}
          r={{ price: sel.close ?? 0, chen: sel.per_share ?? 0, shi: 0 }}
          w={sel.weight ?? 0}
          real={sel}
          jobId={job.id}
          onClose={() => setSel(null)}
        />
      )}
    </div>
  )
}
