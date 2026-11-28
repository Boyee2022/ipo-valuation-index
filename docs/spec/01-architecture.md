# Spec 01 · 系统架构

> 状态：已实现（基线 `d06a5ed`）。本文描述“现在是什么”，不包含未来改造；改造见 [../03-engineering-roadmap.md](../03-engineering-roadmap.md)。

## 1. 定位与边界

ValuationSystem 是挂在 DSH Web 上的**估值跑批工作台**：浏览器端负责参数、指数、成分展示与结果可视化；批跑服务负责数据、逐券计算、多 Agent 评审、汇总与报告；估值方法论在仓库内技能包中，批跑通过子进程调用。

非目标：不做实时交易、不做组合优化、不把估值结果反向校正到市场价格、不提供投资建议。

## 2. 组件

```text
┌──────────────────────────── DSH Web (3081) ────────────────────────────┐
│  shell（顶栏/侧栏/主题）                                                │
│  ├─ @valuation/workbench client bundle                                  │
│  │   ├─ 主面板 workbench：估值跑批单页                                 │
│  │   ├─ 主面板 valuation-agents：估值智能体配置                        │
│  │   ├─ 侧栏入口 + 品牌 + 工作区「估值跑批工作台」                     │
│  │   └─ 侧栏历史报告 DOM 注入 + 报告主题同步                           │
│  └─ 其它 DSH 内置插件（会话、设置、插件管理…）                          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTP /api/*（CORS）
┌───────────────────────────────▼─────────────────────────────────────────┐
│  批跑服务 3089（Python 标准库 ThreadingHTTPServer）                     │
│  server.py → pipeline.py → (input_builder, dsources, sentiment,        │
│                              shadow, agent_config, report_theme,       │
│                              apply_view)                                │
│  逐券 subprocess → skills/llm-ipo-valuation/scripts/*.py               │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ 文件
        runtime/jobs/<id>/      +   ~/.dsh-valuation/valuation-reports/<id>/
```

## 3. 进程、端口与环境

| 项 | 值 | 说明 |
|---|---|---|
| Web 实例 | 3081 | DSH profile `valuation`，由 `scripts/valuation-up.sh` / `.runtime/bin/start-valuation.sh` 启动 |
| 批跑服务 | 3089 | `packages/batch/server.py`，绑定内网 IP（`ipconfig getifaddr en0/en1`） |
| `DSH_HOME` | `~/.dsh-valuation`（部署）或 `.runtime/valuation-home`（本机） | 会话/工作区/存储隔离 |
| 技能目录 | `skills/llm-ipo-valuation` | `VALUATION_SKILL_DIR` 可覆盖；旧路径 `~/.dsh-valuation/agents/skills/llm-ipo-valuation` 兜底 |
| 报告存档 | `~/.dsh-valuation/valuation-reports` | `VALUATION_REPORTS_DIR` 可覆盖 |
| 任务目录 | `runtime/jobs` | `VALUATION_RUNTIME` 可覆盖 |
| 缓存 | `runtime/cache` | 数据源/舆情缓存 |
| 智能体配置 | `~/.dsh-valuation/agents.json` | `VALUATION_AGENTS_CONFIG` 可覆盖 |
| 个股覆写 | `~/.dsh-valuation/overrides/<code>.json` | `VALUATION_OVERRIDES_DIR` 可覆盖 |
| LLM 密钥 | `~/.dsh-valuation/sentiment-llm.env` | `DEEPSEEK_API_KEY`，仓库外 |

## 4. DSH 集成

- **bundle**：`@valuation/workbench` 的 `package.json` 声明 `dsh.bundle.patch` 与 `dsh.client.inject`；`build.mjs` 产出 `lib/client.js`（`window.__ModuleLoader__.load` 包装）和 `lib/index.js`（空 node half）。
- **面板**：`apply.ts` 以 `PANEL_ID = 'workbench'` 认领上游 `ui-workbench` 面板；profile 必须停用上游 `ui-workbench` 行。`AgentsPanel.ts` 另注册 `valuation-agents`。
- **侧栏**：`sidebar.panellist` 注册两行入口；`sidebar/panel-activate-claim` 事件把点击转成 `layout.selectPanel`。
- **品牌**：`sidebar.brand.name` 注入 `ValuationSystem`；同时改写 `document.title` 与首页 hero 文案（prototype 阶段的 DOM 改写）。
- **工作区**：`workspace_ensure.ts` 创建「估值跑批工作台」host 目录工作区（幂等、退避重试）；`SidebarReports.ts` 在该文件夹展开时注入历史任务/报告 DOM 行（共享 WorkspaceBrowser 只显示会话）。
- **主题**：profile 的 `ui-theme.preference=system`；报告通过 `#theme=dark|light` 与 `report_theme.py` 注入样式；`api.ts` 在导航前同步 `#theme`。
- **记忆面板**：`localStorage` 记住上次主面板，刷新/热更新后恢复。

## 5. 批跑服务内部

- `ThreadingHTTPServer`，无鉴权、CORS 全放行，仅内网使用。
- `pipeline.start()` 创建 job 字典并起后台线程；`run_job()` 拉成分、指数点位、可比池，`ThreadPoolExecutor(max_workers=parallel)` 逐券执行。
- 状态：`runtime/jobs/<id>/state.json`，原子替换写（`.tmp.<pid/thread>`）；>800 只的大任务每 10 行落一次盘以控制体积。
- 锁：`_jobs_lock`（任务表）、`_state_lock`（RLock，状态读写/落盘）；逐券文件互不共享。
- 重启：`reconcile_running()` 把遗留 `running` 标为 `error`，避免前端误挂跟踪。
- 逐券产物：`<code>.input.json`、`.out.json`、`.stat.json`、`.report.html`、`.shadow.json`、`*.baseline.json`（apply）。
- 汇总：`_finalize()` 计算指数加权/价格加权、三情景点位、shadow metrics，写 `summary.html`、`shadow.html`，再 `_archive_reports()` 复制 HTML。

## 6. 数据流（时序）

```text
UI → POST /api/run
  → pipeline.start (job 落盘)
  → run_job: components + index_quote + peer_universe (+ warm_annual_revenue)
  → worker[i]: build_input → engine → [shadow.review] → [apply 回写重跑]
               → stat_validation → report_generator → html_check
               → report_theme 注入 → [apply_view 注入]
               → row 状态写回 state.json
  → _finalize: 合成 + 指标 + summary/shadow + 存档
UI 轮询 GET /api/jobs/<id>（2.5s），完成时刷新任务列表/历史
```

## 7. 持久化与目录

```text
runtime/
├── cache/                       # components_<type>.json, fin_<code>.json, sentiment_<code>.json ...
└── jobs/<job_id>/
    ├── state.json               # 任务状态 + 逐券摘要 + summary + shadow_metrics
    ├── <code>.input.json        # 引擎输入
    ├── <code>.out.json          # 引擎输出
    ├── <code>.stat.json         # 统计校验
    ├── <code>.report.html       # 逐券报告（已注入主题）
    ├── <code>.shadow.json       # 完整评审记录（含证据/专家原始建议/主审逐条）
    ├── <code>.input.baseline.json / .out.baseline.json   # apply 基线
    ├── summary.html
    └── shadow.html
~/.dsh-valuation/
├── valuation-reports/<job_id>/  # 报告存档（侧栏浏览）
├── agents.json                  # 智能体配置（唯一真源）
├── overrides/<code>.json        # 个股级人工覆写
└── sentiment-llm.env            # LLM 密钥（仓库外）
```

`runtime/`、`lib/`、`node_modules/` 不入 git。

## 8. 失败与恢复

| 场景 | 行为 |
|---|---|
| 单券数据缺失/引擎失败/中枢 ≤0 | `skip` + `error`，不阻断整批，不计入合成 |
| 可比不足 | 不跳过；引擎剔除可比法、按剩余方法再归一，置信度降档并标注 |
| 可比/DCF 均无效 | 行业基准兜底（v3.31 护栏），置信度“低”，口径标注“行业基准兜底” |
| LLM 不可用 | 舆情规则口径可继续；LLM 舆情/评审直接拒绝提交并提示密钥路径 |
| LLM 评审失败 | 该券 `decision=error`，不影响跑批；`shadow.json` 记录错误 |
| apply 重跑失败 | 恢复 baseline 输入/输出，`apply.error` 留痕 |
| 服务重启 | 遗留 `running` 标 `error`，前端不再跟踪 |
| 缓存写冲突 | 临时文件名带 pid/线程，原子替换 |

## 9. 安全与合规

- 批跑只读公开数据、只写本机任务目录；无用户系统、无鉴权，**仅限可信内网**。
- CORS `*`；报告文件名白名单 `^[\w.\-]+$`，并校验 `Path.resolve()` 在 jobs 根内，防目录穿越。
- LLM 密钥只在仓库外读取，不落日志；`sentiment_llm._env()` 支持环境变量覆盖。
- 报告与页面均带“探索性研究，不构成投资建议”声明。
- 已知弱项：无速率限制、无审计登录、`workspace_ensure.ts` 硬编码原机器路径。

## 10. 部署与构建

```bash
# 前端插件
cd packages/workbench && node build.mjs        # 产出 lib/client.js + lib/index.js

# profile（部署机）
cd ~/.dsh/profiles/valuation && pnpm install   # link @valuation/workbench
bash scripts/valuation-down.sh && bash scripts/valuation-up.sh

# 批跑
cd packages/batch && python3 server.py         # 3089
```

改客户端代码后无需重启 Web 实例：重新 build + 浏览器刷新（profile `patchReload: live`）。改 profile 配置需同步到部署目录并按需 `pnpm install`。

## 11. 技术债（架构向）

1. 逐券“全 pipeline”串行子进程，无法按方法层向量化（见路线第一层）。
2. 前端单文件 400+ 行、CSS 1300+ 行，六步是锚点而非真正分步。
3. 侧栏报告与品牌改写依赖 DOM 注入，上游结构变化会失效。
4. 任务状态与报告分散在 `runtime/` 与 `~/.dsh-valuation`，无统一 DB。
5. 无仓库级测试/CI；接口契约靠人工与技能 smoke。
6. 端口/路径/密钥均有多处硬编码或隐式默认，迁移成本高。
