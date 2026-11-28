# 05 · 实施计划：Demo 优先 + 完全重构（V0–V4）

> **2026-11-28 修订**：以 [08-demo-first-revision.md](08-demo-first-revision.md) 为准。  
> 本轮 demo：**不鉴权、不脱敏、不做数据域隔离/合规认证**；只做公开/构造数据。  
> **完全重构**：现有技能只作公式/行为参照与回归 oracle；新系统在 `packages/valuation_net/` 从零实现，不做 legacy 运行时包装。  
> 执行架构：**A 数据 → B 模型加载 → C 批处理/断点 → D 指数拟合**；模块常驻，批跑完退出。

---

## 0. 总览

### 0.1 阶段与周数

| 阶段 | 周数 | 目标 | 关键交付 | 回滚/验收 |
|---|---|---|---|---|
| **V0** 参照与骨架 | 2 周（W1–W2） | 从技能提取公式/参数/样例；搭新包骨架 | golden fixtures、`ModuleSpec/Batch/ModuleOutput/GraphSpec`、差异清单 | 旧技能不被修改；fixtures 可追到来源 |
| **V1** 数据段 A | 3 周（W3–W5） | 公开数据收集/标准化/缓存 | 源适配器、宽表/列式缓存、manifest、缺失掩码 | 同 as_of 可复现；数据缺口可解释 |
| **V2** 模型加载 B | 3 周（W6–W8） | 模块注册、参数包、常驻 worker | DCF/DCM/可比/舆情/RIM/门控/池化；健康检查；加载失败隔离 | 换模块不改 A/C/D；模块可单独测试 |
| **V3** 批处理 C | 4 周（W9–W12） | 向量化 + 断点恢复 | chunk 调度、原子落盘、manifest、resume、失败隔离 | 中断后续跑；已完成 chunk 不重算 |
| **V4** 指数拟合 D | 3 周（W13–W15） | 选指数/权重/池化/点位/报告 | 五指数图、三情景、诊断、逐券 trace | 点位与逐券可追溯；同输入同输出 |
| **V5** 评论家/校准（研究） | 并行 4 周 | 迭代与鲁棒 | shadow/apply、参数台账、合成目标、缓存/一致性 | 结论稳定率、采纳率；不阻塞 V0–V4 |

**主路径 V0–V4 = 15 周**；V5 是论文/研究线，可与 V3/V4 并行。比旧计划少 5 周：砍掉鉴权/数据域/合规，V0 不再包 legacy，改为参照提取。

### 0.2 三条硬约束

1. **完全重构**：新包不 import 旧 `valuation_engine.py`；旧技能只用于生成 golden fixtures 与对拍。
2. **模块常驻**：B 段加载模块/参数/worker，C 段批量执行，结束后退出；禁止每券重复初始化。
3. **断点是一等公民**：C 段每个 chunk 原子落盘 + manifest；恢复不依赖内存状态。

---

## 1. 推荐仓库结构

```text
packages/
└── valuation_net/                  # 新包（完全重构）
    ├── __init__.py
    ├── core/
    │   ├── types.py                # Batch / ModuleSpec / ModuleOutput / GraphSpec
    │   ├── registry.py             # 模块注册/加载/健康检查
    │   ├── params.py               # 参数包、版本、快照
    │   └── errors.py               # CellError / ModuleError / GraphError
    ├── stages/
    │   ├── a_data.py               # 数据收集/标准化/缓存/manifest
    │   ├── b_model.py              # 模块加载/依赖图/worker 池
    │   ├── c_batch.py              # chunk/向量化/断点/恢复
    │   └── d_index.py              # 指数选择/池化/拟合/报告
    ├── modules/
    │   ├── dcf.py
    │   ├── dcm.py
    │   ├── comparable.py
    │   ├── sentiment.py
    │   ├── rim.py / ddm.py
    │   ├── gates.py
    │   └── pooling.py
    ├── critic/                     # V5：专家/主审/shadow/apply/台账
    └── tests/
```

- 旧 `packages/batch` 继续服务现有 demo；新包独立，通过 CLI/API 接入，不改旧路由。
- 依赖策略：**基础数值层允许 numpy**（向量化收益明确）；核心协议/测试保持纯标准库可跑；舆情/LLM 走异步/线程池。
- 不引入 pandas/数据库作为第一版依赖；宽表用 numpy structured array 或列式 dict，后续再评估 Arrow/Parquet。

---

## 2. 阶段细节

### V0 · 参照与骨架（2 周）

**目标**：把“参考技能”变成可验证的参照物，而不是运行时依赖。

工作：

- 从 `skills/llm-ipo-valuation` 提取：DCF/DCM/可比/舆情/RIM 的公式、默认参数、边界条件、报告字段；生成 `tests/fixtures/` 的 golden inputs/outputs。
- 写 `core/types.py`：`Batch`（ids/features/masks/meta/provenance）、`ModuleOutput`（values/intervals/confidence/evidence/trace）、`ModuleSpec`（kind/inputs/outputs/params/version/health）、`GraphSpec`。
- 写 `registry.py` 的最小实现：注册、查找、版本、加载失败隔离。
- 生成“旧 vs 新”差异清单：哪些公式保留、哪些有意改、哪些暂不支持。

验收：

- 旧技能样例可被新 `Batch` 读取；fixtures 可追溯到技能版本/文件行。
- 新包可 `python -m valuation_net --help`；不 import 旧引擎。
- 差异清单进 `docs/v2/09-reference-diff.md`（V0 产出）。

回滚：无运行路径变更；只新增包与 fixtures。

### V1 · 数据段 A（3 周）

**目标**：公开数据 → 标准化宽表 → 可复现 manifest。

工作：

- 源适配器：东财指数成分/财务/F10/行业估值、腾讯行情、东财新闻/股吧；统一 `as_of`、单位、缺失码。
- 宽表：`UniverseBatch`（ids/features/masks/meta）、`FinancialsBatch`、`PeersBatch`、`SentimentBatch`。
- 缓存：内容寻址 + as_of；临时文件原子替换；失败不写半成品。
- manifest：`batch_id`、`as_of`、源版本、行数、缺失统计、哈希。
- 演示数据：五指数（至少上证50）+ 3 家 IPO 样例（公开/构造）。

验收：

- 同一 as_of 两次拉取，宽表哈希一致（允许源端更新时显式 bump as_of）。
- 缺数据有 `missing[]` 与 mask，不静默补零。
- 单源失败只影响对应列，不阻断整表。

回滚：`data_source=legacy` 读旧缓存；新表不写旧目录。

### V2 · 模型加载 B（3 周）

**目标**：模块注册、参数包、常驻 worker；换模块不改 A/C/D。

工作：

- 模块：`val.dcf`、`val.dcm`、`val.comparable`、`val.sentiment`、`val.rim`、`val.ddm`、`val.industry_fallback`、门控、池化（线性/对数/专家乘积）。
- 参数包：YAML/JSON，版本化；每模块默认参数 + 覆盖；启动时校验 schema。
- worker：模块加载一次，批内复用；每模块健康检查（`health()`）；失败模块禁用并记录，不拖垮全图。
- 依赖图：模块输入/输出类型校验；环检测；缺失依赖报错。
- DCM：先实现一个可配置的折现/资本化模型（口径在实现前确认），与 DCF 分开注册。

验收：

- 同一模块在 3 家样例上可单独运行（不依赖 C/D）。
- 把 DCF 换成 DCM，只改 `GraphSpec`/参数包；A/C/D 代码不变。
- 加载失败只禁用该模块，其他模块继续。

回滚：`module_version` 固定到上一版；禁用新模块。

### V3 · 批处理 C（4 周）

**目标**：向量化 + 断点恢复 + 失败隔离。

工作：

- chunk：按 `chunk_size=200`（可配）切分券；基础模块按列式/矩阵批量；舆情/LLM 逐券或小批并发。
- 向量化：DCF/DCM/可比/池化对 `Batch` 做数组运算；避免逐券 Python 循环（保留逐券 fallback）。
- 断点：每个 chunk 完成即写 `runtime/graph/<batch_id>/<stage>/<chunk_id>.json`；manifest 记录状态；恢复时跳过 `done`，重跑 `failed/running`。
- 原子写：tmp + rename；manifest 只用 append/atomic replace。
- 失败隔离：单券/单模块错误写 `CellError`，继续其他单元；池化按剩余权重再归一。
- 常驻：worker 池在 B 段创建，C 段复用，结束后关闭；内存峰值按 chunk 控制。

验收：

- 杀进程后重启，从最后一个完成 chunk 继续，不重算已完成 chunk；结果与一次跑完逐位一致（确定性模块）。
- 单券异常不改变其他券结果；异常券可单独重跑。
- 2,201 只全市场跑批的内存/时长有基线（待测，先记录）。

回滚：`batch_mode=legacy` 走旧 pipeline；新目录独立。

### V4 · 指数拟合 D（3 周）

**目标**：选指数/权重 → 池化 → 拟合点位 → 三情景 → 报告。

工作：

- 指数：五指数（上证50/180、科创50、沪深300、上证综指）；权重口径（官方/自由流通/总市值）。
- 池化：线性默认；对数/专家乘积可切换；区间同步传播。
- 拟合：`V_idx = P_idx × Σ w_i (V_i/P_i) / Σ w_i`；价格加权对照。
- 三情景：逐券区间按同权重合成；与基准点位一致。
- 报告：逐券 trace、模块贡献、偏离分布、指数点位、证据链；HTML。
- IPO demo：单公司图，输出区间/方法分解/敏感性/定价约束；不输出单一价格。

验收：

- 同一 `as_of + 参数包 + 模块版本` 下，点位可复现；换池化可解释差异。
- 每只券的点位贡献可追溯（权重 × 方法值）。
- 报告能回答“为什么是这个点位”。

回滚：`index_mode=legacy` 读旧 summary；新报告独立。

### V5 · 评论家/校准（研究，4 周并行）

- 专家/主审/shadow/apply/台账；合成目标（一致性/稳定/校准/人评）。
- LLM：`temperature=0`、固定 model/prompt、响应缓存、3 次一致性检查；不依赖 seed。
- 评估：同结论稳定率、参数方差、采纳率、消融。
- 论文：VCG 命题、合成基准、盲评。

验收：同输入重复运行的结论一致率 ≥ 目标（待定）；不一致时有规则兜底与标记。

---

## 3. 测试与验收

| 层 | 测试 |
|---|---|
| 协议 | `Batch/ModuleOutput/GraphSpec` 构造/校验；类型不匹配报错 |
| 模块 | 每模块单元测试 + golden fixture 对拍；DCF/DCM 边界（g<r、负值、缺参） |
| 数据 | 同 as_of 哈希一致；缺失/mask；单源失败 |
| 批处理 | chunk 结果 = 全量结果；断点恢复 = 一次跑完；失败隔离 |
| 指数 | 池化边界/单调；点位贡献可加总；三情景一致 |
| 回归 | 旧技能 170 用例只作 oracle；新模块与旧引擎差异清单 |
| 性能 | 单券/批量/全市场规模、内存、缓存命中；待测基线 |

**门禁**：V0–V4 每阶段必须“可独立运行 + 有测试 + 有回滚”；没有测试不合并。

---

## 4. 与旧路线的关系

- `docs/03-engineering-roadmap.md` 的 M0–M4 仍有效：M1 向量化 → 本 V1/V3；M2 可视化 → V4 报告；M3 Agent → V5；M4 池化/指数 → V4。
- 本计划把“图/模块/断点”提前，把“鉴权/合规/数据域”删除；这是 demo 优先的取舍。
- 旧 `05` 的 V0 “LegacyModule 包装”**作废**；新 V0 是参照提取 + 骨架。

---

## 5. 待拍板

1. **DCM 口径**：股利资本化 / 现金流资本化 / DCF 变体？实现前必须定，否则模块只是空壳。
2. **numpy 依赖**：基础层用 numpy（推荐）还是纯标准库（原型现状）？
3. **chunk 大小**：200 起步，按内存/模块调；是否需要按行业分组？
4. **常驻 worker**：进程池 vs 线程池；LLM 模块是否独立进程？
5. **V5 是否本轮做**：demo 可以先只做 V0–V4，评论家保留现有 shadow 作为参照。
6. **旧技能对拍范围**：全部 170 用例，还是选 20 个代表案例？

---

## 6. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 完全重构导致数值漂移 | 结果不可比 | golden fixtures + 差异清单；允许有意变更但必须解释 |
| 向量化后单券失败污染整批 | 数据缺失 | chunk + CellError + mask；失败隔离测试 |
| 断点状态不一致 | 重跑/漏跑 | manifest 原子写 + 幂等 chunk + 恢复测试 |
| 模块太多、加载慢 | 启动成本 | 懒加载 + 健康检查 + 模块依赖裁剪 |
| DCM 口径未定 | 模块空转 | 先定公式；未定前只做占位与接口 |
| LLM 结论不稳定 | 评审不可复现 | temperature=0 + 缓存 + 3 次一致性 + 规则兜底 |
| demo 数据源不稳 | 跑批失败 | 缓存 + 构造样例 + 源失败降级 |

---

## 7. 本轮不做

- 鉴权、脱敏、数据域隔离、合规认证。
- 真实保密 IPO 材料。
- 端到端训练/BP。
- 自动交易/自动定价。
- 生产级高可用/多租户。
