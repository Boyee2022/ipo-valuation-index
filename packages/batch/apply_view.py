# -*- coding: utf-8 -*-
"""逐券报告「生效回写 · 改前 / 改后」可视化区块。

陈老师技能包生成 *.report.html 后，由本模块在 apply 模式有回写改动时追加一节：
基线估值 → 主审回写 → 重跑结果的对比（KPI、参数改动、四部分估值条）。
只在报告正文首个 <h2> 前插入，不改技能包与报告其余内容；样式仅用报告主题令牌。
"""
import html
import json
import re
from pathlib import Path

SECTION_ID = 'dsh-apply-view'
_SECTION_RE = re.compile(r'<section id="%s".*?</section>\s*' % SECTION_ID, re.S | re.I)
_FIRST_H2_RE = re.compile(r'<h2[^>]*\bid=["\']s1["\']', re.I)

_METHODS = (
    ('part1_dcf', 'DCF'),
    ('part2_comparable_quality', '可比'),
    ('part3_market_sentiment', '舆情'),
)

_CSS = r"""
#dsh-apply-view{margin:28px 0 8px;border:1px solid var(--rt-line,#e2e4e9);border-radius:8px;
  background:var(--rt-panel,#fff);overflow:hidden;font-family:var(--rt-sans,inherit)}
#dsh-apply-view *{box-sizing:border-box}
#dsh-apply-view .apv-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 14px;
  border-bottom:1px solid var(--rt-line,#e2e4e9);background:var(--rt-panel2,#f2f3f5)}
#dsh-apply-view .apv-tag{display:inline-block;padding:1px 7px;border-radius:3px;
  border:1px solid var(--rt-amber,#b45309);color:var(--rt-amber,#b45309);
  font-family:var(--rt-mono,ui-monospace,monospace);font-size:10.5px;font-weight:700;letter-spacing:.06em}
#dsh-apply-view .apv-ttl{font-size:var(--fs-title,14px);font-weight:700;color:var(--rt-ink,#101828)}
#dsh-apply-view .apv-sub{margin-left:auto;font-size:var(--fs-caption,11.5px);color:var(--rt-faint,#939baa)}
#dsh-apply-view .apv-sub a{color:inherit;border-bottom:1px dotted var(--rt-line2,#c9cdd5)}
#dsh-apply-view .apv-body{padding:14px}
#dsh-apply-view .apv-err{margin:0 0 12px;padding:8px 10px;border:1px solid var(--rt-line,#e2e4e9);
  border-left:2px solid var(--rt-up,#c7000b);background:color-mix(in srgb,var(--rt-up,#c7000b) 6%,transparent);
  color:var(--rt-up,#c7000b);font-size:var(--fs-caption,11.5px);border-radius:0 4px 4px 0}
#dsh-apply-view .apv-flow{display:flex;align-items:stretch;gap:8px;flex-wrap:wrap;margin-bottom:12px}
#dsh-apply-view .apv-node{flex:1 1 150px;min-width:0;border:1px solid var(--rt-line,#e2e4e9);
  border-radius:6px;padding:8px 10px;background:var(--rt-panel2,#f2f3f5)}
#dsh-apply-view .apv-node span{display:block;font-size:var(--fs-micro,10.5px);color:var(--rt-faint,#939baa);
  letter-spacing:.05em}
#dsh-apply-view .apv-node b{display:block;margin:2px 0;color:var(--rt-ink,#101828);
  font-family:var(--rt-mono,ui-monospace,monospace);font-size:18px;line-height:1.3;
  font-variant-numeric:tabular-nums}
#dsh-apply-view .apv-node i{font-style:normal;font-size:var(--fs-micro,10.5px);color:var(--rt-dim,#555e6e)}
#dsh-apply-view .apv-node.base b{color:var(--rt-dim,#555e6e)}
#dsh-apply-view .apv-node.mid{border-style:dashed}
#dsh-apply-view .apv-node.fin{border-left:2px solid var(--rt-amber,#b45309)}
#dsh-apply-view .apv-node.fin b{color:var(--rt-amber,#b45309)}
#dsh-apply-view .apv-arrow{display:flex;align-items:center;color:var(--rt-amber,#b45309);
  font-family:var(--rt-mono,ui-monospace,monospace);font-size:16px}
#dsh-apply-view .apv-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:12px}
#dsh-apply-view .apv-kpi{border:1px solid var(--rt-line,#e2e4e9);border-radius:6px;padding:8px 10px;
  background:var(--rt-panel,#fff);min-width:0}
#dsh-apply-view .apv-kpi span{display:block;font-size:var(--fs-micro,10.5px);color:var(--rt-faint,#939baa);
  letter-spacing:.05em}
#dsh-apply-view .apv-kpi b{display:block;margin:3px 0 2px;color:var(--rt-ink,#101828);
  font-family:var(--rt-mono,ui-monospace,monospace);font-size:16px;line-height:1.35;
  font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
#dsh-apply-view .apv-kpi i{display:block;font-style:normal;font-size:var(--fs-caption,11.5px);
  color:var(--rt-dim,#555e6e);line-height:1.55}
#dsh-apply-view .apv-kpi .up{color:var(--rt-up,#c7000b)}
#dsh-apply-view .apv-kpi .down{color:var(--rt-down,#0e7a3d)}
#dsh-apply-view .apv-cols{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:10px}
#dsh-apply-view .apv-card{border:1px solid var(--rt-line,#e2e4e9);border-radius:6px;padding:10px 12px;
  background:var(--rt-panel,#fff);min-width:0}
#dsh-apply-view .apv-h{margin-bottom:6px;font-size:var(--fs-caption,11.5px);font-weight:700;
  color:var(--rt-dim,#555e6e);letter-spacing:.06em}
#dsh-apply-view table.apv-tbl{margin:0;border:0;background:transparent;font-size:var(--fs-caption,11.5px)}
#dsh-apply-view table.apv-tbl th{background:transparent;padding:3px 6px;border-bottom:1px solid var(--rt-line,#e2e4e9);
  color:var(--rt-faint,#939baa);font-size:var(--fs-micro,10.5px);white-space:nowrap}
#dsh-apply-view table.apv-tbl td{padding:4px 6px;border-top:1px solid var(--rt-line,#e2e4e9);
  color:var(--rt-dim,#555e6e);vertical-align:top}
#dsh-apply-view table.apv-tbl td:first-child{color:var(--rt-ink,#101828);white-space:nowrap}
#dsh-apply-view table.apv-tbl td.r{text-align:right;font-family:var(--rt-mono,ui-monospace,monospace);
  font-variant-numeric:tabular-nums}
#dsh-apply-view .apv-dlt{color:var(--rt-amber,#b45309)}
#dsh-apply-view .apv-skip{margin-top:5px;font-size:var(--fs-micro,10.5px);color:var(--rt-amber,#b45309);
  line-height:1.6}
#dsh-apply-view .apv-m{display:grid;grid-template-columns:92px minmax(0,1fr) 118px;gap:8px;
  align-items:center;margin:5px 0}
#dsh-apply-view .apv-mk{font-size:var(--fs-caption,11.5px);color:var(--rt-dim,#555e6e)}
#dsh-apply-view .apv-mk small{display:block;font-size:var(--fs-micro,10.5px);color:var(--rt-faint,#939baa)}
#dsh-apply-view .apv-mb{display:grid;gap:2px}
#dsh-apply-view .apv-mb i{display:block;height:7px;border-radius:2px;min-width:1px}
#dsh-apply-view .apv-mb .b{background:var(--rt-line2,#c9cdd5)}
#dsh-apply-view .apv-mb .f{background:var(--rt-amber,#b45309)}
#dsh-apply-view .apv-mv{text-align:right;font-family:var(--rt-mono,ui-monospace,monospace);
  font-size:var(--fs-caption,11.5px);line-height:1.5;color:var(--rt-dim,#555e6e);
  font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
#dsh-apply-view .apv-mv .f{color:var(--rt-amber,#b45309)}
#dsh-apply-view .apv-m.sum .apv-mk{color:var(--rt-amber,#b45309);font-weight:700}
#dsh-apply-view .apv-legend{display:flex;gap:12px;margin-top:8px;font-size:var(--fs-micro,10.5px);
  color:var(--rt-faint,#939baa);flex-wrap:wrap}
#dsh-apply-view .apv-legend i{display:inline-block;width:16px;height:5px;border-radius:2px;
  margin-right:4px;vertical-align:middle}
#dsh-apply-view .apv-legend .b{background:var(--rt-line2,#c9cdd5)}
#dsh-apply-view .apv-legend .f{background:var(--rt-amber,#b45309)}
#dsh-apply-view .apv-note{margin-top:10px;font-size:var(--fs-micro,10.5px);color:var(--rt-faint,#939baa);
  line-height:1.7}
@media(max-width:900px){
  #dsh-apply-view .apv-cols{grid-template-columns:1fr}
  #dsh-apply-view .apv-kpis{grid-template-columns:1fr 1fr}
}
@media(max-width:600px){
  #dsh-apply-view .apv-kpis{grid-template-columns:1fr}
  #dsh-apply-view .apv-m{grid-template-columns:68px minmax(0,1fr) 92px}
  #dsh-apply-view .apv-sub{margin-left:0}
}
@media print{#dsh-apply-view{break-inside:avoid}}
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _fmt(x, nd=2):
    v = _num(x)
    return '—' if v is None else ('{:,.%df}' % nd).format(v)


def _signed(x, nd=2, suffix=''):
    v = _num(x)
    if v is None:
        return '—'
    return ('{:+,.%df}' % nd).format(v) + suffix


def _esc(x):
    return html.escape(str(x if x is not None else ''))


def _part(syn, key):
    item = (syn.get('four_part') or {}).get(key) or {}
    return _num(item.get('value')), _num(item.get('weight'))


def _bar(value, maxv):
    v = _num(value)
    if v is None or maxv <= 0:
        return 0.0
    return max(1.0, min(100.0, v / maxv * 100.0))


def _cls(delta):
    v = _num(delta)
    if v is None or abs(v) < 1e-9:
        return ''
    return 'up' if v > 0 else 'down'


def _change_value(param, value):
    if isinstance(value, str):
        return _esc(value)
    v = _num(value)
    if v is None:
        return _esc(value)
    if param in ('wacc_pp', 'tg_pp'):
        return '%.2f%%' % v
    return '%.2f' % v


def render(base, final, apply_info, shares=None, close=None, shadow_href=None):
    """base/final 为引擎 out.json 内容；apply_info 为 pipeline 行内 apply 记录。"""
    base_syn = (base or {}).get('synthesis') or {}
    final_syn = (final or {}).get('synthesis') or {}
    bm, fm = _num(base_syn.get('weighted_mid')), _num(final_syn.get('weighted_mid'))
    delta = (fm - bm) if (bm is not None and fm is not None) else None
    pct = (delta / bm * 100.0) if (delta is not None and bm) else None
    shares = _num(shares)
    close = _num(close)
    changes = (apply_info or {}).get('changes') or []
    skipped = (apply_info or {}).get('skipped') or []
    err = (apply_info or {}).get('error')

    base_conf = (base or {}).get('confidence') or {}
    final_conf = (final or {}).get('confidence') or {}
    b_lv = _esc(base_conf.get('level') or '—')
    f_lv = _esc(final_conf.get('level') or '—')
    b_sc, f_sc = _num(base_conf.get('score')), _num(final_conf.get('score'))
    conf_txt = '%s %s → %s %s' % (
        b_lv, _fmt(b_sc, 1) if b_sc is not None else '—',
        f_lv, _fmt(f_sc, 1) if f_sc is not None else '—')

    b_iv = base_syn.get('interval') or []
    f_iv = final_syn.get('interval') or []
    iv_txt = '%s–%s → %s–%s' % (
        _fmt(b_iv[0]) if len(b_iv) > 0 else '—', _fmt(b_iv[1]) if len(b_iv) > 1 else '—',
        _fmt(f_iv[0]) if len(f_iv) > 0 else '—', _fmt(f_iv[1]) if len(f_iv) > 1 else '—')

    # 每股卡片
    ps_b = (bm / shares) if (bm is not None and shares) else None
    ps_f = (fm / shares) if (fm is not None and shares) else None
    if ps_b is not None and ps_f is not None:
        ps_txt = '%s → %s' % (_fmt(ps_b), _fmt(ps_f))
        ps_note = _signed(ps_f - ps_b) + ' 元/股'
        if close:
            ps_note += ' · 较现价 %s：%s → %s' % (
                _fmt(close), _signed((ps_b / close - 1) * 100, suffix='%'),
                _signed((ps_f / close - 1) * 100, suffix='%'))
    else:
        ps_txt, ps_note = '—', '缺少总股本，无法拆算每股'

    mid_txt = '%s → %s' % (_fmt(bm), _fmt(fm))
    mid_note = '%s 亿元 · %s' % (_signed(delta), _signed(pct, suffix='%')) if delta is not None else '—'
    cls = _cls(delta)

    # 参数改动
    rows = []
    for c in changes:
        param = c.get('param') or ''
        label = c.get('label') or param or '改动'
        rows.append(
            '<tr><td>%s</td><td class="r">%s</td><td class="r">%s</td><td class="r apv-dlt">%s</td></tr>' % (
                _esc(label), _change_value(param, c.get('from')),
                _change_value(param, c.get('to')),
                (_signed(c.get('delta'), 1, ' pp') if _num(c.get('delta')) is not None else '—')))
    if not rows:
        rows.append('<tr><td colspan="4">主审未通过任何参数改动，结果沿用基线。</td></tr>')
    params_table = (
        '<table class="apv-tbl"><thead><tr><th>项目</th><th class="r">改前</th>'
        '<th class="r">改后</th><th class="r">变动</th></tr></thead><tbody>%s</tbody></table>'
        % ''.join(rows))
    skip_html = ''
    if skipped:
        skip_html = '<div class="apv-skip">未生效：%s</div>' % _esc('；'.join(str(x) for x in skipped))
    note_w = ''
    if any((c.get('param') == 'weights') for c in changes):
        note_w = '<div class="apv-skip" style="color:var(--rt-faint,#939baa)">' \
                 '方法权重顺序：DCF / 可比 / 舆情。</div>'

    # 四部分对比条
    items = []
    maxv = max([v for v in (bm, fm) if v is not None] or [0.0])
    for key, name in _METHODS:
        bv, bw = _part(base_syn, key)
        fv, fw = _part(final_syn, key)
        for v in (bv, fv):
            if v is not None:
                maxv = max(maxv, v)
        items.append((name, bv, bw, fv, fw))
    rows = []
    for name, bv, bw, fv, fw in items:
        wtxt = ''
        if bw is not None or fw is not None:
            wtxt = '<small>权重 %s → %s</small>' % (
                ('%.1f%%' % (bw * 100)) if bw is not None else '—',
                ('%.1f%%' % (fw * 100)) if fw is not None else '—')
        rows.append(
            '<div class="apv-m"><div class="apv-mk">%s%s</div>'
            '<div class="apv-mb"><i class="b" style="width:%.1f%%"></i>'
            '<i class="f" style="width:%.1f%%"></i></div>'
            '<div class="apv-mv"><div>%s</div><div class="f">%s</div></div></div>' % (
                _esc(name), wtxt, _bar(bv, maxv), _bar(fv, maxv), _fmt(bv), _fmt(fv)))
    rows.append(
        '<div class="apv-m sum"><div class="apv-mk">综合中枢</div>'
        '<div class="apv-mb"><i class="b" style="width:%.1f%%"></i>'
        '<i class="f" style="width:%.1f%%"></i></div>'
        '<div class="apv-mv"><div>%s</div><div class="f">%s</div></div></div>' % (
            _bar(bm, maxv), _bar(fm, maxv), _fmt(bm), _fmt(fm)))
    bars = (
        '<div class="apv-h">方法估值对比（亿元）</div>'
        + ''.join(rows)
        + '<div class="apv-legend"><span><i class="b"></i>改前 · 基线</span>'
          '<span><i class="f"></i>改后 · 重跑</span></div>')

    err_html = ('<div class="apv-err">回写重跑失败，已回滚基线：%s</div>' % _esc(err)) if err else ''
    state = '回写失败 · 已回滚' if err else ('回写生效' if changes else '无改动')
    flow_txt = ('%d 项' % len(changes)) if changes else '—'
    link = (' · <a href="./%s">评审明细 ↗</a>' % _esc(shadow_href)) if shadow_href else ''
    sub = ('主审通过 %d 项 · 改写输入后重跑%s' % (
        len(changes), ' · 已回滚' if err else '')) + link

    return (
        '<section id="%s" class="apv">\n<style>%s</style>\n'
        '<div class="apv-top"><span class="apv-tag">APPLY · 回写生效</span>'
        '<span class="apv-ttl">改前 / 改后</span>'
        '<span class="apv-sub">%s</span></div>\n'
        '<div class="apv-body">%s'
        '<div class="apv-flow">'
        '<div class="apv-node base"><span>改前 · 基线估值</span><b>%s</b><i>亿元</i></div>'
        '<div class="apv-arrow">→</div>'
        '<div class="apv-node mid"><span>回写 · 重跑</span><b>%s</b><i>%s</i></div>'
        '<div class="apv-arrow">→</div>'
        '<div class="apv-node fin"><span>改后 · 最终估值</span><b>%s</b><i>亿元 · %s</i></div>'
        '</div>'
        '<div class="apv-kpis">'
        '<div class="apv-kpi"><span>估值中枢（亿元）</span><b>%s</b>'
        '<i class="%s">%s</i></div>'
        '<div class="apv-kpi"><span>每股估值（元）</span><b>%s</b><i>%s</i></div>'
        '<div class="apv-kpi"><span>置信度 / 区间（亿元）</span><b>%s</b>'
        '<i>区间 %s</i></div>'
        '</div>'
        '<div class="apv-cols">'
        '<div class="apv-card"><div class="apv-h">参数改动（主审通过）</div>%s%s%s</div>'
        '<div class="apv-card">%s</div>'
        '</div>'
        '<div class="apv-note">改前 = 评审证据生成时的基线估值；改后 = 回写参数后重跑的结果。'
        '本区块只呈现差异，报告其余章节均为改后口径；基线输入/输出保留为 '
        '*.baseline.json，不做反向校正。</div>'
        '</div></section>\n' % (
            SECTION_ID, _CSS, sub, err_html,
            _fmt(bm), flow_txt, state, _fmt(fm),
            _signed(pct, suffix='%') if pct is not None else '—',
            mid_txt, cls, mid_note, ps_txt, _esc(ps_note),
            conf_txt, _esc(iv_txt),
            params_table, skip_html, note_w, bars))


def inject(html_text, section):
    """删旧插新（幂等）；优先插在首个 s1 <h2> 前，退化为首个 <h2> / </body> 前。"""
    if not html_text or not section:
        return html_text
    body = _SECTION_RE.sub('', html_text)
    m = _FIRST_H2_RE.search(body)
    idx = m.start() if m else body.lower().find('<h2')
    if idx < 0:
        idx = body.lower().rfind('</body>')
    if idx < 0:
        return body + section
    return body[:idx] + section + body[idx:]


def inject_file(path, section):
    p = Path(path)
    if not p.is_file():
        return False
    text = p.read_text(encoding='utf-8', errors='replace')
    out = inject(text, section)
    if out == text:
        return False
    tmp = p.with_name(p.name + '.apv-tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(out)
    tmp.replace(p)
    return True


def _selfcheck():
    import sys
    jdir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not jdir:
        raise SystemExit('usage: apply_view.py <job_dir> [stem]')
    stem = sys.argv[2] if len(sys.argv) > 2 else '600028_SH'
    base = json.loads((jdir / (stem + '.out.baseline.json')).read_text(encoding='utf-8'))
    final = json.loads((jdir / (stem + '.out.json')).read_text(encoding='utf-8'))
    inp = json.loads((jdir / (stem + '.input.json')).read_text(encoding='utf-8'))
    info = {'changes': [{'param': 'weights', 'label': '方法权重',
                         'from': '30.0/50.0/20.0', 'to': '34.8/42.0/23.2', 'delta': None},
                        {'param': 'wacc_pp', 'label': 'WACC',
                         'from': 10.52, 'to': 10.12, 'delta': -0.4}],
            'skipped': [], 'error': None}
    section = render(base, final, info,
                     shares=(inp.get('financials') or {}).get('total_shares_after_issue'),
                     close=5.94, shadow_href='shadow.html')
    out = jdir / (stem + '.report.preview.html')
    inject_file(out, section)
    print('[ok]', out)


if __name__ == '__main__':
    _selfcheck()