"""可比公司筛选证据链（peer_screening）—— v3.20.0 新增

把「可比公司怎么选的」从外部黑箱变成可审计的字段与判据。四期改造对应四个阶段：

  一期 P0-1  长名单 / 剔除台账      audit_long_list()
  一期 P0-4  信息可得性截点          audit_cutoff()
  二期 P0-2  规模双口径 5 倍诊断     diagnose_scale()
  三期 P0-3  同一实体去重            dedupe_entities()
  三期 P1-1  会计准则可比性          gate_accounting()
  四期 P1-4  次新股溢价剔除          gate_seasoning()
  四期 P1-5  行业指数锚降权          index_anchor_haircut()

设计原则
--------
1. **诊断与执行分离**：本模块默认只产出诊断（status / weight_keep / excluded 名单），
   **不改动引擎的任何数值**；仅当输入显式写 `enforce.filter_sample=true` 时才真正过滤样本。
   `enforce.weight_keep=true` 时才把权重让出比例交给引擎。
2. **缺数据只降级、不阻断**：字段缺失一律 warning + `basis` 标注口径来源，
   不返回 unavailable，避免「原本能算，改完算不出来」。
3. **纯标准库**：不依赖引擎、不依赖第三方，可独立单测。

状态机（与降级契约对齐）
------------------------
    ok           有效样本 >= 5 且无致命问题          weight_keep = 1.00
    degraded     3 <= n < 5 / 规模超限 / 截点违规      weight_keep = 0.50
    weak         n < 3                                weight_keep = 0.25
    unavailable  n == 0                               weight_keep = 0.00

用法
----
    from peer_screening import run_peer_screening
    res = run_peer_screening(input_doc, comparables)
"""

from __future__ import annotations

import datetime as _dt

# ---------------------------------------------------------------- 常量

#: 剔除理由枚举（P0-1）。自由文本理由无法被统计，必须落枚举。
REASON_TYPES = {
    "business_model": "业务模式/技术路线不可比",
    "product": "产品档次/应用场景不可比",
    "scale": "规模量级差异过大",
    "status": "ST/*ST/退市/重大重组",
    "data": "财务期间或口径不可得",
    "listing": "上市时间不足（次新股）",
    "accounting": "会计准则不可比",
    "duplicate": "同一发行人重复（A/H/ADR 多股类）",
    "other": "其他（须在 reason 中说明）",
}

#: 行业分类基准（P0-1）。未指定则长名单不可复现。
CLASSIFICATION_SYSTEMS = ("SW_2021", "SW", "CITIC", "CSRC", "GICS", "custom")

#: 规模诊断默认倍数（P0-2，对齐 CVA comps 第 2 步 5 倍规则）
DEFAULT_SCALE_MULTIPLE = 5.0

#: 长名单相对于最终样本的极小倍数（P0-1 筛选粗度判据）
MIN_LONG_LIST_RATIO = 2.0

#: 财务期间相对截点的最大容忍滞后（天，P0-4）
DEFAULT_MAX_LAG_DAYS = 270

#: 次新股剔除阈值（月，P1-4）
DEFAULT_SEASONING_MONTHS = 12
#: 次新观察区间上限（月）——12~24 月标记但不剔除
SEASONING_WATCH_MONTHS = 24

#: 会计准则别名归一（P1-1）
ACCOUNTING_ALIASES = {
    "cas": "CAS", "中国会计准则": "CAS", "cas(中国)": "CAS", "prc_gaap": "CAS",
    "hkfrs": "HKFRS", "hkfrs/ifrs": "HKFRS", "香港财务报告准则": "HKFRS",
    "ifrs": "IFRS", "国际财务报告准则": "IFRS",
    "usgaap": "USGAAP", "us_gaap": "USGAAP", "gaap": "USGAAP", "美国会计准则": "USGAAP",
    "jpgaap": "JPGAAP", "日本会计准则": "JPGAAP",
}

#: 状态 → 权重让出比例 / 置信度上限（降级契约）
STATUS_POLICY = {
    "ok":          {"weight_keep": 1.00, "confidence_cap": None},
    "degraded":    {"weight_keep": 0.50, "confidence_cap": 0.75},
    "weak":        {"weight_keep": 0.25, "confidence_cap": 0.55},
    "unavailable": {"weight_keep": 0.00, "confidence_cap": 0.40},
}

#: 指数锚降权（P1-5）——级别越低、口径越偏离精选可比，权重上限越低
INDEX_ANCHOR_CAP = {
    "primary": 1.00,       # 精选可比为主口径，指数仅交叉验证（不占权重）
    "fallback_l1": 0.50,   # 上下游相邻环节
    "fallback_l2": 0.40,   # 同技术平台不同应用
    "fallback_l3": 0.30,   # 行业整体估值水平（全样本口径，禁止与精选可比同级）
}


# ---------------------------------------------------------------- 工具

def _parse_date(value):
    """容错解析 YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD；失败返回 None。"""
    if not value:
        return None
    if isinstance(value, _dt.date):
        return value
    s = str(value).strip().replace("/", "-")
    if len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _months_between(d1, d2):
    """d1 → d2 的整月数（d2 晚于 d1 时为正）。"""
    if not d1 or not d2:
        return None
    m = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        m -= 1
    return m


def _median(vals):
    vs = sorted(v for v in vals if isinstance(v, (int, float)) and v is not None)
    if not vs:
        return None
    n = len(vs)
    return vs[n // 2] if n % 2 else (vs[n // 2 - 1] + vs[n // 2]) / 2.0


def _deviation(ratio):
    """相对 1 的偏离倍数（取更远一侧）：ratio=6 → 6；ratio=0.1 → 10。"""
    if not ratio or ratio <= 0:
        return None
    return max(ratio, 1.0 / ratio)


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _standardize_std(v):
    if not v:
        return None
    key = str(v).strip().lower().replace(" ", "")
    return ACCOUNTING_ALIASES.get(key, str(v).strip().upper())


def _entity_key(c):
    """同一经营实体的去重键（P0-3）。优先级：legal_entity_id > code 去后缀 > name 归一。"""
    leid = c.get("legal_entity_id")
    if leid:
        return f"leid:{str(leid).strip()}"
    code = c.get("code")
    if code:
        s = str(code).strip().upper()
        for suf in (".SH", ".SZ", ".BJ", ".HK", ".O", ".N", ".SS"):
            if s.endswith(suf):
                s = s[: -len(suf)]
                break
        return f"code:{s}"
    name = c.get("name")
    if name:
        return f"name:{str(name).strip()}"
    return None


# ---------------------------------------------------------------- 一期 P0-1 长名单 / 剔除台账

def audit_long_list(comparables, cfg):
    """长名单与剔除台账审计。

    检查五件事：
      1. 是否声明行业分类基准（否则长名单不可复现）
      2. 长名单规模是否显著大于最终样本（否则说明筛选过粗或未真筛）
      3. 有长名单却无剔除记录（说明没有筛选过程）
      4. 剔除理由是否落枚举（自由文本不可统计）
      5. 最终样本覆盖率
    """
    n_final = sum(1 for c in comparables if c.get("included") is not False)
    long_size = _num(cfg.get("long_list_size"))
    rejected = cfg.get("rejected") or []
    warns, checks = [], {}

    cls = cfg.get("classification_system")
    checks["classification_system"] = {
        "value": cls,
        "valid": bool(cls) and str(cls) in CLASSIFICATION_SYSTEMS,
        "note": "未声明行业分类基准时长名单不可复现，报告不得声称『已穷尽可比』",
    }
    if not cls:
        warns.append("可比筛选：未声明 classification_system（SW_2021/CITIC/CSRC），长名单不可复现")
    elif str(cls) not in CLASSIFICATION_SYSTEMS:
        warns.append(f"可比筛选：classification_system={cls!r} 不在建议枚举 {CLASSIFICATION_SYSTEMS} 内")

    checks["long_list_size"] = {"value": long_size, "n_final": n_final}
    if long_size is None:
        warns.append("可比筛选：未提供 long_list_size，无法判断筛选是否穷尽")
    else:
        ratio = (long_size / n_final) if n_final else None
        checks["long_list_size"]["ratio_to_final"] = round(ratio, 2) if ratio else None
        if ratio is not None and ratio < MIN_LONG_LIST_RATIO:
            warns.append(
                f"可比筛选：长名单 {int(long_size)} 家 / 最终 {n_final} 家 = {ratio:.2f}× < "
                f"{MIN_LONG_LIST_RATIO:.0f}×，筛选过粗或未真正筛选")

    bad_types, ok_rejected = [], []
    for r in rejected:
        rt = (r or {}).get("reason_type")
        if rt not in REASON_TYPES:
            bad_types.append({"name": (r or {}).get("name"), "reason_type": rt,
                              "reason": (r or {}).get("reason")})
        else:
            ok_rejected.append(r)
    checks["rejected"] = {"n": len(rejected), "typed": len(ok_rejected),
                          "untyped": bad_types, "by_type": {}}
    for r in ok_rejected:
        rt = r.get("reason_type")
        checks["rejected"]["by_type"][rt] = checks["rejected"]["by_type"].get(rt, 0) + 1
    if long_size is not None and long_size > n_final and not rejected:
        warns.append(
            f"可比筛选：长名单 {int(long_size)} 家但无任何剔除记录，"
            "监管问询『为何只选这几家』时无证据链")
    if bad_types:
        warns.append(
            f"可比筛选：{len(bad_types)} 条剔除记录 reason_type 缺失或不在枚举内"
            f"（须落 {sorted(REASON_TYPES)[:3]}… 等枚举）")

    return {
        "enabled": True,
        "checks": checks,
        "coverage": round(n_final / long_size, 4) if (long_size and n_final) else None,
        "warnings": warns,
    }


# ---------------------------------------------------------------- 一期 P0-4 信息可得性截点

def audit_cutoff(comparables, cutoff, max_lag_days=DEFAULT_MAX_LAG_DAYS):
    """信息可得性截点审计（P0-4）。

    估值基准日同时是信息截点：不得使用基准日后发布的财报回填。
    违反 → violation=True（报告须显式披露）；滞后过大 → 逐家 warning。
    """
    cut = _parse_date(cutoff)
    if not cut:
        return {"enabled": True, "cutoff": None, "violations": [], "lagged": [],
                "n_missing": len(comparables), "violation": False,
                "warnings": ["可比筛选：未提供信息可得性截点（info_cutoff / meta.valuation_as_of），"
                             "无法校验可比财务期间是否越过基准日"]}

    violations, lagged, missing = [], [], []
    for c in comparables:
        pe = _parse_date(c.get("financial_period_end") or c.get("as_of"))
        if not pe:
            missing.append(c.get("name"))
            continue
        if pe > cut:
            violations.append({"name": c.get("name"), "financial_period_end": pe.isoformat(),
                               "cutoff": cut.isoformat(), "days_after": (pe - cut).days})
        lag = (cut - pe).days
        if lag > max_lag_days:
            lagged.append({"name": c.get("name"), "financial_period_end": pe.isoformat(),
                           "lag_days": lag})

    warns = []
    if violations:
        warns.append(
            f"可比筛选：{len(violations)} 家可比使用了基准日之后发布的财务数据（回填），"
            f"最早违规 {violations[0]['name']} 财报期末 {violations[0]['financial_period_end']} 晚于截点")
    if lagged:
        warns.append(
            f"可比筛选：{len(lagged)} 家可比的财务期末滞后截点 >{max_lag_days} 天"
            f"（最久 {lagged[0]['name']} {lagged[0]['lag_days']} 天），期间错配须披露")
    if missing and len(missing) < len(comparables) + 1:
        warns.append(f"可比筛选：{len(missing)} 家可比未提供 financial_period_end，截点校验对其不生效")

    return {
        "enabled": True, "cutoff": cut.isoformat(),
        "max_lag_days": max_lag_days,
        "violations": violations, "lagged": lagged, "n_missing": len(missing),
        "violation": bool(violations),
        "warnings": warns,
    }


# ---------------------------------------------------------------- 二期 P0-2 规模双口径诊断

def diagnose_scale(target, comparables, cfg, multiple=DEFAULT_SCALE_MULTIPLE):
    """规模与档次诊断（P0-2）。

    对齐 CVA comps 5 倍规则：
      - 分别算「标的 LTM 收入 ÷ 长名单收入中位」与「标的行情日市值 ÷ 长名单市值中位」
      - **取偏离 1 更远者**作为判定基数（更严格）
      - 比值 >multiple 或 <1/multiple → 必须先收窄到产品档次更接近的子组

    口径诚实性：若未提供 long_list_median（长名单中位数），退化为用**最终样本中位**
    作代理，并标注 basis="final_sample_proxy"——判定强度下降，不假装有长名单数据。
    """
    tgt_rev = _num(target.get("revenue_ltm")) or _num(target.get("revenue"))
    tgt_mcap = _num(target.get("market_cap")) or _num(target.get("mktcap"))

    ll = cfg.get("long_list_median") or {}
    ll_rev = _num(ll.get("revenue"))
    ll_mcap = _num(ll.get("market_cap"))
    basis = "long_list"
    if ll_rev is None:
        ll_rev = _median([_num(c.get("revenue_ltm")) or _num(c.get("revenue")) for c in comparables])
        basis = "final_sample_proxy"
    if ll_mcap is None:
        ll_mcap = _median([_num(c.get("market_cap")) or _num(c.get("mktcap")) for c in comparables])
        basis = "final_sample_proxy" if basis == "long_list" else basis

    rev_ratio = (tgt_rev / ll_rev) if (tgt_rev and ll_rev) else None
    mcap_ratio = (tgt_mcap / ll_mcap) if (tgt_mcap and ll_mcap) else None
    rev_dev = _deviation(rev_ratio)
    mcap_dev = _deviation(mcap_ratio)

    binding, binding_dev = None, None
    if rev_dev is not None and (mcap_dev is None or rev_dev >= mcap_dev):
        binding, binding_dev = "revenue", rev_dev
    elif mcap_dev is not None:
        binding, binding_dev = "market_cap", mcap_dev

    exceed = bool(binding_dev is not None and binding_dev > multiple)
    warns = []
    if exceed:
        warns.append(
            f"可比筛选：规模 {binding} 偏离 {binding_dev:.2f}× > {multiple:.0f}× 阈值"
            f"（标的 {tgt_rev if binding == 'revenue' else tgt_mcap} vs "
            f"中位 {ll_rev if binding == 'revenue' else ll_mcap}），"
            "须先收窄到产品档次与盈利驱动更接近的子组，再计算主乘数")
    if basis != "long_list":
        warns.append(
            "可比筛选：未提供 long_list_median，规模诊断退化为最终样本中位作代理"
            "（判定强度下降，报告须披露该口径）")

    return {
        "enabled": True, "multiple": multiple, "basis": basis,
        "target": {"revenue": tgt_rev, "market_cap": tgt_mcap},
        "benchmark": {"revenue_median": ll_rev, "market_cap_median": ll_mcap},
        "ratio": {"revenue": round(rev_ratio, 4) if rev_ratio else None,
                  "market_cap": round(mcap_ratio, 4) if mcap_ratio else None},
        "deviation": {"revenue": round(rev_dev, 4) if rev_dev else None,
                      "market_cap": round(mcap_dev, 4) if mcap_dev else None},
        "binding": binding, "binding_deviation": round(binding_dev, 4) if binding_dev else None,
        "exceed": exceed,
        "action": "narrow_subgroup" if exceed else "keep",
        "warnings": warns,
    }


# ---------------------------------------------------------------- 三期 P0-3 同一实体去重

def dedupe_entities(comparables):
    """同一发行人的 A/H/ADR 只算一个经营实体（P0-3）。

    重复时保留优先级：A 股（CN，估值环境一致） > 市值更大者 > 先出现者。
    被合并的标 `duplicate_of` 供报告披露，不静默丢弃。
    """
    groups = {}
    for idx, c in enumerate(comparables):
        key = _entity_key(c)
        groups.setdefault(key or f"__anon_{idx}", []).append(c)

    keep, merged = [], []
    for key, items in groups.items():
        if len(items) == 1:
            keep.append(items[0])
            continue
        # A 股优先；其次市值大；再次先出现
        def rank(x):
            is_cn = 0 if str(x.get("exchange", "CN") or "CN").upper() == "CN" else 1
            mc = _num(x.get("market_cap")) or _num(x.get("mktcap")) or 0.0
            return (is_cn, -mc)
        items_sorted = sorted(items, key=rank)
        winner = items_sorted[0]
        keep.append(winner)
        for loser in items_sorted[1:]:
            merged.append({
                "name": loser.get("name"), "exchange": loser.get("exchange"),
                "duplicate_of": winner.get("name"), "entity_key": key,
                "reason_type": "duplicate",
                "reason": f"与 {winner.get('name')} 为同一经营实体的不同股类，只计一次",
            })

    warns = []
    if merged:
        warns.append(
            f"可比筛选：{len(merged)} 条记录与另一可比属同一经营实体（A/H/ADR 多股类），"
            f"已合并计一次（如 {merged[0]['name']} → {merged[0]['duplicate_of']}）")

    return {"enabled": True, "n_input": len(comparables), "n_after": len(keep),
            "merged": merged, "kept_names": [c.get("name") for c in keep],
            "warnings": warns}


# ---------------------------------------------------------------- 三期 P1-1 会计准则可比性

def gate_accounting(comparables, target_std, enabled=True):
    """会计准则可比性（P1-1）。

    跨准则样本的净利润口径（股权激励、研发资本化、政府补助）不可直接比，
    须做调节或不进入 P/E 统计。本函数只**标记**不删除——因为 PS/PB 受影响较小，
    报告可对不同乘数采用不同样本集。
    """
    if not enabled:
        return {"enabled": False}
    tgt = _standardize_std(target_std) or "CAS"
    aligned, cross, unknown = [], [], []
    for c in comparables:
        std = _standardize_std(c.get("standard") or c.get("accounting_standard"))
        if std is None:
            unknown.append(c.get("name"))
            aligned.append(c.get("name"))       # 缺省视为与标的同准则（模板缺省 CAS）
        elif std == tgt:
            aligned.append(c.get("name"))
        else:
            cross.append({"name": c.get("name"), "standard": std, "target_standard": tgt,
                          "requires_reconciliation": True})

    warns = []
    if cross:
        detail = ", ".join("%s:%s" % (x["name"], x["standard"]) for x in cross)
        warns.append(
            "可比筛选：%d 家可比会计准则与标的（%s）不同（%s），"
            "净利润口径须调节后才可进入 P/E 统计" % (len(cross), tgt, detail))
    if unknown and len(unknown) > len(comparables) / 2.0:
        warns.append(
            "可比筛选：%d/%d 家可比未声明会计准则，已按标的准则（%s）默认处理，须核实"
            % (len(unknown), len(comparables), tgt))

    return {
        "enabled": True, "target_standard": tgt,
        "aligned": aligned, "cross": cross, "unknown": unknown,
        "n_aligned": len(aligned), "n_cross": len(cross),
        "clean_for_pe": [x for x in aligned],
        "warnings": warns,
    }


# ---------------------------------------------------------------- 四期 P1-4 次新股溢价剔除

def gate_seasoning(comparables, as_of, min_months=DEFAULT_SEASONING_MONTHS, enabled=True):
    """次新股溢价剔除（P1-4）。

    IPO 定价的特殊陷阱：可比若含上市 <12 个月的次新，其 PE 含炒新溢价，
    直接纳入会系统性抬高发行定价、放大破发风险。上市公司估值不受此影响，
    故该判据为 IPO 场景独有。

    三态：excluded（<min_months）/ watch（min_months~24）/ mature（>24 或未声明）
    """
    if not enabled:
        return {"enabled": False}
    cut = _parse_date(as_of)
    if not cut:
        return {"enabled": True, "as_of": None, "excluded": [], "watch": [], "mature": [],
                "warnings": ["可比筛选：未提供估值基准日（as_of），次新股判据未生效"]}

    excluded, watch, mature, unknown = [], [], [], []
    for c in comparables:
        ld = _parse_date(c.get("listing_date"))
        if not ld:
            unknown.append(c.get("name"))
            mature.append(c.get("name"))
            continue
        m = _months_between(ld, cut)
        if m is None:
            unknown.append(c.get("name"))
            mature.append(c.get("name"))
            continue
        if m < min_months:
            excluded.append({"name": c.get("name"), "listing_date": ld.isoformat(),
                             "months_listed": m, "reason_type": "listing",
                             "reason": f"上市 {m} 个月 < {min_months} 个月，PE/PB 含炒新溢价"})
        elif m < SEASONING_WATCH_MONTHS:
            watch.append({"name": c.get("name"), "listing_date": ld.isoformat(),
                          "months_listed": m,
                          "note": f"上市 {m} 个月，处于次新观察区（{min_months}~{SEASONING_WATCH_MONTHS} 月），须做含/剔双口径对照"})
            mature.append(c.get("name"))
        else:
            mature.append(c.get("name"))

    warns = []
    if excluded:
        warns.append(
            f"可比筛选：{len(excluded)} 家可比上市不足 {min_months} 个月（次新），"
            f"其乘数含炒新溢价，已剔除（如 {excluded[0]['name']} 上市 {excluded[0]['months_listed']} 月）")
    if watch:
        warns.append(
            f"可比筛选：{len(watch)} 家可比处于次新观察区，报告中须并列『含次新 / 剔次新』双口径")

    return {
        "enabled": True, "as_of": cut.isoformat(), "min_months": min_months,
        "excluded": excluded, "watch": watch, "mature": mature, "unknown": unknown,
        "warnings": warns,
    }


# ---------------------------------------------------------------- 四期 P1-5 行业指数锚降权

def index_anchor_haircut(index_used, level="fallback_l3", enabled=True):
    """行业指数锚降权（P1-5）。

    指数 PE/PS 是**全样本口径**（含全部成分股），与「精选可比」不是同一口径。
    shortfall 降级到第三级用它做锚时，必须降权并声明口径，不得与前两级同级使用。
    """
    if not enabled:
        return {"enabled": False}
    if not index_used:
        return {"enabled": True, "used": False, "warnings": [],
                "note": "未启用行业指数锚，无需降权"}
    lvl = level if level in INDEX_ANCHOR_CAP else "fallback_l3"
    cap = INDEX_ANCHOR_CAP[lvl]
    warns = []
    if lvl == "fallback_l3":
        warns.append(
            f"可比筛选：行业指数锚为全样本口径（非精选可比），权重上限 {cap:.2f}，"
            "报告中不得与精选可比同级呈现")
    return {
        "enabled": True, "used": True, "fallback_level": lvl,
        "weight_cap": cap,
        "basis": "full_sample_index" if lvl == "fallback_l3" else "selected_peer",
        "note": "指数锚仅作交叉验证或末级替代；fallback_l3 为全行业口径，须显式降权",
        "warnings": warns,
    }


# ---------------------------------------------------------------- 主入口

def _resolve_cutoff(doc, cfg):
    """截点优先级：peer_screening.info_cutoff > meta.valuation_as_of > meta.as_of"""
    meta = doc.get("meta") or {}
    for cand in (cfg.get("info_cutoff"), meta.get("valuation_as_of"), meta.get("as_of")):
        if cand:
            return cand
    return None


def _target_profile(doc):
    """标的规模字段：meta 优先，回落 financials（含模板主字段 revenue_latest_ttm）。"""
    meta = doc.get("meta") or {}
    fin = doc.get("financials") or {}
    out = {}
    # 收入：模板主字段 revenue_latest_ttm 优先，兼容 revenue_ltm / revenue
    for k in ("revenue_ltm", "revenue", "revenue_latest_ttm"):
        v = meta.get(k) if meta.get(k) is not None else fin.get(k)
        if v is not None:
            out["revenue"] = v
            break
    # 市值：meta/financials 显式字段优先，其次股本 × 价格推算
    for k in ("market_cap", "mktcap"):
        v = meta.get(k) if meta.get(k) is not None else fin.get(k)
        if v is not None:
            out["market_cap"] = v
            break
    if out.get("market_cap") is None:
        shares = fin.get("total_shares_after_issue") or fin.get("total_shares")
        price = fin.get("price") or fin.get("share_price")
        if _num(shares) and _num(price):
            out["market_cap"] = shares * price
    return out


def run_peer_screening(doc, comparables=None):
    """四期改造主入口。返回诊断块；仅当 enforce 显式开启时才影响样本与权重。

    参数
    ----
    doc : dict   完整输入 JSON
    comparables : list | None   可比列表（缺省取 doc["comparables"]）

    返回
    ----
    dict  含 enabled / status / stages / effective_sample / enforce / warnings
    """
    cfg = doc.get("peer_screening") or {}
    if not cfg.get("enabled"):
        return {"enabled": False}

    comps = list(comparables if comparables is not None else (doc.get("comparables") or []))
    meta = doc.get("meta") or {}
    cutoff = _resolve_cutoff(doc, cfg)
    depth = str(cfg.get("depth", "full"))       # light | full
    warns = []

    # ---- 三期 P0-3 去重（先做，后续判据都基于去重后样本）
    dedupe = dedupe_entities(comps)
    work = [c for c in comps if c.get("name") in set(dedupe["kept_names"])]
    if not work:
        work = comps

    # ---- 一期 P0-1 长名单 / P0-4 截点
    long_list = audit_long_list(work, cfg)
    cutoff_audit = audit_cutoff(work, cutoff, int(cfg.get("max_lag_days", DEFAULT_MAX_LAG_DAYS)))

    # ---- 二期 P0-2 规模双口径
    scale = diagnose_scale(_target_profile(doc), work, cfg,
                           float(cfg.get("scale_multiple", DEFAULT_SCALE_MULTIPLE)))

    # ---- 三期 P1-1 会计准则
    acct = gate_accounting(work, meta.get("accounting_standard") or meta.get("standard"),
                           enabled=bool(cfg.get("accounting_gate", True)))

    # ---- 四期 P1-4 次新
    season = gate_seasoning(work, cutoff,
                            int(cfg.get("seasoning_months", DEFAULT_SEASONING_MONTHS)),
                            enabled=bool(cfg.get("seasoning_gate", True)))

    # ---- 四期 P1-5 指数锚降权
    idx_cfg = doc.get("industry_index") or {}
    idx_on = bool(idx_cfg.get("enabled")) or any(
        idx_cfg.get(k) is not None for k in ("pe_median", "ps_median", "pb_median"))
    idx = index_anchor_haircut(idx_on,
                               str(cfg.get("index_fallback_level", "fallback_l3")),
                               enabled=bool(cfg.get("index_anchor_haircut", True)))

    # ---- 合格样本（可用于执行模式过滤）
    season_drop = {x["name"] for x in season.get("excluded", [])} if season.get("enabled") else set()
    acct_drop = {x["name"] for x in acct.get("cross", [])} if acct.get("enabled") else set()
    eligible = [c for c in work
                if c.get("included") is not False and c.get("name") not in season_drop]
    n_eff = len(eligible)
    # 回填「有效样本」口径（长名单审计先于合格样本判定，此处补齐供报告三口径并列）
    long_list["checks"]["long_list_size"]["n_eligible"] = n_eff
    long_list["checks"]["long_list_size"]["n_excluded_by_gate"] = len(work) - n_eff

    # ---- 状态判定（降级契约）
    fatal = cutoff_audit.get("violation") or scale.get("exceed")
    if n_eff == 0:
        status = "unavailable"
    elif n_eff < 3:
        status = "weak"
    elif n_eff < 5 or fatal:
        status = "degraded"
    else:
        status = "ok"
    policy = STATUS_POLICY[status]

    # ---- 汇总诊断口径（报告须逐项披露）
    problems = []
    if not long_list["checks"]["classification_system"]["valid"]:
        problems.append("industry_classification_undefined")
    if long_list["checks"]["rejected"]["n"] == 0 and (long_list["checks"]["long_list_size"]["value"] or 0) > n_eff:
        problems.append("no_rejection_log")
    if cutoff_audit.get("violation"):
        problems.append("information_cutoff_violated")
    if scale.get("exceed"):
        problems.append("scale_beyond_5x")
    if acct.get("enabled") and acct.get("n_cross"):
        problems.append("cross_accounting_standard")
    if season.get("enabled") and season.get("excluded"):
        problems.append("seasoning_excluded")
    if dedupe.get("merged"):
        problems.append("duplicate_entity_merged")

    for blk in (dedupe, long_list, cutoff_audit, scale, acct, season, idx):
        for w in blk.get("warnings") or []:
            if w not in warns:
                warns.append(w)

    enforce_cfg = cfg.get("enforce") or {}
    enforce = {
        "filter_sample": bool(enforce_cfg.get("filter_sample", False)),
        "weight_keep": bool(enforce_cfg.get("weight_keep", False)),
        "applied": False,
        "removed": [],
    }

    return {
        "enabled": True,
        "version": "3.20.0",
        "status": status,
        "depth": depth,
        "stages": {
            "s1_long_list": long_list,
            "s1_cutoff": cutoff_audit,
            "s2_scale": scale,
            "s3_dedupe": dedupe,
            "s3_accounting": acct,
            "s4_seasoning": season,
            "s4_index_anchor": idx,
        },
        "effective_sample": {
            "n_input": len(comps),
            "n_deduped": len(work),
            "n_eligible": n_eff,
            "excluded_seasoning": sorted(season_drop),
            "cross_accounting": sorted(acct_drop),
            "included_false": [c.get("name") for c in work if c.get("included") is False],
        },
        "problems": problems,
        "status_policy": {"weight_keep": policy["weight_keep"],
                          "confidence_cap": policy["confidence_cap"]},
        "eligible_names": [c.get("name") for c in eligible],
        "enforce": enforce,
        "warnings": warns,
    }
