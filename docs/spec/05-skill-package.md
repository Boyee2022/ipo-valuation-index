# Spec 05 · 技能包（skills/llm-ipo-valuation）

> 本轮变更：技能包**首次入库**，从“仓库外、部署机本地”变为“项目组件”。  
> 来源：用户提供的 `@llm-ipo-valuation-skills/`（工作树，2026-11-06），已剔除嵌套 `.git/`、`__pycache__/`、`outputs/`。

## 1. 包定位

技能包是估值方法论的**唯一实现**：输入 JSON → 估值引擎 → 统计校验 → HTML 报告 → 机检。批跑层不重写估值逻辑，只负责组装输入、调度、合成与展示。

- 名称：`llm-ipo-valuation`
- 版本：**v3.29.1**（`SKILL.md` 标题）；`SKILL.md` 描述称引擎 v2.27.1，`valuation_engine.py` docstring 写 v2.22.0，实际运行输出 `engine_version=2.28.0`——包内版本号存在三处漂移，升级时以 `SKILL.md` + 实际回归为准。
- 方法论出处：国金证券《基于大语言模型的上市公司智能估值模型构建》（李双宏、杨利国、王洪涛）+ 达莫达兰生命周期框架。

## 2. 目录

```text
skills/llm-ipo-valuation/
├── SKILL.md                  # 技能主文档：使用方式、七步流程、方法规则、错误处理、合规
├── methodology.md            # 方法论提炼 + 版本变更记录
├── .gitignore                # __pycache__ / pyc / .DS_Store
├── assets/                   # 输入 schema/模板、行业参数、校准先验、错误处理、IPO 清单、报告模板/风格
│   ├── input_schema.json
│   ├── input_template.json
│   ├── industry_params.json
│   ├── calibration_params.json
│   ├── error_handling.md
│   ├── ipo_rules_checklist.md
│   ├── output_template.md
│   ├── output_template_pro.html
│   ├── report_style_guide.md
│   └── industry_multiple_guide.md
├── scripts/                  # 10 个 Python 脚本（纯标准库）
│   ├── valuation_engine.py   # 引擎：路由、DCF/RIM/DDM/可比/舆情/rNPV/SOTP、合成、置信度
│   ├── engine_utils.py       # 纯工具函数层
│   ├── stat_validation.py    # MC / 弹性 / Spearman / 稳健性
│   ├── report_generator.py   # 投行级 11 段 HTML 报告
│   ├── html_check.py         # 八项机检
│   ├── peer_screening.py     # 可比证据链（长名单/剔除台账/截点/规模双口径）
│   ├── beta_estimator.py     # 60 个月 OLS β
│   ├── fetch_data.py         # 东财公开行情/财务/一致预期
│   ├── input_validator.py    # 输入 schema 静态校验
│   └── smoke_test.py         # 冒烟回归（用例数见 §6）
├── examples/                 # 27 个输入/输出/统计样例（宇树、长鑫、天博、罗舟、CXMT 等）
└── references/               # 两份占位说明（完整报告未随包分发，结论已沉淀在 methodology.md）
```

已排除：嵌套 `.git/`（保留在用户原目录，不随仓库分发）、`__pycache__/`、`outputs/`（v318/v319 demo 产物）。

## 3. 批跑如何调用

`packages/batch/pipeline.py` 通过 `config.SKILL_DIR` 解析脚本路径：

```text
ENGINE = skills/llm-ipo-valuation/scripts/valuation_engine.py
STAT   = .../stat_validation.py
REPORT = .../report_generator.py
CHECK  = .../html_check.py
```

逐券执行顺序：

```bash
python3 valuation_engine.py <input.json> -o <out.json>
python3 stat_validation.py <input.json> <out.json> -o <stat.json> --n 3000 --seed 42
python3 report_generator.py <out.json> -o <report.html> --stat <stat.json> --input <input.json>
python3 html_check.py <report.html> --output <out.json>
```

`dsources.py` 还会导入 `fetch_data.py`（财报/一致预期），并在启动时把脚本目录加入 `sys.path`。

路径解析（`config.py`）：

1. `VALUATION_SKILL_DIR` 环境变量（最高优先）；
2. 仓库内 `skills/llm-ipo-valuation`（存在即用）；
3. 旧部署路径 `~/.dsh-valuation/agents/skills/llm-ipo-valuation`（兜底）。

## 4. 输入/输出契约

- 输入：`assets/input_schema.json` + `input_template.json`；顶层字段见 [02-valuation-model.md](02-valuation-model.md)。
- 输出：`synthesis`（综合中枢/区间/四部分）、`confidence`、`lifecycle`、`net_profit_basis_used`、`warnings`、`industry_fallback`（v3.31 护栏，当前技能版本可能不产出）、`rim/ddm/rnpv/sotp` 明细。
- 批跑只消费其中一部分字段；技能升级时需保证这些字段的向后兼容，否则在 `pipeline._worker` 做兼容读取。

## 5. 回归资产

- `scripts/smoke_test.py`：覆盖正常盈利、亏损切 PS、可比不足、权重归一、MC、路由、生命周期、统计校验等。
- `examples/`：输入/输出/统计/报告样例，可作为数值零回归基线。
- `html_check.py`：报告交付前机检（结构、章节、数字、占位符、空表、单位、链接、免责声明）。
- `references/`：两份占位说明，完整报告未入库；结论在 `methodology.md` §5/§6。

**建议的回归门禁**（待落地）：改动技能或批跑输入组装后，跑 `smoke_test.py` + 对 `examples/` 全量重算，逐字段 diff；任何非预期数值变化必须解释。

## 6. 版本与一致性风险

| 项 | 现象 | 影响 | 处理 |
|---|---|---|---|
| 技能 vs 批跑 | 技能 v3.29.1；批跑 `d06a5ed` 已按 v3.31.0 护栏适配（行业基准兜底、PS 5×/10× 弃用、rNPV 覆写等） | 引擎可能不产出 `industry_fallback`，批跑 `.get()` 容错；口径可能与最新技能不一致 | 以 `smoke_test` + examples 回归确认；升级技能到与批跑一致的版本 |
| 包内版本号 | `SKILL.md` 写 v3.29.1 / 引擎 v2.27.1；`valuation_engine.py` docstring 写 v2.22.0；实际输出 2.28.0 | 追溯困难 | 升级时统一版本号，CI 校验 |
| smoke 用例数 | 实跑 **170 全绿（3.9s）**；`SKILL.md` §7 写 169；`smoke_test.py` docstring 写“100 用例”；代码 T 编号去重 152 | 无法用固定数字对外背书 | 文档改为“运行结果 170 全绿（2026-11-28）”并附命令 |
| 参考资料 | `references/*.md` 是占位 | 方法实证细节缺失 | 从 methodology.md 与 `stat_validation.py` 复算/补写 |

## 7. 拆分 TODO（后续工程化）

目标：把“一个大 skill”拆成可独立测试、可向量化调度的模块，同时保持数值零回归。

| # | 模块 | 输入 | 输出 | 依赖 | 验收 |
|---|---|---|---|---|---|
| 1 | 数据/财务 | 证券代码、as_of | 年报/一致预期/三表/质量指标 | 东财接口、缓存 | 与 `fetch_data` 对样例逐字段一致 |
| 2 | 画像/分类 | 财务 + 行业 | 生命周期、行业类别、方法可用集 | 分类器、行业参数 | 与引擎 `lifecycle`/`framework_check` 一致 |
| 3 | 可比池 | 标的 + 全市场池 | 长名单、剔除台账、5 家可比 | `peer_screening` | 与 `peer_screening` 输出一致 |
| 4 | DCF | 财务 + 驱动 + WACC | 中枢、区间、敏感性 | 增长函数、税率、NWC | 与引擎 DCF 分支逐位一致 |
| 5 | 可比法 | 可比倍数 | 中枢、倍数明细 | 倍数规则、PEG 护栏 | 与引擎可比分支一致 |
| 6 | 舆情 | 新闻/股吧 | 标签、调整幅度、证据 | 规则/LLM | 与 sentiment 输出一致 |
| 7 | 合成 | 各方法值 + 权重 | 综合中枢、四部分、区间 | 池子语义 | 与引擎 `synthesis` 一致 |
| 8 | 统计/报告/机检 | 输出 + 输入 | stat/report/check | 现有脚本 | 与现有报告逐项一致 |

拆分原则：**先抽接口，再抽实现**；每个模块有独立输入/输出 JSON 与回归样例；批次调度按模块层向量化（见 [03-engineering-roadmap.md](../03-engineering-roadmap.md) 第一层）。

## 8. 升级流程（建议）

1. 在独立分支替换 `skills/llm-ipo-valuation/`（不直接改线上）；
2. 跑 `smoke_test.py`，记录通过/失败用例；
3. 对 `examples/` 全量重算，与基线 diff（数值、字段、报告章节）；
4. 用批跑服务对 1 个指数（上证50）做 shadow 跑批，对比逐券中枢/置信度/跳过率；
5. 通过后更新 `SKILL.md`/`methodology.md` 版本号与 `docs/spec/05`；
6. 提交并记录 commit/tag；部署机按 `VALUATION_SKILL_DIR` 切换。

## 9. 合规与分发

- 技能为陈老师研究成果，仓库为私有项目仓库；**不要公开分发**或放入公开镜像。
- 技能内的报告模板/风格指南可用于内部报告，但对外发布需确认授权。
- `references/` 占位文件不包含原始实证数据；如需要，按 `stat_validation.py` 复算并单独归档。
