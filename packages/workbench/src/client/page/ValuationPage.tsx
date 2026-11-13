/**
 * The valuation workbench page: the interactive six-step batch flow
 * (参数确认 → 选择指数 → 成分券权重 → 估值日期 → 并行度 → 运行报告),
 * restyled to the dark "客户需求版" design (navy tokens, gold/cyan accents).
 * 真实数据模式：成分与权重来自 Mac 批跑服务（东财指数成分表），运行步提交真实跑批任务；
 * 批跑服务不可达时回退为本地演示数据。
 * 历史报告通过侧边栏工作区「估值跑批工作台」文件夹浏览（见 SidebarReports.ts）。
 */

import { useEffect, useMemo, useState } from 'react'
import type { PropsLocale } from '@deepseek-ai/dsh-client-ui-slots'
import { zh } from '../locales'
import { fetchConstituents, type ConstituentsPayload } from './api'
import { genConstituents, type BatchParams } from './data'
import css from './ValuationPage.module.css'
import { DateStep } from './steps/DateStep'
import { IndexStep } from './steps/IndexStep'
import { ParallelStep } from './steps/ParallelStep'
import { ParamsStep } from './steps/ParamsStep'
import { RunStep } from './steps/RunStep'
import { WeightsStep } from './steps/WeightsStep'

const STEP_KEYS = ['step.1', 'step.2', 'step.3', 'step.4', 'step.5', 'step.6']

export function ValuationPage(props: PropsLocale) {
  const t = (key: string): string => {
    try { return props.t(key) } catch { /* 页面首帧 locale 未就绪时用字典兜底 */ }
    return zh[key] ?? key
  }
  const [step, setStep] = useState(0)
  const [params, setParams] = useState<BatchParams>({ sentiment: 10, dcf: 30, comp: 50, sent: 20 })
  const [indexSel, setIndexSel] = useState('上证50')
  const [date, setDate] = useState<Date>(() => new Date())
  const [parallel, setParallel] = useState<3 | 10>(3)
  const [real, setReal] = useState<ConstituentsPayload | null>(null)
  const [realErr, setRealErr] = useState<string | null>(null)
  const list = useMemo(() => genConstituents(), [])

  useEffect(() => {
    let alive = true
    fetchConstituents()
      .then(p => { if (alive) setReal(p) })
      .catch(e => { if (alive) setRealErr(e instanceof Error ? e.message : String(e)) })
    return () => { alive = false }
  }, [])

  const realMode = real !== null

  const jump = (i: number) => setStep(Math.max(0, Math.min(STEP_KEYS.length - 1, i)))

  return (
    <div className={css.page}>
      <header className={css.pageHead}>
        <h1 className={css.h1}>{t('page.title')}</h1>
        <p className={css.lead}>
          两套估值技能部署在同一环境、跑同一批指数成分券，<strong>用估值替代价格、按权重合成指数点位</strong>。先以上证50 跑通，不纠结准不准，先出结果。
        </p>
        <div className={css.badges}>
          <span className={`${css.badge} ${realMode ? css.badgeOn : ''}`}>
            {realMode && <i />}
            {realMode
              ? `真实数据模式 · 成分数据时点 ${real!.as_of}`
              : '演示原型 · 表单与数据均为示例，不提交真实任务'}
          </span>
          <span className={css.badge}>拟合点位 = 指数收盘 × Σ(权重×每股估值) / Σ(权重×收盘价)</span>
        </div>
      </header>

      <div className={css.stepper}>
        {STEP_KEYS.map((key, i) => (
          <button
            key={key}
            type="button"
            className={`${css.stepBtn} ${i < step ? css.stepDone : ''} ${i === step ? css.stepActive : ''}`}
            onClick={() => jump(i)}
          >
            <span className={css.ic}>{i + 1}</span>
            <span className={css.stName}>{t(key)}</span>
          </button>
        ))}
      </div>

      <div className={css.panel}>
        <div className={css.stepBody} key={step}>
          {step === 0 && <ParamsStep params={params} onChange={setParams} />}
          {step === 1 && <IndexStep indexSel={indexSel} onSelect={setIndexSel} />}
          {step === 2 && (
            <WeightsStep
              list={list}
              real={realMode ? real!.rows : null}
              asOf={realMode ? real!.as_of : ''}
              error={realErr}
            />
          )}
          {step === 3 && <DateStep date={date} onSelect={setDate} asOf={realMode ? real!.as_of : ''} />}
          {step === 4 && <ParallelStep parallel={parallel} onSelect={setParallel} />}
          {step === 5 && (
            <RunStep
              params={params}
              indexSel={indexSel}
              date={date}
              parallel={parallel}
              list={list}
              realMode={realMode}
              realErr={realErr}
              realAsOf={realMode ? real!.as_of : ''}
            />
          )}
        </div>

        <nav className={css.nav}>
          <button className={css.btn} disabled={step === 0} onClick={() => jump(step - 1)}>← 上一步</button>
          <button
            className={`${css.btn} ${css.btnPrimary}`}
            disabled={step === STEP_KEYS.length - 1}
            onClick={() => jump(step + 1)}
          >
            下一步 →
          </button>
        </nav>
        <p className={css.footnote}>
          {realMode ? (
            <>真实成分与权重来自<b>东财指数成分表（{real!.as_of}）</b>，估值由 Mac 批跑服务逐券执行 · <b>拟合点位 = 指数收盘 × Σ(权重×每股估值) / Σ(权重×收盘价)</b> · 探索性研究，不构成投资建议</>
          ) : (
            <>演示数据由前端本地生成，不请求真实行情与估值服务 · 下一里程碑：接真实参数与跑批执行</>
          )}
        </p>
      </div>
    </div>
  )
}
