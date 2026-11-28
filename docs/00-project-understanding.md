# 00 · 项目理解

> 基线：`origin/main` `d06a5ed`（2026-11-27）；技能包 `skills/llm-ipo-valuation` v3.29.1（引擎实际输出 2.28.0）。  
> 本文是新成员、新会话的第一份上下文；实现细节见 [spec/](spec/)，论文视角见 [01-paper-proposal.md](01-paper-proposal.md)。

## 0. 一句话

**用估值替代价格**：逐只估算指数成分券，按指数权重合成“拟合点位”，与真实收盘并列、只展示差异——这是挂在 DSH 网页版上的估值跑批工作台（ValuationSystem）。

## 1. 业务问题与边界

- **来源**：上交所企业估值课题（陈映洲老师）。史老师先有一版独立实现；本项目是宋泊毅这条线在 DSH 上另做的一版，面向指数点位校验与 IPO 估值方法探索。
- **方法**：成分券 → 逐券估值（DCF / 可比 / 舆情三路加权，金融类走 RIM/DDM）→ 每股估值 → 按指数权重合成点位。
- **覆盖**：上证50、上证180、科创50、沪深300、上证综指（全市场，约 2,201 只沪市 A 股，总市值权重，剔除 ST 与未满计入期新股）。
- **边界**：自洽优先、不默认市场对；**差异只展示、不做反向校正**，不拿市场价反推估值；多 Agent 评审的评估口径不以“更贴近指数收盘”论对错。探索性研究，不构成投资建议。
- **已下线**：早期“陈老师 vs 石总”双模型对比卡已移除（`d2b39f0`），项目不再把第二套模型对比作为方向。

## 2. 系统全景

| 层 | 位置 | 职责 |
|---|---|---|
| 浏览器端 | `packages/workbench/`（`@valuation/workbench`） | DSH 客户端插件：估值跑批单页仪表盘 + 估值智能体面板 + 侧栏历史报告；认领上游 `ui-workbench` 面板 id，替换品牌 |
| 批跑服务 | `packages/batch/`（Python 标准库，3089） | 拉数据、逐券子进程、并行调度、状态落盘、汇总合成、报告存档、多 Agent 评审 |
| 估值技能 | `skills/llm-ipo-valuation/` | 陈老师技能包：七步工作流、估值引擎、统计校验、报告生成、八项机检；仓库内随包交付 |
| DSH 集成 | `profiles/valuation/`、`scripts/` | 独立 profile、独立 `DSH_HOME`、3081 Web 实例、3089 批跑服务、启停脚本 |
| 文档 | `docs/` | 理解、论文、工程路线、方法论、spec、HTML 宣讲页 |

运行时关系：

```text
浏览器 (3081, DSH Web)
   │  fetch  http://<host>:3089/api/*
   ▼
批跑服务 (3089, Python ThreadingHTTPServer)
   │  subprocess: python3 <skill>/scripts/*.py
   ▼
技能包 (valuation_engine / stat_validation / report_generator / html_check)
   │  读写 JSON / HTML
   ▼
runtime/jobs/<job_id>/  +  ~/.dsh-valuation/valuation-reports/<job_id>/
```

## 3. 一次跑批的链路

1. **提交**：前端 `POST /api/run`，带指数、并行度、抽样次数、三路权重、舆情轮数与口径、WACC/永续覆盖、`agent_mode`（off/shadow/apply）。
2. **成分与行情**：东财指数成分表（前一日收盘权重）或上证综指全市场快照；腾讯指数点位（当日/昨收，按成分时点选择）。
3. **输入组装**（逐券，`input_builder.py`）：年报营收/归母净利、一致预期、F10 三表年报驱动 FCFF、质量五指标、可比 β、5 家可比、行业估值基准、舆情（规则或 DeepSeek 语义）、可选个股覆写。
4. **引擎**：`valuation_engine.py` 输出综合中枢、区间、四部分（DCF/可比/舆情）、置信度、生命周期、净利口径、警告。
5. **多 Agent 评审**（可选）：三专家（可比质量 / 折现参数 / 舆情）提有界建议 → 主审 accept/clamp/reject；`shadow` 只留痕，`apply` 回写输入并重跑引擎（基线保留、失败回滚）。
6. **统计校验**：`stat_validation.py`，蒙特卡洛默认 3000 次、参数弹性、Spearman、稳健性；seed 固定。
7. **报告与机检**：`report_generator.py` 生成投行级 HTML → `html_check.py` 八项机检 → 注入终端风主题 → `apply` 模式追加“改前/改后”可视化。
8. **合成与存档**：汇总拟合点位与三情景点位，写 `summary.html` / `shadow.html`，复制到报告存档目录；前端轮询任务状态并展示。

失败券（数据缺失、引擎失败、无有效估值）标记 `skip` 并留痕，不阻断整批；跳过券不计入合成分子分母。服务重启时，磁盘上遗留的 `running` 任务会被标记为中断。

## 4. 核心公式与口径

**拟合点位（指数加权，当前主口径）**

```text
V_index = P_index × Σ_i w_i × (V_i / P_i) / Σ_i w_i
```

- `V_i`：单券估值中枢/股（引擎综合中枢 ÷ 总股本）；`P_i`：收盘价；`w_i`：当日指数权重；仅计入 `ok` 且有正权重的券。
- 另有价格加权口径 `P_index × Σ(w_i V_i) / Σ(w_i P_i)` 保留在 `summary` 作对照，但不再作为主口径。

**三情景点位**

```text
low  = P_index × Σ w_i × (interval_low_i / shares_i) / P_i / Σ w_i
high = P_index × Σ w_i × (interval_high_i / shares_i) / P_i / Σ w_i
base = fitted
```

**权重口径**

- 上证50/180、科创50、沪深300：东财成分表前一日收盘权重；若表内无权重，用自由流通市值归一化并在前端标注 `weight_computed`。
- 上证综指：全市场快照，总市值权重；剔除 ST/*ST；新股上市满一年计入，总市值前 10 名满三个月计入。编制口径的单样本 15% 上限当前未显式截断（样本远低于上限，需在正式口径中核实）。
- 指数权重与个股市值的关系：权重因子 × 当日市值 → 归一化当日权重；当前实现直接用成分表权重，尚未做“权重因子 × 当日市值”的逐日重算（路线见 [03](03-engineering-roadmap.md)）。

**差异口径**

```text
diff = V_i / P_i − 1
```

只展示估值与现价的偏离，不反向校正。估值/价 ≥5× 或 ≤0.2× 标“极端偏离”，并在汇总、报告、UI 三处一致展示；极端偏离会给出对拟合偏离的贡献（pp），但不改变估值、权重或点位。

## 5. 多 Agent 评审

| 角色 | 权限 | 证据域 | 可提参数 |
|---|---|---|---|
| 可比质量 | 只审可比证据链 | 样本量、覆盖率、规模倍数、倍数质量、会计可比 | `comp_weight_pp` |
| 折现参数 | 只审折现假设 | β 来源、CAPM、生命周期、增长三角、现金流质量 | `wacc_pp` / `tg_pp` |
| 舆情 | 只审舆情证据 | 口径、标签与幅度、证据条数与方向 | `sent_weight_pp` |
| 主审 | 独立复核、夹断、驳回 | 全部证据 + 专家建议 | 不新增参数 |

- **门槛**：置信度 ≥ 0.65（可按批配置）、证据须引用具体数字、severity 与幅度匹配、方向自洽；未过门槛只留痕。
- **幅度上限**（默认）：可比 5/8/10pp（中/高/严重）、舆情 5/10pp、WACC 0.4/1.0pp、永续 0.2/0.6pp；权重参数 5pp 整数倍，WACC/永续 0.2pp 整数倍。
- **模式**：`off` 关闭；`shadow` 建议只记录、不改引擎参数；`apply` 主审通过项写回输入并重跑引擎，保留 `*.input.baseline.json` / `*.out.baseline.json`，失败自动回滚。
- **配置**：`~/.dsh-valuation/agents.json` 是唯一配置源，保存时严格校验、版本号自增；每批开始时快照写入 `state.json`，运行中的任务不受后续保存影响。
- **评估**：只看建议离散度（中位/IQR）、置信度校准、周环比参数稳定性、人工采纳率；不看“是否更贴近指数收盘”。人工采纳通过 `/api/shadow/adopt` 标记，写入逐券 shadow 记录。

## 6. 数据源

| 数据 | 来源 | 缓存 |
|---|---|---|
| 指数成分/权重 | 东财 `RPT_INDEX_TS_COMPONENT`；上证综指走 `RPT_VALUEANALYSIS_DET` 全市场快照 | 6 小时 |
| 行情/指数点位 | 腾讯 `qt.gtimg.cn` | 5 分钟 |
| 财报/一致预期 | 东财 datacenter（技能 `fetch_data.py`）+ F10 三表 | 7 天 |
| 可比池 | 东财多类指数成分并集，按自由流通市值去重 | 24 小时 |
| 行业估值 | 东财 `RPT_VALUEINDUSTRY_DET`（申万二级整体法） | 24 小时 |
| 舆情 | 东财新闻搜索 + 股吧；规则词频或 DeepSeek 语义 | 6 小时 |
| β | 腾讯月线 60 个月 OLS，基准沪深300 | 24 小时 |

无密钥依赖（LLM 舆情/评审除外）；LLM 密钥只从仓库外读取：`~/.dsh-valuation/sentiment-llm.env` 的 `DEEPSEEK_API_KEY`。个股级人工覆写在 `~/.dsh-valuation/overrides/<code>.json`，只允许注入 rNPV / preferences / framework_check，不改行情财务。

## 7. 仓库结构

```text
ipo-valuation-index/
├── packages/
│   ├── workbench/          # DSH 客户端插件（React + CSS Modules + esbuild）
│   └── batch/              # Python 批跑服务与多 Agent 评审
├── skills/
│   └── llm-ipo-valuation/  # 估值技能包（SKILL.md / methodology / assets / scripts / examples）
├── profiles/valuation/     # DSH profile（bundles、patch、预设）
├── scripts/                # 启停脚本
├── docs/                   # 本文档中心（md + html + spec + LaTeX）
├── README.md
└── pnpm-workspace.yaml
```

技能包已入库（`skills/`），批跑 `config.py` 默认优先仓库内技能，`VALUATION_SKILL_DIR` 可覆盖；外部部署路径仍作兜底。

## 8. 当前能力（d06a5ed）

- **界面**：单页仪表盘（六步锚点导航）、五指数瓦片 × 三情景点位、拟合点位大数字与情景区间带、逐券差异分布/方向环图、逐券结果卡、历史跑批、侧栏报告树、`apply` 改前/改后对比、历史列表“回/影”标记、跨页进度接管。
- **第二个面板**：估值智能体——三专家 + 主审的角色卡、置信门槛、幅度上限、模型/并发/超时配置，保存后下一批生效；可只读查看实际提示词。
- **批跑**：五指数、上证综指全市场、服务重启 reconcile、`apply_view`、行业基准兜底、rNPV 个股覆写、PS 5×/10× 弃用护栏、缓存写竞态修复。
- **可观测**：`state.json` 逐券状态、`shadow.json` 完整评审、`summary.html` / `shadow.html`、`*.report.html` + 八项机检。
- **技能回归**：`smoke_test.py` 2026-11-28 实跑 170 用例全绿（3.9s），引擎输出 `engine_version=2.28.0`。

## 9. 已知差距与风险

1. **技能版本差**：仓库内技能 v3.29.1，批跑层已按 v3.31.0 护栏（行业兜底、PS 弃用、rNPV 等）适配；技能包的 `industry_fallback` 等输出字段在当前版本不存在，需以回归测试确认数值口径。
2. **估值日期未真正生效**：前端日期只作为“参考”展示，`/api/run` 不接收日期；批跑固定使用成分数据时点（前一日/快照日）。这是六步流程里唯一未闭环的一步。
3. **定时任务未接调度器**：周频自动跑仍为规划。
4. **硬编码路径**：`workspace_ensure.ts` 仍写死 `/Users/boyisong/...`；部署到新机器需改。`config.py` 的主体路径已改为仓库内优先。
5. **无仓库级测试/CI**：验证依赖技能 `smoke_test.py`、`html_check.py` 与人工跑批；改动缺少自动回归门禁。
6. **数据源脆弱**：东财/腾讯公开接口无 SLA，字段与限频可能变；全市场 2,201 只跑批的时长与内存需实测。
7. **LLM 随机性**：评审用 DeepSeek，temperature 0.1 但无 seed；重复运行的建议分布未量化，论文实验需报告方差。
8. **报告与配置在仓库外**：`~/.dsh-valuation`、`runtime/` 不随仓库迁移；换机需同步。
9. **循环论证风险**：专家证据与引擎输入同源，主审缺独立证据；论文与产品都需要盲评/外部证据设计。

## 10. 文档地图

- 论文：为什么这样建模、贡献与实验 → [01-paper-proposal.md](01-paper-proposal.md) / [四张学术海报](posters/README.md)
- 工程：下一步怎么改 → [03-engineering-roadmap.md](03-engineering-roadmap.md)
- 技能：方法论与拆分 → [04-skill-methodology.md](04-skill-methodology.md)
- 决策：本轮定了什么 → [05-decision-log.md](05-decision-log.md)
- 接口：架构/模型/评审/数据/技能 → [spec/](spec/)

## 11. 快速上手（本机）

```bash
# 1) 起 Web（3081）——需要 DSH 运行时，见 .runtime/bin/start-valuation.sh
bash ../.runtime/bin/start-valuation.sh

# 2) 起批跑（3089）——技能已在仓库内，无需外部安装
cd packages/batch && python3 server.py

# 3) 健康检查
curl -s http://127.0.0.1:3089/api/health

# 4) 重新构建前端插件（改 client 代码后）
cd packages/workbench && node build.mjs
```

端口、profile、`DSH_HOME` 的隔离说明见 [spec/01-architecture.md](spec/01-architecture.md)。
