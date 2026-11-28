# 03 · 模块目录（Module Catalog）

> 状态：**设计稿**。本目录是 VCG / MVN 的模块清单与契约草案，用于评审、排期与测试设计；**不代表已实现**。  
> 协议见 [02-architecture.md](02-architecture.md) §2；两份图实例见 [`graphs/monitoring.yaml`](graphs/monitoring.yaml)、[`graphs/ipo.yaml`](graphs/ipo.yaml)。  
> 基线事实：批跑 `packages/batch/`（`d06a5ed`）、技能包 `skills/llm-ipo-valuation`（SKILL v3.29.1 / 引擎输出 2.28.0，170 用例全绿）。

## 0. 怎么读这张表

- **ID 规范**：`层.功能`，层取 `enc`（编码）、`val`（估值）、`gate`（门控）、`pool`（组合/池化/合成）、`critic`（评论家）、`entry`（入口）、`out`（输出）。ID 即图节点 `type`。
- **类型枚举**：核心五类 `encoder / valuation / gate / pool / critic` 与原型 `prototype/valnet/spec.py` 的 `MODULE_KINDS` 一致；本文另加 `entry` / `report` 两类，仅用于入口与输出适配，不参与估值算子语义。
- **状态口径（必须诚实区分）**：
  - `existing`：现有代码已实现，且当前生产跑批**已在使用**；包成模块主要是接口整理。
  - `wrap`：现有代码已实现，但**未以模块形式暴露**（可能未被批跑接入、或在引擎内部耦合），需要写适配层、契约测试与 trace。
  - `new`：现有代码没有，需要新写。
  - `proposed`：论文/研究扩展，不承诺本阶段工程落地，只做离线实验。
- **输入/输出**使用 [02](02-architecture.md) §2.1 的类型名（`FinancialsBatch`、`MethodValue` 等），不是随意 dict。
- 每个模块的「验收」都默认包含三条共性门槛：契约测试（端口/类型/约束）、失败隔离（单格失败不阻断整批）、可复算（同输入同参数同 as_of 输出稳定）。个别模块另有专项门槛。

## 1. 模块总览（42 个）

| # | ID | 名称 | 类型 | 状态 | 层/组 |
|---|---|---|---|---|---|
| 1 | `enc.financials` | 财报编码 | encoder | wrap | 数据/编码 |
| 2 | `enc.industry` | 行业/板块编码 | encoder | wrap | 数据/编码 |
| 3 | `enc.lifecycle` | 生命周期编码 | encoder | wrap | 数据/编码 |
| 4 | `enc.cost_capital` | 折现率编码（WACC / Ke） | encoder | wrap | 数据/编码 |
| 5 | `enc.peers` | 可比池编码 | encoder | wrap | 数据/编码 |
| 6 | `enc.sentiment` | 舆情编码 | encoder | existing | 数据/编码 |
| 7 | `enc.pit_quality` | PIT/质量掩码 | encoder | new | 数据/编码 |
| 7a | `agent.evidence` | 前置采样/证据智能体 | encoder | new | 数据/编码 |
| 8 | `val.dcf` | DCF 现金流贴现 | valuation | wrap | 估值 |
| 9 | `val.comparable` | 可比法（PE/PS/EV-EBITDA/PB；PEG 护栏） | valuation | existing | 估值 |
| 10 | `val.sentiment` | 舆情修正法 | valuation | existing | 估值 |
| 11 | `val.rim` | 剩余收益模型 | valuation | wrap | 估值 |
| 12 | `val.ddm` | 股利贴现模型 | valuation | wrap | 估值 |
| 13 | `val.nav` | 净资产价值法 | valuation | wrap | 估值 |
| 14 | `val.rnpv` | 管线药企 rNPV | valuation | wrap | 估值 |
| 15 | `val.sotp` | 分部加总 SOTP | valuation | wrap | 估值 |
| 16 | `val.quality_adjust` | 质量/商誉/流动性调整 | valuation | existing | 估值 |
| 17 | `val.anchor_tx` | 交易/融资/回购锚 | valuation | wrap | 估值 |
| 18 | `val.industry_fallback` | 行业基准兜底 | valuation | wrap | 估值 |
| 19 | `gate.layer0` | Layer 0 路由门 | gate | existing | 门控 |
| 20 | `gate.quality` | 数据质量门 | gate | new | 门控 |
| 21 | `gate.ipo_eligibility` | 发行条件/定价约束门 | gate | new | 门控 |
| 22 | `comb.residual` | 行业残差 | pool | new | 组合/池化 |
| 23 | `comb.attention` | 可比注意力 | pool | wrap | 组合/池化 |
| 24 | `comb.norm` | 截面归一/单位对齐 | pool | new | 组合/池化 |
| 25 | `ens.dropout` | 方法/证据 dropout 集成 | pool | proposed | 组合/池化 |
| 26 | `pool.linear` | 线性池 | pool | existing | 组合/池化 |
| 27 | `pool.log` | 对数池 | pool | new | 组合/池化 |
| 28 | `pool.product` | 专家乘积池 | pool | new | 组合/池化 |
| 29 | `unc.interval` | 区间/不确定性合流 | pool | wrap | 组合/池化 |
| 30 | `idx.index_fit` | 指数合成与交叉校验 | pool | existing | 组合/池化 |
| 31 | `critic.experts` | 三专家（可比/折现/舆情） | critic | existing | 评论家 |
| 32 | `critic.main` | 主审裁决 | critic | existing | 评论家 |
| 33 | `critic.shadow` | 影子对照 | critic | existing | 评论家 |
| 34 | `critic.apply` | 有界回写/回滚 | critic | existing | 评论家 |
| 35 | `critic.ledger` | 参数台账 | critic | new | 评论家 |
| 36 | `critic.audit` | 审计与留痕 | critic | new | 评论家 |
| 37 | `critic.evaluator` | 评估 Agent/合成目标/指标 | critic | new | 评论家 |
| 38 | `entry.monitor` | 指数监控入口 | entry | existing | 入口/输出 |
| 39 | `entry.ipo` | 单公司 IPO 入口 | entry | new | 入口/输出 |
| 40 | `out.report` | 报告生成与机检 | report | existing | 入口/输出 |
| 41 | `out.compliance` | 定价约束/合规输出 | report | new | 入口/输出 |

**状态统计**：existing 13、wrap 15、new 13、proposed 1。即：**28 个模块的「算法本体」在仓库里已有实现**（13 个生产在用、15 个待包装），13 个要新写（含前置证据智能体），1 个纯研究模块（另有 1 个既有模块的研究子项）。这个比例决定了 [05](05-implementation-plan.md) 的 V0–V1 策略：**先包再拆，先图后搜**。

---

## 2. 数据/编码层

### 1. `enc.financials` · 财报编码
- **类型**：encoder
- **输入**：`UniverseBatch`（成分券/公司）、as_of
- **输出**：`FinancialsBatch`（营收、归母净利、净利率、ROE、OCF、Capex、股本、质量五指标、`net_profit_basis`、`data_as_of`）、`provenance[]`
- **约束**：金额统一亿元、比率小数；年报与 TTM 不混用；缺失必留 `missing[]`，不得静默补零；`loss_making` 与净利符号一致
- **状态**：wrap（`input_builder.build_input` 内部组装，`dsources.financials` 已实现；需抽成 batch 节点）
- **代码**：`packages/batch/input_builder.py:318`、`dsources.py:413`、`skills/.../fetch_data.py`
- **验收**：与现有 `input_builder` 对 11 组 examples 逐字段一致；缺失注入只掩码目标券；`data_as_of` 必填

### 2. `enc.industry` · 行业/板块编码
- **类型**：encoder
- **输入**：`UniverseBatch`、公司行业字段
- **输出**：`IndustryBatch`（申万二级/板块、行业键、前缀/粗板块回退链、行业分类来源）
- **约束**：分类基准必须声明（SW2021）；回退层级必须记录；不得把「未分类」静默归入某个行业
- **状态**：wrap（`input_builder._industry_base/_sector_members`、引擎 `industry_params_resolve` 已实现）
- **代码**：`input_builder.py:42–67`、`dsources.py:211 industry_valuation`、`skills/.../assets/industry_params.json`
- **验收**：与引擎 `industry_params` 解析结果一致；回退链可复现；行业缺失券走入兜底且留痕

### 3. `enc.lifecycle` · 生命周期编码
- **类型**：encoder
- **输入**：`FinancialsBatch`、`IndustryBatch`
- **输出**：`LifecycleBatch`（六阶段、判别证据、增速三角、阶段标签）
- **约束**：结构证据优先于盈利符号；`亏损 + 营收≥5亿` 不得先于 `decline`；阶段判定必须可解释（cagr/净利率趋势/ROIC−WACC）
- **状态**：wrap（引擎 `classify_lifecycle`/`damodaran_stage`/`_classify_v326` 已实现，输入已带 `lifecycle_mode=auto`）
- **代码**：`valuation_engine.py:2375/2479/2600`、`input_builder.py` 的 `lifecycle_*` 偏好
- **验收**：与引擎生命周期输出逐券一致；六阶段方法权重表与 v3.28 口径一致；边界样本（正负切换）用例通过

### 4. `enc.cost_capital` · 折现率编码（WACC / Ke）
- **类型**：encoder
- **输入**：`FinancialsBatch`、`IndustryBatch`、`PeersBatch`
- **输出**：`CostBatch`（WACC、Ke、β、rf/ERP/kd/税率/D-E、金融路由 Ke）
- **约束**：WACC > 永续增速；银行行业 β 用 0.90 兜底；可比 β 截断 [0.5, 2.0]；工作台显式覆盖优先
- **状态**：wrap（`input_builder._financial_ke` + 引擎 `wacc_model` + `beta_estimator.py` 已实现）
- **代码**：`input_builder.py:31`、`valuation_engine.py:847`、`skills/.../beta_estimator.py`、`dsources.py:748`
- **验收**：与引擎 CAPM 结果逐位一致；β 退化护栏用例（银行/低波）通过；WACC 覆盖与 `tg` 冲突时报错

### 5. `enc.peers` · 可比池编码
- **类型**：encoder
- **输入**：`UniverseBatch`、`FinancialsBatch`
- **输出**：`PeersBatch`（5 家可比、长名单、剔除台账、规模倍数、覆盖率、报告期/口径）
- **约束**：同行业 → 前缀 → 粗板块三级回退；可比 ≤8 家；无可比不跳过；财务期晚于 as_of 须标注违规
- **状态**：wrap（`input_builder.peer_pool/pick_peers/_peer_evidence`、`peer_screening.py` 已实现）
- **代码**：`input_builder.py:68/111/126`、`skills/.../peer_screening.py`
- **验收**：与现有 5 家选择逐券一致；剔除台账完整；规模 5×/次新/去重规则按 `assets/ipo_rules_checklist.md` 命中

### 6. `enc.sentiment` · 舆情编码
- **类型**：encoder
- **输入**：`UniverseBatch`（代码/名称）、轮数、模式
- **输出**：`SentimentBatch`（标签、调整幅度 ±5%、证据条数/关键词、口径 rule/llm）
- **约束**：LLM 不可用时规则口径可继续；证据必须落盘；不得用未来新闻（时间截点）；LLM 调用记录模型/提示词哈希
- **状态**：existing（`sentiment.py` 规则 + `sentiment_llm.py` 已接入批跑；逐券 sidecar 调度已存在）
- **代码**：`packages/batch/sentiment.py:238`、`sentiment_llm.py`、`pipeline.py:410–413`
- **验收**：与现有输出逐券一致；无密钥时 LLM 模式明确拒绝；缓存 6h TTL 生效；证据可点回原文

### 7. `enc.pit_quality` · PIT/质量掩码
- **类型**：encoder
- **输入**：`UniverseBatch`、`FinancialsBatch`、`PeersBatch`、`SentimentBatch`
- **输出**：`QualityMask`（as_of 一致性、覆盖、财报滞后、亏损、可比缺失）+ 掩码理由
- **约束**：只做 mask/降级，不 drop；每条掩码必须有理由代码；PIT 不一致时禁止与当期数据拼接
- **状态**：new（现有 `data_as_of`、`quality_details` 有数据基础，但无统一 PIT/掩码层；`docs/03-engineering-roadmap.md` §6.3/6.6 待做）
- **代码**：`dsources.py`（各函数返回 as_of）、`input_builder.py` 的质量指标字段；**无统一 PIT 层**
- **验收**：PIT 混期注入必须触发掩码；mask 与 `CellError` 一一对应；旧任务（无 PIT 字段）按 legacy 解释

### 7a. `agent.evidence` · 前置采样/证据智能体
- **类型**：encoder（前置智能体层，不是估值器）
- **输入**：`UniverseBatch`、文档/公告/新闻/行业来源、时间截点 as_of
- **输出**：`EvidenceBatch`（逐券证据包：财务摘录、可比候选、舆情摘要、来源等级、时间、置信、未核验标记）+ `gaps[]`（缺什么、影响哪个模块）
- **约束**：**只改证据，不改估值参数**；不得把未核验文本当事实；不得越过 as_of 使用未来信息；每个字段带 provenance；LLM 调用记录 model/prompt hash；成本/并发受限
- **状态**：new（现有 `fetch_data`、`sentiment`、`peer_pool` 是程序化采集；LLM 文档解析/证据核验层尚未实现）
- **代码**：`dsources.py`、`sentiment.py`、`sentiment_llm.py`、`input_builder.py` 的采集逻辑；无统一 `EvidenceBatch`
- **验收**：证据包可回溯到原文/接口；缺口清单与下游 mask 一致；无密钥时降级为程序化采集；同 as_of 重复运行证据集合稳定（LLM 部分报重复采样方差）

---

## 3. 估值模块层

### 8. `val.dcf` · DCF 现金流贴现
- **类型**：valuation
- **输入**：`FinancialsBatch`、`LifecycleBatch`、`CostBatch`、门控输出（可用集/权重）
- **输出**：`MethodValue`（中枢、情景区间、TV 占比、敏感性、FCFF 驱动来源）、`evidence[]`
- **约束**：`g < WACC`；显式期 4–10 年；TV 占比 >85% 时不出单点（现有 guard）；负 FCFF 占比 >60% 时权重封顶 0.3
- **状态**：wrap（引擎 `dcf_valuation` 已实现且批跑在用；需抽为纯函数并输出统一 `ModuleOutput`）
- **代码**：`valuation_engine.py:4075`、`:3101 growth_model_schedule`、`:847 wacc_model`
- **验收**：11 组 examples + 170 用例数值零回归（|Δ|≤1e-9）；TV 极端档用例禁出单点；失败只掩码本格

### 9. `val.comparable` · 可比法（PE/PS/EV-EBITDA/PB；PEG 护栏）
- **类型**：valuation
- **输入**：`PeersBatch`、`AttentionBatch`、`FinancialsBatch`、门控/发行约束
- **输出**：`MethodValue`（各倍数隐含值、采纳倍数、质量调整后值）、倍数明细、剔除/护栏记录
- **约束**：非正倍数剔除；PEG 只单列不并入合成；PS 隐含值超市值 5×/10× 且利润率不匹配时整法弃用；可比 <3 降置信度（IPO 图只出区间）
- **状态**：existing（PE/PS/PB 与 PEG 护栏已实现并用；**EV/EBITDA 为新子倍数**，当前引擎无）
- **代码**：`valuation_engine.py:3738 comparable_valuation`、`:3306 industry_index_valuation`、`input_builder.py` 可比组装
- **验收**：现有 PE/PS/PB 数值零回归；PEG 护栏用例；EV/EBITDA 需新写并给数据口径（net debt/EBITDA）；
  可比缺失时 `renormalize` 生效、置信度降档

### 10. `val.sentiment` · 舆情修正法
- **类型**：valuation
- **输入**：`SentimentBatch`、可比基数 `MethodValue`、门控
- **输出**：`MethodValue`（修正后值/幅度）、证据链、`layer=correction` 标记
- **约束**：调整幅度 ±5%；只做修正层时权重为 0（不重复计费）；证据方向与幅度自洽
- **状态**：existing（`sentiment_adjust`/`_sentiment_correction` 已实现；批跑按三路权重接入）
- **代码**：`valuation_engine.py:3499/3668`、`input_builder.py:453–458`
- **验收**：与现有三路权重合成一致；修正层口径（w=0）用例；无舆情时明确「不适用」而非 0

### 11. `val.rim` · 剩余收益模型
- **类型**：valuation
- **输入**：`FinancialsBatch`（B0/ROE）、`CostBatch`（Ke）、门控
- **输出**：`MethodValue`、B0/ROE/Ke/持续性参数证据
- **约束**：金融类主方法；ROE 与 B0 同口径（归母普通股权益）；Ke > 永续；B0 缺失时不可用并再归一
- **状态**：wrap（`rim_valuation` 已实现，金融路由批跑在用；需模块化输出）
- **代码**：`valuation_engine.py:1364`、`input_builder.py:573–640`
- **验收**：银行/保险/券商样例数值零回归；B0 缺失用例；RIM 与可比交叉值可解释

### 12. `val.ddm` · 股利贴现模型
- **类型**：valuation
- **输入**：`FinancialsBatch`、`CostBatch`、门控
- **输出**：`MethodValue`（交叉校验值，权重默认 0）、分红率/增速证据
- **约束**：仅金融路由；权重 0 交叉校验；g∞ 与 Ke 的可行性；分红数据缺失时明确不可用
- **状态**：wrap（`ddm_valuation` 已实现，金融路由交叉校验用）
- **代码**：`valuation_engine.py:1470`、`input_builder.py:621–634`
- **验收**：与 RIM 交叉校验记录一致；权重 0 不进入合成；缺失分红用例不崩

### 13. `val.nav` · 净资产价值法
- **类型**：valuation
- **输入**：`FinancialsBatch`（资产/资源储量）、门控
- **输出**：`MethodValue`、资产重估明细
- **约束**：仅资源/公用路由；**数据当前未接入**，默认关闭（`enabled=false`）；不得用净资产兜底冒充 NAV（现有红线）
- **状态**：wrap（引擎 `nav_valuation` 已实现，但批跑未接 NAV 数据；`input_builder` 明确「资源/公用路由待 NAV 接入」）
- **代码**：`valuation_engine.py:1320`、`input_builder.py:509–510`
- **验收**：关闭时零回归；接入数据后需单独数据契约与样例；不得进入常规 PB/NAV

### 14. `val.rnpv` · 管线药企 rNPV
- **类型**：valuation
- **输入**：`FinancialsBatch`、个股覆写 `rnpv` 参数、门控
- **输出**：`MethodValue`、管线明细（适应症/阶段/成功率/峰值销售）
- **约束**：仅 `pipeline_pharma` 路由；参数只来自人工核定覆写（白名单）；缺覆写不可用
- **状态**：wrap（`rnpv_valuation` 已实现；批跑通过 `~/.dsh-valuation/overrides/` 注入）
- **代码**：`valuation_engine.py:1599`、`input_builder.py:274 _apply_stock_override`、`docs/spec/04-data-and-api.md` §5
- **验收**：覆写注入用例；无覆写时不可用并留痕；参数来源写入 `data_sources`

### 15. `val.sotp` · 分部加总 SOTP
- **类型**：valuation
- **输入**：`FinancialsBatch`（分部数据）、`IndustryBatch`、门控
- **输出**：`MethodValue`、分部倍数/折价明细
- **约束**：仅 `multi_segment` 路由；分部数据不全时不可用；分部间不得重复计市值
- **状态**：wrap（`sotp_valuation` 已实现；批跑尚未路由启用）
- **代码**：`valuation_engine.py:1747`、`input_builder.py` 行业路由
- **验收**：分部样例数值一致；缺分部数据时正确不可用；控股折价参数可审计

### 16. `val.quality_adjust` · 质量/商誉/流动性调整
- **类型**：valuation
- **输入**：可比 `MethodValue`、`QualityMask`、`FinancialsBatch`
- **输出**：调整后 `MethodValue`、质量评分、商誉调整、流动性折扣
- **约束**：只作用市场法；调整幅度有上限；质量评分输入必须可追溯（OCF/净利、ROIC、应收、商誉、非经常性）
- **状态**：existing（`quality_score`/`goodwill_adjust`/`liquidity_discount`/`ff_calibration` 已实现）
- **代码**：`valuation_engine.py:3382/3446/1288/3684`
- **验收**：与引擎调整后值零回归；分数构成可复算；调整不改变掩码

### 17. `val.anchor_tx` · 交易/融资/回购锚
- **类型**：valuation
- **输入**：`FinancialsBatch`、交易/融资事件数据、门控
- **输出**：锚定值/区间、溢价折价、证据
- **约束**：只作交叉/诊断，不直接进主合成（可按偏好单列）；事件时点必须早于 as_of
- **状态**：wrap（`transaction_valuation`/`recent_financing_anchor`/`repurchase_valuation` 已实现；批跑未接入）
- **代码**：`valuation_engine.py:1169/1199/1248`
- **验收**：事件时点违规用例被拦；与主中枢差异可解释；不改变默认合成

### 18. `val.industry_fallback` · 行业基准兜底
- **类型**：valuation
- **输入**：`FinancialsBatch`、`IndustryBatch`、门控
- **输出**：单点/区间参照、兜底口径标记、置信度「低」
- **约束**：仅当可比与 DCF 均无效时触发；口径写「行业基准兜底（单点参照）」；PB 兜底只走 `net_assets_fallback`，不进入常规 PB/NAV
- **状态**：wrap（v3.31 护栏在批跑 `_worker` 已实现；技能引擎可能不产出该字段，需以适配层统一）
- **代码**：`pipeline.py:317–321`、`input_builder.py:549–560`、`valuation_engine.py:3306`
- **验收**：双无效用例触发兜底且置信度「低」；不触发时零回归；报告与 UI 显性标注

---

## 4. 门控层

### 19. `gate.layer0` · Layer 0 路由门
- **类型**：gate
- **输入**：`IndustryBatch`、`QualityMask`
- **输出**：路由结果（financial / general / pipeline_pharma / multi_segment）、候选方法集、`blocked_paths`、权重帽
- **约束**：用户显式禁用方法不得复活；金融类 DCF 权重 0；A2 负 FCFF >60% 时 DCF 权重封顶 0.3；否决必须落痕
- **状态**：existing（引擎 `framework_admissibility`/`resolve_method_set` + 批跑 `layer0_check` 已实现）
- **代码**：`valuation_engine.py:2073/2157`、`input_builder.py:508–528/573–600`
- **验收**：路由结果与引擎逐券一致；A/B 门数值零回归；`blocked_paths` 完整

### 20. `gate.quality` · 数据质量门
- **类型**：gate
- **输入**：`QualityMask`、`FinancialsBatch`、`PeersBatch`
- **输出**：方法可用性、置信度帽、降级标记（无可比/低覆盖/滞后）
- **约束**：可比 <3 标注、=0 时剔除可比法；置信度只降不升；降档理由必须进报告
- **状态**：new（相关逻辑散落在 `pipeline._worker` 与引擎 confidence 计算中，未独立成模块）
- **代码**：`pipeline.py:314–327`、`valuation_engine.py:5261–5355`（confidence 计算）
- **验收**：无可比/低覆盖/滞后三类用例的置信度与标注一致；不重复降档

### 21. `gate.ipo_eligibility` · 发行条件/定价约束门
- **类型**：gate
- **输入**：`Company`、`Issuance`（板块、发行股数、发行后总股本、募投、实际发行价）
- **输出**：`IpoConstraints`（板块条件、流通比、募资、截点违规、只出区间的标记）
- **约束**：规则来源 `assets/ipo_rules_checklist.md`；财务期晚于 as_of = 违规；缺发行条款不得补默认值；不得输出「单一建议发行价」
- **状态**：new（规则文档与引擎 `ipo_check` 已有，但没有独立门控模块）
- **代码**：`skills/.../assets/ipo_rules_checklist.md`、`valuation_engine.py:4795 ipo_check`、`input_builder.py` 发行字段
- **验收**：各板块/未盈利/流通比用例；截点违规被拦；输出字段与 ipo.yaml 的 `pricing_constraints` 一致

---

## 5. 组合/池化层

### 22. `comb.residual` · 行业残差
- **类型**：pool
- **输入**：方法矩阵/单方法值、`IndustryBatch`（行业基准）
- **输出**：调整后值、`base/alpha/cap` 审计字段
- **约束**：`V = base + α(f(x) − base)`；`α∈[0,1]` 默认 0；`|V−base| ≤ cap·base` 且 `V>0`；α 不得无记录漂移
- **状态**：new（行业基准兜底是残差的退化特例，未抽象为算子）
- **代码**：`valuation_engine.py` 行业参数与 `input_builder.industry_index`；**无残差算子**
- **验收**：α=0 时输出与输入逐位一致；α>0 时边界与 cap 生效；审计字段完整

### 23. `comb.attention` · 可比注意力
- **类型**：pool
- **输入**：`PeersBatch`、`FinancialsBatch`
- **输出**：`AttentionBatch`（每家可比权重、top-k、kernel 参数）
- **约束**：top_k ≤8；权重和 1；可比 <3 时退化为等权并降置信；权重必须落盘；可复算
- **状态**：wrap（现有 `pick_peers` 的「规模对数距离 top-5」是均匀权重退化实现；softmax 注意力需新写）
- **代码**：`input_builder.py:68–110 peer_pool/pick_peers`
- **验收**：均匀权重与现有可比中位数一致；softmax 版本与均匀版本差异可解释；权重进证据链

### 24. `comb.norm` · 截面归一/单位对齐
- **类型**：pool
- **输入**：方法矩阵（各方法值/区间）
- **输出**：归一后矩阵 + 逆变换记录
- **约束**：winsorize 5%/95%；单位统一（亿元/元每股/小数）；拟合统计量只用当批；输出前逆变换；不改变掩码
- **状态**：new（引擎有 `exclude_outliers` 与部分单位处理，但没有独立归一化层）
- **代码**：`valuation_engine.py` 可比离群处理；`input_builder.py` 单位换算（`_free_cap_yi`）
- **验收**：归一→逆变换可还原（误差 ≤1e-9）；winsorize 只作用于声明范围；单位错误用例被拦

### 25. `ens.dropout` · 方法/证据 dropout 集成
- **类型**：pool
- **输入**：方法矩阵、seed、dropout 概率
- **输出**：集成分布/区间、成员记录、离散度
- **约束**：默认关闭；点估计默认仍取全方法；成本纳入预算；不得用于「训练」
- **状态**：proposed（研究项；现有 MC 抽样属于参数不确定性，不是方法 dropout）
- **代码**：`stat_validation.py`（MC）、`valuation_engine.py` 情景；**无方法 dropout**
- **验收**：p=0 零回归；p>0 时分布可复算；与 MC 区间的关系有实验报告

### 26. `pool.linear` · 线性池
- **类型**：pool
- **输入**：方法矩阵、权重、掩码
- **输出**：`Valuation`（中枢/区间/置信度/四部分分解）
- **约束**：`renormalize` 剔除缺失方法；加权和；区间线性传播；三情景同权重
- **状态**：existing（引擎 `synthesis` 与 `pipeline._finalize` 指数合成都用线性池）
- **代码**：`valuation_engine.py:5377–5455`、`pipeline.py:554–596`
- **验收**：与现有 `weighted_mid`/`interval` 逐位一致；方法缺失时数值不缩水

### 27. `pool.log` · 对数池
- **类型**：pool
- **输入**：方法矩阵、权重、掩码
- **输出**：`Valuation` + 对数空间诊断
- **约束**：所有值必须 >0；非正值先 mask/nudge 并留痕；区间 `[exp(Σw ln a), exp(Σw ln b)]`；输出必须落在方法值 min/max 内
- **状态**：new（路线第五层待实现）
- **代码**：无；参考 `docs/03-engineering-roadmap.md` §3.5
- **验收**：与线性池可切换；负值用例不产生 NaN；离线对比报告（偏离/稳定性）完成

### 28. `pool.product` · 专家乘积池
- **类型**：pool
- **输入**：方法矩阵、每方法 σ/区间、权重
- **输出**：`Valuation`（精度加权中枢、合成 σ、区间）
- **约束**：需先校准 σ；方法相关时乘膨胀因子；无 σ 时不得使用
- **状态**：new（路线第五层待实现）
- **代码**：无；σ 来源可复用 `stat_validation` 的敏感性
- **验收**：σ 未校准时拒绝启用；与线性池差异可解释；区间覆盖实验通过

### 29. `unc.interval` · 区间/不确定性合流
- **类型**：pool
- **输入**：`Valuation`、各方法区间、MC 设置
- **输出**：`Interval`（情景区间 ∩ MC 90%）、覆盖率、宽度诊断
- **约束**：报告区间口径统一为「情景区间 ∩ MC 90%」；区间必须包含中枢；不得为了收窄区间丢弃方法
- **状态**：wrap（现有 `pipeline` 取情景区间 ∩ MC；`stat_validation.py` 产 MC；池化传播为新）
- **代码**：`stat_validation.py`、`pipeline.py:187–211 _scenario`、`valuation_engine.py` 区间输出
- **验收**：与现有报告区间口径一致；池化切换后区间仍包含中枢；覆盖率记录进 trace

### 30. `idx.index_fit` · 指数合成与交叉校验
- **类型**：pool
- **输入**：`Valuation`、`Interval`、`UniverseBatch`（权重/收盘）、`IndexQuote`
- **输出**：拟合点位、三情景、权重口径、交叉校验、偏差分解
- **约束**：口径 A 零回归；口径 B 并列不替换；三情景单调；同券在不同指数估值必须相同；不做反向校正
- **状态**：existing（口径 A 在 `pipeline._finalize` 已实现；口径 B/交叉校验/偏差分解为**新增**）
- **代码**：`pipeline.py:554–596 _finalize`、`docs/03-engineering-roadmap.md` §3.4
- **验收**：口径 A 与现网逐位一致；五指数并列表；交叉一致性每条差异有解释；权重口径 100% 标注

---

## 6. 评论家层

### 31. `critic.experts` · 三专家（可比/折现/舆情）
- **类型**：critic
- **输入**：各专家证据域、当前参数、基线估值
- **输出**：参数建议（param, delta, severity, confidence, evidence, reason）、`gated[]`
- **约束**：专家只见本域证据；不得看指数拟合点位；参数权限与 caps 硬约束；证据门槛 ≥0.65、含数字、方向自洽
- **状态**：existing（`shadow.py` 三专家已实现并在 shadow/apply 使用）
- **代码**：`shadow.py:86–132`（提示词）、`:481 _gate`、`:516 _proposals`、`:702 review`
- **验收**：与现有评审记录逐字段一致；越权/门槛用例；金融路由只 `financial` 参与

### 32. `critic.main` · 主审裁决
- **类型**：critic
- **输入**：专家建议、合并证据、基线、caps
- **输出**：逐条 accept/clamp/reject + 任务级 decision
- **约束**：不新增参数；不跨域；夹断到 caps；方向自洽；主审关闭时 hold；失败不改参数
- **状态**：existing（`shadow.py:134–156` 提示词、`:774–819` 裁决逻辑）
- **代码**：`shadow.py:134/774–821`
- **验收**：与现有主审行为一致；夹断/驳回用例；`decision` 分布与 `shadow.metrics` 对账

### 33. `critic.shadow` · 影子对照
- **类型**：critic
- **输入**：同上
- **输出**：只留痕记录（`*.shadow.json`）
- **约束**：不改引擎参数；与 apply 同提示词/门槛（对照可比）；记录含完整证据
- **状态**：existing（`agent_mode=shadow` 已实现）
- **代码**：`shadow.py:702 review(mode='shadow')`、`pipeline.py:247–253`、`shadow.py:1109 save_record`
- **验收**：shadow 不改变任何数值；记录可复核；与 apply 的差异只在「是否回写」

### 34. `critic.apply` · 有界回写/回滚
- **类型**：critic
- **输入**：主审通过项、当前输入、baseline
- **输出**：新输入/新中枢/changes/skipped；失败回滚
- **约束**：可行域（权重和=1、WACC>g）；先备份 baseline；重跑失败恢复；留痕 `apply.error`
- **状态**：existing（`shadow.apply_to_input` + `pipeline._worker` apply 分支已实现）
- **代码**：`shadow.py:944`、`pipeline.py:254–280`
- **验收**：回写数值与现有 apply 一致；失败回滚零泄漏；`changes/skipped` 完整

### 35. `critic.ledger` · 参数台账
- **类型**：critic
- **输入**：裁决/审批/回写事件
- **输出**：版本化参数（proposed→…→applied/superseded/rolled_back）、哈希链
- **约束**：append-only；人工审批点；批内快照不变；可重放任意版本；与 agents.json 并存迁移
- **状态**：new（`agent_config.py` 只有当前一版；跨批台账是路线第三层待做）
- **代码**：`agent_config.py:163–184`（现状）、`shadow.py:1151 _consensus`（批级信号）
- **验收**：给定版本可完整还原参数；次日默认=最新 approved；回滚可重放；哈希链校验

### 36. `critic.audit` · 审计与留痕
- **类型**：critic
- **输入**：图运行产物（节点输出/trace）、参数台账事件、报告与机检结果
- **输出**：审计记录（run_id、graph/module 版本、params_hash、模型/prompt_hash、审批人、回滚链、哈希链）
- **约束**：append-only；任何数值可回溯到「模块版本 + 参数版本 + 数据 as_of」；不得记录密钥；旧 `shadow.json`/`state.json` 字段不改
- **状态**：new（现有资产分散在 `shadow.json` 完整评审记录、`state.json` 摘要、`html_check.py` 机检；**无统一审计模块与图级 trace**）
- **代码**：`shadow.py:1109 save_record`、`pipeline.py:_save/_persist_review`、`skills/.../html_check.py`；图级 trace 待建
- **验收**：审计记录可重放（run→节点→参数→数据）；密钥扫描为空；哈希链校验；旧诊断字段 100% 兼容

### 37. `critic.evaluator` · 评估 Agent/合成目标/指标
- **类型**：critic
- **输入**：当日评审集合、`shadow.metrics`、采纳数据
- **输出**：参数议题聚类、合成目标向量、收敛/振荡判定、冻结/解冻建议
- **约束**：不以 |V−P| 为目标；议题只提议不裁决；权重变更需版本化；评估指标可复算
- **状态**：new（现有 `shadow.metrics` 只有过程指标，没有议题聚类/合成目标）
- **代码**：`shadow.py:1172 metrics`、`:1151 _consensus`；**无 evaluator**
- **验收**：合成目标四项可复算且不含价格项；振荡用例触发 freeze；人工采纳率与置信度校准对照

---

## 7. 入口/输出层

### 38. `entry.monitor` · 指数监控入口
- **类型**：entry
- **输入**：`index`、`as_of`、（可选）parallel/stat_n
- **输出**：`UniverseBatch`、`IndexQuote`、run 元数据
- **约束**：五指数白名单；成分 as_of 必须记录；全市场任务体积控制；失败拒绝启动而非半成品
- **状态**：existing（`pipeline.start/run_job` + `dsources.components/index_quote` 已实现）
- **代码**：`pipeline.py:86 start`、`:681 run_job`、`config.py:37–40`、`server.py` `/api/run`
- **验收**：五指数成分/权重/收盘与现有接口一致；旧 `/api/run` 零变化；任务 ID 兼容

### 39. `entry.ipo` · 单公司 IPO 入口
- **类型**：entry
- **输入**：`ipo_input.v1`（公司、申报期财务、锁定可比、发行条款、板块）
- **输出**：单行 `Company`/`FinancialsBatch`/`PeersBatch`/`Issuance`
- **约束**：必填校验；财务期不得晚于 as_of；deal 域隔离；缺条款拒绝，不补默认值
- **状态**：new（技能有单公司估值流程与 `examples/`，但**批跑无 IPO 入口**；需定义 schema）
- **代码**：`skills/.../assets/input_schema.json`（单公司输入）、`examples/`；`pipeline` 无 IPO 入口
- **验收**：schema 校验用例；deal 域写入隔离；IPO 图能端到端跑通最小样例；不写监测任务目录

### 40. `out.report` · 报告生成与机检
- **类型**：report
- **输入**：逐券结果、区间、指数汇总、评审记录
- **输出**：逐券 HTML、`summary.html`、`shadow.html`、机检结果
- **约束**：模板不改写估值逻辑；八项机检失败不阻断但标 `check_ok=false`；主题注入幂等；免责声明必含
- **状态**：existing（`report_generator.py`/`html_check.py`/`report_theme.py`/`apply_view.py` 已实现）
- **代码**：`skills/.../report_generator.py`、`html_check.py`、`packages/batch/report_theme.py`、`apply_view.py`
- **验收**：报告与现网逐项一致；机检通过；主题双模式；apply 区块正确

### 41. `out.compliance` · 定价约束/合规输出
- **类型**：report
- **输入**：`Valuation`、`Interval`、`Issuance`、`IpoConstraints`
- **输出**：`ComplianceBlock`（发行 PE/PS 偏离、募资/流通比、板块条件、免责声明、人工复核清单）
- **约束**：不输出单一建议发行价；不输出交易信号；偏离阈值按 `ipo_rules_checklist.md`；输出标「研究参考」
- **状态**：new（引擎 `ipo_check` 是单点检查，缺独立的合规输出模块与领域隔离）
- **代码**：`valuation_engine.py:4795 ipo_check`、`skills/.../assets/ipo_rules_checklist.md`
- **验收**：ipo.yaml `checks` 全过；禁用词/单点发行价检查；合规声明必含；人工复核清单可导出

---

## 8. 与现有实现的映射与缺口

**已有算法本体、可直接包装（28 个：existing 13 + wrap 15）**：`enc.financials/industry/lifecycle/cost_capital/peers/sentiment`、`val.dcf/comparable/sentiment/rim/ddm/nav/rnpv/sotp/quality_adjust/anchor_tx/industry_fallback`、`gate.layer0`、`comb.attention`（退化）、`pool.linear`、`unc.interval`（部分）、`idx.index_fit`（口径 A）、`critic.experts/main/shadow/apply`、`entry.monitor`、`out.report`。

**要新写（12 个）**：`enc.pit_quality`、`gate.quality`、`gate.ipo_eligibility`、`comb.residual`、`comb.norm`、`pool.log`、`pool.product`、`critic.ledger`、`critic.audit`、`critic.evaluator`、`entry.ipo`、`out.compliance`、以及 `val.comparable` 的 EV/EBITDA 子倍数（在既有模块内新增）。

**论文扩展**：`ens.dropout`（1 个独立模块），以及 `comb.attention` 的可学习 softmax 版本（既有模块内的研究子项，不计入状态统计；现有实现只到静态/退化注意力）。

**与技能包 8 模块拆分 TODO（`docs/spec/05-skill-package.md` §7）的关系**：本文的 42 个模块比技能拆分的 8 个更细（数据/财务、画像、可比池、DCF、可比法、舆情、合成、统计/报告）。映射：技能 1→`enc.financials`；2→`enc.industry`+`enc.lifecycle`+`gate.layer0`；3→`enc.peers`+`comb.attention`；4→`val.dcf`+`enc.cost_capital`；5→`val.comparable`+`val.quality_adjust`；6→`enc.sentiment`+`val.sentiment`；7→`pool.*`+`unc.interval`；8→`out.report`。技能拆分仍按「先接口、后实现」推进，不因本目录而提前重构单体技能。

**不在本目录里的东西**：`stat_validation.py` 的 MC/弹性算法归 `unc.interval` 的实现细节；`report_generator.py` 的 11 段内容归 `out.report`；数据源客户端（`dsources.py`/`fetch_data.py`）不是图节点，是 `enc.*` 的依赖；`pipeline._summary_html`、`_archive_reports` 属故事层，归 `out.report`。
