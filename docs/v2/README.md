# docs/v2 · Valuation Computation Graph（设计分支）

> 分支：`design-valuation-net`（从 `main` `f56bb93` 切出）  
> 状态：**构想/原型，不进入生产**；合并前需组内评审。  
> 一句话：把估值从“逐券 pipeline”升级为**类型化、可组合、可审计的估值计算图**，前向是模块图，后向是带合成目标的智能体评论家。  
> **2026-11-28 修订：demo 优先，不鉴权/不脱敏；完全重构；四段式 A/B/C/D；见 [08](08-demo-first-revision.md)。**

## 为什么开这个分支

现有系统已经能跑通五指数、多 Agent 评审与报告，但方法仍是“写在券内的固定流程”。本分支探索下一版：

- 估值模块（DCF、可比、舆情、RIM、rNPV、NAV…）像网络层一样**可插拔**；
- 门控、残差、注意力、归一化、dropout、池化都有明确语义；
- 多智能体评审作为**独立的一层**（actor-critic），不是散落在 pipeline 里；
- 同一组模块服务两个场景：**已上市监控**与**拟上市 IPO 定价**；
- 最终形成可写论文、可工程化的统一架构。

## 阅读顺序

| # | 文档 | 内容 |
|---|---|---|
| 00 | [评估](00-evaluation.md) | 这个想法是否合理：哪些类比成立、哪些必须修正、可行性与合规边界 |
| 01 | [理论](01-theory.md) | 形式化：计算图、门控/残差/注意力/池化、actor-critic/bilevel、命题与相关工作 |
| 02 | [架构](02-architecture.md) | 模块协议、图执行器、两层模式、参数存储、审计、API |
| 03 | [模块目录](03-module-catalog.md) | 每个模块的输入/输出/约束/状态/对应现有代码 |
| 04 | [两个用途](04-use-cases.md) | 已上市监控 + IPO 定价的流程、数据域、输出与边界 |
| 05 | [实施计划](05-implementation-plan.md) | V0–V4、里程碑、代码改动、测试、风险 |
| 06 | [评估协议](06-evaluation.md) | 合成基准、盲评、下游任务、消融、指标 |
| 07 | [Demo 边界](07-compliance.md) | 本轮不鉴权/不脱敏/不接保密材料；生产化另议，不验收 |
| 08 | [Demo 优先修订](08-demo-first-revision.md) | **本轮必读**：不鉴权/不脱敏、完全重构、四段式、DCM、LLM 同结论 |
| — | [HTML 讲解](html/index.html) | 终端风可视化版本，供内部对齐 |
| — | [原型](../../prototype/valnet/README.md) | 最小 Python 图执行器 + 池化 + 测试（stdlib only） |

## 术语

- **VCG / MVN**：Valuation Computation Graph / Modular Valuation Network。本文优先用 VCG，避免“神经网络”被误读为端到端可训练。
- **Module**：有类型、版本、约束、证据与不确定性的估值算子。
- **Gate**：决定模块是否进入、权重多少的条件（行业、生命周期、数据质量、证据）。
- **Pool**：线性池 / 对数池 / 专家乘积。
- **Critic**：多智能体评审层；专家提议、主审裁决、shadow/apply、回滚。
- **Synthetic objective**：没有真值时的校准目标（一致性、稳定、校准、人评）。

## 不做什么

- 不改生产代码、不替换现有引擎；原型独立在 `prototype/valnet/`。
- 不把“神经网络/BP”写成已实现；理论文档明确区分“可微部分”和“离散/黑箱部分”。
- 不用市价当训练标签；不输出交易指令；IPO 输出估值区间而非单一发行价。
- 不在本分支合并到 `main`；评审通过后再拆小 PR。

## 快速验证原型

```bash
cd prototype
python3 -m unittest discover -s valnet/tests -v
python3 -m valnet.runner
```
