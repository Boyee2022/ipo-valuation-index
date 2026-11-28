# skills · 估值技能包

本目录存放项目的方法论实现。当前只有一个包：

```text
skills/
└── llm-ipo-valuation/     # 大模型 IPO 智能估值技能（v3.29.1 / 引擎实际 2.28.0）
```

## 为什么入库

技能是整个项目的“模型层”：DCF / 可比 / 舆情 / 金融 RIM/DDM / 生命周期 / 统计校验 / 报告 / 机检都在这里。此前它放在部署机仓库外（`~/.dsh-valuation/agents/skills/`），导致：

- 无法随代码版本化，换机/交接不可复现；
- 批跑与技能版本容易错位；
- 论文与工程文档缺少可引用的实现基线。

因此自 2026-11-28 起，技能作为项目组件入库；批跑 `packages/batch/config.py` 默认优先使用仓库内路径，`VALUATION_SKILL_DIR` 仍可覆盖。

## 来源与版本

- 来源：用户提供的 `llm-ipo-valuation-skills/` 工作树（2026-11-06）。
- 版本：`SKILL.md` 标题 **v3.29.1**；文档写引擎 v2.27.1，`valuation_engine.py` docstring 写 v2.22.0，实际输出 `engine_version=2.28.0`（包内版本漂移，见 `docs/spec/05-skill-package.md`）。
- 导入时排除：嵌套 `.git/`、`__pycache__/`、`*.pyc`、`.DS_Store`、`outputs/`（v318/v319 demo 产物）。
- 未做任何代码/参数修改，保持工作树原样。

## 目录

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 主文档：三条入口、七步流程、方法规则、错误处理、合规 |
| `methodology.md` | 方法论总览（六层架构）+ 版本变更记录 |
| `assets/` | 输入 schema/模板、行业参数、校准先验、错误处理、IPO 清单、报告模板/风格 |
| `scripts/` | 引擎、统计校验、报告、机检、可比证据链、β、数据抓取、输入校验、冒烟测试 |
| `examples/` | 27 个输入/输出/统计样例，可作数值回归基线 |
| `references/` | 两份占位说明（完整报告未随包分发） |

## 批跑如何调用

```text
valuation_engine.py  → 估值中枢/区间/四部分/置信度/生命周期
stat_validation.py   → MC 3000 / 弹性 / Spearman / 稳健性
report_generator.py  → 投行级 11 段 HTML 报告
html_check.py        → 八项机检
fetch_data.py        → 东财财报/一致预期（由 dsources 导入）
```

路径解析：`VALUATION_SKILL_DIR` > `skills/llm-ipo-valuation` > `~/.dsh-valuation/agents/skills/llm-ipo-valuation`。

## 回归与升级

- 回归：`python3 scripts/smoke_test.py` —— 2026-11-28 实跑 **170 用例全绿（3.9s）**；文档中 100/152/169 为旧口径，以运行输出为准；再对 `examples/` 全量重算并 diff。
- 升级：独立分支替换本目录 → 跑 smoke + examples 回归 → 上证50 shadow 跑批对照 → 更新版本号与 `docs/spec/05` → 提交。
- 禁止：直接改线上目录、跳过回归、把密钥/生成物提交进来。

## 拆分 TODO

当前仍是“一个大 skill”。后续工程化要拆成 8 个可独立测试/向量化调度的模块（数据/画像/可比池/DCF/可比法/舆情/合成/统计报告），接口与验收见：

- [`docs/spec/05-skill-package.md`](../docs/spec/05-skill-package.md)
- [`docs/03-engineering-roadmap.md`](../docs/03-engineering-roadmap.md)
- [`docs/04-skill-methodology.md`](../docs/04-skill-methodology.md)

## 保密

技能为陈老师研究成果，仅限本项目内部使用；仓库为私有，不要公开分发或放入公开镜像。
