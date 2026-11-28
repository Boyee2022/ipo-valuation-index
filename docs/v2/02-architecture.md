# 02 · 架构：类型化估值计算图（VCG）与智能体评论家

> 状态：**设计稿（design）**，不进入生产；执行器、模块协议与 API 均为规划。  
> **2026-11-28 修订**：demo 优先；不鉴权、不脱敏、不做数据域隔离；完全重构（技能只作参照）；执行架构改为 **A 数据 → B 模型加载 → C 批处理/断点 → D 指数拟合**。与本文冲突处以 [08-demo-first-revision.md](08-demo-first-revision.md) 为准。
> 定位：**VCG / MVN（Valuation Computation Graph / Modular Valuation Network）**，前向是带类型的估值计算图，后向是带合成目标的智能体评论家（Agentic Critic）；**不是端到端可训练的神经网络**。  
> 与同批文档的关系：为什么这样定位见 [00-evaluation.md](00-evaluation.md)，形式化与命题见 [01-theory.md](01-theory.md)，模块清单见 [03-module-catalog.md](03-module-catalog.md)，落地顺序见 [05-implementation-plan.md](05-implementation-plan.md)，两个用途见 [04-use-cases.md](04-use-cases.md)。

---

## 0. 定位、边界与与现有系统的关系

现在生产里的执行单元是「一只券跑一次完整流水线」：`pipeline._worker()` 依次做输入组装 → 引擎子进程 → 统计校验 → 报告 → 机检（`packages/batch/pipeline.py:223`）。方法路由、DCF、可比、舆情、合成、置信度全部封在单券引擎内部（`skills/llm-ipo-valuation/scripts/valuation_engine.py`，5,681 行），跨券只共享只读缓存；多 Agent 评审是券内的一次 sidecar 调用（`packages/batch/shadow.py:702`），参数只有当前一版（`packages/batch/agent_config.py:6`）。

本架构要做的是**把「方法」从「券」里抽出来变成图节点**；实现上**完全重构**，现有技能只作公式/行为参照与回归 oracle，不做运行时 legacy 包装：

- **前向**：`GraphSpec` 描述节点（编码器、估值模块、门控、池化、指数合成、报告）与边（类型化端口）；执行器按阶段批处理或逐券调度，每节点输出值、区间、置信度、证据、诊断与 trace。
- **后向**：多专家提议 → 主审核准 → 影子对照 → 有界回写 → 回滚，写入参数台账；用**合成校准目标**（一致性、稳定、校准、人评）排序，而不是用「更贴近指数收盘」当损失。市价只作诊断。
- **双入口**：`monitor(index, date)` 跑指数成分券监控，`valuate(ipo_input)` 跑单公司 IPO 估值与定价约束检查；共享估值模块；`mode=monitoring|ipo` 只作行为/缓存口径开关，demo 阶段**不是安全边界**，不做鉴权/隔离。

本架构明确**不**做：重写引擎、端到端训练、自动交易/自动定价、把「神经网络反向传播」当已实现。见 §9。

### 与 `docs/03-engineering-roadmap.md` 五层的对应

| 路线五层 | 本文对应 | 接口落点 |
|---|---|---|
| ① 解耦与向量化 | 编码层/估值层按层批处理；`Batch` 宽表 + `chunk` 调度 | `enc.*`、`val.*`、执行引擎 §3 |
| ② 表达与可视化 | 每模块 `trace` + `evidence`，图级 trace 取代单券文本块 | `ModuleOutput.trace`、`GET /api/runs/<id>/trace` |
| ③ Agent 评估与参数迭代 | 评论家层 + 参数台账 + 合成目标 + 振荡/回滚 | `critic.*`、`§5`、`/api/params/*` |
| ④ 指数选择与拟合 | `idx.index_fit` 节点：口径 A/B、三情景一致、双权重口径、交叉校验 | `idx.index_fit`、`§4.7` |
| ⑤ 线性池/对数池/专家乘积 | `pool.linear` / `pool.log` / `pool.product` 三池可切换，区间同步传播 | `pool.*`、`§4.6` |

路线里的 M0–M4 与 V0–V4 的映射见 [05](05-implementation-plan.md)；本架构的“层”是模块语义，§1.0 的 A/B/C/D 是执行视角。V0 起**完全重构**，不包 legacy。

---

## 1.0 四段式执行架构（demo 版）

> 本节的 A/B/C/D 是**执行**视角；§1 的七层是**模块语义**视角，两者不冲突。

```text
A. 数据资料收集
   源适配器（公开行情/财报/公告/舆情）→ 标准化 → 宽表/列式缓存 + manifest（as_of、来源、缺失掩码）
        │
B. 模型层加载
   模块注册表 → 依赖图 → 参数包 → 常驻 worker 池 → 预热/健康检查
        │
C. 批处理 + 断点恢复
   按模块/层 chunk → 向量化计算 → 每 chunk 原子落盘 → manifest 记录完成/失败 → 可恢复
        │
D. 指数选择与拟合
   选指数/权重 → 池化 → 拟合点位 → 三情景 → 诊断/报告
```

- **模块常驻**：B 段加载一次，C 段批量跑完再退出；避免每券重复 import/初始化。
- **向量化**：基础层（DCF/DCM/可比/池化）按列式/矩阵批处理；非基础层（舆情/LLM）逐券或小批并发。
- **断点**：manifest 记录 `batch_id + as_of + module_version + params_hash + chunk_id + status`；已完成 chunk 跳过，失败 chunk 重跑。
- **失败隔离**：单券/单模块失败只写 mask/错误，不阻断整批；D 段按剩余权重再归一。
- **demo 边界**：只用公开/构造数据；不做鉴权、脱敏、数据域隔离、合规认证（见 08）。

---

## 1. 分层架构

七个计算层（L0a/L0/L1–L5）+ 两个入口。层间只交换类型化数据；**任何层不得读下一层的私有状态**（例如池化层不得读单券 input 文件，只能读 `ModuleOutput`）。

```text
┌────────────────────────────── 入口层 ──────────────────────────────┐
│  E1 monitor(index, date)              E2 valuate(ipo_input)        │
│  成分券宇宙 / 指数权重 / 收盘          单公司 / 可比 / 发行条款      │
└───────────────┬───────────────────────────────┬────────────────────┘
                │                               │
┌───────────────▼───────────────────────────────▼────────────────────┐
│ L0a 采样/证据智能体层  agent.evidence · agent.docs · agent.peers    │
│   采集/核验/缺口补全/来源标注；产出 EvidenceBatch + 缺口清单        │
└───────────────┬────────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────────┐
│ L0 数据/编码层   enc.financials · enc.industry · enc.lifecycle     │
│                 enc.cost_capital · enc.peers · enc.sentiment       │
│                 enc.pit_quality                                    │
│   产出：类型化 Batch（宽表）+ 质量掩码 + PIT 元数据 + 数据溯源      │
└───────────────┬────────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────────┐
│ L2 门控/路由层   gate.layer0 · gate.quality · gate.ipo_eligibility  │
│   产出：方法可用集、三路/多路权重、否决记录 blocked_paths、置信度帽  │
└───────────────┬────────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────────┐
│ L1 估值模块层   val.dcf · val.comparable · val.sentiment · val.rim  │
│                 val.ddm · val.nav · val.rnpv · val.sotp            │
│                 val.quality_adjust · val.industry_fallback          │
│   产出：每券×每方法 (value, interval, confidence, evidence, trace)  │
└───────────────┬────────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────────┐
│ L3 池化/指数合成层  gate 加权 → comb.norm → comb.residual →        │
│                 ens.dropout → pool.{linear|log|product} →          │
│                 unc.interval → idx.index_fit                       │
└───────────────┬────────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────────┐
│ L4 评论家层     三专家（可比/折现/舆情）→ 主审 → shadow → apply     │
│                 评估 Agent（议题聚类）→ 收敛/振荡判定 → 回滚        │
└───────────────┬────────────────────────────────────────────────────┘
┌───────────────▼────────────────────────────────────────────────────┐
│ L5 参数存储/审计层  参数台账（版本/状态机/审批/哈希链）              │
│                 图级 trace、逐节点产物、报告机检、回滚基线           │
└────────────────────────────────────────────────────────────────────┘
```

> 注：L2 门控在数据流上先于 L1 估值执行（先定谁可用，再算），但层号沿用「数据/编码 → 估值模块 → 门控/路由 → 池化 → 评论家 → 存储」的概念顺序；**编号表示概念分层，不表示执行先后**。

**层职责与不变量：**

| 层 | 职责 | 不变量（违反视为架构 bug） |
|---|---|---|
| L0a 采样/证据 | 智能体采集/核验数据、补缺口、标注来源与置信；产出 EvidenceBatch | 不得直接改参数；不得把未经核验的文本当事实；缺口必须显性 |
| L0 编码 | 原始数据 → 类型化特征；标注 as_of、来源、口径 | 不得做方法选择；不得静默补齐缺失值而不留痕 |
| L1 估值 | 每方法独立计算，失败只掩码本格 | 不得读其他方法的**私有中间量**（可比基数除外，见 `val.sentiment`）;不得改全局参数 |
| L2 门控 | 决定「谁可用、权重多少、置信帽多少」 | 用户显式禁用（`base weight=0`）的方法不得复活；否决必须写 `blocked_paths` |
| L3 池化 | 方法值 → 综合值/区间；指数合成 | 必须可复算、可归因；三情景必须同池同权重 |
| L4 评论家 | 提议/裁决/回写/回滚；不改数值算法 | 不得跨域提参数；不得突破 caps；不得以价格为优化目标 |
| L5 存储审计 | 参数版本、trace、报告、审批/回滚记录 | append-only；任何数值都能回溯到「参数版本 + 模块版本 + 数据 as_of」 |

---

## 2. 模块协议

协议目标：**模块可插拔、类型可校验、失败可隔离、结果可复现**。V1 用纯标准库 dataclass 实现（与 `prototype/valnet/` 原型一致的取向），参数存储与执行器都不要求 numpy。

> 已有参照：同批原型 `prototype/valnet/` 用纯标准库把本节协议跑通了最小闭环（`spec.py` 类型契约、`graph.py` DAG/门控/残差/失败隔离/trace、`pooling.py` 三池，83 个单元测试通过）。它的 `Batch` 是列式最小实现（`ids/features/masks/meta`）；生产协议在此基础上增加 `rows/provenance/errors/cache`，字段只增不改。原型不接生产、不 import `packages/batch`。

### 2.1 类型表达式（TypeExpr）

类型是「语义 + 单位 + 版本」三元组，不是 Python 的 `dict`：

```text
FinancialsBatch  @FY, unit=亿元         # 财报编码输出
PeersBatch       @as_of, n≤8            # 可比池
CostBatch        @FY, unit=小数         # WACC / Ke
MethodValue      @FY, unit=亿元/元每股  # 单方法估值，含 interval/confidence
MethodMatrix     @FY, shape=(N,M)       # 方法矩阵（含掩码）
Valuation        @FY, unit=亿元         # 池化后综合中枢
Interval         @FY, coverage=0.9      # 区间
QualityMask      @as_of, dtype=bool     # 质量/PIT 掩码
CritiqueRecord   @batch, version=1      # 评论家记录
```

以上为核心类型（非穷举）：完整端口类型见 [03](03-module-catalog.md) 各模块与两份 YAML，新增类型必须登记到 TypeExpr 注册表。

规则：**端口名 + 类型必须匹配**；同一端口不得既传亿元又传元；类型升级=主版本号变化，执行器拒绝跨版本直连（需显式 adapter 节点）。

### 2.2 `ModuleSpec`

模块注册表的唯一键；静态声明、运行时不改：

```python
@dataclass(frozen=True)
class ModuleSpec:
    id: str                      # 'val.dcf'，全局唯一，命名空间=层
    type: str                    # encoder | valuation | gate | pool | critic | entry | report
    version: str                 # '0.1.0'；与输出 schema 版本一致
    inputs: dict[str, TypeExpr]  # 端口名 → 类型
    outputs: dict[str, TypeExpr]
    params_schema: dict          # 参数名 → {type, range, default, unit}
    constraints: tuple[Constraint, ...]   # 硬约束，执行器逐条校验
    status: str                  # existing | wrap | new | proposed（诚实标注）
    deterministic: bool          # False 时 trace 必须记录随机源
    schedule: str                # batch | chunked | per_security | single
    cost: str                    # cheap | heavy | llm
    requires: tuple[str, ...]    # 能力依赖，如 'financials.annual'
    cache: str                   # content_hash | none
    evidence: tuple[str, ...]    # 必须产出的证据类型
```

约束示例：`w_m ≥ 0`、`Σw_m = 1`、`V > 0`（或显式允许负值时声明）、`WACC > g`、`n_peers ≤ 8`、`interval[0] ≤ value ≤ interval[1]`。约束失败的处理分两档：`mask_cell`（丢该券该格）与 `abort_node`（仅限池化/一致性这类不可局部修复的节点）。

### 2.3 `Batch`

统一输入/输出容器。V1 是「行式 dict + 掩码」；V2 可换列式（`dict[str, list]`）而不改端口类型：

```python
@dataclass
class Batch:
    ids: list[str]                  # secucode / deal_id，顺序稳定（排序后执行）
    rows: dict[str, dict]           # id → 结构化记录
    mask: dict[str, bool]           # 有效性掩码（质量/PIT/门控）
    meta: dict                      # as_of、universe、data_version、params_hash
    provenance: list[dict]          # 每条数据的来源/as_of/口径
    errors: dict[str, CellError]    # 单元格级错误，不抛整批
```

**异步 sidecar 的 join 规则**：`enc.sentiment` / `val.rnpv` 这类逐券节点按 `id` 与基础层 batch 做左连接；缺失填 `None` + mask，不阻断其他行；join 记录在 trace 中（`sidecar_join`）。

### 2.4 `ModuleOutput`

一个节点对一批券的输出；「值 + 不确定性 + 证据 + 诊断 + trace」五件套：

```python
@dataclass
class ModuleOutput:
    node_id: str
    module_id: str
    module_version: str
    values: Batch                   # 主产物（可多端口，如 value/interval/evidence）
    interval: dict[str, tuple[float, float]] | None
    distribution: dict | None       # MC 分位数/直方图摘要，不是样本全量
    confidence: dict[str, float]    # 0–1，校准后使用
    evidence: list[EvidenceRecord]  # {kind, ref, summary, numbers, gate, as_of}
    diagnostics: dict               # 参数、弹性、覆盖率、被剔除项…
    params: dict                    # 本节点实际生效参数（含解析后的引用）
    params_hash: str
    cache: dict                     # {hit: bool, key: str}
    errors: list[CellError]
    trace: list[TraceSpan]          # 节点级阶段耗时/分支/数据版本
    started: str
    finished: str
```

设计要求：`params` 必须记录**解析后**的值（而不是 `${params.weights}` 引用）；`cache.hit` 为真时 `values` 必须与原始运行逐位一致；`errors` 与 `mask` 必须同时出现（不允许「值在但掩码说不可用」的歧义）。

### 2.5 `GraphSpec` / `NodeSpec`

图是声明式的，可版本化、可 diff、可在测试里直接断言：

```python
@dataclass(frozen=True)
class GraphSpec:
    version: int                    # 图规范版本
    name: str                       # monitoring | ipo
    mode: str                       # monitoring | ipo
    params: dict                    # 图级参数 schema（可被 API 覆盖）
    requires: tuple[str, ...]       # 启动前置能力
    nodes: tuple[NodeSpec, ...]
    edges: tuple[EdgeSpec, ...]     # {(from_node, from_port) → (to_node, to_port)}
    pool: PoolSpec                  # 顶层虚拟节点
    critic: CriticSpec              # 顶层虚拟节点
    checks: tuple[CheckSpec, ...]   # 图级断言（区间包含、情景单调、无价格泄漏）
    outputs: tuple[OutputSpec, ...] # 落盘契约
@dataclass(frozen=True)
class NodeSpec:
    id: str
    type: str                       # 指向 ModuleSpec.id
    inputs: tuple[str, ...]         # 端口名，与 edges 对账
    params: dict                    # 字面量或 ${params.x} 引用
    gate: GateSpec | None           # {when, mode: hard|soft, weight_from, on_fail}
    schedule: str | None            # 覆盖模块默认
    timeout_s: float | None
    checkpoint: bool                # 是否产出层产物
```

两份可读实例见 [`graphs/monitoring.yaml`](graphs/monitoring.yaml) 与 [`graphs/ipo.yaml`](graphs/ipo.yaml)。图规范必须能被未来执行器直接解析：字段、端口类型、虚拟节点约定与校验规则都写死在这两份文件头注释里。

### 2.6 错误隔离与版本

- **单元格级**：单券缺财报/无可比/负值/超时 → 该格 `mask=0` + `CellError`，其余格继续；对应现有「单券 skip 不阻断整批」（`docs/spec/01-architecture.md` §8）。
- **节点级**：节点实现抛异常或违反约束 → 该节点输出标记 `unavailable`，下游节点收到全掩码 + 原因为 `node_unavailable`；若下游是池化/指数合成，则触发**降级路径**（legacy 单券结果 / 行业基准兜底），并在输出与 trace 显式标注。
- **批次级**：依赖的公开数据源整体不可用（如成分表拉不到）→ 拒绝启动（`requires` 校验失败），不产生半成品任务。
- **版本**：`module_id@version` 与 `evidence.schema_version` 同时写进每条证据；参数变更由 L5 台账管理，模块升级走独立版本号 + 消融/回归门禁。

---

## 3. 执行引擎

执行引擎是「图的解释器」，不是新的估值逻辑。目标：**按层批处理、可缓存、可断点、可确定性复算、失败可局部化**，同时不破坏现有 `runtime/jobs` 语义。

### 3.1 编译期（启动前）

1. **拓扑排序**（Kahn），检测环与悬挂端口；`edges` 的 `from/to` 必须与 `nodes[].inputs` 对账（见 YAML 校验脚本）。
2. **类型检查**：相邻端口 TypeExpr 兼容；不兼容必须显式插 adapter 节点。
3. **能力检查**：`requires` 逐条探测（数据源可用性、IPO deal 输入完整性）；IPO 图额外检查 `issuance.terms` 必填。
4. **参数解析**：`${params.x}` / `${input.x}` / `${ledger.latest}` → 具体值，生成 `params_hash`；解析失败在提交阶段返回 4xx，不创建任务。
5. **阶段与 barrier**：按 `stages` 分组；`barrier: true` 的阶段内所有节点完成后才进入下一阶段；`sidecar` 阶段不设 barrier，与基础层并行、最后 join。

### 3.2 调度：按层批处理 vs 逐券

| 节点类型 | 调度 | 理由 | 现有对应 |
|---|---|---|---|
| 编码器（财报/行业/生命周期/成本/可比池） | `batch` 或 `chunked(200)` | 一次读全市场、跨券分位/邻接 | `input_builder.build_input` 逐券 → 待抽 |
| 基础估值（DCF/可比/RIM/DDM/NAV/相对倍数） | `chunked`，方法间 barrier | 可数组化；层间屏障保证可比池完整 | 引擎 `Engine.run()` 内方法串行 |
| 非基础（舆情/rNPV/覆写/评审） | `per_security` 异步 | 语义逐券、可重试、LLM 限流 | `sentiment.py`、`shadow.py` |
| 池化/指数合成 | `batch` barrier | 需要全部方法值与全部券 | 引擎 `synthesis` + `pipeline._finalize` |
| 报告/机检 | `batch` | 逐券可并行但无跨券依赖 | `report_generator.py`、`html_check.py` |

`chunk` 建议 200 只（路线决策点 2 的倾向）：控制 MC 中间数组与内存峰值，chunk 间可并行，chunk 内方法有序。全市场 2,201 只时 11 个 chunk；每 chunk 落一次盘点，失败只重跑该 chunk。

### 3.3 缓存

- 键：`sha256(module_id@version | params_hash | 输入值哈希 | as_of | data_resource_hashes | mode)`；内容寻址，存 `runtime/cache/graph/<hash>.json`。
- 命中条件必须包含数据 as_of；**禁止跨 as_of 复用**；`mode` 只区分 monitoring/ipo 的表达口径，不是安全隔离。
- 缓存只缓存**纯函数节点**；LLM 节点缓存记录模型名、`prompt_hash`、温度与输出，命中与否都写 trace。
- 失效：模块版本升级、图版本升级、数据源 TTL 到期、显式 `--no-cache`。

### 3.4 断点与部分失败

现有 `runtime/jobs/<id>/state.json` 已具备行级状态与 `>800` 行每 10 行落盘（`pipeline.py:76–83`）。图的增量只增不改：

```text
runtime/jobs/<job_id>/
├── state.json                  # 既有：任务状态 + 逐券摘要（新增 graph 摘要字段）
├── <code>.input.json ...       # 旧技能产物：仅作对拍参照，不进入新运行时
└── graph/                      # 新增：仅图模式写
    ├── manifest.json           # 图版本、params_hash、节点状态、chunk 进度、resume_from
    ├── nodes/<node_id>.json    # 层产物（值 + 掩码 + 证据 + trace）
    ├── rows/<code>.json        # 行产物（合并后）
    ├── critic/<code>.shadow.json
    └── trace.jsonl             # 追加式图级 trace
```

- 节点提交是「临时文件 + 原子替换」；`manifest.json` 在节点完成/失败后更新，崩溃后可 `resume_from` 最后完整 chunk。
- 重启语义：图任务把遗留 `running` 标为 `interrupted`（可续跑），legacy 任务保持 `reconcile_running` 的 `running → error`，两者不互相污染。
- 旧任务没有 `graph/` 目录时按 legacy 解释；图执行器必须能读旧 `state.json`，legacy 模式不产生任何新文件。

### 3.5 确定性、超时与限流

- **确定性**：`seed` 从图参数派生；MC 用固定 seed（现有 `stat_validation.py --seed 42`）；排序、去重、浮点求和顺序固定（按 `ids` 排序后计算）；`deterministic=false` 的节点（LLM）必须记录随机源与模型版本，且不参与「逐位一致」验收。
- **超时**：节点级 `timeout_s`（默认 180s）、LLM 单券 90s、报告 600s、机检 300s（沿用现有超时量级）；超时 → 该节点/该格失败，不拖垮整批。
- **重试**：`network: 1`、`llm: 1`、`deterministic: 0`；重试耗尽后按错误隔离处理。
- **限流**：LLM 节点复用现有信号量（`shadow.py:61`，并发 1–12），不新增并发层；全市场评审只抽样（`critic.sampling`），避免 2,201 × 5 次调用。

### 3.6 与现有 `pipeline.py` 的兼容策略

- V0/V1 **新增独立包 `packages/valuation_net/`**（import 名 `valuation_net`），完全重构；旧 `packages/batch` 保持不动，新包通过 CLI/API 接入。不做 `graph_bridge` 式的 legacy 包装。
- 任务 ID 复用 `job_<timestamp>_<hex>` 命名空间，`/api/jobs/<id>` 继续可用；前端 2.5s 轮询逻辑不变（`ValuationPage.tsx:130`）。
- 图模式产出的 `state.json` 字段只增不改（`graph` 摘要 + `run_id` 别名）；旧字段 `rows/summary/shadow_metrics` 仍由池化/报告适配器填充，保证工作台与报告存档无感。
- 报告仍由 `report_generator.py` 生成（图节点 `out.report` 包装它），不重写报告模板。

---

## 4. 算子语义（工程口径）

这一节把 00 评估里的数学类比落成**可执行、可审计、可关闭**的工程语义。所有算子默认关闭或等价于现状（零回归），开启必须逐图/逐参数显式声明。

### 4.1 门控（Gating）

```text
g_m(x) = a_m(x) · normalize( w_m^user · μ_m(x) · exp(γ_m) )
a_m 可用性（Layer 0 路由 / 行业 / 生命周期 / 数据质量）
μ_m 适用度（覆盖率、可比数、现金流稳定性等连续分）
γ_m 先验 logit（默认 0，等于不改变现有权重）
```

工程规则：**用户显式权重优先**（`w_m=0` 视为禁用，门控不得复活）；`a_m=0` 时 `g_m=0` 并记录 `blocked_paths`；若所有方法都被否决，必须有兜底（`val.industry_fallback` 或区间-only），且输出 `confidence=低 + 口径=兜底`；门控输出必须进 trace（每券每方法的最终权重与理由）。

### 4.2 残差（Residual）

```text
V_out = V_base + α · (f(x) − V_base)，  α ∈ [0,1]，默认 α=0
|V_out − V_base| ≤ cap · V_base，且 V_out > 0
```

`V_base` 取行业基准（申万二级中位）或上游方法值；`α` 由配置或评论家给出，**不作为自由可学习参数**随意漂移。残差的作用是把「行业中枢 + 个股偏离」显式化，而不是让模型自由拟合。审计要求：记录 `base、α、cap、原始值、截断后值`。

### 4.3 注意力（Attention）

```text
α_ij = softmax_j( sim(i,j) / T )，sim 由行业一致、规模对数距离、增速差、盈利质量构成
V_cmp = Σ_j α_ij · multiple_j · metric_i
```

工程约束：`top_k ≤ 8`；可比数 <3 时**只出区间**（IPO 图强制），或降置信度（monitoring）；注意力权重必须落盘（可比证据链），不得出现「无法解释的加权中位数」；同一 as_of 下同券的注意力权重必须可复算。当前 `pick_peers` 的「规模对数距离取前 5」是该算子的**退化实现**（均匀权重），升级时先做等价性校验。

### 4.4 归一化（Normalization）

- 截面 winsorize（默认 5%/95%）、单位对齐（亿元、元/股、小数比率）、负值/零值处理；
- 标准化统计量必须**只用当批数据**拟合并记录（`scalers.json`），禁止用未来数据；
- 归一化必须在输出前逆变换回原单位，端口单位不得变成 z-score；
- 归一化不改变排序与掩码；若改变，视为 bug。

### 4.5 Dropout / Ensemble

- **方法 dropout**：以概率 p 丢弃方法后重池化，得到分布，用于**不确定性**（区间/置信度），不是训练技巧；默认 p=0，开启后点估计仍由全方法池化给出（除非显式配置为均值）。
- **证据 dropout**：论文与稳健性检验用，production 默认关。
- **ensemble**：多 seed / 多 prompt / 多池化的结果聚合；必须记录每个成员与聚合规则；离散度进 trace 与置信度校准。
- 成本约束：dropout 的运行次数纳入 `cost` 预算，禁止在 2,201 券上默认开启。

### 4.6 池化与区间传播

```text
线性池    V = Σ w_m V_m / Σ w_m
          区间 [Σ w_m a_m, Σ w_m b_m]
对数池    log V = Σ w_m log V_m  →  V = Π V_m^{w_m}
          区间 [exp(Σ w_m ln a_m), exp(Σ w_m ln b_m)]，要求正数（非正先 mask/nudge 并留痕）
专家乘积  V* = (Σ w_m V_m/σ_m²) / (Σ w_m/σ_m²)，1/σ*² = Σ w_m/σ_m²
          区间 V* ± z·σ*（z 由覆盖率定），方法相关时乘膨胀因子 κ
```

工程约束：缺失方法按 `renormalize` 剔除并按剩余权重再归一（与现有 `method_drop_mode=renormalize` 一致，防止综合值静默缩水）；池化输出必须落在方法值 min/max 内（线性/对数）或与乘积分布一致；三情景必须用同一池、同一权重；池化选择（`pool_choice + reason`）进 trace；默认 `linear` 作零回归基线，log/product 先进离线对比再切默认（路线第五层实验设计）。

### 4.7 指数合成（`idx.index_fit`）

沿用现有口径 A 为**零回归锚点**：

```text
P_A = P_index × Σ w_i (V_i / P_i) / Σ w_i     （指数加权；仅 ok 且权重价格为正的券）
```

V1 起增加：
- **口径 B**：对 `r_i = V_i/P_i` 做加权最小二乘（行业固定效应 + log 市值），`P_B = P × Σw·r̂/Σw`，与 A 并列，不替换；
- **三情景一致**：每券同情景值按同一权重加总，强约束 `low ≤ base ≤ high`；
- **权重口径显式**：`official | computed` 双口径并行，标 `ΔP` 敏感性；
- **交叉一致性**：上证50 ⊂ 上证180 ⊂ 上证综指，同 as_of 同券估值必须相同，点位差异应完全由权重解释，否则报警；
- **偏差分解**：`ΔP = 权重效应 + 行业/风格残差 + 个体残差`，只作诊断，不反向校正估值。

指数层不输出交易信号；输出「估值温度/偏离诊断」，措辞边界见 [04-use-cases.md](04-use-cases.md) 与 [07-compliance.md](07-compliance.md)。

---

## 5. Agentic Critic 层

评论家是**独立一层**，不是散落在 pipeline 里的 prompt 调用。定位：actor-critic / bilevel 的工程近似——专家是 actor（提议），主审是 critic（裁决/夹断），影子是反事实对照，apply 是带信赖域的更新，回滚是安全网。**不是反向传播。**

### 5.1 角色与协议

| 角色 | 输入 | 输出 | 约束 |
|---|---|---|---|
| 三专家（可比/折现/舆情） | 各自证据域 + 当前参数 + 基线估值 | 参数建议（param, delta, severity, confidence, evidence, reason） | 只看本域；不得跨域；不得看指数收盘拟合点位 |
| 主审 | 专家建议 + 合并证据 + 基线 | 逐条 accept/clamp/reject + 任务级 decision | 不新增参数；不跨域；夹断到 caps；方向自洽 |
| 影子（shadow） | 同上 | 只留痕记录，不改参数 | 与 apply 同一套提示词/门槛，保证对照可比 |
| 回写（apply） | 通过的 delta | 新输入 → 重跑 → 新中枢；失败回滚 baseline | 可行域校验（权重和=1、WACC>g）；失败零泄漏 |
| 评估 Agent（V2 新增） | 当日全部评审记录 | 参数议题聚类（方向/证据覆盖/离散度/受影响行业） | 只提议题，不代替主审裁决 |
| 台账（L5） | 裁决/审批 | 版本化参数（proposed→…→applied/superseded/rolled_back） | append-only；人工审批点；可重放 |

现有实现映射：专家/主审/影子/回写/回滚已在 `packages/batch/shadow.py`（`review()` L702、`apply_to_input()` L944、`metrics()` L1172）；参数只有当前一版在 `agent_config.py`；台账是**待新建**部分（路线第三层）。

### 5.2 把 `shadow.py` 包成 CriticModule

V5 才接评论家；旧 `shadow.py` 保持不动，只做类型适配，不做运行时依赖：

```python
class ShadowCriticAdapter(CriticModule):
    spec = ModuleSpec(id='critic.experts+main', type='critic', version='1.0',
                      status='wrap', deterministic=False, cost='llm', ...)
    def propose(self, ctx) -> list[Proposal]:      # 调 shadow.review 的专家部分
    def judge(self, proposals, ctx) -> list[Verdict]:  # 主审部分
    def commit(self, verdicts, baseline) -> Patch: # shadow.apply_to_input 的纯函数版
    def shadow(self, patch, ctx) -> Counterfactual: # 不落盘的对照结果
    def rollback(self, baseline) -> None:          # 复用 *.baseline.json 语义
```

`CritiqueRecord` 保留现有 `shadow.json` 字段（baseline/evidence/agents/expert/main/items/applied/apply/adoption），另加 `graph_run_id`、`node_params_hash`、`model/prompt_hash`、`ledger_version`，使「图级评审」与「单券评审」可互相追溯。

### 5.3 参数存储（台账）与审计（`critic.audit`）

```text
~/.dsh-valuation/ledger/<scope>.jsonl      # append-only；scope=index:sh50 | ipo:<deal_id> | global
状态机：proposed → evaluated → approved | rejected | expired → applied → superseded | rolled_back
条目：{v, parent, status, patches, source_job, evidence_refs, verdicts, approved_by, created,
       hash, prev_hash, model, prompt_hash}
```

- **批内快照不变**：每批开始时读一次，运行中的任务不受保存影响（沿用 `agent_config` 语义）。
- **跨批迭代**：次日默认读「最新 approved」；未显式指定时用台账，显式指定可回放任意版本。
- **审计**：哈希链防篡改；`approve` 需要人工动作（UI 或 API 显式参数）；回滚写 `rolled_back` 并保留原版本。
- **振荡/收敛**：连续 k 期同向且 |Δ| 递减 → converged 冻结；4 期内方向翻转 ≥2 次或 wow 中位 |Δ| 不降 → freeze + 人工，复用 `shadow.metrics` 的 `dispersion/wow/adoption`。

### 5.4 合成校准目标

没有真值，目标**只能是合成指标**，且必须显式声明、可复算：

```text
L_synth = λ1·L_consistency + λ2·L_stability + λ3·L_calibration + λ4·L_human
L_consistency：同券方法间离散度（IQR/中位）与异常跳变惩罚
L_stability ：同指数周环比参数中位 |Δ| + 方向翻转惩罚
L_calibration：区间覆盖率与宽度是否匹配分歧（无真值时为自洽校准 + 专家-人评分一致性）
L_human    ：盲评偏好/采纳率的负对数（人工采纳数据累积后启用）
exclude    ：|V − P|（价格偏离只作诊断，绝不进目标）
```

工程规则：`L_synth` 默认只用于**离线评估与提议排序**，不自动批准参数；任何自动晋级必须过人工审批点与预注册权重；权重 λ 变更视为方法学变更，需版本化与记录。

---

## 6. 两个入口

| 维度 | `monitor(index, date)` | `valuate(ipo_input)` |
|---|---|---|
| 输入 | 指数成分 + 权重 + 收盘；全市场/指数宇宙 | 单公司申报期财务、锁定可比、发行条款、行业 |
| 共享模块 | 编码层、估值模块层、门控、池化、评论家 | 同左（同一 ModuleSpec 与版本） |
| 特有节点 | `entry.monitor`、`idx.index_fit`、交叉一致性检查 | `entry.ipo`、`gate.ipo_eligibility`、`out.compliance`（发行 PE/PS 偏离、募资、流通比） |
| 输出 | 逐券区间、指数拟合点位、偏离/分解、稳定性 | 估值区间、方法分解、敏感性、可比证据链、定价约束检查（研究口径）；**不输出单一建议发行价** |
| 数据域 | 公开数据；缓存按 as_of | **公开/构造数据 demo；不做隔离**；`mode` 仅作缓存/行为开关 |
| 失败语义 | 单券 skip；整指数降级到 legacy | 单公司失败即整单失败（返回明确原因，不产出半成品） |
| 边界 | 估值温度计，不构成交易信号 | 研究参考；**demo 不做鉴权/脱敏/合规认证** |

**共享而不混同（demo 版）**：模块共享是「同一实现 + 同一版本」；`mode=monitoring|ipo` 只用于缓存/行为口径，**不是安全边界**。demo 不接真实保密材料，不做物理隔离；生产化以后再补权限/脱敏/审计。

---

## 7. API 设计

现有 3089 服务（`packages/batch/server.py`，`ThreadingHTTPServer`，无鉴权、内网）保留全部旧路由。图相关新增路由**并列**，不改旧契约：

| 方法 | 路径 | 用途 | 阶段 |
|---|---|---|---|
| GET | `/api/health` | 增加 `graph_ready`、`graph_versions` | V1 |
| GET | `/api/graphs` | 已注册图列表与版本 | V1 |
| GET | `/api/graph/spec?name=monitoring&version=1` | 返回图规范（YAML→JSON） | V1 |
| POST | `/api/graph/run` | 提交图运行；兼容 `index/weights/agent_mode` 旧字段 | V1 |
| GET | `/api/runs/<id>` | 图运行状态；与 `/api/jobs/<id>` 同构（同 id） | V1 |
| GET | `/api/runs/<id>/trace?node=&code=` | 图级 trace（节点耗时、缓存、掩码理由、证据） | V1 |
| GET | `/api/runs/<id>/nodes/<node_id>` | 层产物（`ModuleOutput` JSON） | V1 |
| GET | `/api/runs/<id>/manifest` | manifest（版本、params_hash、resume_from） | V1 |
| GET | `/api/params/ledger?scope=` | 参数台账版本列表 | V2 |
| POST | `/api/params/approve` | 人工批准某版本（写 approved_by） | V2 |
| POST | `/api/params/rollback` | 回滚到指定版本（记 rolled_back） | V2 |
| POST | `/api/ipo/valuate` | 提交单公司 IPO 估值（demo，公开/构造样例） | V4 |

**请求草图：**

```http
POST /api/graph/run
{
  "graph": "monitoring",
  "graph_version": 1,
  "mode": "monitoring",
  "params": {"index": "sh50", "as_of": "2026-11-28",
             "weights": {"dcf": 0.3, "comparable": 0.5, "sentiment": 0.2},
             "pool_mode": "linear", "critic_mode": "shadow", "seed": 42},
  "options": {"parallel": 3, "stat_n": 3000, "no_cache": false},
  "legacy_compat": {"index": "sh50", "agent_mode": "shadow"}
}
→ 200 {"run_id": "job_20261128_101500_ab12cd", "graph": "monitoring", "graph_version": 1}
```

**状态草图（与 `/api/jobs/<id>` 同构）：**

```json
{
  "id": "job_20261128_101500_ab12cd", "state": "running",
  "graph": {"name": "monitoring", "version": 1, "stage": "value",
            "nodes_done": 18, "nodes_total": 28, "degraded": false},
  "done": 50, "total": 50,
  "rows": [{"secucode": "600519.SH", "status": "ok", "weighted_mid": 20000.0,
            "interval": [18000, 22000], "confidence_level": "中",
            "trace_ref": "graph/rows/600519_SH.json"}],
  "summary": {"fitted_point": 2700.0, "scenarios": {"low": 2600, "base": 2700, "high": 2800}}
}
```

**兼容与错误语义：**

- 旧 `/api/run` 不改行为：内部映射为 `graph=monitoring, critic_mode=agent_mode`；响应仍为 `{"job_id": ...}`。前端（`packages/workbench/src/client/page/api.ts`）无需先改。
- 图模式失败仍走任务状态（`error/degraded`），不返回 5xx；提交期非法图/参数返回 400，未知 run 返回 404，未启用 IPO 图返回 404（feature flag）。
- 新增字段一律可选；旧客户端读取时忽略未知字段即可。接口无鉴权与 CORS `*` 沿用现状（仅内网）；**demo 不加入侵式鉴权**，IPO 入口也不做生产级访问控制；生产化另议。

---

## 8. 数据流（时序）

```text
monitoring：
UI POST /api/graph/run(graph=monitoring)
 → 编译 GraphSpec（拓扑/类型/requires/params → params_hash）
 → 创建 run（runtime/jobs/<id>/，写 manifest）
 → L0 编码（batch/chunk）：成分券 → 财报/行业/生命周期/成本/可比池
 → L2 门控（batch）：Layer 0 路由 → 方法可用集/权重/置信帽
 → sidecar（per_security 异步）：舆情（规则或 LLM）→ join
 → L1 估值（chunk × 方法，层间 barrier）→ 每券×每方法 ModuleOutput
 → L3 组合：归一 → 残差（α=0）→ dropout（关）→ 池化（linear）→ 区间合流
 → idx.index_fit：口径 A（+B 对照）→ 点位/三情景/交叉校验
 → L4 critic（抽样券）：专家 → 主审 → shadow/apply → 台账（V2）
 → 落盘 rows/nodes/trace → out.report（逐券 + summary.html）
 → UI 轮询 GET /api/runs/<id>（与 /api/jobs/<id> 同 id）→ 结果区不变

ipo：
POST /api/ipo/valuate(deal) → 编译 ipo 图（mode=ipo；demo 不做独立命名空间）
 → entry.ipo 校验输入 → gate.ipo_eligibility（板块/盈利/流通比/募资/截点）
 → 与 monitoring 相同的编码/估值模块（单行 Batch；可比来自 deal 锁定清单）
 → 池化/区间 → out.compliance（发行 PE/PS 偏离、募资、流通比、免责声明）
 → 报告 + 人工复核清单 → 落盘 deal 域；不写指数任务目录、不继承 monitoring 台账
```

---

## 9. 非目标、已知风险与待决

**非目标（本分支不承诺）：**

1. **完全重构**：新包不 import `valuation_engine.py`；V0 提取 golden fixtures，旧引擎只作对拍 oracle，不做运行时包装。
2. 不做端到端训练/反向传播；可微部分只做敏感度（隐式微分属于 V4 研究）。
3. 不做自动交易/自动定价；不输出单一建议发行价；不用市价当训练标签。
4. 不在本分支改生产 `pipeline.py` 主路径；图模式由开关控制，可随时回退。
5. **demo 不做权限/鉴权/多租户/脱敏**；IPO 只用公开/构造样例；生产化另议。

**已知风险：**

| 风险 | 影响 | 缓解 |
|---|---|---|
| 零回归被打破 | 数值不可信，评审否决 | V0 golden fixtures + 170 用例对拍 + 差异清单；非线性池默认关闭 |
| 层间 barrier/掩码遗漏 | 生命周期/Layer0 否决被绕开 | 约束与图级 checks；故障注入；dual 对比 |
| 评估指标自指 | 合成目标过拟合 | 预注册权重、留出专家、对抗扰动、跨指数/跨期复现 |
| LLM 非确定性/成本 | 不可复现、全市场不可行 | 抽样评审、缓存记录 prompt_hash、离线对照；不承诺逐位一致 |
| 缓存跨 as_of 污染 | 混期结果 | 缓存键含 as_of/mode；manifest 记录资源版本 |
| 图过度设计 | 维护成本 > 收益 | 模块状态诚实标注；V0 参照+新包骨架；每模块契约测试 |

**待决问题**（详见 [05](05-implementation-plan.md) 决策表）：是否引入 numpy 与列式 Batch；层间 barrier 的 chunk 粒度；池化切换由评论家还是人工；图执行器放 `packages/valuation_net/` 还是 `packages/batch/graph/`；引擎以 import 还是子进程方式被模块调用。这些问题不影响 V0（参照提取+骨架）与 V1（数据段）先行。
