# -*- coding: utf-8 -*-
"""第 7 步（a）：金融 RIM/DDM 路由——引擎合成修复 + 报告披露。

背景（600036 A/B 实证）：resolve_method_set 已把金融路由权重算成
{rim 0.6384, comparable 0.3616}，但 scenario() 的 alt_v 只收 rNPV/SOTP，
RIM 价值被静默丢弃（base 4,659.84 = 0.3616×可比；正确应 11,815.33）。
本补丁：
  1) scenario() alt_v 收 rim/ddm（enable_rim / enable_ddm 时）；
  2) 声明权重但取值不可得 → renormalize 剔除并再归一（不留静默缩水）；
  3) 方法分歧度 CV：金融路由下 DCF 名义留痕不参与，改用 RIM vs 可比；
  4) 置信度 method_coverage 有效方法数按可比/RIM/DDM/rNPV/SOTP 计；
  5) methods_available 留痕 rim/ddm；
  6) report_generator：§2/§6.1/§6.3/§7.1/§7.2/§7.3 的 RIM/DDM 披露与文案。

用法：
    python3 step7a_engine.py            # 默认 $HOME/.dsh-valuation/agents/skills/llm-ipo-valuation/scripts
    python3 step7a_engine.py --dry-run
幂等；改前备份 .bak.<时间戳>。
"""
import shutil
import sys
import time
from pathlib import Path

SKILL = Path.home() / '.dsh-valuation/agents/skills/llm-ipo-valuation/scripts'


def rep(src, old, new, tag):
    if src.count(old) != 1:
        sys.exit('[%s] 锚点缺失或多处命中（found %d）' % (tag, src.count(old)))
    return src.replace(old, new, 1)


# ============================ valuation_engine.py ============================
ENG_EDITS = []

# 1) alt_v 收 rim/ddm
ENG_EDITS.append(('alt_v', '''        alt_v = {}
        if rnpv_v is not None:
            alt_v["rnpv"] = rnpv_v
        if sotp_v is not None:
            alt_v["sotp"] = sotp_v
''', '''        alt_v = {}
        if rnpv_v is not None:
            alt_v["rnpv"] = rnpv_v
        if sotp_v is not None:
            alt_v["sotp"] = sotp_v
        # v3.30.0 金融路由：RIM/DDM 进入综合式。此前 alt_v 只收 rNPV/SOTP，
        # resolve_method_set 声明给 RIM 的权重无人读取 → 综合值静默塌缩到其余方法（RIM 价值被丢弃）。
        # RIM/DDM 为情景无关的账面/分红口径（不由情景增速驱动），三情景同值。
        if self.pref.get("enable_rim"):
            _rim_s = self.rim_valuation()
            if _rim_s.get("enabled") and _rim_s.get("value") is not None:
                alt_v["rim"] = float(_rim_s["value"])
        if self.pref.get("enable_ddm"):
            _ddm_s = self.ddm_valuation()
            if _ddm_s.get("enabled") and _ddm_s.get("value") is not None:
                alt_v["ddm"] = float(_ddm_s["value"])
'''))

# 2) 声明权重但取值不可得 → 再归一
ENG_EDITS.append(('alt_missing', '''        w = dict(self.weights)
        if not comp_available and self.method_drop_mode == "renormalize":
''', '''        w = dict(self.weights)
        # v3.30.0：路由声明了 RIM/DDM 权重但取值不可得（缺 B0/ROE/D0）时，不得按 0 静默计入。
        # 与「可比法不可用」同一处置：renormalize 模式剔除该法并按剩余权重再归一（旧输入无 rim/ddm 权重 → 零变化）。
        _alt_missing = [m for m in ("rim", "ddm") if w.get(m, 0.0) > 0 and m not in alt_v]
        if _alt_missing:
            if self.method_drop_mode == "renormalize":
                for _m in _alt_missing:
                    w[_m] = 0.0
                _tot_a = sum(w.values())
                if _tot_a > 0:
                    w = {_k: _v / _tot_a for _k, _v in w.items()}
                if name == "base":
                    self._method_drop = {
                        "dropped": _alt_missing, "mode": "renormalize",
                        "raw_weights": {k: round(self.weights.get(k, 0.0), 4) for k in _alt_missing},
                        "renormalized": {k: round(v, 4) for k, v in w.items()},
                        "reason": ("RIM/DDM 已分配路由权重但取值不可得（缺 B0/ROE/D0），"
                                   "已从综合式剔除并按剩余方法权重再归一"),
                    }
                    self.warnings.append(
                        f"路由主方法 {'、'.join(_alt_missing)} 取值不可得（关键参数缺失），"
                        f"已从综合权重中剔除并按剩余权重再归一："
                        f"{'／'.join(f'{k} {v:.2f}' for k, v in w.items() if v > 0)}。")
            elif name == "base":
                self.warnings.append(
                    f"路由主方法 {'、'.join(_alt_missing)} 取值不可得（关键参数缺失）且 "
                    f"method_drop_mode=zero_silent，按 0 计入 → 综合值会静默缩水；"
                    f"建议 dcf_cost.method_drop_mode=renormalize。")
        if not comp_available and self.method_drop_mode == "renormalize":
'''))

# 3) 方法分歧度：金融路由用 RIM 替代 DCF 名义值
ENG_EDITS.append(('method_vals', '''        method_vals = [base["comparable_adjusted"], base["dcf_value"]]
''', '''        # v3.30.0：金融路由下 DCF 是名义留痕（权重 0、恒为高估方向），不得参与方法分歧度，
        # 否则 CV 被人为抬高 → 虚假「分歧过大」告警与置信度封顶。有 RIM 时以 RIM vs 可比法计。
        _alt_b = base.get("alternative_methods") or {}
        if dcf_inapp and (_alt_b.get("rim") or {}).get("value") is not None:
            method_vals = [base["comparable_adjusted"], _alt_b["rim"]["value"]]
        else:
            method_vals = [base["comparable_adjusted"], base["dcf_value"]]
'''))

# 4) 置信度有效方法数
ENG_EDITS.append(('n_eff', '''            n_eff = 1 if self.weights.get("comparable", 0) > 0 else 0
''', '''            # v3.30.0：按实际携带权重的方法计（金融路由 RIM+可比=2）；原口径只数 comparable，
            # 会把 RIM 路由误判为「单方法驱动」并错误封顶置信度。
            n_eff = sum(1 for _m in ("comparable", "rim", "ddm", "rnpv", "sotp")
                        if self.weights.get(_m, 0.0) > 0)
'''))

# 5) methods_available 留痕
ENG_EDITS.append(('methods_available', '''        methods_inapplicable = []
        if dcf_inapp:                                  # v2.11.4：与 asset_adapter 结论保持一致
            methods_available = [m for m in methods_available if m != "dcf"]
            methods_inapplicable.append("dcf")
''', '''        methods_inapplicable = []
        if dcf_inapp:                                  # v2.11.4：与 asset_adapter 结论保持一致
            methods_available = [m for m in methods_available if m != "dcf"]
            methods_inapplicable.append("dcf")
        # v3.30.0：RIM/DDM 路由主方法留痕（仅权重 >0 时挂出 → 旧输入键集合不变）
        for _m in ("rim", "ddm"):
            if self.weights.get(_m, 0.0) > 0:
                methods_available.append(_m)
'''))


# ============================ report_generator.py ============================
REP_EDITS = []

# R1. 共用变量
REP_EDITS.append(('alt_w', '''    # v3.19.0 P6-B/C：替代主方法（rNPV/SOTP）权重（§7.1 表与综合推导共用；缺省不存在 → 各表不加行）
    _alt_w = out.get("weights") or {}
''', '''    # v3.19.0 P6-B/C：替代主方法（rNPV/SOTP）权重（§7.1 表与综合推导共用；缺省不存在 → 各表不加行）
    _alt_w = out.get("weights") or {}
    # v3.30.0：金融路由主方法 RIM/DDM（多处共用；未启用时为空 dict → 旧文案逐字不变）
    _rim_out = out.get("rim_valuation") or {}
    _ddm_out = out.get("ddm_valuation") or {}
    _rim_main = bool(_rim_out.get("enabled") and _rim_out.get("value") is not None
                     and (_alt_w.get("rim") or 0) > 0)
'''))

# R2. _fw_alert 结论句
REP_EDITS.append(('fw_alert', '''            f'亦不与市场口径构成「互证」</b>。本报告实际主口径为 ② 可比公司法（含盈利质量调整）'
            f'与 ③ 市场舆情（仅情绪），并以 §7.4 净资产法（NAV）及 §4.2 板块 PB 口径作交叉校验。</div>')
''', '''            f'亦不与市场口径构成「互证」</b>。'
            + ((f'本报告实际主口径为 <b>RIM 剩余收益模型</b>（权重 {_fmt(_alt_w.get("rim"))}）'
                f'与 ② 可比公司法（交叉验证，权重 {_fmt(_alt_w.get("comparable"))}）'
                + ('，DDM 作分红口径交叉校验（权重 0）' if (_ddm_out.get("enabled") and _ddm_out.get("value") is not None) else '')
                + '，并以 §7.4 净资产法（NAV）及 §4.2 板块 PB 口径作交叉校验。</div>')
               if _rim_main else
               ('本报告实际主口径为 ② 可比公司法（含盈利质量调整）'
                '与 ③ 市场舆情（仅情绪），并以 §7.4 净资产法（NAV）及 §4.2 板块 PB 口径作交叉校验。</div>')))
'''))

# R3. §6.1 方法框架首句
REP_EDITS.append(('fw_method_txt', '''    _fw_method_txt = (
        ("<b>① DCF 不适用</b>（Layer 0 前提判别：该类主体经营活动现金流不可与负债成本分离、"
         "资本结构受监管约束 → 权重归零并路由替代主方法），综合估值由 <b>② 可比公司法</b>"
         "（可比倍数 + 修正项分层）与 <b>③ 市场舆情</b>（仅情绪）承担；")
        if _dcf_inadm else
        "市场法（可比倍数 + 修正项分层）与内在价值法（两阶段 DCF）并行，")
''', '''    _fw_method_txt = (
        ("<b>① DCF 不适用</b>（Layer 0 前提判别：该类主体经营活动现金流不可与负债成本分离、"
         "资本结构受监管约束 → 权重归零并路由替代主方法），综合估值由 <b>RIM 剩余收益模型</b>"
         "（金融路由主方法）与 <b>② 可比公司法</b>（交叉验证）承担，DDM 仅作分红口径交叉校验（权重 0）；")
        if (_dcf_inadm and _rim_main) else
        ("<b>① DCF 不适用</b>（Layer 0 前提判别：该类主体经营活动现金流不可与负债成本分离、"
         "资本结构受监管约束 → 权重归零并路由替代主方法），综合估值由 <b>② 可比公司法</b>"
         "（可比倍数 + 修正项分层）与 <b>③ 市场舆情</b>（仅情绪）承担；")
        if _dcf_inadm else
        "市场法（可比倍数 + 修正项分层）与内在价值法（两阶段 DCF）并行，")
'''))

# R4. method_items：RIM/DDM 柱（放在 DCF 前，避免 6 柱上限截断）
REP_EDITS.append(('method_items', '''    method_items.append(("DCF", _num(dcf.get("equity_value"))))
''', '''    # v3.30.0：RIM/DDM 进入多方法对比图（RIM 主方法；DDM 交叉验证）
    if _rim_main:
        method_items.append(("RIM", _num(_rim_out.get("value"))))
    if _ddm_out.get("enabled") and _ddm_out.get("value") is not None:
        method_items.append(("DDM（交叉验证）", _num(_ddm_out.get("value"))))
    method_items.append(("DCF", _num(dcf.get("equity_value"))))
'''))

# R5. method_rows：RIM/DDM 行
REP_EDITS.append(('method_rows', '''    method_rows.append((_dcf_row_lbl, f"WACC {_pct(dcf.get('wacc'))} / g {_pct(dcf.get('terminal_growth'))}",
                        _fmt(dcf.get("equity_value")), _dcf_row_ref))
''', '''    method_rows.append((_dcf_row_lbl, f"WACC {_pct(dcf.get('wacc'))} / g {_pct(dcf.get('terminal_growth'))}",
                        _fmt(dcf.get("equity_value")), _dcf_row_ref))
    # v3.30.0：金融路由主方法行（RIM 主 / DDM 交叉验证）
    if _rim_main:
        method_rows.append(("RIM（剩余收益）",
                            f"B0 {_fmt(_rim_out.get('book_value_0'))} 亿 / ROE {_pct(_rim_out.get('roe_steady'))} / Ke {_pct(_rim_out.get('cost_of_equity'))}",
                            _fmt(_rim_out.get("value")),
                            f"权重 {_fmt(_alt_w.get('rim'))}｜终值占比 {_pct(_rim_out.get('tv_share'))}"))
    if _ddm_out.get("enabled") and _ddm_out.get("value") is not None:
        method_rows.append(("DDM（交叉验证）",
                            f"D0 {_fmt(_ddm_out.get('dividend_0'))} 亿 / g1 {_pct(_ddm_out.get('growth_explicit'))} / Ke {_pct(_ddm_out.get('cost_of_equity'))}",
                            _fmt(_ddm_out.get("value")),
                            f"权重 {_fmt(_alt_w.get('ddm'))}（分红口径交叉验证，不参与综合）"))
'''))

# R6. der_rows：RIM/DDM 推导行
REP_EDITS.append(('der_rows', '''    # v3.19.0 P6-B/C：替代主方法进入综合推导（仅启用时插行）
''', '''    # v3.30.0：金融路由主方法进入综合推导（RIM 主方法 / DDM 交叉验证）
    if _rim_main:
        der_rows.append(("＋ RIM × w_rim",
                         f"{_fmt(_rim_out.get('value'))} 亿",
                         f"权重 {_fmt(_alt_w.get('rim'))}（B0 {_fmt(_rim_out.get('book_value_0'))} 亿、"
                         f"ROE {_pct(_rim_out.get('roe_steady'))}、Ke {_pct(_rim_out.get('cost_of_equity'))}）"))
    if _ddm_out.get("enabled") and _ddm_out.get("value") is not None:
        der_rows.append(("＋ DDM × w_ddm",
                         f"{_fmt(_ddm_out.get('value'))} 亿",
                         f"权重 {_fmt(_alt_w.get('ddm'))}（分红口径交叉验证，不参与综合）"))
    # v3.19.0 P6-B/C：替代主方法进入综合推导（仅启用时插行）
'''))

# R7. _fit_rows 可比法「主口径」→ 交叉验证
REP_EDITS.append(('fit_comp', '''         f"<b>主口径</b>（权重 {_fmt(_fit_wcomp)}）｜可用乘数：{_mid_lbl}"),
''', '''         (f"交叉验证（权重 {_fmt(_fit_wcomp)}）｜可用乘数：{_mid_lbl}" if _rim_main else
          f"<b>主口径</b>（权重 {_fmt(_fit_wcomp)}）｜可用乘数：{_mid_lbl}")),
'''))

# R8. _fit_rows 追加 RIM/DDM 适用性行
REP_EDITS.append(('fit_alt', '''    # 补充锚
    anchor_rows = []
''', '''    # v3.30.0：RIM/DDM 适用性行（金融路由，仅启用时挂出）
    if _rim_main:
        _fit_rows.insert(2 + (1 if _fit_rnpv.get("enabled") else 0) + (1 if _fit_sotp.get("enabled") else 0), (
            "RIM<br>（剩余收益模型）",
            "银行/保险/券商等受监管资本约束的金融主体：债务为经营原料、FCFF 不可定义；"
            "账面净资产是估值核心锚，价值来自 ROE 与 Ke 的价差",
            "对 Ke、稳态 ROE 与持续因子 ω 敏感；账面价值须为归母普通股权益（不含少数股东与其他权益工具）；"
            "ROE < Ke 时估值低于账面，模型不给出成长溢价",
            (f"<b>主口径</b>（权重 {_fmt(_alt_w.get('rim'))}）｜B0 {_fmt(_rim_out.get('book_value_0'))} 亿元、"
             f"ROE {_pct(_rim_out.get('roe_steady'))} / Ke {_pct(_rim_out.get('cost_of_equity'))}｜"
             f"RIM {_fmt(_rim_out.get('value'))} 亿元")))
    if _ddm_out.get("enabled") and _ddm_out.get("value") is not None:
        _fit_rows.insert((3 if _rim_main else 2) + (1 if _fit_rnpv.get("enabled") else 0) + (1 if _fit_sotp.get("enabled") else 0), (
            "DDM<br>（股利折现）",
            "已进入成熟期、分红政策稳定的金融/公用事业主体；D0 可由净利×分红率推得",
            "仅刻画分红价值，留存收益的再投资价值被忽略；对 Ke 与 g∞ 的差值极度敏感（Ke−g∞ < 2% 时失真）",
            (f"交叉验证（权重 {_fmt(_alt_w.get('ddm'))}，不参与综合）｜D0 {_fmt(_ddm_out.get('dividend_0'))} 亿元、"
             f"g1 {_pct(_ddm_out.get('growth_explicit'))} / g∞ {_pct(_ddm_out.get('terminal_growth'))}｜"
             f"DDM {_fmt(_ddm_out.get('value'))} 亿元")))

    # 补充锚
    anchor_rows = []
'''))

# R9. §7.3 标题变量
REP_EDITS.append(('sec73', '''    alt_disc = _alt_method_disclosure(out)
    tg_disc = _terminal_growth_disclosure(out)
    gm_disc = _growth_path_model_disclosure(out)

    gen_at = datetime.now().strftime("%Y-%m-%d %H:%M")
''', '''    alt_disc = _alt_method_disclosure(out)
    tg_disc = _terminal_growth_disclosure(out)
    gm_disc = _growth_path_model_disclosure(out)
    # v3.30.0：金融路由（four_part_mode=false）下 §7.3 不再是四部分合成，标题改为替代主方法披露
    _sec73_txt = ("7.3 替代主方法披露（RIM 剩余收益 / DDM 股利折现交叉验证）"
                  if (_rim_main and not four_part)
                  else "7.3 四部分合成（①DCF ②可比法 ③市场舆情 ④统计检验）")

    gen_at = datetime.now().strftime("%Y-%m-%d %H:%M")
'''))

# R10. §6.1 权重行
REP_EDITS.append(('weights_line', '''<p>{_fw_method_txt}权重 w_dcf={_fmt(out.get('weights', {}).get('dcf'))} / w_comparable={_fmt(out.get('weights', {}).get('comparable'))} / w_sentiment={_fmt(out.get('weights', {}).get('sentiment'))}；
''', '''<p>{_fw_method_txt}权重 w_dcf={_fmt(out.get('weights', {}).get('dcf'))} / w_comparable={_fmt(out.get('weights', {}).get('comparable'))} / w_sentiment={_fmt(out.get('weights', {}).get('sentiment'))}{_fw_w_extra}；
'''))

# R11. §7.3 标题行
REP_EDITS.append(('sec73_html', '''<h3>7.3 四部分合成（①DCF ②可比法 ③市场舆情 ④统计检验）</h3>
''', '''<h3>{_sec73_txt}</h3>
'''))

# R12. narrative 口径关系
REP_EDITS.append(('narr', '''                    f"DCF 名义值 {_fmt(_dcf_legacy)} 亿元系 WACC/FCFF 口径对金融主体不适配所致，"
                    f"不构成内在价值判断")
''', '''                    f"DCF 名义值 {_fmt(_dcf_legacy)} 亿元系 WACC/FCFF 口径对金融主体不适配所致，"
                    f"不构成内在价值判断")
        _rim_n = out.get("rim_valuation") or {}
        _rim_w_n = _num((out.get("weights") or {}).get("rim")) or 0.0
        if _rim_n.get("enabled") and _rim_n.get("value") is not None and _rim_w_n > 0:
            gap_note += (f"。实际主口径为 RIM 剩余收益模型（{_fmt(_rim_n.get('value'))} 亿元，"
                         f"权重 {_fmt(_rim_w_n)}），可比法 {_fmt(base.get('comparable_adjusted'))} 亿元"
                         f"作市场口径交叉验证（推导见 §7.2、明细见 §7.3.6）")
'''))

# R13. _alt_method_disclosure 追加 RIM/DDM 披露块
REP_EDITS.append(('alt_disc', '''            f'可比法作交叉验证。</p>')
    return "".join(blocks)
''', '''            f'可比法作交叉验证。</p>')
    rm = out.get("rim_valuation") or {}
    if rm.get("enabled") and rm.get("value") is not None:
        rows = [(str(r.get("year")), _pct(r.get("roe")), _fmt(r.get("book")), _fmt(r.get("residual_income")))
                for r in rm.get("schedule") or []]
        tbl = _table(["年", "ROE", "期末账面价值（亿元）", "剩余收益 RI（亿元）"], rows, num_cols=[1, 2, 3])
        blocks.append(
            '<h3>7.3.6 RIM 剩余收益披露（v3.30.0 金融路由主方法）</h3>'
            f'{tbl}'
            f'<p class="small">口径：<b>V0 = B0 + Σ (ROE_t − Ke)·B_{{t−1}}/(1+Ke)^t + TV</b>，'
            f'B0 = {_fmt(rm.get("book_value_0"))} 亿元（归母普通股权益），'
            f'ROE(稳态) {_pct(rm.get("roe_steady"))}、Ke {_pct(rm.get("cost_of_equity"))}、'
            f'分红率 {_pct(rm.get("payout_ratio"))}、持续因子 ω {_fmt(rm.get("persistence"), 2)}；'
            f'显式期 {len(rows)} 年，账面价值按「留存剩余收益」滚存。'
            f'显式期 RI 现值 {_fmt(rm.get("pv_residual_income"))} 亿元、终值现值 {_fmt(rm.get("tv_pv"))} 亿元'
            f'（终值占比 {_pct(rm.get("tv_share"))}）→ RIM 价值 <b>{_fmt(rm.get("value"))} 亿元</b>'
            + (f'（每股 {_fmt(rm.get("per_share"), 2)} 元）' if rm.get("per_share") else '')
            + '。金融主体债务为经营原料、资本结构受监管约束，FCFF/WACC 不可定义，故以 RIM 为主方法；'
              '可比法作市场口径交叉验证。</p>')
    dm = out.get("ddm_valuation") or {}
    if dm.get("enabled") and dm.get("value") is not None:
        rows = [(str(r.get("year")), _fmt(r.get("dividend"))) for r in dm.get("schedule") or []]
        tbl = _table(["年", "股利（亿元）"], rows, num_cols=[1])
        _guards = "；".join(dm.get("applicability_warnings") or []) or "无"
        blocks.append(
            '<h3>7.3.7 DDM 股利折现披露（v3.30.0 金融路由交叉验证）</h3>'
            f'{tbl}'
            f'<p class="small">口径：两阶段股利折现（显式期逐年 + Gordon 终值）。'
            f'D0 = {_fmt(dm.get("dividend_0"))} 亿元（{_esc(dm.get("net_profit_source") or "—")} × '
            f'分红率 {_pct(dm.get("payout_ratio"))}）、'
            f'g1 = {_pct(dm.get("growth_explicit"))}、g∞ = {_pct(dm.get("terminal_growth"))}、'
            f'Ke = {_pct(dm.get("cost_of_equity"))}；显式期现值 {_fmt(dm.get("pv_explicit"))} 亿元、'
            f'终值现值 {_fmt(dm.get("tv_pv"))} 亿元（终值占比 {_pct(dm.get("tv_share"))}）→ '
            f'DDM 价值 <b>{_fmt(dm.get("value"))} 亿元</b>。'
            f'适用性告警：{_guards}。按中证协口径，DDM 仅适用于成熟期/分红稳定项目，'
            f'本报告仅作分红口径交叉验证、不参与综合权重。</p>')
    return "".join(blocks)
'''))

# R14. 核心观点「方法结构」
REP_EDITS.append(('method_struct', '''    _method_struct = ((f"可比 {_comp_syn_v} / DCF <b>不适用</b>（Layer 0 判否，权重 "
                       f"{_fmt(out.get('weights', {}).get('dcf'))}；名义留痕 {_fmt(dcf.get('equity_value'))} 亿元）")
                      if _dcf_inadm else
                      (f"可比 {_comp_syn_v} / DCF {_fmt(dcf.get('equity_value'))} 亿元（比值 {_fmt(syn.get('dcf_vs_comparable_gap'))}）"))
''', '''    _method_struct = (
        (f"RIM {_fmt(_rim_out.get('value'))}（权重 {_fmt(_alt_w.get('rim'))}） / "
         f"可比 {_comp_syn_v}（交叉验证）；DCF <b>不适用</b>（Layer 0 判否，"
         f"名义留痕 {_fmt(dcf.get('equity_value'))} 亿元）")
        if (_dcf_inadm and _rim_main) else
        ((f"可比 {_comp_syn_v} / DCF <b>不适用</b>（Layer 0 判否，权重 "
          f"{_fmt(out.get('weights', {}).get('dcf'))}；名义留痕 {_fmt(dcf.get('equity_value'))} 亿元）")
         if _dcf_inadm else
         (f"可比 {_comp_syn_v} / DCF {_fmt(dcf.get('equity_value'))} 亿元（比值 {_fmt(syn.get('dcf_vs_comparable_gap'))}）")))
'''))


def patch_engine(dry=False):
    f = SKILL / 'valuation_engine.py'
    src = f.read_text(encoding='utf-8')
    if 'RIM/DDM 进入综合式' in src and '_alt_missing' in src:
        print('engine: already patched')
        return
    out = src
    for tag, old, new in ENG_EDITS:
        out = rep(out, old, new, tag)
    if dry:
        print('engine dry-run ok, %d edits' % len(ENG_EDITS))
        return
    ts = time.strftime('%Y%m%d_%H%M%S')
    shutil.copy2(f, f.with_suffix(f.suffix + '.bak.%s' % ts))
    f.write_text(out, encoding='utf-8')
    print('engine patched (%d edits, backup .bak.%s)' % (len(ENG_EDITS), ts))


def patch_report(dry=False):
    f = SKILL / 'report_generator.py'
    src = f.read_text(encoding='utf-8')
    if '7.3.6 RIM 剩余收益披露' in src and '_rim_main' in src:
        print('report: already patched')
        return
    out = src
    for tag, old, new in REP_EDITS:
        out = rep(out, old, new, tag)
    # R10 依赖 _fw_w_extra 定义：插在 method_rows 之后、html_doc 之前（与 _sec73 同块）
    anchor = '''    # v3.30.0：金融路由（four_part_mode=false）下 §7.3 不再是四部分合成，标题改为替代主方法披露
'''
    extra = ('''    # v3.30.0：§6.1 权重行的 RIM/DDM 追加（未启用时为空串 → 旧文案逐字不变）
    _fw_w_extra = ""
    if _rim_main:
        _fw_w_extra += f" / w_rim={_fmt(_alt_w.get('rim'))}"
    if _ddm_out.get("enabled") and _ddm_out.get("value") is not None:
        _fw_w_extra += f" / w_ddm={_fmt(_alt_w.get('ddm'))}（交叉验证）"
'''
             + anchor)
    if out.count(anchor) != 1:
        sys.exit('[fw_w_extra] 锚点缺失（found %d）' % out.count(anchor))
    out = out.replace(anchor, extra, 1)
    if dry:
        print('report dry-run ok, %d edits' % (len(REP_EDITS) + 1))
        return
    ts = time.strftime('%Y%m%d_%H%M%S')
    shutil.copy2(f, f.with_suffix(f.suffix + '.bak.%s' % ts))
    f.write_text(out, encoding='utf-8')
    print('report patched (%d edits, backup .bak.%s)' % (len(REP_EDITS) + 1, ts))


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    patch_engine(dry)
    patch_report(dry)
    print('done')