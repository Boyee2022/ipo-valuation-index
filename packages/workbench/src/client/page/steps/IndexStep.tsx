/** Step 2 选择指数：本期只落地上证50，上证180/科创50 后续扩展。 */

import css from '../ValuationPage.module.css'

export function IndexStep(props: { indexSel: string; onSelect: (v: string) => void }) {
  const { indexSel, onSelect } = props
  return (
    <section>
      <h2>选择指数</h2>
      <p className={css.sub}>本期仅上线上证50（50 条成分券）；上证180、科创50 随后扩展。</p>
      <div className={css.cards}>
        <div
          className={`${css.card} ${indexSel === '上证50' ? css.cardSel : ''}`}
          onClick={() => onSelect('上证50')}
        >
          {indexSel === '上证50' && <span className={css.selmark}>✓</span>}
          <h3>上证50</h3>
          <p className={css.cardMeta}>50 条成分券 · 本期落地</p>
          <span className={`${css.tag} ${css.tagOk}`}>本期落地</span>
        </div>
        <div className={`${css.card} ${css.cardDis}`}>
          <span className={css.cardSt}><span className={`${css.tag} ${css.tagMut}`}>后续扩展</span></span>
          <h3>上证180</h3>
          <p className={css.cardMeta}>180 条成分券 · 跑通 50 后扩展</p>
        </div>
        <div className={`${css.card} ${css.cardDis}`}>
          <span className={css.cardSt}><span className={`${css.tag} ${css.tagMut}`}>后续扩展</span></span>
          <h3>科创50</h3>
          <p className={css.cardMeta}>50 条成分券 · 跑通 50 后扩展</p>
        </div>
      </div>
      <div className={css.note}>两套技能部署在同一环境、跑同一批样本，逐券估值与最终点位才有可比性。</div>
    </section>
  )
}
