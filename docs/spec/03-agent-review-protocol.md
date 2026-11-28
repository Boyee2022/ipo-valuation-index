# Spec 03 · 多 Agent 评审协议

> 实现：`packages/batch/shadow.py`（评审与回写）、`packages/batch/agent_config.py`（配置）、`server.py`（保存/采纳 API）、前端 `Shadow.tsx` / `AgentsPage.tsx`。  
> 目标：让“LLM 提参数”变成**有界、可审计、可回滚、可评估**的工程协议，而不是自由发挥。

## 1. 设计原则

1. **角色正交**：每个专家只看自己证据域，只能提自己权限内的参数；跨域建议直接判不合法。
2. **有界更新**：参数是离散网格 + 严重度上限 + 可行域约束（权重和 100%、WACC/Ke > 永续增速）。
3. **证据门槛**：置信度、具体数字、方向自洽、理由齐全；未过门槛只留痕，不送主审。
4. **两级裁决**：专家提议 → 主审 accept / clamp / reject；主审不得新增专家未提的参数。
5. **默认保守**：主审默认“维持原参数”；宁可少调，不可乱调。
6. **可回滚**：apply 前保存 baseline，重跑失败恢复；shadow 是空操作对照。
7. **评估不看拟合点位**：只看建议离散度、置信度校准、周环比稳定性、人工采纳率。

## 2. 角色与权限

| agent | 标签 | 可见证据 | 可提参数 |
|---|---|---|---|
| `comparable` | 可比质量 | 公司行、当前参数、估值结果、纳入可比（≤8 家）、筛池/覆盖率/规模倍数/剔除台账 | `comp_weight_pp` |
| `financial` | 折现参数 | 当前参数、估值结果、CAPM（rf/ERP/β/来源/kd/税率/D-E）、TTM 财务、质量五指标、生命周期/增长三角 | `wacc_pp`、`tg_pp` |
| `sentiment` | 舆情 | 当前参数、估值结果、舆情输入（口径/标签/幅度/条数）、舆情证据、舆情法 vs 可比偏离 | `sent_weight_pp` |
| `main` | 主审 | 三专家证据合并版 + 基线 + 各专家结论 + 待审建议 | 不新增参数，只裁决 |

金融路由（`baseline.routed=true`）下：只有 `financial` 参与；`comp_weight_pp` / `sent_weight_pp` 不生效；`wacc_pp` 实为股权成本 Ke，`tg_pp` 写入 DDM 永续增速。

## 3. 证据包

- 所有专家**看不到指数拟合点位**，避免“向指数靠拢”的动机。
- 证据由 `evidence_text(inp, eng, base, focus)` 生成：公司行、当前参数、估值结果与离散度、逐家可比、筛池诊断、CAPM、财务、质量、生命周期、舆情。
- 主审拿到三份证据的合并版 + 专家结论 + 建议 JSON。
- 证据文本进入 `shadow.json` 的 `evidence`，可复核。

## 4. 专家输出（LLM JSON）

```json
{
  "issues": ["最多 5 条，每条 ≤40 字"],
  "suggestions": [
    {
      "param": "comp_weight_pp",
      "delta": -5,
      "severity": "medium|high|critical",
      "confidence": 0.72,
      "evidence": "引用证据中的具体数字，≤60 字",
      "reason": "≤50 字"
    }
  ],
  "confidence": 0.7,
  "one_line": "≤30 字结论"
}
```

参数网格：

| 参数 | 步长 | 绝对值上限 | 严重度档位 |
|---|---|---|---|
| `comp_weight_pp` | 5pp | 10pp | medium / high / critical |
| `sent_weight_pp` | 5pp | 10pp | medium / high |
| `wacc_pp` | 0.2pp | 1.0pp | medium / high |
| `tg_pp` | 0.2pp | 0.6pp | medium / high |

默认严重度上限：可比 5/8/10pp、舆情 5/10pp、WACC 0.4/1.0pp、永续 0.2/0.6pp（可在智能体面板按批配置，只能收紧/放宽在允许区间内）。

## 5. 证据门槛（`_gate`）

一条建议必须同时满足，否则进入 `gated`（只留痕，不送主审）：

1. 参数属于该专家权限；
2. 金融路由下权重参数不生效；
3. `critical` 仅允许 `comp_weight_pp`，且不能上调；
4. severity 在允许档位内；
5. `confidence ≥ gate`（默认 0.65，可按专家配置 0.50–0.95）；
6. evidence 长度 ≥6 且包含数字；
7. reason 长度 ≥4；
8. delta 非零；
9. 可比证据不足时不得上调可比权重；
10. 建议方向与理由不矛盾（“下调”却正 delta 等）。

通过门槛后还会：按步长归一化、按 severity 夹断（记 `capped`）、按可行域平衡权重。

## 6. 主审裁决

主审输出：

```json
{
  "items": [
    {"param": "wacc_pp", "status": "accept|clamp|reject", "final_delta": -0.4, "reason": "≤40 字"}
  ],
  "decision": "accept|partial|reject",
  "confidence": 0.68,
  "one_line": "≤30 字"
}
```

规则：

- 每条专家建议都要有主审条目；主审未列示 → `reject`（主审关闭时 → `hold`，建议仅留痕）。
- `accept` / `clamp` 的 `final_delta` 必须落在严重度上限内，且按步长归一；超限自动 `clamp` 并写明“按证据等级夹断至 x pp”。
- 方向与理由冲突 → `reject`。
- 主审不得跨域、不得新增参数、不得突破 WACC > 永续增速。
- 任务级 `decision`：`accept`（全部通过）/ `partial`（部分）/ `reject`（全部驳回）/ `hold`（维持/主审关闭）/ `error`（专家或主审调用失败）。

## 7. apply 回写

### 7.1 general 路由（非金融）

- 权重参数：按 `applied.weights` 重写 `preferences.weights`（三路和 100%），其余方法按原比例缩放。
- `wacc_pp`：写 `financials.wacc = 基线 WACC% + delta`（小数）。
- `tg_pp`：写 `financials.terminal_growth = 基线 tg% + delta`（小数）。
- 追加 `data_sources` 条目“多 agent 评审回写（apply）”和 `preferences.agent_adjustments`。

### 7.2 routed 路由（金融）

- `wacc_pp`：同时写 `rim.cost_of_equity` 与 `ddm.cost_of_equity`。
- `tg_pp`：写 `ddm.terminal_growth`。
- 权重参数跳过并记入 `skipped`。

### 7.3 重跑与回滚

1. 有变更时，先把当前 `input.json` / `out.json` 复制为 `*.baseline.json`；
2. 写回新输入，重跑引擎；
3. 新中枢必须 >0，否则抛错；
4. 失败：恢复 baseline 输入/输出，`apply.error` 记录原因，结果沿用基线；
5. 成功：更新 `row.weighted_mid / per_share / interval / four_part / confidence...`，并写 `apply` 摘要。

### 7.4 审计

- `state.json` 的 `row.shadow` / `row.apply` 是摘要；
- `<code>.shadow.json` 保存完整记录：`baseline`、`evidence`、`agents`、`expert.suggestions/gated`、`main`、`items`、`applied`、`apply`、`adoption`；
- `summary.html` 写 apply 明细（改动、基线→最终中枢、失败回滚）；
- 逐券报告插入“生效回写 · 改前/改后”区块（`apply_view.py`）。

## 8. 人工采纳

`POST /api/shadow/adopt {job, code, action: adopted|rejected|clear}`：

- 只允许任务 `done`、该券有有效评审记录；
- 写回 `shadow.json` 的 `adoption` 与 `state.json` 的 `row.shadow.adoption`；
- 重新计算任务级指标（采纳率）；
- 前端 `ShadowCard` / `ShadowDetail` 展示，重复点击同一项 = 清除。

## 9. 指标（`shadow.metrics`）

| 指标 | 定义 | 用途 |
|---|---|---|
| `reviewed` | 有有效评审结论的券数 | 覆盖 |
| `errors` | 评审失败券数 | 稳定性 |
| `suggested` / `accepted_items` | 通过门槛建议数 / 主审通过项数 | 活跃度 |
| `gated` | 未过证据门槛条数 | 门槛校准 |
| `decision_dist` | accept/partial/reject/hold/error 分布 | 行为 |
| `mean_confidence` | 有效评审平均置信度 | 校准（需与采纳率对照） |
| `dispersion[p]` | 建议 delta 的中位/IQR/非零数 | 是否过度反应/过于保守 |
| `adoption` | adopted/rejected/pending + 采纳率 | 人工认可 |
| `apply` | 回写数/失败数/中枢变动中位 | 实际影响 |
| `wow[p]` | 与同指数上一次影子任务共同券的参数中位绝对变动 | 周环比稳定性 |

**评估红线**：不以“拟合点位更贴近指数收盘”作为优化目标；市场偏离只作诊断。

## 10. 配置

`~/.dsh-valuation/agents.json`（`VALUATION_AGENTS_CONFIG` 可覆盖）：

```json
{
  "version": 3,
  "model": "deepseek-chat",
  "concurrency": 6,
  "timeout_s": 90,
  "agents": {
    "comparable": {"enabled": true, "confidence_gate": 0.65,
      "caps": {"comp_weight_pp": {"medium": 5, "high": 8, "critical": 10}}},
    "financial": {"enabled": true, "confidence_gate": 0.65,
      "caps": {"wacc_pp": {"medium": 0.4, "high": 1.0}, "tg_pp": {"medium": 0.2, "high": 0.6}}},
    "sentiment": {"enabled": true, "confidence_gate": 0.65,
      "caps": {"sent_weight_pp": {"medium": 5, "high": 10}}},
    "main": {"enabled": true}
  }
}
```

- 保存时严格校验（非法值报错），版本号在磁盘当前版本上自增；读取时非法值回退默认，不阻断跑批。
- 每批开始快照写入 `state.json`，运行中的任务不受后续保存影响。
- 面板可只读查看实际提示词（`prompt_preview`）。

## 11. 失败模式

| 情况 | 处理 |
|---|---|
| 无 API Key | 提交阶段直接 400，提示 `~/.dsh-valuation/sentiment-llm.env` |
| 专家调用失败 | 该专家 `ok=false`，其余专家继续；全部失败 → `decision=error` |
| 主审调用失败 | 建议全部作废（`reject`），任务级 `error`，不改参数 |
| 建议全被门槛拦下 | `hold` + 一句话“建议未过证据门槛” |
| 主审关闭 | `hold`，建议仅留痕 |
| apply 重跑失败 | 回滚 baseline，`apply.error`，结果沿用基线 |
| 配置损坏 | `load()` 回退默认；保存时严格报错 |

## 12. 已知局限

1. **证据同源**：专家证据来自同一引擎输入，缺少独立外部证据/盲评，存在自我确认风险。
2. **LLM 非确定性**：temperature 0.1 但无 seed；建议分布与重复运行方差未量化。
3. **离散网格**：5pp/0.2pp 的步长是工程近似，连续化后需重新讨论收敛性。
4. **无跨日状态**：当前每批独立快照，尚未把“上一批通过参数”作为下一批先验（路线第三层）。
5. **评估样本少**：人工采纳数据需累积；周环比需要同指数多次影子任务。
6. **模型版本漂移**：`model` 可配，需在记录中锁定模型/提示词版本以便复现。
