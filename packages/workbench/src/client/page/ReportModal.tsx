/** Per-stock report modal (demo data or real batch result). */

import { pctDiff, type ValuationResult } from './data'
import { reportUrl, type JobRow } from './api'
import css from './ValuationPage.module.css'

export function ReportModal(props: {
  name: string
  i: number
  r: ValuationResult
  w: number
  onClose: () => void
  real?: JobRow | null
  jobId?: string
  skip?: boolean
}) {
  const { name, i, r, w, onClose, real, jobId, skip } = props
  const skipped = !!skip
  let rows: [string, string][] = []
  if (real) {
    const ok = real.status === 'ok'
    const diff = ok && real.per_share != null && real.close ? real.per_share / real.close - 1 : null
    rows = [
      ['证券代码', real.secucode],
      ['行业', real.industry ?? '—'],
      ['收盘价', real.close != null ? real.close.toFixed(2) : '—'],
      ['当日权重', real.weight != null ? `${real.weight.toFixed(2)}%` : '—'],
      ['估值中枢/股', ok ? real.per_share != null ? real.per_share.toFixed(2) : '—' : `跳过：${real.error ?? '未产出结果'}`],
      ['差异（中枢/现价−1）', diff != null ? pctDiff(diff) : '—'],
      ['估值中枢（亿元）', ok && real.weighted_mid != null ? real.weighted_mid.toFixed(2) : '—'],
      ['情景区间', ok && real.interval ? `${real.interval[0]?.toFixed(0)} ~ ${real.interval[1]?.toFixed(0)}` : '—'],
      ['置信度', real.confidence_level ?? '—'],
      ['生命周期', real.stage_label ?? '—'],
      ['净利口径', real.basis ?? '—'],
      ['八项机检', ok ? (real.check_ok ? '通过' : '未通过') : '—'],
      ['计入合成', ok ? '是' : '否（跳过券不计入分子分母）'],
    ]
  } else {
    rows = [
      ['收盘价（示例）', r.price.toFixed(2)],
      ['陈老师中枢', skipped ? '跳过（β 无法计算）' : r.chen.toFixed(2)],
      ['石总中枢', skipped ? '—' : r.shi.toFixed(2)],
      ['当日权重', `${w.toFixed(2)}%`],
      ['陈差异（中枢/价−1）', skipped ? '—' : pctDiff(r.chen / r.price - 1)],
      ['石差异（中枢/价−1）', skipped ? '—' : pctDiff(r.shi / r.price - 1)],
      ['计入合成', skipped ? '否（跳过券不计入分子分母）' : '是'],
    ]
  }
  return (
    <div className={css.mask} onClick={onClose}>
      <div className={css.modal} onClick={e => e.stopPropagation()}>
        <button className={css.close} aria-label="关闭" onClick={onClose}>×</button>
        <h3>{name}</h3>
        <p className={css.msub}>
          {real
            ? `真实跑批结果 · 第 ${real.idx + 1} 号成分券 · 估值引擎 + 统计校验 + 八项机检`
            : `示例数据 · 第 ${i + 1} 号成分券 · 演示用，不请求真实估值服务`}
        </p>
        <table>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}><th>{k}</th><td>{v}</td></tr>
            ))}
          </tbody>
        </table>
        <p className={css.modalNote}>差异只反映估值与现价的偏离，<b>不做反向校正</b>：不把估值改写成现价，也不把现价改写成估值。</p>
        {real && real.status === 'ok' && real.report && jobId && (
          <p style={{ marginTop: 14 }}>
            <a className={css.linkBtn} href={reportUrl(jobId, real.report)} target="_blank" rel="noreferrer">打开完整估值报告 ↗</a>
          </p>
        )}
      </div>
    </div>
  )
}
