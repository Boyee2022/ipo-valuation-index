"""fetch_data.py — 公开行情/财务/一致预期数据拉取脚本（llm-ipo-valuation v3.12，D2b）

定位：技能内**独立可选工具**（不进引擎主链）。用纯标准库（urllib）拉取东方财富
公开接口的实时行情与估值倍数（PE/PB/PS/市值）及财务/一致预期数据，供 LLM 填充
输入模板的 comparables / industry_index / financials（net_profit_basis 披露档）等字段，
减少手工检索。

v3.12 新增（三步数据源优先级优化·数据采集侧）：
- fetch_financials(code)：归母净利（年度/单季/半年度按最新报告期识别）+ 经营现金流净额 + FCFF + 总股本
  （RPT_LICO_FN_CPD 业绩报表 + RPT_F10_FINANCE_MAINFINADATA 主要指标）
- fetch_consensus(code)：一致预期归母净利 = EPS × 总股本（RPT_WEB_RESPREDICT 机构预测）
- main 增 --financials / --consensus 开关

设计约束：
- 纯标准库（Python 3.8+），无第三方依赖——与技能"纯标准库"红线一致；
- **尽力而为**模式：网络失败/接口变更/解析异常时输出明确错误与手动填写建议，
  退出码非 0，不阻断估值主流程；
- 数据时点以接口返回为准（as_of），使用时须在报告中标注来源与日期；
- 若接口返回"-"或 None，对应字段输出 null（留待人工核实）。

用法：
  python fetch_data.py 688836.SH [-o fetch_result.json]
  python fetch_data.py 603448 [-o fetch_result.json]      # 自动识别市场
  python fetch_data.py 301699.SZ --fields price,pe,pb,ps,mktcap
  python fetch_data.py 688825.SH --financials             # 财务披露档（净利/OCF/FCFF/股本）
  python fetch_data.py 688825.SH --consensus              # 一致预期净利（EPS×股本）
  python fetch_data.py 688825.SH --all                    # 行情+财务+一致预期

数据源：东方财富公开接口（push2 行情 / datacenter 业绩与机构预测，公开免费，无鉴权）。
字段口径：PE(TTM)/PB/PS 为静态或动态口径，仅作参考，正式估值须以财报为准。
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone


EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
FIELDS_DEFAULT = "f43,f57,f58,f59,f162,f167,f164,f116,f117,f60,f168"
# f43 最新价 | f57 代码 | f58 名称 | f59 价格精度 | f162 PE(TTM) | f167 PB
# f164 PE(静) | f116 总市值 | f117 流通市值 | f60 昨收 | f168 换手率

# v3.12：datacenter 财务/一致预期接口（Plan 阶段 WebFetch 实测可用，返回真实数据）
EM_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EM_F10_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
EM_REPORT_FINANCE = "RPT_LICO_FN_CPD"              # 业绩报表（归母净利/营收/每股经营现金流）
EM_REPORT_F10 = "RPT_F10_FINANCE_MAINFINADATA"     # F10 主要指标（OCF 净额/FCFF/总股本）
EM_REPORT_CONSENSUS = "RPT_WEB_RESPREDICT"         # 机构一致预期（EPS/机构数/目标价）

UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://data.eastmoney.com/",
}


def _market_prefix(code):
    """按代码段推断东财 secid 市场前缀（v3.11 修订 2d 扩展海外）：
    A 股沪市 1./深市北交所 0.；美股 US. 前缀 → 105.；港股 HK/后缀.HK → 116.；
    韩股（.KS 等）暂不支持自动拉取（返回 None 由调用方提示手动输入）。"""
    c = code.strip()
    up = c.upper()
    if up.startswith("US."):
        return "105." + up[3:]
    if up.endswith(".US"):
        return "105." + up[:-3]
    if up.startswith("HK"):
        return "116." + up[2:]
    if c.endswith(".HK"):
        return "116." + c[:-3]
    if c.endswith((".KS", ".KSQ", ".KQ", ".T")):
        return None  # 韩股/日股暂不支持
    c6 = c.split(".")[0].zfill(6)
    if c6.startswith(("6", "9")):
        return "1." + c6
    return "0." + c6


def _norm(v):
    """东财返回的 '-' / None → None；数值转 float。"""
    if v is None or v == "-" or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_quote(code, fields=None, timeout=10):
    """拉取单只标的行情。返回 dict（含 source/as_of）；失败抛异常由调用方处理。"""
    secid = _market_prefix(code)
    if secid is None:
        raise ValueError(f"市场暂不支持自动拉取（{code}：韩股/日股请使用 ADR 代码或手动输入估值倍数）")
    params = {
        "secid": secid,
        "fields": fields or FIELDS_DEFAULT,
        "fltt": "2",   # 价格小数位
        "invt": "2",   # 保留两位小数
    }
    url = EASTMONEY_QUOTE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://quote.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    data = (raw or {}).get("data") or {}
    if not data:
        raise ValueError(f"接口未返回数据（secid={secid}），请核实代码或稍后重试")

    price = _norm(data.get("f43"))  # fltt=2 已返回格式化浮点（无需再除 f59 精度）

    mktcap = _norm(data.get("f116"))          # 总市值（元）
    pe_ttm = _norm(data.get("f162"))
    pb = _norm(data.get("f167"))
    ps = None
    if mktcap is not None and price is not None:
        # PS 需营收数据，接口不直接给 → 留空（LLM 用财务数据补充）
        ps = None
    return {
        "code": str(data.get("f57") or code),
        "name": str(data.get("f58") or ""),
        "price": price,
        "pe_ttm": pe_ttm,
        "pb": pb,
        "ps_ttm": ps,
        "mktcap_billion": round(mktcap / 1e8, 2) if mktcap is not None else None,  # 亿元
        "prev_close": _norm(data.get("f60")),
        "turnover_pct": _norm(data.get("f168")),
        "source": "eastmoney push2（公开行情接口）",
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "PE/PB 为接口实时口径（TTM/静态）；PS 需营收数据请另行补充；数据仅供填充输入模板参考，正式估值以财报为准",
    }


def _dc_get(url_base, params, timeout=10):
    """datacenter 接口通用请求：返回 result 列表（尽力而为，异常上抛由调用方处理）。"""
    url = url_base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    result = ((raw or {}).get("result") or {})
    data = result.get("data") if isinstance(result, dict) else None
    if not data:
        raise ValueError(f"接口未返回数据（reportName={params.get('reportName')}），请核实代码或稍后重试")
    return data


def _secucode(code):
    """代码 → SECUCODE 格式（688825 → 688825.SH / 000001 → 000001.SZ）。"""
    c = code.strip().upper()
    if "." in c:
        return c
    c6 = c.zfill(6)
    return c6 + (".SH" if c6.startswith(("6", "9")) else ".SZ")


def _pick(row, *keys):
    """按候选键顺序取首个非空值（接口字段名容错）。"""
    for k in keys:
        v = row.get(k) if isinstance(row, dict) else None
        if v is not None and v != "-" and v != "":
            return _norm(v)
    return None


def fetch_financials(code, timeout=10):
    """拉取披露财务（v3.12 净利披露档）：归母净利（按最新报告期识别 年度/单季/半年度）
    + 营收 + 经营现金流净额 + FCFF + 总股本。
    RPT_LICO_FN_CPD（业绩报表，近 8 期）+ RPT_F10_FINANCE_MAINFINADATA（主要指标）。
    返回 dict（含 source/as_of）；任一接口失败抛异常由调用方处理（尽力而为）。"""
    secu = _secucode(code)
    filt = f'(SECUCODE="{secu}")'
    fin_rows = _dc_get(EM_DATACENTER_URL, {
        "reportName": EM_REPORT_FINANCE, "columns": "ALL", "filter": filt,
        "sortColumns": "REPORTDATE", "sortTypes": "-1", "pageSize": "8",
    }, timeout)
    f10_rows = _dc_get(EM_F10_URL, {
        "reportName": EM_REPORT_F10, "columns": "ALL", "filter": filt,
        "pageSize": "8", "source": "HSF10", "client": "PC",
    }, timeout)

    out = {"code": secu, "annual_net_profit": None, "quarterly_net_profit": None,
           "semiannual_net_profit": None, "latest_report": None,
           "revenue_latest": None, "ocf_latest": None, "fcff_latest": None,
           "capex_implied": None, "total_shares": None}
    # 业绩报表：按最新报告期识别档位（QDATE/REPORTDATE 月份）
    latest = None
    for r in fin_rows:
        rd = str(r.get("REPORTDATE") or r.get("QDATE") or "")
        if not rd:
            continue
        if latest is None:
            latest = rd
            out["latest_report"] = rd[:10]
            np_ = _pick(r, "PARENT_NETPROFIT", "PARENTNETPROFIT", "NETPROFIT")
            rev = _pick(r, "TOTAL_OPERATE_INCOME", "TOTALOPERATEREVE", "OPERATE_INCOME")
            if np_ is not None:
                mm = rd[5:7] if len(rd) >= 7 else ""
                if mm == "12":
                    out["annual_net_profit"] = round(np_ / 1e8, 2) if abs(np_) > 1e6 else np_
                elif mm == "06":
                    out["semiannual_net_profit"] = round(np_ / 1e8, 2) if abs(np_) > 1e6 else np_
                elif mm == "03":
                    out["quarterly_net_profit"] = round(np_ / 1e8, 2) if abs(np_) > 1e6 else np_
                elif mm == "09":
                    out["latest_report"] = rd[:10] + "（三季报累计，未直接年化）"
            if rev is not None:
                out["revenue_latest"] = round(rev / 1e8, 2) if abs(rev) > 1e6 else rev
        # 最近一份年报（若最新期非年报）
        rd_mm = rd[5:7] if len(rd) >= 7 else ""
        if rd_mm == "12" and out["annual_net_profit"] is None:
            np_ = _pick(r, "PARENT_NETPROFIT", "PARENTNETPROFIT", "NETPROFIT")
            if np_ is not None:
                out["annual_net_profit"] = round(np_ / 1e8, 2) if abs(np_) > 1e6 else np_
    # F10 主要指标：OCF 净额/FCFF/总股本（取最新一条非空）
    for r in f10_rows:
        ocf = _pick(r, "NETCASH_OPERATE_PK", "NETCASH_OPERATE")
        fcff = _pick(r, "FCFF_FORWARD", "FCFF")
        ts = _pick(r, "TOTAL_SHARE", "TOTALSHARE")
        if ocf is not None and out["ocf_latest"] is None:
            out["ocf_latest"] = round(ocf / 1e8, 2) if abs(ocf) > 1e6 else ocf
        if fcff is not None and out["fcff_latest"] is None:
            out["fcff_latest"] = round(fcff / 1e8, 2) if abs(fcff) > 1e6 else fcff
        if ts is not None and out["total_shares"] is None:
            out["total_shares"] = round(ts / 1e8, 2) if abs(ts) > 1e6 else ts
    # CapEx 隐含值 = OCF − FCFF（简化，忽略 ΔWC；供 capex_latest 参考）
    if out["ocf_latest"] is not None and out["fcff_latest"] is not None:
        out["capex_implied"] = round(out["ocf_latest"] - out["fcff_latest"], 2)
    out["source"] = f"eastmoney datacenter（{EM_REPORT_FINANCE}+{EM_REPORT_F10}，公开披露）"
    out["as_of"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["note"] = ("归母净利/营收按最新报告期档位识别（12-31=年度、06-30=半年度、03-31=单季，单位亿元）；"
                   "ocf/fcff/股本来自 F10 主要指标；capex_implied=OCF−FCFF 供参考。"
                   "年化口径（季度×4/半年度×2）由引擎 net_profit_basis 档位处理，报告须标注报告期与口径")
    return out


def fetch_consensus(code, timeout=10):
    """拉取机构一致预期（v3.12 净利披露档·市场预期）：2026E-2028E EPS × 总股本 → 一致预期归母净利。
    RPT_WEB_RESPREDICT；EPS 口径，净利 = EPS × TOTAL_SHARE（股本口径须在报告标注）。"""
    secu = _secucode(code)
    filt = f'(SECUCODE="{secu}")'
    rows = _dc_get(EM_DATACENTER_URL, {
        "reportName": EM_REPORT_CONSENSUS, "columns": "ALL", "filter": filt,
        "pageSize": "10",
    }, timeout)
    out = {"code": secu, "consensus_net_profit": {}, "org_num": None, "target_price": None}
    shares = None
    try:
        f10 = _dc_get(EM_F10_URL, {
            "reportName": EM_REPORT_F10, "columns": "ALL", "filter": filt,
            "pageSize": "4", "source": "HSF10", "client": "PC",
        }, timeout)
        for r in f10:
            ts = _pick(r, "TOTAL_SHARE", "TOTALSHARE")
            if ts is not None and shares is None:
                shares = ts / 1e8 if abs(ts) > 1e6 else ts
                break
    except Exception:
        shares = None
    row = rows[0] if rows else {}
    for yr in ("2", "3", "4"):
        # YEAR_MARK{yr}=E 表示预期年（A=实际），EPS{yr} 为一致预期 EPS（元/股）
        eps = _pick(row, f"EPS{yr}")
        mark = row.get(f"YEAR_MARK{yr}") if isinstance(row, dict) else None
        if eps is not None and str(mark).upper() == "E":
            ylabel = {2: "2026E", 3: "2027E", 4: "2028E"}[int(yr)]
            out["consensus_net_profit"][ylabel] = round(eps * shares, 2) if shares else None
    out["org_num"] = _pick(row, "RATING_ORG_NUM", "ORG_NUM")
    out["target_price"] = _pick(row, "DEC_AIMPRICE", "DEC_AIMPRICEMAX", "AIMPRICE")
    out["total_shares_billion"] = round(shares, 2) if shares else None
    out["source"] = f"eastmoney datacenter（{EM_REPORT_CONSENSUS} 机构一致预期）"
    out["as_of"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["note"] = ("一致预期净利 = 一致预期 EPS × 总股本（发行后股本口径，估算）；"
                   "机构数/目标价仅供参考；仅作披露档位输入，正式估值以财报与研报为准")
    return out


def main():
    ap = argparse.ArgumentParser(description="公开行情/财务/一致预期数据拉取（llm-ipo-valuation v3.12 D2b，尽力而为）")
    ap.add_argument("code", help="证券代码（如 688836.SH / 603448 / 301699.SZ）")
    ap.add_argument("-o", "--output", default=None, help="输出 JSON 路径")
    ap.add_argument("--timeout", type=int, default=10, help="请求超时秒数（默认 10）")
    ap.add_argument("--financials", action="store_true", help="拉取披露财务（归母净利档位/OCF/FCFF/股本，v3.12）")
    ap.add_argument("--consensus", action="store_true", help="拉取机构一致预期净利（v3.12）")
    ap.add_argument("--all", action="store_true", help="行情 + 财务 + 一致预期")
    args = ap.parse_args()

    do_fin = args.financials or args.all
    do_con = args.consensus or args.all
    result = {}
    failed = 0
    try:
        result["quote"] = fetch_quote(args.code, timeout=args.timeout)
    except Exception as e:
        failed += 1
        print(f"[ERROR] 行情拉取失败: {e}", file=sys.stderr)
    if do_fin:
        try:
            result["financials"] = fetch_financials(args.code, timeout=args.timeout)
        except Exception as e:
            failed += 1
            print(f"[ERROR] 财务拉取失败: {e}", file=sys.stderr)
    if do_con:
        try:
            result["consensus"] = fetch_consensus(args.code, timeout=args.timeout)
        except Exception as e:
            failed += 1
            print(f"[ERROR] 一致预期拉取失败: {e}", file=sys.stderr)
    if not result:
        print("[ERROR] 全部拉取失败。", file=sys.stderr)
        print("[HINT] 请检查：① 网络连接；② 代码格式（688836.SH / 603448）；③ 接口是否变更。"
              "该脚本为尽力而为工具，失败时不影响估值主流程——可比/指数/财务数据可手工检索填入输入模板。", file=sys.stderr)
        return 1

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[OK] 数据已写入: {args.output}")
    else:
        print(text)
    if failed:
        print(f"[WARN] {failed} 项拉取失败，请人工核验补充。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
