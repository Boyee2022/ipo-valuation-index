/** `valuation-workbench` namespace dictionaries for the valuation batch page. */

/** Dictionary namespace owned by this plugin. */
export const NS = 'valuation-workbench'

/** Simplified Chinese dictionary (the key-set source of truth). */
export const zh = {
  'panel': '估值跑批',
  'page.title': '估值跑批工作台',
  'page.lede': '用估值替代价格、按权重合成指数点位。先以上证50 跑通，先出结果。',
  'page.skeleton': '骨架已通：这是估值工作台在独立 dsh web 实例（3081）上的入口页。六步交互页面为下一里程碑，参照静态原型 valuation-batch-workbench.html。',
  'step.1': '参数确认',
  'step.2': '选择指数',
  'step.3': '成分券权重',
  'step.4': '估值日期',
  'step.5': '并行度',
  'step.6': '运行报告',
  'formula.title': '点位合成',
  'formula.a': '权重因子 × 当日市值 → 归一化 → 当日权重',
  'formula.b': '个股估值（替代价格）× 当日权重 → 加权求和 → 指数点位',
  'formula.warn': '不能直接等权平均——等权结果与指数点位对不上；当日权重盘中才出，可先用前一日因子计算。',
}

/** English dictionary (key set follows zh). */
export const en = {
  'panel': 'Valuation',
  'page.title': 'Valuation Batch Workbench',
  'page.lede': 'Estimate constituents, replace price with valuation, and synthesize the index level by weight.',
  'page.skeleton': 'Skeleton online: entry page of the valuation workbench on its own dsh web instance (3081). The interactive six-step page is the next milestone.',
  'step.1': 'Parameters',
  'step.2': 'Index',
  'step.3': 'Constituents & Weights',
  'step.4': 'Valuation Date',
  'step.5': 'Parallelism',
  'step.6': 'Run & Reports',
  'formula.title': 'Index Level Synthesis',
  'formula.a': 'weight factor × daily market cap → normalize → daily weight',
  'formula.b': 'per-stock valuation (replaces price) × daily weight → weighted sum → index level',
  'formula.warn': 'Never equal-weight: an equal-weighted result will not match the index level.',
}
