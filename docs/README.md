# docs · 估值跑批工作台（ValuationSystem）

本目录是项目的**研究与工程文档中心**：把讨论过程、项目理解、论文构想、技能方法论、工程路线和接口 spec 固化下来，供项目组内部对齐与后续实现使用。

- 代码基线：`origin/main` `d06a5ed`（2026-11-27，51 个提交）
- 技能基线：`skills/llm-ipo-valuation`（v3.29.1，引擎 v2.27.1，2026-11-06 工作树）
- 文档更新：2026-11-28

## 阅读顺序

| # | 文档 | 读者 | 用途 |
|---|---|---|---|
| 00 | [项目理解](00-project-understanding.md) | 所有人 | 5–10 分钟建立全局上下文：业务、架构、链路、公式、现状、风险 |
| 01 | [论文构想](01-paper-proposal.md) | 研究线 | 论文主张、数学骨架、三阶段、论文矩阵、实验设计 |
| 02 | [LaTeX 海报](02-poster.tex) | 研究线 | A0 海报初稿（`xelatex` 编译，产物 `02-poster.pdf`） |
| 03 | [工程路线](03-engineering-roadmap.md) | 工程线 | 五层改进：解耦向量化 / 表达可视化 / Agent 迭代 / 指数拟合 / 合成池 |
| 04 | [技能方法论](04-skill-methodology.md) | 研究线 + 工程线 | 技能包七步流程、六层架构、核心机制、可复用思想、拆分 TODO |
| 05 | [决策日志](05-decision-log.md) | 所有人 | 本轮讨论形成的决策、理由、待决项 |

## Spec

| 文档 | 内容 |
|---|---|
| [01 系统架构](spec/01-architecture.md) | 组件、部署、数据流、目录、DSH 集成、故障与安全边界 |
| [02 估值模型与口径](spec/02-valuation-model.md) | 输入 schema、方法路由、生命周期、合成公式、区间/情景、置信度 |
| [03 多 Agent 评审协议](spec/03-agent-review-protocol.md) | 角色、证据、门槛、严重度、主审、apply/回滚、指标、配置 |
| [04 数据源与 API](spec/04-data-and-api.md) | 五个指数、数据源与 TTL、HTTP 路由、请求/响应、失败语义 |
| [05 技能包](spec/05-skill-package.md) | 技能目录、版本、批跑调用、回归资产、拆分计划、升级流程 |

## HTML 版（内部宣讲/对齐）

- [文档门户](html/index.html)
- [论文建议 · 阅读版](html/paper-proposal.html)
- [工程规划 · 终端风](html/engineering-roadmap.html)
- [SKILL 讲解 · 终端风](html/skill-explainer.html)

HTML 统一使用 [`assets/terminal.css`](assets/terminal.css) 与 [`assets/terminal.js`](assets/terminal.js)：深/浅双主题、发丝线面板、琥珀强调、等宽数字，与估值工作台视觉同源。直接双击打开即可离线阅读。

## 写作与维护约定

1. **事实以仓库为准**：代码/接口变化时，先改 spec，再改理解与路线；HTML 与 md 同步。
2. **版本差异必须显式标注**：技能包（v3.29.1）与批跑层（已按 v3.31.0 护栏适配）存在版本差，见 [05](spec/05-skill-package.md)。
3. **不写没有依据的数字**：性能、样本量、覆盖率等，要么给来源，要么标“待测/待核实”。
4. **中文为主、术语保留英文**：MoE、Layer 0、RIM、rNPV、shadow/apply 等首次出现给解释。
5. **论文与工程分开叙事**：工程文档回答“怎么做、怎么验收”；论文文档回答“为什么这样建模、贡献是什么”。

## 相关仓库外材料

- 业务侧项目理解总览：`../../00-项目理解总览.md`（父目录，覆盖 FactorLab 与本项目）
- 历史讨论纪要：`../../doc/`（2026-11-10 估值跑批方案、2026-11-13 企业估值研究、多 Agent 非线性拟合等）
- 本机运行环境：`../../.runtime/README.md`
