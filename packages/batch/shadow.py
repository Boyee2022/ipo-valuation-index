# -*- coding: utf-8 -*-
"""多 agent 评审（三专家 + 主审）：shadow 留痕 / apply 回写。

- 三个专家各管一段证据：可比质量 → comp_weight_pp；折现参数 → wacc_pp / tg_pp；舆情 → sent_weight_pp。
  主审独立复核、夹断或驳回；专家不得跨域提参数。
- shadow：建议只留痕，引擎始终使用原参数；apply：主审通过项由调用方写回输入后重跑引擎。
- 证据门槛：须声明 severity、confidence≥门槛（默认 0.65，按批配置）、evidence 引用具体数字、reason 齐全、方向自洽；
  幅度按 severity 夹断（默认可比 medium/high/critical = 5/8/10pp、舆情 5/10pp、WACC 0.4/1.0pp、永续 0.2/0.6pp，按批配置覆写）。
- 金融类（银行/保险/券商）走 RIM/DDM 路由：权重不生效，WACC 参数面实为股权成本 Ke
  （写回 rim.cost_of_equity 与 ddm.cost_of_equity），永续增速写回 ddm.terminal_growth。
- 评估只看离散度、置信度校准、周环比稳定性与人工采纳率，不看拟合点位是否更贴近指数收盘。
- 落盘：runtime/jobs/<id>/<code>.shadow.json（逐券）+ shadow.html（任务级 sidecar）。
- 密钥：复用 sentiment_llm 的仓库外读取（DEEPSEEK_API_KEY），失败只标记该券评审错误，不影响跑批。
"""
import html
import json
import os
import re
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import agent_config
import sentiment_llm

PARAM_SPEC = {
    'comp_weight_pp': {
        'agent': 'comparable', 'label': '可比权重', 'step': 5.0, 'max': 10.0,
        'caps': {'medium': 5.0, 'high': 8.0, 'critical': 10.0},
    },
    'sent_weight_pp': {
        'agent': 'sentiment', 'label': '舆情权重', 'step': 5.0, 'max': 10.0,
        'caps': {'medium': 5.0, 'high': 10.0},
    },
    'wacc_pp': {
        'agent': 'financial', 'label': 'WACC', 'step': 0.2, 'max': 1.0,
        'caps': {'medium': 0.4, 'high': 1.0},
    },
    'tg_pp': {
        'agent': 'financial', 'label': '永续增速', 'step': 0.2, 'max': 0.6,
        'caps': {'medium': 0.2, 'high': 0.6},
    },
}
PARAMS = tuple(PARAM_SPEC)
STEPS = {p: (s['step'], s['max']) for p, s in PARAM_SPEC.items()}
MAX_ABS = {p: s['max'] for p, s in PARAM_SPEC.items()}
SEVERITY_CAP = {p: s['caps'] for p, s in PARAM_SPEC.items()}
LABEL = {p: s['label'] for p, s in PARAM_SPEC.items()}
AGENT_PARAMS = {
    'comparable': ('comp_weight_pp',),
    'financial': ('wacc_pp', 'tg_pp'),
    'sentiment': ('sent_weight_pp',),
}
AGENT_LABEL = {'comparable': '可比质量', 'financial': '折现参数', 'sentiment': '舆情'}
MIN_SUGGEST_CONF = 0.65
DECISION_CN = {'accept': '通过', 'partial': '部分通过', 'reject': '驳回', 'hold': '维持', 'error': '评审失败'}

_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get('VALUATION_SHADOW_CONCURRENCY') or 6)))
_SLOT_POOL = {}
_SLOT_LOCK = threading.Lock()


def _slots(n):
    """按本批配置的并发度取信号量；同一并发度复用同一个实例。"""
    n = max(1, min(12, int(n or 6)))
    with _SLOT_LOCK:
        sema = _SLOT_POOL.get(n)
        if sema is None:
            sema = _SLOT_POOL[n] = threading.BoundedSemaphore(n)
        return sema

_BASE_RULES = (
    '默认结论是维持原参数。只有证据指出具体、可量化的缺陷时才提建议；不要为了提而提。\n'
    '每条建议必须同时给出 severity、confidence、evidence、reason：\n'
    '- confidence<0.65 不要提；evidence 必须引用证据中的具体数字（家数/覆盖率/营收/市值/PE/beta/增长率等），不得空泛；\n'
    '- 幅度必须与证据强度匹配，不要机械取最小步长；severity 符合更高档条件时不得报低档。\n'
    '输出严格 JSON：{"issues":["最多5条，每条不超过40字"],'
    '"suggestions":[{"param":"...","delta":数字,"severity":"medium|high|critical",'
    '"confidence":0到1的小数,"evidence":"引用证据中的具体数字，不超过60字","reason":"不超过50字"}],'
    '"confidence":0到1的小数,"one_line":"不超过30字结论"}。只输出 JSON。'
)

AGENT_SYSTEM = {
    'comparable': (
        '你是 A 股指数成分券估值的「可比公司质量专家」。你只审查本次估值的可比证据链，'
        '只允许提出「可比权重 comp_weight_pp」一项参数建议；WACC、永续增速、舆情权重不在你的权限内。\n'
        '你看不到拟合点位，也不得以“更贴近指数收盘”为由提建议。\n'
        '审查维度：\n'
        '1) 样本量与筛池：纳入可比数、长名单规模、筛池覆盖率、因规模/业务模式被剔除的比例；\n'
        '2) 规模可比：目标公司营收/市值与基准中位数、规模倍数是否匹配；\n'
        '3) 业务与会计可比：业务模式、报告期、会计准则是否一致；\n'
        '4) 倍数质量：PE/PS 是否异常（负利润、极端值）、可比增长差异。\n'
        '严重度按数据三档判定，不得主观降级：\n'
        '- critical：纳入可比≤1 家、或筛池覆盖率<10%、或业务/会计明确不可比，幅度固定 10pp（仅下调）；\n'
        '- high：纳入可比 2 家、或覆盖率 10%~20%、或规模倍数≥5×、或个别可比倍数严重失真，幅度固定 8pp；\n'
        '- medium：覆盖率 20%~35%、或规模倍数 3~5×、或倍数轻度失真但仍可容忍，幅度固定 5pp；\n'
        '- 覆盖率≥35% 且规模倍数<3× 且无极端倍数/会计差异时，不得提 comp 建议。\n'
        '方向：可比证据不足时只能下调；若上调，必须在 evidence 中引用可比证据优于其他方法的数字'
        '（覆盖率≥35%、规模倍数<3×、倍数离散度低），且只能用 medium/high（≤8pp）。\n' + _BASE_RULES
    ),
    'financial': (
        '你是 A 股指数成分券估值的「折现参数专家」。你只审查折现与永续假设，'
        '只允许提出「WACC（wacc_pp）」与「永续增速（tg_pp）」两项建议；可比与舆情权重不在你的权限内。\n'
        '金融类公司走 RIM/DDM 路由时，WACC 无权重，wacc_pp 表示股权成本 Ke 的调整，tg_pp 写入 DDM 永续增速。\n'
        '审查维度：\n'
        '1) beta 水平与来源、CAPM 输入（rf/ERP/kd/税率/D/E）是否与证据一致；\n'
        '2) 生命周期阶段与置信度、3 年营收 CAGR、增长三角（可比中位增长/隐含永续增速）是否匹配；\n'
        '3) 现金流质量（OCF/净利、ROIC、应收、商誉、非经常性）是否支持当前折现率与永续假设。\n'
        '严重度档位：\n'
        '- wacc_pp：medium ±0.2~0.4pp；high ±0.6~1.0pp，且 high 仅限 beta 样本/来源明显失真、'
        '或 CAPM 结果与证据明确冲突；\n'
        '- tg_pp：medium ±0.2pp；high ±0.4~0.6pp，且 high 仅限生命周期、增长三角或可比增长明确矛盾。\n'
        '可比样本质量不能作为 WACC/永续增速的依据，每个参数必须有独立证据。证据不足返回空 suggestions。\n'
        + _BASE_RULES
    ),
    'sentiment': (
        '你是 A 股指数成分券估值的「舆情权重专家」。你只审查舆情证据链，'
        '只允许提出「舆情权重 sent_weight_pp」一项建议；可比权重、WACC、永续增速不在你的权限内。\n'
        '审查维度：\n'
        '1) 舆情口径（规则/LLM）、情绪标签与调整幅度、证据条数与关键词构成；\n'
        '2) 舆情调整幅度是否有证据支撑，情绪因子与新闻/股吧证据是否同向；\n'
        '3) 舆情法估值相对可比法/综合中枢的偏离幅度是否与证据强度匹配。\n'
        '严重度档位：\n'
        '- medium 5pp：情绪标签与量化调整轻度矛盾、或证据偏薄但仍可用；\n'
        '- high 10pp：证据明确指向舆情法被系统性高估/低估、或调整幅度与证据方向矛盾。\n'
        '默认维持；优先下调，上调必须引用情绪证据优于其他方法的数字。证据不足返回空 suggestions。\n'
        + _BASE_RULES
    ),
}

MAIN_SYSTEM = (
    '你是估值批跑的「主审」，独立复核三名专家（可比质量 / 折现参数 / 舆情）提出的参数变更建议。'
    '职责是防止过度反应：\n'
    '- 逐条核对五项门槛：severity 必须是 medium/high（可比另允许 critical，且 critical 只能下调可比权重）；'
    'confidence≥0.65；evidence 必须引用证据中的具体数字；'
    '幅度必须与 severity 表匹配（可比 critical 10pp / high 8pp / medium 5pp、舆情 high 10pp / medium 5pp、'
    'WACC 1.0/0.4pp、永续 0.6/0.2pp）；'
    'param 必须属于该专家的权限；任一项不满足即驳回；\n'
    '- 若 evidence 显示覆盖率<10% 或纳入可比≤1 家，但专家报 high/medium 且幅度低于 10pp；'
    '或显示覆盖率 10%~20%、规模倍数≥5×、纳入可比 2 家等高严重度条件，但专家报 medium 且幅度仅 5pp，'
    '视为严重度与证据不符，驳回；\n'
    '- 建议方向必须与证据和理由一致；理由写“下调”但 final_delta 为正（或反之）时驳回；'
    '可比证据不足却上调可比权重时驳回；跨域证据（如用可比样本质量改 WACC）不得采纳；\n'
    '- 每条建议必须由给定证据直接支持；证据弱、与证据矛盾或方向不明时驳回；\n'
    '- 可选择接受 accept、向下夹断 clamp 或驳回 reject；不得新增专家未提的参数；\n'
    '- 权重参数只能 5pp 整数倍且绝对值≤10pp；wacc_pp 只能 0.2pp 整数倍且绝对值≤1.0pp；'
    'tg_pp 只能 0.2pp 整数倍且绝对值≤0.6pp；调整后 WACC / Ke 必须高于永续增速；\n'
    '- shadow 模式的建议只留痕；apply 模式的通过项会写回输入并重跑引擎，宁可保守。\n'
    '输出严格 JSON：{"items":[{"param":"comp_weight_pp|sent_weight_pp|wacc_pp|tg_pp",'
    '"status":"accept|reject|clamp","final_delta":数字,"reason":"不超过40字"}],'
    '"decision":"accept|partial|reject","confidence":0到1的小数,"one_line":"不超过30字"}。'
    'items 必须覆盖专家的每条建议。只输出 JSON。'
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


def _fmt(x, digits=2, suffix=''):
    return '—' if x is None else ('%.*f%s' % (digits, x, suffix))


# ── 证据与基线 ──────────────────────────────────────────────────────────────

def _fractions(eng, weights=None):
    """引擎实际采用的方法权重（小数口径）；引擎未给时退回任务参数。"""
    raw = {}
    for key, aliases in (('dcf', ('dcf',)), ('comparable', ('comparable', 'comp')),
                         ('sentiment', ('sentiment', 'sent'))):
        for a in aliases:
            v = _num((eng.get('weights') or {}).get(a))
            if v is not None:
                raw[key] = v
                break
    if not raw and weights:
        for key, aliases in (('dcf', ('dcf',)), ('comparable', ('comp', 'comparable')),
                             ('sentiment', ('sent', 'sentiment'))):
            for a in aliases:
                v = _num(weights.get(a))
                if v is not None:
                    raw[key] = v
                    break
    total = sum(raw.values())
    if total <= 0:
        return None
    return {k: (v / 100.0 if total > 1.5 else v) for k, v in raw.items()}


def baseline(eng, weights=None, inp=None):
    """原参数基线：引擎实际采用的方法权重 + 折现率/永续增速（金融路由用 Ke）。"""
    eng = eng or {}
    inp = inp or {}
    asr = eng.get('assumptions_summary') or {}
    dcf = asr.get('dcf') or {}
    wraw = eng.get('weights') or {}
    frac = _fractions(eng, weights)
    routed = 'rim' in wraw or (bool(wraw) and 'dcf' not in wraw and 'sentiment' not in wraw)
    base = {
        'routed': routed,
        'rate_kind': 'ke' if routed else 'wacc',
        'rate_label': '股权成本 Ke' if routed else 'WACC',
        'comp_weight': None, 'sent_weight': None, 'dcf_weight': None,
        'wacc_pct': None, 'wacc_alt_pct': None, 'tg_pct': None,
        'wacc_source': '', 'tg_source': '',
        'weights': None if frac is None else {k: round(v, 4) for k, v in frac.items()},
    }
    if frac:
        base['comp_weight'] = _round(frac.get('comparable') * 100.0, 1) if 'comparable' in frac else None
        base['sent_weight'] = _round(frac.get('sentiment') * 100.0, 1) if 'sentiment' in frac else None
        base['dcf_weight'] = _round(frac.get('dcf') * 100.0, 1) if 'dcf' in frac else None
    if routed:
        rim = inp.get('rim') or {}
        ddm = inp.get('ddm') or {}
        rate = _pct(rim.get('cost_of_equity'))
        if rate is None:
            rate = _pct(ddm.get('cost_of_equity'))
        base['wacc_pct'] = rate
        base['wacc_alt_pct'] = _pct(dcf.get('wacc'))
        base['tg_pct'] = _pct(ddm.get('terminal_growth'))
        base['wacc_source'] = 'RIM CAPM Ke' if rim.get('cost_of_equity') is not None else _one_line(dcf.get('wacc_source'), 40)
        base['tg_source'] = 'DDM 永续' if ddm.get('terminal_growth') is not None else _one_line(dcf.get('tg_source'), 40)
    else:
        base['wacc_pct'] = _pct(dcf.get('wacc'))
        base['tg_pct'] = _pct(dcf.get('terminal_growth'))
        base['wacc_source'] = _one_line(dcf.get('wacc_source'), 40)
        base['tg_source'] = _one_line(dcf.get('tg_source'), 40)
    return base


def _result_lines(inp, eng, base):
    """当前估值结果与三法偏离（专家可见中枢，仍不可见指数拟合点位）。"""
    syn = eng.get('synthesis') or {}
    shares = (inp.get('financials') or {}).get('total_shares_after_issue')
    mid = _num(syn.get('weighted_mid'))
    lines = []
    if mid is not None:
        per = round(mid / shares, 2) if shares else None
        lines.append('引擎综合中枢 %s 亿 → 每股 %s 元（仅供参数审查，不可见指数拟合点位）' % (_fmt(mid), _fmt(per)))
    fp = syn.get('four_part') or {}
    vals = {}
    for k, name in (('part1_dcf', 'DCF'), ('part2_comparable_quality', '可比'),
                    ('part3_market_sentiment', '舆情')):
        v = fp.get(k) or {}
        if isinstance(v, dict) and _num(v.get('value')) is not None:
            vals[name] = _num(v.get('value'))
            lines.append('%s法 %s 亿（权重 %s%%）' % (name, _fmt(vals[name]),
                                                     _fmt(_pct(_num(v.get('weight'))), 0)))
    if len(vals) >= 2:
        nums = list(vals.values())
        mean = sum(nums) / len(nums)
        cv = statistics.pstdev(nums) / mean if mean > 0 else None
        lines.append('三法离散度 CV %s；可比 vs DCF %s；舆情 vs 可比 %s' % (
            _fmt(cv, 2),
            _fmt((vals['可比'] - vals['DCF']) / vals['DCF'] * 100.0, 1, '%')
            if '可比' in vals and 'DCF' in vals and vals['DCF'] else '—',
            _fmt((vals['舆情'] - vals['可比']) / vals['可比'] * 100.0, 1, '%')
            if '舆情' in vals and '可比' in vals and vals['可比'] else '—'))
    if base.get('routed'):
        b = (eng.get('scenarios') or {}).get('base') or {}
        alt = b.get('alternative_methods') or {}
        conv = b.get('comparable') or {}
        synth = conv.get('synthesis') or {}
        rim = alt.get('rim') or {}
        ddm = alt.get('ddm') or {}
        cv = _num(synth.get('base_value')) or _num(synth.get('value'))
        pe = (conv.get('pe') or {}).get('median')
        ps = (conv.get('ps') or {}).get('median')
        lines.append('路由法：RIM %s 亿（权重 %s%%，Ke %s%%）· DDM %s 亿（权重 %s%%，g %s%%）· 可比 %s 亿（权重 %s%%）' % (
            _fmt(_num(rim.get('value')), 1), _fmt(_pct(_num(rim.get('weight'))), 1),
            _fmt(base.get('wacc_pct')),
            _fmt(_num(ddm.get('value')), 1), _fmt(_pct(_num(ddm.get('weight'))), 1),
            _fmt(base.get('tg_pct')),
            _fmt(cv, 1), _fmt(_pct((eng.get('weights') or {}).get('comparable')), 1)))
        if pe is not None or ps is not None:
            lines.append('可比倍数中位：PE %s / PS %s' % (_fmt(_num(pe)), _fmt(_num(ps))))
    return lines


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
            _fmt(_pct((stages.get('s1_long_list') or {}).get('coverage') or ps_out.get('coverage')), 1, '%')))
    s2 = stages.get('s2_scale') or {}
    bench = s2.get('benchmark') or {}
    tgt = s2.get('target') or {}
    if bench or tgt:
        lines.append('规模基准：营收中位 %s 亿 / 市值中位 %s 亿；目标营收 %s 亿 / 市值 %s 亿；倍数 %s×' % (
            _fmt(_num(bench.get('revenue_median'))), _fmt(_num(bench.get('market_cap_median'))),
            _fmt(_num(tgt.get('revenue'))), _fmt(_num(tgt.get('market_cap'))),
            _fmt(_num(s2.get('multiple')), 1)))
    if ps_in.get('status') or ps_out.get('status'):
        lines.append('筛池状态：%s（depth=%s）' % (
            _one_line(ps_in.get('status') or ps_out.get('status'), 16),
            _one_line(ps_in.get('depth') or ps_out.get('depth'), 12)))
    return lines


def evidence_text(inp, eng, base, focus='all'):
    meta = inp.get('meta') or {}
    fin = inp.get('financials') or {}
    life = eng.get('lifecycle') or {}
    growth = eng.get('growth_triangulation') or {}
    wm = eng.get('wacc_model') or {}
    comps = inp.get('comparables') or []
    sent = inp.get('sentiment') or {}

    lines = ['公司：%s（%s），行业 %s，会计准则 %s' % (
        _one_line(meta.get('company'), 20), _one_line(meta.get('ticker'), 14),
        _one_line(meta.get('industry'), 20), _one_line(meta.get('accounting_standard'), 10))]
    if base.get('routed'):
        lines.append('参数面：金融类走 RIM/DDM 路由（方法权重不生效）；可调「股权成本 Ke %s%%（%s）」'
                     '与「DDM 永续增速 %s%%（%s）」' % (
                         _fmt(base.get('wacc_pct')), base.get('wacc_source') or '—',
                         _fmt(base.get('tg_pct')), base.get('tg_source') or '—'))
    lines.append('当前参数：可比权重 %s%% · 舆情权重 %s%% · %s %s%%（%s）· 永续增速 %s%%（%s）' % (
        _fmt(base.get('comp_weight'), 1), _fmt(base.get('sent_weight'), 1),
        base.get('rate_label'), _fmt(base.get('wacc_pct')), base.get('wacc_source') or '—',
        _fmt(base.get('tg_pct')), base.get('tg_source') or '—'))
    lines.extend(_result_lines(inp, eng, base))

    if focus in ('all', 'financial'):
        if wm:
            lines.append('CAPM：rf %s%% · ERP %s%% · beta %s（%s）· kd %s%% · 税率 %s%% · D/E %s → 权益成本 %s%%' % (
                _fmt(_pct(wm.get('rf'))), _fmt(_pct(wm.get('erp'))), _fmt(_num(wm.get('beta')), 2),
                _one_line(wm.get('beta_source'), 26), _fmt(_pct(wm.get('cost_of_debt')), 1),
                _fmt(_pct(wm.get('tax_rate')), 0), _fmt(_num(wm.get('d_e_ratio')), 2),
                _fmt(_pct(wm.get('cost_of_equity')))))
        lines.append('财务：TTM 营收 %s 亿 · 净利率 %s%% · ROE %s%% · 3年营收CAGR %s%% · 亏损 %s' % (
            _fmt(_num(fin.get('revenue_latest_ttm'))), _fmt(_pct(fin.get('net_margin')), 1),
            _fmt(_pct(fin.get('roe')), 1), _fmt(_pct((life.get('evidence') or {}).get('cagr_3y')), 1),
            '是' if fin.get('loss_making') else '否'))
        lines.append('质量：OCF/净利 %s · ROIC %s%% · 应收/营收 %s%% · 商誉/净资产 %s%% · 非经常性 %s%%' % (
            _fmt(_num(fin.get('ocf_to_net_profit')), 2), _fmt(_pct(fin.get('roic')), 1),
            _fmt(_pct(fin.get('receivables_to_revenue')), 1), _fmt(_pct(fin.get('goodwill_ratio')), 1),
            _fmt(_pct(fin.get('nonrecurring_ratio')), 1)))
        if life:
            lines.append('生命周期：%s（%s，置信 %s）；可比中位增长 %s%%；隐含永续增速 %s%%' % (
                _one_line(life.get('stage_label'), 16), _one_line(life.get('source'), 14),
                _fmt(_num(life.get('confidence')), 2), _fmt(_num(growth.get('comparable_median_growth')), 2),
                _fmt(_pct(growth.get('implied_terminal_growth')), 2)))

    if focus in ('all', 'comparable'):
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

    if focus in ('all', 'sentiment'):
        sf = _num((((eng.get('scenarios') or {}).get('base') or {}).get('params') or {}).get('sentiment_factor'))
        lines.append('舆情输入：口径 %s · 板块情绪 %s · 个股新闻 %s · 调整幅度 %s%% · 情绪因子 %s' % (
            _one_line(base.get('sentiment_mode') or inp.get('sentiment_mode') or '—', 10),
            _one_line(sent.get('sector_heat'), 10), _one_line(sent.get('company_news_sentiment'), 10),
            _fmt(_num(sent.get('sentiment_adjustment_pct')), 2), _fmt(sf, 3)))
        lines.append('舆情证据：%s' % _one_line(sent.get('evidence'), 240))
        fp = (eng.get('synthesis') or {}).get('four_part') or {}
        p2 = _num((fp.get('part2_comparable_quality') or {}).get('value'))
        p3 = _num((fp.get('part3_market_sentiment') or {}).get('value'))
        if p2 and p3:
            lines.append('舆情法 %s 亿 vs 可比法 %s 亿（偏离 %s）' % (
                _fmt(p3, 1), _fmt(p2, 1), _fmt((p3 - p2) / p2 * 100.0, 1, '%')))

    text = '\n'.join(lines)
    return text[:4200 if focus == 'all' else 3000]


# ── 建议生成、规则化与主审合并 ─────────────────────────────────────────────

def _normalize(param, delta, hi=None):
    """归到允许步长与上限；不足最小步长 → 0。权重类步长 5pp，比率类 0.2pp。"""
    spec = PARAM_SPEC.get(param)
    d = _num(delta) or 0.0
    if spec is None or d == 0:
        return 0.0
    limit = spec['max'] if hi is None else max(spec['step'], float(hi))
    if param.endswith('_weight_pp'):
        if abs(d) < spec['step']:
            return 0.0
        return round(_clamp(d, -limit, limit), 1)
    d = round(d / spec['step']) * spec['step']
    return round(_clamp(d, -limit, limit), 1)


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


def _gate(agent, s, base, inp, eng, min_conf=MIN_SUGGEST_CONF):
    """单项建议的证据门槛；返回 (param, raw, conf, severity, evidence, reason, gate)。"""
    param = str(s.get('param') or '')
    raw = _num(s.get('delta'))
    conf = _num(s.get('confidence'))
    severity = str(s.get('severity') or '').strip().lower()
    evidence = _one_line(s.get('evidence'), 80)
    reason = _one_line(s.get('reason'), 80)
    spec = PARAM_SPEC.get(param)
    gate = None
    if spec is None or param not in AGENT_PARAMS.get(agent, ()):
        gate = '参数不属于该专家'
    elif base.get('routed') and param in ('comp_weight_pp', 'sent_weight_pp'):
        gate = '金融路由下权重不生效'
    elif severity == 'critical' and param != 'comp_weight_pp':
        gate = '严重档仅用于可比权重'
    elif spec and severity not in spec['caps']:
        gate = '未声明有效严重度'
    elif conf is None or conf < min_conf:
        gate = '置信度低于 %.2f' % min_conf
    elif len(evidence) < 6 or not re.search(r'\d', evidence):
        gate = '证据未引用具体数字'
    elif len(reason) < 4:
        gate = '缺少理由'
    elif raw is None or raw == 0:
        gate = '幅度为零'
    elif param == 'comp_weight_pp' and raw > 0 and severity == 'critical':
        gate = '可比权重上调不适用严重档'
    elif param == 'comp_weight_pp' and raw > 0 and _comp_sample_poor(inp, eng):
        gate = '可比证据不足却上调权重'
    elif _direction_conflict(reason, raw):
        gate = '建议方向与理由矛盾'
    return param, raw, conf, severity, evidence, reason, gate


def _proposals(agent, expert, base, inp, eng, cfg):
    """规则化单个专家的建议并执行证据门槛；未过门槛的进入 gated 留痕，不送主审。"""
    out, gated = [], []
    seen = set()
    min_conf = agent_config.gate(cfg, agent)
    for s in (expert or {}).get('suggestions') or []:
        if not isinstance(s, dict):
            continue
        param, raw, conf, severity, evidence, reason, gate = _gate(agent, s, base, inp, eng, min_conf)
        if param in seen:
            continue
        seen.add(param)
        item = {
            'agent': agent, 'param': param, 'label': LABEL.get(param) or param,
            'raw_delta': _round(raw, 2), 'severity': severity or None,
            'confidence': _round(conf, 2), 'evidence': evidence, 'reason': reason,
        }
        if gate:
            gated.append(dict(item, gate=gate))
            continue
        caps = agent_config.caps_for(cfg, param)
        norm = _normalize(param, raw, max(caps.values()) if caps else None)
        if norm == 0.0:
            gated.append(dict(item, gate='幅度低于最小步长'))
            continue
        if _direction_conflict(reason, norm):
            gated.append(dict(item, gate='建议方向与理由矛盾'))
            continue
        cap = caps.get(severity, PARAM_SPEC[param]['caps'][severity])
        capped = abs(norm) > cap
        if capped:
            norm = round((1.0 if norm > 0 else -1.0) * cap, 1)
        out.append({
            'agent': agent, 'param': param, 'label': LABEL[param],
            'raw_delta': _round(raw, 2), 'delta': norm, 'capped': capped,
            'severity': severity, 'expert_confidence': _round(conf, 2),
            'expert_evidence': evidence, 'reason': reason,
        })
    return out, gated


def _rebalance_weights(w, deltas):
    """按 pp 增量调整目标方法权重，其余方法按原比例缩放，总和保持 100%。"""
    cur = {}
    for k in ('dcf', 'comparable', 'sentiment'):
        v = _num((w or {}).get(k))
        if v is None:
            return None
        cur[k] = v
    total = sum(cur.values())
    if total <= 0:
        return None
    if abs(total - 1.0) > 1e-6:
        cur = {k: v / total for k, v in cur.items()}
    targets = {}
    for param, key in (('comp_weight_pp', 'comparable'), ('sent_weight_pp', 'sentiment')):
        if param in deltas:
            targets[key] = cur[key] + deltas[param] / 100.0
    if not targets:
        return {k: round(v, 4) for k, v in cur.items()}
    rest_keys = [k for k in cur if k not in targets]
    rest = 1.0 - sum(targets.values())
    rest_old = sum(cur[k] for k in rest_keys)
    if rest < -1e-9 or rest_old <= 0 or any(v < -1e-9 for v in targets.values()):
        return None
    for k in rest_keys:
        cur[k] = rest * cur[k] / rest_old
    for k, v in targets.items():
        cur[k] = v
    out = {k: round(max(0.0, v), 4) for k, v in cur.items()}
    out['dcf'] = round(out['dcf'] + (1.0 - sum(out.values())), 4)
    if out['dcf'] < 0:
        return None
    return out


def _bounds(base, items):
    """按基线应用已通过的建议，校验权重可行域、上下限与 WACC>永续增速；越界项就地驳回。"""
    applied = {
        'comp_weight': base.get('comp_weight'),
        'sent_weight': base.get('sent_weight'),
        'wacc_pct': base.get('wacc_pct'),
        'tg_pct': base.get('tg_pct'),
        'rate_kind': base.get('rate_kind'),
        'weights': base.get('weights'),
    }
    wd = {}
    for it in items:
        if not it.get('final_delta'):
            continue
        p = it['param']
        if p == 'comp_weight_pp' and base.get('comp_weight') is None:
            it['status'], it['final_delta'] = 'reject', 0.0
            it['reason'] = '缺少可比权重基线'
        elif p == 'sent_weight_pp' and base.get('sent_weight') is None:
            it['status'], it['final_delta'] = 'reject', 0.0
            it['reason'] = '缺少舆情权重基线'
        elif p in ('comp_weight_pp', 'sent_weight_pp'):
            wd[p] = it['final_delta']
    if wd:
        w = _rebalance_weights(base.get('weights'), wd) if base.get('weights') else None
        if w is None:
            for it in items:
                if it['param'] in wd and it.get('final_delta'):
                    it['status'], it['final_delta'] = 'reject', 0.0
                    it['reason'] = '权重调整超出可行域'
        else:
            applied['weights'] = w
            applied['comp_weight'] = round(w['comparable'] * 100.0, 1)
            applied['sent_weight'] = round(w['sentiment'] * 100.0, 1)
    for it in items:
        if not it.get('final_delta'):
            continue
        p = it['param']
        if p == 'wacc_pp':
            if applied['wacc_pct'] is None:
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '引擎未产出折现率基线'
                continue
            v = round(applied['wacc_pct'] + it['final_delta'], 2)
            if not (1.0 <= v <= 20.0):
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '调整后折现率超出 1%%~20%%'
                continue
            applied['wacc_pct'] = v
        elif p == 'tg_pp':
            if applied['tg_pct'] is None:
                it['status'], it['final_delta'] = 'reject', 0.0
                it['reason'] = '引擎未产出永续增速基线'
                continue
            v = round(applied['tg_pct'] + it['final_delta'], 2)
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


def _ask(messages, env, max_tokens, timeout, slots=None):
    last = None
    sema = _slots(slots) if slots else _SLOTS
    for _ in range(2):
        try:
            with sema:
                return sentiment_llm._chat(messages, env, timeout=timeout, max_tokens=max_tokens)
        except Exception as exc:
            last = exc
            time.sleep(1.5)
    raise RuntimeError('LLM 调用失败: %s' % last)


def _run_expert(agent, env, ev, timeout, slots, rules):
    try:
        content, model = _ask([
            {'role': 'system', 'content': AGENT_SYSTEM[agent] + rules},
            {'role': 'user', 'content': ev},
        ], env, 700, timeout, slots)
        return {'agent': agent, 'ok': True, 'data': _json_of(content), 'model': model, 'error': None}
    except Exception as exc:
        return {'agent': agent, 'ok': False, 'data': None, 'model': None, 'error': str(exc)[:200]}


def _main_prompt(ev, by_agent, proposals, base):
    agent_txt = '\n'.join('- %s：%s（置信 %s）' % (x['label'], x['one_line'] or '—', _fmt(x['confidence']))
                          for x in by_agent if x.get('ok'))
    return ('%s\n\n当前基线：%s %s%%，可比权重 %s%%，舆情权重 %s%%，永续增速 %s%%。\n\n'
            '各专家结论：\n%s\n\n按步长与证据等级规则化后的待审建议：\n%s\n\n请逐条复核。' % (
                ev, base.get('rate_label'), _fmt(base.get('wacc_pct')),
                _fmt(base.get('comp_weight'), 1), _fmt(base.get('sent_weight'), 1),
                _fmt(base.get('tg_pct')), agent_txt,
                json.dumps([{
                    'agent': p['agent'], 'param': p['param'], 'delta': p['delta'],
                    'severity': p['severity'], 'expert_confidence': p['expert_confidence'],
                    'expert_evidence': p['expert_evidence'], 'reason': p['reason'],
                } for p in proposals], ensure_ascii=False)))


def review(inp, eng, weights=None, timeout=None, mode='shadow', cfg=None):
    """执行一次三专家 + 主审评审；不触碰引擎参数。cfg 为本批配置快照，缺省读当前文件。"""
    t0 = time.time()
    cfg = agent_config.normalize(cfg or agent_config.load())
    timeout = float(timeout or cfg.get('timeout_s') or 90.0)
    slots = int(cfg.get('concurrency') or 6)
    env = sentiment_llm._env()
    if not env.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('评审未配置：需要在仓库外 ~/.dsh-valuation/sentiment-llm.env 提供 DEEPSEEK_API_KEY')
    if cfg.get('model'):
        env = dict(env, DEEPSEEK_MODEL=cfg['model'])
    base = baseline(eng, weights, inp)
    prefs = inp.get('preferences') or {}
    base['sentiment_mode'] = prefs.get('sentiment_mode') or inp.get('sentiment_mode')
    if base.get('routed'):
        agents = ['financial'] if agent_config.enabled(cfg, 'financial') else []
    else:
        agents = [a for a in ('comparable', 'financial', 'sentiment') if agent_config.enabled(cfg, a)]
    if not agents:
        rec = error_record(inp, eng, weights, RuntimeError('所有专家已关闭'), mode, cfg)
        rec.update({'baseline': base, 'error': None, 'decision': 'hold',
                    'one_line': '所有专家已关闭，维持原参数', 'config': cfg})
        return rec
    ev_all = evidence_text(inp, eng, base, 'all')
    experts = {}
    with ThreadPoolExecutor(max_workers=len(agents)) as ex:
        futs = {ex.submit(_run_expert, a, env, evidence_text(inp, eng, base, a), timeout,
                          slots, agent_config.prompt_rules(cfg, a)): a for a in agents}
        for fut in as_completed(futs):
            r = fut.result()
            experts[r['agent']] = r

    proposals, gated, issues, by_agent = [], [], [], []
    models = []
    for a in agents:
        r = experts.get(a) or {'agent': a, 'ok': False, 'data': None, 'model': None, 'error': '未执行'}
        d = r.get('data') or {}
        pr, ga = ([], [])
        if r.get('ok'):
            pr, ga = _proposals(a, d, base, inp, eng, cfg)
            proposals.extend(pr)
            gated.extend(ga)
            for x in (d.get('issues') or [])[:5]:
                issues.append('%s：%s' % (AGENT_LABEL[a], _one_line(x, 40)))
        if r.get('model') and r['model'] not in models:
            models.append(r['model'])
        by_agent.append({
            'agent': a, 'label': AGENT_LABEL[a], 'ok': bool(r.get('ok')),
            'confidence': _num(d.get('confidence')), 'one_line': _one_line(d.get('one_line'), 60),
            'n_suggest': len(pr), 'n_gated': len(ga), 'error': r.get('error'),
        })
    ok_agents = [x for x in by_agent if x['ok']]
    expert_confs = [x['confidence'] for x in ok_agents if x['confidence'] is not None]
    expert_conf = round(sum(expert_confs) / len(expert_confs), 2) if expert_confs else None
    expert_one = _one_line('；'.join('%s：%s' % (x['label'], x['one_line'])
                                    for x in ok_agents if x['one_line']), 120)

    main = None
    main_error = None
    main_enabled = agent_config.enabled(cfg, 'main')
    if proposals and main_enabled:
        try:
            mcontent, model = _ask([
                {'role': 'system', 'content': MAIN_SYSTEM + agent_config.prompt_rules(cfg, 'main')},
                {'role': 'user', 'content': _main_prompt(ev_all, by_agent, proposals, base)},
            ], env, 800, timeout, slots)
            main = _json_of(mcontent)
            if model and model not in models:
                models.append(model)
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
            status, final, why = 'reject', 0.0, ('主审未启用，建议仅留痕' if not main_enabled else '主审未列示，建议作废')
        else:
            status = str(m.get('status') or 'reject')
            if status not in ('accept', 'clamp', 'reject'):
                status = 'reject'
            final = _normalize(p['param'], m.get('final_delta')) if status != 'reject' else 0.0
            why = _one_line(m.get('reason'), 60)
            if status != 'reject' and final:
                cap = agent_config.caps_for(cfg, p['param']).get(p['severity'], SEVERITY_CAP[p['param']][p['severity']])
                if abs(final) > cap:
                    final = round((1.0 if final > 0 else -1.0) * cap, 1)
                    status = 'clamp'
                    why = (why + '；' if why else '') + '按证据等级夹断至 %gpp' % cap
                if _direction_conflict(why, final):
                    status, final, why = 'reject', 0.0, '主审方向与结论不一致'
            if status != 'reject' and final == 0.0:
                status, why = 'reject', why or '主审夹断为零'
        items.append({
            'agent': p['agent'], 'param': p['param'], 'label': p['label'],
            'raw_delta': p['raw_delta'], 'delta': p['delta'], 'severity': p['severity'],
            'expert_confidence': p['expert_confidence'], 'expert_evidence': p['expert_evidence'],
            'capped': p['capped'], 'status': status, 'final_delta': final, 'reason': why,
        })
    applied = _bounds(base, items)
    active = [it for it in items if it.get('final_delta')]
    if not ok_agents:
        decision = 'error'
    elif not main_enabled:
        decision = 'hold'
    elif not items:
        decision = 'hold'
    elif not active:
        decision = 'reject'
    elif len(active) == len(items) and all(it['status'] == 'accept' for it in items):
        decision = 'accept'
    else:
        decision = 'partial'
    if main_error and proposals:
        decision = 'error'

    conf = _num((main or {}).get('confidence'))
    if conf is None:
        conf = expert_conf
    conf = _round(_clamp(conf, 0.0, 1.0) if conf is not None else 0.5, 2)
    one = _one_line((main or {}).get('one_line') or expert_one, 80)
    if not items and gated:
        one = '建议未过证据门槛（%d 条），维持原参数' % len(gated)
    if not ok_agents:
        one = '专家均调用失败'
    elif not main_enabled and proposals:
        one = '主审已关闭（%d 条建议仅留痕）' % len(proposals)
    if main_error and proposals:
        one = (one + '；' if one else '') + '主审调用失败，建议全部作废'
    rec = {
        'code': _one_line((inp.get('meta') or {}).get('ticker'), 14),
        'name': _one_line((inp.get('meta') or {}).get('company'), 20),
        'industry': _one_line((inp.get('meta') or {}).get('industry'), 20),
        'generated': _now(),
        'elapsed_ms': int((time.time() - t0) * 1000),
        'model': ','.join(models) if models else None,
        'agent_mode': mode,
        'config': cfg,
        'baseline': base,
        'evidence': ev_all,
        'agents': by_agent,
        'expert': {
            'issues': issues[:8],
            'suggestions': [{
                'agent': p['agent'], 'param': p['param'], 'raw_delta': p['raw_delta'],
                'delta': p['delta'], 'severity': p['severity'],
                'confidence': p['expert_confidence'], 'evidence': p['expert_evidence'],
                'reason': p['reason'], 'capped': p['capped'],
            } for p in proposals],
            'gated': gated,
            'confidence': expert_conf,
            'one_line': expert_one,
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
        'apply': None,
        'decision': decision,
        'confidence': conf,
        'one_line': one,
        'adoption': None,
    }
    return rec


_EVIDENCE_GUIDE = {
    'comparable': [
        '公司行：公司 / 代码 / 行业 / 会计准则',
        '当前参数：可比权重、舆情权重、折现率与永续增速（含来源）',
        '估值结果：综合中枢与三法数值、权重、离散度与两两偏离（不含指数拟合点位）',
        '纳入可比：逐家 PE / PS / 营收 / 市值 / 增长 / 准则 / 报告期（最多 8 家）',
        '筛池：长名单规模、中位营收与市值、规模倍数、剔除原因分布、覆盖率与筛池状态',
    ],
    'financial': [
        '公司行：公司 / 代码 / 行业 / 会计准则',
        '当前参数：同上（金融类 RIM/DDM 路由时标注股权成本 Ke 与 DDM 永续增速）',
        '估值结果：综合中枢、三法或路由法数值与权重、离散度（不含指数拟合点位）',
        'CAPM：rf / ERP / beta 与来源 / kd / 税率 / D/E → 权益成本',
        '财务：TTM 营收、净利率、ROE、3 年营收 CAGR、是否亏损',
        '质量：OCF/净利、ROIC、应收/营收、商誉/净资产、非经常性占比',
        '生命周期：阶段与置信度、可比中位增长、隐含永续增速',
    ],
    'sentiment': [
        '公司行：公司 / 代码 / 行业 / 会计准则',
        '当前参数与估值结果：同上（不含指数拟合点位）',
        '舆情输入：口径（规则/LLM）、板块情绪、个股新闻、调整幅度、情绪因子',
        '舆情证据：新闻与股吧语料摘要',
        '舆情法 vs 可比法偏离',
    ],
    'main': [
        '三名专家可见证据的合并完整版（公司、参数、估值结果、财务、可比、筛池、舆情）',
        '当前基线：折现率 / Ke、可比权重、舆情权重、永续增速',
        '各专家结论：逐位专家的一句话结论与置信度',
        '待审建议：每条 agent / param / delta / severity / 专家置信度 / 专家证据 / 理由（JSON）',
    ],
}

_CODE = {'comparable': 'CMP', 'financial': 'DCF', 'sentiment': 'SNT', 'main': 'REV'}


def prompt_preview(cfg=None):
    """只读预览：四个角色实际使用的 system 提示词（含本批配置行）与输入证据结构。"""
    cfg = agent_config.normalize(cfg or agent_config.load())
    roles = {}
    for agent in ('comparable', 'financial', 'sentiment', 'main'):
        params = []
        for param in AGENT_PARAMS.get(agent, ()):
            caps = agent_config.caps_for(cfg, param)
            params.append({
                'key': param,
                'label': LABEL[param],
                'caps': {s: caps.get(s) for s in agent_config.PARAM_SEVERITIES.get(param, ())},
            })
        if agent == 'main':
            params = [{'key': p, 'label': LABEL[p],
                       'caps': {s: agent_config.caps_for(cfg, p).get(s)
                                for s in agent_config.PARAM_SEVERITIES[p]}} for p in PARAMS]
        roles[agent] = {
            'code': _CODE[agent],
            'label': AGENT_LABEL.get(agent, '主审'),
            'enabled': agent_config.enabled(cfg, agent),
            'gate': None if agent == 'main' else agent_config.gate(cfg, agent),
            'params': params,
            'system': (MAIN_SYSTEM if agent == 'main' else AGENT_SYSTEM[agent])
                      + agent_config.prompt_rules(cfg, agent),
            'evidence': list(_EVIDENCE_GUIDE[agent]),
        }
    return {'version': int(cfg.get('version') or 0), 'model': cfg.get('model') or '',
            'generated': _now(), 'roles': roles}


def apply_to_input(inp, eng, rec):
    """把主审通过的增量写回输入 JSON（apply 模式）；返回 (new_inp, changes, skipped)，不改原对象。"""
    base = rec.get('baseline') or {}
    applied = rec.get('applied') or {}
    active = [it for it in rec.get('items') or [] if _num(it.get('final_delta'))]
    if not active:
        return inp, [], []
    new = json.loads(json.dumps(inp, ensure_ascii=False))
    changes, skipped = [], []
    if base.get('routed'):
        rim = new.setdefault('rim', {})
        ddm = new.setdefault('ddm', {})
        for it in active:
            d = _num(it.get('final_delta')) or 0.0
            if it['param'] == 'wacc_pp':
                old = _num(_pct(rim.get('cost_of_equity')))
                if old is None:
                    skipped.append('缺少 Ke 基线，跳过 %s' % LABEL[it['param']])
                    continue
                new_v = round(old + d, 2)
                for obj in (rim, ddm):
                    obj['cost_of_equity'] = round(new_v / 100.0, 6)
                changes.append({'param': 'wacc_pp', 'label': '股权成本 Ke',
                                'from': old, 'to': new_v, 'delta': round(d, 1)})
            elif it['param'] == 'tg_pp':
                old = _num(_pct(ddm.get('terminal_growth')))
                if old is None:
                    skipped.append('缺少 DDM 永续增速基线，跳过 %s' % LABEL[it['param']])
                    continue
                new_v = round(old + d, 2)
                ddm['terminal_growth'] = round(new_v / 100.0, 6)
                changes.append({'param': 'tg_pp', 'label': '永续增速',
                                'from': old, 'to': new_v, 'delta': round(d, 1)})
            else:
                skipped.append('%s 在金融路由下不生效' % LABEL.get(it['param'], it['param']))
    else:
        w = applied.get('weights')
        if w and any(it['param'] in ('comp_weight_pp', 'sent_weight_pp') for it in active):
            old = base.get('weights') or {}
            prefs = new.setdefault('preferences', {})
            prefs['weights'] = {
                'dcf': round(_num(w.get('dcf')) or 0.0, 4),
                'comparable': round(_num(w.get('comparable')) or 0.0, 4),
                'sentiment': round(_num(w.get('sentiment')) or 0.0, 4),
            }
            changes.append({
                'param': 'weights', 'label': '方法权重',
                'from': '%s/%s/%s' % (_fmt(_pct(_num(old.get('dcf'))), 1),
                                      _fmt(_pct(_num(old.get('comparable'))), 1),
                                      _fmt(_pct(_num(old.get('sentiment'))), 1)),
                'to': '%s/%s/%s' % (_fmt(_pct(prefs['weights']['dcf']), 1),
                                    _fmt(_pct(prefs['weights']['comparable']), 1),
                                    _fmt(_pct(prefs['weights']['sentiment']), 1)),
                'delta': None,
            })
        fin = new.setdefault('financials', {})
        for it in active:
            d = _num(it.get('final_delta')) or 0.0
            if it['param'] == 'wacc_pp':
                cur = _num(applied.get('wacc_pct'))
                if cur is None:
                    skipped.append('缺少 WACC 基线，跳过 %s' % LABEL[it['param']])
                    continue
                fin['wacc'] = round(cur / 100.0, 6)
                changes.append({'param': 'wacc_pp', 'label': 'WACC',
                                'from': round(cur - d, 2), 'to': cur, 'delta': round(d, 1)})
            elif it['param'] == 'tg_pp':
                cur = _num(applied.get('tg_pct'))
                if cur is None:
                    skipped.append('缺少永续增速基线，跳过 %s' % LABEL[it['param']])
                    continue
                fin['terminal_growth'] = round(cur / 100.0, 6)
                changes.append({'param': 'tg_pp', 'label': '永续增速',
                                'from': round(cur - d, 2), 'to': cur, 'delta': round(d, 1)})
            elif it['param'] not in ('comp_weight_pp', 'sent_weight_pp'):
                skipped.append('%s 无法回写' % LABEL.get(it['param'], it['param']))
    if not changes:
        return inp, [], skipped
    ds = new.get('data_sources')
    note = {
        'source': '多 agent 评审回写（apply）',
        'items': ['%s %s→%s' % (c['label'], c['from'], c['to']) for c in changes],
        'as_of': _now()[:10],
    }
    if isinstance(ds, list):
        ds.append(note)
    elif isinstance(ds, str) and ds:
        new['data_sources'] = [{'source': ds}, note]
    else:
        new['data_sources'] = [note]
    prefs = new.setdefault('preferences', {})
    if isinstance(prefs, dict):
        prefs['agent_adjustments'] = {
            'mode': 'apply',
            'at': _now(),
            'items': [{'param': it['param'], 'delta': it['final_delta']} for it in active],
            'changes': changes,
        }
    return new, changes, skipped


def error_record(inp, eng, weights, exc, mode='shadow', cfg=None):
    base = baseline(eng, weights, inp)
    return {
        'code': _one_line((inp.get('meta') or {}).get('ticker'), 14),
        'name': _one_line((inp.get('meta') or {}).get('company'), 20),
        'industry': _one_line((inp.get('meta') or {}).get('industry'), 20),
        'generated': _now(),
        'elapsed_ms': 0,
        'model': None,
        'agent_mode': mode,
        'config': cfg,
        'baseline': base,
        'evidence': '',
        'agents': [],
        'expert': None,
        'main': None,
        'main_error': None,
        'items': [],
        'applied': base,
        'apply': None,
        'decision': 'error',
        'confidence': None,
        'one_line': '',
        'adoption': None,
        'error': str(exc)[:300],
    }


def row_summary(rec):
    """写入 state.json 的逐券摘要（UI 直接渲染，完整记录在 <code>.shadow.json）。"""
    items = [{'param': it['param'], 'delta': it['final_delta'], 'status': it['status'],
              'agent': it.get('agent')}
             for it in rec.get('items') or []]
    ap = rec.get('apply') or {}
    return {
        'mode': rec.get('agent_mode') or 'shadow',
        'decision': rec.get('decision'),
        'confidence': rec.get('confidence'),
        'one_line': rec.get('one_line') or '',
        'adoption': rec.get('adoption', {}).get('action') if isinstance(rec.get('adoption'), dict) else None,
        'base': {
            'comp': (rec.get('baseline') or {}).get('comp_weight'),
            'sent': (rec.get('baseline') or {}).get('sent_weight'),
            'wacc': (rec.get('baseline') or {}).get('wacc_pct'),
            'tg': (rec.get('baseline') or {}).get('tg_pct'),
            'rate_kind': (rec.get('baseline') or {}).get('rate_kind'),
        },
        'items': items,
        'agents': [{
            'agent': a.get('agent'), 'label': a.get('label'), 'ok': a.get('ok'),
            'confidence': a.get('confidence'), 'one_line': a.get('one_line'), 'error': a.get('error'),
        } for a in rec.get('agents') or []],
        'n_issue': len((rec.get('expert') or {}).get('issues') or []),
        'n_gated': len((rec.get('expert') or {}).get('gated') or []),
        'apply': None if not ap else {
            'mode': ap.get('mode'), 'changed': bool(ap.get('changed')),
            'changes': ap.get('changes') or [], 'skipped': ap.get('skipped') or [],
            'baseline_mid': ap.get('baseline_mid'), 'final_mid': ap.get('final_mid'),
            'error': ap.get('error'),
        },
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
    apply_m = None
    if job.get('agent_mode') == 'apply':
        changed = [r for r in reviewed if ((r.get('shadow') or {}).get('apply') or {}).get('changed')]
        errors = [r for r in reviewed if ((r.get('shadow') or {}).get('apply') or {}).get('error')]
        moves = []
        for r in changed:
            ap = (r.get('shadow') or {}).get('apply') or {}
            b, f = _num(ap.get('baseline_mid')), _num(ap.get('final_mid'))
            if b is not None and f is not None:
                moves.append(abs(f - b))
        apply_m = {
            'changed': len(changed),
            'errors': len(errors),
            'moved': sum(1 for m in moves if m > 1e-9),
            'median_move': _median(moves),
        }
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
        'apply': apply_m,
        'mode': job.get('agent_mode') or 'shadow',
        'wow': wow,
        'generated': _now(),
    }


# ── sidecar 报告 ───────────────────────────────────────────────────────────

def _item_text(items, rate_label='WACC', only_active=True):
    parts = []
    for it in items or []:
        d = _num(it.get('delta')) or 0.0
        if only_active and not d:
            continue
        if not d:
            continue
        lab = {'comp_weight_pp': '可比', 'sent_weight_pp': '舆情', 'wacc_pp': rate_label or 'WACC',
               'tg_pp': '永续'}.get(it.get('param'), it.get('param'))
        parts.append('%s %+.1fpp' % (lab, d))
    return ' · '.join(parts) if parts else '维持原参数'


def _apply_text(ap):
    if not ap or ap.get('mode') != 'apply':
        return '—'
    if ap.get('error'):
        return '回写失败，沿用基线'
    if not ap.get('changed'):
        return '无通过项'
    return '%s → %s（%d 项）' % (_fmt(_num(ap.get('baseline_mid')), 1),
                                 _fmt(_num(ap.get('final_mid')), 1), len(ap.get('changes') or []))


def report_html(job):
    esc = html.escape
    m = job.get('shadow_metrics') or {}
    rows = job.get('rows') or []
    mode = job.get('agent_mode') or m.get('mode') or 'shadow'
    mode_cn = '生效更新（apply）' if mode == 'apply' else '影子留痕（shadow）'
    didx = lambda k: m.get('decision_dist', {}).get(k, 0)
    ad = m.get('adoption') or {}
    disp = m.get('dispersion') or {}
    wow = m.get('wow')
    apply_m = m.get('apply') or {}
    body = []
    for r in rows:
        if r.get('status') != 'ok':
            continue
        sh = r.get('shadow') or {}
        d = sh.get('decision') or '—'
        tag = {'accept': 'ok', 'partial': 'warn', 'reject': '', 'hold': 'navy', 'error': 'warn'}.get(d, '')
        adoption = {'adopted': '已采纳', 'rejected': '已否决'}.get(sh.get('adoption'), '待定')
        conf = sh.get('confidence')
        agents = '、'.join(a.get('label') or a.get('agent') or '' for a in sh.get('agents') or [] if a.get('ok'))
        rl = 'Ke' if (sh.get('base') or {}).get('rate_kind') == 'ke' else 'WACC'
        body.append(
            '<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><span class="tag %s">%s</span></td>'
            '<td class="num">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                r.get('idx', 0) + 1, esc(str(r.get('name') or '')), esc(str(r.get('secucode') or '')),
                esc(str(r.get('industry') or '—')), esc(agents or '—'),
                esc(_item_text(sh.get('items'), rl)),
                tag, esc(DECISION_CN.get(d, d)), '—' if conf is None else ('%.2f' % conf),
                esc(_apply_text(sh.get('apply'))), esc(adoption), esc(sh.get('one_line') or '')))
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
    wow_line = ('对照 %s（%s）：%d 只共同成分券，周环比中位绝对变动 可比 %spp / 舆情 %spp / WACC %spp / 永续 %spp' % (
        esc(str(wow.get('prev_job'))), esc(str(wow.get('prev_created'))), wow.get('n', 0),
        _fmt(wow.get('comp_weight_pp')), _fmt(wow.get('sent_weight_pp')),
        _fmt(wow.get('wacc_pp')), _fmt(wow.get('tg_pp')))
        if wow else '暂无同指数评审任务，周环比稳定性待累积。')
    apply_card = ''
    if mode == 'apply':
        apply_card = ('<div class="card"><span>apply 回写</span><b>%(chg)d / %(reviewed)d</b>'
                      '<span>回写失败 %(aerr)d · 中枢变动中位 %(move)s 亿</span></div>' % {
                          'chg': apply_m.get('changed', 0), 'reviewed': m.get('reviewed', 0),
                          'aerr': apply_m.get('errors', 0), 'move': _fmt(apply_m.get('median_move'), 1)})
    note = (
        'apply 模式：专家提出变更 → 主审复核/夹断/驳回 → 通过项写回输入并重跑引擎；'
        '基线输入与输出保留为 *.baseline.json，回写或重跑失败自动回滚。<br>'
        if mode == 'apply' else
        'shadow 模式：专家提出变更 → 主审复核/夹断/驳回 → 记录留痕；引擎仍用原参数，拟合点位不受影响。<br>')
    return ('<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            '<title>多 agent 评审 sidecar · %(index)s · %(jobid)s</title></head><body><div class="wrap">'
            '<h1>%(index)s 多 agent 评审记录（%(mode)s）</h1>'
            '<div class="meta">任务 %(jobid)s · 生成 %(ts)s · 三专家：可比质量 / 折现参数 / 舆情；主审独立复核</div>'
            '<div class="cards">'
            '<div class="card"><span>完成评审</span><b>%(reviewed)d</b><span>通过 %(acc)d · 部分 %(part)d · 驳回 %(rej)d · 维持 %(hold)d · 失败 %(err)d</span></div>'
            '<div class="card"><span>有建议 / 主审通过项</span><b>%(sug)d / %(items)d</b><span>%(gate)d 条未过证据门槛</span></div>'
            '<div class="card"><span>人工采纳率</span><b>%(rate)s</b><span>已采纳 %(adopt)d · 已否决 %(veto)d · 待定 %(pend)d</span></div>'
            '%(apply_card)s'
            '</div>'
            '<h2>过程指标（不看拟合点位）</h2>'
            '<table><tbody>'
            '<tr><th>建议离散度</th><td>%(disp)s</td></tr>'
            '<tr><th>批级信号</th><td>%(cons)s</td></tr>'
            '<tr><th>平均置信度</th><td>%(conf)s（%(nconf)d 只）</td></tr>'
            '<tr><th>周环比稳定性</th><td>%(wow)s</td></tr>'
            '</tbody></table>'
            '<h2>逐券评审</h2>'
            '<table><thead><tr><th>#</th><th>名称</th><th>代码</th><th>行业</th><th>专家</th><th>建议</th>'
            '<th>主审</th><th>置信度</th><th>回写</th><th>人工采纳</th><th>主审一句话</th></tr></thead>'
            '<tbody>%(rows)s</tbody></table>'
            '<div class="note">'
            '%(note)s'
            '步长约束：可比 / 舆情权重 5pp 整数倍（|Δ|≤10pp）；WACC / 永续增速 0.2pp 整数倍（上限 1.0pp / 0.6pp）；'
            '调整后 WACC 必须高于永续增速。<br>'
            '证据门槛：severity、置信度≥0.65、证据引用具体数字、方向自洽；'
            '可比 10/8/5pp、舆情 10/5pp、WACC 1.0/0.4pp、永续 0.6/0.2pp；未过门槛的建议只留痕。<br>'
            '评估口径只包括离散度、置信度校准、周环比参数稳定性与人工采纳率，不以是否更贴近指数收盘为评价标准。<br>'
            '本记录由跑批管线自动生成，仅作探索性研究参考，不构成投资建议。'
            '</div></div></body></html>') % {
        'index': esc(job.get('index') or ''), 'jobid': esc(job.get('id') or ''),
        'mode': mode_cn,
        'ts': esc(m.get('generated') or _now()),
        'reviewed': m.get('reviewed', 0),
        'acc': didx('accept'), 'part': didx('partial'), 'rej': didx('reject'),
        'hold': didx('hold'), 'err': didx('error'),
        'sug': m.get('suggested', 0), 'items': m.get('accepted_items', 0), 'gate': m.get('gated', 0),
        'rate': '—' if ad.get('rate') is None else ('%.0f%%' % (ad['rate'] * 100)),
        'adopt': ad.get('adopted', 0), 'veto': ad.get('rejected', 0), 'pend': ad.get('pending', 0),
        'apply_card': apply_card,
        'disp': compact, 'cons': cons_line,
        'conf': _fmt(m.get('mean_confidence')), 'nconf': m.get('reviewed', 0),
        'wow': wow_line, 'rows': ''.join(body), 'note': note,
    }


# ── CLI（单券调试） ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print('usage: python3 shadow.py <input.json> <out.json> [--weights dcf,comp,sent] [--out rec.json] [--apply]',
              file=sys.stderr)
        sys.exit(2)
    inp = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    eng = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    weights = None
    out_path = None
    apply = False
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == '--weights' and i + 1 < len(sys.argv):
            a, c, s = (float(x) for x in sys.argv[i + 1].split(','))
            weights = {'dcf': a, 'comp': c, 'sent': s}
            i += 2
        elif sys.argv[i] == '--out' and i + 1 < len(sys.argv):
            out_path = Path(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--apply':
            apply = True
            i += 1
        else:
            i += 1
    rec = review(inp, eng, weights, mode='apply' if apply else 'shadow')
    result = {'decision': rec['decision'], 'confidence': rec['confidence'],
              'items': [{'param': it['param'], 'agent': it.get('agent'), 'status': it['status'],
                         'final_delta': it['final_delta']} for it in rec['items']],
              'gated': len((rec.get('expert') or {}).get('gated') or []),
              'one_line': rec['one_line']}
    if apply:
        new_inp, changes, skipped = apply_to_input(inp, eng, rec)
        rec['apply'] = {'mode': 'apply', 'changed': bool(changes), 'changes': changes,
                        'skipped': skipped, 'baseline_mid': None, 'final_mid': None, 'error': None}
        if changes and out_path:
            p = out_path.with_name(out_path.stem + '.apply.input.json')
            p.write_text(json.dumps(new_inp, ensure_ascii=False, indent=2), encoding='utf-8')
            result['apply_input'] = str(p)
        result['changes'] = changes
        result['skipped'] = skipped
    if out_path:
        save_record(out_path, rec)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()