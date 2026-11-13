# -*- coding: utf-8 -*-
"""逐券输入组装：真实财务/行情 + 同行业可比公司 → llm-ipo-valuation 输入模板。

口径说明（与技能输入 schema 对齐，单位：金额=亿元、比率=小数、股本=亿股）：
- 营收/归母净利取最近年报口径（与净利披露档 annual 一致；9M 累计不含在 TTM 内，避免口径混用）；
- WACC/永续增速不显式给 → 引擎 capm_auto + 行业参数底座自动解析；
- 舆情：东财新闻搜索+股吧帖（免费公开接口），词频+规则打分 → company_news_sentiment + sentiment_adjustment_pct 显式传入；
- 可比公司：同行业、剔除自身、按自由流通市值对数距离取前 4 家，标注「自动选取、未经人工核验」。
"""
import math

import dsources
import sentiment

PEER_N = 4


def pick_peers(stock, universe, n=PEER_N):
    """同行业可比候选；行业不足 2 家时退到同行业大类（Ⅱ 前段）；仍无则返回空。"""
    code = stock.get('secucode')
    ind = (stock.get('industry') or '').strip()
    me = stock.get('free_cap') or 0
    base = ind.split('Ⅱ')[0] if ind else ''
    cands = [r for r in universe
             if r.get('industry') and r.get('secucode') != code and (r.get('free_cap') or 0) > 0
             and r.get('industry') == ind]
    if len(cands) < 2 and base:
        cands = [r for r in universe
                 if r.get('industry') and r.get('secucode') != code and (r.get('free_cap') or 0) > 0
                 and (r.get('industry') or '').startswith(base)]

    def dist(r):
        cap = r.get('free_cap') or 0
        if me <= 0 or cap <= 0:
            return 1e9
        return abs(math.log(cap / me))
    cands.sort(key=dist)
    return cands[:n]


def _exchange(secucode):
    code, _, mkt = (secucode or '').partition('.')
    if mkt.upper() != 'SH':
        if code.startswith('300'):
            return '深交所创业板'
        return '深交所主板'
    if code.startswith('688'):
        return '上交所科创板'
    return '上交所主板'


def _consensus_first(con):
    if not con:
        return None
    return con.get(sorted(con)[0])


def build_input(stock, universe, params, as_of):
    """组装单券输入。数据缺失抛 ValueError → 跑批跳过并留痕。"""
    code = stock['secucode']
    fin = dsources.financials(code)
    rev = None
    by_year = fin.get('revenue_by_year') or {}
    if by_year:
        rev = by_year[sorted(by_year)[-1]]
    np_ = fin.get('annual_net_profit')
    if rev is None or np_ is None:
        raise ValueError('披露财务缺失（营收/归母净利），跳过')

    peers = pick_peers(stock, universe)
    if not peers:
        raise ValueError('同行业可比公司不足，跳过')

    quotes = dsources.tencent_quotes(
        [dsources._tcode(code)] + [dsources._tcode(p['secucode']) for p in peers])

    comparables = []
    for p in peers:
        try:
            pfin = dsources.financials(p['secucode'])
        except Exception:
            pfin = {}
        q = quotes.get(dsources._tcode(p['secucode'])) or {}
        mktcap = q.get('mktcap_yi') or p.get('free_cap')
        pe = q.get('pe') if q.get('pe') is not None else p.get('pe')
        prev = pfin.get('revenue_latest')
        pb = pfin.get('revenue_by_year') or {}
        growth = None
        if len(pb) >= 2:
            k = sorted(pb)
            a, b = pb[k[-2]], pb[k[-1]]
            if a:
                growth = round((b / a - 1) * 100, 1)
        net_profit = None
        if p.get('eps') is not None and p.get('total_shares'):
            net_profit = round(p['eps'] * p['total_shares'], 2)
        ps = round(mktcap / prev, 2) if mktcap and prev else None
        comparables.append({
            'name': p['name'],
            'code': p['secucode'],
            'mktcap': mktcap,
            'net_profit': net_profit,
            'revenue': prev,
            'pe': pe,
            'ps': ps,
            'growth_pct': growth,
            'note': '同行业自动选取（%s），公开行情 %s，未经人工核验' % (stock.get('industry') or '—', as_of),
        })

    margins = fin.get('margin_history') or []
    if margins:
        nm = margins[-1]
    elif rev:
        nm = round(np_ / rev, 4)
    else:
        nm = None

    ocf = fin.get('ocf_latest')
    capex = fin.get('capex_implied')
    shares = fin.get('total_shares') or stock.get('total_shares')
    roe_pct = stock.get('roe')
    weights = params.get('weights') or {}
    snt = sentiment.score_stock(code, stock['name'], rounds=int(params.get('sentiment_rounds') or 10))
    inp = {
        'meta': {
            'company': stock['name'],
            'ticker': code,
            'industry': stock.get('industry') or '未分类',
            'exchange': _exchange(code),
            'as_of_date': as_of,
            'one_line_input': '%s（%s）最近年报营收 %s 亿元、归母净利 %s 亿元；由估值跑批管线自动组装输入并估值' % (
                stock['name'], stock.get('industry') or '—', rev, np_),
        },
        'financials': {
            'revenue_latest_ttm': rev,
            'revenue_by_year': by_year,
            'net_profit_latest_ttm': np_,
            'net_profit_basis': {
                'annual_net_profit': np_,
                'consensus_net_profit': _consensus_first(fin.get('consensus')),
                'as_of': as_of,
                'annualized_source': '最近年报归母净利（东财披露）+ 机构一致预期（%s）' % (
                    ('%s 家机构' % fin.get('consensus_org_num')) if fin.get('consensus_org_num') else '口径见报告'),
            },
            'net_margin': nm,
            'gross_margin': None,
            'margin_history': margins or None,
            'roe': round(roe_pct / 100, 4) if roe_pct is not None else None,
            'ocf_latest': ocf,
            'capex_latest': capex if capex is not None and capex >= 0 else None,
            'total_shares_after_issue': shares,
            'loss_making': bool(np_ is not None and np_ < 0),
            'data_as_of': as_of,
        },
        'comparables': comparables,
        'sentiment': {
            'sector_heat': 'neutral',
            'company_news_sentiment': snt['label'],
            'sentiment_adjustment_pct': snt['adjustment_pct'],
            'evidence': snt['evidence'],
        },
        'preferences': {
            'weights': {
                'dcf': float(weights.get('dcf', 0.3)),
                'comparable': float(weights.get('comp', 0.5)),
                'sentiment': float(weights.get('sent', 0.2)),
            },
            'scenario_weights': {'bear': 0.25, 'base': 0.5, 'bull': 0.25},
            'exclude_outliers': True,
        },
        'data_sources': [
            {'source': '东财 datacenter 业绩报表/F10/机构一致预期（公开披露）',
             'items': ['营收/归母净利（年报口径）', '经营现金流/FCFF/股本', '一致预期净利']},
            {'source': '腾讯行情（公开实时行情）', 'items': ['可比公司行情、市值、PE']},
            {'source': '东财 datacenter 指数成分（收盘权重）', 'items': ['成分券列表与权重（前一日口径）', '行业分类']},
            {'source': '东财新闻搜索 + 股吧帖（免费公开接口，词频+规则打分）',
             'items': ['近 30 天新闻 %d 条 / 股吧 %d 条' % (snt.get('news_count') or 0, snt.get('guba_count') or 0),
                       'company_news_sentiment=%s，adjustment_pct=%+.1f%%' % (snt['label'], snt['adjustment_pct'])]},
        ],
    }
    return inp
