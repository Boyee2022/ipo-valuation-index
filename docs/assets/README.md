# docs 视觉与写作约定

`docs/` 下的 HTML 统一使用 `assets/terminal.css`，与估值工作台（Bloomberg 终端风）保持同一套视觉语言：深色底、发丝线面板、琥珀色强调、等宽数字、红涨绿跌。默认深色，右上角按钮可切浅色（`assets/terminal.js`）。

## 页面骨架

```html
<!doctype html>
<html lang="zh" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>… · Valuation System Docs</title>
<link rel="stylesheet" href="../assets/terminal.css">
<script src="../assets/terminal.js"></script>
</head>
<body>
<header class="topbar">
  <a class="brand" href="index.html">
    <span class="brand-mark">V</span>
    <span>VALUATION SYSTEM</span>
    <span class="brand-sub">RESEARCH DOCS</span>
  </a>
  <nav class="topnav">
    <a href="index.html">文档首页</a>
    <a href="paper-proposal.html">论文建议</a>
    <a href="engineering-roadmap.html">工程规划</a>
    <a href="skill-explainer.html">SKILL 讲解</a>
  </nav>
  <button class="theme-toggle" data-theme-toggle aria-label="切换主题">☾</button>
</header>
<main class="wrap">
  <section class="hero">
    <div class="kicker">RESEARCH NOTE <span class="dim">/ 2026-11</span></div>
    <h1 class="display">标题<small>SUBTITLE</small></h1>
    <p class="lede">一句话说明。</p>
    <div class="meta-row"><span class="tag am">标签</span>…</div>
  </section>
  …
</main>
<footer class="foot">…</footer>
</body>
</html>
```

当前导航页自身加 `class="on"`。

## 可用组件（详见 terminal.css）

- 布局：`.wrap` / `.wrap.wide` / `.wrap.narrow`、`.layout` + `.toc`（侧边目录）、`.grid.cols-2/3/4`、`.section` + `.section-hd`（`.no` 编号、`h2`、`.en` 英文小标）
- 面板：`.panel`、`.panel-hd`（右侧 `.panel-code`）、`.panel-bd`、`.panel.accent`
- 指标：`.kpis` + `.kpi`（`.kpi-k` / `.kpi-v` / `.kpi-s`）
- 正文：`.prose`（p/ul/ol/h3/blockquote 已带样式）、`.callout`（`.h` 标题，变体 `.blue` / `.red`）
- 公式：`.formula`（`<span class="lbl">…</span>` 标签 + 等宽内容）
- 表格：`.table-wrap` > `table.table`，数字列 `td.num`，强调 `td.ink`
- 标签：`.tag` + `.am` / `.ok` / `.warn` / `.err` / `.mut`
- 时间线：`.timeline` > `.tl-item`（`.done` 实心点）> `.tl-when` / `.tl-title` / `.tl-desc`
- 步骤：`.steps` > `.step` > `.step-no` / `.step-t` / `.step-d`
- 条形：`.bar` > `i`（可 `.blue` / `.green` / `.red`）
- 流程图：`.flow` > `.flow-node`（`small` 副标）+ `.flow-arrow`
- 层级图：`.stack` > `.layer`（`.lk` / `.lv`）
- 文档卡：`.doc-grid` > `.doc-card`（`.no` / `h3` / `p` / `.foot`）
- 其他：`.mono`、`.am`、`.up`（红）、`.down`（绿）、`.dim`、`.faint`、`.tiny`、`.code`

## 写作口径

- 中文为主，术语首次出现给英文；数字用等宽（`.mono`）。
- 不写“革命性/颠覆式”这类空话；每个判断尽量给依据（代码位置、数据、版本号）。
- 论文/工程页面面向内部对齐：先给结论，再给依据、风险、待决项。
- 所有事实以仓库 `origin/main`（2026-11-28，`d06a5ed`）为准；技能包以 `skills/llm-ipo-valuation`（v3.29.1）为准，版本差异要如实标注。
