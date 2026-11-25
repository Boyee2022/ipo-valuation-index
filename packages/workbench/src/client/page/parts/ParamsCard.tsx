/** 右侧参数卡：舆情轮数、方法权重、口径、抽样、并行度与估值日期，全部可直接编辑。 */

import { useState } from 'react'
import { overrideError, type BatchParams } from '../data'
import {
  DateQuick,
  MiniCalendar,
  NumInput,
  ParallelQuick,
  PctInput,
  SentimentSeg,
  WeightsEditor,
} from './fields'
import css from '../ValuationPage.module.css'

export function ParamsCard(props: {
  params: BatchParams
  onChange: (p: BatchParams) => void
  date: Date
  onDate: (d: Date) => void
  parallel: 3 | 10
  onParallel: (v: 3 | 10) => void
  asOf: string
  running: boolean
  online: boolean
  validWeights: boolean
  onRun: () => void
}) {
  const { params, onChange, date, onDate, parallel, onParallel, asOf, running, online, validWeights, onRun } = props
  const [calOpen, setCalOpen] = useState(false)
  const overrideErr = overrideError(params)

  return (
    <div className={css.card} id="sec-params">
      <div className={css.cardHd}>参数确认 <span className={css.cardHdR}>PARAMETERS</span></div>
      <div className={css.cardBd}>
        <div className={css.kv}>
          <span className={css.kvK}>舆情搜索轮数（上限）</span>
          <span className={css.kvV}>
            <NumInput value={params.sentiment} onChange={v => onChange({ ...params, sentiment: v })} min={1} max={10} width={38} label="舆情搜索轮数" />
            <span className={css.kvUnit}>轮</span>
          </span>
        </div>
        <div className={css.lab2}>舆情口径</div>
        <SentimentSeg value={params.sentimentMode} onChange={v => onChange({ ...params, sentimentMode: v })} />

        <div className={css.lab2}>方法加权比例</div>
        <WeightsEditor params={params} onChange={onChange} />

        <div className={css.kv}>
          <span className={css.kvK}>WACC 覆盖</span>
          <span className={css.kvV}>
            <PctInput value={params.waccPct} onChange={v => onChange({ ...params, waccPct: v })} min={2} max={20} placeholder="逐券 CAPM" label="WACC 覆盖（%）" />
            <span className={css.kvUnit}>%</span>
          </span>
        </div>
        <div className={css.kv}><span className={css.kvK}>rf / ERP / β</span><span className={css.kvV}>1.7% / 6% / 0.65</span></div>
        <div className={css.kv}>
          <span className={css.kvK}>永续增速覆盖</span>
          <span className={css.kvV}>
            <PctInput value={params.terminalGrowthPct} onChange={v => onChange({ ...params, terminalGrowthPct: v })} min={0} max={5} placeholder="底座校准" label="永续增速覆盖（%）" />
            <span className={css.kvUnit}>%</span>
          </span>
        </div>
        {(params.waccPct != null || params.terminalGrowthPct != null) && (
          <p className={css.overrideNote}>覆盖对本批全部成分券同值生效（不区分行业），留空 = 逐券自动。</p>
        )}
        {overrideErr && <p className={css.overrideWarn}>{overrideErr}</p>}
        <div className={css.kv}>
          <span className={css.kvK}>蒙特卡洛抽样</span>
          <span className={css.kvV}>
            <NumInput value={params.statN} onChange={v => onChange({ ...params, statN: v })} min={200} max={10000} step={500} width={54} label="蒙特卡洛抽样次数" />
            <span className={css.kvUnit}>次</span>
          </span>
        </div>
        <div className={css.kv}><span className={css.kvK}>剔除离群 / 估不出</span><span className={css.kvV}>开 / 自动跳过</span></div>

        <div className={css.lab2} id="sec-parallel">并行度</div>
        <ParallelQuick parallel={parallel} onParallel={onParallel} />

        <div className={css.lab2} id="sec-date">估值日期</div>
        <DateQuick date={date} onDate={onDate} />
        <button type="button" className={css.calToggle} onClick={() => setCalOpen(v => !v)}>
          {calOpen ? '收起日历' : '选择其他交易日'} <span>{calOpen ? '▴' : '▾'}</span>
        </button>
        {calOpen && <MiniCalendar date={date} onDate={onDate} />}
        <div className={css.dateMiniMeta}>
          <span>数据时点</span><b>{asOf || '—'}</b>
        </div>

        <button
          type="button"
          className={css.btn2}
          disabled={running || !online || !validWeights || !!overrideErr}
          onClick={onRun}
        >
          {running ? '跑批进行中…' : '开始跑批（真实执行）'}
        </button>
        <div className={css.paramStatus}>
          {!online
            ? '批跑服务未连接，无法提交任务'
            : overrideErr
              ? overrideErr
              : !validWeights
                ? '方法加权合计需等于 100%'
                : running
                  ? '任务执行中，可在运行栏跟踪进度'
                  : '提交后由 Mac 批跑服务逐券执行'}
        </div>
      </div>
    </div>
  )
}
