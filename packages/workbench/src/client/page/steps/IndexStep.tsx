/** Step 2 选择指数：本期只落地上证50，上证180/科创50 后续扩展。 */

import css from '../ValuationPage.module.css'

export function IndexStep(props: { indexSel: string; onSelect: (v: string) => void }) {
  const { indexSel, onSelect } = props
  return (
    <section>
      <h2>选择指数</h2>
      <p className={css.sub}>本期仅上线上证50（50 条成分券）；上证180、科创50 随后扩展。</p>
      <div className={css.icards}>
        <div
          className={`${css.icard} ${indexSel === '上证50' ? css.icardSel : ''}`}
          onClick={() => onSelect('上证50')}
        >
          {indexSel === '上证50' && <span className={css.check}>✓</span>}
          <div className={css.iname}>上证50</div>
          <div className={css.icode}>000016.SH</div>
          <div className={css.idsc}>50 条成分券 · 本期落地</div>
          <div className={css.istate}><span className={`${css.tag} ${css.tagOk}`}>本期落地</span></div>
        </div>
        <div className={`${css.icard} ${css.icardOff}`}>
          <div className={css.iname}>上证180</div>
          <div className={css.icode}>000010.SH</div>
          <div className={css.idsc}>180 条成分券 · 跑通 50 后扩展</div>
          <div className={css.istate}><span className={`${css.tag} ${css.tagWarn}`}>后续扩展</span></div>
        </div>
        <div className={`${css.icard} ${css.icardOff}`}>
          <div className={css.iname}>科创50</div>
          <div className={css.icode}>000688.SH</div>
          <div className={css.idsc}>50 条成分券 · 跑通 50 后扩展</div>
          <div className={css.istate}><span className={`${css.tag} ${css.tagWarn}`}>后续扩展</span></div>
        </div>
      </div>
      <div className={css.note}>两套技能部署在同一环境、跑同一批样本，<b>逐券估值与最终点位才有可比性</b>。</div>
    </section>
  )
}
