/** `valuation-workbench` namespace dictionaries for the valuation batch page. */

/** Dictionary namespace owned by this plugin. */
export const NS = 'valuation-workbench'

/** Simplified Chinese dictionary (the key-set source of truth). */
export const zh = {
  'panel': '估值跑批',
  'page.title': '估值跑批工作台',
  'page.lede': '用估值替代价格、按权重合成指数点位。先以上证50 跑通，先出结果。',
  'step.1': '参数确认',
  'step.2': '选择指数',
  'step.3': '成分券权重',
  'step.4': '估值日期',
  'step.5': '并行度',
  'step.6': '运行报告',
}

/** English dictionary (key set follows zh). */
export const en = {
  'panel': 'Valuation',
  'page.title': 'Valuation Batch Workbench',
  'page.lede': 'Estimate constituents, replace price with valuation, and synthesize the index level by weight.',
  'step.1': 'Parameters',
  'step.2': 'Index',
  'step.3': 'Constituents & Weights',
  'step.4': 'Valuation Date',
  'step.5': 'Parallelism',
  'step.6': 'Run & Reports',
}
