"""html_check.py — HTML 估值报告交付前机检（llm-ipo-valuation v3.16.5）

落地 SKILL.md Step 6 既有的**六项机检**硬约束，并补充两项版式结构检查（C7/C8）。
此前六项机检仅存在于规范文本、无可执行脚本，本脚本将其自动化。

检查项
------
C1 占位符零残留：未替换 `$KEY` / `{KEY}` 计数为 0；全文无外链 http(s) 引用（确保离线可开，`xmlns` 豁免）
C2 标签平衡：结构标签开闭计数相等
C3 符号重复：`＋＋` `−−` `＋−` `−＋` `++` `+−` 计数均为 0
C4 单位符号冗余 [MULT-DUP]：`××` 相邻、正则 `×\\s+倍` 计数均为 0
   配套 [CSS-DASH]：ASCII `--` 仅允许出现在 `<style>` 内（HTML 注释标记豁免）
C5 根因防护 [SYM-ROOT]：`×` 之后紧邻 `倍` 计数为 0（值自带 `×` 时模板不得再追加）
C6 数字冒烟对照（可选 `--output`）：报告关键数字与引擎输出逐位一致
C7 结构完整：章节 id 连续、章节编号无缺号、章节数符合期望（默认 11 章）；
   目录锚点一致性仅在该报告**含目录**时校验（v3.16.5：目录为可选组件，默认不出目录）
C8 渲染残留：无未渲染的 Markdown `**加粗**`、无裸占位符文本

用法
----
  python scripts/html_check.py report.html [--output output.json] [--expect-chapters 11]

退出码：0 = 全部通过；1 = 存在 FAIL。
"""

import argparse
import html as _html
import json
import re
import sys

# C2 检查的结构标签（不含自闭合/空元素）
STRUCT_TAGS = ["html", "body", "style", "div", "table", "thead", "tbody", "tr", "th", "td",
               "p", "ul", "ol", "li", "span", "figure", "figcaption", "nav",
               "h1", "h2", "h3", "h4", "svg", "defs", "polyline", "polygon", "g", "text"]

SYM_PAIRS = ["\uff0b\uff0b", "\u2212\u2212", "\uff0b\u2212", "\u2212\uff0b", "++", "+-"]
MULT = "\u00d7"   # ×
MINUS = "\u2212"  # −
PLUS = "\uff0b"   # ＋
BEI = "\u500d"    # 倍
SHU = "\u6570"    # 数
# 单位符号冗余：仅命中"× 倍"（值自带 × 后又追加单位"倍"）；
# `× 倍数` 属合法数学表达（如"增速 × 倍数矩阵"），用否定前瞻排除
BEI_DUP = MULT + r"\s*" + BEI + "(?!" + SHU + ")"


def _strip_style(text):
    return re.sub(r"<style\b[^>]*>.*?</style>", "", text, flags=re.S | re.I)


def _strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def check_c1(text):
    bare = _strip_style(text)
    dollar = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", bare)
    brace = re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", bare)
    no_xmlns = re.sub(r'xmlns\s*=\s*"[^"]*"', "", bare)
    links = re.findall(r"https?://", no_xmlns)
    detail = f"$KEY={len(dollar)}  {{KEY}}={len(brace)}  外链={len(links)}"
    if dollar or brace or links:
        if dollar:
            detail += f"  残留样本={sorted(set(dollar))[:5]}"
        if brace:
            detail += f"  残留样本={sorted(set(brace))[:5]}"
        return False, detail
    return True, detail


def check_c2(text):
    bad = []
    for tag in STRUCT_TAGS:
        opens = len(re.findall(rf"<{tag}(?:\s[^>]*)?(?<!/)>", text, flags=re.I))
        closes = len(re.findall(rf"</{tag}>", text, flags=re.I))
        # <p> 允许省略闭合是 HTML 惯例，但本报告模板要求显式闭合，故仍纳入检查
        if opens != closes:
            bad.append(f"{tag}:{opens}/{closes}")
    return (not bad), ("全部平衡" if not bad else "不平衡 → " + ", ".join(bad))


def check_c3(text):
    hits = {p: text.count(p) for p in SYM_PAIRS}
    hits = {k: v for k, v in hits.items() if v}
    return (not hits), ("无重复符号" if not hits else f"命中 {hits}")


def check_c4(text):
    dup_mul = text.count(MULT + MULT)
    mul_bei = len(re.findall(BEI_DUP, text))
    rest = _strip_comments(_strip_style(text))
    dash = len(re.findall(r"--", rest))
    ok = (dup_mul == 0 and mul_bei == 0 and dash == 0)
    detail = f"[MULT-DUP] \u00d7\u00d7={dup_mul}  \u00d7+倍={mul_bei}  [CSS-DASH] style 外 --={dash}"
    return ok, detail


def check_c5(text):
    root = len(re.findall(BEI_DUP, text)) + len(re.findall(re.escape(MULT) + r"\s*" + re.escape(MULT), text))
    return (root == 0), (f"[SYM-ROOT] \u00d7 紧邻 倍/\u00d7 命中={root}")


def check_c6(text, output_path):
    if not output_path:
        return None, "未提供 --output，跳过数字对照"
    with open(output_path, "r", encoding="utf-8") as f:
        out = json.load(f)
    syn = out.get("synthesis") or {}
    keys = {
        "综合中枢": syn.get("weighted_mid"),
        "Bear": syn.get("bear_value"),
        "Base": syn.get("base_value"),
        "Bull": syn.get("bull_value"),
        "区间下界": (syn.get("interval") or [None, None])[0],
        "区间上界": (syn.get("interval") or [None, None])[1],
    }
    miss = []
    for label, v in keys.items():
        if v is None:
            continue
        s = f"{float(v):,.2f}"
        if s not in text:
            miss.append(f"{label}={s}")
    return (not miss), ("关键数字逐位命中" if not miss else "未命中 → " + ", ".join(miss))


def check_c7(text, expect):
    """结构完整：章节 id 连续 + 章节数；目录锚点一致性仅在**出目录时**校验。

    v3.16.5：报告默认不再输出目录（`.toc` 为可选组件）——无锚点时跳过
    「锚点 ↔ 章节 id 一一对应」校验，仅保留编号连续与章节数校验。
    """
    ids = sorted({int(i) for i in re.findall(r'id="s(\d+)"', text)})
    anchors = sorted({int(i) for i in re.findall(r'href="#s(\d+)"', text)})
    problems = []
    if anchors:
        if ids != anchors:
            problems.append(f"章节 id={ids} 与目录锚点={anchors} 不一致")
        note = f"章节 {len(ids)} 个，目录锚点对应正常"
    else:
        note = f"章节 {len(ids)} 个（未出目录，跳过锚点一致性）"
    if ids != list(range(1, len(ids) + 1)):
        problems.append(f"章节编号不连续：{ids}")
    if expect and len(ids) != expect:
        problems.append(f"章节数 {len(ids)} ≠ 期望 {expect}")
    return (not problems), ("；".join(problems) if problems else note)


def check_c8(text):
    md = re.findall(r"\*\*[^*\n]{1,60}\*\*", text)
    # 裸占位符（允许 {{ }} 之类在 CSS 中已剥离）
    bare = _strip_comments(_strip_style(text))
    naked = re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", bare)
    ok = (not md and not naked)
    detail = []
    if md:
        detail.append(f"Markdown 星号残留 {len(md)} 处，样本={md[:3]}")
    if naked:
        detail.append(f"裸占位符 {len(naked)} 处，样本={naked[:3]}")
    return ok, ("无残留" if ok else "；".join(detail))


def main():
    ap = argparse.ArgumentParser(description="HTML 估值报告交付前机检（六项 + 结构两项；v3.16.5 起目录为可选组件）")
    ap.add_argument("report", help="待检 HTML 报告路径")
    ap.add_argument("--output", default=None, help="引擎输出 JSON（用于 C6 数字对照）")
    ap.add_argument("--expect-chapters", type=int, default=11, help="期望章节数（默认 11）")
    args = ap.parse_args()

    with open(args.report, "r", encoding="utf-8") as f:
        text = f.read()

    checks = [
        ("C1 占位符零残留/无外链", check_c1(text)),
        ("C2 标签平衡", check_c2(text)),
        ("C3 符号重复", check_c3(text)),
        ("C4 单位符号冗余 MULT-DUP / CSS-DASH", check_c4(text)),
        ("C5 根因防护 SYM-ROOT", check_c5(text)),
        ("C6 数字冒烟对照", check_c6(text, args.output)),
        ("C7 结构完整（章节/锚点）", check_c7(text, args.expect_chapters)),
        ("C8 渲染残留", check_c8(text)),
    ]

    failed = 0
    print(f"── HTML 机检：{args.report}")
    for name, (ok, detail) in checks:
        if ok is None:
            print(f"  [SKIP] {name}: {detail}")
        elif ok:
            print(f"  [PASS] {name}: {detail}")
        else:
            failed += 1
            print(f"  [FAIL] {name}: {detail}")
    print(f"── 结果：{'全部通过' if failed == 0 else str(failed) + ' 项未通过'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
