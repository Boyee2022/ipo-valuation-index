# 01 · 理论：估值计算图（VCG）、智能体评论家与无真值校准

> 状态：理论稿 v0.1 · 2026-11-28 · 分支 `design-valuation-net`（研究设计，不进入生产）。  
> 本文回答一个问题：把“估值像神经网络”从比喻升级为可写论文的形式化后，**哪些部分真的是网络语言、哪些部分必须换词**。结论与 [00 · 评估](00-evaluation.md) 一致：**前向是类型化计算图，后向是智能体评论家；不是端到端训练，也不是反向传播**。  
> 定名：**Valuation Computation Graph（VCG）/ Modular Valuation Network（MVN）**。本文优先用 VCG，避免“神经网络”被读成“有标签可训练”。记号沿用 [01-paper-proposal](../01-paper-proposal.md) §3；事实与数字以 [CONTENT](../posters/CONTENT.md) 与 00 为准。

---

## 0 结论先行

**判断一（前向成立，但只是“结构归纳偏置”成立）。** 残差对应“行业基准 + 个体调整”，门控对应“行业/生命周期/证据决定方法可用性与权重”，注意力对应“可比与证据的加权”，池化对应“多方法合成”，归一化对应“截面可比”。这些都能写成带公式的算子。但估值算子的输入输出量纲不同、逐券可用集不同、每个节点必须能单独审计，所以它是**带类型与约束的有向无环算子图**，不是同构张量网络。

**判断二（后向不是 BP）。** 后向是**无真值、部分可微、带硬约束条件下的有界校准**：专家提议、证据门控、主审裁决、带信赖域的稀疏更新。可微子图上用梯度或隐式微分求敏感度；离散路由与 LLM 提议用零阶搜索、策略梯度或贝叶斯优化。把它叫“反向传播”会同时高估可微性、低估审计需求。

**判断三（命题只能关于算子性质）。** 没有真值，就没有“收敛到真值”的定理可写。可写的是：可行域保持（命题 1）、池化有界/单调/齐次（命题 2）、残差–门控图的 Lipschitz 与弹性界（命题 3）、合成基准上区间覆盖的估计精度（命题 4）。四条都绑定可执行验收；不成立即说明实现有 bug。

**判断四（可识别性是第一道数学边界）。** 门控、池化权重、残差缩放在观测数据上一般不可唯一识别。理论贡献应表述为“可识别泛函 + 等价解集 + 敏感性”，而不是假装学到唯一参数；阶段 III 的“系统学”若不带先验、稀疏与单调性约束，只是在拟合同一批证据。

---

## 1 从比喻到映射：哪里是神经网络，哪里不是

### 1.1 逐项映射

| 神经网络构件 | VCG 对应 | 形式对应 | 为什么成立 | 边界（哪里不是 NN） |
|---|---|---|---|---|
| 全连接层 / MLP | 单个估值方法 \(f_m(x;\theta_m)\)：DCF、可比、RIM、rNPV | 特征到价值的复合映射 | 每种方法确是一个条件映射，有参数、有适用域 | \(\theta_m\) 是金融参数（WACC、g、倍数），受 \(r>g\)、正值、上下界约束；没有共享隐表示，也不靠拟合得到“隐层特征” |
| 卷积 / 局部连接 | 同行业、产业链相邻环节的可比聚合；行业参数底座 | 局部邻域 + 权重共享 | 估值实务确实“同行业共享参数、近可比更相关” | 估值没有平移不变性与规则网格；可比只有 5–10 家，行业邻接是稀疏图；不能把卷积核当可比筛选器去学 |
| 残差 / skip | 行业基准 + 个体调整：\(V=V_{\rm base}+\alpha f(\cdot)\)；Layer 0 否决即短路 | \(h^m=\mathrm{Norm}(h^{\rm in}+\alpha_m f_m)\) | 估值天然是“先给中枢、再修正”；\(\alpha_m=0\) 即跳过该模块 | 恒等分支必须保持基准可审计；\(\alpha_m\) 受 caps 与单调性约束；残差不能替代“换方法”（换方法是门控） |
| 注意力 | 可比池、证据、方法三类注意力 | \(\alpha_{ij}=\mathrm{softmax}_j(q_i^\top k_j/\sqrt d)\)，加权和 | 可比不是等权、证据有强弱，加权聚合是自然形式 | 注意力权重不是因果解释，不能把 \(\alpha_{ij}\) 当“为什么选这家”的证明；可比少，温度与数值稳定要处理；没有自注意力序列 |
| 混合专家 / MoE | 层次门控：生命周期 \(z\) × 方法 \(m\) | \(F=\sum_z p(z\mid x)\sum_m w_{m\mid z}f_{m,z}\) | 专家是有金融语义的方法，门控由制度、数据、生命周期决定 | 不做端到端门控训练；专家异质、逐券可用集不同；硬门 \(a_m\) 与软门 \(\mu_m\) 混合，不是同构专家 |
| 归一化 | 截面标准化、winsorize、单位归一 | \(\mathrm{Norm}(h)\)，见 §2.4 | 多方法量纲、尺度、量级不同，必须可比 | 截面统计量带入时点依赖（PIT 风险）；会抹掉绝对水平，必须锚定“元 / 亿元 / 元每股”；全截面 z-score 无全局 Lipschitz（命题 3） |
| dropout | 方法 dropout、证据 dropout、多 seed | 子图随机掩码，见 §2.7 | 用于稳健性与不确定性诊断 | 不是训练期正则（没有训练集）；组合数有限（\(M\le 8\)）；“丢方法”与“丢证据”语义不同 |
| ensemble | 多 seed / 多 prompt / 多情景 / 多池化 | \(\mathrm{Var}(V)=\mathbb E[\mathrm{Var}(V\mid\theta)]+\mathrm{Var}(\mathbb E[V\mid\theta])\) | 降低随机性带来的方差 | 不自动提高正确率（无真值对照）；相关专家让方差虚假缩小（命题 2 的 POE 部分） |
| 池化 | 线性池 / 对数池 / 专家乘积 | \(V_i=\bigoplus_{\omega_i}\{v_i^m\}\) | 多方法合成本来就是加权池 | 三种语义不可互换：对数池要求 \(v_m>0\)，POE 要求校准似然与相关性；当前实现只有线性池 |
| 损失函数 | 合成校准目标 \(\mathcal L_{\rm synth}\) | 四项过程风险，见 §4 | 无真值也要有优化方向 | 不是监督损失：不含 \(\lvert V-P\rvert\)、不含标签；最小值不应为 0 |
| 反向传播 | 智能体评论家 / 有界校准 | bilevel + actor-critic + 黑箱搜索，见 §3 | 参数需要按证据更新 | 不是链式法则、不是一次反传；无全图可微假设；离散网格使梯度不存在 |
| 架构搜索 | 模块集、门控、池化的离散受约束搜索 | 组合选择 | 架构选择客观存在，且应可审计 | 不是 DARTS 式可微搜索；搜索空间小、约束多，且必须稳定（不能每周换架构） |

### 1.2 五个必须拒绝的假设

1. **同构张量假设。** 节点输入输出量纲不同（元、元/股、比率、倍数、证据），不能拼成一个张量；Batch 是“掩码批”而非规则张量（§2.3）。
2. **可微假设。** 方法路由、Layer 0 硬门、参数网格、LLM 提议都是离散或黑箱；硬 top-k 路由的导数几乎处处为零。
3. **标签假设。** 没有 \(V^*\)；市价 \(P\) 不是真值——\(P=V(1+\eta)\)，\(\eta\) 含噪声、流动性、情绪与错价。用 \(P\) 监督会把 \(\eta\) 学进 \(V\)（§4.2）。
4. **共享表示假设。** 网络的“隐层特征”没有金融解释；VCG 的中间量必须可命名、可追溯、可单独替换（WACC、增长序列、可比倍数、情绪修正）。
5. **端到端训练假设。** 不存在“一个损失、一次反传、全体参数同步更新”的闭环；后向是多轮、坐标级、带否决与回滚的协议。**这是本文件与 00 的分界线，也是 VCG 不叫“神经网络”的原因。**

一句话：**可以借前向的骨骼，不能借后向的假设。**

---

## 2 前向：类型化估值计算图

### 2.1 类型与模块

**定义 1（类型）** 记类型系统 \(\mathcal T\) 由基础类型与构造子生成：`Value`（每股价值，元/股）、`EntVal`（企业价值，元）、`Ratio`、`Rate`、`Multiple`、`Evidence`、`Interval⟨τ⟩`、`Dist⟨τ⟩`、`Trace`；每条边带单位标签。类型规则：仅当 type(u) 与端口类型一致，或存在**显式** coercion 节点时才允许连边，**禁止隐式单位换算**。工程含义：现有引擎“元 / 亿元 / 元每股”的隐含换算与口径缺陷，在 VCG 里应变成构图期静态错误——[04 §4.9](../04-skill-methodology.md) 列的 `null` 防御族说明隐式转换正是缺陷来源。

**定义 2（模块）** 模块 \(m=(\mathrm{id},\mathrm{version},\mathrm{sig},\theta_m,\Theta_m,\Phi_m,h_m)\)，签名 \(\mathrm{sig}:\tau_1\times\cdots\times\tau_k\to\tau_{\rm out}\)，\(\Phi_m\) 为前提谓词（数据完备、Layer 0 准入、\(r>g\) 等），输出

\[
\mathcal O_i^m=(v_i^m,[\underline v_i^m,\overline v_i^m],c_i^m,e_i^m,\mathrm{trace}_i^m).
\]

模块契约四条：(C1) 类型正确；(C2) 前提失败返回 \(\bot\) 与原因，不静默兜底；(C3) 必须输出不确定性（可退化为点 + 标记）；(C4) 所有状态依赖进入 trace。

### 2.2 图与图级不变量

**定义 3（图）** \(\mathcal G=(N,A,\tau,\Theta,\prec)\)：节点带类型与模块，边带类型，\(\Theta\) 是带版本的参数集合，\(\prec\) 是执行偏序。图必须是有向无环图（DAG）。图级不变量：

- **I1 类型/单位一致**（构图期检查）；
- **I2 无环**：反馈只在**批间**通过 critic 发生，禁止同批参数改动影响同批判定（否则因果泄漏）；
- **I3 证据边**：每个方法节点至少一条证据边，否则该节点的数不可审计；
- **I4 参数版本单调**：不允许隐藏覆盖，更新必须留下版本与裁决记录；
- **I5 sink 完整**：输出中枢、区间、置信度、诊断四元组，缺一即不可交付。

I1–I3 就是“不是 pipeline”的可检验差异：pipeline 没有类型检查、没有证据边约束、没有图级不变量。

### 2.3 批与掩码子图

**定义 4（批）** \(B=\{(i,x_i)\}_{i\in I}\)，批类型 \(\mathrm{Batch}\langle\tau\rangle:I\to\tau\cup\{\bot\}\)。逐券实例化 \(G_i=M_i(\mathcal G)\)，掩码 \(M_i(n)=a_m(x_i)\cdot\mathrm{data\_ok}_i(n)\)；前向 \(F(\mathcal G,B)=\{F(G_i,x_i)\}\)。缺失输出 \(\bot\) 不进入池化，对应 `method_drop_mode=renormalize`（[spec/02 §2](../spec/02-valuation-model.md)）。

工程含义：batch 不是规则张量，“共享方法层 + 掩码”是可向量化的边界；逐券不同的路由只能在池化层汇合。这也是与 [03 工程路线](../03-engineering-roadmap.md) 五层改造的接口——具体分层编号待架构文档（02）确认。

### 2.4 前向公式

编码：\(h_i^0=E(x_i)\)。

残差块：

\[
h_i^m=\mathrm{Norm}\Big(h_i^{\mathrm{in}(m)}+\alpha_m\,f_m\big(h_i^{\mathrm{in}(m)};\theta_m\big)\Big).
\]

归一化算子取截面版本，并设方差下限：

\[
\mathrm{Norm}(h)=\mathrm{clip}\!\left(\frac{h-\mathrm{med}_{S}(h)}{\max(\sigma_{S}(h),\sigma_0)},-\kappa,\kappa\right),
\]

\(S\) 为同日同类券截面，\(\sigma_0>0\)。两点必须写明：截面统计量有 PIT 风险（用当日截面则无前视，用历史截面必须 as-of）；\(\sigma_0\) 是稳定性参数，不是调参旋钮（见命题 3）。

门控：

\[
g_m(x)=\mathrm{softmax}_m\big(a_m(x)\,\mu_m(x)\,e^{\gamma_m}\big)
=\frac{a_m(x)\mu_m(x)e^{\gamma_m}}{\sum_k a_k(x)\mu_k(x)e^{\gamma_k}},
\]

等价 logit \(\ell_m=\ln a_m+\ln\mu_m+\gamma_m\)。层次版本为 \(p(z\mid x)\) 外层、\(w_{m\mid z}\) 内层（同一 softmax 形式，但适用度改为阶段条件化的 \(\mu_{m,z}\)），合成权重

\[
w_m(x)=\sum_{z\in Z}p(z\mid x)\,w_{m\mid z}(x).
\]

三个语义分工：硬门 \(a_m\)（制度与数据，0/1）、软门 \(\mu_m\)（适用度）、先验 \(\gamma_m\)（“人定 → 系统学”的接口）。当前实现是 [01-paper §3.2](../01-paper-proposal.md) 式 (1)(2) 的工程近似：\(p(z\mid x)\) 近似 one-hot，\(a_m\) 由 Layer 0 与数据完备性决定，\(\mu_{m,z}\) 由规则与置信度近似，\(\gamma_m\) 由三路权重近似。

注意力（以可比为例）：

\[
\alpha_{ij}=\mathrm{softmax}_j\!\left(\frac{q_i^\top k_j}{\sqrt d}\right),
\qquad
v_i^{\mathrm{CMP}}=\sum_j \alpha_{ij}\,\mathrm{mult}_j .
\]

边界：\(q_i,k_j\) 可由规则特征（同行业、规模接近、成长相似）构造，也可在阶段 III 学习；但**选择仍由硬门完成**，注意力只做聚合——否则 softmax 会把不可比公司也按小权重拉进来，且无法解释。注意力权重不能当因果证据，证据链仍以 `peer_screening` 的长名单与剔除台账为准。

### 2.5 池化

\[
V_i=\bigoplus_{\omega_i}\{v_i^m\},\qquad
\omega_i=\mathrm{softmax}\big(h_\omega(x_i)\big),\qquad \textstyle\sum_m\omega_{i,m}=1.
\]

| 语义 | 公式 | 分布层面正名 | 前提与边界 |
|---|---|---|---|
| 线性池 | \(V_L=\sum_m\omega_m v_m\) | 线性意见池（linear opinion pool；Genest & Zidek, 1986） | \(\omega\) 为单纯形；不惩罚分歧，极端值主导 |
| 对数池 | \(V_G=\exp(\sum_m\omega_m\ln v_m)\) | 对数意见池 | \(v_m>0\)；AM-GM 间隙即分歧指标 |
| 专家乘积 | \(p(V\mid e)\propto\prod_m p_m(V\mid e)^{\omega_m}\) | 独立似然相乘（product of experts） | 需校准似然与相关性，否则过度自信 |

与 forecast combination（Bates & Granger, 1969）和 BMA（Hoeting et al., 1999）的关系要讲清：**我们是池化结构的近亲，不是 BMA**——BMA 的权重是后验模型概率，有数据似然支撑；我们的 \(\omega\) 是门控权重，没有真值似然，只能靠先验、证据与人评，因此不可唯一识别（§5）。当前实现只有线性池；对数池与 POE 是论文扩展，自迭代门控学习尚未上线（[spec/02 §9](../spec/02-valuation-model.md)）。

### 2.6 区间与分布传播

- **蒙特卡洛**：\(\theta\sim\pi(\theta)\)，\(V^{(k)}=F(x;\theta^{(k)})\)，\(I=[q_{\alpha/2},q_{1-\alpha/2}]\)。它传播的是**先验参数不确定性 + 抽样噪声**，不是“真值分布”——这一点必须在论文与报告里说清，否则读者会把 90% 区间读成“90% 概率包含内在价值”。
- **模糊 \(\alpha\)-cut**：\(\tilde V=\sum_m\tilde w_m\otimes\tilde v_m/\sum_m\tilde w_m\)，\([V]_\alpha=\{\sum_m w_mv_m/\sum_m w_m: w_m\in[w_m]_\alpha,\ v_m\in[v_m]_\alpha\}\)；端点用顶点枚举或 Charnes-Cooper 变换，安全外包络必包含真 cut 但可能偏宽，应报告宽度差。状态：论文扩展，未实现。
- **池化区间**：固定 \(\omega\) 且 \(v_m\in[l_m,u_m]\) 时，线性池区间 \([\sum\omega_m l_m,\sum\omega_m u_m]\) 精确；若 \(\omega\) 也在单纯形上自由，区间退化到 \([\min l_m,\max u_m]\)。
- **报告口径**：现有产品取“情景区间 ∩ MC 90%”。理论上交集不是名义 90% 覆盖——两个不同不确定性来源的边际区间取交，覆盖取决于联合分布；若要对监管声称 90%，必须在合成基准上实测该交集口径的覆盖，并在报告写“保守交集（非名义 90%）”。当前文案口径待核实。

### 2.7 前向随机性：dropout 与 ensemble

子图掩码 \(\xi\sim\mathrm{Bernoulli}(p)\)，\(V^{(\xi_k)}=F(\mathcal G^{(\xi_k)},x)\)，报告均值与方差；总方差按全方差公式分解为“模块/证据不确定性”与“参数不确定性”两部分。边界：没有训练集，所以 dropout 是**前向蒙特卡洛**而非正则化；输出用于区间宽度与稳健性诊断，不用于点估计（或明确报告两种口径）。seed、mask 分布与子图版本必须进 trace，否则可复现性失效。

### 2.8 trace 与可复现性

**定义 5（轨迹）** \(\mathrm{tr}_i=(\text{node id},\text{param version},\text{input digest},\text{seed},\text{evidence ids},\text{output})\)。可复现性：给定 trace 与引擎版本，重放得到同一输出。纯函数模块可严格保证；LLM 模块只能记录 model id / temperature / prompt hash 并报告重复采样分布——当前无 seed（[spec/03 §12](../spec/03-agent-review-protocol.md)），因此 LLM 参与的后向是随机算子（§3.2），不是确定性函数。

---

## 3 后向：智能体评论家，不是反向传播

### 3.0 两个智能体层：前置采样/证据 与 后置评论家

“把多智能体作为一层”要先分清两个位置，混在一起会导致证据同源与循环论证：

| 层 | 角色 | 输入/输出 | 是否改参数 | 类比 |
|---|---|---|---|---|
| **前置采样/证据层**（`agent.evidence`） | 采集公告/新闻/可比/行业数据，核验口径、补缺口、标注来源与置信 | `UniverseBatch`/文档 → `EvidenceBatch` + 缺口清单 | 否（只影响证据，不改估值参数） | encoder / router / retrieval layer |
| **后置评论家层**（`critic.*`） | 三专家提议、主审裁决、shadow/apply、回滚 | `ModuleOutput` + 证据 → 参数增量 δ | 是（有界、可回滚） | actor-critic / policy layer |

- 前置层是**证据生成器**，不是估值器；输出必须带 provenance、时间、来源等级与“未核验”标记。
- 后置层是**参数更新器**，不能看到前置层的原始未核验文本（只看证据包），否则会把噪声当事实。
- 两层审计分开：前置层记“证据从哪来、可信度多少”，后置层记“为什么改参数、改了哪一版”。

### 3.1 校准问题

**定义 6（内层与外层）** 给定批 \(t\) 的证据 \(e_t\) 与参数 \(\theta_t\in\Theta_{\rm feas}\)：

\[
\delta_t^*=\arg\min_{\delta\in\mathcal C_t(\theta_t)}\ \mathcal L_{\rm synth}(\theta_t+\delta;e_t)+\lambda\|\delta\|_1,
\qquad
\mathcal C_t(\theta)=\{\delta\in\mathcal G:\lvert\delta_j\rvert\le c_j(s),\ \theta+\delta\in\Theta_{\rm feas}\},
\]

\[
\theta_{t+1}=\Pi\big(\theta_t+\eta_t A_t\delta_t^*\big),\qquad \eta_t=\eta_0/(1+t/T).
\]

其中 \(A_t\) 为“被接受坐标”的选择矩阵，\(\Pi\) 为联合投影（§3.3）；\(\mathcal G\) 是离散网格（权重 5pp、WACC/永续 0.2pp，[spec/03 §4](../spec/03-agent-review-protocol.md)），故 \(\mathcal C_t\) 有限，argmin 良定义但组合爆炸；专家提议与主审裁决只是对它的**近似求解**。论文必须写“解释性对应”，不能写“已实现最优化”（[01-paper §3.6](../01-paper-proposal.md)）。外层是跨批元校准：\(\min_\theta\mathbb E_t[\mathcal L_{\rm synth}(\theta;e_t)]\)，更新受信赖域与阻尼约束，目标是“学会何时不该调”，不是无限下调。

**随机性。** LLM 使 \(\delta_t^*\) 成为随机变量，更新算子应写成 \(T:(\theta,e,\xi)\mapsto\theta'\)。命题 1 对每个实现成立（可行域保持不需要确定性）；收敛性只讨论分布——支持集落在 \(\mathcal C\) 内、跨批参数方差有界——不讨论点收敛。

### 3.2 专家 = actor，主审 = critic：解释与限度

- **actor**：\(A_k:(e_t,\theta_t)\mapsto\Delta_k\subseteq\mathcal G\)，只在自己的坐标集 \(S_k\) 上提议（三专家 + 主审的角色正交与权限见 [spec/03 §2](../spec/03-agent-review-protocol.md)）；
- **critic**：主审 \(R\) 做 accept / clamp / reject，是“近似可行投影 + 值函数代理”。没有真值就无法训练 Q 网络，裁决来自规则 + LLM + 合成目标，因此 **actor-critic 是结构性类比**（提议–裁决–有界更新三段式），不是策略梯度定理的直接应用。不能写成“用 actor-critic 训练 LLM”。
- **shadow / apply**：shadow 是严格空操作 \(T_{\rm shadow}=\mathrm{id}\)（反事实），apply 是处理组；这是因果识别与回滚的工程基础。

### 3.3 信赖域、投影与离散网格

- **信赖域**：\(\|\delta\|_1\le\Delta_t\) 加逐坐标 caps；\(\Delta_t\) 随严重度与证据质量缩放；若估值跳变超阈值或主审驳回则回缩，连续多批一致才扩。
- **投影次序**：先连续域投影 \(\Pi_{\Theta_{\rm feas}}\)（闭凸集上唯一），再取可行网格最近点 \(\Pi_{\mathcal G\cap\Theta_{\rm feas}}\)。两个投影**不可交换**：先取整再修可行域可能破坏 \(r>g+\epsilon\)，先修可行域再取整又可能越界。因此必须联合定义，并要求 \(\mathcal G\cap\Theta_{\rm feas}\neq\emptyset\) 且 \(\epsilon\) 余量足够——这是命题 1 的隐含假设，也是实现验收点。
- **离散代价**：rounding 不保非扩张性，可能放大扰动；用阻尼、确定性 tie-break、禁止同日反向更新。周期与振荡要作为可观察的失效模式报告，而不是假设收敛。

### 3.4 可微时：局部梯度与隐式微分

可微子图内用链式法则与自动微分求 \(\partial V/\partial\theta_m\)（Innes et al., 2019 的可微编程），但用途是**敏感度与信赖域缩放**，不是端到端训练信号。若中间量 \(\phi(\theta)\) 由 \(g(\phi,\theta)=0\) 隐式给出（校准到约束边界、稳态永续等），用隐函数定理：

\[
\frac{\partial\phi}{\partial\theta}
=-\left(\frac{\partial g}{\partial\phi}\right)^{-1}\frac{\partial g}{\partial\theta},
\]

条件：\(g\) 可微、\(\partial g/\partial\phi\) 非奇异、解局部唯一。即使每块可微，全图导数仍有三类断点：硬门 \(a\) 的 0/1 跳变、softmax 门控的专家切换、约束投影的导数不连续。因此**全图梯度不存在**，只能分块报告敏感度。

### 3.5 不可微时：四类替代

| 方法 | 适用对象 | 代价与边界 |
|---|---|---|
| Gumbel-Softmax / Concrete 松弛（Jang et al., 2017） | 离散模块/门控选择的近似梯度 | 改变了对象：松弛后的收敛不等于硬路由收敛，必须同时报告硬结果 |
| REINFORCE / score-function（Williams, 1992） | 小规模离散选择 | 高方差；需共同随机数与 baseline 降方差 |
| 零阶 / 有限差分 / 进化策略 | 黑箱 LLM 提议、大规模离散搜索 | 每步昂贵；必须限定维度与预算 |
| 贝叶斯优化 | 低维连续+离散混合（caps、\(\gamma\)、池化组合） | GP 平滑假设与离散目标不完全匹配，需报失败率 |

选择原则：**先降维、再搜索**——可微的用梯度，结构性的用枚举或先验，全黑箱的才用零阶；不做无约束的“全图搜索”。

### 3.6 与 BP 的区别

| 维度 | 端到端 BP（本系统不采用） | VCG 后向 |
|---|---|---|
| 数据 | \((x,y)\) 标签对 | 证据 \(e\) + 评审记录 + 合成目标，**无标签** |
| 目标 | 经验风险 + 正则 | 过程风险四元组 + 硬约束（约束形，非标量） |
| 可微性 | 全图可微 | 部分可微：模块可微，路由/网格/LLM 不可微 |
| 信息传播 | 链式法则一次反传 | 多轮提议–裁决–更新；可微子图用局部梯度/隐式微分 |
| 更新 | 全参数同步 | 坐标级、稀疏（L1）、带 caps 与信赖域 |
| 收敛 | 光滑/凸下有保证 | 无全局保证；阻尼、回滚、周期检测 |
| 失败模式 | 过拟合 / 欠拟合 | reward hacking、自我确认、循环论证、证据同源 |
| 审计 | 梯度难以解释 | 每个 \(\delta\) 有证据、裁决、baseline、回滚（设计要求） |

“没有链式传导”有三层含义：目标不分解为单参数的可微路径；多数更新是离散坐标；更新经过评审否决，信息非平滑传导。所以 credit assignment 是**局部的、由证据解释的**，不是全局链式的。这也是论文里必须正面回答“这不就是 pipeline 换词”的地方（§8 Q1）。

---

## 4 合成目标 \(\mathcal L_{\rm synth}\)

### 4.1 定义

\[
\mathcal L_{\rm synth}(\theta;e)=\big(\mathcal L_{\rm cons},\ \mathcal L_{\rm stab},\ \mathcal L_{\rm cal},\ \mathcal L_{\rm pref}\big).
\]

- **一致性**：\(\mathcal L_{\rm cons}=\frac1N\sum_i\psi_{\tau}\big(\mathrm{disp}_i\big)\)，\(\mathrm{disp}_i=\mathrm{IQR}_m(\ln v_i^m)\)，\(\psi_\tau\) 为单侧 Huber——只罚“过度分歧”，**不奖励“无分歧”**。否则目标会把所有方法拉成同一值，退化为单方法。
- **时序稳定**：\(\mathcal L_{\rm stab}=\mathbb E_t[\mathrm{Huber}(\theta_t-\theta_{t-1})]\)，但只在“证据无显著变化”的子集上计；证据变化大时改为方向一致性约束 \(\mathrm{sign}(\Delta\theta_j)=\mathrm{sign}(\Delta\mu_j)\)，避免把“该调”也罚掉。
- **区间校准**：合成基准上有 \(V^*\)，用 \(\lvert\hat C_{1-\alpha}-(1-\alpha)\rvert+\gamma\overline W\)（覆盖偏差 + 宽度惩罚）；真实数据上没有 \(V^*\)，只能用置信度–稳定性单调性与盲评校准替代（§4.4、命题 4）。
- **人工偏好**：成对盲评的 Bradley-Terry 损失 \(-\sum\log\sigma(s(a)-s(b))\)，仅在评审者间一致性（Krippendorff \(\alpha\)）达标时使用；人评是方向约束，不是真值。
- **正则**：\(\lambda\|\delta\|_1\)（少改）、参数先验偏离惩罚（Mahalanobis）、层级收缩 \(\|\Delta_{m,z}\|\le\tau_m\)。硬约束不放进损失，而用投影或否决执行——罚函数会把硬约束变成可交易项。

### 4.2 为什么不能含价格

1. **会退化为复制价格。** 若目标含 \(\lvert\ln V-\ln P\rvert\)，最小值在 \(V=P\)；而 \(P=V(1+\eta)\)，\(\eta\) 含噪声、流动性、情绪与真实错价；当 \(\eta\) 的条件均值随特征系统变化（情绪、流动性、指数纳入，即内生性）时，\(\mathbb E[P\mid x]=\mathbb E[V\mid x]+\mathbb E[V\eta\mid x]\neq\mathbb E[V\mid x]\)，偏差不会消失，只是被平均。
2. **指数层会失去估值意义。** 以 \(P^{idx}\) 为目标等于优化“复制指数”；指数收盘还受成分调整、停牌、权重影响，不是估值对象。
3. **诊断自毁。** \(e_i=V_i/P_i-1\) 是诊断量；若目标含 \(e_i\)，最优解 \(e_i\equiv 0\)，诊断失去信息，形成循环论证。
4. **边界澄清**：输入特征里出现价格派生量（可比倍数、市值权重）是正常的——可比法本来如此；红线是**目标不含 \(V-P\)，残差不回流参数**（[spec/02 §8](../spec/02-valuation-model.md)）。

### 4.3 写成约束或多目标，而不是标量

三项天然冲突：稳 vs 灵敏、窄区间 vs 覆盖、低分歧 vs 信息量。单标量化会隐藏权衡，权重也无法由数据识别（§5）。推荐形式：

\[
\min_{\theta\in\Theta_{\rm feas}}\ \mathcal L_{\rm cal}
\quad\text{s.t.}\quad
\mathcal L_{\rm cons}\le\tau_1,\ \ \mathcal L_{\rm stab}\le\tau_2,\ \ \mathcal R(\theta)\le\rho .
\]

标量加权版只用于生成候选；最终报告 Pareto 前沿 + 预注册的字典序。**退化检查**：若 \(\mathcal L_{\rm synth}\to0\)，检查是否“全方法同值 / 恒不动 / 区间无穷宽”，并做成断言——合成目标的 0 值是 bug，不是成功。

### 4.4 效度的三层分解

- **内部效度**：可复现、类型正确、shadow 严格空操作、apply 可回滚（可测）。
- **构念效度**：区间、置信度、证据是否与专家盲评一致（[06 评估协议](06-evaluation.md)）。
- **外部效度**：跨期、跨指数、跨市场稳健，市场指标只作诊断。
- **没有准则效度**（criterion validity）：\(V^*\) 不可观测，任何“准确率/预测误差”表述都越界。

### 4.5 防止 reward hacking 的八道防线

1. 预注册主指标与停时规则；2. 目标函数与评估函数分离（critic 看不到评估集与盲评标签）；3. 留出专家 / 留出指数 / 时间切分；4. 多目标 Pareto + 字典序，不为指标调权重；5. 对抗扰动不变量（seed、单位缩放、顺序、行业标签、可比扰动）；6. 退化断言（一致 → 0、区间 → ∞、参数恒不动均报警）；7. 负结果与失败案例强制报告；8. 人工盲评仲裁优先于自动指标。

---

## 5 可识别性

### 5.1 定义

\[
\theta\sim_{D}\theta'\iff F(x;\theta)=F(x;\theta')\ \ \forall x\in D,
\qquad
[\theta]=\{\theta':\theta'\sim_{D}\theta\}.
\]

称泛函 \(\varphi\) 在 \(D\) 上**可识别**，若 \(\theta\sim_D\theta'\Rightarrow\varphi(\theta)=\varphi(\theta')\)。只有可识别泛函能报点估计；其余只能报等价类或区间。这是无真值系统的第一道数学边界，对应计量中的部分识别/集合识别思想（Manski, 2003）。

### 5.2 四个不可识别来源

1. **池化权重（线性池）**：\([\omega]=\{\omega+\eta:\eta^\top v(x)=0\ \forall x\in D,\ \mathbf 1^\top\eta=0\}\)。方法输出越共线，\(\omega\) 的识别区间越宽；\(M=3\) 时也常见。
2. **门控的平移–乘积混叠**：\(\gamma+c\mathbf 1\) 不改变 softmax；且 \(a_m\mu_m e^{\gamma_m}\) 只识别乘积——\(a_m\) 已知为 0/1 时，\(\mu_m e^{\gamma_m}\) 可识别，但其分解不可识别。层次上更强：\(w_m(x)=\sum_z p(z\mid x)w_{m\mid z}(x)\)，只有**边际化权重**可识别，\(p(z\mid x)\) 与 \(w_{m\mid z}\) 的分解需要独立证据（Layer 1 结构证据）或先验收缩才能区分。
3. **残差尺度**：\(f_m\) 对参数线性、且 Norm 吸收尺度时，只识别 \(\alpha_m\theta_m\) 的乘积；不能声称“单独学到了 \(\alpha_m\)”。
4. **Norm 次序/类型**：不同归一化次序可能给出同一输出类，因此图结构本身在观测上也可能不唯一——架构搜索同样受此限制。

### 5.3 识别策略

- **先验锚点**：\(\gamma_{m_0}=0\)、行业参数底座作为先验来源（[04 §4.5](../04-skill-methodology.md)）；
- **归一化约束**：\(\sum\omega=1\)、\(\alpha_m\ge0\)、参数上下界；
- **稀疏与收缩**：\(\lambda\|\delta\|_1\) + 层级收缩；
- **单调性**：\(g_m\) 对 \(\mu_m\) 单调递增；DCF 对 \(r\) 单调递减；\(V\) 对 \(\omega_m\) 的方向由 \(v_m\) 与 \(V\) 的排序确定；
- **敏感性分析**：弹性、有限差分、Sobol 指数，报告识别区间宽度。

### 5.4 报告规范

报三件东西：**可识别泛函**（估值区间、方法排序、门控方向与开关、贡献分解在等价类上的范围）；**不可识别方向**（“只有乘积可识别，单独参数区间为……”）；**结论稳定性**（某结论在所有等价解上不变才可写成无条件结论，否则标注条件）。把“学到唯一参数”改成“压缩了等价解集”，是本文与常规 ML 论文在表述上的根本差异。

---

## 6 命题

四个命题都**不声称估值准确**：命题 1 是归纳不变式，命题 2 是标准分析的组合，命题 3 需要非平凡假设，命题 4 是估计精度命题。价值在于把假设显式化并绑定验收。

### 命题 1（可行域保持）

**假设** (P1-a) \(\Theta_{\rm feas}=\{\theta:r\ge g+\epsilon,\ w\in\Delta,\ \lvert\theta_j\rvert\le B_j\}\) 非空闭凸（半空间 + 单纯形 + 盒约束）；(P1-b) 每个被接受的更新 \(\delta\in\mathcal C_t\)，且在“可行域 → 网格”的联合投影下仍满足可行域；(P1-c) 主审不新增专家未提参数、不跨域；(P1-d) apply 失败回滚基线；(P1-e) 权重回写后重新归一化。

**结论** 对任意 \(t\)，\(\theta_t\in\Theta_{\rm feas}\)，\(F(x;\theta_t)\) 对可执行券有定义；且 \(T_{\rm shadow}=\mathrm{id}\)。

**证明思路** 归纳。基线 \(\theta_0\in\Theta_{\rm feas}\)（工程上需断言）；每一步要么恒等（reject / hold / 回滚），要么是 \(\theta_{t+1}=\Pi(\theta_t+\eta A_t\delta_t)\)，由 (P1-b) 落回可行域。关键是投影次序：网格取整可能破坏 \(r-g\ge\epsilon\)，必须取“可行域内最近网格点”并留 \(\epsilon\) 余量，否则 (P1-b) 不成立。

**工程含义** 可行域保持是验收项，不是自然性质：(i) caps 的**联合覆盖**测试——所有坐标同时取 caps 时仍满足 \(r>g\)；(ii) 敌对建议测试——越权、超限、\(r<g\) 必须 100% 被 clamp/reject；(iii) 回滚测试；(iv) 网格与可行域次序固定且可测。仓库已检查范围与 \(r>g\)，但联合覆盖仍需测试（与 [01-paper 命题 1](../01-paper-proposal.md) 的条件一致，待核实）。

### 命题 2（池化的有界性、单调性与齐次性）

**假设** (P2-a) \(v_m\in[a,b]\subset(0,\infty)\)；(P2-b) \(\omega\in\Delta\)，线性池与对数池使用同一 \(\omega\)；(P2-c) POE 的专家为独立高斯，\(\sigma_m^2>0\)。

**结论** (i) 有界：\(V_L,V_G\in[\min_m v_m,\max_m v_m]\)。(ii) 分歧：\(V_G\le V_L\)，等号当且仅当所有 \(v_m\) 相等；\(\ln V_L-\ln V_G=\ln(\sum_m\omega_m e^{x_m})-\sum_m\omega_m x_m\)（\(x_m=\ln v_m\)）是加权方差型的非负分歧度量，可直接作为诊断指标。(iii) 正齐次：\(\mathrm{pool}(kv)=k\,\mathrm{pool}(v)\)，故 \(V_i=kP_i\) 时指数合成满足 \(V^{idx}=kP^{idx}\)（尺度一致性检验）。(iv) 单调：\(\partial V_L/\partial v_m=\omega_m\ge0\)，\(\partial V_G/\partial v_m=\omega_m V_G/v_m\ge0\)。(v) POE 独立情形 \(V_P=\big(\sum_m\omega_m\mu_m/\sigma_m^2\big)/\big(\sum_m\omega_m/\sigma_m^2\big)\)，\(\sigma_P^{-2}=\sum_m\omega_m/\sigma_m^2\)；相关性 \(\rho>0\) 时有效方差更大，忽略相关性会低估方差（“多 Agent 一定更准”是幻觉）。注：[01-paper 式 (8)](../01-paper-proposal.md) 的独立情形系数应统一为 \(\omega_m\) 而非 \(\omega_m\omega_n\)，相关情形需精度矩阵，此处待与 P2 骨架核对（待核实）。

**证明思路** 凸组合 / 加权 AM-GM / Euler 齐次定理 / 高斯乘积配方；相关情形用精度矩阵。

**工程含义** (i) 池化实现必须检查正性并给出失败原因；(ii) AM-GM 间隙可无真值地度量方法分歧；(iii) 指数合成加尺度一致断言；(iv) POE 上线前完成似然与相关性校准，否则只作敏感性对照；(v) 专家数增加前先看 \(\sigma_P\) 是否真的下降。

### 命题 3（残差–门控图的 Lipschitz 与弹性界）

**假设** (P3-a) 各模块 \(f_m\) 对 \((h,\theta)\) 联合 \(L_m\)-Lipschitz；(P3-b) 截面统计量 \(\mathrm{med}_S,\sigma_S\) 在归一化块外计算（不参与该块微分），\(\mathrm{Norm}\) 在 winsorize 与方差下限 \(\sigma_0\) 下是 \(L_N\)-Lipschitz（\(L_N=1/\sigma_0\)）；(P3-c) \(\lvert\alpha_m\rvert\le\bar\alpha\)；(P3-d) 门控在 logit 空间平滑，softmax 的 Jacobi 谱范数 \(\le p_{\max}(1-p_{\max})\le1/4\)；(P3-e) 路由子图固定；(P3-f) 池化权重对输入 \(L_\omega\)-Lipschitz。

**结论** (i) 固定子图内 \(\|\Delta F\|\le L_F(\|\Delta x\|+\|\Delta\theta\|)\)，链式上界 \(L_F\le L_E\,L_{\rm pool}\prod_{m=1}^{M}L_N(1+\bar\alpha L_m)\)（\(L_E,L_{\rm pool}\) 为编码与池化的 Lipschitz 常数）；若门控依赖隐状态而非仅 \(x\)，块常数需加入 \(\frac14\bar\alpha B\) 型交叉项（\(B\) 为模块输出界）。(ii) 参数弹性：\(\|\partial\ln F/\partial\theta\|\le L_\theta\)，配合 caps \(\|\delta\|_1\le c\) 得 \(\lvert\Delta\ln F\rvert\le L_\theta c+o(\|\delta\|)\)。(iii) 若发生路由切换，Lipschitz 不成立，只能给枚举界——切换前后两个子图都算，取实际差值。

**证明思路** 复合映射的 Lipschitz 常数相乘；残差相加用三角不等式；softmax Jacobi 谱范数；参数方向用中值定理或局部梯度；路由点用反例说明不可微。

**工程含义** (i) caps 可由解析弹性反推：取终值占比 \(s_T=0.7\)、\(r-g=4\%\)，0.6pp 的 \(g\) 上限对应约 10.5% 弹性；取修正久期 \(D_{\rm mod}=12\)，1pp 的 \(r\) 上限对应约 12%（解析示例，与 01-paper 一致）——这解释了为什么 1pp WACC + 0.6pp g 足以让 DCF 移动 10%–20%。(ii) 给监管“单批最大调整幅度”的可证明上界，但前提是路由不变，报告必须同时给路由置信度。(iii) \(\sigma_0\) 是稳定性参数，不能为截面可比无限压低。(iv) 离散切换单独枚举，不能与连续界混为一谈。

### 命题 4（合成基准上的区间校准估计精度）

**假设** (P4-a) 合成基准已知 \(V^*\)，测试案例 \(j=1,\dots,M\) 相互独立，名义覆盖 \(1-\alpha\)；(P4-b) 区间端点由 \(n\) 次蒙特卡洛估计，分位函数在邻域连续且密度有界；(P4-c) 合成生成器与估值器同族（模型正确指定）——只有此时名义覆盖才有解释力；(P4-d) 区间使用固定口径（若报告口径取“情景区间 ∩ MC”，覆盖按交集重新定义）。

**结论** (i) 覆盖率估计 \(\hat C=\frac1M\sum_j\mathbf 1\{V_j^*\in I_j\}\)，其 \(1-\gamma\) 置信半宽为 \(O(M^{-1/2})\)，区间端点误差为 \(O_p(n^{-1/2})\)，整体分辨率 \(O(M^{-1/2})+O(n^{-1/2})\)。(ii) 数值感受：\(M=1200\)、\(C=0.8\) 时 95% 半宽约 \(\pm2.3\)pp；\(n=3000\) 时端点误差对覆盖的影响应在合成基准上实测，不能用公式替代。(iii) 真实数据上 \(V^*\) 不可观测，覆盖率**无无偏估计**，只能报内部一致性校准（跨 seed / 跨评审者）与经验校准。

**证明思路** Bernoulli 方差给出 \(O(M^{-1/2})\)；分位数估计在密度有界假设下 \(\sqrt n\) 收敛；真实数据部分用不可识别性论证（无准则效度）。

**工程含义** (i) 首轮 1,200 例只能分辨约 2pp 的覆盖率差异——报告必须给 CI，不能宣称 0.8 与 0.81 的改进；(ii) MC 3000 次是端点精度与成本的折中，0.5pp 级差异不足为凭；(iii) 真实数据报“置信度单调性 + 采纳率 + 周环比稳定”，不报覆盖率；(iv) 合成基准的校准不能外推为真实校准，这是生态效度的硬限制。

---

## 7 相关工作

| 文献簇 | 代表工作 | 借用什么 | 差异与边界 |
|---|---|---|---|
| 神经模块网络 | Andreas et al., 2016 | 模块组合 + 布局由图决定 | 我们的模块是估值算子（有金融语义与约束），不是视觉/语言算子；布局由路由与证据决定，不端到端学 |
| 混合专家 | Jacobs et al., 1991；Shazeer et al., 2017 | 门控专家；专家只对部分输入负责 | 专家异质、逐券可用集不同；门控由制度/证据驱动，不做全图端到端训练 |
| 超网络 | Ha et al., 2016 | “条件生成参数”的想法：生命周期 → 模块参数 | 当前只用可控的参数表/层级收缩，不用网络生成全部参数；生成器本身也必须可审计 |
| 架构搜索 | Zoph & Le, 2017；Liu et al., 2019 | 模块/门控/池化的组合选择 | 离散、受约束、小空间、低频更新；不是 DARTS 式可微搜索 |
| 模型平均与预测组合 | Bates & Granger, 1969；Hoeting et al., 1999 | 池化作为模型平均的近亲；线性/对数意见池 | BMA 权重是后验模型概率，有似然支撑；我们的权重无真值似然，只能靠先验/证据/人评，故不可识别 |
| actor-critic 与双层优化 | Konda & Tsitsiklis, 2000；Colson et al., 2007 | 提议–裁决–更新的结构；内层单批校准、外层跨批元校准 | 无环境回报、无值函数网络；critic 是规则 + LLM 的裁决器；不能写成策略梯度定理的直接应用 |
| 可微编程 | Innes et al., 2019 | 可微子图的梯度与隐式微分 | 只用于敏感度，不承诺全图可微；不用于端到端训练 |
| LLM 多智能体辩论 | Du et al., 2024 | 多角色独立判断再汇总 | 我们把辩论约束为“参数评审”，不给叙事权；裁决目标是可行域内的有界更新，不是“更正确的文本” |
| 估值理论 | Damodaran, 2012；Ohlson, 1995；Penman, 2013 | 方法语义（生命周期、RIM 剩余收益、财务报表分析）与参数先验 | 不把估值理论当网络组件；理论提供模块的适用域与约束，VCG 提供组合与审计 |

**参考文献**（只列本文引用，不编造页码/DOI）

1. Andreas J, Rohrbach M, Darrell T, Klein D. Neural Module Networks. CVPR 2016.
2. Jacobs R A, Jordan M I, Nowlan S J, Hinton G E. Adaptive Mixtures of Local Experts. Neural Computation, 1991.
3. Shazeer N, Mirhoseini A, Maziarz K, et al. Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer. ICLR 2017.
4. Ha D, Dai A, Le Q V. HyperNetworks. arXiv:1609.09106, 2016（ICLR 2017）.
5. Zoph B, Le Q V. Neural Architecture Search with Reinforcement Learning. ICLR 2017.
6. Liu H, Simonyan K, Yang Y. DARTS: Differentiable Architecture Search. ICLR 2019.
7. Bates J M, Granger C W J. The Combination of Forecasts. Operational Research Quarterly, 1969.
8. Hoeting J A, Madigan D, Raftery A E, Volinsky C T. Bayesian Model Averaging: A Tutorial. Statistical Science, 1999.
9. Konda V R, Tsitsiklis J N. Actor-Critic Algorithms. Advances in Neural Information Processing Systems 12, 2000.
10. Colson B, Marcotte P, Savard G. An Overview of Bilevel Optimization. Annals of Operations Research, 2007.
11. Innes M, Edelman A, Fischer K, et al. A Differentiable Programming System to Bridge Machine Learning and Scientific Computing. arXiv:1907.07587, 2019.
12. Du Y, Li S, Torralba A, Tenenbaum J B, Mordatch I. Improving Factuality and Reasoning in Language Models through Multiagent Debate. ICML 2024.
13. Damodaran A. Investment Valuation: Tools and Techniques for Determining the Value of Any Asset. 3rd ed. Wiley, 2012.
14. Ohlson J A. Earnings, Book Values, and Dividends in Equity Valuation. Contemporary Accounting Research, 1995.
15. Penman S H. Financial Statement Analysis and Security Valuation. 5th ed. McGraw-Hill, 2013.
16. Jang E, Gu S, Poole B. Categorical Reparameterization with Gumbel-Softmax. ICLR 2017.
17. Williams R J. Simple Statistical Gradient-Following Algorithms for Connectionist Reinforcement Learning. Machine Learning, 1992.
18. Genest C, Zidek J V. Combining Probability Distributions: A Critique and an Annotated Bibliography. Statistical Science, 1986.
19. Manski C F. Partial Identification of Probability Distributions. Springer, 2003.

---

## 8 审稿人问题

**Q1 “这不就是把 pipeline 换成图/网络的词？”**
给出三项可检验差异：类型系统让单位/量纲错误在构图期被静态拒绝（现在靠人眼与冒烟）；图级命题（命题 1–3）是 pipeline 没有的；组合语义允许模块替换、裁剪与消融，且每节点有 trace 与证据边。若只实现“pipeline 换名词”，确实不构成贡献——所以验收标准是：类型检查有测试、至少两个命题被测试验证、模块替换消融有实验。

**Q2 “没有标签，凭什么叫学习？”**
把学习算子定义为“数据（批证据 + 评审记录）→ 参数/结构更新”：参数估计、黑箱优化、实验设计都属于广义学习；强化学习同样无标签，BMA 也是从数据更新权重。边界要诚实：我们不承诺泛化到“真值”，只承诺过程指标改善与跨期/跨指数稳健；若连这个都做不到，就只是规则调参，不叫学习。论文同时报告更新前后过程指标与失败案例。

**Q3 “为什么不用端到端 NN？”**
三个硬约束：无标签（端到端会退化为复制价格）；不可微（离散路由、硬约束、LLM）；可解释与可审计（监管要求每个数字可追溯）。NN 只能在子模块内使用（可比选择、舆情打分、证据排序），不能替代图的类型、约束与审计。反事实实验：若未来有可信的 \(V^*\) 数据集，端到端模型可作为**上界对照**，但不是可用方案。

**Q4 “合成目标不会过拟合吗？”**
会，而且比监督学习更隐蔽（没有留出标签可对照）。防线是 §4.5 的八条：预注册、目标/评估分离、留出专家/指数与时间切分、Pareto 而非标量、对抗扰动、退化断言、负结果报告、盲评仲裁。结论表述：报告“目标下降”是否与外部盲评同向；不同向时以盲评为准。

**Q5 “IPO demo 数据怎么办？”**
**demo 口径**：只用公开/构造数据，不接真实保密材料；监控与 IPO 共享模块，`mode` 只作行为/缓存开关，不做鉴权/隔离。IPO 只输出估值区间、方法分解、敏感性与约束检查，不输出单一建议发行价。生产化（权限、保密、合规）另议。

**Q6 “国家队信号是否合规？”**
系统输出“估值温度/偏离诊断”，不输出交易指令，不识别也不预测国家队行为；技术披露口径在 §1、§4.2：价格只作诊断、残差不回流；报告措辞禁用“买入/卖出/撤退/入场”。政策含义由人按程序解读，系统不承担也不暗示择时功能。

**Q7 “命题是不是 trivial、不可证伪？”**
命题 1 是归纳不变式，其价值在工程验收（caps 联合覆盖、敌对建议、回滚测试）；命题 2 证明标准，但直接给出实现断言（正性、AM-GM 间隙、尺度一致性）；命题 3 有非平凡假设（\(\sigma_0\)、软硬路由分离），且给出可测数字（1pp WACC ≈ 12% 弹性）；命题 4 是估计精度命题，明确不声称准确率。四条都绑定测试，不成立即实现有 bug——这正是它们的作用。

**Q8 “LLM 随机性使 critic 不是良定义算子，理论怎么成立？”**
把 critic 定义为随机算子 \(T:(\theta,e,\xi)\mapsto\theta'\)。命题 1 对每个实现成立（可行域保持不需要确定性）；收敛/单调性只讨论分布（支持集在 \(\mathcal C\) 内、跨批方差有界），不讨论点收敛。工程上不依赖 seed，而用 `temperature=0` + 固定 model/prompt + 响应缓存 + 3 次一致性检查；记录 model/prompt 版本与缓存 key，报告结论稳定率；不一致时走规则兜底或只做 shadow（[spec/03 §12](../spec/03-agent-review-protocol.md)）。

**Q9 “多 Agent 一定比单 Agent 更准吗？”**
不。命题 2(v) 给出反例：专家高度相关时 POE 方差被低估，集成只降随机方差、不降共同偏差；线性池会把分歧平均掉，对数池才显式惩罚分歧。正确表述是“多专家提供可分证据与可审计的分歧结构”，不是“更多 Agent 更准”。

---

## 9 与 00 的一致性、术语纪律与实现状态

### 9.1 术语纪律

| 不要写 | 写成 | 原因 |
|---|---|---|
| 端到端训练 / 训练集 | 有界校准 / 批证据 + 合成基准 | 无标签 |
| 反向传播 / 梯度下降（指全系统） | 智能体评论家 / 零阶搜索；局部梯度仅用于敏感度 | 非全图可微 |
| 损失函数（指监督损失） | 过程风险泛函 / 合成校准目标 | 无真值 |
| 准确率 / 预测误差 | 覆盖率 / 校准 / 一致性 / 稳定性 / 采纳率 | 无准则效度 |
| 层 / 神经元 / 可学习权重 | 模块 / 门控 / 参数（有金融语义与约束） | 防止过度联想 |
| 泛化 | 跨期 / 跨指数 / 跨市场稳健性 | 无 i.i.d. 监督设定 |

### 9.2 实现状态（与 [00 §7](00-evaluation.md) 的 V0–V4 对应）

| 能力 | 状态 | 依据 |
|---|---|---|
| 类型化图执行器 / 掩码批 / trace | 研究原型（本分支已实现，83 项单元测试） | `prototype/valnet/`；02 架构文档 |
| 线性池 | 已实现 | [spec/02 §4](../spec/02-valuation-model.md) |
| 对数池 / 专家乘积 | 论文扩展 | spec/02 §9 |
| 模糊 \(\alpha\)-cut | 论文扩展 | 01-paper §3.3 |
| 门控 / 残差 | 部分：Layer 0 + 六阶段方法表是近似；残差式未实现 | 04 §4.1–4.2 |
| 区间传播 | 已实现：MC 3000 + 情景区间 | spec/02 §6 |
| Agentic Critic | 部分：shadow/apply 已落地；bilevel 是最优化解释，非已实现求解器 | spec/03 |
| 合成目标 \(\mathcal L_{\rm synth}\) | 部分：一致性/稳定/采纳等指标存在，统一目标未实现 | spec/03 §9 |
| 可微 / 隐式微分 / 离散搜索 | 未实现（V4 研究） | 00 §7 |

---

## 10 未决与待核实

1. **01-paper 式 (8) 的 POE 权重形式**：独立情形应为 \(\omega_m\) 而非 \(\omega_m\omega_n\)，相关情形需精度矩阵；待与 P2 骨架统一（待核实）。
2. **Norm 的实现细节**：\(\sigma_0\)、winsorize 阈值、截面口径（当日/历史 as-of）尚未定；若无方差下限，命题 3 的 Lipschitz 界不成立（待定）。
3. **报告区间口径**：“情景区间 ∩ MC 90%”不是名义 90% 覆盖，需在合成基准上实测并改文案（待核实）。
4. **门控 \(\gamma\) 的可学习化路径**：需要先验锚点与识别条件，否则退化；无跨批参数台账（spec/03 §12）时“阶段 III 学习”无法验证。
5. **LLM 随机算子的形式化**：无 seed、无重复采样协议前，critic 的分布性质无法报告（待补实验）。
6. **命题 1 的联合覆盖**：caps 与可行域的联合覆盖尚无对抗测试证据（与 01-paper 命题 1 的条件一致，待核实）。
7. **指数聚合的处理**：成分调整、停牌、权重口径（官方/自由流通/总市值三套）如何进入图与池化层，待 02/04 文档统一。
8. **状态表中“原型”条目**：`prototype/valnet/` 的实现范围以 `prototype/valnet/README.md` 为准（已实现最小闭环；不含 LLM、生产数据、API）。
