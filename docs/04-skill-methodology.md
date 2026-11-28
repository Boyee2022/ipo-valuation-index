# 04 · 技能方法论：LLM IPO Valuation 深度提炼

> 分析对象：`skills/llm-ipo-valuation/`（技能工作树，标题版本 v3.29.1；引擎与冒烟脚本最后修改 2026-11-06）
> 对照基线：`origin/main`（`d06a5ed`，2026-11-27）。批跑代码已按 v3.31.0 模型护栏做输入层适配，与本工作树存在版本差，本文逐处标注。
> 核对方式：`SKILL.md` 结构精读 + `methodology.md` §1–§6 + 10 个脚本的 docstring/常量/关键分支 + 实跑 `smoke_test.py`（170 用例）+ 以样例输入实跑引擎核对输出键。

---

## 1. 技能是什么，从哪里来

这是一套**把卖方投行估值工作流写成可执行规约**的技能包，不是一段估值代码。文献来源是国金证券《基于大语言模型的上市公司智能估值模型构建》（李双宏、杨利国、王洪涛），主张四条：结构化财务与非结构化信息（公告、新闻、研报、舆情）**统一建模**；按**类分析师逻辑分步骤推理**（画像→产业链→选法→估值→复核）；用**产业链挖掘**补足单体财务视角；把舆情、财报质量、商誉三个**增量维度**量化并入估值，以可解释、可审计的区间收尾。在此之上，技能把**达莫达兰企业生命周期框架**当“方法定位器”：公司处于初创、年轻成长、高速成长、成熟成长、成熟稳定、衰退哪一档，决定该用哪个工具（期权/VC 法、两阶段 DCF、倍数、DDM、清算价值），而不是给 DCF 乘一个重要性系数。

方法论来源在 `methodology.md` 中按四类标注：**[A] 论文系**（《基于大语言模型的上市公司智能估值模型构建》及其实证姊妹篇、算法研究）、**[B] 课题解读**（国金证券 AI 实验室成果发布、王洪涛公开演讲与《中国金融电脑》文章）、**[C] 专利**（并行博弈动态估值 CN121765307A、多 Agent 协同控制 ZL202410113286.8、产业链智能挖掘申请中）、**[D] 技术论文**。六层映射是：统一建模→A+B [A][B]；类分析师分步推理→E [B]；产业链挖掘→C [B][C]；动态评估/并行博弈→E [C]；舆情/财报/商誉→A+D [A]；可解释与审计留痕→F [B][D]。**未标注处是工程化补充，不等于论文原文**。

工程形态四层：`SKILL.md` 主定义（流程、开关、契约、验收）；`methodology.md` 理论依据与版本史；`assets/` 规约与参数（输入 schema/模板、行业参数、校准先验、IPO 规则、报告规范）；`scripts/` 是 10 个纯标准库 Python 文件——引擎、统计、报告、机检、可比证据链、β 回归、抓数、输入校验、工具层、冒烟。

**必须如实标注的版本差**（本次逐一核对，非笔误）：

| 维度 | 工作树实际 | 文档声明 | 仓库批跑（`d06a5ed`） |
|---|---|---|---|
| 技能版本 | 标题 **v3.29.1** | frontmatter `3.16.12`（陈旧） | 按 **v3.31.0** 护栏适配 |
| 引擎版本 | 输出与 argparse 均 **2.28.0** | `SKILL.md` 描述写 **2.27.1**、文件清单仍 **2.27.0** | 消费 3.31 新字段 |
| 冒烟用例 | 实跑 **170 个全绿（3.9s）** | §7 写 **169** | — |
| 3.31 新键 | 无 `synthesis.industry_fallback`；不读 `net_assets_fallback` | — | `pipeline.py` 判 `industry_fallback`、`input_builder.py` 写 `net_assets_fallback` |

本次实测 `python3 scripts/valuation_engine.py examples/input_example.json` 可正常运行，输出 `engine_version=2.28.0`、综合中枢 **261.4 亿元**、置信度「高」，且输出中**没有** `industry_fallback` 字段——与批跑 `pipeline.py` 的预期不一致。

根因清楚：引擎在 2026-11-06 追加 L4 守卫（净利为负时 `FCF/净利` 无定义，见 `test_t170`），版本号随之到 2.28.0，但文档仍停在 2.27.1/169 例；v3.31 适配写在对端代码里。**结论**：方法论以工作树为准可信；工程接口须按批跑代码描述，联调时用回归测试确认字段，不能假设“技能里有的键批跑就有”。

---

## 2. 七步工作流

三条入口共用一条主链：**一句话估值**（自由文本→自动解析并一次问清 ≤4 项）、**参数模板估值**（填 `input_template.json`）、**增量重估**（新财报/公告/行情，`--compare` 输出 diff 与收敛/发散判定）。第四种“统计校验模式”不是独立入口，而是 A 级默认执行、用户点名时强制的横切层。

- **Step 0 参数解析。** 真正的产物不是填满的模板，而是解析台账 `_parse_ledger`。取值按 `L1 表述 → L2 采集 → L3 问询 → L4 默认`，不得跳层。表述与结构化数据是**三态**而非优先级：一致（净利率 1pp/增速 2pp/金额 5% 容差）→ 采用并记口径；矛盾 → 按营收/净利等原始量计算并披露（净利率是派生量，不能裁决原始量）；未表述 → 转采集。`default`/`assumed` 不计入完整度，否则“填满模板=数据齐全”，置信度公式退化为常数。
- **Step 1 数据采集。** 四档优先级：`fetch_data.py` 自动抓取（最高档）→ 用户文档（招股书/审计报告）→ 已接数据源 → WebSearch（标注“公开检索未验证”）。六路数据：净利披露档（年度 > 季度×4 > 半年×2 > 一致预期 > 营收×净利率兜底）、质量明细、情绪、产业链、可比、规则。建模后写 `lifecycle_mode=auto` 与 `lifecycle_classifier_mode=v326`；后者要求 ≥3 期 `margin_history` 与 `roic`。
- **Step 2 画像与评分。** 六模块画像（商业模式/行业定位/成长性/盈利质量/募投/风险）+ 盈利质量评分卡：OCF/净利 30%、毛利率趋势 20%、应收/营收 20%、商誉比 15%、非经常性损益 15%，基准 60 分，修正系数 `(score−60)/40×10%`，只作用于可比法；另有财务异常识别。
- **Step 3 产业链与可比。** 产业链图谱与关键变量、可比筛选（同环节→同模式→同规模，≥3 家）、四维三档分类（主档优先+逐级回退，`tier_min_samples` 缺省 2）、可比质量评分、环节中枢。可比不足不阻断，而是区间加宽 ±20% 并降置信度。
- **Step 4 引擎计算。** 一次跑出多方法、四部分拆分、修正项、因子校准、确定性敏感性、IPO 约束。4b 统计校验与 4c–4l 十个 opt-in 模块在此汇合：三层计划、P1–P5 框架修订、舆情强度、rNPV/SOTP 路由、可比证据链、增速参数、缺陷修复、惰性求值、增速路径、生命周期判别。
- **Step 5 情景博弈。** 悲观/中性/乐观是五层叠加：L1 离散三情景（增速 ±10pp、净利率 ∓3pp、倍数 ×0.8/1.0/1.2、WACC ∓1pp，权重 25/50/25）；L2 按资产类型与历史波动率改幅度；L3 舆情事件经 `impact_map` 同向平移三档；L4 市场口径情绪只作用于可比法；L5 统计连续带。已进假设层的事件，`impact_pct` 必须归零，否则重复计数。
- **Step 6 投行级报告。** 11 段（执行摘要/核心观点/公司概况/行业与竞争/财务基础/方法与假设/估值结果/IPO 定价约束/风险提示/结论建议/数据溯源），三口径并排（情景区间 + MC 90% + 修正区间）、warnings 全量呈现、方法适用性表、融资估值法、溯源表含获取日期；交付前过 `html_check.py` 八项机检。

每一步都落 JSON 块，这就是“留痕”：`_parse_ledger`、`data_sources[]`、`quality_scorecard`、`peer_screening`、`lifecycle`、`growth_seq_detail`、`wacc_model`、`four_part`、`confidence`、`warnings`。报告只是这些块的渲染视图。

---

## 3. 六层智能估值架构

| 层 | 做什么 | 技能落点（脚本/字段） |
|---|---|---|
| **A 数据层** | 结构化财务 × 非结构化文本 × 行情统一建模 | `fetch_data.py`、批跑 `input_builder`、`financials.*`、`net_profit_basis`、`data_sources[]` |
| **B 理解层** | 六模块画像、行业定位、成长性、盈利质量、风险 | `quality_score`、`quality_scorecard`、`lifecycle.evidence` |
| **C 产业链层** | 图谱、关键变量、可比挖掘与分档 | `peer_screening.py`、`beta_estimator.py`、`comparable_tiers` |
| **D 估值层** | DCF × 相对法 × 增量维度修正 + IPO 约束 | `valuation_engine.py`（`dcf_valuation`/`comparable_valuation`/`rim`/`ddm`/`nav`/`rnpv`/`sotp`/`ipo_check`） |
| **E 推理层** | 分步推理 + 三情景博弈 + 分歧裁决 | 流程层 Step 5 + `scenario()`、`scenario_weights`、`--compare` |
| **F 输出层** | 区间、假设依据、敏感性、溯源、机检 | `report_generator.py`、`html_check.py`、`output_template_pro.html` |

六层与工程落点基本齐整，偏弱的是 E 层。这里有三个**不同层**的东西，不能混为一谈：① **论文/专利的并行博弈**——多空方 Agent 多轮交互、高级 Agent 裁决并加权融合（CN121765307A、ZL202410113286.8），发生在假设生成与裁决层；② **技能的 E 层**——三情景参数化 + 加权裁决，是①的可复算近似，引擎只认参数；③ **批跑层的「三专家 + 主审」**——`packages/batch/shadow.py` 里可比质量/折现参数/舆情三域分工（专家不得跨域提参），主审独立复核、夹断或驳回，仅 `agent_mode=apply` 时把通过项有界写回（可比 5/8/10pp、舆情 5/10pp、WACC 0.4/1.0pp、永续 0.2/0.6pp），保留 baseline、失败回滚。它评审的是**输入参数**，不改变引擎方法结构，也不属于技能包。

---

## 4. 核心机制

### 4.1 六阶段生命周期与方法定位表

**问题**：同一套 DCF 参数不能同时服务管线药企与稳态白电龙头。旧实现用 `k_lifecycle` 乘数（初创 DCF 0.5/可比 0.7/舆情 1.5 等）表达“该阶段偏重哪个方法”，再乘 base 归一化。**实现**：v3.28.0 改为六行**直接权重表**（行内和为 1，不乘 base、不归一化），每格回溯达莫达兰对该阶段工具的表述（`DAMODARAN_STAGE_EVIDENCE`）：

| 阶段 | 工具定位 | DCF | 可比 | 舆情 |
|---|---|---:|---:|---:|
| 初创 startup | 期权/VC 法，P/E 无意义，EV/Sales 为主 | 0.25 | 0.55 | 0.20 |
| 年轻成长 young_growth | 情景 DCF + 生存概率，EV/Sales、EV/User | 0.30 | 0.50 | 0.20 |
| 高速成长 high_growth | 两阶段 DCF（增长+fade），终值易吞估值 | 0.30 | 0.50 | 0.20 |
| 成熟成长 mature_growth | 标准 DCF 与交易倍数并列 | 0.35 | 0.50 | 0.15 |
| 成熟稳定 mature_stable | DCF/DDM + 倍数 | 0.40 | 0.50 | 0.10 |
| 衰退 decline | 清算价值 vs 持续经营价值并列 | 0.45 | 0.45 | 0.10 |

**为什么换掉乘数**：三处可复算硬伤——初创舆情 ×1.5 归一化后占 **37.50%**，是 DCF 18.75% 的两倍；成长档恒等 `{1,1,1}`，终值常 70%+ 却零调整；衰退与成熟的舆情占比只差 **0.05pp**，“按阶段调权重”空转。语义也错位：阶段问“用哪个工具”（方法定位），乘数答“某方法重要几倍”（重要性折算），12 个无出处系数既换不来工具替换，也无法一行审计。25 例仅改开关，Δ ∈ **[−4.69%, +3.03%]**。

**边界**：base 为 0（用户显式禁用）与 Layer 0 否决 DCF，二者不得被表“复活”，统一记 `blocked_paths`（中航沈飞若覆盖成 0.40，中枢 −37.76%）；阶段由四阶段派生，关键是 **15% 线**，与 v326 的 8% 线不同源（美的 CAGR 9.85% 分属两档，须并列披露）；25 例落点 15/7/3/0/0/0，初创·年轻·衰退无实证。

### 4.2 Layer 0 前提 A/B 门与行业路由

**问题**：FCFF 并非对所有行业可定义。银行债务是经营原料、资本结构即经营要素；资源类价值随储量耗尽；管线药企现金流二元（成/败）；多分部集团合并现金流没有经济含义。硬跑 DCF 得到的是“看起来很专业的错数”。**实现**：`framework_admissibility()` 检验 A 现金流可定义/可预测（经营流可分离、负 FCFF ≤60%、有正现金流史、数据完备）与 B 资本结构≈融资选择（不受资本充足率监管、D/E 可目标化、利息非经营成本），不成立则改走替代主方法，并用 `dcf_weight_cap` 封顶或归零：

| industry_class | DCF 准入 | 建议主方法 | 权重上限 |
|---|---|---|---:|
| financial | 否 | RIM / DDM | 0.0 |
| resource | 否 | NAV | 0.0 |
| reit_utility | 条件 | NAV | 0.3 |
| pipeline_pharma | 条件 | rNPV | 0.2 |
| holdco | 条件 | SOTP | 0.3 |
| negative_fcff | 条件 | 概率加权 DCF | 0.3 |
| general | 是 | DCF | 1.0 |

v3.17.0 补三条：P1 让替代方法**可携带权重进入综合**（否则“只渲染成文本”等于没实现）；P3 判据四维化（σ_ln 判周期、终值占比、ROIC−WACC）；P5 补齐 RIM/DDM。rNPV 只对上市后收益乘 PoS、成本不乘；SOTP 只做加总桥与控股折价，不在引擎内重跑分部 DCF。

**边界**：关键词路由靠中文别名，同形异义会误命中——“高速”曾把“高频高速覆铜板”判成收费公路（已改“高速公路”）；裸“资源”仍可能命中“人力资源服务”、裸“生物”仍可能命中“生物质能/生物农药”（**未修，留痕备查**）。路由只决定“谁当主方法”，不保证替代方法数据齐备。

### 4.3 三路/多路加权与四部分拆分

**问题**：旧综合式把 DCF、可比法、情绪修正混在一个加权平均里，情绪既进了可比倍数、又被单独加权，同一事件计两次。**实现**：v3.15.0 起四部分独立合成——① DCF（缺省 0.30，内在价值、不承受市场修正）；② 可比公司法（0.50，含盈利质量、商誉折价、因子校准、流动性折扣）；③ 市场舆情（0.20，`comp_v×(1+情绪修正)`，clamp ±10%，与质量解耦）；④ 统计区间（不参与加权，供 P5–P95）。合成式 `value = ②×w_comp + ③×w_sent + ①×w_dcf`，输出 `synthesis.four_part` 逐项值与权重。v3.17.0 的 P1 把候选集从写死三路泛化为路由驱动，P2 可把舆情降为“作用于②的乘性修正”，B5 声明②③共用 `comp_v`、有效路径数按 **2.3** 计。

**边界**：`four_part_mode` 缺省 true 是**既定 breaking change**（质量系数 0.7→0.5、情绪 0.7→0.2），v3.15 前的旧输入默认中枢会变；“零回归”只覆盖各逐项开关，不覆盖四部分本身；权重仍有人工成分，覆盖后“方法定位表”与“用户偏好”谁优先须在报告写清。

### 4.4 增长函数 `g_t = tg + (g1 − tg)·E(t)`

**问题**：旧五形态三处硬伤——`s_curve` 名为 S 曲线、实为“第一年跌得最狠”的反向 logistic；exp/mean_revert/s_curve 都是渐近线，永不到达 tg，只能靠 `forced` 尾段等差插值，把形态静默作废；`rho/half_life/lam` 全部无出处。**实现**：v3.29.0 改为**缺口归一化族**，`E(1)=1`、`E(n)=0` 由构造保证，既精确过首年、又精确闭合 tg，无需补丁。四种 E(t)：`logistic_cap`（真 S：平台→陡降→平台，拐点=CAP）、`geometric`（κ=1−1/CAP）、`mean_revert`（ρ=0.62，来自 Fama-French 2000 的年均回归 38%）、`linear`。六档 n=10/10/8/7/6/4、CAP=6/5/4/3，n 与 CAP 均有随阶段不增的双向断言；`CAP ≥ n−1` 时 S 曲线降级线性并留痕 `form_downgraded`。另有状态空间路径 `growth_model`（趋势层 μ + 幂次冲击 u），冲突时 plc6 优先并挂 warning。

**边界**：`growth_shape_mode` 缺省 `legacy`，opt-in 后 10 例 Δ ∈ [−4.14%, +1.84%]；形态**可识别性**有限——终值占比中位 70%、DCF 权重 0.30，差异传到总估值约打 0.09 折，缺口 3pp 时四形态极差 1.69pp → 总估值 0.15%，缺口 47.5pp 时上限也只有 2.0%，`logistic_cap` 与 `linear` 在 cap=3/n=6 下差 ≤0.17%。故“六态配六函数”不可识别，文档明确拒绝（判据 I18）。

### 4.5 参数底座与行业参数库

**问题**：WACC 曾硬编码 11%（rf 1.9% 时代的旧值），不填 WACC 时 DCF 被系统性低估三成以上；ERP 又有 Damodaran 5.5% 与 CVA 隐含 8.04% 两套口径，混用则 WACC 差 2.5pp×β。**实现**：`wacc_model()` 做 CAPM 分解——rf 1.9%、ERP 双轨（`capm_auto` 取 CVA 8.04%、否则 5.5%）、β 四级链（用户 > 无杠杆再杠杆 > 可比均值再杠杆 > 行业兜底）、D/E 取可比中位；显式 WACC 优先、CAPM 只作校验。`industry_params.json`（11 个行业 + default）提供 β_u、WACC 区间、kd、税率、`g_lt`、ROIC、PE/PS 中枢、`half_life`，作为**参数第 4 档来源**与**校验锚**（WACC 偏离区间 ±0.5pp、倍数偏离中枢 >30% 告警）；行业匹配按**最长命中别名优先**。

**边界**：ERP 是对中枢影响最大的一项——格力实测 8.04%→5.5% 使每股 65.29→89.38（**+36.7%**），远超其余修复项之和；无 `wacc_params` 时 β 只能靠 `industry_beta`（default 1.00），正解是 `beta_estimator.py` 回归或补 `unlevered_beta`；未覆盖行业回落 default，`g_lt`/`half_life` 仍属先验。

### 4.6 可比证据链与 β 60 个月回归

**问题**：监管问询“发行 PE 高于可比中位数”时，第一个问题是“你为什么只选这几家”。技能的 `comparables` 是外部输入，没有长名单、剔除台账和信息截点，结论无法自证。**实现**：`peer_screening.py` 四期判据——P0-1 长名单/剔除台账（分类基准、长名单 ≥2× 最终样本、剔除理由落枚举、覆盖率）；P0-4 信息截点（财务期末晚于截点=用基准日后数据回填）；P0-2 规模双口径 5 倍（收入与市值比值取偏离 1 更远者）；P0-3 同一实体去重（A 股优先于大市值 H 股）；P1-1 跨准则标记但不删除；P1-4 次新股 12 月剔除 / 12–24 月 watch；P1-5 指数锚四级降权 1.00/0.50/0.40/0.30。状态机 `ok/degraded/weak/unavailable` 对应建议权重 1.00/0.50/0.25/0.00 与置信度上限。默认**诊断模式**只产问题清单、不改数值；`enforce.filter_sample=true` 才过滤，过滤后为空必须阻止执行。`beta_estimator.py` 用东财月 K 线做 **60 个月 OLS**（含 R²、样本量），再按 D/E 去杠杆，支持 A/美/港股，失败给手动建议而不阻断。

**边界**：技能**不能自己找可比**，只能要求证据、缺失降级、逐项留痕；长名单中位缺失时退化为最终样本中位代理；可比公司“经营性”与“投资性”利润拆分**未解决**（含联营投资收益的白电龙头 PE 会失真）；`weight_keep` 只是建议值。

### 4.7 统计校验层

**问题**：WACC、增速、净利率、终值增速、倍数、情绪修正都是主观判断，点估计无法表达“这些判断整体上有多不确定”。**实现**：`stat_validation.py` 按 `calibration_params.json` 先验做 **3000 次联合抽样**（固定 seed 42），得 P5–P95 的 90% 区间与直方图；每参数单独 ±1σ 扰动并做 OLS 得弹性与影响度排序；MC 样本中参数扰动值与估值做 Spearman 秩相关；稳健性跑 3 种权重方案 + 可比极端样本剔除；最后以“原始情景区间 ∩ MC 90% + 稳健中枢”给修正区间。成功率 ≥95% 才算 `validation_passed`。三者分工清楚：S4.4 确定性敏感性是单变量两档点扰动（方向），4b 是全参数联合分布（带宽），Step 5 是三档离散情景（中枢）。

**边界**：先验是经验值（WACC σ1.5pp、净利率 3pp、终值增速 1pp、倍数 σ0.2），“统计显著”不等于“经济正确”；clamp 是绝对区间，曾使负增速标的扰动被截回 0、低 WACC 标的弹性“同号非单调”，基线感知下界只是补丁；修正区间取交集，偏窄是保守化代价。

### 4.8 置信度、报告与机检

**实现**：`factor = (0.7+0.3×完整度) × (0.6+0.4×质量/60) × 因子校准系数`，≥80 高、60–80 中、<60 低；再叠三类校正——方法覆盖度（DCF 不适用且单市场法驱动，×diversity 并封顶 79.9）、方法分歧度（`method_cv > 0.60` 时折减并封顶）、参数护栏（终值占比 >85% 封顶、tg 守卫 −20 分）。`html_check.py` 八项：C1 占位符/无外链、C2 标签平衡、C3 符号重复、C4 单位符号冗余、C5 根因防护、C6 数字对照引擎、C7 章节结构、C8 渲染残留，退出码非 0 不得交付。

**边界**：`--output` 指向**引擎输出 JSON** 而非机检结果路径，误传报告路径会 `FileNotFoundError`；C1/C8 抓不到“键缺失渲染 `None`”（融资锚 `适用=None` 只能靠新增断言）；机检保证“没有明显错误”，不保证“数字合理”。

### 4.9 输入 schema / 校验 / 错误处理

**实现**：`input_schema.json` 只强 required 两块（`meta`、`financials`），另有 70 条字段规则，由 `input_validator.py` 静态检查；引擎 `_validate_input` 做业务勾稽（毛利率>净利率、净利率×营收 vs 净利偏差 ≤30%、可比时点差 ≤30 天、数据时效 ≤180 天）。`error_handling.md` 按输入/数据/计算/推理/统计/场景分层，原则是“宁可标注假设、不可编造数字”“矛盾必须告知口径”“缺失降级不阻断”。

**边界**：schema 与引擎校验是两层，静态通过不代表业务自洽；显式 `null` 防御（`_nn`、`get(k) or 0.0`）属补丁族，历史上同一缺陷多次暴露（中国平安崩溃、`issue_shares: null`、融资锚 `None` 渲染）。

---

## 5. 设计思想提炼

1. **结构化先验优先于黑箱拟合。** 能用一张可读表表达的，就不写拟合或隐式系数：`DAMODARAN_STAGE_WEIGHTS`（六行三列）、`SIGNAL_STRENGTH_MATRIX`（量级×一致性）、`PLC6_SHAPE_PARAMS`（n/CAP/形态）、`TV_SHARE_GRADES`（40/75/85）。LLM 负责取数与叙事，不负责发明数值。

2. **可审计证据链优先于结论。** 每个数字都要能回答“从哪来”：可比七项判据 + 剔除理由枚举 + 状态机；`growth_seq_detail[{t,g,src,clamped_by}]` 逐年标来源；`coefficient_detail` 让权重可逐项复算；`data_sources[]` 带 `as_of`。判据 I16：需“先乘 A 再归一化”才看得到结果的参数，应改为直接权重表 + 证据列。

3. **边界护栏优先于“算得出来”。** `blocked_paths`（显式归零/Layer 0 否决不得被表复活）、结构参数单调性导入期断言（违反直接抛错）、`floor = max(0, net_cash)`（股东有限责任）、DDM 四条适用性护栏、PEG 双道护栏、终值占比 >85% 禁出单点。共同点：宁可不出数，不出错数。

4. **单一真源与版本化参数。** 常量集中在引擎顶部与 `industry_params.json`，报告层不自算、只渲染引擎输出（生成器 docstring 反复强调“引擎与统计数值零改动”）；参数库带版本（industry_params 1.0.1→1.0.3，calibration 有 default + case 覆盖），改表即改口径。

5. **机器可检优先于人工复核。** 170 个冒烟用例不是“跑通”，而是分层断言：源码结构断言、行为断言、**反向断言**（不得出现某文案/调用）、性质测试（权益恒 ≥0 且随净现金单调不减）、AST 断言（`_pct()` 不得 0 位小数）、A/B 逐字节零回归；报告侧再用八项机检兜交付。

6. **失败可解释、诚实退化。** “任何算了但没用的数字，最终一定会被引用一次”——未选中的 FCFF 口径只输出 `skipped + switched_to + reason`；可比法不可用时 `renormalize` 并挂 `method_drop`，不按 0 静默计入；口径冲突（8% vs 15% 线、显式阶段 vs 客观证据）并列披露并挂 warning，不由引擎替用户裁决。

这些思想与文献的对应关系：可审计/溯源对应输出层 F 的 [B][D]（幻觉三层防御的后置环节）；分步推理与裁决对应推理层 E 的 [B][C]；增量维度对应 [A]；而单一真源、机器可检、诚实退化属工程补充（未标注），不应冒充论文原文。

---

## 6. 局限与风险

- **无真值。** 全套体系校验的是“内部一致、可复算、可解释”，没有一例用事后股价或发行定价做样本外检验。论文“实证分析”在技能里是案例校验（长鑫、DeepSeek、格力、美的等），不是统计回测。
- **参数经验性强。** 六阶段权重、PoS 表、商誉折价档、情绪强度矩阵、行业 `g_lt` 多为先验；技能自认 `rho/half_life/lam`“全部无出处”并在 v3.29 替换，但 CAP 拐点仍是标定值，形态差异对总估值上限只有约 2%。
- **样本覆盖窄。** 25 例落点 15/7/3/0/0/0，初创、年轻成长、衰退三档**零实证**；样本几乎全是已上市主体（发审筛选把“青春期”与“晚年”剔掉了），而这恰是 IPO 估值最需要的三档。Dickinson 美国分布约 6/38/43/7/6，差距是结构性的。
- **复杂度与可维护性。** 引擎 5,681 行、报告生成器 146KB、SKILL.md 182KB 且 1,208 行里大量超长行；十个 opt-in 模块彼此有仲裁规则（Layer 0 vs B4、plc6 vs growth_model、four_part vs 旧合成），改一处要同时看常量、导入期断言、冒烟用例、报告披露。
- **版本漂移已经发生。** 标题 3.29.1、frontmatter 3.16.12、引擎 2.28.0、SKILL 描述 2.27.1/清单 2.27.0、冒烟 170 vs 169；批跑按 3.31.0 适配，工作树却无 `industry_fallback`、不读 `net_assets_fallback`。若直接替换线上技能目录，两处 v3.31 护栏会**静默失效**（不报错、只是不生效）。
- **LLM 层与引擎层的边界靠纪律。** 引擎纯标准库、无网络、可复算；LLM 只在取数、画像、叙事、报告层活动。但报告 11 段大量文案由引擎字段拼装，“渲染型自由文本未全量覆盖”同族缺陷暴露过 **6 次**（伊利/美的/三一/中车/中国石油/北方稀土），说明边界靠逐站点扫描与机检断言维持，不靠架构图。

---

## 7. 拆分 TODO：从单仓技能到可组合模块

目标不是“把大文件切小”，而是让每个模块有稳定输入/输出契约，可独立测试、可被批跑按需组合。建议 9 个模块（≈“8 个左右”，数据与财务合并、报告与机检合并）：

| # | 模块 | 输入 | 输出 | 依赖 | 验收标准 |
|---|---|---|---|---|---|
| M1 | 数据与财务口径 | 代码/披露文档/行情 | 归一化 `financials`（净利披露档、margin_history、ocf/capex、roic、股本）+ `data_sources` | 无（仅公开接口） | 缺字段显式 null + 来源；同代码两次抓取逐字节一致（缓存命中） |
| M2 | 画像与生命周期 | `financials` + `meta` | `lifecycle{stage,sub_stage,evidence}`、`quality_scorecard` | M1 | 25 例落点与 v3.29.1 逐位一致；零覆盖档标注“无实证” |
| M3 | 可比池与证据链 | `comparables` + `target_profile` + `peer_screening` | `comparable_tiers`、`peer_screening.stages`、`comparable_betas` | M1 | 七项判据可复算；诊断模式全字段与基线逐字节一致（T109） |
| M4 | DCF 内核 | `financials` + `dcf_growth`/`dcf_cost` + `dcf_drivers` | `scenarios.*.dcf`（wacc、growth_seq、tv_share、fcf_basis） | M2、M5 | 11 个 examples 的 DCF 值与基线逐位一致；单调性/终值断言全过 |
| M5 | 相对估值与替代法 | `comparables` + `segment_benchmark` + `rnpv`/`sotp` | `comparable_valuation`、`rim/ddm/nav/rnpv/sotp` 块 | M1、M3 | 手算交叉校验通过（T99/T102/T103）；未选中口径不产数值 |
| M6 | 舆情与增量维度 | `sentiment`（事件/政策/热度） | `impact_map`、`sentiment_adjust`、商誉折价 | M1 | 方向/强度正交；band 分化与 K_MAX 上限可复算（T100a–j） |
| M7 | 合成与裁决 | 各方法取值 + `preferences.weights` + 方法表 | `synthesis{four_part, weighted_mid, interval}`、`scenario_weights`、`confidence` | M2、M4、M5、M6 | 四部分自洽（权重和 1、逐项可加）；有效路径 2.3 与 `blocked_paths` 留痕 |
| M8 | 统计校验 | 输入 + M7 输出 | `monte_carlo`、`elasticity`、`correlation`、`robustness`、`adjusted_interval` | M7（需引擎可重跑） | 固定 seed 42 两次跑逐位一致；success_rate 口径不变 |
| M9 | 报告与机检 | M7 输出 + M8 统计 + 输入 | 11 段 HTML、`html_check` 退出码 | M1–M8 | 八项机检全过；15+ 案例 A/B 逐字节 IDENTICAL |

**如何保证“数值零回归”**：① **冻结基线**——把 v3.29.1 的 11 个 `examples/input_*.json` 与对应 output/stat 固化为 golden（含 `engine_version` 与 seed），拆分前后逐字节比对；② **三层门禁**——单元层（性质断言，如权益 ≥0、权重和 1）、样例层（golden byte-compare）、批跑层（25+ 案例的中枢/区间/置信度分布，差异须白名单并归因）；③ **开关语义不变**——每模块仍守“缺省 opt-in = 旧行为逐位不变”，新模块只能通过新键改数值；④ **顺序不可交换**——同一输入跑“串行”与“模块化编排”两遍，比对全部 JSON 键集合与浮点序列化；⑤ **版本钉住**——升级先改 golden 再改代码，不允许“先跑出新数再回填基线”。

---

## 8. 与仓库的接口

**批跑如何调用。** `packages/batch/config.py` 解析 `SKILL_DIR`：仓库内 `skills/llm-ipo-valuation` 优先，`VALUATION_SKILL_DIR` 可覆盖，缺省回落 `~/.dsh-valuation/agents/skills/...`；同时定义 `runtime/jobs`、报告归档 `~/.dsh-valuation/valuation-reports`、端口 3089。`pipeline.py` 用 `sys.executable` 起四个子进程，超时分别 600s（引擎）/1200s（统计）/600s（报告）/300s（机检）：

```
valuation_engine.py <input.json> -o <out.json>
stat_validation.py <input.json> <out.json> -o <stat.json> --n 3000 --seed 42
report_generator.py <out.json> -o <report.html> --stat <stat.json> --input <input.json>
html_check.py <report.html> --output <out.json>        # --output 是引擎 JSON，不是机检结果
```

机检退出码即 `row.check_ok`；随后 `report_theme.theme_file()` 就地注入终端风主题。单券失败不阻断整批，记 `status=skip` 与原因。指数拟合点位 = 指数收盘 × Σ(权重×每股估值÷收盘价) / Σ权重，跳过券不计入分子分母。

**输入 JSON 顶层字段**（`input_builder.build_input` 实际组装）：`meta`（公司/行业/板块/基准日/`framework_check`/市值/会计准则）、`financials`（营收与逐年序列、归母净利与 `net_profit_basis`、`margin_history`、roe/roic、ocf/capex、股本、亏损标记、`wacc_params`）、`comparables[]`、`sentiment`、`preferences`（weights/scenario_weights/lifecycle_mode/lifecycle_classifier_mode/layer0_check）、`dcf_cost`（`method_drop_mode=renormalize`、`wacc_default_mode=capm_auto`、`erp_default_mode=auto`、`fcf_ratio_lazy`）、`dcf_drivers`、`peer_screening`（长名单/剔除台账/截断/enforce 关闭）、`industry_index`、`segment_benchmark`、`fundraising`、`data_sources[]`、`_parse_ledger`（流程层产物，引擎不消费）。

**输出 JSON 关键字段**：`synthesis`（`weighted_mid`/`interval`/`method_cv`/`dcf_tv_share_base`/`four_part{part1_dcf, part2_comparable_quality, part3_market_sentiment, part4_statistical}`）；`confidence`（`score`/`level`/`data_completeness`/`methods_available`，触发时另有 `method_divergence`/`method_coverage`）；`lifecycle{stage, stage_label, source, confidence, sub_stage?, evidence}`；`net_profit_basis_used{basis, source}`；`scenarios.{bear,base,bull}`；`wacc_model`、`cashflow_statistics`、`growth_triangulation`、`peer_screening`、`fcf_ratio`、`warnings[]`；以及仅触发时挂出的 `wacc_default`、`method_drop`、`point_estimate_suppressed`、`comparables_shortfall`。批跑 `row` 取 `weighted_mid/per_share/interval/four_part/confidence_level/stage_label/basis/check_ok/warnings[:6]`。

**报告与机检的关系**：报告是引擎输出的渲染器，不做重算；机检 C6 用 `--output` 指向引擎 JSON 做关键数字逐位对照，C7 校验 11 章结构与 `id="s1..s11"` 锚点（目录为可选组件，默认不出），C8 抓未渲染 Markdown 与裸占位符。三者构成“引擎→报告→机检”单向链：机检失败即该券不可交付，但机检通过不等于估值合理。

**版本差对接口的影响**（联调必查）：本次实测 `input_example.json` 输出 `2.28.0` / 中枢 `261.4` 亿 / 置信度「高」，输出中无 `industry_fallback`。工作树引擎不产 `synthesis.industry_fallback`，`pipeline.py` 里“行业基准兜底→置信度低”的分支永远不会触发；`input_builder` 写入的 `financials.net_assets_fallback` 在 v2.28.0 引擎中无消费方（引擎只读 `net_assets`），会退化为普通忽略字段。两处都不报错，只会让线上报告比生产环境“少一层兜底”。合并前应以 `d06a5ed` 批跑 + 3.31 引擎跑同一批券做差分，确认中枢与置信度分布一致。
