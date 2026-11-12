/** Per-stock report modal (demo data). */

import { SKIP_INDEXES, type ValuationResult } from './data'
import css from './ValuationPage.module.css'

export function ReportModal(props: {
  name: string
  i: number
  r: ValuationResult
  w: number
  onClose: () => void
}) {
  const { name, i, r, w, onClose } = props
  const skipped = SKIP_INDEXES.has(i)
  const rows: [string, string][] = [
    ['收盘价（示例）', r.price.toFixed(2)],
    ['陈老师估值', skipped ? '跳过（β 无法计算）' : r.chen.toFixed(2)],
    ['石总估值', skipped ? '—' : r.shi.toFixed(2)],
    ['当日权重', `${w.toFixed(2)}%`],
    ['陈 / 价', skipped ? '—' : (r.chen / r.price).toFixed(2)],
    ['石 / 价', skipped ? '—' : (r.shi / r.price).toFixed(2)],
    ['计入合成', skipped ? '否（跳过券不计入分子分母）' : '是'],
  ]
  return (
    <div className={css.mask} onClick={onClose}>
      <div className={css.modal} onClick={e => e.stopPropagation()}>
        <button className={css.close} aria-label="关闭" onClick={onClose}>×</button>
        <h3>{name}</h3>
        <p className={css.msub}>示例数据 · 第 {i + 1} 号成分券 · 演示用，不请求真实估值服务</p>
        <table>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}><th>{k}</th><td>{v}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
