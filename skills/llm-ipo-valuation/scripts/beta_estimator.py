"""beta_estimator.py — 可比公司 β 公开回归估计器（llm-ipo-valuation v3.11，修订 1b）

用**公开市场数据**估计可比公司股权 β：拉取个股与基准指数的历史月收益率序列
（东方财富 kline 接口，纯标准库），OLS 回归 → 原始 β（含 R²、样本量）→ 按 D/E
去杠杆 → 输出结果供 wacc_model 的 comparable_betas 使用（估值引擎 β 链第 2 优先）。

设计约束：
- 纯标准库（urllib + statistics），无第三方依赖；
- **尽力而为**：网络失败/接口变更输出明确错误与手动估算建议，不阻断估值主流程；
- **可复算**：固定窗口（默认 60 个月）、固定基准指数、固定 OLS 公式；
- 支持 A 股（SH/SZ）、美股（US. 前缀）、港股（HK 前缀）；韩股等暂以手动输入+note 处理。

用法：
  python beta_estimator.py --codes 603986.SH,MU.US,000660.KS --benchmark SH000300 [--months 60] [-o beta.json]
  # --de 可传每家 D/E（逗号对齐 codes）用于去杠杆：--de 0.2,0.5,0.6
输出（beta.json）：[{code, raw_beta, r2, n, unlevered_beta?, note}]

wacc_model 集成：将输出中各家的 raw_beta（或 unlevered_beta）填入
financials.wacc_params.comparable_betas = [1.32, 1.18, ...]，引擎自动均值再杠杆。
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


def secid_of(code):
    """代码 → 东财 secid（A股 1./0.；美股 105.；港股 116.；韩股暂不支持返回 None）。"""
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
    if c.endswith(".KS") or c.endswith(".KSQ") or c.endswith(".KQ"):
        return None  # 韩股暂不通过东财拉取（建议手动输入 β 或使用 ADR）
    c6 = c.split(".")[0].zfill(6)
    if c6.startswith(("6", "9")):
        return "1." + c6
    return "0." + c6


def fetch_monthly_close(secid, months=60, timeout=12):
    """拉取月线收盘价序列（klt=103，不复权 fqt=1）。返回 [(date_str, close), ...] 升序。"""
    end = datetime.now()
    beg = end - timedelta(days=months * 31 + 60)
    params = {
        "secid": secid, "klt": "103", "fqt": "1",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f53",  # 日期、收盘
        "beg": beg.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
    }
    url = KLINE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://quote.eastmoney.com/"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    klines = ((raw or {}).get("data") or {}).get("klines") or []
    out = []
    for k in klines:
        parts = k.split(",")
        if len(parts) >= 2:
            try:
                out.append((parts[0], float(parts[1])))
            except ValueError:
                pass
    return out


def monthly_returns(prices):
    """收盘价序列 → 月收益率序列（简单收益）。"""
    rets = []
    for i in range(1, len(prices)):
        if prices[i - 1] and prices[i - 1] > 0:
            rets.append(prices[i] / prices[i - 1] - 1.0)
    return rets


def ols_beta(xs, ys):
    """OLS 回归 ys = a + b·xs，返回 (b, r2, n)。样本 <2 返回 (None, None, n)。"""
    n = len(xs)
    if n < 2:
        return None, None, n
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    if den == 0:
        return None, None, n
    b = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den
    a = my - b * mx
    ss_tot = sum((ys[i] - my) ** 2 for i in range(n))
    ss_res = sum((ys[i] - (a + b * xs[i])) ** 2 for i in range(n))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    return b, r2, n


def main():
    ap = argparse.ArgumentParser(description="可比公司 β 公开回归估计器（llm-ipo-valuation v3.11）")
    ap.add_argument("--codes", required=True, help="可比代码，逗号分隔（603986.SH / MU.US / 000660.KS / HK0700）")
    ap.add_argument("--benchmark", default="SH000300", help="基准指数代码（默认 SH000300 沪深300；可 399006.SZ 创业板指 / US.SPX）")
    ap.add_argument("--months", type=int, default=60, help="回归窗口月数（默认 60）")
    ap.add_argument("--de", default=None, help="各家 D/E，逗号对齐 codes（如 0.2,0.5,0.6）→ 输出无杠杆 β")
    ap.add_argument("-o", "--output", default=None, help="输出 JSON 路径")
    ap.add_argument("--timeout", type=int, default=12, help="请求超时秒数")
    args = ap.parse_args()

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    de_list = [float(x) for x in args.de.split(",")] if args.de else None
    if de_list and len(de_list) != len(codes):
        print("[ERROR] --de 数量须与 --codes 对齐", file=sys.stderr)
        return 1

    bench_secid = secid_of(args.benchmark)
    if bench_secid is None:
        print(f"[ERROR] 基准指数代码不支持: {args.benchmark}", file=sys.stderr)
        return 1
    try:
        bench_prices = fetch_monthly_close(bench_secid, args.months, args.timeout)
        bench_rets = monthly_returns([p for _, p in bench_prices])
    except Exception as e:
        print(f"[ERROR] 基准指数拉取失败: {e}", file=sys.stderr)
        print("[HINT] 检查网络/接口；失败时可比 β 可用 Damodaran 行业表或手工估算填入 comparable_betas。", file=sys.stderr)
        return 1
    if len(bench_rets) < 24:
        print(f"[ERROR] 基准指数有效样本不足（{len(bench_rets)} 个月，需 ≥24）", file=sys.stderr)
        return 1

    results = []
    for i, code in enumerate(codes):
        secid = secid_of(code)
        if secid is None:
            results.append({"code": code, "error": "市场暂不支持自动拉取（韩股等），请使用 ADR 或手动输入 β"})
            continue
        try:
            prices = fetch_monthly_close(secid, args.months, args.timeout)
            rets = monthly_returns([p for _, p in prices])
            if len(rets) < 24:
                results.append({"code": code, "error": f"样本不足（{len(rets)} 个月）"})
                continue
            # 对齐基准（取相同的窗口长度：基准截断到相同样本数，用同期收益）
            n = min(len(rets), len(bench_rets))
            xs = bench_rets[len(bench_rets) - n:]
            ys = rets[len(rets) - n:]
            b, r2, _ = ols_beta(xs, ys)
            rec = {"code": code, "raw_beta": round(b, 3) if b is not None else None,
                   "r2": round(r2, 3) if r2 is not None else None, "n": n,
                   "benchmark": args.benchmark}
            if de_list is not None and b is not None:
                rec["unlevered_beta"] = round(b / (1.0 + (1.0 - 0.15) * de_list[i]), 3)
            results.append(rec)
        except Exception as e:
            results.append({"code": code, "error": str(e)})

    out = {"benchmark": args.benchmark, "window_months": args.months,
           "as_of": datetime.now().strftime("%Y-%m-%d"),
           "source": "eastmoney kline（公开月线，纯标准库 OLS 回归）",
           "results": results,
           "usage": "将 results[].raw_beta（或 unlevered_beta）填入 financials.wacc_params.comparable_betas=[...]，引擎自动均值再杠杆"}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[OK] β 估计结果已写入: {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
