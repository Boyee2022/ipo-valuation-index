/**
 * Sidebar workspace-folder report injection (DOM layer).
 *
 * The shipped WorkspaceBrowser renders sessions only under a workspace folder;
 * the「估值跑批工作台」folder owns zero sessions, so its historical batch
 * reports are injected as plain DOM rows into the expanded folder. This is the
 * prototype-phase DOM-rewrite route (same policy as the brand-title rewrite):
 * nothing in the shared dsh base changes, and the injected subtree is removed
 * whenever the sidebar collapses or React rebuilds the folder's children.
 *
 * Anchors: the folder row is the `[role=treeitem][aria-expanded]` element
 * whose text contains the folder title; the injection container hangs off the
 * row's grandparent (the group section holding the row wrapper). Hashed
 * CSS-module class names are never referenced.
 */

import { fetchJobs, pollJob, reportUrl, type JobMeta, type JobStatus } from './page/api'

const FOLDER_TITLE = '估值跑批工作台'
const MARKER = 'data-vreports'
const POLL_MS = 30000
const STYLE_ID = 'vreports-style'

let jobs: JobMeta[] | null = null
let jobsBroken = false
let lastFetch = 0
const detail = new Map<string, JobStatus | null>()
const openJobs = new Set<string>()

function findFolderRow(): HTMLElement | null {
  if (!document.body) return null
  const items = document.querySelectorAll<HTMLElement>('[role="treeitem"]')
  for (const el of Array.from(items)) {
    if (el.getAttribute('aria-expanded') === null) continue
    if ((el.textContent ?? '').includes(FOLDER_TITLE)) return el
  }
  return null
}

function findContainer(): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[${MARKER}]`)
}

function ensureStyle(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = [
    `[${MARKER}] { margin-left: 22px; display: flex; flex-direction: column; gap: 2px; padding: 2px 0 10px; }`,
    `[${MARKER}] .vr-row { display: flex; align-items: center; gap: 6px; width: 100%; border: 0; background: none; cursor: pointer; text-align: left; padding: 4px 8px; border-radius: 8px; font-size: 12.5px; color: rgb(15, 17, 21); font-family: inherit; }`,
    `[${MARKER}] .vr-row:hover { background: rgba(0, 0, 0, 0.05); }`,
    `[${MARKER}] .vr-caret { flex: none; width: 10px; color: #7b8494; }`,
    `[${MARKER}] .vr-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }`,
    `[${MARKER}] .vr-files { display: flex; flex-direction: column; gap: 2px; margin-left: 16px; padding: 0 0 4px; }`,
    `[${MARKER}] .vr-file { color: #0e7490; }`,
    `[${MARKER}] .vr-file:hover { background: rgba(14, 116, 144, 0.08); }`,
    `[${MARKER}] .vr-hint { color: #9ca3af; font-size: 12px; padding: 4px 8px; }`,
    `[${MARKER}] .vr-skip { color: #b45309; font-size: 11px; padding: 2px 8px; }`,
    // 深色外壳（ui-theme preference=dark，body[data-ds-dark-theme]）：与工作台深色设计令牌对齐。
    `body[data-ds-dark-theme] [${MARKER}] .vr-row { color: #C7D3E6; }`,
    `body[data-ds-dark-theme] [${MARKER}] .vr-row:hover { background: rgba(255, 255, 255, 0.06); }`,
    `body[data-ds-dark-theme] [${MARKER}] .vr-caret { color: #5A6B8C; }`,
    `body[data-ds-dark-theme] [${MARKER}] .vr-file { color: #38BDF8; }`,
    `body[data-ds-dark-theme] [${MARKER}] .vr-file:hover { background: rgba(56, 189, 248, 0.10); }`,
    `body[data-ds-dark-theme] [${MARKER}] .vr-hint { color: #7E8FAE; }`,
    `body[data-ds-dark-theme] [${MARKER}] .vr-skip { color: #F5C24B; }`,
  ].join('\n')
  document.head.appendChild(style)
}

function hint(container: HTMLElement, text: string): void {
  const p = document.createElement('div')
  p.className = 'vr-hint'
  p.textContent = text
  container.appendChild(p)
}

function stateLabel(state: JobMeta['state']): string {
  return state === 'done' ? '完成' : state === 'running' ? '进行中' : '异常'
}

function jobLabel(job: JobMeta): string {
  let label = `${job.created.slice(5, 16)} · ${stateLabel(job.state)}`
  if (job.fitted_point != null) label += ` · 拟合 ${job.fitted_point.toFixed(0)}`
  return label
}

function fileRow(text: string, href: string): HTMLElement {
  const a = document.createElement('a')
  a.className = 'vr-row vr-file'
  a.href = href
  a.target = '_blank'
  a.rel = 'noopener'
  a.textContent = text
  a.addEventListener('click', (e) => { e.stopPropagation() })
  return a
}

function renderJobDetail(container: HTMLElement, job: JobMeta): void {
  const files = document.createElement('div')
  files.className = 'vr-files'
  const st = detail.get(job.id)
  if (st === undefined) {
    hint(files, '加载中…')
    pollJob(job.id).then(d => {
      detail.set(job.id, d)
      if (openJobs.has(job.id)) render(container)
    }).catch(() => {
      detail.set(job.id, null)
      if (openJobs.has(job.id)) render(container)
    })
    container.appendChild(files)
    return
  }
  if (st === null) {
    hint(files, '明细加载失败')
    container.appendChild(files)
    return
  }
  files.appendChild(fileRow('汇总报告.html', reportUrl(job.id, 'summary.html')))
  const withReport = st.rows.filter(r => r.status === 'ok' && r.report)
  for (const r of withReport) {
    files.appendChild(fileRow(`${r.name} · ${r.secucode}`, reportUrl(job.id, r.report!)))
  }
  const skipped = st.rows.length - withReport.length
  if (skipped > 0) {
    const s = document.createElement('span')
    s.className = 'vr-skip'
    s.textContent = `跳过 ${skipped} 只（无报告）`
    files.appendChild(s)
  }
  container.appendChild(files)
}

function render(container: HTMLElement): void {
  container.textContent = ''
  if (jobs === null) {
    hint(container, jobsBroken ? '批跑服务未连接' : '加载中…')
    return
  }
  if (jobs.length === 0) {
    hint(container, '暂无历史报告')
    return
  }
  for (const job of jobs) {
    const open = openJobs.has(job.id)
    const row = document.createElement('button')
    row.type = 'button'
    row.className = 'vr-row'
    const caret = document.createElement('span')
    caret.className = 'vr-caret'
    caret.textContent = open ? '▾' : '▸'
    const label = document.createElement('span')
    label.className = 'vr-label'
    label.textContent = jobLabel(job)
    row.append(caret, label)
    row.addEventListener('click', (e) => {
      e.stopPropagation()
      if (openJobs.has(job.id)) openJobs.delete(job.id)
      else openJobs.add(job.id)
      render(container)
    })
    container.appendChild(row)
    if (open) renderJobDetail(container, job)
  }
}

async function refresh(): Promise<void> {
  try {
    const list = await fetchJobs()
    jobs = list
    jobsBroken = false
    lastFetch = Date.now()
  } catch {
    jobsBroken = true
  }
  const container = findContainer()
  if (container) render(container)
}

/**
 * Keep the injected report rows consistent with the folder's rendered state.
 * Idempotent: safe to run on every mutation batch.
 */
function reconcile(): void {
  const row = findFolderRow()
  const container = findContainer()
  if (!row) {
    container?.remove()
    return
  }
  const expandedNow = row.getAttribute('aria-expanded') === 'true'
  const group = row.parentElement?.parentElement
  if (!expandedNow) {
    container?.remove()
    return
  }
  if (!group) return
  ensureStyle()
  if (!container) {
    const fresh = document.createElement('div')
    fresh.setAttribute(MARKER, '')
    group.appendChild(fresh)
    render(fresh)
    if (jobs === null || Date.now() - lastFetch > POLL_MS) void refresh()
    return
  }
  if (container.parentElement !== group) group.appendChild(container)
}

/**
 * Install the sidebar report tree. Returns the disposer.
 */
export function installSidebarReports(): () => void {
  let disposed = false
  let observer: MutationObserver | null = null
  let timer = 0
  const start = (): void => {
    if (disposed || observer) return
    observer = new MutationObserver(schedule)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['aria-expanded'],
    })
    timer = window.setInterval(() => {
      const container = findContainer()
      if (container && Date.now() - lastFetch >= POLL_MS) void refresh()
    }, POLL_MS)
    schedule()
  }
  let scheduled = false
  const schedule = (): void => {
    if (scheduled) return
    scheduled = true
    queueMicrotask(() => {
      scheduled = false
      reconcile()
    })
  }
  // The bundle applies before the shell mounts; wait for the DOM to exist.
  if (document.body) start()
  else document.addEventListener('DOMContentLoaded', start, { once: true })
  return () => {
    disposed = true
    document.removeEventListener('DOMContentLoaded', start)
    observer?.disconnect()
    observer = null
    window.clearInterval(timer)
    findContainer()?.remove()
    document.getElementById(STYLE_ID)?.remove()
  }
}
