# Spec 04 · 数据源与 API

> 服务：`packages/batch/server.py`，默认端口 3089，仅内网。  
> 前端：`packages/workbench/src/client/page/api.ts`，`API_BASE = http://${location.hostname}:3089`。

## 1. 路由总表

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 存活、成分数据时点、`shadow_ready` |
| GET | `/api/constituents?index=sh50` | 成分券 + 权重 + 指数收盘 |
| GET | `/api/agents` | 智能体配置 + 默认值 + 标签 + 提示词预览 |
| POST | `/api/agents` | 严格校验并保存配置，版本自增 |
| POST | `/api/run` | 提交跑批，返回 `job_id` |
| POST | `/api/shadow/adopt` | 人工采纳/否决/清除 |
| GET | `/api/jobs` | 任务列表（含三情景点位、agent 模式） |
| GET | `/api/jobs/<id>` | 任务状态 + 逐券结果 + summary + shadow_metrics |
| GET | `/api/jobs/<id>/reports/<file>` | 逐券报告 / summary.html / shadow.html / *.shadow.json |

CORS 全放行；文件名白名单 `^[\w.\-]+$`，并校验 resolve 后仍在 jobs 根内。无鉴权。

## 2. 关键请求/响应

### 2.1 `GET /api/health`

```json
{"ok": true, "components_as_of": "2026-11-27", "components_rows": 50, "error": null, "shadow_ready": true}
```

`shadow_ready` 表示 LLM 密钥可用（`sentiment_llm.available()`）。

### 2.2 `GET /api/constituents`

```json
{
  "index": "sh50", "index_name": "上证50", "as_of": "2026-11-27",
  "index_close": 2650.12, "weight_computed": false,
  "rows": [{"code": "600519", "secucode": "600519.SH", "name": "贵州茅台",
            "industry": "白酒Ⅱ", "weight": 12.34, "close": 1500.0,
            "pe": 24.1, "eps": 62.3, "roe": 31.2, "total_shares": 12.56, "free_cap": 18000.0}]
}
```

- `sh50/sh180/kc50/hs300`：东财成分表；无 WEIGHT 时用自由流通市值归一化，`weight_computed=true`。
- `sse`：全市场快照，总市值权重；`rows` 约 2,201 只；`weight_computed=true`。

### 2.3 `POST /api/run`

```json
{
  "index": "sh50",
  "parallel": 3,
  "stat_n": 3000,
  "weights": {"dcf": 0.3, "comp": 0.5, "sent": 0.2},
  "sentiment_rounds": 10,
  "sentiment_mode": "rule",
  "wacc_pct": null,
  "terminal_growth_pct": null,
  "agent_mode": "off"
}
```

校验：

- `index` 必须在五指数内；`parallel` 只接受 3/10；
- `stat_n` 默认 3000；
- `wacc_pct` 1–20、`terminal_growth_pct` 0–5，且 WACC > 永续；
- `sentiment_mode=llm` 或 `agent_mode != off` 时必须有 LLM 密钥，否则 400；
- `agent_mode` 不在 off/shadow/apply 时，若 `shadow=true` 视为 shadow，否则 off。

响应：`{"job_id": "job_20261127_164845_ab12cd"}`。

### 2.4 `GET /api/jobs/<id>`

任务对象关键字段：

```json
{
  "id": "...", "index": "sh50", "created": "2026-11-27 16:48:45",
  "state": "running|done|error", "done": 12, "total": 50,
  "components_as_of": "2026-11-27", "index_close": 2650.12,
  "parallel": 3, "stat_n": 3000,
  "weights": {"dcf": 0.3, "comp": 0.5, "sent": 0.2},
  "sentiment_mode": "rule", "agent_mode": "shadow", "shadow_mode": true,
  "wacc_pct": null, "terminal_growth_pct": null,
  "rows": [{"idx": 0, "secucode": "600519.SH", "status": "ok", "weight": 12.34,
            "close": 1500.0, "per_share": 1600.0, "weighted_mid": 20000.0,
            "interval": [18000, 22000], "confidence_level": "中",
            "shadow": {"decision": "partial", "items": [...], "adoption": null}}],
  "summary": {"fitted_point": 2700.0, "fitted_point_index": 2700.0,
              "fitted_point_price_weighted": 2690.0, "fitted_point_basis": "index_weight",
              "index_close": 2650.12, "ok": 49, "skip": 1, "total": 50,
              "scenario_low": 2600.0, "scenario_high": 2800.0},
  "shadow_metrics": {...}
}
```

> 注：`summary` 的三情景点位在 `_finalize` 写入；历史任务在 `list_jobs` 里按逐券区间回填。

### 2.5 `GET /api/jobs`

```json
{"jobs": [{"id": "...", "index": "sh50", "created": "...", "state": "done",
  "done": 50, "total": 50, "components_as_of": "...", "fitted_point": 2700.0,
  "index_close": 2650.12, "scenario_low": 2600, "scenario_base": 2700, "scenario_high": 2800,
  "ok": 49, "skip": 1, "sentiment_mode": "rule", "agent_mode": "shadow",
  "shadow_mode": true, "agent_config_version": 3}]}
```

### 2.6 智能体

`GET /api/agents` 返回 `config / defaults / labels / path / exists / updated_at / model_env / llm_ready / prompts / saved`。

`POST /api/agents` body `{"config": {...}}` 或直接配置对象；严格校验，成功返回同结构 + `saved=true`。

### 2.7 采纳

```json
POST /api/shadow/adopt
{"job": "job_...", "code": "600519.SH", "action": "adopted"}
```

返回 `{"shadow": {...}, "shadow_metrics": {...}}`；仅 `done` 任务、有有效评审记录可标记。

## 3. 数据源与缓存

| 数据 | 接口/实现 | TTL |
|---|---|---|
| 指数成分 | `RPT_INDEX_TS_COMPONENT`（datacenter） | 6h |
| 上证综指全市场 | `RPT_VALUEANALYSIS_DET` 最新交易日快照（沪市 A 股） | 6h |
| 指数/个股行情 | 腾讯 `qt.gtimg.cn` | 300s |
| 财报/一致预期 | 技能 `fetch_data.py` + 东财 datacenter | 7d |
| 年报现金流 | `RPT_LICO_FN_CPD` / F10 | 7d |
| 三表驱动 | F10 利润表/现金流量表/资产负债表 | 7d |
| 质量五指标/ROIC | F10 | 7d |
| B0（归母权益） | F10 BPS × 股本 | 7d |
| 可比 β | 腾讯月线 60 个月 OLS（基准沪深300） | 24h |
| 可比池 | 东财多类指数成分并集 | 24h |
| 行业估值 | `RPT_VALUEINDUSTRY_DET`（申万二级整体法） | 24h |
| 舆情 | 东财新闻搜索 + 股吧；规则或 LLM | 6h |

缓存目录 `runtime/cache/`，临时文件名带 pid/线程，原子替换；失败不写半成品。

## 4. 上证综指口径

- 数据：东财全 A 估值快照最新交易日，筛 `.SH`。
- 权重：总市值（A+H 计全部股本）。编制口径含单样本 15% 上限，当前代码未显式截断（样本远低，需在正式口径中核实）。
- 剔除：ST/*ST（兼容 XD/XR/DR 与 S 前缀）。
- 新股：上市满一年计入；总市值前 10 名满三个月计入（以当前总市值近似日均）。
- 行业：快照 `BOARD_NAME`；ROE 用 PB/PE 推 TTM 近似（快照无 ROE 字段），仅作参考。
- 代码注释里“push2 行情列表”是旧说法，实际实现为 datacenter 快照。

## 5. 个股覆写

`~/.dsh-valuation/overrides/<secucode 点换下划线>.json`：

```json
{
  "note": "人工核定：XX 管线 rNPV 参数",
  "rnpv": {"enabled": true, "pos_overrides": {...}},
  "preferences": {"enable_rnpv": true, "method_set_mode": "routed", "layer0_check": true},
  "framework_check": {"industry_class": "pipeline_pharma"}
}
```

白名单外字段忽略；不改行情/财务；来源写入 `data_sources`。用于 rNPV/特殊行业等人工核定场景。

## 6. 失败语义

| HTTP | 场景 |
|---|---|
| 400 | 未知指数、权重/覆盖越界、LLM 未配置、配置非法、采纳动作非法 |
| 404 | 任务/证券/报告不存在 |
| 500 | 服务内部错误（返回截断信息） |

批跑内部失败不返回 5xx，而是把 row 标 `skip`/`error` 并在 `state.json` 留痕；提交失败才返回 4xx。

## 7. 安全与运维

- 只绑内网 IP；CORS `*`；无鉴权——**不要暴露到公网**。
- 报告路径白名单 + resolve 校验；配置保存严格校验；密钥只从仓库外读取。
- 健康检查：`curl http://<host>:3089/api/health`。
- 日志：启动器输出；服务本身 `log_message` 静默。
- 重启：`reconcile_running()` 清理遗留 running；不会自动续跑。

## 8. 已知问题

1. `server.py` 顶部 docstring 的 `/api/run` 参数仍写 `shadow?`，实际为 `agent_mode`，文档滞后。
2. `config.py` 注释仍提 push2，实际走 datacenter 快照。
3. 无分页/限流；全市场任务列表与 state.json 体积较大（>800 只每 10 行落盘）。
4. `CORS *` + 无鉴权只适合可信内网。
5. `/api/constituents` 全市场一次返回 2,201 行，前端渲染与首屏需关注。
6. 无 OpenAPI/schema 文件，本文档即契约；改接口需同步更新。
