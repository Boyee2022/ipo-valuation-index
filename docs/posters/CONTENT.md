# 四张学术海报 · 共享内容包（Single Source of Truth）

> 用途：四张海报（中文金融刊物 / 中文核心期刊 / 英文 NLP 顶会 / 英文海外金融期刊）共用的事实、作者、公式、案例与措辞边界。  
> 所有数字必须与本文件一致；不确定的一律不写。禁止编造指数回测收益、准确率、覆盖率、时延。

## 1. 作者与单位

**英文**

> Yingzhou Chen†, Boyi Song†,\*, Shenyi Sun†  
> China Securities Index Co., Ltd. (CSI), Shanghai, China  
> † Equal contribution. \* Corresponding author: Boyi Song, bysong@sse.com.cn

**中文**

> 陈映洲†　宋泊毅†,\*　孙棽一†  
> 中证指数有限公司，上海  
> † 共同第一作者；\* 通信作者：宋泊毅，bysong@sse.com.cn

- 作者顺序固定：陈映洲、宋泊毅、孙棽一。
- 宋泊毅为通信作者；三人共同第一作者。
- 单位统一写“中证指数有限公司 / China Securities Index Co., Ltd.”，不要写成上海证券交易所或“SSE 研究部”。
- 视觉使用上交所风格（lacquer red / ink / cream / ledger serif），但不是上交所官方标识，不使用上交所 Logo。

## 2. 一句话主张

**EN:** Enterprise valuation is a conditional nonlinear mapping under fuzzy evidence; multi-agent review is not an oracle but a bounded, auditable parameter updater; the system should move from human-set parameters to agent-proposed, system-learned calibration.

**CN:** 企业估值是模糊证据下的条件非线性映射；多智能体不是“估值 oracle”，而是有界、可审计的参数更新器；系统优化方向是“人定 → Agent 提 → 系统学”。

## 3. 问题与三重模糊

| 模糊 | 表现 | 当前处理 |
|---|---|---|
| 输入模糊 | 财报口径、缺失、新股/ST、可比不足、舆情真假、时点不 PIT | 四层取值阶梯；缺失跳过或降置信度 |
| 模型模糊 | DCF / 可比 / 舆情 / RIM / DDM / NAV / rNPV / SOTP 的适用边界；生命周期判别误差 | Layer 0 前提门 + 六阶段生命周期 + 方法路由 + 三路加权；不可用方法剔除后按剩余权重再归一 |
| 目标模糊 | 没有真值；市价≠价值；指数收盘≠答案；“准/稳/可解释/可审计”冲突 | 不以贴近收盘为目标；差异只诊断、不反向校正；多指标三角验证 |

**关键立场（必须原样保留）**：不以“贴近指数收盘”为优化目标；市场价格只作诊断，不作监督信号；不声称跑赢指数或预测点位。

## 4. 数学骨架

记号：成分券 \(i\)，特征 \(x_i\)，不可观测价值 \(V_i\)，方法 \(m\)，方法输出 \(f_m(x;\theta_m)\)，可用性 \(a_m\)，适用度 \(\mu_m\)，生命周期 \(z\)。

**层次 MoE / 门控**

\[
F(x;\Theta)=\sum_z p(z\mid x)\sum_m w_{m\mid z}(x)\,f_{m,z}(x;\theta_{m,z}),
\qquad
w_{m\mid z}(x)=\frac{a_m(x)\mu_{m,z}(x)e^{\gamma_m}}{\sum_j a_j(x)\mu_{j,z}(x)e^{\gamma_j}}.
\]

**模糊加权与 \(\alpha\)-cut**

\[
\tilde V=\frac{\sum_m \tilde w_m\otimes \tilde v_m}{\sum_m \tilde w_m},\qquad
[V]_\alpha=\left\{\frac{\sum_m w_m v_m}{\sum_m w_m}: w_m\in[w_m]_\alpha,\ v_m\in[v_m]_\alpha\right\}.
\]

去模糊化报告 \(\hat V=\tfrac12(V^-_{0.5}+V^+_{0.5})\)，并报告 \([V]_{0.1},[V]_{0.5},[V]_{0.9}\)。

**三种合成语义**：线性池 \(\sum w_mv_m\)；对数池 \(\exp(\sum w_m\ln v_m)\)；专家乘积 \(\prod p_m^{w_m}\)。当前实现为线性池，另外两种为论文扩展。

**指数点位合成（当前主口径）**

\[
V^{idx}=P^{idx}\cdot\frac{\sum_i w_i(V_i/P_i)}{\sum_i w_i},
\qquad
V^{pw}=P^{idx}\cdot\frac{\sum_i w_iV_i}{\sum_i w_iP_i}\quad(\text{对照}).
\]

跳过券不计入分子分母；三情景点位由逐券区间按同一权重合成；价格加权只作对照。

**Agent 受限算子**

\[
T_{\text{apply}}(x)=F\big(x;\theta+A\,R\,G\,\Pi(e)\big),\qquad
T_{\text{shadow}}(x)=F(x;\theta),
\]
\[
\delta^*=\arg\min_{\delta\in\mathcal C}\ \mathcal L(\theta+\delta;e)+\lambda\|\delta\|_1,
\qquad
\mathcal C=\{\delta:|\delta_j|\le c_j(s),\ \theta+\delta\in\Theta_{\text{feas}}\}.
\]

自迭代：\(\theta_{t+1}=\theta_t+\eta_tA_t\delta_t^*\)。

## 5. 系统事实（可写）

- **五指数**：上证50、上证180、科创50、沪深300、上证综指（沪市 A 股全市场，约 **2,201** 只；总市值权重；剔除 ST/*ST 与未满计入期新股）。
- **估值方法**：DCF、可比（PE/PS/EV-EBITDA/PB/PEG）、舆情；金融走 RIM/DDM；管线药企 rNPV；多分部 SOTP；NAV 预留。
- **多智能体**：三专家（可比质量 / 折现参数 / 舆情）+ 主审；每个专家只提自己域内参数；主审 accept / clamp / reject。
- **参数族**：可比权重、舆情权重、WACC（金融为 Ke）、永续增速。
- **幅度上限**：可比 5/8/10pp（中/高/严重）、舆情 5/10pp、WACC 0.4/1.0pp、永续 0.2/0.6pp；权重 5pp 整数倍，WACC/永续 0.2pp 整数倍。
- **模式**：`shadow` 只留痕、不改参数；`apply` 回写输入并重跑引擎，保留 baseline，失败回滚。
- **可审计**：每批配置快照、逐券 `shadow.json`、`summary.html`/`shadow.html`、逐券报告、8 项机检。
- **工程**：每券 4 个脚本子进程（引擎 / 统计 / 报告 / 机检）；并行 3 或 10；报告 11 段；8 项机检。
- **回归**：`smoke_test.py` 实跑 **170 用例全绿**（约 5s）；`examples/` 27 个文件（11 input / 9 output / 7 stat）。
- **技能包**：v3.29.1（文档口径；实际引擎输出 `engine_version=2.28.0`）；10 个脚本；随仓库交付。
- **数据**：东财指数成分/财报/F10/行业估值 + 腾讯行情 + 东财新闻/股吧；公开披露；无付费数据依赖。
- **环境**：DSH 网页端 + Python 批跑服务（3089）+ 仓库内技能包。

## 6. 参考案例（可写，必须标注“示例/非指数回测”）

| 案例 | 行业 | 综合中枢（亿元） | 区间（亿元） | 引擎置信度 |
|---|---|---:|---|---|
| 芯曜微电 | AI 芯片设计（Fabless） | 271.23 | 149.81–423.03 | 高 |
| 长鑫科技 | 半导体 | 3,425.67 | 1,630.64–5,659.13 | 高 |
| 天博智能 | 汽车热管理零部件 | 123.62 | 53.57–216.45 | 高 |
| 宇树科技 | 人形/四足机器人 | 972.42 | 569.24–1,446.64 | 高 |

写表时必须加注：**“Skill reference cases shipped with the examples; not an index-level backtest; confidence is engine-reported and the examples are selected, not a random sample.”** 中文：**“技能包示例案例，不是指数级回测；置信度为引擎输出，样本为示例、非随机抽样。”**

## 7. 评估协议（无真值）

三件套：

1. **合成基准**：已知 \(V_i^\star\)，注入财报错误、可比缺失、路由错误；测恢复误差、区间覆盖、路由准确、参数恢复。
2. **人工盲评**：隐藏 Agent 建议与点位；4–6 人独立评“证据 / 方向 / 幅度 / 置信”；两轮 Delphi + 仲裁；报 Krippendorff \(\alpha\)。
3. **内部一致性**：同输入多 seed；股票排列、单位缩放、行业标签扰动；shadow 空操作；apply 回滚；8 项机检。

**市场指标只作诊断**：方向命中、跟踪误差、偏离分布；不作为优化目标。

## 8. 贡献（四个，四张海报都要有，但措辞可按受众调整）

1. **问题形式化**：三重模糊；估值是条件非线性映射；无真值约束优化；不以价格为标签。
2. **模型**：层次 MoE（生命周期 × 方法）+ 模糊加权/α-cut + 三种合成语义 + 指数点位合成。
3. **协议**：三专家 + 主审的有界评审；证据门槛、severity caps、grid、shadow/apply、baseline 回滚；形式化为信赖域算子。
4. **系统与评估**：五指数/2,201 只、170 回归、11 段报告/8 项机检；无真值评估协议（合成 + 盲评 + 一致性）。

## 9. 海报矩阵

| 文件 | 语言 | 尺寸 | 受众/风格 | 核心叙事 |
|---|---|---|---|---|
| `cn-finance.tex` | 中文 | A0 竖版 841×1189mm | 国内证券/金融刊物、指数业务 | 为什么用估值合成指数、五指数落地、案例与启示 |
| `cn-core.tex` | 中文 | A0 横版 1189×841mm | 中文核心期刊/学术会议 | 形式化、方法、协议、实验设计、局限；三线表/编号公式/参考文献 |
| `en-nlp.tex` | 英文 | 48×36in 横版 | ACL/EMNLP/NAACL | LLM 多智能体、证据门控、有界参数编辑、评估与可复现 |
| `en-finance.tex` | 英文 | A0 竖版 841×1189mm | 海外金融期刊/AFA 风格 | 经济问题、指数构建、估值框架、案例、讨论；少 ML 术语 |

## 10. 设计 tokens

**上交所风格（四张共用底色）**

- Lacquer red `#A6192E`（主）
- Vermilion `#E60012`（强调，少量）
- Ink `#141414`
- Cream `#F7F2E8`
- Stone `#6E6A63`
- Gold `#B08A4A`
- Hairline `#D8D0C2`

**中文金融版**：cream 底、红色通栏、宋体标题/正文、金色细线、ledger 表格；2 栏。
**中文核心版**：白底、黑字、红色细线；宋体正文、黑体标题；3 栏；编号章节；三线表；GB/T 7714。
**英文 NLP 版**：白底、navy `#0B1F33` 顶栏、teal `#0E7C86`、coral `#D95D39`、SSE red 点缀；Helvetica Neue；4 栏；彩色 section header；大图。
**英文金融版**：parchment `#FBF8F2` 底、oxford `#12263A`、burgundy `#7A1F2B`、gold；Palatino；2 栏；serif；克制的表格。

## 11. 禁止项

- 不写“跑赢指数/预测点位/准确率 90%/覆盖率 100%/收益提升”等未验证结论。
- 不把示例案例写成“实证样本”或“回测结果”。
- 不把论文扩展（模糊 α-cut、对数池/专家乘积、自迭代门控学习）写成“已上线”。
- 不使用上交所官方 Logo、不冒充上交所署名；只使用其视觉风格。
- 不编造作者头衔、基金号、DOI、页码。
- 不写“全球首个/颠覆式/革命性”等无法证实的措辞。

## 12. 参考文献池（按海报取 4–6 条）

1. 李双宏, 杨利国, 王洪涛. 基于大语言模型的上市公司智能估值模型构建[J]. 证券信息技术, 2026.
2. Damodaran A. Investment Valuation: Tools and Techniques for Determining the Value of Any Asset[M]. 3rd ed. Hoboken: Wiley, 2012.
3. Jacobs R A, Jordan M I, Nowlan S J, et al. Adaptive Mixtures of Local Experts[J]. Neural Computation, 1991, 3(1): 79–87.
4. Du Y, Li S, Torralba A, et al. Improving Factuality and Reasoning in Language Models through Multiagent Debate[C]//Proceedings of ICML, 2024.
5. Wei J, Wang X, Schuurmans D, et al. Chain-of-Thought Prompting Elicits Reasoning in Large Language Models[C]//NeurIPS, 2022.
6. Gneiting T, Raftery A E. Strictly Proper Scoring Rules, Prediction, and Estimation[J]. Journal of the American Statistical Association, 2007, 102(477): 359–378.
7. 上海证券交易所. 上证综合指数编制方案[EB/OL]. 2020.
8. Baker M, Wurgler J. Investor Sentiment and the Cross-Section of Stock Returns[J]. Journal of Finance, 2006, 61(4): 1645–1680.
