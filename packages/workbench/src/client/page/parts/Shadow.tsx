/** 影子评审阶段一：可比质量专家 + 主审的逐券变更单、过程指标与人工采纳。 */

import { useEffect, useState } from 'react'
import { fmtNum } from '../data'
import {
  reportUrl,
  shadowRecordUrl,
  type JobRow,
  type JobStatus,
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

const PARAMS: ShadowParam[] = ['comp_weight_pp', 'wacc_pp', 'tg_pp']
const PARAM_CN: Record<ShadowParam, string> = { comp_weight_pp: '可比权重', wacc_pp: 'WACC', tg_pp: '永续增速' }
const MAIN_STATUS: Record<string, string> = { accept: '通过', clamp: '夹断', reject: '驳回' }
const SEV_CN: Record<string, string> = { medium: '中', high: '高', critical: '严重' }

function pp(x: number | null | undefined, digits = 1): string {
  if (x == null || !Number.isFinite(x)) return '—'
  return `${x > 0 ? '+' : x < 0 ? '−' : ''}${Math.abs(x).toFixed(digits)}pp`
}

function deltaText(items: ShadowItem[]): string {
  const on = items.filter(i => i.delta)
  if (on.length === 0) return '维持原参数'
  return on.map(i => `${PARAM_CN[i.param]} ${pp(i.delta)}`).join(' · ')
}

interface ShadowRecord {
  baseline: { comp_weight: number | null; wacc_pct: number | null; tg_pct: number | null; wacc_source?: string; tg_source?: string }
  evidence?: string
  elapsed_ms?: number
  model?: string | null
  expert: {
    issues?: string[]
    confidence?: number | null
    one_line?: string
    suggestions?: {
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
  return (
    <div className={css.mask} onClick={onClose}>
      <div className={`${css.modal} ${css.shModal}`} onClick={e => e.stopPropagation()}>
        <div className={css.modalHd}>
          <span className={css.modalKicker}>SHADOW REVIEW · 阶段一</span>
          <button className={css.close} aria-label="关闭" onClick={onClose}>×</button>
        </div>
        <h3>{row.name}</h3>
        <p className={css.msub}>
          {row.secucode} · {row.industry ?? '—'} · 原参数：可比权重 {fmtNum(sh?.base.comp, 1)}% / WACC {fmtNum(sh?.base.wacc)}% / 永续增速 {fmtNum(sh?.base.tg)}%
        </p>
        {err && <p className={css.errNote}>读取评审记录失败：{err}</p>}
        {!rec && !err && <p className={css.empty}>读取评审记录…</p>}
        {rec && (
          <>
            {rec.expert?.issues && rec.expert.issues.length > 0 && (
              <>
                <h4 className={css.shSec}>专家问题清单</h4>
                <ul className={css.shList}>
                  {rec.expert.issues.map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </>
            )}
            <h4 className={css.shSec}>专家建议 → 主审结论</h4>
            <table>
              <thead>
                <tr><th>参数</th><th>严重度·置信</th><th>专家幅度</th><th>规则化</th><th>主审</th><th>证据与理由</th></tr>
              </thead>
              <tbody>
                {(rec.expert?.suggestions ?? []).length === 0 && (
                  <tr><td colSpan={6}>专家未提出参数变更（维持原参数）</td></tr>
                )}
                {(rec.expert?.suggestions ?? []).map(s => {
                  const m = (rec.main?.items ?? []).find(x => x.param === s.param)
                  return (
                    <tr key={s.param}>
                      <td>{PARAM_CN[s.param] ?? s.param}</td>
                      <td>{s.severity ? `${SEV_CN[s.severity] ?? s.severity} · ${fmtNum(s.confidence ?? null)}` : '—'}</td>
                      <td className={css.mono}>{pp(s.raw_delta)}</td>
                      <td className={css.mono}>{pp(s.delta)}{s.capped ? '（按等级夹断）' : ''}</td>
                      <td>{m ? `${MAIN_STATUS[m.status] ?? m.status} ${pp(m.final_delta)}` : '未列示'}</td>
                      <td>
                        {s.evidence && <div>{s.evidence}</div>}
                        <div>{m?.reason ?? s.reason ?? '—'}</div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {(rec.expert?.gated ?? []).length > 0 && (
              <>
                <h4 className={css.shSec}>未过证据门槛（{(rec.expert?.gated ?? []).length} 条，未送主审）</h4>
                <ul className={css.shList}>
                  {(rec.expert?.gated ?? []).map((g, i) => (
                    <li key={`${g.param}-${i}`}>
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
            <div className={css.shMetaLine}>
              <span>模型 {rec.model ?? '—'}</span>
              <span>耗时 {rec.elapsed_ms ?? '—'} ms</span>
              <span>专家置信 {fmtNum(rec.expert?.confidence ?? null)} · 主审置信 {fmtNum(rec.main?.confidence ?? null)}</span>
            </div>
            {rec.evidence && (
              <>
                <h4 className={css.shSec}>送审证据（可比质量 + 折现参数）</h4>
                <pre className={css.shEvidence}>{rec.evidence}</pre>
              </>
            )}
            <p className={css.modalNote}>
              影子记录只用于过程质量评估：建议不进入引擎，拟合点位不受影响；<b>不以是否更贴近收盘为评价标准</b>。
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

  return (
    <>
      <div className={css.card}>
        <div className={css.cardHd}>
          影子评审
          <span className={css.cardHdR}>
            可比质量专家 + 主审 · 引擎未改参 ·{' '}
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
                {disp && (
                  <span>
                    建议离散度（中位 / IQR）：{PARAMS.map(p => `${PARAM_CN[p]} ${fmtNum(disp[p]?.median, 1)}（${fmtNum(disp[p]?.iqr[0], 1)}~${fmtNum(disp[p]?.iqr[1], 1)}，${disp[p]?.nonzero ?? 0} 只有建议）`).join(' · ')}
                  </span>
                )}
                <span>
                  {wow
                    ? `周环比稳定性：对照 ${wow.prev_job}（${wow.prev_created}），${wow.n} 只共同成分券，中位绝对变动 可比 ${fmtNum(wow.comp_weight_pp, 1)}pp / WACC ${fmtNum(wow.wacc_pp, 1)}pp / 永续 ${fmtNum(wow.tg_pp, 1)}pp`
                    : '周环比稳定性：待同指数下一期影子任务累积后计算'}
                </span>
              </div>
            </>
          )}

          {rows.length === 0 && (
            <p className={css.empty}>
              {job.state === 'running'
                ? '影子评审随逐券完成陆续产出…'
                : errRow?.shadow?.error
                  ? `影子评审未产出有效记录：${errRow.shadow.error}`
                  : '本次任务没有可展示的影子记录。'}
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
                    <div className={css.shSug} title={`原参数：可比权重 ${fmtNum(sh.base.comp, 1)}% / WACC ${fmtNum(sh.base.wacc)}% / 永续增速 ${fmtNum(sh.base.tg)}%`}>
                      {deltaText(sh.items)}{!sh.items.some(i => i.delta) && sh.n_gated ? `（${sh.n_gated} 条未过门槛）` : ''}
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
            专家只提可比权重 / WACC / 永续增速三项，须给出严重度、置信与数字证据，主审逐条复核并夹断；{canAdopt ? '采纳标记仅记录人工判断，不回写引擎。' : '任务完成后可标记采纳。'}
          </div>
        </div>
      </div>
      {detail && <ShadowDetail jobId={job.id} row={detail} onClose={() => setDetail(null)} />}
    </>
  )
}