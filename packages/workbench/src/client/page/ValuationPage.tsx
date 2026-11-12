/**
 * The valuation workbench page: skeleton entry for the six-step batch flow.
 * Next milestone: interactive steps mirroring the static prototype
 * valuation-batch-workbench.html (参数确认 → 选择指数 → 成分券权重 →
 * 估值日期 → 并行度 → 运行报告), driven by a page-directed agent preset.
 */

import type { PropsLocale } from '@deepseek-ai/dsh-client-ui-slots'
import { zh } from '../locales'

export function ValuationPage(props: PropsLocale) {
  const t = (key: string): string => {
    try { return props.t(key) } catch { /* 页面首帧 locale 未就绪时用字典兜底 */ }
    return zh[key] ?? key
  }
  const steps = ['step.1', 'step.2', 'step.3', 'step.4', 'step.5', 'step.6']
  return (
    <div style={{ padding: '28px 32px', maxWidth: 880 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, margin: '0 0 6px' }}>{t('page.title')}</h1>
      <p style={{ color: '#5c6875', margin: '0 0 20px', fontSize: 14 }}>{t('page.lede')}</p>
      <ol style={{ display: 'flex', flexWrap: 'wrap', gap: 8, listStyle: 'none', padding: 0, margin: '0 0 20px' }}>
        {steps.map((key, i) => (
          <li key={key} style={{ border: '1px solid #dbe1e8', borderRadius: 999, padding: '6px 14px', fontSize: 13, color: '#0c6379', fontWeight: 600 }}>
            {i + 1} · {t(key)}
          </li>
        ))}
      </ol>
      <div style={{ border: '1px solid #dbe1e8', borderRadius: 12, padding: 16, background: '#eef2f6' }}>
        <p style={{ fontWeight: 700, margin: '0 0 8px', fontSize: 14 }}>{t('formula.title')}</p>
        <p style={{ margin: '4px 0', fontSize: 13 }}>{t('formula.a')}</p>
        <p style={{ margin: '4px 0', fontSize: 13 }}>{t('formula.b')}</p>
        <p style={{ margin: '10px 0 0', fontSize: 12.5, color: '#b45309' }}>{t('formula.warn')}</p>
      </div>
      <p style={{ color: '#5c6875', fontSize: 13, marginTop: 20 }}>{t('page.skeleton')}</p>
    </div>
  )
}
