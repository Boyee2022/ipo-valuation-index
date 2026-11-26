# -*- coding: utf-8 -*-
"""估值智能体配置：三专家 + 主审的唯一配置源。

- 文件默认 ~/.dsh-valuation/agents.json（仓库外），可用 VALUATION_AGENTS_CONFIG 覆盖。
- 每批跑批开始时读取一次快照写入任务 state.json；运行中的任务不受后续保存影响。
- 只保留当前一版并自增版本号，不做跨批参数台账（探索阶段）。
"""
import json
import os
import re
import threading
import time
from pathlib import Path

AGENTS = ('comparable', 'financial', 'sentiment', 'main')
EXPERT_AGENTS = ('comparable', 'financial', 'sentiment')
AGENT_LABEL = {'comparable': '可比质量', 'financial': '折现参数', 'sentiment': '舆情', 'main': '主审'}
AGENT_PARAMS = {
    'comparable': ('comp_weight_pp',),
    'financial': ('wacc_pp', 'tg_pp'),
    'sentiment': ('sent_weight_pp',),
}
PARAM_SEVERITIES = {
    'comp_weight_pp': ('medium', 'high', 'critical'),
    'sent_weight_pp': ('medium', 'high'),
    'wacc_pp': ('medium', 'high'),
    'tg_pp': ('medium', 'high'),
}
CAP_RANGE = {
    'comp_weight_pp': (0.5, 20.0),
    'sent_weight_pp': (0.5, 20.0),
    'wacc_pp': (0.1, 3.0),
    'tg_pp': (0.1, 1.5),
}

DEFAULTS = {
    'version': 0,
    'model': '',
    'concurrency': 6,
    'timeout_s': 90,
    'agents': {
        'comparable': {
            'enabled': True,
            'confidence_gate': 0.65,
            'caps': {'comp_weight_pp': {'medium': 5.0, 'high': 8.0, 'critical': 10.0}},
        },
        'financial': {
            'enabled': True,
            'confidence_gate': 0.65,
            'caps': {'wacc_pp': {'medium': 0.4, 'high': 1.0},
                     'tg_pp': {'medium': 0.2, 'high': 0.6}},
        },
        'sentiment': {
            'enabled': True,
            'confidence_gate': 0.65,
            'caps': {'sent_weight_pp': {'medium': 5.0, 'high': 10.0}},
        },
        'main': {'enabled': True},
    },
}

_MODEL_RE = re.compile(r'^[A-Za-z0-9._:\-/]*$')
_LOCK = threading.Lock()


def path():
    """配置文件路径：环境变量优先，默认仓库外的 ~/.dsh-valuation/agents.json。"""
    override = os.environ.get('VALUATION_AGENTS_CONFIG')
    return Path(override).expanduser() if override else Path.home() / '.dsh-valuation' / 'agents.json'


def display_path():
    p = path()
    home = str(Path.home())
    s = str(p)
    return '~' + s[len(home):] if s.startswith(home) else s


def updated_at():
    try:
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(path().stat().st_mtime))
    except OSError:
        return None


def _num(v, default=None):
    try:
        f = float(v)
        return f if f == f and abs(f) != float('inf') else default
    except (TypeError, ValueError):
        return default


def _fail(msg, strict):
    if strict:
        raise ValueError(msg)


def normalize(raw, strict=False):
    """合并默认值并校验。strict=True 用于保存（非法值报错）；运行路径非法值回退默认。"""
    src = raw if isinstance(raw, dict) else {}
    out = {'version': int(_num(src.get('version'), 0) or 0), 'model': '',
           'concurrency': 6, 'timeout_s': 90, 'agents': {}}

    model = str(src.get('model') or '').strip()
    if not _MODEL_RE.match(model) or len(model) > 64:
        _fail('模型名含非法字符或过长', strict)
        model = ''
    out['model'] = model

    concurrency = _num(src.get('concurrency'), 6)
    if concurrency is None or not 1 <= concurrency <= 12:
        _fail('并发数需在 1~12', strict)
        concurrency = 6
    out['concurrency'] = int(round(concurrency))

    timeout = _num(src.get('timeout_s'), 90)
    if timeout is None or not 30 <= timeout <= 240:
        _fail('超时需在 30~240 秒', strict)
        timeout = 90
    out['timeout_s'] = int(round(timeout))

    agents_in = src.get('agents') if isinstance(src.get('agents'), dict) else {}
    for agent in AGENTS:
        conf = agents_in.get(agent) if isinstance(agents_in.get(agent), dict) else {}
        enabled = conf.get('enabled')
        if not isinstance(enabled, bool):
            if enabled is not None:
                _fail('%s 启停需为布尔值' % AGENT_LABEL[agent], strict)
            enabled = True
        item = {'enabled': enabled}
        if agent == 'main':
            out['agents'][agent] = item
            continue
        gate = _num(conf.get('confidence_gate'), 0.65)
        if gate is None or not 0.5 <= gate <= 0.95:
            _fail('%s 置信门槛需在 0.50~0.95' % AGENT_LABEL[agent], strict)
            gate = 0.65
        item['confidence_gate'] = round(gate, 2)
        caps_in = conf.get('caps') if isinstance(conf.get('caps'), dict) else {}
        caps = {}
        for param in AGENT_PARAMS[agent]:
            sevs = PARAM_SEVERITIES[param]
            fallback = DEFAULTS['agents'][agent]['caps'][param]
            got = caps_in.get(param) if isinstance(caps_in.get(param), dict) else {}
            lo, hi = CAP_RANGE[param]
            vals = []
            for sev in sevs:
                v = _num(got.get(sev), fallback[sev])
                if v is None or not lo <= v <= hi:
                    _fail('%s 幅度上限需在 %g~%gpp' % (param, lo, hi), strict)
                    v = fallback[sev]
                vals.append(round(v, 2))
            if any(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
                _fail('%s 幅度上限需按严重度递增（%s）' % (param, ' ≤ '.join(sevs)), strict)
                vals = [fallback[s] for s in sevs]
            caps[param] = dict(zip(sevs, vals))
        item['caps'] = caps
        out['agents'][agent] = item
    return out


def load():
    """运行路径：读取当前配置；文件缺失或损坏时回退默认值，不阻断跑批。"""
    try:
        raw = json.loads(path().read_text(encoding='utf-8'))
    except Exception:
        return normalize({})
    return normalize(raw)


def save(raw):
    """保存路径：严格校验后原子落盘，版本号在磁盘当前版本上自增。"""
    with _LOCK:
        current = load()
        cfg = normalize(raw, strict=True)
        cfg['version'] = max(1, int(current.get('version') or 0) + 1)
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(cfg, saved_at=time.strftime('%Y-%m-%d %H:%M:%S'))
        tmp = p.with_name(p.name + '.tmp.%d.%d' % (os.getpid(), threading.get_ident()))
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(p)
        return cfg


def enabled(cfg, agent):
    return bool(((cfg.get('agents') or {}).get(agent) or {}).get('enabled', True))


def gate(cfg, agent):
    return float(((cfg.get('agents') or {}).get(agent) or {}).get('confidence_gate') or 0.65)


def caps_for(cfg, param):
    """某参数的严重度→幅度上限；缺失时回退内置默认。"""
    for agent in EXPERT_AGENTS:
        caps_map = ((cfg.get('agents') or {}).get(agent) or {}).get('caps') or {}
        if param in caps_map:
            return caps_map[param]
    for agent in EXPERT_AGENTS:
        if param in DEFAULTS['agents'][agent]['caps']:
            return DEFAULTS['agents'][agent]['caps'][param]
    return {}


def _caps_text(cfg):
    comp = caps_for(cfg, 'comp_weight_pp')
    sent = caps_for(cfg, 'sent_weight_pp')
    wacc = caps_for(cfg, 'wacc_pp')
    tg = caps_for(cfg, 'tg_pp')
    return ('可比 严重/高/中 %.1f/%.1f/%.1fpp、舆情 高/中 %.1f/%.1fpp、'
            'WACC/Ke 高/中 %.2f/%.2fpp、永续 高/中 %.2f/%.2fpp' % (
                comp.get('critical', 10.0), comp.get('high', 8.0), comp.get('medium', 5.0),
                sent.get('high', 10.0), sent.get('medium', 5.0),
                wacc.get('high', 1.0), wacc.get('medium', 0.4),
                tg.get('high', 0.6), tg.get('medium', 0.2)))


def prompt_rules(cfg, agent):
    """追加到系统提示词的「本批配置」行：代码门槛以配置为准，上文数字仅作默认。"""
    if agent == 'main':
        return '\n本批配置（优先于上文数字）：幅度上限 %s。' % _caps_text(cfg)
    return '\n本批配置（优先于上文数字）：confidence≥%.2f；幅度上限 %s。' % (
        gate(cfg, agent), _caps_text(cfg))