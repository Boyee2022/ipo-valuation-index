/**
 * 估值工作台 · 彭博终端风单页仪表盘。
 * 六步流程全部落在一页：抬头与点位、指数瓦片、运行栏、参数/权重/侧卡三栏、结果区。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import logoStd from '../assets/logo-csindex.png'
import logoRev from '../assets/logo-csindex-white.png'
import { fmtDateShort, fmtNum, indexMeta, overrideError, type BatchParams } from './data'
import {
  fetchConstituents,
  fetchJobs,
  pollJob,
  reportUrl,
  runBatch,
  setShadowAdoption,
  type ConstituentsPayload,
  type JobMeta,
  type JobStatus,
} from './api'
import { ParamsCard } from './parts/ParamsCard'
import { Hero, type SparkPoint } from './parts/Hero'
import { IndexTiles } from './parts/IndexTiles'
import { ConsTable } from './parts/ConsTable'
import { TopWeightsCard, RecentRunsCard, DuoCard, CronCard, recentForIndex } from './parts/SideCards'
import { RunBar, type LogLine, type ToastMsg } from './parts/RunBar'
import { Results } from './parts/Results'
import css from './ValuationPage.module.css'

const STEP_NAMES = ['参数确认', '选择指数', '成分券权重', '估值日期', '并行度', '运行报告']
const SHORT: Record<string, string> = { sh50: 'SH50', sh180: 'SH180', kc50: 'KC50', hs300: 'HS300' }

const msgOf = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function ValuationPage() {
  const [params, setParams] = useState<BatchParams>({
    sentiment: 10,
    dcf: 30,
    comp: 50,
    sent: 20,
    sentimentMode: 'rule',
    statN: 1000,
    waccPct: null,
    terminalGrowthPct: null,
    shadow: false,
  })
  const [indexSel, setIndexSel] = useState('sh50')
  const [date, setDate] = useState<Date>(() => new Date())
  const [parallel, setParallel] = useState<3 | 10>(3)

  const [cons, setCons] = useState<ConstituentsPayload | null>(null)
  const [consErr, setConsErr] = useState<string | null>(null)
  const [consLoading, setConsLoading] = useState(true)
  const [hist, setHist] = useState<JobMeta[] | null>(null)
  const [histErr, setHistErr] = useState<string | null>(null)
  const [viewJob, setViewJob] = useState<JobStatus | null>(null)
  const [viewLoading, setViewLoading] = useState(true)

  const [running, setRunning] = useState(false)
  const [tracking, setTracking] = useState(false)
  const [activeJob, setActiveJob] = useState<JobStatus | null>(null)
  const [logs, setLogs] = useState<LogLine[]>([])
  const [toast, setToast] = useState<ToastMsg | null>(null)

  const meta = indexMeta(indexSel)
  const online = !consErr
  const count = cons?.rows.length ?? meta.count
  const weightSum = params.dcf + params.comp + params.sent
  const validWeights = weightSum === 100
  const overrideErr = overrideError(params)
  const canRun = online && !running && validWeights && !overrideErr

  const pollRef = useRef<number | null>(null)
  const seenRef = useRef<Set<number>>(new Set())
  const failRef = useRef(0)
  const jobIdRef = useRef<string | null>(null)
  const toastTimer = useRef<number | null>(null)
  const logRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logs])
  useEffect(() => () => {
    if (pollRef.current !== null) window.clearInterval(pollRef.current)
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
  }, [])

  const showToast = (text: string, kind: ToastMsg['kind'] = 'ok') => {
    setToast({ text, kind })
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), 6000)
  }
  const push = (text: string, kind: LogLine['kind'] = 'info') => setLogs(prev => [...prev, { text, kind }])

  const stopPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const refreshJobs = async (): Promise<JobMeta[] | null> => {
    try {
      const jobs = await fetchJobs()
      setHist(jobs)
      setHistErr(null)
      return jobs
    } catch (e) {
      setHist(prev => prev ?? [])
      setHistErr(msgOf(e))
      return null
    }
  }

  // 切指数：拉真实成分券，并载入该指数最近一次完成的跑批。
  useEffect(() => {
    let alive = true
    setCons(null)
    setConsErr(null)
    setConsLoading(true)
    setViewJob(null)
    setViewLoading(true)
    fetchConstituents(indexSel)
      .then(p => { if (alive) setCons(p) })
      .catch(e => { if (alive) setConsErr(msgOf(e)) })
      .finally(() => { if (alive) setConsLoading(false) })
    fetchJobs()
      .then(async jobs => {
        if (!alive) return
        setHist(jobs)
        setHistErr(null)
        const latest = jobs.find(j => j.index === indexSel && j.state === 'done' && j.fitted_point != null)
        if (latest) {
          try {
            const detail = await pollJob(latest.id)
            if (alive) setViewJob(detail)
          } catch { /* 保留空态 */ }
        }
        if (alive) setViewLoading(false)
      })
      .catch(e => {
        if (!alive) return
        setHist([])
        setHistErr(msgOf(e))
        setViewLoading(false)
      })
    return () => { alive = false }
  }, [indexSel])

  const pollOnce = async (jobId: string) => {
    try {
      const st = await pollJob(jobId)
      failRef.current = 0
      setActiveJob(st)
      for (const r of st.rows) {
        if (seenRef.current.has(r.idx)) continue
        if (r.status === 'ok') {
          seenRef.current.add(r.idx)
          push(`[完成] ${r.name} · 中枢/股 ${r.per_share?.toFixed(2) ?? '—'} · 置信度 ${r.confidence_level ?? '—'}`, 'ok')
        } else if (r.status === 'skip') {
          seenRef.current.add(r.idx)
          push(`[跳过] ${r.name} · ${r.error ?? '未产出结果'}`, 'dim')
        }
      }
      if (st.state === 'done') {
        stopPolling()
        setRunning(false)
        setTracking(false)
        setActiveJob(st)
        setViewJob(st)
        const s = st.summary
        push(`[完成] ${st.total} 条处理完毕：估值 ${s?.ok ?? 0} 条 · 跳过 ${s?.skip ?? 0} 条`, 'ok')
        push(`[合成] 拟合点位 ${fmtNum(s?.fitted_point)} · 指数收盘 ${fmtNum(s?.index_close)}`, 'ok')
        showToast(`跑批完成 · 拟合点位 ${fmtNum(s?.fitted_point)} · 收盘 ${fmtNum(s?.index_close)}`, 'ok')
        void refreshJobs()
      } else if (st.state === 'error') {
        stopPolling()
        setRunning(false)
        setTracking(false)
        push(`[错误] 任务异常：${(st.error ?? '').split('\n')[0]}`, 'err')
        showToast('跑批任务异常，详情见日志', 'err')
        void refreshJobs()
      }
    } catch {
      failRef.current += 1
      push(`[轮询] 第 ${failRef.current} 次查询失败，继续重试`, 'dim')
      if (failRef.current >= 6) {
        stopPolling()
        setTracking(false)
        push('[提示] 连续查询失败，已停止跟踪；任务仍在服务端继续，可点「恢复跟踪」续看', 'dim')
        showToast('查询失败，已停止跟踪；任务仍在服务端继续', 'warn')
      }
    }
  }

  const startRun = async () => {
    if (!online) { showToast('批跑服务未连接，无法提交任务', 'err'); return }
    if (running) { showToast('已有跑批在进行中，请等待完成', 'warn'); return }
    if (!validWeights) { showToast('方法加权合计需等于 100%', 'warn'); return }
    if (overrideErr) { showToast(overrideErr, 'warn'); return }
    stopPolling()
    setRunning(true)
    setTracking(true)
    setActiveJob(null)
    setLogs([])
    seenRef.current = new Set()
    failRef.current = 0
    const ov = [
      params.waccPct != null ? `WACC ${params.waccPct}%` : null,
      params.terminalGrowthPct != null ? `永续增速 ${params.terminalGrowthPct}%` : null,
    ].filter(Boolean).join(' / ')
    push(`[准备] ${meta.name} ${count} 条 · 并行 ${parallel} · 抽样 ${params.statN} · 舆情 ${params.sentimentMode === 'llm' ? 'LLM 语义' : '规则打分'} ≤${params.sentiment} 轮 · 影子评审 ${params.shadow ? '开（可比 + 主审）' : '关'} · 估值日期 ${fmtDateShort(date)}（参考） · 数据时点 ${cons?.as_of ?? '—'}${ov ? ` · 覆盖 ${ov}` : ''}`, 'dim')
    document.getElementById('sec-run')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    try {
      const { job_id } = await runBatch({
        index: indexSel,
        parallel,
        stat_n: params.statN,
        weights: { dcf: params.dcf / 100, comp: params.comp / 100, sent: params.sent / 100 },
        sentiment_rounds: params.sentiment,
        sentiment_mode: params.sentimentMode,
        wacc_pct: params.waccPct,
        terminal_growth_pct: params.terminalGrowthPct,
        shadow: params.shadow,
      })
      jobIdRef.current = job_id
      push(`[任务] ${job_id} 已提交，开始跟踪`, 'dim')
      showToast(`任务已提交：${job_id}`, 'ok')
      void pollOnce(job_id)
      pollRef.current = window.setInterval(() => void pollOnce(job_id), 2500)
    } catch (e) {
      setRunning(false)
      setTracking(false)
      push(`[错误] 提交任务失败：${msgOf(e)} · 批跑服务不可达`, 'err')
      showToast('提交任务失败 · 批跑服务不可达', 'err')
    }
  }

  const stopTracking = () => {
    if (!running) return
    stopPolling()
    setTracking(false)
    push('[跟踪] 已停止跟踪；任务仍在服务端继续执行', 'dim')
    showToast('已停止跟踪，任务仍在服务端执行；可恢复跟踪', 'warn')
  }

  const resumeTracking = () => {
    if (!running || tracking) return
    if (!jobIdRef.current) { showToast('没有可恢复的任务', 'warn'); return }
    setTracking(true)
    push('[恢复] 继续跟踪任务进度', 'dim')
    void pollOnce(jobIdRef.current)
    pollRef.current = window.setInterval(() => void pollOnce(jobIdRef.current!), 2500)
  }

  const pickIndex = (id: string) => {
    if (id === indexSel) return
    if (running) { showToast('跑批进行中，完成后可切换指数', 'warn'); return }
    setIndexSel(id)
  }

  const markShadow = async (code: string, action: 'adopted' | 'rejected' | 'clear') => {
    const job = viewJob
    if (!job) return
    try {
      const res = await setShadowAdoption(job.id, code, action)
      setViewJob(prev => prev && prev.id === job.id
        ? {
            ...prev,
            shadow_metrics: res.shadow_metrics ?? prev.shadow_metrics,
            rows: prev.rows.map(r => (r.secucode === code ? { ...r, shadow: res.shadow } : r)),
          }
        : prev)
      showToast(action === 'adopted' ? '已标记采纳' : action === 'rejected' ? '已标记否决' : '已清除采纳标记', 'ok')
    } catch (e) {
      showToast(`标记失败：${msgOf(e)}`, 'err')
    }
  }

  const pickJob = async (id: string) => {
    if (viewJob?.id === id) return
    setViewLoading(true)
    try {
      const job = await pollJob(id)
      setViewJob(job)
    } catch {
      showToast('读取任务失败', 'err')
    } finally {
      setViewLoading(false)
    }
  }

  const focus = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  const onFlow = (i: number) => {
    if (i === 5) { focus('sec-results'); return }
    focus(['sec-params', 'sec-index', 'sec-weights', 'sec-date', 'sec-parallel'][i])
  }

  const onResults = () => {
    if (!viewJob) { showToast('尚无逐券结果，先提交一次跑批', 'warn'); return }
    focus('sec-results')
  }

  const onParams = () => focus('sec-params')

  const onSummary = () => {
    if (viewJob) window.open(reportUrl(viewJob.id, 'summary.html'), '_blank', 'noopener')
  }

  const spark: SparkPoint[] = useMemo(
    () =>
      (hist ?? [])
        .filter(h => h.index === indexSel && h.state === 'done' && h.fitted_point != null && h.index_close != null)
        .slice(0, 12)
        .reverse()
        .map(h => ({ fit: h.fitted_point!, close: h.index_close! })),
    [hist, indexSel],
  )
  const recent = useMemo(() => recentForIndex(hist, indexSel), [hist, indexSel])
  const flowCur = viewJob ? 5 : 4
  const asOf = cons?.as_of ?? ''

  const paramsCard = (
    <ParamsCard
      params={params}
      onChange={setParams}
      date={date}
      onDate={setDate}
      parallel={parallel}
      onParallel={setParallel}
      asOf={asOf}
      running={running}
      online={online}
      validWeights={validWeights}
      onRun={() => void startRun()}
    />
  )

  const runBar = (
    <RunBar
      running={running}
      tracking={tracking}
      activeJob={activeJob}
      viewJob={viewJob}
      logs={logs}
      logRef={logRef}
      online={online}
      canRun={canRun}
      toast={toast}
      onRun={() => void startRun()}
      onStop={stopTracking}
      onResume={resumeTracking}
      onResults={onResults}
      onSummary={onSummary}
      onParams={onParams}
    />
  )

  const results = <Results job={viewJob} params={params} loading={viewLoading} onAdoption={markShadow} />

  return (
    <div className={css.page}>
      <header className={css.topbar}>
        <div className={css.topbarInner}>
          <span className={css.brand}>
            <img className={css.logoStd} src={logoStd} alt="中证指数 CHINA SECURITIES INDEX" />
            <img className={css.logoRev} src={logoRev} alt="中证指数 CHINA SECURITIES INDEX" />
          </span>
          <div className={css.ttl}>估值工作台<small>INDEX VALUATION WORKBENCH</small></div>
          <div className={css.topRight}>
            <span className={`${css.live} ${consLoading ? css.liveWait : online ? css.liveOn : css.liveOff}`}>
              <i />{consLoading ? '连接批跑服务…' : online ? '批跑服务已连接 · 10.200.103.86:3089' : '批跑服务未连接 · 10.200.103.86:3089'}
            </span>
            <span className={css.topMeta}>
              成分数据时点 <b className={css.mono}>{asOf || '—'}</b> · 引擎 llm-ipo-valuation · 统计层 MC {params.statN} 次
            </span>
          </div>
        </div>
      </header>

      <div className={css.cmdbar}>
        <div className={css.cmdInner}>
          <span className={css.prompt}>CSI-VAL&gt;</span>
          <span className={css.cmd}>{SHORT[indexSel] ?? indexSel.toUpperCase()} <span className={css.mono}>{meta.code}</span> 拟合点位监控台</span>
          <button type="button" className={css.go} onClick={() => void startRun()} title="提交真实跑批">&lt;GO&gt;</button>
          <span className={css.cur} />
          <div className={css.cmdRight}>
            <span className={css.formula}>拟合点位 = 指数收盘 × Σ(权重×每股估值) / Σ(权重×收盘价)</span>
          </div>
        </div>
      </div>

      <div className={css.flow}>
        <div className={css.flowInner}>
          {STEP_NAMES.map((name, i) => (
            <span className={css.fstepWrap} key={name}>
              <button
                type="button"
                className={`${css.fstep} ${i < flowCur ? css.flowDone : ''} ${i === flowCur ? css.flowCur : ''}`}
                onClick={() => onFlow(i)}
              >
                <span className={css.fic}>{i < flowCur ? '✓' : i + 1}</span>{name}
              </button>
              {i < STEP_NAMES.length - 1 && <span className={css.arr}>→</span>}
            </span>
          ))}
          <span className={css.flowHint}>两套估值技能同环境部署 · 跑同一批指数成分券 · 差异只做展示，不做反向校正</span>
        </div>
      </div>

      <main className={css.main}>
        <Hero meta={meta} job={viewJob} spark={spark} loading={viewLoading} />
        <div id="sec-index"><IndexTiles indexSel={indexSel} onSelect={pickIndex} hist={hist} disabled={running} /></div>
        <div id="sec-run">{runBar}</div>
        <div className={css.grid}>
          <div className={`${css.col} ${css.colLeft}`}>
            <TopWeightsCard rows={cons?.rows ?? null} />
            <RecentRunsCard items={recent} viewId={viewJob?.id ?? null} loading={hist === null} indexName={meta.name} onPick={id => void pickJob(id)} />
            {histErr && <p className={css.tinyNote}>任务列表读取失败：{histErr}</p>}
          </div>
          <div className={`${css.col} ${css.colCenter}`} id="sec-weights">
            <ConsTable rows={cons?.rows ?? null} loading={consLoading} error={consErr} indexName={meta.name} asOf={asOf} weightComputed={cons?.weight_computed === true} />
            <DuoCard indexName={meta.name} chenFit={viewJob?.summary?.fitted_point ?? null} />
          </div>
          <div className={`${css.col} ${css.colRight}`}>
            {paramsCard}
            <CronCard />
          </div>
        </div>
        <div className={css.resultsSection} id="sec-results">{results}</div>
      </main>

      <div className={css.status}>
        <div className={css.statusInner}>
          <span><b>数据源：</b>东财指数成分表 / 东财财报 / 腾讯行情（{asOf || '—'}）</span>
          <span><b>估值：</b>Mac 批跑服务逐券执行（输入组装 → 估值引擎 → 统计校验 → HTML 报告 → 八项机检）</span>
          <span className={css.statusR}>中证指数 · CHINA SECURITIES INDEX · 探索性研究，不构成投资建议</span>
        </div>
      </div>
    </div>
  )
}
