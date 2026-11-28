# Spec 02 · 估值模型与口径

> 目标：把“输入什么、走哪条方法路由、怎么合成、怎么给区间/置信度”写成可核对的契约。  
> 事实基线：技能 v3.29.1 / 引擎 v2.27.1；批跑层 `d06a5ed` 已按 v3.31.0 护栏做输入适配（差异见 [05](05-skill-package.md)）。

## 1. 逐券输入（`input_builder.py` 产出）

| 顶层字段 | 内容 | 说明 |
|---|---|---|
| `meta` | 公司、代码、行业、交易所、as_of、一句话输入、市值、会计准则、`framework_check` | `framework_check.industry_class` 决定 Layer 0 路由 |
| `financials` | 营收/净利（年报口径）、净利构成、净利率、ROE、现金流、股本、亏损标记、质量五指标、`wacc_params` | 金额亿元、比率小数、股本亿股 |
| `comparables` | 5 家可比：市值、净利、营收、PE、PS、增速、报告期、口径备注 | 同行业优先，细行业不足回退前缀/粗板块；无则不跳过 |
| `sentiment` | `company_news_sentiment`、`sentiment_adjustment_pct`、证据 | 规则词频或 LLM 语义，±5% 内 |
| `preferences` | 三路权重、情景权重、离群、生命周期模式、Layer 0、方法集、PEG 开关 | 权重默认 30/50/20 |
| `dcf_cost` | 方法弃用再归一、WACC/ERP 自动模式、FCF 比率 | `method_drop_mode=renormalize` |
| `dcf_drivers` | 报表驱动 FCFF：营收、EBIT率、D&A率、Capex率、NWC率、税率、基期 FCFF、历史 | 非金融且三表齐全时启用 |
| `peer_screening` | 长名单、剔除台账、规模倍数、覆盖率、median | 诊断模式，不改估值数值 |
| `industry_index` | 申万二级 PE/PS/PB 中位（整体法） | 行业基准兜底候选 |
| `rim` / `ddm` | 金融路由：B0、ROE、Ke、分红率、永续 | 仅金融关键词命中 |
| `rnpv` | 管线药企参数（个股覆写注入） | 覆写白名单 |
| `data_sources` | 数据溯源条目 | 报告“数据溯源表”来源 |

单位与口径：最近年报营收/归母净利（与净利披露档 annual 一致，9M 累计不混入 TTM）；WACC/永续默认由引擎 `capm_auto` + 行业底座解析，工作台覆盖时以小数写入 `financials.wacc` / `terminal_growth` 并优先。

## 2. 方法路由（Layer 0）

```text
行业关键词（银行/保险/证券/券商/金融）
  └─ financial：interest_is_operating=true, regulated_capital=true
       └─ RIM 主方法 + 可比交叉；DDM 分红口径校验（权重 0）
非金融
  ├─ 管线药企（pipeline_pharma）→ rNPV 主 + 可比
  ├─ 多分部（multi_segment）→ SOTP + 可比
  ├─ 资源/公用（NAV 可用）→ NAV 路由（当前工作台未接 NAV 数据）
  └─ general → DCF + 可比 + 舆情；Layer 0 A/B 门
```

- **A/B 门（general）**：A2 负 FCFF 占比 >60% → `negative_fcff`，DCF 权重封顶 0.3；当前基础权重 0.3 时数值不变，但会阻断后续上调。
- **方法候选集**：`dcf`、`comparable`、`sentiment`、`rim`、`ddm`、`nav`、`rnpv`、`sotp`；未选中/不可计算的方法不产生数值，剩余方法按 `method_drop_mode=renormalize` 再归一，避免综合值静默缩水。
- **金融**：WACC 参数面实为股权成本 Ke；β 用行业 β 0.90（银行）或可比 β 再杠杆；ROE 取近 3 年年均，B0 取归母普通股权益。
- **可比缺失**：不跳过；引擎剔除可比法、置信度降档；产品层再下调一档并标注“无可比，已剔除可比法”。

## 3. 生命周期与增长

六阶段（达莫达兰）：初创 `startup`、年轻成长 `young_growth`、高速成长 `high_growth`、成熟成长 `mature_growth`、成熟稳定 `mature_stable`、衰退 `decline`。

- **方法定位表（v3.28）**：六行表直接给出各阶段三路径权重（行内和为 1，不乘 base、不再归一），替代旧 `k_lifecycle` 乘数；base 权重为 0 的方法视为用户显式禁用，表不得复活；Layer 0 否决同样记入 `blocked_paths`。
- **判定顺序（v3.29.1）**：结构证据优先于盈利符号；“亏损 + 营收 ≥5 亿”不再先于 `decline`；增速 <8% 仍判 young_growth 时挂复核提示。
- **增长函数（v3.29）**：

```text
g_t = tg + (g1 − tg) · E(t)
E(1)=1, E(n)=0
E(t) ∈ { logistic_cap（真 S 曲线）, geometric, mean_revert, linear }
```

六档显式期 n = 10/10/8/7/6/4；CAP 拐点 6/5/4/3；`growth_shape_mode` 缺省 legacy，opt-in 后零回归。旧实现 `forced` 尾段插值会把 S 曲线静默退化为线性，v3.29 用“缺口归一化”消除该补丁。

## 4. 合成

单券综合中枢：

```text
V_i = Σ_m w_m · V_{i,m} / Σ_m w_m        （仅可用方法；w 以 preferences/方法表为准）
```

- 四部分拆分：`part1_dcf`、`part2_comparable_quality`、`part3_market_sentiment`（+ 统计检验），报告与 UI 可下钻。
- 三路默认权重 30/50/20，可由工作台调整（必须合计 100%）。
- PEG 只单列，不并入可比合成均值；非正倍数剔除；PEG 隐含值超市值 2.5× 时展示护栏。
- 金融类 DCF 权重 0，候选集 RIM + 可比；RIM 不可用时按剩余权重再归一。

**区间/情景**：引擎给出逐券情景区间（bear/base/bull）与统计校验 MC 区间；产品层取“情景区间 ∩ MC 90%”作为报告区间口径。前端情景区间带与三情景点位由逐券区间按指数权重合成，不再由前端估算。

**指数点位**：

```text
V_index = P_index × Σ_i w_i × (V_i / P_i) / Σ_i w_i
```

- `w_i`：指数权重；`P_i`：收盘价；仅 `ok` 且权重/价格为正的券。
- 价格加权对照：`P_index × Σ(w_i V_i) / Σ(w_i P_i)`，只存 summary，不主展示。
- 跳过券不计入分子分母；极端偏离（V/P ≥5× 或 ≤0.2×）只标识并给出贡献 pp，不改点位。

## 5. 置信度与兜底

- 引擎给 `confidence.level`（高/中/低）与构成；产品层在“无可比”时降一档，在“可比 <3 家”时标注。
- **行业基准兜底（v3.31 护栏）**：可比与 DCF 均无效、区间为 0 时，用申万二级行业基准给单点，置信度强制“低”，口径写“行业基准兜底（单点参照）”；净资产兜底只走 `financials.net_assets_fallback`，不进入常规 PB/NAV。
- **PS 护栏**：PS 隐含值超市值 5×/10× 且利润率不匹配时整法弃用。
- **个股覆写**：`~/.dsh-valuation/overrides/<code>.json` 只允许 `rnpv`、`preferences.enable_rnpv/method_set_mode/layer0_check`、`framework_check.industry_class`；不改行情/财务，覆写来源写入 `data_sources`。

## 6. 统计校验

`stat_validation.py`：

- 蒙特卡洛 3000 次联合抽样（默认，工作台可调 200–10000），seed 42；
- 参数弹性（±1σ + OLS）；
- Spearman 秩相关；
- 稳健性：3 种权重方案 + 可比极端剔除；
- 输出中位数、区间、弹性、警告；与点估计差异过大时报告提示。

## 7. 报告与机检

- `report_generator.py`：投行级 11 段（摘要、公司/行业、方法适用性、DCF、可比、舆情、融资估值、情景、敏感性、结论、数据溯源），方法适用性与局限性表、数据溯源表。
- `html_check.py`：八项机检（结构、必需章节、数字一致性、占位符、空表、单位、链接、免责声明等）；失败写 `check_ok=false`，不阻断跑批。
- `report_theme.py`：统一终端风字号/发丝线/琥珀强调/双主题，幂等注入；服务端读取时刷新存量报告。
- `apply_view.py`：apply 有回写时，在报告首个 `<h2>` 前插入“生效回写 · 改前/改后”区块（KPI、参数改动、四部分估值条）。

## 8. 口径红线

1. 差异只展示，不反向校正；不把估值改成现价，也不把现价改成估值。
2. 不以“贴近指数收盘”作为模型优化目标；市场对照只作诊断。
3. 估值日期当前只是参考，批跑使用成分数据时点；若未来接入日期，需保证价格、财务、权重全部 PIT。
4. 任何“兜底/降档/弃用”必须在报告与 UI 显性标注，不静默处理。
5. 版本升级必须做数值零回归（examples + smoke），否则视为破坏性变更。

## 9. 待统一/待核实

| 项 | 现状 | 待办 |
|---|---|---|
| 技能版本 | v3.29.1 vs 批跑 v3.31 护栏 | 以回归测试确认字段与数值 |
| 权重日更 | 直接用成分表权重 | 指数权重因子 × 当日市值重算（路线） |
| 估值日期 | 仅参考 | PIT 数据 + API 透传 |
| 三池合成 | 仅线性池 | 对数池/专家乘积（路线第五层） |
| 模糊表达 | MC 区间 + 情景 | fuzzy/α-cut 形式化（论文） |
