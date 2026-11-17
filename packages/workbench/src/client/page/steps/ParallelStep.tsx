/** Step 5 并行度：3 或 10 先试跑再定（按所选指数成分数估算耗时）。 */

import css from '../ValuationPage.module.css'

const MINS_PER_STOCK = 20

export function ParallelStep(props: {
  parallel: 3 | 10
  count: number
  onSelect: (v: 3 | 10) => void
}) {
  const { parallel, count, onSelect } = props
  const hours = (p: number) => +((count / p) * (MINS_PER_STOCK / 60)).toFixed(1)
  const batches = (p: number) => Math.ceil(count / p)
  const serial = +(count * (MINS_PER_STOCK / 60)).toFixed(1)
  return (
    <section>
      <h2>并行度</h2>
      <p className={css.sub}>原为本机串行，单股约 {MINS_PER_STOCK} 分钟（{count} 股串行约 {serial} 小时）；3 或 10 条先试跑再定。</p>
      <div className={css.pcards}>
        <div className={`${css.pcard} ${parallel === 3 ? css.pcardSel : ''}`} onClick={() => onSelect(3)}>
          <div className={css.ptitle}>每批 3 条 <span className={`${css.tag} ${css.tagOk}`}>稳妥</span></div>
          <div className={css.pdesc}>约 {batches(3)} 批跑完 · 对机器与网络更友好，先试跑验证稳定性</div>
          <div className={css.phrs}>≈ {hours(3)} <small>小时</small></div>
        </div>
        <div className={`${css.pcard} ${parallel === 10 ? css.pcardSel : ''}`} onClick={() => onSelect(10)}>
          <div className={css.ptitle}>每批 10 条 <span className={`${css.tag} ${css.tagWarn}`}>激进</span></div>
          <div className={css.pdesc}>约 {batches(10)} 批跑完 · 更快，但并发舆情搜索成本与稳定性待验证</div>
          <div className={css.phrs}>≈ {hours(10)} <small>小时</small></div>
        </div>
      </div>
      <div className={css.insightCard} style={{ marginTop: 12 }}>
        <div className={css.insightHead}>
          预计耗时对比
          <small>按单股约 {MINS_PER_STOCK} 分钟、{count} 条成分估算</small>
        </div>
        <div className={css.hbarChart}>
          {([
            ['本机串行', serial, serial],
            ['每批 3 条', hours(3), serial],
            ['每批 10 条', hours(10), serial],
          ] as [string, number, number][]).map(([label, h, max]) => {
            const on = (label === '每批 3 条' && parallel === 3) || (label === '每批 10 条' && parallel === 10)
            return (
              <div className={css.hbarRow} key={label}>
                <span className={css.hbarLab}>{label}</span>
                <div className={css.hbarTrack}>
                  <i className={on ? css.hbarFillOn : css.hbarFill} style={{ width: `${(h / max) * 100}%` }} />
                </div>
                <b>≈ {h} 小时</b>
              </div>
            )
          })}
        </div>
      </div>
      <div className={css.note}>最终目标 {count} 条并行跑完；<b>初期用 3 或 10 试跑定档，再上全量</b>。</div>
    </section>
  )
}
