/** HERO：拟合点位大数字 + 情景区间带 + 近次跑批 sparkline。 */

import { fmtNum, pctDiff, signedPoints, type IndexMeta } from '../data'
import type { JobStatus } from '../api'
import css from '../ValuationPage.module.css'

export interface SparkPoint {
  fit: number
  close: number
}

export interface Scenario {
  low: number
  base: number
  high: number
}

/** 逐券情景区间（亿元）÷ 总股本 → 每股区间，再按当日权重合成指数点位。 */
export function scenarioOf(job: JobStatus | null): Scenario | null {
  const s = job?.summary
  if (!job || !s || s.fitted_point == null || !s.index_close) return null
  let lo = 0
  let hi = 0
  let wp = 0
  for (const r of job.rows) {
    if (r.status !== 'ok' || !r.interval || !r.total_shares || !r.close || !r.weight) continue
    lo += r.weight * (r.interval[0] / r.total_shares)
    hi += r.weight * (r.interval[1] / r.total_shares)
    wp += r.weight * r.close
  }
  if (!(wp > 0)) return null
  const close = s.index_close
  return {
    low: Math.min((close * lo) / wp, s.fitted_point),
    base: s.fitted_point,
    high: Math.max((close * hi) / wp, s.fitted_point),
  }
}

function Sparkline({ pts }: { pts: SparkPoint[] }) {
  if (pts.length < 2) return <p className={css.sparkEmpty}>暂无足够跑批记录（同指数至少 2 次完成）</p>
  const W = 700
  const H = 90
  const PAD = 8
  const vals = pts.flatMap(p => [p.fit, p.close])
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const X = (i: number) => PAD + (i * (W - PAD * 2)) / (pts.length - 1)
  const Y = (v: number) => H - PAD - ((v - min) / span) * (H - PAD * 2)
  const path = (key: 'fit' | 'close') =>
    pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(i).toFixed(1)} ${Y(p[key]).toFixed(1)}`).join(' ')
  const last = pts[pts.length - 1]
  return (
    <svg className={css.sparkSvg} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-label="近次跑批走势">
      <path className={css.sparkIdx} d={path('close')} fill="none" strokeWidth="1.2" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
      <path className={css.sparkFit} d={path('fit')} fill="none" strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
      <circle className={css.sparkDot} cx={X(pts.length - 1)} cy={Y(last.fit)} r="3" />
    </svg>
  )
}

export function Hero(props: { meta: IndexMeta; job: JobStatus | null; spark: SparkPoint[]; loading: boolean }) {
  const { meta, job, spark, loading } = props
  const s = job?.summary
  const fit = s?.fitted_point ?? null
  const close = s?.index_close ?? null
  const diff = fit != null && close ? fit / close - 1 : null
  const diffPts = fit != null && close ? fit - close : null
  const sc = scenarioOf(job)
  const markPct = sc && sc.high > sc.low ? Math.min(96, Math.max(4, ((sc.base - sc.low) / (sc.high - sc.low)) * 100)) : 50
  return (
    <div className={css.hero}>
      <div className={css.hmain}>
        <div className={css.hKicker}>
          {meta.name} · 拟合点位 <span>FITTED INDEX LEVEL</span>
        </div>
        <div className={css.hBig}>
          {fit != null ? fmtNum(fit) : loading ? '…' : '—'}<small>点</small>
        </div>
        {job && s ? (
          <>
            <div className={css.hSub}>
              数据时点 <b>{job.components_as_of ?? '—'}</b> · 覆盖 <b>{s.ok}/{s.total}</b> 只成分券 · 任务{' '}
              <b className={css.mono}>{job.id}</b> · 跑批 <b>{job.created}</b>
            </div>
            <div className={`${css.hDelta} ${diff != null && diff >= 0 ? css.up : css.down}`}>
              {diff == null ? '—' : pctDiff(diff)}
              <span>vs 指数收盘 {fmtNum(close)}（{diffPts == null ? '—' : `${signedPoints(diffPts)} 点`}）</span>
            </div>
          </>
        ) : (
          <div className={css.hSub}>
            {loading ? '正在读取该指数最近一次跑批…' : '尚无该指数的真实跑批 · 在参数卡确认后开始跑批'}
          </div>
        )}
      </div>
      <div className={css.hside}>
        <div className={css.hbox}>
          <div className={css.hboxK}>
            情景区间 <span>SCENARIO RANGE</span>
            <small>逐券区间按权重合成</small>
          </div>
          {sc ? (
            <>
              <div className={css.band}>
                <div className={css.bandBg} />
                <div className={css.bandMk} style={{ left: `${markPct}%` }} />
              </div>
              <div className={css.bandLabs}>
                <span>悲观 <b>{fmtNum(sc.low)}</b></span>
                <span className={css.bandMid}>基准 <b>{fmtNum(sc.base)}</b></span>
                <span>乐观 <b>{fmtNum(sc.high)}</b></span>
              </div>
            </>
          ) : (
            <p className={css.sparkEmpty}>区间数据不足（需要逐券估值区间与总股本）</p>
          )}
        </div>
        <div className={css.hbox}>
          <div className={css.hboxK}>
            近 {spark.length} 次跑批 <span>SPARKLINE</span>
            <small className={css.sparkLegend}><i className={css.lgFit} />拟合点位<i className={css.lgIdx} />指数收盘</small>
          </div>
          <Sparkline pts={spark} />
        </div>
      </div>
    </div>
  )
}
