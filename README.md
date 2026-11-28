# ValuationSystem — 估值跑批工作台

指数估值跑批工作台：逐只估算指数成分券，**用估值替代价格**，按指数权重合成“拟合点位”，
与真实收盘并列展示。覆盖上证50、上证180、科创50、沪深300、上证综指（沪市 A 股全市场）。

> 探索性研究，不构成投资建议。差异只展示、不做反向校正；不默认市场对。

## 形态

建立在 DSH 网页版（dsh-web-app）上的独立项目：

- **独立仓库**：与 FactorLab 的 csi-dsh 隔离；dsh-base / dsh-web-app 仅作运行时依赖。
- **客户端插件** `@valuation/workbench`：估值跑批单页仪表盘 + 估值智能体面板；认领上游 `ui-workbench` 面板 id，profile 停用上游行；品牌名 ValuationSystem。
- **批跑服务**：`packages/batch`（纯标准库 Python，3089），负责数据、逐券计算、多 Agent 评审、合成与报告存档。
- **估值技能**：`skills/llm-ipo-valuation`（v3.29.1），随仓库交付；批跑默认使用仓库内路径。
- **独立实例**：profile `valuation`，Web 3081，`DSH_HOME=~/.dsh-valuation`（与 FactorLab 的 3080 / `~/.dsh` 隔离）。

## 能力

- **五指数**：上证50 / 上证180 / 科创50 / 沪深300 / 上证综指（约 2,201 只，总市值权重，剔除 ST 与未满计入期新股）。
- **三情景点位**：逐券区间按指数权重合成悲观/基准/乐观，指数瓦片可切换。
- **多 Agent 评审**：三专家（可比质量 / 折现参数 / 舆情）+ 主审；证据门槛、严重度上限、accept/clamp/reject；`shadow` 只留痕、`apply` 回写并按 baseline 回滚。
- **估值智能体面板**：角色启停、置信门槛、幅度上限、模型/并发/超时配置；保存后下一批生效。
- **报告**：逐券投行级 HTML、汇总报告、评审 sidecar、apply 改前/改后可视化；侧栏工作区浏览。
- **数据**：东财指数成分/财报/F10/行业估值 + 腾讯行情 + 东财新闻/股吧；规则或 DeepSeek 语义舆情。

## 六步流程（单页锚点）

1. 参数确认（舆情轮数、三路权重、WACC/永续覆盖、抽样、多 Agent 模式）
2. 选择指数（五指数）
3. 成分券权重（东财前一日收盘权重；全市场总市值权重）
4. 估值日期（当前为参考，批跑使用成分数据时点）
5. 并行度（3 / 10）
6. 运行报告（逐券 + 汇总 + 三情景点位 + 评审）

**拟合点位（指数加权）**：

```text
V_index = P_index × Σ_i w_i × (V_i / P_i) / Σ_i w_i
```

跳过券不计入分子分母；另保留价格加权口径作对照。

## 目录

```text
packages/workbench/   # DSH 客户端插件（React + CSS Modules + esbuild）
packages/batch/       # 批跑服务、输入组装、多 Agent 评审、报告主题/回写可视化
skills/llm-ipo-valuation/  # 估值技能包（引擎/统计/报告/机检）
profiles/valuation/   # DSH profile 配置（部署到 ~/.dsh/profiles/valuation/）
scripts/              # 启停脚本
docs/                 # 项目理解、论文、工程路线、技能方法论、spec、HTML 宣讲页
```

文档入口：[`docs/README.md`](docs/README.md)。

## 构建与部署

```bash
# 依赖
pnpm install

# 前端插件（改 client 代码后）
cd packages/workbench && node build.mjs     # lib/client.js + lib/index.js

# 批跑服务（3089）
cd packages/batch && python3 server.py

# profile（部署机）
cd ~/.dsh/profiles/valuation && pnpm install
bash scripts/valuation-down.sh && bash scripts/valuation-up.sh   # Web 3081
```

改客户端代码后无需重启 Web 实例：重新 build + 浏览器刷新即可（profile `patchReload: live`）。
改 profile 配置需同步到部署目录并按需 `pnpm install`。

## 配置与环境

| 项 | 默认 |
|---|---|
| 技能目录 | `skills/llm-ipo-valuation`（`VALUATION_SKILL_DIR` 可覆盖） |
| 报告存档 | `~/.dsh-valuation/valuation-reports`（`VALUATION_REPORTS_DIR`） |
| 任务/缓存 | `runtime/jobs`、`runtime/cache`（`VALUATION_RUNTIME`） |
| 智能体配置 | `~/.dsh-valuation/agents.json`（`VALUATION_AGENTS_CONFIG`） |
| 个股覆写 | `~/.dsh-valuation/overrides/<code>.json` |
| LLM 密钥 | `~/.dsh-valuation/sentiment-llm.env` 的 `DEEPSEEK_API_KEY`（仓库外） |

## 已知限制

- 无真值：结果用于研究/内部对照，不以“贴近指数收盘”为目标。
- 估值日期尚未透传到批跑（UI 标注“参考”）。
- 定时任务未接调度器。
- 技能 v3.29.1 与批跑 v3.31 护栏存在版本差，需回归确认。
- 仓库无 CI；验证依赖技能 `smoke_test.py`、`html_check.py` 与人工跑批。
- `workspace_ensure.ts` 仍有原部署机硬编码路径，迁移时需改。

## 文档

- [项目理解](docs/00-project-understanding.md)
- [论文构想](docs/01-paper-proposal.md) / [四张学术海报](docs/posters/README.md)
- [工程路线](docs/03-engineering-roadmap.md)
- [技能方法论](docs/04-skill-methodology.md)
- [Spec](docs/spec/) / [决策日志](docs/05-decision-log.md)
