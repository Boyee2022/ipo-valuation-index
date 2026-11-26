# -*- coding: utf-8 -*-
"""第 7 步（b）：金融 RIM/DDM 路由——跑批侧（B0 数据源 + 输入组装 + 参数面板）。

1) dsources.book_equity()：F10 年报 BPS × TOTAL_SHARE / 1e8 = 归母普通股权益（亿元）；
   银行 GBALANCE 不可用、TOTAL_EQUITY_PK 含少数股东/其他权益工具 → 都不用。
2) input_builder：金融行业（银行/保险/证券/券商/金融）自动挂 Layer 0 路由：
   layer0_check=true、method_set_mode=routed、four_part_mode=false、
   meta.framework_check.industry_class=financial、显式 rim/ddm 块（Ke = CAPM）。
3) ParamsCard：补一行「金融类方法」。

用法：
    python3 step7b_workbench.py ~/workspace/valuation-workbench [--dry-run]
幂等；改前备份 .bak.<时间戳>。
"""
import shutil
import sys
import time
from pathlib import Path


def rep(src, old, new, tag):
    if src.count(old) != 1:
        sys.exit('[%s] 锚点缺失或多处命中（found %d）' % (tag, src.count(old)))
    return src.replace(old, new, 1)


# ---------------------------- dsources.py ----------------------------
DS_ANCHOR = '''# ---- 可比公司 β（SKILL beta_estimator 口径：60 个月月收益 OLS，基准沪深300；月线取腾讯前复权）----
'''
DS_NEW = '''# ---- 归母普通股权益 B0（RIM 金融路由；F10 年报 BPS × 总股本，单位亿元）----
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
            return {'book_equity': None, 'year': None}
        r = main[y]
        bps, sh = r.get('BPS'), r.get('TOTAL_SHARE')
        if bps is None or not sh:
            return {'book_equity': None, 'year': y, 'bps': bps, 'total_share': sh}
        return {'book_equity': round(float(bps) * float(sh) / 1e8, 2),
                'year': y, 'bps': float(bps), 'total_share': float(sh)}

    try:
        return _cache_get('book_%s' % key, 0 if force else TTL_BOOK, load)
    except Exception:
        return {'book_equity': None}


''' + DS_ANCHOR

# ---------------------------- input_builder.py ----------------------------
IB_ANCHOR = '''    if '银行' in ind:
        inp['data_sources'].append({
            'source': 'skill 行业β表（金融 0.90，再杠杆）',
'''

IB_NEW = '''    # ---- 金融路由（v3.30.0）：RIM 主方法 + 可比交叉；DDM 分红口径校验（权重 0）----
    if any(k in ind for k in _FIN_KEYS):
        beta_l, ke = _financial_ke(ind, wacc_params)
        be = dsources.book_equity(code)
        b0 = be.get('book_equity')
        roe_dec = inp['financials'].get('roe')
        if roe_dec is None and b0 and np_:
            roe_dec = round(np_ / b0, 4)
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
        if b0 and roe_dec is not None:
            inp['rim'] = {
                'enabled': True,
                'book_value_equity': b0,
                'roe_steady': round(float(roe_dec), 4),
                'cost_of_equity': ke,
                'payout_ratio': payout,
                'persistence': 0.70,
                'explicit_years': 5,
                'note': ('B0=归母普通股权益（F10 年报 BPS×总股本，%s 年）；ROE 取最近年报；'
                         'Ke 为 CAPM 股权成本；ω/分红率取 skill 金融底座 0.70/0.30' % (be.get('year') or '—')),
            }
            inp['preferences']['enable_rim'] = True
            _fs_items.append('RIM：B0 %.2f 亿元（FY%s，BPS %s × 总股本 %.2f 亿股）、ROE %.2f%%、Ke %.2f%%' % (
                b0, be.get('year') or '—', be.get('bps'), (be.get('total_share') or 0) / 1e8,
                roe_dec * 100, ke * 100))
            if np_ and np_ > 0:
                g1 = max(0.0, min(0.10, round(float(roe_dec) * (1 - payout), 4)))
                inp['ddm'] = {
                    'enabled': True,
                    'cost_of_equity': ke,
                    'payout_ratio': payout,
                    'dividend_growth': g1,
                    'terminal_growth': 0.02,
                    'explicit_years': 5,
                }
                inp['preferences']['enable_ddm'] = True
                _fs_items.append('DDM（交叉验证）：D0=归母净利×%.0f%%、g1=ROE×(1−分红率)=%.2f%%、g∞ 2.00%%' % (
                    payout * 100, g1 * 100))
        else:
            _fs_items.append('RIM 未启用：B0 缺失（引擎将按剩余权重再归一）')
        inp['data_sources'].append({
            'source': '东财 F10 主要财务指标（年报）+ skill 金融估值口径',
            'items': _fs_items,
        })
''' + IB_ANCHOR

IB_TOP_ANCHOR = '''PEER_N = 4
'''
IB_TOP_NEW = '''PEER_N = 4

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
'''

# ---------------------------- ParamsCard.tsx ----------------------------
PC_ANCHOR = '''        <div className={css.kv}><span className={css.kvK}>永续增长率</span><span className={css.kvV}>2.0% 起，逐券校准</span></div>
'''
PC_NEW = PC_ANCHOR + '''        <div className={css.kv}><span className={css.kvK}>金融类方法</span><span className={css.kvV}>RIM 主 + 可比（DDM 交叉）</span></div>
'''


def patch_dsources(root, dry=False):
    f = root / 'packages/batch/dsources.py'
    src = f.read_text(encoding='utf-8')
    if 'def book_equity' in src:
        print('dsources: already patched')
        return
    out = rep(src, DS_ANCHOR, DS_NEW, 'dsources')
    if dry:
        print('dsources dry-run ok')
        return
    ts = time.strftime('%Y%m%d_%H%M%S')
    shutil.copy2(f, f.with_suffix(f.suffix + '.bak.%s' % ts))
    f.write_text(out, encoding='utf-8')
    print('dsources patched (backup .bak.%s)' % ts)


def patch_input(root, dry=False):
    f = root / 'packages/batch/input_builder.py'
    src = f.read_text(encoding='utf-8')
    if '_financial_ke' in src:
        print('input_builder: already patched')
        return
    out = rep(src, IB_TOP_ANCHOR, IB_TOP_NEW, 'ib_top')
    out = rep(out, IB_ANCHOR, IB_NEW, 'ib_fin')
    if dry:
        print('input_builder dry-run ok')
        return
    ts = time.strftime('%Y%m%d_%H%M%S')
    shutil.copy2(f, f.with_suffix(f.suffix + '.bak.%s' % ts))
    f.write_text(out, encoding='utf-8')
    print('input_builder patched (backup .bak.%s)' % ts)


def patch_panel(root, dry=False):
    f = root / 'packages/workbench/src/client/page/parts/ParamsCard.tsx'
    src = f.read_text(encoding='utf-8')
    if '金融类方法' in src:
        print('ParamsCard: already patched')
        return
    out = rep(src, PC_ANCHOR, PC_NEW, 'panel')
    if dry:
        print('ParamsCard dry-run ok')
        return
    ts = time.strftime('%Y%m%d_%H%M%S')
    shutil.copy2(f, f.with_suffix(f.suffix + '.bak.%s' % ts))
    f.write_text(out, encoding='utf-8')
    print('ParamsCard patched (backup .bak.%s)' % ts)


if __name__ == '__main__':
    root = Path(sys.argv[1]).expanduser()
    dry = '--dry-run' in sys.argv
    patch_dsources(root, dry)
    patch_input(root, dry)
    patch_panel(root, dry)
    print('done')