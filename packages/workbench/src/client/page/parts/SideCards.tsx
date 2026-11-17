/** 左栏 TOP15 权重 / 最近跑批，右栏双模型对比 / 定时任务。 */

import { fmtNum, pctDiff, shortTime } from '../data'
import type { RealConstituent, JobMeta } from '../api'
import css from '../ValuationPage.module.css'

export function TopWeightsCard(props: { rows: RealConstituent[] | null }) {
  const rows = [...(props.rows ?? [])].sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0)).slice(0, 15)
  const max = Math.max(...rows.map(r => r.weight ?? 0), 0.0001)
  const topSum = rows.reduce((a, r) => a + (r.weight ?? 0), 0)
  return (
    <div className={css.card}>
      <div className={css.cardHd}>
        样本券权重 TOP15 <span className={css.cardHdR}>{rows.length > 0 ? `合计 ${topSum.toFixed(2)}%` : '等待真实数据'}</span>
      </div>
      <div className={css.cardBd}>
        {rows.length === 0 && <p className={css.empty}>成分数据加载中或批跑服务未连接。</p>}
        {rows.map(r => (
          <div className={css.trow} key={r.secucode}>
            <span className={css.trowNm}>{r.name}</span>
            <span className={css.trowBarWrap}>
              <i className={css.trowBar} style={{ width: `${((r.weight ?? 0) / max) * 100}%` }} />
            </span>
            <span className={`${css.trowWt} ${css.mono}`}>{r.weight != null ? r.weight.toFixed(2) : '—'}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function RecentRunsCard(props: {
  items: JobMeta[]
  viewId: string | null
  loading: boolean
  indexName: string
  onPick: (id: string) => void
}) {
  const { items, viewId, loading, indexName, onPick } = props
  return (
    <div className={css.card}>
      <div className={css.cardHd}>
        最近跑批 <span className={css.cardHdR}>{items.length} 次 · {indexName}</span>
      </div>
      <div className={css.cardBd}>
        {loading && <p className={css.empty}>读取任务列表…</p>}
        {!loading && items.length === 0 && <p className={css.empty}>该指数暂无任务记录。</p>}
        {items.length > 0 && (
          <div className={css.recentScroll}>
            <table className={css.minitab}>
              <tbody>
                {items.map(h => {
                  const diff = h.fitted_point != null && h.index_close ? h.fitted_point / h.index_close - 1 : null
                  const tag = h.state === 'done' ? css.tagOk : h.state === 'running' ? css.tagWarn : css.tagErr
                  const st = h.state === 'done' ? '完成' : h.state === 'running' ? '进行中' : '异常'
                  return (
                    <tr
                      key={h.id}
                      className={viewId === h.id ? css.miniSel : ''}
                      onClick={() => onPick(h.id)}
                      title={`查看 ${h.id}`}
                    >
                      <td className={css.mono}>{shortTime(h.created)}</td>
                      <td className={`${css.numTd} ${css.mono} ${css.am}`}>{h.fitted_point != null ? fmtNum(h.fitted_point) : '—'}</td>
                      <td className={`${css.numTd} ${css.mono} ${diff == null ? '' : diff >= 0 ? css.up : css.down}`}>{diff == null ? '—' : pctDiff(diff)}</td>
                      <td className={css.numTd}><span className={`${css.tag} ${tag}`}>{st}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className={css.cardFoot}>点击任意一次回看该批点位与逐券结果</div>
      </div>
    </div>
  )
}

export function DuoCard(props: { indexName: string; chenFit: number | null }) {
  const { indexName, chenFit } = props
  return (
    <div className={css.card}>
      <div className={css.cardHd}>双模型对比 <span className={css.cardHdR}>陈老师 vs 石总</span></div>
      <div className={css.cardBd}>
        <div className={css.duo}>
          <div className={`${css.duoRow} ${css.duoHd}`}>
            <span className={css.duoC1}>参数</span><span className={css.duoC2}>陈老师技能</span><span className={css.duoC3}>石总模型</span>
          </div>
          <div className={css.duoRow}><span className={css.duoC1}>方法</span><span className={css.duoC2}>DCF+可比+舆情</span><span className={css.duoC3}>DCF+可比</span></div>
          <div className={css.duoRow}><span className={css.duoC1}>合成</span><span className={css.duoC2}>全指标加权</span><span className={css.duoC3}>主指标</span></div>
          <div className={css.duoRow}><span className={css.duoC1}>舆情调整</span><span className={css.duoC2}>质量得分 → 倍数</span><span className={css.duoC3}>无</span></div>
          <div className={css.duoRow}>
            <span className={css.duoC1}>拟合点位</span>
            <span className={`${css.duoC2} ${css.am} ${css.mono}`}>{chenFit != null ? fmtNum(chenFit) : '—'}</span>
            <span className={`${css.duoC3} ${css.faint}`}>— 待部署</span>
          </div>
        </div>
        <div className={css.cardFoot}>{indexName} · 石总模型尚未接入批跑服务，暂不并列合成。</div>
      </div>
    </div>
  )
}

function nextFriday(): string {
  const now = new Date()
  const day = now.getDay()
  let delta = (5 - day + 7) % 7
  if (delta === 0 && now.getHours() >= 17) delta = 7
  const d = new Date(now)
  d.setDate(d.getDate() + delta)
  const m = d.getMonth() + 1
  const dd = d.getDate()
  return `${d.getFullYear()}-${m < 10 ? '0' + m : m}-${dd < 10 ? '0' + dd : dd} 17:00`
}

export function CronCard() {
  return (
    <div className={css.card}>
      <div className={css.cardHd}>定时任务 <span className={css.cardHdR}>CRON · 规划中</span></div>
      <div className={css.cardBd}>
        <div className={css.cron}>
          <b>每周五 17:00 自动跑</b> · 拟于 <span className={css.cronNext}>{nextFriday()}</span> 首次启用<br />
          周频起步 → 逐周累积 → 5–10 周形成点位序列，与上证走势对照。
        </div>
        <div className={css.cardFoot}>定时任务尚未接入调度器，当前请在右侧手动提交跑批。</div>
      </div>
    </div>
  )
}

export function recentForIndex(hist: JobMeta[] | null, index: string): JobMeta[] {
  return (hist ?? []).filter(h => h.index === index).slice(0, 12)
}
