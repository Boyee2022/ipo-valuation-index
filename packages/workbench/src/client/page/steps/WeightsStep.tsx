/** Step 3 成分券与权重：50 条成分券表 + 权重合成公式。 */

import type { Constituent } from '../data'
import css from '../ValuationPage.module.css'

export function WeightsStep(props: { list: Constituent[] }) {
  const { list } = props
  const sum = list.reduce((a, r) => a + r.w, 0)
  return (
    <section>
      <h2>成分券与权重</h2>
      <p className={css.sub}>自动列出所选日期的 50 条成分券及权重，由指数成分券表自动生成。</p>
      <div className={css.fstrip}>
        <span className={css.chunk}>权重因子（每期更新）</span><span className={css.op}>×</span>
        <span className={css.chunk}>当日市值（每日变动）</span><span className={css.arr}>→</span>
        <span className={css.chunk}>当日权重（归一化）</span>
      </div>
      <div className={css.tablewrap}>
        <table className={css.clist}>
          <thead>
            <tr><th>#</th><th>成分券（示例）</th><th>权重因子</th><th>当日市值（亿元 · 示例）</th><th>当日权重</th></tr>
          </thead>
          <tbody>
            {list.map((r, i) => (
              <tr key={r.name}>
                <td className={css.mono}>{i + 1}</td>
                <td>{r.name}</td>
                <td className={css.mono}>{r.factor.toFixed(4)}</td>
                <td className={css.mono}>{r.cap.toLocaleString('zh-CN')}</td>
                <td className={css.mono}><b>{r.w.toFixed(2)}%</b></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td colSpan={5}>共 {list.length} 条 · 当日权重合计 <b>{sum.toFixed(2)}%</b> · 由指数成分券表自动生成</td></tr>
          </tfoot>
        </table>
      </div>
      <div className={css.note}>权重因子每期更新、期间不变；当日市值每日变动。当日权重盘中才出，<b>可先用前一日因子计算</b>。</div>
    </section>
  )
}
