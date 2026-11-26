/** The sidebar's agents entry icon; the sidebar owns the button, label, and selected state around it. */

import type { ReactNode } from 'react'
import type { PropsRuntime } from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'

/**
 * Render the agents glyph at the size the sidebar asks for.
 * @param props - the sidebar's icon share: the requested edge and whether the panel is selected.
 * @returns the icon element.
 */
export function AgentsIcon({ size }: PropsRuntime<'sidebar.panellist'>): ReactNode {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="2.4" />
      <circle cx="18" cy="6" r="2.4" />
      <circle cx="12" cy="18" r="2.6" />
      <path d="M6 8.4v2.8c0 1.1.7 1.9 1.7 2.2l2.4.7M18 8.4v2.8c0 1.1-.7 1.9-1.7 2.2l-2.4.7" />
    </svg>
  )
}