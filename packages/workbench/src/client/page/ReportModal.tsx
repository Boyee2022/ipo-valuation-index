/** 逐券明细弹窗（真实批跑结果 / 历史任务回看）。 */

import { fmtNum, pctDiff, type ValuationResult } from './data'
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
      ['收盘价', fmtNum(real.close)],
      ['当日权重', `${fmtNum(real.weight)}%`],
      ['估值中枢/股', ok ? fmtNum(real.per_share) : `跳过：${real.error ?? '未产出结果'}`],
      ['差异（中枢/现价−1）', diff != null ? pctDiff(diff) : '—'],
      ['估值中枢（亿元）', ok ? fmtNum(real.weighted_mid) : '—'],
      ['情景区间（亿元）', ok && real.interval ? `${Math.round(real.interval[0])} ~ ${Math.round(real.interval[1])}` : '—'],
      ['置信度', real.confidence_level ?? '—'],
      ['生命周期', real.stage_label ?? '—'],
      ['净利口径', real.basis ?? '—'],
      ['八项机检', ok ? (real.check_ok ? '通过' : '未通过') : '—'],
      ['计入合成', ok ? '是' : '否（跳过券不计入分子分母）'],
    ]
  } else {
    rows = [
      ['收盘价', fmtNum(r.price)],
      ['估值中枢', skipped ? '跳过（β 无法计算）' : fmtNum(r.chen)],
      ['当日权重', `${fmtNum(w)}%`],
      ['差异（中枢/价−1）', skipped ? '—' : pctDiff(r.chen / r.price - 1)],
      ['计入合成', skipped ? '否（跳过券不计入分子分母）' : '是'],
    ]
  }
  return (
    <div className={css.mask} onClick={onClose}>
      <div className={css.modal} onClick={e => e.stopPropagation()}>
        <div className={css.modalHd}>
          <span className={css.modalKicker}>SECURITY DETAIL</span>
          <button className={css.close} aria-label="关闭" onClick={onClose}>×</button>
        </div>
        <h3>{name}</h3>
        <p className={css.msub}>
          {real
            ? `真实跑批结果 · 第 ${real.idx + 1} 号成分券 · 估值引擎 + 统计校验 + 八项机检`
            : `示例口径 · 第 ${i + 1} 号成分券`}
        </p>
        <table>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}><th>{k}</th><td className={css.mono}>{v}</td></tr>
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
