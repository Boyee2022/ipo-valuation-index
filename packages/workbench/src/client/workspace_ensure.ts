/** 注册 dsh 工作区「估值跑批工作台」（幂等；宿主机目录未建好时指数退避重试）。
 *  宿主机路径：Mac 上 ~/.dsh-valuation/valuation-reports（批跑管线 finalize 时落盘）。 */

const REPORTS_HOST_DIR = '/Users/boyisong/.dsh-valuation/valuation-reports'
const REPORTS_WS_TITLE = '估值跑批工作台'

export async function ensureReportsWorkspace(ctx: any): Promise<boolean> {
  try {
    const ws = await ctx.workspaces.create({ path: REPORTS_HOST_DIR })
    if (ws && ws.title !== REPORTS_WS_TITLE) {
      try {
        await ctx.workspaces.rename(ws.workspaceId, REPORTS_WS_TITLE)
      } catch {
        /* 改名失败不致命：保留默认标题 */
      }
    }
    return true
  } catch {
    return false
  }
}

export function scheduleReportsWorkspace(ctx: any, attempt = 0) {
  const delays = [2000, 8000, 20000, 60000]
  const delay = delays[Math.min(attempt, delays.length - 1)]
  window.setTimeout(() => {
    void ensureReportsWorkspace(ctx).then(ok => {
      if (!ok && attempt < 7) scheduleReportsWorkspace(ctx, attempt + 1)
    })
  }, delay)
}
