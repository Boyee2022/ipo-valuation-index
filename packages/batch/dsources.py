# -*- coding: utf-8 -*-
"""公开数据源：东财 datacenter（指数成分/披露财务/一致预期）+ 腾讯行情（实时）。带本地缓存，纯标准库。

缓存目录 runtime/cache（不入 git）。尽力而为：单项失败上抛，由调用方（跑批 worker）决定跳过。
"""
import json
import sys
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
    tmp = f.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(f)
    return data


def components(itype, force=False):
    """指数成分 + 收盘权重（东财 RPT_INDEX_TS_COMPONENT，MAXTRADEDATE=前一日口径）。"""
    def load():
        q = {'reportName': 'RPT_INDEX_TS_COMPONENT', 'columns': 'ALL',
             'pageSize': '300', 'filter': '(TYPE="%s")' % itype}
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
        return {'as_of': as_of, 'rows': out}
    return _cache_get('components_%s' % itype, 0 if force else TTL_COMPONENTS, load)


def peer_universe(force=False):
    """可比公司全集：全部指数成分并集（按 SECUCODE 去重、保留自由流通市值最大行）。"""
    def load():
        uni = {}
        for t in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10'):
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
    """最近 3 个年报：营收/归母净利（亿元）与净利率序列（旧→新）。失败返回空。"""
    try:
        secu = fd._secucode(code)
        q = {'reportName': 'RPT_LICO_FN_CPD', 'columns': 'ALL',
             'filter': '(SECUCODE="%s")' % secu, 'sortColumns': 'REPORTDATE',
             'sortTypes': '-1', 'pageSize': '16'}
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
        rev_yi = round(rev / 1e8, 2) if abs(rev) > 1e6 else rev
        np_yi = round(np_ / 1e8, 2) if np_ is not None and abs(np_) > 1e6 else np_
        by_year[y] = rev_yi
        if np_yi is not None and rev_yi:
            margins.append(round(np_yi / rev_yi, 4))
        if len(by_year) >= 3:
            break
    by_year = {k: by_year[k] for k in sorted(by_year)}
    return by_year, list(reversed(margins))


def financials(code, force=False):
    """披露财务 + 一致预期 + 年报序列（缓存 7 天）。fetch_financials 失败上抛（worker 跳过该券）。"""
    key = code.replace('.', '_')

    def load():
        fin = fd.fetch_financials(code, timeout=25)
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
            'total_shares': fin.get('total_shares'),
            'consensus': con.get('consensus_net_profit') or {},
            'consensus_org_num': con.get('org_num'),
            'revenue_by_year': by_year,
            'margin_history': margins,
        }
    return _cache_get('fin_%s' % key, 0 if force else TTL_FINANCIALS, load)
