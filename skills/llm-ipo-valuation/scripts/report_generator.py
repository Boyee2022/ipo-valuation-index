"""report_generator.py — 投行版估值报告自动生成器 v2（llm-ipo-valuation v3.16.18，D4 详实版）

在 v1 基础上按投行报告标准升级为**详实版**：参考《天博智能估值报告_投行版》手工基准
（11 段结构）实现全自动生成——页眉/报告编号、执行摘要（KPI+三口径区间条+核心观点）、
核心观点表、公司概况（营收趋势图）、行业与竞争（可比矩阵+指数交叉验证）、财务基础（质量卡明细）、
方法与假设（来源审计 + 生命周期阶段与逐年增速数值）、估值结果（多方法柱状图+综合推导+补充锚+敏感性含矩阵）、
IPO 定价约束（隐含 vs 实际双口径）、风险提示（warnings 表+弹性横向条形图+统计状态）、
结论与建议（callout）、数据溯源、页脚。

v3.16.18 报告层修复（用户指定案例「特变电工」暴露；**引擎与统计数值零改动**）：
  ★ **「DCF 退化披露」触发条件过宽**——v2.14.2 起的判据仅 `fcf0 ≤ 0`，未校验 DCF 是否
  **真的**退化。「退化」的严格含义是**显式期现值与终值现值同时为 0**（`pv_sum == tv_pv == 0`）、
  权益被 `floor = max(0, net_cash)` 钳制；**基准期 FCF 为负 ≠ 退化**——只要 `pv_sum + tv_pv ≠ 0`
  （终值通常为大额正数），DCF 仍产出有效权益。**本轮扫描全部 22 个既有引擎输出**：真退化仅
  **中航沈飞**（0.00 / 0.00 / 0.00 / 78.34）；**中芯国际**（−247.51 / 499.05 / 4,759.51 / 4,999.18）
  与**特变电工**（−94.12 / −8.76 / 961.36 / 726.87）**均未退化**，却被渲染「显式期现值与终值现值
  均为 0、DCF 退化为净现金下限 X 亿元」——与引擎输出**直接矛盾**。**修复**：拆两支（真退化→原文案；
  基准期为负但未退化→新增「基准期为负披露」文案，给出显式期现值／终值现值／终值占比，提示
  「高度依赖永续期假设」）。**零回归**：fcf0 > 0 的 20 例不进入分支；中航沈飞走分支①文案逐字节不变。
  并补冒烟 **T94**（源码层结构断言 ＋ 行为断言：未退化样本不得出「净现金下限」字样、须出「基准期为负」
  ＋ 真退化样本仍出「退化披露」 ＋ 零回归）。

v3.16.15 报告层修复（用户指定案例「北方稀土」暴露；**引擎与统计数值零改动**）：
  ★ **「渲染型自由文本站点未全量覆盖」缺陷族第 6 次暴露**——v3.16.12 声称「全量覆盖
  `_rich()`」，实则只覆盖了 `data_sources[].item`、`meta.industry`、`meta.note_asset_type`
  三处；同表的 **`data_sources[].source`**（来源列，人工撰写、常含机构/接口说明与强调）仍走
  `_esc()`，北方稀土案例该列写入 `**分析师加工口径**` → 裸记号落入 HTML（机检 **C8** 捕获）。
  同类**潜在**站点：`meta.exchange`（上市沿革，人工撰写，KPI 注与页眉元信息条两处渲染）。
  **修复**：`data_sources[].source`、`meta.exchange`（两处）由 `_esc()` 改 `_rich()`；
  `as_of` / `confidence` / 引擎生成的 `note` 等短标签站点继续 `_esc()`（保持不变）。
  **零回归**：以上字段不含成对 `**` 时 `_rich(s) == _esc(s)` → 输出逐字节不变；
  经 `docs/_ab_report_v31615.py` 对 16 个既有案例逐字节验证（全部 IDENTICAL，见 `docs/_ab_r31615/`）。
  并补冒烟 **T91**（源码层：`source` 与 `exchange` 两站点须走 `_rich()` 的结构性断言 ＋
  两站点不得再走 `_esc()` 的反向断言；报告层：含 `**` 的 source/exchange 注入后须出 `<strong>` 且无裸 `**`）。

v3.16.14 报告层修复（用户指定案例「中信证券」暴露；**引擎与统计数值零改动**）：
  ★ **§7.4 补充锚「最近融资价格法」行渲染出字面量 `适用=None`**——根因：引擎
  `recent_financing_anchor()` **仅在输入提供 `exclusions[]` 时才写入 `applicable` 键**
  （未提供 `exclusions` 时直接 `return base`，base 不含该键），而生成器无条件
  `rfa.get('applicable')` 并直接拼进 f-string → 该键缺失时渲染为字符串 `None`。
  机检 C1 只抓 `$KEY` / `{KEY}` 占位符、C8 只抓 `**粗体**` / 裸占位符，**均抓不到「键缺失渲染 None」**，
  故此前 9 例含融资锚的报告（福耀玻璃、中芯国际等）均带此瑕疵而未被拦截。
  **修复**：`applicable is None`（未提供排除检查）→ 展示「是」（语义＝未触发 9 项排除检查）；
  `applicable is False` → 展示「否」；`applicable is True` → 展示「是」。
  并补冒烟 **T90**（源码层断言不得出现 `适用={rfa.get(` 直拼 ＋ 报告层断言正文不含 `None`）。

v3.16.13 报告层版式修订（用户指定案例「福耀玻璃」暴露；**引擎与统计数值零改动**）：
  ★ **页眉由「左右结构」改为「上下结构」**——原 `.masthead{display:flex;justify-content:
  space-between}` ＋ 右侧 `.meta{text-align:right;white-space:nowrap}` 把「报告编号／估值基准日／
  引擎」等元信息固定为**不折行**的一列；当 `meta.exchange`（上市沿革）或 `meta.note_asset_type`
  （长段说明，10 例实测 184~692 字）较长时，右列宽度可占去整幅的一半以上，**左侧企业简介被
  挤压成窄列 → 副题折行十余行 → 页眉纵向高度异常**（福耀案例副题 509 字，窄列下约 15 行）。
  **修复**：`.masthead` 改 `display:block`；简介（品牌行／h1／副题）独占整幅宽度；元信息改为
  其下的**元信息条**（浅渐变底＋金色左边框＋圆角），内部以 `<span class="m">`（标签 `.k` +
  取值 `.v`）＋ `｜` 分隔（`.sep`）自然折行——长取值不再撑宽版面。
  **零回归**：改动仅落在页眉区块 CSS 与页眉 HTML，其余 10 个章节逐字节不变
  （`docs/_ab_report_v31613.py` 验证：9 个既有案例差异全部落在页眉行，行数不变）。
  并补冒烟 **T89**（源码层 `display:block`／无 `space-between`／无 `nowrap` 结构性断言 +
  报告层 `.meta` 须位于 `.sub` 之后、6 个元信息项、长文本不得截断）。

v3.16.12 报告层修复（用户指定案例「中国石油」暴露；**引擎与统计数值零改动**）：
  ★ **渲染型自由文本站点未全量覆盖（v3.16.10 修复不彻底的延续）**——v3.16.10 的 `_rich()`
  修复**只覆盖了 `data_sources[].items` 一个站点**，而同族的另两处展示型自由文本站点仍走
  `_esc()`：① **§2 公司概况**渲染 `meta.industry`（本例含 `**…**`）；② **页眉副标题**渲染
  `meta.industry` + `meta.note_asset_type`（本例后者含 `**一体化结构而非纯上游资源股**`，
  由机检 **C8「渲染残留」** 捕获）。这是同族缺陷的**第 5 次暴露**（伊利→data_sources、
  美的→比率精度、三一→周期桥接、中车→§7.6 手工补写、中国石油→meta.industry/note_asset_type）。
  **修复**：两站点 `_esc()` → `_rich()`（`_ind_txt`、页眉 `sub`）。**零回归**：全量扫描
  7 个既有案例输入的 `meta.industry` / `meta.note_asset_type`，**均不含成对 `**`** →
  `_rich(s) == _esc(s)`，输出逐字节不变（`docs/_ab_report_v31611.py` 验证：catl/crrc/gree/
  midea/pingan/sany/yili 全部 IDENTICAL；仅 petrochina 1 行差异＝页眉副标题；
  `<strong>` 计数 48→49、`**` 计数 2→0、行数 303 不变）。
  并补冒烟 **T88**（源码层 `_rich(meta_inp.get("industry")`/`_rich(meta.get('industry')`/
  `_rich(meta_inp.get('note_asset_type')` 结构性断言 + `_esc(...note_asset_type...)` 反向断言 +
  报告层注入含 `**` 的 `meta.industry`/`meta.note_asset_type` → 输出须含 `<strong>` 且无裸 `**`）。

v3.16.10 报告层修复（用户指定案例「伊利股份」暴露；**引擎与统计数值零改动**）：
  ★ **渲染型自由文本中的 Markdown 粗体标记原样落入 HTML（缺陷族）**——`input.json ›
  data_sources[].items`（§11 数据溯源表的「数据项」单元格）由**人工撰写**，常带 Markdown
  `**粗体**` 强调；生成器原只经 `_esc()`（`html.escape`，`*` 不在转义集内）→ 伊利案例
  §11 出现两处裸记号：`**资产减值损失 −24.56 亿元**`、`**ToB 深加工、成人营养品、国际化**`
  （由机检 **C8「渲染残留」** 捕获）。属**族级缺陷**：任一案例的任一展示型字段写入 `**` 即复发
  ——本案例输入共 26 个字段含 `**`，其中仅 data_sources 的 items 被渲染，故此前 13 个用例
  （11 examples + catl/pingan/gree/midea）均未暴露，该缺陷长期未被发现。
  **修复**：新增 `_rich()`——**先 `_esc()` 再仅把成对的 `**…**` 转 `<strong>…</strong>`**
  （DOTALL 允许跨行；不成对则原样保留、不吞字）；应用于数据项单元格（唯一调用点）；
  安全边界＝替换在已转义文本上进行（转义后不可能出现裸 `<`，注入 `<strong>` 安全），
  **SVG 路径一律不调用 `_rich()`**，数值/短标签站点继续用 `_esc()`。
  **零回归**：文本不含成对 `**` 时 `_rich(s) == _esc(s)` → 输出逐字节不变
  （已由 docs/_ab_report_v31610.py 逐字节验证：13 个既有用例全部逐字节一致，
  仅伊利案例差异为「记号 → 粗体」，行数不变、还原记号后逐行逐字节相同）。
  并补冒烟 **T87**（工具层成对/不成对/多组/转义顺序 + 源码层 `_rich(_it` 结构性断言 +
  报告层注入 `**` 后输出须含 `<strong>` 且无裸 `**`）。

v3.16.9 报告层修复（用户指定案例「美的集团」暴露；**引擎与统计数值零改动**）：
  ★ **「比率量 0 位小数」显示缺陷族（precision family）**——多处 `_pct(值, 0)` 把**比率型字段**
  截断为整数百分点，导致同一报告内自相矛盾：
    ① §7.1 多方法表 DCF 行 `WACC {_pct(wacc, 0)} / g {_pct(tg, 0)}`——
       美的集团 WACC 8.5% 渲染为「8%」、永续增速 2.5% 渲染为「2%」，
       而同报告 §6.2 关键假设表显示 **8.5% / 2.5%**（该表用 `_pct(v)` 默认 1 位）。
       **WACC 是主导敏感变量**（本案例弹性 −11.51%/+20.39%），0.5pp 截断对应约 13% 估值偏差，
       属**实质性误导**而非排版瑕疵。
    ② §6.3 方法适用性表 DCF 行同一写法（同族，一并修）。
    ③ **§4.2「与可比法偏差」双重缺陷**——原式 `_pct(idx_out['vs_comparable_deviation'] / 100, 0)`：
       `vs_comparable_deviation` 由引擎以**比率**输出（`round(dev,4)`，如 `-0.0385` = −3.85%），
       再除 100 属**口径误用**，叠加 0 位小数后美的显示「−0%」、
       `examples/output_example_unitree.json`（−0.7054）显示「−1%」，
       而**同一报告 §6.3 该行**用 `_pct(v, 2)` 正确显示「−70.54%」→ 同页两个数相差 70 倍。
    ④ §4.1b 境内/海外分组缺口 `_pct(abs(gap), 0)` → 亦为比率量，提至 1 位（保持「折价/溢价」判定不变）。
  另修一处**静默丢数**：原 §4.2 守卫写作 `if _num(v)` —— `_num(0.0)` 为假值，偏差恰为 0%
  时该格回退为「—」（真实存在的「与可比法完全一致」被渲染成缺失）；改为 `is not None` 判定。
  **修复口径**：比率型字段一律按 `_pct(v)`（1 位）或 `_pct(v, 2)`（2 位）渲染，**不再出现 `nd=0`**；
  §4.2 去掉错误的 `/100`，与 §6.3 对齐为 2 位小数。判定「比率 vs 百分点」以**引擎输出定义为准**
  （引擎一律输出比率；`*_pct` 命名亦为比率，如 `group_gap_pct`）。
  影响面：全部报告含 DCF 行者 WACC/g/终值占比显示值变更；仅启用行业指数者 §4.2 变更。
  生成器终值/权重等其他数字与所有引擎输出**逐字节不变**。

v3.16.8 报告层修复（用户指定案例「宁德时代」暴露；**引擎与统计数值零改动**）：
  ★ **`gap_note` 比值判读对称化**：`dcf_vs_comparable_gap` = 可比法值 ÷ DCF 值（1.0 = 两法一致），
  原逻辑为「gap ≥ 1.5 → 显著背离；gap < 0.8 → **两口径接近、相互印证**；其余 → 温和背离」——
  **方向不对称**：gap=0.69 实为可比法比 DCF 低 31%（宁德时代：可比 12,569 亿 vs DCF 18,160 亿，
  相差 44%），却被读作「分歧小」，判读与事实相反。因 `examples/` 全部 9 个案例的 gap 均 > 0.8
  （0.95~15.58），该分支**此前从未被触发**，故缺陷长期未被发现。
  现改为按 |gap − 1| 三档对称判读（≤0.15 基本一致 / ≤0.40 分歧中等 / >0.40 背离显著），
  并显式给出偏离幅度与方向（可比法高于或低于 DCF）。影响面：9 个既有案例仅 1 个档位微调
  （gap 0.950 由「温和背离」改为「基本一致」，更准确），其余档位不变。
  ★ 与 v3.16.7 的 Layer 0 分支正交：`dcf_admissible is False` 时仍优先走「不适用、不作为互证」分支。

v3.16.7 报告层修复（用户指定案例「中国平安」暴露；**引擎数值口径零改动**）：
  ★ **Layer 0 「DCF 不适用」披露**（framework_check.dcf_admissible is False 时触发，其余输入零变化）：
  引擎在金融/资源类路由下已把 dcf 权重归零（dcf_weight_cap=0），但报告层原为**无条件**措辞——
  ① §2「方法结构」把 DCF 名义留痕值当作并行法呈现；
  ② §6.1 称「市场法…与内在价值法（两阶段 DCF）并行」，与 w_dcf=0.00 自相矛盾；
  ③ §7.1 直接列出 DCF 隐含值而不声明其不适用；
  ④ `_build_narrative` 的 `gap_note` 按「比值 <0.8 → 两口径接近、相互印证」判读，而
     金融主体 DCF 留痕值恰为**高估**（平安：DCF 26,990 亿 vs 可比口径 10,528 亿，比值 0.39
     被判为「分歧小」，实为 2.6 倍背离、且方向相反）。
  现新增：§2 方法结构行改写、§6.1 段落改写、§7.1 表格后 `callout.alert` 方法选择结论、
  §7.2 DCF 行标注「权重 0（Layer 0 判否）」、narrative 口径关系改写。
  ★ **§10 置信度构成透出**：`confidence.method_coverage` / `method_divergence`（引擎两条折减机制）
  原仅存于引擎输出、报告不呈现，导致「置信度=中」缺少理由（Step 6「置信度总评」缺项）。
  现于 §10 结论框内增一行，数值全部来自引擎 confidence 块，生成器不产生任何估值数字。

v3.16.5 报告版式修订（用户指定；**引擎与统计数值口径零改动**）：
  ① **取消目录**（`.toc` 组件与 `_toc()` 一并移除）——页眉后直接进入执行摘要；
     章节序号徽标 01–11 与 `id="s1..s11"` 锚点保留（供 §x.y 交叉引用与打印定位）。
  ② **执行摘要去重**——移除「方法离散度」KPI 卡（CV 属 §7/§9 诊断量，非摘要级信息）
     与「合理估值区间」结论条 `.verdict`（与 KPI「综合估值区间」卡重复）；
     摘要区只保留 KPI 三卡 + 图 1 三口径区间条 + 结论前置段落。
  ③ **§6 关键假设补数值**——新增「生命周期阶段」（stage/来源/置信度 + 增速形态/显式期/终值）
     与「预测期增速（逐年）」两行，数值取自引擎 `lifecycle` / `scenarios.base.dcf.growth_schedule.seq`；
     年份由 `input.financials.growth_forecast` 的键推导（缺键时退化为「第 i 年」，不臆造年份）；
     另新增「增速三角参照」行（自身历史 CAGR / 可比增速中位 / 行业增速 / 三角校准值）。
  ④ **字号统一**——正文级文字（正文/表格/注释/图注/标签/页脚/页眉）全部统一为 `--fs:14px`；
     展示型数字（KPI 卡）统一为 `--fs-num:24px`；标题阶梯收敛为 h1 22 / h2 18 / h3 15.5 / h4 14；
     图内文字（SVG）统一 `CHART_FS=14`（用户单位），且各图 viewBox 宽度归一为 1000
     （≈浏览器容器宽度）→ 图内文字渲染尺寸≈正文字号，消除「图表字大于正文」的观感割裂。

核心原则（X3 防幻觉）：**报告内所有估值数字均来自引擎输出（output.json / stat.json），
生成器只做版面编排与定性论述（基于数字的模板化解读），不产生任何新的估值数字。**

用法：
  python report_generator.py output.json -o report.html --stat stat.json --input input.json
  # input 为详实版核心输入（公司/行业/财务章节数据源）；缺失时相应章节降级提示。
"""

import argparse
import html
import json
import re
import sys
from datetime import datetime

# ---------- 工具 ----------

def _fmt(v, nd=2):
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v, nd=1):
    if v is None:
        return "—"
    try:
        return f"{float(v) * 100:.{nd}f}%"
    except (TypeError, ValueError):
        return str(v)


def _esc(s):
    return html.escape(str(s or ""))


# v3.16.14（报告生成器 v3.16.14）：修 §7.4「最近融资价格法」行渲染字面量 `None`——引擎仅在提供
#   exclusions[] 时写 `applicable` 键，缺失时原代码把 `None` 拼进正文；改为缺省＝「是」。仅动该行文本。
# v3.16.13（报告生成器 v3.16.13）：**页眉由左右结构改为上下结构**——原 flex + 右侧 nowrap 元信息
# 在 exchange / note_asset_type 较长时挤压左侧简介成窄列，页眉纵向过高（福耀案例副题 509 字）。
# 现简介独占整幅宽度、元信息改为其下的元信息条（.m/.k/.v + .sep 自然折行）。仅动页眉区块。
# v3.16.12（报告生成器 v3.16.12）：把 v3.16.10 的 `_rich()` 修复**推广到全部展示型自由文本站点**
# ——§2 公司概况（meta.industry）与页眉副标题（meta.industry + meta.note_asset_type）此前仍走 `_esc()`，
# 中国石油案例的 note_asset_type 含 `**…**` → C8「渲染残留」（同族第 5 次暴露）。两站点改 `_rich()`。
# v3.16.10（报告生成器 v3.16.10）：族级修复「输入留痕文本中的 Markdown 粗体标记原样落入 HTML」。
# input.json 的**展示型长文本**（data_sources.items 等）由人工撰写，常带 Markdown `**粗体**`；
# 生成器原只做 `_esc()`（HTML 转义），`*` 不在转义集内 → `**…**` 原样出现在表格/段落，
# 由机检 C8「渲染残留」捕获（伊利股份案例暴露：2 处）。此处新增 `_rich()`：**先 HTML 转义、
# 再把成对的 `**…**` 转为 `<strong>…</strong>`**（跨行匹配用 DOTALL；不成对则原样保留）。
# 安全边界：只在已转义文本上做替换——转义后不可能出现裸 `<`，故注入 `<strong>` 安全；
# 仅用于**展示型长文本**站点（HTML 文本上下文），**SVG 路径一律不调用 `_rich()`**，
# 数值/短标签站点继续用 `_esc()`，避免向 SVG 注入元素。
# 零回归：文本不含成对 `**` 时 `_rich(s) == _esc(s)`，输出逐字节不变。
_RICH_RE = re.compile(r"\*\*(.+?)\*\*", re.S)


def _rich(s):
    return _RICH_RE.sub(r"<strong>\1</strong>", _esc(s))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------- SVG 组件（详实版） ----------

# v3.16.5 字号统一：图内文字统一使用该字号（SVG **用户单位**）。
# 各图 viewBox 宽度统一归一为 1000（≈浏览器内容区宽度 1012px at 1120px 画布），
# 故缩放比≈1.0 → 图内文字渲染尺寸≈正文字号（--fs:14px），不会出现"图表字大于正文"。
CHART_FS = 14

# v3.16.7：质量分基准（与引擎 QUALITY_SCORE_DEFAULT 同值）。
# 仅用于 §10 置信度构成行的**分母展示**（"盈利质量分 60.8/60"），不参与任何计算；
# 若引擎侧调整该基准，须同步此处（审计留痕由 §10 行文案承担）。
QUALITY_SCORE_DEFAULT = 60.0


def svg_range_bar(lo, hi, mid, max_v=None, caption=None, tone=""):
    """估值区间横条（**百分比**定位，随容器自适应；v3.16.3 修复原 px 定位在不同容器宽度下比例失真）。"""
    lo, hi, mid = _num(lo), _num(hi), _num(mid)
    if lo is None and hi is None:
        return ""
    lo = lo if lo is not None else 0.0
    hi = hi if hi is not None else lo
    mid = mid if mid is not None else (lo + hi) / 2
    max_v = max_v or (hi * 1.18 or 1)
    if max_v <= 0:
        max_v = 1.0

    def pct(v):
        return max(0.0, min(100.0, v / max_v * 100))

    left, right = pct(lo), pct(hi)
    width = max(1.2, right - left)
    cls = "bar gold" if tone == "gold" else "bar"
    cap = f'<div class="cap">{caption}</div>' if caption else ""
    return f'''<div class="rangebar">
  <div class="axis"><div class="{cls}" style="left:{left:.2f}%;width:{width:.2f}%"></div>
  <div class="midmark" style="left:{pct(mid):.2f}%"></div></div>
  <div class="labels"><span>0</span><b>{_fmt(lo)} – {_fmt(hi)}（中枢 {_fmt(mid)}）</b><span>{_fmt(max_v)}</span></div>
  {cap}
</div>'''


def _sentiment_correction_disclosure(scenarios):
    """v3.18.0：舆情强度修正披露表（Base / Bear / Bull 三情景）。

    仅在引擎输出 scenarios.{x}.sentiment_correction 存在时渲染（sentiment_layer=correction）。
    strength 口径额外给出「方向 × 强度 → 幅度 → 上限」的可复算拆解。
    """
    rows = []
    mode = None
    for name in ("bear", "base", "bull"):
        sc = (scenarios.get(name) or {}).get("sentiment_correction")
        if not sc:
            continue
        sig = sc.get("signal") or {}
        sd = sig.get("signal_detail") or {}
        mode = sc.get("adjust_mode") or mode
        if mode == "strength":
            detail = (f"方向 {(_num(sig.get('direction')) or 0):+.0f} × 强度 k={_fmt(sig.get('k_signal'), 2)}"
                      f" × 成立度 {_fmt(sig.get('magnitude'), 2)}"
                      f" → 未截断 {(_num(sig.get('adj_raw')) or 0) * 100:+.2f}%"
                      f"｜上限 ±{(_num(sig.get('ceiling')) or 0) * 100:.2f}%"
                      f"{'（触及上限）' if sig.get('clamp_hit') else ''}")
        else:
            detail = f"信号强度 k={_fmt(sig.get('k_signal'), 2)}（legacy 口径：clamp(sent×k, ±band)）"
        _od = _num(sig.get("overlap_discount"))
        if _od:
            detail += f"；已去相关折让 ×{_fmt(_od, 2)}"
        tier = sd.get("tier") or "—"
        cons = sd.get("consistency") or "—"
        extras = []
        if sd.get("has_high_importance"):
            extras.append("高重要性")
        if sd.get("authority"):
            extras.append("权威出处")
        _dcy = _num(sd.get("decay"))
        if _dcy is not None and _dcy < 1.0:
            extras.append(f"衰减×{_fmt(_dcy, 2)}")
        if extras:
            cons = f"{cons}（{'/'.join(extras)}）"
        rows.append((
            {"bear": "Bear 悲观", "base": "Base 中性", "bull": "Bull 乐观"}.get(name, name),
            f"±{(_num(sc.get('band_pct')) or 0) * 100:.1f}%",
            f"{(_num(sc.get('correction_pct')) or 0) * 100:+.2f}%",
            f"{tier} / {cons}",
            detail,
        ))
    if not rows:
        return ""
    tbl = _table(["情景", "带宽 (band)", "修正幅度", "信号档 / 一致性", "拆解（可复算）"],
                 rows, num_cols=[1, 2])
    cap_note = ("强度口径上限 = band × 1.60（v3.18.0 口径 C：强信号可有序突破基础带宽，"
                "同时保留硬上限）" if mode == "strength" else "幅度受 band 硬截断（legacy 口径）")
    return ('<h3>7.3.1 舆情强度修正披露（v3.18.0）</h3>'
            f'{tbl}'
            f'<p class="small">③ 市场舆情不独立占权重，作为 ② 可比法的乘性修正系数（P2）；'
            f'{cap_note}。强度矩阵：量级（无 / 1–2 / 3–5 / 6+）× 一致性（一致 / 冲突）；'
            f'高重要性 ×1.20，权威出处 ×1.15，时效衰减按 days_since_event。</p>')


def _terminal_growth_disclosure(out):
    """v3.21.0 §7.3.4：永续增速合理性披露。

    只在 v3.21 任一开关启用（`dcf_growth` 相关输出块存在）时渲染：
    守卫处置 / 取值链 / 三情景 tg / 终值占比档位 / 市场隐含 g*。
    报告层不产生任何新数字，全部取自 `scenarios.base.dcf` 与 `assumptions_summary.dcf`。
    """
    base = (out.get("scenarios") or {}).get("base") or {}
    dcf = base.get("dcf") or {}
    dcf_ass = ((out.get("assumptions_summary") or {}).get("dcf")) or {}
    guard = dcf.get("terminal_guard")
    chain = dcf_ass.get("tg_chain")
    tvg = dcf_ass.get("tv_share_grade")
    itg = dcf.get("implied_terminal_growth_market")
    stg = dcf_ass.get("scenario_tg_adj_pp")
    tgv2 = dcf_ass.get("tg_anchors_v2")
    if not any((guard, chain, tvg, itg, stg, tgv2)):
        return ""

    blocks = []
    # ① 守卫处置（A1）
    if guard and guard.get("violation"):
        if guard.get("action") == "clamp":
            body = (f"<b>永续增速 {_pct(guard.get('tg_clamped_from'))} 不低于折现率 "
                    f"{_pct(guard.get('wacc'))}</b>，已按 clamp 口径压至 WACC−1pp"
                    f"（{_pct(guard.get('tg_clamped_to'))}）。{_esc(guard.get('clamp_reason') or '')}"
                    f"置信度已折减一档。")
        else:
            body = (f"<b>永续增速 {_pct(guard.get('tg'))} 不低于折现率 {_pct(guard.get('wacc'))}</b>"
                    f"（分母 {_fmt(guard.get('gap_pp'), 2)}pp）→ Gordon 终值无经济意义，"
                    f"已按 fail-closed 口径仅计<b>显式期现值 + 净现金</b>，终值置 0。"
                    f"本情形下 DCF 值不代表内在价值，须先修正资本成本或永续假设。置信度已折减一档。")
        blocks.append(f'<div class="callout alert"><p><b>终值前提不成立（A1 守卫触发）</b>：{body}</p></div>')

    # ② 取值链（A3/A4）
    if chain:
        _PICK = {"user_explicit": "① 用户显式", "industry_g_lt": "② 行业 g_lt",
                 "inflation_anchor": "③ 通胀锚"}
        rows = []
        for c in chain.get("chain") or []:
            rows.append((_esc(_PICK.get(c.get("source"), c.get("source"))),
                         _pct(c.get("raw")) if c.get("raw") is not None else "未提供",
                         _pct(c.get("value")) if c.get("value") is not None else "—",
                         "命中" if c.get("hit") else "未命中",
                         _esc(c.get("industry") or "—")))
        vc = chain.get("validation") or {}
        tail = (f'<p class="small">三角校准值已降为<b>校验参照</b>（不参与取值）：'
                f'{_pct(vc.get("implied_terminal_growth"))}，偏差 {_fmt(vc.get("deviation_pp"), 2)}pp'
                f'{"（超过 1pp 阈值，已告警）" if vc.get("alert") else "（在 1pp 阈值内）"}。'
                f'GDP 上限 {_pct(chain.get("gdp_cap"))}，通胀锚 {_pct(chain.get("inflation_anchor"))}。</p>'
                if vc else "")
        blocks.append('<h3>7.3.4 永续增速合理性披露（v3.21.0）</h3>'
                      '<p class="small"><b>取值链（A3/A4）</b>：按「用户显式 &gt; 行业 g_lt &gt; 通胀锚」'
                      '逐级回落，命中即止；行业 g_lt 由 GDP 上限封顶、通胀锚托底。</p>'
                      + _table(["优先级", "原始值", "采用值", "是否命中", "行业类目"], rows, hl_cols=[3])
                      + tail)

    # ③ 三情景 tg（A5）
    if stg:
        rows = []
        for k, lbl in (("bear", "Bear 悲观"), ("base", "Base 中性"), ("bull", "Bull 乐观")):
            d2 = ((out.get("scenarios") or {}).get(k) or {}).get("dcf") or {}
            rows.append((lbl, f"{_fmt(stg.get(k), 2)}pp", _pct(d2.get("terminal_growth")),
                         _pct(d2.get("tv_share")),
                         _fmt(d2.get("equity_value"))))
        blocks.append('<p class="small"><b>永续增速情景化（A5）</b>：tg 随情景移动，'
                      'bull 侧受长期名义 GDP 上限约束。</p>'
                      + _table(["情景", "tg 调整", "采用 tg", "终值占比", "权益价值（亿元）"],
                               rows, num_cols=[1, 2, 3, 4]))

    # ④ 终值占比档位（A6）
    if tvg:
        _GV = {"low": "过低（<40%）", "in_range": "区间内（40–75%）",
               "high": "偏高（75–85%）", "extreme": "极端（>85%）"}
        blocks.append(f'<p class="small"><b>终值占比门禁（A6）</b>：{_pct(tvg.get("tv_share"))} '
                      f'→ 档位「{_esc(_GV.get(tvg.get("grade"), tvg.get("grade")))}」，'
                      f'{_esc(tvg.get("message"))}。</p>')

    # ⑤ 市场隐含 g*（A7）
    if itg:
        if itg.get("solvable"):
            blocks.append(
                '<p class="small"><b>市场隐含永续增速（A7）</b>：市值 '
                f'{_fmt(itg.get("market_cap"))} − 净现金 {_fmt(itg.get("net_cash"))} − 显式期现值 '
                f'{_fmt(itg.get("pv_sum"))} = 残值 {_fmt(itg.get("residual_tv_pv"))} 亿元，'
                f'反解 <b>g* = {_pct(itg.get("implied_g"))}</b>。判读：{_esc(itg.get("verdict"))}。</p>')
        else:
            blocks.append(
                '<p class="small"><b>市场隐含永续增速（A7）</b>：显式期现值 '
                f'{_fmt(itg.get("pv_sum"))} + 净现金 {_fmt(itg.get("net_cash"))} 已超过市值 '
                f'{_fmt(itg.get("market_cap"))}，<b>任何正数永续增速都无法把估值压到市价</b>'
                f'——{_esc(itg.get("verdict"))}。</p>')
    # ⑥ 三锚取值（v3.25.0）
    if tgv2 and tgv2.get("applied"):
        _AN = {"industry_g_lt": "行业长期增速 g_lt（结构锚）",
               "implied_market": "市场隐含 g*（定价锚）",
               "sgr": "SGR = ROIC×(1−派息率)（结构硬约束）"}
        rows = []
        for k, lbl in _AN.items():
            if k in (tgv2.get("anchors") or {}):
                rows.append((lbl, _pct(tgv2["anchors"][k]), "参与"))
            elif k in (tgv2.get("skipped_anchors") or {}):
                rows.append((lbl, "—", _esc(tgv2["skipped_anchors"][k])))
        caps = tgv2.get("caps") or {}
        blocks.append(
            '<p class="small"><b>永续增速三锚交叉（v3.25.0）</b>：替代「逐级回落」取值链——'
            '链式口径的取值完全取决于哪一级先命中，行业参数一命中，SGR 与市场隐含即被弃置，'
            '等于用单一口径冒充交叉验证。三锚口径取多来源中位后再双上限夹逼。</p>'
            + _table(["来源", "取值", "参与 / 说明"], rows, num_cols=[1])
            + f'<p class="small">合成：中位 {_pct(tgv2.get("raw"))} → 夹逼 → '
              f'<b>tg = {_pct(tgv2.get("value"))}</b>'
              f'（封顶来源 {_esc(tgv2.get("capped_by") or "未触限")}；'
              f'有效上限 min(GDP {_pct(caps.get("gdp_cap"))}, WACC {_pct(caps.get("wacc"))} − '
              f'{_fmt((caps.get("spread_min") or 0) * 100, 1)}pp) = {_pct(caps.get("effective_cap"))}；'
              f'下限 {_pct(tgv2.get("floor"))}）。'
              f'不采用 6% / 2% 双轨缺省——6% 与同文件 GDP 上限 4.5% 自相矛盾，2% 只是通胀锚、'
              f'不应兼任缺省值。spread {_fmt((tgv2.get("spread") or 0) * 100, 2)}pp。</p>')
    return "".join(blocks)


def _growth_path_model_disclosure(out):
    """v3.25.0 §7.3.5：显式期增速路径模型披露（状态空间分解）。

    ★教训沿用（「引擎有输出 ≠ 报告有呈现」缺陷族第 8 次）：引擎已产出
    `dcf.growth_model` / `dcf.growth_seq_detail`，若不渲染，报告读者仍只能看到
    一串裸增速数字，无法回答「某一年凭什么是这个数」。故逐年列出
    趋势层 μ / 冲击层 u / 来源标签，并给出参数与闭合校验。
    """
    base = (out.get("scenarios") or {}).get("base") or {}
    dcf = base.get("dcf") or {}
    gm = dcf.get("growth_model")
    if not gm:
        return ""
    rows = []
    for r in (dcf.get("growth_seq_detail") or []):
        rows.append((f"t{r['t']}", _pct(r["g"]), _esc(r.get("src") or ""),
                     _esc(r.get("clamped_by") or "—")))
    bounds = gm.get("bounds") or {}
    closure = gm.get("closure") or {}
    _SRC = {"user_path": "用户路径首年（L1，不冒充实测）", "explicit": "显式输入",
            "shape_rule": "历史形态矩阵", "fallback": "兜底（非实测，须标注）"}
    body = (
        '<h3>7.3.5 显式期增速路径模型披露（v3.25.0）</h3>'
        '<p class="small">口径：<b>g_t = μ_t + u_t</b>——增长率拆成「趋势层」与「冲击层」。'
        '趋势层 μ_t 以归一化指数从中期锚 μ₀ 收敛到永续增速 tg（构造上精确到达，非渐近）；'
        '冲击层 u_t = (g₁ − μ₀)·(1 − (t−1)/(n−1))<sup>p</sup> 为幂次衰减，t=n 时恰为 0。'
        '替代原五种硬编码形态（exp / mean_revert / s_curve / decline / linear）——'
        '其 rho=0.30、half_life=3、lam=0.30 均无出处，且渐近线数学上永不到达 tg，'
        '只能靠 forced 硬覆盖末端。</p>'
        + _table(["年", "增速 g", "来源", "受限于"], rows, num_cols=[1])
        + f'<p class="small">参数：冲击形态 p = {_fmt(gm.get("p"), 2)}'
          f'（周期性 1.0 / 混合 1.5 / 结构性 2.0）｜趋势退化率 κ = {_fmt(gm.get("kappa"), 3)}'
          f'（等价 CAP ≈ {_fmt(gm.get("cap_life_years"), 1)} 年护城河，κ = 1 − 1/CAP）｜'
          f'显式期 {len(rows)} 年。首年 g₁ = {_pct(gm.get("g1"))}'
          f'（来源：{_esc(_SRC.get(gm.get("g1_source"), gm.get("g1_source")))}）；'
          f'中期锚 μ₀ = {_pct(gm.get("mu0"))}（来源：{_esc(gm.get("mu0_source"))}）；'
          f'首年冲击 u₁ = {_fmt(gm.get("u1_pp"), 2)}pp'
          f'{"，已标注为历史 σ 之外的异常冲击" if gm.get("shock_flag") else ""}。</p>'
        f'<p class="small">约束：上限 min(GDP {_pct(bounds.get("gdp_cap"))}, '
        f'SGR {_pct(bounds.get("sgr")) if bounds.get("sgr") is not None else "缺 ROIC 未约束"}) '
        f'= {_pct(bounds.get("effective_cap"))}（生效来源 {_esc(bounds.get("cap_source"))}），'
        f'下限 {_pct(bounds.get("floor"))}；'
        f'约束⑤：|μ₀ − g₁| &gt; 5pp 时 μ₀ 退化为 g₁（防 V 型非单调）'
        f'{"——<b>本案例已触发</b>" if gm.get("mu0_degraded") else "——本案例未触发"}。'
        f'闭合校验：t=1 精确等于 g₁ {closure.get("t1_equals_g1")}、'
        f't=n 精确等于 tg {closure.get("tn_equals_tg")}。</p>')
    if gm.get("mu0_degraded") or gm.get("mu0_clamped_by"):
        body += (f'<p class="small">注：μ₀ 生效值 {_pct(gm.get("mu0"))}'
                 + (f'，因被 {_esc(gm.get("mu0_clamped_by"))} 夹逼调整' if gm.get("mu0_clamped_by") else "")
                 + '。μ₀ 是路径唯一的自由判断，其方向反直觉——调高 μ₀ 会使 u₁ 更负（冲击更深），'
                   '权益不一定上升，报告不宜按「锚越高越乐观」解读。</p>')
    return body


def _alt_method_disclosure(out):
    """v3.19.0 P6-B/C：替代主方法（rNPV / SOTP）披露表。

    仅在引擎输出 rnpv_valuation / sotp_valuation 启用且 value 非空时渲染。
    rNPV：逐管线 PoS / 峰值销售 / 上市年份 / rNPV + 生命周期剖面口径的可复算说明。
    SOTP：逐分部价值 / 持股 / 贡献 + EV→股权价值的加总桥（含控股折价）。
    """
    rn = out.get("rnpv_valuation") or {}
    st = out.get("sotp_valuation") or {}
    blocks = []
    if rn.get("enabled") and rn.get("value") is not None:
        rows = []
        for p in rn.get("pipelines_detail") or []:
            if p.get("value") is None and p.get("rnpv") is None:
                rows.append((_esc(p.get("name")), _esc(p.get("phase") or "—"), "—", "—", "—",
                             _esc(p.get("note") or "缺参数")))
                continue
            rows.append((_esc(p.get("name")), _esc(p.get("phase")), f"{_fmt(p.get('pos'), 2)}",
                         f"{_fmt(p.get('peak_sales'))} 亿（Y{p.get('launch_year')} 上市）",
                         _fmt(p.get("rnpv")),
                         f"风险调整收入现值 {_fmt(p.get('pv_risk_adjusted_revenue'))} − 研发成本现值 {_fmt(abs(_num(p.get('pv_rnd_cost')) or 0))}"))
        tbl = _table(["管线", "阶段", "成功率 PoS", "峰值销售 / 上市", "rNPV（亿元）", "拆解"], rows,
                     num_cols=[2, 4])
        blocks.append(
            '<h3>7.3.2 rNPV 管线估值披露（v3.19.0 B）</h3>'
            f'{tbl}'
            f'<p class="small">口径：<b>rNPV = Σ_t [ PoS × 风险调整现金流_t / (1+r)^t ]</b>，'
            f'r = {_pct(rn.get("discount_rate"))}。收益按上市成功率 PoS 概率加权（<b>成本不乘 PoS</b>，保守口径）；'
            f'生命周期剖面 = 上市后爬坡 4 年 → 峰值 → 专利悬崖线性衰减 8 年 → 残值 10%。'
            f'合计：{_fmt(rn.get("n_pipelines"), 0)} 条管线，风险调整收入现值 {_fmt(rn.get("pv_risk_adjusted_revenue"))} 亿元、'
            f'研发成本现值 {_fmt(abs(_num(rn.get("pv_rnd_cost")) or 0))} 亿元 → rNPV <b>{_fmt(rn.get("value"))} 亿元</b>。'
            f'PoS 取自业界区间中值（preclinical 0.10 / I 期 0.20 / II 期 0.35 / III 期 0.60 / NDA 0.80），'
            f'可由 rnpv.pos_overrides 逐管线覆盖；可比法作交叉验证。</p>')
    if st.get("enabled") and st.get("value") is not None:
        rows = []
        for s in st.get("segments_detail") or []:
            if s.get("value") is None:
                rows.append((_esc(s.get("name")), "—", "—", "—", _esc(s.get("note") or "缺价值")))
                continue
            rows.append((_esc(s.get("name")), f"{_fmt(s.get('value'))} 亿",
                         f"{_fmt(s.get('stake'), 2)}", f"{_fmt(s.get('contribution'))} 亿",
                         _esc(s.get("method"))))
        tbl = _table(["分部", "分部价值", "持股比例", "加权贡献（亿元）", "分部法口径"], rows,
                     num_cols=[1, 2, 3])
        blocks.append(
            '<h3>7.3.3 SOTP 分部加总披露（v3.19.0 C）</h3>'
            f'{tbl}'
            f'<p class="small">加总桥：Σ(分部价值×持股) <b>{_fmt(st.get("sum_segment_value"))} 亿</b>'
            f' ＋ 联营/金融资产 {_fmt(st.get("associates_value"))} 亿 ＝ EV {_fmt(st.get("ev_sum"))} 亿'
            f' － 净债 {_fmt(st.get("net_debt"))} 亿 ＝ 折价前股权 {_fmt(st.get("equity_before_discount"))} 亿'
            f' × (1 − 控股折价 {_pct(st.get("holdco_discount"))}) ＝ <b>{_fmt(st.get("value"))} 亿元</b>。'
            f'控股折价依据：{_esc(st.get("holdco_discount_basis"))}（上限 40%；分部越多、异构度越高折价越接近上沿）。'
            f'分部价值采用「输入+加总」口径（分部法价值由外部给定，引擎不重跑分部 DCF），可审计；'
            f'可比法作交叉验证。</p>')
    return "".join(blocks)


def svg_four_part(fp, base_value=None, weighted_mid=None, ci90=None, scen_w=None):
    """四部分合成构成条（v3.15.0 / 版式 v3.16.3）。

    呈现 Base 情景下 ①DCF ②可比法 ③舆情 的值与权重，并给出**可复算**的合成等式：
      Base 合成 = Σ(值 × 权重)，再由情景权重加权为综合中枢。
    两端等式均与引擎输出逐位对齐，避免"读者复算对不上"。
    """
    if not fp:
        return ""
    parts = [
        ("① DCF 现金流贴现", fp.get("part1_dcf") or {}, "a"),
        ("② 可比公司法（含质量）", fp.get("part2_comparable_quality") or {}, "b"),
        ("③ 市场舆情（仅情绪）", fp.get("part3_market_sentiment") or {}, "c"),
    ]
    vals, ws = [], []
    for label, d, cls in parts:
        vals.append(_num(d.get("value")) or 0.0)
        ws.append(_num(d.get("weight")) or 0.0)
    if not any(vals):
        return ""
    mx = max(vals) or 1.0
    rows = []
    for (label, _d, cls), v, w in zip(parts, vals, ws):
        rows.append(
            '<div class="row">'
            f'<div class="k">{_esc(label)}</div>'
            f'<div class="track"><div class="fill {cls}" style="width:{max(0.6, v / mx * 100):.2f}%"></div></div>'
            f'<div class="v">{_fmt(v)} 亿　× {w:.2f}</div></div>')
    contrib = sum(v * w for v, w in zip(vals, ws))
    eq = ("<div class='eq'>Base 情景四部分合成：<b>"
          + " ＋ ".join(f"{w:.2f} × {_fmt(v)}" for v, w in zip(vals, ws))
          + f" ＝ {_fmt(contrib)} 亿元</b>")
    if weighted_mid is not None and scen_w:
        eq += (f"；再按情景权重 {scen_w.get('bear')}/{scen_w.get('base')}/{scen_w.get('bull')}"
               f"（Bear/Base/Bull）加权 → 综合中枢 <b>{_fmt(weighted_mid)} 亿元</b>")
    elif weighted_mid is not None:
        eq += f"；综合中枢 <b>{_fmt(weighted_mid)} 亿元</b>（含情景加权）"
    if ci90 and len(ci90) == 2:
        eq += f"。④ 统计检验：MC P5–P95 ＝ [{_fmt(ci90[0])}, {_fmt(ci90[1])}] 亿元"
    eq += "。③ 不含质量与流动性折扣；②③ 共用可比基数，不计作两条独立路径。</div>"
    return '<div class="stack">' + "".join(rows) + eq + "</div>"


def svg_trend(rev_by_year, rev_latest=None):
    """营收趋势折线（面积 + 折线 + 网格 + 数据标注）。返回纯 SVG，图注由 _fig 承载。

    v3.16.5：viewBox 宽度归一为 1000（≈容器宽度，缩放比≈1），图内文字统一 CHART_FS。
    """
    items = sorted((rev_by_year or {}).items(), key=lambda kv: kv[0])
    if len(items) < 2:
        return ""
    vals = [float(v) for _, v in items]
    years = [str(k) for k, _ in items]
    max_v = max(vals) * 1.25 or 1
    w, h, pad_l, pad_b, pad_t = 1000, 340, 80, 46, 40
    plot_w, plot_h = w - pad_l - 30, h - pad_b - pad_t
    base_y = pad_t + plot_h
    pts = []
    for i, v in enumerate(vals):
        x = pad_l + i * plot_w / (len(vals) - 1)
        y = base_y - v / max_v * plot_h
        pts.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pad_l},{base_y} " + poly + f" {pts[-1][0]:.1f},{base_y}"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#fff" stroke="#123A7E" stroke-width="3"/>'
                   for x, y in pts)
    labels = "".join(
        f'<text x="{x:.1f}" y="{y - 14:.1f}" text-anchor="middle" font-size="{CHART_FS}" fill="#0B2A5B" font-weight="600">{v:,.2f}</text>'
        for (x, y), v in zip(pts, vals))
    year_labels = "".join(f'<text x="{x:.1f}" y="{base_y + 26:.1f}" text-anchor="middle" font-size="{CHART_FS}" fill="#5F6470">{y}</text>'
                          for (x, y), y in zip(pts, years))
    grid = "".join(
        f'<line x1="{pad_l}" y1="{base_y - frac * plot_h:.1f}" x2="{w - 30}" y2="{base_y - frac * plot_h:.1f}" '
        f'stroke="#E4E7EE" stroke-width="1" stroke-dasharray="5 5"/>'
        for frac in (0.5, 1.0))
    return f'''<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="营收趋势">
  <defs><linearGradient id="revfill" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#123A7E" stop-opacity="0.16"/>
    <stop offset="100%" stop-color="#123A7E" stop-opacity="0.01"/></linearGradient></defs>
  {grid}
  <line x1="{pad_l}" y1="{base_y}" x2="{w - 30}" y2="{base_y}" stroke="#D3D9E4" stroke-width="1.4"/>
  <polygon points="{area}" fill="url(#revfill)"/>
  <polyline points="{poly}" fill="none" stroke="#123A7E" stroke-width="3.5" stroke-linejoin="round"/>
  {dots}{labels}{year_labels}
</svg>'''


def svg_method_bars(items):
    """多方法估值对比柱状图（含网格线）。items=[(标签, 数值)] 取前 6。

    v3.16.5：viewBox 宽度固定 1000，柱位按可用宽度**均分**（不再随方法数改变画布宽度，
    避免"柱数少时字形被放大"），图内文字统一 CHART_FS。
    """
    items = [it for it in items if it[1] is not None][:6]
    if not items:
        return "<p>无可用方法对比数据</p>"
    max_v = max(v for _, v in items)
    w, base_h, plot_h = 1000, 300, 240
    left, right, gap = 96, 40, 26
    n = len(items)
    slot = (w - left - right - gap * (n - 1)) / n
    bar_w = slot * 0.62
    parts = [f'<svg viewBox="0 0 {w} 360" width="100%" role="img" aria-label="多方法估值对比">']
    parts.append(f'<line x1="{left}" y1="{base_h}" x2="{w - right}" y2="{base_h}" stroke="#C9CCD4" stroke-width="1.4"/>')
    for grid_v in (0.5, 0.75):
        gy = base_h - grid_v * plot_h
        parts.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{w - right}" y2="{gy:.1f}" stroke="#E3E6EC" stroke-width="1" stroke-dasharray="5 5"/>')
        parts.append(f'<text x="{left - 10}" y="{gy + 5:.1f}" text-anchor="end" font-size="{CHART_FS}" fill="#888780">{max_v * grid_v:.0f}</text>')
    for i, (label, v) in enumerate(items):
        h = int(plot_h * v / max_v) if max_v else 0
        x = left + i * (slot + gap) + (slot - bar_w) / 2
        parts.append(f'<rect x="{x:.1f}" y="{base_h - h}" width="{bar_w:.1f}" height="{h}" rx="5" fill="#123A7E"/>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{base_h - h - 10}" text-anchor="middle" font-size="{CHART_FS}" font-weight="600" fill="#0B2A5B">{_fmt(v)}</text>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{base_h + 26}" text-anchor="middle" font-size="{CHART_FS}" fill="#5F5E5A">{_esc(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_elasticity(items):
    """参数弹性横向条形图（±1σ 对估值影响 %）。items=[(标签, 弹性%)] 取前 5。

    v3.16.5：viewBox 宽度归一为 1000；左侧为标签列（右对齐至 x=350）、中轴 x=690、
    双向半幅 250，**标签列与负向条互不重叠**；图内文字统一 CHART_FS。
    """
    items = [it for it in items if it[1] is not None][:5]
    if not items:
        return "<p>无弹性数据</p>"
    max_abs = max(abs(v) for _, v in items) or 1
    w, axis, half, rowh, barh = 1000, 690, 250, 54, 26
    scale = half / max_abs
    h = 24 + len(items) * rowh
    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="参数弹性排序">']
    parts.append(f'<line x1="{axis}" y1="10" x2="{axis}" y2="{h - 14}" stroke="#C9CCD4" stroke-width="1.2"/>')
    for i, (label, v) in enumerate(items):
        y = 16 + i * rowh
        bw = int(abs(v) * scale)
        if v >= 0:
            parts.append(f'<rect x="{axis}" y="{y}" width="{bw}" height="{barh}" fill="#123A7E"/>')
            parts.append(f'<text x="{axis + bw + 10}" y="{y + 19}" font-size="{CHART_FS}" fill="#0B2A5B" font-weight="600">{v:+.1f}%</text>')
        else:
            parts.append(f'<rect x="{axis - bw}" y="{y}" width="{bw}" height="{barh}" fill="#C9A227"/>')
            parts.append(f'<text x="{axis - bw - 10}" y="{y + 19}" text-anchor="end" font-size="{CHART_FS}" fill="#854F0B" font-weight="600">{v:+.1f}%</text>')
        parts.append(f'<text x="{axis - half - 90}" y="{y + 19}" text-anchor="end" font-size="{CHART_FS}" fill="#5F5E5A">{_esc(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------- 表格组件 ----------

def _table(headers, rows, hl_cols=None, hl_rows=None, warn_rows=None, ok_rows=None, num_cols=None):
    hl_cols, hl_rows = hl_cols or [], hl_rows or []
    warn_rows, ok_rows = warn_rows or [], ok_rows or []
    num_cols = num_cols or []
    thead = "".join(f"<th{' class=r' if i in num_cols else ''}>{_esc(h)}</th>" for i, h in enumerate(headers))
    trs = []
    for ri, row in enumerate(rows):
        tds = []
        for ci, cell in enumerate(row):
            cls = []
            if ci in hl_cols:
                cls.append("hl")
            if ri in hl_rows:
                cls.append("hl-row")
            if ci in num_cols:
                cls.append("r")
            style = f' class="{" ".join(cls)}"' if cls else ""
            tds.append(f"<td{style}>{cell}</td>")
        row_cls = " class='warn'" if ri in warn_rows else (" class='ok'" if ri in ok_rows else "")
        trs.append(f"<tr{row_cls}>{''.join(tds)}</tr>")
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(trs)}</tbody></table>"


def _kv_table(pairs):
    rows = "".join(f"<tr><th style='width:26%'>{_esc(k)}</th><td>{v}</td></tr>" for k, v in pairs)
    return f"<table class='kv'><tbody>{rows}</tbody></table>"


def _peer_screening_html(ps):
    """§4.1c 可比公司筛选证据链（v3.20.0）。未激活时返回空串 → 旧输入报告逐字节不变。

    披露四期改造的产出：一期长名单/剔除台账与信息截点、二期规模双口径 5 倍诊断、
    三期实体去重与会计准则闸、四期次新股剔除与指数锚降权。
    全部数字取自引擎 peer_screening 输出块，生成器不做任何计算。
    """
    if not ps or not ps.get("enabled"):
        return ""
    st = ps.get("stages") or {}
    ll, cut, sc = st.get("s1_long_list") or {}, st.get("s1_cutoff") or {}, st.get("s2_scale") or {}
    dd, ac = st.get("s3_dedupe") or {}, st.get("s3_accounting") or {}
    se, ix = st.get("s4_seasoning") or {}, st.get("s4_index_anchor") or {}
    eff, pol = ps.get("effective_sample") or {}, ps.get("status_policy") or {}

    label = {"ok": "完整", "degraded": "降级", "weak": "弱化", "unavailable": "不可用"}.get(
        ps.get("status"), "—")
    keep = pol.get("weight_keep")
    intro = (f"筛选状态 <b>{label}</b>（status={_esc(ps.get('status'))}）；"
             f"有效样本 <b>{eff.get('n_eligible') if eff.get('n_eligible') is not None else '—'}</b> 家"
             f"（输入 {eff.get('n_input', '—')} → 去重后 {eff.get('n_deduped', '—')}）；"
             f"建议可比法权重保留 {_pct(keep) if keep is not None else '—'}"
             f"（{('权重让出 ' + _pct(1 - keep)) if isinstance(keep, (int, float)) and keep < 1 else '无需让出'}）。")

    # ① 一期：长名单与剔除台账
    chk = ll.get("checks") or {}
    cls, lls, rej = chk.get("classification_system") or {}, chk.get("long_list_size") or {}, chk.get("rejected") or {}
    by_type = rej.get("by_type") or {}
    type_txt = "、".join(f"{k} {v}" for k, v in sorted(by_type.items())) or "—"
    ratio = lls.get("ratio_to_final")
    ledger = _table(
        ["台账项", "取值", "判定"],
        [("行业分类基准", _esc(cls.get("value") or "未声明"),
          "可复现" if cls.get("valid") else "不可复现（不得声称已穷尽可比）"),
         ("长名单规模", f"{lls.get('value') if lls.get('value') is not None else '—'} 家；"
                        f"去重后 {lls.get('n_final', '—')} 家、有效 {lls.get('n_eligible', '—')} 家"
                        f"（比值 {_fmt(ratio, 2) if ratio else '—'}×）",
          "充分" if isinstance(ratio, (int, float)) and ratio >= 2 else "筛选过粗或未筛选"),
         ("剔除记录", f"{rej.get('n', 0)} 条（落枚举 {rej.get('typed', 0)} 条）", type_txt),
         ("样本覆盖率", _pct(ll.get("coverage")) if _num(ll.get("coverage")) is not None else "—",
          "去重后样本 ÷ 长名单（有效样本另见上方）")],
        num_cols=[1])

    # ② 一期：信息可得性截点
    if cut.get("cutoff"):
        cut_txt = (f"截点 {_esc(cut.get('cutoff'))}；越界 {len(cut.get('violations') or [])} 家、"
                   f"滞后超 {cut.get('max_lag_days')} 天 {len(cut.get('lagged') or [])} 家、"
                   f"未提供期末 {cut.get('n_missing', 0)} 家")
        cut_judge = "存在回填（违反截点）" if cut.get("violation") else "合规"
    else:
        cut_txt, cut_judge = "未提供信息可得性截点", "无法校验期间错配"

    # ③ 二期：规模双口径
    sc_rows = []
    rr, dv = sc.get("ratio") or {}, sc.get("deviation") or {}
    tgt, bench = sc.get("target") or {}, sc.get("benchmark") or {}
    if sc.get("enabled"):
        for key, name in (("revenue", "LTM 营业收入"), ("market_cap", "权益市值")):
            sc_rows.append((name,
                            _fmt(tgt.get(key)) if _num(tgt.get(key)) is not None else "—",
                            _fmt(bench.get(key + "_median")) if _num(bench.get(key + "_median")) is not None else "—",
                            f"{_fmt(rr.get(key), 2)}×" if _num(rr.get(key)) is not None else "—",
                            f"{_fmt(dv.get(key), 2)}×" if _num(dv.get(key)) is not None else "—",
                            "判定基数" if sc.get("binding") == key else "—"))
    sc_tbl = _table(["口径", "标的", "长名单中位", "比值", "偏离（取远）", "判定"], sc_rows,
                    hl_cols=[5], num_cols=[1, 2, 3, 4]) if sc_rows else ""
    sc_note = (f"以偏离更远者 <b>{_esc(sc.get('binding') or '—')}</b> 为判定基数"
               f"（{_fmt(sc.get('binding_deviation'), 2) if _num(sc.get('binding_deviation')) is not None else '—'}×，"
               f"阈值 {_fmt(sc.get('multiple'), 1)}×）→ "
               + ("<b>须先收窄到产品档次更接近的子组</b>，不得直接用长名单中位作中枢"
                  if sc.get("exceed") else "在阈值内，可直接采用")
               + f"；基数口径 {_esc(sc.get('basis') or '—')}"
               + ("（长名单中位缺失，已退化为最终样本中位代理）" if sc.get("basis") == "final_sample_proxy" else "")
               + "。")

    # ④ 三/四期：筛选例外与处置
    ex_rows = []
    for m in dd.get("merged") or []:
        ex_rows.append((_esc(m.get("name")), "同一实体重复（A/H/ADR）", "合并计一次",
                        _esc(m.get("duplicate_of") or "—")))
    for x in ac.get("cross") or []:
        ex_rows.append((_esc(x.get("name")), "会计准则与标的不同",
                        "需调节后才可进 P/E 统计", f"{_esc(x.get('standard'))} vs {_esc(x.get('target_standard'))}"))
    for x in se.get("excluded") or []:
        ex_rows.append((_esc(x.get("name")), "次新股（含炒新溢价）",
                        f"剔除（上市 {x.get('months_listed')} 月）", _esc(x.get("listing_date") or "—")))
    for x in se.get("watch") or []:
        ex_rows.append((_esc(x.get("name")), "次新观察区",
                        "保留但须做含/剔双口径", f"上市 {x.get('months_listed')} 月"))
    for x in cut.get("violations") or []:
        ex_rows.append((_esc(x.get("name")), "财报期末晚于截点",
                        "回填（违反信息截点）", _esc(x.get("financial_period_end"))))
    for x in cut.get("lagged") or []:
        ex_rows.append((_esc(x.get("name")), "财务期间滞后过大",
                        f"须披露期间错配（{x.get('lag_days')} 天）", _esc(x.get("financial_period_end"))))
    ex_tbl = (_table(["可比公司", "例外类型", "处置", "依据"], ex_rows, warn_rows=list(range(len(ex_rows))))
              if ex_rows else '<p class="sub">本次无可比筛选例外（全部样本通过七项判据）。</p>')

    # ⑤ 四期：指数锚降权
    if ix.get("used"):
        ix_txt = (f"行业指数锚按 <b>{_esc(ix.get('fallback_level'))}</b> 级使用，"
                  f"权重上限 {_fmt(ix.get('weight_cap'), 2)}"
                  f"（口径：{_esc(ix.get('basis'))}）——指数为全样本口径，不得与精选可比同级呈现。")
    else:
        ix_txt = "未启用行业指数锚，无需降权。"

    probs = ps.get("problems") or []
    prob_txt = ("；".join(_esc(p) for p in probs)) if probs else "无"

    return (
        "<h3>4.1c 可比公司筛选证据链（v3.20.0）</h3>"
        f"<p class=\"sub\">{intro}</p>"
        f"<h4>（一）长名单与剔除台账（一期 P0-1 / P0-4）</h4>{ledger}"
        f"<p class=\"sub\">信息可得性截点：{cut_txt} → <b>{cut_judge}</b>。"
        "估值基准日同时是信息截点，不得使用基准日后发布的财报回填。</p>"
        f"<h4>（二）规模双口径 5 倍诊断（二期 P0-2）</h4>{sc_tbl}"
        f"<p class=\"sub\">{sc_note}</p>"
        f"<h4>（三）筛选例外与处置（三期 P0-3 / P1-1；四期 P1-4）</h4>{ex_tbl}"
        f"<p class=\"sub\">指数锚降权（四期 P1-5）：{ix_txt}</p>"
        f"<p class=\"sub\">诊断项汇总：{prob_txt}。本块的筛选状态与建议权重由引擎输出，"
        "报告不自行重算；执行模式（enforce.filter_sample）未开启时，例外样本仅标注而不影响估值数值。</p>"
    )


# ---------- 版面骨架组件（v3.16.5：章节编号 / 图卡；目录已于 v3.16.5 取消） ----------

SECTION_TITLES = [
    "执行摘要", "核心观点（数据支撑）", "公司概况与核心业务", "行业与竞争格局",
    "财务基础", "估值方法与关键假设", "估值结果", "IPO 定价约束与发行定位",
    "风险提示", "结论与建议", "数据溯源与口径说明",
]


def _h2(i, name=None):
    """带序号徽标的章节标题（编号与 h3 的 x.y 呼应，并与正文 §x.y 引用对齐）。"""
    return (f'<h2 id="s{i}"><span class="secno">{i:02d}</span>'
            f'{_esc(name or SECTION_TITLES[i - 1])}</h2>')


def _fig(num, title, body, note=None):
    """图卡：编号徽标 + 标题 + 图形区 + 注释（统一图表容器，替代裸 svgbox）。"""
    note_html = f'<div class="fig-note">{note}</div>' if note else ""
    return (f'<figure class="fig"><figcaption class="fig-h">'
            f'<span class="fig-n">{num}</span>{_esc(title)}</figcaption>'
            f'<div class="fig-body">{body}</div>{note_html}</figure>')


# ---------- 定性论述生成（基于引擎数字的模板化解读，不产生新数字） ----------

def _build_narrative(out, stat, inp):
    syn = out.get("synthesis") or {}
    base = (out.get("scenarios") or {}).get("base") or {}
    comp = base.get("comparable") or {}
    dcf = base.get("dcf") or {}
    elast = (stat or {}).get("elasticity") or {}
    mc = (stat or {}).get("monte_carlo") or {}
    adj = (stat or {}).get("adjusted_interval") or {}
    ipo = out.get("ipo_check") or {}
    mid = _num(syn.get("weighted_mid")) or 0
    mc_p50 = _num(mc.get("p50"))
    gap = _num(syn.get("dcf_vs_comparable_gap"))

    # 弹性特征（数据驱动、行业中性）
    # v3.16.6 修复：原 else 分支硬编码「倍数×净利率双驱动——周期制造特征」，对消费/白酒类标的失真
    # ——净利率弹性 ≈0 时仍称「双驱动」，「周期制造」亦为行业专属措辞（五粮液案例已列遗留项）。
    _DRIVE_LBL = {"growth_forecast": "营收增速", "net_margin": "净利率",
                  "comparable_multiples": "可比倍数", "wacc": "WACC",
                  "terminal_growth": "永续增速", "sentiment": "情绪修正",
                  "quality_indicators": "盈利质量指标"}
    top = sorted([(k, _num(v.get("delta_pct_1sigma"))) for k, v in elast.items()
                  if isinstance(v, dict) and _num(v.get("delta_pct_1sigma")) is not None],
                 key=lambda kv: abs(kv[1]), reverse=True)
    growth_el = next((v for k, v in top if k == "growth_forecast"), None)
    margin_el = next((v for k, v in top if k == "net_margin"), None)
    multi_el = next((v for k, v in top if k == "comparable_multiples"), None)
    drive = ""
    if top:
        dom_k, dom_v = top[0]
        dom_lbl = _DRIVE_LBL.get(dom_k, dom_k)
        if growth_el is not None and dom_k == "growth_forecast":
            drive = f"估值由<b>营收增速主导</b>（弹性 {growth_el:+.1f}%）——成长驱动型"
        else:
            # 次敏感项与主导项量级相当（≥60%）才称「双驱动」，否则如实称单主导
            second = next(((k, v) for k, v in top[1:]
                           if k in ("growth_forecast", "net_margin", "comparable_multiples")), None)
            if second and dom_v and abs(second[1]) >= 0.6 * abs(dom_v):
                s_lbl = _DRIVE_LBL.get(second[0], second[0])
                drive = (f"估值由<b>{dom_lbl}×{s_lbl}双驱动</b>"
                         f"（{dom_lbl} {dom_v:+.1f}% / {s_lbl} {second[1]:+.1f}%）——增速非第一敏感")
            else:
                drive = f"估值由<b>{dom_lbl}主导</b>（弹性 {dom_v:+.1f}%）——增速非第一敏感"

    # 口径背离
    # v3.16.7：Layer 0 判否（金融/资源类）时 DCF 权重已归零，其「隐含值」是名义留痕、
    # 且对金融主体恒为高估方向 → 原「比值 <0.8 = 两口径接近/相互印证」的判读方向相反，
    # 必须改写为「不适用、不作为互证」。
    gap_note = ""
    _fw_n = out.get("framework_check") or {}
    _dcf_inadm_n = _fw_n.get("dcf_admissible") is False
    if _dcf_inadm_n:
        _dcf_legacy = _num(dcf.get("equity_value"))
        gap_note = (f"① DCF 因前提不成立而权重归零、未参与综合（Layer 0 判否；原因："
                    f"{_fw_n.get('route_reason') or '现金流不可定义／资本结构受监管'}）。"
                    f"上列「市场口径 vs DCF」比值（{_fmt(gap)}）仅为留痕口径，不构成两法互证；"
                    f"DCF 名义值 {_fmt(_dcf_legacy)} 亿元系 WACC/FCFF 口径对金融主体不适配所致，"
                    f"不构成内在价值判断")
    elif gap is not None:
        # v3.16.8：比值判读对称化。gap = 可比法值 ÷ DCF 值（1.0 = 两法一致）。
        # 原逻辑以「gap < 0.8 → 两口径接近、相互印证」判读，且仅对 gap ≥ 1.5 判「背离」——
        # 方向不对称：gap=0.69 实为可比法低于 DCF 31%（宁德时代案例：可比 12,569 亿 vs
        # DCF 18,160 亿，相差 44%），却被读作「分歧小」，与事实相反。现按 |gap − 1| 对称分档，
        # 并显式给出偏离幅度与方向。
        _dev = abs(gap - 1.0)
        _lo = gap < 1.0
        if _dev <= 0.15:
            gap_note = (f"市场口径与 DCF 内在价值基本一致（比值 {_fmt(gap)}，偏离 {_dev * 100:.0f}%）："
                        f"两口径相互印证，估值分歧小")
        elif _dev <= 0.40:
            gap_note = (f"市场口径{'低于' if _lo else '高于'} DCF 内在价值（比值 {_fmt(gap)}，"
                        f"偏离 {_dev * 100:.0f}%）："
                        + ("差异源于市场对周期位置与竞争格局的折价，两口径分歧中等，"
                           "结论以综合权重口径为准、DCF 值可作上行情景参照"
                           if _lo else
                           "差异来自情绪/成长预期溢价，两口径分歧中等，结论以综合权重口径为准"))
        else:
            gap_note = (f"市场口径与 DCF 内在价值背离显著（比值 {_fmt(gap)}，偏离 {_dev * 100:.0f}%）："
                        + ("可比法隐含市场估值显著低于 DCF 现金流内在价值——以市场口径为审慎基准、"
                           "DCF 作为上行情景，须在结论中标注两口径分歧"
                           if _lo else
                           "市场口径含情绪/成长预期溢价，DCF 反映自由现金流现实——"
                           "以市场口径为主、DCF 为风险下限的定价框架更审慎"))

    # 发行定位 / 已上市标的市场定位（v3.16.4：已上市须并列「市场价 vs 模型隐含价」双口径）
    issue_mv = _num(ipo.get("issue_market_cap"))
    _fu = (inp or {}).get("fundraising") or {}
    _mkt_mv, _mkt_px = _num(_fu.get("market_cap")), _num(_fu.get("market_price"))
    _ps_model = _num(ipo.get("price_per_share"))
    issue_note = ""
    if issue_mv and mid:
        dev = (issue_mv - mid) / mid * 100
        if dev < -15:
            issue_note = (f"发行估值约 {_fmt(issue_mv)} 亿元显著低于模型中枢 {_fmt(mid)} 亿（{dev:+.0f}%），"
                          f"发行定价审慎、上市后存在估值修复空间")
        elif dev > 15:
            issue_note = f"发行估值约 {_fmt(issue_mv)} 亿元高于模型中枢 {_fmt(mid)} 亿（{dev:+.0f}%），发行定价偏乐观"
        else:
            issue_note = f"发行估值约 {_fmt(issue_mv)} 亿元与模型中枢 {_fmt(mid)} 亿基本一致（{dev:+.0f}%），定价合理"
    elif _mkt_mv and mid:
        dev = (_mkt_mv - mid) / mid * 100
        _px_txt = (f"（现价 {_fmt(_mkt_px)} 元/股、模型隐含 {_fmt(_ps_model)} 元/股）"
                   if _mkt_px and _ps_model else "")
        if abs(dev) <= 5:
            issue_note = (f"已上市标的：市场现价隐含总市值约 {_fmt(_mkt_mv)} 亿元，与模型综合中枢 {_fmt(mid)} 亿元"
                          f"基本一致（{dev:+.1f}%），市场价格已反映内在价值{_px_txt}")
        elif dev > 0:
            issue_note = (f"已上市标的：市场现价隐含总市值约 {_fmt(_mkt_mv)} 亿元，较模型综合中枢 {_fmt(mid)} 亿元"
                          f"溢价 {abs(dev):.1f}%，市场预期已高于模型内在价值{_px_txt}")
        else:
            issue_note = (f"已上市标的：市场现价隐含总市值约 {_fmt(_mkt_mv)} 亿元，较模型综合中枢 {_fmt(mid)} 亿元"
                          f"折价 {abs(dev):.1f}%，存在估值修复空间{_px_txt}")

    # 统计稳健性
    rob_note = ""
    if mc_p50 and mid:
        dev = (mc_p50 - mid) / mid * 100
        rob_note = (f"点估计中枢与 MC 中位数偏差 {dev:+.1f}%，"
                    f"{'点估计稳健' if abs(dev) < 5 else '存在统计分歧，建议以统计区间为主口径'}")

    # 弹性变量名中文化（v3.16.5 可读性）：仅做展示映射，未知键回落原文；数值仍取引擎输出
    # v3.16.6：与上方 drive 文案共用同一映射 _DRIVE_LBL（消除重复定义导致的措辞漂移）
    elast_top = [(_DRIVE_LBL.get(k, k), v) for k, v in top[:5]]

    return {
        "drive": drive, "gap_note": gap_note, "issue_note": issue_note, "rob_note": rob_note,
        "elast_top": elast_top, "confidence": (out.get("confidence") or {}),
    }


CSS = """
:root{
  --navy:#123A7E;--navy-deep:#0B2A5B;--navy-ink:#071B36;
  --gold:#C9A227;--gold-deep:#8A6D14;--gold-soft:#FBF3D6;
  --ink:#20242B;--gray:#5F6470;--gray2:#8B909B;
  --bg:#FFFFFF;--panel:#F7F8FA;--panel2:#EDF1F7;
  --line:#E4E7EE;--line2:#D3D9E4;
  --up:#D8352A;--down:#0F8A5F;--warn-bg:#FDF1E3;--ok-bg:#E9F6F0;
  --r:10px;--r-sm:6px;
  --sh-sm:0 1px 2px rgba(11,42,91,.06);
  --sh:0 2px 10px rgba(11,42,91,.07);
  --sh-lg:0 10px 30px rgba(11,42,91,.10);
  /* ── 字号令牌（v3.16.5 统一字号）──
     正文级文字（正文/表格/注释/图注/标签/页眉/页脚）统一 --fs；展示型数字（KPI）统一 --fs-num；
     标题层级保留阶梯 h1>h2>h3>h4；图内文字由 Python 常量 CHART_FS 统一（与 --fs 等值）。 */
  --fs:14px;--fs-num:24px;
  --fs-h1:22px;--fs-h2:18px;--fs-h3:15.5px;--fs-h4:var(--fs);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.72;font-size:var(--fs);
     font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei UI","Microsoft YaHei","Source Han Sans SC","Noto Sans CJK SC","Helvetica Neue",Arial,sans-serif;
     -webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 1}
.page{max-width:1120px;margin:0 auto;padding:0 36px 84px;border-top:4px solid var(--navy)}
/* ── 页眉（v3.16.13：改为「上下结构」——企业简介（品牌行＋标题＋副题）在上，
     报告元信息条（报告编号／估值基准日／上市板块／引擎／统计／抽样）在下。
     原左右结构下，右侧 `text-align:right;white-space:nowrap` 的元信息在长文本
     （如 exchange 含上市沿革、note_asset_type 为长段说明）时会占去大量横向空间，
     把左侧企业简介挤压成窄列 → 副题折行十余行、页眉纵向异常高大。改为上下结构后，
     两行各占整幅宽度，元信息在条内自然折行，纵向高度显著收敛。 ── */
.masthead{display:block;padding:26px 0 20px;border-bottom:1px solid var(--line2)}
.masthead .brand{display:flex;align-items:center;gap:8px;font-size:var(--fs);color:var(--navy);font-weight:700;letter-spacing:2.2px}
.masthead .brand::before{content:"";width:13px;height:13px;background:var(--gold);border-radius:3px}
h1{font-size:var(--fs-h1);line-height:1.34;color:var(--navy-deep);font-weight:700;margin:10px 0 6px;letter-spacing:-.2px}
.masthead .sub{color:var(--gray);font-size:var(--fs)}
.masthead .meta{display:block;margin-top:18px;padding:11px 18px;background:linear-gradient(180deg,#fff,var(--panel));border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:var(--r-sm);box-shadow:var(--sh-sm);font-size:var(--fs);color:var(--gray);line-height:1.85}
.masthead .meta .m{white-space:normal}
.masthead .meta .k{margin-right:6px}
.masthead .meta .v{color:var(--navy-deep);font-weight:600}
.masthead .meta .sep{margin:0 10px;color:var(--line2)}
/* ── 标题层级 ── */
h2{display:flex;align-items:center;gap:11px;font-size:var(--fs-h2);color:var(--navy-deep);font-weight:700;margin:44px 0 16px;padding-bottom:10px;border-bottom:2px solid var(--line);scroll-margin-top:16px}
h2 .secno{display:inline-flex;align-items:center;justify-content:center;min-width:38px;height:26px;padding:0 9px;background:linear-gradient(150deg,var(--navy),var(--navy-deep));color:#fff;border-radius:var(--r-sm);font-size:var(--fs);font-weight:700;letter-spacing:1px;font-variant-numeric:tabular-nums;flex:none}
h2::after{content:"";flex:1;height:2px;margin-left:4px;background:linear-gradient(90deg,var(--gold),rgba(201,162,39,0))}
h3{font-size:var(--fs-h3);color:var(--navy-deep);font-weight:600;margin:26px 0 10px;padding-left:10px;border-left:3px solid var(--gold)}
h4{font-size:var(--fs-h4);color:var(--navy);font-weight:600;margin:18px 0 8px;letter-spacing:.2px}
p{margin:9px 0;text-align:justify}
.sub{color:var(--gray);font-size:var(--fs)}
/* ── KPI 卡（展示型数字统一 --fs-num） ── */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:18px 0}
.kpi{background:linear-gradient(180deg,#fff,var(--panel));border:1px solid var(--line);border-top:3px solid var(--navy);border-radius:var(--r);padding:15px 17px;box-shadow:var(--sh-sm)}
.kpi .label{font-size:var(--fs);color:var(--gray)}
.kpi .value{font-size:var(--fs-num);line-height:1.3;font-weight:700;color:var(--navy-deep);margin:5px 0 3px;letter-spacing:-.4px;font-variant-numeric:tabular-nums}
.kpi .value.gold{color:var(--gold-deep)}
.kpi .note{font-size:var(--fs);color:var(--gray);line-height:1.6}
.kpi.hl{background:linear-gradient(155deg,var(--navy),var(--navy-deep));border-color:transparent;border-top-color:var(--gold);box-shadow:var(--sh)}
.kpi.hl .label,.kpi.hl .note{color:#AFC3E6}
.kpi.hl .value{color:#fff}
/* ── 区间条 ── */
.rangebar{margin:16px 0 6px}
.rangebar .axis{position:relative;height:24px;background:linear-gradient(90deg,#EDF2FB,#DCE6F5);border-radius:var(--r-sm);margin:6px 0}
.rangebar .bar{position:absolute;top:2px;height:20px;background:linear-gradient(90deg,var(--navy),#2A5AA8);border-radius:5px;box-shadow:var(--sh-sm)}
.rangebar .bar.gold{background:linear-gradient(90deg,var(--gold),#E0BE55)}
.rangebar .midmark{position:absolute;top:-3px;height:30px;width:2px;background:var(--navy-ink);border-radius:1px}
.rangebar .labels{display:flex;justify-content:space-between;font-size:var(--fs);color:var(--gray);margin-top:4px}
.rangebar .labels b{color:var(--navy-deep);font-size:var(--fs)}
.rangebar .cap{font-size:var(--fs);color:var(--gray);margin-top:2px}
/* ── 表格 ── */
table{width:100%;border-collapse:separate;border-spacing:0;font-size:var(--fs);background:#fff;border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--sh-sm);margin:14px 0}
th{background:linear-gradient(180deg,var(--navy),var(--navy-deep));color:#fff;font-weight:600;padding:10px 13px;text-align:left;white-space:nowrap}
th:first-child{border-top-left-radius:var(--r)}
th:last-child{border-top-right-radius:var(--r)}
td{padding:9px 13px;border-top:1px solid var(--line);vertical-align:top}
tbody tr:nth-child(even) td{background:#F6F8FC}
tbody tr:hover td{background:#EDF3FB}
td.r,th.r{text-align:right}
td.hl{color:var(--gold-deep);font-weight:700}
tr.hl-row td{background:var(--gold-soft)!important;font-weight:600}
tr.warn td{background:var(--warn-bg)!important}
tr.ok td{background:var(--ok-bg)!important}
.up{color:var(--up);font-weight:600}.down{color:var(--down);font-weight:600}
.num{font-variant-numeric:tabular-nums}
table.kv th{background:#F1F4F9;color:var(--navy-deep);white-space:normal;border-top:1px solid var(--line)}
table.kv td{background:#fff!important}
table.kv tbody tr:nth-child(even) th{background:#EDF1F8}
/* ── 标签 / 高亮 ── */
.tag{display:inline-block;padding:2px 10px;border-radius:11px;font-size:var(--fs);font-weight:600;white-space:nowrap}
.tag.warn{background:#FCE8D9;color:#B4511C}
.tag.ok{background:#DDF2E6;color:#0F6E56}
.tag.navy{background:#DEE8F7;color:var(--navy)}
.hl{background:linear-gradient(transparent 62%,var(--gold-soft) 62%);padding:0 1px}
/* ── 结论框（v3.16.5：结论条 .verdict 已取消，区间大字改由 KPI 卡承载） ── */
.callout{border-left:4px solid var(--gold);background:var(--panel);padding:15px 20px;margin:18px 0;border-radius:0 var(--r) var(--r) 0;box-shadow:var(--sh-sm)}
.callout b{color:var(--navy-deep)}
.callout p:first-child{margin-top:0}.callout p:last-child{margin-bottom:0}
.callout.alert{border-left-color:var(--up);background:var(--warn-bg)}
/* ── 图卡 ── */
.fig{margin:18px 0;border:1px solid var(--line);border-radius:var(--r);background:linear-gradient(180deg,#fff,var(--panel));box-shadow:var(--sh-sm);overflow:hidden}
.fig-h{display:flex;align-items:center;gap:9px;padding:11px 18px;font-size:var(--fs);color:var(--navy-deep);font-weight:600;border-bottom:1px solid var(--line);background:#FBFCFE}
.fig-n{display:inline-flex;align-items:center;height:22px;padding:0 9px;background:var(--gold-soft);color:var(--gold-deep);border-radius:var(--r-sm);font-size:var(--fs);font-weight:700;letter-spacing:.5px}
.fig-body{padding:16px 18px 8px}
.fig-body svg{display:block;width:100%;height:auto}
.fig-note{padding:0 18px 12px;font-size:var(--fs);color:var(--gray);line-height:1.65}
.svgbox{margin:18px 0;padding:16px 18px;border:1px solid var(--line);border-radius:var(--r);background:linear-gradient(180deg,#fff,var(--panel));box-shadow:var(--sh-sm)}
.svgbox .cap{font-size:var(--fs);color:var(--gray);margin-top:6px;text-align:center}
/* ── 构成堆叠条 ── */
.stack{margin:16px 0}
.stack .row{display:grid;grid-template-columns:168px 1fr 124px;gap:12px;align-items:center;margin:7px 0;font-size:var(--fs)}
.stack .k{color:var(--gray)}
.stack .track{position:relative;height:20px;background:var(--panel2);border-radius:5px;overflow:hidden}
.stack .fill{position:absolute;left:0;top:0;height:100%;border-radius:5px;background:linear-gradient(90deg,var(--navy),#2A5AA8)}
.stack .fill.g{background:linear-gradient(90deg,var(--gold),#E0BE55)}
.stack .fill.s{background:linear-gradient(90deg,#5F6470,#8890A0)}
.stack .v{text-align:right;font-variant-numeric:tabular-nums;color:var(--navy-deep);font-weight:600}
.stack .eq{margin-top:10px;padding-top:10px;border-top:1px dashed var(--line2);font-size:var(--fs);color:var(--gray)}
.stack .eq b{color:var(--navy-deep)}
/* ── 布局（缺省单列纵向堆叠） ── */
.grid2{display:grid;grid-template-columns:1fr;gap:18px}
ul,ol{margin:8px 0 8px 22px}li{margin:5px 0}
.foot{margin-top:52px;padding-top:16px;border-top:2px solid var(--navy);font-size:var(--fs);color:var(--gray);line-height:1.8}
/* ── 打印（A4；字号令牌整体收敛，保持"统一字号"在打印态同样成立） ── */
@media print{
  @page{size:A4;margin:14mm 12mm}
  :root{--fs:11.5px;--fs-num:19px;--fs-h1:19px;--fs-h2:15px;--fs-h3:13px}
  html{scroll-behavior:auto}
  body{line-height:1.6;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .page{max-width:none;padding:0;border-top:0}
  .no-print{display:none!important}
  a{color:inherit;text-decoration:none}
  thead{display:table-header-group}
  tr,.kpi,.fig,.svgbox,.callout,.stack{page-break-inside:avoid}
  table{box-shadow:none}
  h2{margin:22px 0 10px;page-break-after:avoid}
  h3{margin:14px 0 6px;page-break-after:avoid}
  th{padding:7px 9px}td{padding:6px 9px}
  .masthead{padding:0 0 12px}
  .masthead .meta{box-shadow:none;padding:9px 14px}
  .foot{margin-top:26px}
}
/* ── 响应式 ── */
@media(max-width:860px){
  .page{padding:0 18px 60px}
  .masthead .meta{padding:10px 13px}
  .masthead .meta .sep{margin:0 6px}
  .kpis{grid-template-columns:1fr 1fr}
  .stack .row{grid-template-columns:116px 1fr 100px}
}
@media(max-width:560px){.kpis{grid-template-columns:1fr}.stack .row{grid-template-columns:1fr;gap:2px}}
"""


def generate_report(out, stat=None, inp=None):
    meta = out.get("meta") or {}
    syn = out.get("synthesis") or {}
    conf = out.get("confidence") or {}
    base = (out.get("scenarios") or {}).get("base") or {}
    comp = base.get("comparable") or {}
    dcf = base.get("dcf") or {}
    ipo = out.get("ipo_check") or {}
    sens = out.get("sensitivity") or {}
    company = meta.get("company") or "估值标的"
    as_of = meta.get("as_of_date") or "—"
    asset_type = meta.get("asset_type") or "未指定"
    eng_ver = out.get("engine_version", "?")
    stat_ver = (stat or {}).get("meta", {}).get("stat_version", "?")
    n = (stat or {}).get("meta", {}).get("n", 3000)
    seed = (stat or {}).get("meta", {}).get("seed", 42)
    report_no = f"VAL-{datetime.now().strftime('%Y%m%d')}-{(datetime.now().hour * 100 + datetime.now().minute):05d}"
    narr = _build_narrative(out, stat, inp)

    fin = (inp or {}).get("financials") or {}
    cmps = (inp or {}).get("comparables") or []
    idx = (inp or {}).get("industry_index") or {}
    meta_inp = (inp or {}).get("meta") or {}

    # v3.16.7：Layer 0 前提判别门（framework_check）「DCF 不适用」披露开关。
    # dcf_admissible is False（金融/资源类）时引擎已把 dcf 权重归零，报告层须同步改写
    # §2/§6.1/§7.1/§7.2 与 narrative 口径关系，避免把「DCF 名义留痕值」误读为并行法结果。
    # 其余输入（含 conditional 档：权重非 0）_dcf_inadm=False → 逐字块不变（旧输入零变化）。
    _fw = out.get("framework_check") or {}
    _dcf_inadm = _fw.get("dcf_admissible") is False
    # v3.19.0 P6-B/C：替代主方法（rNPV/SOTP）权重（§7.1 表与综合推导共用；缺省不存在 → 各表不加行）
    _alt_w = out.get("weights") or {}

    # v3.16.7：置信度构成透出（Step 6「置信度总评」缺项补齐）。
    # 引擎 confidence 的两条折减机制（method_coverage / method_divergence）原仅存于输出 JSON，
    # 报告只给最终档位而无理由。此处逐项拼接**引擎已输出的数值**——
    # 生成器不产生任何新数字，亦不自行重算乘积（避免与引擎口径漂移）。
    _conf_terms = []
    if conf.get("data_completeness") is not None:
        _conf_terms.append(f"数据完整性 {_fmt(conf.get('data_completeness'), 2)}")
    if conf.get("quality_score") is not None:
        _conf_terms.append(f"盈利质量分 {_fmt(conf.get('quality_score'), 1)}/{_fmt(QUALITY_SCORE_DEFAULT, 0)}")
    _conf_terms.append("多因子校准层 " + ("已启用" if conf.get("ff_calibrated") else "未启用（系数 0.90）"))
    _conf_base_txt = " × ".join(_conf_terms)
    _conf_disc_txt, _conf_cap = None, None
    _mcov = conf.get("method_coverage") or {}
    _mdiv = conf.get("method_divergence") or {}
    if _mcov:
        _inapp = "/".join(conf.get("methods_inapplicable") or []) or "—"
        _conf_disc_txt = (
            f"方法覆盖度折扣 ×{_fmt(_mcov.get('diversity_factor'), 3)}"
            f"（有效方法 {_fmt(_mcov.get('effective_method_count'), 0)} 个；不适用 {_inapp}）")
        _conf_cap = _mcov.get("level_cap")
    if _mdiv:
        _seg = (f"方法分歧度折扣 ×{_fmt(_mdiv.get('divergence_factor'), 3)}"
                f"（CV {_fmt(_mdiv.get('method_cv'), 3)} ＞ 阈值 {_fmt(_mdiv.get('cv_cap'), 2)}）")
        _conf_disc_txt = f"{_conf_disc_txt}；{_seg}" if _conf_disc_txt else _seg
        _conf_cap = _mdiv.get("level_cap") or _conf_cap
    if not _conf_disc_txt:
        _conf_disc_txt = (
            f"未触发折减（方法间离散度 CV {_fmt(syn.get('method_cv'), 3)} 未超阈值，"
            f"且有效方法覆盖充足）")
    _conf_cap_txt = f"，置信度封顶「{_esc(_conf_cap)}」档" if _conf_cap else ""
    _conf_detail = (
        f"<b>置信度构成：</b>{_conf_base_txt}"
        f"，为数据可支撑度；折减项 {_conf_disc_txt}{_conf_cap_txt}"
        f"；可用方法 {'、'.join(conf.get('methods_available') or []) or '—'}"
        f" → 综合置信度 <b>{_esc(conf.get('score'))}（{_esc(conf.get('level'))}）</b>。")

    # ---------- 一、执行摘要 ----------
    # v3.16.5：摘要去重——KPI 仅保留「中枢 / 情景区间 / MC 90%」三卡
    #（原「方法离散度」卡与「合理估值区间」结论条 .verdict 与区间卡重复，已移除；
    #  CV 属 §7.2 / §9 诊断量，区间大字由 KPI 卡承载）
    intv = syn.get("interval") or [None, None]
    mc = (stat or {}).get("monte_carlo") or {}
    adj = (stat or {}).get("adjusted_interval") or {}
    issue_mv = _num(ipo.get("issue_market_cap"))
    issue_pe = _num(ipo.get("issue_pe"))
    mid = _num(syn.get("weighted_mid"))
    mkt_mv = _num(((inp or {}).get("fundraising") or {}).get("market_cap"))
    kpis = f'''
  <div class="kpi hl"><div class="label">综合估值中枢</div><div class="value">{_fmt(syn.get('weighted_mid'))} 亿</div>
    <div class="note">Bear {_fmt(syn.get('bear_value'))} / Base {_fmt(syn.get('base_value'))} / Bull {_fmt(syn.get('bull_value'))}</div></div>
  <div class="kpi"><div class="label">综合估值区间（情景区间）</div><div class="value">{_fmt(intv[0])} – {_fmt(intv[1])} 亿</div>
    <div class="note">{_rich(meta.get('exchange') or '')} · 置信度 {_esc(conf.get('level'))}（{_esc(conf.get('score'))}）</div></div>
  <div class="kpi"><div class="label">MC 90% 区间</div><div class="value gold">{_fmt(mc.get('p5'))} – {_fmt(mc.get('p95'))} 亿</div>
    <div class="note">中位数 {_fmt(mc.get('p50'))} ｜ 均值 {_fmt(mc.get('mean'))} ± {_fmt(mc.get('std'))}</div></div>'''

    views = "".join(f"<li>{v}</li>" for v in [
        f"<b>驱动特征：</b>{narr['drive']}（§9.2 参数弹性排序）",
        f"<b>口径关系：</b>{narr['gap_note'] or '见 §7.2 综合价值推导'}",
        f"<b>统计稳健性：</b>{narr['rob_note'] or '见 §9.3 统计校验状态'}",
        f"<b>发行定位：</b>{narr['issue_note'] or '见 §8 IPO 定价约束'}",
        f"<b>补充锚：</b>融资价格法/回购/流动性折扣/净资产法/贝叶斯锚定等校验锚见 §7.4（{'已启用' if any(k in out for k in ('recent_financing_anchor','repurchase_anchor','liquidity_discount','nav_valuation','anchor_update')) else '未启用'}）",
    ])

    _si = adj.get("synthesis_interval") or [None, None]
    range_bars = (
        svg_range_bar(intv[0], intv[1], syn.get("weighted_mid"),
                      caption="① 情景区间（Bear/Base/Bull 加权中枢）")
        + svg_range_bar(mc.get("p5"), mc.get("p95"), mc.get("p50"), tone="gold",
                        caption="② MC 90% 统计区间（" + str(n) + " 次，seed=" + str(seed) + "）")
        + svg_range_bar(_si[0], _si[1], adj.get("synthesis_mid"),
                        caption="③ 修正综合区间（情景区间 ∩ MC 90%）")
    )

    # ---------- 二、核心观点表 ----------
    _comp_syn_v = _fmt((comp.get("synthesis") or {}).get("base_value"))
    _method_struct = ((f"可比 {_comp_syn_v} / DCF <b>不适用</b>（Layer 0 判否，权重 "
                       f"{_fmt(out.get('weights', {}).get('dcf'))}；名义留痕 {_fmt(dcf.get('equity_value'))} 亿元）")
                      if _dcf_inadm else
                      (f"可比 {_comp_syn_v} / DCF {_fmt(dcf.get('equity_value'))} 亿元（比值 {_fmt(syn.get('dcf_vs_comparable_gap'))}）"))
    core_rows = [
        ("估值中枢", f"{_fmt(syn.get('weighted_mid'))} 亿元", "§7.2"),
        ("统计口径", f"MC 90% {_fmt(mc.get('p5'))}–{_fmt(mc.get('p95'))} 亿元（中位 {_fmt(mc.get('p50'))}）", "§9.3"),
        ("方法结构", _method_struct, "§7.1"),
        ("主导变量", "、".join(f"{k} {v:+.1f}%" for k, v in narr["elast_top"][:3]), "§9.2"),
        ("定价参考", (f"发行市值 {_fmt(issue_mv)} 亿元（PE {_fmt(issue_pe)}）" if issue_mv
                      else (f"市场市值 {_fmt(mkt_mv)} 亿元 vs 模型中枢 {_fmt(mid)} 亿元"
                            if mkt_mv else "—")), "§8"),
    ]

    # ---------- 三、公司概况 ----------
    rev_by_year = fin.get("revenue_by_year") or {}
    trend_svg = svg_trend(rev_by_year, fin.get("revenue_latest_ttm"))
    _tp = meta_inp.get("target_profile") or {}
    _TPMAP = {"baijiu": "白酒", "branded_baijiu": "品牌白酒自产自销", "mega": "千亿级", "large": "百亿级",
              "small": "中小型", "startup": "初创期", "growth": "成长期", "mature": "成熟期", "decline": "衰退期",
              "chip": "芯片设计", "power": "电力设备"}
    _tp_txt = "／".join(_TPMAP.get(str(_tp.get(k)), str(_tp.get(k))) for k in ("segment", "mode", "scale", "growth_stage") if _tp.get(k))
    _ind_txt = _rich(meta_inp.get("industry") or "—")
    biz_rows = [
        ("资产类型", f"{_esc(meta_inp.get('asset_type') or asset_type)}（引擎 asset_adapter 主方法建议）"),
        ("TTM 营收", f"{_fmt(fin.get('revenue_latest_ttm'))} 亿元（净利 {_fmt(fin.get('net_profit_latest_ttm'))} 亿）"),
        ("行业定位", _ind_txt + (f"｜四维画像：{_esc(_tp_txt)}" if _tp_txt else "")),
        ("可比数量", f"{len(cmps)} 家（{_esc('、'.join(c.get('name', '') for c in cmps))}）"),
    ]
    biz_html = _kv_table(biz_rows) if inp else '<p class="sub">未提供 input.json，公司概况章节省略。</p>'

    # ---------- 四、行业与竞争（可比矩阵） ----------
    comp_rows = []
    if inp:
        for c in cmps:
            comp_rows.append((_esc(c.get("name", "—")), _esc(c.get("exchange", "CN")),
                              _fmt(c.get("pe")), _fmt(c.get("pb")),
                              _fmt(c.get("growth_pct")), _esc(c.get("as_of") or "—")))
    comp_rows.append(("<b>中位数</b>", "—", _fmt((comp.get("pe") or {}).get("median")), _fmt((comp.get("pb") or {}).get("median")),
                      _fmt((comp.get("metrics") or {}).get("growth_pct", {}).get("median")), "—"))
    # v3.11：境内/海外分组对比（comparable_group_gap）
    group_html = ""
    gg = (syn or {}).get("comparable_group_gap") or {}
    if gg.get("groups"):
        g_rows = []
        for g, gv in gg["groups"].items():
            g_rows.append((g, gv.get("n"), _fmt(gv.get("pe", {}).get("median")), _fmt(gv.get("pb", {}).get("median"))))
        gap = gg.get("group_gap_pct")
        gap_note = (f"海外组 PE 中位较境内组{'折价' if gap and gap < 0 else '溢价'} "
                    f"{_pct(abs(gap)) if gap is not None else '—'}（集团业务/会计口径/流动性差异）") if gap is not None else ""
        group_html = (f"<h3>4.1b 境内/海外分组统计（v3.11）</h3>"
                      f"{_table(['市场组', '样本数', 'PE 中位', 'PB 中位'], g_rows, num_cols=[1, 2, 3])}"
                      f"<p class='sub'>{gap_note}——倍数口径差异（GAAP/IFRS vs CAS、税率、流动性）须在报告解释；"
                      f"业务最可比优先于市场环境可比（全球化行业须含海外龙头）。</p>")
    idx_out = out.get("industry_index") or {}
    idx_rows = [("行业指数参照", f"{_esc(idx.get('name') or '—')}", f"{_fmt(idx_out.get('base_value'))} 亿",
                 f"与可比法偏差 {_pct(idx_out.get('vs_comparable_deviation'), 2) if _num(idx_out.get('vs_comparable_deviation')) is not None else '—'}")
                ] if idx_out.get("enabled") else []
    idx_html = _table(["参照", "指数", "隐含值（亿）", "与可比偏差"], idx_rows, warn_rows=[0] if idx_out.get("enabled") else [])
    # v3.20.0：可比公司筛选证据链（未激活时为空串 → 旧报告逐字节不变）
    peer_html = _peer_screening_html(out.get("peer_screening"))

    # ---------- 五、财务基础 + 质量卡 ----------
    q = out.get("quality_scorecard") or {}
    fin_rows = [
        ("TTM 营收", _fmt(fin.get("revenue_latest_ttm")), "输入口径（input.json）"),
        ("归母净利", _fmt(fin.get("net_profit_latest_ttm")), "输入口径"),
        ("净利率 / 毛利率", f"{_pct(fin.get('net_margin'))} / {_pct(fin.get('gross_margin'))}", "输入口径"),
        ("OCF/净利", _fmt(fin.get("ocf_to_net_profit"), 2), "输入口径（FCF 校准 L1/L3）"),
        ("质量评分", f"{_fmt(q.get('score'))}（修正 {_pct(q.get('adjustment_pct'), 2)}）", "引擎 quality_scorecard"),
    ]
    q_detail = (q.get("detail") or {})
    # 兼容两种 schema：dict（旧）与 list[dict]（引擎 v2.x 现行 → 原实现按 dict 取用导致「无评分卡明细」）
    _QLBL = {"ocf_to_net_profit": "OCF/净利", "gross_margin_trend_pp": "毛利率趋势（pp）",
             "receivables_to_revenue": "应收/营收", "goodwill_ratio": "商誉/净资产",
             "nonrecurring_ratio": "非经常性损益占比"}
    if isinstance(q_detail, dict) and q_detail:
        q_rows = [(_esc(k), _fmt(v, 2)) for k, v in q_detail.items()]
    elif isinstance(q_detail, list) and q_detail:
        q_rows = []
        for _d in q_detail:
            if not isinstance(_d, dict):
                continue
            _nm = _QLBL.get(_d.get("indicator"), _d.get("indicator") or "—")
            _pt = _d.get("points")
            _pt_txt = "—" if _pt is None else str(_pt)
            _sc = "".join(f"权重 {_fmt(_d.get('weight'), 2)}，得分 {_pt_txt}")
            _v = "—" if _d.get("value") is None else _fmt(_d.get("value"), 2)
            q_rows.append((_esc(_nm), f"{_v}（{_sc}）"))
        if q.get("components_score") is not None:
            q_rows.append(("合计（加权得分）", f"{_fmt(q.get('components_score'))} ／ 缺失指标 {_fmt(q.get('missing_indicators'), 0)} 项"))
    else:
        q_rows = []

    # ---------- 六、方法与假设 ----------
    # v3.16.5：新增「生命周期阶段 / 预测期增速（逐年）/ 增速三角参照」三行**数值**——
    # 阶段与增速形态取自引擎 lifecycle（Layer 1 判别），逐年增速取自
    # scenarios.base.dcf.growth_schedule.seq（全长度使用，非仅前 3 年）；
    # 年份由 input.financials.growth_forecast 的键推导（缺键时退化为「第 i 年」，不臆造年份）。
    ass = out.get("assumptions_summary") or {}
    dcf_ass = ass.get("dcf") or {}
    mkt_ass = ass.get("market") or {}
    lc = out.get("lifecycle") or {}
    gs = dcf.get("growth_schedule") or {}
    gt = out.get("growth_triangulation") or {}
    _FORM_LBL = {"mean_revert": "均值回归", "exp_fade": "指数衰减（fade）",
                 "s_curve": "S 曲线", "decline_converge": "衰退收敛",
                 # v3.29.0：plc6 四种 E(t)（与 engine_utils.PLC6_SHAPE_LABELS 同口径）
                 "logistic_cap": "S 曲线（缺口归一化，CAP 拐点）",
                 "geometric": "几何衰减（CAP 反算 κ）",
                 "linear": "线性收敛"}
    # v2.14.2：补齐全部终值模式的中文标签（引擎 LIFECYCLE_DEFAULTS.terminal 取值域为
    # exit_multiple / three_method / gordon / zero_growth_or_nav —— 原映射缺后两者，
    # 成长期案例 §6.2 会渲染出未翻译的内部枚举值「three_method」）。
    _TERM_LBL = {"gordon": "Gordon 永续增长", "exit_multiple": "退出倍数",
                 "prob_weighted": "概率加权终值",
                 "three_method": "三方法交叉（Gordon／退出倍数／概率加权）",
                 "zero_growth_or_nav": "零增长或净资产值"}
    _seq = gs.get("seq") or dcf.get("growth_seq") or []
    try:
        _y0 = min(int(k) for k in (fin.get("growth_forecast") or {}))
    except (TypeError, ValueError):
        _y0 = None
    if _seq:
        _n_seq = int(_num(gs.get("n")) or len(_seq))
        _growth_txt = " → ".join(
            f"{str(_y0 + i) + 'E' if _y0 is not None else '第' + str(i + 1) + '年'} {_pct(g, 2)}"
            for i, g in enumerate(_seq))
        _growth_txt += f"（显式期 {_n_seq} 年；来源：{_esc(dcf_ass.get('growth_source') or '—')}）"
    else:
        _growth_txt = "—（引擎未输出增长序列）"
    if lc.get("enabled"):
        _form = _FORM_LBL.get(gs.get("form") or (lc.get("config") or {}).get("form"),
                              gs.get("form") or (lc.get("config") or {}).get("form") or "—")
        # v3.26.0：v326 口径额外带出子类（周期性收缩 / 结构性衰退 / 待定），
        # 否则「营收 −3.4% 却判成熟期」在报告里没有任何解释入口。
        _sub = ""
        if lc.get("sub_stage_label"):
            _sub = f"·{_esc(lc['sub_stage_label'])}"
        _lc_txt = (f"{_esc(lc.get('stage_label') or lc.get('stage') or '—')}{_sub}"
                   f"（来源：{_esc(lc.get('source') or '—')}，置信度 {_fmt(lc.get('confidence'), 2)}）"
                   f"｜增速形态：{_esc(_form)}，显式期 {_fmt(gs.get('n'), 0)} 年"
                   f"｜终值：{_esc(_TERM_LBL.get(gs.get('terminal') or (lc.get('config') or {}).get('terminal'), gs.get('terminal') or (lc.get('config') or {}).get('terminal') or '—'))}")
        if lc.get("reason"):
            _lc_txt += f"<br/><span class=\"small\">判定依据：{_esc(lc['reason'])}</span>"
        # v3.29.0：plc6 六阶段增长函数——形态参数与闭合须与数值同屏，否则「S 曲线」只是个词
        if (gs.get("model") == "plc6"):
            _p6 = gs.get("params") or {}
            _p6_bits = []
            if gs.get("stage_6_label"):
                _p6_bits.append(f"六阶段档位：{_esc(gs['stage_6_label'])}")
            if _p6.get("cap") is not None:
                _p6_bits.append(f"护城河拐点 {_fmt(_p6.get('cap'), 1)} 年"
                                f"（来源：{_esc(gs.get('cap_source') or '—')}）")
            if _p6.get("steep") is not None:
                _p6_bits.append(f"陡度 a={_fmt(_p6.get('steep'), 1)}")
            if _p6.get("rho") is not None:
                _p6_bits.append(f"留存 ρ={_fmt(_p6.get('rho'), 2)}"
                                f"（半衰期 {_fmt(gs.get('implied_half_life'), 2)} 年）")
            if _p6_bits:
                _lc_txt += f"<br/><span class=\"small\">增长路径口径：{'；'.join(_p6_bits)}</span>"
            if gs.get("evidence"):
                _lc_txt += f"<br/><span class=\"small\">依据：{_esc(gs['evidence'])}</span>"
            if gs.get("form_downgraded"):
                _lc_txt += f"<br/><span class=\"small\">⚠ {_esc(gs['form_downgraded'])}</span>"
            if gs.get("stage_6_fallback"):
                _lc_txt += (f"<br/><span class=\"small\">⚠ 档位派生："
                            f"{_esc(gs['stage_6_fallback'])}</span>")
        if lc.get("objective_conflict_with_explicit"):
            _lc_txt += (f"<br/><span class=\"small\">⚠ 口径冲突："
                        f"{_esc(lc['objective_conflict_with_explicit'])}（已按显式阶段执行）</span>")
    else:
        _lc_txt = "未启用生命周期判别（legacy 口径：按 growth_forecast 前 3 年线性插值）"
    # 口径陷阱（须牢记）：引擎 growth_triangulation 的**单位是混合的**——
    # self_cagr / implied_growth 为小数（0.1435），而 comparable_median_growth / industry_growth
    # 为**百分数**（-32.2 / 60.0，源自 _comparable_growth_median() 与 index.index_growth_pct）。
    # 故前两者用 _pct() 转换，后两者直接加 "%"（曾误用 _pct → 60.0 渲染成 6000.0%）。
    _cmg = _num(gt.get("comparable_median_growth"))
    _indg = _num(gt.get("industry_growth"))
    _gt_txt = ("自身历史 CAGR " + _pct(gt.get("self_cagr"), 2)
               + " ｜ 可比增速中位 " + (f"{_cmg:.1f}%" if _cmg is not None else "—")
               + " ｜ 行业增速 " + (f"{_indg:.1f}%" if _indg is not None else "未提供")
               + "；三角校准值 " + _pct(gt.get("implied_growth"), 1)
               + "（用户显式优先，三角值作参照）")
    ass_rows = [
        ("生命周期阶段", _lc_txt),
        ("预测期增速（逐年）", _growth_txt),
        ("增速三角参照", _gt_txt),
        ("WACC", f"{_pct(dcf_ass.get('wacc'))}（{_esc(dcf_ass.get('wacc_source'))}，β {_esc(str(dcf_ass.get('beta_source') or '—').replace('给定β', '给定'))}）"),
        ("永续增速", f"{_pct(dcf_ass.get('terminal_growth'))}（{_esc(dcf_ass.get('tg_source'))}）"),
        # v3.24.0（F1）：比率法未被采用且未计算时 `fcf_ratio` 为 None——不得渲染成「—（OCF/净利）」
        # 那种**暗示主口径用了比率法**的假数，直接给出「未计算：FCFF 口径=…（比率法未被采用）」。
        ("FCF 比率", (_esc(dcf_ass.get('fcf_source')) if dcf_ass.get('fcf_ratio') is None
                     else f"{_fmt(dcf_ass.get('fcf_ratio'), 4)}（{_esc(dcf_ass.get('fcf_source'))}）")),
        ("流动性折扣", f"{_pct(mkt_ass.get('liquidity_discount')) if mkt_ass.get('liquidity_discount') is not None else '未启用'}"),
        ("行业指数 PE", _fmt(mkt_ass.get("industry_index_pe"))),
    ]
    # v3.21.0：增速参数体系四项披露（每项仅在对应开关启用时追加 → 缺省报告逐字节不变）
    _TVG_LBL = {"low": "过低（<40%）——复核是否过度保守（现金流衰减/资本开支过高）",
                "in_range": "区间内（40%–75%）——CVA 可解释区间",
                "high": "偏高（75%–85%）——须披露永续增速敏感性",
                "extreme": "极端（>85%）——估值几乎完全由永续假设决定，置信度已封顶"}
    _tvg = dcf_ass.get("tv_share_grade")
    if _tvg:
        ass_rows.append(("终值占比档位",
                         f"{_pct(_tvg.get('tv_share'))}｜{_esc(_TVG_LBL.get(_tvg.get('grade'), _tvg.get('grade') or '—'))}"
                         f"（分档：{_esc('低<40% / 区间 40–75% / 偏高 75–85% / 极端 >85%')}）"))
    _tgc = dcf_ass.get("tg_chain")
    if _tgc:
        _PICK_LBL = {"user_explicit": "① 用户显式", "industry_g_lt": "② 行业 g_lt", "inflation_anchor": "③ 通胀锚"}
        _chain_txt = " → ".join(
            f"{_PICK_LBL.get(c.get('source'), c.get('source'))}"
            f"（{_pct(c.get('raw')) if c.get('raw') is not None else '未提供'}"
            f"{'，命中' if c.get('hit') else '，未命中'}）"
            for c in (_tgc.get("chain") or []))
        _vc = _tgc.get("validation") or {}
        ass_rows.append(("永续增速取值链",
                         f"命中 {_esc(_PICK_LBL.get(_tgc.get('picked'), _tgc.get('picked')))}"
                         f"＝{_pct(_tgc.get('value'))}"
                         f"（{_chain_txt}；GDP 上限 {_pct(_tgc.get('gdp_cap'))}）"
                         + (f"｜三角参照偏差 {_fmt(_vc.get('deviation_pp'), 2)}pp"
                            f"{'（已告警）' if _vc.get('alert') else ''}" if _vc else "")))
    _stg = dcf_ass.get("scenario_tg_adj_pp")
    if _stg:
        ass_rows.append(("永续增速情景调整",
                         f"bear {_fmt(_stg.get('bear'), 2)}pp ｜ base {_fmt(_stg.get('base'), 2)}pp ｜ "
                         f"bull {_fmt(_stg.get('bull'), 2)}pp（stepped：永续增速随情景移动，bull 受 GDP 上限约束）"))
    _hs = dcf_ass.get("growth_history_shape")
    if _hs:
        _hm = _hs.get("metrics") or {}
        ass_rows.append(("历史增速形态",
                         f"{_esc(_hs.get('history_case') or '—')}"
                         + (f"（H1 {_pct(_hm.get('H1'), 2)}／H2 {_pct(_hm.get('H2'), 2)}／H3 {_pct(_hm.get('H3'), 2)}，"
                            f"σ {_fmt(_hm.get('sigma_pp'), 2)}pp、极差 {_fmt(_hm.get('range_pp'), 2)}pp）"
                            if _hm else "")
                         + f"；处置：{_esc(_hs.get('base_rule') or '—')}"))

    # v3.16.16 报告层修复（用户指定案例「特变电工」暴露；**引擎与统计数值零改动**）：
    # ★ **「DCF 退化披露」触发条件过宽**——原判据仅 `fcf0 ≤ 0`，未校验 DCF 是否**真的**退化。
    #   所谓「退化」的严格含义是**显式期现值与终值现值同时为 0**（`pv_sum == tv_pv == 0`）、
    #   权益被 `floor = max(0, net_cash)` 钳制；但基准期 FCF 为负并**不等于**退化——只要
    #   `pv_sum + tv_pv ≠ 0`（终值通常为大额正数），DCF 仍产出有效权益，只是高度依赖永续期。
    #   技能实例（本轮扫描全部 22 个既有引擎输出）：真正退化仅**中航沈飞**（fcf0 0.00 /
    #   pv_sum 0.00 / tv_pv 0.00 / equity 78.34＝净现金下限）；而**中芯国际**（fcf0 −247.51 /
    #   pv_sum 499.05 / tv_pv 4,759.51 / equity 4,999.18）与**特变电工**（fcf0 −94.12 /
    #   pv_sum −8.76 / tv_pv 961.36 / equity 726.87）**均未退化**却被误渲染「退化为净现金下限
    #   X 亿元」，其中「显式期现值与终值现值均为 0」一句与引擎输出直接矛盾——属**报告层与
    #   引擎输出冲突**（比仅措辞不当更严重）。
    #   **修复**：拆为两支——① 真退化（pv_sum 与 tv_pv 均 ≈ 0）→ 原「退化披露」文案；
    #   ② 基准期为负但未退化 → 新增「基准期为负披露」文案，如实给出显式期现值、终值现值与
    #   终值占比，提示「高度依赖永续期假设」。两支仅在 fcf0 ≤ 0 时渲染。
    #   **零回归**：全部既有案例中，fcf0 > 0 者（20 例）不进入本分支；fcf0 ≤ 0 且真退化者
    #   （中航沈飞）走分支①、文案逐字节不变；仅中芯国际／特变电工由分支①改走分支②（即修复本身）。
    _fcfr = out.get("fcf_ratio") or {}
    _fcf0 = _num(dcf.get("fcf0"))
    degen_html = ""
    if _fcf0 is not None and _fcf0 <= 0:
        _eq = _num(dcf.get("equity_value"))
        _pvs = _num(dcf.get("pv_sum")); _tvs = _num(dcf.get("terminal_value_pv"))
        _tvshare = _num(dcf.get("tv_share"))
        _ocf = _num(_fcfr.get("ocf_latest")); _cpx = _num(_fcfr.get("capex_latest"))
        _fcftxt = f"披露口径 FCF/净利 = {_fmt(_fcfr.get('used'), 4)}"
        if _ocf is not None and _cpx is not None:
            _fcftxt += f"，最新年经营现金流 {_fmt(_ocf)} 亿 − 资本开支 {_fmt(_cpx)} 亿 ＝ {_fmt(_ocf - _cpx)} 亿"
        _degen = (_pvs is not None and _tvs is not None
                  and abs(_pvs) < 1e-9 and abs(_tvs) < 1e-9)
        if _degen:
            degen_html = (
                '<div class="callout alert"><b>方法选择结论（DCF 退化披露）：</b>'
                f'标的自由现金流为负（{_fcftxt}）→ 显式期现值与终值现值均为 0，'
                f'DCF 退化为<b>净现金下限 {_fmt(_eq)} 亿元</b>。此系资本开支／再投资周期的结构性特征，'
                '非模型故障；该口径应解读为内在价值<b>下限与风险底</b>，不构成独立定价依据——'
                '估值以 ② 可比法为主锚、③ 市场舆情为修正、① DCF 为下限约束。</div>')
        else:
            _share_txt = ""
            if _tvshare is not None:
                _share_txt = f"（终值占比 {_fmt(_tvshare * 100, 1)}%）"
            _pv_txt = (f"显式期现值合计 {_fmt(_pvs)} 亿元、终值现值 {_fmt(_tvs)} 亿元{_share_txt}"
                       if _pvs is not None and _tvs is not None else "现值构成见 §7.1")
            degen_html = (
                '<div class="callout alert"><b>方法选择结论（DCF 基准期为负披露）：</b>'
                f'标的基准期自由现金流为负（{_fcftxt}）——{_pv_txt}，'
                f'DCF 权益 {_fmt(_eq)} 亿元<b>高度依赖永续期假设</b>，须谨慎解读。'
                '该法在本案不构成独立定价依据，估值以 ② 可比法为主锚、③ 市场舆情为修正；'
                '① DCF 仅作为「再投资周期结束后现金流转正」情景下的长期参照。</div>')

    # v3.16.7 报告层：Layer 0「DCF 不适用」披露（framework_check.dcf_admissible is False）。
    # 技能先例：金融（银行/保险/证券）与资源类主体——FCFF 不可定义、资本结构受监管约束，
    # 引擎已按 dcf_weight_cap 把 dcf 权重归零并路由替代主方法；报告若不声明，读者会把
    # §7.1 的 DCF 名义留痕值（平安案例 26,990 亿）误读为内在价值。仅在 is False 时渲染。
    _fw_alert = ""
    if _dcf_inadm:
        _w_comp_v = _fmt(out.get("weights", {}).get("comparable"))
        _w_sent_v = _fmt(out.get("weights", {}).get("sentiment"))
        _fw_alert = (
            '<div class="callout alert"><b>方法选择结论（Layer 0 前提判别 · DCF 不适用披露）：</b>'
            f'标的行业类别判定为 <b>{_esc(_fw.get("industry_class"))}</b>，前提 A（经营活动现金流可与负债成本分离）'
            f'与前提 B（资本结构≈融资选择）均不成立 → <b>DCF(FCFF/WACC) 不适用</b>，'
            f'权重按 dcf_weight_cap 归零并重分配（最终权重 w_dcf={_fmt(out.get("weights", {}).get("dcf"))} ／ '
            f'w_comparable={_w_comp_v} ／ w_sentiment={_w_sent_v}），'
            f'引擎路由建议主方法为 <b>{_esc(_fw.get("recommended_primary"))}</b>。'
            f'<br>故下表 DCF 行与图 3 的「DCF」柱为<b>名义留痕值 {_fmt(dcf.get("equity_value"))} 亿元</b>'
            f'（WACC／FCFF 口径对金融主体不适配，恒为高估方向）——<b>不参与综合、不构成内在价值判断，'
            f'亦不与市场口径构成「互证」</b>。本报告实际主口径为 ② 可比公司法（含盈利质量调整）'
            f'与 ③ 市场舆情（仅情绪），并以 §7.4 净资产法（NAV）及 §4.2 板块 PB 口径作交叉校验。</div>')

    # ---------- 七、估值结果 ----------
    # v3.16.7：§6.1 方法框架首句——DCF 不适用时不得再称「两法并行」
    _fw_method_txt = (
        ("<b>① DCF 不适用</b>（Layer 0 前提判别：该类主体经营活动现金流不可与负债成本分离、"
         "资本结构受监管约束 → 权重归零并路由替代主方法），综合估值由 <b>② 可比公司法</b>"
         "（可比倍数 + 修正项分层）与 <b>③ 市场舆情</b>（仅情绪）承担；")
        if _dcf_inadm else
        "市场法（可比倍数 + 修正项分层）与内在价值法（两阶段 DCF）并行，")
    # v3.16.7：DCF 权重归零时不得再称其「内在价值口径」（其数值恒为高估方向的名义留痕）
    _fw_dcf_txt = ("DCF 权重已归零，其隐含值仅为留痕、不作为内在价值（详见 §7.1 方法选择结论）；"
                   if _dcf_inadm else "DCF 为内在价值口径不受市场修正项影响；")
    method_items = []
    for k, label in (("pe", "PE"), ("ps", "PS"), ("ev_ebitda", "EV/EBITDA"), ("pb", "PB")):
        if k in comp and _num(comp[k].get("value_median")) is not None:
            method_items.append((label, _num(comp[k]["value_median"])))
    if (comp.get("synthesis") or {}).get("peg_value"):
        method_items.append(("PEG*", _num(comp["synthesis"]["peg_value"])))
    method_items.append(("DCF", _num(dcf.get("equity_value"))))
    method_rows = []
    for k, label in (("pe", "PE 法"), ("ps", "PS 法"), ("ev_ebitda", "EV/EBITDA 法"), ("pb", "PB 法")):
        if k in comp:
            ex = "、".join(str(n) for n, _ in comp[k].get("excluded", [])) or "—"
            method_rows.append((label, f"{_fmt(comp[k].get('median'))}×", _fmt(comp[k].get("value_median")), ex))
    if (comp.get("synthesis") or {}).get("peg_value"):
        method_rows.append(("PEG（单列）", "—", _fmt(comp["synthesis"]["peg_value"]), "—"))
    _dcf_row_lbl = "DCF（不适用·Layer 0 判否）" if _dcf_inadm else "DCF（内在价值）"
    _dcf_row_ref = (f"权重 0（dcf_weight_cap=0）" if _dcf_inadm
                    else f"终值占比 {_pct(dcf.get('tv_share'))}")
    method_rows.append((_dcf_row_lbl, f"WACC {_pct(dcf.get('wacc'))} / g {_pct(dcf.get('terminal_growth'))}",
                        _fmt(dcf.get("equity_value")), _dcf_row_ref))
    # v3.19.0 P6-B/C：替代主方法（rNPV / SOTP）进入 §7.1 多方法表（仅引擎启用时挂出）
    _rnpv_blk = out.get("rnpv_valuation") or {}
    _sotp_blk = out.get("sotp_valuation") or {}
    if _rnpv_blk.get("enabled") and _rnpv_blk.get("value") is not None:
        method_rows.append(("rNPV（风险调整净现值）",
                            f"r={_pct(_rnpv_blk.get('discount_rate'))} / {_fmt(_rnpv_blk.get('n_pipelines'), 0)} 条管线",
                            _fmt(_rnpv_blk.get("value")),
                            f"权重 {_fmt(_alt_w.get('rnpv'))}"))
    if _sotp_blk.get("enabled") and _sotp_blk.get("value") is not None:
        method_rows.append(("SOTP（分部加总）",
                            f"EV {_fmt(_sotp_blk.get('ev_sum'))} 亿 − 净债 {_fmt(_sotp_blk.get('net_debt'))} 亿",
                            _fmt(_sotp_blk.get("value")),
                            f"控股折价 {_pct(_sotp_blk.get('holdco_discount'))}｜权重 {_fmt(_alt_w.get('sotp'))}"))

    # 综合推导（v3.16.6：可比合成口径按实际可用乘数动态呈现，原硬编码「PE/PS/PB 可用方法均值」在单一乘数案例失真）
    _mid_lbl = "、".join(lb for k, lb in (("pe", "PE"), ("ps", "PS"), ("ev_ebitda", "EV/EBITDA"), ("pb", "PB"))
                         if k in comp) or "可用方法"
    # v3.28.0：达莫达兰阶段表生效时，§7.2 须声明权重来源——
    # 否则读者会把 40/50/10 误读成「用户填的 base 权重」（实际是阶段表覆盖后的值）。
    _pw_blk = (out.get("synthesis") or {}).get("path_weights") or {}
    _w_note = ""
    if _pw_blk.get("mode") == "damodaran_table" and _pw_blk.get("damodaran_stage"):
        _dw = _pw_blk.get("damodaran_weights") or {}
        _w_note = (
            '<p class="sub">权重口径：达莫达兰企业生命周期 <b>'
            + _esc(_pw_blk.get("damodaran_stage_label") or "")
            + "</b> → DCF " + _fmt(_dw.get("dcf")) + " ／ 可比 " + _fmt(_dw.get("comparable"))
            + " ／ 舆情 " + _fmt(_dw.get("sentiment"))
            + "（行内和为 1 的直接权重，不乘 base、不再归一化）。判定依据："
            + _esc(_pw_blk.get("damodaran_reason") or "")
            + ("。★用户输入的 base 权重已被阶段表覆盖，二者不可混读。"
               if _pw_blk.get("base_weight_superseded") else "。")
            + "</p>")
    der_rows = [
        ("可比合成值", _fmt((comp.get("synthesis") or {}).get("base_value")) + " 亿", f"{_mid_lbl} 可用方法均值"),        ("＋市场修正项", _pct(base.get("adjustments", {}).get("total_market_adjust"), 2), "质量/商誉/情绪/因子（市场口径）"),
        ("市场口径（修正后）", _fmt(base.get("comparable_adjusted")) + " 亿", f"加权 w_comp+w_sent={_fmt(out.get('weights', {}).get('comparable'))}+{_fmt(out.get('weights', {}).get('sentiment'))}"),
        ("＋ DCF × w_dcf", (f"{_fmt(dcf.get('equity_value'))} 亿" + ("（不适用，权重 0）" if _dcf_inadm else "")),
         f"权重 {_fmt(out.get('weights', {}).get('dcf'))}" + ("（Layer 0 判否，未参与综合）" if _dcf_inadm else "")),
    ]
    # v3.19.0 P6-B/C：替代主方法进入综合推导（仅启用时插行）
    _rnpv_blk2 = out.get("rnpv_valuation") or {}
    _sotp_blk2 = out.get("sotp_valuation") or {}
    if _rnpv_blk2.get("enabled") and _rnpv_blk2.get("value") is not None:
        der_rows.append((("＋ rNPV × w_rnpv"),
                         f"{_fmt(_rnpv_blk2.get('value'))} 亿",
                         f"权重 {_fmt(out.get('weights', {}).get('rnpv'))}（管线风险调整：收益×PoS，r={_pct(_rnpv_blk2.get('discount_rate'))}）"))
    if _sotp_blk2.get("enabled") and _sotp_blk2.get("value") is not None:
        der_rows.append((("＋ SOTP × w_sotp"),
                         f"{_fmt(_sotp_blk2.get('value'))} 亿",
                         f"权重 {_fmt(out.get('weights', {}).get('sotp'))}（EV − 净债，控股折价 {_pct(_sotp_blk2.get('holdco_discount'))}）"))
    der_rows.append(
        ("<b>综合加权值（Base）</b>", f"<b>{_fmt(base.get('value'))} 亿</b>", f"Bear {_fmt(syn.get('bear_value'))} / Bull {_fmt(syn.get('bull_value'))} → 区间 [{_fmt(intv[0])}, {_fmt(intv[1])}] 中枢 {_fmt(syn.get('weighted_mid'))}"),
    )

    # ---------- 六·3 方法适用性与局限性（v3.16.7 补齐 Step 6 强制要素） ----------
    # SKILL.md「强制要素」要求逐方法说明适用场景与局限（可比 / DCF / NAV / PEG / 舆情 / 一级市场锚 /
    # 统计检验 / 行业指数交叉验证）。本表的「适用场景」「主要局限」两列为**定性模板**；
    # 「本案例适用性」列全部取自引擎输出（weights / framework_check / 各模块 enabled 开关），
    # 生成器不产生任何估值数字。
    _fit_w = out.get("weights") or {}
    _fit_wcomp, _fit_wdcf, _fit_wsent = (_fit_w.get("comparable"), _fit_w.get("dcf"), _fit_w.get("sentiment"))
    _fit_nav = out.get("nav_valuation") or {}
    _fit_idx = out.get("industry_index") or {}
    _fit_peg = (comp.get("synthesis") or {}).get("peg_value")
    _fit_anchors = [nm for nm, blk in (("最近融资价格法", out.get("recent_financing_anchor")),
                                       ("回购价格法", out.get("repurchase_anchor")),
                                       ("流动性折扣", out.get("liquidity_discount")),
                                       ("贝叶斯锚定", out.get("anchor_update")))
                    if (blk or {}).get("enabled")]
    if _fit_anchors:
        _fit_anchor_txt = "启用：" + "、".join(_fit_anchors)
    else:
        _fit_anchor_txt = "未启用（无可用一级市场锚）"
    _fit_rows = [
        ("可比公司法<br>（PE / PB / PS / EV-EBITDA）",
         "有活跃同类上市可比、盈利为正、商业模式与会计口径可比；适用于多数已上市与拟上市主体",
         "受市场情绪与流动性溢价影响（需情绪倍数与流动性折扣修正）；会计口径差异与行业周期性会使倍数失真；"
         "可比样本 <3 家时中位数不稳",
         f"<b>主口径</b>（权重 {_fmt(_fit_wcomp)}）｜可用乘数：{_mid_lbl}"),
        ("DCF<br>（FCFF / WACC 两阶段）",
         "经营活动现金流可与负债成本分离、资本结构可目标化（Layer 0 前提 A/B 成立）；FCFF 为正且有可外推增长路径",
         "对 WACC 与永续增速高度敏感，终值占比通常 60%+；FCFF 为负时退化为净现金下限；"
         "<b>金融/资源类主体前提不成立</b>（债务为经营原料、资本结构受监管约束）",
         ("<b>不适用</b>（Layer 0 判否，权重 0.00；名义留痕值不参与综合）" if _dcf_inadm else
          f"适用（权重 {_fmt(_fit_wdcf)}）｜WACC {_pct(dcf.get('wacc'))} / g {_pct(dcf.get('terminal_growth'))}"
          f"｜终值占比 {_pct(dcf.get('tv_share'))}")),
        ("净资产法<br>（NAV / PB 锚）",
         "重资产、金融与控股平台型主体，账面净资产接近公允价值；或用作内在价值下限校验",
         "忽视盈利能力与成长性；对隐蔽资产、资产质量与负债久期差异不敏感；PB 合理水平依赖 ROE 与风险贴现",
         (f"启用（调整后 NAV {_fmt(_fit_nav.get('adjusted_nav'))} 亿元、每股 {_fmt(_fit_nav.get('nav_per_share'))} 元）"
          if _fit_nav.get("enabled") else "未启用（无适用净资产口径）")),
        ("PEG<br>（增速调整市盈率）",
         "成长型主体、增速稳定为正且可外推；PE 与增速须同源同基（同一利润口径、同一期间）",
         "增速口径决定结果，近零正增速会产生伪值；线性假设与非线性增长不匹配；"
         "引擎已设增速门槛与中位数上限护栏，超限整法弃用",
         (f"单列校验（名义值 {_fmt(_fit_peg)} 亿元，不并入综合权重）" if _fit_peg else "未启用")),
        ("市场舆情<br>（情绪修正）",
         "存在可观测的板块热度与事件驱动（政策、订单、风险事件、投资者导向）",
         "短期性强、不改变基本面；窗口内噪声大；与可比法共用基数、相关性高，<b>不作为独立论证</b>",
         f"独立权重 {_fmt(_fit_wsent)}（仅情绪：板块热度 + 个股舆情 + 情景因子；不含质量与流动性）"),
        ("一级市场锚<br>（交易 / 融资价格法）",
         "近期存在可比融资、回购或发行定价，一级→二级折溢价可观测",
         "一级市场流动性折价与轮次权利差异；时点衰减明显，陈旧锚值参考性下降；缺乏可比交易时不可用",
         _fit_anchor_txt),
        ("统计检验<br>（MC / 弹性 / 稳健性）",
         "参数不确定性可量化、可比样本充足、分布假设可接受",
         "结论依赖先验分布设定，<b>不解决模型设定错误</b>；尾部相关性需显式建模；样本量不足时区间偏窄",
         f"n={n}、seed={seed}｜MC 90% [{_fmt(mc.get('p5'))}, {_fmt(mc.get('p95'))}] 亿元"),
        ("行业指数<br>（交叉验证，不并入权重）",
         "目标行业有公开指数或板块估值口径（PE/PB 中位）",
         "指数成分与目标公司业务不完全可比；板块口径为整体中位，不含个体质地差异",
         (f"启用（行业 PB 中位 {_fmt(idx.get('pb_median'))}×｜隐含 "
          f"{_fmt((_fit_idx.get('implied_values') or {}).get('pb'))} 亿元，与可比法偏差 "
          f"{_pct(_fit_idx.get('vs_comparable_deviation'), 2)}）" if _fit_idx.get("enabled")
          else "未启用（无可用行业指数口径）")),
    ]
    # v3.19.0 P6-B/C：rNPV / SOTP 适用性行（仅引擎启用时挂出）
    _fit_rnpv = out.get("rnpv_valuation") or {}
    _fit_sotp = out.get("sotp_valuation") or {}
    if _fit_rnpv.get("enabled"):
        _fit_rows.insert(2, (
            "rNPV<br>（风险调整净现值）",
            "管线型医药/生物：核心价值来自在研管线（临床前至 NDA），当前现金流为负或不可定义；"
            "须提供逐管线峰值销售、上市年份与所处阶段",
            "对峰值销售、上市时点与成功率 PoS 三项假设高度敏感；PoS 取自业界区间中值（非精确统计）；"
            "上市前成本未乘 PoS（保守口径）；专利悬崖剖面为模板化近似",
            (f"启用（主方法，权重 {_fmt(_alt_w.get('rnpv'))}）｜{_fmt(_fit_rnpv.get('n_pipelines'), 0)} 条管线｜"
             f"rNPV {_fmt(_fit_rnpv.get('value'))} 亿元（r={_pct(_fit_rnpv.get('discount_rate'))}）"
             if _fit_rnpv.get("value") is not None else "启用但缺峰值销售/上市年份，未计算")))
    if _fit_sotp.get("enabled"):
        _fit_rows.insert(3 if _fit_rnpv.get("enabled") else 2, (
            "SOTP<br>（分部加总）",
            "多业务控股平台/集团：各分部业务模式、成长性与估值锚差异大，单一整体倍数会相互稀释；"
            "须提供逐分部价值（或分部 metric×multiple）与持股比例",
            "分部价值采用「输入+加总」口径（分部法价值由外部给定，引擎不重跑分部 DCF）；"
            "控股折价（复杂度折价）经验区间宽；分部间内部交易与共享成本的处理口径不统一",
            (f"启用（主方法，权重 {_fmt(_alt_w.get('sotp'))}）｜{_fmt(_fit_sotp.get('n_segments'), 0)} 个分部｜"
             f"SOTP {_fmt(_fit_sotp.get('value'))} 亿元（控股折价 {_pct(_fit_sotp.get('holdco_discount'))}，"
             f"{_esc(_fit_sotp.get('holdco_discount_basis'))}）"
             if _fit_sotp.get("value") is not None else "启用但所有分部缺价值，未计算")))

    # 补充锚
    anchor_rows = []
    rfa = out.get("recent_financing_anchor") or {}
    if rfa.get("enabled"):
        # v3.16.14：引擎 recent_financing_anchor() 仅在输入提供 exclusions[] 时才写入 `applicable`；
        # 未提供时该键缺失 → 原 `rfa.get('applicable')` 直接落为字符串 "None"（机检 C1 只抓 {KEY}/$KEY，
        # 抓不到此类「键缺失渲染 None」）。缺省语义＝适用（未触发 9 项排除检查），故 None → "是"。
        _rfa_ok = rfa.get("applicable")
        _rfa_txt = "是" if (_rfa_ok is None or _rfa_ok) else "否"
        anchor_rows.append(("最近融资价格法", f"适用={_rfa_txt}，锚值 {_fmt(rfa.get('anchor_value'))} 亿（{_fmt(rfa.get('months_since'))} 个月前，衰减 {_fmt(rfa.get('time_decay'), 3)}）"))
    rp = out.get("repurchase_anchor") or {}
    if rp.get("enabled"):
        anchor_rows.append(("回购价格法", f"回购 {_fmt(rp.get('repurchase_value'))} vs 主估值 {_fmt(rp.get('main_value'))} → 孰高 {_fmt(rp.get('adopted'))}"))
    ld = out.get("liquidity_discount") or {}
    if ld.get("enabled"):
        anchor_rows.append(("流动性折扣", f"{_pct(ld.get('discount_pct'))}（{_esc(ld.get('method_used'))}，折价 {_fmt(ld.get('discount_value'))} 亿，DCF 不折）"))
    nav = out.get("nav_valuation") or {}
    if nav.get("enabled"):
        anchor_rows.append(("净资产法", f"NAV {_fmt(nav.get('adjusted_nav'))} 亿（每股 {_fmt(nav.get('nav_per_share'))} 元）"))
    anch = out.get("anchor_update") or {}
    if anch.get("enabled"):
        anchor_rows.append(("贝叶斯锚定", f"锚 {_fmt(anch.get('anchor_value'))} 亿 → 锚定中枢 {_fmt(anch.get('anchored_mid'))}（原 {_fmt(anch.get('original_mid'))}，Δ{_fmt(anch.get('delta_pct'))}%）"))
    anchor_html = _kv_table(anchor_rows) if anchor_rows else '<p class="sub">未启用补充锚。</p>'

    # 敏感性（WACC + 增速×倍数矩阵中枢行）
    wacc_sens = sens.get("wacc_sensitivity") or {}
    wacc_rows = [(k, _fmt(v)) for k, v in wacc_sens.items()]
    matrix = sens.get("growth_pe_matrix") or {}
    mid_row_key = next((k for k in matrix if k in ("+0%", "0%")), None)
    mid_row = matrix.get(mid_row_key) if mid_row_key else None
    matrix_html = ""
    if mid_row:
        mh = ["倍数 Δ"] + [_esc(k) for k in mid_row]
        mr = [["增速基准"] + [_fmt(v) for v in mid_row.values()]]
        matrix_html = _table(mh, mr, num_cols=list(range(1, len(mh))))

    # ---------- 八、IPO 定价约束 / 已上市标的双口径定位 ----------
    # v3.16.4：已上市标的必须并列「市场价（隐含市值）vs 模型隐含价」双口径（硬约束）
    _fu8 = (inp or {}).get("fundraising") or {}
    _mkt_mv8, _mkt_px8 = _num(_fu8.get("market_cap")), _num(_fu8.get("market_price"))
    _listed8 = (_mkt_mv8 is not None) or (_mkt_px8 is not None)
    _mid8 = _num(syn.get("weighted_mid"))
    _lbl8 = "模型隐含" if _listed8 else "发行"
    ipo_rows = [
        (f"{_lbl8} PE", f"{_fmt(ipo.get('issue_pe'))}×", f"可比中位 {_fmt(ipo.get('comparable_pe_median'))}×", _esc(ipo.get("pe_status"))),
        (f"{_lbl8} PS", f"{_fmt(ipo.get('issue_ps'))}×", f"可比中位 {_fmt(ipo.get('comparable_ps_median'))}×", _esc(ipo.get("ps_status"))),
        (f"{_lbl8}每股价格", f"{_fmt(ipo.get('price_per_share'))} 元", f"摊薄 EPS {_fmt(ipo.get('diluted_eps'))} 元", "—"),
    ]
    if _listed8:
        _dev8 = ((_mkt_mv8 - _mid8) / _mid8 * 100) if (_mkt_mv8 and _mid8) else None
        if _dev8 is None:
            _concl8 = "—"
        elif abs(_dev8) <= 5:
            _concl8 = f"基本一致（{_dev8:+.1f}%）"
        else:
            _concl8 = f"市场{'溢价' if _dev8 > 0 else '折价'} {abs(_dev8):.1f}%"
        _ldate = _esc(_fu8.get("listing_date") or "—")
        _mtxt = "亿元" if _mkt_mv8 is not None else "—"
        ipo_rows = [
            ("市场现价（双口径·实际）", f"{_fmt(_mkt_px8)} 元/股", f"模型隐含 {_fmt(ipo.get('price_per_share'))} 元/股", _concl8),
            ("对应总市值（双口径·实际）", f"{_fmt(_mkt_mv8)} {_mtxt}", f"模型中枢 {_fmt(_mid8)} 亿元", _concl8),
        ] + ipo_rows
        ipo_caption = (f"已上市标的（上市日 {_ldate}）：上表前两行为<b>实际市场口径</b>（现价／总市值），"
                       f"其后为<b>模型隐含口径</b>；两口径并列即为「实际发行/市场价 vs 模型隐含价」校验。"
                       f"<br><b>口径说明：</b>模型隐含 PE/PS 的分母为最近一期（TTM）归母净利／营收，"
                       f"与可比中位（TTM 口径）<b>同基可比</b>；而估值中枢以预测口径利润为基数（见关键假设章），"
                       f"故「模型隐含 PE vs 可比中位」的偏离含<b>前瞻估值 vs TTM 倍数</b>的口径因素，非计算错误。")
    else:
        ipo_rows.append(("募资额", f"{_fmt(ipo.get('raise_amount'))} 亿", f"流通比例 {_fmt(ipo.get('float_ratio'))}", _esc(ipo.get("raise_status"))))
        ipo_caption = "拟发行标的：模型隐含定价（PE/PS/每股价格）与可比中位对照，募资额按拟发行方案。"
    ipo_html = _table(["检查项", "模型口径", "参照", "结论"], ipo_rows,
                      warn_rows=[i for i, r in enumerate(ipo_rows) if "预警" in str(r[3]) or "警示" in str(r[3]) or "异常" in str(r[3])])

    # ---------- 九、风险提示 ----------
    warns = out.get("warnings") or []
    warn_rows = [(f"⚠ {_esc(w)}", "引擎警示") for w in warns[:8]] or [("无引擎警示", "—")]
    warn_html = _table(["引擎警告（强制呈现）", "性质"], warn_rows, warn_rows=list(range(len(warn_rows))))
    elast_svg = svg_elasticity(narr["elast_top"])
    mc_rows = [
        ("样本成功率", f"{mc.get('n_success')} / {mc.get('n_total')}（{'通过' if (stat or {}).get('validation_passed') else '未通过'}，≥95%）"),
        ("MC 中位 vs 点估计", f"{_fmt(mc.get('p50'))} vs {_fmt(syn.get('weighted_mid'))}（{narr['rob_note']}）"),
        ("修正区间（情景∩MC）", f"[{_fmt((adj.get('synthesis_interval') or [None, None])[0])}, {_fmt((adj.get('synthesis_interval') or [None, None])[1])}]（中枢 {_fmt(adj.get('synthesis_mid'))}）"),
        ("统计配置", f"seed={seed} / n={n} / 尾部联动 ρ={_fmt((stat or {}).get('mc_config', {}).get('growth_multiple_corr'))}"),
    ]

    # ---------- 十一、数据溯源 ----------
    src_rows = []
    # v3.16.7：SKILL.md「数据溯源表含获取日期列」同时要求标注**置信度**（估算项标「中低（估算）」）；
    # 原表只有「数据项 / 来源 / 日期」三列。此处**按需启用**——仅当至少一项 data_sources
    # 提供 `confidence` 时才追加该列，故未提供该字段的既有输入输出逐字节不变。
    _ds_list = (inp or {}).get("data_sources") or []
    _src_has_conf = any(s.get("confidence") not in (None, "") for s in _ds_list)
    for s in _ds_list:
        # 兼容 item（单值）与 items（列表）两种写法
        _it = s.get("item")
        if _it is None:
            _its = s.get("items")
            _it = "；".join(str(x) for x in _its) if isinstance(_its, (list, tuple)) else _its
        # v3.16.15：`source` 同属人工撰写的展示型自由文本（常含机构/接口说明与 `**强调**`），
        # 与 `item` 一致改走 `_rich()`；`as_of` / `confidence` 为短标签，保持 `_esc()`。
        _row = (_rich(_it or "—"), _rich(s.get("source") or "—"), _esc(s.get("as_of") or "—"))
        if _src_has_conf:
            _row = _row + (_esc(s.get("confidence") or "—"),)
        src_rows.append(_row)
    _src_hdr = ["数据项", "来源", "日期"] + (["置信度"] if _src_has_conf else [])
    src_html = _table(_src_hdr, src_rows) if src_rows else '<p class="sub">未提供 input.json 的 data_sources。</p>'

    # ---------- 图卡与四部分合成组件（v3.16.3 版式升级） ----------
    _rev_years = sorted((fin.get("revenue_by_year") or {}).keys())
    trend_fig = ""
    if trend_svg and _rev_years:
        trend_fig = _fig("图 2", f"{_rev_years[0]}–{_rev_years[-1]} 营业收入趋势（亿元）", trend_svg,
                         note="数据来源：input.json › financials.revenue_by_year（亿元）；节点标注为当年营业收入。")
    _peg_note = ("PEG* 单列展示、不参与综合均值；" if (comp.get("synthesis") or {}).get("peg_value") else "")
    # v3.16.7：DCF 权重归零时不得再称其「内在价值口径」（名义留痕值恒为高估方向）
    _dcf_fig_note = ("DCF 不适用（Layer 0 判否，权重 0），其柱为名义留痕值、不参与综合。"
                     if _dcf_inadm else "DCF 为内在价值口径，不承受市场修正项。")
    method_fig = _fig("图 3", "多方法估值对比（亿元，Base 情景）", svg_method_bars(method_items),
                      note=_peg_note + _dcf_fig_note)
    elast_fig = _fig("图 4", "参数弹性排序（±1σ 对估值影响）", elast_svg,
                     note="横条向右为正向弹性、向左（金色）为负向；"
                          + narr["drive"].replace("<b>", "").replace("</b>", "") + "。")
    four_part = syn.get("four_part") or {}
    four_fig = ""
    fp_table = ""
    sent_disc = ""
    alt_disc = ""
    if four_part:
        four_fig = _fig("图 5", "四部分合成构成（Base 情景）",
                        svg_four_part(four_part, base_value=syn.get("base_value"),
                                      weighted_mid=syn.get("weighted_mid"),
                                      ci90=mc.get("ci90"), scen_w=out.get("scenario_weights")),
                        note="横条长度按三部分取值等比缩放；权重与合成等式均取自引擎 synthesis.four_part，可逐位复算。")
        fp_rows = []
        for _k, _lbl in (("part1_dcf", "① DCF 现金流贴现"),
                         ("part2_comparable_quality", "② 可比公司法（含质量调整）"),
                         ("part3_market_sentiment", "③ 市场舆情（仅情绪）")):
            _d = four_part.get(_k) or {}
            fp_rows.append((_lbl, _fmt(_d.get("value")), _fmt(_d.get("weight"), 2), _esc(_d.get("note") or "")))
        fp_rows.append(("<b>综合中枢（含情景加权）</b>", f"<b>{_fmt(syn.get('weighted_mid'))}</b>", "—",
                        "④ 统计检验区间取 MC P5–P95（见 §9.3）；②③ 共用可比基数，不计作两条独立路径"))
        fp_table = _table(["部分", "值（亿元）", "权重", "口径与说明"], fp_rows, num_cols=[1, 2],
                          hl_rows=[len(fp_rows) - 1])
        # v3.18.0：舆情强度修正披露（仅 sentiment_layer=correction 时；strength 口径额外给出方向/强度/上限拆解）
        sent_disc = _sentiment_correction_disclosure(out.get("scenarios", {}))
    # v3.19.0 P6-B/C：替代主方法（rNPV / SOTP）披露（不受 four_part 开关限制，仅引擎启用时渲染）
    alt_disc = _alt_method_disclosure(out)
    tg_disc = _terminal_growth_disclosure(out)
    gm_disc = _growth_path_model_disclosure(out)

    gen_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(company)} 估值报告</title>
<style>{CSS}</style></head>
<body><div class="page">

<!-- ══════════ 页眉（v3.16.13：上下结构——简介在上、元信息条在下） ══════════ -->
<div class="masthead">
  <div class="brand">LLM IPO VALUATION · 智能估值研究中心</div>
  <h1>{_esc(company)}（{_esc(meta.get('code') or meta.get('ticker') or '—')}）估值报告</h1>
  <div class="sub">{_rich(meta.get('industry') or '')} · {_rich(meta_inp.get('note_asset_type') or '')}</div>
  <div class="meta"><span class="m"><span class="k">报告编号</span><span class="v">{report_no}</span></span><span class="sep">｜</span><span class="m"><span class="k">估值基准日</span><span class="v">{_esc(as_of)}</span></span><span class="sep">｜</span><span class="m"><span class="k">上市板块</span><span class="v">{_rich(meta.get('exchange') or '—')}</span></span><span class="sep">｜</span><span class="m"><span class="k">引擎</span><span class="v">v{_esc(eng_ver)}</span></span><span class="sep">｜</span><span class="m"><span class="k">统计</span><span class="v">v{_esc(stat_ver)}</span></span><span class="sep">｜</span><span class="m"><span class="k">抽样</span><span class="v">seed={seed} · n={n}</span></span></div>
</div>

<!-- ══════════ 一、执行摘要 ══════════ -->
{_h2(1)}
<div class="kpis">{kpis}</div>
{_fig('图 1', '三口径估值区间并排（亿元）', range_bars,
      note='① 情景区间＝Bear/Base/Bull 加权；② MC 90%＝蒙特卡洛 ' + str(n) + ' 次（seed=' + str(seed) + '）；③ 修正综合区间＝情景区间 ∩ MC 90%。三条共用同一比例刻度，可横向比对。')}
<div class="callout">
  <b>结论前置：</b>{_esc(company)}合理估值区间 <b>{_fmt(intv[0])} – {_fmt(intv[1])} 亿元，中枢 {_fmt(syn.get('weighted_mid'))} 亿元</b>；
  MC 90% 区间 <b>{_fmt(mc.get('p5'))} – {_fmt(mc.get('p95'))} 亿元</b>（中位 {_fmt(mc.get('p50'))}）。  {narr['rob_note']}；{narr['drive'].replace('<b>', '').replace('</b>', '')}。{narr['issue_note']}。{narr['gap_note']}。
</div>
<h3>核心观点</h3>
<ol>{views}</ol>

<!-- ══════════ 二、核心观点 ══════════ -->
{_h2(2)}
{_table(["观点", "数据支撑", "来源"], core_rows)}

<!-- ══════════ 三、公司概况 ══════════ -->
{_h2(3)}
{biz_html}
{trend_fig}

<!-- ══════════ 四、行业与竞争 ══════════ -->
{_h2(4)}
<h3>4.1 可比公司估值矩阵（单一可比集，按市场分组）</h3>
{_table(["公司", "市场", "PE", "PB", "增速%", "数据时点"], comp_rows, hl_rows=[len(comp_rows) - 1], num_cols=[2, 3, 4])}
{group_html}
<p class="sub">注：同一可比集同时服务市场法倍数、DCF 风险参数（β/D/E）与 FCF 比率 L2 层——可比集一致运用（comparable_set_usage）。</p>
{peer_html}
<h3>4.2 行业指数交叉验证</h3>
{idx_html}
<p class="sub">行业指数仅作检验，不并入综合权重（对应中证协"行业指标法仅用于检验"）。</p>

<!-- ══════════ 五、财务基础 ══════════ -->
{_h2(5)}
<h3>5.1 关键财务指标</h3>
{_table(["指标", "数值", "口径"], fin_rows, num_cols=[1])}
<h3>5.2 盈利质量评分卡（修正 {_pct(q.get('adjustment_pct'), 2)}，总分 {_fmt(q.get('score'))}）</h3>
{_table(["指标", "数值"], q_rows, num_cols=[1]) if q_rows else '<p class="sub">无评分卡明细。</p>'}

<!-- ══════════ 六、估值方法与关键假设 ══════════ -->
{_h2(6)}
<h3>6.1 方法框架</h3>
<p>{_fw_method_txt}权重 w_dcf={_fmt(out.get('weights', {}).get('dcf'))} / w_comparable={_fmt(out.get('weights', {}).get('comparable'))} / w_sentiment={_fmt(out.get('weights', {}).get('sentiment'))}；
{_fw_dcf_txt}情景权重 {_fmt(out.get('scenario_weights', {}).get('bear'))}/{_fmt(out.get('scenario_weights', {}).get('base'))}/{_fmt(out.get('scenario_weights', {}).get('bull'))}。
补充锚（融资价格法/回购/流动性折扣/NAV/贝叶斯锚定）作校验不并入综合权重。</p>
<h3>6.2 关键假设汇总（生命周期阶段 / 增速 / WACC / FCF）</h3>
{_kv_table(ass_rows)}
<p class="sub">{_esc(ass.get('note'))}。生命周期与增速序列均取自引擎 Layer 1 判别的输出块（`lifecycle` / `dcf.growth_schedule`），可逐位复算。</p>
<h3>6.3 方法适用性与局限性</h3>
{_table(["方法", "适用场景", "主要局限", "本案例适用性"], _fit_rows, hl_cols=[3])}
<p class="sub">「本案例适用性」列取自引擎输出（路径权重 / `framework_check` / 各模块 `enabled` 开关）；「适用场景」与「主要局限」为方法论层面的通用边界说明，不构成对标的的额外判断。多方法交叉验证的可解释性要求：凡权重为 0 的方法，其数值仅为留痕，不得与在用的方法并列表述为「互证」。</p>

<!-- ══════════ 七、估值结果 ══════════ -->
{_h2(7)}
<h3>7.1 多方法估值对比（Base 情景）</h3>
{method_fig}
{_table(["方法", "倍数中位", "隐含值（亿）", "IQR 剔除"], method_rows, hl_cols=[2], num_cols=[1, 2])}
{degen_html}
{_fw_alert}
<h3>7.2 综合价值推导</h3>
{_table(["环节", "数值", "说明"], der_rows, hl_rows=[len(der_rows) - 1], warn_rows=([len(der_rows) - 1] if _num(syn.get('method_cv')) and _num(syn.get('method_cv')) > 0.6 else []), num_cols=[1])}
{_w_note}
<h3>7.3 四部分合成（①DCF ②可比法 ③市场舆情 ④统计检验）</h3>
{four_fig}
{fp_table}
{sent_disc}
{alt_disc}
{tg_disc}
{gm_disc}
<h3>7.4 补充锚（校验，不并入权重）</h3>
{anchor_html}
<h3>7.5 敏感性分析</h3>
<div class="grid2">
  <div>
    <h4>WACC 敏感性（DCF 口径）</h4>
    {_table(["WACC", "DCF 值（亿）"], wacc_rows, num_cols=[0, 1])}
    <p class="sub">WACC ±1pp → DCF 反向变动（口径：base 情景有效增速，v2.2.0 起与 base DCF 一致）。</p>
  </div>
  <div>
    <h4>增速 × 倍数矩阵（中枢行）</h4>
    {matrix_html or '<p class="sub">无矩阵数据。</p>'}
    <p class="sub">{_esc(sens.get('note'))}</p>
  </div>
</div>

<!-- ══════════ 八、IPO 定价约束 ══════════ -->
{_h2(8)}
<p class="sub">{ipo_caption}</p>
{ipo_html}
<div class="callout"><b>定价定位：</b>{narr['issue_note']}。{narr['gap_note']}。</div>

<!-- ══════════ 九、风险提示 ══════════ -->
{_h2(9)}
<h3>9.1 引擎显性警告（warnings 强制呈现）</h3>
{warn_html}
<h3>9.2 参数弹性排序（主导不确定变量）</h3>
{elast_fig}
<h3>9.3 统计校验状态</h3>
{_kv_table(mc_rows)}

<!-- ══════════ 十、结论与建议 ══════════ -->
{_h2(10)}
<div class="callout">
  <p><b>估值结论：</b>{_esc(company)}合理估值区间 <b>{_fmt(intv[0])}–{_fmt(intv[1])} 亿元，中枢 {_fmt(syn.get('weighted_mid'))} 亿元</b>；
  MC 90% 收敛区间 <b>{_fmt(mc.get('p5'))}–{_fmt(mc.get('p95'))} 亿元</b>（中位 {_fmt(mc.get('p50'))}）。{narr['rob_note']}，置信度"{_esc(conf.get('level'))}"。</p>
  <p class="sub">{_conf_detail}</p>
  <p><b>定价参考口径：</b>{narr['issue_note']}；{narr['gap_note']}；{narr['drive'].replace('<b>', '').replace('</b>', '')}，建议以敏感性分析中的关键变量为跟踪重点。本报告为研究性估值结论，不构成投资建议。</p>
</div>

<!-- ══════════ 十一、数据溯源 ══════════ -->
{_h2(11)}
{src_html}
<p class="sub">估算项已在输入文件 note 标注；估值基于公开信息与模型假设，不构成投资建议；市场有风险，决策需独立判断。</p>

<div class="foot">
  LLM IPO VALUATION · 智能估值研究中心 ｜ 报告编号 {report_no} ｜ 引擎 v{_esc(eng_ver)} / 统计 v{_esc(stat_ver)} / seed={seed} / n={n} ｜ 生成时间 {gen_at}
  <br>本报告全部数字来自引擎可复算输出（X3 防幻觉：生成器仅做版面编排与定性解读，不产生任何估值数字）；假设修订须基于可比公司与历史数据，方法论可追溯（methodology.md）。打印建议：A4 纵向、边距默认、勾选"背景图形"以保留色块。
</div>

</div></body></html>"""
    return html_doc


def main():
    ap = argparse.ArgumentParser(description="投行版估值报告自动生成器 v2·详实版（llm-ipo-valuation v3.16.13：页眉改上下结构（简介在上 / 元信息条在下，长文本不再挤压简介区）；v3.16.12：渲染型自由文本站点全量覆盖 `_rich()`（meta.industry / meta.note_asset_type 亦转 `<strong>`，裸记号不再落入 HTML，C8）；v3.16.11：data_sources items 的 Markdown 粗体修复；v3.16.9：比率量显示精度修复（WACC/永续增速/终值占比不再 0 位小数、行业指数偏差去误除 100）；v3.16.8：gap_note 比值判读对称化；v3.16.7：Layer 0「DCF 不适用」披露 + §10 置信度构成透出 + §6.3 方法适用性与局限性表 + 数据溯源置信度列；v3.16.5：取消目录 / 摘要去重 / §6 补阶段与增速数值 / 统一字号）")
    ap.add_argument("output", help="引擎输出 JSON（valuation_engine.py -o 的产物）")
    ap.add_argument("-o", "--out", default=None, help="HTML 输出路径（缺省 stdout）")
    ap.add_argument("--stat", default=None, help="统计校验 JSON（三口径/弹性/统计状态）")
    ap.add_argument("--input", default=None, help="输入 JSON（公司/行业/财务章节与数据溯源）")
    args = ap.parse_args()

    with open(args.output, "r", encoding="utf-8") as f:
        out = json.load(f)
    stat = json.load(open(args.stat, "r", encoding="utf-8")) if args.stat else None
    inp = json.load(open(args.input, "r", encoding="utf-8")) if args.input else None

    doc = generate_report(out, stat, inp)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(doc)
        print(f"[OK] 详实投行版报告已生成: {args.out}")
    else:
        print(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
