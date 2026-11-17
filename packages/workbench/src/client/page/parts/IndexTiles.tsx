/** 指数瓦片：四个指数全部接通真实成分与跑批，展示各自最近一次完成结果。 */

import { INDEXES, fmtNum, pctDiff } from '../data'
import type { JobMeta } from '../api'
import css from '../ValuationPage.module.css'

export function IndexTiles(props: {
  indexSel: string
  onSelect: (id: string) => void
  hist: JobMeta[] | null
  disabled?: boolean
}) {
  const { indexSel, onSelect, hist, disabled } = props
  const latest = new Map<string, JobMeta>()
  for (const h of hist ?? []) {
    if (h.state === 'done' && h.fitted_point != null && !latest.has(h.index)) latest.set(h.index, h)
  }
  return (
    <div className={css.tiles}>
      {INDEXES.map(x => {
        const job = latest.get(x.id)
        const diff = job?.fitted_point != null && job.index_close ? job.fitted_point / job.index_close - 1 : null
        const sel = indexSel === x.id
        return (
          <button
            key={x.id}
            type="button"
            className={`${css.tile} ${sel ? css.tileSel : ''} ${disabled && !sel ? css.tileDim : ''}`}
            onClick={() => onSelect(x.id)}
            title={disabled && !sel ? '跑批进行中，完成后可切换指数' : undefined}
          >
            <span className={css.tileName}>{x.name}</span>
            <span className={`${css.tag} ${css.tagOk} ${css.tileTag}`}>真实数据</span>
            <div className={`${css.tileCode} ${css.mono}`}>{x.code} · {x.count} 条成分券</div>
            <div className={`${css.tileVal} ${css.mono}`}>{job?.fitted_point != null ? fmtNum(job.fitted_point) : '—'}</div>
            <div className={css.tileDesc}>
              {job?.fitted_point != null && diff != null ? (
                <>拟合点位 · 偏离 <span className={diff >= 0 ? css.up : css.down}>{pctDiff(diff)}</span></>
              ) : (
                <>尚无该指数完成跑批</>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
