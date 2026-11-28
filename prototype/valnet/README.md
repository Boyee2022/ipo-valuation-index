# valnet · VCG 最小可运行原型

> 状态：**原型 / 研究用，不进入生产**。只写 `prototype/valnet/`，不 import
> `packages/batch`，不调用网络或 LLM；运行时不修改任何生产状态。
> 对应设计文档：[docs/v2/README.md](../../docs/v2/README.md)（构想）、
> [02-architecture.md](../../docs/v2/02-architecture.md)（模块协议/执行器/算子语义）。

这是一个**纯标准库（Python 3.11+）**的最小实现，用来验证
"类型化模块 + DAG 执行器 + 门控/残差/池化 + trace" 的接口形状是否成立，
不是真实估值引擎，也不是可训练网络。

## 快速开始

```bash
cd prototype

# 单元测试（70 个，stdlib unittest）
python3 -m unittest discover -s valnet/tests -v

# 运行示例：3 家公司跑 monitoring 图，打印逐券输出、trace 与指数合成
python3 -m valnet.runner
```

测试输出末尾应为 `Ran 70 tests ... OK`（全部通过）。

## 目录与职责

```text
prototype/valnet/
  __init__.py        # 包导出（Batch / ModuleSpec / execute / pool_* ...）
  spec.py            # 类型化契约：Batch / ModuleOutput / ModuleSpec /
                     # NodeSpec / EdgeSpec / PoolSpec / GraphSpec
  graph.py           # DAG 执行器：校验、Kahn 拓扑、门控、残差、失败隔离、trace
  pooling.py         # 线性池 / 对数池 / 专家乘积；权重归一；区间/置信度合成
  modules.py         # 4 个 stub 模块：DCF / Comparable / Sentiment / IndustryBaseline
  runner.py          # 3 家合成数据、monitoring 图、逐券打印、市值加权指数合成
  tests/
    test_pooling.py  # 池化边界：归一、None 跳过、非正值报错、区间传播
    test_graph.py    # 拓扑/环/门控/残差/失败隔离/确定性/trace/数据契约
  README.md          # 本文件
```

## 架构与数据流

```text
                    Batch(ids, features, masks, meta)
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
   industry_baseline (encoder)                 dcf / comparable (valuation)
       value = industry_median                    value = 模型 stub 输出
              │                                       │
              └──────────► sentiment ◄────────────────┘
                    deps=industry_baseline
                    residual: norm(base + α · f(x)), α=0.5
                                  │
                                  ▼
                 pool(linear | log | product)
                 逐券跳过 None 成员，剩余权重再归一
                 同时合成 values / intervals / confidence
                                  │
                                  ▼
        GraphResult(values, intervals, confidence, outputs, trace)
                                  │
                                  ▼
             runner: 市值加权指数合成（演示口径，非真实点位）
```

执行器语义（`graph.execute`）：

1. `validate_graph`：节点 id 唯一、依赖存在、`edges` 与 `deps` 对账、池化成员存在；
2. Kahn 拓扑排序（按节点声明顺序确定性打破平局），有环 → `CycleError`；
3. 逐节点执行：门控值逐券为 0 的券不进入模块（只对活跃子批调用），节点级门控优先；
4. 残差节点：`bounded_residual` 做 `base + α · clip(module − base)`，区间端点同变换；
5. 节点异常（含门控异常、输出长度违约）只把该节点输出置 `None` 并记 trace，
   不中断整图；残差基线缺失时该券输出 `None`（严格传播）；
6. 池化：线性/对数/专家乘积，同时合成区间与置信度；池化输入非法抛 `GraphError`；
7. 返回不可变 `GraphResult` 与逐节点 `ExecutionTrace`（状态、门控数、残差数、
   基线缺失数、错误文本），无时间戳、无随机，同输入逐字段相等。

接口速查（详见 `spec.py` docstring）：

```python
Batch(ids, features, masks, meta)                    # 列式输入；长度构造时校验
ModuleOutput(values, intervals, confidence, evidence, diagnostics)
ModuleSpec(name, kind, version, inputs, outputs, run, gate)
NodeSpec(id, spec, deps, residual_alpha, gate)
PoolSpec(kind, weights)                              # kind ∈ linear/log/product
GraphSpec(name, nodes, edges, pool, output, version)
execute(graph, batch) -> GraphResult
```

示例 runner 的输出（节选；公司名与数值均为虚构）：

```text
[3] C003 寂野科技
    行业基准     = 36.00  区间 [30.60, 41.40]  conf=0.50
    DCF      = 33.48  区间 [26.79, 40.18]  conf=0.75
    可比       = —（节点无输出）
    舆情/残差    = 35.64  区间 [33.88, 37.40]  conf=0.35
    fair_value = 34.31  区间 [29.51, 39.11]  conf=0.60

执行 trace（拓扑顺序）
  00 industry_baseline  encoder    ok     values=3/3
  01 dcf                valuation  ok     values=3/3
  02 comparable         valuation  ok     values=2/3 gated=1
  03 sentiment          valuation  ok     values=3/3 α=0.5 residual=3
```

C003 无可比 PE：`comparable` 被 mask 门控逐券跳过，`sentiment` 回退行业中位，
池化对剩余权重（DCF 0.40 + 舆情 0.25）再归一——这正是原型要演示的跳过/兜底路径。

## 与 `docs/v2/02-architecture.md` 的对应关系

原型是 02 架构的**极简切片**：只实现 §2 协议、§3 执行器中"校验 + 拓扑 + 失败隔离"、
§4.1/4.2/4.6 三个算子与 §4.7 的退化版；L4 评论家、L5 参数台账、API 均不在范围内。

| 主题 | 02-architecture 位置 | 原型实现 | 差异 / 简化 |
|---|---|---|---|
| 分层 | §1（L0–L5） | `Batch` → `modules` → `graph` → `pool` → `runner` | 无 L4 评论家、L5 参数台账/落盘；L0 编码层用硬编码 fixture 代替 |
| 类型表达式 | §2.1 TypeExpr | `ModuleSpec.inputs/outputs` 为字符串名 | 无"语义 + 单位 + 版本"类型；执行器不做端口类型检查 |
| `ModuleSpec` | §2.2 | `name/kind/version/inputs/outputs/run/gate` | 无 `params_schema/constraints/status/schedule/cost/requires/cache/evidence`；确定性靠实现约定（无随机），无 `deterministic` 字段 |
| `Batch` | §2.3 | `ids/features/masks/meta`（列式） | 无 `rows/provenance/errors/CellError`；02 文档说列式是 V2 方向，原型直接用了列式 |
| `ModuleOutput` | §2.4 | `values/intervals/confidence/evidence/diagnostics` | 无 `node_id/module_id/params/params_hash/cache/errors/distribution/逐节点 trace`；evidence 是字符串而非 `EvidenceRecord` |
| `GraphSpec` / `NodeSpec` | §2.5 | `name/nodes/edges/pool/output/version`；节点带 `deps/residual_alpha/gate` | 无 `mode/params/requires/critic/checks/outputs`；边只按节点 id 对账，无端口粒度；残差放在节点上而非 L3 池化前 |
| 编译期 | §3.1 | `validate_graph`：唯一性、依赖、边对账、池化成员、Kahn 环检测 | 无类型检查、能力检查、参数解析、stages/barrier |
| 调度/缓存/断点/API | §3.2–3.6、§7 | 单进程、按拓扑逐节点、单次执行 | 无层间批处理、缓存、断点续跑、超时/限流、HTTP API、`runtime/jobs` 落盘 |
| 门控 | §4.1 | 门控函数返回逐券 `list[float]`，0 即跳过；mask 生成默认门控；活跃子批执行 | 只实现可用性 `a_m` 的二元版，无 `μ_m/γ_m` 软权重、`blocked_paths`、置信帽 |
| 残差 | §4.2 | `NodeSpec.residual_alpha` + `bounded_residual`：`base + α·clip(f−base)`，`cap=50%`；区间端点同变换；trace 记 α/生效数/基线缺失数 | 无参数台账/评论家给出的 α、无落盘审计字段；`cap` 是 stub 常数，非真实归一化 |
| 池化与区间 | §4.6 | `linear/log/product` 三函数 + 端点区间传播；缺失成员按剩余权重再归一 | 02 的 product 是精度加权（`1/σ²`），原型是 log-density 相乘特例；区间端点独立合成，未处理相关性与 min/max 约束；无三情景 |
| 指数合成 | §4.7 | `runner.compose_index`：逐券合成值按市值权重平均 | 不是 `P_A = P_index × Σw(V/P)/Σw` 的价格相对口径；无口径 A/B、三情景一致、交叉一致性检查 |
| 评论家 / 合规 | §5、§7 | 未实现 | 原型的非目标，见下节 |

## 关键设计取舍

1. **残差绑定在节点上，而不是单独放在池化层前**（02 §4.2 把残差列为 L3 算子）。
   原型把 `base`（唯一依赖）+ `α` 直接写在 `NodeSpec` 上，使"行业中枢 + 个股偏离"
   在图上可见、可单测、trace 可直接记录；代价是同一残差算子无法跨方法复用，
   且一条节点边既表示数据依赖又表示残差基线，语义比纯池化层方案更窄。
2. **门控在模块执行前生效（活跃子批 + 回填），而不是先全量执行再掩码**。
   执行器用 `Batch.select` 只把可用券送进模块，再用 `ModuleOutput.expand` 散射回
   整批，因此不可用券真正不消耗计算、也不会因缺失数据让整个节点异常；代价是
   门控只能是"进 / 不进"的二元决策，无法表达连续软权重。
3. **失败隔离严格到节点级，且残差节点基线缺失时输出 `None`**。
   任何节点（含门控函数、输出长度违约）的异常都只污染该节点，池化自动按剩余
   权重再归一；但残差节点不允许绕过基线直接输出模块裸值，宁可让该券缺值。
   这牺牲了 02 §2.6 允许的 legacy/行业兜底，换来"任何合成值都能解释来源"的审计性。
4. **`product` 与 `log` 在语义上强制区分**：`log` 是权重和归一的加权几何平均，
   `product` 是 `exp(Σw·ln v)`、权重不归一的专家乘积（log-density 相乘）。这样
   两者不会因为实现细节退化成同一个函数；代价是 `product` 与 02 §4.6 的精度加权
   形式不同，且当权重和恰为 1 时两者数值相同（语义仍是乘积）。

## 已知简化 / 非目标

- **无真实数据**：`runner.py` 硬编码 3 家合成 fixture（公司名、数值均为虚构），
  不接财报/行情/可比数据源，不读 `runtime/`，不 import `packages/batch`。
- **无 LLM / Agent**：无评论家、无参数评审、无 shadow/apply/回滚、无模型调用。
- **无区间相关性**：区间是模块 ±固定比例的 stub 输出；池化对上下界独立合成，
  忽略模块间相关性，因此合成区间不是严格统计意义上的覆盖区间；无 MC/分布。
- **无真实归一化**：残差 `norm` 只是相对 winsorize stub（±50%）；零/近零基线会退化。
- **门控是二元的**：只实现可用性 mask，无软权重、无 `μ/γ`、无 `blocked_paths`。
- **池化是简化版**：`log` 内部按权重和归一（02 文档假定权重已归一，此时等价）；
  `product` 未使用方差/精度，见上文取舍 4；无池化输出 min/max 约束检查。
- **指数合成不是生产口径**：`runner` 用市值加权平均逐券值演示"指数合成"，
  不是 02 §4.7 的价格相对口径，也不是真实指数点位；不输出交易信号。
- **Sentiment 公式的量纲修正**：任务 stub 写 `peer_median * (1 + adj)`；若
  `peer_median` 取 PE 中位数会得到倍数而非价格，原型因此取
  "可比法隐含估值中位" `median(peer PE) × earnings` 再乘 `(1 + adj)`，并在
  evidence/diagnostics 标注回退行业基准的家数。纯 PE 中位数版本可按需替换。
- **工程能力缺失**：无缓存、断点、超时/限流、类型表达式校验、参数解析、
  多入口（IPO 图）、落盘 trace、API/UI；图只有一个 monitoring 示例。
- **数值无金融意义**：stub 公式只用于验证管线形状，不能用于投资决策。

## 测试覆盖

- `tests/test_pooling.py`：线性池（加权、权重缩放不变、None 跳过、零/负权重、
  长度不一致、NaN）；对数池（几何平均、非正值报错）；专家乘积（与 log 区分、
  归一后等价、非正值报错）；区间传播（线性/log/product、None 跳过、端点非法报错）；
  置信度线性合成；池化方式分派。
- `tests/test_graph.py`：拓扑顺序（依赖优先、声明顺序确定性）；环/缺依赖/边不一致/
  重复节点/池化成员非法；门控（逐券跳过且模块只在子批执行、全跳过、门控异常隔离、
  门控长度违约）；残差（公式 + winsorize、区间变换、基线失败时输出 `None`、
  α 必须单依赖）；失败隔离（节点异常、输出长度违约、`log` 非正值 → `GraphError`）；
  `product` 原始权重；确定性（两次执行逐字段相等）；trace 完整（拓扑/状态/版本）；
  `Batch`/`ModuleOutput` 契约（长度、掩码、区间、置信度、select/expand）。
- 结果：70 tests，全部通过；runner 无第三方依赖、无网络、无随机，输出可复现。
