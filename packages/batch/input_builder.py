# -*- coding: utf-8 -*-
"""逐券输入组装：真实财务/行情 + 同行业可比公司 → llm-ipo-valuation 输入模板。

口径说明（与技能输入 schema 对齐，单位：金额=亿元、比率=小数、股本=亿股）：
- 营收/归母净利取最近年报口径（与净利披露档 annual 一致；9M 累计不含在 TTM 内，避免口径混用）；
- WACC/永续增速默认不显式给 → 引擎 capm_auto + 行业参数底座自动解析；工作台覆盖时按 % ÷ 100
  写入 financials.wacc / financials.terminal_growth，优先于引擎自动解析；
- 舆情：东财新闻搜索+股吧帖（免费公开接口），词频+规则打分 → company_news_sentiment + sentiment_adjustment_pct 显式传入；
- 可比公司：同行业优先，细行业样本不足时回退行业前缀/粗板块，按自由流通市值对数距离取前 PEER_N（5）家，
  标注「自动选取、未经人工核验」；无可比时不跳过，引擎剔除可比法并下调置信度。
"""
import math

import dsources
import sentiment
import sentiment_llm

PEER_N = 5

# 金融路由关键词（与引擎 Layer 0 的 industry_class 推断一致）+ 非银金融兜底
_FIN_KEYS = ('银行', '保险', '证券', '券商', '金融')
# 与引擎 capm_auto 缺省一致：rf 1.9% / CVA ERP 8.04% / 税率 15% / D:E 0.3
_RF_DEFAULT = 0.019
_ERP_CVA = 0.0804
_TAX_DEFAULT = 0.15
_DE_DEFAULT = 0.3


def _financial_ke(ind, wacc_params):
    """金融路由 Ke：与引擎 CAPM 同口径（βL = βu × (1+(1−t)×D/E)，Ke = rf + βL×ERP）。"""
    if '银行' in ind:
        beta_u = 0.90
    else:
        bs = wacc_params.get('comparable_betas') or []
        beta_u = sum(bs) / len(bs) if bs else 1.00
    beta_l = beta_u * (1.0 + (1.0 - _TAX_DEFAULT) * _DE_DEFAULT)
    return round(beta_l, 4), round(_RF_DEFAULT + beta_l * _ERP_CVA, 4)

# 细行业在可比池中样本过少时的粗板块归组；仅用于兜底，不影响正常同行业选取。
SECTOR_GROUPS = {
    '消费出行': ('旅游零售Ⅱ', '旅游及景区', '酒店餐饮', '航空机场', '一般零售', '专业连锁Ⅱ', '贸易Ⅱ'),
    '家电': ('其他家电Ⅱ', '白色家电', '黑色家电', '小家电', '厨卫电器', '家电零部件Ⅱ', '照明设备Ⅱ'),
    '农业': ('农业综合Ⅱ', '动物保健Ⅱ', '养殖业', '种植业', '饲料', '渔业', '农产品加工'),
    '能源化工': ('焦炭Ⅱ', '油气开采Ⅱ', '煤炭开采', '炼化及贸易', '化学原料', '化学制品', '化学纤维', '燃气Ⅱ'),
    '材料': ('非金属材料Ⅱ', '玻璃玻纤', '水泥', '装修建材', '化学制品', '塑料', '橡胶', '金属新材料'),
    '美妆个护': ('化妆品', '个护用品', '医疗美容'),
}


def _industry_base(ind):
    return (ind or '').replace('Ⅱ', '').replace('Ⅲ', '').strip()


def _industry_tokens(ind):
    base = _industry_base(ind)
    return {base[i:i + 2] for i in range(len(base) - 1)}


def _sector_members(ind):
    for members in SECTOR_GROUPS.values():
        if ind in members:
            return members
    return ()


def peer_pool(stock, universe):
    """可比长名单：与 pick_peers 同口径但不截断；返回 (pool, scope)，scope ∈ same/prefix/sector/none。"""
    code = stock.get('secucode')
    ind = (stock.get('industry') or '').strip()
    me = stock.get('free_cap') or 0
    if me <= 0:
        me = next(((r.get('free_cap') or 0) for r in universe if r.get('secucode') == code), 0)
    base = _industry_base(ind)

    def usable(r):
        return (bool(r.get('industry')) and r.get('secucode') != code
                and (r.get('free_cap') or 0) > 0)

    def dist(r):
        cap = r.get('free_cap') or 0
        if me <= 0 or cap <= 0:
            return 1e9
        return abs(math.log(cap / me))

    same = [r for r in universe if usable(r) and r.get('industry') == ind]
    if len(same) >= 2:
        return sorted(same, key=dist), 'same'

    if base:
        prefix = [r for r in universe if usable(r) and (r.get('industry') or '').startswith(base)]
        # 只要前缀还有候选就沿用旧口径，避免把本来有可比的公司改判成跨板块。
        if prefix:
            return sorted(prefix, key=dist), 'prefix'

    members = _sector_members(ind)
    if not members:
        return [], 'none'

    tokens = _industry_tokens(ind)
    pool = [r for r in universe if usable(r) and r.get('industry') in members]

    def rank(r):
        shared = bool(tokens & _industry_tokens(r.get('industry')))
        return (0 if shared else 1, dist(r))

    return sorted(pool, key=rank), 'sector'


def pick_peers(stock, universe, n=PEER_N):
    """同行业可比候选；细行业样本不足时逐级回退到行业前缀/粗板块；仍无则返回空。"""
    return peer_pool(stock, universe)[0][:n]


def _median(vals):
    vals = sorted(v for v in vals if v is not None)
    n = len(vals)
    if not n:
        return None
    if n % 2:
        return round(vals[n // 2], 2)
    return round((vals[n // 2 - 1] + vals[n // 2]) / 2.0, 2)


def _peer_evidence(stock, universe, peers, target_year, as_of):
    """peer_screening v3.20.0 诊断块：长名单/剔除台账/截点/规模双口径（不改估值数值）。"""
    pool, scope = peer_pool(stock, universe)
    me = stock.get('free_cap') or 0
    ind = (stock.get('industry') or '').strip()
    selected = {p['secucode'] for p in peers}
    med_rev, med_mcap, rejected = [], [], []
    for r in pool:
        code = r.get('secucode')
        close, sh = r.get('close'), r.get('total_shares')
        mcap = round(close * sh, 2) if (close and sh) else None
        rv = ((dsources.annual_revenue_series(code).get('by_year') or {}).get(target_year)
              if target_year else None)
        if mcap:
            med_mcap.append(mcap)
        if rv:
            med_rev.append(rv)
        if code in selected:
            continue
        shared = bool(_industry_tokens(ind) & _industry_tokens(r.get('industry') or ''))
        if scope == 'sector' and not shared:
            rt, why = 'business_model', '跨细分行业兜底：与标的无共享行业词元'
        elif mcap is None or rv is None:
            miss = '、'.join(x for x, v in (('总市值', mcap), ('年报营收', rv)) if not v)
            rt, why = 'data', '缺失%s，无法计算规模距离/乘数' % miss
        else:
            cap = r.get('free_cap') or 0
            mult = math.exp(abs(math.log(cap / me))) if (cap > 0 and me > 0) else None
            if mult is not None and mult > 5.0:
                rt, why = 'scale', '自由流通市值偏离 %.2f× > 5×' % mult
            elif mult is not None:
                rt, why = 'other', '按自由流通市值距离排序未进入前 %d（偏离 %.2f×）' % (len(peers), mult)
            else:
                rt, why = 'other', '按规模距离排序未进入前 %d' % len(peers)
        rejected.append({'name': r.get('name'), 'code': code,
                         'reason_type': rt, 'reason': why})
    return {
        'enabled': True,
        'depth': 'full',
        'classification_system': 'SW_2021',
        'info_cutoff': as_of,
        'scale_multiple': 5,
        'long_list_size': len(pool),
        'long_list_median': {'revenue': _median(med_rev), 'market_cap': _median(med_mcap)},
        'rejected': rejected,
        'accounting_gate': True,
        'seasoning_gate': True,
        'index_anchor_haircut': True,
        'enforce': {'filter_sample': False, 'weight_keep': False},
        'note': 'skill peer_screening v3.20.0 四期证据链；诊断模式（enforce 未开启）不改估值数值',
    }


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


_DRV_LIMITS = {
    'ebit_margin': (-0.5, 1.0),
    'da_to_revenue': (0.0, 0.6),
    'capex_to_revenue': (0.0, 2.0),
    'nwc_to_revenue': (-1.5, 1.5),
}
# 负 NWC/营收下限：负营运资本随收入增长会无限释放现金，按 -20% 封顶
_NWC_FLOOR = -0.20


def _nwc_basis(st):
    """NWC/营收取可得年报均值；负值以 _NWC_FLOOR 为下限。"""
    hist = [(h.get('fy'), h.get('nwc_to_revenue')) for h in (st.get('history') or [])
            if h.get('nwc_to_revenue') is not None]
    if len(hist) >= 2:
        avg = sum(v for _, v in hist) / len(hist)
        basis = '3y_avg'
        years = [fy for fy, _ in hist]
    elif hist:
        avg = hist[0][1]
        basis = 'latest'
        years = [hist[0][0]]
    else:
        avg = st['nwc_to_revenue']
        basis = 'latest'
        years = [st['fy']] if st.get('fy') else []
    used = max(min(avg, _DRV_LIMITS['nwc_to_revenue'][1]), _NWC_FLOOR)
    return avg, used, basis, years, avg < _NWC_FLOOR


def _driver_block(st, ind):
    """报表驱动 FCFF ① 档（技能 dcf_drivers）：金融/数据不全/比率越界 → (None, 原因)。"""
    if any(k in (ind or '') for k in _FIN_KEYS):
        return None, '金融路由（DCF 权重 0）'
    if not st or not st.get('fy'):
        return None, 'F10 三表年报不全'
    for k, (lo, hi) in _DRV_LIMITS.items():
        v = st.get(k)
        if v is None or not (lo <= v <= hi):
            return None, '%s=%s 越界 [%s, %s]' % (k, v, lo, hi)
    nwc_avg, nwc_used, nwc_basis, nwc_years, nwc_floor = _nwc_basis(st)
    base_fcff = (st['revenue'] * st['ebit_margin'] * (1 - st['tax_rate'])
                 + st['revenue'] * st['da_to_revenue'] - st['revenue'] * st['capex_to_revenue'])
    nwc_note = 'NWC/营收 取%s %.2f%%' % (
        ('近 %d 年均值' % len(nwc_years)) if nwc_basis == '3y_avg' else '最新年报', nwc_used * 100)
    if nwc_floor:
        nwc_note += '（原始均值 %.2f%%，按负值下限 %.0f%% 调整）' % (nwc_avg * 100, _NWC_FLOOR * 100)
    note = 'FY%s 年报三表联立；EBIT=营业利润+财务费用；D&A/Capex 取现金流量表；NWC 含合同负债/预收/预付款；%s；税率 %s' % (
        st['fy'], nwc_note, st.get('tax_note') or '')
    if base_fcff < 0:
        note += '；基期 FCFF 为负，DCF 受净现金下限约束'
    return {
        'enabled': True,
        'base_revenue': st['revenue'],
        'ebit_margin': st['ebit_margin'],
        'da_to_revenue': st['da_to_revenue'],
        'capex_to_revenue': st['capex_to_revenue'],
        'nwc_to_revenue': round(nwc_used, 4),
        'nwc_latest': st['nwc_to_revenue'],
        'nwc_avg': round(nwc_avg, 4),
        'nwc_years': nwc_years,
        'nwc_basis': nwc_basis,
        'nwc_floor_applied': bool(nwc_floor),
        'tax_rate': st['tax_rate'],
        'fy': st['fy'],
        'tax_raw': st.get('tax_raw'),
        'tax_note': st.get('tax_note'),
        'base_fcff': round(base_fcff, 2),
        'ebit': st['ebit'],
        'da': st['da'],
        'capex': st['capex'],
        'nwc': st['nwc'],
        'definitions': st.get('definitions'),
        'history': st.get('history'),
        'note': note,
    }, None


def build_input(stock, universe, params, as_of):
    """组装单券输入。财务数据缺失抛 ValueError（跑批跳过）；无可比公司时照常出估值，由引擎剔除可比法并降级。"""
    code = stock['secucode']
    ind = (stock.get('industry') or '').strip()
    fin = dsources.financials(code)
    qual = dsources.quality_details(code, stock.get('industry'))
    stmt = {} if any(k in ind for k in _FIN_KEYS) else dsources.statement_drivers(code)
    drv, drv_skip = _driver_block(stmt, ind)
    rev = None
    by_year = fin.get('revenue_by_year') or {}
    if by_year:
        rev = by_year[sorted(by_year)[-1]]
    np_ = fin.get('annual_net_profit')
    if rev is None or np_ is None:
        raise ValueError('披露财务缺失（营收/归母净利），跳过')

    peers = pick_peers(stock, universe)
    peer_betas = dsources.comparable_betas([p['secucode'] for p in peers])
    # β 退化护栏（P3）：银行回归β在低波板块趋 0，改走 skill 行业β表；其余截断 [0.5, 2.0]
    if '银行' in ind:
        wacc_params = {'industry_beta': 0.90, 'beta_benchmark': 'SH000300', 'beta_window_months': 60}
    else:
        wacc_params = {'comparable_betas': [min(max(float(b['raw_beta']), 0.5), 2.0)
                                            for b in peer_betas] or None,
                       'beta_benchmark': 'SH000300', 'beta_window_months': 60}

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
        pb = pfin.get('revenue_by_year') or {}
        # 与标的年报口径对齐：PS 分母取可比最新年报营收（revenue_latest 是最新累计报告期，会高估 PS）
        prev = pb[max(pb)] if pb else pfin.get('revenue_latest')
        prev_basis = ('FY%s 年报' % max(pb)) if pb else '最新报告期'
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
        peer_ind = (p.get('industry') or '').strip()
        scope = '同行业' if peer_ind == ind else '同板块'
        lr = str(pfin.get('latest_report') or '')
        period_end = (('%s-12-31' % max(pb)) if pb
                      else (lr[:10] if len(lr) >= 10 and lr[4] == '-' else None))
        comparables.append({
            'name': p['name'],
            'code': p['secucode'],
            'included': True,
            'standard': 'CAS',
            'financial_period_end': period_end,
            'mktcap': mktcap,
            'net_profit': net_profit,
            'revenue': prev,
            'pe': pe,
            'ps': ps,
            'growth_pct': growth,
            'note': '%s自动选取（%s%s），财务口径 %s，公开行情 %s，未经人工核验' % (
                scope, ind or '—', '' if peer_ind == ind else '→' + (peer_ind or '—'),
                prev_basis, as_of),
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
    mode = str(params.get('sentiment_mode') or 'rule')
    wacc_pct = params.get('wacc_pct')
    tg_pct = params.get('terminal_growth_pct')
    if mode == 'llm':
        snt = sentiment_llm.score_stock(code, stock['name'], rounds=int(params.get('sentiment_rounds') or 10))
    else:
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
            'wacc_params': wacc_params,
            'ocf_to_net_profit': qual.get('ocf_to_net_profit'),
            'gross_margin_trend_pp': qual.get('gross_margin_trend_pp'),
            'receivables_to_revenue': qual.get('receivables_to_revenue'),
            'goodwill_ratio': qual.get('goodwill_ratio'),
            'nonrecurring_ratio': qual.get('nonrecurring_ratio'),
            'roic': qual.get('roic'),
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
            # PEG 仅单列展示：不并入可比合成均值（技能开关，缺省 true）
            'enable_peg_in_synthesis': False,
            'lifecycle_mode': 'auto',
            'lifecycle_classifier_mode': 'v326',
        },
        'dcf_cost': {
            # 可比法不可用时按剩余方法再归一，避免把可比法按 0 计入导致综合值静默缩水。
            'method_drop_mode': 'renormalize',
            'wacc_default_mode': 'capm_auto',
            'erp_default_mode': 'auto',
        },
        'data_sources': [
            {'source': '东财 datacenter 业绩报表/F10/机构一致预期（公开披露）',
             'items': ['营收/归母净利（年报口径）', '经营现金流/资本开支（年报口径，F10 现金流量表）/股本', '一致预期净利']},
            {'source': '腾讯行情（公开实时行情）', 'items': ['可比公司行情、市值、PE']},
            {'source': '东财 datacenter 指数成分（收盘权重）', 'items': ['成分券列表与权重（前一日口径）', '行业分类']},
            {'source': '东财新闻搜索 + 股吧帖（免费公开接口，%s）' % ('DeepSeek 语义打分' if mode == 'llm' else '词频+规则打分'),
             'items': ['近 30 天新闻 %d 条 / 股吧 %d 条' % (snt.get('news_count') or 0, snt.get('guba_count') or 0),
                       'company_news_sentiment=%s，adjustment_pct=%+.1f%%' % (snt['label'], snt['adjustment_pct'])]},
        ],
    }
    if drv:
        inp['dcf_drivers'] = drv
        inp['dcf_cost']['fcf_ratio_lazy'] = True
        _nwc_src = (('近 %d 年均值' % len(drv.get('nwc_years') or []))
                    if drv.get('nwc_basis') == '3y_avg' else '最新年报')
        if drv.get('nwc_floor_applied'):
            _nwc_src += '；负值下限 −20%'
        inp['data_sources'].append({
            'source': '东财 F10 利润表/现金流量表/资产负债表（年报，FY%s）' % drv['fy'],
            'items': ['报表驱动 FCFF（dcf_drivers ① 档）：营收 %.2f 亿、EBIT率 %.2f%%、D&A/营收 %.2f%%、Capex/营收 %.2f%%、NWC/营收 %.2f%%（%s）、税率 %.2f%%（有效税率 %s）、基期 FCFF %.2f 亿' % (
                drv['base_revenue'], drv['ebit_margin'] * 100, drv['da_to_revenue'] * 100,
                drv['capex_to_revenue'] * 100, drv['nwc_to_revenue'] * 100, _nwc_src, drv['tax_rate'] * 100,
                ('%.2f%%' % (drv['tax_raw'] * 100)) if drv.get('tax_raw') is not None else '—',
                drv['base_fcff'])],
        })
    elif not any(k in ind for k in _FIN_KEYS):
        inp['data_sources'].append({
            'source': '东财 F10 三表年报（未启用报表驱动 FCFF）',
            'items': [drv_skip or '数据不全'],
        })
    # ---- Layer 0 前提 A/B 门（非金融）----
    # 显式 general：资源/公用行业路由依赖 NAV 数据，工作台尚未接入，本步只开 A/B 门
    # （A2 负 FCFF 占比 >60% → negative_fcff，DCF 权重封顶 0.3；当前基础权重 0.3 时数值不变）。
    if not any(k in ind for k in _FIN_KEYS) and stmt:
        _fch = stmt.get('fcff_history') or []
        _fneg = stmt.get('fcff_neg_ratio')
        inp['preferences']['layer0_check'] = True
        inp['meta']['framework_check'] = {
            'industry_class': 'general',
            'fcff_history': _fch,
            'interest_is_operating': False,
            'regulated_capital': False,
        }
        _fch_txt = ' / '.join('%sE %+.2f' % (y, v)
                              for y, v in zip(stmt.get('fcff_years') or [], _fch)) or '历史不足'
        inp['data_sources'].append({
            'source': 'Layer 0 前提判别（F10 三表年报，近 3 年报表 FCFF）',
            'items': ['行业类别显式 general（资源/公用行业路由待 NAV 接入）',
                      '报表 FCFF：%s 亿元；负值占比 %s；供前提 A2（负 FCFF≤60%%）判别' % (
                          _fch_txt, ('%.0f%%' % (_fneg * 100)) if _fneg is not None else '历史不足3年')],
        })
    _shares = fin.get('total_shares') or stock.get('total_shares')
    _close = stock.get('close')
    inp['meta']['market_cap'] = (round(_close * _shares, 2)
                                 if (_close and _shares) else None)
    inp['meta']['accounting_standard'] = 'CAS'
    inp['peer_screening'] = _peer_evidence(stock, universe, peers,
                                           str(max(by_year)) if by_year else None, as_of)
    if wacc_pct is not None or tg_pct is not None:
        ov = []
        if wacc_pct is not None:
            inp['financials']['wacc'] = round(float(wacc_pct) / 100, 4)
            ov.append('WACC %.2f%%' % float(wacc_pct))
        if tg_pct is not None:
            inp['financials']['terminal_growth'] = round(float(tg_pct) / 100, 4)
            ov.append('永续增速 %.2f%%' % float(tg_pct))
        inp['data_sources'].append({
            'source': '工作台参数覆盖（人工指定，全批统一）',
            'items': ['%s：显式传入引擎，优先于逐券 CAPM 与行业参数底座' % '、'.join(ov)],
        })
    # ---- 金融路由（v3.30.0）：RIM 主方法 + 可比交叉；DDM 分红口径校验（权重 0）----
    if any(k in ind for k in _FIN_KEYS):
        beta_l, ke = _financial_ke(ind, wacc_params)
        be = dsources.book_equity(code)
        b0 = be.get('book_equity')
        roe_dec = inp['financials'].get('roe')
        # RIM 的 ROE 与 B0 同口径（归母普通股权益）；近 3 年年均平滑周期波动（保险权益收益尤甚）
        hist = be.get('history') or []
        roe_hist = [(h['year'], h['net_profit'] / h['book_equity']) for h in hist
                    if h.get('net_profit') and h.get('book_equity') and h['net_profit'] > 0]
        if roe_hist:
            roe_rim = round(sum(r for _, r in roe_hist) / len(roe_hist), 4)
            roe_years = ('%d–%d' % (roe_hist[-1][0], roe_hist[0][0])
                         if len(roe_hist) > 1 else str(roe_hist[0][0]))
        else:
            roe_rim = round(float(np_) / float(b0), 4) if (b0 and np_ and np_ > 0) else roe_dec
            roe_years = str(be.get('year') or '—')
        payout = 0.30
        inp['preferences']['layer0_check'] = True
        inp['preferences']['method_set_mode'] = 'routed'
        inp['preferences']['four_part_mode'] = False
        inp['meta']['framework_check'] = {
            'industry_class': 'financial',
            'interest_is_operating': True,
            'regulated_capital': True,
            'source': '行业关键词（%s）→ Layer 0 前提 A/B 不成立，引擎路由 RIM/DDM' % ind,
        }
        _fs_items = ['Layer 0 金融路由：DCF 权重 0，候选集 RIM 主 + 可比法（method_set_mode=routed）',
                     'βL %.4f（%s）→ Ke %.2f%%（CAPM：rf 1.9%% + βL×ERP 8.04%%）' % (
                         beta_l, '银行行业β 0.90 再杠杆' if '银行' in ind else '可比β均值再杠杆', ke * 100)]
        if b0 and roe_rim is not None:
            inp['rim'] = {
                'enabled': True,
                'book_value_equity': b0,
                'roe_steady': round(float(roe_rim), 4),
                'cost_of_equity': ke,
                'payout_ratio': payout,
                'persistence': 0.70,
                'explicit_years': 5,
                'note': ('B0=归母普通股权益（F10 年报 BPS×总股本，%s 年）；ROE 取近 3 年年均（%s，各年归母净利/B0）；'
                         'Ke 为 CAPM 股权成本；ω/分红率取 skill 金融底座 0.70/0.30' % (be.get('year') or '—', roe_years)),
            }
            inp['preferences']['enable_rim'] = True
            _fs_items.append('RIM：B0 %.2f 亿元（FY%s，BPS %s × 总股本 %.2f 亿股）、ROE %.2f%%（%s年均 %s）、Ke %.2f%%' % (
                b0, be.get('year') or '—', be.get('bps'), (be.get('total_share') or 0) / 1e8,
                roe_rim * 100, '近 3 年' if len(roe_hist) > 1 else '年报', roe_years, ke * 100))
            if roe_hist:
                _fs_items.append('ROE 逐年：' + ' / '.join('%d %.2f%%' % (yy, rr * 100) for yy, rr in roe_hist))
            if np_ and np_ > 0:
                g1 = max(0.0, min(0.10, round(float(roe_rim) * (1 - payout), 4)))
                g_inf = round(float(tg_pct) / 100, 4) if tg_pct is not None else 0.02
                inp['ddm'] = {
                    'enabled': True,
                    'cost_of_equity': ke,
                    'payout_ratio': payout,
                    'dividend_growth': g1,
                    'terminal_growth': g_inf,
                    'explicit_years': 5,
                }
                inp['preferences']['enable_ddm'] = True
                _fs_items.append('DDM（交叉验证）：D0=归母净利×%.0f%%、g1=ROE×(1−分红率)=%.2f%%、g∞ %.2f%%' % (
                    payout * 100, g1 * 100, g_inf * 100))
        else:
            _fs_items.append('RIM 未启用：B0 缺失（引擎将按剩余权重再归一）')
        inp['data_sources'].append({
            'source': '东财 F10 主要财务指标（年报）+ skill 金融估值口径',
            'items': _fs_items,
        })
    if '银行' in ind:
        inp['data_sources'].append({
            'source': 'skill 行业β表（金融 0.90，再杠杆）',
            'items': ['银行回归β在低波板块退化，按 skill 行业β兜底'],
        })
    elif peer_betas:
        inp['data_sources'].append({
            'source': '腾讯月线（beta_estimator 口径：60 个月 OLS，基准沪深300）',
            'items': ['可比公司 β（截断 [0.5, 2.0]）：%s' % '、'.join(
                '%s %.2f' % (b['code'].split('.')[0], min(max(float(b['raw_beta']), 0.5), 2.0))
                for b in peer_betas)],
        })
    return inp
