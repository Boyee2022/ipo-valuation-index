/** Step 3 成分券与权重：真实成分券表（批跑服务不可达时回退示例数据）。 */

import type { RealConstituent } from '../api'
import type { Constituent } from '../data'
import css from '../ValuationPage.module.css'

function WeightBars({ items }: { items: { name: string; weight: number }[] }) {
  const top = [...items].sort((a, b) => b.weight - a.weight).slice(0, 10)
  const max = Math.max(...top.map(x => x.weight), 0.0001)
  const topSum = top.reduce((a, x) => a + x.weight, 0)
  return (
    <div className={css.insightCard}>
      <div className={css.insightHead}>前 10 大权重<small>合计 {topSum.toFixed(1)}%</small></div>
      <div className={css.wrowList}>
        {top.map(x => (
          <div className={css.wrow} key={x.name}>
            <span className={css.wrowNm}>{x.name}</span>
            <div className={css.wrowTrack}><i className={css.wrowFill} style={{ width: `${(x.weight / max) * 100}%` }} /></div>
            <span className={css.wrowVal}>{x.weight.toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function IndustryTiles({ rows }: { rows: RealConstituent[] }) {
  const map = new Map<string, number>()
  rows.forEach(r => {
    const k = r.industry ?? '未分类'
    map.set(k, (map.get(k) ?? 0) + (r.weight ?? 0))
  })
  const all = [...map.entries()].sort((a, b) => b[1] - a[1])
  const top = all.slice(0, 5)
  const rest = all.slice(5).reduce((a, [, w]) => a + w, 0)
  const max = top[0]?.[1] ?? 1
  return (
    <div className={css.insightCard}>
      <div className={css.insightHead}>行业权重分布<small>申万Ⅱ · {all.length} 个行业</small></div>
      <div className={css.secTiles}>
        {top.map(([name, w]) => (
          <div
            key={name}
            className={css.secTile}
            style={{ background: `color-mix(in srgb, var(--accent) ${Math.round(5 + (w / max) * 18)}%, var(--card))` }}
          >
            <span className={css.secTileNm}>{name}</span>
            <b className={css.secTileVal}>{w.toFixed(1)}%</b>
          </div>
        ))}
        {rest > 0 && (
          <div className={css.secTile}>
            <span className={css.secTileNm}>其他 {all.length - top.length} 个行业</span>
            <b className={`${css.secTileVal} ${css.secTileMore}`}>{rest.toFixed(1)}%</b>
          </div>
        )}
      </div>
    </div>
  )
}

export function WeightsStep(props: {
  list: Constituent[]
  real: RealConstituent[] | null
  asOf: string
  error: string | null
  indexName: string
  weightComputed: boolean
}) {
  const { list, real, asOf, error, indexName, weightComputed } = props

  if (real && real.length > 0) {
    const sum = real.reduce((a, r) => a + (r.weight ?? 0), 0)
    return (
      <section>
        <h2>成分券与权重</h2>
        <p className={css.sub}>{indexName} 真实成分券与收盘权重（东财指数成分表 · 数据时点 {asOf}）。</p>
        <div className={css.pipe}>
          <b>权重因子</b><span className={css.arr}>×</span><b>当日市值</b><span className={css.arr}>→</span><b>当日权重</b><span style={{ marginLeft: 8 }}>（归一化）</span>
        </div>
        <div className={css.chartDuo}>
          <WeightBars items={real.map(r => ({ name: r.name, weight: r.weight ?? 0 }))} />
          <IndustryTiles rows={real} />
        </div>
        <div className={`${css.tblWrap} ${css.tblTall}`}>
          <table className={css.clist}>
            <thead>
              <tr><th>#</th><th>代码</th><th>名称</th><th>行业</th><th className={css.numTd}>收盘价</th><th className={css.numTd}>当日权重</th></tr>
            </thead>
            <tbody>
              {real.map((r, i) => (
                <tr key={r.secucode}>
                  <td className={css.mono}>{i + 1}</td>
                  <td className={css.mono}>{r.secucode}</td>
                  <td>{r.name}</td>
                  <td>{r.industry ?? '—'}</td>
                  <td className={`${css.mono} ${css.numTd}`}>{r.close?.toFixed(2) ?? '—'}</td>
                  <td className={`${css.mono} ${css.numTd}`}><b>{r.weight?.toFixed(2)}%</b></td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr><td colSpan={6}>共 {real.length} 条 · 权重合计 <b>{sum.toFixed(2)}%</b> · 数据时点 {asOf}（前一日收盘权重口径）</td></tr>
            </tfoot>
          </table>
        </div>
        <div className={css.tblFoot}>
          <span>共 {real.length} 条 · 权重合计 <b>{sum.toFixed(2)}%</b> · 数据时点 {asOf}（前一日收盘权重口径）</span>
        </div>
        <div className={css.note}>
          {weightComputed ? (
            <><b>{indexName} 东财不直接披露成分权重，此处由自由流通市值归一化计算</b>（口径近似，正式合成前建议对照指数公司披露复核）。权重因子每期更新、期间不变；当日市值每日变动，<b>用前一日收盘权重计算（与指数口径一致）</b>。</>
          ) : (
            <>权重因子每期更新、期间不变；当日市值每日变动。当日权重盘中才出，<b>用前一日收盘权重计算（与指数口径一致）</b>。</>
          )}
        </div>
      </section>
    )
  }

  const sum = list.reduce((a, r) => a + r.w, 0)
  return (
    <section>
      <h2>成分券与权重</h2>
      <p className={css.sub}>{indexName} · 自动列出所选日期的 {list.length} 条成分券及权重，由指数成分券表自动生成。</p>
      <div className={css.pipe}>
        <b>权重因子</b><span className={css.arr}>×</span><b>当日市值</b><span className={css.arr}>→</span><b>当日权重</b><span style={{ marginLeft: 8 }}>（归一化）</span>
      </div>
      <div className={`${css.chartDuo} ${css.chartSolo}`}>
        <WeightBars items={list.map(r => ({ name: r.name, weight: r.w }))} />
      </div>
      <div className={`${css.tblWrap} ${css.tblTall}`}>
        <table className={css.clist}>
          <thead>
            <tr><th>#</th><th>成分券（示例）</th><th>权重因子</th><th>当日市值（亿元 · 示例）</th><th className={css.numTd}>当日权重</th></tr>
          </thead>
          <tbody>
            {list.map((r, i) => (
              <tr key={r.name}>
                <td className={css.mono}>{i + 1}</td>
                <td>{r.name}</td>
                <td className={`${css.mono} ${css.numTd}`}>{r.factor.toFixed(4)}</td>
                <td className={`${css.mono} ${css.numTd}`}>{r.cap.toLocaleString('zh-CN')}</td>
                <td className={`${css.mono} ${css.numTd}`}><b>{r.w.toFixed(2)}%</b></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td colSpan={5}>共 {list.length} 条 · 当日权重合计 <b>{sum.toFixed(2)}%</b> · 由指数成分券表自动生成</td></tr>
          </tfoot>
        </table>
      </div>
      <div className={css.tblFoot}>
        <span>共 {list.length} 条 · 当日权重合计 <b>{sum.toFixed(2)}%</b> · 由指数成分券表自动生成</span>
      </div>
      <div className={css.note}>
        权重因子每期更新、期间不变；当日市值每日变动。当日权重盘中才出，<b>可先用前一日因子计算</b>。
        {error && <span style={{ color: 'var(--gold)' }}>（批跑服务未连接：{error}，当前为示例数据）</span>}
      </div>
    </section>
  )
}
