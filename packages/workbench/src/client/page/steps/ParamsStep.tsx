/** Step 1 参数确认：舆情轮数上限 + 方法加权比例 + 内置参数清单。 */

import type { BatchParams } from '../data'
import css from '../ValuationPage.module.css'

const PARAM_ROWS: { p: string; chen: string; shi: string; status: 'ok' | 'warn' | 'mut'; statusText: string }[] = [
  { p: '方法组合', chen: 'DCF＋可比公司＋市场舆情（三步）', shi: 'DCF＋可比公司（两步）', status: 'ok', statusText: '沿用内置' },
  { p: '指标口径', chen: 'DCF、PS、PE、PB 全算完再加权合成', shi: '选一个主指标作为估值', status: 'ok', statusText: '沿用内置' },
  { p: '舆情调整', chen: '舆情 → 公司质量得分 → 调整估值倍数', shi: '无', status: 'ok', statusText: '沿用内置' },
  { p: '舆情搜索轮数', chen: '每轮 ≤ 10 轮', shi: '—', status: 'ok', statusText: '已定上限' },
  { p: '增速假设 / 永续增长率', chen: '技能内置，两套各一套', shi: '模型内置', status: 'warn', statusText: '待研究定标' },
  { p: '贴现率（WACC）口径', chen: '如 5.61% 一类口径', shi: '口径待确认', status: 'warn', statusText: '待研究定标' },
  { p: 'β', chen: '有的企业算得出、有的算不出', shi: '同左', status: 'mut', statusText: '边界搁置' },
  { p: '单券估不出', chen: '自动跳过', shi: '未逐家遍历，行为待验证', status: 'mut', statusText: '先跑通主流程' },
]

const TAG_CLS = { ok: css.tagOk, warn: css.tagWarn, mut: css.tagMut }

export function ParamsStep(props: { params: BatchParams; onChange: (p: BatchParams) => void }) {
  const { params, onChange } = props
  const sum = params.dcf + params.comp + params.sent
  const setNum = (key: 'sentiment' | 'dcf' | 'comp' | 'sent', value: string) => {
    const n = Number.parseInt(value, 10)
    onChange({ ...params, [key]: Number.isFinite(n) ? n : 0 })
  }
  return (
    <section>
      <h2>参数确认</h2>
      <p className={css.sub}>把技能里写死的参数拉成表单，跑前确认；舆情搜索按次扣费，是跑批的主要变动成本。</p>
      <div className={css.fgrid}>
        <div className={css.fitem}>
          <label>舆情搜索轮数（每轮运行上限）</label>
          <input
            className={css.numInput}
            type="number"
            min={1}
            max={10}
            value={params.sentiment}
            onChange={e => setNum('sentiment', e.target.value)}
          />
          <p className={css.hint}>成本约束：上限拟定为每轮最多搜 10 轮，作为固定参数进表单，跑前可调。</p>
        </div>
        <div className={css.fitem}>
          <label>方法加权比例（合计 100%）</label>
          <div className={css.fgrid} style={{ gap: 10 }}>
            <div>
              <input className={css.numInput} type="number" min={0} max={100} value={params.dcf} onChange={e => setNum('dcf', e.target.value)} />
              <p className={css.hint}>DCF</p>
            </div>
            <div>
              <input className={css.numInput} type="number" min={0} max={100} value={params.comp} onChange={e => setNum('comp', e.target.value)} />
              <p className={css.hint}>可比公司</p>
            </div>
            <div>
              <input className={css.numInput} type="number" min={0} max={100} value={params.sent} onChange={e => setNum('sent', e.target.value)} />
              <p className={css.hint}>市场舆情</p>
            </div>
          </div>
          <div className={css.wbars}>
            <i className={css.wb1} style={{ flex: params.dcf }} />
            <i className={css.wb2} style={{ flex: params.comp }} />
            <i className={css.wb3} style={{ flex: params.sent }} />
          </div>
          <div className={css.wsum}>
            <span>默认比例沿用技能内置，跑前可调</span>
            <b className={sum === 100 ? css.wsumOk : css.wsumBad}>
              {sum === 100 ? '合计 100%' : `合计 ${sum}%（需等于 100%）`}
            </b>
          </div>
        </div>
      </div>
      <div className={css.note} style={{ marginTop: 20 }}>
        <b>内置参数清单：</b>增速假设、永续增长率、贴现率（如 WACC 5.61% 口径）、β 等硬编码参数后续全部列入清单做成可视化配置；个别券 β 算不出属边界情况，先搁置、主流程跑通优先。
      </div>
      <table className={css.pt} style={{ marginTop: 16 }}>
        <thead>
          <tr><th>参数</th><th>陈老师技能（默认）</th><th>石总模型（默认）</th><th style={{ width: 110 }}>状态</th></tr>
        </thead>
        <tbody>
          {PARAM_ROWS.map(r => (
            <tr key={r.p}>
              <td>{r.p}</td>
              <td className={css.mono}>{r.chen}</td>
              <td className={css.mono}>{r.shi}</td>
              <td><span className={`${css.tag} ${TAG_CLS[r.status]}`}>{r.statusText}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
