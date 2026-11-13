/** Step 1 参数确认：舆情轮数上限 + 方法加权比例 + 内置参数清单 + 两套技能参数对照。 */

import type { BatchParams } from '../data'
import css from '../ValuationPage.module.css'

const BUILTIN_PARAMS: [string, string, string?][] = [
  ['增速假设（2026 / 2027 / 2028）', '4% / 5% / 5%'],
  ['永续增长率', '3.0%'],
  ['贴现率（WACC）口径', '5.61%', 'rf 1.7% + β 0.65 × ERP 6%'],
  ['β 处理', '0.65', '个别券算不出 → 边界搁置'],
  ['蒙特卡洛模拟', '3000 次'],
  ['剔除离群可比公司', '开'],
  ['情景权重', '悲观 25% / 基准 50% / 乐观 25%'],
  ['单券估不出', '自动跳过，主流程跑通优先'],
]

const PARAM_ROWS: { p: string; chen: string; shi: string; status: 'ok' | 'warn' | 'mut'; statusText: string }[] = [
  { p: '方法组合', chen: 'DCF＋可比公司＋市场舆情（三步）', shi: 'DCF＋可比公司（两步）', status: 'mut', statusText: '沿用内置' },
  { p: '指标口径', chen: 'DCF、PS、PE、PB 全算完再加权合成', shi: '选一个主指标作为估值', status: 'mut', statusText: '沿用内置' },
  { p: '舆情调整', chen: '舆情 → 公司质量得分 → 调整估值倍数', shi: '无', status: 'mut', statusText: '沿用内置' },
  { p: '舆情搜索轮数', chen: '每轮 ≤ 10 轮', shi: '—', status: 'ok', statusText: '已定上限' },
  { p: '增速假设 / 永续增长率', chen: '技能内置，两套各一套', shi: '模型内置', status: 'warn', statusText: '待研究定标' },
  { p: '贴现率（WACC）口径', chen: '如 5.61% 一类口径', shi: '口径待确认', status: 'warn', statusText: '待研究定标' },
  { p: 'β', chen: '有的企业算得出、有的算不出', shi: '同左', status: 'warn', statusText: '边界搁置' },
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
  const pct = (v: number) => `${sum === 0 ? 0 : (v / sum) * 100}%`
  return (
    <section>
      <h2>参数确认</h2>
      <p className={css.sub}>把技能里写死的参数拉成表单，跑前确认；舆情搜索按次扣费，是跑批的主要变动成本。</p>

      <h3>舆情搜索轮数（每轮运行上限）</h3>
      <div className={css.frow}>
        <div className={css.lab}>舆情搜索上限<small>成本约束 · 跑前可调</small></div>
        <input
          className={css.numInput}
          type="number"
          min={1}
          max={10}
          value={params.sentiment}
          onChange={e => setNum('sentiment', e.target.value)}
        />
        <span className={css.suffix}>轮（成本约束：上限拟定为每轮最多搜 10 轮，作为固定参数进表单，跑前可调）</span>
      </div>

      <h3>方法加权比例（合计 100%）</h3>
      <p className={css.hint}>默认比例沿用技能内置，跑前可调。</p>
      <div className={css.wbar}>
        <i className={css.wb1} style={{ width: pct(params.dcf) }} />
        <i className={css.wb2} style={{ width: pct(params.comp) }} />
        <i className={css.wb3} style={{ width: pct(params.sent) }} />
      </div>
      <div className={css.wlegend}>
        <span className={css.wGroup}>
          <i className={css.wb1} />DCF（%）：
          <input className={css.numInput} type="number" min={0} max={100} value={params.dcf} onChange={e => setNum('dcf', e.target.value)} />
        </span>
        <span className={css.wGroup}>
          <i className={css.wb2} />可比公司（%）：
          <input className={css.numInput} type="number" min={0} max={100} value={params.comp} onChange={e => setNum('comp', e.target.value)} />
        </span>
        <span className={css.wGroup}>
          <i className={css.wb3} />市场舆情（%）：
          <input className={css.numInput} type="number" min={0} max={100} value={params.sent} onChange={e => setNum('sent', e.target.value)} />
        </span>
      </div>
      <div className={`${css.wsum} ${sum === 100 ? '' : css.wsumBad}`}>
        {sum === 100 ? '合计 100%' : `合计 ${sum}%（需等于 100%）`}
      </div>

      <h3>内置参数清单</h3>
      <p className={css.hint}>
        增速假设、永续增长率、贴现率（如 WACC 5.61% 口径）、β 等硬编码参数后续全部列入清单做成可视化配置；个别券 β 算不出属边界情况，先搁置、主流程跑通优先。
      </p>
      <div className={css.pgrid}>
        {BUILTIN_PARAMS.map(([k, v, small]) => (
          <div className={css.pitem} key={k}>
            <div className={css.pk}>{k}</div>
            <div className={css.pv}>{v}{small && <small> {small}</small>}</div>
          </div>
        ))}
      </div>

      <h3>两套技能参数对照（跑同一批样本，结果才可比）</h3>
      <div className={css.tblWrap}>
        <table className={css.pt}>
          <thead>
            <tr><th style={{ width: 150 }}>参数</th><th>陈老师技能（默认）</th><th>石总模型（默认）</th><th style={{ width: 110 }}>状态</th></tr>
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
      </div>
    </section>
  )
}
