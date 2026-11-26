/** 估值智能体：三专家 + 主审的四张角色卡。配置与服务端批跑同源，保存后下一批生效。 */

import { useEffect, useMemo, useState } from 'react'
import { fetchJobs, type JobMeta } from './api'
import {
  PARAM_META,
  ROLE_META,
  SEV_LABEL,
  cloneConfig,
  fetchAgents,
  saveAgents,
  validateAgents,
  type AgentKey,
  type AgentsConfig,
  type AgentsPayload,
  type ExpertKey,
  type ParamKey,
  type PromptRole,
  type Severity,
} from './agents'
import css from './AgentsPage.module.css'

const EXPERT_KEYS: ExpertKey[] = ['comparable', 'financial', 'sentiment']
const msgOf = (e: unknown) => (e instanceof Error ? e.message : String(e))

function NumInput(props: {
  value: number
  min: number
  max: number
  step: number
  disabled?: boolean
  onChange: (v: number) => void
}) {
  return (
    <input
      className={css.num}
      type="number"
      value={Number.isFinite(props.value) ? props.value : ''}
      min={props.min}
      max={props.max}
      step={props.step}
      disabled={props.disabled}
      onChange={e => {
        const n = Number(e.target.value)
        props.onChange(Number.isFinite(n) ? n : 0)
      }}
    />
  )
}

function Switch(props: { checked: boolean; disabled?: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={props.checked}
      className={css.switch}
      data-on={props.checked || undefined}
      disabled={props.disabled}
      onClick={() => props.onChange(!props.checked)}
    >
      <span className={css.knob} />
    </button>
  )
}

function RoleCard(props: {
  k: AgentKey
  cfg: AgentsConfig
  disabled: boolean
  onChange: (next: AgentsConfig) => void
  onPrompt?: () => void
}) {
  const { k, cfg, disabled, onChange, onPrompt } = props
  const role = cfg.agents[k]
  const meta = ROLE_META[k]
  const patchRole = (patch: Partial<typeof role>) =>
    onChange({ ...cfg, agents: { ...cfg.agents, [k]: { ...role, ...patch } } })
  const patchCap = (param: ParamKey, sev: Severity, value: number) => {
    const caps = { ...(role.caps ?? {}) }
    caps[param] = { ...(caps[param] ?? {}), [sev]: value }
    patchRole({ caps })
  }
  const mainCaps = (param: ParamKey) => {
    for (const key of EXPERT_KEYS) {
      if (ROLE_META[key].params.includes(param)) {
        return cfg.agents[key].caps?.[param]?.['high'] ?? PARAM_META[param].hi
      }
    }
    return PARAM_META[param].hi
  }

  return (
    <section className={css.card} data-off={!role.enabled || undefined} data-main={k === 'main' || undefined}>
      <header className={css.cardHd}>
        <span className={css.code}>{meta.code}</span>
        <div className={css.cardTitle}>
          <b>{meta.name}</b>
          <small>{meta.tagline}</small>
        </div>
        <div className={css.hdRight}>
          {onPrompt && (
            <button type="button" className={css.pvBtn} onClick={onPrompt}>提示词</button>
          )}
          <Switch
            checked={role.enabled}
            disabled={disabled}
            onChange={v => patchRole({ enabled: v })}
          />
        </div>
      </header>
      <p className={css.desc}>{meta.desc}</p>

      {k === 'main' ? (
        <div className={css.mainBody}>
          <div className={css.capsChip}>
            <span>裁决上限（高严重度）</span>
            <b>可比 {mainCaps('comp_weight_pp')}pp</b>
            <b>舆情 {mainCaps('sent_weight_pp')}pp</b>
            <b>WACC {mainCaps('wacc_pp')}pp</b>
            <b>永续 {mainCaps('tg_pp')}pp</b>
          </div>
          <p className={css.note}>主审关闭时，三专家建议只留痕、不回写；影子与回写重跑都由主审裁决。</p>
        </div>
      ) : (
        <div className={css.controls}>
          <div className={css.row}>
            <span className={css.lab}>
              置信门槛
              <i>低于门槛的专家建议直接拒绝</i>
            </span>
            <div className={css.gate}>
              <input
                type="range"
                min={0.5}
                max={0.95}
                step={0.01}
                value={role.confidence_gate ?? 0.65}
                disabled={disabled || !role.enabled}
                onChange={e => patchRole({ confidence_gate: Number(e.target.value) })}
              />
              <span className={css.gateVal}>{(role.confidence_gate ?? 0.65).toFixed(2)}</span>
            </div>
          </div>

          <div className={css.capBox}>
            <div className={css.capTitle}>
              单券参数调整幅度上限
              <i>代码层按此截断，超出即压回上限</i>
            </div>
            {meta.params.map(param => {
              const pm = PARAM_META[param]
              return (
                <div className={css.capGroup} key={param}>
                  <div
                    className={css.capRow}
                    style={{ gridTemplateColumns: `minmax(84px, 1fr) repeat(${pm.sevs.length}, 64px)` }}
                  >
                    <span className={css.capLab}>
                      {pm.label}
                      <i>{pm.unit}</i>
                    </span>
                    {pm.sevs.map(sev => (
                      <span className={css.capCell} key={sev}>
                        <span className={css.sevHead}>{SEV_LABEL[sev]}</span>
                        <NumInput
                          value={role.caps?.[param]?.[sev] ?? pm.lo}
                          min={pm.lo}
                          max={pm.hi}
                          step={pm.step}
                          disabled={disabled || !role.enabled}
                          onChange={v => patchCap(param, sev, v)}
                        />
                      </span>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
      {!role.enabled && <div className={css.offTag}>已停用 · 不参与本批评审</div>}
    </section>
  )
}

const SEVS: Severity[] = ['medium', 'high', 'critical']

function PromptModal(props: {
  k: AgentKey
  role: PromptRole
  version: number
  model: string
  onClose: () => void
}) {
  const { role, onClose } = props
  const meta = ROLE_META[props.k]
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className={css.overlay}
      onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className={css.modal} role="dialog" aria-modal="true" aria-label={`${meta.name}提示词`}>
        <header className={css.modalHd}>
          <span className={css.code}>{meta.code}</span>
          <div className={css.modalTitle}>
            <b>{meta.name} · 提示词</b>
            <small>只读 · 与批跑实际发送的系统提示词一致</small>
          </div>
          <button type="button" className={css.close} onClick={onClose} aria-label="关闭">✕</button>
        </header>
        <div className={css.modalBody}>
          <div className={css.pvFacts}>
            <span>状态<b>{role.enabled ? '启用' : '停用'}</b></span>
            {role.gate != null && <span>置信门槛<b>{role.gate.toFixed(2)}</b></span>}
            <span>配置版本<b>v{props.version}</b></span>
            <span>模型<b>{props.model || '环境默认'}</b></span>
          </div>
          <h3 className={css.pvH}>
            系统提示词
            <small>system message · 末尾「本批配置」行按当前配置生成</small>
          </h3>
          <pre className={css.prompt}>{role.system}</pre>
          <h3 className={css.pvH}>
            参数权限与幅度上限
            <small>{props.k === 'main' ? '主审不新增参数，只裁决下列四项' : '越权或超上限的建议会被代码拒绝 / 夹断'}</small>
          </h3>
          <table className={css.pvTable}>
            <thead>
              <tr>
                <th>参数</th>
                {SEVS.map(s => <th key={s}>{SEV_LABEL[s]}</th>)}
              </tr>
            </thead>
            <tbody>
              {role.params.map(p => (
                <tr key={p.key}>
                  <td>{p.label}<i>{p.key}</i></td>
                  {SEVS.map(s => (
                    <td key={s}>{p.caps[s] == null ? '—' : `${p.caps[s]}pp`}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <h3 className={css.pvH}>
            逐券输入证据结构
            <small>user message · 每只券运行时生成，内容随数据变化</small>
          </h3>
          <ul className={css.pvList}>
            {role.evidence.map(x => <li key={x}>{x}</li>)}
          </ul>
          <p className={css.pvNote}>
            以上按已保存配置 v{props.version} 生成；页面里未保存的修改不会出现在这里。
            影子 / 回写模式共用同一套提示词，区别只在主审裁决后的处理。
          </p>
        </div>
      </div>
    </div>
  )
}

export function AgentsPage() {
  const [cfg, setCfg] = useState<AgentsConfig | null>(null)
  const [saved, setSaved] = useState<AgentsConfig | null>(null)
  const [meta, setMeta] = useState<AgentsPayload | null>(null)
  const [jobs, setJobs] = useState<JobMeta[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [promptKey, setPromptKey] = useState<AgentKey | null>(null)

  const load = async () => {
    setLoading(true)
    setErr(null)
    setJobs(null)
    try {
      const payload = await fetchAgents()
      setMeta(payload)
      setCfg(cloneConfig(payload.config))
      setSaved(cloneConfig(payload.config))
      fetchJobs().then(setJobs).catch(() => setJobs([]))
    } catch (e) {
      setErr(msgOf(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 5000)
    return () => window.clearTimeout(timer)
  }, [toast])

  const dirty = useMemo(
    () => !!cfg && !!saved && JSON.stringify(cfg) !== JSON.stringify(saved),
    [cfg, saved],
  )
  const invalid = useMemo(() => (cfg ? validateAgents(cfg) : null), [cfg])
  const lastJob = useMemo(
    () => (jobs ?? []).find(j => j.agent_config_version != null) ?? null,
    [jobs],
  )

  const save = async () => {
    if (!cfg || !meta) return
    const bad = validateAgents(cfg)
    if (bad) { setToast({ text: bad, kind: 'err' }); return }
    setSaving(true)
    try {
      const payload = await saveAgents(cfg)
      setMeta(payload)
      setCfg(cloneConfig(payload.config))
      setSaved(cloneConfig(payload.config))
      setToast({ text: `已保存 v${payload.config.version} · 从下一批开始生效`, kind: 'ok' })
    } catch (e) {
      setToast({ text: `保存失败：${msgOf(e)}`, kind: 'err' })
    } finally {
      setSaving(false)
    }
  }

  const revert = () => {
    if (!saved) return
    setCfg(cloneConfig(saved))
    setToast({ text: '已还原为已保存配置', kind: 'ok' })
  }

  return (
    <div className={css.page}>
      <div className={css.inner}>
        <header className={css.head}>
          <div className={css.headMain}>
            <div className={css.kicker}>AGENT CONFIG · 3 EXPERTS + 1 REVIEWER</div>
            <h1>估值智能体</h1>
            <p className={css.sub}>
              三专家 + 主审与批跑共用同一份配置；保存后从下一批开始生效，正在运行的任务不受影响。
            </p>
            <div className={css.chips}>
              <span className={css.chip}>{meta ? `版本 v${cfg?.version ?? meta.config.version}` : '版本 —'}</span>
              <span className={css.chip}>{meta?.updated_at ? `更新 ${meta.updated_at}` : '尚未保存过'}</span>
              <span className={css.chip} data-on={meta?.llm_ready || undefined}>
                LLM {meta?.llm_ready ? '已就绪' : '未配置'}
              </span>
            </div>
          </div>
          <div className={css.headRight}>
            <span className={css.state} data-on={(!err && !loading) || undefined}>
              <i />{loading ? '连接批跑服务…' : err ? '批跑服务未连接' : '批跑服务已连接'}
            </span>
            <div className={css.btns}>
              <button
                type="button"
                className={css.btn2}
                onClick={revert}
                disabled={!dirty || saving}
              >
                还原修改
              </button>
              <button
                type="button"
                className={css.btn}
                onClick={() => void save()}
                disabled={!dirty || !!invalid || saving}
              >
                {saving ? '保存中…' : dirty ? '保存配置' : '已保存'}
              </button>
            </div>
            {invalid && dirty && <div className={css.invalid}>{invalid}</div>}
          </div>
        </header>

        {err ? (
          <section className={css.empty}>
            <b>无法读取智能体配置</b>
            <p>{err}</p>
            <p className={css.tiny}>批跑服务地址由页面主机名推导（:3089）。请确认服务已启动后重试。</p>
            <button type="button" className={css.btn2} onClick={() => void load()}>重试</button>
          </section>
        ) : loading || !cfg || !meta ? (
          <section className={css.empty}><b>正在读取配置…</b></section>
        ) : (
          <>
            <section className={css.globals}>
              <label className={css.gField}>
                <span className={css.gLab}>评审模型<small>三专家 + 主审 · 留空 = 环境默认{meta.model_env ? `（${meta.model_env}）` : ''}</small></span>
                <input
                  className={css.input}
                  value={cfg.model}
                  placeholder={meta.model_env || '环境默认'}
                  onChange={e => setCfg({ ...cfg, model: e.target.value.trim() })}
                />
              </label>
              <div className={css.gField}>
                <span className={css.gLab}>并发数<small>同时评审的券数 · 1–12</small></span>
                <NumInput
                  value={cfg.concurrency}
                  min={1}
                  max={12}
                  step={1}
                  onChange={v => setCfg({ ...cfg, concurrency: Math.round(v) })}
                />
              </div>
              <div className={css.gField}>
                <span className={css.gLab}>单券超时<small>秒 · 30–240</small></span>
                <NumInput
                  value={cfg.timeout_s}
                  min={30}
                  max={240}
                  step={10}
                  onChange={v => setCfg({ ...cfg, timeout_s: Math.round(v) })}
                />
              </div>
              <div className={css.gField}>
                <span className={css.gLab}>配置文件<small>仓库外，随任务留档</small></span>
                <span className={`${css.path} ${css.mono}`}>{meta.path}</span>
              </div>
            </section>

            <div className={css.roles}>
              {(['comparable', 'financial', 'sentiment', 'main'] as AgentKey[]).map(k => (
                <RoleCard
                  key={k}
                  k={k}
                  cfg={cfg}
                  disabled={saving}
                  onChange={setCfg}
                  onPrompt={meta.prompts ? () => setPromptKey(k) : undefined}
                />
              ))}
            </div>

            <section className={css.sync}>
              <span>
                最近一批：{lastJob
                  ? <b className={css.mono}>{lastJob.id}</b>
                  : '暂无使用智能体的已完成批跑'}
                {lastJob?.agent_config_version != null && ` · 快照 v${lastJob.agent_config_version}`}
              </span>
              <span>本页保存的配置只影响之后的批跑，不回改历史任务。</span>
              <span>启用与否在「估值跑批」页选择评审模式（关 / 影子 / 回写重跑）。</span>
            </section>

            <footer className={css.foot}>
              <span>配置为当前一版，保存时版本号自增；暂不做学习闭环与跨批参数台账。</span>
              <span>密钥只存放在仓库外；本页仅显示模型名与 LLM 连通状态，不回显任何密钥。</span>
            </footer>
          </>
        )}
      </div>
      {promptKey && meta?.prompts && (
        <PromptModal
          k={promptKey}
          role={meta.prompts.roles[promptKey]}
          version={meta.prompts.version}
          model={meta.prompts.model || meta.model_env}
          onClose={() => setPromptKey(null)}
        />
      )}
      {toast && <div className={css.toast} data-kind={toast.kind}>{toast.text}</div>}
    </div>
  )
}