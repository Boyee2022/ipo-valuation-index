#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stat_validation.py — 估值参数不确定性量化与统计校验模块（llm-ipo-valuation v3.4.3）

目的：对估值引擎中的主观判断参数做系统性统计检验，输出可审计的置信区间与参数影响度。
方法：
  1) 蒙特卡洛模拟（默认 3000 次）：按 assets/calibration_params.json 的先验分布对
     关键主观参数联合抽样 → 重跑引擎 → 估值分布（P5-P95/90%预测区间、直方图数据）；
  2) 参数弹性分析：每个参数单独 ±1σ 扰动 → 估值变化% → OLS log-log 弹性系数；
  3) 相关性：蒙特卡洛样本中 参数扰动值 vs 估值 的 Spearman 秩相关；
  4) 稳健性检验：3 种权重方案 + 可比极端样本剔除 → 中枢变化%；
  5) 修正估值区间：蒙特卡洛 90% 区间与原始情景区间对照，给出修正结论。

用法：
  python stat_validation.py <input.json> <engine_output.json> -o <stat.json>
                 [--n 3000] [--seed 42] [--calibration <calib.json>] [--case <case_id>]
纯标准库（Python 3.8+），无第三方依赖；结果全部可复现（固定 seed）。

参数扰动设计（与 calibration_params.json 对应）：
  wacc / net_margin / terminal_growth / sentiment  —— 高斯加性（pp）
  growth_forecast / comparable_multiples            —— 对数正态乘性（common_factor 控制组内相关性）
  quality_indicators                                —— 高斯加性（pp，clamp [0,1]）

v3.1.0 重构（2026-08-14，技能 v3.2）：
  * 扰动逻辑统一（rng 顺序不变）/ success_rate / 双向弹性 / run_validation 抽取
v3.2.0 强化（2026-08-14，技能 v3.3）：
  * wacc 扰动基准读引擎 wacc_model.wacc_used（CAPM 模型值生效时一致）
  * use_mc_calibration：用历史现金流波动率（cashflow_statistics.std_growth）校准 growth_forecast.sigma
    （只改分布参数，PARAM_ORDER 与 rng 序列零变化 → seed 复算承诺不变）
v3.3.0 强化（2026-08-19，技能 v3.6，B8）：
  * 弹性方向异常自动诊断增强：_detect_clamp_truncation 检测 ±1σ 扰动是否被 clamp 截断于边界，
    方向异常时附加"扰动被截断→弹性失真"说明（替代仅标记不解释）
v3.4.3 修复（2026-10-03，技能 v3.16.9，**负增速假设**标的 MC 偏差 + 弹性诊断失效）：
  * growth_forecast 的 clamp_abs 是**绝对**区间（缺省 [0.0, 2.5]），其下界 0.0 隐含「增速不可能为负」
    的假设——对**成熟期/衰退期标的**（营收负增长）不成立。乘性扰动 v×mult 在基准值 v<0 时
    **两侧均落在 0 以下**，被下界 0.0 全部截回 0.0（格力电器案例：2026 增速假设 −2%，
    mult∈[exp(−3σ), exp(+3σ)] 使 v×mult∈[−4.2%, −0.9%]，**正负两侧皆被截断**）：
      ① MC 的 3000 次抽样中该年增速**恒为 0%**，基准年被静默抬升 → MC 区间系统性上偏；
      ② ±1σ 点扰动同被抬升 → 弹性「±1σ 同号非单调」（+4.67% / +1.40%），方向诊断误报。
  * 修复：新增 _growth_lo()——**基线感知下界**。仅当基准值 v<0 时把下界放宽到
    min(clamp_abs[0], v×exp(4σ))；v≥0 时返回原 clamp_abs[0]。因正数 × 正乘子恒 ≥0 > 下界，
    该放宽对**全部非负增速假设的输入为严格空操作**（rng 序列与 MC/弹性输出逐位不变，
    已用 27 例 A/B 验证）。_clamp_hit_one 的 growth_forecast 分支同步改为逐键用 _growth_lo 判定。
  * 与 v3.4.2 的边界差异：v3.4.2 的基线感知放宽**只在弹性诊断路径**（_elasticity_dists）；
    本例 MC 本身即被污染，故修复落在 _perturb_param 的公共路径。二者原理一致
    （「路径级基线感知放宽，绝不放宽全局」）。
v3.4.2 修复（2026-10-01，技能 v3.16.6，低 WACC/低 tg 标的弹性诊断失效）：
  * 新增 _elasticity_dists：**弹性诊断专用**的「基线感知 clamp」——把高斯类参数（wacc /
    net_margin / terminal_growth）的 clamp 在诊断路径上放宽到「基准值 ±2σ」，使基准值落在
    clamp 内、±1σ 双向均不触界。原区间下，基准值低于下界的标的（长江电力 wacc 6.5% < 0.07、
    tg 2.0% = 下界）两侧扰动同被抬升 → 「±1σ 同号非单调」＋「−1σ 零响应」，弹性诊断失效。
  * **MC 抽样口径零变化**：MC 仍用原始 dists，故全部历史案例的 MC 区间逐位不变（已用 27 例 A/B 验证）。
    曾试将全局 clamp 下界放宽（wacc 0.07→0.04、tg 0.02→0.00），经验证会使 22/27 案例的 MC 尾部
    显著膨胀（wacc→0.04 时 1/(wacc−tg) 双曲放大，如茅台 std 2582→12485），故**不采用全局放宽**。
  * _detect_clamp_truncation 改为双向检测：原仅查调用侧（+1σ），基准值低于 clamp 下界时
    漏报 −1σ 侧截断（拆出 _clamp_hit_one 供两方向复用）；诊断现改用 dists_el，正常情形下不再误报。
  * EXPECTED_SIGNS["quality_indicators"] 由 +1 改为 None：指标束方向混合（ocf 越高越好、
    receivables/inventory/nonrecurring 越低越好），单一符号期望不成立——长江电力案例的
    「+1σ 方向异常 −0.08%」实为 nonrecurring_ratio 越过 5% 阈值的**真实**质量降档，非缺陷。
v3.4.1 修复（2026-09-24，技能 v3.14.2，质量指标 null 扰动崩溃）：
  * _perturb_param 的 quality_indicators 分支原以 `if key in fin` 判断，当输入显式提供该键
    且值为 null（未披露）时进入分支，`None + float` 抛 TypeError 使统计层整体失败
    （与引擎 v2.11.3 修复的是同一类缺陷）。现改为对 None/非数值跳过扰动。
  * 影响面：质量指标全部为数值的输入输出零变化（rng 消耗序列不变，seed 复算保持）；
    仅「含 null 质量指标」的输入由崩溃转为可运行。
v3.4.0 强化（2026-08-19，技能 v3.8，v3.6b 批次 2）：
  * B4 增速×倍数尾部联动：comparable_multiples.cross_corr_growth（ρ）将 growth 公共因子 z 与倍数
    公共因子 zc 相关变换（zc_eff=ρ·z+√(1−ρ²)·zc）——只重组已有抽数，rng 序列与分布均不变，seed 复算保持；
    默认 ρ=0 零变化；cxmt 案例 0.5 建模"周期回落时增速与倍数同向崩溃"尾部风险
  * B5 流动性折扣入 MC：PARAM_ORDER 末尾条件追加 liquidity_discount（未启用不消耗 rng）；
    put_option/blend 扰动 volatility，empirical 扰动 discount_pct；mc_config 输出扰动配置留痕
  * 扰动逻辑统一：apply_perturbation / point_perturbation 共用 _perturb_param
    （各参数 rng 抽数顺序与 v3.0.0 完全一致，seed 复算承诺不变）
  * 输出 success_rate 与顶层 validation_passed / validation_status（<95% 即"统计校验未通过"）
  * 弹性输出双向：新增 delta_pct_minus_1sigma（-1σ）与 direction_flag / elasticity_issues
    （+1σ 方向异常、±1σ 同号非单调自动检测）
  * 抽取 run_validation() 供冒烟测试内存调用
"""

import argparse
import copy
import json
import math
import random
import statistics
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from valuation_engine import Engine  # 复用引擎（同目录）

# ---------- 统计工具（纯 stdlib） ----------

def percentile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[int(k)]
    return xs[f] * (c - k) + xs[c] * (k - f)


def spearman(xs, ys):
    """Spearman 秩相关（纯 Python）。"""
    n = len(xs)
    if n < 3:
        return 0.0
    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    sx = math.sqrt(sum((v - mx) ** 2 for v in rx))
    sy = math.sqrt(sum((v - my) ** 2 for v in ry))
    return cov / (sx * sy) if sx and sy else 0.0


def ols_slope(xs, ys):
    """OLS 斜率（弹性近似：log-log）。"""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    return num / den if den else None


def histogram(xs, bins=20):
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-9:
        return {"bins": [], "counts": []}
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in xs:
        idx = min(bins - 1, int((v - lo) / step))
        counts[idx] += 1
    edges = [round(lo + i * step, 1) for i in range(bins + 1)]
    return {"edges": edges, "counts": counts}


# ---------- 参数扰动（v3.1.0：统一实现，保持 v3.0.0 rng 抽数顺序） ----------

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _growth_lo(v, clamp_abs, sigma, guard_sigma=4.0):
    """v3.4.3：growth_forecast 的下界——**基线感知**（仅当基准增速为负时放宽）。

    clamp_abs 缺省 [0.0, 2.5] 的绝对下界 0.0 隐含「增速不可能为负」，对成熟/衰退期标的
    （营收负增长、显式假设增速为负）不成立：乘性扰动 v×mult 在 v<0 时正负两侧都 <0，
    全部被截回 0.0 → 基准年增速在 MC 全样本与 ±1σ 点扰动中被静默抬升为 0%。
    仅在 v<0 时把下界放到 min(clamp_abs[0], v×exp(guard_sigma·σ))（v<0 ⇒ 结果 <v<0）；
    v≥0 时原样返回 clamp_abs[0]（正数×正乘子恒 ≥0，永不触下界）→ 对非负增速输入为严格空操作。
    """
    try:
        lo = float(clamp_abs[0])
    except (TypeError, ValueError, IndexError):
        lo = 0.0
    try:
        vf = float(v)
    except (TypeError, ValueError):
        return lo
    if vf >= 0:
        return lo
    try:
        s = float(sigma)
    except (TypeError, ValueError):
        s = 0.25
    return min(lo, vf * math.exp(guard_sigma * max(0.0, s)))


PARAM_ORDER = ["wacc", "net_margin", "terminal_growth", "growth_forecast",
               "comparable_multiples", "sentiment", "quality_indicators",
               "liquidity_discount"]  # v3.4.0 B5：末尾条件追加——未启用不消耗 rng（seed 复算保持）
# 弹性方向期望符号（+1=参数增大估值升，-1=参数增大估值降）；用于方向一致性自动检测
# v3.4.2：quality_indicators 置 None（**方向不设期望**）——该参数是「指标束」，同一 +δ 同时作用于
#   盈利质量方向相反的四项（ocf_to_net_profit 越高越好；receivables/inventory/nonrecurring 越低越好），
#   单一符号的经济学方向本身不成立（长江电力案例：+5pp 使 nonrecurring_ratio 0.031→0.081 越过 5% 阈值，
#   质量分降档 → 估值 −0.08%，属**真实**机制而非缺陷）。置 None 后仅跳过方向告警，弹性数值与 MC 均不变。
EXPECTED_SIGNS = {"comparable_multiples": 1, "growth_forecast": 1, "wacc": -1,
                  "net_margin": 1, "terminal_growth": 1, "sentiment": 1, "quality_indicators": None,
                  "liquidity_discount": -1}  # v3.4.0 B5：折扣增大 → 估值降


def _perturb_param(d, dists, param, rng, base_sent_adj=0.0, direction=1.0, sample=None, ctx=None):
    """原地扰动单个参数（v3.1.0：apply_perturbation / point_perturbation 共用）。
    rng 为 None 时按确定性 ±1σ（direction=+1/-1，弹性分析用）；否则按 rng 随机抽样（MC 用）。
    注意：各参数内部 rng 抽数顺序必须与 v3.0.0 逐行一致（seed 可复算承诺，勿重排）。
    v3.4.0 B4：ctx 为跨参数上下文（MC 同一轮内传递 growth 公共因子，用于增速×倍数尾部联动）；
    相关性变换只重组已有抽数（zc_eff=ρ·z+√(1−ρ²)·zc），rng 抽数序列与分布均不变 → seed 复算保持。
    v3.4.0 B5：liquidity_discount 为 PARAM_ORDER 末尾条件参数——未启用直接 return（不消耗 rng，旧输入序列不变）。"""
    fin = d["financials"]
    sent = d.setdefault("sentiment", {})
    comps = d.get("comparables", [])
    if ctx is None:
        ctx = {}

    if param == "wacc":
        w = dists["wacc"]
        fin["wacc"] = _clamp((fin.get("wacc") or 0.11) +
                             (rng.gauss(0, w["sigma_pp"] / 100.0) if rng is not None
                              else direction * w["sigma_pp"] / 100.0),
                             w["clamp"][0], w["clamp"][1])
        if sample is not None:
            sample["wacc"] = fin["wacc"]
    elif param == "net_margin":
        m = dists["net_margin"]
        fin["net_margin"] = _clamp((fin.get("net_margin") or 0.1) +
                                   (rng.gauss(0, m["sigma_pp"] / 100.0) if rng is not None
                                    else direction * m["sigma_pp"] / 100.0),
                                   m["clamp"][0], m["clamp"][1])
        if sample is not None:
            sample["net_margin"] = fin["net_margin"]
    elif param == "terminal_growth":
        t = dists["terminal_growth"]
        fin["terminal_growth"] = _clamp((fin.get("terminal_growth") or 0.05) +
                                        (rng.gauss(0, t["sigma_pp"] / 100.0) if rng is not None
                                         else direction * t["sigma_pp"] / 100.0),
                                        t["clamp"][0], t["clamp"][1])
        if sample is not None:
            sample["terminal_growth"] = fin["terminal_growth"]
    elif param == "growth_forecast":
        gf = dists["growth_forecast"]
        items = list((fin.get("growth_forecast") or {"y1": 0.2}).items())
        # v3.4.3：下界改为「基线感知」——负增速假设（成熟/衰退期）不再被绝对下界 0.0 截断。
        # 不新增 rng 抽数，抽样序列与 v3.4.2 逐位一致（seed 复算承诺保持）。
        g_sigma = gf.get("sigma", 0.25)
        if rng is not None:
            z = rng.gauss(0, 1)  # 组内公共因子（先抽）
            ctx["z_growth"] = z  # v3.4.0 B4：供 comparable_multiples 尾部联动使用
            gf_new = {}
            for k, v in items:
                z_i = rng.gauss(0, 1)
                mult = math.exp(gf["sigma"] * (gf["common_factor"] * z + (1 - gf["common_factor"]) * z_i))
                gf_new[k] = _clamp(v * mult, _growth_lo(v, gf["clamp_abs"], g_sigma), gf["clamp_abs"][1])
            fin["growth_forecast"] = gf_new
        else:
            mult = math.exp(direction * gf["sigma"])
            fin["growth_forecast"] = {k: _clamp(v * mult, _growth_lo(v, gf["clamp_abs"], g_sigma),
                                                gf["clamp_abs"][1]) for k, v in items}
        if sample is not None:
            gf_new = fin["growth_forecast"]
            sample["growth_mult"] = gf_new.get("2026") if "2026" in gf_new else list(gf_new.values())[0]
    elif param == "comparable_multiples":
        cm = dists["comparable_multiples"]
        mc_lo, mc_hi = cm.get("mult_clamp", [0.3, 3.0])
        if rng is not None:
            zc = rng.gauss(0, 1)  # 跨公司公共因子（先抽）
            # v3.4.0 B4：增速×倍数尾部联动——用 growth 公共因子做相关变换（zc_eff 仍标准正态）
            rho = float(cm.get("cross_corr_growth", 0.0) or 0.0)
            zc_eff = zc
            if rho and ctx.get("z_growth") is not None:
                zc_eff = rho * ctx["z_growth"] + math.sqrt(max(0.0, 1.0 - rho * rho)) * zc
            for c in comps:
                zc_i = rng.gauss(0, 1)
                mult = _clamp(math.exp(cm["sigma"] * (cm["common_factor"] * zc_eff + (1 - cm["common_factor"]) * zc_i)),
                              mc_lo, mc_hi)
                for key in ("pe", "ps", "ev_ebitda"):
                    if c.get(key):
                        c[key] = c[key] * mult
            if sample is not None:
                sample["multiple_mult"] = _clamp(math.exp(cm["sigma"] * cm["common_factor"] * zc_eff), mc_lo, mc_hi)
        else:
            mult = _clamp(math.exp(direction * cm["sigma"]), mc_lo, mc_hi)
            for c in comps:
                for key in ("pe", "ps", "ev_ebitda"):
                    if c.get(key):
                        c[key] = c[key] * mult
    elif param == "sentiment":
        s = dists["sentiment"]
        sent["sentiment_adjustment_pct"] = _clamp(base_sent_adj +
                                                  (rng.gauss(0, s["sigma_pp"] / 100.0) if rng is not None
                                                   else direction * s["sigma_pp"] / 100.0),
                                                  -0.10, 0.10)
        if sample is not None:
            sample["sentiment"] = sent["sentiment_adjustment_pct"]
    elif param == "quality_indicators":
        qi = dists["quality_indicators"]
        for key in ("ocf_to_net_profit", "receivables_to_revenue", "inventory_to_revenue", "nonrecurring_ratio"):
            # v3.4.1 修复：显式 null（未披露）的指标跳过扰动——原实现 `key in fin` 为真时
            # 直接参与算术，None + float 抛 TypeError 使整个统计层失败；
            # 引擎 v2.11.3 起质量评分卡对 null 指标记 0 分，此处同步跳过以保持口径一致。
            # 注：非 None 指标的 rng 消耗序列不变 → 完整输入的 seed 复算结果与 v3.4.0 一致。
            v = fin.get(key)
            if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            fin[key] = _clamp(v + (rng.gauss(0, qi["sigma_pp"] / 100.0) if rng is not None
                                   else direction * qi["sigma_pp"] / 100.0),
                              qi["clamp"][0], qi["clamp"][1])
        if sample is not None:
            sample["quality"] = fin.get("ocf_to_net_profit", 0.9)
    elif param == "liquidity_discount":
        # v3.4.0 B5：流动性折扣 σ/T 入 MC——PARAM_ORDER 末尾条件参数。
        # 未启用直接 return（不消耗 rng）→ 旧输入 rng 序列与 v3.3.0 完全一致（seed 复算保持）。
        # 启用时：put_option/blend 扰动 volatility（σ），empirical 扰动 discount_pct（经验折扣）。
        liq = d.get("liquidity") or {}
        if not liq.get("enabled"):
            return d
        cfg = dists.get("liquidity_discount") or {"sigma_pp": 5, "clamp": [0.05, 0.95]}
        delta = (rng.gauss(0, cfg["sigma_pp"] / 100.0) if rng is not None
                 else direction * cfg["sigma_pp"] / 100.0)
        method = str(liq.get("method", "put_option"))
        if method == "empirical":
            disc = float(liq.get("discount_pct") or 0.2)
            liq["discount_pct"] = _clamp(disc + delta, 0.0, 0.5)
            if sample is not None:
                sample["liquidity_discount"] = liq["discount_pct"]
        else:  # put_option / blend：扰动波动率 σ（T 固定）
            vol = float(liq.get("volatility") or 0.4)
            liq["volatility"] = _clamp(vol + delta, cfg["clamp"][0], cfg["clamp"][1])
            if sample is not None:
                sample["liquidity_vol"] = liq["volatility"]
    return d


def _elasticity_dists(data, dists):
    """v3.4.2：弹性诊断专用分布——把高斯类参数的 clamp 放宽到「基准值 ±2σ」，
    使基准值本身落在 clamp 内、±1σ 双向扰动均不触界。

    背景：clamp 是**绝对**区间（wacc [0.07,0.16]、terminal_growth [0.02,0.10]），
    当标的基准值落在区间外（长江电力 wacc 6.5% < 0.07、tg 2.0% = 下界）时，
    ±1σ（甚至 ±2σ）扰动被同向压回边界 → 弹性「同号非单调」、下侧零响应，诊断失效。

    修复边界：**只改诊断路径**（±1σ 点扰动），MC 抽样继续用原始 dists →
    全部历史案例的 MC 区间逐位不变（曾试放宽全局 clamp，会因 wacc→0.04 时
    1/(wacc−tg) 双曲放大而使 22/27 案例 MC 尾部显著膨胀，故弃用该方案）。
    """
    out = copy.deepcopy(dists)
    fin = (data.get("financials") or {})
    bases = {"wacc": fin.get("wacc"),
             "net_margin": fin.get("net_margin"),
             "terminal_growth": fin.get("terminal_growth")}
    for param, base in bases.items():
        cfg = out.get(param)
        if not isinstance(cfg, dict) or base is None or "clamp" not in cfg:
            continue
        try:
            base = float(base)
            pad = float(cfg.get("sigma_pp", 0.0)) / 100.0 * 2.0
        except (TypeError, ValueError):
            continue
        lo, hi = cfg["clamp"]
        cfg["clamp"] = [min(lo, base - pad), max(hi, base + pad)]
    # quality_indicators：clamp [0,1] 是按「比率型指标」设计，但 ocf_to_net_profit 是
    # 覆盖倍数（健康标的常 > 1，如长江电力 1.7553）——+1σ 会把 1.80 截回 1.0，使方向反号。
    # 诊断路径按实际取值放宽到 [min−2σ, max+2σ]；MC 抽样仍用 clamp [0,1] 不变。
    qcfg = out.get("quality_indicators")
    if isinstance(qcfg, dict) and "clamp" in qcfg:
        vals = [fin.get(k) for k in ("ocf_to_net_profit", "receivables_to_revenue",
                                     "inventory_to_revenue", "nonrecurring_ratio")]
        vals = [float(v) for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if vals:
            try:
                pad = float(qcfg.get("sigma_pp", 0.0)) / 100.0 * 2.0
            except (TypeError, ValueError):
                pad = 0.0
            lo, hi = qcfg["clamp"]
            qcfg["clamp"] = [min(lo, min(vals) - pad), max(hi, max(vals) + pad)]
    return out


def _detect_clamp_truncation(param, dists, data, base_sent_adj, direction=1.0):
    """v3.3.0 B8：检测单参数 ±1σ 点扰动是否被 clamp 截断于边界。
    v3.4.2：改为**双向**检测——原实现只查调用侧方向（+1σ）。当基准值本身低于 clamp 下界时
    （长江电力案例：wacc 6.5% < 原下界 7.0%、tg 2.0% = 原下界），−1σ 侧被截断而上侧不触界 →
    漏报，告警只留「±1σ 同号非单调」而无截断说明，读者无法定位根因。
    返回说明字符串（如"触下界 0.04（反向 -1σ）"）；两侧均未触界返回 None。"""
    hit = _clamp_hit_one(param, dists, data, base_sent_adj, direction)
    if hit:
        return hit
    tag = "反向 -1σ" if direction > 0 else "反向 +1σ"
    hit2 = _clamp_hit_one(param, dists, data, base_sent_adj, -direction)
    return f"{hit2}（{tag}）" if hit2 else None


def _clamp_hit_one(param, dists, data, base_sent_adj, direction=1.0):
    """单方向 clamp 触界检测（v3.4.2 由 _detect_clamp_truncation 拆出，供双向调用）。"""
    try:
        pd = point_perturbation(data, dists, param, direction, base_sent_adj)
    except Exception:
        return None
    cfg = dists.get(param) or {}
    lo = hi = val = None
    if param == "wacc":
        val = pd["financials"].get("wacc"); lo, hi = cfg.get("clamp", [0.02, 0.25])
    elif param == "net_margin":
        val = pd["financials"].get("net_margin"); lo, hi = cfg.get("clamp", [-0.5, 0.6])
    elif param == "terminal_growth":
        val = pd["financials"].get("terminal_growth"); lo, hi = cfg.get("clamp", [0.0, 0.10])
    elif param == "sentiment":
        val = (pd.get("sentiment") or {}).get("sentiment_adjustment_pct"); lo, hi = -0.10, 0.10
    elif param == "quality_indicators":
        lo, hi = cfg.get("clamp", [0.0, 1.0])
        for k in ("ocf_to_net_profit", "receivables_to_revenue", "inventory_to_revenue", "nonrecurring_ratio"):
            v = pd["financials"].get(k)
            if isinstance(v, (int, float)) and (abs(v - lo) < 1e-9 or abs(v - hi) < 1e-9):
                val = v
                break
    elif param == "growth_forecast":
        # v3.4.3：下界逐键用「基线感知」_growth_lo（与 _perturb_param 同步），
        # 基准值为负时下界随之下移 → 不再把「正常扰动」误报为触界截断。
        gf = pd["financials"].get("growth_forecast") or {}
        base_gf = (data.get("financials") or {}).get("growth_forecast") or {}
        ca = cfg.get("clamp_abs", [-0.5, 2.0])
        hi = ca[1] if isinstance(ca, (list, tuple)) and len(ca) > 1 else None
        sigma = cfg.get("sigma", 0.25)
        for k, v in gf.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            lo_k = _growth_lo(base_gf.get(k, v), ca, sigma)
            if abs(v - lo_k) < 1e-9:
                return f"触下界 {round(lo_k, 4)}"
            if hi is not None and abs(v - hi) < 1e-9:
                return f"触上界 {hi}"
        return None
    elif param == "comparable_multiples":
        # 乘性扰动，clamp 作用于乘子（0.3~3.0）；方向极端时近似判定
        lo, hi = cfg.get("mult_clamp", [0.3, 3.0])
        mult = math.exp(direction * cfg.get("sigma", 0.4))
        if mult <= lo + 1e-9:
            return "倍数乘子触下界 0.3"
        if mult >= hi - 1e-9:
            return "倍数乘子触上界 3.0"
        return None
    if val is None or lo is None:
        return None
    if abs(val - lo) < 1e-9:
        return f"触下界 {lo}"
    if abs(val - hi) < 1e-9:
        return f"触上界 {hi}"
    return None


def apply_perturbation(data, dists, rng, base_sent_adj):
    """对输入 data 深拷贝并按 dists 分布施加一次联合扰动，返回 (new_data, sample_params)。
    v3.1.0：循环 PARAM_ORDER 调用 _perturb_param，rng 消耗次序与 v3.0.0 完全一致。
    v3.4.0 B4：ctx 在参数间传递 growth 公共因子（增速×倍数尾部联动），不新增 rng 抽数。"""
    d = copy.deepcopy(data)
    sample = {}
    ctx = {}
    for param in PARAM_ORDER:
        _perturb_param(d, dists, param, rng, base_sent_adj, sample=sample, ctx=ctx)
    return d, sample


def point_perturbation(data, dists, param, direction=1.0, base_sent_adj=0.0):
    """弹性分析：单参数确定性点扰动（±1σ）。返回 perturbed_data。
    v3.1.0：委托 _perturb_param（rng=None），语义与 v3.0.0 一致。"""
    d = copy.deepcopy(data)
    _perturb_param(d, dists, param, None, base_sent_adj, direction)
    return d


# ---------- 主流程 ----------

def run_mc(data, dists, n, seed, base_sent_adj):
    rng = random.Random(seed)
    values, samples = [], []
    base_engine = Engine(data)
    base_mid = base_engine.run()["synthesis"]["weighted_mid"]
    for i in range(n):
        pd, smp = apply_perturbation(data, dists, rng, base_sent_adj)
        try:
            mid = Engine(pd).run()["synthesis"]["weighted_mid"]
        except Exception:
            continue  # 极端样本引擎降级失败则跳过（记录于 robustness）
        values.append(mid)
        smp["value"] = mid
        samples.append(smp)
    return values, samples, base_mid


def run_validation(data, eng, calib, n=None, seed=None, case=None, calibration_file=None):
    """统计校验主流程（v3.2.0：从 main() 抽出，供 CLI 与冒烟测试内存调用）。
    data=估值输入 dict；eng=引擎输出 dict；calib=校准参数库 dict。
    返回 stat dict（含 success_rate / validation_passed / 双向弹性 / elasticity_issues）。
    v3.2.0：wacc 扰动基准读引擎 wacc_model.wacc_used；use_mc_calibration 用历史波动率校准 growth sigma（只改参数，不改 rng 序列）。"""
    dists = dict(calib["default"]["distributions"])
    if case and case in calib.get("cases", {}):
        dists.update(calib["cases"][case].get("distributions", {}))
    n = n or calib["default"]["mc_n"]
    seed = seed if seed is not None else calib["default"]["seed"]

    # v3.2.0：深拷贝 data（避免污染调用方）；wacc 扰动基准 = 引擎 wacc_model.wacc_used（激活时）
    data = copy.deepcopy(data)
    wacc_used = (eng.get("wacc_model") or {}).get("wacc_used")
    if wacc_used is not None:
        data.setdefault("financials", {})["wacc"] = wacc_used
    # v3.2.0：MC 先验校准——历史现金流波动率覆盖 growth_forecast.sigma（只改分布参数，不改 PARAM_ORDER/rng 序列）
    # 上限 0.60 保护：超高波动历史序列（如 300%+ 年增速）经乘性扰动会指数爆炸，cap 保持 MC 区间可解释
    if (data.get("preferences") or {}).get("use_mc_calibration"):
        std_g = (eng.get("cashflow_statistics") or {}).get("std_growth")
        if std_g:
            dists["growth_forecast"] = dict(dists.get("growth_forecast") or {})
            dists["growth_forecast"]["sigma"] = min(0.60, max(0.10, std_g))

    # 基准情绪修正（引擎自动值），供扰动与弹性使用
    base_sent_adj = eng["scenarios"]["base"]["adjustments"]["sentiment"]["adjustment_pct"]

    # 1) 蒙特卡洛
    values, samples, base_mid = run_mc(data, dists, n, seed, base_sent_adj)
    vals = sorted(values)
    p = lambda q: percentile(vals, q)
    p5, p25, p50, p75, p95 = p(0.05), p(0.25), p(0.50), p(0.75), p(0.95)
    mean_v, std_v = statistics.mean(vals), statistics.pstdev(vals)
    success_rate = len(vals) / n if n else None
    mc = {
        "n_success": len(vals), "n_total": n,
        "success_rate": round(success_rate, 4) if success_rate is not None else None,
        "mean": round(mean_v, 2), "std": round(std_v, 2),
        "p5": round(p5, 2), "p25": round(p25, 2), "p50": round(p50, 2),
        "p75": round(p75, 2), "p95": round(p95, 2),
        "ci90": [round(p5, 2), round(p95, 2)],
        "histogram": histogram(vals, calib["default"]["reporting"]["histogram_bins"]),
    }

    # 2) 参数弹性（单参数 ±1σ 点扰动；v3.1.0 双向输出 + 方向一致性自动检测）
    #    v3.4.2：弹性诊断使用「基线感知」clamp（见 _elasticity_dists）——仅此路径放宽，
    #    MC 抽样仍用原始 dists，保证历史案例 MC 逐位不变。
    params = PARAM_ORDER
    dists_el = _elasticity_dists(data, dists)
    elasticity = {}
    elasticity_issues = []
    for param in params:
        pd = point_perturbation(data, dists_el, param, 1.0, base_sent_adj)
        try:
            v_up = Engine(pd).run()["synthesis"]["weighted_mid"]
            pd2 = point_perturbation(data, dists_el, param, -1.0, base_sent_adj)
            v_dn = Engine(pd2).run()["synthesis"]["weighted_mid"]
            delta_up = (v_up - base_mid) / base_mid * 100.0
            delta_dn = (v_dn - base_mid) / base_mid * 100.0
            issues = []
            exp = EXPECTED_SIGNS.get(param)
            if exp is not None and delta_up * exp < 0:
                issues.append(f"{param}: +1σ 方向异常（期望{'升' if exp > 0 else '降'}，实际 {delta_up:+.2f}%）")
            if exp is not None and delta_up * delta_dn > 0:
                issues.append(f"{param}: ±1σ 同号非单调（{delta_up:+.2f}%/{delta_dn:+.2f}%），检查 clamp 是否作用于乘子")
            # v3.3.0 B8：方向异常时检测 clamp 截断（扰动触界 → 弹性失真诊断）
            if issues:
                trunc = _detect_clamp_truncation(param, dists_el, data, base_sent_adj, 1.0)
                if trunc:
                    issues.append(f"{param}: 扰动被 clamp 截断（{trunc}），弹性可能失真——建议放宽扰动幅度或检查边界合理性")
            elasticity_issues.extend(issues)
            elasticity[param] = {
                "value_1sigma_up": round(v_up, 2), "value_1sigma_dn": round(v_dn, 2),
                "base_value": round(base_mid, 2),
                "delta_pct_1sigma": round(delta_up, 2),
                "delta_pct_minus_1sigma": round(delta_dn, 2),
                "signed_delta_pct": round((v_up - v_dn) / base_mid * 100.0, 2),
                "direction_flag": "异常" if issues else "正常",
            }
        except Exception as e:
            elasticity[param] = {"error": str(e)}

    # 3) 相关性（蒙特卡洛样本：参数扰动值 vs 估值，Spearman）
    corr = {}
    keys = ["wacc", "net_margin", "terminal_growth", "growth_mult", "multiple_mult", "sentiment"]
    for k in keys:
        xs = [s.get(k) for s in samples if s.get(k) is not None and s.get("value") is not None]
        ys = [s["value"] for s in samples if s.get(k) is not None and s.get("value") is not None]
        corr[k] = {"spearman_r": round(spearman(xs, ys), 3), "n": len(xs)}

    # 4) 稳健性检验
    robust = {}
    schemes = calib["default"]["robustness"]["weight_schemes"]
    for name, w in schemes.items():
        pd = copy.deepcopy(data)
        pd.setdefault("preferences", {})["weights"] = w
        try:
            mid = Engine(pd).run()["synthesis"]["weighted_mid"]
            robust.setdefault("weights", {})[name] = {
                "weights": w, "mid": round(mid, 2),
                "delta_pct_vs_default": round((mid - base_mid) / base_mid * 100.0, 2),
            }
        except Exception as e:
            robust.setdefault("weights", {})[name] = {"error": str(e)}
    # 可比极端样本剔除（剔除倍数最高者）
    if calib["default"]["robustness"].get("exclude_extreme_comparable", True) and data.get("comparables"):
        comps = data["comparables"]
        def max_key(c):
            for k in ("ps", "pe"):
                if c.get(k):
                    return k, c[k]
            return None, 0
        scored = [(max_key(c), i) for i, c in enumerate(comps)]
        if scored:
            (k, v), idx = max(scored, key=lambda t: t[0][1] if t[0][1] else 0)
            pd = copy.deepcopy(data)
            pd["comparables"] = [c for i, c in enumerate(pd["comparables"]) if i != idx]
            try:
                mid_ex = Engine(pd).run()["synthesis"]["weighted_mid"]
                robust["comparable_exclusion"] = {
                    "excluded": comps[idx].get("name"), "key": k, "value": v,
                    "mid": round(mid_ex, 2),
                    "delta_pct_vs_default": round((mid_ex - base_mid) / base_mid * 100.0, 2),
                }
            except Exception as e:
                robust["comparable_exclusion"] = {"error": str(e)}

    # 5) 修正估值区间
    raw_interval = eng["synthesis"]["interval"]
    raw_mid = eng["synthesis"]["weighted_mid"]
    adjusted = {
        "raw_interval": raw_interval,
        "raw_mid": round(raw_mid, 2),
        "mc_ci90": mc["ci90"],
        "mc_p50": mc["p50"],
        "synthesis_interval": [round(max(raw_interval[0], mc["ci90"][0]), 2),
                               round(min(raw_interval[1], mc["ci90"][1]), 2)],
        "synthesis_mid": round((mc["p50"] + raw_mid) / 2.0, 2),
        "note": "synthesis_interval=原始情景区间∩MC 90%区间；synthesis_mid=MC中位数与原始中枢均值（稳健口径）",
    }

    validation_passed = success_rate is not None and success_rate >= 0.95
    # v3.4.0 B4/B5：记录 MC 分布配置（增速×倍数联动相关系数、流动性折扣扰动是否激活）——审计留痕
    cm_cfg = dists.get("comparable_multiples") or {}
    mc_config = {
        "growth_multiple_corr": float(cm_cfg.get("cross_corr_growth", 0.0) or 0.0),
        "liquidity_perturbed": bool((data.get("liquidity") or {}).get("enabled")),
        "note": "growth_multiple_corr=增速×倍数尾部联动相关系数（>0 建模周期回落同向崩溃）；liquidity_perturbed=流动性折扣 σ 是否纳入 MC",
    }
    out = {
        "meta": {"case": case or data.get("meta", {}).get("company"),
                 "as_of": data.get("meta", {}).get("as_of_date", ""),
                 "engine_version": eng.get("engine_version", ""),
                 "stat_version": "3.4.3", "seed": seed, "n": n,
                 "calibration_file": calibration_file or "calibration_params.json"},
        "base_mid": round(base_mid, 2),
        "monte_carlo": mc,
        "mc_config": mc_config,
        "elasticity": elasticity,
        "correlation": corr,
        "robustness": robust,
        "adjusted_interval": adjusted,
        "validation_passed": validation_passed,
        "validation_status": "通过" if validation_passed else "统计校验未通过（样本成功率<95%）",
        "elasticity_issues": elasticity_issues,
    }
    return out


def main():
    ap = argparse.ArgumentParser(description="估值参数不确定性量化与统计校验（v3.1.0）")
    ap.add_argument("input", help="估值输入 JSON（input_template.json 格式）")
    ap.add_argument("engine_output", help="引擎输出 JSON（valuation_engine.py -o 的产物）")
    ap.add_argument("-o", "--output", default=None, help="统计结果 JSON 路径")
    ap.add_argument("--n", type=int, default=None, help="蒙特卡洛次数（默认取校准库）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（默认取校准库，可复现）")
    ap.add_argument("--calibration", default=None, help="校准参数库 JSON（默认 assets/calibration_params.json）")
    ap.add_argument("--case", default=None, help="案例级校准覆盖（如 cxmt / deepseek）")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(args.engine_output, "r", encoding="utf-8") as f:
        eng = json.load(f)

    calib_path = args.calibration or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "assets", "calibration_params.json")
    with open(calib_path, "r", encoding="utf-8") as f:
        calib = json.load(f)

    out = run_validation(data, eng, calib, n=args.n, seed=args.seed, case=args.case,
                         calibration_file=os.path.basename(calib_path))

    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        mc = out["monte_carlo"]
        adjusted = out["adjusted_interval"]
        print(f"[OK] 统计结果已写入: {args.output}")
        print(f"[OK] MC 90%区间(亿): {mc['ci90']} | 中位数 {mc['p50']} | 均值 {mc['mean']}±{mc['std']}")
        print(f"[OK] 修正综合区间: {adjusted['synthesis_interval']} | 修正中枢 {adjusted['synthesis_mid']}")
        print(f"[OK] 样本成功率: {mc['n_success']}/{mc['n_total']} | 状态: {out['validation_status']}")
        top = sorted(out["elasticity"].items(), key=lambda kv: abs(kv[1].get("delta_pct_1sigma", 0)), reverse=True)
        print("[OK] 弹性Top3:", " | ".join(f"{k}:{v.get('delta_pct_1sigma')}%" for k, v in top[:3]))
        for issue in out["elasticity_issues"]:
            print(f"[WARN] {issue}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
