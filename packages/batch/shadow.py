# -*- coding: utf-8 -*-
"""影子模式阶段一：可比质量专家 + 估值主审（默认关）。

主 agent（专家）在可比证据链上提出参数变更建议，主审独立复核、夹断或驳回；
建议只留痕，引擎始终使用原参数。评估只看离散度、置信度校准、周环比稳定性与人工采纳率，
不看拟合点位是否更贴近指数收盘。

- 参数面只有三项：comp_weight_pp（可比权重三档 5/8/10pp）、wacc_pp（±0.2pp 步长）、tg_pp（±0.2pp 步长）
- 证据门槛：每条建议必须声明 severity、confidence≥0.65、引用具体数字的 evidence 与理由，
  幅度按 severity 夹断（可比 medium/high/critical = 5/8/10pp、WACC 0.4/1.0pp、永续 0.2/0.6pp）；
  未过门槛的建议留痕但不进主审
- 证据：输入 comparable/peer_screening + 引擎 assumptions_summary/wacc_model/lifecycle/growth_triangulation
- 落盘：runtime/jobs/<id>/<code>.shadow.json（逐券）+ shadow.html（任务级 sidecar）
- 密钥：复用 sentiment_llm 的仓库外读取（DEEPSEEK_API_KEY），失败只标记该券影子错误，不影响跑批
"""
import html
import json
import os
import re
import statistics
import sys
import threading
import time
from pathlib import Path

import sentiment_llm

STEPS = {'comp_weight_pp': (5.0, 10.0), 'wacc_pp': (0.2, 0.2), 'tg_pp': (0.2, 0.2)}
MAX_ABS = {'comp_weight_pp': 10.0, 'wacc_pp': 1.0, 'tg_pp': 0.6}
MIN_SUGGEST_CONF = 0.65
SEVERITY_CAP = {
    'comp_weight_pp': {'medium': 5.0, 'high': 8.0, 'critical': 10.0},
    'wacc_pp': {'medium': 0.4, 'high': 1.0},
    'tg_pp': {'medium': 0.2, 'high': 0.6},
}
LABEL = {'comp_weight_pp': '可比权重', 'wacc_pp': 'WACC', 'tg_pp': '永续增速'}
DECISION_CN = {'accept': '通过', 'partial': '部分通过', 'reject': '驳回', 'hold': '维持', 'error': '专家失败'}
PARAMS = ('comp_weight_pp', 'wacc_pp', 'tg_pp')

_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get('VALUATION_SHADOW_CONCURRENCY') or 6)))

EXPERT_SYSTEM = (
    '你是 A 股指数成分券估值的「可比公司质量专家」。你只审查本次估值证据的质量，判断是否需要调整三类参数；'
    '你看不到拟合点位，也不得以“更贴近指数收盘”为由提建议。\n'
    '默认结论是维持原参数。只有证据指出具体、可量化的缺陷时才提建议；不要为了提而提。\n'
    '审查维度：\n'
    '1) 样本量与筛池：纳入可比数、长名单规模、筛池覆盖率、因规模/业务模式被剔除的比例；\n'
    '2) 规模可比：目标公司营收/市值与基准中位数、规模倍数是否匹配；\n'
    '3) 业务与会计可比：业务模式、报告期、会计准则是否一致；\n'
    '4) 倍数质量：PE/PS 是否异常（负利润、极端值）、可比增长差异；\n'
    '5) 折现参数证据：beta 水平与来源、CAPM 输入、永续增速与生命周期/增长三角是否匹配。\n'
    '每条建议必须同时给出 severity、confidence、evidence、reason：\n'
    '- confidence<0.65 不要提；evidence 必须引用上面证据中的具体数字（家数/覆盖率/营收/市值/PE/beta/增长率等），'
    '不得空泛；\n'
    '- 幅度必须与证据强度匹配，不要机械取最小步长。\n'
    '严重度按数据三档判定，不得主观降级：\n'
    '- comp_weight_pp：critical 当纳入可比≤1 家、或筛池覆盖率<10%、或业务/会计明确不可比，'
    '幅度固定 10pp；high 当纳入可比 2 家、或覆盖率 10%~20%、或规模倍数≥5×、或个别可比倍数严重失真，'
    '幅度固定 8pp；medium 仅当覆盖率 20%~35%、或规模倍数 3~5×、或倍数轻度失真但仍可容忍，'
    '幅度固定 5pp；覆盖率≥35% 且规模倍数<3× 且无极端倍数/会计差异时，不得提 comp 建议；\n'
    '- wacc_pp：medium ±0.2~0.4pp；high ±0.6~1.0pp，且 high 仅限 beta 样本/来源明显失真、'
    '或 CAPM 结果与证据明确冲突；\n'
    '- tg_pp：medium ±0.2pp；high ±0.4~0.6pp，且 high 仅限生命周期、增长三角或可比增长明确矛盾。\n'
    'severity 与幅度必须按上表对应：符合更高档条件时不得报低档，也不得只报最小幅度；'
    'critical 只能用于可比权重，上调可比权重只能用 medium/high（≤8pp）。\n'
    '建议方向必须与理由一致：可比证据不足时只能下调可比权重；若上调，必须在 evidence 中引用可比证据优于其他方法的数字'
    '（如覆盖率≥35%、规模倍数<3×、倍数离散度低），否则不要提。\n'
    '可比样本质量不能作为 WACC/永续增速的依据，每个参数必须有独立证据。证据不足返回空 suggestions。\n'
    '输出严格 JSON：{"issues":["最多5条，每条不超过40字"],'
    '"suggestions":[{"param":"comp_weight_pp|wacc_pp|tg_pp","delta":数字,"severity":"medium|high|critical",'
    '"confidence":0到1的小数,"evidence":"引用证据中的具体数字，不超过60字","reason":"不超过50字"}],'
    '"confidence":0到1的小数,"one_line":"不超过30字结论"}。只输出 JSON。'
)

MAIN_SYSTEM = (
    '你是估值批跑的「主审」，独立复核可比质量专家提出的参数变更建议。职责是防止过度反应：\n'
    '- 逐条核对四项门槛：severity 必须是 medium/high（可比另允许 critical，且 critical 只能用于可比）；'
    'confidence≥0.65；evidence 必须引用证据中的具体数字；'
    '幅度必须与 severity 表匹配（可比 critical 10pp / high 8pp / medium 5pp、WACC 0.4/1.0pp、永续 0.2/0.6pp）；'
    '任一项不满足即驳回；\n'
    '- 若 evidence 显示覆盖率<10% 或纳入可比≤1 家，但专家报 high/medium 且幅度低于 10pp；'
    '或显示覆盖率 10%~20%、规模倍数≥5×、纳入可比 2 家等高严重度条件，但专家报 medium 且幅度仅 5pp，'
    '视为严重度与证据不符，驳回；\n'
    '- 建议方向必须与证据和理由一致；理由写“下调”但 final_delta 为正（或反之）时驳回；'
    '可比证据不足却上调可比权重时驳回；\n'
    '- 每条建议必须由给定证据直接支持；证据弱、与证据矛盾或方向不明时驳回；\n'
    '- 可选择接受 accept、向下夹断 clamp 或驳回 reject；不得新增专家未提的参数；\n'
    '- comp_weight_pp 只能在 5~10pp 内；wacc_pp 只能 0.2pp 整数倍且绝对值≤1.0pp；'
    'tg_pp 只能 0.2pp 整数倍且绝对值≤0.6pp；调整后 WACC 必须高于永续增速；\n'
    '- 这是影子模式：建议不进入引擎，但记录会被人工复核，宁可保守。\n'
    '输出严格 JSON：{"items":[{"param":"同上","status":"accept|reject|clamp",'
    '"final_delta":数字,"reason":"不超过40字"}],"decision":"accept|partial|reject",'
    '"confidence":0到1的小数,"one_line":"不超过30字"}。items 必须覆盖专家的每条建议。只输出 JSON。'
)


def _now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def _num(v):
    try:
        f = float(v)
        return f if f == f and abs(f) != float('inf') else None
    except (TypeError, ValueError):
        return None


def _round(x, n=2):
    return None if x is None else round(x + 0.0, n)


def _pct(v, n=2):
    x = _num(v)
    return None if x is None else round(x * 100.0, n)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _json_of(content):
    text = (content or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.startswith('json'):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        i, j = text.find('{'), text.rfind('}')
        if i >= 0 and j > i:
            return json.loads(text[i:j + 1])
        raise


def _one_line(v, n=60):
    return str(v or '').replace('\n', ' ').strip()[:n]


# ── 证据与基线 ──────────────────────────────────────────────────────────────

def baseline(eng, weights=None):
    """原参数基线：引擎实际采用的 WACC/永续增速 + 合成权重。"""
    dcf = (eng.get('assumptions_summary') or {}).get('dcf') or {}
    w = eng.get('weights') or weights or {}
    comp = _num(w.get('comparable'))
    if comp is None:
        comp = _num(w.get('comp'))
    if comp is not None and comp <= 1.5:
        comp *= 100.0
    return {
        'comp_weight': _round(comp, 1),
        'wacc_pct': _pct(dcf.get('wacc')),
        'tg_pct': _pct(dcf.get('terminal_growth')),
        'wacc_source': _one_line(dcf.get('wacc_source'), 40),
        'tg_source': _one_line(dcf.get('tg_source'), 40),
    }


def _fmt(x, digits=2, suffix=''):
    return '—' if x is None else ('%.*f%s' % (digits, x, suffix))


def _peer_lines(inp, eng):
    ps_in = inp.get('peer_screening') or {}
    ps_out = eng.get('peer_screening') or {}
    lines = []
    med = ps_in.get('long_list_median') or {}
    lines.append('输入筛池：长名单 %s 家 · 中位营收 %s 亿 · 中位市值 %s 亿 · 规模倍数 %s×' % (
        _fmt(_num(ps_in.get('long_list_size')), 0), _fmt(_num(med.get('revenue'))),
        _fmt(_num(med.get('market_cap'))), _fmt(_num(ps_in.get('scale_multiple')), 1)))
    rej = ps_in.get('rejected') or []
    if rej:
        by = {}
        for r in rej:
            t = str(r.get('reason_type') or 'other')
            by[t] = by.get(t, 0) + 1
        lines.append('剔除 %d 家：%s' % (len(rej), '、'.join('%s %d' % (k, v) for k, v in sorted(by.items()))))
        for r in rej[:4]:
            lines.append('  · %s（%s）%s' % (_one_line(r.get('name'), 12), _one_line(r.get('code'), 12),
                                              _one_line(r.get('reason'), 44)))
    stages = ps_out.get('stages') or {}
    s1 = ((stages.get('s1_long_list') or {}).get('checks') or {})
    ll = s1.get('long_list_size') or {}
    if ll:
        lines.append('引擎筛池：候选 %s → 纳入 %s（覆盖率 %s）' % (
            _fmt(_num(ll.get('value')), 0), _fmt(_num(ll.get('n_final')), 0),
            _fmt(_pct(ps_out.get('stages', {}).get('s1_long_list', {}).get('coverage') or
                      ps_out.get('coverage')), 1, '%')))
    s2 = stages.get('s2_scale') or {}
    bench = s2.get('benchmark') or {}
    tgt = s2.get('target') or {}
    if bench or tgt:
        lines.append('规模基准：营收中位 %s 亿 / 市值中位 %s 亿；目标营收 %s 亿 / 市值 %s 亿；倍数 %s×' % (
            _fmt(_num(bench.get('revenue_median'))), _fmt(_num(bench.get('market_cap_median'))),
            _fmt(_num(tgt.get('revenue'))), _fmt(_num(tgt.get('market_cap'))),
            _fmt(_num(s2.get('multiple')), 1)))
    if ps_out.get('status'):
        lines.append('筛池状态：%s（depth=%s）' % (_one_line(ps_out.get('status'), 16), _one_line(ps_out.get('depth'), 12)))
    return lines


def evidence_text(inp, eng, base):
    meta = inp.get('meta') or {}
    fin = inp.get('financials') or {}
    life = eng.get('lifecycle') or {}
    growth = eng.get('growth_triangulation') or {}
    wm = eng.get('wacc_model') or {}
    comps = inp.get('comparables') or []

    lines = ['公司：%s（%s），行业 %s，会计准则 %s' % (
        _one_line(meta.get('company'), 20), _one_line(meta.get('ticker'), 14),
        _one_line(meta.get('industry'), 20), _one_line(meta.get('accounting_standard'), 10))]
    lines.append('当前参数：可比权重 %s%% · WACC %s%%（%s）· 永续增速 %s%%（%s）' % (
        _fmt(base.get('comp_weight'), 1), _fmt(base.get('wacc_pct')), base.get('wacc_source') or '—',
        _fmt(base.get('tg_pct')), base.get('tg_source') or '—'))
    if wm:
        lines.append('CAPM：rf %s%% · ERP %s%% · beta %s（%s）· kd %s%% · 税率 %s%% · D/E %s → 权益成本 %s%%' % (
            _fmt(_pct(wm.get('rf'))), _fmt(_pct(wm.get('erp'))), _fmt(_num(wm.get('beta')), 2),
            _one_line(wm.get('beta_source'), 26), _fmt(_pct(wm.get('cost_of_debt')), 1),
            _fmt(_pct(wm.get('tax_rate')), 0), _fmt(_num(wm.get('d_e_ratio')), 2),
            _fmt(_pct(wm.get('cost_of_equity')))))
    lines.append('财务：TTM 营收 %s 亿 · 净利率 %s%% · ROE %s%% · 3年营收CAGR %s%% · 亏损 %s' % (
        _fmt(_num(fin.get('revenue_latest_ttm'))), _fmt(_pct(fin.get('net_margin')), 1),
        _fmt(_pct(fin.get('roe')), 1),
        _fmt(_pct((life.get('evidence') or {}).get('cagr_3y')), 1),
        '是' if fin.get('loss_making') else '否'))
    if life:
        lines.append('生命周期：%s（%s，置信 %s）；可比中位增长 %s%%；隐含永续增速 %s%%' % (
            _one_line(life.get('stage_label'), 16), _one_line(life.get('source'), 14),
            _fmt(_num(life.get('confidence')), 2), _fmt(_num(growth.get('comparable_median_growth')), 2),
            _fmt(_pct(growth.get('implied_terminal_growth')), 2)))

    inc = [c for c in comps if c.get('included', True)]
    lines.append('纳入可比 %d 家：' % len(inc))
    for c in inc[:8]:
        lines.append('  · %s（%s）PE %s / PS %s · 营收 %s 亿 · 市值 %s 亿 · 增长 %s%% · %s · 报告期 %s%s' % (
            _one_line(c.get('name'), 12), _one_line(c.get('code'), 12),
            _fmt(_num(c.get('pe'))), _fmt(_num(c.get('ps'))),
            _fmt(_num(c.get('revenue'))), _fmt(_num(c.get('mktcap'))),
            _fmt(_num(c.get('growth_pct')), 1), _one_line(c.get('standard'), 8),
            _one_line(c.get('financial_period_end'), 10),
            (' · ' + _one_line(c.get('note'), 30)) if c.get('note') else ''))
    lines.extend(_peer_lines(inp, eng))
    text = '\n'.join(lines)
    return text[:3200]


# ── 建议生成、规则化与主审合并 ─────────────────────────────────────────────

def _normalize(param, delta):
    """把任意幅度归到允许步长与上限；不足最小步长 → 0。"""
    d = _num(delta) or 0.0
    if param == 'comp_weight_pp':
        if abs(d) < 5.0:
            return 0.0
        return round(_clamp(d, -10.0, 10.0), 1)
    if param in ('wacc_pp', 'tg_pp'):
        d = round(d / 0.2) * 0.2
        return round(_clamp(d, -MAX_ABS[param], MAX_ABS[param]), 1)
    return 0.0


_DOWN_WORDS = ('下调', '降低', '减少', '调低', '压低')
_UP_WORDS = ('上调', '提高', '增加', '调高', '抬升')


def _direction_conflict(text, delta):
    t = text or ''
    down = any(w in t for w in _DOWN_WORDS)
    up = any(w in t for w in _UP_WORDS)
    if down and up:
        return False
    return bool((delta > 0 and down) or (delta < 0 and up))


def _comp_sample_poor(inp, eng):
    """结构化证据：可比样本是否差到只能下调权重。"""
    ps_in = inp.get('peer_screening') or {}
    ps_out = eng.get('peer_screening') or {}
    inc = [c for c in inp.get('comparables') or [] if c.get('included', True)]
    scale = _num(ps_in.get('scale_multiple'))
    cov = _pct(((ps_out.get('stages') or {}).get('s1_long_list') or {}).get('coverage'))
    if cov is None:
        cov = _pct(ps_out.get('coverage'))
    return (len(inc) < 3 or (scale is not None and scale >= 5.0)
            or (cov is not None and cov < 20.0))


def _proposals(expert, base, inp=None, eng=None):
    """规则化专家建议并执行证据门槛；未过门槛的进入 gated 留痕，不送主审。"""
    out, gated = [], []
    seen = set()
    for s in expert.get('suggestions') or []:
        if not isinstance(s, dict):
            continue
        param = str(s.get('param') or '')
        if param not in PARAMS or param in seen:
            continue
        seen.add(param)
        raw = _num(s.get('delta'))
        conf = _num(s.get('confidence'))
        severity = str(s.get('severity') or '').strip().lower()
        evidence = _one_line(s.get('evidence'), 80)
        reason = _one_line(s.get('reason'), 80)
        gate = None
        if severity == 'critical' and param != 'comp_weight_pp':
            gate = '严重档仅用于可比权重'
        elif severity not in SEVERITY_CAP[param]:
            gate = '未声明有效严重度'
        elif conf is None or conf < MIN_SUGGEST_CONF:
            gate = '置信度低于 0.65'
        elif len(evidence) < 6 or not re.search(r'\d', evidence):
            gate = '证据未引用具体数字'
        elif len(reason) < 4:
            gate = '缺少理由'
        elif raw is None or raw == 0:
            gate = '幅度为零'
        if gate:
            gated.append({
                'param': param, 'label': LABEL[param], 'raw_delta': _round(raw, 2),
                'severity': severity or None, 'confidence': _round(conf, 2),
                'evidence': evidence, 'reason': reason, 'gate': gate,
            })
            continue
        norm = _normalize(param, raw)
        if norm == 0.0:
            gated.append({
                'param': param, 'label': LABEL[param], 'raw_delta': _round(raw, 2),
                'severity': severity, 'confidence': _round(conf, 2),
                'evidence': evidence, 'reason': reason, 'gate': '幅度低于最小步长',
            })
            continue
        if param == 'comp_weight_pp' and norm > 0 and inp is not None and eng is not None \
                and _comp_sample_poor(inp, eng):
            gated.append({
                'param': param, 'label': LABEL[param], 'raw_delta': _round(raw, 2),
                'severity': severity, 'confidence': _round(conf, 2),
                'evidence': evidence, 'reason': reason, 'gate': '可比证据不足却上调权重',
            })
            continue
        if param == 'comp_weight_pp' and norm > 0 and severity == 'critical':
            gated.append({
                'param': param, 'label': LABEL[param], 'raw_delta': _round(raw, 2),
                'severity': severity, 'confidence': _round(conf, 2),
                'evidence': evidence, 'reason': reason, 'gate': '可比权重上调不适用严重档',
            })
            continue
        if _direction_conflict(reason, norm):
            gated.append({
                'param': param, 'label': LABEL[param], 'raw_delta': _round(raw, 2),
                'severity': severity, 'confidence': _round(conf, 2),
                'evidence': evidence, 'reason': reason, 'gate': '建议方向与理由矛盾',
            })
            continue
        cap = SEVERITY_CAP[param][severity]
        capped = abs(norm) > cap
        if capped:
            norm = round((1.0 if norm > 0 else -1.0) * cap, 1)
        out.append({
            'param': param, 'label': LABEL[param],
            'raw_delta': _round(raw, 2), 'delta': norm, 'capped': capped,
            'severity': severity, 'expert_confidence': _round(conf, 2),
            'expert_evidence': evidence, 'reason': reason,
        })
    return out, gated


def _bounds(base, items):
    """按基线应用已通过的建议，校验上下限与 WACC>永续增速；越界项就地驳回。"""
    applied = {
        'comp_weight': base.get('comp_weight'),
        'wacc_pct': base.get('wacc_pct'),
        'tg_pct': base.get('tg_pct'),
    }
    for it in items:
        if not it.get('final_delta'):
            continue
        p, d = it['param'], it['final_delta']
        if p == 'comp_weight_pp':
            if applied['comp_weight'] is None:
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '缺少可比权重基线'
                continue
            applied['comp_weight'] = round(_clamp(applied['comp_weight'] + d, 0.0, 100.0), 1)
        elif p == 'wacc_pp':
            if applied['wacc_pct'] is None:
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '引擎未产出 WACC 基线'
                continue
            v = round(applied['wacc_pct'] + d, 2)
            if not (1.0 <= v <= 20.0):
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '调整后 WACC 超出 1%%~20%%'
                continue
            applied['wacc_pct'] = v
        elif p == 'tg_pp':
            if applied['tg_pct'] is None:
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '引擎未产出永续增速基线'
                continue
            v = round(applied['tg_pct'] + d, 2)
            if not (0.0 <= v <= 5.0):
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '调整后永续增速超出 0%%~5%%'
                continue
            applied['tg_pct'] = v
    if (applied['wacc_pct'] is not None and applied['tg_pct'] is not None
            and applied['wacc_pct'] <= applied['tg_pct']):
        for it in items:
            if it['param'] in ('wacc_pp', 'tg_pp') and it.get('final_delta'):
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '调整后 WACC 需高于永续增速'
        applied['wacc_pct'] = base.get('wacc_pct')
        applied['tg_pct'] = base.get('tg_pct')
    return applied


def _ask(messages, env, max_tokens, timeout):
    last = None
    for _ in range(2):
        try:
            return sentiment_llm._chat(messages, env, timeout=timeout, max_tokens=max_tokens)
        except Exception as exc:
            last = exc
            time.sleep(1.5)
    raise RuntimeError('LLM 调用失败: %s' % last)


def _main_prompt(ev, expert, proposals, base):
    return ('%s\n\n当前基线：可比权重 %s%%，WACC %s%%，永续增速 %s%%。\n\n'
            '专家原始输出：\n%s\n\n按步长与证据等级规则化后的建议：\n%s\n\n请逐条复核。' % (
                ev, _fmt(base.get('comp_weight'), 1), _fmt(base.get('wacc_pct')),
                _fmt(base.get('tg_pct')), json.dumps(expert, ensure_ascii=False),
                json.dumps([{k: p[k] for k in ('param', 'delta', 'severity', 'expert_confidence',
                                              'expert_evidence', 'reason')} for p in proposals],
                           ensure_ascii=False)))


def review(inp, eng, weights=None, timeout=75.0):
    """执行一次两级影子评审；不触碰引擎参数。返回落盘用记录（失败抛异常由调用方兜底）。"""
    t0 = time.time()
    env = sentiment_llm._env()
    if not env.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('影子评审未配置：需要在仓库外 ~/.dsh-valuation/sentiment-llm.env 提供 DEEPSEEK_API_KEY')
    base = baseline(eng, weights)
    ev = evidence_text(inp, eng, base)

    with _SLOTS:
        content, model = _ask([
            {'role': 'system', 'content': EXPERT_SYSTEM},
            {'role': 'user', 'content': ev},
        ], env, 800, timeout)
        expert = _json_of(content)
        proposals, gated = _proposals(expert, base, inp, eng)
        main = None
        main_error = None
        if proposals:
            try:
                mcontent, model = _ask([
                    {'role': 'system', 'content': MAIN_SYSTEM},
                    {'role': 'user', 'content': _main_prompt(ev, expert, proposals, base)},
                ], env, 800, timeout)
                main = _json_of(mcontent)
            except Exception as exc:
                main_error = str(exc)[:200]

    items = []
    main_by = {}
    for it in ((main or {}).get('items') or []):
        p = str(it.get('param') or '')
        if p in PARAMS and p not in main_by:
            main_by[p] = it
    for p in proposals:
        m = main_by.get(p['param'])
        if m is None:
            status, final, why = 'reject', 0.0, '主审未列示，建议作废'
        else:
            status = str(m.get('status') or 'reject')
            if status not in ('accept', 'clamp', 'reject'):
                status = 'reject'
            final = _normalize(p['param'], m.get('final_delta')) if status != 'reject' else 0.0
            why = _one_line(m.get('reason'), 60)
            if status != 'reject' and final:
                cap = SEVERITY_CAP[p['param']][p['severity']]
                if abs(final) > cap:
                    final = round((1.0 if final > 0 else -1.0) * cap, 1)
                    status = 'clamp'
                    why = (why + '；' if why else '') + '按证据等级夹断至 %gpp' % cap
                if _direction_conflict(why, final):
                    status, final, why = 'reject', 0.0, '主审方向与结论不一致'
            if status != 'reject' and final == 0.0:
                status, why = 'reject', why or '主审夹断为零'
        items.append({
            'param': p['param'], 'label': p['label'],
            'raw_delta': p['raw_delta'], 'delta': p['delta'],
            'severity': p['severity'], 'expert_confidence': p['expert_confidence'],
            'expert_evidence': p['expert_evidence'], 'capped': p['capped'],
            'status': status, 'final_delta': final, 'reason': why,
        })
    applied = _bounds(base, items)
    active = [it for it in items if it.get('final_delta')]
    if not items:
        decision = 'hold'
    elif not active:
        decision = 'reject'
    elif len(active) == len(items) and all(it['status'] == 'accept' for it in items):
        decision = 'accept'
    else:
        decision = 'partial'
    if main_error:
        decision = 'error'

    conf = _num((main or {}).get('confidence'))
    if conf is None:
        conf = _num(expert.get('confidence'))
    conf = _round(_clamp(conf, 0.0, 1.0) if conf is not None else 0.5, 2)
    one = _one_line((main or {}).get('one_line') or expert.get('one_line'), 60)
    if not items and gated:
        one = '建议未过证据门槛（%d 条），维持原参数' % len(gated)
    if main_error:
        one = (one + '；' if one else '') + '主审调用失败，建议全部作废'
    rec = {
        'code': _one_line((inp.get('meta') or {}).get('ticker'), 14),
        'name': _one_line((inp.get('meta') or {}).get('company'), 20),
        'industry': _one_line((inp.get('meta') or {}).get('industry'), 20),
        'generated': _now(),
        'elapsed_ms': int((time.time() - t0) * 1000),
        'model': model,
        'baseline': base,
        'evidence': ev,
        'expert': {
            'issues': [_one_line(x, 80) for x in (expert.get('issues') or [])][:5],
            'suggestions': [{
                'param': p['param'], 'raw_delta': p['raw_delta'], 'delta': p['delta'],
                'severity': p['severity'], 'confidence': p['expert_confidence'],
                'evidence': p['expert_evidence'], 'reason': p['reason'], 'capped': p['capped'],
            } for p in proposals],
            'gated': gated,
            'confidence': _num(expert.get('confidence')),
            'one_line': _one_line(expert.get('one_line'), 60),
        },
        'main': None if main is None else {
            'decision': _one_line(main.get('decision'), 16),
            'items': main.get('items') if isinstance(main.get('items'), list) else [],
            'confidence': _num(main.get('confidence')),
            'one_line': _one_line(main.get('one_line'), 60),
        },
        'main_error': main_error,
        'items': items,
        'applied': applied,
        'decision': decision,
        'confidence': conf,
        'one_line': one,
        'adoption': None,
    }
    return rec


def error_record(inp, eng, weights, exc):
    base = baseline(eng, weights)
    return {
        'code': _one_line((inp.get('meta') or {}).get('ticker'), 14),
        'name': _one_line((inp.get('meta') or {}).get('company'), 20),
        'industry': _one_line((inp.get('meta') or {}).get('industry'), 20),
        'generated': _now(),
        'elapsed_ms': 0,
        'model': None,
        'baseline': base,
        'evidence': '',
        'expert': None,
        'main': None,
        'main_error': None,
        'items': [],
        'applied': base,
        'decision': 'error',
        'confidence': None,
        'one_line': '',
        'adoption': None,
        'error': str(exc)[:300],
    }


def row_summary(rec):
    """写入 state.json 的逐券摘要（UI 直接渲染，完整记录在 <code>.shadow.json）。"""
    items = [{'param': it['param'], 'delta': it['final_delta'], 'status': it['status']}
             for it in rec.get('items') or []]
    return {
        'decision': rec.get('decision'),
        'confidence': rec.get('confidence'),
        'one_line': rec.get('one_line') or '',
        'adoption': rec.get('adoption', {}).get('action') if isinstance(rec.get('adoption'), dict) else None,
        'base': {
            'comp': (rec.get('baseline') or {}).get('comp_weight'),
            'wacc': (rec.get('baseline') or {}).get('wacc_pct'),
            'tg': (rec.get('baseline') or {}).get('tg_pct'),
        },
        'items': items,
        'n_issue': len((rec.get('expert') or {}).get('issues') or []),
        'n_gated': len((rec.get('expert') or {}).get('gated') or []),
        'error': rec.get('error') or rec.get('main_error'),
    }


def save_record(path, rec):
    p = Path(path)
    tmp = p.with_name(p.name + '.tmp.%d' % threading.get_ident())
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(p)


# ── 评估指标（只看过程质量，不看点位拟合） ──────────────────────────────────

def _median(xs):
    return round(statistics.median(xs), 2) if xs else None


def _iqr(xs):
    if not xs:
        return [None, None]
    s = sorted(xs)
    n = len(s)

    def q(p):
        if n == 1:
            return s[0]
        k = (n - 1) * p
        f = int(k)
        c = min(f + 1, n - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    return [round(q(0.25), 2), round(q(0.75), 2)]


def _param_map(job):
    out = {}
    for r in job.get('rows') or []:
        sh = r.get('shadow') or {}
        if sh.get('decision') in (None, 'error'):
            continue
        vals = {it.get('param'): _num(it.get('delta')) or 0.0 for it in sh.get('items') or []}
        code = r.get('secucode') or str(r.get('idx'))
        out[code] = {p: vals.get(p, 0.0) for p in PARAMS}
    return out


def _consensus(reviewed):
    """批级信号：同批同参同向占比，供 4~6 期后判断是否升级为批级变更单。"""
    out = {}
    for p in PARAMS:
        vals = []
        for r in reviewed:
            v = 0.0
            for it in (r.get('shadow') or {}).get('items') or []:
                if it.get('param') == p:
                    v = _num(it.get('delta')) or 0.0
            if v:
                vals.append(v)
        up = sum(1 for v in vals if v > 0)
        down = sum(1 for v in vals if v < 0)
        out[p] = {
            'nonzero': len(vals), 'up': up, 'down': down,
            'share': round(max(up, down) / len(vals), 2) if vals else None,
        }
    return out


def metrics(job, prev=None):
    rows = job.get('rows') or []
    ok = [r for r in rows if r.get('status') == 'ok']
    reviewed = [r for r in ok if (r.get('shadow') or {}).get('decision') in ('accept', 'partial', 'reject', 'hold')]
    failed = [r for r in ok if not r.get('shadow') or (r.get('shadow') or {}).get('decision') == 'error']
    dist = {k: 0 for k in ('accept', 'partial', 'reject', 'hold', 'error')}
    for r in ok:
        d = (r.get('shadow') or {}).get('decision')
        if d in dist:
            dist[d] += 1
    confs = [_num((r.get('shadow') or {}).get('confidence')) for r in reviewed]
    confs = [c for c in confs if c is not None]
    disp = {}
    for p in PARAMS:
        vals = []
        nonzero = 0
        for r in reviewed:
            v = 0.0
            for it in (r.get('shadow') or {}).get('items') or []:
                if it.get('param') == p:
                    v = _num(it.get('delta')) or 0.0
            vals.append(v)
            if v:
                nonzero += 1
        disp[p] = {'median': _median(vals), 'iqr': _iqr(vals), 'nonzero': nonzero, 'n': len(vals)}
    adopt = {'adopted': 0, 'rejected': 0, 'pending': 0}
    for r in reviewed:
        a = (r.get('shadow') or {}).get('adoption')
        if a in ('adopted', 'rejected'):
            adopt[a] += 1
        else:
            adopt['pending'] += 1
    decided = adopt['adopted'] + adopt['rejected']
    adopt['rate'] = round(adopt['adopted'] / decided, 3) if decided else None
    wow = None
    if prev:
        cur, old = _param_map(job), _param_map(prev)
        common = sorted(set(cur) & set(old))
        if common:
            wow = {'prev_job': prev.get('id'), 'prev_created': prev.get('created'), 'n': len(common)}
            for p in PARAMS:
                diffs = [abs(cur[c][p] - old[c][p]) for c in common]
                wow[p] = _median(diffs)
    return {
        'reviewed': len(reviewed),
        'errors': len(failed),
        'suggested': sum(1 for r in reviewed if any((it.get('delta') or 0) for it in (r.get('shadow') or {}).get('items') or [])),
        'accepted_items': sum(1 for r in reviewed for it in (r.get('shadow') or {}).get('items') or [] if it.get('delta')),
        'gated': sum(int((r.get('shadow') or {}).get('n_gated') or 0) for r in reviewed),
        'decision_dist': dist,
        'mean_confidence': round(sum(confs) / len(confs), 2) if confs else None,
        'dispersion': disp,
        'consensus': _consensus(reviewed),
        'adoption': adopt,
        'wow': wow,
        'generated': _now(),
    }


# ── sidecar 报告 ───────────────────────────────────────────────────────────

def _item_text(items, only_active=True):
    parts = []
    for it in items or []:
        d = _num(it.get('delta')) or 0.0
        if only_active and not d:
            continue
        if not d:
            continue
        if it.get('param') == 'comp_weight_pp':
            parts.append('可比 %+.1fpp' % d)
        elif it.get('param') == 'wacc_pp':
            parts.append('WACC %+.1fpp' % d)
        elif it.get('param') == 'tg_pp':
            parts.append('永续 %+.1fpp' % d)
    return ' · '.join(parts) if parts else '维持原参数'


def report_html(job):
    esc = html.escape
    m = job.get('shadow_metrics') or {}
    rows = job.get('rows') or []
    didx = lambda k: m.get('decision_dist', {}).get(k, 0)
    ad = m.get('adoption') or {}
    disp = m.get('dispersion') or {}
    wow = m.get('wow')
    body = []
    for r in rows:
        if r.get('status') != 'ok':
            continue
        sh = r.get('shadow') or {}
        d = sh.get('decision') or '—'
        tag = {'accept': 'ok', 'partial': 'warn', 'reject': '', 'hold': 'navy', 'error': 'warn'}.get(d, '')
        adoption = {'adopted': '已采纳', 'rejected': '已否决'}.get(sh.get('adoption'), '待定')
        conf = sh.get('confidence')
        body.append(
            '<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><span class="tag %s">%s</span></td>'
            '<td class="num">%s</td><td>%s</td><td>%s</td></tr>' % (
                r.get('idx', 0) + 1, esc(str(r.get('name') or '')), esc(str(r.get('secucode') or '')),
                esc(str(r.get('industry') or '—')), esc(_item_text(sh.get('items'))),
                tag, esc(DECISION_CN.get(d, d)), '—' if conf is None else ('%.2f' % conf),
                esc(adoption), esc(sh.get('one_line') or '')))
    compact = '<br>'.join(
        '%s：中位 %s / IQR %s~%s（%d/%d 只有建议）' % (
            LABEL[p], _fmt(disp.get(p, {}).get('median')), _fmt((disp.get(p, {}).get('iqr') or [None])[0]),
            _fmt((disp.get(p, {}).get('iqr') or [None, None])[1]),
            disp.get(p, {}).get('nonzero', 0), disp.get(p, {}).get('n', 0))
        for p in PARAMS)
    cons = m.get('consensus') or {}
    cons_line = '<br>'.join(
        ('%s：无有效建议' % LABEL[p]) if not (cons.get(p) or {}).get('nonzero') else
        ('%s：%d 条建议 · 上调 %d / 下调 %d（同向占比 %d%%）' % (
            LABEL[p], cons[p]['nonzero'], cons[p]['up'], cons[p]['down'],
            round((cons[p].get('share') or 0) * 100)))
        for p in PARAMS)
    wow_line = ('对照 %s（%s）：%d 只共同成分券，周环比中位绝对变动 可比 %spp / WACC %spp / 永续 %spp' % (
        esc(str(wow.get('prev_job'))), esc(str(wow.get('prev_created'))), wow.get('n', 0),
        _fmt(wow.get('comp_weight_pp')), _fmt(wow.get('wacc_pp')), _fmt(wow.get('tg_pp')))
        if wow else '暂无同指数影子任务，周环比稳定性待累积。')
    return ('<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            '<title>影子评审 sidecar · %(index)s · %(jobid)s</title></head><body><div class="wrap">'
            '<h1>%(index)s 影子评审记录（阶段一：可比质量专家 + 主审）</h1>'
            '<div class="meta">任务 %(jobid)s · 生成 %(ts)s · 引擎参数未改变，建议仅供人工复核</div>'
            '<div class="cards">'
            '<div class="card"><span>完成评审</span><b>%(reviewed)d</b><span>通过 %(acc)d · 部分 %(part)d · 驳回 %(rej)d · 维持 %(hold)d · 失败 %(err)d</span></div>'
            '<div class="card"><span>有建议 / 主审通过项</span><b>%(sug)d / %(items)d</b><span>%(gate)d 条未过证据门槛</span></div>'
            '<div class="card"><span>人工采纳率</span><b>%(rate)s</b><span>已采纳 %(adopt)d · 已否决 %(veto)d · 待定 %(pend)d</span></div>'
            '</div>'
            '<h2>过程指标（不看拟合点位）</h2>'
            '<table><tbody>'
            '<tr><th>建议离散度</th><td>%(disp)s</td></tr>'
            '<tr><th>批级信号</th><td>%(cons)s</td></tr>'
            '<tr><th>平均置信度</th><td>%(conf)s（%(nconf)d 只）</td></tr>'
            '<tr><th>周环比稳定性</th><td>%(wow)s</td></tr>'
            '</tbody></table>'
            '<h2>逐券评审</h2>'
            '<table><thead><tr><th>#</th><th>名称</th><th>代码</th><th>行业</th><th>建议</th>'
            '<th>主审</th><th>置信度</th><th>人工采纳</th><th>主审一句话</th></tr></thead>'
            '<tbody>%(rows)s</tbody></table>'
            '<div class="note">'
            '影子模式：专家提出变更 → 主审复核/夹断/驳回 → 记录留痕；引擎仍用原参数，拟合点位不受影响。<br>'
            '步长约束：可比权重 5~10pp；WACC / 永续增速 0.2pp 整数倍（上限 1.0pp / 0.6pp）；调整后 WACC 必须高于永续增速。<br>'
            '证据门槛：每条建议须声明严重度（medium/high/critical）、置信度≥0.65、证据引用具体数字；'
            '可比 critical 10pp / high 8pp / medium 5pp，WACC 0.4/1.0pp，永续 0.2/0.6pp；'
            '方向须与理由一致，未过门槛的建议只留痕。<br>'
            '评估口径只包括离散度、置信度校准、周环比参数稳定性与人工采纳率，不以是否更贴近指数收盘为评价标准。<br>'
            '本记录由跑批管线自动生成，仅作探索性研究参考，不构成投资建议。'
            '</div></div></body></html>') % {
        'index': esc(job.get('index') or ''), 'jobid': esc(job.get('id') or ''),
        'ts': esc(m.get('generated') or _now()),
        'reviewed': m.get('reviewed', 0),
        'acc': didx('accept'), 'part': didx('partial'), 'rej': didx('reject'),
        'hold': didx('hold'), 'err': didx('error'),
        'sug': m.get('suggested', 0), 'items': m.get('accepted_items', 0), 'gate': m.get('gated', 0),
        'rate': '—' if ad.get('rate') is None else ('%.0f%%' % (ad['rate'] * 100)),
        'adopt': ad.get('adopted', 0), 'veto': ad.get('rejected', 0), 'pend': ad.get('pending', 0),
        'disp': compact, 'cons': cons_line,
        'conf': _fmt(m.get('mean_confidence')), 'nconf': m.get('reviewed', 0),
        'wow': wow_line, 'rows': ''.join(body),
    }


# ── CLI（单券调试） ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print('usage: python3 shadow.py <input.json> <out.json> [--weights dcf,comp,sent] [--out rec.json]',
              file=sys.stderr)
        sys.exit(2)
    inp = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    eng = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    weights = None
    out_path = None
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == '--weights' and i + 1 < len(sys.argv):
            a, c, s = (float(x) for x in sys.argv[i + 1].split(','))
            weights = {'dcf': a, 'comp': c, 'sent': s}
            i += 2
        elif sys.argv[i] == '--out' and i + 1 < len(sys.argv):
            out_path = Path(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    rec = review(inp, eng, weights)
    if out_path:
        save_record(out_path, rec)
    print(json.dumps({'decision': rec['decision'], 'confidence': rec['confidence'],
                      'items': [{'param': it['param'], 'status': it['status'],
                                 'final_delta': it['final_delta']} for it in rec['items']],
                      'gated': len((rec.get('expert') or {}).get('gated') or []),
                      'one_line': rec['one_line']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()