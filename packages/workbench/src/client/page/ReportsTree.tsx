/** 左侧常驻「估值跑批工作台」报告文件树：任务文件夹 → 汇总 + 逐券报告。六步均可见。 */

import { useEffect, useState } from 'react'
import { fetchJobs, pollJob, reportUrl, type JobMeta, type JobStatus } from './api'
import css from './ValuationPage.module.css'

export function ReportsTree(props: { active: boolean }) {
  const { active } = props
  const [jobs, setJobs] = useState<JobMeta[] | null>(null)
  const [err, setErr] = useState(false)
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<Record<string, JobStatus | null>>({})

  const load = async () => {
    try {
      setJobs(await fetchJobs())
      setErr(false)
    } catch {
      setJobs([])
      setErr(true)
    }
  }

  useEffect(() => {
    if (!active) return
    void load()
    const t = window.setInterval(() => void load(), 30000)
    return () => window.clearInterval(t)
  }, [active])

  const toggle = async (id: string) => {
    if (open.has(id)) {
      const next = new Set(open)
      next.delete(id)
      setOpen(next)
      return
    }
    const next = new Set(open)
    next.add(id)
    setOpen(next)
    if (detail[id] === undefined) {
      try {
        const st = await pollJob(id)
        setDetail(prev => ({ ...prev, [id]: st }))
      } catch {
        setDetail(prev => ({ ...prev, [id]: null }))
      }
    }
  }

  const stLabel = (s: JobMeta['state']) => (s === 'done' ? '完成' : s === 'running' ? '进行中' : '异常')

  return (
    <aside className={css.treeRail}>
      <div className={css.treeHead}>
        <span className={css.treeTitle}>估值跑批工作台</span>
        <span className={css.linkBtn} style={{ fontWeight: 400, fontSize: 12 }} onClick={() => void load()}>刷新</span>
      </div>
      <div className={css.treeBody}>
        {jobs === null && <p className={css.treeHint}>加载中…</p>}
        {jobs !== null && err && <p className={css.treeHint}>批跑服务未连接</p>}
        {jobs !== null && !err && jobs.length === 0 && <p className={css.treeHint}>暂无历史报告</p>}
        {jobs !== null && jobs.map(job => (
          <div key={job.id} className={css.treeFolder}>
            <button className={css.treeFolderBtn} onClick={() => void toggle(job.id)} title={job.id}>
              <span className={css.treeCaret}>{open.has(job.id) ? '▾' : '▸'}</span>
              <span className={css.treeFolderNm}>
                {job.created.slice(5, 16)} · {stLabel(job.state)}
                {job.fitted_point != null && <b> 拟合 {job.fitted_point.toFixed(0)}</b>}
              </span>
            </button>
            {open.has(job.id) && detail[job.id] !== undefined && (
              <div className={css.treeFiles}>
                {detail[job.id] === null && <p className={css.treeHint}>明细加载失败</p>}
                {detail[job.id] !== null && (
                  <>
                    <button className={css.treeFile} onClick={() => window.open(reportUrl(job.id, 'summary.html'), '_blank', 'noopener')}>
                      汇总报告.html
                    </button>
                    {detail[job.id]!.rows.filter(r => r.status === 'ok' && r.report).map(r => (
                      <button key={r.idx} className={css.treeFile} onClick={() => window.open(reportUrl(job.id, r.report!), '_blank', 'noopener')}>
                        {r.name} · {r.secucode}
                      </button>
                    ))}
                    {detail[job.id]!.rows.filter(r => r.status !== 'ok').length > 0 && (
                      <span className={css.treeSkip}>跳过 {detail[job.id]!.rows.filter(r => r.status !== 'ok').length} 只（无报告）</span>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  )
}
