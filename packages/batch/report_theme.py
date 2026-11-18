# -*- coding: utf-8 -*-
"""报告终端风主题：与估值工作台主页同源的字号、发丝线面板、琥珀强调与等宽数字。

陈老师技能包（仓库外）负责生成 *.report.html，本模块只在落盘与服务端读取时注入覆盖样式，
不改技能包本身。注入幂等，服务端每次读取都会刷新（存量报告同样生效）。
"""
import re
from pathlib import Path

STYLE_ID = 'dsh-terminal-theme'
_BLOCK_RE = re.compile(r'<style[^>]*id="%s"[^>]*>.*?</style>\s*' % STYLE_ID, re.S | re.I)
_META_RE = re.compile(r'<meta[^>]*name="color-scheme"[^>]*>\s*', re.I)
_VIEWPORT_RE = re.compile(r'<meta[^>]*name="viewport"[^>]*>', re.I)

CSS = r"""
/* ── 与主页一致的终端风：七级字号、发丝线、琥珀强调、等宽数字、浅/深双主题 ── */
:root{
  color-scheme:light;
  --rt-bg:#f4f5f7;--rt-panel:#ffffff;--rt-panel2:#eef0f3;
  --rt-line:rgba(17,22,35,.09);--rt-line2:rgba(17,22,35,.18);
  --rt-ink:#101828;--rt-dim:#555e6e;--rt-faint:#939baa;
  --rt-amber:#b45309;--rt-amber2:#c2410c;--rt-on-amber:#ffffff;
  --rt-up:#c7000b;--rt-down:#0e7a3d;--rt-blue:#1d6fa5;
  --rt-mono:"Cascadia Mono","JetBrains Mono","SF Mono",ui-monospace,Consolas,"Liberation Mono",monospace;
  --rt-sans:"Inter","PingFang SC","Microsoft YaHei",system-ui,-apple-system,"Segoe UI",sans-serif;
  --fs-micro:10.5px;--fs-caption:11.5px;--fs-body:12.5px;--fs-title:14px;--fs-lg:16px;--fs-num:24px;
  /* 重映射技能包令牌 */
  --bg:var(--rt-bg);--panel:var(--rt-panel);--panel2:var(--rt-panel2);
  --line:var(--rt-line);--line2:var(--rt-line2);
  --ink:var(--rt-ink);--gray:var(--rt-dim);--gray2:var(--rt-faint);
  --navy:var(--rt-ink);--navy-deep:var(--rt-ink);--navy-ink:var(--rt-ink);
  --gold:var(--rt-amber);--gold-deep:var(--rt-amber);
  --gold-soft:color-mix(in srgb,var(--rt-amber) 12%,transparent);
  --up:var(--rt-up);--down:var(--rt-down);
  --warn-bg:color-mix(in srgb,var(--rt-amber) 8%,transparent);
  --ok-bg:color-mix(in srgb,var(--rt-down) 8%,transparent);
  --r:8px;--r-sm:4px;--sh-sm:none;--sh:none;--sh-lg:none;
  --fs:12.5px;--fs-num:24px;--fs-h1:16px;--fs-h2:14px;--fs-h3:12.5px;--fs-h4:11.5px;
}
@media (prefers-color-scheme:dark){
  :root{
    color-scheme:dark;
    --rt-bg:#151517;--rt-panel:#232324;--rt-panel2:#2c2c2e;
    --rt-line:rgba(255,255,255,.06);--rt-line2:rgba(255,255,255,.12);
    --rt-ink:#f9fafb;--rt-dim:#cfd3d6;--rt-faint:#8a9099;
    --rt-amber:#ffb000;--rt-amber2:#ff8c00;--rt-on-amber:#151002;
    --rt-up:#ff5b5b;--rt-down:#2ecc71;--rt-blue:#5aa2dc;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--rt-bg);color:var(--rt-ink);font-family:var(--rt-sans);
     font-size:var(--fs-body);line-height:1.6;font-variant-numeric:tabular-nums;
     -webkit-font-smoothing:antialiased}
::selection{background:color-mix(in srgb,var(--rt-amber) 28%,transparent)}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-thumb{background:var(--rt-line2);border-radius:4px}
::-webkit-scrollbar-track{background:transparent}
.page{max-width:1180px;margin:0 auto;padding:0 28px 64px;border-top:2px solid var(--rt-amber)}
/* ── 页眉 ── */
.masthead{display:block;padding:20px 0 14px;border-bottom:1px solid var(--rt-line2)}
.masthead .brand{display:flex;align-items:center;gap:7px;font-size:var(--fs-micro);color:var(--rt-amber);
     font-weight:700;letter-spacing:.14em}
.masthead .brand::before{content:"";width:6px;height:6px;background:var(--rt-amber);border-radius:1px}
h1,.masthead h1{font-size:var(--fs-lg);line-height:1.4;color:var(--rt-ink);font-weight:700;
     margin:8px 0 4px;letter-spacing:0}
.masthead .sub,.sub{color:var(--rt-dim);font-size:var(--fs-caption)}
.masthead .meta{display:block;margin-top:12px;padding:8px 10px;background:var(--rt-panel2);
     border:1px solid var(--rt-line);border-left:2px solid var(--rt-amber);border-radius:4px;
     box-shadow:none;font-size:var(--fs-caption);color:var(--rt-dim);line-height:1.7}
.masthead .meta .m{white-space:normal}
.masthead .meta .k{margin-right:4px;color:var(--rt-faint);letter-spacing:.04em}
.masthead .meta .v{color:var(--rt-ink);font-family:var(--rt-mono);font-weight:600}
.masthead .meta .sep{margin:0 8px;color:var(--rt-line2)}
/* ── 标题层级 ── */
h2{display:flex;align-items:center;gap:8px;font-size:var(--fs-title);color:var(--rt-ink);font-weight:700;
   letter-spacing:.02em;margin:28px 0 10px;padding-bottom:7px;border-bottom:1px solid var(--rt-line2);
   scroll-margin-top:16px}
h2 .secno{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:18px;
   padding:0 5px;background:transparent;border:1px solid var(--rt-line2);color:var(--rt-amber);
   border-radius:3px;font-family:var(--rt-mono);font-size:var(--fs-micro);font-weight:700;
   letter-spacing:.06em;flex:none}
h2::after{display:none}
h3{font-size:var(--fs-body);color:var(--rt-ink);font-weight:700;line-height:1.4;margin:20px 0 8px;
   padding-left:8px;border-left:2px solid var(--rt-amber)}
h4{font-size:var(--fs-caption);color:var(--rt-dim);font-weight:700;margin:14px 0 6px;letter-spacing:.06em}
p{margin:7px 0;text-align:justify;line-height:1.7}
/* ── KPI 卡 ── */
.kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
.kpi{background:var(--rt-panel);border:1px solid var(--rt-line);border-top:1px solid var(--rt-line);
     border-radius:8px;padding:10px 12px;box-shadow:none}
.kpi .label{font-size:var(--fs-micro);color:var(--rt-faint);letter-spacing:.06em}
.kpi .value{font-family:var(--rt-mono);font-size:var(--fs-num);line-height:1.3;font-weight:700;
     color:var(--rt-ink);margin:4px 0 2px;letter-spacing:0;font-variant-numeric:tabular-nums}
.kpi .value.gold{color:var(--rt-amber)}
.kpi .note{font-size:var(--fs-caption);color:var(--rt-dim);line-height:1.55}
.kpi.hl{background:var(--rt-panel);border-color:var(--rt-line);
     border-top:2px solid var(--rt-amber);box-shadow:none}
.kpi.hl .label,.kpi.hl .note{color:var(--rt-dim)}
.kpi.hl .value{color:var(--rt-amber)}
/* ── 区间条 ── */
.rangebar{margin:12px 0 4px}
.rangebar .axis{position:relative;height:18px;background:var(--rt-panel2);border:1px solid var(--rt-line);
     border-radius:3px;margin:6px 0}
.rangebar .bar{position:absolute;top:2px;height:12px;background:var(--rt-amber);border-radius:2px;box-shadow:none}
.rangebar .bar.gold{background:var(--rt-blue)}
.rangebar .midmark{position:absolute;top:-4px;height:24px;width:1px;background:var(--rt-ink);border-radius:1px}
.rangebar .labels{display:flex;justify-content:space-between;font-size:var(--fs-micro);color:var(--rt-faint);
     font-family:var(--rt-mono);margin-top:4px;font-variant-numeric:tabular-nums}
.rangebar .labels b{color:var(--rt-ink);font-size:var(--fs-micro);font-family:var(--rt-mono)}
.rangebar .cap{font-size:var(--fs-caption);color:var(--rt-dim);margin-top:2px}
/* ── 表格 ── */
table{width:100%;border-collapse:separate;border-spacing:0;font-size:var(--fs-caption);
      background:var(--rt-panel);border:1px solid var(--rt-line);border-radius:6px;box-shadow:none;margin:12px 0}
th{background:var(--rt-panel2);color:var(--rt-dim);font-weight:700;font-size:var(--fs-micro);
   letter-spacing:.05em;padding:6px 9px;text-align:left;white-space:nowrap;border-bottom:1px solid var(--rt-line2)}
th:first-child{border-top-left-radius:6px}
th:last-child{border-top-right-radius:6px}
td{padding:5px 9px;border-top:1px solid var(--rt-line);vertical-align:top;color:var(--rt-dim);
   font-variant-numeric:tabular-nums}
tbody tr:nth-child(even) td{background:transparent}
tbody tr:hover td{background:color-mix(in srgb,var(--rt-amber) 5%,transparent)}
td.r,th.r{text-align:right}
td.r,th.r,td.num,th.num,.num{font-family:var(--rt-mono)}
td.hl{color:var(--rt-amber);font-weight:700}
tr.hl-row td{background:color-mix(in srgb,var(--rt-amber) 8%,transparent)!important;font-weight:600}
tr.warn td{background:color-mix(in srgb,var(--rt-amber) 6%,transparent)!important}
tr.ok td{background:color-mix(in srgb,var(--rt-down) 6%,transparent)!important}
.up{color:var(--rt-up);font-weight:600}.down{color:var(--rt-down);font-weight:600}
table.kv th{background:var(--rt-panel);color:var(--rt-dim);white-space:normal;border-top:1px solid var(--rt-line);
   font-size:var(--fs-caption);font-weight:600;letter-spacing:0}
table.kv td{background:var(--rt-panel)!important;color:var(--rt-ink)}
table.kv tbody tr:nth-child(even) th{background:var(--rt-panel)}
/* ── 标签 / 高亮 / 结论框 ── */
.tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:var(--fs-micro);font-weight:600;
     white-space:nowrap;border:1px solid var(--rt-line);background:var(--rt-panel2);color:var(--rt-dim);
     letter-spacing:.03em;line-height:1.5}
.tag.warn{background:color-mix(in srgb,var(--rt-amber) 10%,transparent);color:var(--rt-amber);
     border-color:color-mix(in srgb,var(--rt-amber) 40%,transparent)}
.tag.ok{background:color-mix(in srgb,var(--rt-down) 9%,transparent);color:var(--rt-down);
     border-color:color-mix(in srgb,var(--rt-down) 35%,transparent)}
.tag.navy{background:color-mix(in srgb,var(--rt-blue) 9%,transparent);color:var(--rt-blue);
     border-color:color-mix(in srgb,var(--rt-blue) 40%,transparent)}
.hl{background:none;color:var(--rt-amber);font-weight:600;padding:0}
.callout{border:1px solid var(--rt-line);border-left:2px solid var(--rt-amber);background:var(--rt-panel);
     padding:12px 14px;margin:14px 0;border-radius:0 6px 6px 0;box-shadow:none}
.callout b{color:var(--rt-ink)}
.callout p:first-child{margin-top:0}.callout p:last-child{margin-bottom:0}
.callout.alert{border-left-color:var(--rt-up);background:color-mix(in srgb,var(--rt-up) 6%,var(--rt-panel))}
/* ── 图卡 ── */
.fig{margin:14px 0;border:1px solid var(--rt-line);border-radius:8px;background:var(--rt-panel);
     box-shadow:none;overflow:hidden}
.fig-h{display:flex;align-items:center;gap:8px;padding:7px 10px;font-size:var(--fs-caption);
     color:var(--rt-dim);font-weight:600;border-bottom:1px solid var(--rt-line);background:var(--rt-panel2)}
.fig-n{display:inline-flex;align-items:center;height:18px;padding:0 6px;background:transparent;
     color:var(--rt-amber);border:1px solid var(--rt-line2);border-radius:3px;font-family:var(--rt-mono);
     font-size:var(--fs-micro);font-weight:700;letter-spacing:.04em}
.fig-body{padding:12px 14px 6px}
.fig-body svg{display:block;width:100%;height:auto}
.fig-note{padding:0 14px 10px;font-size:var(--fs-micro);color:var(--rt-faint);line-height:1.65}
.svgbox{margin:14px 0;padding:12px 14px;border:1px solid var(--rt-line);border-radius:8px;
     background:var(--rt-panel);box-shadow:none}
.svgbox .cap{font-size:var(--fs-micro);color:var(--rt-faint);margin-top:6px;text-align:center}
/* ── 构成堆叠条 ── */
.stack{margin:12px 0}
.stack .row{display:grid;grid-template-columns:160px 1fr 108px;gap:10px;align-items:center;
     margin:6px 0;font-size:var(--fs-caption)}
.stack .k{color:var(--rt-dim)}
.stack .track{position:relative;height:16px;background:var(--rt-panel2);border:1px solid var(--rt-line);
     border-radius:3px;overflow:hidden}
.stack .fill{position:absolute;left:0;top:0;height:100%;border-radius:2px;background:var(--rt-amber)}
.stack .fill.g{background:var(--rt-blue)}
.stack .fill.s{background:var(--rt-faint)}
.stack .v{text-align:right;font-variant-numeric:tabular-nums;color:var(--rt-ink);font-weight:600;
     font-family:var(--rt-mono)}
.stack .eq{margin-top:8px;padding-top:8px;border-top:1px dashed var(--rt-line2);font-size:var(--fs-caption);
     color:var(--rt-dim)}
.stack .eq b{color:var(--rt-ink)}
/* ── 布局 / 页脚 ── */
.grid2{display:grid;grid-template-columns:1fr;gap:14px}
ul,ol{margin:6px 0 6px 20px}li{margin:4px 0}
a{color:var(--rt-blue);text-decoration:none;border-bottom:1px dotted color-mix(in srgb,var(--rt-blue) 55%,transparent)}
a:hover{color:var(--rt-amber);border-bottom-color:var(--rt-amber)}
.foot{margin-top:40px;padding-top:12px;border-top:1px solid var(--rt-line2);font-size:var(--fs-micro);
      color:var(--rt-faint);line-height:1.75}
/* ── 图表内联 SVG 配色对齐（属性选择器可覆盖 presentation attribute） ── */
svg [fill="#123A7E"]{fill:var(--rt-amber)}
svg [stroke="#123A7E"]{stroke:var(--rt-amber)}
svg [fill="#0B2A5B"]{fill:var(--rt-ink)}
svg [stroke="#0B2A5B"]{stroke:var(--rt-ink)}
svg [fill="#C9A227"]{fill:var(--rt-blue)}
svg [stroke="#C9A227"]{stroke:var(--rt-blue)}
svg [fill="#854F0B"]{fill:var(--rt-blue)}
svg [stroke="#854F0B"]{stroke:var(--rt-blue)}
svg [fill="#5F5E5A"],svg [fill="#5F6470"],svg [fill="#888780"]{fill:var(--rt-dim)}
svg [stroke="#5F5E5A"],svg [stroke="#5F6470"],svg [stroke="#888780"]{stroke:var(--rt-dim)}
svg [fill="#E4E7EE"],svg [fill="#E3E6EC"]{fill:var(--rt-line)}
svg [stroke="#E4E7EE"],svg [stroke="#E3E6EC"]{stroke:var(--rt-line)}
svg [fill="#D3D9E4"],svg [fill="#C9CCD4"]{fill:var(--rt-line2)}
svg [stroke="#D3D9E4"],svg [stroke="#C9CCD4"]{stroke:var(--rt-line2)}
svg [fill="#fff"]{fill:var(--rt-panel)}
/* ── 批跑总结报告（summary.html） ── */
.wrap{max-width:1180px;margin:0 auto;padding:20px 28px 56px;border-top:2px solid var(--rt-amber)}
.wrap h1{display:block;font-size:var(--fs-lg);line-height:1.4;margin:0 0 4px;color:var(--rt-ink);letter-spacing:0}
.wrap h2{display:block;font-size:var(--fs-title);margin:24px 0 10px;padding-bottom:7px;
     border-bottom:1px solid var(--rt-line2);color:var(--rt-ink);letter-spacing:0}
.wrap .meta{font-size:var(--fs-caption);color:var(--rt-dim);margin:4px 0 14px}
.wrap .cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
.wrap .card{background:var(--rt-panel);border:1px solid var(--rt-line);border-radius:8px;
     padding:10px 12px;box-shadow:none}
.wrap .card:first-child{border-left:2px solid var(--rt-amber)}
.wrap .card b{display:block;margin:3px 0 2px;font-size:var(--fs-num);line-height:1.3;color:var(--rt-ink);
     font-family:var(--rt-mono);letter-spacing:0;font-variant-numeric:tabular-nums}
.wrap .card span{color:var(--rt-faint);font-size:var(--fs-micro);letter-spacing:.04em}
.wrap table{width:100%;border-collapse:separate;border-spacing:0;background:var(--rt-panel);
     border:1px solid var(--rt-line);border-radius:6px;box-shadow:none;font-size:var(--fs-caption);margin:12px 0}
.wrap th,.wrap td{border-bottom:1px solid var(--rt-line);padding:5px 8px}
.wrap thead th{background:var(--rt-panel2);color:var(--rt-dim);font-size:var(--fs-micro);font-weight:700;
     letter-spacing:.05em;border-bottom:1px solid var(--rt-line2)}
.wrap tbody tr:hover td{background:color-mix(in srgb,var(--rt-amber) 5%,transparent)}
.wrap td{color:var(--rt-dim);font-variant-numeric:tabular-nums}
.wrap td:nth-child(3),.wrap td:nth-child(5),.wrap td:nth-child(6),.wrap td:nth-child(7),
.wrap td:nth-child(8),.wrap td:nth-child(9){font-family:var(--rt-mono)}
.wrap .note{font-size:var(--fs-micro);color:var(--rt-faint);line-height:1.75;margin-top:12px}
[style*="color:#0f766e"]{color:var(--rt-down)!important}
[style*="color:#b45309"]{color:var(--rt-amber)!important}
/* ── 打印：强制浅色纸张口径 ── */
@media print{
  :root{color-scheme:light;--rt-bg:#fff;--rt-panel:#fff;--rt-panel2:#f2f3f5;
    --rt-line:#e2e4e9;--rt-line2:#c9cdd5;--rt-ink:#101828;--rt-dim:#555e6e;--rt-faint:#7c8288;
    --rt-amber:#b45309;--rt-up:#c7000b;--rt-down:#0e7a3d;--rt-blue:#1d6fa5;
    --fs-micro:9.5px;--fs-caption:10.5px;--fs-body:11px;--fs-title:12.5px;--fs-lg:14px;--fs-num:18px;
    --fs:11px;--fs-num:18px;--fs-h1:14px;--fs-h2:12.5px;--fs-h3:11.5px;--fs-h4:10.5px}
  body{background:#fff}
  .page,.wrap{max-width:none;padding:0;border-top:0}
  .kpi,.fig,.svgbox,.callout,.stack,table{box-shadow:none}
  .masthead .meta{background:var(--rt-panel2)}
}
/* ── 响应式 ── */
@media(max-width:980px){
  .kpis,.wrap .cards{grid-template-columns:1fr 1fr}
}
@media(max-width:860px){
  .page{padding:0 16px 48px}
  .wrap{padding:16px 16px 48px}
  .masthead .meta{padding:7px 9px}
  .stack .row{grid-template-columns:116px 1fr 96px}
}
@media(max-width:700px){
  .kpis,.wrap .cards{grid-template-columns:1fr}
  .wrap{overflow-x:auto}
  .wrap table{min-width:860px}
}
@media(max-width:560px){
  .stack .row{grid-template-columns:1fr;gap:2px}
}
"""


def inject(html_text):
    """在 </head> 前注入主题；重复调用只保留一份（内容刷新）。"""
    if not html_text:
        return html_text
    idx = html_text.lower().rfind('</head>')
    if idx < 0:
        return html_text
    body = _BLOCK_RE.sub('', html_text)
    body = _META_RE.sub('', body)
    idx = body.lower().rfind('</head>')
    payload = ('<meta name="color-scheme" content="light dark">\n'
               '<style id="%s">%s</style>\n' % (STYLE_ID, CSS))
    if not _VIEWPORT_RE.search(body):
        payload = '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n' + payload
    return body[:idx] + payload + body[idx:]


def inject_bytes(data):
    return inject(data.decode('utf-8', 'replace')).encode('utf-8')


def theme_file(path):
    """就地注入；返回是否发生改动。"""
    p = Path(path)
    if not p.is_file():
        return False
    text = p.read_text(encoding='utf-8', errors='replace')
    out = inject(text)
    if out == text:
        return False
    tmp = p.with_name(p.name + '.theme-tmp')
    tmp.write_text(out, encoding='utf-8', newline='\n')
    tmp.replace(p)
    return True


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='向报告 HTML 注入终端风主题（幂等，可批量）')
    ap.add_argument('path', help='HTML 文件或目录（目录递归处理 *.html）')
    args = ap.parse_args(argv)
    p = Path(args.path)
    files = [p] if p.is_file() else sorted(p.rglob('*.html'))
    changed = sum(1 for f in files if theme_file(f))
    print('themed %d / %d html files' % (changed, len(files)))


if __name__ == '__main__':
    main()