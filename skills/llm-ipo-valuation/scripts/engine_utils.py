"""engine_utils.py — 估值引擎纯工具函数层（llm-ipo-valuation v3.9，D3 模块拆分）

从 valuation_engine.py 拆分出的**无引擎依赖**纯函数（统计/折现/序列处理）。
- valuation_engine.py 顶部显式导入（import 后外部 `ve.xxx` 引用仍兼容）；
- stat_validation.py / smoke_test.py 经由 valuation_engine 模块属性访问，无需改动；
- 纯标准库（math/statistics），无第三方依赖。
"""

import math
import statistics


def _norm_cdf(x):
    """标准正态累积分布函数（纯标准库）。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _ols_slope_r2(xs, ys):
    """OLS 线性回归 y=a+b·x，返回 (斜率 b, R²)。样本 <2 返回 (None, None)。"""
    n = len(xs)
    if n < 2:
        return None, None
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den == 0:
        return None, None
    b = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den
    a = my - b * mx
    ss_tot = sum((ys[i] - my) ** 2 for i in range(n))
    ss_res = sum((ys[i] - (a + b * xs[i])) ** 2 for i in range(n))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    return b, r2


def _geo_mean_growth(values):
    """几何均值增速（CAGR）：values 为按年份升序的数值列表。"""
    if len(values) < 2:
        return None
    first, last = values[0], values[-1]
    if first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / (len(values) - 1)) - 1.0


def _series_from_year_dict(d):
    """将 {year: value} 转为按年份升序的数值列表（缺省空列表）。"""
    if not d:
        return []
    return [v for _, v in sorted(d.items(), key=lambda kv: kv[0])]


def _months_between(date_str, as_of_str):
    """两个 YYYY-MM-DD 字符串之间的月数差（年差×12+月差，近似）。任一缺失返回 None。"""
    try:
        from datetime import date as _date

        def _parse(s):
            if not s:
                return None
            y, m, d = (int(x) for x in str(s).split("-")[:3])
            return _date(y, m, d)

        d1, d2 = _parse(date_str), _parse(as_of_str)
        if not d1 or not d2:
            return None
        return (d2.year - d1.year) * 12 + (d2.month - d1.month)
    except Exception:
        return None


def _median(xs):
    return statistics.median(xs) if xs else None


def _mean(xs):
    return statistics.mean(xs) if xs else None


def iqr_filter(values, excluded_out):
    """1.5×IQR 异常值剔除，返回 (保留列表, 剔除列表)。"""
    if len(values) < 4:
        return values, []
    s = sorted(values)
    q1, q3 = statistics.quantiles(s, n=4)[0], statistics.quantiles(s, n=4)[2]
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    keep, drop = [], []
    for i, v in enumerate(values):
        if lo <= v <= hi:
            keep.append(v)
        else:
            drop.append((excluded_out[i], v))
    return keep, drop


def _winsorize(values, lo_pct=0.01, hi_pct=0.99):
    """1%/99% 分位 winsorize 截尾（v2.5.0 B3）：用于可比增速/倍数极端值（如概念溢价可比）——
    在 IQR 之前先压缩尾部，防止单家极端值抬高截面中位数。样本 <5 时不处理（保持旧行为）。"""
    if not values or len(values) < 5:
        return list(values)
    s = sorted(values)
    n = len(s)
    lo_idx = max(1, int(n * lo_pct))
    hi_idx = min(n - 1, int(n * hi_pct) + 1)
    lo_v, hi_v = s[lo_idx - 1], s[hi_idx - 1]
    return [max(lo_v, min(hi_v, v)) for v in values]


TERMINAL_GUARD_EPS = 1e-4


def check_terminal_growth(wacc, tg, eps=TERMINAL_GUARD_EPS):
    """v3.21.0 A1：Gordon 终值的经济前提守卫——`g < WACC` 必须严格成立。

    分母 `wacc − tg` 在 `tg ≥ wacc` 时 ≤ 0：等于 0 直接除零崩溃，小于 0 得到**负终值**
    （越保守的假设反而抬高估值，方向性错误），而原实现的 warning 把它归因成「内在价值为负」。
    本函数只判定不改值——clamp 由调用方决定（引擎侧统一压到 `wacc − 1pp`）。

    返回 dict：violation / wacc / tg / gap_pp / suggested_tg / message。
    `eps=1e-4` 而非 0：`wacc−tg` 极小时终值仍会爆炸到天文规模（10bp 对应约 1,000× 终值），
    与 `tg ≥ wacc` 同属「无经济意义」区间。
    """
    gap = float(wacc) - float(tg)
    if gap < eps:
        return {
            "violation": True,
            "wacc": round(float(wacc), 6), "tg": round(float(tg), 6),
            "gap_pp": round(gap * 100.0, 4),
            "suggested_tg": round(max(-0.9, float(wacc) - 0.01), 6),
            "message": "永续增速不低于折现率（g ≥ WACC），Gordon 终值无经济意义",
        }
    return {"violation": False, "wacc": round(float(wacc), 6), "tg": round(float(tg), 6),
            "gap_pp": round(gap * 100.0, 4), "suggested_tg": None, "message": ""}


def two_stage_dcf(fcf0, growth_seq, terminal_growth, wacc, guard=None, mid_year=False):
    """两阶段 DCF：显式期 + 永续终值。返回 (pv_sum, tv_pv, detail)。

    v3.21.0 A1：`guard` 为 `check_terminal_growth()` 的结果时，若 violation 则终值置 0
    （fail-closed：不产出负终值或天文数字），detail 标记 `terminal_suppressed`。
    `guard=None`（缺省）逐位保持历史行为——旧调用方与旧输入零变化。

    v3.23.0 D1：`mid_year=True` 启用年中折现——显式期 t 年现金流按 `(1+wacc)^(t−0.5)` 折现，
    终值同按 `n−0.5`（终值隐含现金流亦在年中发生）。缺省 False 逐位保持年末口径。
    """
    fcf = fcf0
    pv_sum = 0.0
    detail = []
    for t, g in enumerate(growth_seq, start=1):
        fcf = fcf * (1.0 + g)
        expo = (t - 0.5) if mid_year else t
        df = (1.0 + wacc) ** expo
        pv = fcf / df
        pv_sum += pv
        detail.append({"t": t, "growth": round(g, 4), "fcf": round(fcf, 4), "pv": round(pv, 4)})
    suppressed = bool((guard or {}).get("violation"))
    if suppressed:
        tv, tv_pv = 0.0, 0.0
    else:
        tv = fcf * (1.0 + terminal_growth) / (wacc - terminal_growth)
        tv_expo = (len(growth_seq) - 0.5) if mid_year else len(growth_seq)
        tv_pv = tv / ((1.0 + wacc) ** tv_expo)
    out = {"pv_detail": detail, "terminal_value": round(tv, 4), "terminal_value_pv": round(tv_pv, 4)}
    if suppressed:
        out["terminal_suppressed"] = "永续增速 ≥ 折现率，Gordon 终值已置 0（fail-closed）"
    return pv_sum, tv_pv, out


def discount_fcf_series(fcf_series, terminal_growth, wacc, guard=None, mid_year=False):
    """对逐年现金流序列折现（v2.6.0 B1：FCFF 报表级口径用——capEx 分年输入时逐年现金流不同）。
    序列长度即显式期年数；终值基于末期现金流（Gordon）。返回 (pv_sum, tv_pv, detail)。
    v3.21.0 A1：`guard` 语义同 `two_stage_dcf`。
    v3.23.0 D1：`mid_year=True` 时显式期按 `(t−0.5)`、终值按 `(n−0.5)` 折现（缺省年末口径）。"""
    pv_sum = 0.0
    detail = []
    for t, fcf in enumerate(fcf_series, start=1):
        expo = (t - 0.5) if mid_year else t
        df = (1.0 + wacc) ** expo
        pv = fcf / df
        pv_sum += pv
        detail.append({"t": t, "fcf": round(fcf, 4), "pv": round(pv, 4)})
    suppressed = bool((guard or {}).get("violation"))
    if suppressed:
        tv, tv_pv = 0.0, 0.0
    else:
        tv = fcf_series[-1] * (1.0 + terminal_growth) / (wacc - terminal_growth)
        tv_expo = (len(fcf_series) - 0.5) if mid_year else len(fcf_series)
        tv_pv = tv / ((1.0 + wacc) ** tv_expo)
    out = {"pv_detail": detail, "terminal_value": round(tv, 4), "terminal_value_pv": round(tv_pv, 4)}
    if suppressed:
        out["terminal_suppressed"] = "永续增速 ≥ 折现率，Gordon 终值已置 0（fail-closed）"
    return pv_sum, tv_pv, out


def build_growth_seq(growth_forecast, terminal_growth, adj_pp=0.0, full_path=False):
    """5 年显式期增速序列（legacy 口径）：前 3 年取 growth_forecast（每档加 adj_pp），第 4/5 年线性收敛到终值增速。
    v2.1.0：允许负增速（保留 -0.9 硬下限防除零/荒谬值），原 max(0.0,…) 会静默抹平负增长。
    v3.21.0 B1：`full_path=True`（growth_path_mode="user_full"）时**不再只取前 3 年**——
    用户给 7 年即用满 7 年，仅当不足 5 年时按线性 fade 补齐；缺省 False 逐位保持截断行为。"""
    base = [max(-0.9, g + adj_pp / 100.0) for g in growth_forecast]
    if full_path:
        n = max(5, len(base))
        seq = list(base[:n])
        L = n - len(seq)
        if L > 0:
            g_anchor = seq[-1]
            for i in range(1, L + 1):
                seq.append(max(-0.9, g_anchor + (terminal_growth - g_anchor) * i / float(L)))
        return seq[:n]
    g4 = (base[2] + terminal_growth) / 2.0
    g5 = (g4 + terminal_growth) / 2.0
    return [base[0], base[1], base[2], g4, g5]


def build_growth_schedule(stage, growth_forecast, terminal_growth, cfg=None, adj_pp=0.0,
                          terminal_mode="asymptotic"):
    """四阶段显式期增速路径（v3.16.0 / Layer 1）——按生命周期选形态并定显式期长度 n。

    - 前 m 年（m=len(growth_forecast)）优先采用用户预测（每档 +adj_pp）→ 修复 legacy「只取前 3 年」缺陷，
      用户给 5 年即用满 5 年（n≥m 时不截断）；
    - 剩余 n-m 年按阶段形态从末档增速 fade 到终值增速 tg；
    - stage ∈ {startup, growth, mature, decline}；cfg 覆写 LIFECYCLE_DEFAULTS[stage]。
    v3.21.0 B5：`terminal_mode="forced"` 时改用等差插值，**末点精确等于 tg**——exp/mean_revert/s_curve
    三个形态都是渐近线，数学上永不到达 tg（实测 legacy 末段 1.88% vs tg 2.00%，tg=6% 时落差 −1.12pp），
    而「成熟期」的定义就是增速已稳定，末期不落在长期增长率上与该定义矛盾。
    返回 (seq, detail)；detail = {stage, form, n, n_user, g0, g_terminal, terminal_mode}。
    """
    cfg = cfg or {}
    base = [max(-0.9, float(g) + adj_pp / 100.0) for g in (growth_forecast or [])]
    if not base:
        base = [float(terminal_growth)]
    form = str(cfg.get("form", "linear"))
    n = max(int(cfg.get("n", 5)), len(base))
    tg = float(terminal_growth)
    m = len(base)
    seq = list(base[:n])
    L = n - m
    forced = (terminal_mode == "forced" and L > 0)
    if L > 0:
        g_anchor = seq[-1]
        if forced:
            # 等差收敛：把 [g_anchor, tg] 均分 L 份，第 L 步恰好落在 tg
            for i in range(1, L + 1):
                seq.append(max(-0.9, g_anchor + (tg - g_anchor) * i / float(L)))
            seq[-1] = tg
        else:
            for i in range(1, L + 1):
                if form == "exp":
                    hl = float(cfg.get("half_life", 3.0) or 3.0)
                    k = math.log(2.0) / hl
                    g = tg + (g_anchor - tg) * math.exp(-k * i)
                elif form == "mean_revert":
                    rho = float(cfg.get("rho", 0.30) or 0.30)
                    g = tg + (g_anchor - tg) * (rho ** i)
                elif form == "decline":
                    lam = float(cfg.get("lam", 0.30) or 0.30)
                    g_perm = float(cfg.get("g_perm", tg))
                    g = g_perm + (g_anchor - g_perm) * ((1.0 - lam) ** i)
                elif form == "s_curve":
                    tm = float(cfg.get("t_mid", max(1.0, (n - 1) / 2.0)))
                    k = math.log(3.0) / tm
                    g = tg + (g_anchor - tg) * (2.0 / (1.0 + math.exp(k * i)))
                else:  # linear
                    g = tg + (g_anchor - tg) * (1.0 - i / float(L))
                seq.append(max(-0.9, g))
    detail = {"stage": stage, "form": form, "n": n, "n_user": m,
              "g0": round(base[0], 4), "g_terminal": round(tg, 4)}
    if forced:                                     # v3.21.0 B5 留痕（缺省不挂 → 键集合不变）
        detail["terminal_mode"] = "forced"
        detail["terminal_applied"] = True
    return [round(x, 6) for x in seq], detail


# ============ v3.25.0：状态空间分解增速模型（增长率建模建议书 §3.1）============
# 动因：五种形态（exp/mean_revert/s_curve/decline/linear）的 rho=0.30 / half_life=3 /
# lam=0.30 全部无出处；且渐近线数学上永不到达 tg（tg=6% 时末段落差 −1.12pp）。
# 改为两层分解：
#   g_t  = mu_t + u_t                          增长率 = 趋势 + 冲击
#   mu_t = tg + (mu0 − tg)·E_t                 趋势层（归一化指数，精确收敛 tg）
#   u_t  = (g1 − mu0)·(1 − (t−1)/(n−1))^p      冲击层（幂次，t=n 恰为 0）
# 三层闭合由构造保证：
#   t=1 → u=0, E=1 → g_1 = g1（首年精确通过，不打折）
#   t=n → u=0, E=0 → g_n = tg（末端精确闭合，无需强制覆盖）
GROWTH_MODEL_DEFAULTS = {
    "p": 1.5,                  # 冲击形态：周期性 1.0 / 混合 1.5 / 结构性 2.0
    "cap_life_years": 10.0,    # CAP 中位 10–15 年（Rappaport 1986 / Mauboussin 1997）
    "mu0_div_max_pp": 5.0,     # |mu0 − g1| > 5pp 时 mu0 退化为 g1（防 V 型非单调）
    "shock_sigma": 2.0,        # |g1 − mu0| > 2σ_hist 时标 shock
    "floor": -0.30,
}


def growth_shape_kappa(cap_life_years=None):
    """趋势退化率 kappa —— 由 CAP 反算：`f = 1/CAP`，`kappa = 1 − f`。

    **与建议书 §3.1 的差异（本实现修正）**：建议书原方案用 `kappa = eps^(1/(n−1))` 反解，
    以保证 `mu_n` 残余 ≤ eps。代价是 kappa 变成 n 的派生量——**CAP 失去表达企业差异的能力**
    （10 年护城河与 2 年护城河得到同一个 kappa，n=7 时都是 0.607）。

    本条把"末端闭合"交给趋势层的**归一化因子** `E_t = (kappa^(t−1) − kappa^(n−1))/(1 − kappa^(n−1))`，
    构造上就保证 `E_1 = 1`、`E_n = 0`，于是 kappa 恢复为可标定的自由参数：
    缺省 0.90（CAP=10 年），强护城河 0.93（CAP≈14 年），无护城河 0.75（CAP=4 年）。
    """
    cap = float(GROWTH_MODEL_DEFAULTS["cap_life_years"] if cap_life_years is None
                else cap_life_years)
    if cap <= 1.0:
        return 0.0
    return max(0.0, min(0.99, 1.0 - 1.0 / cap))


def space_state_growth_schedule(g1, mu0, tg, n, p=None, kappa=None, cap_life_years=None,
                                sgr=None, gdp_cap=0.045, floor=None,
                                hist_sigma_pp=None, mu0_div_max_pp=None):
    """v3.25.0：状态空间分解增速路径（替代五种硬编码形态）。缺省不激活。

    参数
    ----
    g1 : 首年增速（实际数导出，L1–L7 分级由调用侧负责）
    mu0 : 中期锚（行业 g_lt × 份额因子；无数据时 = tg）
    tg : 永续增速
    n : 显式期年数
    p : 冲击形态。周期性冲击（国补退坡/去库存）1.0 / 混合 1.5 / 结构性（份额流失）2.0
    kappa : 趋势退化率，缺省由 CAP 反算（见 growth_shape_kappa）
    sgr : 可持续增长率 ROIC×(1−payout)，作为增速上限（防"挣不到的增长"）
    hist_sigma_pp : 历史增速标准差（pp），用于 shock 标记

    返回 (seq, detail)。seq 为 n 个增速（小数）；detail 含逐行 mu/u/clamped_by。
    """
    n = int(max(2, n))
    g1, tg, mu0 = float(g1), float(tg), float(mu0)
    p = float(GROWTH_MODEL_DEFAULTS["p"] if p is None else p)
    kappa = growth_shape_kappa(cap_life_years) if kappa is None else float(kappa)
    floor = float(GROWTH_MODEL_DEFAULTS["floor"] if floor is None else floor)
    div_max = float(GROWTH_MODEL_DEFAULTS["mu0_div_max_pp"]
                    if mu0_div_max_pp is None else mu0_div_max_pp)

    # 上限：SGR 与 GDP 上限取小（SGR 缺失时只用 GDP）
    g_cap, cap_src = float(gdp_cap), "gdp_cap"
    if sgr is not None and float(sgr) < g_cap:
        g_cap, cap_src = float(sgr), "sgr"

    # 约束⑤：mu0 与 g1 偏离过大 → mu0 退化为 g1。
    # 实测教训（建议书 §7 边界 3）：美的 mu0 取到 SGR 4.88% 时路径变成
    # 2.60 → 2.01 → 1.82 → 1.84 → 1.95 —— 先跌后升，经济上不成立。原因是 mu0 高时
    # u1 更负（2.6 − 4.88 = −2.28pp），冲击把前几年压到趋势线以下，而趋势线又在往 tg 退，
    # 两个方向打架产生 V 型。故偏离超 5pp 时放弃"追求中间目标"，退化为纯冲击衰减。
    mu0_raw, mu0_deg = mu0, False
    if abs(mu0 - g1) * 100.0 > div_max:
        mu0, mu0_deg = g1, True
    mu0_pre_clamp = mu0
    mu0 = max(tg, min(mu0, max(g_cap, tg)))     # 中期锚夹在 [tg, 结构上限]
    # 退化若被夹逼抵消（典型：深度负增长标的 μ0 退化为 g1 后被 [tg, cap] 下限拉回 tg），
    # 实际生效值与输入值相同 → 不得标 degraded（否则报告会声称发生过一次未发生的调整）。
    mu0_clamped_by = None
    if abs(mu0 - mu0_pre_clamp) > 1e-12:
        mu0_clamped_by = "tg_floor" if mu0_pre_clamp < tg else "cap_ceiling"
    if mu0_deg and abs(mu0 - mu0_raw) < 1e-12:
        mu0_deg = False

    # 趋势层归一化因子：构造上保证 E_1 = 1、E_n = 0（替代 kappa 反解的末端闭合）
    e_last = kappa ** (n - 1)
    denom = (1.0 - e_last) if abs(1.0 - e_last) > 1e-12 else None

    rows = []
    for t in range(1, n + 1):
        e_t = kappa ** (t - 1)
        if denom is None:                        # kappa≈1：趋势层退化为常数 mu0
            mu = mu0
        else:
            mu = tg + (mu0 - tg) * (e_t - e_last) / denom
        u = (g1 - mu0) * ((1.0 - (t - 1) / float(n - 1)) ** p)
        g = mu + u
        clamped_by = None
        if t == 1:
            g, src = g1, "first_year"            # 首年精确通过
        elif t == n:
            g, src = tg, "terminal"              # 末端精确闭合
        else:
            src = "mu+shock"
            if g > g_cap:
                g, clamped_by = g_cap, cap_src
            elif g < floor:
                g, clamped_by = floor, "floor"
        rows.append({"t": t, "g": round(g, 6), "mu": round(mu, 6), "u": round(u, 6),
                     "src": src, "clamped_by": clamped_by})
    seq = [r["g"] for r in rows]
    detail = {
        "model": "space_state",
        "n": n, "p": round(p, 4), "kappa": round(kappa, 4),
        "cap_life_years": (round(1.0 / (1.0 - kappa), 2) if kappa < 1.0 else None),
        "g1": round(g1, 6), "mu0": round(mu0, 6), "mu0_input": round(mu0_raw, 6),
        "mu0_degraded": mu0_deg, "tg": round(tg, 6),
        "mu0_clamped_by": mu0_clamped_by,
        "mu0_effective": round(mu0, 6),
        "u1_pp": round((g1 - mu0) * 100.0, 4),
        "bounds": {"gdp_cap": round(float(gdp_cap), 4),
                   "sgr": (round(float(sgr), 4) if sgr is not None else None),
                   "effective_cap": round(g_cap, 4), "cap_source": cap_src,
                   "floor": round(floor, 4)},
        "closure": {"t1_equals_g1": abs(seq[0] - g1) < 1e-9,
                    "tn_equals_tg": abs(seq[-1] - tg) < 1e-9},
        "rows": rows,
        "note": "g_t = mu_t + u_t；mu 为归一化指数趋势（构造精确收敛 tg），u 为幂次冲击（t=n 恰为 0）",
    }
    if hist_sigma_pp is not None:
        detail["shock_flag"] = bool(
            abs(g1 - mu0) * 100.0 > GROWTH_MODEL_DEFAULTS["shock_sigma"] * float(hist_sigma_pp))
    return seq, detail


# ============ v3.29.0：六阶段增长函数（plc6）——统一「缺口归一化」族 ============
# 【为什么重写】旧 `build_growth_schedule` 的五个形态（exp / mean_revert / s_curve / decline /
# linear）存在三处结构性缺陷：
#   ① **名为 S 曲线，实为单调衰减**：`s_curve` 分支写的是 `g = tg + (g_anchor−tg)·2/(1+e^{k·i})`，
#      i=1 时已 <1、i→∞ 趋于 0，从第一年就往下掉——它是「反向 logistic 衰减」，不是 S 曲线；
#      `t_mid` 只改陡度（k=ln3/t_mid），并不是 S 的拐点位置，命名与语义不符。
#   ② **渐近线永不到达**：exp / mean_revert / s_curve 数学上极限才等于 tg，n 年末仍有残差；
#      旧补丁 `terminal_mode="forced"` 用**等差插值整体替换尾段**——形态被静默作废（形态=声明，
#      结果=线性），属「字段定义但未被消费」。
#   ③ **参数无出处**：rho=0.30 / half_life=3 / lam=0.30 / t_mid 全部是经验值，无文献锚。
#
# 【新框架】把六个阶段统一成**一个公式、六种 E(t)**：
#       g_t = tg + (g1 − tg) · E(t),      E(1) = 1,  E(n) = 0
#   E(t) 只回答一个问题：**超额增速缺口以什么节奏闭合**。三条性质由构造保证：
#       t=1 → g=g1（首年精确通过，不打折）；t=n → g=tg（末端精确闭合，不需要 forced 补丁）；
#       中间 → 由 E 的形状决定，且 E 归一化后**不需要任何渐近假设**。
#
# 【E 的四个形状与出处】
#   logistic_cap  **真 S**：慢（护城河有效）→ 陡（壁垒集中失效）→ 平（贴近 tg）。
#                 参数 = cap（拐点年，即壁垒失效的中位时点）+ steep（陡度 a）。
#                 依据：达莫达兰把「超额增长能持续多久」归于**进入壁垒**（Valuation ch.12：
#                 "high growth comes from high project returns, which comes from barriers to entry"），
#                 故拐点 = CAP（competitive advantage period，Rappaport 1986 / Mauboussin 1997）。
#   geometric     缺口按固定比例闭合（前重后轻）。kappa 由 CAP 反算（1 − 1/CAP），与
#                 `growth_shape_kappa()` 同一口径——同一 CAP 输入在两处得到同一 kappa。
#   mean_revert   部分调整模型：E = ρ^(t−1)，ρ 为**留存率**（不是回归速度）。
#                 ρ=0.62 ← Fama & French (2000, JB) 年均回归 38%（1−0.38=0.62），
#                 隐含半衰期 ln0.5/ln0.62 = 1.45 年；英国样本 Allen & Salim (2002) 约 25%/年（ρ=0.75）。
#                 ★口径注意：FF 的 38% 测的是**盈利能力（ROA）**回归，不是营收增速。本表只在
#                 mature_stable / decline 两档用它——这两档增速缺口本身很小（g1 已接近 tg），
#                 用盈利回归速度近似增速回归速度，误差被缺口幅度压住；高增长档一律用
#                 logistic_cap（拐点+陡度），**不把 38% 外推到 20%→2% 的大缺口上**。
#   linear        缺口按等额百分点闭合（审计最友好；达莫达兰把稳定增长期的不确定性归到
#                 再投资率而非增速本身，等额收敛是"不主张形状"的中性选择）。
#
# 【六档映射的 n】10 / 10 / 8 / 7 / 6 / 4。与 v3.27.0 的四阶段表（10/8/6/4）相容：
#   startup 10 = 原 startup；high_growth 8 = 原 growth；mature_stable 6 = 原 mature；
#   decline 4 = 原 decline。新增两档 young_growth / mature_growth 是**达莫达兰把原
#   startup 与 growth 各切一刀**的产物：young_growth 承接「有收入仍亏损」，n 与 startup 同为 10；
#   mature_growth 落在 8 与 6 之间取 7——**此为插值值，无独立文献依据**，故在 detail 里标注
#   `n_basis="interpolated"`，报告须如实披露。
# 【cap 的取值性质】cap 6/5/4/3 与 steep 6/5.5/5/4 是**引擎标定值（非文献值）**：文献只给
#   "CAP 中位 8–10 年"「壁垒决定持续性」这一定性结论，未给分阶段数值。标定逻辑是
#   「越往后，剩余超额增长窗口越短、失效越快」，且 cap 随阶段单调递减（下方断言守护）。
#   用户显式给 `growth_model.cap_life_years` 时覆盖 cap——**这是唯一有外部输入的口子**。
PLC6_SHAPE_PARAMS = {
    "startup":       {"n": 10, "shape": "logistic_cap", "cap": 6.0, "steep": 6.0,
                      "n_basis": "table"},
    "young_growth":  {"n": 10, "shape": "logistic_cap", "cap": 5.0, "steep": 5.5,
                      "n_basis": "table"},
    "high_growth":   {"n": 8,  "shape": "logistic_cap", "cap": 4.0, "steep": 5.0,
                      "n_basis": "table"},
    "mature_growth": {"n": 7,  "shape": "logistic_cap", "cap": 3.0, "steep": 4.0,
                      "n_basis": "interpolated"},
    "mature_stable": {"n": 6,  "shape": "mean_revert",  "rho": 0.62,
                      "n_basis": "table"},
    "decline":       {"n": 4,  "shape": "linear",       "n_basis": "table"},
}
PLC6_STAGE_ORDER = ("startup", "young_growth", "high_growth",
                    "mature_growth", "mature_stable", "decline")
# 单调性硬约束：n 随阶段不增（允许相等），防止再出现「成熟期比成长期还长」的倒挂。
_p6_n = [PLC6_SHAPE_PARAMS[s]["n"] for s in PLC6_STAGE_ORDER]
assert all(_p6_n[i] >= _p6_n[i + 1] for i in range(len(_p6_n) - 1)), \
    f"六阶段显式期须随阶段单调不增：{dict(zip(PLC6_STAGE_ORDER, _p6_n))}"
# 第二条单调性：护城河拐点 cap 亦须随阶段不增（窗口越往后越短）。
_p6_c = [PLC6_SHAPE_PARAMS[s].get("cap") or 0.0 for s in PLC6_STAGE_ORDER]
assert all(_p6_c[i] >= _p6_c[i + 1] for i in range(len(_p6_c) - 1)), \
    f"六阶段 CAP 拐点须随阶段单调不增：{dict(zip(PLC6_STAGE_ORDER, _p6_c))}"
PLC6_SHAPE_LABELS = {
    "logistic_cap": "S 曲线（CAP 拐点 + 陡降）",
    "geometric": "几何衰减（CAP 反算 κ）",
    "mean_revert": "部分调整（ρ=0.62 留存，FF 2000）",
    "linear": "线性收敛",
}
PLC6_SHAPE_EVIDENCE = {
    "logistic_cap": "达莫达兰：高增长持续性由进入壁垒决定 → 拐点=CAP；S 形（中段陡降）对应壁垒集中失效，"
                    "而非逐年线性流失（Valuation ch.12；Rappaport 1986 / Mauboussin 1997）",
    "geometric": "O'Brien (2003) 衰减因子 d；κ=1−1/CAP（Rappaport 1986 / Mauboussin 1997）",
    "mean_revert": "Fama & French (2000)：年均均值回归 38% → 留存 ρ=0.62（半衰期 1.45 年）；"
                   "仅用于小缺口档，不外推到大缺口",
    "linear": "不主张形状的中性选择；等额百分点收敛，审计可逐格复算",
}


def plc_shape_e(shape, n, cap=None, steep=8.0, rho=0.62, kappa=None):
    """返回长度 n 的缺口闭合因子 E（E[0]=1、E[n-1]=0），下标 0 对应 t=1。"""
    n = int(max(2, n))
    if shape == "linear":
        return [1.0 - i / float(n - 1) for i in range(n)]
    if shape == "mean_revert":
        r = float(rho)
        raw = [r ** i for i in range(n)]
        end = raw[-1]
        den = 1.0 - end
        return [1.0] * n if abs(den) < 1e-12 else [(x - end) / den for x in raw]
    if shape == "geometric":
        k = growth_shape_kappa(cap) if kappa is None else float(kappa)
        if k <= 0.0 or k >= 1.0:                       # CAP≤1 或极端值 → 退化为线性
            return [1.0 - i / float(n - 1) for i in range(n)]
        raw = [k ** i for i in range(n)]
        end = raw[-1]
        den = 1.0 - end
        return [(x - end) / den for x in raw]
    if shape == "logistic_cap":
        # 平滑 S：拐点在 x0 = cap/(n−1)，a 控陡度。与「硬平台 + 陡降」相比没有折点，
        # 首年不精确等于 g1 的偏差由下方 out[0] 强制归位（尾部用同族时则不需要）。
        capf = float(cap if cap is not None else (n - 1) / 2.0)
        x0 = min(0.95, max(0.05, capf / float(n - 1)))
        a = float(steep)
        _s = lambda z: 1.0 / (1.0 + math.exp(-z))
        lo = _s(a * (x0 - 1.0))
        den = _s(a * x0) - lo
        out = [(_s(a * (x0 - i / float(n - 1))) - lo) / den for i in range(n)]
        out[0], out[-1] = 1.0, 0.0
        return out
    raise ValueError(f"未知增长形态：{shape}")


def plc_growth_path(stage, user_path, g1, tg, n=None, cap=None, shape=None, steep=None,
                    rho=None, kappa=None):
    """v3.29.0：六阶段增长函数（plc6）。g_t = tg + (g1 − tg)·E(t)。

    user_path 非空时前 m 年沿用用户给定值（不再二次塑形），其余年份按 E 从**末档值**收敛到 tg，
    与 `build_growth_schedule` 的契约一致（n < m 时截断到 n）。
    """
    cfg = dict(PLC6_SHAPE_PARAMS.get(stage) or PLC6_SHAPE_PARAMS["mature_growth"])
    if shape:
        cfg["shape"] = shape
    if n:
        cfg["n"] = int(n)
    if cap is not None:
        cfg["cap"] = float(cap)
    if steep is not None:
        cfg["steep"] = float(steep)
    if rho is not None:
        cfg["rho"] = float(rho)
    n = int(max(2, cfg.pop("n")))
    form = cfg["shape"]
    # 拐点超出显式期 → S 曲线退化（x0 会夹逼到 0.95，实际形状≈末尾急跌）。与其静默夹逼，
    # 不如显式降级为线性并留痕：cape 8 年 + n=7 时读者会以为看到 S，实际看不到。
    _form_note = None
    if form == "logistic_cap" and cfg.get("cap") is not None \
            and float(cfg["cap"]) >= n - 1:
        _form_note = (f"CAP（{float(cfg['cap']):.1f} 年）≥ 显式期−1（{n - 1} 年）："
                      "护城河长于预测窗口，S 曲线无可观测的陡降段，已降级为线性收敛")
        form = "linear"

    base = [max(-0.9, float(x)) for x in (user_path or [])]
    m = min(len(base), n)
    seq = list(base[:m])
    L = n - m
    # 尾段的护城河拐点须扣除「已被用户路径占用的年数」——否则 m 年用户路径 + cap=4 会
    # 变成「拐点后移 4 年」，等于凭用户路径给公司免费续了护城河。
    cap_tail = cfg.get("cap")
    if cap_tail is not None:
        cap_tail = max(0.5, float(cap_tail) - m)
    if L > 0:
        anchor = seq[-1] if seq else float(g1)
        # 尾段用「以末档值为 g1、长度 L」的同一族：保证 E(0)=1 接续、E(L)=0 落在 tg
        e_tail = plc_shape_e(form, L + 1, cap=cap_tail, steep=cfg.get("steep", 5.0),
                             rho=cfg.get("rho", 0.62), kappa=kappa)
        for i in range(1, L + 1):
            g = float(tg) + (anchor - float(tg)) * e_tail[i]
            seq.append(max(-0.9, g))
        seq[-1] = float(tg)
    seq = seq[:n]
    _first = float(base[0]) if base else float(g1)
    if seq:
        seq[0] = _first

    det = {
        "model": "plc6", "stage": stage, "form": form,
        "form_label": PLC6_SHAPE_LABELS.get(form, form),
        "evidence": PLC6_SHAPE_EVIDENCE.get(form, ""),
        "n": n, "n_user": len(base), "n_basis": cfg.get("n_basis", "table"),
        "g1": round(float(g1), 6), "g_terminal": round(float(tg), 6),
        "params": {k: cfg.get(k) for k in ("cap", "steep", "rho") if cfg.get(k) is not None},
        "closure": {"t1_equals_g1": bool(seq) and abs(seq[0] - _first) < 1e-6,
                    "tn_equals_tg": bool(seq) and abs(seq[-1] - float(tg)) < 1e-9},
        "monotone_nonincreasing": all(seq[i] >= seq[i + 1] - 1e-9 for i in range(len(seq) - 1)),
    }
    if form == "mean_revert":
        det["implied_half_life"] = round(math.log(0.5) / math.log(float(cfg.get("rho", 0.62))), 2)
    if form == "geometric":
        det["kappa"] = round(growth_shape_kappa(cfg.get("cap")) if kappa is None else float(kappa), 4)
    if form == "logistic_cap":
        det["cap_years"] = round(float(cfg.get("cap") or (n - 1) / 2.0), 2)
    if _form_note:
        det["form_downgraded"] = _form_note
        det["form_requested"] = cfg.get("shape")
    return [round(x, 6) for x in seq], det


# v3.21.0 B2：历史增速形态判定（对应 CVA R8「不得机械外推」要求）
# CVA 对历史增速的处理是「先判形态、再定规则」，而原实现只有「无 gf 时复制首值」一条路
# （格力 [−2%]×3、可比中位 11.15%×3），形态信息被完全丢弃。
_HISTORY_CASE_RULES = "含正含负→正负切换；全负→按变化方向分恶化/收敛/震荡；全正→按趋势与幅度分六型"


def growth_history_shape(history, min_periods=3):
    """历史增速形态判定（v3.21.0 B2，纯函数、不改数值）。

    输入 `history` 为按年份升序的增速序列（小数，如 [0.0793, -0.0726, -0.0989]）。
    输出 history_case + metrics（H1/H2/H3、mean、median、range_pp、sigma_pp、sample_std）。
    判定顺序：数据不足 → 含正含负（正负切换）→ 全负（恶化/收敛/震荡）→ 全正（低位/稳定/上行/回落/震荡）。

    设计取舍：只判形态、不代拟数值。真正改数必须有业务驱动证据（订单/产能/政策），
    引擎不承担「从历史形态反推未来路径」的职责——那是编造。
    """
    vals = [float(x) for x in (history or []) if x is not None]
    if len(vals) < min_periods:
        return {"enabled": True, "history_case": "数据不足", "n": len(vals),
                "metrics": None, "base_rule": "样本不足 3 期，不判形态；建议补充历史营收序列",
                "note": "B2 形态判定：仅 advisory，不改数值"}
    tail = vals[-min_periods:]
    mean = statistics.mean(tail)
    sigma = statistics.stdev(tail)
    rng = max(tail) - min(tail)
    pos = [v for v in tail if v > 0]
    neg = [v for v in tail if v < 0]
    if pos and neg:
        case = "正负切换且无稳定方向"
        rule = "不得取平均、不得机械外推；优先业务驱动（订单/产能/政策），缺证据时保留用户假设并强制披露"
    elif not pos:
        if tail[-1] < tail[-2] < tail[-3]:
            case, rule = "持续负增长（降幅仍在扩大）", "按衰退收敛处理，终值增速不应高于 0"
        elif tail[-1] > tail[-2]:
            case, rule = "负增长收敛", "降幅收窄可按均值回归外推，但首年不应假设转正"
        else:
            case, rule = "负增长震荡", "方向不稳定，不得取平均外推"
    else:
        rising = tail[-1] > tail[-2] > tail[-3]
        falling = tail[-1] < tail[-2] < tail[-3]
        if max(tail) < 0.03:
            case, rule = "低位徘徊（|g|<3%）", "与长期增长率同量级，可直接向 tg 收敛"
        elif rising:
            # CVA 口径：D1、D2 均 > 0 即「持续加速」——与跨度无关，跨度只影响幅度描述。
            # 规则一致：禁止机械外推加速度，须以最新可得期间证据定首年。
            case = ("持续加速（禁止外推斜率）" if tail[0] >= 0.05
                    else "温和上行（禁止外推斜率）")
            rule = "规则明确禁止外推加速度：须以最新可得期间（半年报/季报）证据定首年，不得延续斜率"
        elif falling:
            case = "高增长回落" if tail[0] >= 0.15 else "增速温和下行"
            rule = "按 fade 收敛到 tg，回落幅度以可比/行业为参照"
        elif rng > 0.10:
            case, rule = "高位震荡（跨度>10pp）", "取最新期间为锚，参考中位数而非均值"
        else:
            case, rule = "稳定增长", "可按均值外推并向 tg 收敛"
    return {
        "enabled": True, "n": len(tail), "history_case": case,
        "metrics": {"H1": round(tail[0], 4), "H2": round(tail[1], 4), "H3": round(tail[2], 4),
                    "mean": round(mean, 4), "median": round(statistics.median(tail), 4),
                    "range_pp": round(rng * 100.0, 2), "sigma_pp": round(sigma * 100.0, 2)},
        "base_rule": rule,
        "alpha_rule": _HISTORY_CASE_RULES,
        "note": "B2 形态判定：仅 advisory，不改数值（改数须业务驱动证据，不由引擎代拟）",
    }


def value_driver_fcf_series(ebit_base, tax, growth_seq, roic, nwc_to_rev=None, rev_base=None):
    """P0 价值驱动式现金流序列（v3.16.0 / Layer 1）：
    NOPAT_t = EBIT_t×(1−t)；RR_t = clamp(g_t/ROIC, 0, 1)；FCFF_t = NOPAT_t×(1−RR_t)。
    增长由再投资「挣得」（g=ROIC×RR 守恒）。返回 (series, detail)；roic 缺失 → (None, None) 不激活。"""
    if not roic or roic <= 0:
        return None, None
    series, rows = [], []
    ebit_t = float(ebit_base)
    for t, g in enumerate(growth_seq, start=1):
        ebit_t = ebit_t * (1.0 + g)
        nopat = ebit_t * (1.0 - tax)
        rr = max(0.0, min(1.0, g / roic))
        fcff = nopat * (1.0 - rr)
        series.append(fcff)
        rows.append({"t": t, "growth": round(g, 4), "ebit": round(ebit_t, 4),
                     "nopat": round(nopat, 4), "reinvestment_rate": round(rr, 4),
                     "reinvestment": round(nopat * rr, 4), "fcff": round(fcff, 4)})
    return series, {"roic": round(roic, 4), "tax_rate": round(tax, 4), "rows": rows,
                    "formula": "FCFF_t = NOPAT_t × (1 − g_t/ROIC)，增长由再投资挣得（g = ROIC × RR）"}


# ============ v3.23.0：现金流模型与参数取值的纯函数层（D2/D3/D4/D5/D6/D7）============

#: CVA CCPFC2026 规模溢价表（贝塔调整后口径，直接加在 CAPM 之上；市值单位：亿元）
SIZE_PREMIUM_CVA_2026 = {
    "edition": "2026",
    "source": "CCPFC2026《中国企业资本成本估计参数表》附录（隐含 ERP 8.04%）",
    "deciles": [
        ("1", 357.18, 17246.01, 0.0033), ("2", 188.36, 354.16, 0.0081),
        ("3", 122.80, 188.31, 0.0060), ("4", 88.54, 122.58, 0.0129),
        ("5", 68.19, 88.45, 0.0105), ("6", 53.35, 68.18, 0.0264),
        ("7", 42.54, 53.31, 0.0460), ("8", 32.89, 42.52, 0.0711),
        ("9", 24.42, 32.87, 0.0858), ("10", 2.06, 24.41, 0.1114),
    ],
    "split_10": [("10w", 22.05, 24.41, 0.0803), ("10x", 18.88, 22.04, 0.0929),
                 ("10y", 14.94, 18.76, 0.0901), ("10z", 2.06, 14.89, 0.1829)],
}


def size_premium_cva(market_cap_yi, edition="2026"):
    """D2：按市值查 CVA 规模溢价（贝塔调整后口径，直接加在 CAPM 之上）。

    规则与 CVA `wacc_params.size_premium` 一致：市值 ≤24.41 亿用 10w/10x/10y/10z 细分
    （按上界升序匹配，间隙向上取），否则按十分位下界降序匹配。
    返回 dict；市值不可用（None/≤0）→ {"applied": False}。
    """
    try:
        cap = float(market_cap_yi)
    except (TypeError, ValueError):
        return {"applied": False, "reason": "market_cap 不可用"}
    if cap <= 0:
        return {"applied": False, "reason": "market_cap ≤ 0"}
    table = SIZE_PREMIUM_CVA_2026
    if cap <= 24.41:
        for grp, lo, hi, prem in sorted(table["split_10"], key=lambda r: r[2]):
            if cap <= hi:
                return {"applied": True, "edition": table["edition"], "group": grp,
                        "premium": prem, "market_cap": round(cap, 2),
                        "source": table["source"]}
    for grp, lo, hi, prem in table["deciles"]:
        if cap >= lo:
            return {"applied": True, "edition": table["edition"], "group": grp,
                    "premium": prem, "market_cap": round(cap, 2),
                    "source": table["source"]}
    last = table["split_10"][-1]
    return {"applied": True, "edition": table["edition"], "group": last[0],
            "premium": last[3], "market_cap": round(cap, 2), "source": table["source"]}


def growth_base_from_history(hist, min_periods=3):
    """D4：按历史形态给出「基准增速建议值」（CVA 取值矩阵的引擎侧子集）。

    与 `growth_history_shape` 的分工：形态判定只判不改（B2），本函数把形态映射成
    **建议基准值**，供「用户未提供 growth_forecast」时使用；用户显式路径永不覆盖。
    不可自动取平均的形态（正负切换/负增长震荡/数据不足）→ applied=False + 需业务证据。
    """
    if not hist or not hist.get("enabled") or not hist.get("metrics"):
        return {"applied": False, "case": (hist or {}).get("history_case"), "needs_evidence": True,
                "reason": "无有效历史增速序列（需 revenue_by_year ≥4 年）"}
    m = hist["metrics"]
    case = hist.get("history_case", "")
    h1, h2, h3 = m["H1"], m["H2"], m["H3"]
    if case == "稳定增长" or case.startswith("低位徘徊"):
        val, rule = m["mean"], "稳定形态 → 三年算术平均"
    elif case.startswith("持续加速"):
        val, rule = 0.2 * h1 + 0.3 * h2 + 0.5 * h3, "持续加速 → 0.2/0.3/0.5 近期加权（禁止外推斜率）"
    elif case.startswith("温和上行"):
        val, rule = h3, "温和上行 → 首年取最近一年（须业务证据支撑）"
    elif case.startswith("高增长回落") or case.startswith("增速温和下行"):
        val, rule = h3, "增速下行 → 首年取最近一年（最近一年更具代表性）"
    elif case.startswith("高位震荡"):
        val, rule = m["median"], "高位震荡 → 取中位数（均值受极值影响）"
    elif case.startswith("负增长收敛"):
        val, rule = h3, "负增长收敛 → 首年取最近一年，不得假设转正"
    elif case.startswith("持续负增长"):
        val, rule = h3, "持续负增长 → 取最近一年（最保守），终值不应高于 0"
    elif case.startswith("正负切换") or case.startswith("负增长震荡"):
        return {"applied": False, "case": case, "needs_evidence": True,
                "reason": "形态为「%s」，平均值无经济意义；须补业务驱动证据（订单/产能/政策）" % case}
    else:
        return {"applied": False, "case": case, "needs_evidence": True,
                "reason": "未识别的历史形态，保持用户/兜底取值"}
    return {"applied": True, "case": case, "base_growth": round(val, 6), "rule": rule,
            "metrics": m, "needs_evidence": False}


def margin_sigma_step(history, lo_pp=1.0, hi_pp=3.0):
    """D5：利润率情景步长 = 历史 σ，clamp[1,3]pp（CVA 口径，与收入增速 2–5pp 分开）。

    `history` 为按年份升序的净利率（或 EBIT 利润率）序列，小数。样本 <3 → not applied。
    """
    vals = [float(x) for x in (history or []) if x is not None]
    if len(vals) < 3:
        return {"applied": False, "reason": "利润率历史样本 <3 期"}
    sd_pp = statistics.stdev(vals) * 100.0
    step = max(lo_pp, min(hi_pp, sd_pp))
    return {"applied": True, "sigma_pp": round(sd_pp, 2), "step_pp": round(step, 2),
            "clamp_pp": [lo_pp, hi_pp]}


def capex_magnitude_check(capex, d_a, band=(0.5, 10.0)):
    """D3：Capex/D&A 量级勾稽——拦截「capex 异常偏低/偏高」的数据级错误。

    依据：白电 Capex/D&A 正常带约 1.5–3.5；格力案例 capex 误填 7.30 亿（应 125.31 亿）时
    比值 0.15，8% 营收阈值完全拦不住，而开 fcff_mode 后估值跳升 46.6%。
    """
    if capex is None or d_a in (None, 0):
        return {"applied": False, "reason": "capex 或 d_a 缺失/为零，无法勾稽"}
    ratio = float(capex) / float(d_a)
    lo, hi = band
    if ratio < lo:
        level, msg = "warning", (f"Capex/D&A = {ratio:.2f}，低于合理带 {lo:g}–{hi:g}——"
                                f"疑似资本开支漏计（或 D&A 含大额摊销），开 fcff_mode 将系统性高估 FCFF")
    elif ratio > hi:
        level, msg = "warning", (f"Capex/D&A = {ratio:.2f}，高于合理带 {lo:g}–{hi:g}——"
                                f"疑似扩产期或资本开支含非维持性项目，请核实口径")
    else:
        level, msg = "ok", f"Capex/D&A = {ratio:.2f}，处于合理带 {lo:g}–{hi:g}"
    return {"applied": True, "ratio": round(ratio, 4), "band": [lo, hi],
            "level": level, "message": msg}


def statement_fcff_series(base_revenue, growth_seq, ebit_margin=None, capex_to_revenue=None,
                          da_to_revenue=None, nwc_to_revenue=None, nwc_turnover=None,
                          tax_rate=0.15, base_da=None, cost_ratio=None, expense_ratio=None,
                          delta_wc_first=None):
    """D6/D7：报表驱动式 FCFF 逐年序列（与 CVA DCF 的三表口径同构）。

    构造链：Revenue_t = Revenue_{t−1}×(1+g_t) → EBIT_t = Revenue_t×EBIT率
    → NOPAT_t = EBIT_t×(1−t) → FCFF_t = NOPAT_t + D&A_t − Capex_t − ΔWC_t。

    - EBIT 率：优先 `ebit_margin`；也可由 `1 − cost_ratio − expense_ratio` 合成（对应 CVA 的
      营业成本率 + 营业费用率两组驱动）。
    - D&A：`da_to_revenue` 优先；否则按 `base_da × Revenue_t/Revenue_0` 随收入外推。
    - Capex：`capex_to_revenue`（标量或逐年序列）。
    - ΔWC：`nwc_turnover`（收入/营运资本 周转次数）优先 → NWC_t=Rev_t/Turnover，
      ΔWC_t=NWC_t−NWC_{t−1}；否则 `nwc_to_revenue` → ΔWC_t=ΔRev_t×比率；均缺省 0。
    - `delta_wc_first`：**仅第 1 年**的一次性营运资本变动（如美的 −67.24 亿的释放）。
      与 `nwc_to_revenue` 的区别：后者随收入逐年重复，前者只发生一次——把一次性项
      按比例年化是「单年 FCFF 外推」口径的典型失真来源。

    标量入参自动广播到全期；序列短于显式期时以末值延续。返回 (series, detail)。
    """
    if not base_revenue or base_revenue <= 0:
        return None, None

    def _at(x, i):
        if x is None:
            return None
        if isinstance(x, (list, tuple)):
            if not x:
                return None
            return float(x[i]) if i < len(x) else float(x[-1])
        return float(x)

    rev = float(base_revenue)
    rev_prev = rev
    nwc_prev = (rev / float(nwc_turnover)) if nwc_turnover else None
    # 基期 FCFF（t=0，无 ΔWC）：用于 fcf0 口径统一与首年对照
    _m0 = _at(ebit_margin, 0)
    if _m0 is None and cost_ratio is not None:
        _m0 = 1.0 - float(_at(cost_ratio, 0) or 0.0) - float(_at(expense_ratio, 0) or 0.0)
    if _m0 is None:
        return None, None
    _da0 = _at(da_to_revenue, 0)
    _da0_v = rev * _da0 if _da0 is not None else (float(base_da) if base_da else 0.0)
    _capex0_v = rev * float(_at(capex_to_revenue, 0) or 0.0)
    base_fcff = rev * _m0 * (1.0 - float(tax_rate)) + _da0_v - _capex0_v
    series, rows = [], []
    for i, g in enumerate(growth_seq):
        rev = rev * (1.0 + g)
        m = _at(ebit_margin, i)
        if m is None and cost_ratio is not None:
            m = 1.0 - float(_at(cost_ratio, i) or 0.0) - float(_at(expense_ratio, i) or 0.0)
        if m is None:
            return None, None
        ebit = rev * m
        nopat = ebit * (1.0 - float(tax_rate))
        da_r = _at(da_to_revenue, i)
        d_a = rev * da_r if da_r is not None else (float(base_da) * rev / float(base_revenue) if base_da else 0.0)
        capex = rev * float(_at(capex_to_revenue, i) or 0.0)
        if nwc_turnover:
            nwc_t = rev / float(nwc_turnover)
            delta_wc = nwc_t - (nwc_prev if nwc_prev is not None else nwc_t)
            nwc_prev = nwc_t
        else:
            delta_wc = (rev - rev_prev) * float(nwc_to_revenue or 0.0)
        if delta_wc_first is not None and i == 0:
            delta_wc += float(delta_wc_first)
        fcff = nopat + d_a - capex - delta_wc
        series.append(fcff)
        rows.append({"t": i + 1, "growth": round(g, 4), "revenue": round(rev, 4),
                     "ebit_margin": round(m, 4), "ebit": round(ebit, 4), "nopat": round(nopat, 4),
                     "d_a": round(d_a, 4), "capex": round(capex, 4),
                     "delta_wc": round(delta_wc, 4), "fcff": round(fcff, 4)})
        rev_prev = rev
    return series, {"base_revenue": round(float(base_revenue), 4), "tax_rate": round(float(tax_rate), 4),
                    "base_fcff": round(base_fcff, 4), "delta_wc_first": delta_wc_first,
                    "rows": rows,
                    "formula": "FCFF_t = EBIT_t×(1−t) + D&A_t − Capex_t − ΔWC_t（报表驱动，逐年传导）"}
