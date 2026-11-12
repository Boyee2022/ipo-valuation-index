/**
 * Register the valuation workbench: a root-scoped main panel page and the
 * sidebar entry beside New Session that opens it. Claims the upstream
 * `ui-workbench` panel id, so the valuation profile must disable that
 * upstream row (see the bundle's cordis.patch.yml).
 */

import type { Context as ClientContext } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-api-remotes/client'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type { MainPanelId } from '@deepseek-ai/dsh-client-ui-layout/client'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import type {} from '@deepseek-ai/dsh-client-ui-sidebar/client'
import type {} from '@deepseek-ai/dsh-client-ui-slots'
import { BrandName } from './BrandName'
import { en, NS, zh } from './locales'
import { ValuationPage } from './page/ValuationPage'
import { WorkbenchIcon } from './WorkbenchIcon'

/** The id shared by the sidebar entry and the main panel it opens. */
export const PANEL_ID = 'workbench' as MainPanelId

/** Product name of this instance, replacing the shell's baked-in brand. */
export const PRODUCT_NAME = 'ValuationSystem'

/** Services required by the page. */
export const inject = ['slots', 'locale', 'layout']

/**
 * Register the workbench dictionaries, page, and sidebar entry.
 * @param ctx - the browser plugin context.
 */
export function apply(ctx: ClientContext): void {
  ctx.effect(() => ctx.locale.register(NS, { zh, en }), 'valuation-workbench: dictionaries')
  const t = ctx.locale.bind(NS)
  // The product title is compiled into the shared client bundles (the
  // DSH_CLIENT_TITLE build define), so it cannot be changed per instance
  // through config; rewrite it here and keep it rewritten whenever the
  // shell resets the tab title.
  ctx.effect(() => {
    const rewrite = (): void => {
      if (document.title.includes('FactorLab')) {
        document.title = document.title.split('FactorLab').join(PRODUCT_NAME)
      }
    }
    rewrite()
    const node = document.querySelector('title')
    if (!node) return undefined
    const observer = new MutationObserver(rewrite)
    observer.observe(node, { childList: true, characterData: true, subtree: true })
    return () => observer.disconnect()
  }, 'valuation-workbench: product title')
  // The new-session hero headline is baked into the shared ui-conversation
  // package ("探索指数，构建策略", its own locale namespace, no per-instance
  // override); rewrite the rendered text node to instance-appropriate copy.
  ctx.effect(() => {
    const SOURCE = '探索指数，构建策略'
    const rewrite = (): void => {
      if (!document.body || !document.body.textContent || !document.body.textContent.includes(SOURCE)) return
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      while (walker.nextNode()) {
        const node = walker.currentNode as Text
        if (node.nodeValue === SOURCE) node.nodeValue = '探索指数估值，合成指数点位'
      }
    }
    rewrite()
    const observer = new MutationObserver(rewrite)
    observer.observe(document.body, { childList: true, characterData: true, subtree: true })
    return () => observer.disconnect()
  }, 'valuation-workbench: hero headline')
  ctx.slots.inject('sidebar.brand.name', () => ctx.slots.register({
    name: 'sidebar.brand.name',
  }, BrandName))
  ctx.slots.inject('main', () => ctx.slots.register({
    name: 'main',
    key: PANEL_ID,
    locale: NS,
    inject: () => ({}),
  }, ValuationPage))
  // The shipped panel list, not a fork-only slot: the sidebar derives its rows
  // from `sidebar.panellist` registrations, so this entry appears beside
  // Plugins and Skills on a stock harness. Sorted ascending before the shipped
  // entries, so the workbench is the first row of the panel list.
  ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
    name: 'sidebar.panellist',
    id: PANEL_ID,
    order: -1,
    label: () => t('panel'),
    locale: NS,
  }, WorkbenchIcon))
  // The sidebar entry activates the panel through a private claim event; answer
  // it so selecting the row brings the workbench page to the foreground.
  ctx.effect(() => ctx.on('sidebar/panel-activate-claim', (request: { panelId: string }) => {
    if (request.panelId !== PANEL_ID) return undefined
    ctx.layout.selectPanel(PANEL_ID)
    return true
  }), 'valuation-workbench: entry activation')
}
