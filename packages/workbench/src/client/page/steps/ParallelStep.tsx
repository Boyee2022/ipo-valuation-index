/** Step 5 并行度：3 或 10 先试跑再定。 */

import css from '../ValuationPage.module.css'

export function ParallelStep(props: { parallel: 3 | 10; onSelect: (v: 3 | 10) => void }) {
  const { parallel, onSelect } = props
  return (
    <section>
      <h2>并行度</h2>
      <p className={css.sub}>原为本机串行，单股约 20 分钟（50 股串行约 16.7 小时）；3 或 10 条先试跑再定。</p>
      <div className={css.pcards}>
        <div className={`${css.pcard} ${parallel === 3 ? css.pcardSel : ''}`} onClick={() => onSelect(3)}>
          <div className={css.ptitle}>每批 3 条 <span className={`${css.tag} ${css.tagOk}`}>稳妥</span></div>
          <div className={css.pdesc}>约 17 批跑完 · 对机器与网络更友好，先试跑验证稳定性</div>
          <div className={css.phrs}>≈ 5.6 <small>小时</small></div>
        </div>
        <div className={`${css.pcard} ${parallel === 10 ? css.pcardSel : ''}`} onClick={() => onSelect(10)}>
          <div className={css.ptitle}>每批 10 条 <span className={`${css.tag} ${css.tagWarn}`}>激进</span></div>
          <div className={css.pdesc}>约 5 批跑完 · 更快，但并发舆情搜索成本与稳定性待验证</div>
          <div className={css.phrs}>≈ 1.7 <small>小时</small></div>
        </div>
      </div>
      <div className={css.note}>最终目标 50 条并行跑完；<b>初期用 3 或 10 试跑定档，再上全量</b>。</div>
    </section>
  )
}
