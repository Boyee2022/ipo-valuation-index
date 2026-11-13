/** Step 4 选择估值日期：日期盒（今天/昨天快捷）+ 日历（周一开头，周末与未来禁用）。 */

import { useState } from 'react'
import { WEEK_CN, fmtDate } from '../data'
import css from '../ValuationPage.module.css'

const WEEK_HEAD = ['一', '二', '三', '四', '五', '六', '日']
const MON_EN = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

export function DateStep(props: { date: Date; onSelect: (d: Date) => void; asOf: string }) {
  const { date, onSelect, asOf } = props
  const [viewY, setViewY] = useState(() => date.getFullYear())
  const [viewM, setViewM] = useState(() => date.getMonth())

  const move = (delta: number) => {
    let m = viewM + delta
    let y = viewY
    if (m < 0) { m = 11; y -= 1 }
    if (m > 11) { m = 0; y += 1 }
    setViewY(y)
    setViewM(m)
  }

  const daysInMonth = new Date(viewY, viewM + 1, 0).getDate()
  const offset = (new Date(viewY, viewM, 1).getDay() + 6) % 7
  const today = new Date()
  const todayStart = new Date()
  todayStart.setHours(0, 0, 0, 0)
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  const isTodaySel = sameDay(date, today)
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  const isYestSel = sameDay(date, yesterday)
  const isWeekend = (d: number) => {
    const w = new Date(viewY, viewM, d).getDay()
    return w === 0 || w === 6
  }
  const isToday = (d: number) =>
    viewY === today.getFullYear() && viewM === today.getMonth() && d === today.getDate()
  const isSel = (d: number) =>
    viewY === date.getFullYear() && viewM === date.getMonth() && d === date.getDate()

  const cells: (number | null)[] = []
  for (let k = 0; k < offset; k++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  while (cells.length % 7 !== 0) cells.push(null)

  return (
    <section>
      <h2>估值日期</h2>
      <p className={css.sub}>选某一天跑批（今天或昨天）；任意历史交易日可在下方日历点选（周末与未来日期不可选）。周频运行时不需手选，由定时任务自动带入当天。</p>
      <div className={css.datebox}>
        <div className={css.calTile}>
          <span className={css.mo}>{MON_EN[date.getMonth()]}</span>
          <span className={css.dd}>{date.getDate()}</span>
        </div>
        <div>
          <div className={css.dtext}>{fmtDate(date)}（周{WEEK_CN[date.getDay()]}）</div>
          <div className={css.dsub}>成分与权重取前一交易日收盘口径{asOf ? `（数据时点 ${asOf}）` : ''}</div>
        </div>
        <div className={css.dq}>
          <button className={`${css.qbtn} ${isTodaySel ? css.qbtnOn : ''}`} onClick={() => onSelect(new Date())}>今天</button>
          <button className={`${css.qbtn} ${isYestSel ? css.qbtnOn : ''}`} onClick={() => onSelect(yesterday)}>昨天</button>
        </div>
      </div>
      <div className={css.calwrap}>
        <div className={css.cal}>
          <div className={css.chead}>
            <button onClick={() => move(-1)}>‹</button>
            <span>{viewY} 年 {viewM + 1} 月</span>
            <button onClick={() => move(1)}>›</button>
          </div>
          <table className={css.calTable}>
            <thead><tr>{WEEK_HEAD.map(w => <th key={w}>{w}</th>)}</tr></thead>
            <tbody>
              {Array.from({ length: cells.length / 7 }, (_, r) => (
                <tr key={r}>
                  {cells.slice(r * 7, r * 7 + 7).map((d, c) => {
                    if (d === null) return <td key={c} />
                    const off = isWeekend(d) || new Date(viewY, viewM, d) > todayStart
                    const cls = [
                      css.calBtn,
                      off ? css.calBtnOff : '',
                      isSel(d) ? css.calBtnSel : '',
                      isToday(d) ? css.calBtnToday : '',
                    ].filter(Boolean).join(' ')
                    return (
                      <td key={c}>
                        <button className={cls} disabled={off} onClick={() => onSelect(new Date(viewY, viewM, d))}>
                          {d}
                          {isToday(d) && <span className={css.calDot} />}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className={css.note}>初期每周五 17:00 后自动跑；<b>周频起步 → 逐周累积 → 5–10 周后形成点位序列</b>，与上证走势对照。</div>
    </section>
  )
}
