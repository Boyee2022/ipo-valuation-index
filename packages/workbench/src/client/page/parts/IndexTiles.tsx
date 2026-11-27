/** 指数瓦片：五个指数全部接通真实成分与跑批，按情景选择展示各自最近一次完成的点位。 */

import { useState } from 'react'
import { INDEXES, fmtNum, pctDiff } from '../data'
import type { JobMeta } from '../api'
import css from '../ValuationPage.module.css'

type Scenario = 'low' | 'base' | 'high'

const SCENARIOS: { id: Scenario; name: string }[] = [
  { id: 'low', name: '悲观' },
  { id: 'base', name: '基准' },
  { id: 'high', name: '乐观' },
]

const SCEN_CN: Record<Scenario, string> = { low: '悲观', base: '基准', high: '乐观' }

function scenarioPoint(job: JobMeta | undefined, s: Scenario): number | null {
  if (!job) return null
  if (s === 'low') return job.scenario_low ?? null
  if (s === 'high') return job.scenario_high ?? null
  return job.scenario_base ?? job.fitted_point ?? null
}

export function IndexTiles(props: {
  indexSel: string
  onSelect: (id: string) => void
  hist: JobMeta[] | null
  disabled?: boolean
}) {
  const { indexSel, onSelect, hist, disabled } = props
  const [scen, setScen] = useState<Scenario>('base')
  const latest = new Map<string, JobMeta>()
  for (const h of hist ?? []) {
    if (h.state === 'done' && h.fitted_point != null && !latest.has(h.index)) latest.set(h.index, h)
  }
  return (
    <div className={css.tilesWrap}>
      <div className={css.tilesBar}>
        <span className={css.tilesLbl}>情景点位</span>
        <div className={`${css.seg} ${css.scenSeg}`} role="group" aria-label="情景点位选择">
          {SCENARIOS.map(s => (
            <button
              key={s.id}
              type="button"
              className={scen === s.id ? css.segSel : undefined}
              aria-pressed={scen === s.id}
              onClick={() => setScen(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>
      </div>
      <div className={css.tiles}>
        {INDEXES.map(x => {
          const job = latest.get(x.id)
          const val = scenarioPoint(job, scen)
          const close = job?.index_close ?? null
          const diff = val != null && close ? val / close - 1 : null
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
              <div className={`${css.tileCode} ${css.mono}`}>
                {x.code} · {x.allMarket ? '沪市 A 股全市场' : `${x.count} 条成分券`}
              </div>
              <div className={`${css.tileVal} ${css.mono}`}>{fmtNum(val)}</div>
              <div className={css.tileDesc}>
                {val != null && diff != null ? (
                  <>{SCEN_CN[scen]} · 偏离 <span className={diff >= 0 ? css.up : css.down}>{pctDiff(diff)}</span> · 收盘 {fmtNum(close)}</>
                ) : (
                  <>{job ? '本次跑批无该情景点位' : '尚无该指数完成跑批'}</>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}