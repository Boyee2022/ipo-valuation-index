/** 运行栏：真实跑批提交、跟踪控制、进度、日志与结果入口。 */

import type { RefObject } from 'react'
import type { JobStatus } from '../api'
import css from '../ValuationPage.module.css'

export interface LogLine {
  text: string
  kind: 'ok' | 'dim' | 'info' | 'err'
}

export interface ToastMsg {
  text: string
  kind: 'ok' | 'warn' | 'err'
}

export function RunBar(props: {
  running: boolean
  tracking: boolean
  activeJob: JobStatus | null
  viewJob: JobStatus | null
  logs: LogLine[]
  logRef: RefObject<HTMLDivElement | null>
  online: boolean
  canRun: boolean
  toast: ToastMsg | null
  onRun: () => void
  onStop: () => void
  onResume: () => void
  onResults: () => void
  onSummary: () => void
  onParams: () => void
}) {
  const { running, tracking, activeJob, viewJob, logs, logRef, online, canRun, toast } = props
  const progJob = activeJob?.state === 'running' ? activeJob : viewJob?.state === 'running' ? viewJob : null
  const prog = progJob && progJob.total > 0 ? (progJob.done / progJob.total) * 100 : 0
  const okCount = viewJob?.summary?.ok ?? null
  return (
    <div className={css.runbarWrap}>
      <div className={css.runbar}>
        <button type="button" className={css.btn} disabled={running || !canRun} onClick={props.onRun}>
          {running ? '跑批进行中…' : viewJob?.summary?.fitted_point != null ? '重新跑批（真实执行）' : '开始跑批（真实执行）'}
        </button>
        {running && tracking && <button type="button" className={`${css.btn} ${css.ghost}`} onClick={props.onStop}>停止跟踪</button>}
        {running && !tracking && <button type="button" className={`${css.btn} ${css.ghost}`} onClick={props.onResume}>恢复跟踪</button>}
        <button type="button" className={`${css.btn} ${css.ghost}`} disabled={!viewJob} onClick={props.onResults}>
          逐券结果{okCount != null ? ` · ${okCount}` : ''}
        </button>
        <button type="button" className={`${css.btn} ${css.ghost}`} disabled={!viewJob} onClick={props.onSummary}>最近汇总报告 ↗</button>
        <button type="button" className={`${css.btn} ${css.ghost}`} onClick={props.onParams}>参数配置</button>
        {toast ? (
          <div className={`${css.toast} ${css.toastOn} ${toast.kind === 'err' ? css.toastErr : toast.kind === 'warn' ? css.toastWarn : ''}`}>{toast.text}</div>
        ) : !online ? (
          <div className={`${css.toast} ${css.toastOn} ${css.toastErr}`}>批跑服务未连接 · 检查 Mac 上的 3089 服务后刷新页面</div>
        ) : (
          <div className={css.toast}>真实执行提交批跑服务 API（POST /api/run），完成后点位与区间自动更新。</div>
        )}
      </div>
      {progJob && (
        <div className={css.progWrap}>
          <div className={css.progBar}><i style={{ width: `${prog}%` }} /></div>
          <span className={`${css.progTxt} ${css.mono}`}>
            {progJob.done}/{progJob.total} · {progJob.id}
          </span>
        </div>
      )}
      {logs.length > 0 && (
        <div className={css.runlog} ref={logRef}>
          {logs.map((l, i) => (
            <div key={i} className={l.kind === 'ok' ? css.logOk : l.kind === 'err' ? css.logErr : l.kind === 'dim' ? css.logDim : undefined}>{l.text}</div>
          ))}
        </div>
      )}
    </div>
  )
}
