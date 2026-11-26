/** 多 agent 评审：三专家（可比质量 / 折现参数 / 舆情）逐券变更单、主审结论、apply 回写与人工采纳。 */

import { useEffect, useState } from 'react'
import { fmtNum } from '../data'
import {
  reportUrl,
  shadowRecordUrl,
  type AgentMode,
  type JobRow,
  type JobStatus,
  type ShadowAgent,
  type ShadowApply,
  type ShadowDecision,
  type ShadowItem,
  type ShadowParam,
  type ShadowRow,
} from '../api'
import css from '../ValuationPage.module.css'

const DEC: Record<ShadowDecision, { cn: string; cls: string }> = {
  accept: { cn: '通过', cls: css.tagOk },
  partial: { cn: '部分通过', cls: css.tagWarn },
  reject: { cn: '驳回', cls: css.tagMut },
  hold: { cn: '维持原参数', cls: css.tagMut },
  error: { cn: '评审失败', cls: css.tagErr },
}

const PARAMS: ShadowParam[] = ['comp_weight_pp', 'sent_weight_pp', 'wacc_pp', 'tg_pp']
const PARAM_CN: Record<ShadowParam, string> = {
  comp_weight_pp: '可比权重',
  sent_weight_pp: '舆情权重',
  wacc_pp: 'WACC',
  tg_pp: '永续增速',
}
const MAIN_STATUS: Record<string, string> = { accept: '通过', clamp: '夹断', reject: '驳回' }
const SEV_CN: Record<string, string> = { medium: '中', high: '高', critical: '严重' }
const AGENT_CN: Record<string, string> = { comparable: '可比质量', financial: '折现参数', sentiment: '舆情' }

function pp(x: number | null | undefined, digits = 1): string {
  if (x == null || !Number.isFinite(x)) return '—'
  return `${x > 0 ? '+' : x < 0 ? '−' : ''}${Math.abs(x).toFixed(digits)}pp`
}

function rateCn(kind?: 'wacc' | 'ke'): string {
  return kind === 'ke' ? 'Ke' : 'WACC'
}

function deltaText(items: ShadowItem[], rateKind?: 'wacc' | 'ke'): string {
  const on = items.filter(i => i.delta)
  if (on.length === 0) return '维持原参数'
  return on.map(i => `${i.param === 'wacc_pp' ? rateCn(rateKind) : PARAM_CN[i.param] ?? i.param} ${pp(i.delta)}`).join(' · ')
}

function baseText(base: ShadowRow['base']): string {
  const parts = [
    base.comp != null ? `可比权重 ${fmtNum(base.comp, 1)}%` : null,
    base.sent != null ? `舆情权重 ${fmtNum(base.sent, 1)}%` : null,
    base.wacc != null ? `${rateCn(base.rate_kind)} ${fmtNum(base.wacc)}%` : null,
    base.tg != null ? `永续增速 ${fmtNum(base.tg)}%` : null,
  ].filter(Boolean)
  return parts.join(' / ') || '—'
}

function applyText(ap: ShadowApply | null | undefined): string {
  if (!ap) return '—'
  if (ap.error) return '回写失败，沿用基线'
  if (!ap.changed) return '无通过项'
  return `中枢 ${fmtNum(ap.baseline_mid, 1)} → ${fmtNum(ap.final_mid, 1)}（${ap.changes.length} 项）`
}

interface ShadowRecordItem {
  agent?: string
  param: ShadowParam
  label?: string
  raw_delta: number | null
  delta: number | null
  severity?: string
  expert_confidence?: number | null
  expert_evidence?: string
  capped?: boolean
  status: string
  final_delta: number
  reason: string
}

interface ShadowRecord {
  agent_mode?: AgentMode
  baseline: {
    comp_weight: number | null
    sent_weight?: number | null
    wacc_pct: number | null
    tg_pct: number | null
    rate_kind?: 'wacc' | 'ke'
    wacc_source?: string
    tg_source?: string
    routed?: boolean
  }
  agents?: ShadowAgent[]
  evidence?: string
  elapsed_ms?: number
  model?: string | null
  expert: {
    issues?: string[]
    confidence?: number | null
    one_line?: string
    suggestions?: {
      agent?: string
      param: ShadowParam
      raw_delta: number
      delta: number
      severity?: string
      confidence?: number | null
      evidence?: string
      reason: string
      capped?: boolean
    }[]
    gated?: {
      agent?: string
      param: ShadowParam
      raw_delta?: number | null
      severity?: string | null
      confidence?: number | null
      evidence?: string
      reason?: string
      gate: string
    }[]
  } | null
  main: {
    decision?: string
    confidence?: number | null
    one_line?: string
    items?: { param: string; status: string; final_delta: number; reason: string }[]
  } | null
  main_error?: string | null
  items?: ShadowRecordItem[]
  apply?: ShadowApply | null
  error?: string | null
}

function ShadowDetail(props: { jobId: string; row: JobRow; onClose: () => void }) {
  const { jobId, row, onClose } = props
  const [rec, setRec] = useState<ShadowRecord | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    setRec(null)
    setErr(null)
    fetch(shadowRecordUrl(jobId, row.secucode))
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: ShadowRecord) => { if (alive) setRec(data) })
      .catch(e => { if (alive) setErr(e instanceof Error ? e.message : String(e)) })
    return () => { alive = false }
  }, [jobId, row.secucode])

  const sh = row.shadow
  const mode = rec?.agent_mode ?? sh?.mode ?? 'shadow'
  const items = rec?.items ?? []
  const changeText = (c: { from: number | string; to: number | string }): string =>
    typeof c.from === 'number' ? `${fmtNum(c.from, 2)}% → ${fmtNum(c.to as number, 2)}%` : `${c.from} → ${c.to}`

  return (
    <div className={css.mask} onClick={onClose}>
      <div className={`${css.modal} ${css.shModal}`} onClick={e => e.stopPropagation()}>
        <div className={css.modalHd}>
          <span className={css.modalKicker}>
            {mode === 'apply' ? 'APPLY REVIEW · 生效回写' : 'SHADOW REVIEW · 留痕'}
          </span>
          <button className={css.close} aria-label="关闭" onClick={onClose}>×</button>
        </div>
        <h3>{row.name}</h3>
        <p className={css.msub}>
          {row.secucode} · {row.industry ?? '—'} · 原参数：{baseText(sh?.base ?? { comp: null, wacc: null, tg: null })}
        </p>
        {err && <p className={css.errNote}>读取评审记录失败：{err}</p>}
        {!rec && !err && <p className={css.empty}>读取评审记录…</p>}
        {rec && (
          <>
            {(rec.agents ?? []).length > 0 && (
              <>
                <h4 className={css.shSec}>专家意见</h4>
                <table className={css.shTblAgents}>
                  <thead>
                    <tr><th>专家</th><th>状态</th><th>置信</th><th>结论</th></tr>
                  </thead>
                  <tbody>
                    {(rec.agents ?? []).map(a => (
                      <tr key={a.agent}>
                        <td>{a.label || AGENT_CN[a.agent] || a.agent}</td>
                        <td>{a.ok ? '完成' : '失败'}</td>
                        <td className={css.mono}>{fmtNum(a.confidence ?? null)}</td>
                        <td>{a.ok ? (a.one_line || '—') : (a.error || '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
            {rec.expert?.issues && rec.expert.issues.length > 0 && (
              <>
                <h4 className={css.shSec}>专家问题清单</h4>
                <ul className={css.shList}>
                  {rec.expert.issues.map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </>
            )}
            <h4 className={css.shSec}>专家建议 → 主审结论</h4>
            <div className={css.shTblWrap}>
              <table className={css.shTblItems}>
                <thead>
                  <tr><th>参数</th><th>提出专家</th><th>严重度·置信</th><th>专家幅度</th><th>规则化</th><th>主审</th><th>证据与理由</th></tr>
                </thead>
                <tbody>
                  {items.length === 0 && (
                    <tr><td colSpan={7}>专家未提出参数变更（维持原参数）</td></tr>
                  )}
                  {items.map(s => (
                    <tr key={s.param}>
                      <td>{s.label ?? PARAM_CN[s.param] ?? s.param}</td>
                      <td>{AGENT_CN[s.agent ?? ''] ?? s.agent ?? '—'}</td>
                      <td>{s.severity ? `${SEV_CN[s.severity] ?? s.severity} · ${fmtNum(s.expert_confidence ?? null)}` : '—'}</td>
                      <td className={css.mono}>{pp(s.raw_delta)}</td>
                      <td className={css.mono}>{pp(s.delta)}{s.capped ? '（按等级夹断）' : ''}</td>
                      <td>{`${MAIN_STATUS[s.status] ?? s.status} ${pp(s.final_delta)}`}</td>
                      <td>
                        {s.expert_evidence && <div>{s.expert_evidence}</div>}
                        <div>{s.reason || '—'}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(rec.expert?.gated ?? []).length > 0 && (
              <>
                <h4 className={css.shSec}>未过证据门槛（{(rec.expert?.gated ?? []).length} 条，未送主审）</h4>
                <ul className={css.shList}>
                  {(rec.expert?.gated ?? []).map((g, i) => (
                    <li key={`${g.param}-${i}`}>
                      {AGENT_CN[g.agent ?? ''] ? `${AGENT_CN[g.agent ?? '']} · ` : ''}
                      {PARAM_CN[g.param] ?? g.param} {pp(g.raw_delta)} · {g.gate}
                      {g.confidence != null ? ` · 置信 ${fmtNum(g.confidence)}` : ''}
                      {g.reason ? ` · ${g.reason}` : ''}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {rec.main?.one_line && <p className={css.shQuote}>主审：{rec.main.one_line}</p>}
            {rec.main_error && <p className={css.errNote}>主审调用失败：{rec.main_error}</p>}
            {rec.error && <p className={css.errNote}>评审失败：{rec.error}</p>}
            {rec.apply && (
              <>
                <h4 className={css.shSec}>回写结果（apply）</h4>
                {rec.apply.error && <p className={css.errNote}>{rec.apply.error}</p>}
                {rec.apply.changed ? (
                  <ul className={css.shList}>
                    {rec.apply.changes.map((c, i) => (
                      <li key={i}>{c.label}：{changeText(c)}</li>
                    ))}
                  </ul>
                ) : (
                  !rec.apply.error && <p className={css.empty}>无主审通过项，未改动输入。</p>
                )}
                {(rec.apply.skipped ?? []).length > 0 && (
                  <ul className={css.shList}>
                    {(rec.apply.skipped ?? []).map((s, i) => <li key={i}>跳过：{s}</li>)}
                  </ul>
                )}
                {rec.apply.changed && (
                  <p className={css.shMetaLine}>
                    <span>估值中枢 {fmtNum(rec.apply.baseline_mid, 2)} → {fmtNum(rec.apply.final_mid, 2)}</span>
                  </p>
                )}
              </>
            )}
            <div className={css.shMetaLine}>
              <span>模型 {rec.model ?? '—'}</span>
              <span>耗时 {rec.elapsed_ms ?? '—'} ms</span>
              <span>专家置信 {fmtNum(rec.expert?.confidence ?? null)} · 主审置信 {fmtNum(rec.main?.confidence ?? null)}</span>
            </div>
            {rec.evidence && (
              <>
                <h4 className={css.shSec}>送审证据（可比 / 折现 / 舆情）</h4>
                <pre className={css.shEvidence}>{rec.evidence}</pre>
              </>
            )}
            <p className={css.modalNote}>
              {mode === 'apply'
                ? '主审通过项已写入输入 JSON 并重跑引擎；基线备份保留，重跑失败自动回滚。评价仍不看是否更贴近收盘。'
                : '评审记录只用于过程质量评估：建议不进入引擎，拟合点位不受影响；不以是否更贴近收盘为评价标准。'}
            </p>
          </>
        )}
      </div>
    </div>
  )
}

export function ShadowCard(props: {
  job: JobStatus
  onAdoption: (code: string, action: 'adopted' | 'rejected' | 'clear') => Promise<void>
}) {
  const { job, onAdoption } = props
  const [pending, setPending] = useState<string | null>(null)
  const [detail, setDetail] = useState<JobRow | null>(null)
  const m = job.shadow_metrics
  const mode: AgentMode = m?.mode ?? job.agent_mode ?? 'shadow'
  const rows = job.rows.filter(r => r.status === 'ok' && r.shadow)
  const canAdopt = job.state === 'done'
  const okTotal = job.summary?.ok ?? job.rows.filter(r => r.status === 'ok').length
  const errRow = rows.find(r => r.shadow?.decision === 'error')

  const act = async (code: string, action: 'adopted' | 'rejected' | 'clear') => {
    setPending(code)
    try {
      await onAdoption(code, action)
    } finally {
      setPending(null)
    }
  }

  const disp = m?.dispersion
  const ad = m?.adoption
  const wow = m?.wow
  const ap = m?.apply

  return (
    <>
      <div className={css.card}>
        <div className={css.cardHd}>
          {mode === 'apply' ? '多 agent 评审 · 生效回写' : '多 agent 评审 · 影子留痕'}
          <span className={css.cardHdR}>
            三专家 + 主审 · {mode === 'apply' ? '引擎已回写' : '引擎未改参'} ·{' '}
            <a className={css.linkBtn} href={reportUrl(job.id, 'shadow.html')} target="_blank" rel="noreferrer">
              shadow.html ↗
            </a>
          </span>
        </div>
        <div className={css.cardBd}>
          {m && (
            <>
              <div className={css.shKpis}>
                <div className={css.shKpi}><span>完成评审</span><b>{m.reviewed}<small>/ {okTotal} 只</small></b></div>
                <div className={css.shKpi}><span>有建议</span><b>{m.suggested}<small>只</small></b></div>
                <div className={css.shKpi}><span>主审通过项</span><b>{m.accepted_items}</b></div>
                <div className={css.shKpi}><span>平均置信</span><b>{fmtNum(m.mean_confidence)}</b></div>
                {mode === 'apply' && ap && (
                  <div className={css.shKpi}>
                    <span>回写生效</span>
                    <b>{ap.changed}<small>/ {m.reviewed} 只{ap.errors ? ` · ${ap.errors} 失败` : ''}</small></b>
                  </div>
                )}
                <div className={css.shKpi}><span>人工采纳率</span><b>{ad?.rate == null ? '—' : `${Math.round(ad.rate * 100)}%`}<small>{ad ? ` ${ad.adopted} 采纳 / ${ad.rejected} 否决` : ''}</small></b></div>
                <div className={css.shKpi}><span>评审失败</span><b>{m.errors}</b></div>
              </div>
              <div className={css.shNote}>
                <span>
                  主审分布：通过 {m.decision_dist.accept} · 部分 {m.decision_dist.partial} · 驳回 {m.decision_dist.reject} · 维持 {m.decision_dist.hold} · 失败 {m.decision_dist.error}
                </span>
                {!!m.gated && (
                  <span>证据门槛拦截：{m.gated} 条建议未送主审（缺严重度 / 置信&lt;0.65 / 未引用数字 / 方向矛盾）</span>
                )}
                {mode === 'apply' && ap && (
                  <span>
                    回写：{ap.changed} 只生效 · 中枢实际变动 {ap.moved} 只
                    {ap.median_move != null ? ` · 中位变动 ${fmtNum(ap.median_move, 2)} 点` : ''}
                    {ap.errors ? ` · 回写失败 ${ap.errors} 只` : ''}
                  </span>
                )}
                {disp && (
                  <span>
                    建议离散度（中位 / IQR）：{PARAMS.map(p => `${PARAM_CN[p]} ${fmtNum(disp[p]?.median, 1)}（${fmtNum(disp[p]?.iqr[0], 1)}~${fmtNum(disp[p]?.iqr[1], 1)}，${disp[p]?.nonzero ?? 0} 只有建议）`).join(' · ')}
                  </span>
                )}
                <span>
                  {wow
                    ? `周环比稳定性：对照 ${wow.prev_job}（${wow.prev_created}），${wow.n} 只共同成分券，中位绝对变动 ${PARAMS.map(p => `${PARAM_CN[p]} ${fmtNum(wow[p], 1)}pp`).join(' / ')}`
                    : '周环比稳定性：待同指数下一期评审任务累积后计算'}
                </span>
              </div>
            </>
          )}

          {rows.length === 0 && (
            <p className={css.empty}>
              {job.state === 'running'
                ? '评审随逐券完成陆续产出…'
                : errRow?.shadow?.error
                  ? `评审未产出有效记录：${errRow.shadow.error}`
                  : '本次任务没有可展示的评审记录。'}
            </p>
          )}

          {rows.length > 0 && (
            <div className={css.shRows}>
              {rows.map(r => {
                const sh = r.shadow as ShadowRow
                const dec = DEC[sh.decision ?? 'error'] ?? DEC.error
                return (
                  <div className={css.shRow} key={r.secucode}>
                    <div className={css.shName}>
                      <b>{r.name}</b>
                      <span className={css.mono}>{r.secucode}</span>
                    </div>
                    <div className={css.shSug} title={`原参数：${baseText(sh.base)}`}>
                      {deltaText(sh.items, sh.base.rate_kind)}{!sh.items.some(i => i.delta) && sh.n_gated ? `（${sh.n_gated} 条未过门槛）` : ''}
                      {sh.apply?.changed && <span className={css.shConf}> · 已回写</span>}
                      {sh.apply?.error && <span className={css.shConf}> · 回写失败</span>}
                    </div>
                    <div className={css.shVerdict}>
                      <span className={`${css.tag} ${dec.cls}`}>{dec.cn}</span>
                      {sh.confidence != null && <span className={css.shConf}>置信 {sh.confidence.toFixed(2)}</span>}
                    </div>
                    <div className={css.shAdopt}>
                      <button
                        type="button"
                        className={`${css.shBtn} ${sh.adoption === 'adopted' ? css.shBtnYes : ''}`}
                        disabled={!canAdopt || pending === r.secucode || sh.decision === 'error'}
                        title={sh.adoption === 'adopted' ? '再次点击清除标记' : '采纳该券变更单'}
                        onClick={() => void act(r.secucode, sh.adoption === 'adopted' ? 'clear' : 'adopted')}
                      >
                        采纳
                      </button>
                      <button
                        type="button"
                        className={`${css.shBtn} ${sh.adoption === 'rejected' ? css.shBtnNo : ''}`}
                        disabled={!canAdopt || pending === r.secucode || sh.decision === 'error'}
                        title={sh.adoption === 'rejected' ? '再次点击清除标记' : '否决该券变更单'}
                        onClick={() => void act(r.secucode, sh.adoption === 'rejected' ? 'clear' : 'rejected')}
                      >
                        否决
                      </button>
                    </div>
                    <div className={css.shOne} title={sh.one_line || undefined}>
                      {sh.decision === 'error' ? (sh.error ?? '评审失败') : (sh.one_line || '—')}
                    </div>
                    <button type="button" className={css.shMore} onClick={() => setDetail(r)}>明细 ›</button>
                  </div>
                )
              })}
            </div>
          )}

          <div className={css.cardFoot}>
            专家按域提参：可比质量 → 可比权重，折现参数 → {mode === 'apply' ? 'Ke / WACC / ' : ''}永续增速，舆情 → 舆情权重；须给出严重度、置信与数字证据，主审逐条复核并夹断。
            {mode === 'apply'
              ? '通过项已回写输入并重跑引擎（金融路由写 Ke，一般券写 WACC/权重），采纳标记只记录人工复核意见。'
              : canAdopt
                ? '采纳标记仅记录人工判断，不回写引擎。'
                : '任务完成后可标记采纳。'}
          </div>
        </div>
      </div>
      {detail && <ShadowDetail jobId={job.id} row={detail} onClose={() => setDetail(null)} />}
    </>
  )
}