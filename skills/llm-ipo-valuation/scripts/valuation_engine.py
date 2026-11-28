#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
valuation_engine.py — IPO 智能估值引擎 v2.22.0（可复算）

方法论出处：国金证券《基于大语言模型的上市公司智能估值模型构建》（李双宏、杨利国、王洪涛）
v2.22.0 修订（2026-10-29，技能 v3.24.0，**单输出多候选：未选中的口径不产数值**）：
  * ★根因：`run()` 此前**无条件**调用 `fcf_ratio_analysis()`。当 FCFF 口径已由更高优先级的
    路径确定（① `dcf_drivers` 三表联立 / ② `fcff_mode` 报表级 / ③ `p0_value_driver`）时，
    该比率**没有任何消费方**，却照样完整算一遍并作为 `out["fcf_ratio"]` 挂出。格力 R3 实测：
    比率真值 1.541 被 `min(1.5, …)` **静默截断**成 1.50，既非真值、也非被采用的口径，却进了
    报告并被误归因为「P0 披露档」。任何「算了但没用」的数字，最终一定会被引用一次。
  * F1 `dcf_cost.fcf_ratio_lazy`（缺省 false＝legacy 逐位不变）：改用 `_get_fcfr()` **惰性求值**
    —— 只有真正走到 ④ 比率档（或 ③ 的降级分支）才计算；报表族口径下输出
    `{enabled:false, skipped:true, switched_to, reason}`（**字段存在、语义是「未计算」**），
    `assumptions_summary.dcf.fcf_ratio` 置 `None` + `fcf_source="未计算：FCFF 口径=…"`，
    报告层不再打出一个暗示「主口径用了比率法」的假数。`preferences.diagnostics_fcf_ratio=true`
    可强制求值（阶梯对照需要「若走比率法会差多少」），标 `role="diagnostic_only"`。
    副产品：④ 档原在 `_fcf_ratio` 为 None 时退回裸 `ocf_to_net_profit`，使三层校准在最需要它的
    档位静默降级——惰性求值后该档一定拿到三层校准值（惰性只改「算不算」，不改「算出来是多少」）。
  * F1b `dcf_valuation()` 的 `_fcff_base()` 由**无条件预计算**改为「未命中 ① 时才算」——
    命中三表联立时其结果本就被整段丢弃（同一反模式）。
  * F2 比率 clamp 留痕：上界 `min(1.5, raw)` 原为静默截断，现输出 `clamped_from` / `clamp_bound`
    并挂 warning（指向「OCF 含非经营性流入」这一典型成因）。
  * F3 `fcff_suggest` 增第二触发面 **OCF 质量**（`FCFF_SUGGEST_OCF_RATIO=1.30`）：原雷达只看
    `capex/营收 > 8%`，对「轻资产 + OCF 被并表财务公司吸收存款污染」的标的完全沉默——格力
    capex/营收仅 1.01%（不告警）而 OCF/净利 1.60（比率法实测与报表级差 −30.55%）。输出
    `fcff_suggestion.trigger ∈ {capex_intensity, ocf_quality}`；报表驱动已生效时不重复建议。
  * 零回归：`fcf_ratio_lazy` 缺省时输出与 v2.21.1 **逐位相同**（比率块不得新增 skipped/role/
    switched_to 键）；守护＝冒烟 **T140–T145 共 6 例**（跳过声明 / 比率档仍算准 / 诊断索取 /
    零回归 / clamp 留痕与边界 / OCF 质量四态触发），**156 用例全绿**。
v2.14.6 修复（2026-10-07，技能 v3.16.17，Layer 0 关键词的**中文同形异义词**误命中）：
  * framework_admissibility() 的 reit_utility 关键词组含裸 "高速"，原意是「高速公路」收费权类
    重资产标的；但「高速」在电子/通信语境意为 high-speed（高频高速覆铜板 / 高速接口 / SerDes）。
    生益科技（600183.SH）第 29 例暴露：meta.industry 写「全球刚性覆铜板第二大厂商（高频高速
    覆铜板 / 粘结片 / 印制线路板）」→ `"高速" in hay` 命中 → 误判 reit_utility
    （`dcf_weight_cap = 0.3`、`recommended_primary = "nav"`），而该公司为一般制造业、
    与收费公路毫无关系；误路由**静默发生、引擎不报警**（同「石油/资源」误路由族）。
  * 修复口径：`"高速"` → `"高速公路"`。★零回归保证：hay 仅由 `meta.industry` +
    `framework_check.industry_class` 构成；对全部既有输入（18 个案例 + examples 11 例）
    静态扫描确认**无一例的该两字段含「高速」**（其余出现均为 `note` 字段，不参与 hay），
    故输出必然逐位不变——已由 `docs/_ab_engine_v2146.py` 实跑 A/B 复核（29 例全部 IDENTICAL）。
    含「高速公路」的真实收费公路标的仍照旧命中 reit_utility。
  * ★通用教训：**单字/单词级关键词在中文里极易被同形异义词误命中**，凡关键词组中出现
    可跨行业复用的词（高速 / 资源 / 生物 / 公用 / 电力），须问一次「该词在本行业外的
    常见语境是什么」。残余风险（本轮未改，留痕备查）：resource 的裸 "资源" 会误命中
    「人力资源服务」；pipeline_pharma 的裸 "生物" 会误命中「生物质能/生物农药」。
v2.14.5 修复（2026-10-07，技能 v3.16.16，净现金下限的有限责任约束）：
  * dcf_valuation() 的 `if equity < 0: equity = net_cash_in` 在 net_cash 为**负**（净负债）
    时返回负的权益价值。万华化学（600309.SH）第 27 例暴露：bear 情景 PV(经营) 586 亿 <
    净负债 937.67 亿 → 原实现返回 −937.67 亿作为「DCF 内在价值」，把 Bear 下界从
    （应为 0 下限口径的）982.07 亿人为压到 702.64 亿、情景区间由 4.25× 虚增至 5.94×。
    中国石化（600028.SH）第 12 例同缺陷：bear 返回 −3,803.61 亿。
  * 修复口径：`floor = max(0.0, net_cash_in)` —— 净现金为正时仍为净现金下限（**历史行为
    逐位不变**：全案例族扫描确认仅上述 2 例的 bear 情景命中该分支），净现金为负时取 0
    （股东有限责任）。
v2.14.4 修复（2026-10-02，技能 v3.16.7，显式 null 全链路防御补全）：
  * v2.14.3 只修了 ipo_check() 一处；同一缺陷族仍在 10 处存在——`fin.get(key, 0.0)` 在
    键存在且值为 None 时返回 None 并进入算术语义。中国平安案例（综合金融，模板字段几乎
    全部显式 null）在 dcf_valuation() 的 `equity = pv_sum + tv_pv + self.fin.get("net_cash", 0.0)`
    处抛 TypeError 崩溃。本次统一改用新增的 `_nn(v, d)` 助手（仅 None 回落默认值，其余原值
    原类型返回 → 非 null 输入逐位零变化，含 `0` vs `0.0` 的序列化亦不变）：
      · _g1() 的 cagr_3y 兜底（growth_forecast 缺失且 cagr_3y=null）
      · _forward() 的 revenue_latest_ttm
      · transaction_valuation() 的 revenue_latest_ttm / ebitda_ttm
      · industry_index_valuation() 的 revenue_latest_ttm
      · comparable_valuation() 的 net_cash
      · dcf_valuation() 的 net_cash（崩溃点，两处）
      · sensitivity() 的 net_margin / revenue_latest_ttm
      · fundraising 增量校验的 net_cash
  非 null 输入逐位不变（数值型 0 与默认 0.0 等价；键缺失时行为同前）。
v2.14.3 修复（2026-10-01，技能 v3.16.6，显式 null 防御）：
  * ipo_check() 中 shares/issue/np_ttm 原用 dict.get(key, 0.0) 取默认值——当输入**显式写 null**
    （键存在、值为 None）时默认值不生效，issue*price 抛 TypeError（长江电力案例：
    "issue_shares": null 使引擎崩溃）。改为 `get(key) or 0.0`（None/0 一律回落 0.0）。
    未提供该键的旧输入逐位不变（0.0 与默认 0.0 等价）。
v2.14.2 修复（2026-10-01，技能 v3.16.6，WACC 来源标注）：
  * assumptions_summary.dcf.wacc_source 原「只要 wacc_params.enabled 就标 CAPM 模型」，
    但引擎恒为「显式 wacc 优先、CAPM 作校验」→ 报告出现「WACC 8.5%（CAPM 模型）」
    与风险提示「CAPM 模型值 5.96%（偏差 +2.54pp）」自相矛盾（比亚迪案例）。
    改为：显式 wacc 与 CAPM 并存时标「显式给定（CAPM 校验偏差 ±X pp）」；
    仅 CAPM 时标「CAPM 模型」。仅改标注文本，数值逐位不变。
v2.14.1 修复（2026-10-01，技能 v3.16.6，Layer 2 行业匹配）：
  * 行业参数匹配由「首个命中别名即赢」改为「最长命中别名优先」：泛化别名会抢占具体行业——
    「酒、饮料和精制茶制造业」被「机械制造」的别名「制造」命中、「电力设备」被「设备」命中。
    贵州茅台/五粮液案例 matched_industry 均误判为「机械制造」。改为按最长别名打分后，
    Moutai→消费、电力设备→电力设备，命中恢复正确；同时收紧 / 扩充别名表（见 industry_params.json 1.0.1）。
v2.14.0 修复（2026-09-30，技能 v3.16.4，PEG 护栏）：
  * PEG 样本增速门槛：growth_pct < peg_min_growth_pct（缺省 5%）的样本剔除。近零正增速会使 PE/增速 虚高，
    单只此类可比即可污染中位数——五粮液案例中茅台 growth=1.3% → PEG 中位 14.86 → PEG 值放大至 3.19 万亿
    （约市值 12 倍），并因 PEG 值 = 利润 × PEG中位 × (g1×100) 而把增速重复计入，量级爆炸。
  * PEG 中位数上限：median > peg_max_ratio（缺省 5.0）判定失真 → PEG 整法弃用（不做截断，避免注入错误数值）。
  * 开关 preferences.peg_guard（缺省 true）；置 false 即回到 v2.13.1 行为（旧输入逐位不变）。
  * 留痕：剔除样本进 peg.guard_excluded，整法弃用进 peg.dropped_by_guard + warning；全样本被剔除时
    挂出无 value 的诊断块（不参与 candidates / synthesis.peg_value）。
v2.13.1 修复（2026-09-30，技能 v3.16.2，三层计划设计矛盾清理）：
  * Layer 0 与 B4 权重仲裁：dcf 权重封顶改在 B4 权重重算之后施加（conditional 档封顶不再被覆盖）；
    B4 基准权重改用「用户/模板解析后的 self.weights」（原误用 DEFAULT_WEIGHTS 常量 → 丢弃 preferences.weights）
  * DCF 适用性判定统一：layer0_check=true 时以 Layer 0 前提检验为准（原与 asset_type 适配器结论可能相反），
    二者相反时留痕 warning
  * Layer 0 关键词收紧：裸 "电力" 不再误命中「电力设备/电力装备」（一般制造业）而判为 reit_utility
  * Layer 0 前提 A4 数据完备（营收序列 ≥3 年）参与判定：一般行业由 full 降为 conditional（封顶 0.3）
  * 早期阶段营收缩口阈值统一为常量 EARLY_STAGE_REVENUE_THRESHOLD（原管线药企 3 亿 / 初创 5 亿不一致）
  * Layer 1 终值方法/再投资模式随阶段留痕（terminal/rr_mode 进 growth_schedule，消除「定义未消费」）
v2.0 升级（依据《技能校验与完善报告》5 个代表性案例场景逐项校验）：
  * 盈利质量评分卡（论文「财报」维度量化落地）：OCF/净利·毛利率趋势·应收/营收·商誉比·非经常性损益
  * 情绪修正（v3.15.0 口径 B：与质量解耦，clamp(板块热度+个股舆情+情景因子, ±10%)；原"情绪-质量交叉验证"已移除）
  * 商誉折价概率化分级（论文「商誉」维度升级）：10/15/30% 分档，替代一刀切
  * 多因子校准层（对应国金「AI估值助手·Fama-French五因子」落地案例）：ff_factor_adjust + 环节估值中枢
  * 调整项明细输出（quality/goodwill/sentiment/ff 各自贡献，可审计）
  * 增量重估 diff（--compare 上一案例输出）：区间变化、假设变化、收敛/发散判定
  * 用户配置优先级：显式提供的修正值 > 引擎自动生成
v2.1.0 重构（2026-08-14，技能 v3.2）：
  * 权重归一化：preferences.weights / scenario_weights 三项和 ≠1 时归一化并 warning（默认行为不变）
  * 负增速支持：营收增速允许负值（原被 max(0.0,…) 静默抹平），加 warning 与 DCF 负值净现金下限兜底
  * 修正项提升：quality_score/goodwill_adjust/ff_calibration 在 run() 层计算一次，
    scenario() 接收预计算值（原单次 run 调 quality_score 7 次 → 1 次，数值等价）
  * 风格统一：sentiment 数据统一经 self.sent 访问
  * _data_completeness 简化；diff_report.assumption_changes 输出真实假设差异列表（替代 base_case_id 字符串）
v2.2.0 强化（2026-08-14，技能 v3.3）：
  * wacc_model：CAPM 分解（rf/ERP/β/债务成本/资本结构/税率，β 去杠杆再杠杆），显式 wacc 优先模型作校验
  * cashflow_statistics：历史营收/FCF/OCF 序列统计特征（均值/几何CAGR/标准差/CV/OLS趋势/R²），增速假设校验
  * growth_triangulation：自身历史 + 可比增速中位 + 行业增速 三角校准营收/永续增长率（用户显式优先）
  * comparable 指标扩展：PB/净利率/ROE/EV-Sales + PB 估值法 + comparable_metrics 指标汇总表
  * industry_index_valuation：行业指数隐含估值交叉验证（偏差>30% 提示，可比<3家降级基准）
  * sentiment_structured：舆情事件/政策聚合 → impact_map 假设层调整（与市场口径 sentiment_adjust 分层）
  * 全部新功能可选激活：缺省不改变 v2.1.0 输出（旧输入零变化）
v2.3.0 强化（2026-08-19，技能 v3.4）：
  * fcf_ratio_analysis：FCF 比率三层校准（L1 自身 OCF/净利−CapEx/净利｜L2 可比集中位｜L3 兜底），
    替代"净利×OCF/净利"近似；fcf_ratio<0.5 触发再投资敏感性提示
  * wacc_model β 降级链：beta > unlevered_beta > comparable_betas > industry_beta（新增兜底）；
    d_e_ratio 缺省取可比集中位（可比集一致性）
  * transaction_valuation：可比交易锚（一级市场融资/并购倍数，时间衰减），与行业指数并列输出
  * recent_financing_anchor：最近融资价格锚（简化版，时间衰减；完整 9 项排除检查 v3.5）
  * comparable_set_usage / comparables_shortfall 输出块：可比集一致运用与无可比替代路径显式化
v2.4.0 强化（2026-08-19，技能 v3.5，中证协四方法完整版 + 边界/校验/输出增强）：
  * recent_financing_anchor 完整版：9 项排除情形检查（RFP_EXCLUSION_DEFS，E1-E9），
    命中任一 → 融资价格法不适用并输出逐项命中表；缺省不提供 exclusions 时与 v2.3.0 逐键一致
  * repurchase_valuation：回购价格法（回购价×股数 与主估值孰高 + 回购实现概率加权，作锚/下限）
  * liquidity_discount：非上市股权流动性折扣模型化——看跌期权法 discount=2N(v√T/2)−1
    （Longstaff v√T 公式）｜经验 10-50%｜混合；只作用于市场法（可比乘数），DCF 不折，
    与 ipo_check.float_ratio 分层不叠加；旧输入缺省 0 → 综合值逐位不变
  * nav_valuation：净资产法（重资产/控股主方法候选；清算场景作估值下限提示）
  * comparable_valuation synthesis 增加 peg_value 单列展示（不参与权重，旧输入数值不变）
  * 输入校验增强（_check_input + _validate_input）/ 资产类型适配（asset_type 方法适用性判断）
  * 输出结构增强：assumptions_summary 关键假设汇总块 + liquidity_discount.basis/discount_value
v2.5.0 强化（2026-08-19，技能 v3.6，数据可靠性与参数计算增强）：
  * A1 WACC 公开参考值表（rf 10Y 国债/ERP Damodaran/行业β表，用户显式优先，缺省用参考）
  * A2 可比数据时点统一校验（as_of 混合日期 >30 天警示）｜A3 三表勾稽校验（净利×净利率/毛利>净利/净现比）
  * A4 数据时效引擎化（数据距基准日 >180 天警示，中证协第六条从严）
  * B3 三角校准 winsorize（可比增速 1%/99% 截尾防概念溢价）｜B2 现金流统计营收近似显式标注
  * C2 PEG 参与开关（enable_peg_in_synthesis 缺省 true 保持旧行为，false 仅单列）
v2.8.1 强化（2026-08-19，技能 v3.11.1）：
  * fcf_ratio_analysis 支持用户显式 financials.fcf_ratio（FCF/净利）优先，覆盖三层校准；
    缺省不激活 → 旧输入零变化（T17 断言保持）
v2.10.0 强化（2026-08-20，技能 v3.12，三步数据源优先级优化）：
  * 净利披露档（net_profit_basis）：annual > quarterly×4 > semiannual×2 > consensus(前向) >
    现行 rev×net_margin 兜底；normalized 仅 enable_normalized=true 时覆盖；_forward 分支化、
    A3 勾稽改校验披露隐含净利率；输出 net_profit_basis_used / dcf.profit_source
  * FCF 披露档（P0 最高优先）：fcf_ratio = (披露OCF − 披露CapEx) ÷ 披露净利 > 显式 fcf_ratio > 三层校准
  * 可比来源档位：comparables.source/priority 透传 + comparable_sources 块（S3.3 来源评分由 SKILL.md 执行）
  * 全部新增字段缺省不激活 → 旧输入零变化（T17/T29 保持）
v2.11.4 修复（2026-09-24，技能 v3.14.2，DCF 不适用时的置信度虚高）：
  * 现象：meta.asset_type=startup（DCF 不适用）且权重集中于市场法时，置信度仍报 100 分/「高」。
    根因：置信度因子只含 数据完整性 × 质量分 × 因子校准，缺「有效方法数」维度；
    同时 methods_available 无条件写入 "dcf"，与 asset_adapter.dcf_applicable=False 自相矛盾。
  * 修法：当 asset_adapter 判定 dcf_applicable=False 时——
    ① methods_available 剔除 "dcf"，新增 methods_inapplicable=["dcf"]；
    ② 置信度乘方法覆盖度因子 diversity = 0.5 + 0.5×(有效估值方法数/2)，并封顶 79.9 分（不得为「高」）；
    ③ confidence.method_coverage 留痕（有效方法数/因子/封顶档位）。
  * 另修 ipo_check 口径标注：原 price_per_share 为「估值中枢 ÷ 发行后总股本」的**模型隐含**
    发行价，对已上市公司易被误读为实际发行价；现增列 price_source 标注口径，并支持可选入参
    fundraising.issue_price_actual（+issue_pe_actual / issue_pb_actual / listing_date /
    actual_raise）——提供后 price_per_share 取实际价、保留 price_per_share_indicative，
    并输出 issue_mktcap_actual 与「实际发行市值 vs 模型中枢」偏离。缺省不提供 issue_price_actual
    时输出与旧版逐位一致（不新增任何键，T17 保持）。
  * 影响面：仅 asset_type=startup（或未来 dcf_applicable=False 的类型）输入；其余输入输出零变化
    （沈鼓/长鑫/宇树等 mature/growth 档不受影响）。
v2.11.3 修复（2026-09-24，技能 v3.14.2，评分卡 null 输入崩溃）：
  * quality_score() 中 5 项质量指标原用 fin.get(k, default) 取值，当输入 JSON 显式提供该键
    且值为 null（模板允许的「未披露」状态）时返回 None 并参与 >= 数值比较，抛
    TypeError: '>=' not supported between instances of 'NoneType' and 'int'，导致引擎整体
    崩溃（stat_validation 复用引擎亦随之失败）。现改为：None/非数值 → 该指标记 0 分并标记
    missing=True；非 None 路径逐位保持原判分逻辑。
  * 影响面：提供全部 5 项指标的输入输出零变化；仅「含 null 质量指标」的输入由崩溃转为可运行。
v2.11.2 修复（2026-09-18，技能 v3.14.1，FCF 披露档期间口径错配）：
  * P0 披露档原以 (披露OCF − 披露CapEx) ÷ 年化披露净利，分子为单期披露现金流、分母为年化净利，
    期间不一致导致 FCF/净利被系统性低估（半年度档 50%、单季度档 75%）；
  * 改为按净利披露档同因子年化分子，输出新增 annualization_factor 留痕；
  * 影响面：net_profit_basis 为 annual/consensus 或未提供 ocf_latest/capex_latest 的输入输出零变化；
    仅 semiannual×2/quarterly×4 + 披露现金流档的输入（长鑫科技 2026Q1 档）FCF 比率与 DCF 结果会上修。
v2.11.0 强化（2026-08-21，技能 v3.13.1，FCF 比率优先级重排）：
  * fcf_ratio 优先级链调整：披露档 P0 ＞ 三层校准（L1 自身 / L2 可比 / L3 兜底）＞ 用户显式；
    用户显式降为兜底（三层校准不可用、无任何 CapEx 数据时启用）
  * 用户显式被校准覆盖时留痕：explicit_value / explicit_overridden / explicit_deviation（审计可追溯）
  * 三层校准不可用回退显式时 source 仍为"用户显式"，note 标注"三层校准不可用"（下游 fcf_source 兼容）

用法：
  python valuation_engine.py <input.json> [-o <output.json>]
                 [--scenarios '{"bull":{"growth_adj_pp":15}}']
                 [--compare <prev_output.json>]     # 增量重估：输出 diff
纯标准库，Python 3.8+，无第三方依赖。

字段单位（与 assets/input_template.json 一致）：金额=亿元；比率=小数；股票=亿股。
"""

import argparse
import json
import math
import os
import statistics
import sys

# v3.9 D3：工具函数层拆分（engine_utils.py）——显式导入，外部 ve.xxx 引用仍兼容
from engine_utils import (_norm_cdf, _ols_slope_r2, _geo_mean_growth, _series_from_year_dict,
                          _months_between, _median, _mean, iqr_filter, _winsorize,
                          two_stage_dcf, discount_fcf_series, build_growth_seq,
                          build_growth_schedule, value_driver_fcf_series,
                          check_terminal_growth, growth_history_shape,
                          size_premium_cva, growth_base_from_history, margin_sigma_step,
                          capex_magnitude_check, statement_fcff_series,
                          space_state_growth_schedule, growth_shape_kappa,
                          plc_growth_path, plc_shape_e, PLC6_SHAPE_PARAMS,
                          PLC6_STAGE_ORDER, PLC6_SHAPE_LABELS,
                          GROWTH_MODEL_DEFAULTS)

DEFAULT_WACC = 0.11
DEFAULT_TERMINAL_GROWTH = 0.06
# v3.21.0 A2：永续增速缺省值双轨——legacy 保持 6%（零回归），cva_2pct 对齐 CVA 缺省与通胀锚。
# 6% 与同文件 TERMINAL_GROWTH_PUBLIC["gdp_cap"]=4.5% 自相矛盾（缺省值突破自己设定的 GDP 上限）。
TERMINAL_GROWTH_DEFAULT_MODES = {
    "legacy_6pct": DEFAULT_TERMINAL_GROWTH,
    "cva_2pct": 0.02,
}
# v3.21.0 A6：终值占比四档门禁（CVA 只要求「重点检查」不阻断 → 最高档 error 级告警 + 置信度封顶）
TV_SHARE_GRADES = [
    (0.40, "low", "warning", "终值占比过低，复核是否过度保守（现金流衰减/资本开支过高）"),
    (0.75, "in_range", None, "终值占比处于 40%–75% 区间（CVA 可解释区间）"),
    (0.85, "high", "warning", "终值依赖偏高，须披露永续增速敏感性"),
    (9.99, "extreme", "error", "终值占比 >85%，估值几乎完全由永续假设决定，须补永续增速依据"),
]
DEFAULT_WEIGHTS = {"dcf": 0.30, "comparable": 0.50, "sentiment": 0.20}
DEFAULT_SCENARIO_WEIGHTS = {"bear": 0.25, "base": 0.50, "bull": 0.25}


def _nn(v, d=0.0):
    """显式 null 防御（v2.14.4）：仅当取值为 None（键缺失或**显式写 null**）时回落默认值；
    其余原值、原类型返回。区别于 `v or d`——后者会把合法的 int 0 变成 float 0.0，
    造成 `0` vs `0.0` 的序列化差异；也区别于 `dict.get(k, d)`——后者在键存在且值为 None
    时返回 None 并进入算术语义（中国平安案例的崩溃根因）。"""
    return d if v is None else v
DEFAULT_GROWTH_WEIGHTS = {"self": 0.4, "comparable": 0.4, "industry": 0.2}
# v3.15.0：估值四部分拆分（preferences.four_part_mode）
# ① DCF(0.30) ｜ ② 可比法(含质量/商誉/因子/流动性, 0.50) ｜ ③ 市场舆情(仅情绪, 0.20) ｜ ④ 统计检验区间
# true（缺省）：③ 舆情独立加权，不再并入可比法；false：逐位回退旧合成（情绪并入可比法）→ 旧输入零变化
FOUR_PART_MODE_DEFAULT = True
SCENARIO_DEFAULTS = {
    "bear": {"growth_adj_pp": -10, "margin_adj_pp": -3, "multiple_factor": 0.80, "wacc_adj_pp": 1, "sentiment_factor": -0.05},
    "base": {"growth_adj_pp": 0, "margin_adj_pp": 0, "multiple_factor": 1.00, "wacc_adj_pp": 0, "sentiment_factor": 0.00},
    "bull": {"growth_adj_pp": 10, "margin_adj_pp": 3, "multiple_factor": 1.20, "wacc_adj_pp": -1, "sentiment_factor": 0.05},
}
QUALITY_SCORE_DEFAULT = 60.0

# v2.4.0：中证协《非上市公司股权估值指引》(2025修订) 第八条——最近融资价格法 9 项排除情形
RFP_EXCLUSION_DEFS = [
    {"code": "E1", "name": "新老投资权利义务不同",
     "desc": "新老投资者权利/义务存在重大差异（如优先清算、回购承诺不同）"},
    {"code": "E2", "name": "回报担保",
     "desc": "关联方或第三方为新投资人提供回报担保"},
    {"code": "E3", "name": "不成比例稀释",
     "desc": "本轮融资导致不成比例稀释"},
    {"code": "E4", "name": "价格明显低于公允",
     "desc": "强迫交易/救援措施/员工激励/显失公允关联交易等"},
    {"code": "E5", "name": "特定协同/非现金投入",
     "desc": "含特定协同效应或非现金资源投入"},
    {"code": "E6", "name": "轮次间隔短价格波动大/同业破发",
     "desc": "轮次间隔短但价格波动大或同业新股破发"},
    {"code": "E7", "name": "融资金额过低/发行对象有限",
     "desc": "融资金额过低或发行对象有限"},
    {"code": "E8", "name": "宏观政策市场重大变化",
     "desc": "宏观/政策/市场/整体估值水平发生重大变化"},
    {"code": "E9", "name": "企业自身重大事件",
     "desc": "主业变化/业绩偏离/欺诈诉讼/资不抵债/管理层变动/技术壁垒突破"},
]

# v2.4.0：资产类型适配规则（meta.asset_type → DCF 适用性与主方法建议）
ASSET_TYPE_RULES = {
    "startup": {"dcf_applicable": False, "primary_methods": ["ps", "recent_financing", "transactions"],
                "note": "初创/未盈利：DCF 不适用（无稳定现金流），以 PS/融资价格锚/交易锚为主；亏损自动禁 PE"},
    "growth": {"dcf_applicable": True, "primary_methods": ["ps", "peg", "dcf"],
               "note": "成长期：PS/PEG 与 DCF 并用；DCF 对增速与再投资假设敏感，须配套敏感性分析"},
    "mature": {"dcf_applicable": True, "primary_methods": ["pe", "ev_ebitda", "dcf"],
               "note": "成熟期：PE/EV-EBITDA 与 DCF 并用（中证协：DCF 适用成熟期/现金流稳定）"},
    "private": {"dcf_applicable": True, "primary_methods": ["dcf", "recent_financing", "transactions"],
                "note": "非上市公司：建议施加流动性折扣；以融资/交易锚交叉验证；可选用净资产法"},
}

# v2.5.0：WACC 公开参考值表（A1，数据来源公开可复算；用户显式参数优先，缺省用参考值）
# rf：中国 10 年期国债收益率（中债登/央行公开）；ERP：Damodaran 中国年度股权风险溢价（NYU 公开）
# industry_beta：Damodaran 行业无杠杆 β 表（取整近似）——仅作兜底，用户/可比 β 优先级更高
WACC_PUBLIC_REFERENCE = {
    "rf_default": 0.019,          # 2026 年中国 10Y 国债收益率约 1.9%（参考值，可 override）
    "erp_default": 0.055,         # Damodaran 中国 ERP 参考区间 5%-6%，取 5.5%
    "industry_beta": {            # 行业无杠杆 β（Damodaran 行业表，近似）
        "半导体": 1.20, "软件": 1.10, "AI": 1.25, "机器人": 1.30, "汽车零部件": 1.10,
        "机械制造": 1.05, "电力设备": 1.00, "医药": 0.95, "食品饮料": 0.80, "金融": 0.90,
        "default": 1.00,
    },
    "note": "公开参考值（rf 国债/ERP Damodaran/行业β），用户 wacc_params 显式参数优先；缺省 wacc_params.enabled=true 且不填 rf/erp/beta 时启用参考值",
}

# ============ v3.22.0：估值缺陷修复六项（全部 opt-in，缺省 = v3.21.0 行为 → 逐位零回归）============
# 背景：审计发现的六类「会让估值系统性偏离且不报错」的缺陷——
#   ① 缺省 WACC=11% 对当下中国市场偏高（rf 1.9% + β×ERP 应得 7~9%）→ capm_auto
#   ② p0_value_driver 声明但缺 ebit/roic 时静默回退比率法（承诺了没执行却不告知）→ error 模式
#   ③ comp_v = ... or 0.0 静默归零（可比法不可用时综合值缩水一半而不报错）→ renormalize
#   ④ 重资产高 CapEx 标的仍走「净利×比率」口径（漏扣资本开支）→ fcff_suggest
#   ⑤ 只开 cva_2pct 永续增速、不改 WACC 时终值倍数 21.2× → 11.3×（降 47%）→ require_explicit_wacc
#   ⑥ 终值占比 >85% 仍出单点估值（CVA comps 是直接 point_estimate=null）→ point_estimate_guard
ERP_DEFAULT_MODES = {
    "legacy_5p5": WACC_PUBLIC_REFERENCE["erp_default"],   # Damodaran 中国 ERP 5.5%
    "cva_8p04": 0.0804,                                    # CVA CCPFC2026 隐含 ERP（A 股统计模型法）
}
DCF_COST_DEFAULTS = {
    "wacc_default_mode": "legacy_11pct",   # legacy_11pct | capm_auto（rf + β×ERP + 债务成本动态构造）
    "erp_default_mode": "auto",            # auto（capm_auto→cva_8p04 / 否则 legacy_5p5）| legacy_5p5 | cva_8p04
    "cashflow_fallback_mode": "silent",    # silent | error（p0 声明但缺参时：静默回退 vs 显式留痕+降置信度）
    "method_drop_mode": "zero_silent",     # zero_silent | renormalize（comp_v 不可用时：归零 vs 剔除并按剩余权重再归一）
    "fcff_suggest": False,                 # 重资产（capex/营收 > 阈值）自动建议开启 fcff_mode
    "point_estimate_guard": False,         # A6 extreme 档（终值占比 >85%）禁出单点估值
    # v3.23.0（D1–D3/D5/D8/D9）：现金流模型细节层，全部 opt-in、缺省逐位零回归
    "discount_timing": "year_end",         # year_end | mid_year（年中折现）
    "size_premium_mode": "off",            # off | cva_deciles（CVA 2026 规模溢价查表，β 调整后加在 CAPM 上）
    "capex_check": False,                  # Capex/D&A 量级勾稽（拦「capex 异常偏低」的数据级错误）
    "capex_da_band": [0.5, 10.0],          # 合理带；白电约 1.5–3.5
    "margin_step_mode": "off",             # off | cva_sigma（利润率情景步长 = σ clamp[1,3]pp）
    "reinvestment_check": False,           # 期末再投资一致性自检（g 与 (Capex−D&A)/NOPAT 是否自洽）
    "normalization_hint": False,           # 非经常性损益/异常低税率提示开启正常化
    # v3.24.0（F1）：FCF 比率惰性求值——「单输出多候选：未选中路径不产数值」
    "fcf_ratio_lazy": False,               # false=预计算（legacy，逐位不变）| true=仅命中比率档才求值
}
FCFF_SUGGEST_CAPEX_RATIO = 0.08            # 资本开支/营收 阈值（>8% 视为重资产，比率法易失真）
# v3.24.0（F3）：比率法失真的**第二个**触发面——OCF 质量（原实现只看 capex 强度）
# 格力 capex/营收仅 1.01%（远低于 8%）→ 雷达完全沉默；但其 OCF/净利 1.60 含并表财务公司的
# 「吸收存款」，比率法同样失真（实测与报表级差 −30.55%）。轻资产 + OCF 污染是独立盲区。
FCFF_SUGGEST_OCF_RATIO = 1.30              # OCF/净利 阈值（>1.3 视为 OCF 含非经营性流入）
#: 终值倍数的两种缺省组合（用于修复⑤的量化告警文案，可复算）
_TV_MULTIPLE_LEGACY = round((1.0 + DEFAULT_TERMINAL_GROWTH) / (DEFAULT_WACC - DEFAULT_TERMINAL_GROWTH), 2)
_TV_MULTIPLE_CVA_TG_ONLY = round((1.0 + 0.02) / (DEFAULT_WACC - 0.02), 2)

# v3.11（修订 1a）：永续增速公开锚——公开市场数据估计（10Y 国债 + 长期通胀 为下限锚、长期名义 GDP 为上限约束）
TERMINAL_GROWTH_PUBLIC = {
    "rf_anchor": WACC_PUBLIC_REFERENCE["rf_default"] + 0.02,  # 10Y 国债 1.9% + 长期通胀 2% ≈ 3.9%（合理中枢/下限）
    "gdp_cap": 0.045,          # 中国长期名义 GDP 增速约束（永续增速上限锚）
    "inflation": 0.02,
    "note": "永续增速公开锚（v3.11）：行业长期增速受 GDP 上限约束（min(行业长期, 4.5%)），以 10Y 国债+通胀 3.9% 为下限保底；clamp [2%,10%]",
}

# v2.5.0：输入校验阈值（A2/A3/A4）
CHECK_AS_OF_MAX_SPREAD_DAYS = 30     # 可比数据时点最大允许差（天）
CHECK_DATA_STALENESS_DAYS = 180      # 数据距基准日最大时效（中证协第六条：原则上不超过 1 年，从严 180 天）
CHECK_GROSS_MARGIN_ABOVE_NET = True  # 毛利率应高于净利率
CHECK_NETPROFIT_TOLERANCE = 0.30     # 净利率×营收 vs 净利 偏差容差（30%）
# v2.11.5：置信度·方法分歧度阈值（市场口径 vs DCF 内在价值的 CV 上限；超此值封顶「中」）
CONFIDENCE_METHOD_CV_CAP = 0.60
# v3.16.2：早期阶段营收规模阈值——统一「Layer 0 管线药企推断」与「Layer 1 初创判别」口径
# （原分别用 3 亿/5 亿，同一「早小」概念两套阈值 → 已收敛为单一常量）
EARLY_STAGE_REVENUE_THRESHOLD = 5.0

# ============ v3.16.0：三层计划（Layer 0 判别门 / Layer 2 参数底座 / Layer 1 现金流主计算）============
# 【Layer 1】生命周期四阶段默认配置——显式期长度 n / 增速形态 form / 终值方法 / 再投资模式
# ★v3.27.0 显式期重标定为 **10 / 8 / 6 / 4**（原 10 / 6 / 4或7 / 5），修复两处结构性缺陷：
#   ① **阶段间倒挂**：v3.21.0 B3 为压终值占比把 mature 单独抬到 7，而 growth 仍为 6，
#      形成「成长期显式期(6) < 成熟期显式期(7)」——越确定的公司要求预测得越远，
#      与「成长期超额增长窗口更长、成熟期信息优势衰减更快」的经济含义相反；
#   ② **n 与 CAP 脱钩**：`growth_model.cap_life_years` 只决定 κ（收敛形状），不决定长度，
#      故出现「CAP=8 年、路径第 6 年精确落到 tg」的自我矛盾（美的集团实证）。
#   单调性硬约束（须恒成立）：n_startup ≥ n_growth > n_mature ≥ n_decline → 10 > 8 > 6 > 4。
#   growth 8 年 ≈ 2.67 个半衰期（half_life 3.0 → 残余 15.7%），与缺省 CAP 8~10 年同阶。
#   mature 6 年（非 7）：去掉 B3 为凑「终值占比 60–70%」而增加的展示性年数——终值占比对
#   成熟企业本就该高（稳态现金流），用 n 凑占比是拿展示指标倒推模型结构。
LIFECYCLE_DEFAULTS = {
    "startup": {"n": 10, "form": "s_curve", "t_mid": 4.0, "terminal": "exit_multiple", "rr_mode": "growth",
                "note": "初创期：S 曲线渗透，显式期 10 年；禁用 Gordon 终值（终值占比易 >100%），走退出倍数/概率加权"},
    "growth": {"n": 8, "form": "exp", "half_life": 3.0, "terminal": "three_method", "rr_mode": "growth",
               "note": "成长期：指数 fade（高增长半衰期 half_life），显式期 8 年；终值 Gordon/退出倍数/价值驱动三法取区间"},
    "mature": {"n": 6, "form": "mean_revert", "rho": 0.30, "terminal": "gordon", "rr_mode": "growth",
               "note": "成熟期：均值回归快速收敛，显式期 6 年；Gordon 终值可靠"},
    "decline": {"n": 4, "form": "decline", "lam": 0.30, "g_perm": -0.05, "tg_floor": 0.0,
                "terminal": "zero_growth_or_nav", "rr_mode": "shrink",
                "note": "衰退期：衰退收敛（g0<0），显式期 4 年（一个产能/库存周期）；零增长/清算 NAV 终值，RR 转负（回收资本）"},
}
# v3.27.0：显式期单调性硬约束——导入期即校验，防止后续再出现「阶段间倒挂」。
# 判据：n_startup ≥ n_growth > n_mature ≥ n_decline。违反直接抛错，不允许静默出表。
_LIFE_N = {k: int((v or {}).get("n", 0)) for k, v in LIFECYCLE_DEFAULTS.items()}
assert (_LIFE_N["startup"] >= _LIFE_N["growth"] > _LIFE_N["mature"] >= _LIFE_N["decline"]), (
    "生命周期显式期倒挂：须满足 startup ≥ growth > mature ≥ decline，实测 "
    f"{_LIFE_N['startup']}/{_LIFE_N['growth']}/{_LIFE_N['mature']}/{_LIFE_N['decline']}"
)
# 【Layer 1 + B4】生命周期对三路径权重的调节因子 k_lifecycle（乘在 base 权重上，随后归一化）
LIFECYCLE_WEIGHT_FACTORS = {
    "startup": {"dcf": 0.5, "comparable": 0.7, "sentiment": 1.5},
    "growth":  {"dcf": 1.0, "comparable": 1.0, "sentiment": 1.0},
    "mature":  {"dcf": 1.3, "comparable": 1.0, "sentiment": 0.7},
    "decline": {"dcf": 1.2, "comparable": 0.8, "sentiment": 0.6},
}
LIFECYCLE_STAGE_LABELS = {"startup": "初创期", "growth": "成长期", "mature": "成熟期", "decline": "衰退期"}
# ============ v3.28.0：达莫达兰六阶段「方法定位表」——替代 k_lifecycle 乘数 ============
# 【为什么替换】k_lifecycle 的语义是「某阶段某方法重要多少倍」（12 个无出处系数），
# 达莫达兰企业生命周期框架的语义是「某阶段该用哪个工具」——是**方法定位**，不是重要性折算。
# 用乘数表达「选工具」属方向错位：既拿不到真正的工具替换（rNPV/SOTP/NAV 未进三路候选），
# 系数又只能凭经验拍定；且乘数必须「乘 base → 再归一化」两步才能看到结果，不可直接审计。
# 本表把 k 显式化为「阶段 → 三路径直接权重」，行内和为 1、不再乘 base、不再归一化，
# 每格可回溯到达莫达兰对该阶段估值工具的表述（DAMODARAN_STAGE_EVIDENCE）。
# ★与 LIFECYCLE_WEIGHT_FACTORS 并存：缺省仍走 multiplier_k（零回归），本表须显式开启。
DAMODARAN_HIGH_GROWTH_CAGR = 0.15
# 上值依据：达莫达兰把 Mature Growth 描述为「growth slows to low-double or high-single digits」，
# 故 ≥15% 仍归高速成长、8%–15% 归成熟成长。这是对原文区间的解读值，非原文数字。
# v3.29.1：Stage 2「年轻成长」的增速下限——低于此值仍判 young_growth 时须挂 warning。
# 取 8% 与 v326 的 growth 线同源，避免同一概念两把尺（记忆：判据索引「生命周期」条）。
DAMODARAN_STAGE2_MIN_CAGR = 0.08
DAMODARAN_STAGES = ("startup", "young_growth", "high_growth", "mature_growth", "mature_stable", "decline")
DAMODARAN_STAGE_LABELS = {
    "startup": "1 初创期", "young_growth": "2 年轻成长", "high_growth": "3 高速成长",
    "mature_growth": "4 成熟成长", "mature_stable": "5 成熟稳定", "decline": "6 衰退期",
}
# 行内和为 1 的**直接权重**（不是乘数）。四条单调性约束见下方断言。
DAMODARAN_STAGE_WEIGHTS = {
    "startup":       {"dcf": 0.25, "comparable": 0.55, "sentiment": 0.20},
    "young_growth":  {"dcf": 0.30, "comparable": 0.50, "sentiment": 0.20},
    "high_growth":   {"dcf": 0.30, "comparable": 0.50, "sentiment": 0.20},
    "mature_growth": {"dcf": 0.35, "comparable": 0.50, "sentiment": 0.15},
    "mature_stable": {"dcf": 0.40, "comparable": 0.50, "sentiment": 0.10},
    "decline":       {"dcf": 0.45, "comparable": 0.45, "sentiment": 0.10},
}
DAMODARAN_STAGE_EVIDENCE = {
    "startup": {"tools": "期权定价 / VC 法（含生存概率）；P/E 无意义、P/S 被过小分母扭曲",
                "why": "价值几乎全在增长期权，现有资产现金流为负。引擎以 s_curve+退出倍数终值近似 VC 法，"
                       "但缺生存概率调整 → DCF 降为辅助；EV/Sales 是唯一可用倍数 → 可比法为主",
                "src": "Damodaran《The Corporate Life Cycle》(2019) 阶段—工具表；2024 年成书"},
    "young_growth": {"tools": "情景 DCF + 生存概率；EV/Sales、EV/User",
                     "why": "有收入但仍亏损、再投资强度最大。引擎无生存概率模块，情景 DCF 的信度不足以加权，"
                            "故三路维持 base 定位（不作人为倾斜）",
                     "src": "同上"},
    "high_growth": {"tools": "两阶段 DCF（增长 + fade）；终值易吞掉估值",
                    "why": "两阶段 DCF 是该阶段的标准工具 → DCF 为主；" 
                           "达莫达兰对「终值吞掉估值」的处置是加约束而非降权，故权重仍为 base 30/50/20，"
                           "由 tv_share_guard 承担该风险",
                    "src": "同上"},
    "mature_growth": {"tools": "标准 DCF + 交易倍数（并列）",
                      "why": "增速回落到 high-single 至 low-double，现金流可预测性上升 → DCF 略升；"
                             "倍数仍是一等交叉验证工具 → 可比法持平；舆情信息量下降",
                      "src": "同上"},
    "mature_stable": {"tools": "DCF / 分红折现（DDM）+ 倍数",
                      "why": "稳态现金流使 Gordon 终值最可靠 → DCF 升至 40%；"
                             "成熟公司的事件冲击多为一次性，舆情对内在价值无增量信息 → 降至 10%",
                      "src": "同上"},
    "decline": {"tools": "清算价值 vs 持续经营价值（二者须并列）",
                "why": "关键是「卖资产值多少 vs 继续经营值多少」。引擎 decline 档已走 zero_growth_or_nav，"
                       "DCF 内涵清算对照 → 权重最高；可比法在衰退期最危险（同行倍数同向反映衰退 → 循环论证）"
                       "→ 降至 45%；舆情多为重组/退市传闻噪音 → 10%",
                "src": "同上"},
}
# 结构断言（v3.28.0）：① 行内和为 1；② DCF 权重随阶段单调不减；③ 可比与舆情单调不增。
# 理由同 v3.27.0 显式期：这类「按类别分别定值」的参数，单点改动不会报错，只会静默造出反直觉配置。
for _s in DAMODARAN_STAGES:
    _w = DAMODARAN_STAGE_WEIGHTS[_s]
    assert abs(sum(_w.values()) - 1.0) < 1e-9, f"达莫达兰权重表行内和须为 1：{_s}={sum(_w.values())}"
_seq_dcf = [DAMODARAN_STAGE_WEIGHTS[s]["dcf"] for s in DAMODARAN_STAGES]
_seq_cmp = [DAMODARAN_STAGE_WEIGHTS[s]["comparable"] for s in DAMODARAN_STAGES]
_seq_sen = [DAMODARAN_STAGE_WEIGHTS[s]["sentiment"] for s in DAMODARAN_STAGES]
assert all(_seq_dcf[i] <= _seq_dcf[i + 1] + 1e-9 for i in range(len(_seq_dcf) - 1)), \
    f"达莫达兰权重表 DCF 须随阶段单调不减：{_seq_dcf}"
assert all(_seq_cmp[i] >= _seq_cmp[i + 1] - 1e-9 for i in range(len(_seq_cmp) - 1)), \
    f"达莫达兰权重表 可比法须随阶段单调不增：{_seq_cmp}"
assert all(_seq_sen[i] >= _seq_sen[i + 1] - 1e-9 for i in range(len(_seq_sen) - 1)), \
    f"达莫达兰权重表 舆情须随阶段单调不增：{_seq_sen}"
# v3.26.0：收缩/衰退的第二维子类（不新增顶层阶段，只作 mature 的子标记）
# 理由：LIFECYCLE_DEFAULTS["decline"] 的配置破坏力太大（n=5、tg 压至 ≤0、terminal=zero_growth_or_nav、
# rr_mode=shrink），若把「ROIC 仍高于 WACC」的公司判进去，等于用清算口径对待仍在创造超额回报的现金流机器。
LIFECYCLE_SUB_LABELS = {
    "cyclical_shrink": "周期性收缩", "structural_decline": "结构性衰退",
    "mild_shrink": "低个位数收缩", "ambiguous_shrink": "收缩待定（须 LLM 判成因）",
    "high_growth": "高增长", "steady": "稳态", "early_loss": "亏损起步", "unknown": "证据不足",
}
# 【Layer 0】前提检验路由表：industry_class → (dcf_admissible, recommended_primary, dcf_weight_cap)
FRAMEWORK_ROUTES = {
    "financial": {"dcf_admissible": False, "recommended_primary": "rim/ddm", "dcf_weight_cap": 0.0,
                  "reason": "金融业：债务为经营原料，FCFF 不可定义、资本结构≈经营要素（前提 A1/B1/B3 失败）"},
    "resource": {"dcf_admissible": False, "recommended_primary": "nav", "dcf_weight_cap": 0.0,
                 "reason": "资源类：储量耗尽、价格外生，逐项目 NAV 分块优于公司级 FCFF"},
    "reit_utility": {"dcf_admissible": "conditional", "recommended_primary": "nav", "dcf_weight_cap": 0.3,
                     "reason": "REITs/公用/重资产：监管定价、重资产，NAV 为主、DCF 为辅"},
    "pipeline_pharma": {"dcf_admissible": "conditional", "recommended_primary": "rnpv", "dcf_weight_cap": 0.2,
                        "reason": "管线型药企：现金流二元不可预测，rNPV 风险调整"},
    "holdco": {"dcf_admissible": "conditional", "recommended_primary": "sotp", "dcf_weight_cap": 0.3,
               "reason": "多分部异质集团：分部加总 SOTP"},
    "negative_fcff": {"dcf_admissible": "conditional", "recommended_primary": "prob_weighted_dcf", "dcf_weight_cap": 0.3,
                      "reason": "负 FCFF 占比 >60%：以情景概率加权替代确定性现金流"},
    "general": {"dcf_admissible": True, "recommended_primary": "dcf", "dcf_weight_cap": 1.0,
                "reason": "前提成立：FCFF 可定义且资本结构≈融资选择，DCF 准入"},
}
# ============ v3.17.0：全市场估值框架修订（P1 权重键集泛化 / P2 舆情降修正层 / P4 舆情带宽分化）============
# 【P1】动态候选方法集：路由声明的候选方法 → 是否可进入综合权重。
# 设计口径：`method_set_mode="routed"` 时，候选集由 framework_check 路由输出（含替代主方法）动态构造，
# 替代方法（nav/rim/ddm/rnpv/sotp）**可携带权重进入综合**，打破原「三路写死」——原实现只允许
# dcf_weight_cap 做减法、无机制做加法，致 NAV/融资锚等实现后仍以「不并入综合权重」身份空转。
METHOD_SET_MODE_DEFAULT = "legacy"          # legacy（三路，旧输入逐位不变）| routed（动态候选集）
# 替代方法的可靠度基准（R_i 的「方法成熟度」因子；假设主导度越高越降权）
METHOD_MATURITY = {
    "dcf": 1.00, "rim": 1.00, "ddm": 0.95, "comparable": 0.90,
    "nav": 0.85, "sotp": 0.80, "rnpv": 0.60, "sentiment": 0.90,
}
# 【P6 权重包络校验】可计算方法白名单：只有列在此处的方法，scenario() 才有对应的取值分支。
# ★根因：resolve_method_set() 曾把 rnpv/sotp 写进 weights，但 scenario() 综合式只读 comparable/dcf 两键，
#   导致 rnpv/sotp 的权重「凭空蒸发」（价值被少算），是比「空转」更严重的**静默错算**。
#   本闸门：候选集中出现白名单外方法时，其权重降为 0 并按比例回流，同时写 warning（诚实退化）。
COMPUTABLE_METHODS = {"dcf", "comparable", "sentiment", "rim", "ddm", "nav", "rnpv", "sotp"}
# 权重回流的目标方法优先级（回流给「第一个可计算」的方法；comparable 恒为兜底）
WEIGHT_RECYCLE_PRIORITY = ("comparable", "dcf", "nav", "rim", "ddm", "sentiment")
# 路由 → 候选方法集的权重骨架（仅 method_set_mode="routed" 且该路由命中时启用；未命中回退 base 权重）
ROUTE_METHOD_WEIGHTS = {
    # 一般经营：DCF 与可比法双主
    "general": {"dcf": 0.40, "comparable": 0.60},
    # 金融：RIM/DDM 主 + PB（可比法口径）
    "financial": {"rim": 0.55, "comparable": 0.45},
    # 资源/重资产：NAV 主 + 可比
    "resource": {"nav": 0.60, "comparable": 0.40},
    "reit_utility": {"nav": 0.50, "dcf": 0.30, "comparable": 0.20},
    # 管线药企：rNPV 主 + 可比
    "pipeline_pharma": {"rnpv": 0.60, "comparable": 0.40},
    # 多分部：SOTP 主 + 可比
    "holdco": {"sotp": 0.60, "comparable": 0.40},
    # 负 FCFF：概率加权 DCF（用 dcf 键承载）+ 可比
    "negative_fcff": {"dcf": 0.50, "comparable": 0.50},
}
# 【P2】舆情口径：path（独立路径，v3.15.0 四部分口径）| correction（修正层，作用于可比法）
SENTIMENT_LAYER_DEFAULT = "path"
# 【P4】舆情修正带宽按企业类型分化（替代固定 ±10%）
SENTIMENT_BAND = {
    "startup": 0.15, "growth_tech": 0.15, "growth": 0.10,
    "mature": 0.05, "financial": 0.05, "cyclical": 0.08,
    "decline": 0.05, "private": 0.00, "default": 0.10,
}
# 生命周期阶段 → 舆情带宽键
LIFECYCLE_TO_BAND = {"startup": "startup", "growth": "growth", "mature": "mature", "decline": "decline"}

# ============ v3.18.0：舆情强度驱动估值调整（sentiment-adjusted valuation）============
# 背景：P2 修正层已把舆情降为「作用于可比法的乘性系数」，但幅度仍由「舆情值本身」上限
# clamp(±band) 决定 —— 存在**双重截断冗余**：sentiment_adjust() 已 clamp ±10%，_sentiment_correction()
# 再 clamp ±band，导致内生信号强度 s_signal 的放大作用被吃掉（如 mature band=5%、sent=+10%、
# s_signal=1.3 → 13% → 又被截回 5%，等于没放大）。
# 本层口径：把「舆情方向」与「舆情强度」拆成两个正交因子——
#   方向 = sign(sent)（正/负）          强度 = k_signal（信号强度系数，≥0）
#   修正幅度 = band × k_signal_sign（k_signal_signed 保留方向），并允许在 band 之上按 K_MAX 有限放大。
# 【开关】sentiment_adjust_mode="strength" 时启用（缺省 "legacy" → 逐位零回归）
SENTIMENT_ADJUST_MODE_DEFAULT = "legacy"        # legacy（clamp(sent×k, ±band)）| strength（band×k_signal 口径）
# v3.26.0：生命周期判别口径（opt-in）
LIFECYCLE_CLF_MODE_DEFAULT = "legacy"     # legacy（输入 cagr_3y + 单维）| v326（cagr 反算 + 第二维）
LIFECYCLE_DIM2_MARGIN_PP = 0.01           # 第二维：净利率首末变动 ±1pp 视为噪声带
LIFECYCLE_MILD_SHRINK_CAGR = 0.05         # 低个位数收缩门槛：|CAGR| < 5% 且 ROIC>WACC → 不判衰退
# 【口径 C】修正幅度上限 = band × K_MAX（承认强信号可突破基础带宽，但设硬上限）
SIGNAL_K_MAX = 1.60          # 修正幅度上限倍数（band×1.60）
SENT_REFERENCE_BAND = 0.10   # 参照带宽：用于把 sent 强度归一化到 [0,1]（min(|sent|/0.10, 1.0)）
# 【信号强度矩阵】信号条数 n × 方向一致性 → k_signal 基础值
# 行：0（无信号）；1–2（少信号）；3–5（中量）；6+（大量）
# 列：consistent（方向一致）| conflict（方向冲突）；无信号单独一档
SIGNAL_STRENGTH_MATRIX = {
    "none":        {"base": 0.50},                                  # n == 0
    "few":         {"consistent": 0.70, "conflict": 0.60},           # 1 <= n <= 2
    "medium":      {"consistent": 1.00, "conflict": 0.70},           # 3 <= n <= 5
    "many":        {"consistent": 1.30, "conflict": 0.70},           # n >= 6
}
# 【强度加成】高重要性事件 / 权威政策源 / 时效衰减
SIGNAL_HIGH_MULT = 1.20        # 含 importance="high" 事件时 ×1.20（原实现硬编码 1.2）
SIGNAL_AUTHORITY_MULT = 1.15   # 政策源具备 authority=true 时 ×1.15（新增：权威出处加成）
SIGNAL_DECAY_START_DAYS = 30   # 事件后 N 天内不衰减
SIGNAL_DECAY_SPAN_DAYS = 90    # N 天之后，每 1 天线性衰减 1/90（下限 0）
# 【开关】权威加成 / 衰减口径是否启用（缺省 legacy 保持与 _sentiment_signal() 同值）
SIGNAL_AUTHORITY_MODE_DEFAULT = "legacy"   # legacy（不加成）| weighted（authority=true ×1.15）
SIGNAL_DECAY_MODE_DEFAULT = "legacy"       # legacy（1−(d−30)/90，同 _sentiment_signal）| stepped（分段）
# 【去相关折让】舆情强度与假设层 impact_map.multiple_factor 存在同源重叠：
#   事件驱动型影响（如政策利好 → 同时抬高 sentiment 与 multiple）会在 comp_v 与 (1+sent_corr) 上重复计费。
#   参照 B5 路径相关性先例，strength 口径下对舆情修正系数按 0.70 折让（仅当 impact_map 生效时）。
SENTIMENT_OVERLAP_DISCOUNT = 0.70

# ============ v3.19.0：路由主方法的引擎取值分支（P6-A 权重包络的 B/C 闭合）============
# 背景（承接 v3.18.0 P6-A）：权重包络闸门把「有权重但无取值分支」的方法权重回流（消除静默少算），
# 但 rnpv / sotp 仍是**空壳**——路由为管线药企/多分部主体声明了 0.60 权重，实际无对应计算。
# 本版补齐两者的**引擎取值分支**，使声明即计算：
#   B. rNPV（风险调整净现值）—— 管线药企（pipeline_pharma 路由）
#   C. SOTP（分部加总）—— 控股平台/多业务主体（holdco 路由）
# 全部 opt-in：enable_rnpv / enable_sotp 缺省 false → 旧输入逐位不变（零回归）。
# ---------------------------------------------------------------- rNPV 参数表（数据源：公开行业惯例，非精确统计）
# 各临床阶段 → 上市成功率 PoS（probability of success）。取自业界常用口径区间中值，
# 落在「可行（可覆盖输入）」而非「精确」位置；用户可经 rnpv.pos_overrides 逐管线覆盖。
RNPV_POS_TABLE = {
    "preclinical": 0.10,   # 临床前/发现期
    "phase1": 0.20,        # I 期
    "phase2": 0.35,        # II 期
    "phase3": 0.60,        # III 期
    "nda": 0.80,           # 注册申报（NDA/BLA）
    "approved": 1.00,      # 已上市（仅剩商业化风险）
}
# 阶段序（用于按「剩余里程碑数」累计成功率时判断后续阶段）
RNPV_PHASE_ORDER = ("preclinical", "phase1", "phase2", "phase3", "nda", "approved")
# 缺省折现率（风险调整后现金流用；医药行业底座若给 rnpv_discount 则优先）
RNPV_DISCOUNT_DEFAULT = 0.12
# 峰值销售达成形态：上市后逐年爬坡至峰值所需年数 + 爬坡后按专利悬崖衰减的年限/残值
RNPV_RAMP_YEARS = 4            # 上市→峰值约 4 年（S 型爬坡）
RNPV_TAIL_YEARS = 8            # 峰值后专利悬崖期（线性衰减窗口）
RNPV_TAIL_FLOOR = 0.10         # 悬崖后残值率（仿制药竞争后稳态）

# ---------------------------------------------------------------- SOTP 参数（分部加总）
# 口径：EV = Σ(分部价值_i × 持股比例_i) + 联营/金融资产 − 净债 − 控股折价
#   · 分部价值_i 由「分部法」给出：segment.metric × segment.multiple（可比倍数/行业倍数）
#     —— 「分部价值输入 + 加总」模式（segment-value-in-and-sum），不在引擎内重跑各分部 DCF，
#        以保持可审计（每个分部的价值口径由用户给出并留痕），与 NAV/成本法同族的「输入驱动」定位一致。
#   · 控股折价（conglomerate/holdco discount）：多业务主体的「复杂度折价」，作用于加总股权价值。
SOTP_HOLDCO_DISCOUNT_DEFAULT = 0.15    # 缺省控股折价 15%（业界常用 10%~20% 中值）
SOTP_HOLDCO_DISCOUNT_MAX = 0.40        # 硬上限（折价过高会遮蔽分部价值）
# 缺省控股折价按分部数递增（分部越多、异构度越高，折价越接近上沿）
SOTP_DISCOUNT_BY_SEGMENTS = {1: 0.0, 2: 0.05, 3: 0.10, 4: 0.15}   # 5+ → SOTP_HOLDCO_DISCOUNT_DEFAULT


# 【Layer 2】行业参数底座文件名
INDUSTRY_PARAMS_FILE = "industry_params.json"


def _load_industry_params():
    """读取 assets/industry_params.json（Layer 2 参数底座）；失败回退空 default。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", INDUSTRY_PARAMS_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"industries": {"default": {}}}


class Engine:
    def __init__(self, data, scenario_overrides=None):
        self.d = data
        self.fin = data.get("financials", {})
        self.comp = data.get("comparables", [])
        self.pref = data.get("preferences", {})
        self.sent = data.get("sentiment", {})
        self.idx = data.get("industry_index", {})
        self.warnings = []
        self.weights = self._normalize_weights(
            {**DEFAULT_WEIGHTS, **(self.pref.get("weights") or {})}, "preferences.weights")
        self.scen_w = self._normalize_weights(
            {**DEFAULT_SCENARIO_WEIGHTS, **(self.pref.get("scenario_weights") or {})}, "preferences.scenario_weights")
        self.exclude_outliers = bool(self.pref.get("exclude_outliers", True))
        # v3.15.0：估值四部分模式（缺省 true；false 回退旧合成 → 旧输入零变化）
        self.four_part_mode = bool(self.pref.get("four_part_mode", FOUR_PART_MODE_DEFAULT))
        # v3.16.0：三层计划开关（全部 opt-in，缺省 legacy → 旧输入零变化）
        self.layer0_check = bool(self.pref.get("layer0_check", False))          # Layer 0 前提判别
        self.lifecycle_mode = str(self.pref.get("lifecycle_mode", "legacy"))     # legacy | auto
        # v3.28.0：生命周期权重口径（opt-in，缺省 multiplier_k → 旧输入逐位不变）
        #   multiplier_k     ：w = normalize(base × k_lifecycle)（v3.16.0 起的行为，12 个无出处乘数）
        #   damodaran_table  ：w = DAMODARAN_STAGE_WEIGHTS[达莫达兰六阶段]（直接权重，行内和为 1，
        #                      **不乘 base、不归一化**；阶段由 damodaran_stage() 从 v326 四阶段派生）
        self.lifecycle_weight_mode = str(self.pref.get("lifecycle_weight_mode", "multiplier_k"))
        # v3.26.0：生命周期判别口径（opt-in，缺省 legacy → 旧输入逐位不变）
        #   legacy：只用输入里的 financials.cagr_3y（**从不自动计算**）+ 单维阈值（cagr<0 即 decline）
        #   v326  ：cagr_3y 可从 revenue_by_year 反算 + 第二维（净利率趋势 / ROIC−WACC）拆分
        #           cyclical_shrink（收缩但不衰退）与 structural_decline（真衰退）
        self.lifecycle_clf_mode = str(self.pref.get("lifecycle_classifier_mode",
                                                    LIFECYCLE_CLF_MODE_DEFAULT))  # legacy | v326
        self.cashflow_model = str(self.pref.get("cashflow_model", "p2_legacy"))  # p2_legacy | p1_fcff | p0_value_driver
        self.path_weight_mode = str(self.pref.get("path_weight_mode", "fixed"))  # fixed | adaptive
        # v3.17.0：全市场框架修订（全部 opt-in，缺省 legacy/path → 旧输入逐位不变）
        self.method_set_mode = str(self.pref.get("method_set_mode", METHOD_SET_MODE_DEFAULT))  # legacy | routed
        self.sentiment_layer = str(self.pref.get("sentiment_layer", SENTIMENT_LAYER_DEFAULT))   # path | correction
        self.sentiment_signal_mode = str(self.pref.get("sentiment_signal_mode", "legacy"))      # legacy | endogenous
        self.sentiment_band_mode = str(self.pref.get("sentiment_band_mode", "fixed"))           # fixed | typed
        # v3.18.0：舆情强度驱动调整（全部 opt-in，缺省 legacy → 旧输入逐位不变）
        self.sentiment_adjust_mode = str(self.pref.get("sentiment_adjust_mode", SENTIMENT_ADJUST_MODE_DEFAULT))  # legacy | strength
        self.signal_authority_mode = str(self.pref.get("signal_authority_mode", SIGNAL_AUTHORITY_MODE_DEFAULT))  # legacy | weighted
        self.signal_decay_mode = str(self.pref.get("signal_decay_mode", SIGNAL_DECAY_MODE_DEFAULT))              # legacy | stepped
        self.sentiment_overlap_discount = bool(self.pref.get("sentiment_overlap_discount", False))              # 去相关折让（opt-in）
        # v3.18.0 P6：权重包络校验（缺省 true —— 属纠错；仅在 routed 模式下生效，legacy 不受影响）
        self.method_weight_envelope = bool(self.pref.get("method_weight_envelope", True))
        # v3.19.0：路由主方法引擎取值分支（rNPV / SOTP，缺省 false → 旧输入逐位不变）
        self.enable_rnpv = bool(self.pref.get("enable_rnpv", False))   # B：管线药企 rNPV
        self.enable_sotp = bool(self.pref.get("enable_sotp", False))   # C：控股平台 SOTP
        # v3.21.0：成熟期「显式期增速 + 永续增速」参数体系（12 项开关，全部 opt-in，缺省逐位零回归）
        # 放在顶层 dcf_growth 块（建模口径而非用户偏好，便于报告 §6.2 逐项披露来源）
        dcg = data.get("dcf_growth") or {}
        self.dcg = dcg if isinstance(dcg, dict) else {}
        self.tg_guard = str(self.dcg.get("terminal_growth_guard", "off"))            # off | clamp
        self.tg_default_mode = str(self.dcg.get("terminal_growth_default", "legacy_6pct"))
        self.tg_basis = str(self.dcg.get("terminal_growth_basis", "legacy"))          # legacy | chain
        self.tg_scenario_mode = str(self.dcg.get("terminal_growth_scenario_mode", "flat"))  # flat | stepped
        _stg = self.dcg.get("scenario_tg_adj_pp") or {}
        self.scenario_tg_adj_pp = {"bear": float(_stg.get("bear", -0.5)),
                                   "base": float(_stg.get("base", 0.0)),
                                   "bull": float(_stg.get("bull", 0.5))}
        self.tv_share_guard = bool(self.dcg.get("tv_share_guard", False))
        self.implied_tg_market = bool(self.dcg.get("implied_tg_market", False))
        self.growth_path_mode = str(self.dcg.get("growth_path_mode", "legacy_truncate"))
        self.growth_history_mode = str(self.dcg.get("growth_history_shape", "off"))    # off | advisory
        self.scenario_step_mode = str(self.dcg.get("scenario_step_mode", "fixed"))     # fixed | cva_sigma
        self.growth_terminal_mode = str(self.dcg.get("growth_terminal_mode", "asymptotic"))
        # v3.29.0：增长函数形态族——legacy（旧五形态，缺省、逐位零回归）/ plc6（六阶段 S 曲线族）
        self.growth_shape_mode = str(self.dcg.get("growth_shape_mode", "legacy"))
        self.mature_n_mode = str(self.dcg.get("lifecycle_mature_n_mode", "table"))
        # v3.27.0：成熟期显式期取值模式——table（缺省，用 LIFECYCLE_DEFAULTS 的 6 年）
        # / legacy_4（v3.21.0 前旧行为，显式 4 年）/ cva_7（B3 试点口径，显式 7 年）。
        # `legacy_4` 由「无覆盖」改为「显式覆盖为 4」：原实现只在 cva_7 时覆盖，
        # 表值一改（4→6）就会让显式写 legacy_4 的输入静默变成 6 年。
        # v3.22.0：估值缺陷修复六项（顶层 dcf_cost 块，全部 opt-in，缺省 = v3.21.0 行为）
        _dc = data.get("dcf_cost") or {}
        self.dcost = _dc if isinstance(_dc, dict) else {}
        self.wacc_default_mode = str(self.dcost.get("wacc_default_mode", DCF_COST_DEFAULTS["wacc_default_mode"]))
        self.erp_default_mode = str(self.dcost.get("erp_default_mode", DCF_COST_DEFAULTS["erp_default_mode"]))
        self.cashflow_fallback_mode = str(self.dcost.get("cashflow_fallback_mode",
                                                         DCF_COST_DEFAULTS["cashflow_fallback_mode"]))
        self.method_drop_mode = str(self.dcost.get("method_drop_mode", DCF_COST_DEFAULTS["method_drop_mode"]))
        self.fcff_suggest = bool(self.dcost.get("fcff_suggest", DCF_COST_DEFAULTS["fcff_suggest"]))
        self.point_estimate_guard = bool(self.dcost.get("point_estimate_guard",
                                                        DCF_COST_DEFAULTS["point_estimate_guard"]))
        # 修复⑤：cva_2pct 永续增速必须配套显式/模型化 WACC（否则终值倍数腰斩）
        self.require_explicit_wacc = bool(self.dcg.get("require_explicit_wacc_with_cva_tg", False))
        # v3.23.0（D1–D3/D5/D8/D9）：现金流模型细节层（全部 opt-in，缺省 = v3.22.0 行为）
        self.discount_timing = str(self.dcost.get("discount_timing", DCF_COST_DEFAULTS["discount_timing"]))
        self.size_premium_mode = str(self.dcost.get("size_premium_mode", DCF_COST_DEFAULTS["size_premium_mode"]))
        self.capex_check = bool(self.dcost.get("capex_check", DCF_COST_DEFAULTS["capex_check"]))
        _band = self.dcost.get("capex_da_band", DCF_COST_DEFAULTS["capex_da_band"])
        self.capex_da_band = tuple(float(x) for x in (_band or [0.5, 10.0])[:2])
        self.margin_step_mode = str(self.dcost.get("margin_step_mode", DCF_COST_DEFAULTS["margin_step_mode"]))
        self.reinvestment_check = bool(self.dcost.get("reinvestment_check",
                                                      DCF_COST_DEFAULTS["reinvestment_check"]))
        self.normalization_hint = bool(self.dcost.get("normalization_hint",
                                                      DCF_COST_DEFAULTS["normalization_hint"]))
        # D4：历史形态 → 基准增速取值矩阵（缺省 off，只在用户未给 growth_forecast 时生效）
        self.growth_base_rule = str(self.dcg.get("growth_base_rule", "off"))   # off | cva_matrix
        # D6/D7：报表驱动式 FCFF（顶层 dcf_drivers 块；无块 → 不激活，零回归）
        _drv = data.get("dcf_drivers") or {}
        self.drivers = _drv if isinstance(_drv, dict) else {}
        self._gf_rule = None
        self._margin_step_cache = None
        self._capex_check_meta = None
        self._size_premium_meta = None
        self._reinv_check = None
        self._normalization_hint_meta = None
        # v3.24.0（F1）：FCF 比率惰性求值状态（缺省 fcf_ratio_lazy=False → 行为与 v2.21.1 逐位一致）
        self.fcf_ratio_lazy = bool(self.dcost.get("fcf_ratio_lazy",
                                                 DCF_COST_DEFAULTS["fcf_ratio_lazy"]))
        self._fcfr_cache = None
        self._fcfr_done = False
        self._fcf_basis = None            # 由 dcf_valuation() 写入（决定 role / skipped 文案）
        self._tg_meta = None
        self._tg_meta2 = None            # v3.25.0：三锚口径（terminal_growth_model）
        self._growth_step_cache = None
        self._tv_share_level = None
        self._tg_guard_fired = False
        self._history_shape = None
        self._tg_warned = set()
        # v3.22.0：六项修复的留痕容器（缺省 None → 不挂出，键集合不变）
        self._wacc_default_meta = None
        self._cf_fallback = None
        self._method_drop = None
        self._fcff_suggest_meta = None
        self._wacc_explicit_warned = False
        self._lifecycle = None
        self._framework = None
        self._industry = None
        self._sent_signal = None
        self._assumption_impact_active = False
        self.scen_ov = scenario_overrides or {}
        # v2.4.0：流动性折扣缺省 0（scenario 中乘 (1-0) 数值不变 → 旧输入零变化）
        self._liquidity_discount = 0.0
        self._check_input()
        gf = self.fin.get("growth_forecast") or {}
        if gf and any(v is not None and v < 0 for v in gf.values()):
            self.warnings.append("营收增速含负值，按负增长口径计算，请核实假设合理性。")

    def _normalize_weights(self, raw, label):
        """权重归一化（v2.1.0）：三项之和 ≠1（容差 1e-9）时按比例归一化并 warning。"""
        total = sum(raw.values())
        if total <= 0 or abs(total - 1.0) < 1e-9:
            return raw
        self.warnings.append(f"{label} 三项之和 {total:.3f} ≠ 1，已归一化处理。")
        return {k: v / total for k, v in raw.items()}

    # ---------- 输入校验 ----------
    def _check_input(self):
        fin = self.fin
        if not fin.get("revenue_latest_ttm") or fin.get("net_profit_latest_ttm") is None:
            self.warnings.append("财务数据缺失：营收/净利为必填，已按可用字段降级计算。")
        if fin.get("loss_making") and fin.get("net_profit_latest_ttm", 0) > 0:
            self.warnings.append("loss_making=true 但净利为正，已按盈利口径计算。")
        if len(self.comp) < 3:
            self.warnings.append(f"可比公司仅 {len(self.comp)} 家，置信度下降，综合区间自动加宽。")

    # ---------- 基础参数 ----------
    def _g1(self, adj_pp=0.0):
        gf = self.fin.get("growth_forecast") or {}
        g = list(gf.values())[0] if gf else _nn(self.fin.get("cagr_3y"), 0.20)
        return max(-0.9, g + adj_pp / 100.0)

    def _net_profit_base(self):
        """v2.10.0：净利披露档（公开披露/市场预期，最高优先级）→ (base_profit, source, basis)。
        优先级链：normalized(仅 preferences.enable_normalized=true 显式启用时覆盖披露值)
                  > annual(年度归母净利) > quarterly×4(季度归母净利×4) > semiannual×2(半年度归母净利×2)
                  > consensus(市场一致预期，视为前向利润)。
        缺省无 net_profit_basis 字段 → (None, None, None)，_forward 走现行 rev×net_margin 兜底（旧输入零变化）。"""
        npb = self.fin.get("net_profit_basis") or {}
        if self.pref.get("enable_normalized") and npb.get("normalized_net_profit") is not None:
            return float(npb["normalized_net_profit"]), "周期正常化(显式启用)", "normalized"
        if npb.get("annual_net_profit") is not None:
            return float(npb["annual_net_profit"]), "年度归母净利(公开披露)", "annual"
        if npb.get("quarterly_net_profit") is not None:
            return float(npb["quarterly_net_profit"]) * 4.0, "季度归母净利×4(公开披露)", "quarterly×4"
        if npb.get("semiannual_net_profit") is not None:
            return float(npb["semiannual_net_profit"]) * 2.0, "半年度归母净利×2(公开披露)", "semiannual×2"
        if npb.get("consensus_net_profit") is not None:
            return float(npb["consensus_net_profit"]), "市场一致预期(公开披露)", "consensus"
        return None, None, None

    def _forward(self, adj_pp=0.0, margin_adj_pp=0.0):
        """利润外推（v2.10.0 分支化）：披露档激活时以披露净利为基推算（base 情景利润=披露值×(1+g1)，
        consensus 档视为前向利润不再×g1）；未激活 → 现行 rev×net_margin 逐位不变。
        profit_source/profit_basis 存实例属性供输出块挂出。"""
        rev0 = _nn(self.fin.get("revenue_latest_ttm"), 0.0)
        g1 = self._g1(adj_pp)
        rev = rev0 * (1.0 + g1)
        base_p, p_src, p_basis = self._net_profit_base()
        self._profit_source = p_src
        self._profit_basis = p_basis
        if base_p is not None:
            # 披露档：隐含净利率 = 披露净利 / 基准营收（未外推）
            implied_margin = base_p / max(rev0, 1e-9)
            if p_basis == "consensus":
                profit = base_p * (1.0 + margin_adj_pp / 100.0)
            else:
                profit = rev * (implied_margin + margin_adj_pp / 100.0)
            margin = profit / max(rev, 1e-9)
        else:
            margin = (self.fin.get("net_margin") or 0.0) + margin_adj_pp / 100.0
            profit = rev * margin
        ebitda = (self.fin.get("ebitda_ttm") or 0.0) * (1.0 + g1)
        return rev, profit, ebitda

    # ========== v2.2.0：统计强化（WACC 模型 / 现金流统计 / 增长三角校准 / 行业指数 / 舆情结构化） ==========
    def wacc_model(self):
        """CAPM 分解 WACC（v2.2.0，v2.3.0 增强）。显式 financials.wacc 优先，模型作校验（偏差>1pp warning）。
        β 降级链（v2.3.0）：beta > unlevered_beta(再杠杆) > comparable_betas均值(再杠杆) > industry_beta(行业β兜底，再杠杆)。
        d_e_ratio 缺省时取可比集中位（可比集一致性）。"""
        wp = self.fin.get("wacc_params") or {}
        # v3.22.0 修复①：capm_auto 时即使 wacc_params 未启用也构造 CAPM，
        # 取代「未填 WACC 就硬编码 11%」——11% 对应 rf 1.9% 时代严重偏高，DCF 被系统性低估三成以上。
        auto = (self.wacc_default_mode == "capm_auto")
        if not wp.get("enabled") and not auto:
            return {"enabled": False}
        # v3.22.0：ERP 缺省双轨（auto = capm_auto 时取 CVA 8.04%，否则沿用 Damodaran 5.5%）
        _erp_key = self.erp_default_mode
        if _erp_key == "auto":
            _erp_key = "cva_8p04" if auto else "legacy_5p5"
        _erp_ref = ERP_DEFAULT_MODES.get(_erp_key, ERP_DEFAULT_MODES["legacy_5p5"])
        # v2.5.0 A1：rf/erp 缺省时用公开参考值（10Y 国债 / Damodaran 中国 ERP），用户显式优先
        rf = float(wp["rf"]) if wp.get("rf") is not None else WACC_PUBLIC_REFERENCE["rf_default"]
        erp = float(wp["erp"]) if wp.get("erp") is not None else _erp_ref
        rf_source = "公开参考(10Y国债)" if wp.get("rf") is None else "用户给定"
        if wp.get("erp") is not None:
            erp_source = "用户给定"
        elif _erp_key == "cva_8p04":
            erp_source = "公开参考(CVA CCPFC2026 隐含ERP 8.04%)"
        else:
            erp_source = "公开参考(Damodaran中国ERP)"
        t = float(wp.get("tax_rate", 0.15))
        kd = float(wp.get("cost_of_debt", 0.035))
        # v2.3.0：D/E 缺省取可比集中位（可比集一致性），否则默认 0.3
        if wp.get("d_e_ratio") is not None:
            d_e = float(wp["d_e_ratio"])
            de_source = "用户给定"
        else:
            de_vals = [c.get("d_e_ratio") for c in self.comp if c.get("d_e_ratio") is not None]
            if de_vals:
                d_e = _median(de_vals)
                de_source = "可比集中位"
            else:
                d_e = 0.3
                de_source = "默认0.3"
        beta, beta_source = None, ""
        # v3.11 β 链（修订 1b）：用户β > 可比β均值（公开回归估计优先）> 无杠杆β > 行业β > 行业参考表
        if wp.get("beta") is not None:
            beta, beta_source = float(wp["beta"]), "用户给定β"
        elif wp.get("comparable_betas"):
            bs = [float(b) for b in wp["comparable_betas"] if b]
            if bs:
                bu = sum(bs) / len(bs)
                beta = bu * (1.0 + (1.0 - t) * d_e)
                beta_source = "可比β均值再杠杆（可由 beta_estimator.py 公开回归估计）"
        elif wp.get("unlevered_beta") is not None:
            bu = float(wp["unlevered_beta"])
            beta = bu * (1.0 + (1.0 - t) * d_e)
            beta_source = "无杠杆β再杠杆"
        elif wp.get("industry_beta") is not None:
            bi = float(wp["industry_beta"])
            beta = bi * (1.0 + (1.0 - t) * d_e)
            beta_source = "行业β再杠杆（Damodaran/指数回归，无可比兜底）"
        else:
            # v2.5.0 A1：行业 β 参考表兜底（按 meta.industry 匹配，含 default）
            industry = (self.d.get("meta") or {}).get("industry", "") or "default"
            bi = WACC_PUBLIC_REFERENCE["industry_beta"].get(industry)
            if bi is None:
                bi = WACC_PUBLIC_REFERENCE["industry_beta"]["default"]
            beta = bi * (1.0 + (1.0 - t) * d_e)
            beta_source = f"行业β参考表({industry or 'default'})再杠杆"
        if beta is None:
            return {"enabled": False,
                    "note": "wacc_params 无有效 β（需 beta/unlevered_beta/comparable_betas/industry_beta 之一）"}
        ke = rf + beta * erp
        # v3.23.0 D2：规模溢价（CVA CCPFC2026 十分位，β 调整后口径直接加在 CAPM 之上）。
        # 仅 size_premium_mode=cva_deciles 且市值可得时生效；显式 WACC 仍优先（溢价只改模型值）。
        _sp = None
        if self.size_premium_mode == "cva_deciles":
            _mcap = self.fin.get("market_cap")
            if _mcap is None:
                _mcap = (self.d.get("meta") or {}).get("market_cap")
            _sp = size_premium_cva(_mcap)
            if _sp.get("applied"):
                ke += float(_sp["premium"])
                self._size_premium_meta = {**_sp, "ke_without_premium": round(rf + beta * erp, 4),
                                           "ke_with_premium": round(ke, 4)}
                self.warnings.append(
                    f"规模溢价 +{_sp['premium']:.2%}（CVA {_sp['edition']} 第 {_sp['group']} 组，"
                    f"市值 {_sp['market_cap']:.2f} 亿元）已计入股权成本，WACC 相应上移；"
                    f"该溢价为 β 调整后口径，与大市值标的比较时须说明口径差异。")
        kd_after = kd * (1.0 - t)
        ev = 1.0 / (1.0 + d_e)
        dv = d_e / (1.0 + d_e)
        wacc_model = ev * ke + dv * kd_after
        explicit = self.fin.get("wacc")
        wacc_used = float(explicit) if explicit is not None else wacc_model
        deviation = (float(explicit) - wacc_model) * 100.0 if explicit is not None else None
        if deviation is not None and abs(deviation) > 1.0:
            self.warnings.append(f"显式 WACC 与 CAPM 模型值偏差 {deviation:+.2f}pp，请核实。")
        # v3.22.0 修复①：capm_auto 且未给显式 WACC 时，记录「动态替代 11%」的留痕（仅此情形挂出）
        if explicit is None and auto:
            self._wacc_default_meta = {
                "mode": "capm_auto",
                "rf": round(rf, 4), "erp": round(erp, 4), "erp_source": erp_source,
                "beta": round(beta, 4), "beta_source": beta_source,
                "d_e_ratio": round(d_e, 4), "tax_rate": t, "cost_of_debt": kd,
                "wacc_model": round(wacc_model, 4),
                "replaced_default": DEFAULT_WACC,
                "delta_pp": round((wacc_model - DEFAULT_WACC) * 100.0, 2),
                "note": ("WACC 由 CAPM 动态构造（rf + β×ERP + 债务成本），替代原硬编码 "
                         f"{DEFAULT_WACC:.0%}；ERP 口径 {_erp_key}"),
            }
            if abs(wacc_model - DEFAULT_WACC) > 0.01:
                self.warnings.append(
                    f"WACC 动态构造值 {wacc_model:.2%} 与原缺省 {DEFAULT_WACC:.0%} 相差 "
                    f"{(wacc_model - DEFAULT_WACC) * 100:+.2f}pp（ERP {erp:.2%}、βL {beta:.3f}），"
                    f"DCF 中枢随之变动，请核实 ERP 口径与 β 来源。")
        _out = {
            "enabled": True, "method": "capm", "rf": rf, "erp": erp, "rf_source": rf_source, "erp_source": erp_source,
            "beta": round(beta, 4), "beta_source": beta_source,
            "d_e_ratio": d_e, "d_e_source": de_source, "tax_rate": t,
            "cost_of_equity": round(ke, 4), "cost_of_debt_after_tax": round(kd_after, 4),
            "equity_weight": round(ev, 4), "debt_weight": round(dv, 4),
            "wacc_model": round(wacc_model, 4), "wacc_used": round(wacc_used, 4),
            "deviation_pp": round(deviation, 2) if deviation is not None else None,
            "note": "显式 wacc 优先，模型作校验" if explicit is not None else "采用 CAPM 模型值",
        }
        # v3.23.0 D2：规模溢价留痕（仅启用且查得时挂出 → 缺省键集合不变）
        if _sp and _sp.get("applied"):
            _out["size_premium"] = {"group": _sp["group"], "premium": _sp["premium"],
                                    "edition": _sp["edition"], "market_cap": _sp["market_cap"],
                                    "basis": "β 调整后口径，直接加在 CAPM 之上（CVA 修正 CAPM）"}
            if self._wacc_default_meta:
                self._wacc_default_meta["size_premium"] = _out["size_premium"]
        return _out

    def fcf_ratio_analysis(self):
        """FCF 比率优先级链（v2.11.0；v2.11.2 修正披露档期间口径）：披露档 P0 ＞ 三层校准（L1 自身 / L2 可比 / L3 兜底）＞ 用户显式。
        P0 披露档 = (披露OCF − 披露CapEx) × 净利档年化因子 ÷ 披露净利（年化因子：annual/consensus 1、半年×2、季度×4）。
        L1 自身 = OCF/净利 − CapEx/净利（CapEx/净利 = CapEx/营收 ÷ 净利率）
        L2 可比 = 可比集中位 ocf_ratio − 可比集中位 capex_to_rev ÷ 目标净利率
        L3 兜底 = OCF/净利（无 CapEx 信息，与 v3.3 行为一致）
        加权 0.5/0.3/0.2（缺失项重归一化）；三层校准不可用（无任何 CapEx 数据）时回退用户显式；
        用户显式被校准覆盖时留痕（explicit_value/explicit_overridden/explicit_deviation）。
        fcf_ratio < 0.5 → 提示 DCF 对增速与再投资假设敏感。"""
        fin = self.fin
        # v2.10.0 P0：披露档最高优先——公开披露经营现金流净额与资本开支齐备且净利披露档可用时，
        # FCF/净利 = (OCF − CapEx) / 披露净利（capex_latest 可由 fetch_data capex_implied=OCF−FCFF 填充）
        ocf_disc = fin.get("ocf_latest")
        capex_disc = fin.get("capex_latest")
        base_p, _p_src, _p_basis = self._net_profit_base()
        # v2.11.2：披露现金流与披露净利的期间口径必须对齐。base_p 已由 net_profit_basis 年化
        # （半年×2 / 季度×4），而 ocf_latest/capex_latest 为"最新报告期"单期披露值，故须按同一因子年化，
        # 否则 FCF/净利被系统性低估（半年度档低估 50%、单季度档低估 75%），进而使 DCF 基年 FCF 失真。
        ann = {"annual": 1.0, "consensus": 1.0, "normalized": 1.0,
               "semiannual×2": 2.0, "quarterly×4": 4.0}.get(_p_basis, 1.0)
        if ocf_disc is not None and capex_disc is not None and base_p is not None and base_p > 0:
            fcff_disc = (float(ocf_disc) - float(capex_disc)) * ann
            used_d, _cm_d = self._clamp_fcf_ratio(fcff_disc / base_p, "披露档")
            if used_d < 0.5:
                self.warnings.append(f"FCF 比率仅 {used_d:.2f}（披露口径），资本开支强度高，DCF 对增速与再投资假设敏感。")
            return {"enabled": True, "used": round(used_d, 4), "source": "披露现金流/净利",
                    "ocf_latest": round(float(ocf_disc), 4), "capex_latest": round(float(capex_disc), 4),
                    "disclosed_net_profit": round(base_p, 4),
                    "annualization_factor": ann,
                    "l1_self": None, "l2_comparable": None, "l3_fallback": None,
                    **_cm_d,
                    "note": f"FCF/净利 = (披露OCF {ocf_disc} − 披露CapEx {capex_disc}) × 年化因子 {ann:g} ÷ 披露净利 {base_p:.2f} = {used_d:.3f}（最高优先级；年化因子取自净利披露档 {_p_basis}）"}
        # v2.11.0：三层校准提升至第二优先（位于用户显式之前）；用户显式降为兜底
        ocf_self = fin.get("ocf_to_net_profit", 0.9) or 0.9
        margin = fin.get("net_margin") or 0.0
        capex_rev_self = fin.get("capex_to_revenue")
        ocf_vals = [c.get("ocf_ratio") for c in self.comp if c.get("ocf_ratio")]
        cap_vals = [c.get("capex_to_rev") for c in self.comp if c.get("capex_to_rev")]
        ocf_med = _median(ocf_vals) if ocf_vals else None
        cap_med = _median(cap_vals) if cap_vals else None

        def _capex_to_np(cap_rev):
            if cap_rev is None or not margin:
                return 0.0
            return cap_rev / margin

        # v2.28.0（L4 守卫）：净利为负时 FCF/净利 **无定义**。
        #   CapEx/净利 的分母为负 → 比值变负 → l1 = ocf_self −(负数) 反向放大 → 撞上界 1.5，
        #   而 `used < 0.5` 的告警**永远不会触发**：越亏越安静，且 1.5 看起来像「转化率 150%、
        #   质量极好」。亏损标的的 FCF 增长率越高越负（再投资比 NOPAT 掉得更快），
        #   乘一个大于 1 的系数只会把负值放大。故显式置 not_applicable 并退回单层 OCF/净利，
        #   同时要求消费方改走「margin 由负爬到行业中枢」的稳态口径（见分类器 fcf_layer）。
        if margin < 0:
            _exp = fin.get("fcf_ratio")
            _used = (max(0.0, min(1.5, float(_exp))) if _exp is not None
                     else max(0.0, min(1.5, ocf_self)))
            _note = ("净利为负（净利率 %.2f%%）：FCF/净利 无定义——CapEx/净利 为负会使转换率"
                     "反向放大至上界，且不触发低转换率告警。已标记 not_applicable，"
                     "按%s取值 %.2f；亏损标的应改用稳态口径（margin 爬坡）。"
                     % (margin * 100.0, "用户显式" if _exp is not None else "OCF/净利 单层", _used))
            if not getattr(self, "_fcfr_loss_warned", False):
                self._fcfr_loss_warned = True
                self.warnings.append(_note)
            _out = {"enabled": True, "used": round(_used, 4),
                    "source": "不适用（净利为负）", "not_applicable": True,
                    "ocf_ratio": round(ocf_self, 4),
                    "capex_to_revenue": capex_rev_self,
                    "l1_self": None, "l2_comparable": None, "l3_fallback": None,
                    "note": _note}
            if _exp is not None:
                _out["explicit_value"] = round(max(0.0, min(1.5, float(_exp))), 4)
            return _out

        l1 = ocf_self - _capex_to_np(capex_rev_self)
        l2 = None
        if ocf_med is not None or cap_med is not None:
            l2 = (ocf_med if ocf_med is not None else ocf_self) - _capex_to_np(cap_med)
        explicit = fin.get("fcf_ratio")
        if capex_rev_self is None and cap_med is None:
            # 三层校准不可用（无任何 CapEx 数据）→ 回退用户显式；无显式时保持 v3.3 口径（OCF/净利）
            if explicit is not None:
                used = max(0.0, min(1.5, float(explicit)))
                if used < 0.5:
                    self.warnings.append(f"FCF 比率仅 {used:.2f}（资本开支强度高），DCF 对增速与再投资假设敏感。")
                return {"enabled": True, "used": round(used, 4), "source": "用户显式",
                        "l1_self": None, "l2_comparable": None, "l3_fallback": None,
                        "ocf_ratio": round(ocf_self, 4), "capex_to_revenue": None,
                        "note": f"无 CapEx 数据三层校准不可用，回退用户显式 FCF/净利 = {used:.2f}"}
            return {"enabled": False, "used": round(ocf_self, 4),
                    "note": "无 CapEx 数据，FCF 比率保持 v3.3 口径（OCF/净利）"}
        terms = []
        if capex_rev_self is not None:
            terms.append(("l1_self", l1, 0.5))
        if l2 is not None:
            terms.append(("l2_comparable", l2, 0.3))
        terms.append(("l3_fallback", ocf_self, 0.2))
        total = sum(w for _, _, w in terms)
        used, _cm_t = self._clamp_fcf_ratio(sum(v * w for _, v, w in terms) / total, "三层校准")
        if used < 0.5:
            self.warnings.append(f"FCF 比率仅 {used:.2f}（资本开支强度高），DCF 对增速与再投资假设敏感。")
        out = {"enabled": True, "used": round(used, 4), "source": "三层校准",
               "l1_self": round(l1, 4),
               "l2_comparable": round(l2, 4) if l2 is not None else None,
               "l3_fallback": round(ocf_self, 4), "ocf_ratio": round(ocf_self, 4),
               "capex_to_revenue": capex_rev_self,
               "comparable_capex_to_rev": round(cap_med, 4) if cap_med is not None else None,
               "capex_to_net_profit": round(_capex_to_np(capex_rev_self), 4) if capex_rev_self is not None else None,
               **_cm_t,
               "note": "FCF/净利 = OCF/净利 − CapEx/净利；三层加权（L1 0.5/L2 0.3/L3 0.2），缺失项重归一化；三层校准优先于用户显式"}
        if explicit is not None:
            exp = max(0.0, min(1.5, float(explicit)))
            dev = (used - exp) / exp if exp > 0 else None
            out["explicit_value"] = round(exp, 4)
            out["explicit_overridden"] = True
            out["explicit_deviation"] = round(dev, 4) if dev is not None else None
            out["note"] += f"；用户显式 {exp:.2f} 被三层校准覆盖（偏差 {dev:.1%}）"
        return out

    # ---------- v3.24.0（F1）：FCF 比率惰性求值 ----------
    def _get_fcfr(self):
        """FCF 比率的**惰性求值**入口（v3.24.0，`dcf_cost.fcf_ratio_lazy=true` 时生效）。

        ★根因：`run()` 原先**无条件**调用 `fcf_ratio_analysis()`。当 FCFF 口径已由更高优先级
        路径（`dcf_drivers` 三表联立 / `fcff_mode` 报表级 / `p0_value_driver`）确定时，该比率
        **无任何消费方**，却照样完整算一遍（三层校准 + 告警 + clamp），并作为 `out["fcf_ratio"]`
        挂出。格力实测：比率真值 1.541 被静默 clamp 到 1.50，既非真值、也非被采用的口径，
        却进了报告并被误归因为「P0 披露档」。

        口径（单输出多候选铁律）：**只有被选中的候选路径才计算数值；未选中路径只允许输出
        「未采用 + 原因」，不允许输出数值**——任何「算了但没用」的数字，最终一定会被引用一次。

        惰性求值同时解决另一个隐患：④ 比率档原先在 `self._fcf_ratio` 为 None 时会退回裸
        `ocf_to_net_profit`（`:3509`），使三层校准在最需要它的一档被静默降级。改由本方法
        按需求值后，④ 档一定拿到三层校准值。
        """
        if not self._fcfr_done:
            self._fcfr_cache = self.fcf_ratio_analysis()
            self._fcfr_done = True
            if self._fcfr_cache.get("enabled"):
                self._fcf_ratio = self._fcfr_cache["used"]
        return self._fcfr_cache

    def _fcfr_skipped_block(self, basis=None):
        """未计算时的**显式声明**（字段仍存在，语义是「未计算」而非缺失）。"""
        _b = basis or self._fcf_basis or "statement_drivers"
        return {"enabled": False, "skipped": True, "switched_to": _b,
                "reason": (f"FCFF 口径={_b}，比率法未被采用 → 未计算"
                           "（单输出多候选：未选中的口径不产数值，避免「算了但没用」的数字被引用）")}

    def _fcfr_view(self):
        """输出/披露用的 FCF 比率块：已算 → 原块 + `role`；未算 → skipped 标记。

        `role` 三态：`driving`（主口径即比率法）｜`diagnostic_only`（报表口径下仅供对照，
        须 `preferences.diagnostics_fcf_ratio=true` 主动索取）｜未算（skipped）。
        """
        if not self._fcfr_done:
            return self._fcfr_skipped_block()
        blk = dict(self._fcfr_cache)
        # `role` 只在惰性/诊断模式下挂出——legacy 模式的输出块须与 v2.21.1 **逐字节相同**
        if blk.get("diagnostic_only"):
            blk["role"] = "diagnostic_only"
        elif self.fcf_ratio_lazy:
            blk["role"] = ("driving" if (self._fcf_basis or "net_profit_ratio") == "net_profit_ratio"
                           else "diagnostic_only")
        return blk

    # ---------- v3.24.0（F2）：比率 clamp 留痕 ----------
    def _clamp_fcf_ratio(self, raw, label):
        """FCF 比率截断留痕（v3.24.0）。

        ★根因：上界 `min(1.5, raw)` 原为**静默截断**。格力实测 L1 真值 1.541 → 截成 1.50，
        输出里只剩 `used = 1.5`，既不报错也不留痕——它看起来就像一个真实的「现金流转化率」，
        实际是被上界压过的伪值，并被写进报告、被误归因为「P0 披露档」。
        截断必须留痕（`clamped_from` + `clamp_bound` + warning），否则「有数」与「真值」不可区分。
        """
        lo, hi = 0.0, 1.5
        used = max(lo, min(hi, raw))
        meta = {}
        if raw > hi + 1e-12:
            meta = {"clamped_from": round(raw, 4), "clamp_bound": "upper"}
            self.warnings.append(
                f"FCF 比率真值 {raw:.3f}（{label}）超出上界 {hi:g}，已截断为 {used:.3f}——"
                f"「自由现金流 ≥ 净利的 1.5 倍」通常意味着 OCF 含非经营性流入"
                f"（典型：并表财务公司的吸收存款），请核实后改用报表驱动口径（dcf_drivers）。")
        elif raw < lo - 1e-12:
            meta = {"clamped_from": round(raw, 4), "clamp_bound": "lower"}
            self.warnings.append(
                f"FCF 比率真值 {raw:.3f}（{label}）低于下界 {lo:g}，已截断为 {used:.3f}——"
                f"净利为正而自由现金流为负，请核实资本开支与营运资本口径。")
        return used, meta

    def transaction_valuation(self):
        """可比交易锚（v2.3.0）：一级市场融资/并购案例倍数 → 目标公司隐含值。
        交易距估值日>12 个月时间衰减（×0.8）；不并入综合权重（交叉验证定位，与行业指数并列）。"""
        txns = self.d.get("transactions") or []
        if not txns:
            return {"enabled": False}
        rev = _nn(self.fin.get("revenue_latest_ttm"), 0.0)
        ebitda = _nn(self.fin.get("ebitda_ttm"), 0.0)
        as_of = (self.d.get("meta") or {}).get("as_of_date")
        ev_s, ev_e = [], []
        for t in txns:
            months = _months_between(t.get("date"), as_of)
            decay = 1.0 if (months is None or months <= 12) else 0.8
            if t.get("ev_sales"):
                ev_s.append((t.get("name", ""), float(t["ev_sales"]) * decay))
            if t.get("ev_ebitda"):
                ev_e.append((t.get("name", ""), float(t["ev_ebitda"]) * decay))
        implied = {}
        if ev_s and rev:
            implied["ev_sales"] = round(rev * _median([v for _, v in ev_s]), 2)
        if ev_e and ebitda:
            implied["ev_ebitda"] = round(ebitda * _median([v for _, v in ev_e]), 2)
        if not implied:
            return {"enabled": False, "note": "交易数据无可计算倍数（需 ev_sales 或 ev_ebitda）"}
        base = round(sum(implied.values()) / len(implied), 2)
        return {"enabled": True, "n": len(txns), "implied_values": implied, "base_value": base,
                "median_ev_sales": round(_median([v for _, v in ev_s]), 2) if ev_s else None,
                "median_ev_ebitda": round(_median([v for _, v in ev_e]), 2) if ev_e else None,
                "note": "可比交易锚（一级市场倍数，>12月交易×0.8时间衰减），不并入综合权重"}

    def recent_financing_anchor(self):
        """最近融资价格锚（v2.4.0 完整版）：post_money × 时间衰减（≤12月 1.0，12-24月线性 1.0→0.7，>24月 0.7）。
        对应中证协指引第八条；提供 exclusions[] 时执行 9 项排除情形检查——命中任一 → 融资价格法不适用。
        缺省不提供 exclusions → 行为与 v2.3.0 简化版逐键一致（旧输入零变化）。不并入综合权重。"""
        rf = self.d.get("recent_financing") or {}
        if not rf.get("enabled") or not rf.get("post_money"):
            return {"enabled": False}
        post = float(rf["post_money"])
        as_of = (self.d.get("meta") or {}).get("as_of_date")
        months = _months_between(rf.get("financing_date"), as_of)
        if months is None:
            decay = 1.0
        elif months <= 12:
            decay = 1.0
        elif months <= 24:
            decay = 1.0 - 0.3 * (months - 12) / 12.0
        else:
            decay = 0.7
        base = {"enabled": True, "post_money": post,
                "months_since": months if months is not None else "未知",
                "time_decay": round(decay, 4)}
        # v2.4.0：9 项排除情形检查——仅当用户提供 exclusions[] 时激活（旧输入零变化）
        exclusions = rf.get("exclusions") or []
        if not exclusions:
            return {**base, "anchor_value": round(post * decay, 2),
                    "note": "最近融资价格锚（时间衰减，未提供排除检查输入），不并入综合权重"}
        hits = []
        for item in exclusions:
            if not item.get("present"):
                continue
            code = str(item.get("code") or item.get("type") or "")
            defn = next((d for d in RFP_EXCLUSION_DEFS
                         if d["code"] == code or code in d["name"]), None)
            hits.append({"code": defn["code"] if defn else code,
                         "name": defn["name"] if defn else item.get("type", ""),
                         "note": item.get("note", "") or (defn["desc"] if defn else "")})
        applicable = len(hits) == 0
        excl = {"checked": True, "total": len(exclusions), "applicable": applicable,
                "hits": hits,
                "note": "通过 9 项排除检查" if applicable
                else f"融资价格法不适用：命中 {len(hits)} 项排除情形（详见 hits）"}
        if not applicable:
            return {**base, "applicable": False, "anchor_value": None,
                    "exclusion_check": excl,
                    "note": "最近融资价格法不适用（命中排除情形），锚失效；不并入综合权重"}
        return {**base, "applicable": True, "anchor_value": round(post * decay, 2),
                "exclusion_check": excl,
                "note": "最近融资价格锚（时间衰减，通过 9 项排除检查），不并入综合权重"}

    def repurchase_valuation(self, main_value):
        """回购价格法（v2.4.0，中证协 2025 新增）：业绩未达预期/未按时 IPO 触发回购条款时采用。
        回购价值 = repurchase_price(元/股) × shares(亿股)；与主估值孰高（实务原则），
        结合投资人回购意愿 likelihood ∈[0,1] 实现条件加权。作锚/下限校验，不并入综合权重。"""
        rp = self.d.get("repurchase") or {}
        if not rp.get("enabled"):
            return {"enabled": False}
        try:
            price = float(rp.get("repurchase_price") or 0.0)
            shares = float(rp.get("shares") or 0.0)
        except (TypeError, ValueError):
            price, shares = 0.0, 0.0
        if price <= 0 or shares <= 0:
            return {"enabled": True, "repurchase_value": None,
                    "main_value": round(main_value, 2), "adopted": round(main_value, 2),
                    "likelihood_adjusted": None,
                    "note": "回购价格法：repurchase_price/shares 无效（需正数），未计算"}
        repurchase_value = price * shares  # 元/股 × 亿股 = 亿元
        likelihood = max(0.0, min(1.0, float(rp.get("investor_repurchase_likelihood", 1.0))))
        adopted = max(repurchase_value, main_value)  # 孰高原则
        return {"enabled": True,
                "trigger_condition": rp.get("trigger_condition", ""),
                "repurchase_value": round(repurchase_value, 2),
                "main_value": round(main_value, 2),
                "adopted": round(adopted, 2),
                "likelihood": round(likelihood, 4),
                "likelihood_adjusted": round(adopted * likelihood, 2),
                "redemption_yield": rp.get("redemption_yield"),
                "note": "回购价值与主估值孰高（中证协实务）；likelihood 为回购实现概率加权；不并入综合权重（锚/下限校验）"}

    def _liquidity_put_discount(self, sigma, T):
        """亚式平价看跌期权流动性折扣（Longstaff 风格）：discount = 2N(v√T/2) − 1。
        v√T = sqrt(σ²T + ln[2(e^{σ²T}−σ²T−1)] − 2·ln(e^{σ²T}−1))。
        返回 (discount, v√T)；σ²T≤1e-12 时返回 (0, 0) 防 ln(0) NaN。"""
        s2 = sigma * sigma * T
        if s2 <= 1e-12:
            return 0.0, 0.0
        vT = math.sqrt(s2 + math.log(2.0 * (math.exp(s2) - s2 - 1.0)) - 2.0 * math.log(math.exp(s2) - 1.0))
        return 2.0 * _norm_cdf(vT / 2.0) - 1.0, vT

    def liquidity_discount(self):
        """非上市股权流动性折扣（v2.4.0，中证协第二十条/二十一条）。
        method ∈ put_option(看跌期权模型) | empirical(经验 10-50%) | blend(加权混合)。
        只作用于市场法（可比上市公司乘数口径），DCF 不折；与 ipo_check.float_ratio（IPO 流通比例约束）分层不叠加。"""
        lq = self.d.get("liquidity") or {}
        if not lq.get("enabled"):
            return {"enabled": False}
        method = str(lq.get("method", "empirical"))
        if method not in ("put_option", "empirical", "blend"):
            method = "empirical"
        try:
            sigma = float(lq.get("volatility") or 0.0)
            T = float(lq.get("holding_period_years") or 0.0)
            empirical = max(0.0, min(0.5, float(lq.get("discount_pct") or 0.0)))
            weight = max(0.0, min(1.0, float(lq.get("weight") or 0.5)))
        except (TypeError, ValueError):
            sigma, T, empirical, weight = 0.0, 0.0, 0.0, 0.5
        put_disc, vT = self._liquidity_put_discount(sigma, T) if (sigma > 0 and T > 0) else (0.0, None)
        if method == "put_option":
            disc = put_disc
        elif method == "empirical":
            disc = empirical
        else:
            disc = weight * put_disc + (1.0 - weight) * empirical
        disc = max(0.0, min(0.5, disc))  # clamp 经验区间 [0, 50%]
        return {"enabled": True, "method_used": method, "discount_pct": round(disc, 4),
                "put_option_detail": ({"sigma": sigma, "holding_period_years": T,
                                       "v_sqrt_T": round(vT, 4), "put_discount": round(put_disc, 4)}
                                      if method != "empirical" else None),
                "empirical_discount": round(empirical, 4), "blend_weight": round(weight, 4),
                "note": "非上市股权流动性折扣：只作用于市场法（可比乘数），DCF 不折；与 ipo_check.float_ratio 分层不叠加；交易/融资锚含一级市场折价不额外折"}

    def nav_valuation(self):
        """净资产法（v2.4.0，中证协成本法）：企业价值主要来源于资产时适用（重资产/投资控股），
        亦可用于经营不佳/可能清算企业（liquidation_scenario=true 时作估值下限提示）。
        调整后净资产 = net_assets ± adjustments；输出 NAV/股。不并入综合权重。"""
        nv = self.d.get("nav") or {}
        if not nv.get("enabled"):
            return {"enabled": False}
        net_assets = nv.get("net_assets") if nv.get("net_assets") is not None else self.fin.get("net_assets")
        if net_assets is None:
            return {"enabled": True, "adjusted_nav": None, "nav_per_share": None,
                    "note": "净资产法：net_assets 缺失（nav 与 financials.net_assets 均无），未计算"}
        try:
            adjusted_nav = float(net_assets) + float(nv.get("adjustments") or 0.0)
        except (TypeError, ValueError):
            return {"enabled": True, "adjusted_nav": None, "nav_per_share": None,
                    "note": "净资产法：net_assets/adjustments 数值无效，未计算"}
        shares = self.fin.get("total_shares_after_issue") or 0.0
        nav_ps = round(adjusted_nav / shares, 2) if shares else None  # 亿元/亿股 = 元/股
        return {"enabled": True, "adjusted_nav": round(adjusted_nav, 2),
                "nav_per_share": nav_ps,
                "liquidation_scenario": bool(nv.get("liquidation_scenario", False)),
                "note": "净资产法：重资产/控股平台主方法候选；清算场景作估值下限参考（不强制改综合值）"}

    # ---------- v3.17.0 P5：金融路由替代主方法（RIM / DDM） ----------
    def _share_count(self):
        """股本取值（v3.17.0 P5）：供 RIM/DDM 每股换算。
        优先链：shares_outstanding > total_shares_after_issue（发行后总股本）> issue_shares（仅发行量，兜底）。
        **单位约定与金额字段一致：亿股**（输入 $note 惯例「金额=亿元，股票=亿股」）。
        故价值（亿元）/ 股本（亿股）= 元/股，无需任何换算。
        返回 (股本数[亿股], 来源字段, 单位说明)；均缺失时 (None, None, None)。"""
        fin = self.fin
        for k in ("shares_outstanding", "total_shares_after_issue", "issue_shares"):
            v = _nn(fin.get(k), None)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv <= 0:
                continue
            return fv, k, "亿股（与金额亿元口径一致：价值/股本=元/股）"
        return None, None, None

    def rim_valuation(self, adj_pp=0.0):
        """剩余收益模型 RIM（v3.17.0 P5）：金融路由主方法。
        V0 = B0 + Σ (ROE_t − Ke) × B_{t−1} / (1+Ke)^t + 终值
        终值口径：持续因子 ω 的衰减式 TV = (ROE_T − Ke) × B_T / (1 + Ke − ω)
        适用：银行/保险/券商等受监管资本约束主体（债务为经营原料，FCFF 不可定义）。
        激活条件（三档优先，任一层命中即可）：
          ① d.rim.enabled 显式块（最高优先）
          ② preferences.enable_rim=true 且财务侧可推出 B0 与 ROE（次之）
          ③ 行业参数底座发（金融类 roe_steady/ke，作最后兜底）
        缺失关键参数时返回 enabled=True + value=None（留痕），不静默。"""
        rim = self.d.get("rim") or {}
        fin = self.fin
        # B0：显式块 > financials.net_assets + 别名
        b0 = rim.get("book_value_equity")
        if b0 is None:
            b0 = _nn(fin.get("net_assets"), None)
        if b0 is None:
            b0 = _nn(fin.get("net_assets_latest"), None)
        if b0 is None:
            b0 = _nn(fin.get("equity_book_value"), None)
        # ROE
        roe = rim.get("roe_steady")
        if roe is None:
            roe = _nn(fin.get("roe"), None) or _nn(fin.get("roe_latest"), None)
        # Ke：显式 > 行业底座 > 有效 WACC > 10% 兜底
        ke = rim.get("cost_of_equity")
        if ke is None:
            ke = _nn(fin.get("ke"), None)
        if ke is None:
            _ipp = ((self._industry or {}).get("params") or {})
            ke = _ipp.get("ke")
        if isinstance(ke, str):
            ke = None
        if ke is None:
            wm = getattr(self, "_wacc_eff", None)
            ke = wm if wm is not None else 0.10        # 权益成本缺省 10%（金融类 Ke 通常高于一般企业 WACC）
        # 行业底座兜底：ROE / payout / ω / 期数
        _ipp = ((self._industry or {}).get("params") or {})
        if roe is None:
            roe = _ipp.get("roe_steady")
        payout = rim.get("payout_ratio")
        if payout is None:
            payout = _nn(fin.get("payout_ratio"), None)
        if payout is None:
            payout = _ipp.get("payout_ratio")
        if payout is None:
            payout = 0.40
        omega = rim.get("persistence")
        if omega is None:
            omega = _ipp.get("persistence_omega")
        if omega is None:
            omega = 0.85                              # 持续因子 ω∈[0.6,0.95]
        enabled = bool(rim.get("enabled")) or bool(self.pref.get("enable_rim"))
        if not enabled:
            return {"enabled": False}
        if b0 is None or roe is None:
            return {"enabled": True, "value": None,
                    "note": "RIM：book_value_equity/net_assets 与 roe 均须提供，当前缺失，未计算"}
        try:
            b0, roe, ke = float(b0), float(roe), float(ke)
            payout, omega = float(payout), float(omega)
        except (TypeError, ValueError):
            return {"enabled": True, "value": None, "note": "RIM：关键参数数值无效，未计算"}
        if not (0.0 < omega < 1.0):
            omega = 0.85
        omega = max(0.50, min(0.95, omega))
        payout = max(0.0, min(0.95, payout))
        n = int(rim.get("explicit_years", 5))
        roe_adj = roe + adj_pp / 100.0
        # 显式期：ROE 向稳态回归（若提供 roe_terminal）
        roe_term = rim.get("roe_terminal")
        roe_term = float(roe_term) if roe_term is not None else roe_adj
        pv_ri, b_t, rows = 0.0, b0, []
        for t in range(1, n + 1):
            w = t / n
            roe_t = roe_adj * (1 - w) + roe_term * w
            ri = (roe_t - ke) * b_t
            pv_ri += ri / (1 + ke) ** t
            b_t = b_t * (1.0 + ri / b_t * (1 - payout)) if b_t else b_t   # 留存剩余收益 → 账面价值增长
            rows.append({"year": t, "roe": round(roe_t, 4), "book": round(b_t, 2),
                         "residual_income": round(ri, 2)})
        ri_term = (roe_term - ke) * b_t
        tv = ri_term / (1 + ke - omega) if (1 + ke - omega) > 0 else 0.0
        tv_pv = tv / (1 + ke) ** n
        value = b0 + pv_ri + tv_pv
        out = {"enabled": True, "value": round(value, 2), "equity_value": round(value, 2),
               "book_value_0": round(b0, 2),
               "roe_steady": round(roe_adj, 4), "roe_terminal": round(roe_term, 4),
               "cost_of_equity": round(ke, 4), "persistence": omega, "payout_ratio": round(payout, 4),
               "pv_residual_income": round(pv_ri, 2), "tv_pv": round(tv_pv, 2),
               "tv_share": round(tv_pv / value, 4) if value else None,
               "schedule": rows,
               "note": "剩余收益模型 RIM（P5）：金融路由主方法；V0 = B0 + ΣRI/(1+Ke)^t + TV，"
                       "TV 用持续因子 ω 衰减；ROE 期内向 roe_terminal 线性回归"}
        # 每股换算（提供股本时）
        sh, sh_src, sh_unit = self._share_count()
        if sh:
            try:
                out["per_share"] = round(value / float(sh), 4)
                out["shares_outstanding"] = float(sh)
                out["share_source"] = sh_src
                out["share_unit"] = sh_unit
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        return out

    def ddm_valuation(self):
        """股利折现模型 DDM（v3.17.0 P5）：金融路由辅助方法。
        两阶段：显式期逐年股利折现 + Gordon 终值。
        适用（中证协口径）：**仅适用于已进入成熟期或经营、分红稳定的项目**。
        激活条件：d.ddm.enabled 或 preferences.enable_ddm=true，且
          D0 = 显式 dividend_latest ＞ 净利×payout（财务侧）＞ 行业底座 payout 兜底。
        缺 Ke 时依次取 显式 / financials.ke / 行业底座 ke / 有效 WACC / 10%。"""
        ddm = self.d.get("ddm") or {}
        fin = self.fin
        enabled = bool(ddm.get("enabled")) or bool(self.pref.get("enable_ddm"))
        if not enabled:
            return {"enabled": False}
        _ipp = ((self._industry or {}).get("params") or {})
        payout = ddm.get("payout_ratio")
        if payout is None:
            payout = _nn(fin.get("payout_ratio"), None)
        if payout is None:
            payout = _ipp.get("payout_ratio")
        if payout is None:
            payout = 0.40
        d0 = ddm.get("dividend_latest")
        if d0 is None:
            # 净利基：披露档（_net_profit_base）> 直接字段 net_profit_latest_ttm > net_profit_latest
            base_p, _, _ = self._net_profit_base()
            np_ = base_p
            np_src = "net_profit_basis 披露档" if base_p is not None else None
            if np_ is None:
                np_ = _nn(fin.get("net_profit_latest_ttm"), None)
                np_src = "net_profit_latest_ttm" if np_ is not None else np_src
            if np_ is None:
                np_ = _nn(fin.get("net_profit_latest"), None)
                np_src = "net_profit_latest" if np_ is not None else np_src
            if np_ is None:
                # 最后兜底：营收 × 净利率
                _rev = _nn(fin.get("revenue_latest_ttm"), None)
                _nm = _nn(fin.get("net_margin"), None)
                if _rev is not None and _nm is not None:
                    np_ = float(_rev) * float(_nm)
                    np_src = "营收×净利率（兜底）"
            if np_ is not None:
                d0 = float(np_) * float(payout)
                self._ddm_np_src = np_src
        if d0 is None:
            return {"enabled": True, "value": None,
                    "note": "DDM：dividend_latest 缺失且无法由净利×分红率推得，未计算"}
        ke = ddm.get("cost_of_equity")
        if ke is None:
            ke = _nn(fin.get("ke"), None)
        if ke is None:
            ke = _ipp.get("ke")
        if isinstance(ke, str):
            ke = None
        if ke is None:
            ke = getattr(self, "_wacc_eff", None) or 0.10
        try:
            ke = float(ke)
            payout = float(payout)
        except (TypeError, ValueError):
            return {"enabled": True, "value": None, "note": "DDM：Ke/payout 数值无效，未计算"}
        g1 = float(ddm.get("dividend_growth", self._g1()))
        g_term = float(ddm.get("terminal_growth", self.fin.get("terminal_growth") or 0.02))
        n = int(ddm.get("explicit_years", 5))
        # v3.17.0 P5：适用性护栏（中证协口径——仅成熟期/分红稳定）。三条件任取其一即告警：
        # ① Ke ≤ g∞（Gordon 不成立）② 显式期增速过高（>25%，成长股不符合分红稳定假设）
        # ③ 终值占比 >85%（价值几乎全在永续假设，DDM 对 g∞ 极度敏感）
        guards = []
        if ke <= g_term:
            return {"enabled": True, "value": None,
                    "note": f"DDM：权益成本 {ke:.2%} ≤ 永续增速 {g_term:.2%}，Gordon 模型不成立，未计算"}
        if g1 > 0.25:
            guards.append(f"显式期股利增速 {g1:.0%} > 25%（成长股不符合「分红稳定」前提，DDM 结论慎用）")
        if g1 < 0:
            guards.append(f"显式期股利增速 {g1:.0%} < 0（分红递减，须核实是否可持续）")
        if ke - g_term < 0.02:
            guards.append(f"Ke−g∞ = {ke - g_term:.2%} < 2%（分母过小，估值对参数极度敏感）")
        pv, d_t, rows = 0.0, float(d0), []
        for t in range(1, n + 1):
            d_t = d_t * (1 + g1)
            pv += d_t / (1 + ke) ** t
            rows.append({"year": t, "dividend": round(d_t, 2)})
        tv = d_t * (1 + g_term) / (ke - g_term)
        tv_pv = tv / (1 + ke) ** n
        value = pv + tv_pv
        _tv_share = (tv_pv / value) if value else 0.0
        if _tv_share > 0.85:
            guards.append(f"终值占比 {_tv_share:.0%} > 85%（价值主要由永续假设承载，须做 g∞ 敏感性）")
        out = {"enabled": True, "value": round(value, 2), "equity_value": round(value, 2),
               "dividend_0": round(float(d0), 2), "d1": round(float(d0) * (1 + g1), 2),
               "payout_ratio": round(payout, 4),
               "net_profit_source": getattr(self, "_ddm_np_src", "dividend_latest 直接给定"),
               "cost_of_equity": round(ke, 4), "growth_explicit": round(g1, 4),
               "terminal_growth": round(g_term, 4),
               "pv_explicit": round(pv, 2), "tv_pv": round(tv_pv, 2),
               "tv_share": round(tv_pv / value, 4) if value else None,
               "schedule": rows,
               "note": "股利折现模型 DDM（P5）：中证协口径仅适用于成熟期/分红稳定项目"}
        if guards:
            out["applicability_warnings"] = guards
            out["note"] += "；适用性告警：" + "；".join(guards)
        sh, sh_src, sh_unit = self._share_count()
        if sh:
            try:
                out["per_share"] = round(value / float(sh), 4)
                out["shares_outstanding"] = float(sh)
                out["share_source"] = sh_src
                out["share_unit"] = sh_unit
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        return out

    # ---------- v3.19.0 B：rNPV 管线药企估值（风险调整净现值）----------
    def _rnpv_pos(self, phase, overrides=None):
        """单阶段 → 上市成功率 PoS（用户覆盖 > 内置表 > 缺省 0.35）。返回 (pos, phase_key)。"""
        pk = str(phase or "").strip().lower()
        # 别名归一（用户可能写 I期/二期/临床III/已上市…）
        alias = {"i": "phase1", "1": "phase1", "一期": "phase1", "phase1": "phase1",
                 "ii": "phase2", "2": "phase2", "二期": "phase2", "phase2": "phase2",
                 "iii": "phase3", "3": "phase3", "三期": "phase3", "phase3": "phase3",
                 "nda": "nda", "bla": "nda", "申报": "nda", "注册": "nda",
                 "approved": "approved", "已上市": "approved", "上市": "approved",
                 "preclinical": "preclinical", "临床前": "preclinical", "发现期": "preclinical"}
        pk = alias.get(pk, pk)
        if overrides and pk in overrides:
            try:
                return max(0.0, min(1.0, float(overrides[pk]))), pk
            except (TypeError, ValueError):
                pass
        return RNPV_POS_TABLE.get(pk, 0.35), pk

    def rnpv_valuation(self):
        """rNPV 风险调整净现值（v3.19.0 B）：管线药企路由（pipeline_pharma）主方法。

        口径（逐管线）：
          rNPV_i = Σ_t [ PoS × 风险调整现金流_t / (1+r)^t ] − 已投入/剩余研发成本现值
        其中现金流按「上市后爬坡 → 峰值 → 专利悬崖衰减」生命周期剖面生成——
          · 上市前（相对 launch_year）：现金流为负（研发投入 R&D_i，按 PoS 概率加权？否 —— 成本已发生/确定，不乘 PoS）
          · 上市后：收入 = 峰值销售 × ramp(t) × decay(t)，净现金流 = 收入 × 净利率
        风险调整仅作用于**上市后收益**（乘 PoS），上市前成本按确定性计入（口径保守、可审计）。

        输入（d.rnpv）：
          {enabled, pipelines:[{name, phase, peak_sales, launch_year, rnd_annual?, margin?, pos?}],
           discount_rate?, pos_overrides?{phase:PoS}, horizon_years?}
        Layers：折现率取 显式 > 行业底座 rnpv_discount > RNPV_DISCOUNT_DEFAULT(12%)。
        输出与 nav/rim 同构（value / per_share / pipelines_detail / pos_schedule）。
        缺关键参数时返回 enabled=True + value=None（留痕），不静默。"""
        rn = self.d.get("rnpv") or {}
        enabled = bool(rn.get("enabled")) or bool(self.enable_rnpv)
        if not enabled:
            return {"enabled": False}
        pipes = rn.get("pipelines") or []
        if not isinstance(pipes, list) or not pipes:
            return {"enabled": True, "value": None, "pipelines_detail": [],
                    "note": "rNPV：pipelines 清单为空，未计算（须提供管线：phase/peak_sales/launch_year）"}
        # 折现率：显式 > 行业底座 > 缺省
        _ipp = (self._industry or {}).get("params") or {}
        r = rn.get("discount_rate")
        if r is None:
            r = _ipp.get("rnpv_discount")
        if r is None:
            r = RNPV_DISCOUNT_DEFAULT
        try:
            r = float(r)
        except (TypeError, ValueError):
            r = RNPV_DISCOUNT_DEFAULT
        if not (0.0 < r < 0.60):
            r = RNPV_DISCOUNT_DEFAULT
        pos_ovr = rn.get("pos_overrides") or {}
        margin_glb = rn.get("margin")
        if margin_glb is None:
            margin_glb = _ipp.get("ebit_margin_steady") or 0.30   # 医药稳态利润率兜底（税后近似）
        try:
            margin_glb = float(margin_glb)
        except (TypeError, ValueError):
            margin_glb = 0.30
        horizon = int(rn.get("horizon_years") or 15)

        detail, pos_sched = [], []
        total_npv, total_rnd_pv, total_rev_pv = 0.0, 0.0, 0.0
        for p in pipes:
            if not isinstance(p, dict):
                continue
            name = p.get("name") or "未命名管线"
            phase = p.get("phase")
            pos, pk = self._rnpv_pos(p.get("pos") if p.get("pos") is not None else phase, pos_ovr)
            # 峰值销售（亿元）
            peak = p.get("peak_sales")
            try:
                peak = float(peak)
            except (TypeError, ValueError):
                peak = None
            launch = p.get("launch_year")
            try:
                launch = int(launch)
            except (TypeError, ValueError):
                launch = None
            rnd = p.get("rnd_annual")
            try:
                rnd = float(rnd) if rnd is not None else 0.0
            except (TypeError, ValueError):
                rnd = 0.0
            margin = p.get("margin")
            try:
                margin = float(margin) if margin is not None else margin_glb
            except (TypeError, ValueError):
                margin = margin_glb
            if peak is None or launch is None:
                detail.append({"name": name, "phase": pk, "pos": round(pos, 4),
                               "value": None, "note": "缺 peak_sales / launch_year，跳过"})
                continue
            # 逐现金流折现：t=1..horizon；t < launch → 研发成本（不乘 PoS）；t ≥ launch → 收益（乘 PoS）
            npv_pipe, npv_rnd, npv_rev, rows = 0.0, 0.0, 0.0, []
            for t in range(1, horizon + 1):
                if t < launch:
                    cf = -rnd
                    npv_rnd += cf / (1 + r) ** t
                    rows.append({"t": t, "kind": "R&D", "cf": round(cf, 3),
                                 "pv": round(cf / (1 + r) ** t, 3)})
                    continue
                y = t - launch + 1                     # 上市后第 y 年
                # 爬坡（上市→峰值，线性）；峰值后按专利悬崖线性衰减至残值
                if y <= RNPV_RAMP_YEARS:
                    shape = y / float(RNPV_RAMP_YEARS)
                else:
                    dy = y - RNPV_RAMP_YEARS
                    if dy <= RNPV_TAIL_YEARS:
                        shape = 1.0 - (1.0 - RNPV_TAIL_FLOOR) * (dy / float(RNPV_TAIL_YEARS))
                    else:
                        shape = RNPV_TAIL_FLOOR
                rev = peak * shape
                cf_risked = rev * margin * pos         # 风险调整：收益×PoS（成本不乘）
                pv = cf_risked / (1 + r) ** t
                npv_pipe += pv
                npv_rev += pv
                rows.append({"t": t, "kind": "revenue", "year_post_launch": y,
                             "shape": round(shape, 4), "revenue": round(rev, 3),
                             "risk_adjusted_cf": round(cf_risked, 3),
                             "pv": round(pv, 3)})
            npv_pipe += npv_rnd                         # 加回（负的）研发成本现值
            total_npv += npv_pipe
            total_rnd_pv += npv_rnd
            total_rev_pv += npv_rev
            detail.append({"name": name, "phase": pk, "pos": round(pos, 4),
                           "peak_sales": round(peak, 2), "launch_year": launch,
                           "margin": round(margin, 4), "rnd_annual": round(rnd, 3),
                           "rnpv": round(npv_pipe, 2), "pv_risk_adjusted_revenue": round(npv_rev, 2),
                           "pv_rnd_cost": round(npv_rnd, 2), "schedule": rows})
            pos_sched.append({"name": name, "phase": pk, "pos": round(pos, 4)})
        if not detail:
            return {"enabled": True, "value": None, "pipelines_detail": [],
                    "note": "rNPV：pipelines 元素无效（须为对象），未计算"}
        # 若全部管线均缺关键参数 → 不返回 0（易被误读为「估值为零」），而是留痕 None
        if not any(d.get("rnpv") is not None for d in detail):
            return {"enabled": True, "value": None, "pipelines_detail": detail,
                    "note": "rNPV：全部管线缺 peak_sales/launch_year，未计算（不返回 0，避免误读为估值为零）"}
        value = round(total_npv, 2)
        out = {"enabled": True, "value": value, "equity_value": value,
               "method": "rnpv", "discount_rate": round(r, 4),
               "n_pipelines": len(detail),
               "pv_risk_adjusted_revenue": round(total_rev_pv, 2),
               "pv_rnd_cost": round(total_rnd_pv, 2),
               "pipelines_detail": detail, "pos_schedule": pos_sched,
               "note": "rNPV 风险调整净现值（v3.19.0 B）：管线药企路由主方法；"
                       "收益按上市成功率 PoS 概率加权（成本不乘 PoS），"
                       f"生命周期剖面=爬坡{RNPV_RAMP_YEARS}年→峰值→悬崖衰减{RNPV_TAIL_YEARS}年→残值{RNPV_TAIL_FLOOR:.0%}；"
                       "可比法作交叉验证"}
        sh, sh_src, sh_unit = self._share_count()
        if sh:
            try:
                out["per_share"] = round(value / float(sh), 4)
                out["shares_outstanding"] = float(sh)
                out["share_source"] = sh_src
                out["share_unit"] = sh_unit
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        return out

    # ---------- v3.19.0 C：SOTP 分部加总估值 ----------
    def sotp_valuation(self):
        """SOTP 分部加总（v3.19.0 C）：控股平台/多业务主体（holdco 路由）主方法。

        EV = Σ(分部价值_i × 持股比例_i) + 联营/金融资产 − 净债
        股权价值 = EV × (1 − 控股折价)

        口径为「分部价值输入 + 加总」模式（segment-value-in-and-sum）：每个分部价值由用户/外部
        按分部法（可比倍数或分部 DCF）给出，引擎负责**加总口径**与**控股折价**，不在引擎内重跑各分部
        现金流 —— 该分部价值口径可审计，且与 NAV/成本法的「输入驱动」定位同族。

        输入（d.sotp）：
          {enabled, segments:[{name, value|(metric×multiple), stake?, method?}],
           net_debt?, associates_value?, holdco_discount?|auto, discount_by_segments?}
        · 分部价值 = 显式 value ；或 metric × multiple；
        · 控股折价：显式值 > auto（按分部数取 SOTP_DISCOUNT_BY_SEGMENTS）> 缺省 0.0（单分部），
          上限 SOTP_HOLDCO_DISCOUNT_MAX。
        缺分部或价值时返回 enabled=True + value=None（留痕），不静默。"""
        st = self.d.get("sotp") or {}
        enabled = bool(st.get("enabled")) or bool(self.enable_sotp)
        if not enabled:
            return {"enabled": False}
        segs = st.get("segments") or []
        if not isinstance(segs, list) or not segs:
            return {"enabled": True, "value": None, "segments_detail": [],
                    "note": "SOTP：segments 清单为空，未计算（须提供分部 value 或 metric×multiple）"}
        seg_detail, sum_value, missing = [], 0.0, 0
        for s in segs:
            if not isinstance(s, dict):
                continue
            name = s.get("name") or "未命名分部"
            v = s.get("value")
            if v is None:
                # metric × multiple 口径
                met = _nn(s.get("metric"), None)
                mul = _nn(s.get("multiple"), None)
                if met is not None and mul is not None:
                    v = float(met) * float(mul)
            try:
                v = float(v)
            except (TypeError, ValueError):
                missing += 1
                seg_detail.append({"name": name, "value": None, "stake": s.get("stake"),
                                   "note": "缺 value 且无法由 metric×multiple 推得，跳过"})
                continue
            stake = s.get("stake")
            try:
                stake = float(stake) if stake is not None else 1.0
            except (TypeError, ValueError):
                stake = 1.0
            stake = max(0.0, min(1.0, stake))
            contrib = v * stake
            sum_value += contrib
            seg_detail.append({"name": name, "value": round(v, 2), "stake": round(stake, 4),
                               "method": s.get("method") or ("metric×multiple" if s.get("metric") is not None else "显式 value"),
                               "contribution": round(contrib, 2)})
        if not seg_detail or all(d.get("value") is None for d in seg_detail):
            return {"enabled": True, "value": None, "segments_detail": seg_detail,
                    "note": "SOTP：所有分部均缺价值，未计算"}
        associates = _nn(st.get("associates_value"), 0.0)
        try:
            associates = float(associates)
        except (TypeError, ValueError):
            associates = 0.0
        net_debt = _nn(st.get("net_debt"), None)
        if net_debt is None:
            net_debt = _nn(self.fin.get("net_debt"), 0.0)
        try:
            net_debt = float(net_debt)
        except (TypeError, ValueError):
            net_debt = 0.0
        ev_sum = sum_value + associates
        equity_pre = ev_sum - net_debt
        # 控股折价：显式 > auto（按有效分部数）> 缺省（1 分部分无折价）
        n_seg = sum(1 for d in seg_detail if d.get("value") is not None)
        disc = st.get("holdco_discount")
        disc_basis = "显式"
        if disc is None:
            if bool(st.get("auto_discount", True)):
                if n_seg in SOTP_DISCOUNT_BY_SEGMENTS:
                    disc = SOTP_DISCOUNT_BY_SEGMENTS[n_seg]
                else:
                    disc = SOTP_HOLDCO_DISCOUNT_DEFAULT
                disc_basis = f"auto（按 {n_seg} 个分部）"
            else:
                disc = 0.0
                disc_basis = "未启用折价"
        try:
            disc = float(disc)
        except (TypeError, ValueError):
            disc = 0.0
        disc = max(0.0, min(SOTP_HOLDCO_DISCOUNT_MAX, disc))
        value = equity_pre * (1.0 - disc)
        out = {"enabled": True, "value": round(value, 2), "equity_value": round(value, 2),
               "method": "sotp",
               "sum_segment_value": round(sum_value, 2), "associates_value": round(associates, 2),
               "ev_sum": round(ev_sum, 2), "net_debt": round(net_debt, 2),
               "equity_before_discount": round(equity_pre, 2),
               "holdco_discount": round(disc, 4), "holdco_discount_basis": disc_basis,
               "n_segments": n_seg, "segments_detail": seg_detail,
               "note": "SOTP 分部加总（v3.19.0 C）：holdco 路由主方法；"
                       "EV=Σ(分部价值×持股)+联营金融资产−净债；股权价值=EV×(1−控股折价)；"
                       "分部价值采用「输入+加总」口径（分部法价值由用户给定，可审计）；可比法作交叉验证"}
        sh, sh_src, sh_unit = self._share_count()
        if sh:
            try:
                out["per_share"] = round(value / float(sh), 4)
                out["shares_outstanding"] = float(sh)
                out["share_source"] = sh_src
                out["share_unit"] = sh_unit
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        return out

    # ---------- v2.4.0：输入校验 / 资产类型适配 / 关键假设汇总 ----------
    def _validate_input(self):
        """输入数据校验与异常值处理（v2.4.0；v2.5.0 增加 A2/A3/A4）。返回 issues 列表（level: error/warning + 规则说明）；
        issues 非空时 run() 挂出 input_validation 块。仅校验与提示，不强制改值（估值口径由用户负责）。"""
        issues = []
        fin = self.fin
        meta = self.d.get("meta") or {}
        def _num(field):
            v = fin.get(field)
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        rev = _num("revenue_latest_ttm")
        if rev is not None and (rev <= 0 or rev > 50000):
            issues.append({"level": "warning", "field": "revenue_latest_ttm", "value": rev,
                           "rule": "TTM 营收应 >0 且 <5 万亿（亿元），疑似单位错误或极端异常值"})
        margin = _num("net_margin")
        if margin is not None and not (-2.0 <= margin <= 1.0):
            issues.append({"level": "error", "field": "net_margin", "value": margin,
                           "rule": "净利率应在 [-200%, 100%] 区间"})
        wacc = _num("wacc")
        if wacc is not None and not (0.02 <= wacc <= 0.25):
            issues.append({"level": "warning", "field": "wacc", "value": wacc,
                           "rule": "WACC 应在 [2%, 25%] 区间"})
        tg = _num("terminal_growth")
        if tg is not None and not (0.0 <= tg <= 0.10):
            issues.append({"level": "warning", "field": "terminal_growth", "value": tg,
                           "rule": "永续增速应在 [0%, 10%] 区间（GDP 长期增速锚定，高于 10% 需强依据）"})
        gf = fin.get("growth_forecast") or {}
        for k, v in gf.items():
            if isinstance(v, (int, float)) and (v < -0.9 or v > 5.0):
                issues.append({"level": "warning", "field": f"growth_forecast.{k}", "value": v,
                               "rule": "营收增速应在 [-90%, 500%] 区间"})
        for c in self.comp:
            for k in ("pe", "pb"):
                v = c.get(k)
                if isinstance(v, (int, float)) and not (0 < v <= 500):
                    issues.append({"level": "warning", "field": f"comparables.{c.get('name')}.{k}", "value": v,
                                   "rule": f"{k} 应在 (0, 500] 区间，异常值将被 IQR 剔除或影响中位数"})
            for k in ("ps", "ev_ebitda"):
                v = c.get(k)
                if isinstance(v, (int, float)) and not (0 < v <= 200):
                    issues.append({"level": "warning", "field": f"comparables.{c.get('name')}.{k}", "value": v,
                                   "rule": f"{k} 应在 (0, 200] 区间"})
        # ===== v2.5.0 新增 =====
        # A3 三表勾稽校验（v2.10.0：净利披露档激活时校验 net_margin vs 披露隐含净利率）
        base_p, _p_src, p_basis = self._net_profit_base()
        if rev is not None and margin is not None:
            if base_p is not None:
                implied_m = base_p / max(rev * (1.0 + self._g1(0.0)), 1e-9)
                if implied_m > 0 and abs(margin - implied_m) / implied_m > CHECK_NETPROFIT_TOLERANCE:
                    issues.append({"level": "warning", "field": "net_margin vs 披露档",
                                   "value": round(margin, 4),
                                   "rule": f"净利率 {margin:.0%} 与披露档({p_basis})隐含净利率 {implied_m:.0%} 偏差"
                                           f"{abs(margin - implied_m) / implied_m:.0%} >30%，请核实口径"})
            else:
                implied_profit = rev * margin
                np_ = _num("net_profit_latest_ttm")
                if np_ is not None and np_ > 0 and implied_profit > 0:
                    dev = abs(np_ - implied_profit) / max(np_, 1e-9)
                    if dev > CHECK_NETPROFIT_TOLERANCE:
                        issues.append({"level": "warning", "field": "net_profit×net_margin",
                                       "value": round(implied_profit, 2),
                                       "rule": f"净利率×营收 = {implied_profit:.2f} 与净利 {np_:.2f} 偏差 {dev:.0%} >30%，三表勾稽不一致，请核实口径"})
        gross = _num("gross_margin")
        if CHECK_GROSS_MARGIN_ABOVE_NET and gross is not None and margin is not None and gross < margin:
            issues.append({"level": "error", "field": "gross_margin", "value": gross,
                           "rule": f"毛利率 {gross:.0%} 低于净利率 {margin:.0%}，违背利润结构常识，请核实"})
        ocf_r = _num("ocf_to_net_profit")
        recv_r = _num("receivables_to_revenue")
        if ocf_r is not None and ocf_r < 0.5:
            issues.append({"level": "warning", "field": "ocf_to_net_profit", "value": ocf_r,
                           "rule": "净现比 <0.5，盈利现金含量低，DCF 现金流口径需谨慎（应收/存货占压或利润含金量不足）"})
        if recv_r is not None and recv_r > 0.4 and ocf_r is not None and ocf_r > 1.0:
            issues.append({"level": "warning", "field": "receivables_to_revenue", "value": recv_r,
                           "rule": "应收/营收 >0.4 与净现比 >1.0 存在矛盾（应收高应压低现金含量），请核实"})
        # A2 可比数据时点统一（comparables.as_of 混合日期警示）
        asofs = []
        for c in self.comp:
            a = c.get("as_of")
            if a:
                asofs.append((str(a), c.get("name", "")))
        if len(asofs) >= 2:
            from datetime import date as _date
            def _p(s):
                try:
                    y, m, d = (int(x) for x in str(s).split("-")[:3])
                    return _date(y, m, d)
                except Exception:
                    return None
            dates = [(_p(a), n) for a, n in asofs if _p(a)]
            if len(dates) >= 2:
                dmin = min(d[0] for d in dates); dmax = max(d[0] for d in dates)
                spread = (dmax - dmin).days
                if spread > CHECK_AS_OF_MAX_SPREAD_DAYS:
                    issues.append({"level": "warning", "field": "comparables.as_of",
                                   "value": spread,
                                   "rule": f"可比数据时点最大差 {spread} 天 >30 天（{dmin} ~ {dmax}），倍数口径不一致，建议统一数据日期"})
        # A4 数据时效（数据日期距估值基准日 >180 天 → 警示）
        as_of_date = meta.get("as_of_date")
        stale_fields = []
        if as_of_date:
            from datetime import date as _date
            def _p2(s):
                try:
                    y, m, d = (int(x) for x in str(s).split("-")[:3])
                    return _date(y, m, d)
                except Exception:
                    return None
            base_d = _p2(as_of_date)
            if base_d:
                for label, src in (("财务数据", fin.get("data_as_of")),
                                   ("可比数据", None)):
                    pass
                # 可比 as_of
                for a, n in asofs:
                    ad = _p2(a)
                    if ad and base_d and (base_d - ad).days > CHECK_DATA_STALENESS_DAYS:
                        stale_fields.append(f"{n}({a})")
                # 财务数据 data_as_of（可选）
                fd = fin.get("data_as_of")
                if fd:
                    fd_d = _p2(fd)
                    if fd_d and base_d and (base_d - fd_d).days > CHECK_DATA_STALENESS_DAYS:
                        stale_fields.append(f"财务数据({fd})")
                if stale_fields:
                    issues.append({"level": "warning", "field": "data_staleness", "value": stale_fields,
                                   "rule": f"以下数据距估值基准日 {as_of_date} 超过 {CHECK_DATA_STALENESS_DAYS} 天：{'、'.join(stale_fields)}（中证协第六条：数据原则上不超过 1 年，从严提示）"})
        return issues

    def asset_type_adapter(self):
        """资产类型适配（v2.4.0）：meta.asset_type ∈ startup/growth/mature/private → 方法适用性建议。
        仅提示不强制（DCF 权重仍由用户负责），缺省不提供 asset_type 不激活（旧输入零变化）。"""
        at = (self.d.get("meta") or {}).get("asset_type")
        if not at:
            return {"enabled": False}
        rule = ASSET_TYPE_RULES.get(at)
        if not rule:
            return {"enabled": True, "asset_type": at, "recognized": False,
                    "note": f"未知资产类型 {at}（可选 startup/growth/mature/private），未做适配"}
        warns = []
        if not rule["dcf_applicable"] and self.weights.get("dcf", 0) > 0:
            warns.append(f"资产类型 {at} 下 DCF 适用性低，但当前 dcf 权重 {self.weights['dcf']}，建议调降并加强 PS/融资锚。")
        if at == "private" and not (self.d.get("liquidity") or {}).get("enabled"):
            warns.append("非上市公司建议启用 liquidity（流动性折扣），以反映相对上市公司乘数的折价。")
        return {"enabled": True, "asset_type": at, "recognized": True,
                "dcf_applicable": rule["dcf_applicable"],
                "primary_methods": rule["primary_methods"],
                "warnings": warns, "note": rule["note"]}

    # ==================== v3.16.0 Layer 2：行业参数底座 ====================
    def industry_params_resolve(self):
        """Layer 2 行业参数底座（v3.16.0）：按 meta.industry / target_profile.segment 关键词匹配行业基准。
        作用有二：① 参数解析第 4 档来源（用户显式 > 公司历史 > 可比中位 > 行业基准 > 全局默认）；
        ② 校验锚（WACC 偏离区间 / 首年增速 vs 行业 ROIC / 倍数中枢偏离）。
        仅作校验与参照，不强制改值；preferences.industry_params=false 时关闭。"""
        if not self.pref.get("industry_params"):
            return {"enabled": False}
        db = _load_industry_params().get("industries", {})
        meta = self.d.get("meta") or {}
        tp = meta.get("target_profile") or {}
        hay = " ".join(str(x) for x in [meta.get("industry", ""), tp.get("segment", ""),
                                        meta.get("company", "")]).lower()
        # v2.14.1：改为「最长命中别名优先」（原先匹配先赢 → 泛化别名如「制造」抢占具体行业，
        # 如「酒、饮料和精制茶制造业」被「机械制造」命中、「电力设备」被「设备」命中）。
        matched, params = "default", db.get("default", {})
        best_len = 0
        for name, p in db.items():
            if name == "default":
                continue
            hit = 0
            for kw in (p.get("aliases") or []):
                k = str(kw or "").lower()
                if k and k in hay and len(k) > hit:
                    hit = len(k)
            if hit > best_len:
                matched, params, best_len = name, p, hit
        checks = []
        # 校验锚 1：WACC 模型值 vs 行业区间
        wacc_used = getattr(self, "_wacc_eff", None)
        wr = params.get("wacc_range")
        if wacc_used is not None and wr:
            if wacc_used < wr[0] - 0.005 or wacc_used > wr[1] + 0.005:
                checks.append({"rule": "wacc_vs_industry", "value": round(wacc_used, 4),
                               "range": wr, "level": "warning",
                               "msg": f"WACC {wacc_used:.1%} 偏离行业区间 {wr[0]:.0%}–{wr[1]:.0%}"})
        # 校验锚 2：首年增速 vs 行业 ROIC（增长须由再投资挣得）
        g1 = self._g1()
        roic = params.get("roic")
        if roic and g1 is not None and g1 > roic:
            checks.append({"rule": "growth_vs_roic", "value": round(g1, 4), "roic": roic, "level": "info",
                           "msg": f"首年增速 {g1:.1%} 高于行业 ROIC {roic:.0%}：高增长须由再投资支撑（g=ROIC×RR）"})
        # 校验锚 3：可比倍数中位 vs 行业中枢（偏离 >30%）
        try:
            comp = self.comparable_valuation()
            for key, med_key in (("pe_med", "pe"), ("ps_med", "ps")):
                base_v = params.get(key)
                got = (comp.get(med_key) or {}).get("median")
                if base_v and got and abs(got - base_v) / base_v > 0.30:
                    checks.append({"rule": f"{med_key}_vs_industry", "value": round(got, 2),
                                   "industry": base_v, "level": "info",
                                   "msg": f"可比 {med_key.upper()} 中位 {got:.1f}× 偏离行业中枢 {base_v}× 超 30%"})
        except Exception:
            pass
        return {
            "enabled": True, "matched_industry": matched,
            "params": {k: params.get(k) for k in ("beta_u", "wacc_range", "kd", "tax_rate", "g_lt",
                                                  "ebit_margin_steady", "roic", "nwc_to_rev", "capex_to_rev",
                                                  "pe_med", "ps_med", "ev_ebitda_med", "tg_cap", "half_life")},
            "checks": checks,
            "source": "assets/industry_params.json（Damodaran 行业库 + A 股实际）",
            "note": "行业参数为第 4 档来源与校验锚；参数优先级：用户显式 > 公司历史 > 可比中位 > 行业基准 > 全局默认",
        }

    # ==================== v3.17.0 P1：动态候选方法集 ====================
    def resolve_method_set(self, fw=None, lc=None):
        """P1 权重键集泛化（v3.17.0）：把写死的 {dcf, comparable, sentiment} 三路，
        扩展为「由 framework_check 路由动态输出」的候选方法集，替代主方法（nav/rim/ddm/rnpv/sotp）
        可携带权重进入综合，打破原「只减不换」。

        仅 preferences.method_set_mode="routed" 时激活；缺省 legacy → 返回 None（调用方走原三路，零变化）。
        系数口径：w_i = A_i（适用性）× R_i（可靠度）× D_i（独立度）× k_lifecycle_i，归一化后输出。
        - A_i：路由准入（dcf_weight_cap / 路由表 dcf_admissible）；替代方法按其是否为 recommended_primary 取 1.0/0.5
        - R_i：METHOD_MATURITY（方法成熟度）× 数据完整性
        - D_i：独立度——舆情与可比法共用 comp_v 基数，去相关后按 0.7 折减（B5 治理口径）
        """
        if self.method_set_mode != "routed":
            return None
        fw = fw if fw is not None else self.framework_admissibility()
        cls = (fw or {}).get("industry_class", "general") if fw.get("enabled") else "general"
        primary = (fw or {}).get("recommended_primary") if fw.get("enabled") else None
        cap = (fw or {}).get("dcf_weight_cap", 1.0) if fw.get("enabled") else 1.0
        # ---- 候选骨架：路由表 → 权重骨架；未命中回落「用户/默认三路」----
        skeleton = dict(ROUTE_METHOD_WEIGHTS.get(fw.get("route_key") or cls) or {})
        if not skeleton:
            skeleton = {"dcf": self.weights["dcf"], "comparable": self.weights["comparable"],
                        "sentiment": self.weights["sentiment"]}
        # 路由不允许 DCF 时，从骨架剔除（避免 cap=0 仍带 dcf 键产生与路由声明不符的候选集）
        if cap is not None and float(cap) <= 0 and "dcf" in skeleton and len(skeleton) > 1:
            drop = skeleton.pop("dcf")
            _rest = sum(skeleton.values()) or 1.0
            skeleton = {k: v + drop * (v / _rest) for k, v in skeleton.items()}
        completeness = self._data_completeness()
        lc_stage = (lc or {}).get("stage") if (lc or {}).get("enabled") else None
        k_life = LIFECYCLE_WEIGHT_FACTORS.get(lc_stage or "growth",
                                              {"dcf": 1.0, "comparable": 1.0, "sentiment": 1.0})
        raw, detail = {}, {}
        for m, base_w in skeleton.items():
            a = 1.0
            if m == "dcf" and cap is not None:
                a = min(1.0, float(cap)) if cap < 1.0 else 1.0          # DCF 封顶作为适用性上限
            if primary and m in ("rim", "ddm", "nav", "rnpv", "sotp"):
                # 替代方法：是路由推荐主方法 → 全额；否则降为交叉验证
                a = 1.0 if primary.startswith(m) else 0.5
            r = METHOD_MATURITY.get(m, 0.9) * (0.7 + 0.3 * completeness)
            d = 0.7 if m == "sentiment" else 1.0                        # 共用 comp_v 基数 → 去相关折减
            k = k_life.get(m if m in ("dcf", "comparable", "sentiment") else "dcf", 1.0)
            raw[m] = base_w * a * r * d * k
            detail[m] = {"base": round(base_w, 4), "A": round(a, 4), "R": round(r, 4),
                         "D": round(d, 4), "k_lifecycle": round(k, 4)}
        tot = sum(raw.values()) or 1.0
        resolved = {m: raw[m] / tot for m in raw}
        # ---- P6 权重包络校验：剔除「有权重但无取值分支」的方法，权重按比例回流 ----
        # ★只有当该方法确实不可计算时才剔除（COMPUTABLE_METHODS 白名单）。
        # 启用开关：preferences.method_weight_envelope（缺省 true —— 这是**纠错**而非新特性，
        # 因为原行为本身就是错的；但为严格零回归，缺省仅在 routed 模式下生效，legacy 不受影响）。
        envelope = []
        if self.method_weight_envelope:
            uncomputable = [m for m in list(resolved) if m not in COMPUTABLE_METHODS]
            if uncomputable:
                recycled = sum(resolved[m] for m in uncomputable)
                for m in uncomputable:
                    resolved.pop(m)
                if resolved:
                    target = next((t for t in WEIGHT_RECYCLE_PRIORITY if t in resolved), None)
                    if target:
                        resolved[target] = resolved[target] + recycled
                    else:
                        _tot = sum(resolved.values()) or 1.0
                        resolved = {k: v / _tot for k, v in resolved.items()}
                else:
                    resolved = {"comparable": 1.0}
                envelope = [{"method": m, "reason": "该方法尚无引擎取值分支（不在 COMPUTABLE_METHODS）",
                             "action": "权重回流"} for m in uncomputable]
        tot2 = sum(resolved.values()) or 1.0
        resolved = {m: v / tot2 for m, v in resolved.items()}
        return {
            "enabled": True, "mode": "routed",
            "industry_class": cls, "recommended_primary": primary, "dcf_weight_cap": cap,
            "candidates": list(resolved.keys()),
            "coefficient_detail": detail,
            "resolved_weights": {m: round(v, 4) for m, v in resolved.items()},
            "envelope_checks": envelope,
            "note": "P1 动态候选集：w = A（适用性）× R（可靠度）× D（独立度）× k_lifecycle，归一化；"
                    "替代主方法（nav/rim/ddm/rnpv/sotp）可携带权重进入综合；"
                    "P6 权重包络校验：无取值分支的方法权重回流（消除静默错算）",
        }

    # ==================== v3.16.0 Layer 0：前提判别门 ====================
    def framework_admissibility(self):
        """Layer 0 判别门（v3.16.0）：判定 DCF(FCFF/WACC) 框架是否准入。
        前提 A 现金流可定义/可预测；前提 B 资本结构≈融资选择（非经营要素）。
        输入 meta.framework_check{industry_class, interest_is_operating, regulated_capital, fcff_history[]}；
        industry_class 缺省由 meta.industry 关键词推断。仅 preferences.layer0_check=true 时激活（缺省关闭 → 零变化）。
        v3.17.0：方法自注册 self._framework（此前仅由 run() 赋值，直接调用时下游读到 None/stale）。"""
        out = self._framework_admissibility_impl()
        self._framework = out if out.get("enabled") else None
        return out

    def _framework_admissibility_impl(self):
        if not self.layer0_check:
            return {"enabled": False}
        fc = (self.d.get("meta") or {}).get("framework_check") or {}
        meta = self.d.get("meta") or {}
        hay = " ".join(str(x) for x in [meta.get("industry", ""), fc.get("industry_class", "")]).lower()
        # industry_class 推断（缺省 general）
        cls = fc.get("industry_class")
        matched_kw = None                      # v3.17.0 P3：命中关键词回显（审计可追溯）
        if not cls:
            if any(k in hay for k in ("银行", "保险", "证券", "券商", "金融")):
                cls = "financial"
                matched_kw = next(k for k in ("银行", "保险", "证券", "券商", "金融") if k in hay)
            elif any(k in hay for k in ("矿", "石油", "天然气", "煤炭", "资源")):
                cls = "resource"
                matched_kw = next(k for k in ("矿", "石油", "天然气", "煤炭", "资源") if k in hay)
            elif (any(k in hay for k in ("reit", "公用", "水务", "高速公路", "燃气", "电网"))
                  or ("电力" in hay and "设备" not in hay and "装备" not in hay)):
                # v3.16.2：收紧关键词——裸 "电力" 会误命中「电力设备/电力装备」（一般制造业），
                # 故仅当不含"设备/装备"时才判为 reit_utility（公用事业/重资产）
                # v2.14.6（技能 v3.16.17）：裸 "高速" 改 "高速公路"——**中文同形异义词**误命中：
                #   「高速」在电子/通信语境指 high-speed（高频高速覆铜板、高速接口、高速 SerDes），
                #   在交通语境指 highway（高速公路收费权，才是本关键词的本意）。生益科技（600183.SH）
                #   第 29 例暴露：meta.industry 写「高频高速覆铜板」→ 被误判 reit_utility
                #   （dcf_weight_cap 0.3、primary=nav），而该公司与收费公路毫无关系。
                #   ★残余风险（未修，待复核）：resource 的裸 "资源" 会误命中「人力资源服务」；
                #   pipeline_pharma 的裸 "生物" 会误命中「生物质能/生物农药」——两者尚无案例命中，
                #   暂不改动以免影响既有语义（改动须逐一评估），此处留痕备查。
                cls = "reit_utility"
            elif (any(k in hay for k in ("医药", "生物", "创新药"))
                  and (self.fin.get("revenue_latest_ttm") or 0) < EARLY_STAGE_REVENUE_THRESHOLD):
                cls = "pipeline_pharma"
            else:
                cls = "general"
        # ---- 前提 A：现金流可定义 / 可预测 ----
        interest_op = bool(fc.get("interest_is_operating"))
        hist = fc.get("fcff_history") or []
        neg_ratio, has_pos = None, True
        if len(hist) >= 3:
            vals = [float(x) for x in hist]
            neg_ratio = sum(1 for x in vals if x < 0) / len(vals)
            has_pos = any(x > 0 for x in vals)
        rev_years = len(self.fin.get("revenue_by_year") or {})
        ocf_years = len(self.fin.get("ocf_by_year") or {})
        data_ok = rev_years >= 3                                  # A4（判定用）：营收序列 ≥3 年
        cashflow_ok = (ocf_years >= 3 or self.fin.get("ocf_latest") is not None)  # A4 现金流证据
        a_fail = interest_op or (neg_ratio is not None and neg_ratio > 0.60)
        # ---- v3.17.0 P3：判据四维化（CV 波动率 / 终值占比 / ROIC−WACC），数据源均为现成字段 ----
        # 仅 preferences.layer0_extended=true 时参与判定；缺省关闭 → 只作证据留痕，不改 outcome（零变化）
        ext = bool(self.pref.get("layer0_extended"))
        cv_rev, tv_share, roic_v, wacc_v, g_vol = None, None, None, None, None
        # v3.17.0 P3：周期性的度量用「增长率波动」而非水平 CV（水平 CV 会把指数增长误判为周期）。
        # 阈值口径：真实周期行业（半导体/航运/化工/有色）营收增长率 σ_ln 通常 ≥ 0.60；
        # 高成长期公司的单次结构性跃升（如 3.9→17.1 亿，σ_ln≈46%）**不构成周期**，故阈值取 0.60。
        # 另要求**方向发生过反转**（至少一次负增长），纯单调高增长不算周期。
        has_neg_growth = False
        try:
            _vals = [float(v) for v in (self.fin.get("revenue_by_year") or {}).values()]
            if len(_vals) >= 3 and _mean(_vals):
                cv_rev = statistics.pstdev(_vals) / abs(_mean(_vals))
            if len(_vals) >= 4 and all(x > 0 for x in _vals):
                _logs = [math.log(_vals[i] / _vals[i - 1]) for i in range(1, len(_vals))]
                if len(_logs) >= 3:
                    g_vol = statistics.pstdev(_logs)     # 对数增长率标准差
                    has_neg_growth = any(x < 0 for x in _logs)
        except (TypeError, ValueError, ZeroDivisionError):
            cv_rev = None
        ip = self._industry or {}
        if ip.get("enabled"):
            roic_v = (ip.get("params") or {}).get("roic")
        if roic_v is None:
            roic_v = self.fin.get("roic")
        wacc_v = self.fin.get("wacc")
        if wacc_v is None:
            wm = (self._wacc_eff if hasattr(self, "_wacc_eff") else None)
            wacc_v = wm
        excess = None
        if isinstance(roic_v, (int, float)) and isinstance(wacc_v, (int, float)):
            excess = float(roic_v) - float(wacc_v)
        # v3.17.0 P3：强周期 = 增长率高波动（σ_ln > 0.60）**且**期间出现过负增长（方向反转）。
        # 单次结构性跃升（如宇树 3.93→17.08 亿，σ_ln≈46%）判为高成长而非周期。
        cyclical = bool((g_vol is not None and g_vol > 0.60 and has_neg_growth) or
                        (g_vol is None and cv_rev is not None and cv_rev > 1.50))
        A = {"pass": not a_fail,
             "evidence": {"A1_经营流可分离": not interest_op,
                          "A2_负FCFF占比": round(neg_ratio, 2) if neg_ratio is not None else None,
                          "A2_通过": not (neg_ratio is not None and neg_ratio > 0.60),
                          # v3.16.2：A3 由 A2 覆盖（全负→占比 100%>60% 必失败）；未提供历史时默认通过，
                          #         故 A3 不再独立 gate，仅作证据留痕
                          "A3_有正现金流史": has_pos if len(hist) >= 3 else "未提供历史(默认通过)",
                          "A4_数据完备(营收≥3年)": data_ok, "A4_现金流序列完备": cashflow_ok,
                          # v3.17.0 P3 新增三维
                          "A5_营收波动CV": round(cv_rev, 3) if cv_rev is not None else None,
                          "A5_增长率波动σ_ln": round(g_vol, 3) if g_vol is not None else None,
                          "A5_强周期": cyclical,
                          "A6_终值占比": round(tv_share, 3) if tv_share is not None else None,
                          "A7_超额回报(ROIC−WACC)": round(excess, 4) if excess is not None else None,
                          "A7_增长创造价值": (excess > 0) if excess is not None else None,
                          "营收年数": rev_years, "OCF年数": ocf_years}}
        # ---- 前提 B：资本结构≈融资选择 ----
        regulated = bool(fc.get("regulated_capital"))
        b_fail = regulated or interest_op
        B = {"pass": not b_fail,
             "evidence": {"B1_受监管资本约束": regulated, "B2_D/E可目标化": True,
                          "B3_利息归属经营成本": interest_op}}
        # ---- 路由判定（前提失败优先 → 行业类别 → 负现金流 → 兜底 general） ----
        if interest_op or regulated:
            key = "financial"                                  # 利息计入营业成本 / 受监管资本 → 金融业专属路由
        elif not A["pass"]:
            key = "negative_fcff"                              # A 失败：现金流不可定义/不可预测 → 概率加权
        elif cls in ("financial", "resource", "reit_utility", "pipeline_pharma", "holdco", "negative_fcff"):
            key = cls                                          # v3.17.0：negative_fcff 也属显式类别（不再依赖 neg_ratio 重算）
        elif neg_ratio is not None and neg_ratio > 0.60:
            key = "negative_fcff"
        else:
            key = "general"
        route = FRAMEWORK_ROUTES[key]
        dcf_adm = route["dcf_admissible"]
        cap = route["dcf_weight_cap"]
        primary = route["recommended_primary"]
        reason = route["reason"]
        # v3.16.2：A4 数据不完备（营收序列 <3 年）参与判定——一般行业由 full 降为 conditional（封顶 0.3）
        if dcf_adm is True and not data_ok:
            dcf_adm, cap = "conditional", min(cap, 0.3)
            reason = ("前提 A4 数据不完备（营收序列 <3 年）：DCF 条件准入（权重封顶 0.3），"
                      "建议补齐 3 年财务序列后再评估")
        # v3.17.0 P3：强周期在 layer0_extended 下由 full 降为 conditional（识别得出周期即须提要求）
        if ext and dcf_adm is True and cyclical:
            dcf_adm, cap = "conditional", min(cap, 0.5)
            reason = (f"前提 A5 强周期（营收 CV={cv_rev:.0%} > 30%）：DCF 条件准入（权重封顶 0.5），"
                      "建议先做周期中枢利润正常化（preferences.enable_normalized）")
        excess_note = None
        if ext and excess is not None and excess <= 0:
            excess_note = (f"超额回报 ROIC−WACC = {excess:+.2%} ≤ 0：增长毁灭价值，"
                           "增长率与估值呈负相关，敏感性方向须反向解读")
        return {
            "enabled": True, "industry_class": cls,
            "route_key": key,
            "precondition_A": A, "precondition_B": B,
            "dcf_admissible": dcf_adm,
            "recommended_primary": primary,
            "dcf_weight_cap": cap,
            "route_reason": reason,
            "matched_keywords": matched_kw,
            "extended_judgments": ({"cv_revenue": round(cv_rev, 4) if cv_rev is not None else None,
                                    "cyclical": cyclical,
                                    "roic_minus_wacc": round(excess, 4) if excess is not None else None,
                                    "growth_creates_value": (excess > 0) if excess is not None else None,
                                    "note": excess_note or "P3 扩展判据（CV/终值占比/ROIC−WACC）"}),
            "note": "Layer 0 前提判别门（v3.16.0）：false/conditional 时按 dcf_weight_cap 封顶 DCF 权重并路由替代模型；"
                    "v3.17.0 P3 增 CV/ROIC−WACC 判据与命中词回显",
        }

    # ==================== v3.16.0 Layer 1：生命周期判别 ====================
    def _cagr_3y(self):
        """营收 3 年复合增速（v3.26.0）：输入优先，缺输入时可由 revenue_by_year 反算。

        ★原实现的硬伤：`financials.cagr_3y` **从不自动计算**——全脚本 3 处引用全部是读取，
        没有一处从 `revenue_by_year` 推出来。于是输入不给该字段时，`classify_lifecycle()` 的
        `cagr is None` 一路落到最后的 `else`，判成 **growth（conf 0.55）**——对一家连续两年
        营收下滑的公司，这个结论比「误判为衰退」更荒谬。格力 R3 输入正是如此，只是被
        `meta.lifecycle_stage="mature"` 显式覆盖才没暴露。

        返回 (value, source)。`legacy` 口径只读输入（零回归）；`v326` 口径缺输入时反算。
        """
        v = self.fin.get("cagr_3y")
        if v is not None:
            return float(v), "explicit"
        if self.lifecycle_clf_mode != "v326":
            return None, "missing（legacy 口径不反算）"
        series = _series_from_year_dict(self.fin.get("revenue_by_year") or {})
        if len(series) < 4:
            return None, f"missing（revenue_by_year 仅 {len(series)} 期，需 ≥4 期算 3 年 CAGR）"
        base, last = series[-4], series[-1]
        if not base or base <= 0 or last is None:
            return None, "missing（营收基期非正或缺失）"
        return (float(last) / float(base)) ** (1.0 / 3.0) - 1.0, "revenue_3y（自动反算）"

    def _lifecycle_dim2(self):
        """第二维：盈利质量趋势 + 资本回报价差（v3.26.0）。

        为什么必须加这一维：营收 CAGR 是**一维剪影**，把三种完全不同的处境压成同一个"负号"——
        ① 周期性退坡（营收降、利润率升、ROIC>WACC，格力）；② 结构性衰退（营收降、利润率降、
        ROIC<WACC）；③ 主动砍低毛利业务（营收降、利润率升）。三者的 `μ₀`／`p`／终值口径全不同，
        用同一个 `decline` 配置对待会把仍能创造超额回报的公司当清算标的。

        - `margin_delta_pp`：`margin_history` 首末差（格力 12.28%→17.02% = **+4.74pp**）。
          该字段原本只被情景步长 `margin_sigma_step` 消费，判别层完全没用。
        - `roic_wacc_spread_pp`：价值创造分界，以 0 为界（不设人为阈值）。
        """
        mh = [float(x) for x in (self.fin.get("margin_history") or []) if x is not None]
        d_margin = (mh[-1] - mh[0]) if len(mh) >= 3 else None
        roic = self.fin.get("roic")
        wacc = self.fin.get("wacc")
        if wacc is None:
            wacc = getattr(self, "_wacc_eff", None)
        spread = (float(roic) - float(wacc)) if (roic is not None and wacc is not None) else None
        return {
            "margin_delta_pp": (round(d_margin * 100.0, 2) if d_margin is not None else None),
            "margin_first_last": ([round(mh[0], 4), round(mh[-1], 4)] if len(mh) >= 3 else None),
            "margin_periods": len(mh),
            "roic": roic, "wacc": (round(float(wacc), 4) if wacc is not None else None),
            "roic_wacc_spread_pp": (round(spread * 100.0, 2) if spread is not None else None),
            "thresholds": {"margin_pp": LIFECYCLE_DIM2_MARGIN_PP * 100.0,
                           "mild_cagr": LIFECYCLE_MILD_SHRINK_CAGR,
                           "spread_pp": 0.0},
        }

    def classify_lifecycle(self):
        """Layer 1 生命周期判别（v3.16.0；v3.26.0 加第二维）：三源优先级「用户显式 > 客观指标判别 > 兜底 growth」。
        指标：营收 CAGR / 净利率 / 亏损 / 营收规模 / 增速趋势(OLS)；v326 口径再叠加
        净利率趋势 + ROIC−WACC。
        仅 preferences.lifecycle_mode='auto' 时驱动增速模型；判别块本身在 auto 下挂出。"""
        if self.lifecycle_mode != "auto":
            return {"enabled": False}
        _v326 = (self.lifecycle_clf_mode == "v326")
        meta = self.d.get("meta") or {}
        explicit = meta.get("lifecycle_stage")
        cagr, cagr_src = self._cagr_3y()
        nm = self.fin.get("net_margin")
        loss = bool(self.fin.get("loss_making"))
        rev = self.fin.get("revenue_latest_ttm")
        cf = self.cashflow_statistics()
        trend = cf.get("trend_label") if cf.get("enabled") else None
        dim2 = self._lifecycle_dim2() if _v326 else None
        ev = {"cagr_3y": cagr, "cagr_source": cagr_src, "net_margin": nm,
              "loss_making": loss, "revenue_latest_ttm": rev, "trend_label": trend}
        if dim2 is not None:
            ev["dim2"] = dim2
        sub_stage, reason = None, None
        obj_conflict = None
        if explicit in LIFECYCLE_DEFAULTS:
            stage, src, conf = explicit, "用户显式", 1.0
            # 显式阶段仍给出客观维度的对照（不改 stage，只披露「若按客观判别会是什么」）
            if _v326:
                sub_stage, reason = self._sub_stage_from_dim2(cagr, dim2)
                # 显式与客观冲突须告警（不夺权：用户判断优先，但不能悄悄不一致）
                if stage == "decline" and sub_stage in ("cyclical_shrink", "mild_shrink", "steady"):
                    obj_conflict = (f"显式判衰退期，但客观第二维指向「{LIFECYCLE_SUB_LABELS[sub_stage]}」"
                                    f"（净利率 {dim2.get('margin_delta_pp')}pp、"
                                    f"ROIC−WACC {dim2.get('roic_wacc_spread_pp')}pp）")
                elif stage in ("mature", "growth") and sub_stage == "structural_decline":
                    obj_conflict = (f"显式判{LIFECYCLE_STAGE_LABELS[stage]}，但客观第二维指向"
                                    f"「结构性衰退」（净利率 {dim2.get('margin_delta_pp')}pp、"
                                    f"ROIC−WACC {dim2.get('roic_wacc_spread_pp')}pp）")
                if obj_conflict:
                    self.warnings.append(f"生命周期判别冲突：{obj_conflict}；已按显式阶段执行，请复核。")
        else:
            if _v326:
                stage, sub_stage, conf, reason = self._classify_v326(cagr, loss, rev, dim2)
                if sub_stage == "structural_decline":
                    stage = "decline"
                elif sub_stage in ("cyclical_shrink", "mild_shrink", "ambiguous_shrink"):
                    stage = "mature"
            else:
                if loss and (rev is None or rev < EARLY_STAGE_REVENUE_THRESHOLD):
                    stage, conf = "startup", 0.80
                elif cagr is not None and cagr < 0:
                    stage, conf = "decline", 0.72
                elif cagr is not None and cagr >= 0.08 and (not loss or (rev or 0) >= EARLY_STAGE_REVENUE_THRESHOLD):
                    stage, conf = "growth", 0.85
                elif cagr is not None and 0 <= cagr < 0.08 and not loss:
                    stage, conf = "mature", 0.72
                else:
                    stage, conf = "growth", 0.55
                # legacy 口径不产 sub_stage（保证 note 文本与 v3.25.0 逐字相同）
            src = "客观判别"
            if trend in ("上行", "下行"):
                conf = min(0.95, conf + 0.05)
        at = meta.get("asset_type")
        legacy_map = {"startup": "startup", "growth": "growth", "mature": "mature"}
        inconsistent = bool(at in legacy_map and legacy_map[at] != stage)
        if not _v326:
            # legacy 文本口径逐字保留（零回归：报告层按此断言）
            note = f"{LIFECYCLE_STAGE_LABELS.get(stage, stage)}（{src}）："
            note += f"CAGR={cagr:.0%}，" if isinstance(cagr, (int, float)) else "CAGR=n/a，"
            note += f"净利率={nm:.1%}，亏损={loss}，趋势={trend}"
            if inconsistent:
                note += f"；与输入 asset_type={at} 不一致，已按规则覆盖"
        else:
            note = f"{LIFECYCLE_STAGE_LABELS.get(stage, stage)}"
            if sub_stage:
                note += f"·{LIFECYCLE_SUB_LABELS.get(sub_stage, sub_stage)}"
            note += f"（{src}）："
            if isinstance(cagr, (int, float)):
                note += f"CAGR={cagr:.2%}（{cagr_src}），"
            else:
                note += f"CAGR=n/a（{cagr_src}），"
            note += f"净利率={nm:.1%}，亏损={loss}，趋势={trend}"
            if dim2:
                if (dim2.get("margin_delta_pp") is not None
                        and dim2.get("roic_wacc_spread_pp") is not None):
                    note += (f"；第二维：净利率 {dim2['margin_delta_pp']:+.2f}pp、"
                             f"ROIC−WACC {dim2['roic_wacc_spread_pp']:+.2f}pp")
                else:
                    note += "；第二维：数据不足（需 margin_history ≥3 期、roic 与 wacc）"
            if reason:
                note += f"。判定依据：{reason}"
            if inconsistent:
                note += f"；与输入 asset_type={at} 不一致，已按规则覆盖"
        out = {"enabled": True, "stage": stage, "stage_label": LIFECYCLE_STAGE_LABELS.get(stage, stage),
               "source": src, "confidence": round(conf, 2), "explicit": explicit,
               "evidence": ev, "inconsistent_with_asset_type": inconsistent,
               "config": LIFECYCLE_DEFAULTS.get(stage), "note": note}
        if _v326:
            out["classifier_mode"] = "v326"
            out["sub_stage"] = sub_stage
            out["sub_stage_label"] = LIFECYCLE_SUB_LABELS.get(sub_stage, sub_stage)
            out["reason"] = reason
            out["objective_conflict_with_explicit"] = obj_conflict
        return out

    def damodaran_stage(self, lc=None):
        """v3.28.0：由 v326 四阶段 + 子类 + 亏损/规模，派生达莫达兰六阶段。

        映射规则（确定性、可审计，逐条对应达莫达兰的阶段定义）：
          stage=startup                      → 1 初创期（亏损且营收 < 5 亿：只有想法、没有收入）
          亏损且营收 ≥ 5 亿                   → 2 年轻成长（Revenue exists but losses dominate）★跨 stage 覆盖
          stage=growth 且 (sub=high_growth 或 CAGR ≥ 15%) → 3 高速成长
          stage=growth 且 CAGR < 15%          → 4 成熟成长（增速已落 high-single/low-double）
          stage=mature                       → 5 成熟稳定（含 cyclical_shrink/mild_shrink：仍在创造 FCF）
          stage=decline                      → 6 衰退期
        ★「亏损且营收≥5亿」优先于 stage 判定：v326 只在「亏损且营收<5亿」判 startup，
        故「有收入但仍亏损」的公司会被判成 growth/mature，而达莫达兰口径它明确是 Stage 2。
        这是六阶段比四阶段更严的地方，也是本表最主要的增量信息。
        """
        lc = lc if lc is not None else (getattr(self, "_lifecycle", None) or {})
        if not lc.get("enabled"):
            return {"enabled": False, "stage": None, "label": None,
                    "reason": "生命周期判别未启用（lifecycle_mode≠auto），无阶段可派生"}
        ev = lc.get("evidence") or {}
        stage = lc.get("stage")
        sub = lc.get("sub_stage")
        loss = bool(ev.get("loss_making"))
        rev = ev.get("revenue_latest_ttm")
        cagr = ev.get("cagr_3y")
        # v3.29.1：判定顺序修复——原「亏损 + 营收≥5 亿 → 年轻成长」写在 decline 之前，
        # 会把「营收下滑、ROIC<WACC、仍在亏损」的衰退企业重新判成 Stage 2（DCF 权重 0.45→0.30、
        # 显式期 4→10 年）。达莫达兰 Stage 2 的定义前提是 "revenues are growing"，
        # 收缩中的亏损不属于此列。故：结构证据（v326 decline）优先于盈利符号（亏损）。
        _guard = None
        if stage == "startup":
            d, why = "startup", f"v326 判初创期（亏损且营收 {rev} 低于 5 亿），对应达莫达兰「只有想法、没有收入」"
        elif stage == "decline":
            d, why = "decline", f"v326 判衰退期（{lc.get('reason') or '结构性收缩'}）"
            if loss:
                _guard = ("亏损但营收在收缩（结构性衰退），未按「有收入仍亏损」归入年轻成长："
                          "达莫达兰 Stage 2 的前提是收入仍在增长")
        elif loss and isinstance(rev, (int, float)) and rev >= EARLY_STAGE_REVENUE_THRESHOLD \
                and not (isinstance(cagr, (int, float)) and cagr < 0):
            d, why = ("young_growth",
                      f"亏损（净利率 {ev.get('net_margin')}）但营收 {rev:.2f} 亿 ≥ 5 亿、"
                      f"增速 {cagr:.2%} 未转负：收入已存在、亏损仍主导，达莫达兰口径为「年轻成长」而非初创")
            if isinstance(cagr, (int, float)) and cagr < DAMODARAN_STAGE2_MIN_CAGR:
                _guard = (f"营收增速仅 {cagr:.2%}、低于 {DAMODARAN_STAGE2_MIN_CAGR:.0%}，"
                          "与 Stage 2「收入仍在较快增长」的典型形态有距离，建议 LLM 复核"
                          "是否实为「成熟期盈利崩塌」")
        elif stage == "growth":
            if isinstance(cagr, (int, float)) and cagr >= DAMODARAN_HIGH_GROWTH_CAGR:
                d = "high_growth"
                why = (f"营收 CAGR {cagr:.2%} ≥ {DAMODARAN_HIGH_GROWTH_CAGR:.0%}，"
                       "落在达莫达兰「高速成长」（增长 + 衰减两阶段）区间")
            else:
                d = "mature_growth"
                _c = f"{cagr:.2%}" if isinstance(cagr, (int, float)) else "n/a"
                why = (f"营收 CAGR {_c} 低于 {DAMODARAN_HIGH_GROWTH_CAGR:.0%}，"
                       "落在 high-single/low-double 区间，达莫达兰口径为「成熟成长」（增速趋稳、FCF 转正）")
                if sub == "high_growth":
                    why += ("；★与 v326 的 high_growth 标签不一致：v326 用 8% 线（「相对 A 股整体较快」），"
                            "达莫达兰 15% 线针对的是生命周期形态（增长是否仍在加速），二者不是同一把尺，"
                            "本表按达莫达兰口径执行")
        elif stage == "mature":
            d, why = "mature_stable", f"v326 判成熟期（{lc.get('sub_stage_label') or '稳态'}），对应「成熟稳定」"
        else:
            d = "mature_stable"
            why = f"阶段 {stage} 无达莫达兰对应档，保守回落「成熟稳定」"
        return {"enabled": True, "stage": d, "label": DAMODARAN_STAGE_LABELS.get(d, d),
                "weights": dict(DAMODARAN_STAGE_WEIGHTS.get(d) or {}),
                "evidence": DAMODARAN_STAGE_EVIDENCE.get(d) or {},
                "v326_stage": stage, "v326_sub_stage": sub,
                "cagr_3y": cagr, "reason": why,
                "guard": _guard,
                "note": "v3.28.0 达莫达兰六阶段方法定位表：阶段 → 三路径直接权重（行内和为 1），"
                        "替代 k_lifecycle 乘数；仅在 preferences.lifecycle_weight_mode='damodaran_table' 时生效"}

    def _sub_stage_from_dim2(self, cagr, dim2):
        """v326 第二维判别（纯判定，不做 stage 赋值）。返回 (sub_stage, reason)。

        A×B 四象限 + C 裁决：
            营收↓ 净利率↑ ROIC>WACC  → cyclical_shrink（收缩但不衰退；格力）
            营收↓ 净利率↓ ROIC<WACC  → structural_decline（真衰退）
            营收↓ 净利率↑ ROIC<WACC  → ambiguous_shrink（利润靠一次性/财务收益，须 LLM 复核）
        """
        if cagr is None:
            return "unknown", "营收 CAGR 不可得，第二维无法判别"
        d_mar = (dim2 or {}).get("margin_delta_pp")
        spread = (dim2 or {}).get("roic_wacc_spread_pp")
        d_mar_frac = (d_mar / 100.0) if d_mar is not None else None
        spread_frac = (spread / 100.0) if spread is not None else None
        thr = LIFECYCLE_DIM2_MARGIN_PP
        if cagr < 0:
            if d_mar_frac is not None and d_mar_frac > thr and spread_frac is not None and spread_frac > 0:
                return ("cyclical_shrink",
                        f"营收 {cagr:.2%} 下滑但净利率 {d_mar:+.2f}pp、"
                        f"ROIC 高于 WACC {spread:+.2f}pp —— 量降价升，资本仍在创造超额回报，"
                        f"属周期退坡或结构优化，非需求永久性消失")
            if d_mar_frac is not None and d_mar_frac < -thr and spread_frac is not None and spread_frac < 0:
                return ("structural_decline",
                        f"营收 {cagr:.2%} 下滑且净利率 {d_mar:+.2f}pp、"
                        f"ROIC 低于 WACC {spread:+.2f}pp —— 量价齐跌、资本被毁灭，符合衰退期定义")
            if d_mar_frac is not None and d_mar_frac < -thr:
                # 利润在恶化、但资本回报仍高于 WACC：两条证据打架，不得按规则强行归到
                # mild_shrink（会把「利润率掉了 9pp」也当轻度收缩）或 decline（会否定仍存在的超额回报）
                return ("ambiguous_shrink",
                        f"营收 {cagr:.2%} 下滑、净利率 {d_mar:+.2f}pp 亦在恶化，"
                        f"但 ROIC 相对 WACC 为 {spread if spread is not None else 'n/a'}pp —— "
                        f"量价背离，须由 LLM 判定是周期底部的利润率压缩还是份额流失初期的价格战")
            if abs(cagr) < LIFECYCLE_MILD_SHRINK_CAGR and (spread_frac is None or spread_frac > 0):
                return ("mild_shrink",
                        f"营收仅 {cagr:.2%}（低个位数收缩，未达衰退量级），"
                        f"净利率变动 {d_mar if d_mar is not None else 'n/a'}pp 落在 ±{thr*100:.0f}pp 噪声带内，"
                        f"ROIC 未见跌破 WACC")
            if spread_frac is not None and spread_frac > 0:
                return ("ambiguous_shrink",
                        f"营收 {cagr:.2%} 下滑、ROIC 仍高于 WACC {spread:+.2f}pp，"
                        f"但净利率变动 {d_mar if d_mar is not None else 'n/a'}pp 未形成同向证据 —— "
                        f"须由 LLM 结合订单/政策/份额归属，不得按规则强行归类")
            return ("ambiguous_shrink",
                    f"营收 {cagr:.2%} 下滑，但缺净利率历史或 ROIC/WACC，第二维证据不足")
        if cagr >= 0.08:
            return "high_growth", f"营收 CAGR {cagr:.2%} ≥ 8%"
        return "steady", f"营收 CAGR {cagr:.2%} 处于 0–8% 稳态区间"

    def _classify_v326(self, cagr, loss, rev, dim2):
        """v326 客观判别：先排除初创，再按第二维拆收缩/衰退。返回 (stage, sub, conf, reason)。"""
        if loss and (rev is None or rev < EARLY_STAGE_REVENUE_THRESHOLD):
            return ("startup", "early_loss", 0.80,
                    f"亏损且营收 {rev} 低于初创门槛，判初创期")
        sub, reason = self._sub_stage_from_dim2(cagr, dim2)
        _conf = {"cyclical_shrink": 0.75, "structural_decline": 0.75, "mild_shrink": 0.68,
                 "ambiguous_shrink": 0.55, "high_growth": 0.85, "steady": 0.72,
                 "unknown": 0.55}.get(sub, 0.55)
        if cagr is None:
            # cagr 不可得时不得假装能判：保持旧兜底，但显式标注证据不足
            return ("growth", "unknown", 0.55, reason)
        stage = ("decline" if sub == "structural_decline"
                 else ("growth" if sub == "high_growth" else "mature"))
        return (stage, sub, _conf, reason)

    def assumptions_summary(self, base, wacc_m, cf_stats, tri, fcfr, ld):
        """关键假设汇总块（v2.4.0）：报告'关键假设'章节数据源——汇总 DCF 与市场法全部关键参数
        及来源（显式/模型/三角校准），与引擎输出一一对应，可审计。始终挂出（纯汇总，不改数值）。"""
        dcf = base["dcf"]
        has_gf = bool(self.fin.get("growth_forecast"))
        # v2.14.2：WACC 来源标注修正——原逻辑只要 wacc_params.enabled 就标「CAPM 模型」，
        # 但引擎实际始终「显式 wacc 优先、CAPM 仅作校验」。当两者并存且偏差显著时，
        # 报告会出现「WACC 8.5%（CAPM 模型）」与风险提示「CAPM 模型值 5.96%」自相矛盾（比亚迪案例）。
        _wacc_src = "用户显式" if self.fin.get("wacc") is not None else "默认 11%"
        if wacc_m.get("enabled"):
            _dev = wacc_m.get("deviation_pp")
            if self.fin.get("wacc") is not None:
                _wacc_src = ("显式给定 ｜ CAPM 校验偏差 %+.2fpp" % _dev) if isinstance(_dev, (int, float)) else "显式给定"
            else:
                _wacc_src = "CAPM 模型"
        # v3.21.0 A2/A3：tg 来源标注不再硬编码「默认 6%」，改读常量 + 取值链
        if self._tg_meta and self._tg_meta.get("picked"):
            _pick_lbl = {"user_explicit": "用户显式", "industry_g_lt": "行业 g_lt",
                         "inflation_anchor": "通胀锚"}.get(self._tg_meta["picked"], self._tg_meta["picked"])
            _tg_src = f"取值链·{_pick_lbl}"
        elif self.fin.get("terminal_growth") is not None:
            _tg_src = "用户显式"
        elif tri.get("enabled") and getattr(self, "_tg_eff", None) is not None:
            _tg_src = "三角校准"
        else:
            _tg_src = ("默认 6%" if self.tg_default_mode == "legacy_6pct"
                       else f"默认 {self._tg_default():.0%}（{self.tg_default_mode}）")
        # v3.24.0（F1）：比率法未被采用且未计算时，`fcf_ratio` 必须为 None 并说明「未使用」——
        # 原实现会回落成 `ocf_to_net_profit` 并标来源「OCF/净利」，等于**报告里打出一个假数**
        # （读者会以为主口径用了它，实际用的是三表联立）。
        _fcfr_skipped = bool(fcfr.get("skipped"))
        _fcfr_switch = fcfr.get("switched_to") or self._fcf_basis or "报表驱动"
        _dcf_block = {
            "wacc": dcf.get("wacc"),
            "wacc_source": _wacc_src,
            "beta_source": wacc_m.get("beta_source") if wacc_m.get("enabled") else None,
            "terminal_growth": dcf.get("terminal_growth"),
            "tg_source": _tg_src,
            "fcf_ratio": (None if _fcfr_skipped else
                          (fcfr.get("used") if fcfr.get("enabled")
                           else (self.fin.get("ocf_to_net_profit") or 0.9))),
            "fcf_source": (f"未计算：FCFF 口径={_fcfr_switch}（比率法未被采用）" if _fcfr_skipped else
                           ("披露现金流/净利" if fcfr.get("source") == "披露现金流/净利"
                            else ("用户显式" if fcfr.get("source") == "用户显式"
                                  else ("三层校准" if fcfr.get("enabled") else "OCF/净利")))),
            "growth_source": ("三角校准" if tri.get("enabled") and not has_gf
                              else ("用户显式" if has_gf else "默认")),
            "implied_growth": tri.get("implied_growth") if tri.get("enabled") else None,
            "implied_terminal_growth": tri.get("implied_terminal_growth") if tri.get("enabled") else None,
        }
        # v3.21.0：增速参数体系的四项披露（仅启用时挂出 → 旧输入 assumptions_summary 键集合不变）
        if self._tg_meta:
            _dcf_block["tg_chain"] = self._tg_meta
        # v3.25.0：三锚口径留痕（opt-in；缺省不挂出 → 旧 assumptions_summary 键集合不变）
        if self._tg_meta2:
            _dcf_block["tg_anchors_v2"] = self._tg_meta2
        if dcf.get("growth_model"):
            _dcf_block["growth_model"] = dcf["growth_model"]
        if dcf.get("growth_seq_detail"):
            _dcf_block["growth_seq_detail"] = dcf["growth_seq_detail"]
        if self.tv_share_guard:
            _dcf_block["tv_share_grade"] = dcf.get("tv_share_grade")
        if self.tg_scenario_mode == "stepped":
            _dcf_block["scenario_tg_adj_pp"] = dict(self.scenario_tg_adj_pp)
            _dcf_block["scenario_tg_used"] = {
                k: dcf.get("terminal_growth") for k in ("base",)}
        if self._growth_step_cache and self._growth_step_cache.get("applied"):
            _dcf_block["scenario_step"] = self._growth_step_cache
        if self.growth_history_mode == "advisory" and getattr(self, "_history_shape", None):
            _dcf_block["growth_history_shape"] = self._history_shape
        if self.growth_path_mode != "legacy_truncate":
            _dcf_block["growth_path_mode"] = self.growth_path_mode
        if self.growth_terminal_mode != "asymptotic":
            _dcf_block["growth_terminal_mode"] = self.growth_terminal_mode
        if self.mature_n_mode != "table":
            _dcf_block["lifecycle_mature_n_mode"] = self.mature_n_mode
        if self.growth_shape_mode != "legacy":
            _dcf_block["growth_shape_mode"] = self.growth_shape_mode
        # v3.23.0：现金流模型细节层四项披露（仅启用时挂出 → 旧输入键集合不变）
        if self.discount_timing != "year_end":
            _dcf_block["discount_timing"] = self.discount_timing
        if self._size_premium_meta:
            _dcf_block["size_premium"] = self._size_premium_meta
        if self._capex_check_meta:
            _dcf_block["capex_check"] = self._capex_check_meta
        if self._gf_rule:
            _dcf_block["growth_base_rule"] = self._gf_rule
        if self._margin_step_cache and self._margin_step_cache.get("applied"):
            _dcf_block["margin_step"] = self._margin_step_cache
        if self._reinv_check is not None:
            _dcf_block["reinvestment_check"] = self._reinv_check
        if self._normalization_hint_meta:
            _dcf_block["normalization_hint"] = self._normalization_hint_meta
        return {
            "dcf": _dcf_block,
            "market": {
                "multiple_medians": {k: base["comparable"].get(k, {}).get("median")
                                     for k in ("pe", "ps", "ev_ebitda", "pb") if base["comparable"].get(k)},
                "liquidity_discount": ld.get("discount_pct") if ld.get("enabled") else None,
                "industry_index_pe": (self.idx.get("pe_median") if self.idx else None),
            },
            "note": "关键假设汇总（assumptions_summary）：与报告'关键假设'章节一一对应；source 标注来源，便于审计",
        }

    def anchor_bayesian_update(self, mid, bear_val, bull_val):
        """贝叶斯锚定（v2.7.0 C1，v3.6b 批次 3）：外部价格锚（发行价/最近融资/交易对价）→ 情景权重贝叶斯更新。
        先验 = scenario_weights；似然 L_i = exp(−(v_i−anchor)²/(2σ²))，σ = anchor×sigma_pct（缺省 10%）；
        后验 w_i' ∝ w_i×L_i 归一化；锚定中枢 new_mid = Σ w_i'×v_i。
        与主结果并列输出（审计原则：主结果不变，锚定值为外部信号修正参照）。
        preferences.anchor_update 缺省未启用 → 零变化。"""
        cfg = self.pref.get("anchor_update")
        if not cfg or not isinstance(cfg, dict) or not cfg.get("enabled"):
            return {"enabled": False}
        anchor = cfg.get("anchor_value")
        if anchor is None:
            return {"enabled": False, "note": "anchor_update 已启用但缺 anchor_value"}
        anchor = float(anchor)
        sigma_pct = float(cfg.get("sigma_pct", 0.10) or 0.10)
        sigma = max(1.0, anchor * sigma_pct)
        atype = str(cfg.get("anchor_type", "external"))
        vals = {"bear": float(bear_val), "base": float(mid), "bull": float(bull_val)}
        prior = {k: float(self.scen_w.get(k, 0.0)) for k in vals}
        like = {k: math.exp(-((v - anchor) ** 2) / (2.0 * sigma * sigma)) for k, v in vals.items()}
        denom = sum(prior[k] * like[k] for k in vals)
        post = {k: (prior[k] * like[k] / denom) if denom else prior[k] for k in vals}
        new_mid = sum(post[k] * vals[k] for k in vals)
        delta = (new_mid - mid) / mid * 100.0 if mid else None
        self.warnings.append(
            f"贝叶斯锚定：外部锚 {anchor:.0f} 亿（{atype}，σ={sigma:.0f}）→ 锚定中枢 {new_mid:.0f} 亿（原 {mid:.0f} 亿，Δ{delta:+.1f}%），主结果不变。")
        return {
            "enabled": True, "anchor_value": round(anchor, 2), "anchor_type": atype,
            "sigma_pct": sigma_pct, "sigma": round(sigma, 2),
            "prior": {k: round(v, 4) for k, v in prior.items()},
            "likelihood": {k: round(v, 6) for k, v in like.items()},
            "posterior": {k: round(v, 4) for k, v in post.items()},
            "original_mid": round(mid, 2), "anchored_mid": round(new_mid, 2),
            "delta_pct": round(delta, 2) if delta is not None else None,
            "note": "贝叶斯锚定（先验=情景权重，似然=N(情景值|锚,σ)）：主结果不变，锚定中枢为外部价格信号修正参照",
        }

    def cashflow_statistics(self):
        """历史序列统计特征（v2.2.0）。序列优先级：fcf_by_year → ocf_by_year → revenue_by_year；不足 3 年不激活。"""
        rev = self.fin.get("revenue_by_year") or {}
        series, series_used = None, ""
        for name, d in (("FCF", self.fin.get("fcf_by_year") or {}),
                        ("OCF", self.fin.get("ocf_by_year") or {}),
                        ("营收", rev)):
            if len(d) >= 3:
                series = _series_from_year_dict(d)
                series_used = name
                break
        if series is None or len(series) < 3:
            return {"enabled": False, "note": "历史序列不足 3 年（需 revenue_by_year 至少 3 年）"}
        gs = [series[i] / series[i - 1] - 1.0 for i in range(1, len(series))]
        mean_g = sum(gs) / len(gs)
        geo_g = _geo_mean_growth(series)
        std_g = (sum((g - mean_g) ** 2 for g in gs) / (len(gs) - 1)) ** 0.5 if len(gs) > 1 else 0.0
        cv = std_g / abs(mean_g) if mean_g else None
        slope, r2 = _ols_slope_r2(list(range(1, len(gs) + 1)), gs)
        if slope is not None and r2 is not None:
            if abs(slope) < 0.02 and r2 < 0.5:
                trend = "稳定"
            elif slope >= 0.02:
                trend = "上行"
            elif slope <= -0.02:
                trend = "下行"
            else:
                trend = "波动"
        else:
            trend = "数据不足"
        # v2.5.0 B2：营收序列近似时显式标注（未提供 FCF/OCF 序列）
        approx_note = "" if series_used in ("FCF", "OCF") else "（未提供 FCF/OCF 序列，现金流波动以营收增速近似）"
        return {"enabled": True, "series_used": series_used, "n": len(series),
                "mean_growth": round(mean_g, 4),
                "geometric_growth": round(geo_g, 4) if geo_g is not None else None,
                "std_growth": round(std_g, 4), "cv": round(cv, 4) if cv is not None else None,
                "ols_slope": round(slope, 4) if slope is not None else None,
                "r_squared": round(r2, 4) if r2 is not None else None,
                "trend_label": trend, "note": f"基于{series_used}序列（{len(series)} 年）{approx_note}"}

    def _comparable_growth_median(self):
        """可比公司增速中位数（v2.5.0 B3：1%/99% winsorize 截尾后再 IQR 剔除，防概念溢价可比抬高截面中位）。"""
        gs = [c["growth_pct"] for c in self.comp if c.get("growth_pct")]
        if not gs:
            return None
        gs_w = _winsorize(gs)
        if len(gs_w) >= 3 and self.exclude_outliers:
            keep, _ = iqr_filter(gs_w, list(range(len(gs_w))))
            return _median(keep) if keep else _median(gs_w)
        return _median(gs_w)

    def growth_triangulation(self, cf_stats=None):
        """增长假设三角校准（v2.2.0）：自身历史 CAGR + 可比增速中位 + 行业增速 → 隐含营收/永续增长率。
        用户显式 growth_forecast/terminal_growth 优先；未显式时引擎采用三角值。"""
        cfg = self.pref.get("growth_weights") or {}
        w_self, w_cmp, w_ind = cfg.get("self"), cfg.get("comparable"), cfg.get("industry")
        if w_self is None and w_cmp is None and w_ind is None:
            w_self, w_cmp, w_ind = DEFAULT_GROWTH_WEIGHTS["self"], DEFAULT_GROWTH_WEIGHTS["comparable"], DEFAULT_GROWTH_WEIGHTS["industry"]
        self_cagr = (cf_stats or {}).get("geometric_growth") if cf_stats else None
        ind_g = self.idx.get("index_growth_pct")
        ind_lt = self.idx.get("index_long_term_growth")
        cmp_med = self._comparable_growth_median()
        # 可用项归一化
        items = [("self", self_cagr, w_self),
                 ("comparable", cmp_med / 100.0 if cmp_med else None, w_cmp),
                 ("industry", ind_g / 100.0 if ind_g is not None else None, w_ind)]
        avail = [(k, v, w) for k, v, w in items if v is not None and w is not None]
        if not avail:
            return {"enabled": False, "note": "三角校准缺数据（需自身历史 CAGR/可比增速/行业增速至少一项）"}
        total_w = sum(w for _, _, w in avail)
        implied = max(0.0, min(1.0, sum(v * w for _, v, w in avail) / total_w))
        # 永续增速：向行业长期增速收敛（可比为短期增速，乘长期化系数 0.3）
        # v3.11 公开锚：行业长期增速受 GDP 上限约束、以 10Y 国债+通胀保底（公开市场数据估计）
        pub = TERMINAL_GROWTH_PUBLIC
        lt_base = ind_lt / 100.0 if ind_lt is not None else None
        if lt_base is not None:
            lt_base = max(pub["rf_anchor"], min(lt_base, pub["gdp_cap"]))
        tg_terms = []
        if self_cagr is not None:
            tg_terms.append(("self", min(self_cagr, lt_base if lt_base is not None else 0.06) * 0.5, w_self))
        if lt_base is not None:
            tg_terms.append(("industry", lt_base, w_ind))
        if cmp_med is not None:
            # v3.11：可比短期增速长期化后仍须受 GDP 上限约束（防周期峰值增速抬高永续）
            tg_terms.append(("comparable", min((cmp_med / 100.0) * 0.3, pub["gdp_cap"]), w_cmp))
        tg_avail = [(k, v, w) for k, v, w in tg_terms if v is not None and w is not None]
        implied_tg = None
        tg_public = None
        if tg_avail:
            tw = sum(w for _, _, w in tg_avail)
            implied_tg = max(0.02, min(0.10, sum(v * w for _, v, w in tg_avail) / tw))
        if lt_base is not None:
            tg_public = max(pub["rf_anchor"], min(lt_base, pub["gdp_cap"]))
        return {"enabled": True,
                "self_cagr": round(self_cagr, 4) if self_cagr is not None else None,
                "comparable_median_growth": round(cmp_med, 2) if cmp_med is not None else None,
                "industry_growth": round(ind_g, 2) if ind_g is not None else None,
                "implied_growth": round(implied, 4),
                "implied_terminal_growth": round(implied_tg, 4) if implied_tg is not None else None,
                "public_anchor_tg": round(tg_public, 4) if tg_public is not None else None,
                "growth_weights_used": {k: round(w, 4) for k, _, w in avail},
                "note": "用户显式 growth_forecast/terminal_growth 优先，三角值作参照；永续增速受 GDP 上限约束（min(行业长期,4.5%)）并以 10Y 国债+通胀 3.9% 保底（公开锚）"}

    # ==================== v3.21.0：成熟期增速参数体系（A2/A3/A4/A5/A7/B2/B4）====================
    def _tg_default(self):
        """A2：永续增速缺省值（legacy 6% / cva_2pct 2%）。缺省 legacy → 旧输入逐位不变。"""
        return TERMINAL_GROWTH_DEFAULT_MODES.get(self.tg_default_mode,
                                                 DEFAULT_TERMINAL_GROWTH)

    def resolve_terminal_growth(self, tri=None):
        """A3/A4：永续增速取值链重构——把四套并存的数字收敛成一条可解释的链。

        原实现的 tg 由三个偶然因素决定：用户填没填、三角校准有没有腿、行业 `g_lt` 是否被消费
        （实测全库 0 处消费 → 家电 `g_lt=3%` 是死参数）。`legacy` 模式下三角值与 `g_lt` 均不参与
        取值（三角值只作告警参照），`chain` 模式下按「用户显式 > 行业 g_lt > 通胀锚」逐级回落，
        三角校准值**降级为校验参照**（|tg − 三角值| > 1pp 才告警，不改值）。

        返回 {mode, picked, value, industry, capped_by, chain[], validation}；legacy 返回 None（不挂出）。
        """
        if self.tg_basis != "chain":
            return None
        pub = TERMINAL_GROWTH_PUBLIC
        gdp_cap = pub["gdp_cap"]
        inflation_anchor = pub["inflation"]
        chain = []
        user_tg = self.fin.get("terminal_growth")
        ind_g_lt = ((self._industry or {}).get("params") or {}).get("g_lt")
        ind_name = (self._industry or {}).get("matched_industry")

        picked, value, capped_by, industry = None, None, None, None
        if user_tg is not None:
            picked, value = "user_explicit", float(user_tg)
            if value > gdp_cap:
                capped_by = gdp_cap
                value = gdp_cap
                self.warnings.append(
                    f"永续增速 {float(user_tg):.2%} 超过长期名义 GDP 上限 {gdp_cap:.2%}，"
                    f"已压至上限；如确有依据请补充 terminal_growth_rationale。")
            chain.append({"rank": 1, "source": "user_explicit", "raw": round(float(user_tg), 4),
                          "value": round(value, 4), "hit": True})
        else:
            chain.append({"rank": 1, "source": "user_explicit", "raw": None, "value": None, "hit": False})

        if picked is None and ind_g_lt is not None:
            raw = float(ind_g_lt)
            value = max(inflation_anchor, min(raw, gdp_cap))
            picked, industry = "industry_g_lt", ind_name
            if value != raw:
                capped_by = gdp_cap if raw > gdp_cap else inflation_anchor
            chain.append({"rank": 2, "source": "industry_g_lt", "industry": ind_name,
                          "raw": round(raw, 4), "value": round(value, 4), "hit": True})
        else:
            chain.append({"rank": 2, "source": "industry_g_lt",
                          "raw": round(float(ind_g_lt), 4) if ind_g_lt is not None else None,
                          "value": None, "hit": False})

        if picked is None:
            picked, value = "inflation_anchor", inflation_anchor
            chain.append({"rank": 3, "source": "inflation_anchor", "raw": inflation_anchor,
                          "value": round(inflation_anchor, 4), "hit": True})
        else:
            chain.append({"rank": 3, "source": "inflation_anchor", "raw": inflation_anchor,
                          "value": None, "hit": False})

        # 三角校准值降为校验参照（不参与取值）
        validation, implied = None, (tri or {}).get("implied_terminal_growth")
        if implied is not None:
            dev_pp = (value - implied) * 100.0
            validation = {"implied_terminal_growth": implied, "deviation_pp": round(dev_pp, 2),
                          "alert": abs(dev_pp) > 1.0,
                          "note": "三角校准值仅作校验参照（|偏差|>1pp 告警），不参与 tg 取值"}
            if abs(dev_pp) > 1.0:
                self.warnings.append(
                    f"永续增速取值 {value:.2%} 与三角参照 {implied:.2%} 偏离 {dev_pp:+.2f}pp，需补充依据。")
        return {"mode": "chain", "picked": picked, "value": round(value, 4),
                "industry": industry, "capped_by": capped_by, "chain": chain,
                "gdp_cap": gdp_cap, "inflation_anchor": inflation_anchor,
                "validation": validation,
                "note": "取值链：用户显式 > 行业 g_lt（clamp [通胀锚, GDP 上限]）> 通胀锚；三角值仅校验"}

    # ==================== v3.25.0：增长率建模（建议书 §3.1 / §3.3）====================
    def resolve_terminal_growth_v2(self, tri=None, wacc=None):
        """v3.25.0：永续增速「三锚取中 + 双上限」（建议书 §3.3）。

        与 A3/A4 的 `resolve_terminal_growth()`（chain 模式）并存但口径不同：
        - `chain`：**单来源逐级回落**（用户 > 行业 g_lt > 通胀锚），值取决于"哪一级先命中"；
        - `v2`：**多来源交叉**（行业 g_lt / 市场隐含 g* / SGR 各算一个，取中位），再双上限夹逼。

        三锚的取舍：
        - `industry_g_lt`：行业长期增速（结构锚）
        - `implied_market`：由 EV/EBITDA 与 WACC 反解的隐含永续增速（市场定价锚）；
          **仅在解为正时参与**——残值为负说明市场隐含的是收缩，不能当中位锚之一
        - `sgr = ROIC×(1−payout)`：可持续增长率（结构硬约束，防"挣不到的增长"）

        双上限：`min(gdp_cap 4.5%, WACC − spread_min 3pp)`；双下限：`max(0, cfg.floor)`。
        缺省不激活（`financials.terminal_growth_model.enabled` 缺省 False）→ 逐位零回归。
        """
        cfg = self.fin.get("terminal_growth_model") or {}
        if not cfg.get("enabled"):
            return None
        caps = cfg.get("caps") or {}
        gdp_cap = float(caps.get("gdp_cap", TERMINAL_GROWTH_PUBLIC["gdp_cap"]))
        spread_min = float(caps.get("spread_min", 0.03))
        floor = float(cfg.get("floor", 0.0))
        want = [str(x) for x in (cfg.get("anchors")
                                 or ["industry_g_lt", "implied_market", "sgr"])]
        anchors, skipped = {}, {}

        if "industry_g_lt" in want:
            glt = ((self._industry or {}).get("params") or {}).get("g_lt")
            if glt is None:
                skipped["industry_g_lt"] = "行业参数未命中（industry_params 无该类目 g_lt）"
            else:
                anchors["industry_g_lt"] = round(float(glt), 4)

        if "implied_market" in want:
            imp = (tri or {}).get("implied_terminal_growth")
            if imp is None:
                skipped["implied_market"] = "三角校准未产出 implied_terminal_growth"
            elif float(imp) <= 0:
                skipped["implied_market"] = f"反解 {float(imp):.2%} ≤ 0（残值非正），不参与"
            else:
                anchors["implied_market"] = round(float(imp), 4)

        if "sgr" in want:
            roic = self.fin.get("roic")
            if roic is None:
                skipped["sgr"] = "缺 financials.roic"
            else:
                payout, psrc = self.fin.get("payout_ratio"), "explicit"
                if payout is None:
                    # 不猜分红率：取 0 使 SGR = ROIC（上界最宽），并留痕说明
                    payout, psrc = 0.0, "missing→0（SGR 退化为 ROIC 上界）"
                payout = max(0.0, min(0.95, float(payout)))
                anchors["sgr"] = round(float(roic) * (1.0 - payout), 4)
                anchors["_sgr_payout_src"] = psrc

        payout_src = anchors.pop("_sgr_payout_src", None)
        if not anchors:
            return {"enabled": True, "applied": False, "anchors": {}, "skipped_anchors": skipped,
                    "reason": "三锚均不可用（缺行业参数 / 隐含解非正 / 缺 ROIC）"}

        combine = str(cfg.get("combine", "median"))
        vals = sorted(anchors.values())
        raw = float(_median(vals)) if combine == "median" else sum(vals) / float(len(vals))

        g_cap_eff, cap_side = gdp_cap, "gdp_cap"
        if wacc is not None and (float(wacc) - spread_min) < g_cap_eff:
            g_cap_eff, cap_side = float(wacc) - spread_min, "spread"
        value, capped_by = raw, None
        if value > g_cap_eff:
            value, capped_by = g_cap_eff, cap_side
        elif value < floor:
            value, capped_by = floor, "floor"

        out = {
            "enabled": True, "applied": True, "mode": "anchors_v2",
            "anchors": {k: v for k, v in anchors.items() if not k.startswith("_")},
            "skipped_anchors": skipped, "combine": combine,
            "raw": round(raw, 4), "value": round(value, 4),
            "caps": {"gdp_cap": gdp_cap, "spread_min": spread_min,
                     "wacc": (round(float(wacc), 4) if wacc is not None else None),
                     "effective_cap": round(g_cap_eff, 4), "cap_side": cap_side},
            "floor": floor, "capped_by": capped_by,
            "spread": (round(float(wacc) - value, 4) if wacc is not None else None),
            "sgr_payout_source": payout_src,
            "note": "三锚取中位 → clamp[floor, min(gdp_cap, WACC−spread_min)]；不采用 6%/2% 双轨缺省",
        }
        # spread 脆性告警：原实现只校验 tg < WACC，6%/8.14% 这种 spread 仅 2.14pp 的区间无提示
        if out["spread"] is not None and out["spread"] < spread_min:
            _k = ("tgv2_spread", round(value, 4), round(float(wacc), 4))
            if _k not in self._tg_warned:
                self._tg_warned.add(_k)
                self.warnings.append(
                    f"永续增速 {value:.2%} 与 WACC {float(wacc):.2%} 的 spread 仅 "
                    f"{out['spread'] * 100:.2f}pp（< {spread_min * 100:.0f}pp 经验下限），"
                    f"Gordon 终值进入脆性区——±50bp 参数误差即可动估值 20% 以上。")
        return out

    def _gm_first_year(self, cfg):
        """L1–L7 首年增速分级（建议书 §3.2）：只向上取最可靠一级，不跨级混合。"""
        if cfg.get("g1") is not None:
            return float(cfg["g1"]), "explicit"
        basis = str(cfg.get("first_basis", "auto"))
        gf_first = None
        gf = self.fin.get("growth_forecast") or {}
        if isinstance(gf, dict) and gf:
            gf_first = float(list(gf.values())[0])
        elif isinstance(gf, (list, tuple)) and gf:
            gf_first = float(gf[0])
        if basis == "auto":
            if gf_first is not None:
                # 用户路径首年。**不冒充实测**——真实可靠性由输入侧决定（本案两家为中报+H2 推导=L3）
                return gf_first, "user_path"
            shape = getattr(self, "_gf_rule", None)
            if shape and shape.get("applied"):
                return float(shape["base_growth"]), "shape_rule"
            return float(self._g1()), "fallback"
        if basis == "shape_rule":
            shape = getattr(self, "_gf_rule", None)
            if shape and shape.get("applied"):
                return float(shape["base_growth"]), "shape_rule"
            return float(self._g1()), "fallback"
        if gf_first is not None:
            return gf_first, basis
        return float(self._g1()), "fallback"

    def _gm_mu0(self, cfg, tg):
        """中期锚 mu0：扩张份额 / 守份额 / 让份额，四种取值模式。"""
        if cfg.get("mu0") is not None:
            return float(cfg["mu0"]), "explicit"
        mode = str(cfg.get("mu0_mode", "tg_default"))
        glt = ((self._industry or {}).get("params") or {}).get("g_lt")
        if mode == "industry_g_lt":
            if glt is not None:
                return float(glt), "industry_g_lt"
            return float(tg), "tg_default（fallback：行业参数未命中）"
        if mode == "industry_share":
            share = self.fin.get("share_drift") or {}
            if glt is not None and share.get("enabled"):
                d = max(-0.05, min(0.05, float(share.get("delta_ratio", 0.0))))
                return (1.0 + float(glt)) * (1.0 + d) - 1.0, "industry_share"
            return float(tg), "tg_default（fallback：缺份额漂移序列）"
        if mode == "median_anchor":
            h = self._history_shape or {}
            if h.get("metrics"):
                return float(h["metrics"]["median"]), "median_anchor"
            return float(tg), "tg_default（fallback：无历史增速序列）"
        return float(tg), "tg_default"

    def _mature_n_override(self, stage):
        """v3.27.0：成熟期显式期长度的显式覆盖（返回 None 表示沿用 LIFECYCLE_DEFAULTS 表值）。

        三档语义：`table`（缺省，6 年）／`legacy_4`（v3.21.0 前旧行为 4 年）／
        `cva_7`（B3 试点口径 7 年）。只对 mature 生效，其余阶段一律返回 None。
        """
        if stage != "mature":
            return None
        m = self.mature_n_mode
        if m == "legacy_4":
            return 4
        if m == "cva_7":
            return 7
        return None

    def growth_model_schedule(self, tg, n_hint=None):
        """v3.25.0：状态空间分解增速路径（建议书 §3.1）。缺省不激活。

        优先级高于 `cva_matrix`、低于用户显式 `growth_forecast`（除非 override_manual=true）。
        """
        cfg = self.fin.get("growth_model") or {}
        if not cfg.get("enabled"):
            return None
        g1, g1_src = self._gm_first_year(cfg)
        mu0, mu0_src = self._gm_mu0(cfg, tg)

        # 显式期长度：显式 n > 生命周期表值（v3.27.0：10/8/6/4）> 5
        n = int(cfg.get("n") or 0)
        if not n:
            stage = (self._lifecycle or {}).get("stage")
            n = int((LIFECYCLE_DEFAULTS.get(stage) or {}).get("n", 5))
            _ov = self._mature_n_override(stage)
            if _ov:
                n = _ov
        if n_hint:
            n = int(n_hint)

        # SGR 上限（bounds.sgr 缺省 true；ROIC 缺失则不约束）
        sgr, sgr_src = None, "not_applied"
        bounds_cfg = cfg.get("bounds") or {}
        if bool(bounds_cfg.get("sgr", True)):
            roic = self.fin.get("roic")
            if roic is not None:
                payout = self.fin.get("payout_ratio")
                payout = 0.0 if payout is None else max(0.0, min(0.95, float(payout)))
                sgr, sgr_src = float(roic) * (1.0 - payout), "roic×(1−payout)"
            else:
                sgr_src = "缺 financials.roic"

        # 历史 σ（pp）：用于 shock 标记
        sigma_pp = None
        h = self._history_shape or {}
        if h.get("metrics"):
            sigma_pp = float(h["metrics"]["sigma_pp"])

        seq, det = space_state_growth_schedule(
            g1=g1, mu0=mu0, tg=tg, n=n,
            p=cfg.get("p"),
            kappa=cfg.get("kappa"),
            cap_life_years=cfg.get("cap_life_years"),
            sgr=sgr,
            gdp_cap=float(bounds_cfg.get("gdp_cap", TERMINAL_GROWTH_PUBLIC["gdp_cap"])),
            floor=bounds_cfg.get("floor"),
            hist_sigma_pp=sigma_pp,
            # 约束⑤ 只对「真锚」（行业 g_lt / 份额漂移 / 历史中位）生效。
            # μ0 缺省取 tg 时它不是判断结论，而是"没有中期判断"的占位——此时若因
            # |tg − g1| > 5pp 就退化为 g1，等于把趋势层从"向 tg 收敛"改成"直接等于 g1"，
            # 反而抹掉了趋势层（格力 −7.6% 首年、tg 2% 时差 9.6pp 即会误触发）。
            mu0_div_max_pp=(cfg.get("mu0_div_max_pp")
                            if not str(mu0_src).startswith("tg_default") else 1e9),
        )
        det.update({"enabled": True, "g1_source": g1_src, "mu0_source": mu0_src,
                    "sgr_source": sgr_src,
                    "override_manual": bool(cfg.get("override_manual"))})
        if g1_src in ("fallback",):
            self.warnings.append(
                "增长率模型：首年增速落到 fallback 档（无实际数、无形态表值），"
                "路径首年非实测，报告须标注。")
        if det.get("mu0_degraded"):
            _k = ("gm_mu0_deg", round(float(det.get("mu0_input") or 0), 4), round(g1, 4))
            if _k not in self._tg_warned:
                self._tg_warned.add(_k)
                self.warnings.append(
                    f"增长率模型：中期锚 μ0={det['mu0_input']:.2%} 与首年 {g1:.2%} 偏离超过 "
                    f"{GROWTH_MODEL_DEFAULTS['mu0_div_max_pp']:.0f}pp，已退化为 μ0=g1（防 V 型非单调路径）。")
        return seq, det

    def _growth_step(self):
        """B4：情景增速步长——固定 ±10pp 会让 bear 首年增速突破历史极值。

        格力历史三年 +7.93/−7.26/−9.89（σ=9.62pp），±10pp 使 bear g1 = −12.00%，比历史最差
        （−9.89%）还差 2.1pp，等于用情景标签制造了从未发生过的假设。CVA 口径按 σ 定步长并
        clamp 到 [2, 5]pp。缺省 `fixed` 逐位不变。
        """
        if self.scenario_step_mode != "cva_sigma":
            return {"mode": "fixed", "step_pp": 10.0, "applied": False}
        if self._growth_step_cache is not None:
            return self._growth_step_cache
        rev = self.fin.get("revenue_by_year") or {}
        vals = _series_from_year_dict(rev)
        g = [vals[i] / vals[i - 1] - 1.0 for i in range(1, len(vals)) if vals[i - 1]]
        if len(g) < 3:
            self.warnings.append(
                f"情景步长 σ 口径要求近三年增速（现有 {len(g)} 期），已回退固定 ±10pp。")
            self._growth_step_cache = {"mode": "cva_sigma", "step_pp": 10.0, "applied": False,
                                       "fallback": "历史不足 3 期"}
            return self._growth_step_cache
        tail = g[-3:]
        sigma_pp = statistics.stdev(tail) * 100.0
        step = max(2.0, min(5.0, sigma_pp))
        self._growth_step_cache = {
            "mode": "cva_sigma", "applied": True, "sigma_pp": round(sigma_pp, 2),
            "raw_step_pp": round(sigma_pp, 2), "step_pp": round(step, 2),
            "clamp_pp": [2.0, 5.0], "history_growth": [round(x, 4) for x in tail],
            "note": "步长 = clamp(近三年增速 σ, 2pp, 5pp)；避免 bear 突破历史极值",
        }
        return self._growth_step_cache

    def growth_rule(self):
        """D4：历史形态 → 基准增速取值矩阵（CVA 口径，仅用户未给 growth_forecast 时生效）。

        与 B2 的分工：B2 只判形态（advisory），本方法把形态映射成**建议基准值**并接入计算，
        使「判出持续下降却仍用 20% 兜底」不再发生。用户显式路径永不覆盖。
        不可取平均的形态（正负切换/负增长震荡/样本不足）→ 保持兜底并强制披露。
        """
        if self.growth_base_rule != "cva_matrix":
            return None
        if self._gf_rule is not None:
            return self._gf_rule
        if self.fin.get("growth_forecast"):
            self._gf_rule = {"mode": "cva_matrix", "applied": False,
                             "reason": "用户已提供 growth_forecast，取值矩阵不覆盖"}
            return self._gf_rule
        vals = _series_from_year_dict(self.fin.get("revenue_by_year") or {})
        hist = [vals[i] / vals[i - 1] - 1.0 for i in range(1, len(vals)) if vals[i - 1]]
        shape = growth_history_shape(hist)
        rule = growth_base_from_history(shape)
        out = {"mode": "cva_matrix", "history_case": shape.get("history_case"),
               "history": [round(x, 4) for x in hist[-3:]], **rule}
        self._gf_rule = out
        if rule.get("applied"):
            self.warnings.append(
                f"未提供 growth_forecast：按历史形态「{shape.get('history_case')}」取基准增速 "
                f"{rule['base_growth']:.2%}（CVA 取值矩阵：{rule['rule']}）；"
                f"该值为引擎自动基准，如有订单/产能证据请显式给出 growth_forecast。")
        else:
            self.warnings.append(
                f"未提供 growth_forecast 且历史形态为「{shape.get('history_case')}」："
                f"{rule.get('reason')}；已保持兜底增速，请在报告中披露该假设来源。")
        return out

    def margin_step(self):
        """D5：利润率情景步长（历史 σ clamp[1,3]pp）——与收入增速步长分开。"""
        if self.margin_step_mode != "cva_sigma":
            return {"mode": "off", "applied": False}
        if self._margin_step_cache is not None:
            return self._margin_step_cache
        hist = self.fin.get("margin_history") or []
        res = margin_sigma_step(hist if isinstance(hist, list) else list(hist.values()))
        res["mode"] = "cva_sigma"
        if not res.get("applied"):
            self.warnings.append("利润率步长 σ 口径需 margin_history ≥3 期，已保持原情景调整。")
        self._margin_step_cache = res
        return res

    def implied_terminal_growth_market(self, dcf):
        """A7：市场隐含永续增速反解——把「市场不接受这个估值」翻译成「市场在假设什么」。

        用 base 情景的显式期现值与净现金，反解使 EV 成立的 g*：
        `residual_tv_pv = 市值 − 净现金 − 显式期现值`，再对 Gordon 反解 g*。
        `residual_tv_pv ≤ 0` → 无解（显式期现值已超市场 EV，分歧不在永续假设）。
        缺省 `implied_tg_market=false` 不挂出。
        """
        if not self.implied_tg_market:
            return None
        mcap = None
        for src in (self.fin.get("market_cap"), (self.d.get("meta") or {}).get("market_cap")):
            if src:
                mcap = float(src)
                break
        if mcap is None:
            px, sh = self.fin.get("price"), self.fin.get("total_shares_after_issue")
            if px and sh:
                mcap = float(px) * float(sh)
        pv_sum = _nn(dcf.get("pv_sum"), 0.0)
        net_cash = _nn(self.fin.get("net_cash"), 0.0)
        wacc = _nn(dcf.get("wacc"), DEFAULT_WACC)
        n = len(dcf.get("growth_seq") or []) or 5
        if mcap is None:
            return {"enabled": True, "solvable": False, "note": "缺市值/股价，无法反解"}
        residual = mcap - net_cash - pv_sum
        out = {"enabled": True, "market_cap": round(mcap, 2), "pv_sum": round(pv_sum, 2),
               "net_cash": round(net_cash, 2), "residual_tv_pv": round(residual, 2),
               "wacc": round(wacc, 4), "n_explicit": n}
        if residual <= 0:
            out.update({"solvable": False, "implied_g": None,
                        "verdict": "无经济解（显式期现值已超市场 EV，分歧不在永续假设）"})
            return out
        # Gordon 反解：residual = fcf_n × (1+g)/(wacc−g) / (1+wacc)^n
        fcf_n = _nn(dcf.get("fcf0"), 0.0)
        for gr in (dcf.get("growth_seq") or []):
            fcf_n *= (1.0 + gr)
        if fcf_n <= 0:
            out.update({"solvable": False, "implied_g": None,
                        "verdict": "末期现金流为负，g* 无经济含义"})
            return out
        denom = residual * ((1.0 + wacc) ** n)
        # denom = fcf_n(1+g)/(wacc−g) → g = (denom·wacc − fcf_n)/(denom + fcf_n)
        g_star = (denom * wacc - fcf_n) / (denom + fcf_n)
        cap = TERMINAL_GROWTH_PUBLIC["gdp_cap"]
        if g_star < -0.05:
            verdict = "市场隐含 g* < −5%：市场按长期收缩定价，分歧不在永续假设而在现金流路径"
        elif g_star > cap:
            verdict = f"市场隐含 g* > GDP 上限 {cap:.1%}：市场在定价超长期增长，须复核现金流假设"
        else:
            verdict = "市场隐含 g* 落在经济可解释区间，可通过永续假设对齐市场预期"
        out.update({"solvable": True, "implied_g": round(g_star, 4), "terminal_fcf": round(fcf_n, 2),
                    "gdp_cap": cap, "verdict": verdict})
        return out

    def industry_index_valuation(self, comp_base=None):
        """行业指数可比信息（v2.2.0）：隐含估值与可比法交叉验证（偏差>30% 提示）；可比<3家时降级基准。
        对应中证协'行业指标法仅用于检验'定位，不并入综合权重。"""
        idx = self.idx
        if not idx or not any(idx.get(k) for k in ("pe_median", "ps_median", "pb_median")):
            return {"enabled": False}
        rev = _nn(self.fin.get("revenue_latest_ttm"), 0.0)
        profit = rev * (self.fin.get("net_margin") or 0.0)
        net_assets = self.fin.get("net_assets")
        implied = {}
        if idx.get("pe_median") and profit > 0:
            implied["pe"] = round(profit * idx["pe_median"], 2)
        if idx.get("ps_median") and rev > 0:
            implied["ps"] = round(rev * idx["ps_median"], 2)
        if idx.get("pb_median") and net_assets:
            implied["pb"] = round(net_assets * idx["pb_median"], 2)
        if not implied:
            return {"enabled": False, "note": "行业指数无可计算乘数（需 pe/ps/pb_median 且对应财务字段）"}
        base = round(sum(implied.values()) / len(implied), 2)
        dev = (base - comp_base) / comp_base if comp_base else None
        if dev is not None and abs(dev) > 0.30:
            self.warnings.append(f"可比法与行业指数隐含值偏差 {dev:+.0%}，建议审查可比选择。")
        return {"enabled": True, "name": idx.get("name", ""), "implied_values": implied,
                "base_value": base,
                "vs_comparable_deviation": round(dev, 4) if dev is not None else None,
                "note": "行业指数仅作交叉验证/降级基准，不并入综合权重"}

    def sentiment_structured(self):
        """舆情结构化（v2.2.0）：events/policy 聚合为 impact_map（假设层调整）。
        与 sentiment_adjust（市场口径 ±10%）分层；risks severity=high 时 Bear 情景 WACC 额外 +0.5pp。"""
        s = self.sent
        events = s.get("events") or []
        policy = s.get("policy") or []
        risks = s.get("risks") or []
        orient = s.get("investor_orientation") or {}
        if not (events or policy or risks or orient):
            return {"enabled": False}
        imp_w = {"high": 1.0, "medium": 0.6, "low": 0.3}
        sign = {"positive": 1.0, "negative": -1.0, "利好": 1.0, "利空": -1.0, "中性": 0.0}
        nets = {"growth": 0.0, "margin": 0.0, "wacc": 0.0, "multiple": 0.0, "terminal": 0.0}
        evidence = {"growth": [], "margin": [], "wacc": [], "multiple": [], "terminal": []}
        for e in events:
            tgt = e.get("impact_target", "growth")
            if tgt not in nets:
                continue
            w = imp_w.get(e.get("importance", "low"), 0.3)
            pct = float(e.get("impact_pct", 0) or 0)
            sgn = sign.get(e.get("impact_direction", ""), 0.0)
            nets[tgt] += w * pct * sgn
            if e.get("title"):
                evidence[tgt].append(e["title"])
        for p in policy:
            tgt = p.get("impact_target", "growth")
            if tgt not in nets:
                continue
            pct = float(p.get("impact_pct", 0) or 0)
            sgn = sign.get(p.get("direction", "中性"), 0.0)
            nets[tgt] += pct * sgn
            if p.get("policy"):
                evidence[tgt].append(p["policy"])
        impact_map = {
            "growth_adj_pp": round(max(-15.0, min(15.0, nets["growth"])), 2),
            "margin_adj_pp": round(max(-15.0, min(15.0, nets["margin"])), 2),
            "wacc_adj_pp": round(max(-2.0, min(2.0, nets["wacc"])), 2),
            "multiple_factor": round(max(0.8, min(1.2, 1.0 + nets["multiple"] / 100.0)), 4),
            "terminal_growth_adj_pp": round(max(-15.0, min(15.0, nets["terminal"])), 2),
            "evidence": {k: v for k, v in evidence.items() if v},
            "note": "假设层调整（v2.2.0），与 sentiment_adjust 市场口径修正分层；用户显式参数优先",
        }
        risks_summary = [{"type": r.get("type", ""), "description": r.get("description", ""),
                          "severity": r.get("severity", "low"), "impact_target": r.get("impact_target", "margin")}
                         for r in risks]
        return {"enabled": True, "impact_map": impact_map, "risks_summary": risks_summary,
                "orientation": orient, "note": "舆情结构化（v3.3）"}

    # ========== v2.0：增量维度量化（论文三维度 + 因子校准） ==========
    def quality_score(self):
        """盈利质量评分卡（0-100，基准 60）。明细全部留痕。

        v2.11.3 修复：任一指标输入为 null（模板允许的「未披露」状态）时，原实现
        `fin.get(k, default)` 在 key 存在但值为 None 时返回 None 并参与数值比较，
        触发 TypeError 使引擎整体崩溃。现改为：显式 None → 该指标记 0 分并在明细中
        标记 missing=True（缺失不加分也不扣分），非 None 路径逐位保持原逻辑（旧输入零变化）。
        """
        fin = self.fin

        def _v(key, default):
            """取数值型指标；None/非数值 → 返回 (None, True) 表示未披露。"""
            raw = fin.get(key, default)
            if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return None, True
            return float(raw), False

        items = {}
        ocf, m = _v("ocf_to_net_profit", 0.9)
        items["ocf_to_net_profit"] = (
            ocf if not m else None, 0.30, m,
            +10 if ocf is not None and ocf >= 0.9 else
            (+5 if ocf is not None and ocf >= 0.6 else
             (0 if ocf is not None and ocf >= 0.3 else (-10 if ocf is not None else 0))))
        gm_trend, m = _v("gross_margin_trend_pp", 0.0)
        items["gross_margin_trend_pp"] = (
            gm_trend if not m else None, 0.20, m,
            +5 if gm_trend is not None and gm_trend >= 3 else
            (0 if gm_trend is not None and gm_trend >= -3 else (-5 if gm_trend is not None else 0)))
        rec, m = _v("receivables_to_revenue", 0.25)
        items["receivables_to_revenue"] = (
            rec if not m else None, 0.20, m,
            +5 if rec is not None and rec < 0.20 else
            (0 if rec is not None and rec <= 0.35 else (-5 if rec is not None else 0)))
        gw, m = _v("goodwill_ratio", 0.0)
        items["goodwill_ratio"] = (
            gw if not m else None, 0.15, m,
            +5 if gw is not None and gw < 0.10 else
            (0 if gw is not None and gw <= 0.30 else (-10 if gw is not None else 0)))
        nr, m = _v("nonrecurring_ratio", 0.0)
        items["nonrecurring_ratio"] = (
            nr if not m else None, 0.15, m,
            +5 if nr is not None and nr < 0.05 else
            (0 if nr is not None and nr <= 0.15 else (-10 if nr is not None else 0)))

        score = QUALITY_SCORE_DEFAULT
        detail = []
        for key, (raw, w, missing, pts) in items.items():
            score += w * pts
            entry = {"indicator": key, "value": raw, "weight": w, "points": pts}
            if missing:
                entry["missing"] = True
                entry["note"] = "输入未提供（null）→ 记 0 分，不参与加分/扣分"
            detail.append(entry)
        adj = (score - QUALITY_SCORE_DEFAULT) / 40.0 * 0.10  # ±10%
        missing_n = sum(1 for _, (_, _, mi, _) in items.items() if mi)
        out = {"score": round(score, 1), "adjustment_pct": round(adj, 4), "detail": detail,
               "components_score": round(sum(w * p for _, (_, w, _, p) in items.items()), 1),
               "missing_indicators": missing_n}
        if missing_n:
            out["note"] = (f"{missing_n}/5 项质量指标输入缺失（null），已按 0 分处理；"
                           "缺失项不参与加分，评分卡对本案的区分度相应下降。")
        return out

    def goodwill_adjust(self):
        """商誉折价概率化分级（论文「商誉」维度，v2.0 替代一刀切）。"""
        gw = self.fin.get("goodwill_ratio", 0.0) or 0.0
        if gw < 0.10:
            return 0.0, "无显著商誉风险"
        if gw < 0.15:
            return -0.02, f"商誉占比 {gw:.0%}：小幅风险，关注业绩承诺"
        if gw < 0.30:
            return -0.05, f"商誉占比 {gw:.0%}：中等风险，减值概率上升"
        return -0.08, f"商誉占比 {gw:.0%}：高风险，减值可能显著冲击利润"

    # ==================== v3.17.0 P2/P4：舆情修正层 + 信号强度内生 + 带宽分化 ====================
    def sentiment_band(self, lc=None):
        """P4 舆情修正带宽（v3.17.0）：按企业类型分化，替代固定 ±10%。
        仅 preferences.sentiment_band_mode="typed" 时启用；缺省 fixed → 恒 0.10（零变化）。
        优先级：强周期（CV 高）> 金融/资源路由 > 生命周期阶段 > asset_type > default。"""
        if self.sentiment_band_mode != "typed":
            return 0.10, "固定 ±10%（sentiment_band_mode=fixed）"
        fw = self._framework or {}
        cls = fw.get("industry_class") if fw.get("enabled") else None
        at = (self.d.get("meta") or {}).get("asset_type")
        # 强周期识别：优先用 framework_check 已算出的增长波动 σ_ln（口径统一），否则本地重算
        g_vol = None
        _ex_ev = ((fw.get("precondition_A") or {}).get("evidence") or {})
        if isinstance(_ex_ev.get("A5_增长率波动σ_ln"), (int, float)):
            g_vol = _ex_ev["A5_增长率波动σ_ln"]
        else:
            try:
                vals = [float(v) for v in (self.fin.get("revenue_by_year") or {}).values()]
                if len(vals) >= 4 and all(x > 0 for x in vals):
                    logs = [math.log(vals[i] / vals[i - 1]) for i in range(1, len(vals))]
                    if len(logs) >= 3:
                        g_vol = statistics.pstdev(logs)
            except (TypeError, ValueError, ZeroDivisionError):
                g_vol = None
        if g_vol is not None and g_vol > 0.60:
            # 与 framework_check 同口径：σ_ln > 0.60 且出现过负增长才算强周期
            _vals2 = [float(v) for v in (self.fin.get("revenue_by_year") or {}).values()]
            _neg = any(_vals2[i] < _vals2[i - 1] for i in range(1, len(_vals2)))
            if _neg:
                return SENTIMENT_BAND["cyclical"], f"强周期（增长率σ_ln={g_vol:.0%}，有负增长）→ ±{SENTIMENT_BAND['cyclical']:.0%}"
        if cls == "financial":
            return SENTIMENT_BAND["financial"], "金融路由 → ±5%"
        if cls in ("resource", "reit_utility"):
            return SENTIMENT_BAND["financial"], f"{cls} 路由（资产锚）→ ±5%"
        stage = (lc or {}).get("stage") if (lc or {}).get("enabled") else None
        # 显式 asset_type / stage / class 兜底链：private（非上市）优先于阶段
        if at == "private":
            return SENTIMENT_BAND["private"], "非上市（asset_type=private）→ 舆情不适用（±0%）"
        band_key = cls if cls in SENTIMENT_BAND else (LIFECYCLE_TO_BAND.get(stage) or at or "default")
        band = SENTIMENT_BAND.get(band_key, SENTIMENT_BAND["default"])
        return band, f"{band_key} → ±{band:.0%}"

    def _sentiment_correction(self, sent, scenario_factor=0.0):
        """P2 舆情修正层（v3.17.0）：把舆情从「独立加权路径」降为「作用于可比法的修正系数」，
        并由舆情强弱内生决定修正幅度。

        - 缺省 sentiment_layer="path" → 原样返回（走 v3.15.0 四部分口径，零变化）
        - sentiment_layer="correction" → 返回 (修正后情绪值, 带宽, 信号强度块)
        信号强度 s_signal（sentiment_signal_mode="endogenous"）：
          无事件 0.5｜单弱信号 0.8｜方向一致多信号 1.3｜方向冲突 0.7，高重要性 ×1.2，时效衰减 (1−d/90)
        """
        if self.sentiment_layer != "correction":
            return sent, 0.10, None
        band, band_reason = self.sentiment_band(self._lifecycle)
        # v3.18.0：强度口径（sentiment_adjust_mode="strength"）→ 走 band × k_signal 口径
        if self.sentiment_adjust_mode == "strength":
            return self._sentiment_correction_strength(sent, band, band_reason)
        k_signal, sig_detail = 1.0, None
        if self.sentiment_signal_mode == "endogenous":
            k_signal, sig_detail = self._sentiment_signal()
        corrected = max(-band, min(band, sent * k_signal))
        self._sent_signal = {
            "layer": "correction", "band": band, "band_reason": band_reason,
            "k_signal": round(k_signal, 4), "raw": round(sent, 4), "corrected": round(corrected, 4),
            "signal_detail": sig_detail,
            "note": "舆情修正层（P2）：作用于可比法的修正系数，不独立占权重；幅度由舆情强弱内生决定",
        }
        return corrected, band, self._sent_signal

    def _sentiment_signal(self):
        """舆情信号强度（v3.17.0 P2）：由 events/policy/risks 的数量、方向一致性、重要性、时效决定。"""
        s = self.sent
        events = s.get("events") or []
        policy = s.get("policy") or []
        n = len(events) + len(policy)
        if n == 0:
            return 0.5, {"n_signal": 0, "consistency": None, "note": "无舆情事件 → 无信号，修正幅度减半"}
        signs = []
        has_high = False
        for e in events:
            sg = {"positive": 1, "negative": -1, "利好": 1, "利空": -1, "中性": 0}.get(e.get("impact_direction", ""), 0)
            signs.append(sg)
            if e.get("importance") == "high":
                has_high = True
        for p in policy:
            sg = {"positive": 1, "negative": -1, "利好": 1, "利空": -1, "中性": 0}.get(p.get("direction", "中性"), 0)
            signs.append(sg)
        nz = [x for x in signs if x != 0]
        conflict = (len(nz) >= 2 and min(nz) < 0 < max(nz))
        if conflict:
            k, cons = 0.7, "conflict"
        elif n >= 3:
            k, cons = 1.3, "consistent" if (not nz or len(set(nz)) == 1) else "mixed"
        elif n <= 2:
            k, cons = 0.8, "few"
        else:
            k, cons = 1.0, "normal"
        if has_high:
            k *= 1.2
        days = s.get("days_since_event")
        decay = 1.0
        if isinstance(days, (int, float)) and days > 30:
            decay = max(0.0, 1.0 - (float(days) - 30.0) / 90.0)
            k *= decay
        return round(min(1.6, k), 4), {"n_signal": n, "consistency": cons, "has_high_importance": has_high,
                                       "decay": round(decay, 4), "note": "信号强度：无/少/一致/冲突四态 × 重要性 × 时效"}

    def _sentiment_signal_strength(self):
        """舆情信号强度（v3.18.0）：查表口径，替代 _sentiment_signal() 的 if/else 阶梯。

        口径：k = MATRIX[量级][一致性] × 高重要性 × 权威出处 × 时效衰减，上限 SIGNAL_K_MAX。
        - 量级按信号条数 n 分四档：none(0) / few(1–2) / medium(3–5) / many(6+)
        - 一致性：无负号混合 → consistent；出现正负共存 → conflict
        - 高重要性 importance=="high" 事件存在 → ×SIGNAL_HIGH_MULT
        - 权威出处：policy 项 authority==true 且 signal_authority_mode=="weighted" → ×SIGNAL_AUTHORITY_MULT
        - 时效：days>30 后线性衰减 1−(d−30)/90，下限 0
        """
        s = self.sent
        events = s.get("events") or []
        policy = s.get("policy") or []
        n = len(events) + len(policy)
        if n == 0:
            return SIGNAL_STRENGTH_MATRIX["none"]["base"], {
                "n_signal": 0, "tier": "none", "consistency": None,
                "note": "无舆情事件 → 无信号，修正强度减半",
            }
        signs = []
        has_high = False
        for e in events:
            sg = {"positive": 1, "negative": -1, "利好": 1, "利空": -1, "中性": 0}.get(e.get("impact_direction", ""), 0)
            signs.append(sg)
            if e.get("importance") == "high":
                has_high = True
        has_authority = False
        for p in policy:
            sg = {"positive": 1, "negative": -1, "利好": 1, "利空": -1, "中性": 0}.get(p.get("direction", "中性"), 0)
            signs.append(sg)
            if p.get("authority") is True:
                has_authority = True
        nz = [x for x in signs if x != 0]
        conflict = (len(nz) >= 2 and min(nz) < 0 < max(nz))
        tier = "many" if n >= 6 else ("medium" if n >= 3 else "few")
        base = SIGNAL_STRENGTH_MATRIX[tier]["conflict" if conflict else "consistent"]
        k = base
        if has_high:
            k *= SIGNAL_HIGH_MULT
        auth_applied = False
        if has_authority and self.signal_authority_mode == "weighted":
            k *= SIGNAL_AUTHORITY_MULT
            auth_applied = True
        days = s.get("days_since_event")
        decay = 1.0
        if isinstance(days, (int, float)) and days > SIGNAL_DECAY_START_DAYS:
            if self.signal_decay_mode == "stepped":
                dd = float(days) - SIGNAL_DECAY_START_DAYS
                decay = 1.0 if dd <= 30 else (0.5 if dd <= 60 else 0.2)
            else:
                decay = max(0.0, 1.0 - (float(days) - SIGNAL_DECAY_START_DAYS) / float(SIGNAL_DECAY_SPAN_DAYS))
            k *= decay
        k = max(0.0, min(SIGNAL_K_MAX, k))
        return round(k, 4), {
            "n_signal": n, "tier": tier, "consistency": "conflict" if conflict else "consistent",
            "base": base, "has_high_importance": has_high, "authority": auth_applied,
            "decay": round(decay, 4), "cap": SIGNAL_K_MAX,
            "note": "强度矩阵（量级×一致性）× 高重要性 × 权威出处 × 时效衰减，上限 K_MAX",
        }

    def _sentiment_correction_strength(self, sent, band, band_reason):
        """v3.18.0 强度口径修正：把「方向」与「强度」正交拆分，消除双重截断冗余。

        公式：adj_raw = band × k_signal × sign(sent) × min(|sent|/SENT_REFERENCE_BAND, 1.0)
              adj_sent = clamp(adj_raw, ±band × SIGNAL_K_MAX)      # 口径 C：允许有限突破 band
        其中：
          - sign(sent) 只承载方向（正/负），强度全交给 k_signal；
          - min(|sent|/0.10, 1.0) 是「信号是否成立」的归一化开关：|sent| ≥ 10%（旧 clamp 上限）即满权；
            |sent| 很小（如 +1%）时按比例缩小，避免「无实质舆情也有满额修正」；
          - band 是基础带宽（企业类型分化后），k_signal ∈ [0.5, 1.6] → 实际修正可达 band×1.6。
        返回 (修正值, band, 信号块)。
        """
        # strength 口径下强制启用强度矩阵（否则与 legacy 无区别）
        k_signal, sig_detail = self._sentiment_signal_strength()
        ref = SENT_REFERENCE_BAND
        magnitude = min(abs(sent) / ref, 1.0) if ref > 0 else 0.0
        direction = 1.0 if sent > 0 else (-1.0 if sent < 0 else 0.0)
        adj_raw = band * k_signal * direction * magnitude
        # 去相关折让：与 impact_map.multiple_factor 同源的重叠部分按 0.70 折让（仅 opt-in 且假设层生效时）
        overlap_applied = False
        if self.sentiment_overlap_discount and self._assumption_impact_active:
            adj_raw *= SENTIMENT_OVERLAP_DISCOUNT
            overlap_applied = True
        ceiling = band * SIGNAL_K_MAX
        adj_sent = max(-ceiling, min(ceiling, adj_raw))
        clamp_hit = abs(adj_raw) > ceiling + 1e-12
        self._sent_signal = {
            "layer": "correction",
            "adjust_mode": "strength",
            "band": band, "band_reason": band_reason,
            "k_signal": round(k_signal, 4),
            "raw": round(sent, 4),
            "magnitude": round(magnitude, 4),
            "direction": direction,
            "adj_raw": round(adj_raw, 6),
            "ceiling": round(ceiling, 6),
            "clamp_hit": clamp_hit,
            "corrected": round(adj_sent, 6),
            "overlap_discount": SENTIMENT_OVERLAP_DISCOUNT if overlap_applied else None,
            "signal_detail": sig_detail,
            "note": "强度口径（v3.18.0）：方向=sign(sent)，强度=k_signal；幅度 = band×k_signal×min(|sent|/10%,1)，上限 band×1.60",
        }
        return adj_sent, band, self._sent_signal

    def sentiment_adjust(self, scenario_factor=0.0):
        """舆情/情绪修正（论文「舆情」维度；v3.15.0 口径 B：与盈利质量彻底解耦）。
        规则：clamp(板块热度 + 个股舆情 + 情景因子, ±10%)；用户显式 sentiment_adjustment_pct 优先。
        v3.15.0：去掉 q_score 依赖与两条交叉验证规则（泡沫抑制/舆情错杀），
        使 ③ 市场舆情部分不含任何质量信息（仅板块热度 + 个股舆情 + 情景因子）。"""
        s = self.sent
        user_cfg = s.get("sentiment_adjustment_pct")
        if user_cfg is not None:
            return max(-0.10, min(0.10, float(user_cfg))), "用户配置（优先）"
        heat = {"high": 0.05, "neutral": 0.0, "low": -0.05}.get(s.get("sector_heat", "neutral"), 0.0)
        news = {"positive": 0.03, "neutral": 0.0, "negative": -0.03}.get(s.get("company_news_sentiment", "neutral"), 0.0)
        adj = max(-0.10, min(0.10, heat + news + scenario_factor))
        reason = f"板块{heat:+.0%} + 个股{news:+.0%} + 情景{scenario_factor:+.0%}"
        window = s.get("sentiment_window_days", 30)
        return max(-0.10, min(0.10, adj)), f"{reason}；窗口{window}天"

    def ff_calibration(self):
        """多因子校准层（对应国金「AI估值助手·FF五因子」案例）。"""
        ff = self.fin.get("ff_factor_adjust")
        seg = self.d.get("segment_benchmark", {})
        out = {"enabled": False, "note": "未做因子校准（未提供 ff_factor_adjust / segment_median），置信度−1档"}
        if ff is not None:
            out["enabled"] = True
            out["ff_factor_adjust"] = ff
            out["note"] = f"因子校准系数 {ff:+.0%}（用户/LLM 基于多因子模型提供）"
        if seg.get("median_ps") or seg.get("median_pe"):
            out["enabled"] = True
            out["segment"] = seg
            rev, profit, _ = self._forward()
            implied = []
            if seg.get("median_ps"):
                implied.append(round(rev * seg["median_ps"], 2))
            if seg.get("median_pe") and profit > 0:
                implied.append(round(profit * seg["median_pe"], 2))
            out["segment_implied"] = implied
            out["segment_note"] = "环节估值中枢隐含值（与可比法并列对比）"
        return out

    # ---------- 可比公司倍数法 ----------
    # v3.13.0：可比公司三档分类（最可比/较可比/一般可比）
    # 基于 S3.2 四维匹配：同环节(segment)/同模式(mode)/同规模(scale)/同成长阶段(growth_stage)
    # 自动推断；当 meta.target_profile 缺失或无可比公司含新字段时整体归入"最可比"（旧输入零变化）
    def _infer_comparability(self):
        tp = (self.d.get("meta") or {}).get("target_profile") or {}
        dims = ("segment", "mode", "scale", "growth_stage")
        has_new = any(c.get(d) is not None for c in self.comp for d in dims)
        buckets = {"most": [], "fair": [], "general": []}
        if not tp or not has_new:
            for c in self.comp:
                buckets["most"].append(c.get("name"))
            return buckets
        for c in self.comp:
            name = c.get("name")
            expl = c.get("comparability")
            if expl in ("most", "fair", "general"):
                buckets[expl].append(name)
                continue
            match = 0
            for d in dims:
                tv, cv = tp.get(d), c.get(d)
                if tv is not None and cv is not None and str(tv) == str(cv):
                    match += 1
            if match >= 4:
                buckets["most"].append(name)
            elif match >= 2:
                buckets["fair"].append(name)
            else:
                buckets["general"].append(name)
        return buckets

    def comparable_valuation(self, adj_pp=0.0, margin_adj_pp=0.0, multiple_factor=1.0):
        rev, profit, ebitda = self._forward(adj_pp, margin_adj_pp)
        pe_s, ps_s, ev_s, peg_s, pb_s = [], [], [], [], []
        # v2.14.0：PEG 护栏入参（缺省开启；置 peg_guard=false 即回到 v2.13.1 行为）
        peg_guard = bool(self.pref.get("peg_guard", True))
        peg_min_growth = float(self.pref.get("peg_min_growth_pct", 5.0))
        peg_max_ratio = float(self.pref.get("peg_max_ratio", 5.0))
        peg_guard_excluded = []
        for c in self.comp:
            if (c.get("pe") or 0) > 0:
                pe_s.append((c["name"], c["pe"]))
            if (c.get("ps") or 0) > 0:
                ps_s.append((c["name"], c["ps"]))
            if (c.get("ev_ebitda") or 0) > 0:
                ev_s.append((c["name"], c["ev_ebitda"]))
            if (c.get("pb") or 0) > 0:
                pb_s.append((c["name"], c["pb"]))
            if (c.get("pe") or 0) > 0 and (c.get("growth_pct") or 0) > 0:
                _g = float(c["growth_pct"])
                _ratio = c["pe"] / _g
                if peg_guard and _g < peg_min_growth:
                    # 近零正增速 → PE/增速 虚高，剔除并留痕（不进入中位数）
                    peg_guard_excluded.append([c["name"], round(_ratio, 4), _g])
                else:
                    peg_s.append((c["name"], _ratio))

        res = {}
        # v2.1.0 修复：亏损企业（forward 利润<0）禁用 PE 法——原实现负净利×PE 产生负估值混入综合值
        if pe_s and profit > 0:
            names = [p[0] for p in pe_s]
            vals = [p[1] for p in pe_s]
            keep, drop = iqr_filter(vals, names) if self.exclude_outliers else (vals, [])
            res["pe"] = {"samples": vals, "excluded": drop, "median": _median(keep), "mean": _mean(keep),
                         "value_median": round(profit * _median(keep) * multiple_factor, 2) if _median(keep) else None,
                         "value_mean": round(profit * _mean(keep) * multiple_factor, 2) if _mean(keep) else None}
        if ps_s:
            names = [p[0] for p in ps_s]
            vals = [p[1] for p in ps_s]
            keep, drop = iqr_filter(vals, names) if self.exclude_outliers else (vals, [])
            res["ps"] = {"samples": vals, "excluded": drop, "median": _median(keep), "mean": _mean(keep),
                         "value_median": round(rev * _median(keep) * multiple_factor, 2) if _median(keep) else None,
                         "value_mean": round(rev * _mean(keep) * multiple_factor, 2) if _mean(keep) else None}
        net_cash = _nn(self.fin.get("net_cash"), 0.0)
        if ev_s:
            names = [p[0] for p in ev_s]
            vals = [p[1] for p in ev_s]
            keep, drop = iqr_filter(vals, names) if self.exclude_outliers else (vals, [])
            med = _median(keep)
            res["ev_ebitda"] = {"samples": vals, "excluded": drop, "median": med, "mean": _mean(keep),
                                "value_median": round(ebitda * med * multiple_factor + net_cash, 2) if med else None}
        # v2.2.0：PB 估值法（净资产口径，无盈利要求，需 financials.net_assets）
        net_assets = self.fin.get("net_assets")
        if pb_s and net_assets:
            names = [p[0] for p in pb_s]
            vals = [p[1] for p in pb_s]
            keep, drop = iqr_filter(vals, names) if self.exclude_outliers else (vals, [])
            res["pb"] = {"samples": vals, "excluded": drop, "median": _median(keep), "mean": _mean(keep),
                         "value_median": round(net_assets * _median(keep) * multiple_factor, 2) if _median(keep) else None,
                         "value_mean": round(net_assets * _mean(keep) * multiple_factor, 2) if _mean(keep) else None}
        if peg_s and profit > 0:
            names = [p[0] for p in peg_s]
            vals = [p[1] for p in peg_s]
            keep, drop = iqr_filter(vals, names) if self.exclude_outliers else (vals, [])
            med = _median(keep)
            # v3.23.1 修复：PEG 的经济前提是「目标公司增长为正」（PEG=PE/g，g≤0 时指标无经济含义）。
            # 原实现 value = 利润 × PEG中位 × (g1×100) 在 g1<0 时直接产出**负估值**，而负值在
            # `if res.get("peg",{}).get("value")` 判定中为真 → 混入 candidates 被均值化，
            # 把可比法中枢静默拖低（格力案例：−2,455 亿把 2,687 亿拉到 1,658 亿，−38%）。
            _g1_adj = self._g1(adj_pp)
            block = {"samples": vals, "excluded": drop, "median": med,
                     "value": round(profit * med * (_g1_adj * 100.0) * multiple_factor, 2)
                     if (med and _g1_adj > 0) else None,
                     "target_growth_g1": round(_g1_adj, 6)}
            if med and _g1_adj <= 0:
                block["dropped_by_guard"] = (
                    f"目标公司首年增速 {_g1_adj:.2%} ≤ 0，PEG（PE/增速）无经济含义，"
                    "PEG 法不参与综合合成（原实现会产出负估值并拉低可比法中枢）")
                if block["dropped_by_guard"] not in self.warnings:
                    self.warnings.append(block["dropped_by_guard"])
            if peg_guard_excluded:
                block["guard_excluded"] = peg_guard_excluded
                block["guard_note"] = (f"PEG 护栏：增速 < {peg_min_growth}% 的样本已剔除"
                                       "（近零正增速使 PE/增速 虚高，中位数失真）")
            # v2.14.0：中位数上限护栏 —— 超上限判定失真则整法弃用（不做截断，避免注入错误数值）
            if peg_guard and med is not None and peg_max_ratio and med > peg_max_ratio:
                block["value"] = None
                block["dropped_by_guard"] = (f"PEG 中位数 {round(med, 4)} > 上限 {peg_max_ratio}，"
                                             "判定为失真，PEG 法不参与综合合成")
                if block["dropped_by_guard"] not in self.warnings:
                    self.warnings.append(block["dropped_by_guard"])
            res["peg"] = block
        elif peg_guard_excluded:
            # 全部 PEG 样本被护栏剔除：挂出无 value 的诊断块（不参与 candidates / synthesis.peg_value）
            res["peg"] = {"samples": [], "excluded": [], "median": None, "value": None,
                          "guard_excluded": peg_guard_excluded,
                          "guard_note": (f"PEG 护栏：全部可比样本增速均 < {peg_min_growth}%"
                                         "（近零/负增速），PEG 法整体弃用")}
        # v2.2.0：可比指标汇总表（仅当 comparables 含新增指标 pb/net_margin/roe/ev_sales 时挂出，保证旧输入输出零变化）
        has_new_metrics = any(c.get(k) is not None for c in self.comp for k in ("pb", "net_margin", "roe", "ev_sales"))
        if has_new_metrics:
            metrics = {}
            for key in ("pe", "ps", "ev_ebitda", "pb", "net_margin", "roe", "ev_sales", "growth_pct"):
                vals = [c.get(key) for c in self.comp if c.get(key) is not None]
                missing = sum(1 for c in self.comp if c.get(key) is None)
                if vals:
                    m = _mean(vals)
                    metrics[key] = {"median": round(_median(vals), 4), "mean": round(m, 4),
                                    "n": len(vals), "missing": missing,
                                    "cv": round(statistics.pstdev(vals) / m, 4) if len(vals) > 1 and m else None}
                else:
                    metrics[key] = {"median": None, "mean": None, "n": 0, "missing": missing, "cv": None}
            res["metrics"] = metrics
        # v3.11（修订 2b）：可比分组统计（境内/海外组中位 + 估值差%）——海外可比（DRAM 巨头等）纳入后的口径透明化
        groups = {}
        for c in self.comp:
            g = str(c.get("exchange", "CN") or "CN")
            groups.setdefault(g, []).append(c)
        if len(groups) > 1:
            by_group = {}
            for g, cg in groups.items():
                gv = {"n": len(cg)}
                for key in ("pe", "ps", "pb", "ev_ebitda"):
                    vals = [c.get(key) for c in cg if c.get(key) is not None]
                    gv[key] = {"median": round(_median(vals), 4) if vals else None, "n": len(vals)}
                by_group[g] = gv
            # 海外组（非 CN）vs 境内组（CN）PE 中位估值差%
            cn_pe = by_group.get("CN", {}).get("pe", {}).get("median")
            ov_pe_vals = [by_group[g]["pe"]["median"] for g in by_group if g != "CN" and by_group[g]["pe"].get("median") is not None]
            group_gap = None
            if cn_pe and ov_pe_vals:
                ov_med = _median(ov_pe_vals)
                group_gap = round((ov_med - cn_pe) / cn_pe, 4) if cn_pe else None
            res["metrics_by_group"] = {"groups": by_group, "group_gap_pct": group_gap,
                                       "note": "group_gap=海外组(非CN)PE中位 vs 境内组(CN)PE中位 估值差%（负=海外折价）；倍数口径差异（会计/税率/流动性）须在报告解释"}
        # v3.13.0：三档分类 + 主档优先逐级回退汇总
        tier_buckets = self._infer_comparability()
        tier_min = int(self.pref.get("tier_min_samples", 2))
        active = (self.d.get("meta") or {}).get("target_profile") is not None and \
                 any(c.get(d) is not None for c in self.comp
                     for d in ("segment", "mode", "scale", "growth_stage"))
        # 逐级回退：most -> most+fair -> 全部，直到样本数≥tier_min_samples
        selected, sel_names = [], set()
        for tier in ("most", "fair", "general"):
            selected.append(tier)
            sel_names.update(tier_buckets[tier])
            if len(sel_names) >= tier_min:
                break
        names_set = sel_names if active else None

        def _tval(key, base):
            if base is None:
                return None
            if key == "pe" and profit <= 0:
                return None
            if key == "pb" and not self.fin.get("net_assets"):
                return None
            sub = [c for c in self.comp if c.get(key) and (names_set is None or c["name"] in names_set)]
            if not sub:
                return None
            vals = [c[key] for c in sub]
            keep, _ = iqr_filter(vals, [c["name"] for c in sub]) if self.exclude_outliers else (vals, [])
            med = _median(keep)
            if not med:
                return None
            if key == "ev_ebitda":
                return round(ebitda * med * multiple_factor + net_cash, 2)
            return round(base * med * multiple_factor, 2)

        candidates = []
        dropped_nonpositive = []
        for key, base in (("pe", profit), ("ps", rev), ("ev_ebitda", ebitda), ("pb", net_assets)):
            v = _tval(key, base)
            if v is None:
                continue
            # v3.23.1 修复：股权估值不可能为负（有限责任），非正值一律不进均值——
            # 否则单个负值方法会以「等权成员」身份把中枢拽低，且不留任何痕迹。
            if v > 0:
                candidates.append(v)
            else:
                dropped_nonpositive.append([key, v])
        # v2.5.0 C2：PEG 参与开关（缺省 true 保持 v2.4.0 行为；PEG 不参与分档，沿用全样本）
        if res.get("peg", {}).get("value") and bool(self.pref.get("enable_peg_in_synthesis", True)):
            candidates.append(res["peg"]["value"])
        if dropped_nonpositive:
            self.warnings.append(
                "可比法剔除非正方法值：" + "；".join(f"{k}={v} 亿" for k, v in dropped_nonpositive)
                + "（股权价值受有限责任约束，非正值不参与均值）")
        base_value = round(_mean(candidates), 2) if candidates else None
        value_range = [round(min(candidates), 2), round(max(candidates), 2)] if candidates else None
        # v3.13.0：逐档倍数中位（口径透明化，可供报告引用）
        value_median_by_tier = {}
        for tier, names in tier_buckets.items():
            if not names:
                continue
            tset = set(names)
            row = {}
            for key, base in (("pe", profit), ("ps", rev), ("ev_ebitda", ebitda), ("pb", net_assets)):
                if base is None:
                    continue
                if key == "pe" and profit <= 0:
                    continue
                if key == "pb" and not self.fin.get("net_assets"):
                    continue
                sub = [c for c in self.comp if c.get(key) and c["name"] in tset]
                if sub:
                    vals = [c[key] for c in sub]
                    keep, _ = iqr_filter(vals, [c["name"] for c in sub]) if self.exclude_outliers else (vals, [])
                    m = _median(keep)
                    if m:
                        row[key] = round(m, 4)
            if row:
                value_median_by_tier[tier] = row
        res["comparable_tiers"] = {
            "active": active,
            "tiers": tier_buckets,
            "selected_tiers": selected,
            "tier_min_samples": tier_min,
            "note": "active=true 时按 最可比->较可比->一般可比 逐级回退汇总（样本数<tier_min_samples 时并入下一档）；active=false 时整体按最可比（旧输入零变化）"
        }
        res["value_median_by_tier"] = value_median_by_tier
        res["synthesis"] = {"method_values": candidates, "base_value": base_value, "range": value_range,
                            "active_tiers": selected}
        # v2.4.0：PEG 单列展示（仅 PEG 可用时挂出；不参与 candidates/权重 → 旧输入数值不变）
        if res.get("peg", {}).get("value"):
            res["synthesis"]["peg_value"] = res["peg"]["value"]
        return res

    # ---------- 可比公司筛选证据链（v3.20.0 四期改造） ----------
    def peer_screening_report(self):
        """可比公司选取的证据链审计（P0-1 长名单/台账｜P0-4 截点｜P0-2 规模双口径｜
        P0-3 实体去重｜P1-1 会计准则｜P1-4 次新股｜P1-5 指数锚降权）。

        缺省不激活（peer_screening.enabled=false）→ 不挂出输出块、不改样本、不改数值。
        两种模式：
          - **诊断模式（缺省）**：只产出 status / problems / 建议权重，不动样本与数值；
          - **执行模式**（`enforce.filter_sample=true`）：按合格名单过滤 self.comp 后再进场景计算，
            过滤后为空时**阻止执行并保持原样本**（不得因筛选把估值打空）。
        `enforce.weight_keep` 仅产出「建议让出比例」与 warning，**不在此处改权重**——
        权重再分配属编排层职责，避免本模块静默改变数值。
        """
        cfg = self.d.get("peer_screening") or {}
        if not cfg and (self.pref.get("peer_screening") or {}):
            cfg = self.pref.get("peer_screening") or {}
            self.d["peer_screening"] = cfg          # 回写，供报告层读取同一份配置
        if not cfg.get("enabled"):
            return {"enabled": False}
        try:
            from peer_screening import run_peer_screening
        except ImportError:                          # 兼容非脚本目录启动（sys.path 不含 scripts/）
            import sys as _sys
            _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from peer_screening import run_peer_screening
        res = run_peer_screening(self.d, self.comp)
        if not res.get("enabled"):
            return {"enabled": False}
        for w in res.get("warnings") or []:
            if w not in self.warnings:
                self.warnings.append(w)
        enf = res.get("enforce") or {}
        # 执行模式 A：按合格名单过滤样本（会改变数值 → 须显式开启）
        if enf.get("filter_sample"):
            keep = set(res.get("eligible_names") or [])
            # 去重合并的实体与「判据剔除」分开计，避免报告把 A/H 合并说成"不适格剔除"
            merged_names = {x.get("name") for x in
                            ((res.get("stages") or {}).get("s3_dedupe") or {}).get("merged") or []}
            dropped = [c.get("name") for c in self.comp if c.get("name") not in keep]
            removed = [n for n in dropped if n not in merged_names]
            merged_gone = [n for n in dropped if n in merged_names]
            if dropped and len(dropped) < len(self.comp):
                n_before = len(self.comp)
                self.comp = [c for c in self.comp if c.get("name") in keep]
                enf["applied"] = True
                enf["removed"] = removed
                enf["merged_away"] = merged_gone
                enf["n_before"] = n_before
                enf["n_after"] = len(self.comp)
                msg = "可比筛选（执行模式）：可比样本 %d → %d" % (n_before, len(self.comp))
                if removed:
                    msg += "；剔除不适格 %d 家（%s）" % (len(removed), "、".join(str(x) for x in removed))
                if merged_gone:
                    msg += "；重复实体合并 %d 家（%s）" % (len(merged_gone), "、".join(str(x) for x in merged_gone))
                self.warnings.append(msg)
            else:
                enf["applied"] = False
                enf["removed"] = dropped
                enf["blocked"] = ("过滤后样本为空" if dropped else "无可剔除样本")
                if dropped:
                    self.warnings.append(
                        "可比筛选（执行模式）：过滤后样本为空，已阻止执行并保持原样本计算")
        # 执行模式 B：权重让出（仅建议，不动数值）
        if enf.get("weight_keep"):
            keep_ratio = float((res.get("status_policy") or {}).get("weight_keep", 1.0))
            enf["weight_keep_suggested"] = keep_ratio
            enf["weight_keep_applied"] = False
            if keep_ratio < 1.0:
                self.warnings.append(
                    "可比筛选：status=%s，建议可比法权重让出 %d%%（weight_keep=%.2f）；"
                    "本引擎不自动改权重，须由编排层重分配"
                    % (res.get("status"), round((1 - keep_ratio) * 100), keep_ratio))
        return res

    # ---------- DCF ----------
    def _fcff_base(self):
        """FCFF 报表级口径基准（v2.6.0 B1）：FCFF = EBIT×(1−t) + D&A − CapEx − ΔWC。
        返回 (fcff0, 明细 dict)；ebit/capex 任一缺失 → (None, None)（不激活，回退现口径）。"""
        fin = self.fin
        ebit = fin.get("ebit")
        capex = fin.get("capex")
        if ebit is None or capex is None:
            return None, None
        tax = float((fin.get("wacc_params") or {}).get("tax_rate", 0.15) or 0.15)
        d_a = float(fin.get("d_a", 0.0) or 0.0)
        delta_wc = float(fin.get("delta_wc", 0.0) or 0.0)
        fcff0 = ebit * (1.0 - tax) + d_a - capex - delta_wc
        detail = {"ebit": round(ebit, 4), "tax_rate": round(tax, 4), "d_a": round(d_a, 4),
                  "capex": round(capex, 4), "delta_wc": round(delta_wc, 4), "fcff0": round(fcff0, 4)}
        return fcff0, detail

    def _fcff_series_by_year(self, growth_seq, base_info):
        """capex_by_year 分年输入时生成显式期逐年 FCFF 序列（v2.6.0 B1）：
        逐年 ebit/d_a 按增速外推（第 t 年 = 基年 × Π(1+g_i), i≤t），capEx 取分年值（缺省按基年 capex×外推），ΔWC 固定。
        与募投产能挂钩：capEx 分年输入直接采用募投节奏，而非简单外推。"""
        fin = self.fin
        cap_by_year = fin.get("capex_by_year") or {}
        ebit = base_info["ebit"]; d_a = base_info["d_a"]; delta_wc = base_info["delta_wc"]
        tax = base_info["tax_rate"]; capex0 = base_info["capex"]
        # 将 {year: v} 转为按年份升序的 capex 列表（与 growth_seq 长度对齐，缺省用基年 capex 外推）
        years = sorted(cap_by_year.keys())
        series = []
        ebit_t = ebit; d_a_t = d_a
        for i, g in enumerate(growth_seq):
            ebit_t = ebit_t * (1.0 + g)
            d_a_t = d_a_t * (1.0 + g)
            capex_t = float(cap_by_year.get(years[i], capex0 * (1.0 + g))) if i < len(years) else capex0 * (1.0 + g)
            series.append(ebit_t * (1.0 - tax) + d_a_t - capex_t - delta_wc)
        return series

    def dcf_valuation(self, adj_pp=0.0, margin_adj_pp=0.0, wacc_adj_pp=0.0, comp=None, tg_adj_pp=0.0):
        # v2.2.0：wacc 取 wacc_model.wacc_used（run() 预置 _wacc_eff），增速/终值取三角校准值（_gf_eff/_tg_eff）
        wacc_base = getattr(self, "_wacc_eff", None)
        if wacc_base is None:
            wacc_base = self.fin.get("wacc") or DEFAULT_WACC
        wacc = wacc_base + wacc_adj_pp / 100.0
        tg_base = getattr(self, "_tg_eff", None)
        if tg_base is None:
            tg_base = self.fin.get("terminal_growth")
        if tg_base is None:
            tg_base = self._tg_default()          # v3.21.0 A2：6%（legacy）或 2%（cva_2pct）
        tg = tg_base + _nn(tg_adj_pp, 0.0) / 100.0   # v3.21.0 A5：永续增速进入情景
        # v3.21.0 A2：cva_2pct 口径下把输入校验上限由 10% 收到长期名义 GDP 4.5%
        # （6% 的缺省值曾突破引擎自己设定的 GDP 上限，说明校验与常量两张皮）
        if self.tg_default_mode == "cva_2pct" and self.fin.get("terminal_growth") is not None:
            _cap_a2 = TERMINAL_GROWTH_PUBLIC["gdp_cap"]
            if float(self.fin["terminal_growth"]) > _cap_a2 and not self.fin.get("terminal_growth_rationale"):
                _k = ("a2", round(float(self.fin["terminal_growth"]), 4))
                if _k not in self._tg_warned:
                    self._tg_warned.add(_k)
                    self.warnings.append(
                        f"永续增速 {float(self.fin['terminal_growth']):.2%} 超过长期名义 GDP 上限 "
                        f"{_cap_a2:.2%}；如确有依据请补充 financials.terminal_growth_rationale，否则建议下调。")
        # v3.21.0 A5：bull 侧护栏——情景调整不得把 tg 推出长期名义 GDP 上限
        tg_capped = None
        _cap = TERMINAL_GROWTH_PUBLIC["gdp_cap"]
        if _nn(tg_adj_pp, 0.0) and tg > _cap:      # 仅情景调整生效时护栏（缺省零回归）
            tg_capped, tg = round(tg, 6), _cap
        # v3.21.0 A1：Gordon 终值前提守卫（g < WACC）——分母为 0 崩溃、为负得负终值、归因为「内在价值为负」
        tguard = check_terminal_growth(wacc, tg)
        tg_meta = None
        if tguard["violation"]:
            if self.tg_guard == "clamp":
                tg_old = tg
                tg = tguard["suggested_tg"]
                tg_meta = {**tguard, "action": "clamp", "tg_clamped_from": round(tg_old, 6),
                           "tg_clamped_to": round(tg, 6),
                           "clamp_reason": "永续增速 ≥ 折现率，压至 WACC − 1pp 以恢复 Gordon 终值的经济意义"}
                _k = ("clamp", round(tg_old, 4), round(wacc, 4))
                if _k not in self._tg_warned:
                    self._tg_warned.add(_k)
                    self.warnings.append(
                        f"永续增速 {tg_old:.2%} 被压至 WACC−1pp（{tg:.2%}，WACC {wacc:.2%}），请复核资本成本或永续假设。")
                tguard = check_terminal_growth(wacc, tg)
            else:
                # off：不改 tg，但终值置 0（fail-closed，不产出负终值/天文数字），归因改为终值无意义
                tg_meta = {**tguard, "action": "fail_closed"}
                _k = ("fail_closed", round(tg, 4), round(wacc, 4))
                if _k not in self._tg_warned:
                    self._tg_warned.add(_k)
                    self.warnings.append(
                        f"永续增速 {tg:.2%} 不低于折现率 {wacc:.2%}，Gordon 终值无经济意义"
                        f"（分母 {wacc - tg:+.4%}）；已按 fail-closed 口径仅计显式期现值 + 净现金，"
                        f"请复核资本成本或永续假设。")
            self._tg_guard_fired = True
        rev, profit, _ = self._forward(adj_pp, margin_adj_pp)
        # v3.23.0 D4：取值矩阵优先于三角校准——三角校准的 implied_growth 是历史均值，
        # 与「按形态取最近一年/加权」的规则冲突；仅当用户未给路径时才让规则接管。
        _rule_takeover = bool(getattr(self, "_gf_rule", None) and self._gf_rule.get("applied")
                              and not self.fin.get("growth_forecast"))
        gf_src = None if _rule_takeover else getattr(self, "_gf_eff", None)
        if gf_src is None and not _rule_takeover:
            gf_src = self.fin.get("growth_forecast") or {}
        gf = list(gf_src.values()) if isinstance(gf_src, dict) else list(gf_src or [])
        # v3.23.0 D4：用户未给路径时，按历史形态矩阵取基准增速（仅 cva_matrix 模式且判定成功）
        if not gf and getattr(self, "_gf_rule", None) and self._gf_rule.get("applied"):
            _base_g = float(self._gf_rule["base_growth"])
            gf = [_base_g, _base_g, _base_g]
        if len(gf) < 3:
            gf = [self._g1()] * 3
        # v3.16.0 Layer 1：lifecycle_mode=auto 时按四阶段形态 + 显式期长度构建增速路径
        gs_detail = None
        # v3.26.0 修复：衰退期的 tg 上限必须在**选路之前**生效，且必须在 growth_model 求值之前。
        # 原实现写在下面的 lifecycle elif 分支内（`if stage == "decline": tg = min(tg, tg_floor)`），
        # 两个漏洞：① growth_model 接管时走 `if gm_seq is not None` 分支，整条夹逼被绕过；
        # ② 即便把夹逼提到分支前，若仍排在 `growth_model_schedule(tg)` 之后，路径末端会按旧 tg
        #    收敛，造成「terminal_growth=0 而路径末年=2%」的断裂。
        _stage_now = ((self._lifecycle or {}).get("stage")
                      if (self._lifecycle or {}).get("enabled") else None)
        if _stage_now == "decline":
            _tf = float((LIFECYCLE_DEFAULTS.get("decline") or {}).get("tg_floor", 0.0))
            if tg > _tf:
                tg = _tf
        # v3.25.0：状态空间分解增速（opt-in，优先级高于 cva_matrix，低于用户显式路径）
        # v3.29.0：plc6 与 growth_model 是**两套并行的显式口径**，不能都生效也不能静默择一——
        #   原实现下「显式打开 growth_shape_mode=plc6」会被 growth_model.enabled 静默架空
        #   （美的实测：plc6 全无影响，正是「声明了但没被消费」的老毛病）。现按 plc6 优先，
        #   并挂 warning 要求报告披露口径冲突。
        gm_seq, gm_det = None, None
        _gm_cfg = self.fin.get("growth_model") or {}
        _plc6 = (self.growth_shape_mode == "plc6")
        if _gm_cfg.get("enabled") and _plc6 and not getattr(self, "_plc6_conflict_warned", False):
            self._plc6_conflict_warned = True
            self.warnings.append(
                "增长路径口径冲突：growth_model（状态空间）与 growth_shape_mode=plc6 同时声明，"
                "已按 plc6 执行（状态空间模型被抑制）；如需状态空间口径，须显式关闭 plc6。")
        if _gm_cfg.get("enabled") and not _plc6 and (not self.fin.get("growth_forecast")
                                                     or _gm_cfg.get("override_manual")):
            gm_seq, gm_det = self.growth_model_schedule(tg)
        if _plc6:
            # v3.29.0：六阶段增长函数——**最高优先级的显式口径**（高于 growth_model 与四阶段形态）
            #   g_t = tg + (g1 − tg)·E(t)，E(1)=1 / E(n)=0 由构造保证（不再依赖 forced 补丁）
            _lc = self._lifecycle or {}
            _stage0 = _lc.get("stage") if _lc.get("enabled") else None
            _d6 = self.damodaran_stage() or {}
            _ds = _d6.get("stage") if _d6.get("enabled") else None
            if _ds not in PLC6_STAGE_ORDER:
                _ds = {"startup": "startup", "growth": "high_growth",
                       "mature": "mature_stable", "decline": "decline"}.get(
                           _stage0, "mature_growth")
                _ds_fallback = ("v326 四阶段直接映射（达莫达兰阶段不可派生）" if _stage0
                                else "无生命周期阶段（判别未启用）→ 保守回落成熟成长")
            else:
                _ds_fallback = None
            _cap_in = _gm_cfg.get("cap_life_years")
            _n6 = self._mature_n_override(_stage0) if _stage0 == "mature" else None
            # ★情景步长必须与 legacy 同口径：adj_pp 是**百分点**，legacy 在
            #   `build_growth_schedule` 内部对 base 逐档加 adj_pp/100。plc6 若直接吃原始 gf，
            #   bear/bull 会得到与 base 逐位相同的路径 → 情景区间塌缩成一点（实测：万华 bull
            #   6,311.9→3,109.1，中枢 −10.39%，全部来自"情景消失"而非形态差异）。
            gf_adj = [max(-0.9, float(g) + adj_pp / 100.0) for g in gf]
            growth_seq, gs_detail = plc_growth_path(
                _ds, gf_adj, self._g1(adj_pp), tg, n=_n6, cap=_cap_in)
            gs_detail["stage_6"] = _ds
            gs_detail["stage_6_label"] = DAMODARAN_STAGE_LABELS.get(_ds, _ds)
            gs_detail["v326_stage"] = _stage0
            gs_detail["cap_source"] = ("growth_model.cap_life_years" if _cap_in
                                       else "plc6 表值（引擎标定）")
            if _ds_fallback:
                gs_detail["stage_6_fallback"] = _ds_fallback
            if gs_detail.get("form_downgraded") and not getattr(self, "_plc6_deg_warned", False):
                self._plc6_deg_warned = True
                self.warnings.append("增长路径：" + gs_detail["form_downgraded"] + "。")
            # 用户显式 cap 与表值差异超过 2 年 → 留痕（避免「填了没生效」）
            _cap_tab = (PLC6_SHAPE_PARAMS.get(_ds) or {}).get("cap")
            if _cap_in is not None and _cap_tab is not None \
                    and abs(float(_cap_in) - float(_cap_tab)) > 2.0 \
                    and not getattr(self, "_plc6_cap_warned", False):
                self._plc6_cap_warned = True
                self.warnings.append(
                    f"增长路径：显式 cap_life_years={float(_cap_in):.1f} 年与 plc6 表值 "
                    f"{float(_cap_tab):.1f} 年相差超 2 年，已按显式值执行（拐点显著后移/前移）。")
            _lcfg6 = dict(LIFECYCLE_DEFAULTS.get(_stage0 or "mature", {}))
            gs_detail["terminal"] = _lcfg6.get("terminal")
            gs_detail["rr_mode"] = _lcfg6.get("rr_mode")
        elif gm_seq is not None:
            growth_seq, gs_detail = gm_seq, gm_det
        elif self.lifecycle_mode == "auto" and self._lifecycle and self._lifecycle.get("enabled"):
            stage = self._lifecycle["stage"]
            lcfg = dict(LIFECYCLE_DEFAULTS.get(stage, {}))
            if self._industry and self._industry.get("enabled") and stage == "growth":
                hl = (self._industry.get("params") or {}).get("half_life")
                if hl:
                    lcfg["half_life"] = hl           # 行业半衰期优先（Layer 2 → Layer 1）
            # v3.27.0：成熟期显式期覆盖（table 6 / legacy_4 4 / cva_7 7）
            _ov = self._mature_n_override(stage)
            if _ov:
                lcfg["n"] = _ov
            # 衰退期 tg 上限已在选路前统一夹逼（见上方 v3.26.0 修复），此处不再重复
            growth_seq, gs_detail = build_growth_schedule(
                stage, gf, tg, lcfg, adj_pp,
                terminal_mode=self.growth_terminal_mode)   # v3.21.0 B5：asymptotic | forced
            # v3.16.2：终值方法/再投资模式随阶段留痕（消除「字段定义但未被消费」）
            if gs_detail:
                gs_detail["terminal"] = lcfg.get("terminal")
                gs_detail["rr_mode"] = lcfg.get("rr_mode")
        else:
            # v3.21.0 B1：legacy_truncate（前 3 年）/ user_full（用满用户路径）
            growth_seq = build_growth_seq(gf, tg, adj_pp,
                                          full_path=(self.growth_path_mode == "user_full"))
        if any(g < -0.3 for g in growth_seq):
            self.warnings.append("DCF 显式期存在大幅负增长（<-30%），注意现金流口径合理性。")
        # v2.6.0 B1：FCFF 报表级口径（financials.fcff_mode=true 且 ebit/capex 齐备时激活）
        # v3.23.0 D1：折现时点（mid_year=年中折现，缺省年末）
        mid_year = (self.discount_timing == "mid_year")
        fcff_mode = bool(getattr(self, "_fcff_mode", False))
        # v3.24.0（F1）：`_fcff_base()` 延迟到「报表驱动是否已命中」判断之后再算——
        # 原实现在此处**无条件**预计算，命中 ① 三表联立时其结果被整段丢弃（同为「算了但没用」）。
        fcff_base, fcff_det = None, None
        fcf_basis = "net_profit_ratio"
        fcff_out = None
        cashflow_schedule = None
        drivers_out = None
        # v3.23.0 D6/D7：报表驱动式 FCFF（dcf_drivers 块，收入→EBIT→NOPAT→+D&A−Capex−ΔWC 逐年传导）
        _drv = self.drivers or {}
        _drv_active = bool(_drv.get("enabled", True)) and bool(_drv)
        _drv_series, _drv_det = None, None
        if _drv_active:
            _tax_drv = float(_drv.get("tax_rate")
                             or (self.fin.get("wacc_params") or {}).get("tax_rate", 0.15) or 0.15)
            _drv_series, _drv_det = statement_fcff_series(
                base_revenue=_drv.get("base_revenue") or self.fin.get("revenue_latest_ttm"),
                growth_seq=growth_seq,
                ebit_margin=_drv.get("ebit_margin"),
                capex_to_revenue=_drv.get("capex_to_revenue", self.fin.get("capex_to_revenue")),
                da_to_revenue=_drv.get("da_to_revenue"),
                nwc_to_revenue=_drv.get("nwc_to_revenue"),
                nwc_turnover=_drv.get("nwc_turnover"),
                tax_rate=_tax_drv,
                base_da=_drv.get("base_da", self.fin.get("d_a")),
                cost_ratio=_drv.get("cost_ratio"),
                expense_ratio=_drv.get("expense_ratio"),
                delta_wc_first=_drv.get("delta_wc_first"),
            )
            if _drv_series is None:
                self.warnings.append(
                    "dcf_drivers 已提供但缺少 ebit_margin（或 cost_ratio/expense_ratio）与 base_revenue，"
                    "报表驱动口径未激活，已回退下一档现金流口径。")
        # v3.24.0（F1）：只有未命中 ①（三表联立）时才需要报表级基期 FCFF（② 档的输入）。
        # 非惰性模式保持原行为（无条件计算，逐位不变）。
        if not (self.fcf_ratio_lazy and _drv_series):
            fcff_base, fcff_det = self._fcff_base()
        if _drv_series:
            pv_sum, tv_pv, dcf_detail = discount_fcf_series(_drv_series, tg, wacc,
                                                            guard=tguard, mid_year=mid_year)
            # fcf0 统一为**基期** FCFF（与 fcff_mode 的 fcf0 同义；首年现金流见 rows[0].fcff）
            fcf0 = (_drv_det or {}).get("base_fcff") or _drv_series[0]
            fcf_basis = "statement_drivers"
            drivers_out = _drv_det
        elif fcff_mode and fcff_base is not None:
            cap_by_year = self.fin.get("capex_by_year") or {}
            if cap_by_year:
                series = self._fcff_series_by_year(growth_seq, fcff_det)
                pv_sum, tv_pv, dcf_detail = discount_fcf_series(series, tg, wacc,
                                                                guard=tguard, mid_year=mid_year)
                fcf0 = fcff_base  # 口径统一：fcf0=基准年 FCFF（与两阶段模式一致；第一年现金流见 series[0]）
                fcf_basis = "fcff_by_year"
                fcff_out = {**fcff_det, "capex_by_year": {k: round(float(v), 4) for k, v in cap_by_year.items()},
                            "series": [round(s, 4) for s in series]}
            else:
                fcf0 = fcff_base
                pv_sum, tv_pv, dcf_detail = two_stage_dcf(fcf0, growth_seq, tg, wacc,
                                                          guard=tguard, mid_year=mid_year)
                fcf_basis = "fcff"
                fcff_out = fcff_det
            if fcf0 < 0:
                self.warnings.append("FCFF 基准为负（资本开支/营运资本占用过高），DCF 内在价值可能失真，请核实再投资假设。")
        else:
            # v3.16.0 P0 价值驱动式（cashflow_model=p0_value_driver 且 ebit + roic 齐备时激活）
            tax_p0 = float((self.fin.get("wacc_params") or {}).get("tax_rate", 0.15) or 0.15)
            roic_p0 = self.fin.get("roic") or ((self._industry or {}).get("params", {}) or {}).get("roic")
            if self.cashflow_model == "p0_value_driver" and self.fin.get("ebit") is not None and roic_p0:
                series, p0_det = value_driver_fcf_series(self.fin["ebit"], tax_p0, growth_seq, roic_p0)
                if series:
                    pv_sum, tv_pv, dcf_detail = discount_fcf_series(series, tg, wacc,
                                                                    guard=tguard, mid_year=mid_year)
                    fcf0 = series[0]
                    fcf_basis = "value_driver_p0"
                    cashflow_schedule = p0_det
                else:
                    # v3.24.0（F1）：惰性模式下按需求值（此前该档只会退回裸 OCF/净利）
                    ocf_ratio = (getattr(self, "_fcf_ratio", None)
                                 or ((self._get_fcfr() or {}).get("used") if self.fcf_ratio_lazy else None)
                                 or self.fin.get("ocf_to_net_profit", 0.9) or 0.9)
                    fcf0 = profit * ocf_ratio
                    pv_sum, tv_pv, dcf_detail = two_stage_dcf(fcf0, growth_seq, tg, wacc,
                                                              guard=tguard, mid_year=mid_year)
            else:
                # v3.22.0 修复②：p0_value_driver 已声明但缺 ebit/roic —— 原实现静默回退比率法，
                # 用户以为用了「增长由再投资挣得」的口径，实际跑的是「净利×常数比率」（无再投资约束，
                # 高增长标的 FCFF 被系统性高估）。现显式留痕 + 告警，error 模式下并降置信度。
                if self.cashflow_model == "p0_value_driver":
                    _miss = []
                    if self.fin.get("ebit") is None:
                        _miss.append("ebit")
                    if not roic_p0:
                        _miss.append("roic")
                    if _miss:
                        self._cf_fallback = {
                            "requested": "p0_value_driver", "used": "p2_legacy",
                            "missing": _miss, "mode": self.cashflow_fallback_mode,
                            "note": ("p0 价值驱动式 FCFF_t = NOPAT_t×(1−g_t/ROIC) 需 ebit + roic 齐备"
                                     "（守恒律 g = ROIC × RR）；缺参时降级为「净利×FCF 比率」，"
                                     "该口径不含再投资约束，高增长假设下 FCFF 会被系统性高估。"),
                        }
                        self.warnings.append(
                            f"cashflow_model=p0_value_driver 但缺少 {'/'.join(_miss)}，已降级 p2_legacy"
                            f"（净利×FCF 比率）——该口径无再投资约束，高增长假设下 FCFF 被高估；"
                            f"请补 {'/'.join(_miss)} 后重跑。")
                # v2.3.0：FCF 比率三层校准（无 CapEx 数据时 used=OCF/净利，与 v3.3 零变化）
                ocf_ratio = getattr(self, "_fcf_ratio", None)
                if ocf_ratio is None and self.fcf_ratio_lazy:
                    # v3.24.0（F1）：只有走到比率档才求值——保证 ④ 档拿到的是三层校准值，
                    # 而非退化成裸 OCF/净利（原实现在此静默降级，恰在最需要它的档位）。
                    ocf_ratio = (self._get_fcfr() or {}).get("used")
                if ocf_ratio is None:
                    ocf_ratio = self.fin.get("ocf_to_net_profit", 0.9) or 0.9
                fcf0 = profit * ocf_ratio  # FCF≈净利×FCF比率（内在价值口径，不受市场修正项影响）
                pv_sum, tv_pv, dcf_detail = two_stage_dcf(fcf0, growth_seq, tg, wacc,
                                                          guard=tguard, mid_year=mid_year)
        net_cash_in = _nn(self.fin.get("net_cash"), 0.0)
        equity = pv_sum + tv_pv + net_cash_in
        if equity < 0:
            # v2.14.5：净现金下限须受**有限责任**约束。原实现 `equity = net_cash_in` 在
            # net_cash 为负（净负债）时返回**负的权益价值**——与「保持下游口径有意义」的
            # 注释自相矛盾（股东权益不可能为负；PV(经营) < 净负债 时股权价值应为 0）。
            # 实例：万华化学 bear 情景 PV 586 亿 < 净负债 937.67 亿 → 原返回 −937.67，
            # 拖低 Bear 下界并人为放大情景区间；中国石化 bear 返回 −3,803.61（同类）。
            # 现取 `floor = max(0.0, net_cash_in)`：净现金为正时仍为净现金下限（历史
            # 行为逐位不变），净现金为负时取 0（有限责任）。
            floor = max(0.0, net_cash_in)
            equity = floor
            self.warnings.append(
                f"DCF 内在价值为负，已按权益下限 {floor:.2f} 亿元处理"
                f"（净现金 {net_cash_in:.2f} 亿元、有限责任约束；保持下游口径有意义）。")
        # v2.6.0 B7：终值退出倍数交叉（Gordon 与可比退出倍数取区间）
        tv_range = None
        tv_exit = None
        if comp is None:
            comp = self.comparable_valuation()
        pe_med = (comp.get("pe") or {}).get("median")
        ps_med = (comp.get("ps") or {}).get("median")
        profit_t, rev_t = profit, rev
        for g in growth_seq:
            profit_t *= (1.0 + g)
            rev_t *= (1.0 + g)
        exit_tv_pv = None
        if pe_med:
            exit_tv_pv = (profit_t * pe_med) / ((1.0 + wacc) ** len(growth_seq))
            tv_exit = {"method": "exit_pe", "multiple": round(pe_med, 2),
                       "terminal_profit": round(profit_t, 2), "tv_pv": round(exit_tv_pv, 2)}
        elif ps_med:
            exit_tv_pv = (rev_t * ps_med) / ((1.0 + wacc) ** len(growth_seq))
            tv_exit = {"method": "exit_ps", "multiple": round(ps_med, 2),
                       "terminal_revenue": round(rev_t, 2), "tv_pv": round(exit_tv_pv, 2)}
        if tv_exit:
            tv_range = [round(min(tv_pv, exit_tv_pv), 2), round(max(tv_pv, exit_tv_pv), 2)]
        tv_share_v = round(tv_pv / (pv_sum + tv_pv), 3) if (pv_sum + tv_pv) else None
        # v3.23.0 D9：期末再投资一致性自检——g 与 (Capex−D&A+ΔWC)/NOPAT 是否自洽（g = ROIC×RR）
        self._reinv_check = None
        if self.reinvestment_check:
            rows = (drivers_out or {}).get("rows") or []
            if rows:
                last = rows[-1]
                nopat_n = last.get("nopat") or 0.0
                rr_implied = ((last.get("capex", 0.0) - last.get("d_a", 0.0) + last.get("delta_wc", 0.0))
                              / nopat_n) if nopat_n else None
                roic_v = self.fin.get("roic") or ((self._industry or {}).get("params") or {}).get("roic")
                rr_target = (tg / roic_v) if (roic_v and tg >= 0) else None
                # v3.23.1 修复：原实现 dev = |rr_implied − rr_target| 是**百分点差**，却与 0.5 比较
                # （文案写的是「偏离 >50%」——相对口径）。结果：隐含 RR = −13.6%（净减投资）
                # 对目标 RR = +16.6%，差 30.2pp，符号完全相反，却判为「自洽」而放过。
                # 正解：相对偏离 = |差| / |目标|；并增设**符号翻转**规则——一边减投资一边要求正增长，
                # 属结构性不自洽，无论相对幅度大小都必须告警。
                gap_pp = (abs(rr_implied - rr_target)
                          if (rr_implied is not None and rr_target is not None) else None)
                dev = (gap_pp / max(abs(rr_target), 1e-6)
                       if (gap_pp is not None and rr_target is not None) else None)
                sign_flip = bool(rr_implied is not None and rr_target is not None
                                 and rr_implied < 0 < rr_target)
                flag = bool((dev is not None and dev > 0.5)
                            or (sign_flip and gap_pp is not None and gap_pp > 0.05))
                self._reinv_check = {
                    "available": True, "terminal_year": last.get("t"),
                    "rr_implied": round(rr_implied, 4) if rr_implied is not None else None,
                    "roic": round(roic_v, 4) if roic_v else None,
                    "rr_target": round(rr_target, 4) if rr_target is not None else None,
                    "gap_pp": round(gap_pp, 4) if gap_pp is not None else None,
                    "deviation": round(dev, 4) if dev is not None else None,
                    "basis": "相对偏离 = |rr_implied − rr_target| / |rr_target|（v3.23.1 修正；原为百分点差）",
                    "sign_flip": sign_flip,
                    "flag": flag,
                    "note": ("期末再投资率与 g=ROIC×RR 自洽" if not flag else
                             ("期末净减投资（RR<0）却要求正增长，终端 FCFF 与增速假设结构性不自洽" if sign_flip else
                              f"期末再投资率与永续增速隐含 RR 相对偏离 {dev:.0%} >50%，终端 FCFF 与增速假设不自洽")),
                }
                if flag:
                    _w = (f"期末再投资一致性告警：隐含 RR {(last.get('capex', 0) - last.get('d_a', 0) + last.get('delta_wc', 0)) / nopat_n:+.2%}"
                          f" vs 永续增速隐含 RR {rr_target:+.2%}（相对偏离 {dev:.0%}，符号翻转={sign_flip}）——"
                          "capex 长期低于 D&A 意味着资产存量在收缩，与正增长假设矛盾；"
                          "请核对 capex 口径（是否漏计）或下调永续增速。")
                    if _w not in self.warnings:      # 情景/方法多次调用同一段，去重避免重复刷屏
                        self.warnings.append(_w)
            else:
                self._reinv_check = {"available": False,
                                     "reason": "需 dcf_drivers 报表驱动口径（逐年 capex/D&A/NOPAT 明细）"}
        # v3.24.0（F1）：把实际生效的 FCFF 口径记到实例上——`_fcfr_view()` 据此判定
        # 比率法的 role（driving / diagnostic_only / 未算），报表族口径下不再输出驱动值。
        self._fcf_basis = fcf_basis
        out = {"wacc": round(wacc, 4), "terminal_growth": tg, "fcf0": round(fcf0, 4),
               "fcf_basis": fcf_basis,
               "growth_seq": [round(g, 4) for g in growth_seq],
               "pv_sum": round(pv_sum, 2), "terminal_value_pv": round(tv_pv, 2),
               "equity_value": round(equity, 2), "detail": dcf_detail,
               "tv_share": tv_share_v}
        # v3.21.0 A5：情景 tg 调整留痕（仅非零或触及上限时挂出 → 缺省零回归）
        if _nn(tg_adj_pp, 0.0):
            out["tg_scenario_adj_pp"] = round(_nn(tg_adj_pp, 0.0), 4)
            out["tg_base"] = round(tg_base, 6)
            if tg_capped is not None:
                out["tg_capped_by_gdp"] = {"from": tg_capped, "to": _cap}
        elif tg_capped is not None:
            out["tg_capped_by_gdp"] = {"from": tg_capped, "to": _cap}
        # v3.21.0 A1：守卫留痕（仅触发时挂出 → 旧输入键集合不变）
        if tg_meta:
            out["terminal_guard"] = tg_meta
        if tguard["violation"]:
            out["terminal_guard"] = out.get("terminal_guard") or tguard
        # v3.21.0 A6：终值占比档位（tv_share_guard=true 时挂出并判定）
        if self.tv_share_guard and tv_share_v is not None:
            grade, level, msg = "unknown", None, ""
            for th, g, lv, m in TV_SHARE_GRADES:
                if tv_share_v < th:
                    grade, level, msg = g, lv, m
                    break
            out["tv_share_grade"] = {"tv_share": tv_share_v, "grade": grade,
                                     "level": level, "message": msg,
                                     "bands": "低<40% / 区间40–75% / 偏高75–85% / 极端>85%"}
            self._tv_share_level = level
        # v3.21.0 A7：市场隐含永续增速反解（opt-in）
        _itg = self.implied_terminal_growth_market(out)
        if _itg:
            out["implied_terminal_growth_market"] = _itg
        if getattr(self, "_profit_source", None):
            out["profit_source"] = self._profit_source
            out["profit_basis"] = getattr(self, "_profit_basis", None)
        if fcff_out:
            out["fcff"] = fcff_out
        # v3.23.0 D6/D7：报表驱动口径留痕（仅激活时挂出 → 缺省键集合不变）
        if drivers_out:
            out["cashflow_drivers"] = drivers_out
        # v3.23.0 D1：折现时点留痕（仅 mid_year 时挂出）
        if mid_year:
            out["discount_timing"] = {
                "mode": "mid_year",
                "exponent": "显式期 (t−0.5)；终值 (n−0.5)",
                "note": "年中折现：现金流按年中发生，较年末口径增加约 WACC/2 的现值（WACC 8.8% ≈ +4.4%）",
            }
        # v3.23.0 D9：再投资一致性（仅开关开启时挂出）
        if self._reinv_check is not None:
            out["reinvestment_check"] = self._reinv_check
        if tv_range:
            out["tv_range"] = tv_range
            out["tv_exit_multiple"] = tv_exit
        # v3.16.0 Layer 1：增速路径留痕（lifecycle_mode=auto 时挂出）
        if gs_detail:
            out["growth_schedule"] = {**gs_detail, "seq": [round(g, 4) for g in growth_seq]}
            if gs_detail.get("stage"):
                out["lifecycle_stage"] = gs_detail["stage"]
            # v3.25.0：逐行来源标签（首年=first_year / 中间=mu+shock / 末端=terminal）
            # 原实现 growth_seq 只是裸数值数组，报告无法说明"某一年增速凭什么是这个数"。
            if gs_detail.get("rows"):
                out["growth_seq_detail"] = [
                    {"t": r["t"], "g": round(r["g"], 4), "src": r.get("src"),
                     "clamped_by": r.get("clamped_by")} for r in gs_detail["rows"]]
            if gs_detail.get("model") == "space_state":
                out["growth_model"] = {
                    "model": "space_state", "p": gs_detail.get("p"),
                    "kappa": gs_detail.get("kappa"),
                    "cap_life_years": gs_detail.get("cap_life_years"),
                    "g1": gs_detail.get("g1"), "g1_source": gs_detail.get("g1_source"),
                    "mu0": gs_detail.get("mu0"), "mu0_source": gs_detail.get("mu0_source"),
                    "mu0_degraded": gs_detail.get("mu0_degraded"),
                    "mu0_clamped_by": gs_detail.get("mu0_clamped_by"),
                    "u1_pp": gs_detail.get("u1_pp"), "sgr_source": gs_detail.get("sgr_source"),
                    "bounds": gs_detail.get("bounds"),
                    "closure": gs_detail.get("closure"),
                    "shock_flag": gs_detail.get("shock_flag"),
                    "note": gs_detail.get("note"),
                }
        # v3.16.0 P0：现金流计划与再投资一致性（cashflow_model=p0 时挂出）
        if cashflow_schedule:
            out["cashflow_schedule"] = cashflow_schedule
            roic_v = cashflow_schedule.get("roic") or 0
            g_hi = [r for r in cashflow_schedule.get("rows", []) if roic_v and r["growth"] > roic_v]
            out["reinvestment_consistency"] = {
                "roic": roic_v,
                "violations": len(g_hi),
                "g_over_roic_years": [r["t"] for r in g_hi],
                "note": ("增速未超 ROIC 支撑上限（g ≤ ROIC×RR 守恒成立）" if not g_hi
                         else f"{len(g_hi)} 个年份增速超过 ROIC 支撑上限，须提高 ROIC 或下调增速"),
            }
        return out

    # ---------- 情景化综合（v2.0：修正项分层，DCF 为内在价值不受市场修正） ----------
    def scenario(self, name, q, gw, gw_reason, ff, extra=None):
        """情景估值（v2.2.0：extra 传入 run() 预计算的统计强化值）。
        修正项（质量/商誉/因子）计算一次三情景共用；舆情 impact_map 为假设层局部叠加（不进 SCENARIO_DEFAULTS）。"""
        extra = extra or {}
        ov = self.scen_ov.get(name, {})
        p = {**SCENARIO_DEFAULTS[name], **ov}
        # v3.21.0 A5：永续增速进入情景（缺省 flat=0；tg_adj_pp 仅在生效时写入 p，避免键集合外泄）
        tg_adj_pp = 0.0
        if self.tg_scenario_mode == "stepped":
            tg_adj_pp = float(ov.get("tg_adj_pp", self.scenario_tg_adj_pp.get(name, 0.0)))
            p["tg_adj_pp"] = tg_adj_pp
        elif "tg_adj_pp" in ov:
            tg_adj_pp = float(ov["tg_adj_pp"])
            p["tg_adj_pp"] = tg_adj_pp
        # v3.21.0 B4：情景增速步长按历史波动率（cva_sigma 时覆盖 SCENARIO_DEFAULTS 的 ±10pp）
        if self.scenario_step_mode == "cva_sigma" and "growth_adj_pp" not in ov:
            _st = self._growth_step()
            if _st.get("applied") and name in ("bear", "bull"):
                p["growth_adj_pp"] = _st["step_pp"] if name == "bull" else -_st["step_pp"]
        # v3.23.0 D5：利润率情景步长按自身 σ（clamp[1,3]pp），与收入步长分开
        if self.margin_step_mode == "cva_sigma" and "margin_adj_pp" not in ov:
            _ms = self.margin_step()
            if _ms.get("applied") and name in ("bear", "bull"):
                p["margin_adj_pp"] = _ms["step_pp"] if name == "bull" else -_ms["step_pp"]
        # v2.2.0：舆情影响映射（假设层）局部叠加——仅激活时生效，缺省逐位等价 v2.1.0
        smap = extra.get("sentiment_structure") or {}
        # v3.18.0：记录假设层影响映射是否生效（供舆情强度去相关折让判定，避免 multiple_factor 重复计费）
        self._assumption_impact_active = bool(smap.get("enabled") and (smap.get("impact_map") or {}))
        if smap.get("enabled"):
            im = smap["impact_map"]
            p["growth_adj_pp"] += im.get("growth_adj_pp", 0.0)
            p["margin_adj_pp"] += im.get("margin_adj_pp", 0.0)
            p["wacc_adj_pp"] += im.get("wacc_adj_pp", 0.0)
            p["multiple_factor"] *= im.get("multiple_factor", 1.0)
            # v3.21.0 A5：消费 terminal_growth_adj_pp（原先由 sentiment_structured 产出但**全库 0 处消费**
            # 的死字段）；仅在 stepped 模式下叠加，flat 缺省保持逐位不变
            if self.tg_scenario_mode == "stepped":
                p["tg_adj_pp"] += im.get("terminal_growth_adj_pp", 0.0)
            if name == "bear" and any(r.get("severity") == "high" and r.get("impact_target") == "wacc"
                                      for r in smap.get("risks_summary", [])):
                p["wacc_adj_pp"] += 0.5
                self.warnings.append("Bear 情景：存在高严重度 WACC 相关风险，WACC 额外 +0.5pp（保守处理）。")
        adj_pp = p["growth_adj_pp"]
        margin_adj_pp = p["margin_adj_pp"]
        mf = p["multiple_factor"]
        wacc_adj_pp = p["wacc_adj_pp"]
        sent_factor = p["sentiment_factor"]
        tg_adj_pp = _nn(p.get("tg_adj_pp"), tg_adj_pp)

        comp = self.comparable_valuation(adj_pp, margin_adj_pp, mf)
        # v2.6.0 B7：dcf 传入 comp 复用可比倍数（终值退出倍数交叉）
        dcf = self.dcf_valuation(adj_pp, margin_adj_pp, wacc_adj_pp, comp, tg_adj_pp)

        # v3.22.0 修复③：comp_v 三态——原 `or 0.0` 在可比法不可用时静默归零，但权重仍占 50%，
        # 综合值缩水一半且不报错（结果看似正常）。renormalize 模式下剔除该法并按剩余权重再归一。
        _comp_syn = comp.get("synthesis") or {}
        _comp_raw = _comp_syn.get("base_value")
        comp_available = _comp_raw is not None
        comp_v = float(_comp_raw) if comp_available else 0.0
        dcf_v = dcf["equity_value"]

        # v3.19.0 P6-B/C：路由主方法的引擎取值分支（rNPV/SOTP）——使「声明权重」可被综合式读取（消除静默少算）。
        # 缺省（未 opt-in）时两者 value=None → 不进入综合（键与数值逐位不变）。
        rnpv_v = None
        if self.enable_rnpv or (self.d.get("rnpv") or {}).get("enabled"):
            _rn = self.rnpv_valuation()
            if _rn.get("enabled") and _rn.get("value") is not None:
                rnpv_v = float(_rn["value"])
        sotp_v = None
        if self.enable_sotp or (self.d.get("sotp") or {}).get("enabled"):
            _st = self.sotp_valuation()
            if _st.get("enabled") and _st.get("value") is not None:
                sotp_v = float(_st["value"])
        # 替代法取值为「情景无关」的资产口径（rNPV/SOTP 不由情景增速驱动），三情景同值（与 NAV 同族）
        alt_v = {}
        if rnpv_v is not None:
            alt_v["rnpv"] = rnpv_v
        if sotp_v is not None:
            alt_v["sotp"] = sotp_v

        # 修正项分层：市场口径修正（质量/商誉/因子）作用于②可比法；情绪独立为③市场舆情
        sent, sent_reason = self.sentiment_adjust(sent_factor)   # v3.15.0：不再传 q_score
        ff_adj = float(ff.get("ff_factor_adjust", 0.0))
        total_adj = q["adjustment_pct"] + gw + sent + ff_adj     # 兼容留痕（旧口径合成值）

        # v2.4.0：流动性折扣（非上市股权整体折价）乘在市场法结果上；DCF 不折
        liq = self._liquidity_discount  # run() 预计算，缺省 0.0
        # v3.22.0 修复③：可比法不可用时的权重处置
        #   zero_silent（缺省）= 旧行为：权重照占、取值按 0（综合值静默缩水，不报错）
        #   renormalize      = 剔除可比法（及共用 comp_v 的舆情路径），按剩余权重再归一
        w = dict(self.weights)
        if not comp_available and self.method_drop_mode == "renormalize":
            _drop = [k for k in ("comparable", "sentiment") if w.get(k)]
            for _k in _drop:
                w[_k] = 0.0
            _tot = sum(w.values())
            if _tot > 0:
                w = {_k: _v / _tot for _k, _v in w.items()}
            if name == "base":
                self._method_drop = {
                    "dropped": _drop, "mode": "renormalize",
                    "raw_weights": {k: round(self.weights.get(k, 0.0), 4) for k in _drop},
                    "renormalized": {k: round(v, 4) for k, v in w.items()},
                    "reason": ("可比法 synthesis.base_value 为空（无有效倍数样本），已从综合式中剔除，"
                               "并按剩余方法权重再归一；原口径把该法按 0 计入 → 综合值静默缩水"),
                }
                self.warnings.append(
                    "可比法无可信取值（synthesis.base_value 为空），已从综合权重中剔除并按剩余方法再归一；"
                    f"剔除项 {('、'.join(_drop))}，剩余权重 "
                    f"{'／'.join(f'{k} {v:.2f}' for k, v in w.items() if v > 0)}。")
        # v3.17.0 P2/P4：舆情口径（path=独立路径 | correction=修正层）与带宽分化
        sent_corr, sent_band, sent_signal = self._sentiment_correction(sent, sent_factor)
        # 兜底绑定：任一分支未赋值时保持键集合稳定（防御 UnboundLocalError）
        comp_quality = comp_sent = comp_adj = None
        sent_impact = 0.0
        if self.four_part_mode and self.sentiment_layer == "correction":
            # ---- P2 修正层口径：舆情不独立占权重，作为可比法的**乘性修正系数**（消除对 comp_v 的重复计费）----
            # 口径：market = comp_v × (1+q+gw+ff) × (1+liq折) × (1+sent_corr)；舆情增量 = market × sent_corr（一阶）
            comp_nosent = comp_v * (1.0 + q["adjustment_pct"] + gw + ff_adj) * (1.0 - liq)   # 无舆情修正的市场法值
            comp_quality = comp_nosent * (1.0 + sent_corr)                                   # 含舆情修正（P2 修正层）
            comp_sent = comp_quality                                                         # 修正层下 ②③ 同值（③ 权重为 0）
            w_comp = w.get("comparable", 0.5) + w.get("sentiment", 0.0)                       # 舆情原权重回归可比法
            value = comp_quality * w_comp + w.get("dcf", 0.0) * dcf_v
            # v3.19.0：替代主方法（rNPV/SOTP）按其权重进入综合（权重已由 resolve_method_set 归一化）
            for _m, _v in alt_v.items():
                value += w.get(_m, 0.0) * _v
            sent_impact = comp_nosent * sent_corr * w_comp                                    # 舆情贡献（供披露）
            comp_adj = (comp_quality * w_comp + w.get("dcf", 0.0) * dcf_v + sum(w.get(_m, 0.0) * _v for _m, _v in alt_v.items())) \
                / (w_comp + w.get("dcf", 0.0) + sum(w.get(_m, 0.0) for _m in alt_v)) \
                if (w_comp + w.get("dcf", 0.0) + sum(w.get(_m, 0.0) for _m in alt_v)) else comp_quality
            if liq and name == "base":
                self._liq_impact = comp_v * (1.0 + q["adjustment_pct"] + gw + ff_adj) * liq
        elif self.four_part_mode:
            # v3.15.0 四部分：②可比法（质量+商誉+因子，含 liq）＋③市场舆情（仅情绪，不含 liq）
            comp_quality = comp_v * (1.0 + q["adjustment_pct"] + gw + ff_adj) * (1.0 - liq)
            comp_sent = comp_v * (1.0 + sent_corr)
            w_sent = w.get("sentiment", 0.0)
            w_comp = w.get("comparable", 0.0)
            mw = w_comp + w_sent
            value = comp_quality * w_comp + comp_sent * w_sent + w.get("dcf", 0.0) * dcf_v
            # v3.19.0：替代主方法（rNPV/SOTP）按其权重进入综合
            for _m, _v in alt_v.items():
                value += w.get(_m, 0.0) * _v
            # 市场法综合值（②③在市场权重内归一化加权）→ 供 method_cv/分歧度比较，语义与旧口径一致
            comp_adj = (comp_quality * w_comp + comp_sent * w_sent) / mw if mw else comp_quality
            sent_impact = (comp_sent - comp_quality) * w_sent
            if liq and name == "base":
                self._liq_impact = comp_v * (1.0 + q["adjustment_pct"] + gw + ff_adj) * liq
        else:
            # 旧口径（逐位回退）：情绪并入可比法（comparable 权重 + sentiment 权重共同承担）
            comp_adj = comp_v * (1.0 + total_adj) * (1.0 - liq)
            if liq and name == "base":
                self._liq_impact = comp_v * (1.0 + total_adj) * liq
            value = comp_adj * (w.get("comparable", 0.0) + w.get("sentiment", 0.0)) + w.get("dcf", 0.0) * dcf_v
            for _m, _v in alt_v.items():
                value += w.get(_m, 0.0) * _v
            comp_quality = comp_adj
            comp_sent = comp_v * (1.0 + sent)
            sent_impact = 0.0

        adjustments = {
            "quality": {"adjustment_pct": q["adjustment_pct"], "score": q["score"],
                        "indicators": q["detail"]},
            "goodwill": {"adjustment_pct": gw, "reason": gw_reason},
            "sentiment": {"adjustment_pct": sent, "reason": sent_reason},
            "ff_calibration": ff,
            "total_market_adjust": round(total_adj, 4),
        }
        out_sc = {
            "name": name, "params": p,
            "comparable": comp, "dcf": dcf,
            "adjustments": adjustments,
            "comparable_raw": (round(comp_v, 2) if comp_available
                               else (None if self.method_drop_mode == "renormalize" else 0.0)),
            "comparable_adjusted": round(comp_adj, 2),
            "dcf_value": round(dcf_v, 2),
            "value": round(value, 2),
        }
        # v3.22.0 修复③：可比法剔除留痕（仅 renormalize 且实际剔除时挂出 → 缺省键集合不变）
        if self._method_drop and name == "base":
            out_sc["method_drop"] = self._method_drop
        # v3.19.0 P6-B/C：替代主方法取值留痕（仅启用时挂出 → 缺省键集合不变）
        if alt_v:
            out_sc["alternative_methods"] = {
                m: {"value": round(v, 2), "weight": round(w.get(m, 0.0), 4),
                    "contribution": round(w.get(m, 0.0) * v, 2)} for m, v in alt_v.items()
            }
        # v3.15.0：四部分口径下的分层留痕键；旧口径不挂出 → 情景键集合逐位不变
        if self.four_part_mode:
            out_sc["comparable_quality"] = round(comp_quality, 2)
            out_sc["comparable_sentiment"] = round(comp_sent, 2)
        # v3.17.0 P2/P4：舆情修正层留痕（仅 sentiment_layer=correction 时挂出，缺省 path 不挂出 → 键集合不变）
        if self.sentiment_layer == "correction" and self.four_part_mode:
            out_sc["sentiment_correction"] = {
                "layer": "correction",
                "adjust_mode": self.sentiment_adjust_mode,   # v3.18.0：legacy | strength
                "band_pct": round(sent_band, 4),
                "correction_pct": round(sent_corr, 4),
                "impact_value": round(sent_impact, 2),
                "signal": sent_signal,
                "note": "P2 舆情从独立路径降为可比法修正系数（消除对 comp_v 的重复计费）；"
                        "P4 带宽按企业类型分化（startup/growth_tech ±15%、growth ±10%、cyclical ±8%、mature/financial/decline ±5%、private 0%）；"
                        "v3.18.0 strength 口径：方向=sign(sent)、强度=k_signal，幅度 = band×k_signal×min(|sent|/10%,1)，上限 band×1.60",
            }
        return out_sc

    # ---------- 敏感性 ----------
    def sensitivity(self, base_adj=None):
        """确定性敏感性（v2.2.0：WACC 敏感性采用 base 情景有效增速调整——含舆情 impact_map 假设层，
        保证与 base 情景 DCF 口径一致；旧输入无 impact_map 时 base_adj 全 0，行为不变）。"""
        base_adj = base_adj or {}
        g_adj = base_adj.get("growth", 0.0)
        m_adj = base_adj.get("margin", 0.0)
        g1 = self._g1()
        margin = _nn(self.fin.get("net_margin"), 0.0)
        comp = self.comparable_valuation()
        pe_med = (comp.get("pe") or {}).get("median")
        ps_med = (comp.get("ps") or {}).get("median")
        rev = _nn(self.fin.get("revenue_latest_ttm"), 0.0)
        levels = [-0.2, -0.1, 0.0, 0.1, 0.2]
        grid = {}
        if pe_med:
            formula = "矩阵=TTM营收×(1+g1×(1+Δg))×净利率×(可比PE中位数×(1+Δ倍数))，PE口径"
            for g_adj_lv in levels:
                row = {}
                for m_adj_lv in levels:
                    val = rev * (1 + g1 * (1 + g_adj_lv)) * margin * pe_med * (1 + m_adj_lv)
                    row[f"{m_adj_lv:+.0%}"] = round(val, 2)
                grid[f"{g_adj_lv:+.0%}"] = row
        elif ps_med:
            formula = "矩阵=TTM营收×(1+g1×(1+Δg))×(可比PS中位数×(1+Δ倍数))，PS口径（可比PE缺失：亏损/未盈利场景自动回退）"
            for g_adj_lv in levels:
                row = {}
                for m_adj_lv in levels:
                    val = rev * (1 + g1 * (1 + g_adj_lv)) * ps_med * (1 + m_adj_lv)
                    row[f"{m_adj_lv:+.0%}"] = round(val, 2)
                grid[f"{g_adj_lv:+.0%}"] = row
        else:
            formula = "无有效倍数样本，敏感性矩阵不可用（检查可比输入）"
        wacc_sens = {}
        for dw in (-0.01, 0.0, 0.01):
            wacc_sens[f"{dw:+.0%}"] = round(self.dcf_valuation(g_adj, m_adj, dw * 100.0, comp)["equity_value"], 2)
        return {"growth_pe_matrix": grid, "wacc_sensitivity": wacc_sens, "note": formula}

    # ---------- IPO 定价约束检查 ----------
    def ipo_check(self, mid_value):
        fin = self.fin
        checks = {}
        # v2.14.3：显式 null 不再覆盖默认值（原 get(k, 0.0) 在键存在且值为 None 时返回 None → 下游 TypeError）
        shares = fin.get("total_shares_after_issue") or 0.0
        issue = fin.get("issue_shares") or 0.0
        np_ttm = fin.get("net_profit_latest_ttm") or 0.0
        checks["price_per_share"] = round(mid_value / shares, 2) if shares else None
        checks["diluted_eps"] = round(np_ttm / shares, 4) if shares else None
        # v2.11.4：已上市公司可选传入实际发行价（fundraising.issue_price_actual）——
        # 缺省时 price_per_share 即「模型隐含发行价（估值中枢 ÷ 发行后总股本）」，
        # 对已定价/已上市标的会被误读为实际发行价，故显式标注口径；提供实际价时
        # 增列实际市值、实际募资额与「实际 vs 模型」偏离，模型隐含值另行保留。
        fr0 = self.d.get("fundraising") or {}
        act_price = fr0.get("issue_price_actual")
        if act_price:
            checks["price_per_share_indicative"] = checks["price_per_share"]
            checks["price_per_share"] = round(float(act_price), 2)
            checks["price_source"] = "实际发行价（fundraising.issue_price_actual）"
            if shares:
                checks["issue_mktcap_actual"] = round(float(act_price) * shares, 2)
                if mid_value:
                    checks["price_status"] = (
                        f"实际发行市值 {checks['issue_mktcap_actual']:.2f} 亿元 vs 模型中枢 "
                        f"{round(mid_value, 2):.2f} 亿元（偏离 "
                        f"{(checks['issue_mktcap_actual'] - mid_value) / mid_value:+.1%}）")
            for k_in, k_out in (("issue_pe_actual", "issue_pe_actual"),
                                ("issue_pb_actual", "issue_pb_actual"),
                                ("listing_date", "listing_date"),
                                ("actual_raise", "actual_raise")):
                if fr0.get(k_in) is not None:
                    checks[k_out] = fr0[k_in]
        issue_pe = mid_value / np_ttm if np_ttm > 0 else None
        comp = self.comparable_valuation()
        comp_pe = (comp.get("pe") or {}).get("median")
        comp_ps = (comp.get("ps") or {}).get("median")
        rev_ttm = fin.get("revenue_latest_ttm", 0.0)
        checks["issue_pe"] = round(issue_pe, 1) if issue_pe else None
        checks["comparable_pe_median"] = comp_pe
        if issue_pe and comp_pe:
            dev = (issue_pe - comp_pe) / comp_pe
            checks["pe_deviation"] = round(dev, 4)
            if dev > 0.30 or dev < -0.20:
                checks["pe_status"] = f"预警⚠️（偏离{dev:+.1%}，需补充估值论证）"
            elif dev > 0.10:
                checks["pe_status"] = f"提示（偏离{dev:+.1%}，建议补充论证）"
            else:
                checks["pe_status"] = f"正常✅（偏离{dev:+.1%}）"
        else:
            checks["pe_status"] = "PE口径不可用（目标或可比未盈利），回退PS口径"
        # PS 口径发行约束（亏损/未盈利场景）
        issue_ps = mid_value / rev_ttm if rev_ttm > 0 else None
        checks["issue_ps"] = round(issue_ps, 1) if issue_ps else None
        checks["comparable_ps_median"] = comp_ps
        if issue_ps and comp_ps:
            dev_ps = (issue_ps - comp_ps) / comp_ps
            checks["ps_deviation"] = round(dev_ps, 4)
            if dev_ps > 0.30 or dev_ps < -0.20:
                checks["ps_status"] = f"预警⚠️（偏离{dev_ps:+.1%}）"
            elif dev_ps > 0.10:
                checks["ps_status"] = f"提示（偏离{dev_ps:+.1%}）"
            else:
                checks["ps_status"] = f"正常✅（偏离{dev_ps:+.1%}）"
        checks["raise_amount"] = round(issue * checks["price_per_share"], 2) if checks["price_per_share"] else None
        planned = (self.d.get("fundraising") or {}).get("planned_raise")
        if planned and checks["raise_amount"]:
            diff = (checks["raise_amount"] - planned) / planned
            checks["planned_raise"] = planned
            checks["raise_deviation"] = round(diff, 4)
            checks["raise_status"] = "超募⚠️" if diff > 0.1 else ("缩募⚠️" if diff < -0.1 else "匹配✅")
        fr = self.d.get("fundraising") or {}
        if fr.get("post_ipo_years_profit_add") or fr.get("post_ipo_years_revenue_add"):
            rev_add = fr.get("post_ipo_years_revenue_add", 0.0)
            profit_add = fr.get("post_ipo_years_profit_add", 0.0)
            ps_med = (self.comparable_valuation().get("ps") or {}).get("median") or 0.0  # v2.11.1：可比集无 PS 数据时不再 KeyError
            pe_med = comp_pe or 0.0
            checks["project_increment_value"] = round(rev_add * ps_med + profit_add * pe_med, 2)
            checks["project_target_year"] = fr.get("post_ipo_years_target_year", "达产后")
        if shares and issue:
            float_pct = issue / shares
            disc = 0.0 if float_pct >= 0.25 else (-0.05 if float_pct >= 0.10 else -0.08)
            checks["float_ratio"] = round(float_pct, 4)
            checks["liquidity_discount"] = disc
        checks["net_cash"] = _nn(fin.get("net_cash"), 0.0)
        return checks

    # ---------- 汇总 ----------
    def run(self):
        # v2.1.0：场景无关修正项只计算一次（原 3×scenario + sentiment 内部共 7 次 quality_score → 1 次）
        q = self.quality_score()
        gw, gw_reason = self.goodwill_adjust()
        ff = self.ff_calibration()
        # v2.4.0：输入数据校验与异常值检测（issues 非空时挂出 input_validation 块）
        input_issues = self._validate_input()
        for iss in input_issues:
            self.warnings.append(f"输入校验[{iss['level']}] {iss['field']}={iss.get('value')}: {iss['rule']}")
        # v2.2.0：统计强化预计算（全部可选激活，缺省不影响既有行为）
        wacc_m = self.wacc_model()
        cf_stats = self.cashflow_statistics()
        tri = self.growth_triangulation(cf_stats)
        smap = self.sentiment_structured()
        # v2.3.0：FCF 比率三层校准 / 可比交易锚 / 最近融资价格锚
        # v3.24.0（F1）：惰性模式不预计算——比率法只在「④ 比率档」被真正采用时求值。
        # `preferences.diagnostics_fcf_ratio=true` 强制求值（阶梯对照需要「若走比率法会差多少」），
        # 并标 diagnostic_only，确保它不会被误当成驱动值。
        _diag_ratio = bool(self.pref.get("diagnostics_fcf_ratio"))
        if self.fcf_ratio_lazy and not _diag_ratio:
            fcfr = {"enabled": False, "skipped": True, "pending": True}
        else:
            fcfr = self._get_fcfr()
            if _diag_ratio and fcfr.get("enabled"):
                fcfr = {**fcfr, "diagnostic_only": True}
                self._fcfr_cache = fcfr
        txv = self.transaction_valuation()
        rfa = self.recent_financing_anchor()
        # v2.6.0 B1：FCFF 报表级口径开关（fcff_mode=true 且 ebit/capex 齐备时 dcf_valuation 激活）
        self._fcff_mode = bool(self.fin.get("fcff_mode"))
        # v3.22.0 修复④：重资产标的（CapEx/营收 > 8%）仍走「净利×FCF 比率」时主动建议开启 fcff_mode。
        # 比率法不含再投资约束，资本开支强度越高、FCFF 被高估越多（格力实测与报表级差 22.9%）。
        # v3.24.0（F3）：若报表驱动逐年口径（dcf_drivers）**已生效**，则「建议改用报表口径」是
        # 无的放矢——先判其是否具备激活条件（与 statement_fcff_series 的入参要求一致）。
        _drv_on = (bool(self.drivers) and bool(self.drivers.get("enabled", True))
                   and (self.drivers.get("ebit_margin") is not None
                        or (self.drivers.get("cost_ratio") is not None
                            and self.drivers.get("expense_ratio") is not None))
                   and bool(self.drivers.get("base_revenue")
                            or self.fin.get("revenue_latest_ttm")))
        if self.fcff_suggest and not self._fcff_mode and not _drv_on:
            _cr = self.fin.get("capex_to_revenue")
            _cr_src = "公司披露口径"
            if _cr is None:
                # v3.24.0：惰性模式下 fcfr 未启用（未计算）→ 不得依赖被淘汰口径的副产物。
                # 改用「披露 capex ÷ 披露营收」现算（口径独立、可复算）；两者缺一则不提示。
                if fcfr.get("enabled"):
                    _cr = fcfr.get("comparable_capex_to_rev")
                    _cr_src = "可比集中位"
                else:
                    _cap_l = self.fin.get("capex_latest")
                    _rev_l = self.fin.get("revenue_latest_ttm")
                    if _cap_l is not None and _rev_l:
                        _cr = float(_cap_l) / float(_rev_l)
                        _cr_src = "披露 capex ÷ 披露营收（现算）"
            _triggers = []
            if _cr is not None and float(_cr) > FCFF_SUGGEST_CAPEX_RATIO:
                _triggers.append("capex_intensity")
            _ocf_q = self.fin.get("ocf_to_net_profit")
            _ocf_trig = _ocf_q is not None and float(_ocf_q) > FCFF_SUGGEST_OCF_RATIO
            if _ocf_trig:
                _triggers.append("ocf_quality")
            if _triggers:
                _has_ebit = self.fin.get("ebit") is not None
                self._fcff_suggest_meta = {
                    "capex_to_revenue": (round(float(_cr), 4) if _cr is not None else None),
                    "source": _cr_src if _cr is not None else None,
                    "threshold": FCFF_SUGGEST_CAPEX_RATIO, "ebit_available": _has_ebit,
                    "trigger": _triggers,
                    "ocf_to_net_profit": (round(float(_ocf_q), 4) if _ocf_q is not None else None),
                    "ocf_threshold": FCFF_SUGGEST_OCF_RATIO,
                    "recommend": ("启用 financials.fcff_mode=true 并以 capex_by_year 挂募投产能节奏"
                                  if _has_ebit else "补 financials.ebit 与 capex 后启用 fcff_mode=true"),
                    "reason": (("资本开支/营收超过 8%，属重资产口径；「净利×FCF 比率」漏扣资本开支，"
                                "FCFF 系统性偏高") if "capex_intensity" in _triggers else
                               (f"OCF/净利 {float(_ocf_q):.2f} 超过 {FCFF_SUGGEST_OCF_RATIO:g} 阈值——"
                                "经营现金流含非经营性流入（典型：并表财务公司的吸收存款），"
                                "「净利×FCF 比率」会把这部分当成可持续自由现金流，FCFF 系统性偏高")),
                }
                if "capex_intensity" in _triggers:
                    self.warnings.append(
                        f"资本开支/营收 {float(_cr):.1%} 超过 {FCFF_SUGGEST_CAPEX_RATIO:.0%} 阈值（{_cr_src}），"
                        f"当前仍用「净利×FCF 比率」口径（不含再投资约束），重资产标的 FCFF 易被高估；"
                        f"建议开启 financials.fcff_mode=true" + ("。" if _has_ebit else "（需补 ebit/capex）。"))
                if _ocf_trig:
                    self.warnings.append(
                        f"OCF/净利 {float(_ocf_q):.2f} 超过 {FCFF_SUGGEST_OCF_RATIO:g} 阈值——"
                        f"经营现金流可能含非经营性流入（并表财务公司的吸收存款 / 客户资金等），"
                        f"「净利×FCF 比率」口径会系统性高估 FCFF；建议改用报表驱动逐年口径"
                        f"（顶层 dcf_drivers 块）而非仅 fcff_mode。")
        # v2.4.0：流动性折扣（必须在 scenario 前设置）/ 净资产法 / 资产类型适配
        ld = self.liquidity_discount()
        ad = self.asset_type_adapter()
        if ad.get("enabled"):
            for w in ad.get("warnings") or []:
                self.warnings.append(f"资产适配: {w}")
        nav = self.nav_valuation()
        # v3.17.0 P5：金融路由主方法（RIM 剩余收益 / DDM 股利折现），仅 opt-in（preferences 显式启用）时计算；
        # 缺省不计算 → 旧输入键集合与数值均不变（零回归）。
        rim = self.rim_valuation() if self.pref.get("enable_rim") else {"enabled": False}
        ddm = self.ddm_valuation() if self.pref.get("enable_ddm") else {"enabled": False}
        # v3.19.0 P6-B/C：路由主方法的引擎取值分支（rNPV 管线药企 / SOTP 控股平台），仅 opt-in 时计算
        rnpv = self.rnpv_valuation() if (self.enable_rnpv or (self.d.get("rnpv") or {}).get("enabled")) else {"enabled": False}
        sotp = self.sotp_valuation() if (self.enable_sotp or (self.d.get("sotp") or {}).get("enabled")) else {"enabled": False}
        if ld.get("enabled"):
            self._liquidity_discount = ld["discount_pct"]
        # 有效 wacc / 增速 / 终值增速（用户显式优先，未显式用模型/三角值）
        if wacc_m.get("enabled"):
            self._wacc_eff = wacc_m["wacc_used"]
        # v3.22.0 修复⑤：只开 cva_2pct（永续增速 6%→2%）却不改 WACC=11% 时，终值倍数 21.20× → 11.33×
        # （−46.6%），用户以为只动了永续假设、实际砍掉近一半终值。开启 require_explicit_wacc 时给出可复算告警。
        if self.require_explicit_wacc and self.tg_default_mode == "cva_2pct":
            _w_explicit = self.fin.get("wacc")
            _w_modeled = bool(wacc_m.get("enabled") and wacc_m.get("wacc_used") is not None)
            if _w_explicit is None and not _w_modeled:
                self._wacc_explicit_warned = True
                self.warnings.append(
                    f"永续增速已切 cva_2pct（2%），但 WACC 仍为硬编码缺省 {DEFAULT_WACC:.0%}："
                    f"终值倍数将由 {_TV_MULTIPLE_LEGACY:.2f}× 降至 {_TV_MULTIPLE_CVA_TG_ONLY:.2f}×"
                    f"（{(_TV_MULTIPLE_CVA_TG_ONLY / _TV_MULTIPLE_LEGACY - 1) * 100:+.1f}%），"
                    f"该降幅源于 WACC 与 g 不匹配、而非永续假设施加；请显式给 financials.wacc，"
                    f"或开启 dcf_cost.wacc_default_mode=capm_auto。")
        if tri.get("enabled"):
            user_gf = self.fin.get("growth_forecast") or {}
            if user_gf:
                first = list(user_gf.values())[0]
                if abs(first - tri["implied_growth"]) > 0.10:
                    self.warnings.append(
                        f"预测增速与三角参照偏离（{first:.0%} vs 三角 {tri['implied_growth']:.0%}），需补充依据。")
            else:
                self._gf_eff = {"y1": tri["implied_growth"], "y2": tri["implied_growth"],
                                "y3": tri["implied_growth"]}
            user_tg = self.fin.get("terminal_growth")
            if user_tg is not None and tri.get("implied_terminal_growth") is not None:
                if abs(user_tg - tri["implied_terminal_growth"]) > 0.02:
                    self.warnings.append(
                        f"终值增速与三角参照偏离（{user_tg:.0%} vs 三角 {tri['implied_terminal_growth']:.0%}），需补充依据。")
            elif user_tg is None and tri.get("implied_terminal_growth") is not None:
                self._tg_eff = tri["implied_terminal_growth"]
        # ============ v3.16.0 三层计划：Layer 0 判别门 → Layer 2 参数底座 → Layer 1 生命周期 ============
        # Layer 2 行业参数底座（校验锚 + 参数第 4 档来源）
        ind = self.industry_params_resolve()
        if ind.get("enabled"):
            self._industry = ind
        # v3.21.0 A3/A4：永续增速取值链（chain 模式在行业参数就位后解析：用户显式 > g_lt > 通胀锚）
        _tgm = self.resolve_terminal_growth(tri)
        if _tgm:
            self._tg_meta = _tgm
            self._tg_eff = _tgm["value"]
        # v3.25.0：三锚口径（多来源交叉取中位 + 双上限）优先于 chain（逐级回落）。
        # chain 的缺陷：取值完全取决于"哪一级先命中"——行业参数一命中，SGR 与市场隐含
        # 就被弃置，等于用单一口径冒充交叉验证。v2 口径下 chain 结果保留为对照（_tg_meta）。
        _tgv2 = self.resolve_terminal_growth_v2(tri, wacc=getattr(self, "_wacc_eff", None))
        if _tgv2 and _tgv2.get("applied"):
            self._tg_meta2 = _tgv2
            self._tg_eff = _tgv2["value"]
            if _tgm and abs(_tgm["value"] - _tgv2["value"]) > 1e-9:
                self.warnings.append(
                    f"永续增速口径切换：chain 逐级回落得 {_tgm['value']:.2%}"
                    f"（来源 {_tgm['picked']}），三锚取中位得 {_tgv2['value']:.2%}"
                    f"（锚 {list(_tgv2['anchors'])}），已采用后者。")
        # v3.21.0 B2：历史增速形态判定（advisory 只判形态、不改数值）
        _hist = None
        if self.growth_history_mode == "advisory":
            rev_by_year = _series_from_year_dict(self.fin.get("revenue_by_year") or {})
            hist = [rev_by_year[i] / rev_by_year[i - 1] - 1.0
                    for i in range(1, len(rev_by_year)) if rev_by_year[i - 1]]
            _hist = growth_history_shape(hist)
            self._history_shape = _hist
            _gf_now = self.fin.get("growth_forecast") or {}
            if _gf_now and _hist.get("history_case"):
                _gf_vals = [v for v in _gf_now.values() if v is not None]
                _mismatch = (_hist["history_case"].startswith("正负切换") and _gf_vals and min(_gf_vals) >= 0)
                if _mismatch:
                    self.warnings.append(
                        f"增速路径与历史形态不匹配：历史为「{_hist['history_case']}」"
                        f"（近三年 {_hist['metrics']['H1']:.2%}/{_hist['metrics']['H2']:.2%}/"
                        f"{_hist['metrics']['H3']:.2%}，σ {_hist['metrics']['sigma_pp']:.2f}pp），"
                        f"而假设路径全为正增长；须补业务驱动证据（订单/产能/政策）。")
        # v3.23.0 D4/D5：历史形态取值矩阵 + 利润率步长（均在情景计算前就位）
        self.growth_rule()
        if self.margin_step_mode == "cva_sigma":
            self.margin_step()
        # v3.23.0 D3：Capex/D&A 量级勾稽（拦「capex 异常偏低」，8% 营收阈值拦不住的一类错误）
        if self.capex_check:
            _cc = capex_magnitude_check(self.fin.get("capex"), self.fin.get("d_a"), self.capex_da_band)
            self._capex_check_meta = _cc
            if _cc.get("applied") and _cc.get("level") == "warning":
                self.warnings.append(_cc["message"])
        # v3.23.0 D8：非经常性损益/异常低税率的正常化提示（纯诊断，不改数值）
        if self.normalization_hint:
            _hints = []
            _nrr = self.fin.get("non_recurring_ratio")
            if _nrr is not None and abs(float(_nrr)) > 0.15:
                _hints.append(f"非经常性损益占净利 {float(_nrr):.1%}（>15%），建议 enable_normalized=true 或改用扣非口径")
            _tx = (self.fin.get("wacc_params") or {}).get("tax_rate")
            if _tx is not None and float(_tx) < 0.10:
                _hints.append(f"有效税率 {float(_tx):.1%}（<10%），须确认税收优惠可持续性，否则税率正常化后 FCFF 下降")
            _basis = getattr(self, "_profit_basis", None)
            if _basis and str(_basis).startswith(("semiannual", "quarterly")) and _nrr is None:
                _hints.append(f"净利披露档为 {_basis}（年化口径），非经常性损益未单独剔除，请核实")
            self._normalization_hint_meta = {"checked": True, "hints": _hints,
                                             "profit_basis": _basis,
                                             "note": "仅提示，不改数值；开启 enable_normalized 才实际切换口径"}
            if _hints:
                self.warnings.append("正常化提示：" + "；".join(_hints))
        # Layer 0 前提判别门（v3.16.0；v3.16.2：dcf 权重封顶改在 B4 之后施加，避免被 B4 重算覆盖）
        fw = self.framework_admissibility()
        if fw.get("enabled"):
            self._framework = fw
        # Layer 1 生命周期判别（lifecycle_mode=auto 时驱动增速模型与权重调节）
        lc = self.classify_lifecycle()
        if lc.get("enabled"):
            self._lifecycle = lc
        # B4 权重条件化（path_weight_mode=adaptive：w = normalize(base × k_lifecycle × k_admissible)）
        # v3.16.2：base 取「用户/模板解析后的基准权重」(self.weights)，而非 DEFAULT 常量——尊重 preferences.weights
        path_weights = None
        if self.path_weight_mode == "adaptive":
            base_w = {"dcf": self.weights["dcf"], "comparable": self.weights["comparable"],
                      "sentiment": self.weights["sentiment"]}
            k_adm = 1.0
            if fw.get("enabled") and fw.get("dcf_admissible") is False:
                k_adm = 0.0
            # v3.28.0：达莫达兰六阶段方法定位表（opt-in）——直接权重，不乘 base、不归一化
            if self.lifecycle_weight_mode == "damodaran_table":
                dmd = self.damodaran_stage(lc)
                tw = dict(dmd.get("weights") or {})
                if not tw:
                    # 判别未启用时不得凭空造阶段：回落 base，并在留痕里明示
                    tw = dict(base_w)
                    dmd = {"enabled": False, "stage": None, "label": None,
                           "reason": "生命周期判别未启用，达莫达兰表不可派生，回落 base 权重"}
                # ★保护一：DCF 前提不成立（Layer 0 路由否决）→ dcf 必须为 0。
                # ★保护二：**base 权重为 0 的路径 = 用户显式禁用，表不得复活**。
                #   反例（中航沈飞）：输入层显式 weights.dcf=0（「DCF 准入 ≠ DCF 可算」的处置），
                #   若表直接覆盖成 0.40，会把已判定「算不出有意义数」的 DCF 重新拉进来，中枢 −37.76%。
                #   这与坑 10/31「用户显式被静默压制」同族，故在表生效前先剔除。
                blocked = set()
                if k_adm == 0.0:
                    blocked.add("dcf")
                blocked |= {k for k in base_w if abs(float(base_w[k])) < 1e-9}
                if blocked:
                    live = [k for k in tw if k not in blocked]
                    rest = sum(tw[k] for k in live)
                    if rest > 0:
                        tw = {k: (0.0 if k in blocked else tw[k] / rest) for k in tw}
                    elif live:                       # 理论上不会发生：表内各路径均 >0
                        tw = {k: (0.0 if k in blocked else 1.0 / len(live)) for k in tw}
                self.weights = {k: float(v) for k, v in tw.items()}
                _superseded = any(abs(base_w[k] - self.weights.get(k, 0.0)) > 1e-6 for k in base_w)
                path_weights = {
                    "mode": "damodaran_table", "base_weights": base_w,
                    "damodaran_stage": dmd.get("stage"), "damodaran_stage_label": dmd.get("label"),
                    "damodaran_weights": {k: round(v, 4) for k, v in self.weights.items()},
                    "damodaran_reason": dmd.get("reason"),
                    "damodaran_evidence": dmd.get("evidence") or {},
                    "v326_stage": (lc.get("stage") if lc.get("enabled") else "unknown"),
                    "v326_sub_stage": (lc.get("sub_stage") if lc.get("enabled") else None),
                    "damodaran_guard": dmd.get("guard"),
                    "k_admissible_dcf": k_adm,
                    "blocked_paths": sorted(blocked),
                    "lifecycle_stage": (lc.get("stage") if lc.get("enabled") else "unknown"),
                    "base_weight_superseded": _superseded,
                    "resolved_weights": {k: round(v, 4) for k, v in self.weights.items()},
                    "note": "三路径权重取达莫达兰六阶段方法定位表（行内和为 1 的直接权重，不乘 base、"
                            "不归一化）；base_weight_superseded=true 表示用户输入的 preferences.weights 已被"
                            "阶段表覆盖，二者不可混读；blocked_paths 为被强制置零的路径"
                            "（Layer 0 否决 or 用户显式归零——表不复活）",
                }
                self.warnings.append(
                    f"权重取达莫达兰阶段表（{dmd.get('label') or 'n/a'}）：{base_w} → "
                    f"{path_weights['resolved_weights']}"
                    + ("；用户 base 权重已被阶段表覆盖" if _superseded else "；与 base 一致，无覆盖"))
                if dmd.get("guard"):
                    self.warnings.append(f"达莫达兰阶段判定提示（{dmd.get('label')}）：{dmd['guard']}")
            else:
                k_life = LIFECYCLE_WEIGHT_FACTORS.get(lc.get("stage") if lc.get("enabled") else "growth",
                                                      {"dcf": 1.0, "comparable": 1.0, "sentiment": 1.0})
                raw = {k: base_w[k] * k_life.get(k, 1.0) * (k_adm if k == "dcf" else 1.0) for k in base_w}
                tot = sum(raw.values()) or 1.0
                self.weights = {k: raw[k] / tot for k in raw}
                path_weights = {
                    "mode": "adaptive", "base_weights": base_w,
                    "k_lifecycle": {k: round(v, 4) for k, v in k_life.items()},
                    "k_admissible_dcf": k_adm,
                    "lifecycle_stage": (lc.get("stage") if lc.get("enabled") else "unknown"),
                    "resolved_weights": {k: round(v, 4) for k, v in self.weights.items()},
                    "note": "三路径权重条件化：w = normalize(base × k_lifecycle × k_admissible)；缺省 fixed 时不变",
                }
                self.warnings.append(
                    f"权重条件化（{lc.get('stage_label', 'unknown')}）：权重 {base_w} → {path_weights['resolved_weights']}")
        # Layer 0 dcf 权重封顶（v3.16.2：在 B4 之后施加——保证 conditional 档封顶 0.2/0.3 不被 B4 重算丢弃）
        if fw.get("enabled"):
            cap = fw.get("dcf_weight_cap", 1.0)
            if cap is not None and self.weights.get("dcf", 0) > cap:
                old_w = self.weights["dcf"]
                self.weights["dcf"] = cap
                rest = sum(v for k, v in self.weights.items() if k != "dcf")
                scale = (1.0 - cap) / rest if rest > 0 else 0.0
                for k in list(self.weights):
                    if k != "dcf":
                        self.weights[k] *= scale
                self.warnings.append(
                    f"Layer 0 前提判别：DCF 准入={fw['dcf_admissible']}，dcf 权重 {old_w:.2f}→{cap:.2f}（按 dcf_weight_cap 封顶并重分配）")
        # v3.17.0 P1：动态候选方法集（method_set_mode="routed"）——替代主方法可携带权重进入综合。
        # 在 B4 与 Layer 0 封顶之后施加（覆盖三路骨架），并把带帽权重按候选集重归一化；缺省 legacy → ms=None。
        method_set = self.resolve_method_set(fw, lc)
        if method_set and method_set.get("enabled"):
            self.weights = dict(method_set["resolved_weights"])
            self.warnings.append(
                f"P1 动态候选集（{method_set['industry_class']}）：候选 {method_set['candidates']} → "
                f"权重 {method_set['resolved_weights']}")
        extra = {"wacc_model": wacc_m, "cashflow_stats": cf_stats, "growth_triangulation": tri,
                 "sentiment_structure": smap}
        # v2.6.0 B6：情景档位自适应（preferences.adaptive_scenarios=true 时启用；缺省关闭保持 ±10pp）
        scen_adapter = {"enabled": False}
        if self.pref.get("adaptive_scenarios"):
            at = (self.d.get("meta") or {}).get("asset_type")
            base_span = {"startup": 15, "growth": 10, "mature": 8, "private": 10}.get(at, 10)
            span, basis = base_span, f"asset_type={at or 'default'}"
            std_g = (cf_stats.get("std_growth") or 0.0) if cf_stats.get("enabled") else 0.0
            if std_g > 0:
                std_span = int(round(max(5.0, min(20.0, std_g * 100.0))))
                span = max(base_span, std_span)
                basis += f"; 历史波动率 std_growth={std_g:.0%} → {std_span}pp"
            self.scen_ov.setdefault("bear", {})["growth_adj_pp"] = -span
            self.scen_ov.setdefault("bull", {})["growth_adj_pp"] = span
            self.warnings.append(f"情景档位自适应：Bear/Bull 增速幅度调整为 ±{span}pp（{basis}）。")
            scen_adapter = {"enabled": True, "asset_type": at, "growth_span_pp": span, "basis": basis,
                            "note": "preferences.adaptive_scenarios=true 时启用；缺省关闭保持 ±10pp"}
        # v3.20.0：可比公司筛选证据链（四期改造）——必须在 scenario 之前，
        # 执行模式下会过滤 self.comp，进而影响 comparable_valuation 的样本集。
        # 缺省 peer_screening.enabled=false → 返回 {"enabled": False}，样本与数值逐位不变。
        peer_screen = self.peer_screening_report()
        base = self.scenario("base", q, gw, gw_reason, ff, extra)
        bear = self.scenario("bear", q, gw, gw_reason, ff, extra)
        bull = self.scenario("bull", q, gw, gw_reason, ff, extra)
        sens = self.sensitivity({"growth": base["params"]["growth_adj_pp"],
                                 "margin": base["params"]["margin_adj_pp"]})
        idx_out = self.industry_index_valuation(comp_base=base["comparable_raw"])
        # v2.4.0：关键假设汇总（始终挂出，纯汇总不改数值）
        ass_sum = self.assumptions_summary(base, wacc_m, cf_stats, tri, self._fcfr_view(), ld)
        # v3.21.0 A6：终值占比门禁告警（只在 base 情景发一次，避免三情景重复刷屏）
        _tvsg = (base["dcf"].get("tv_share_grade") or {})
        if self.tv_share_guard and _tvsg.get("level"):
            _lv = _tvsg["level"]
            # 以 base 情景为准（dcf_valuation 的实例变量会被 bull 最后一次调用覆盖）
            self._tv_share_level = _lv
            _msg = f"终值占比 {_tvsg['tv_share']:.1%}（{_tvsg['grade']}）：{_tvsg['message']}"
            self.warnings.append(("【error】" if _lv == "error" else "") + _msg)
        # v3.21.0 A5：三情景终值增速留痕（stepped 时可在报告披露）
        _tg_by_scen = {k: v["dcf"].get("terminal_growth") for k, v in
                       (("bear", bear), ("base", base), ("bull", bull))}

        mid = self.scen_w["base"] * base["value"] + self.scen_w["bear"] * bear["value"] + self.scen_w["bull"] * bull["value"]
        lower, upper = bear["value"], bull["value"]
        if self.exclude_outliers and len(self.comp) < 3:
            span = (upper - lower) * 0.2
            lower, upper = lower - span, upper + span
            self.warnings.append("可比公司不足3家：区间已加宽 ±20% 以反映不确定性。")

        ipo = self.ipo_check(mid)
        # v2.4.0：回购价格法（孰高+概率加权）与 NAV 清算下限提示（mid 计算后）
        rpv = self.repurchase_valuation(mid)
        # v2.7.0 C1：贝叶斯锚定（外部价格锚 → 情景权重更新；缺省不激活）
        anch = self.anchor_bayesian_update(mid, bear["value"], bull["value"])
        if nav.get("enabled") and nav.get("adjusted_nav") is not None and nav.get("liquidation_scenario"):
            if nav["adjusted_nav"] > mid:
                self.warnings.append(
                    f"NAV {nav['adjusted_nav']} 亿元高于综合估值中枢 {mid} 亿元，清算场景建议以 NAV 为保守参考下限。")
        # v2.7.0 C2b：PEG 条件化建议（高成长时提示，不强制）
        peg_v = (base["comparable"].get("synthesis") or {}).get("peg_value")
        if peg_v and self._g1() > 0.3 and not bool(self.pref.get("enable_peg_in_synthesis", True)):
            self.warnings.append(
                f"首年增速 {self._g1():.0%} >30% 且 PEG 可用（{peg_v} 亿）：建议开启 preferences.enable_peg_in_synthesis=true "
                "使 PEG 参与综合（高成长股 PEG 参考性较强）。")
        # v3.16.0 B5：adaptive 模式下把分歧度扩到三路径（②可比法 ③舆情 ①DCF）；缺省 fixed 保持两法 CV（零变化）
        method_vals = [base["comparable_adjusted"], base["dcf_value"]]
        path_corr_note = None
        if self.path_weight_mode == "adaptive" and self.four_part_mode:
            # 分歧度保持「市场口径综合值 vs DCF」（comparable_adjusted 已含 ②③），不因加入相关路径而人为压低 CV
            sent_dev = (base["comparable_sentiment"] - base["comparable_quality"])
            # ③ 与 ② 共用 comp_v 基数 → 高度相关，去相关后有效路径数 ≈ 2.3（非 3）
            path_corr_note = {
                "comp_vs_sent": "shared_base",
                "effective_path_count": 2.3,
                "sentiment_vs_quality_abs": round(sent_dev, 2),
                "note": "③舆情与②可比法共用 comp_v 基数：③ 的独立信息 = sent 本身（±10% 带）；"
                        "分歧度取锚对锚（②vs①），有效路径数按去相关计（2.3 而非 3），避免相关性误读为论证强度",
            }
        cv = (statistics.pstdev(method_vals) / _mean(method_vals)) if _mean(method_vals) else None
        if cv and cv > 0.60:
            self.warnings.append(f"各方法离散度过高(CV={cv:.0%})：市场口径与 DCF 分歧大，差值来自情绪/成长预期溢价。")

        # 置信度合成（v2.0：数据完整性 × 质量分相对基准 × 因子校准）
        # factor = (0.7+0.3×完整性) × (0.6+0.4×质量/60) × ff校准系数；→ 高≥80 / 中60~80 / 低<60
        completeness = self._data_completeness()
        ff_penalty = 1.0 if ff.get("enabled") else 0.9
        factor = (0.7 + 0.3 * completeness) * (0.6 + 0.4 * min(1.5, q["score"] / QUALITY_SCORE_DEFAULT)) * ff_penalty
        # v2.11.4：方法覆盖度校正——DCF 不适用（asset_adapter.dcf_applicable=False）时，DCF 分支
        # 仅由净现金下限机械兜底、不携带估值信号，若权重又集中于单一市场法，则「数据完整性满分」
        # 不能支撑「高」置信度。仅在适配器明确判定 DCF 不适用时触发（其余输入零变化）。
        # v3.16.2：DCF 适用性判定统一——layer0_check=true 时以 Layer 0 前提检验为准（现金流可定义性
        # 优先于 asset_type 标签，消除「同一标的 asset_type 判不适用 / Layer 0 判可准入」的矛盾）；
        # 否则沿用 asset_type 适配器。二者结论相反时留痕 warning。
        if fw.get("enabled"):
            dcf_inapp = fw.get("dcf_admissible") is False
            if (ad.get("enabled") and ad.get("recognized") and ad.get("dcf_applicable") is False
                    and fw.get("dcf_admissible") is not False):
                self.warnings.append(
                    "DCF 适用性判定不一致：asset_type 标签判不适用，Layer 0 前提检验判可准入——"
                    "已以 Layer 0 为准（现金流可定义性优先于资产类型标签）。")
        else:
            dcf_inapp = bool(ad.get("enabled") and ad.get("recognized")
                             and ad.get("dcf_applicable") is False)
        method_coverage = None
        if dcf_inapp:
            n_eff = 1 if self.weights.get("comparable", 0) > 0 else 0
            coverage = min(1.0, n_eff / 2.0)          # 有效估值方法数 / 参照方法数(2)
            diversity = 0.5 + 0.5 * coverage          # 单一有效方法 → 0.75
            factor = min(factor * diversity, 0.799)   # 折减 + 上限「中」档（79.9 分）
            method_coverage = {
                "dcf_applicable": False,
                "effective_method_count": n_eff,
                "diversity_factor": round(diversity, 3),
                "level_cap": "中",
                "note": "DCF 不适用 + 市场法单方法驱动 → 按方法覆盖度折减置信度并封顶；"
                        "data_completeness 衡量的是字段齐备度，不衡量方法充分性。",
            }
        confidence_score = round(max(20.0, min(100.0, 100.0 * factor)), 1)
        confidence_level = "高" if confidence_score >= 80 else ("中" if confidence_score >= 60 else "低")
        # v2.11.5：方法分歧度校正——市场口径（可比法）与 DCF 内在价值分歧过大时，「数据完整性满分 +
        # 质量分达标」只能证明**输入齐备**，不能证明**估值结论可靠**。仅在 base 情景两法均 >0 且
        # CV 超阈值时触发；缺省（CV≤0.60 或无有效 DCF）逐位保持 v2.11.4 行为。
        method_divergence = None
        if cv is not None and cv > CONFIDENCE_METHOD_CV_CAP:
            div_factor = round(min(1.0, CONFIDENCE_METHOD_CV_CAP / cv), 3)
            factor = min(factor * div_factor, 0.799)   # 折减 + 上限「中」档（79.9 分）
            confidence_score = round(max(20.0, min(100.0, 100.0 * factor)), 1)
            confidence_level = "高" if confidence_score >= 80 else ("中" if confidence_score >= 60 else "低")
            method_divergence = {
                "method_cv": round(cv, 3),
                "cv_cap": CONFIDENCE_METHOD_CV_CAP,
                "divergence_factor": div_factor,
                "comparable_adjusted": round(base["comparable_adjusted"], 2),
                "dcf_value": round(base["dcf_value"], 2),
                "ratio": round(max(base["comparable_adjusted"], base["dcf_value"]) /
                               max(1e-9, min(base["comparable_adjusted"], base["dcf_value"])), 2),
                "level_cap": "中",
                "note": "市场口径与 DCF 分歧度 CV 超阈值 → 按分歧度折减置信度并封顶；"
                        "data_completeness 衡量字段齐备度，不衡量方法间一致性。",
            }
        # v3.21.0：增速参数体系的置信度约束（A1 守卫触发 −20 分；A6 极端终值占比封顶「中」）
        growth_param_caps = None
        _caps = []
        if getattr(self, "_tg_guard_fired", False):
            factor = max(0.20, factor - 0.20)
            _caps.append({"rule": "terminal_guard_fired", "effect": "score −20（折减一档）",
                          "note": "永续增速不低于折现率，Gordon 终值不成立 → 估值结论不可按原档采信"})
        if self._tv_share_level == "error":
            factor = min(factor, 0.799)
            _caps.append({"rule": "tv_share_extreme", "effect": "封顶「中」档（≤79.9 分）",
                          "note": "终值占比 >85%，估值几乎完全由永续假设决定"})
        # v3.22.0 修复②：p0 降级（error 模式）→ 封顶「中」
        if self._cf_fallback and self.cashflow_fallback_mode == "error":
            factor = min(factor, 0.799)
            _caps.append({"rule": "cashflow_model_fallback", "effect": "封顶「中」档（≤79.9 分）",
                          "note": (f"cashflow_model=p0_value_driver 缺 "
                                   f"{'/'.join(self._cf_fallback['missing'])}，已降级 p2_legacy——"
                                   f"该口径无再投资约束，高增长假设下 FCFF 偏高，结论按降档采信")})
        if _caps:
            confidence_score = round(max(20.0, min(100.0, 100.0 * factor)), 1)
            confidence_level = "高" if confidence_score >= 80 else ("中" if confidence_score >= 60 else "低")
            growth_param_caps = {"caps": _caps, "final_score": confidence_score,
                                 "final_level": confidence_level,
                                 "note": "v3.21.0 增速参数体系的置信度约束（A1 守卫 / A6 终值占比）"}
        # v2.2.0：可用方法清单（审计留痕）
        methods_available = ["comparable", "dcf"]
        if "pb" in base["comparable"]:
            methods_available.append("pb")
        methods_inapplicable = []
        if dcf_inapp:                                  # v2.11.4：与 asset_adapter 结论保持一致
            methods_available = [m for m in methods_available if m != "dcf"]
            methods_inapplicable.append("dcf")
        for name, enabled in (("wacc_model", wacc_m.get("enabled")), ("cashflow_statistics", cf_stats.get("enabled")),
                              ("growth_triangulation", tri.get("enabled")),
                              ("industry_index", idx_out.get("enabled")),
                              ("sentiment_structured", smap.get("enabled"))):
            if enabled:
                methods_available.append(name)

        syn = {
            "bear_value": round(bear["value"], 2),
            "base_value": round(base["value"], 2),
            "bull_value": round(bull["value"], 2),
            "weighted_mid": round(mid, 2),
            "interval": [round(lower, 2), round(upper, 2)],
            "interval_mid": round((lower + upper) / 2, 2),
            "method_cv": round(cv, 3) if cv else None,
            "dcf_tv_share_base": base["dcf"].get("tv_share"),
            "dcf_vs_comparable_gap": (round(base["comparable_raw"] / base["dcf_value"], 2)
                                      if (base["dcf_value"] and base.get("comparable_raw") is not None)
                                      else None),
        }
        # v3.22.0 修复⑥：A6 极端档（终值占比 >85%）禁出单点估值——CVA comps 口径 point_estimate=null；
        # 原实现只把置信度封顶「中」却仍照出中枢，读者仍会采信那个数。仅在 opt-in 时挂出（零回归）。
        if self.point_estimate_guard and self._tv_share_level == "error":
            _tvs = base["dcf"].get("tv_share")
            syn["point_estimate"] = None
            syn["point_estimate_suppressed"] = {
                "rule": "tv_share_extreme", "tv_share": _tvs,
                "reason": ("终值占比超过 85% 极端档，估值几乎完全由永续增速假设决定；"
                           "单点估值不具备可采信性，结论应以区间与永续增速敏感性表达"),
                "note": "区间（情景区间 / MC 90%）仍然有效；如需单点，须先延长显式期或补永续增速依据",
            }
            self.warnings.append(
                (f"终值占比 {_tvs:.1%} 超过 85% 极端档" if isinstance(_tvs, (int, float))
                 else "终值占比超过 85% 极端档")
                + "，已按 point_estimate_guard 取消单点估值（区间口径仍有效）。")
        # v3.15.0：估值四部分分解（four_part_mode=true 时挂出；旧口径不挂出 → 键集合不变）
        if self.four_part_mode:
            syn["four_part"] = {
                "part1_dcf": {"value": round(base["dcf_value"], 2),
                              "weight": round(self.weights.get("dcf", 0.0), 4),
                              "note": "① DCF 现金流贴现法（内在价值，不承受市场修正）"},
                "part2_comparable_quality": {"value": round(base["comparable_quality"], 2),
                                             "weight": round(self.weights.get("comparable", 0.0), 4),
                                             "note": "② 可比公司法（含盈利质量调整：质量+商誉+因子+流动性折扣；不含情绪）"},
                "part3_market_sentiment": {"value": round(base["comparable_sentiment"], 2),
                                           "weight": round(self.weights.get("sentiment", 0.0), 4),
                                           "note": "③ 市场舆情（仅情绪：板块热度+个股舆情+情景因子；不含质量、不含流动性）"},
                "part4_statistical": {"interval": "见 stat_validation 输出 ci90（P5–P95）",
                                      "note": "④ 统计检验区间（口径本次不变）"},
                "weighted_mid": round(mid, 2),
                "note": "四部分拆分：①DCF ②可比公司法(含质量调整) ③市场舆情(独立权重) ④统计检验(P5/P95)",
            }
            if path_corr_note:                      # v3.16.0 B5：三路径相关性声明
                syn["four_part"]["path_correlation"] = path_corr_note
            # v3.17.0 P2：舆情降为修正层时，③ 不再独立占权重，权重回归 ② → 覆盖四部分口径说明
            if self.sentiment_layer == "correction":
                _w_c = self.weights.get("comparable", 0.0) + self.weights.get("sentiment", 0.0)
                syn["four_part"]["part2_comparable_quality"]["weight"] = round(_w_c, 4)
                syn["four_part"]["part3_market_sentiment"] = {
                    "value": round(base["comparable_sentiment"], 2),
                    "weight": 0.0,
                    "layer": "correction",
                    "adjust_mode": self.sentiment_adjust_mode,
                    "note": ("③ 市场舆情已降为②可比法的修正系数（P2，w=0 不再独立计费）；"
                             + ("修正幅度 = band × k_signal × sign(sent) × min(|sent|/10%,1)，"
                                "上限 band×1.60（v3.18.0 strength 口径：方向/强度正交，破除双重截断）"
                                if self.sentiment_adjust_mode == "strength" else
                                "修正幅度由信号强度（无事件 0.5 / 少量 0.8 / 一致 1.3 / 冲突 0.7）×带宽（P4 按企业类型分化）决定")),
                }
                syn["four_part"]["note"] = ("四部分拆分（P2 修正层口径）：①DCF ②可比公司法(含质量调整+舆情修正) "
                                            "③舆情(修正层，w=0) ④统计检验(P5/P95)")
            # v3.22.0 修复③：可比法被剔除时四部分口径同步（权重归 0、取值置 None，不留 0 值冒充）
            if self._method_drop:
                _eff = self._method_drop.get("renormalized") or {}
                syn["four_part"]["part2_comparable_quality"] = {
                    "value": None, "weight": 0.0, "dropped": True,
                    "note": "② 可比公司法无可信取值（无有效倍数样本），已从综合式剔除"}
                if self.sentiment_layer != "correction":
                    syn["four_part"]["part3_market_sentiment"] = {
                        "value": None, "weight": 0.0, "dropped": True,
                        "note": "③ 市场舆情与②共用 comp_v 基数，② 不可用时同步剔除"}
                syn["four_part"]["part1_dcf"]["weight"] = round(_eff.get("dcf", 0.0), 4)
                syn["four_part"]["note"] = ("四部分拆分（可比法剔除口径）：①DCF 按剩余权重再归一化、"
                                            "②③ 剔除、④统计检验不变；剔除明细见 method_drop")
                syn["method_drop"] = self._method_drop
            # v3.17.0 P1：动态候选方法集留痕（RoutedMethodSet 时挂出）
            if method_set and method_set.get("enabled"):
                syn["four_part"]["method_set"] = {
                    "industry_class": method_set["industry_class"],
                    "candidates": method_set["candidates"],
                    "resolved_weights": method_set["resolved_weights"],
                    "note": method_set["note"],
                }
        if path_weights:                            # v3.16.0 B4：权重条件化留痕（adaptive 时挂出）
            syn["path_weights"] = path_weights
        # v2.2.0：可比指标汇总表仅在有新增指标数据时挂出（保证旧输入 synthesis 键集合不变）
        if base["comparable"].get("metrics"):
            syn["comparable_metrics"] = base["comparable"]["metrics"]
        # v3.11（修订 2b）：海外可比分组统计（仅多组时挂出，旧输入零变化）
        if base["comparable"].get("metrics_by_group"):
            syn["comparable_group_gap"] = base["comparable"]["metrics_by_group"]
        out = {
            "meta": self.d.get("meta", {}),
            "weights": self.weights,
            "scenario_weights": self.scen_w,
            "quality_scorecard": q,
            "scenarios": {"bear": bear, "base": base, "bull": bull},
            "synthesis": syn,
            "confidence": {"score": confidence_score, "level": confidence_level,
                           "data_completeness": round(completeness, 2),
                           "quality_score": q["score"], "ff_calibrated": ff.get("enabled"),
                           "methods_available": methods_available,
                           **({"methods_inapplicable": methods_inapplicable,
                               "method_coverage": method_coverage} if dcf_inapp else {}),
                           **({"method_divergence": method_divergence} if method_divergence else {}),
                           **({"growth_param_caps": growth_param_caps} if growth_param_caps else {})},
            "sensitivity": sens,
            "ipo_check": ipo,
            "warnings": self.warnings,
            "engine_version": "2.28.0",
        }
        # v2.4.0：关键假设汇总始终挂出（报告'关键假设'章节数据源）
        out["assumptions_summary"] = ass_sum
        # v2.4.0：输入校验问题非空时挂出（旧输入无异常 → 不挂出，键集合不变）
        if input_issues:
            out["input_validation"] = {"issues": input_issues, "n_issues": len(input_issues),
                                       "note": "输入校验与异常值检测结果（仅提示，未强制改值）"}
        # v2.2.0/v2.3.0/v2.4.0：统计强化与替代锚输出块（仅激活时挂出，向后兼容）
        for key, obj in (("wacc_model", wacc_m), ("cashflow_statistics", cf_stats),
                         ("growth_triangulation", tri), ("industry_index", idx_out),
                         ("sentiment_structure", smap),
                         ("fcf_ratio", self._fcfr_view()), ("transactions_anchor", txv),
                         ("recent_financing_anchor", rfa),
                         ("liquidity_discount", ld), ("nav_valuation", nav),
                         ("rim_valuation", rim), ("ddm_valuation", ddm),
                         ("rnpv_valuation", rnpv), ("sotp_valuation", sotp),
                         ("repurchase_anchor", rpv), ("asset_adapter", ad),
                         ("scenario_adapter", scen_adapter),
                         ("anchor_update", anch),
                         # v3.16.0 三层计划留痕块（各自 opt-in，缺省不挂出 → 旧输入键集合不变）
                         ("industry_params", ind), ("framework_check", fw), ("lifecycle", lc)):
            if obj.get("enabled"):
                out[key] = obj
        # v3.24.0（F1）：未计算时仍须**显式声明**（字段存在、语义为「未计算」）而非静默缺失——
        # 否则读者无法区分「比率法不适用」与「引擎忘了算」。legacy 模式不触发此分支。
        if "fcf_ratio" not in out:
            _fv_skip = self._fcfr_view()
            if _fv_skip.get("skipped"):
                out["fcf_ratio"] = _fv_skip
        # v2.4.0：流动性折扣补充基准信息（作用于市场法 base 情景可比修正值）
        if ld.get("enabled") and getattr(self, "_liq_impact", None):
            out["liquidity_discount"]["basis_value"] = round(base["comparable_adjusted"] + self._liq_impact, 2)
            out["liquidity_discount"]["discount_value"] = round(self._liq_impact, 2)
        # v3.12：净利披露档输出（仅激活时挂出，旧输入零变化）
        if getattr(self, "_profit_source", None):
            npb = self.fin.get("net_profit_basis") or {}
            out["net_profit_basis_used"] = {
                "source": self._profit_source, "basis": getattr(self, "_profit_basis", None),
                "annualized_source": npb.get("annualized_source"),
                "as_of": npb.get("as_of"),
                "note": "净利披露档（v3.12 最高优先级）：公开披露/市场预期净利 > 现行 rev×net_margin 兜底；"
                        "consensus 视为前向利润不再乘首年增速；周期正常化仅 enable_normalized=true 时覆盖"}
        # v3.12：可比来源档位统计（仅任一可比带 source 时挂出，旧输入零变化）
        src_list = [(c.get("name"), c.get("source"), c.get("priority")) for c in self.comp if c.get("source")]
        if src_list:
            cnt = {}
            for _, s, _p in src_list:
                cnt[s] = cnt.get(s, 0) + 1
            prios = [p for _, _s, p in src_list if isinstance(p, (int, float))]
            out["comparable_sources"] = {
                "count": cnt, "n_with_source": len(src_list), "n_total": len(self.comp),
                "min_priority": min(prios) if prios else None,
                "note": "可比来源档位（v3.12）：research_report>public_info>auto>user>none；"
                        "研报来源参与 S3.3 质量评分（+10/+5/+3/0/−10），<60 分区间加宽 ±20%"}
        # v3.20.0：可比公司筛选证据链（仅 peer_screening.enabled=true 时挂出 → 旧输入键集合不变）
        if peer_screen.get("enabled"):
            out["peer_screening"] = peer_screen
        # v2.3.0：可比集一致运用（仅当 DCF 参数从可比集/新增字段取值时挂出）
        set_used = False
        set_usage = {"n_comparables": len(self.comp), "multiple_medians": {}}
        for k in ("pe", "ps", "ev_ebitda", "pb"):
            if base["comparable"].get(k):
                set_usage["multiple_medians"][k] = base["comparable"][k].get("median")
        if wacc_m.get("enabled"):
            if str(wacc_m.get("beta_source", "")).startswith("可比"):
                set_usage["beta_source"] = wacc_m["beta_source"]
                set_used = True
            if wacc_m.get("d_e_source") == "可比集中位":
                set_usage["de_source"] = "可比集中位"
                set_used = True
        _fv_use = self._fcfr_view()
        if _fv_use.get("enabled"):
            _src_use = _fv_use.get("source") or "三层校准（L1 自身 / L2 可比 / L3 兜底）"
            if _fv_use.get("role") == "diagnostic_only":
                _src_use += "（仅诊断对照，未进入估值）"
            set_usage["fcf_ratio_source"] = _src_use
            set_used = True
        if tri.get("enabled"):
            set_usage["growth_source"] = "三角校准（自身+可比+行业）"
        if set_used:
            out["comparable_set_usage"] = set_usage
        # v2.3.0：可比不足时的替代路径显式化（无可比替代框架）
        if len(self.comp) < 3:
            out["comparables_shortfall"] = {
                "n_comparables": len(self.comp),
                "fallback_paths": {"industry_index": bool(idx_out.get("enabled")),
                                   "transactions": bool(txv.get("enabled")),
                                   "recent_financing": bool(rfa.get("applicable", rfa.get("enabled", False)))},
                "interval_widened_pct": 20,
                "confidence_impact": "置信度下调（可比不足）",
                "note": "无可比替代框架：行业指数/可比交易/最近融资价格锚；区间已加宽 ±20%",
            }
        # ===== v3.22.0：估值缺陷修复六项的留痕块（各自仅在生效时挂出 → 缺省键集合不变）=====
        if self._wacc_default_meta:
            out["wacc_default"] = self._wacc_default_meta
        if self._cf_fallback:
            out["cashflow_model_fallback"] = self._cf_fallback
        if self._fcff_suggest_meta:
            out["fcff_suggestion"] = self._fcff_suggest_meta
        # ===== v3.23.0：现金流模型细节层（D2/D3/D4/D8/D9）的留痕块 =====
        if self._size_premium_meta:
            out["size_premium"] = self._size_premium_meta
        if self._capex_check_meta:
            out["capex_check"] = self._capex_check_meta
        if self._normalization_hint_meta:
            out["normalization_hint"] = self._normalization_hint_meta
        if self._gf_rule:
            out["growth_base_rule"] = self._gf_rule
        return out

    def _data_completeness(self):
        """数据完整性评分：必填字段缺失每项 −20%，<60% 需补问（v2.1.0 简化）。"""
        missing = sum(1 for k in ("revenue_latest_ttm", "net_profit_latest_ttm")
                      if k not in self.fin or self.fin.get(k) is None)
        if not (self.d.get("meta") or {}).get("exchange"):
            missing += 1
        return max(0.0, 1.0 - 0.2 * missing)


def _assumption_diffs(prev, new):
    """对比两次运行的假设类字段，返回差异描述列表（v2.1.0：替代原 base_case_id 字符串）。"""
    diffs = []
    pairs = [
        ("weights", prev.get("weights"), new.get("weights")),
        ("scenario_weights", prev.get("scenario_weights"), new.get("scenario_weights")),
        ("confidence.level", (prev.get("confidence") or {}).get("level"), (new.get("confidence") or {}).get("level")),
    ]
    for label, pv, nv in pairs:
        if pv != nv:
            diffs.append(f"{label}: {pv} → {nv}")
    scen_keys = set((prev.get("scenarios") or {}).keys()) | set((new.get("scenarios") or {}).keys())
    for name in sorted(scen_keys):
        pv = (prev.get("scenarios") or {}).get(name, {}).get("params")
        nv = (new.get("scenarios") or {}).get(name, {}).get("params")
        if pv != nv:
            diffs.append(f"scenarios.{name}.params: {pv} → {nv}")
    return diffs


def diff_report(prev, new):
    """增量重估 diff：区间变化、假设变化、收敛/发散判定。"""
    ps, ns = prev["synthesis"], new["synthesis"]
    prev_mid, new_mid = ps["weighted_mid"], ns["weighted_mid"]
    prev_range = ps["interval"][1] - ps["interval"][0]
    new_range = ns["interval"][1] - ns["interval"][0]
    width_delta = (new_range - prev_range) / prev_range if prev_range else None
    verdict = "发散" if (width_delta is not None and width_delta > 0.30) else ("收敛" if width_delta is not None and width_delta < -0.10 else "基本稳定")
    return {
        "prev_mid": prev_mid, "new_mid": new_mid,
        "mid_change_pct": round((new_mid - prev_mid) / prev_mid, 4) if prev_mid else None,
        "interval_prev": ps["interval"], "interval_new": ns["interval"],
        "width_change_pct": round(width_delta, 4) if width_delta is not None else None,
        "verdict": verdict,
        "assumption_changes": _assumption_diffs(prev, new),
        "base_case_id": (new.get("meta") or {}).get("base_case_id", ""),
        "quality_prev": prev.get("quality_scorecard", {}).get("score"),
        "quality_new": new.get("quality_scorecard", {}).get("score"),
    }


def main():
    ap = argparse.ArgumentParser(description="IPO 智能估值引擎 v2.28.0")
    ap.add_argument("input", help="输入参数 JSON（assets/input_template.json 格式）")
    ap.add_argument("-o", "--output", default=None, help="输出 JSON 路径")
    ap.add_argument("--scenarios", default=None, help='情景覆盖 JSON，如 \'{"bull":{"growth_adj_pp":15}}\'')
    ap.add_argument("--compare", default=None, help="上一案例输出 JSON 路径（增量重估 diff）")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    scen_ov = json.loads(args.scenarios) if args.scenarios else None
    result = Engine(data, scen_ov).run()
    if args.compare:
        with open(args.compare, "r", encoding="utf-8") as f:
            result["diff_vs_prev"] = diff_report(json.load(f), result)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        s = result["synthesis"]
        print(f"[OK] 输出已写入: {args.output}")
        print(f"[OK] 综合区间(亿): {s['interval']} | 中枢: {s['weighted_mid']} | 置信度: {result['confidence']['level']}")
        print(f"[OK] Bear/Base/Bull(亿): {s['bear_value']} / {s['base_value']} / {s['bull_value']}")
        print(f"[OK] 质量评分: {result['quality_scorecard']['score']} | 修正项: "
              f"quality{result['scenarios']['base']['adjustments']['quality']['adjustment_pct']:+.1%} "
              f"goodwill{result['scenarios']['base']['adjustments']['goodwill']['adjustment_pct']:+.1%} "
              f"sentiment{result['scenarios']['base']['adjustments']['sentiment']['adjustment_pct']:+.1%}")
        for w in result["warnings"]:
            print(f"[WARN] {w}")
    else:
        print(text)


if __name__ == "__main__":
    sys.exit(main())
