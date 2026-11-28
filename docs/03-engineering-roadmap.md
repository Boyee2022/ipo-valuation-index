# 工程改进路线：从逐券 pipeline 到分层向量化估值

> **状态**：规划文件，不含任何代码改动 · **基线**：`origin/main` @ `d06a5ed`（2026-11-28） · **技能包**：`skills/llm-ipo-valuation`（SKILL.md 变更记录口径 v3.29.1，引擎 v2.28.0）
> **一句话**：现在跑一批指数 = 对每只券各跑一次完整流水线；目标是把「方法」从「券」里抽出来，一层对全部企业统一算完，再进入下一层。

---

## 1. 现状基线（`d06a5ed`）

### 1.1 一条券是怎么跑完的

`packages/batch/pipeline.py` 的 `_worker()` 是唯一的执行单元。一只券进 worker 后顺序做五件事：

1. `input_builder.build_input()` 在本进程组装输入（财务、可比、β、舆情、Layer 0 门、覆写），落 `<code>.input.json`；
2. 起子进程调用技能包 `valuation_engine.py`（超时 600s），得到 `<code>.out.json`；
3. 若 `agent_mode ∈ {shadow, apply}`，跑「三专家 + 主审」评审（每券 4 次 LLM 调用，信号量默认 6）；apply 把通过项写回输入、备份 `*.baseline.json`、重跑引擎，失败回滚基线；
4. 起子进程跑 `stat_validation.py`（3000 次 MC、seed 42，超时 1200s）→ `<code>.stat.json`；
5. 起子进程跑 `report_generator.py`（600s）→ `<code>.report.html`，再跑 `html_check.py`（300s）八项机检，最后注入主题。

也就是说：**一只券 = 4 次子进程 + 1 次进程内组装**。50 只券是 200 次进程启动；上证综指全市场约 **2,201 只**券时，是 8,800 次量级的进程启动与 JSON 往返。

并行只发生在最外层：`ThreadPoolExecutor(max_workers=parallel)`（`pipeline.py:715`），`parallel` 由服务端限制为 3 或 10（`server.py:208–210`）。批跑服务本身是**单进程 `ThreadingHTTPServer`**（`server.py:275`），所有任务的线程共享一个进程——内存峰值就是进程 RSS，没有多进程隔离可用。券与券之间没有共享的中间状态，只共享进程内的只读 TTL 缓存。

### 1.2 已有能力与局限

| 维度 | 已有能力（证据） | 局限 |
|---|---|---|
| 执行单元 | 券级 worker + 线程池，`parallel ∈ {3,10}`（`pipeline.py:715`）；单进程 `ThreadingHTTPServer`（`server.py:275`） | 没有「层」；方法在券内串行；单进程内存峰值 = 进程 RSS，无法多进程分摊 |
| 单券流水线 | 输入组装 → 引擎 → 评审 → 统计 → 报告 → 机检，四脚本均为子进程（`pipeline.py:50–54`、`282–293`） | 每券重复进程启动 + 全量 JSON 序列化；引擎只接受单文档输入，无批量入口 |
| 任务状态 | `runtime/jobs/<id>/state.json`；`total > 800` 时每 10 行落盘（`pipeline.py:76–83`）；重启后 `running` → `error` | 全量重写、无逐层产物、无逐券计时；中断后只能整批重跑 |
| 数据层 | 进程内 TTL 缓存：成分 6h / 可比全集 24h / 财报 7d / 行情 300s（`dsources.py:22–25`）；原子 `replace` 写入，临时名带 pid+线程号 | 缓存无数据时点（PIT）与任务级 manifest；并行 worker 会重复回填同一 key |
| 可比池 | 全指数成分并集 + 本次成分并入；同行业 → 前缀 → 粗板块三级回退；自由流通市值对数距离取前 5 | 池子每次跑批现拼；行业分位/长名单每券重算 |
| 评审 | 三专家 + 主审，shadow / apply 两档；apply 写回输入并重跑，失败回滚 baseline（`shadow.py:944`） | 配置只保留当前一版，版本号自增、**不做跨批参数台账**（`agent_config.py:6`）；没有「次日用前一天通过参数」这条路 |
| 指数 | 五指数（`config.py:37–40`）：上证50 / 上证180 / 科创50 / 沪深300 走东财成分表（官方 `WEIGHT`，缺 `WEIGHT` 时按自由流通市值归一，如 上证180）；上证综指走全 A 估值快照，约 2,201 只，**总市值加权**、剔除 ST/*ST 与未满计入期新股（`dsources.py:95–170`） | 权重口径三套（官方 / 自由流通市值 / 总市值）；指数层没有独立拟合模块 |
| 点位 | 拟合点位 = 指数收盘 × Σw(V/P)/Σw（指数加权，V=每股估值）；三情景点位由逐券区间端点按同一权重合成，再与拟合点位取 min/max（`pipeline.py:187–211`） | 情景不同源（区间端点 vs 中枢）；无指数层偏差分解与交叉校验；README 六步流程里的「权重因子×当日市值→归一化当日权重」**尚未实现**，现用成分表自带权重 |
| 报告 | 逐券 `report.html` + `summary.html` + `shadow.html`，归档到 `~/.dsh-valuation/valuation-reports` | 报告与工作台两套展示；方法树与参数来源只有文本块 |
| 技能包 | `SKILL.md` 1208 行 + `methodology.md` 756 行 + 10 脚本 + 11 组输入/9 组输出；纯标准库 | 单体未拆分；版本标记三处不一致（§6.7） |

### 1.3 本轮已完成、作为 M0 基线的事实

- 技能包已入库 `skills/llm-ipo-valuation/`（不再只存在于 `~/.dsh-valuation/agents/skills/`），随仓库版本化；
- `config.py` 技能目录改为「**仓库内优先 + `VALUATION_SKILL_DIR` 覆盖 + 旧部署路径兜底**」（`config.py:22–27`）；
- 前端已移除「陈老师 vs 石总」双模型对比，`data.ts` 只保留价格与中枢；
- 文档中心 `docs/` 建立，与工作台同一套视觉语言；
- 仍缺：`runtime/` 不入库、无历史跑批产物，性能基线（单券耗时、内存峰值）**待测**。

**基线判断**：现在这套东西「能跑完、能留痕、能单券回滚」，但**「层」不存在**——所有方法都在每券内部串行，跨券只共享只读缓存；因此无法做跨券的批量计算、跨券的分位、跨券的情景一致性，也无法把「今天的评审结论」变成「明天的默认参数」。

---

## 2. 目标架构

### 2.1 三层抽离

把混在 `pipeline.py` 里的职责拆成三层，层间只通过数据契约通信：

- **故事层（Story）**：指数、点位、情景、报告、工作台。只消费聚合产物，**不碰单券数值**。
- **模型层（Model）**：数据装配 + 方法核 + 合成核。输入宽表，输出「每券 × 每方法」的值、区间、诊断与掩码。
- **Agent 层（Agent）**：评审、适用性判定、参数台账、池子选择。**只读写接口与参数，不直接改数值。**

### 2.2 文字版架构图

```
故事层  narrative/
        index_fit(五指数聚合·三情景) · report(逐券/汇总) · workbench(插件页面)
           ▲ 只读聚合产物
           │
模型层  model/
        universe.build ──► X(N×F) + M0(N) + meta(as_of, hash)
             │
        kernels{dcf, rim, ddm, nav, rel}   ← 基础层，一次算 N 只
             │
        sidecar{sentiment, rnpv, override, review}  ← 非基础层，逐券异步
             │
        pool.combine(V, M, W, mode)  ──► V*, interval, pool_choice
           ▲ 方法产物 + 诊断
           │
Agent 层 agent/
        review(三专家+主审) · evaluate(适用/不适用) · ledger(参数版本) · gate(池子裁决)
```

### 2.3 层 → 模块 → 接口

| 层 | 模块 | 接口（输入 → 输出） | 现状对应 |
|---|---|---|---|
| 模型 | `universe.build(as_of, index)` | `index` → `(X, M0, meta)` 宽表 | `input_builder.build_input` |
| 模型 | `kernels.<method>(X, θ)` | 宽表 → `(V∈R^N, M∈{0,1}^N, diag)` | 引擎单券方法 |
| 模型 | `pool.combine(V, M, W, mode)` | 方法矩阵 → `(V*, interval, why)` | 引擎 `synthesis` |
| 模型 | `index_fit.aggregate(rows, weights)` | 行级结果 → 点位 / 三情景 / 偏差分解 | `pipeline._finalize` |
| Agent | `review.review(inp, eng, cfg)` | 单券输入输出 → 评审记录 | `shadow.review` |
| Agent | `evaluate.judge(recs, ledger)` | 当日评审集合 → 议题与裁决 | 无 |
| Agent | `ledger.commit(verdicts)` | 裁决 → `params_v{n+1}` | `agent_config.save`（仅当前版） |
| 故事 | `report.*` / 插件 | 聚合产物 → HTML / 页面 | `summary.html` + `Results.tsx` |

### 2.4 与 DSH 插件、批跑服务、技能包的关系

- **DSH 插件（`@valuation/workbench`）** 是故事层前端壳。现在直调 `:3089` 并自行推导展示逻辑；改造后读 `GET /api/jobs/<id>/models/<code>`，不再自行算口径。
- **批跑服务（`server.py`，3089）** 保留为唯一执行入口与状态源，新增 `/api/layers`（层产物清单）与 `/api/params/ledger`（参数版本）两组路由。向量化计算留在服务进程内或受控子进程里，前端不感知实现方式。
- **技能包** 仍是被调用的「方法字典」。M1 前让引擎以**函数**形式被 import（而非 subprocess + 文件），M2 起输出结构化诊断；技能拆分是 M4 之后的独立事项，不在本路线承诺内。

---

## 3. 五层改进逐条展开

### 3.1 第一层：建模流程的解耦与向量化

**问题.** 一只券跑完整 pipeline：DCF 算完才算可比，可比算完才算舆情，同一批券的同一方法被重复调度 50–2,201 次；跨券信息（行业分位、可比名单）只能每券重算；并行只能靠线程池堆进程。这不是「慢一点」，而是**结构上做不到「一层对所有企业统一处理」**。

**方案.** 按「是否依赖非客观数据」切成两类：

- **(a) 基础层（客观数据）**：DCF、RIM、DDM、NAV、相对估值（PE/PS/PB/PEG）。只依赖财务/行情/行业/参数，抽成纯函数 `f_m(X; θ_m)`，对全部企业一次性计算。方法之间用**层间 barrier**：所有企业的 DCF 和 RIM 都完成，才进入可比（因为可比需要全市场的行业分位与邻接）。
- **(b) 非基础层（非客观数据）**：舆情打分（规则或 LLM）、rNPV 人工管线、个股级覆写、LLM 评审。每券语义不同、可重试、可跳过，**逐券单独调度**，结果作为 sidecar 与基础层 join，不设 barrier。

**数学表达.** 记 N 为本次样本券数，F 为特征列数：

```
X ∈ R^{N×F}        财务块 | 行情块 | 行业块 | 政策块（WACC / 永续增速 / 方法权重）
V_m = f_m(X; θ_m) ∈ R^N        第 m 个方法对全部企业一次算完
M_m ∈ {0,1}^N                  有效性掩码（数据缺失 / 路由否决 / 越界）
```

DCF 是逐券显式期长度不同的求和，用「填充到 T_max + 掩码」表达：

```
V_dcf,i = Σ_{t=1..T_i} FCFF_{i,t} / (1+r_i)^t  +  TV_i / (1+r_i)^{T_i}
         （t ≤ T_i 的项才计入；T_i 由生命周期阶段给出）
```

可比法不是矩阵乘，而是「一次批量 gather + 行内中位数」：

```
Â[i,j] = 1  当 j ∈ P_i（同行业 + 自由流通市值对数距离 top-5）
V_comp,i = median_{j∈P_i}(multiple_j) × metric_i
```

合成（三方法 + 掩码 + 重归一），这是把现在引擎里的 `renormalize` 语义写成矩阵：

```
W ∈ R^{N×3}, M ∈ {0,1}^{N×3}
V* = ((W ⊙ M) · V_methods) / ((W ⊙ M) · 1)
```

**伪代码.**

```python
X, M0, meta = universe.build(as_of, index)        # 一次装配，宽表 + 有效性 + manifest
V, M, D = {}, {}, {}
for m in ("dcf", "rim", "ddm", "nav", "rel"):      # 基础层：层内按方法，层间 barrier
    V[m], M[m], D[m] = KERNEL[m](X, THETA)         # 一次算 N 只，返回掩码与诊断
    store_layer(job, "base", m, V[m], M[m], D[m])  # 层产物
side = schedule_per_stock(X, M0)                   # 逐券异步，可重试
V["sent"], M["sent"] = join_sidecar(side, key="secucode")
Vstar, interval, why = pool.combine(V, M, W, mode=POOL)   # 第三/五层
rows = merge_rows(V, M, D, side)                   # 行产物
```

**数据布局.** 一张宽表 `universe.<as_of>.jsonl` + 列块元数据（列名、单位、来源、as_of）。N=2,201、F≈60 时纯数值约 1.1MB 量级；内存主项是 MC：若把 3000 次抽样批量化，`chunk × 3000` 的中间数组按 chunk（建议 200 只）切片，数十 MB 级，**待实测**。

**接口与中间产物.** 产物分三级：层产物 `layer_outputs/<method>.json`、行产物 `rows/<code>.json`、任务级 `manifest.json`（as_of、代码版本、参数 hash、行数、跳过清单、每层耗时）；缓存键 =「资源名 + as_of + 参数 hash」；`state.json` 只存索引与摘要。

**内存与失败隔离.** 行级掩码 + 行级 `error`：单券异常只置 `M_m,i = 0`，不 abort 整批；整层异常则整层 `skip` 并降级 legacy。监控项：峰值 RSS、chunk 数、单 chunk 耗时。

**任务编排：混合调度.** 基础层内允许 chunk 流水（chunk 间可并行，chunk 内方法有序）；层间必须 barrier（可比要全市场分位，指数聚合要全部方法值）。非基础层**不设 barrier**，与基础层并行后 join——LLM 分钟级、基础层秒级，串行会白等。

**但非基础层不能矩阵化，必须逐券 + 限流。** 舆情 1 次 + 评审 4 次 LLM 调用/券，默认并发 6（`shadow.py:61`、`agent_config.concurrency` 1–12），2,201 只券在单进程里不可能全量跑。可行组合：

- 舆情：全市场走规则打分（零成本），LLM 只在抽样券上做口径对照；
- 评审：按「权重 top-N + 置信度低 + 极端偏离（估值/价 ≥5× 或 ≤0.2×）」分层抽样，抽样比例可配；
- 限流：沿用现有信号量，不新增并发层；失败按券重试 1 次后记 `error`，不阻断整批。

**断点续跑与 `runtime/jobs` 兼容.** 现有语义已具备续跑基础：行级 `status` 随 `state.json` 落盘（`>800` 行每 10 行一次），`reconcile_running` 把遗留 `running` 标成 `error`。改造只增不改：

- 目录结构在原任务目录内**只增** `layer_outputs/`、`rows/`、`manifest.json`，与现有 `<code>.input.json` / `.out.json` 等同目录共存；
- 层产物按 `(as_of, method, params_hash)` 幂等，中断后从最后一个完整 chunk 继续，不重跑已完成层；
- `reconcile_running` 保留，新增 `resume_from` 标记（最后完成的 chunk / 层），前端显示「可续跑」；
- 旧任务没有 manifest 时按 legacy 解释，新代码必须能读旧 `state.json`；legacy 模式下不产生任何新文件。

**与现有逐券线程池的差异.**

| 维度 | 现状 | 目标 |
|---|---|---|
| 执行单元 | 券（1 券 4 子进程） | 方法（1 方法 1 批） |
| 跨券信息 | 每券内重算 | 一次算完全市场分位/邻接 |
| 进程模型 | 线程池 + subprocess | 进程内 kernel，chunk 级可选子进程 |
| 并行来源 | `parallel=3/10` | 数组化 + chunk 并行 |
| 失败粒度 | 券级 skip | 方法 × 券的单元格 |
| 中间产物 | 每券 input/out/stat/report | 层产物 + 行产物 + manifest |
| 回滚 | `*.baseline.json` | `pipeline_mode` 开关 + 按 job 隔离 |

**迁移步骤（每步可独立回滚）.**

1. **冻结基线**：11 组 `examples` + 170 个用例输出快照 + hash；
2. **抽 kernel**：单券方法改成可 import 的纯函数，先单券调用，数值逐位相同（只移位置，不改算法）；
3. **加宽表**：`universe` 与 `input_builder` 解耦，输出 `(X, M0, 行元数据)`；
4. **dual 模式**：同一 as_of、同一参数下同时跑 legacy 与 vector，逐券 diff；
5. **切换默认**：vector 为默认，legacy 保留一个季度。

**验收标准.** 同 as_of、同参数下覆盖率与跳过率与 legacy 逐券一致；11 组 examples + 170 个用例数值零回归（逐位或 |Δ| ≤ 1e-9）；单券耗时中位 ↓≥30%（**待测**，现无逐券计时）；内存峰值 ≤1.5× 基线（**待测**）；四类故障注入只掩码目标券；**杀进程重启可续跑**，已完成 chunk 不重算；旧 `runtime/jobs` 任务仍可查看。

**风险.** 零回归是最大风险；向量化把「分支」变「掩码」，生命周期路由、Layer 0 否决、夹断最易漏；内存放大；调试可读性下降。

**依赖.** 引擎可 import；是否引入 numpy（决策点 1）；宽表 as_of 一致性（§6.6）。

### 3.2 第二层：建模表达与可视化

**问题.** 工作台能看到：中枢、区间、置信度一句备注、`basis`、四部分里的三项、前 6 条 warning、评审摘要。**看不到**：为什么选这个方法（Layer 0 路由、生命周期在引擎内部）、参数从哪来、可比剔除台账、`stat.json` 的 ±1σ 弹性与 MC 分位、两批之间哪个参数变了。

**方案.** 每券产出「模型履历」`model_trace.json`，四个区块：

- **方法树**：Layer 0 类别 → 候选方法集 → 选中/否决及理由（`blocked_paths`）→ 各方法值与权重；
- **参数溯源**：`{name, value, unit, source_type ∈ data|industry_base|override|agent_apply|skill_default, ref, as_of, note}`；
- **证据链**：`{kind: peer|financial|sentiment, ref, summary, numbers[], gate}`；
- **敏感度与区间**：`{param, sigma, delta_plus_1σ, delta_minus_1σ, elasticity, direction_flag}` + MC 分位 + 区间/三情景。

**接口/数据结构.** `model_trace.schema.json` v1（字段版本化）；工作台新增「模型履历」抽屉（左树右证据）；逐券报告消费同一 JSON；`diff(trace_a, trace_b)` 支撑两批对比。

**验收标准.** `ok` 券 trace 覆盖率 100%；数值与引擎输出逐位一致（派生，不重算）；参数可点回来源；任改一个参数在 trace 中可见；两批 diff 可列出「哪只券哪个参数变了」。

**风险.** 双写不一致（必须从引擎派生）；字段膨胀（trace 独立文件）；报告与工作台渲染再次漂移。

**依赖.** 引擎 `assumptions_summary` / 路由已部分结构化；前端面板不阻塞后端。

### 3.3 第三层：Agent 评估与参数迭代

**问题.** shadow 是「批内逐券评审 + 人工采纳」：专家提建议、主审夹断或驳回、页面标 adopted/rejected。参数只有当前一版（`agent_config` 自增版本号、文件在仓库外），**明确不做跨批台账**，因此「昨天通过的参数今天用」不存在，也没有人对评估 Agent 的意见做适用性判定，更没有收敛/振荡判据。

**方案.** 把评审升级成迭代闭环，三个角色分工：

- **专家（3 个）**：提参数建议，受 severity / confidence / caps 约束；
- **评估 Agent**：把当日 N 只券的建议聚类成「参数议题」（param、方向、证据覆盖家数、离散度、受影响行业）；
- **主 Agent**：对每个议题判 **适用 / 不适用 / 观察**，给出理由与适用范围，写入台账。

次日跑批默认读台账最新「已生效」版本，页面显示「本批参数版本 v{n}」。

**接口/数据结构：参数版本.**

```
P_v = {weights, wacc_pp, tg_pp, caps, pool_mode} + meta{v, created, source_job, verdicts, approved_by, hash}
状态机：proposed → evaluated → approved | rejected | expired → applied → superseded | rolled_back
时序：   T 日 09:00 跑批(P_v) → 10:00 评审 → 10:30 评估汇总 → 11:00 主审裁决 → T+1 09:00 跑批(P_{v+1})
```

当天任务不受当天裁决影响（沿用现有「每批开始时读一次配置快照」的语义）。

**收敛/振荡.** 稳定：连续 k 期同方向且 |Δ| 递减 → `converged`，冻结 4 周。振荡：4 期内方向翻转 ≥2 次，或 wow 中位 |Δ| 不降 → `freeze` + 人工介入 + 回退上一 converged 版本。判据复用 `shadow.metrics` 的 `dispersion` / `wow` / `adoption.rate`（`shadow.py:1172`）。

**评估指标.** 采纳率、评审覆盖率、平均置信、离散度、apply 后中枢移动中位数、单券 token 成本、重复评审 Δ 一致性。

**shadow / apply.** 保留 `off / shadow / apply`；跨批只经台账传参，apply 仍只在单批内回写输入；未显式指定参数时读台账（iter）。

**失败回滚.** 台账每次写入前快照；若 P_{v+1} 的跳过率上升超阈值、或 apply 后 |Δ| 超 caps，自动回退 P_v 并标 `rolled_back`；人工一键回滚。

**人工审批点.** 版本晋升需一次点击确认；caps / gate 变更仍走 AgentsPage 校验；池子切换需主审 + 人工双确认。

**验收标准.** 给定 v 能完整还原参数与来源（可重放）；次日默认参数 = 台账最新 approved（自动化测试）；apply 失败回滚零泄漏；构造序列能触发振荡检测。

**风险.** LLM 随机性（固定温度/种子并记录）；成本（每券 5 次 × 2,201 券不可行）；自指偏差；参数漂移。

**依赖.** `*.shadow.json` 已落盘；`agent_config` 需从「单版」扩成「版本表」。

### 3.4 第四层：指数选择与估值拟合

**问题.** 五个指数是「选一个跑一批」，指数层只有一条加权比率公式 `P × Σw(V/P)/Σw`；三情景点位由逐券区间端点合成后与拟合点位夹逼，不是同情景一致加总；权重口径**三套**（官方 `WEIGHT` / 自由流通市值 / 总市值）；无交叉校验、无偏差分解。README 六步流程的「权重因子×当日市值→归一化当日权重」**尚未实现**，属待做项。

**方案.** 独立的指数层模块 `index_fit`。**接口/数据结构.** `index_fit.fit(rows, weights) → {P_A, P_B, α_w, scenarios, weight_kind, checks[]}`。

1. **口径 A（零回归锚点）**：`P_A = close × Σw_i(ps_i/close_i)/Σw_i`，`w_i` 用成分表权重并标注口径；
2. **口径 B（拟合）**：对 `r_i = ps_i/close_i` 做加权最小二乘 `r_i = α + β·log(mcap_i) + γ·行业固定效应 + ε_i`，指数层系统性偏离 `α_w = Σw_i·r̂_i / Σw_i`，`P_B = close × α_w`；
3. **三情景一致**：每券同情景值（bear/base/bull）按同一权重加总，强约束 `P_bear ≤ P_base ≤ P_bull`；
4. **权重口径**：显式标注 `official | computed`，双口径并行输出 `ΔP` 作为口径敏感性；
5. **多指数交叉**：上证50 ⊂ 上证180 ⊂ 上证综指，同一 as_of 下同一券估值必须相同，点位差异应完全由权重解释，否则是数据或口径 bug。

**验收标准.** 五指数同日并列表；情景点位单调；权重口径标注 100%（逐指数声明）；交叉一致性通过或每条差异有解释；偏差可分解为 α + 权重效应 + 残差；「权重因子×当日市值」若实装，须作独立口径并列，不直接替换。

**风险.** N=50 时回归过拟合（行业固定效应 + 收缩）；包含关系会暴露计算权重与官方权重差异；指数收盘与成分 as_of 不同日。

**依赖.** 行级产物含 `mcap / industry / weight`；第一层宽表。

### 3.5 第五层：线性池 vs 对数池 vs 专家乘积

**问题.** 只有加权算术平均：方法分歧大时（DCF 与可比差 3 倍）被大值主导；区间端点线性加总不满足尺度不变；没有「该换池子」的判据。

**方案.** 三种池子全部实现，由评估 Agent 决定采用哪种。**接口.** `pool.combine(V, M, W, mode) → (V*, interval, pool_choice, diag)`，`mode ∈ {linear, log, product}`。

**三种池子的数学性质.**

```
线性池   V = Σ w_m V_m / Σ w_m
对数池   log V = Σ w_m log V_m   →   V = Π V_m^{w_m}
专家乘积 p(V) ∝ p0(V) · Π p_m(V)^{w_m}
         正态近似：V* = (Σ w_m V_m/σ_m²) / (Σ w_m/σ_m²)，1/σ*² = Σ w_m/σ_m²
```

**模糊（区间）传递.**

```
线性池   [Σw·a_m, Σw·b_m]
对数池   [exp(Σw·ln a_m), exp(Σw·ln b_m)]
乘积池   [V* − z·σ*, V* + z·σ*]（z 由置信水平定，σ_m 须先校准）
```

**适用条件.**

| 池子 | 数学性质 | 适用 | 不适用 |
|---|---|---|---|
| 线性 | 算术均值；可加可分解；对离群线性放大 | 方法数 ≤2、分歧小（IQR/中位 <30%）、需要按方法分解 | 单方法极端值；跨行业尺度差异大 |
| 对数 | 几何均值；尺度不变；对低值更敏感（下行保守） | 方法值同号且量级差 >2×；乘数型方法为主 | 有 ≤0 值（需 mask/nudge）；需要线性加总到指数 |
| 乘积 | 精度加权；方差收缩；需概率解释 | 每方法有校准 σ / 区间；方法近似条件独立 | σ 未校准；方法高度相关（重复计信息） |

**切换策略.** 默认线性（零回归）；评估 Agent 按「离散度 + 是否同号 + σ 是否可用」提议，主审复核并记 `pool_choice + reason`；单批可逐券切换，但指数层须报告池子分布，三情景须同一池子。

**实验设计.** 同一 as_of 三池并算（离线 shadow，不进生产），比较：与收盘偏离分布、周环比稳定性、极端券（估值/价 ≥5×）占比、MC p5–p95 是否覆盖收盘；跑满 4 周定默认池子。

**验收标准.** 三池可切换、可复算；区间单调且覆盖；池子选择有 reason 且可审计；线性池与现引擎逐位一致。

**风险.** 对数池遇负值/缺失的定义（mask 与 nudge 会引入偏移）；乘积池 σ 未校准会收窄区间；池子选择的可解释性。

**依赖.** 每方法 σ/区间（第二层的 sens 与 stat）；评估 Agent（第三层）。

---

## 4. 里程碑

相对周次，不绑定日历日期；总计 17 周。

| 里程碑 | 周次 | 交付物（1–2 周粒度） | 验收指标 | 回滚点 |
|---|---|---|---|---|
| **M0 基线固化** | W1–W2 | W1：核验本轮已完成事实——技能包在 `skills/` 随仓库版本化、`config.py` 三级解析（仓库内 → `VALUATION_SKILL_DIR` → 旧部署路径）、前端无「陈老师 vs 石总」双模型对比、`docs/` 文档中心建立；`smoke_test` 170 个用例全绿 + 11 组 examples 输出快照（`runtime/baseline/<tag>/`，含 hash）。W2：legacy 双跑脚本（同 as_of 同参数跑两次逐位 diff）；仓库级最小门禁（lint + 单测，**可选**：只覆盖新增模块）；本文档定稿 | 快照可复算（hash 一致）；冒烟全绿；两次跑批 diff = 0；`config.py` 三级解析写成测试；门禁可一键跑（可选） | 无运行路径变更，只增快照目录与测试 |
| **M1 解耦向量化（基础层）** | W3–W6 | W3：kernel 抽取（先单券调用，只移位置）；W4：宽表组装 + 层产物格式 + manifest；W5：批量 DCF/相对估值 + 合成；W6：dual 模式 + 失败隔离 + 性能测量 | 11 组 examples + sh50 零回归；单券耗时中位 ↓≥30%（待测）；内存 ≤1.5×（待测）；注入故障只影响 1 券 | `pipeline_mode` 回 legacy；层产物按 job 隔离 |
| **M2 表达与可视化** | W7–W9 | W7：trace schema v1 + 引擎诊断结构化；W8：工作台「模型履历」面板 + 两批 diff；W9：报告消费同一 JSON + 字段完整率检查 | trace 覆盖率 100%；数值一致；溯源可点；可读性内部评分 ≥4/5 | 面板 feature flag；旧报告模板保留 |
| **M3 Agent 迭代** | W10–W13 | W10：参数台账 schema + 状态机；W11：评估 Agent（议题聚类）；W12：主审适用性判定 + 次日默认参数；W13：振荡检测 + 回滚 + 审批 UI | 台账可重放；次日默认 = 最新 approved；振荡用例触发；apply 回滚零泄漏 | 跑批可显式指定 P_v；一键回退 |
| **M4 合成池与指数拟合** | W14–W17 | W14：三池实现 + 线性零回归；W15：指数拟合（口径 A/B + 三情景 + 双权重）；W16：五指数并列 + 交叉一致性；W17：三池离线实验报告 + 默认池子决策材料 | 三池可复算；线性 = 现引擎；五指数并列表；交叉一致性通过 | `pool_mode=linear` 为默认；`index_fit` 双口径并存 |

M1 与 M4 是唯二会动数值的里程碑，均以「零回归 + dual 对比 + 开关」为前置；M2、M3 只增字段与流程。

---

## 5. 指标与验收

| 指标 | 定义 | 现状 | 目标 | 采集方式 |
|---|---|---|---|---|
| 覆盖率 | `ok / total`（按指数） | 待测（本工作副本无 `runtime/` 历史） | ≥ 基线，逐指数记录 | `state.json` summary |
| 跳过率 | `skip / total`，按原因分类 | 待测 | ≤ 基线；原因分布可解释 | `row.error` 归类 |
| 单券耗时 | `pending → ok` 墙钟，取中位/p95 | 待测（无逐券计时字段） | 中位 ↓≥30% | 新增 `row.timing_ms` |
| 批跑总时长 | `created → finished` | 待测 | sh50 ≤ 基线 0.7× | `state.json` |
| 内存峰值 | 服务进程 RSS 峰值 | 待测 | ≤ 1.5× 基线 | 采样 / `psutil` |
| 数值零回归 | 对基线快照的 `max|Δ|` | 基线未固化 | 0（逐位）或 ≤1e-9 | dual diff |
| 报告可读性 | trace 字段完整率 + 人工评分 | 无 | 完整率 100%，评分 ≥4/5 | schema 校验 + 问卷 |
| Agent 采纳率 | `adopted / (adopted + rejected)` | 有指标无历史 | ≥60% 且不低于基线 | `shadow_metrics.adoption` |
| 参数稳定性 | 周环比中位 `|Δ|`、方向翻转率 | 有 `wow` 字段 | `|Δ|` 递减，翻转 ≤1/4 期 | `shadow_metrics.wow` |

「待测」项须在 M0 补基线测量，否则 M1 验收没有分母。

---

## 6. 风险与待决

**6.1 数值零回归.** 最大风险。kernel 抽取只「移位置」不改算法；dual 逐位 diff；examples + 170 用例 + 50 只真实券三层守护；非零 diff 阻断发布。

**6.2 向量化后单券失败隔离.** 行级 mask + 行级 error + 层内 try/except；禁止整批 abort；四类故障注入（缺财报/无可比/负值/超时）。

**6.3 缓存一致性.** TTL 缓存无 PIT（`dsources.py:37–50`）；向量化一次读全市场，as_of 混杂会放大。策略：manifest 记 as_of + 资源 hash，层产物带 as_of，跨 as_of 拒合并。

**6.4 技能拆分接口.** 单体技能（引擎 5000+ 行、SKILL.md 1208 行）一次性拆成 `spec/05` 的 8 模块会破坏「技能即文档」形态。策略：先接口后实现，先加「函数入口 + schema」薄适配层，8 模块作为目标形态、随 M4 后推进（决策点 5）。

**6.5 LLM 成本/随机性.** 每券 5 次调用；2,201 券全市场不可行（单进程、并发 6）。策略：全市场只跑规则舆情；评审按权重/行业分层抽样或只评异常券；温度与种子固定；成本入指标。

**6.6 数据 PIT.** 财报、成分、行情 as_of 不同源；指数收盘与「前一日权重」不同步。策略：manifest 记录每个资源 as_of 并披露；禁止跨 as_of 拼接。

**6.7 版本漂移.** 已存在实例：`SKILL.md` frontmatter `3.16.12`、变更记录到 v3.29.1、引擎 `2.28.0`、冒烟脚本头注「100 用例」而实际 170 个 `test_*`、SKILL.md 写「169 用例」；根目录另有未入库副本。技能路径已由 `config.py` 三级解析兜底，版本号仍无单一来源。策略：单一 `VERSION` + 发布校验；重复副本删除或改 submodule（待决）。

---

## 7. 本次不实现

本文件是**规划**：不改代码、不改其他 docs、不 git。落地顺序与验收见 §4；不承诺具体日期，周次为相对 Week。

需要拍板的 5 个决策点：

| # | 决策点 | 选项 | 倾向 | 影响面 |
|---|---|---|---|---|
| 1 | 向量化粒度 | A 方法级 kernel + 宽表（引入 numpy/pandas）；B 只做进程复用与批量 IO（零依赖）；C 混合（基础层 numpy，非基础层纯 Python） | C | 依赖、内存、可移植性 |
| 2 | 层间 barrier | A 全量 barrier（实现简单、内存高）；B chunk 内 barrier + 层内流水（省内存、复杂） | B（chunk=200） | 峰值内存 vs 实现复杂度 |
| 3 | 池子切换由谁决定 | A 评估 Agent 提议 + 主审复核（自动）；B 人工固定；C 逐指数固定 + 异常时提议 | A（附人工确认） | 可解释性、稳定性 |
| 4 | Agent 迭代频率 | A 每日（跑批日频、参数日晋级）；B 每周；C 事件驱动（离散度触发） | A，周频作为回退档 | LLM 成本、收敛速度 |
| 5 | 技能拆分边界 | A 按 `spec/05` 的 8 模块一次拆；B 保留单体 + 批跑侧适配层；C 先把 scripts 变成可 import 模块（接口先行） | C 起步，8 模块为目标形态 | 交付形态、版本管理 |

这 5 项不拍板，M1 代码形态无法定稿；M0 与 M2 可先行。
