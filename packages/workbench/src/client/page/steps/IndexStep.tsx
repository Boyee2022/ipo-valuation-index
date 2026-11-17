/** Step 2 选择指数：上证50 / 上证180 / 科创50 / 沪深300，全部接通真实成分、行情与舆情。 */

import css from '../ValuationPage.module.css'
import { INDEXES } from '../data'

export function IndexStep(props: { indexSel: string; onSelect: (v: string) => void }) {
  const { indexSel, onSelect } = props
  return (
    <section>
      <h2>选择指数</h2>
      <p className={css.sub}>四个指数全部接通真实成分券、行情与舆情流水线；切换后成分权重与跑批自动切换。</p>
      <div className={css.icards}>
        {INDEXES.map(x => (
          <div
            key={x.id}
            className={`${css.icard} ${indexSel === x.id ? css.icardSel : ''}`}
            onClick={() => onSelect(x.id)}
          >
            {indexSel === x.id && <span className={css.check}>✓</span>}
            <div className={css.iname}>{x.name}</div>
            <div className={css.icode}>{x.code}</div>
            <div className={css.idsc}>{x.count} 条成分券 · 真实数据跑批</div>
            <div className={css.istate}><span className={`${css.tag} ${css.tagOk}`}>真实数据</span></div>
          </div>
        ))}
      </div>
      <div className={css.note}>两套技能部署在同一环境、跑同一批样本，<b>逐券估值与最终点位才有可比性</b>。</div>
    </section>
  )
}
