# 05 · 实施计划：V0–V4

> 状态：**规划文件（不写生产代码、不改仓库结构）**。所有阶段、周次与验收都是可评审的承诺草案，不是既定工期。  
> 前提事实：批跑基线 `d06a5ed`；技能包 `skills/llm-ipo-valuation`（SKILL v3.29.1、引擎输出 2.28.0，`smoke_test.py` 170 用例全绿）；现有 `runtime/jobs` 状态语义与报告链路见 [docs/spec/01-architecture.md](../spec/01-architecture.md)。  
> 架构与模块清单见 [02](02-architecture.md)、[03](03-module-catalog.md)；图实例见 [`graphs/monitoring.yaml`](graphs/monitoring.yaml)、[`graphs/ipo.yaml`](graphs/ipo.yaml)。

---

## 0. 总览

### 0.1 阶段与周数

| 阶段 | 周数 | 目标（一句话） | 关键交付 | 回滚手段 |
|---|---|---|---|---|
| **V0** 基线固化 | **3 周**（W1–W3） | 把现有引擎包成 `LegacyModule`，数值零回归 | 快照基线 + LegacyModule + 图协议 v1 + dual diff 脚本 | 无运行路径变更 |
| **V1** 图执行器 + 模块注册 + 池化 | **5 周**（W4–W8） | 图能跑 monitoring，先接 3 个真模块，其余 adapter；三池可切 | 执行器/注册表/缓存/断点 + 3 模块 + 3 池 + 7 条图/运行 API | `graph_mode=off` 回 legacy |
| **V2** Agentic Critic 层 + 台账 + 合成目标 | **5 周**（W9–W13） | 评论家独立成层，参数可跨批迭代、可回滚、可评估 | critic 适配层 + 台账 + evaluator + 合成目标 + 3 条 API | `critic_mode=off`；台账只读 |
| **V3** 双模式（monitoring / IPO）+ 数据域/合规 | **7 周**（W14–W20） | IPO 单公司入口与合规输出；两域隔离 | ipo 图 + IPO schema + 门控 + 合规输出 + 域隔离 | IPO feature flag 关闭 |
| **V4** 架构搜索/可微模块（研究） | **6 周**（W17–W22，可与 V3 后段并行） | 离散搜索与可微模块的离线实验 | `research/` 包、实验报告、评估协议 | 不进生产路径 |

**主路径（V0–V3）20 周**；V4 是研究线，6 周，可在 V3 后段并行，不阻塞交付。若资源只够一组人，V4 整体后置——它是论文扩展，不是工程必需。

### 0.2 与 `docs/03-engineering-roadmap.md` 的对齐

| VCG 阶段 | 路线里程碑 | 关系 |
|---|---|---|
| V0 | M0 基线固化（W1–W2） | 直接复用；VCG 额外增加「图协议冻结 + LegacyModule 包装」约 1 周 |
| V1 | M1 解耦向量化（W3–W6）+ M4 的池化/指数拟合（W14–W17 提前） | 路线 M1 提供向量化 kernel 与宽表；这里包成图节点；三池与 `index_fit` 口径 B 并入 V1 后半 |
| V2 | M3 Agent 迭代（W10–W13）+ M2 的表达（trace 部分） | 台账/评估/振荡直接复用路线第三层；trace schema 在 V1 已最小化，V2 补齐可视化契约 |
| V3 | 路线无直接对应 | 双模式/IPO 是 v2 新增范围（路线只覆盖 monitoring 五指数）；依赖 V1/V2 的图与评论家 |
| V4 | 路线决策点 1/2/3 的实验化 | 向量化粒度、barrier、池子选择的可学习化，属研究 |

也就是说：**V0–V2 约 13 周与路线 M0–M3 基本重合**，不是另起一套；差异是 V1 把 M4 的部分提前，V3 是新增的 7 周。两份文档若冲突，以本文件的阶段验收为准，路线文件提供算法与指标细节。

### 0.3 全局纪律（每个阶段都适用）

1. **数值零回归优先于新功能**：任何改动先证明「不改数值」，再谈开关；线性池 + legacy 适配必须逐位一致（|Δ|≤1e-9）。
2. **只增不改**：`runtime/jobs` 目录、`state.json` 字段、旧 API 路由都只增字段/新目录；旧任务能读、旧客户端能跑。
3. **状态诚实**：代码没写完的模块在目录里标 `wrap/new/proposed`；文档不把设计写成已实现。
4. **可回滚**：每个阶段有开关与回滚点；回滚验证本身是验收项。
5. **测试资产先行**：V0 的快照与 170 用例是所有后续阶段的裁判；没有快照不许合并 V1。

---

## 1. 推荐仓库结构与依赖策略

**不实际创建**，以下仅为 V0/V1 落地时的建议结构：

```text
packages/
├── valuation_net/                    # 新包（V0 起；目录名用下划线保证可 import）
│   ├── __init__.py
│   ├── core/
│   │   ├── types.py                  # TypeExpr / Batch / ModuleSpec / ModuleOutput / GraphSpec / NodeSpec / EdgeSpec
│   │   ├── registry.py               # 模块注册表 + 能力探测
│   │   ├── validate.py               # 图编译：拓扑/端口/类型/约束/参数解析
│   │   ├── executor.py               # 阶段/barrier/chunk/per_security/timeout/retry
│   │   ├── cache.py                  # 内容寻址缓存（含 as_of/domain）
│   │   ├── checkpoint.py             # manifest / resume_from / 原子提交
│   │   ├── interval.py               # 区间传播（线性/对数/乘积）
│   │   └── errors.py                 # CellError / NodeUnavailable / Degraded
│   ├── adapters/
│   │   └── batch_universe.py        # V0：包装 packages/batch/input_builder 的逐券/宽表适配
│   ├── modules/
│   │   ├── legacy.py                 # LegacyModule（V0）：包住现有引擎
│   │   ├── enc/ val/ gate/ pool/     # 按 03 目录逐层落
│   │   └── entry/ out/
│   ├── critic/
│   │   ├── adapter_shadow.py         # 包装 packages/batch/shadow.py
│   │   ├── ledger.py evaluator.py objective.py oscillation.py
│   ├── store/ledger_store.py         # 仓库外台账读写（追加式 + 哈希链）
│   ├── schemas/
│   │   └── ipo_input.v1.json        # V3：IPO 输入 schema
│   ├── graphs/
│   │   ├── monitoring.yaml           # V1 从 docs/v2/graphs 复制并冻结
│   │   └── ipo.yaml                  # V3
│   └── tests/
│       ├── test_types.py test_validate.py test_executor.py test_resume.py
│       ├── test_modules_*.py test_pool.py test_critic.py
│       └── golden/                   # 小快照入 git；大快照 runtime/baseline/
└── batch/
    ├── graph_bridge.py               # V1 薄适配：server → valuation_net
    └── server.py                     # 只增路由（/api/graph/*、/api/runs/*、/api/params/*）
```

**为什么独立成包而不是 `packages/batch/graph/`**：

- `packages/batch/` 是扁平脚本目录（`import config`、`import dsources`），没有包边界；把图代码塞进去会让「import 副作用 + 相对路径」更难测试。独立包有明确 `__init__.py`，可被 `pytest`、技能脚本、未来 CLI 复用。
- 回滚干净：`graph_mode=off` 时新包完全不被加载，batch 旧路径零影响。
- 若仓库治理只允许一个包，退路是 `packages/batch/graph/`，但必须保证 `graph_bridge` 单向依赖、不回引 `pipeline`。

**依赖策略**：V0/V1 **仅标准库**（与技能包「纯标准库」一致，部署无需新依赖）；V2 起允许 `numpy` 作为**可选**依赖用于 MC/池化向量化（路线决策点 1 的 C 方案：基础层可用 numpy，非基础层纯 Python），但 `valuation_net` 在无 numpy 环境必须能降级运行。不引入 pandas/scipy 作为硬依赖。

---

## 2. V0 · 基线固化（W1–W3，3 周）

### 2.1 目标

把「现有引擎 + 输入组装 + 统计 + 报告」包进图的第一个模块，证明**图能表达现有系统且数值零回归**；冻结图协议 v1 与测试快照，为 V1 提供裁判。

### 2.2 改动文件 / 新目录

| 类型 | 路径 | 内容 |
|---|---|---|
| 新增 | `packages/valuation_net/core/types.py` | 协议 dataclass（02 §2）；先最小字段集，允许后续只增 |
| 新增 | `packages/valuation_net/modules/legacy.py` | `LegacyModule`：输入 `Financials/Comparables/...` 或直接 `legacy_input`，输出既有 `out.json` 的 `synthesis/confidence/warnings`，附 `ModuleOutput` 外壳 |
| 新增 | `packages/valuation_net/adapters/batch_universe.py` | 包装 `input_builder.build_input`：逐券调用 vs 宽表两模式，V0 只做逐券 |
| 新增 | `packages/valuation_net/tests/` | 协议/适配层测试；`golden/` 放 11 组 examples 的输入/输出摘要 |
| 新增 | `runtime/baseline/<tag>/`（不入 git） | 技能 `examples/` 输出快照 + hash；sh50 一次真实跑批的逐券 `out.json` 摘要 |
| 新增 | `scripts/dual_diff.py`（建议） | 同 as_of / 同参数跑 legacy 与图模式，逐券逐字段 diff，输出 CSV/JSON 报告 |
| 不改 | `pipeline.py`、`server.py`、`shadow.py`、`agent_config.py` | V0 不动主路径 |

### 2.3 API

- 不新增写路由；可选只读 `GET /api/graph/spec`（返回冻结的图 JSON）用于内部演示，默认关闭。
- `POST /api/run` 行为不变；`state.json` 不变。

### 2.4 测试

1. `smoke_test.py` **170 用例**全绿（命令与结果记入 `runtime/baseline/<tag>/README`）。
2. 11 组 `examples/` 全量重算，与快照逐字段 diff = 0（数值 ≤1e-9，字段集合一致）。
3. `LegacyModule` 对 examples 的输出与引擎直接调用逐位一致。
4. dual diff：sh50 同 as_of 同参数跑两遍，逐券 `weighted_mid/interval/confidence` diff = 0。
5. `types.py` 契约测试：非法端口/单位/版本被拒。

### 2.5 验收指标

- 快照可复算：同一 tag 两次重算 hash 一致；
- 170 用例全绿、examples diff = 0、dual diff = 0；
- 无生产路径变更（`git diff` 不触及 `pipeline/server/shadow/agent_config` 运行逻辑）；
- 图协议 v1 评审通过（字段冻结，后续只增）。

### 2.6 风险与回滚

- **风险**：快照本身不稳定（数据源漂移）→ 快照必须记录 as_of 与数据源版本，只用于「同输入」比对，不用于跨日比对；`LegacyModule` 子进程超时/错误语义与现有一致。
- **回滚**：V0 没有运行路径变更，回滚 = 删除新包；快照目录保留。

---

## 3. V1 · 图执行器 + 模块注册 + 池化（W4–W8，5 周）

### 3.1 目标

图能端到端跑 monitoring（先只接 3 个真模块：`val.dcf`、`val.comparable`、`val.sentiment`，其余用 `LegacyModule`/adapter 占位），支持**线性/对数/专家乘积**三池与区间传播；执行器具备缓存、断点、部分失败、超时、确定性；API 与 3089 兼容。

### 3.2 改动文件 / 新目录

| 类型 | 路径 | 内容 |
|---|---|---|
| 新增 | `core/validate.py`、`core/registry.py` | 图编译、端口/类型/参数/能力校验 |
| 新增 | `core/executor.py` | 拓扑/阶段/barrier/chunk/per_security/timeout/retry/隔离 |
| 新增 | `core/cache.py`、`core/checkpoint.py` | 内容寻址缓存；manifest 与 resume |
| 新增 | `core/interval.py` | 三池区间传播与 hull/单调校验 |
| 新增 | `modules/enc/financials.py`、`modules/enc/peers.py`（最小）、`modules/val/dcf.py`、`modules/val/comparable.py`、`modules/val/sentiment.py` | 前 3 个真模块 + 依赖的最小编码器；其余 `modules/legacy.py` 兜底 |
| 新增 | `modules/pool/linear.py`、`log.py`、`product.py` | 三池；线性池对齐引擎 `synthesis` |
| 新增 | `graphs/monitoring.yaml` | 从 `docs/v2/graphs/monitoring.yaml` 复制并冻结（加同步测试） |
| 新增 | `packages/batch/graph_bridge.py` | server → executor 的薄适配；任务目录兼容 |
| 修改 | `packages/batch/server.py` | 只增 `/api/graph/*`、`/api/runs/*` 路由组（7 条）；旧路由不动 |
| 修改 | `packages/batch/pipeline.py` | 仅在 `graph_mode` 分支调用 bridge；默认关闭 |
| 新增 | `runtime/jobs/<id>/graph/` | manifest/nodes/rows/trace（只增目录） |
| 参照 | `prototype/valnet/`（不新增、不修改） | 同批原型：协议/执行器/三池已跑通（70 单元测试），作为 V1 的接口形状参照，不接生产、不 import batch |

### 3.3 API（草图见 02 §7）

- `POST /api/graph/run`：`{graph, graph_version, params, options, legacy_compat}` → `{run_id}`。
- `GET /api/graphs`、`GET /api/graph/spec?name=monitoring&version=1`。
- `GET /api/runs/<id>`：与 `/api/jobs/<id>` 同 id、同构；新增 `graph` 摘要字段。
- `GET /api/runs/<id>/trace`、`GET /api/runs/<id>/nodes/<node_id>`、`GET /api/runs/<id>/manifest`。
- `GET /api/health` 增加 `graph_ready`、`graph_version`。

### 3.4 测试

| 类别 | 用例 |
|---|---|
| 契约 | 每个注册模块：端口/类型/约束/输出 schema；图 YAML 编译与端口对账（本仓库两份 YAML 的校验脚本可复用） |
| 零回归 | sh50 `pool=linear` 与 V0/legacy 逐券 `weighted_mid/interval/confidence` \|Δ\|≤1e-9；DCF/可比/舆情三模块方法值逐位一致 |
| 池化 | 三池可切换；线性零回归；对数池负值/缺失 mask；乘积池无 σ 时拒绝启用；区间包含中枢、单调 |
| 故障注入 | 缺财报 / 无可比 / 负值 / 超时四类：只掩码目标券，整批继续（路线 6.2） |
| 断点 | 杀进程重启 → `interrupted` → 从最后完整 chunk 续跑，已完成 chunk 不重算 |
| 确定性 | 同输入同 seed 两次运行，纯函数节点输出逐位一致；LLM 节点记录随机源 |
| 缓存 | 同 as_of 命中、跨 as_of 不命中、跨 domain 不命中 |
| 兼容 | 旧 `runtime/jobs` 任务可读；旧 `/api/run` 响应不变；旧前端 2.5s 轮询可完成 |

### 3.5 验收指标

- sh50 线性池零回归（逐位）；三池可复算且可切换；区间单调且包含中枢；
- 四类故障注入只影响 1 券；杀进程可续跑（已完成 chunk 不重算）；
- trace 覆盖率：`ok` 券 100%（节点、参数、掩码理由、缓存命中）；
- 旧任务/旧接口兼容通过；`graph_mode=off` 时行为与今天逐位一致；
- 性能基线（路线 §5）：单券耗时、批总时长、峰值 RSS 首次可测（不承诺 V1 即达标，先建立分母）。

### 3.6 风险与回滚

- **风险**：零回归（最高）；生命周期/Layer0 否决在掩码化时漏判；内存峰值（chunk 太小/太大）；trace 体积膨胀；子进程模式下每模块启动开销反而更大。
- **缓解**：dual 逐位 diff；四类故障注入；chunk=200 起步并实测；trace 独立文件 + 截断策略；V1 前半继续用子进程，后半评估 import 化（决策点 5）。
- **回滚**：`graph_mode=off` 一行开关回 legacy；`graph/` 目录按 job 隔离，删除不影响旧任务；池化默认 `linear`，log/product 仅显式开启。

---

## 4. V2 · Agentic Critic 层 + 参数存储 + 合成目标（W9–W13，5 周）

### 4.1 目标

把现有 `shadow.py` 的评审流程包成**独立评论家层**，新增跨批参数台账、评估 Agent、合成目标与振荡/回滚；评论家只动参数、不动数值算法，且默认仍然保守（shadow 优先，apply 需显式开启 + 人工审批）。

### 4.2 改动文件 / 新目录

| 类型 | 路径 | 内容 |
|---|---|---|
| 新增 | `critic/adapter_shadow.py` | 包装 `shadow.review/apply_to_input/metrics`；`CritiqueRecord` 增加 `graph_run_id/params_hash/model/prompt_hash/ledger_version` |
| 新增 | `critic/ledger.py`、`store/ledger_store.py` | 台账状态机、append-only JSONL、哈希链、审批、回滚、scope（index/ipo） |
| 新增 | `critic/evaluator.py` | 议题聚类、覆盖家数、离散度、受影响行业 |
| 新增 | `critic/objective.py` | 四项合成目标（一致性/稳定/校准/人评）；断言不含 \|V−P\| |
| 新增 | `critic/oscillation.py` | 收敛/振荡判定（复用 `shadow.metrics` 的 dispersion/wow/adoption） |
| 修改 | `packages/batch/server.py` | 3 条 `/api/params/*` 路由；`/api/graph/run` 的 `critic_mode` |
| 不改 | `packages/batch/shadow.py`、`agent_config.py` 的运行逻辑 | 适配层不改协议；`agents.json` 仍是当前批参数真源，台账是跨批增量 |
| 新增 | `~/.dsh-valuation/ledger/<scope>.jsonl`（仓库外） | 参数版本；不入 git、不含密钥 |

### 4.3 API

- `GET /api/params/ledger?scope=index:sh50` → 版本列表（v/status/created/source_job/approved_by/hash）。
- `POST /api/params/approve {scope, version, by}` → 状态推进（人工审批点）。
- `POST /api/params/rollback {scope, version}` → `rolled_back` + 新条目。
- `POST /api/graph/run` 的 `critic_mode ∈ {off, shadow, apply}`；apply 在 IPO 域强制人工复核。

### 4.4 测试

- 台账：给定版本完整还原参数；状态机非法迁移被拒；哈希链校验；scope 隔离。
- 次日默认：跑批不显式指定参数时读到「最新 approved」（自动化测试）。
- 回滚：apply 失败 → baseline 恢复零泄漏；台账 `rolled_back` 可重放。
- 振荡：构造 4 期方向翻转序列 → 触发 freeze；连续同向 |Δ| 递减 → converged。
- 合成目标：四项指标可复算；断言不含价格项；权重变更版本化。
- 评审兼容：`shadow.json` 字段与现有逐字段一致（adapter 不破坏现有前端 `Shadow.tsx`/`AgentsPage.tsx` 读取）。

### 4.5 验收指标

- 台账可重放（给定 v 能还原参数与来源）；
- 次日默认 = 最新 approved（测试固化）；
- apply 回滚零泄漏；振荡检测用例触发；
- 评审记录字段兼容率 100%（旧前端可读）；
- 过程指标（`shadow.metrics`）与新增 evaluator 指标对账一致；
- 成本：每券 token 成本、评审覆盖率、抽样比例入指标。

### 4.6 风险与回滚

- **风险**：LLM 非确定性/模型漂移（记录 model/prompt_hash，温度固定）；自指偏差（专家证据同源）；台账安全（仓库外文件、append-only、审批人）；参数漂移（信赖域 + 振荡冻结）；成本失控（抽样 + 并发上限）。
- **回滚**：`critic_mode=off` → 评论家整层跳过；台账只读；`agents.json` 继续作为当前批参数真源；删除台账不影响历史 `shadow.json`。

---

## 5. V3 · 双模式（monitoring / IPO）+ 数据域/合规（W14–W20，7 周）

### 5.1 目标

新增 `valuate(ipo_input)` 单公司入口与 `ipo` 图，输出估值区间、方法分解、敏感性、可比证据链、定价约束与合规声明；与 monitoring 共享模块，但**数据域、台账、缓存、报告物理/逻辑隔离**。**不输出单一建议发行价，不输出交易信号。**

### 5.2 改动文件 / 新目录

| 类型 | 路径 | 内容 |
|---|---|---|
| 新增 | `modules/entry/ipo.py`、`schemas/ipo_input.v1.json` | IPO 输入 schema（公司、申报期财报、锁定可比、发行条款、板块）与校验 |
| 新增 | `modules/gate/ipo_eligibility.py` | 板块条件、流通比、募资、信息可得性截点；规则来自 `assets/ipo_rules_checklist.md` |
| 新增 | `modules/out/compliance.py` | 定价约束/合规输出（发行 PE/PS 偏离、募资、流通比、免责声明、人工复核清单） |
| 新增 | `graphs/ipo.yaml` | 从 `docs/v2/graphs/ipo.yaml` 复制冻结 |
| 修改 | `packages/batch/server.py` | `POST /api/ipo/valuate`（feature flag 控制，默认 404） |
| 修改 | `core/cache.py`、`store/ledger_store.py` | `domain` 字段强制；跨域拒绝；IPO 存储独立子目录与权限 |
| 修改 | `out/report.py` | IPO 报告模板与合规区块；monitoring 报告不变 |
| 新增 | `docs/spec/ipo-input.md`（后续） | 输入字段与口径说明（V3 交付，不属本分支） |

### 5.3 API

- `POST /api/ipo/valuate {deal_id, as_of, graph, params, input}` → `{run_id}`；输入 schema 校验失败 400。
- `GET /api/runs/<id>` 同构；`domain=ipo` 字段可见。
- 合规输出随报告与 JSON 落盘；`out.compliance` 字段固定（见 ipo.yaml `outputs`）。
- 访问控制：部署层实现（至少内网 + 简单 token/来源白名单）；**无鉴权现状不能直接承载 IPO 保密数据**，这是 V3 的硬前置。

### 5.4 测试

- schema：必填缺失/财务期晚于 as_of/发行条款缺失 → 拒绝，不补默认值。
- 端到端：1 个 IPO 样例（脱敏）跑通 ipo 图 → 区间/分解/敏感性/证据链/定价约束齐备。
- 隔离：IPO 写 `runtime/jobs/<id>` 但 `domain=ipo` 子命名空间；缓存不跨域；台账 scope `ipo:<deal_id>` 不读 monitoring；monitoring 跑批不读 IPO 数据。
- 合规：禁用词检查（单一建议发行价/买卖建议）；免责声明必含；发行 PE/PS 偏离阈值按清单；人工复核清单可导出。
- 回归：monitoring 全部旧用例继续通过（IPO 改动不得影响 monitoring）。

### 5.5 验收指标

- ipo 图 `checks` 全过（单点发行价禁止、弱可比只出区间、截点违规阻断、无价格泄漏）；
- 域隔离测试 100% 通过（双向）；
- 报告机检（`html_check.py`）通过，合规区块存在；
- monitoring 零回归（V1 验收项复跑）；
- 合规评审：合规/法务对「输出措辞与禁用项」签字（流程项，非代码）。

### 5.6 风险与回滚

- **风险**：保密与公平（隔离与访问控制不到位）；监管口径（发行定价、静默期、利益冲突披露）；范围蔓延（把 IPO 做成自动定价）；数据口径（申报期 vs 上市后）。
- **回滚**：IPO feature flag 关闭 → 路由 404、ipo 图不注册、monitoring 完全不受影响；数据/台账目录保留但不再写入。

---

## 6. V4 · 架构搜索/可微模块（研究线，6 周，W17–W22 可并行）

### 6.1 目标

在**离线、可复现、不进生产**的前提下研究三件事：门控/模块集/池化的**离散、受约束搜索**；可微模块的敏感度（隐式微分/可微编程）；monitoring ↔ IPO 的跨域迁移。产出论文实验与评估协议，不产出生产代码路径。

### 6.2 交付物 / 目录

- `research/` 独立目录（或独立分支）：搜索脚本、实验配置、结果表、负结果记录；
- 实验注册表：每个实验固定「数据 as_of、参数、seed、评估口径」，可重放；
- 评估协议草案（与 [06-evaluation.md](06-evaluation.md) 对齐）：合成基准、盲评、消融、下游任务；
- 可微模块原型：只做 DCF/可比的可微近似与敏感度对照，不承诺全图可微。

### 6.3 验收与退出条件

- 实验可重放（同配置同 seed 同结果）；每个结论有消融或对照；
- 搜索空间受约束（权重和、WLS 可行性、caps），不做无约束「调参」；
- 负结果如实记录；不以「更贴近指数收盘」作为优越性证据；
- 任何成果进入生产必须重新走 V1–V3 的零回归与审计门槛；
- 退出条件：连续 2 个实验周期无可复现增益 → 冻结研究线，结论归档。

### 6.4 风险

过拟合合成目标；架构搜索的可解释性；可微近似与真实引擎数值漂移；研究代码泄漏到生产路径。回滚：研究目录不进生产 import 图，物理隔离即可。

---

## 7. 测试矩阵与验收指标

| 指标 | 定义 | 现状 | V0 | V1 | V2 | V3 |
|---|---|---|---|---|---|---|
| 170 用例 | `smoke_test.py` 全绿 | 170 全绿（3.9s） | 必须保持 | 必须保持 | 必须保持 | 必须保持 |
| 数值零回归 | 对基线快照 max\|Δ\| | 基线未固化 | 固化 | 线性池逐位 | 参数改动仅 apply | monitoring 复跑 |
| 覆盖率 | `ok/total` | 待测 | 记录 | ≥ 基线 | ≥ 基线 | ≥ V1 |
| 跳过率 | `skip/total` 按原因 | 待测 | 记录 | ≤ 基线 | ≤ 基线 | ≤ V1 |
| 单券耗时 | 中位/p95 | 无计时字段 | 基线 | 建立分母 | — | — |
| 内存峰值 | 服务 RSS | 待测 | 基线 | ≤1.5× | — | — |
| trace 覆盖 | ok 券有节点/参数/掩码理由 | 无 | — | 100% | 评论家字段 100% | IPO 100% |
| 台账可重放 | 给定 v 还原参数 | 无 | — | — | 通过 | 通过 |
| 次日默认 | 跑批读最新 approved | 无 | — | — | 通过 | 通过 |
| 采纳率 | adopted/(adopted+rejected) | 有字段无历史 | — | — | ≥60% 且不低于基线 | 分域统计 |
| 参数稳定 | wow 中位\|Δ\|、翻转率 | 有 wow 字段 | — | — | \|Δ\| 递减、翻转≤1/4 期 | 分域 |

**各阶段通用门槛**：契约测试全绿；故障注入只影响目标券；回滚开关验证通过；旧任务/旧接口兼容测试通过；文档与代码状态一致（`existing/wrap/new/proposed` 不得漂移）。

---

## 8. 风险登记与回滚矩阵

| 风险 | 阶段 | 触发信号 | 缓解 | 回滚 |
|---|---|---|---|---|
| 数值零回归被打破 | V0–V1 | dual diff ≠0、examples diff ≠0 | 只移位置不改算法；逐位 diff 阻断发布；线性池默认 | `graph_mode=off` |
| 掩码化漏判路由 | V1 | 跳过率上升、置信度异常 | Layer0/生命周期用例、四类故障注入、dual 对比 | 回 legacy |
| 内存/性能不达标 | V1 | RSS、单券耗时 | chunk=200 实测、trace 截断、子进程/import 二选一 | chunk 调参 / 关闭缓存 |
| LLM 非确定性/成本 | V2 | 重复评审 Δ 不一致、token 成本 | 固定温度/记录 prompt_hash、抽样、并发上限 | `critic_mode=off`/抽样比例调低 |
| 合成目标过拟合 | V2/V4 | 离线指标好、盲评不升 | 预注册权重、留出专家、负结果、跨期复现 | 目标仅评估、不参与晋级 |
| 台账安全/漂移 | V2 | 版本跳跃、未审批 applied | 哈希链、审批点、信赖域、振荡冻结 | 回滚版本 + `agents.json` 兜底 |
| IPO 保密/合规 | V3 | 跨域读写、措辞违规 | 域隔离、访问控制、合规评审 | IPO flag 关闭 |
| 研究与生产混淆 | V4 | research 代码被 import | 物理隔离、依赖检查 | 研究目录不入生产依赖 |

---

## 9. 决策点

路线文件列出 5 个决策点；本计划在其上补 2 个。每项给出倾向，**未拍板不阻塞 V0**。

| # | 决策点 | 选项 | 倾向 | 决策阶段 |
|---|---|---|---|---|
| 1 | 向量化粒度 | A numpy/pandas；B 只做进程复用与批量 IO；C 混合 | **C**（基础层可 numpy，非基础层纯 Python） | V1 前 |
| 2 | 层间 barrier | A 全量；B chunk 内 barrier + 层内流水 | **B（chunk=200）** | V1 前 |
| 3 | 池子切换由谁决定 | A 评估 Agent 提议 + 主审复核；B 人工固定；C 逐指数固定 + 异常提议 | **A（附人工确认）**，默认 linear | V2 |
| 4 | Agent 迭代频率 | A 每日；B 每周；C 事件驱动 | **A，周频回退** | V2 |
| 5 | 技能拆分边界 | A 一次拆 8 模块；B 单体 + 适配层；C 先可 import 接口 | **C 起步** | V1–V3 持续 |
| 6 | 图代码放哪 | A `packages/valuation_net/`（下划线，可 import）；B `packages/batch/graph/` | **A**（独立包、回滚干净） | V0 前 |
| 7 | API 形态 | A 新增 `/api/graph/*` 与 `/api/runs/*`；B 直接扩 `/api/run` | **A 并存**（旧路由不动，`run_id=job_id`） | V1 前 |
| 8 | 引擎调用方式 | A 子进程（现状）；B import 纯函数；C 混合（V1 子进程，V2 起 import 化） | **C**（先保零回归，再谈性能） | V1 后半 |

---

## 10. 本计划不做什么

1. **不写生产代码**：本文与 02/03 是设计文档；V0 起才动代码，且每阶段独立评审与回滚。
2. **不重写引擎**：`valuation_engine.py` 只被包装，不被改写；技能拆分按 `docs/spec/05` 的「先接口后实现」推进。
3. **不训练神经网络、不做反向传播**：可微部分只在 V4 做敏感度研究。
4. **不自动交易、不自动定价、不输出单一建议发行价**。
5. **不改现有 `runtime/jobs` 语义**：只增 `graph/` 目录与字段；旧任务永远可读。
6. **不承诺 V4 进生产**：研究线的成果要重新过 V1–V3 的门槛。
