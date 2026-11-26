/** 成分券与权重（真实东财成分表，前一日收盘权重口径）。 */

import { API_BASE, type RealConstituent } from '../api'
import css from '../ValuationPage.module.css'

export function ConsTable(props: {
  rows: RealConstituent[] | null
  loading: boolean
  error: string | null
  indexName: string
  asOf: string
  weightComputed: boolean
}) {
  const { rows, loading, error, indexName, asOf, weightComputed } = props
  const list = rows ?? []
  const sum = list.reduce((a, r) => a + (r.weight ?? 0), 0)

  const ind = new Map<string, number>()
  list.forEach(r => {
    const k = r.industry ?? '未分类'
    ind.set(k, (ind.get(k) ?? 0) + (r.weight ?? 0))
  })
  const indTop = [...ind.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)

  return (
    <div className={css.card}>
      <div className={css.cardHd}>
        成分券与权重（{loading ? '…' : list.length}） <span className={css.cardHdR}>{indexName} · 权重合计 {list.length > 0 ? `${sum.toFixed(2)}%` : '—'} · 前一日收盘口径</span>
      </div>
      <div className={css.cardBd}>
        {loading && <p className={css.empty}>正在从批跑服务读取成分券与权重…</p>}
        {!loading && error && (
          <div className={css.offlineBox}>
            <b>批跑服务未连接</b>
            <span>{error}</span>
            <span className={css.mono}>{API_BASE}</span>
          </div>
        )}
        {!loading && !error && list.length === 0 && <p className={css.empty}>未返回成分券数据。</p>}
        {list.length > 0 && (
          <>
            <div className={css.tabwrap}>
              <table className={css.dense}>
                <thead>
                  <tr>
                    <th>#</th><th>代码</th><th>名称</th><th>行业</th>
                    <th className={css.numTd}>收盘价</th><th className={css.numTd}>当日权重</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((r, i) => (
                    <tr key={r.secucode}>
                      <td className={css.mono}>{i + 1}</td>
                      <td className={`${css.mono} ${css.nm}`}>{r.secucode}</td>
                      <td>{r.name}</td>
                      <td className={css.dimCell}>{r.industry ?? '—'}</td>
                      <td className={`${css.mono} ${css.numTd}`}>{r.close != null ? r.close.toFixed(2) : '—'}</td>
                      <td className={`${css.mono} ${css.numTd} ${css.am}`}><b>{r.weight != null ? r.weight.toFixed(2) : '—'}%</b></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={css.consMeta}>
              <span>东财指数成分表（{asOf || '—'}）· 权重因子每期更新 × 当日市值 → 当日权重</span>
              <span className={css.mono}>{list.length} 条 · {sum.toFixed(2)}%</span>
            </div>
            <div className={css.indRow}>
              <span className={css.indLab}>行业 TOP5</span>
              {indTop.map(([name, w]) => (
                <span className={css.indChip} key={name}>{name}<b>{w.toFixed(1)}%</b></span>
              ))}
            </div>
            {weightComputed && (
              <p className={css.tinyNote}>
                {indexName} 的东财成分表不直接披露权重，此处由自由流通市值归一化计算（weight_computed）；正式合成前建议对照指数公司披露复核。
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
