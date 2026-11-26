/**
 * Register the「估值智能体」panel: a second main panel beside the workbench
 * and its sidebar entry. Self-contained so the workbench's own registration
 * (including its remembered-panel logic) stays untouched.
 */

import type { Context as ClientContext } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type { MainPanelId } from '@deepseek-ai/dsh-client-ui-layout/client'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'
import type {} from '@deepseek-ai/dsh-client-ui-slots'
import { AgentsIcon } from './AgentsIcon'
import { NS } from './locales'
import { AgentsPage } from './page/AgentsPage'

export const AGENTS_PANEL_ID = 'valuation-agents' as MainPanelId

/**
 * Register the agents page and its sidebar row.
 * @param ctx - the browser plugin context (already has slots/locale/layout).
 */
export function installAgentsPanel(ctx: ClientContext): void {
  const t = ctx.locale.bind(NS)
  ctx.slots.inject('main', () => ctx.slots.register({
    name: 'main',
    key: AGENTS_PANEL_ID,
    locale: NS,
    inject: () => ({}),
  }, AgentsPage))
  ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
    name: 'sidebar.panellist',
    id: AGENTS_PANEL_ID,
    order: 0,
    label: () => t('panel.agents'),
    locale: NS,
  }, AgentsIcon))
  ctx.effect(() => ctx.on('sidebar/panel-activate-claim', (request: { panelId: string }) => {
    if (request.panelId !== AGENTS_PANEL_ID) return undefined
    ctx.layout.selectPanel(AGENTS_PANEL_ID)
    return true
  }), 'valuation-workbench: agents entry activation')
}