# -*- coding: utf-8 -*-
"""公开数据源：东财 datacenter（指数成分/披露财务/一致预期）+ 腾讯行情（实时）。带本地缓存，纯标准库。

缓存目录 runtime/cache（不入 git）。尽力而为：单项失败上抛，由调用方（跑批 worker）决定跳过。
"""
import json
import os
import re
from datetime import datetime, timedelta
import sys
import threading
import time
import urllib.parse
import urllib.request

from config import CACHE, SKILL_DIR

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
EM = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
TENCENT = 'http://qt.gtimg.cn/q='

TTL_COMPONENTS = 6 * 3600
TTL_UNIVERSE = 24 * 3600
TTL_FINANCIALS = 7 * 86400
TTL_QUOTES = 300

sys.path.insert(0, str(SKILL_DIR / 'scripts'))
import fetch_data as fd  # noqa: E402  技能包脚本（datacenter 财务/一致预期，纯标准库）


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def _cache_get(name, ttl, loader):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / ('%s.json' % name)
    if f.exists() and time.time() - f.stat().st_mtime < ttl:
        try:
            return json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            pass
    data = loader()
    # 唯一临时名：并行 worker 会同时回填同一代码（本券+被选为可比），固定 .tmp 会让后写者的 replace 扑空
    tmp = f.with_suffix('.tmp.%d.%d' % (os.getpid(), threading.get_ident()))
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(f)
    return data


def _num(v):
    """push2 数值字段：停牌/缺失时为 '-'，统一转 float 或 None。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


SSE_ST_PREFIX = re.compile(r'^(?:(?:XD|XR|DR))?(?:S)?\*?ST')


def _sse_st_name(name):
    """ST/*ST（兼容 XD/XR/DR 除权除息前缀与历史 S 前缀）。"""
    return bool(SSE_ST_PREFIX.match(str(name or '').upper()))


def _sse_recent_listings(as_of):
    """as_of 前一年内上市的沪市股票 {code: 上市日}；按截止日缓存 2 天。"""
    cut = (datetime.strptime(as_of, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')

    def load():
        out = {}
        page = 1
        while True:
            q = {'reportName': 'RPT_F10_BASIC_ORGINFO',
                 'columns': 'SECUCODE,SECURITY_CODE,LISTING_DATE',
                 'pageSize': '2000', 'pageNumber': str(page),
                 'filter': "(LISTING_DATE>='%s')" % cut,
                 'sortColumns': 'LISTING_DATE', 'sortTypes': '-1'}
            d = _get_json(EM + '?' + urllib.parse.urlencode(q), timeout=90)
            rs = ((d.get('result') or {}).get('data') or [])
            for r in rs:
                if str(r.get('SECUCODE') or '').endswith('.SH'):
                    out[str(r.get('SECURITY_CODE'))] = str(r.get('LISTING_DATE') or '')[:10]
            if len(rs) < 2000:
                break
            page += 1
        return out

    return _cache_get('sse_recent_listings_%s' % cut.replace('-', ''), 2 * 86400, load)


def _sse_components(force=False):
    """上证综指：东财 datacenter 全 A 股估值快照（RPT_VALUEANALYSIS_DET）取沪市 A 股。

    datacenter 成分表不含该指数，改用逐股估值快照合成。按上证综指编制口径：
    总市值加权（A+H 公司计全部股本，单样本 15% 上限，样本均远低于上限）；
    剔除 ST/*ST；新股上市满一年计入，总市值前 10 名满三个月计入（以当前总市值近似日均）。
    as_of 为快照交易日，批跑合成时点位与收盘同口径。
    """
    def load():
        q = {'reportName': 'RPT_VALUEANALYSIS_DET', 'columns': 'TRADE_DATE',
             'pageSize': '1', 'pageNumber': '1', 'sortColumns': 'TRADE_DATE', 'sortTypes': '-1'}
        d = _get_json(EM + '?' + urllib.parse.urlencode(q))
        latest = (((d.get('result') or {}).get('data')) or [{}])[0]
        as_of = str(latest.get('TRADE_DATE') or '')[:10]
        if not as_of:
            raise ValueError('上证综指：估值快照交易日获取失败')
        q = {'reportName': 'RPT_VALUEANALYSIS_DET', 'columns': 'ALL',
             'pageSize': '6000', 'pageNumber': '1',
             'filter': "(TRADE_DATE='%s')" % as_of,
             'sortColumns': 'SECURITY_CODE', 'sortTypes': '1'}
        d = _get_json(EM + '?' + urllib.parse.urlencode(q), timeout=90)
        rows = ((d.get('result') or {}).get('data') or [])
        out = []
        for r in rows:
            sec = str(r.get('SECUCODE') or '')
            if not sec.endswith('.SH'):
                continue
            pe = _num(r.get('PE_TTM'))
            pb = _num(r.get('PB_MRQ'))
            close = _num(r.get('CLOSE_PRICE'))
            total_cap = _num(r.get('TOTAL_MARKET_CAP'))
            if not total_cap:
                total_cap = (_num(r.get('TOTAL_SHARES')) or 0) * (close or 0) or None
            out.append({
                'code': r.get('SECURITY_CODE'),
                'secucode': sec,
                'name': r.get('SECURITY_NAME_ABBR'),
                'industry': r.get('BOARD_NAME'),
                'weight': None,
                'close': close,
                'pe': pe,
                'eps': None,
                'bps': None,
                # 快照无 ROE 字段：PB/PE 推 TTM ROE（同口径近似），供非金融引擎参考
                'roe': round(pb / pe * 100, 4) if (pe and pb and pe > 0 and pb > 0) else None,
                'total_shares': None,
                'free_cap': _num(r.get('NOTLIMITED_MARKETCAP_A')) or total_cap,
                'total_cap': total_cap,
            })
        recent = _sse_recent_listings(as_of)
        cut = (datetime.strptime(as_of, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
        cut3 = (datetime.strptime(as_of, '%Y-%m-%d') - timedelta(days=92)).strftime('%Y-%m-%d')
        top10 = {r['code'] for r in sorted(out, key=lambda x: -(x.get('total_cap') or 0))[:10]}
        st_n = new_n = 0
        members = []
        for r in out:
            if _sse_st_name(r.get('name')):
                st_n += 1
                continue
            ld = recent.get(r['code'])
            if ld and ld > cut:
                if r['code'] in top10 and ld <= cut3:
                    members.append(r)
                else:
                    new_n += 1
                continue
            members.append(r)
        cap_sum = sum(r.get('total_cap') or 0 for r in members)
        if cap_sum > 0:
            for r in members:
                cap = r.get('total_cap') or 0
                r['weight'] = round(cap / cap_sum * 100, 4) if cap else None
        return {'as_of': as_of, 'rows': members, 'weight_computed': bool(members),
                'source': 'datacenter 全A估值快照（沪市 A 股，总市值权重，剔除 ST 与未满计入期新股）',
                'excluded': {'st': st_n, 'new': new_n}}
    return _cache_get('components_sse', 0 if force else TTL_COMPONENTS, load)


def components(itype, force=False):
    """指数成分 + 收盘权重（东财 RPT_INDEX_TS_COMPONENT，MAXTRADEDATE=前一日口径）。"""
    if itype == 'sse':
        return _sse_components(force)
    def load():
        q = {'reportName': 'RPT_INDEX_TS_COMPONENT', 'columns': 'ALL',
             'pageSize': '400', 'filter': '(TYPE="%s")' % itype}
        d = _get_json(EM + '?' + urllib.parse.urlencode(q))
        rows = ((d.get('result') or {}).get('data') or [])
        as_of = max((str(r.get('MAXTRADEDATE') or '')[:10] for r in rows), default='')
        out = []
        for r in rows:
            out.append({
                'code': r.get('SECURITY_CODE'),
                'secucode': r.get('SECUCODE'),
                'name': r.get('SECURITY_NAME_ABBR'),
                'industry': r.get('INDUSTRY'),
                'weight': r.get('WEIGHT'),
                'close': r.get('CLOSE_PRICE'),
                'pe': r.get('PE'),
                'eps': r.get('EPS'),
                'bps': r.get('BPS'),
                'roe': r.get('ROE'),
                'total_shares': r.get('TOTAL_SHARES'),
                'free_cap': r.get('FREE_CAP'),
            })
        weight_computed = bool(out) and all(r.get('weight') is None for r in out)
        if weight_computed:
            # 上证180 等东财不提供 WEIGHT：用自由流通市值归一化近似（口径说明由前端展示）
            cap_sum = sum(r.get('free_cap') or 0 for r in out)
            if cap_sum > 0:
                for r in out:
                    cap = r.get('free_cap') or 0
                    r['weight'] = round(cap / cap_sum * 100, 4) if cap else None
        return {'as_of': as_of, 'rows': out, 'weight_computed': weight_computed}
    return _cache_get('components_%s' % itype, 0 if force else TTL_COMPONENTS, load)


def industry_valuation(force=False):
    """申万二级行业估值（东财 RPT_VALUEINDUSTRY_DET，最新交易日全表）：行业名 → pe/ps/pb 与样本数。"""
    def load():
        q = {'reportName': 'RPT_VALUEINDUSTRY_DET', 'columns': 'ALL',
             'pageSize': '1', 'pageNumber': '1',
             'sortColumns': 'TRADE_DATE', 'sortTypes': '-1'}
        d = _get_json(EM + '?' + urllib.parse.urlencode(q), timeout=60)
        rows = ((d.get('result') or {}).get('data') or [])
        as_of = str(rows[0].get('TRADE_DATE') or '')[:10] if rows else ''
        if not as_of:
            raise ValueError('行业估值：最新交易日获取失败')
        q = {'reportName': 'RPT_VALUEINDUSTRY_DET', 'columns': 'ALL',
             'pageSize': '500', 'pageNumber': '1',
             'filter': "(TRADE_DATE='%s')" % as_of}
        d = _get_json(EM + '?' + urllib.parse.urlencode(q), timeout=60)
        rows = ((d.get('result') or {}).get('data') or [])
        out = {}
        for r in rows:
            name = (r.get('BOARD_NAME') or '').strip()
            if not name:
                continue
            out[name] = {'pe': _num(r.get('PE_TTM')), 'ps': _num(r.get('PS_TTM')),
                         'pb': _num(r.get('PB_MRQ')), 'n': _num(r.get('NUM')),
                         'as_of': as_of}
        return {'as_of': as_of, 'rows': out,
                'source': 'datacenter 申万二级行业估值（东财 RPT_VALUEINDUSTRY_DET，整体法）'}
    return _cache_get('industry_val', 0 if force else TTL_UNIVERSE, load)


def peer_universe(force=False):
    """可比公司全集：全部指数成分并集（按 SECUCODE 去重、保留自由流通市值最大行）。"""
    def load():
        uni = {}
        for t in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13'):
            try:
                c = components(t)
            except Exception:
                continue
            for r in c['rows']:
                code = r.get('secucode')
                if not code:
                    continue
                cur = uni.get(code)
                if cur is None or (r.get('free_cap') or 0) > (cur.get('free_cap') or 0):
                    uni[code] = r
        return {'rows': sorted(uni.values(), key=lambda x: x['secucode'])}
    return _cache_get('peer_universe', 0 if force else TTL_UNIVERSE, load)


def _tcode(secucode):
    """'600519.SH' → 'sh600519'；'000001.SZ' → 'sz000001'；已是前缀原样返回。"""
    c = secucode.strip().lower()
    if c.startswith(('sh', 'sz')):
        return c
    code, _, mkt = c.partition('.')
    return ('sh' if mkt.lower() == 'sh' else 'sz') + code


def tencent_quotes(codes):
    """腾讯批量行情。codes 形如 sh600519/sz000001；返回 {code: {...}}，单项缺失即无该键。"""
    out = {}
    if not codes:
        return out
    for i in range(0, len(codes), 60):
        chunk = codes[i:i + 60]
        try:
            raw = urllib.request.urlopen(TENCENT + ','.join(chunk), timeout=15).read().decode('gbk', 'ignore')
        except Exception:
            continue
        lines = raw.strip().split(';')
        for req_code, line in zip(chunk, lines):
            line = line.strip()
            if not line or '=' not in line:
                continue
            body = line.split('=', 1)[1].strip().strip('"')
            f = body.split('~')
            if len(f) < 6:
                continue
            try:
                item = {
                    'name': f[1],
                    'price': float(f[3]) if f[3] else None,
                    'prev_close': float(f[4]) if f[4] else None,
                }
                if len(f) > 39 and f[39]:
                    item['pe'] = float(f[39])
                if len(f) > 45 and f[45]:
                    item['mktcap_yi'] = float(f[45])
                if len(f) > 46 and f[46]:
                    item['pb'] = float(f[46])
                out[req_code] = item
                out[f[2]] = item
            except (ValueError, IndexError):
                continue
    return out


def index_quote(code='sh000016'):
    """指数点位（腾讯）。价格字段：f3 当前、f4 昨收。"""
    q = tencent_quotes([code]).get(code)
    if not q:
        raise ValueError('指数行情获取失败（%s）' % code)
    return q


def revenue_by_year(code):
    """最近 4 个年报：营收（亿元）与净利率序列（旧→新）；v326 需 ≥4 期反算 3 年 CAGR。失败返回空。"""
    try:
        secu = fd._secucode(code)
        q = {'reportName': 'RPT_LICO_FN_CPD', 'columns': 'ALL',
             'filter': '(SECUCODE="%s")' % secu, 'sortColumns': 'REPORTDATE',
             'sortTypes': '-1', 'pageSize': '20'}
        d = _get_json(EM + '?' + urllib.parse.urlencode(q))
        rows = ((d.get('result') or {}).get('data') or [])
    except Exception:
        return {}, []
    by_year = {}
    margins = []
    for r in rows:
        rd = str(r.get('REPORTDATE') or '')[:10]
        if not rd or rd[5:7] != '12':
            continue
        rev = fd._pick(r, 'TOTAL_OPERATE_INCOME', 'TOTALOPERATEREVE', 'OPERATE_INCOME')
        np_ = fd._pick(r, 'PARENT_NETPROFIT', 'PARENTNETPROFIT', 'NETPROFIT')
        y = rd[:4]
        if y in by_year or rev is None:
            continue
        rev_yi = round(rev / 1e8, 2) or round(rev / 1e8, 6)  # 微营收（<100 万元）保留 6 位，避免序列出现 0 触发引擎零除
        np_yi = round(np_ / 1e8, 2) if np_ is not None else None
        by_year[y] = rev_yi
        if np_yi is not None and rev_yi:
            margins.append(round(np_yi / rev_yi, 4))
        if len(by_year) >= 4:
            break
    by_year = {k: by_year[k] for k in sorted(by_year)}
    return by_year, list(reversed(margins))


TTL_REV = 7 * 86400


def annual_revenue_series(code, force=False):
    """年报营收序列（亿元，旧→新），缓存 7 天；供可比长名单的规模双口径诊断。"""
    key = code.replace('.', '_')

    def load():
        by, _ = revenue_by_year(code)
        return {'by_year': by}

    try:
        return _cache_get('revy_%s' % key, 0 if force else TTL_REV, load)
    except Exception:
        return {'by_year': {}}


def warm_annual_revenue(codes, workers=6):
    """并发预热长名单年报营收缓存，避免并行 worker 重复取数。"""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
        list(ex.map(annual_revenue_series, codes))


# ---- 年报口径现金流（覆盖 fd.fetch_financials 的「最新报告期」口径）----
def _annual_cashflow(code):
    """(OCF, CapEx, 年份)，亿元。现金流量表 12-31 行优先；金融类无该表时退主表年报 OCF（CapEx=None）。"""
    secu = fd._secucode(code)

    def rows(report, size):
        q = {'reportName': report, 'columns': 'ALL', 'filter': '(SECUCODE="%s")' % secu,
             'sortColumns': 'REPORT_DATE', 'sortTypes': '-1', 'pageSize': str(size),
             'source': 'HSF10', 'client': 'PC'}
        d = _get_json(fd.EM_F10_URL + '?' + urllib.parse.urlencode(q))
        return ((d.get('result') or {}).get('data') or [])

    def annual(rs):
        out = {}
        for r in rs:
            rd = str(r.get('REPORT_DATE') or '')
            if rd[5:7] == '12':
                out[rd[:4]] = r
        return out

    try:
        cf = annual(rows('RPT_F10_FINANCE_GCASHFLOW', 12))
        if cf:
            y = max(cf)
            ocf = cf[y].get('NETCASH_OPERATE')
            capex = cf[y].get('CONSTRUCT_LONG_ASSET')
            return (round(ocf / 1e8, 2) if ocf is not None else None,
                    round(capex / 1e8, 2) if capex is not None else None, y)
        main = annual(rows('RPT_F10_FINANCE_MAINFINADATA', 20))
        if main:
            y = max(main)
            ocf = main[y].get('NETCASH_OPERATE_PK')
            if ocf is None:
                ocf = main[y].get('NETCASH_OPERATE')
            return (round(ocf / 1e8, 2) if ocf is not None else None, None, y)
    except Exception:
        pass
    return None, None, None


def financials(code, force=False):
    """披露财务 + 一致预期 + 年报序列（缓存 7 天）。fetch_financials 失败上抛（worker 跳过该券）。"""
    key = code.replace('.', '_')

    def load():
        fin = fd.fetch_financials(code, timeout=25)
        ann_ocf, ann_capex, fy = _annual_cashflow(code)
        if ann_ocf is not None:
            # fd 的 ocf/fcff 取「最新报告期」，capex_implied=OCF−FCFF_FORWARD 混用季报累计与前瞻值；
            # 统一覆盖为年报口径，与营收/净利的年报口径对齐。
            fin['ocf_latest'] = ann_ocf
            fin['capex_implied'] = ann_capex
            fin['cashflow_basis'] = (('FY%s 年报·现金流量表' % fy) if ann_capex is not None
                                     else ('FY%s 年报·OCF（无 capex）' % fy))
        try:
            con = fd.fetch_consensus(code, timeout=25)
        except Exception:
            con = {}
        by_year, margins = revenue_by_year(code)
        return {
            'code': fin.get('code', code),
            'annual_net_profit': fin.get('annual_net_profit'),
            'semiannual_net_profit': fin.get('semiannual_net_profit'),
            'quarterly_net_profit': fin.get('quarterly_net_profit'),
            'latest_report': fin.get('latest_report'),
            'revenue_latest': fin.get('revenue_latest'),
            'ocf_latest': fin.get('ocf_latest'),
            'fcff_latest': fin.get('fcff_latest'),
            'capex_implied': fin.get('capex_implied'),
            'cashflow_basis': fin.get('cashflow_basis'),
            'total_shares': fin.get('total_shares'),
            'consensus': con.get('consensus_net_profit') or {},
            'consensus_org_num': con.get('org_num'),
            'revenue_by_year': by_year,
            'margin_history': margins,
        }
    return _cache_get('fin_%s' % key, 0 if force else TTL_FINANCIALS, load)


# ---- 报表驱动 FCFF（技能 dcf_drivers ① 档：利润表/现金流量表/资产负债表三表联立）----
TTL_STMT = 7 * 86400
_STMT_TAX_LO, _STMT_TAX_HI, _STMT_TAX_DEFAULT = 0.10, 0.25, 0.15


def _stmt_annual(rows):
    out = {}
    for r in rows:
        rd = str(r.get('REPORT_DATE') or '')
        if rd[5:7] == '12':
            out[rd[:4]] = r
    return out


def _stmt_ebit(i):
    """息税前经营利润：营业利润＋财务费用；营业利润缺失时退回利润总额。"""
    eb = i.get('OPERATE_PROFIT')
    if eb is None:
        eb = i.get('TOTAL_PROFIT')
    return (eb + (i.get('FINANCE_EXPENSE') or 0.0)) if eb is not None else None


def _stmt_da(c):
    parts = [c.get(k) for k in ('FA_IR_DEPR', 'IA_AMORTIZE', 'LPE_AMORTIZE')]
    return sum(v for v in parts if v is not None) if any(v is not None for v in parts) else None


def _stmt_nwc(b):
    """经营性净营运资本：含合同负债/预收/预付款/合同资产——负营运资本业务（造船等）不可剔除。"""
    return ((b.get('NOTE_ACCOUNTS_RECE') or 0.0) + (b.get('INVENTORY') or 0.0)
            + (b.get('PREPAYMENT') or 0.0) + (b.get('CONTRACT_ASSET') or 0.0)
            - (b.get('NOTE_ACCOUNTS_PAYABLE') or 0.0) - (b.get('CONTRACT_LIAB') or 0.0)
            - (b.get('ADVANCE_RECEIVABLES') or 0.0) - (b.get('STAFF_SALARY_PAYABLE') or 0.0)
            - (b.get('TAX_PAYABLE') or 0.0))


def _stmt_tax(i):
    """D8 税率规范化：有效税率 ∈ [10%,25%] 用原值，>25% 取 25%，<10% 或缺失取 15%。"""
    tp, tax = i.get('TOTAL_PROFIT'), i.get('INCOME_TAX')
    tax_raw = (tax / tp) if (tax is not None and tp and tp > 0) else None
    if tax_raw is None:
        return _STMT_TAX_DEFAULT, None, '有效税率缺失/利润总额≤0，取 15%'
    if tax_raw < _STMT_TAX_LO:
        return _STMT_TAX_DEFAULT, tax_raw, '有效税率 %.2f%% <10%%，按 D8 取 15%%' % (tax_raw * 100)
    if tax_raw > _STMT_TAX_HI:
        return _STMT_TAX_HI, tax_raw, '有效税率 %.2f%% >25%%，截断为 25%%' % (tax_raw * 100)
    return round(tax_raw, 4), tax_raw, '有效税率 %.2f%%，原值' % (tax_raw * 100)


def statement_drivers(code, force=False):
    """报表驱动 FCFF 基期参数（亿元/小数），技能 dcf_drivers ① 档。

    三表取同一最新年报：营收/EBIT/税率来自利润表，D&A/Capex 来自现金流量表，
    NWC 来自资产负债表。税率按技能 D8 规范化：有效税率 ∈ [10%, 25%] 用原值，
    >25% 取 25%，<10% 或缺失取 15%。失败返回 {}。
    """
    key = code.replace('.', '_')

    def load():
        secu = fd._secucode(code)

        def rows(report, size):
            q = {'reportName': report, 'columns': 'ALL', 'filter': '(SECUCODE="%s")' % secu,
                 'sortColumns': 'REPORT_DATE', 'sortTypes': '-1', 'pageSize': str(size),
                 'source': 'HSF10', 'client': 'PC'}
            d = _get_json(fd.EM_F10_URL + '?' + urllib.parse.urlencode(q))
            return ((d.get('result') or {}).get('data') or [])

        # 24 行 ≈ 6 个年报：latest 之外还需 3 年 FCFF 历史（每年需上年 NWC 作差分）
        inc = _stmt_annual(rows('RPT_F10_FINANCE_GINCOME', 24))
        cf = _stmt_annual(rows('RPT_F10_FINANCE_GCASHFLOW', 24))
        bal = _stmt_annual(rows('RPT_F10_FINANCE_GBALANCE', 24))
        years = sorted(set(inc) & set(cf) & set(bal), reverse=True)
        if not years:
            return {}
        y = years[0]
        i, c, b = inc[y], cf[y], bal[y]
        rev = i.get('TOTAL_OPERATE_INCOME')
        if not rev or rev <= 0:
            return {}
        ebit, capex, da = _stmt_ebit(i), c.get('CONSTRUCT_LONG_ASSET'), _stmt_da(c)
        if ebit is None or capex is None or da is None:
            return {}
        nwc = _stmt_nwc(b)
        tax_rate, tax_raw, tax_note = _stmt_tax(i)
        # 近 3 年报表 FCFF（含 ΔNWC，供 Layer 0 前提 A2「负 FCFF 占比」判别）：
        # 需上年资产负债表作 NWC 差分，故从升序年份的第 2 年起算。
        fcff_hist, fcff_detail = [], []
        for j in range(1, len(sorted(years))):
            asc = sorted(years)
            yy, yp = asc[j], asc[j - 1]
            ii, cc, bb = inc[yy], cf[yy], bal[yy]
            rv = ii.get('TOTAL_OPERATE_INCOME')
            eb, dd, cx = _stmt_ebit(ii), _stmt_da(cc), cc.get('CONSTRUCT_LONG_ASSET')
            if not rv or rv <= 0 or eb is None or dd is None or cx is None:
                continue
            tr, traw, _ = _stmt_tax(ii)
            fcff = ((eb / 1e8) * (1 - tr) + dd / 1e8 - cx / 1e8
                    - (_stmt_nwc(bb) - _stmt_nwc(bal[yp])) / 1e8)
            fcff_hist.append(round(fcff, 2))
            fcff_detail.append({'fy': yy, 'fcff': round(fcff, 2),
                                'tax_rate': round(float(tr), 4),
                                'tax_raw': round(traw, 4) if traw is not None else None})
        fcff_hist, fcff_detail = fcff_hist[-3:], fcff_detail[-3:]
        fcff_neg_ratio = (sum(1 for v in fcff_hist if v < 0) / len(fcff_hist)
                          if len(fcff_hist) >= 3 else None)
        history = []
        for yy in years[:3]:
            ii, cc, bb = inc[yy], cf[yy], bal[yy]
            rv = ii.get('TOTAL_OPERATE_INCOME')
            if not rv or rv <= 0:
                continue
            eb, dd, cx, nw = _stmt_ebit(ii), _stmt_da(cc), cc.get('CONSTRUCT_LONG_ASSET'), _stmt_nwc(bb)
            history.append({
                'fy': yy,
                'revenue': round(rv / 1e8, 2),
                'ebit_margin': round(eb / rv, 4) if eb is not None else None,
                'da_to_revenue': round(dd / rv, 4) if dd is not None else None,
                'capex_to_revenue': round(cx / rv, 4) if cx is not None else None,
                'nwc_to_revenue': round(nw / rv, 4),
            })
        return {
            'fy': y,
            'revenue': round(rev / 1e8, 2),
            'ebit': round(ebit / 1e8, 2),
            'ebit_margin': round(ebit / rev, 4),
            'da': round(da / 1e8, 2),
            'da_to_revenue': round(da / rev, 4),
            'capex': round(capex / 1e8, 2),
            'capex_to_revenue': round(capex / rev, 4),
            'nwc': round(nwc / 1e8, 2),
            'nwc_to_revenue': round(nwc / rev, 4),
            'tax_raw': round(tax_raw, 4) if tax_raw is not None else None,
            'tax_rate': round(float(tax_rate), 4),
            'tax_note': tax_note,
            'history': history,
            'fcff_history': fcff_hist,
            'fcff_years': [d['fy'] for d in fcff_detail],
            'fcff_neg_ratio': round(fcff_neg_ratio, 3) if fcff_neg_ratio is not None else None,
            'fcff_detail': fcff_detail,
            'definitions': {
                'ebit': '营业利润＋财务费用（营业利润缺失时用利润总额）',
                'da': '固定资产折旧＋无形资产摊销＋长期待摊费用摊销',
                'capex': '购建固定资产、无形资产和其他长期资产支付的现金',
                'nwc': '应收票据及应收账款＋存货＋预付款项＋合同资产−应付票据及应付账款−合同负债−预收款项−应付职工薪酬−应交税费',
            },
        }

    try:
        # v2：payload 增 fcff_history/fcff_neg_ratio（Layer 0 前提 A2），旧 stmt_ 缓存无该字段
        return _cache_get('stmt_v2_%s' % key, 0 if force else TTL_STMT, load)
    except Exception:
        return {}


# ---- 质量五指标 + ROIC（SKILL Step 2 S2.2 / v3.26.0 第二维；缺失给 None 由引擎按缺失处理）----
TTL_QUALITY = 7 * 86400
_FIN_INDUSTRIES = ('银行', '保险', '证券', '多元金融')


def _qd_annual(rows):
    out = {}
    for r in rows:
        rd = str(r.get('REPORT_DATE') or '')
        if rd[5:7] == '12':
            out[rd[:4]] = r
    return out


def quality_details(code, industry='', force=False):
    """OCF/净利、毛利率3年趋势(pp)、应收/营收、商誉/归母净资产、非经常性损益占比、ROIC（小数）。
    金融类（银行/保险/证券/多元金融）报表模板不同且毛利率/应收/商誉无经济含义，五项显式 null；
    ROIC 仍按 F10 主表返回（生命周期第二维 ROIC−WACC 需要）。"""
    keys = ('ocf_to_net_profit', 'gross_margin_trend_pp', 'receivables_to_revenue',
            'goodwill_ratio', 'nonrecurring_ratio')
    fin_ind = any(k in (industry or '') for k in _FIN_INDUSTRIES)
    key = code.replace('.', '_')

    def load():
        secu = fd._secucode(code)

        def rows(report, size):
            q = {'reportName': report, 'columns': 'ALL', 'filter': '(SECUCODE="%s")' % secu,
                 'sortColumns': 'REPORT_DATE', 'sortTypes': '-1', 'pageSize': str(size),
                 'source': 'HSF10', 'client': 'PC'}
            d = _get_json(fd.EM_F10_URL + '?' + urllib.parse.urlencode(q))
            return ((d.get('result') or {}).get('data') or [])

        main = _qd_annual(rows('RPT_F10_FINANCE_MAINFINADATA', 24))
        y = max(main) if main else None
        roic = (round(main[y]['ROIC'] / 100.0, 4)
                if y and main[y].get('ROIC') is not None else None)
        out = {k: None for k in keys}
        out.update({'year': y, 'roic': roic})
        if fin_ind or not y:
            return out
        bal = _qd_annual(rows('RPT_F10_FINANCE_GBALANCE', 24))
        cf = _qd_annual(rows('RPT_F10_FINANCE_GCASHFLOW', 8))
        years = sorted(set(main) & set(bal) & set(cf), reverse=True)
        if not years:
            return out
        y = years[0]
        m, b, c = main[y], bal[y], cf[y]
        np_ = m.get('PARENTNETPROFIT')
        rev = m.get('TOTALOPERATEREVE')
        eq = b.get('TOTAL_PARENT_EQUITY') or b.get('TOTAL_EQUITY')
        y3 = str(int(y) - 3)
        out.update({
            'year': y,
            'ocf_to_net_profit': (round(c['NETCASH_OPERATE'] / np_, 3)
                                  if c.get('NETCASH_OPERATE') is not None and np_ and np_ > 0 else None),
            'gross_margin_trend_pp': (round(m['XSMLL'] - main[y3]['XSMLL'], 2)
                                      if y3 in main and m.get('XSMLL') is not None
                                      and main[y3].get('XSMLL') is not None else None),
            'receivables_to_revenue': (round((b.get('ACCOUNTS_RECE') or 0.0) / rev, 4)
                                       if rev else None),
            'goodwill_ratio': (round((b.get('GOODWILL') or 0.0) / eq, 4)
                               if eq and eq > 0 else None),
            'nonrecurring_ratio': (round((np_ - m['KCFJCXSYJLR']) / abs(np_), 4)
                                   if np_ and m.get('KCFJCXSYJLR') is not None else None),
        })
        return out

    try:
        return _cache_get('qd_%s' % key, 0 if force else TTL_QUALITY, load)
    except Exception:
        return {}


# ---- 归母普通股权益 B0（RIM 金融路由；F10 年报 BPS × 总股本，单位亿元）----
TTL_BOOK = 7 * 86400


def book_equity(code, force=False):
    """归母普通股权益 B0（亿元）：F10 主要财务指标年报 BPS × TOTAL_SHARE / 1e8。
    银行 GBALANCE 表不可用（返回 0 行）；TOTAL_EQUITY_PK 含少数股东与其他权益工具，不作 B0。"""
    key = code.replace('.', '_')

    def load():
        secu = fd._secucode(code)
        q = {'reportName': 'RPT_F10_FINANCE_MAINFINADATA', 'columns': 'ALL',
             'filter': '(SECUCODE="%s")' % secu,
             'sortColumns': 'REPORT_DATE', 'sortTypes': '-1', 'pageSize': '24',
             'source': 'HSF10', 'client': 'PC'}
        d = _get_json(fd.EM_F10_URL + '?' + urllib.parse.urlencode(q))
        rows = ((d.get('result') or {}).get('data') or [])
        main = _qd_annual(rows)
        y = max(main) if main else None
        if not y:
            return {'book_equity': None, 'year': None, 'history': []}
        r = main[y]
        bps, sh = r.get('BPS'), r.get('TOTAL_SHARE')
        # 近 3 年年报（B0 与归母净利同口径），供输入侧做 ROE 三年平滑
        hist = []
        for yy in sorted(main, reverse=True):
            rr = main[yy]
            bps_i, sh_i, np_i = rr.get('BPS'), rr.get('TOTAL_SHARE'), rr.get('PARENTNETPROFIT')
            if bps_i and sh_i:
                hist.append({'year': int(yy),
                             'book_equity': round(float(bps_i) * float(sh_i) / 1e8, 2),
                             'net_profit': round(float(np_i) / 1e8, 2) if np_i is not None else None})
            if len(hist) >= 3:
                break
        if bps is None or not sh:
            return {'book_equity': None, 'year': y, 'bps': bps, 'total_share': sh, 'history': hist}
        return {'book_equity': round(float(bps) * float(sh) / 1e8, 2),
                'year': y, 'bps': float(bps), 'total_share': float(sh), 'history': hist}

    try:
        return _cache_get('book3_%s' % key, 0 if force else TTL_BOOK, load)
    except Exception:
        return {'book_equity': None}


# ---- 可比公司 β（SKILL beta_estimator 口径：60 个月月收益 OLS，基准沪深300；月线取腾讯前复权）----
TTL_BETA = 7 * 86400
_BETA_BENCH = 'sh000300'
_BETA_SRC = '腾讯月线（前复权）'


def _month_close(tcode, months):
    """腾讯月线收盘价（前复权；指数无复权字段）。返回 [(date, close)] 升序。"""
    url = ('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,month,,,%d,qfq'
           % (tcode, months))
    d = _get_json(url)
    node = (d.get('data') or {}).get(tcode) or {}
    rows = node.get('qfqmonth') or node.get('month') or []
    out = []
    for r in rows:
        try:
            out.append((str(r[0])[:10], float(r[2])))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def beta_estimate(code, months=60, force=False):
    """单券股权 β（月收益 OLS，raw_beta）；样本不足/失败返回 {}。缓存 7 天。
    口径对齐 SKILL beta_estimator（60 个月、基准沪深300、简单月收益 OLS）；
    数据源为腾讯月线：东财 push2his kline 在本机网络不可达（RemoteDisconnected）。"""
    def load():
        bench = _cache_get('beta_bench_%d' % months, 0 if force else TTL_BETA,
                           lambda: [p for _, p in _month_close(_BETA_BENCH, months)])
        prices = [p for _, p in _month_close(_tcode(code), months)]
        rets = [prices[i] / prices[i - 1] - 1.0
                for i in range(1, len(prices)) if prices[i - 1] > 0]
        bench_rets = [bench[i] / bench[i - 1] - 1.0
                      for i in range(1, len(bench)) if bench[i - 1] > 0]
        if len(rets) < 24 or len(bench_rets) < 24:
            return {}
        n = min(len(rets), len(bench_rets))
        xs, ys = bench_rets[-n:], rets[-n:]
        mx, my = sum(xs) / n, sum(ys) / n
        den = sum((x - mx) ** 2 for x in xs)
        if den == 0:
            return {}
        b = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den
        a = my - b * mx
        ss_tot = sum((y - my) ** 2 for y in ys)
        ss_res = sum((ys[i] - (a + b * xs[i])) ** 2 for i in range(n))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
        return {'code': code, 'raw_beta': round(b, 3), 'r2': round(r2, 3) if r2 is not None else None,
                'n': n, 'benchmark': 'SH000300', 'months': months, 'source': _BETA_SRC}
    try:
        return _cache_get('beta_%s_%d' % (code.replace('.', '_'), months),
                          0 if force else TTL_BETA, load)
    except Exception:
        return {}


def comparable_betas(codes, months=60):
    """可比公司 β 明细（raw_beta）；失败/样本不足的券跳过。"""
    out = []
    for c in codes:
        rec = beta_estimate(c, months)
        if rec.get('raw_beta') is not None:
            out.append(rec)
    return out
