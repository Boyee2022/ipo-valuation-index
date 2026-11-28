# 错误与边界情况处理手册（error_handling.md）

> 技能执行时遇到以下情况按本手册处理。原则：**宁可标注假设、不可编造数字**；
> **数据矛盾必须告知用户采用口径，不默默选一个**（对应论文"可解释、可审计"主张与幻觉防御）。

## 1. 输入侧

### 1.0 取值四层阶梯（v3.26.1，§1.1–§1.4 的总纲）

一句话输入里的任何字段，按以下**顺序**取值，**不得跳层**：

| 层 | 来源 | 何时用 | 台账标记 |
|---|---|---|---|
| **L1 表述** | 一句话/自由文本中用户明确给出 | 该字段有任何可用表述 | `stated` |
| **L2 采集** | Step 1 四档优先级（`fetch_data` → 用户文档 → 数据源 → WebSearch） | L1 无表述，**且标的具备公开披露** | `fetched` |
| **L3 问询** | Step 0 一次问清（≤4 项） | L1 无表述，**且标的不具备公开披露**（未上市/早期项目/未披露） | `stated`（用户答复） |
| **L4 默认** | 行业中枢 / 引擎缺省 | L1–L3 全部不可得，或用户明确表示"你来定" | `default` |

**跨越 L2 直接落 L4 是本手册最需要防的错误**：默认值填进模板后字段看起来是齐的，但它是假设不是实测——净利率默认值与真值差 5pp，DCF 的 NOPAT 基数就差 5pp，而读者无从分辨。

### 1.1 一句话信息不足
- 处理：对照 `input_template.json` 必填项（行业、营收或 CAGR、净利/净利率或亏损状态、板块），缺失项**一次问清（≤4个问题）**，不逐条追问、不反复打断。
- **问什么、不问什么**：只有「L2 采集不到且 L4 默认值会显著改变估值」的字段才问。可按 §1.3 兜底表安全落默认的字段（WACC、质量明细、永续增速）**不问**，直接落默认并标注。
- 用户回答后自动回填并继续；用户表示"你来定"时用行业惯例默认值并在报告标注"假设值"。

### 1.2 一句话表述与结构化数据的关系（三态，非"谁优先"）

**判据是「一致 / 矛盾 / 未表述」三态，不是「表述优先」或「数据优先」二选一。**

| 态 | 判据 | 处理 |
|---|---|---|
| **一致** | 表述值与计算值偏离 ≤ 容差（净利率 1pp、增速 2pp、金额 5%） | 直接采用，**记录口径**（归母/扣非、合并/母公司），不宣告谁优先——此时两者等价 |
| **矛盾** | 偏离超容差 | **按结构化数据（营收/净利）计算**，在报告"一句话输入"栏保留原话并披露差异与采用口径，不回问用户 |
| **未表述** | 一句话未涉及该字段 | **不落默认**，转入 §1.3 L2 采集；采集不可得再按 §1.0 的 L3/L4 处理 |

**为何矛盾时不采表述**：净利率是**派生量**，营收与净利是**原始量**。一句"净利率 20%"可能是扣非前、可能含政府补助、可能是母公司口径，三者都可能；而"营收 12.5 亿、净利 2.5 亿"可直接勾稽。用口径不明的派生比率去定 NOPAT 基数，误差会整条传导进 DCF 且无法追溯。

**"一致"这一态必须显式记录**：既有的「矛盾」与「缺失」两态之外，一致态此前无处理规则，导致口径信息（归母/扣非）在顺利路径上最容易丢失。

### 1.3 财务数据不全
- **前置：先走 §1.0 的 L2 采集，不得直接落默认值**。已上市/有招股书/有公开财报 → `fetch_data.py --financials` 取披露口径；未上市且无公开披露 → 回 §1.1 一次问清。
- 三层均不可得时，缺失项用默认值：净利率按行业中枢（医药 25%、半导体设计 15%、制造 10%…）；CAGR 缺失时用最近两年营收反推；WACC 默认 11%（可在 preferences 覆盖）。
- **质量明细缺失（v2.0）**：OCF/净利 默认 0.9、应收/营收 默认 0.25、毛利率趋势 默认 0、非经常性损益 默认 0；缺失越多，质量评分越接近基准 60（修正≈0），并标注"质量明细为默认值，置信度下调"。
- **环节中枢/因子参数缺失（v2.0）**：`segment_benchmark` 与 `ff_factor_adjust` 缺省时不报错，报告标注"未做因子校准"，置信度−1 档。
- 所有默认值在报告中标注"假设值 ⚠"。

### 1.4 解析台账（v3.26.1，Step 0 的真正产物）

Step 0 的目标**不是把模板填满，而是把每个字段的"数从哪来"记清**。产出 `_parse_ledger`：

```json
"_parse_ledger": {
  "entry": "一句话 | 参数模板 | 增量重估",
  "field_source": { "revenue_latest_ttm": "stated|fetched|derived|default|assumed",
                    "net_margin": "stated", "wacc": "default", "exchange": "derived" },
  "field_confidence": { "net_margin": "高|中|低" },
  "asked": ["拟上市板块"],
  "conflicts": [{ "field": "net_margin", "stated": 0.20, "computed": 0.05, "adopted": 0.05 }],
  "defaults_applied": ["wacc", "terminal_growth", "quality_details"]
}
```

**五类 `field_source` 语义**：`stated` 用户明确给出｜`fetched` 公开渠道采集｜`derived` 由其他字段算出（如净利率=净利/营收、板块按规则推断）｜`default` 行业中枢或引擎缺省｜`assumed` 引擎内部兜底常量。

**对置信度合成的约束**：`default` 与 `assumed` **不得计入"数据完整度"的分子**——否则填满模板即等于数据齐全，`factor=(0.7+0.3×完整性)×…` 退化为常数，X1 置信度管理失效。报告中「数据完整度」与「置信度」分列时，前者须注明"其中 N 项为默认值"。

**一句话里的表述还须分级**，模糊表述不得量化为数字（违反 X3 幻觉防御）：

| 类型 | 例 | 处置 |
|---|---|---|
| 硬数据 | "2025 年营收 12.5 亿" | 可用，`stated`，置信度高 |
| 比率 | "净利率 20%" | 可用，`stated` + 标"用户口径、未勾稽"，置信度中 |
| 模糊 | "毛利率比较高""增长很快" | **不可量化**，转 L2 采集或 L3 问询 |
| 前瞻 | "预计明年增长 30%" | 非实测，落 `financials.growth_forecast`，不得写入历史字段 |

## 2. 数据侧

### 2.1 可比公司不足 3 家
- 按 `ipo_rules_checklist.md` §4 降级扩展；报告显著标注"可比公司仅 N 家，置信度下调"。
- 引擎输出 `comparable_warning: true`，综合区间自动加宽（×1.2）。

### 2.2 可比数据矛盾（不同来源 PE 不一致）
- 以最近披露日期数据为准；两来源差距 >30% 时两值都保留并取区间，报告注明"数据存在分歧"。

### 2.3 外部数据源不可用（接口断开/无网络）
- 降级：用户提供数据 + WebSearch 公开数据 + 行业惯例参数完成计算；
- 所有外部参数标记"未验证"，报告置信度降级，提示用户核验。

### 2.4 行情数据时效
- 使用最近交易日数据并在报告中写明"截至 {date}"；超过 5 个交易日未更新则触发"数据时效提示"。

## 3. 计算侧（引擎自动处理，LLM 负责解释）

| 情况 | 引擎行为 | 报告呈现 |
|---|---|---|
| 亏损企业（loss_making=true 或可比全部未盈利） | 禁用 PE/PEG，自动切 PS/EV-Sales；<b>敏感性矩阵与发行约束同步回退 PS 口径</b>（v2.0.1 修复：PE 样本缺失时不再报错） | 单列"未盈利估值说明" + PS 口径标注 |
| 可比 PE 为负/缺失 | 该样本不计入 PE，计入 PS 样本 | 剔除原因列出 |
| 极端倍数 | 1.5×IQR 剔除 | 剔除前后对比表 |
| DCF 终值 > 总价值 70% | 提示"终值依赖过高" | 建议改用三阶段或降低终值增速 |
| WACC 缺失 | 默认 11%，敏感性含 WACC ±1% | 标注假设值 |
| 各方法结果离散度过大（CV>60%） | 输出离散度警告 | 方法对比表附差异解释 |
| 发行PE偏离可比 >30% | 预警（+10~30% 提示） | §5 IPO 约束检查标红/标黄 |
| 质量异常（v2.0）：应收增速>营收增速、毛利率与现金流背离 | 质量评分卡扣分，修正转负 | 评分卡明细 + 异常提示 |
| ~~情绪-质量背离（v2.0）：板块热度高但质量分<50~~ | **v3.15.0 已移除**（舆情与质量彻底解耦，口径 B；情绪不再引用质量分） | ③市场舆情不再输出交叉规则 |
| ~~舆情错杀（v2.0）：个股负面但质量分>75~~ | **v3.15.0 已移除**（同上） | — |
| 商誉风险（v2.0） | 分级折价：<10%:0｜10~15%:−2%｜15~30%:−5%｜>30%:−8%（规则统一收敛于引擎，本手册不再重复定义） | 修正表 + 原因说明 |
| 环节中枢偏差（v2.0）：可比法 vs 环节中枢隐含值偏差>30% | 输出可比选择审查提示 | 因子校准表标注 |
| wacc_params 无有效 β（v3.3） | 输出 `wacc_model.enabled=false` + 原因，DCF 回退显式 wacc/默认 11%，不阻断 | 标注"未做 CAPM 分解" |
| 历史现金流序列 <3 年（v3.3） | `cashflow_statistics.enabled=false` + warning，增速校验与 MC 校准自动跳过 | 标注"历史统计不足" |
| 行业指数与可比偏差>30%（v3.3） | warning 建议审查可比选择；可比<3家时行业指数作降级基准 | 行业指数章节标注 |
| 舆情 impact_map clamp（v3.3） | 增速/净利率/终值增速 clamp ±15pp、WACC ±2pp、倍数 ×(0.8~1.2)，超限截断 | 传导链章节标注 clamp 后值 |
| FCF 比率 <0.5（v3.4） | warning"DCF 对增速与再投资假设敏感"；报告提示资本开支强度 | DCF 章节标注 |
| fcf_ratio 无 CapEx 数据（v3.4） | 不激活，保持 OCF/净利 口径（零变化） | 标注"未做 CapEx 校准" |
| wacc_params 无有效 β（含 industry_beta）（v3.4） | `wacc_model.enabled=false` + 原因，DCF 回退显式 wacc/默认 11% | 标注"未做 CAPM 分解" |
| 可比 <3 家（v3.4 替代框架） | `comparables_shortfall` 输出替代路径（指数/交易/融资锚）+ 区间加宽 ±20% + 置信度下调 | 报告"无可比替代"章节 |
| RFP 命中排除情形（v3.5） | `recent_financing_anchor.applicable=false` + 逐项命中表，锚失效；fallback_paths 同步置 false | 报告"融资价格法适用性"章节 |
| repurchase 输入无效（v3.5） | repurchase_price/shares ≤0 → 输出可解释占位（repurchase_value=None），不报错 | 标注"回购条款无效" |
| liquidity σ²T≈0（v3.5） | 看跌期权法返回折扣 0（防 ln(0) NaN）；经验法正常 | 标注"波动率/持有期缺失" |
| nav 净资产缺失（v3.5） | `adjusted_nav=None` + 说明，不报错 | 标注"净资产法未计算" |
| 输入异常值（v3.5） | `input_validation` 输出分级（error/warning）规则与命中清单，仅提示不强制改值 | 报告"数据校验"章节标注 |
| 可比数据时点混用（v3.6 A2） | comparables.as_of 差 >30 天 → 警示，建议统一数据日期 | 报告"可比选择"章节标注 |
| 三表勾稽不一致（v3.6 A3） | 净利×净利率偏差>30% / 毛利率<净利率 / 净现比<0.5 → 分级警示 | 报告"数据校验"章节标注 |
| 数据时效（v3.6 A4） | 数据距基准日 >180 天 → 警示（中证协第六条从严） | 报告"数据口径"章节标注 |
| WACC 参数缺省（v3.6 A1） | rf/erp/β 缺省用公开参考值（10Y 国债/Damodaran/行业β表），rf_source/erp_source/beta_source 留痕 | 假设汇总章节标注来源 |
| 弹性 clamp 截断（v3.6 B8） | 方向异常时检测扰动触界 → "扰动被截断，弹性可能失真"说明（v3.4.2 起双向检测：`_clamp_hit_one`） | 统计校验章节披露 |
| **低 WACC/低 tg 标的弹性失真（v3.4.2）** | 基准值落在校准库**绝对** clamp 外时（如 wacc 6.5% < 下界 0.07），±1σ 双向同被抬升 → 「同号非单调」＋「−1σ 零响应」。修复：`_elasticity_dists` 在**诊断路径**把 clamp 放宽到「基准值 ±2σ」，**MC 抽样口径零变化**。**切勿放宽全局 clamp**——wacc→0.04 会使 1/(wacc−tg) 双曲放大，实测 22/27 案例 MC 尾部膨胀（茅台 std 2582→12485） | `elasticity` / `elasticity_issues` |
| **quality_indicators 弹性方向异常（v3.4.2）** | 该参数是**方向混合**的指标束（ocf 越高越好；应收/存货/非经常性越低越好），单一 +δ 的符号期望不成立——`EXPECTED_SIGNS` 已置 `None`。若见「+1σ 方向异常」，先查是否某项指标**跨过评分档阈值**（如 nonrecurring_ratio 越过 5%），属真实机制而非缺陷 | `elasticity.quality_indicators` |
| 输入静态结构错误（v3.6 D1） | input_validator.py 按 input_schema.json 检查必填/类型/范围，error 级即阻断 | 运行前校验 |
| FCFF 基准为负（v3.7 B1） | fcff_mode 激活且 EBIT(1−t)+D&A−CapEx−ΔWC<0 → warning"资本开支/营运资本占用过高，DCF 可能失真" | DCF 章节标注 |
| fcff_mode=true 但 ebit/capex 缺失（v3.7 B1） | 静默回退"净利×FCF比率"口径（零变化），不报错 | 标注"未启用报表级 FCFF" |
| capex_by_year 长度不足 5 年（v3.7 B1） | 缺少年份按基年 capex×增速外推补齐 | fcff 明细标注 |
| 情景档位自适应启用但无 asset_type（v3.7 B6） | 按默认 ±10pp（growth 档），basis 标注 asset_type=default | scenario_adapter 块标注 |
| MC 尾部联动 ρ 设置（v3.8 B4） | cross_corr_growth ∈ [0,1)（default 0 零变化；cxmt 0.5 周期示范）；ρ>0 时 MC 尾部更宽，报告标注"已建模增速×倍数联动" | mc_config 输出 |
| liquidity 未启用时 MC 含 liquidity_discount 参数（v3.8 B5） | 不消耗 rng、不扰动（seed 复算保持），弹性 delta=0 | mc_config.liquidity_perturbed=false |
| liquidity 扰动 clamp（v3.8 B5） | volatility clamp [0.05,0.95]、discount_pct clamp [0,0.5]，超限截断 | mc_config/弹性章节标注 |
| anchor_update 启用但缺 anchor_value（v3.9 C1） | 输出 enabled=false + note，不报错 | 标注"锚值缺失" |
| 贝叶斯锚在情景区间外（v3.9 C1） | 后验集中最接近情景（数学正确），报告提示锚显著偏离模型区间 | 锚定章节标注 |
| **WACC 未填时硬编码 11%（v3.22.0 修复①）** | 11% 是 rf 1.9% 时代的旧值；`dcf_cost.wacc_default_mode=capm_auto` 时改为 `rf + β×ERP + 债务成本` 动态构造，挂 `wacc_default`（rf/erp/β_L/wacc/delta_pp），偏差 >1pp 告警。显式 `financials.wacc` 仍优先，CAPM 只作校验 | 假设汇总「WACC 取值来源」行 |
| **ERP 口径混用（v3.22.0 ①b）** | `erp_default_mode=auto`：capm_auto 时取 CVA CCPFC2026 隐含 ERP **8.04%**、否则 Damodaran 5.5%；`erp_source` 逐档标注。实测 8.04%→5.5% 使格力每股 +36.9%、美的 +38.2%——**这是全组最大敏感项**，报告须并列披露两口径 | `wacc_default.erp_source` |
| **p0_value_driver 缺参静默回退（v3.22.0 修复②）** | `cashflow_model=p0_value_driver` 但缺 ebit/roic 时，原实现静默回退「净利×比率」（无再投资约束）。现恒挂 `cashflow_model_fallback`（missing 清单 + 降级去向）；`cashflow_fallback_mode=error` 时再降置信度封顶「中」 | `cashflow_model_fallback` 块 |
| **可比法不可用致综合值缩水（v3.22.0 修复③）** | `comp_v = ... or 0.0` 使可比法无值时取 0、权重仍占 50%，综合值只剩 DCF 的 30% 且不报错。`method_drop_mode=renormalize` 时剔除该法（及共用 comp_v 的舆情路径）并按剩余权重再归一，`comparable_raw=null`、挂 `method_drop` | `scenarios.base.method_drop` |
| **重资产仍走比率法（v3.22.0 修复④）** | `fcff_suggest=true` 时，若 Capex/营收 >8% 且未启 `fcff_mode`，输出 `fcff_suggestion` + warning（含是否已具备 ebit）。**注意该阈值只拦「capex 偏高」，拦不住「capex 异常偏低」**（格力曾误填 7.30 亿 vs 应 125.31 亿，强度 0.45% 不触发但开 fcff_mode 高估 46.6%） | `fcff_suggestion` 块 |
| **tg 与 WACC 不联动（v3.22.0 修复⑤）** | 只开 `cva_2pct` 而 WACC 仍 11% 时，终值倍数 `(1+g)/(WACC−g)` 由 21.20× 掉到 11.33×（−46.6%）。`require_explicit_wacc_with_cva_tg=true` 时给出可复算告警，提示补 `financials.wacc` 或开 `capm_auto` | warnings + 报告 §6.2 |
| **极端终值占比仍出单点（v3.22.0 修复⑥）** | A6 extreme 档（>85%）原只封顶置信度「中」、中枢照出。`point_estimate_guard=true` 时 `synthesis.point_estimate=null` + `point_estimate_suppressed`；**情景区间与 MC 90% 仍有效**，结论降级为区间口径而非无结论 | `synthesis.point_estimate` / `_suppressed` |
| **DCF 缺省为「起点×增速」而非报表传导（v3.23.0 D6/D7）** | 缺省 p2_legacy 下 Capex/D&A/ΔWC 都不随增速联动，高增长标的 FCFF 被高估。需要报表口径时用顶层 `dcf_drivers`（收入→EBIT→NOPAT→+D&A−Capex−ΔWC），支持成本率+费用率合成 EBIT 率、逐年 capex 路径、`nwc_turnover` 周转率口径 | `scenarios.base.dcf.cashflow_drivers` |
| **一次性 ΔWC 被永久年化（v3.23.0 D7）** | `fcff_mode` 把单年 FCFF（含一次性营运资本释放）整体按 g 外推。美的 ΔWC −67.24 亿 → fcff 口径 136.69 元 vs drivers 口径 121.85 元（**+12.2%**）。一次性项用 `dcf_drivers.delta_wc_first`，只计第 1 年 | `cashflow_drivers.rows[].delta_wc` |
| **年末折现系统性低估（v3.23.0 D1）** | 现金流并非全部在年末到账。`discount_timing=mid_year` 时显式期 `t−0.5`、终值 `n−0.5`，WACC 8.8% 时现值 +4.3% | `dcf.discount_timing` |
| **小市值标的缺规模溢价（v3.23.0 D2）** | `size_premium_mode=cva_deciles` 按 `market_cap` 查 CVA 十分位（0.33%–11.14%，≤24.41 亿最高 18.29%），加在 CAPM ke 上；**显式 wacc 时不覆盖**。缺市值 → 不激活并留 `applied=False` | `wacc_model.size_premium` / 顶层 `size_premium` |
| **capex 偏低无法拦截（v3.23.0 D3）** | 8% 营收阈值只拦偏高。`capex_check=true` 时按 `capex/d_a` 合理带（缺省 [0.5, 10]，白电 1.5–3.5）判定；格力 7.30 亿笔误比值 0.15 → warning | `capex_check` |
| **形态判出但不改数（v3.23.0 D4）** | B2 只判形态，缺省增速仍可能用 20% 兜底。`growth_base_rule=cva_matrix` 时按形态取基准（下行→最近一年、加速→0.2/0.3/0.5），用户显式 `growth_forecast` 永不覆盖；正负切换/样本不足 → 不取平均并强制披露 | `growth_base_rule` |
| fetch_data 网络失败/接口变更（v3.9 D2b） | 输出明确错误+HINT（手动检索建议），退出码非 0，不影响估值主流程 | 标注"行情拉取失败，数据手工补充" |
| report_generator 输入缺 stat/input（v3.9 D4） | stat 缺失时三口径仅情景区间（MC 行显示"—"）；input 缺失时溯源章节提示 | 报告章节自适应 |
| 行业长期增速缺失（v3.11 公开锚） | lt_base=None → 不注入公开锚项（旧行为零变化），implied_tg 由自身/可比项加权 | growth_triangulation 标注 |
| 海外可比组无 PE 数据（v3.11 分组） | metrics_by_group 该组 pe=None（n=0），group_gap 用有值组计算 | 分组表标注 |
| β 回归样本不足（v3.11 beta_estimator） | 月收益 <24 个月 → 输出 error 提示，回退手填 comparable_betas/Damodaran 行业表 | beta.json error 字段 |
| 海外代码不支持（v3.11） | 韩股 .KS 等 secid_of 返回 None → 明确提示用 ADR 或手动输入 | 脚本 stderr 提示 |

## 4. 推理侧（LLM 幻觉防御）

- **数字红线**：报告中的财务数字、区间、倍数、敏感性数值一律来自引擎输出或用户文件原文，LLM 不得自行生成具体数字；
- **溯源要求**：每个关键假设必须给出"依据/来源"列，来源缺失的标"假设值"；
- **多模型交叉验证**（如环境支持）：关键结论用两个模型/两次推理核对；不一致时以低置信度处理并标注；
- **置信度阈值**：综合区间置信度 <60% 时（可比不足、数据未验证等），报告顶部显式声明"结果置信度低，仅供方向参考"；
- **审计留痕**：报告保留输入参数 JSON 摘要与引擎输出文件路径，便于复核。

## 4b. 统计校验侧（v3.0 新增 / v3.2 增强，stat_validation.py）

| 情况 | 处理 |
|---|---|
| 蒙特卡洛样本成功率 <95% | 直接读取 `monte_carlo.success_rate` 与顶层 `validation_passed=false`：报告顶部强制标注"统计校验未通过（样本失败率 {x}%）"，并列出失败原因（多为极端参数组合导致引擎降级） |
| MC 90% 区间宽于情景区间 >±20% | 置信度表述降一档；报告说明"参数不确定性高于情景设计"，建议以统计区间为主口径 |
| MC 中位数偏离点估计 >±15% | 提示"点估计受参数组合非线性影响"，报告给出两者对照与取舍依据 |
| 弹性分析出现方向异常（如倍数 +1σ 反致估值下降） | 脚本已自动检测：读取 `elasticity.*.direction_flag`（异常）与顶层 `elasticity_issues`；检查 clamp/扰动逻辑是否失效（参考 v3.0 曾发生的倍数钳位 bug：clamp 必须作用于乘子而非倍数绝对值）；修复后重跑 |
| 校准库缺失（calibration_params.json 不存在） | 使用内置默认先验分布并在 stat.json 标注"默认校准"，不阻断流程 |
| 参数间真实相关性未知 | MC 仅按设计控制组内相关（增速/倍数组内 common_factor），不覆盖真实市场相关性（如周期回落时增速与倍数同向崩溃）→ 报告中声明尾部风险可能被低估 |
| 先验分布幅度（σ）主观性 | 报告注明"σ 基于案例校准，无权威基准"；用户可 --calibration 覆盖 |

## 5. 场景侧

| 场景 | 处理 |
|---|---|
| 用户只要一句话结论 | 先给区间结论 + 3 条核心依据，再询问是否出完整报告 |
| 增量重估 | 保留原案例假设，diff 输出变化项；区间收敛/发散分析 |
| 集团多业务 | 引擎支持分部 SOTP 输入（`segments[]`），每分部选法 |
| 未盈利+无收入（早期生物科技） | 用管线/里程碑估值（rNPV）框架，需用户提供管线参数，否则明示"无收入公司需管线参数，无法仅凭一句话估值" |
| 境外上市（港股/美股） | 调整板块规则（如港交所 18A、美股 SPAC），可比改用海外同业，流动性折价参数不同 |
| 涉及敏感标的/合规 | 遵循保密要求；不提供构成操纵市场的建议 |

## 6. 用户常见误区纠正（主动提示）

- "估值越高越好"：技能给出区间而非单点，提示高倍数对应的假设强度；
- "PE 万能"：亏损/周期股禁用 PE 时主动解释；
- "DCF 结果低于市场价=模型错"：解释 DCF 为内在价值口径，市场价含情绪溢价（论文"情绪/舆情维度修正"的正向应用）。

## 7. 三层计划（v3.16.0 / v3.16.1）边界与降级路径

| 场景 | 处理 | 留痕 |
|---|---|---|
| Layer 0 判 `dcf_admissible=false`（金融/资源） | dcf 权重按 `dcf_weight_cap` 归零并比例重分配其余路径；路由 RIM/DDM/NAV；**不可对同一标的既跑 DCF 又跑替代模型再平均**（前提互斥） | `framework_check` + warning |
| Layer 0 判 `conditional`（REITs/管线/负 FCFF/多分部） | 保留 DCF 但权重封顶（0.2~0.3），主方法标注替代模型 | `framework_check.dcf_weight_cap` |
| Layer 1 判衰退期且 `tg` 输入 > 0 | 强制 `tg = min(tg, tg_floor=0)` 并 warning；再投资率转负（回收资本） | `growth_schedule` + warning |
| Layer 1 初创期 + 终值占比 >100% | 提示禁用 Gordon 终值（应走退出倍数/概率加权）；DCF 结果仅作参照 | warning |
| P0 价值驱动式 `g_t > ROIC` | RR 触上界 1.0 → FCFF 归零 → DCF 退化为净现金下限；输出违规年份，提示"提高 ROIC 或下调增速" | `reinvestment_consistency` |
| P0 缺 `ebit` 或 `roic` | 静默回退 P2（净利×FCF 比率），不报错 | `dcf.fcf_basis` 可见 |
| 行业未命中 `industry_params.json` | 回落 `default` 全局兜底行；不影响主流程 | `industry_params.matched_industry="default"` |
| **发电侧公用事业回落 default（v3.16.6 / industry_params 1.0.3）** | 原表只有「电力设备」（制造业）无发电侧类目，水电/核电运营商会回落 default。现已补「公用事业」类目（别名 水力发电/水电/发电/电力生产/电力、热力/核电/供电；**不含裸「电力」**以避与电力设备歧义）。若仍见 `matched_industry="default"`，检视行业串是否含上述词形 | `industry_params.matched_industry` |
| 输入键**显式给 null** 致引擎崩溃（**v2.14.3 起修，v2.14.4 缺陷族补全**） | `dict.get(k, default)` **仅在键缺失时**返回 default；键存在且值 `None` 时返回 `None` → 下游算术抛 `TypeError`（中国平安案例崩溃点：`dcf_valuation()` 的 `equity = pv_sum + tv_pv + net_cash`）。**v2.14.4 已全链路补全**：新增助手 `_nn(v, d)`＝`d if v is None else v`，替换 9 处取数点（`cagr_3y` / `revenue_latest_ttm`×3 / `ebitda_ttm` / `net_cash`×3 / `net_margin`）。**为何不用 `v or d`**：会把合法 int `0` 变成 float `0.0`，造成 `0` vs `0.0` 序列化差异（首版修复即被 A/B 捕获）。**通用处置**：新增数值字段取数一律经 `_nn`，不得依赖 `get(k, default)` 语义；输入层 null 只限语义确为「缺失/不适用」的字段 | 运行期 `TypeError` / 字段渲染为 0 |
| **报告层把「DCF 名义留痕值」当并行法呈现（v3.16.7）** | 金融/资源类路由（`framework_check.dcf_admissible=false`）下引擎已把 dcf 权重归零（`dcf_weight_cap=0`）并路由替代主方法，但 DCF 分支仍被机械算出一个**名义值**（平安 26,990.12 亿，恒为高估方向）。报告若照常呈现，会把「市场口径 vs DCF 比值 0.39」误读为「两口径接近、相互印证」。**处置**：`report_generator.py` v3.16.7 在 `dcf_admissible is False` 时改写 §2/§6.1/§7.1（含新增 `callout.alert`「方法选择结论」）/§7.2 与 `gap_note`，明确「不参与综合、不构成内在价值判断、不与市场口径构成互证」 | `framework_check.dcf_admissible` / `weights.dcf=0` |
| **置信度只给档位不给理由（v3.16.7）** | 引擎 `confidence.method_coverage` / `method_divergence` 两条折减机制原先仅在输出 JSON、报告不呈现，读者无法理解「为何是『中』档」。**处置**：§10 结论框增「置信度构成」行，透出 `数据完整性 × 盈利质量分(/60) × 多因子校准层 → 折减项（覆盖度/分歧度与封顶档位）→ 可用方法清单 → 综合分档`；**生成器只拼接引擎已有数值，不重算乘积、不产生新数字** | `confidence` 块全字段 |
| 行业串含通用分类后缀（如「制造业」）致 Layer 2 误命中泛化别名（v3.16.6） | 匹配按**最长命中别名优先**（不再首个命中即赢）；别名表同步收紧（`机械制造` 删「制造」、`消费` 补「白酒/酿酒/酒类」）。若仍误判，检视 `matched_industry` 与 `meta.industry` 是否含更长的具体行业词 | `industry_params.matched_industry` |
| 行业串**罗列多业务**致次要业务别名抢占主业（v3.16.6 / industry_params 1.0.2） | 典型：比亚迪「新能源汽车（…储能、光伏）」被电力设备别名「储能/光伏」抢占。处置：**补该行业类目并以更长主业别名夺回**（汽车类 alias 用「新能源汽车/汽车制造/整车」）；底座缺项时先判断是「回落 default」还是「被他行业抢占」，后者须查 `meta.industry` 串中的他行业业务词 | `industry_params.matched_industry` |
| `growth_forecast` 年数 > 阶段 n | 全部保留（n = max(阶段 n, 用户年数)），不截断 | `growth_schedule.n_user` |
| 五开关混用 | 相互独立；`path_weight_mode=adaptive` 需 `lifecycle_mode=auto` 才能取到非成长阶段（否则按成长基线 k=1，数值等于 legacy） | `synthesis.path_weights` |
| Layer 0 与 `path_weight_mode=adaptive` 同时开启（v3.16.2） | **先 B4（base×k_lifecycle×k_admissible，base=用户 `preferences.weights`）→ 再按 `dcf_weight_cap` 封顶并重分配**；`conditional` 档封顶不再被 B4 重算覆盖 | `synthesis.path_weights` + warning |
| Layer 0 与 `asset_type` 就 DCF 适用性结论相反（v3.16.2） | 以 **Layer 0 前提检验**为准（现金流可定义性优先于资产类型标签），留痕 warning；`layer0_check=false` 时沿用 `asset_type` 适配器 | warning + `framework_check.dcf_admissible` |
| Layer 0 前提 A4 营收序列 <3 年（v3.16.2） | 一般行业由 full 降为 `conditional`（`dcf_weight_cap` 封顶 0.3）；建议补齐 3 年财务序列 | `framework_check.precondition_A.evidence.A4_数据完备` |
| 输入未提供 `lifecycle_mode` 键（历史输入） | 引擎按 `legacy` 执行（5 年线性插值）；**新案例的模板/流程已默认写入 `auto`**，故正常新案走生命周期判别 | 仅 `auto` 时挂 `lifecycle` 块 |
