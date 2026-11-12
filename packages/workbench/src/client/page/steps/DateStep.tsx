/** Step 4 选择估值日期：日历（周一开头），任意交易日可选（周末与未来日期禁用）。 */

import { useState } from 'react'
import { WEEK_CN, fmtDate } from '../data'
import css from '../ValuationPage.module.css'

const WEEK_HEAD = ['一', '二', '三', '四', '五', '六', '日']

export function DateStep(props: { date: Date; onSelect: (d: Date) => void }) {
  const { date, onSelect } = props
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
      <h2>选择估值日期</h2>
      <p className={css.sub}>一次只估一天，任意交易日可选（周末与未来日期不可选）；周频运行时不需手选，由定时任务自动带入当天。</p>
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
        <div className={css.pickinfo}>
          <p className={css.hint} style={{ marginTop: 0 }}>已选估值日期</p>
          <p className={css.chosen}>{fmtDate(date)}（周{WEEK_CN[date.getDay()]}）</p>
          <div className={css.quick}>
            <button onClick={() => onSelect(new Date())}>今天</button>
            <button onClick={() => { const y = new Date(); y.setDate(y.getDate() - 1); onSelect(y) }}>昨天</button>
          </div>
          <div className={css.note} style={{ marginTop: 18 }}>
            初期每周五 17:00 后自动跑；周频起步 → 逐周累积 → 5–10 周后形成点位序列，与上证走势对照。
          </div>
        </div>
      </div>
    </section>
  )
}
