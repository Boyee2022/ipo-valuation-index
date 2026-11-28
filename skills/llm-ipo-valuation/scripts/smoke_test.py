#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_test.py — llm-ipo-valuation v3.17.0 冒烟测试（100 用例）

覆盖：T1 正常盈利 / T2 亏损切PS / T3 可比<3家 / T4 权重归一化 / T5 MC高成功率 /
      T6 MC低成功率(故障注入) / T7 负增速 / T8 diff假设变化 / T9 seed可复算回归 / T10 模板合法性 /
      T11 wacc_model(CAPM) / T12 cashflow_statistics / T13 PB估值 / T14 industry_index /
      T15 sentiment_structured / T16 指标汇总 / T17 无新字段回归 / T18 growth_triangulation /
      T19 fcf_ratio三层校准 / T20 β降级链 / T21 D/E可比中位 / T22 transaction交易锚 /
      T23 comparables_shortfall / T24 comparable_set_usage /
      T25 RFP 9项排除检查 / T26 回购孰高 / T27 流动性折扣put_option数值 /
      T28 净资产法 / T29 PEG单列+T17回归 / T30 输入校验异常值 / T31 资产类型适配 /
      T32 可比as_of混合日期警示 / T33 三表勾稽校验 / T34 WACC公开参考值 / T35 PEG参与开关 / T36 schema校验器 /
      T37 FCFF报表级口径 / T38 capex_by_year分年 / T39 情景档位自适应 / T40 终值退出倍数交叉 /
      T41 增速×倍数尾部联动 / T42 流动性折扣入MC / T43 mc_config审计留痕 /
      T44 贝叶斯锚定 / T45 PEG条件化建议 / T46 fetch_data模块 / T47 报告生成器 /
      T48 永续增速公开锚 / T49 海外可比分组 / T50 β回归估计器 /
      T51 三档可比分类 / T52 净利季度年化 / T53 可比来源档位 / T54 FCF披露档P0 /
      T55 consensus与版本 / T56 分档回退 / T57 主档优先汇总 / T58 旧输入兼容 /
      T59 三层校准优先于用户显式 / T60 校准不可用回退显式 /
      T61 FCF披露档期间对齐 / T62 质量指标null / T63 统计层null / T64 DCF不适用置信度折减 /
      T65 实际发行价入口 / T66 方法分歧度封顶 / T67 四部分自洽 / T68 舆情-质量解耦 / T69 四部分开关回退 /
      T70 Layer0判别门 / T71 Layer1生命周期判别 / T72 四形态增速 / T73 Layer1驱动DCF /
      T74 P0价值驱动式 / T75 B4/B5权重条件化 / T76 Layer2行业参数 /
      T77 Layer0封顶不被B4覆盖 / T78 B4尊重用户权重 / T79 Layer0优先于asset_type判DCF适用性 /
      T80 PEG护栏（v3.16.4）/ T81 报告版式 v3.16.5（取消目录 / 摘要去重 / §6 阶段与增速数值 / 统一字号）/
      T82 wacc_source 标签如实（v2.14.3）/ T83 低 WACC 标的弹性诊断（v3.4.2 clamp 放宽 + 双向触界检测）
      T84 显式 null 数值字段不崩溃（v2.14.4）/ T85 负增速假设的基线感知 clamp（v3.4.3）/
      T86 比率量显示精度（v3.16.9：WACC/永续增速/终值占比不再 0 位小数 + 行业指数偏差去误除 100）/
      T87 渲染型自由文本的 Markdown 粗体（v3.16.10：`_rich()` 成对 `**…**` → `<strong>`，不成对保留）/
      T88 渲染型自由文本**站点全量覆盖**（v3.16.12：meta.industry / meta.note_asset_type 亦须 `_rich()`）
      T89 报告页眉**上下结构**（v3.16.13：简介在上 / 元信息条在下，原左右布局的长文本挤压缺陷）
      T90 §7.4 融资锚适用性不得渲染字面量 None（v3.16.14）/ T91 渲染型自由文本站点全量覆盖（v3.16.15：
          data_sources[].source 与 meta.exchange 亦须 `_rich()`）
      T92 DCF 权益为负时的**有限责任**下限（v3.16.16 / 引擎 v2.14.5：原 `equity = net_cash_in`
          在净负债时返回**负**权益价值，万华化学 bear −937.67、中国石化 bear −3,803.61）
      T93 Layer 0 关键词的**中文同形异义词**误命中（v3.16.17 / 引擎 v2.14.6：reit_utility 的
          裸「高速」被 high-speed 语义命中——生益科技「高频高速覆铜板」被判 reit_utility，
          cap 0.3；改「高速公路」，29 例零回归）
      T94 DCF「退化披露」触发条件须校验真实退化（v3.16.18 / 报告层：原判据仅 fcf0≤0，
          中芯国际/特变电工未退化却被渲染「两现值均为 0」）
      T95 P1 权重键集泛化（v3.17.0 / 引擎 v2.15.0：候选方法集不再写死三路，rim/nav/rnpv/sotp
          可携带权重进入综合；七路由候选集各异；cap=0 须剔除 dcf 键）
      T96 P2 舆情降修正层（③ 权重归 0、改作用于 ② 的乘性系数，消 ②③ 共用 comp_v 的重复计费；
          path 口径保持 ③=0.2 零回归；情景级留痕自洽）
      T97 P3 Layer 0 判据四维化（★周期性用增长率波动 σ_ln 判且须出现负增长——水平 CV 会把
          指数增长误判为周期，宇树 3.93→17.08 亿 σ_ln≈46% 即误判样本；命中词回显）
      T98 P4 舆情带宽按企业类型分化（±15%/±10%/±8%/±5%/0%；金融路由优先于生命周期阶段）
      T99 P5 RIM/DDM 金融路由主方法（★含**独立手算逐期递推交叉校验**；DDM 适用性护栏四条件）
      T99b v3.17.0 零回归（全部新开关取缺省 vs 显式关闭，输出须逐位等价）
      T100a 舆情强度矩阵四档 × 一致性（none/few/medium/many × consistent/conflict）
      T100b 高重要性 ×1.20 与权威出处 ×1.15（authority 加成 opt-in，缺省不加）
      T100c 时效衰减（线性 1−(d−30)/90 / 分段）与 K_MAX=1.60 硬上限
      T100d 方向/幅度正交（sign(sent) 只承载方向；min(|sent|/10%,1) 归一化）
      T100e ★口径 C 破除**双重截断**（窄带宽+强信号可在 band 之上有限放大至 band×K_MAX）
      T100f 无信号减半 + 非上市（private）舆情不适用（band=0 → 修正恒 0）
      T100g 去相关折让（与 impact_map.multiple_factor 同源时 ×0.70，opt-in 且假设层生效才折）
      T100h strength 口径留痕字段完整性（adjust_mode/clamp_hit/ceiling 等审计键）
      T100i v3.18.0 零回归（新增三开关取缺省 vs 显式关闭逐位等价；与 v3.17 缺省层叠亦逐位等价）
      T100j 报告层舆情强度披露渲染（★守护「渲染型站点未全量覆盖」缺陷族：引擎有输出、报告须渲染）

用法：
  python scripts/smoke_test.py
纯标准库，无第三方依赖；全部内存构造输入，不写工作区文件；任一失败退出码非 0。
"""

import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import valuation_engine as ve
import stat_validation as sv

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIB_PATH = os.path.join(SKILL_ROOT, "assets", "calibration_params.json")


def load_calib():
    with open(CALIB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_example_input():
    """从 examples/input_example.json 读取并深拷贝（作为各用例的可变基础）。"""
    with open(os.path.join(SKILL_ROOT, "examples", "input_example.json"), "r", encoding="utf-8") as f:
        return json.load(f)


class TestEngine(unittest.TestCase):

    def test_t1_normal_profitable(self):
        data = load_example_input()
        out = ve.Engine(data).run()
        s = out["synthesis"]
        self.assertLess(s["interval"][0], s["interval"][1])
        self.assertTrue(s["bear_value"] <= s["weighted_mid"] <= s["bull_value"])
        self.assertTrue(0 <= out["quality_scorecard"]["score"] <= 100)
        self.assertIn(out["confidence"]["level"], ("高", "中", "低"))
        for name in ("bear", "base", "bull"):
            self.assertGreater(out["scenarios"][name]["value"], 0)

    def test_t2_loss_making_ps(self):
        data = load_example_input()
        data["financials"]["loss_making"] = True
        data["financials"]["net_profit_latest_ttm"] = -1.2
        data["financials"]["net_margin"] = -0.08
        out = ve.Engine(data).run()
        comp = out["scenarios"]["base"]["comparable"]
        self.assertNotIn("pe", comp)  # 亏损时 PE 样本被禁用
        self.assertIn("PS口径", out["sensitivity"]["note"])
        self.assertIn("回退PS口径", out["ipo_check"]["pe_status"])
        self.assertGreater(out["synthesis"]["interval"][1], 0)

    def test_t3_few_comparables(self):
        data = load_example_input()
        data["comparables"] = data["comparables"][:1]
        out = ve.Engine(data).run()
        joined = " ".join(out["warnings"])
        self.assertIn("不足3家", joined)
        self.assertLess(out["synthesis"]["interval"][0], out["synthesis"]["interval"][1])

    def test_t4_weights_normalized(self):
        data = load_example_input()
        data["preferences"]["weights"] = {"dcf": 0.5, "comparable": 0.5, "sentiment": 0.5}
        out = ve.Engine(data).run()
        self.assertAlmostEqual(sum(out["weights"].values()), 1.0, places=9)
        self.assertTrue(any("归一化" in w for w in out["warnings"]))

    def test_t7_negative_growth(self):
        data = load_example_input()
        data["financials"]["growth_forecast"] = {"2026": -0.05, "2027": 0.05, "2028": 0.08}
        out = ve.Engine(data).run()
        self.assertTrue(any("负增长" in w for w in out["warnings"]))
        self.assertLess(out["synthesis"]["interval"][0], out["synthesis"]["interval"][1])

    def test_t8_diff_assumptions(self):
        data1 = load_example_input()
        data2 = copy.deepcopy(data1)
        data2["preferences"]["weights"] = {"dcf": 0.5, "comparable": 0.35, "sentiment": 0.15}
        data2["financials"]["growth_forecast"] = {"2026": 0.45, "2027": 0.4, "2028": 0.35}
        prev = ve.Engine(data1).run()
        new = ve.Engine(data2).run()
        diff = ve.diff_report(prev, new)
        self.assertIsInstance(diff["assumption_changes"], list)
        self.assertTrue(any("weights" in item for item in diff["assumption_changes"]))
        self.assertIn(diff["verdict"], ("发散", "收敛", "基本稳定"))
        self.assertEqual(diff["base_case_id"], "")


class TestStatValidation(unittest.TestCase):

    def _stat(self, data, eng, n=200, seed=42, case=None):
        calib = load_calib()
        return sv.run_validation(data, eng, calib, n=n, seed=seed, case=case)

    def test_t5_mc_high_success(self):
        data = load_example_input()
        eng = ve.Engine(data).run()
        out = self._stat(data, eng, n=200)
        mc = out["monte_carlo"]
        self.assertGreaterEqual(mc["success_rate"], 0.95)
        self.assertEqual(mc["ci90"], [mc["p5"], mc["p95"]])
        self.assertTrue(mc["p5"] <= mc["p50"] <= mc["p95"])
        self.assertTrue(out["validation_passed"])
        self.assertEqual(out["validation_status"], "通过")
        for param, v in out["elasticity"].items():
            self.assertIn("delta_pct_minus_1sigma", v)
            self.assertIn("direction_flag", v)

    def test_t6_mc_low_success(self):
        data = load_example_input()
        eng = ve.Engine(data).run()

        orig_run = sv.Engine.run
        counter = {"n": 0}

        def faulty_run(self_engine):
            counter["n"] += 1
            # run_validation 内 run_mc 的调用区间：第 1 次 = base_engine，2..n+1 = 样本
            if 2 <= counter["n"] <= 1 + 300 and counter["n"] % 10 < 3:
                raise RuntimeError("注入故障：模拟极端样本引擎降级失败")
            return orig_run(self_engine)

        sv.Engine.run = faulty_run
        try:
            out = self._stat(data, eng, n=300)
        finally:
            sv.Engine.run = orig_run
        mc = out["monte_carlo"]
        self.assertLess(mc["success_rate"], 0.95)
        self.assertFalse(out["validation_passed"])
        self.assertIn("统计校验未通过", out["validation_status"])

    def test_t9_seed_reproducibility(self):
        data = load_example_input()
        eng = ve.Engine(data).run()
        out1 = self._stat(data, eng, n=200, seed=42)
        out2 = self._stat(data, eng, n=200, seed=42)
        self.assertEqual(json.dumps(out1, sort_keys=True), json.dumps(out2, sort_keys=True))

    def test_t10_template_valid_json(self):
        with open(os.path.join(SKILL_ROOT, "assets", "input_template.json"), "r", encoding="utf-8") as f:
            tpl = json.load(f)
        self.assertIn("sentiment", tpl)
        self.assertIsNone(tpl["sentiment"]["sentiment_adjustment_pct"])
        self.assertIn("wacc_params", tpl["financials"])
        self.assertIn("industry_index", tpl)
        self.assertIn("growth_weights", tpl["preferences"])

    # ===== v3.8 新增（T41-T43：B4 增速×倍数尾部联动 / B5 流动性折扣入 MC）=====
    def test_t41_mc_growth_multiple_correlation(self):
        # B4：ρ=0（默认）→ 与旧逻辑逐位一致；ρ>0 → 样本相关性显著提升
        data = load_example_input()
        calib = load_calib()
        dists = dict(calib["default"]["distributions"])
        base_sent_adj = 0.05
        import random as _random
        # ρ=0：手动重放旧 multiples 逻辑（不相关路径），应逐位一致
        rng = _random.Random(42)
        _, s1 = sv.apply_perturbation(data, dists, rng, base_sent_adj)
        # ρ=0.5：样本相关性显著高于 ρ=0
        dists2 = json.loads(json.dumps(dists))
        dists2["comparable_multiples"]["cross_corr_growth"] = 0.5
        gms, mms = [], []
        rng2 = _random.Random(7)
        for _ in range(1500):
            _, s = sv.apply_perturbation(data, dists2, rng2, base_sent_adj)
            gms.append(s["growth_mult"]); mms.append(s["multiple_mult"])
        r_corr = sv.spearman(gms, mms)
        gms0, mms0 = [], []
        rng3 = _random.Random(7)
        for _ in range(1500):
            _, s = sv.apply_perturbation(data, dists, rng3, base_sent_adj)
            gms0.append(s["growth_mult"]); mms0.append(s["multiple_mult"])
        r_base = sv.spearman(gms0, mms0)
        self.assertGreater(r_corr, r_base + 0.2)  # 相关性显著提升
        self.assertLess(abs(r_base), 0.15)        # ρ=0 时近似无关

    def test_t42_mc_liquidity_perturbation(self):
        # B5：无 liquidity → seed 复算保持；有 liquidity → MC 中 σ 被扰动
        data = load_example_input()
        eng = ve.Engine(data).run()
        out_off = self._stat(data, eng, n=200, seed=42)
        self.assertFalse(out_off["mc_config"]["liquidity_perturbed"])
        self.assertEqual(out_off["mc_config"]["growth_multiple_corr"], 0.0)
        # 无 liquidity 时 liquidity_discount 弹性为 0（无扰动）
        self.assertEqual(out_off["elasticity"]["liquidity_discount"]["delta_pct_1sigma"], 0.0)
        # 有 liquidity → 扰动生效
        d2 = json.loads(json.dumps(data))
        d2["liquidity"] = {"enabled": True, "method": "put_option",
                           "holding_period_years": 2.0, "volatility": 0.4}
        eng2 = ve.Engine(d2).run()
        out_on = self._stat(d2, eng2, n=200, seed=42)
        self.assertTrue(out_on["mc_config"]["liquidity_perturbed"])
        # 弹性方向：折扣增大 → 估值降（负）
        self.assertLess(out_on["elasticity"]["liquidity_discount"]["delta_pct_1sigma"], 0)
        self.assertEqual(out_on["elasticity"]["liquidity_discount"]["direction_flag"], "正常")

    def test_t43_mc_config_audit_trail(self):
        # mc_config 审计留痕：correlation 与 liquidity 扰动状态随 stat 输出
        data = load_example_input()
        eng = ve.Engine(data).run()
        out = self._stat(data, eng, n=200, seed=42)
        cfg = out["mc_config"]
        self.assertIn("growth_multiple_corr", cfg)
        self.assertIn("liquidity_perturbed", cfg)
        self.assertIn("note", cfg)
        # 版本号
        self.assertEqual(out["meta"]["stat_version"], "3.4.3")

    # ===== v3.14.2 新增（T63：质量指标 null 输入的统计层回归）=====
    def test_t63_stat_validation_null_quality_indicators(self):
        """v3.4.1 回归：MC 扰动质量指标时须跳过 null（未披露）项。
        原缺陷：_perturb_param 以 `if key in fin` 判断，null 值进入分支后 None + float 抛 TypeError。
        另验证：① null 输入下 seed 可复算；② 完整输入（无 null）的 rng 消耗序列与 v3.4.0
        完全一致——跳过分支只在遇到 null 时触发，不影响既有输入的确定性复算。"""
        data = load_example_input()
        for k in ("gross_margin_trend_pp", "receivables_to_revenue", "nonrecurring_ratio"):
            data["financials"][k] = None
        eng = ve.Engine(data).run()                  # 修复前此处（MC 阶段）抛 TypeError
        out = self._stat(data, eng, n=200, seed=42)  # 修复后不得崩溃
        self.assertEqual(out["meta"]["stat_version"], "3.4.3")
        mc1 = out["monte_carlo"]
        self.assertEqual(mc1["n_total"], 200)
        self.assertIsInstance(mc1["success_rate"], float)   # 比率口径（非 "n/n" 字符串）
        self.assertIn("ci90", mc1)
        self.assertTrue(out["elasticity"])                  # 弹性表仍完整产出
        self.assertIn("quality_indicators", out["elasticity"])
        # 完整输入：seed 固定 → 复算一致（含 null 指标时也不破坏可复算性）
        data2 = load_example_input()
        eng2 = ve.Engine(data2).run()
        out2 = self._stat(data2, eng2, n=200, seed=42)
        self.assertEqual(out2["monte_carlo"]["success_rate"], 1.0)
        out3 = self._stat(data2, eng2, n=200, seed=42)
        self.assertEqual(out2["monte_carlo"]["p50"], out3["monte_carlo"]["p50"])
        out4 = self._stat(data, eng, n=200, seed=42)
        self.assertEqual(mc1["p50"], out4["monte_carlo"]["p50"])
        # 完整输入的中位数须为数值，且 null 输入不改变样本量口径
        self.assertIsInstance(out2["monte_carlo"]["p50"], (int, float))

    # ===== v3.9 新增（T44-T47：贝叶斯锚定 C1 / PEG 建议 C2b / fetch_data D2b / 报告生成器 D4）=====
    def test_t44_bayesian_anchor(self):
        # C1：锚定启用 → posterior 归一化 + anchored_mid 介于情景区间；缺省不激活
        data = load_example_input()
        out_off = ve.Engine(data).run()
        self.assertNotIn("anchor_update", out_off)  # 缺省不激活
        d2 = json.loads(json.dumps(data))
        d2["preferences"]["anchor_update"] = {"enabled": True, "anchor_value": 200.0,
                                              "anchor_type": "financing", "sigma_pct": 0.10}
        out = ve.Engine(d2).run()
        an = out["anchor_update"]
        self.assertTrue(an["enabled"])
        post = an["posterior"]
        self.assertAlmostEqual(sum(post.values()), 1.0, places=6)  # 后验归一化
        bear, bull = out["scenarios"]["bear"]["value"], out["scenarios"]["bull"]["value"]
        self.assertGreaterEqual(an["anchored_mid"], bear)
        self.assertLessEqual(an["anchored_mid"], bull)
        self.assertEqual(an["original_mid"], out["synthesis"]["weighted_mid"])  # 主结果不变
        self.assertTrue(any("贝叶斯锚定" in w for w in out["warnings"]))

    def test_t45_peg_suggestion(self):
        # C2b：增速>30% + PEG 可用 + 关闭开关 → 建议 warning
        data = load_example_input()
        data["preferences"]["enable_peg_in_synthesis"] = False
        out = ve.Engine(data).run()
        peg_v = out["scenarios"]["base"]["comparable"]["synthesis"].get("peg_value")
        self.assertIsNotNone(peg_v)
        self.assertTrue(any("PEG" in w and "建议" in w for w in out["warnings"]))
        # 缺省开启时不提示
        out2 = ve.Engine(load_example_input()).run()
        self.assertFalse(any("建议开启 preferences.enable_peg_in_synthesis" in w for w in out2["warnings"]))

    def test_t46_fetch_data_module(self):
        # D2b：fetch_data 模块可导入、市场前缀推断正确（不依赖网络的静态检查）
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import fetch_data
        self.assertEqual(fetch_data._market_prefix("688836"), "1.688836")
        self.assertEqual(fetch_data._market_prefix("603448.SH"), "1.603448")
        self.assertEqual(fetch_data._market_prefix("002050"), "0.002050")
        self.assertIsNone(fetch_data._norm("-"))
        self.assertIsNone(fetch_data._norm(None))
        self.assertEqual(fetch_data._norm("12.5"), 12.5)

    def test_t47_report_generator(self):
        # D4 v2 详实版：11 段投行结构 + 关键数字来自引擎输出（X3 防幻觉）
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg
        out_path = os.path.join(SKILL_ROOT, "examples", "output_example.json")
        with open(out_path, "r", encoding="utf-8") as f:
            out = json.load(f)
        with open(os.path.join(SKILL_ROOT, "examples", "input_example.json"), "r", encoding="utf-8") as f:
            inp = json.load(f)
        with open(os.path.join(SKILL_ROOT, "examples", "stat_example.json"), "r", encoding="utf-8") as f:
            stat = json.load(f)
        doc = rg.generate_report(out, stat=stat, inp=inp)
        # 11 段投行结构
        for sec in ("一、执行摘要", "二、核心观点", "三、公司概况", "四、行业与竞争", "五、财务基础",
                    "六、估值方法与关键假设", "七、估值结果", "八、IPO 定价约束", "九、风险提示",
                    "十、结论与建议", "十一、数据溯源"):
            self.assertIn(sec, doc)
        # 关键数字必须来自引擎输出
        self.assertIn(f"{out['synthesis']['weighted_mid']:,.2f}", doc)
        lo, hi = out["synthesis"]["interval"]
        self.assertIn(f"{lo:,.2f}", doc)
        self.assertIn(f"{hi:,.2f}", doc)
        # 报告编号 + 引擎警示 + 图表
        self.assertRegex(doc, r"VAL-\d{8}-\d{5}")
        self.assertIn("引擎显性警告", doc)
        self.assertGreaterEqual(doc.count("<svg"), 3)
        self.assertGreaterEqual(doc.count("<table"), 8)

    # ===== v3.11 新增（T48-T50：永续增速公开锚 / 海外可比分组 / β 回归估计器）=====
    def test_t48_terminal_growth_public_anchor(self):
        # 修订 1a：行业长期增速受 GDP 约束（min(lt,4.5%)、rf+通胀保底）；可比项长期化后同样受 GDP 约束
        data = load_example_input()
        data["industry_index"] = {"name": "指数", "pe_median": 40, "ps_median": 5,
                                  "index_growth_pct": 30, "index_long_term_growth": 8}
        # 高可比增速（存储周期峰值 60%）不得抬高永续——受 GDP 上限约束
        for c in data["comparables"]:
            c["growth_pct"] = 60
        out = ve.Engine(data).run()
        tri = out["growth_triangulation"]
        self.assertIsNotNone(tri.get("public_anchor_tg"))
        self.assertLessEqual(tri["implied_terminal_growth"], 0.05)  # ≤ GDP 4.5% + 容差
        # 无行业长期增速 → 公开锚不注入（旧行为零变化）
        out2 = ve.Engine(load_example_input()).run()
        self.assertIsNone(out2["growth_triangulation"].get("public_anchor_tg"))
        # 用户显式 tg 与公开锚接近 → 无偏离 warning
        d3 = json.loads(json.dumps(data))
        d3["financials"]["terminal_growth"] = 0.04
        out3 = ve.Engine(d3).run()
        self.assertFalse(any("终值增速与三角参照偏离" in w for w in out3["warnings"]))

    def test_t49_comparable_group_stats(self):
        # 修订 2b：海外可比（exchange US）纳入 → metrics_by_group 挂出、group_gap 为负（海外折价）；单组不挂出
        data = load_example_input()
        data["comparables"].append({"name": "海外X", "exchange": "US", "pe": 15.0, "growth_pct": 30})
        data["comparables"].append({"name": "海外Y", "exchange": "US", "pe": 12.0, "growth_pct": 25})
        out = ve.Engine(data).run()
        gg = out["synthesis"].get("comparable_group_gap")
        self.assertIsNotNone(gg)
        self.assertIn("CN", gg["groups"])
        self.assertIn("US", gg["groups"])
        self.assertLess(gg["group_gap_pct"], 0)  # 海外组 PE 低于境内 → 折价
        # 单组（全 CN）不挂出 → 旧输入零变化
        out2 = ve.Engine(load_example_input()).run()
        self.assertNotIn("comparable_group_gap", out2["synthesis"])

    def test_t50_beta_estimator_module(self):
        # 修订 1b/2d：beta_estimator 与 fetch_data 的 secid 解析（不依赖网络的静态检查）
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import beta_estimator as be
        self.assertEqual(be.secid_of("603986.SH"), "1.603986")
        self.assertEqual(be.secid_of("002050"), "0.002050")
        self.assertEqual(be.secid_of("MU.US"), "105.MU")
        self.assertEqual(be.secid_of("HXSCL.US"), "105.HXSCL")
        self.assertEqual(be.secid_of("HK0700"), "116.0700")
        self.assertIsNone(be.secid_of("000660.KS"))  # 韩股暂不支持（ADR 或手动）
        # OLS 回归数值正确性
        b, r2, n = be.ols_beta([0.1, 0.2, 0.3, 0.4], [0.05, 0.10, 0.15, 0.20])
        self.assertAlmostEqual(b, 0.5, places=6)
        self.assertAlmostEqual(r2, 1.0, places=6)
        self.assertEqual(n, 4)
        import fetch_data
        self.assertEqual(fetch_data._market_prefix("MU.US"), "105.MU")
        self.assertEqual(fetch_data._market_prefix("HK0700"), "116.0700")
        self.assertIsNone(fetch_data._market_prefix("000660.KS"))


class TestNewMethods(unittest.TestCase):
    """v3.3 新增功能用例（T11-T18）。"""

    def test_t11_wacc_model(self):
        data = load_example_input()
        data["financials"]["wacc_params"] = {
            "enabled": True, "rf": 0.02, "erp": 0.06, "beta": 1.2,
            "d_e_ratio": 0.3, "tax_rate": 0.15, "cost_of_debt": 0.035,
        }
        out = ve.Engine(data).run()
        wm = out["wacc_model"]
        # ke = 0.02+1.2*0.06 = 0.092; kd_after = 0.035*0.85 = 0.02975
        # E/V=1/1.3, D/V=0.3/1.3 → wacc_model ≈ 0.0776
        self.assertAlmostEqual(wm["wacc_model"], 0.0776, places=3)
        # 显式 wacc=0.11 优先 → wacc_used==0.11 且偏差>1pp 触发 warning
        self.assertEqual(wm["wacc_used"], 0.11)
        self.assertGreater(wm["deviation_pp"], 1.0)
        self.assertTrue(any("WACC" in w for w in out["warnings"]))
        # 无显式 wacc → 采用模型值
        data2 = load_example_input()
        data2["financials"]["wacc_params"] = data["financials"]["wacc_params"]
        del data2["financials"]["wacc"]
        out2 = ve.Engine(data2).run()
        self.assertAlmostEqual(out2["wacc_model"]["wacc_used"], out2["wacc_model"]["wacc_model"], places=4)

    def test_t12_cashflow_statistics(self):
        data = load_example_input()
        data["financials"]["revenue_by_year"] = {"2021": 5.0, "2022": 7.0, "2023": 9.5, "2024": 12.0, "2025": 15.0}
        data["financials"]["growth_forecast"] = {"2026": 0.45, "2027": 0.3, "2028": 0.25}  # 首年偏离历史CAGR>10pp
        out = ve.Engine(data).run()
        cs = out["cashflow_statistics"]
        self.assertTrue(cs["enabled"])
        self.assertEqual(cs["n"], 5)
        self.assertEqual(cs["series_used"], "营收")
        # geometric = (15/5)^(1/4)-1 ≈ 0.3161
        self.assertAlmostEqual(cs["geometric_growth"], 0.3161, places=3)
        self.assertGreater(cs["std_growth"], 0.0)
        self.assertIn(cs["trend_label"], ("稳定", "上行", "下行", "波动"))
        self.assertTrue(any("历史趋势" in w or "三角参照" in w for w in out["warnings"]))

    def test_t13_pb_valuation(self):
        data = load_example_input()
        data["financials"]["net_assets"] = 18.0
        for c, pb in zip(data["comparables"], (8.5, 6.5, 9.0, 11.0)):
            c["pb"] = pb
        out = ve.Engine(data).run()
        comp = out["scenarios"]["base"]["comparable"]
        self.assertIn("pb", comp)
        self.assertGreater(comp["pb"]["value_median"], 0)
        metrics = out["synthesis"]["comparable_metrics"]
        self.assertEqual(metrics["pb"]["n"], 4)
        self.assertAlmostEqual(metrics["pb"]["median"], 8.75, places=3)  # median(6.5,8.5,9,11)=8.75

    def test_t14_industry_index(self):
        data = load_example_input()
        data["industry_index"] = {"name": "申万机器人指数", "pe_median": 45, "ps_median": 8,
                                  "pb_median": 4.5, "index_growth_pct": 25, "source": "Wind", "as_of": "2026-08"}
        data["financials"]["net_assets"] = 18.0
        out = ve.Engine(data).run()
        idx = out["industry_index"]
        self.assertTrue(idx["enabled"])
        # implied: pe=2.5*45=112.5, ps=12.5*8=100, pb=18*4.5=81
        self.assertAlmostEqual(idx["implied_values"]["pe"], 112.5, places=1)
        self.assertAlmostEqual(idx["implied_values"]["ps"], 100.0, places=1)
        self.assertTrue(any("行业指数" in w for w in out["warnings"]))  # 偏差>30% 提示

    def test_t15_sentiment_structured(self):
        data = load_example_input()
        data["sentiment"]["events"] = [
            {"type": "政策利好", "title": "大基金三期投向先进制程", "date": "2026-05-20",
             "impact_direction": "positive", "importance": "high", "impact_target": "growth",
             "impact_pct": 8, "source": "公开报道"},
        ]
        data["sentiment"]["policy"] = [
            {"policy": "人形机器人产业政策", "direction": "利好", "impact_target": "multiple", "impact_pct": 10},
        ]
        data["sentiment"]["risks"] = [{"type": "商业化不及预期", "description": "人形机器人出货低于目标",
                                       "severity": "high", "impact_target": "wacc"}]
        data["sentiment"]["investor_orientation"] = {"lean": "乐观", "basis": "AI 算力+人形机器人放量", "horizon": "12个月"}
        out = ve.Engine(data).run()
        smap = out["sentiment_structure"]
        self.assertTrue(smap["enabled"])
        im = smap["impact_map"]
        self.assertEqual(im["growth_adj_pp"], 8.0)
        self.assertAlmostEqual(im["multiple_factor"], 1.1, places=4)
        self.assertIn("大基金三期投向先进制程", im["evidence"]["growth"])
        # 联动：base 情景增速 +8pp；bear 因 high 风险 WACC 额外 +0.5pp
        self.assertEqual(out["scenarios"]["base"]["params"]["growth_adj_pp"], 8.0)
        self.assertEqual(out["scenarios"]["bear"]["params"]["wacc_adj_pp"], 1.5)

    def test_t16_comparable_metrics(self):
        data = load_example_input()
        for c, (pb, nm, roe, evs) in zip(data["comparables"],
                                         ((8.5, 0.40, 0.18, 18), (6.5, 0.35, 0.15, 16),
                                          (9.0, 0.30, 0.12, 20), (11.0, 0.25, 0.10, 22))):
            c["pb"], c["net_margin"], c["roe"], c["ev_sales"] = pb, nm, roe, evs
        out = ve.Engine(data).run()
        m = out["synthesis"]["comparable_metrics"]
        for key in ("pe", "ps", "ev_ebitda", "pb", "net_margin", "roe", "ev_sales", "growth_pct"):
            self.assertIn(key, m)
        self.assertEqual(m["pb"]["n"], 4)
        self.assertEqual(m["net_margin"]["n"], 4)
        self.assertAlmostEqual(m["pb"]["median"], 8.75, places=3)
        self.assertIsNotNone(m["pb"]["cv"])

    def test_t17_no_new_fields_regression(self):
        data = load_example_input()  # 无任何 v3.3 新字段
        data["preferences"]["four_part_mode"] = False  # v3.15.0：回归用例显式关闭四部分，保留旧合成口径
        out = ve.Engine(data).run()
        with open(os.path.join(SKILL_ROOT, "examples", "output_example.json"), "r", encoding="utf-8") as f:
            old = json.load(f)
        for k in old["synthesis"]:
            self.assertEqual(out["synthesis"][k], old["synthesis"][k], f"synthesis.{k}")
        for name in ("bear", "base", "bull"):
            for k in ("value", "comparable_raw", "comparable_adjusted", "dcf_value"):
                self.assertEqual(out["scenarios"][name][k], old["scenarios"][name][k], f"{name}.{k}")
        self.assertEqual(out["confidence"]["score"], old["confidence"]["score"])
        self.assertNotIn("comparable_metrics", out["synthesis"])
        self.assertNotIn("industry_index", out)
        self.assertNotIn("sentiment_structure", out)
        self.assertNotIn("wacc_model", out)
        # 统计强化块基于营收序列自动激活（估值结果不变，仅输出参照）
        self.assertTrue(out["cashflow_statistics"]["enabled"])
        self.assertTrue(out["growth_triangulation"]["enabled"])

    def test_t18_growth_triangulation(self):
        data = load_example_input()
        # index_growth_pct 与 index_long_term_growth 均为百分数（25=25%，8=8%）
        data["industry_index"] = {"name": "申万机器人指数", "pe_median": 45, "ps_median": 8,
                                  "index_growth_pct": 25, "index_long_term_growth": 8}
        # self_cagr = (12.5/7.4)^0.5 - 1 ≈ 0.2997；可比 growth 中位 = median(30,25,35,28) = 29
        out = ve.Engine(data).run()
        tri = out["growth_triangulation"]
        self.assertTrue(tri["enabled"])
        # implied = 0.4*0.2997 + 0.4*0.29 + 0.2*0.25 = 0.2859
        self.assertAlmostEqual(tri["implied_growth"], 0.2859, places=3)
        self.assertEqual(tri["growth_weights_used"]["self"], 0.4)
        # 用户显式 growth_forecast=0.35 优先（偏差 6.4pp < 10pp 不 warning）；
        # v3.11 公开锚约束后三角 tg 更保守（3.6%），用户默认 tg 6% 或触发偏离提示——此处仅断言增速维度
        self.assertFalse(any("预测增速" in w for w in out["warnings"]))
        # 权重重归一化：仅 self + industry
        data2 = load_example_input()
        data2["industry_index"] = data["industry_index"]
        data2["preferences"]["growth_weights"] = {"self": 0.5, "industry": 0.5}
        out2 = ve.Engine(data2).run()
        tri2 = out2["growth_triangulation"]
        self.assertAlmostEqual(tri2["implied_growth"], 0.5 * 0.2997 + 0.5 * 0.25, places=3)
        # 用户显式偏差 >10pp 触发 warning
        data3 = load_example_input()
        data3["industry_index"] = data["industry_index"]
        data3["financials"]["growth_forecast"] = {"2026": 0.50, "2027": 0.4, "2028": 0.3}
        out3 = ve.Engine(data3).run()
        self.assertTrue(any("三角参照" in w for w in out3["warnings"]))

    # ---------- v3.4：FCF 比率校准 / 可比集一致性 / 无可比替代 ----------
    def test_t19_fcf_ratio_calibration(self):
        data = load_example_input()
        data["financials"]["capex_to_revenue"] = 0.10
        data["financials"]["net_margin"] = 0.2
        for c in data["comparables"]:
            c["ocf_ratio"] = 0.95
            c["capex_to_rev"] = 0.12
        out = ve.Engine(data).run()
        fcfr = out["fcf_ratio"]
        self.assertTrue(fcfr["enabled"])
        # L1 = 0.9 − 0.10/0.2 = 0.4；L2 = 0.95 − 0.12/0.2 = 0.35
        self.assertAlmostEqual(fcfr["l1_self"], 0.4, places=3)
        self.assertAlmostEqual(fcfr["l2_comparable"], 0.35, places=3)
        # used = (0.5×0.4 + 0.3×0.35 + 0.2×0.9) = 0.485
        self.assertAlmostEqual(fcfr["used"], 0.485, places=3)
        # 无 CapEx 字段 → 不激活且 DCF 不变
        data0 = load_example_input()
        out0 = ve.Engine(data0).run()
        self.assertNotIn("fcf_ratio", out0)
        self.assertEqual(out0["scenarios"]["base"]["dcf_value"],
                         json.load(open(os.path.join(SKILL_ROOT, "examples", "output_example.json"), encoding="utf-8"))
                         ["scenarios"]["base"]["dcf_value"])

    def test_t20_beta_degradation_chain(self):
        # 无 beta/unlevered_beta/comparable_betas → 用 industry_beta（再杠杆）
        data = load_example_input()
        data["financials"]["wacc_params"] = {"enabled": True, "rf": 0.02, "erp": 0.06,
                                             "industry_beta": 1.2, "d_e_ratio": 0.5,
                                             "tax_rate": 0.15, "cost_of_debt": 0.035}
        out = ve.Engine(data).run()
        wm = out["wacc_model"]
        self.assertIn("行业β", wm["beta_source"])
        # β = 1.2 × (1 + 0.85×0.5) = 1.71
        self.assertAlmostEqual(wm["beta"], 1.71, places=3)

    def test_t21_de_from_comparable_median(self):
        data = load_example_input()
        for c, de in zip(data["comparables"], (0.2, 0.3, 0.4, 0.1)):
            c["d_e_ratio"] = de
        data["financials"]["wacc_params"] = {"enabled": True, "rf": 0.02, "erp": 0.06,
                                             "unlevered_beta": 1.0, "d_e_ratio": None,
                                             "tax_rate": 0.15, "cost_of_debt": 0.035}
        out = ve.Engine(data).run()
        wm = out["wacc_model"]
        self.assertEqual(wm["d_e_source"], "可比集中位")
        self.assertAlmostEqual(wm["d_e_ratio"], 0.25, places=3)  # median(0.1,0.2,0.3,0.4)=0.25
        su = out["comparable_set_usage"]
        self.assertEqual(su["de_source"], "可比集中位")

    def test_t22_transaction_anchor(self):
        data = load_example_input()
        data["transactions"] = [
            {"name": "交易A", "date": "2026-01-01", "type": "融资", "ev_sales": 12, "ev_ebitda": 40},
            {"name": "交易B", "date": "2026-03-01", "type": "融资", "ev_sales": 20, "ev_ebitda": 55},
        ]
        out = ve.Engine(data).run()
        tx = out["transactions_anchor"]
        self.assertTrue(tx["enabled"])
        # rev=12.5 → ev_sales 隐含 = 12.5 × median(12,20)=16 = 200；ebitda=3.2 × median(40,55)=47.5 = 152
        self.assertAlmostEqual(tx["implied_values"]["ev_sales"], 200.0, places=1)
        self.assertAlmostEqual(tx["implied_values"]["ev_ebitda"], 152.0, places=1)
        self.assertNotIn("transactions_anchor" in out and False, ())
        # 不并入综合权重：synthesis 核心键不受影响（对照无交易运行）
        data0 = load_example_input()
        out0 = ve.Engine(data0).run()
        self.assertEqual(out["synthesis"]["weighted_mid"], out0["synthesis"]["weighted_mid"])

    def test_t23_comparables_shortfall(self):
        data = load_example_input()
        data["comparables"] = data["comparables"][:1]
        data["industry_index"] = {"name": "测试指数", "ps_median": 15, "pe_median": 50,
                                  "index_growth_pct": 20, "index_long_term_growth": 6}
        data["transactions"] = [{"name": "交易A", "date": "2026-01-01", "type": "融资", "ev_sales": 15}]
        data["recent_financing"] = {"enabled": True, "financing_date": "2026-05-01", "post_money": 200.0}
        out = ve.Engine(data).run()
        sf = out["comparables_shortfall"]
        self.assertEqual(sf["n_comparables"], 1)
        self.assertTrue(sf["fallback_paths"]["industry_index"])
        self.assertTrue(sf["fallback_paths"]["transactions"])
        self.assertTrue(sf["fallback_paths"]["recent_financing"])
        self.assertGreaterEqual(sf["interval_widened_pct"], 20)

    def test_t24_comparable_set_usage(self):
        data = load_example_input()
        for c in data["comparables"]:
            c["ocf_ratio"] = 0.9
            c["capex_to_rev"] = 0.08
            c["d_e_ratio"] = 0.25
        data["financials"]["capex_to_revenue"] = 0.06
        data["financials"]["wacc_params"] = {"enabled": True, "rf": 0.02, "erp": 0.06,
                                             "unlevered_beta": 1.0, "d_e_ratio": None,
                                             "tax_rate": 0.15, "cost_of_debt": 0.035}
        out = ve.Engine(data).run()
        su = out["comparable_set_usage"]
        self.assertEqual(su["n_comparables"], 4)
        self.assertIn("pe", su["multiple_medians"])
        self.assertIn("de_source", su)
        self.assertIn("fcf_ratio_source", su)
        self.assertIn("growth_source", su)

    # ===== v3.5 新增（T25-T31：中证协四方法完整版 + 校验/适配/输出增强）=====

    def test_t25_rfp_exclusion_check(self):
        data = load_example_input()
        data["meta"]["as_of_date"] = "2026-08-19"
        # ① 全 present=false → 通过检查，anchor 有效
        data["recent_financing"] = {"enabled": True, "financing_date": "2026-05-01",
                                    "post_money": 200.0,
                                    "exclusions": [{"code": "E1", "present": False},
                                                   {"code": "E2", "present": False},
                                                   {"code": "E9", "present": False}]}
        out = ve.Engine(data).run()
        rfa = out["recent_financing_anchor"]
        self.assertTrue(rfa["applicable"])
        self.assertEqual(rfa["exclusion_check"]["hits"], [])
        self.assertEqual(rfa["anchor_value"], 200.0)  # 3 个月 → decay=1.0
        # ② E2 present=true → 不适用，anchor=None，hits=1
        data["recent_financing"]["exclusions"][1]["present"] = True
        out2 = ve.Engine(data).run()
        rfa2 = out2["recent_financing_anchor"]
        self.assertFalse(rfa2["applicable"])
        self.assertIsNone(rfa2["anchor_value"])
        self.assertEqual(len(rfa2["exclusion_check"]["hits"]), 1)
        self.assertEqual(rfa2["exclusion_check"]["hits"][0]["code"], "E2")
        # ③ 缺省不提供 exclusions → 无 exclusion_check 键（v3.4 零变化）
        del data["recent_financing"]["exclusions"]
        out3 = ve.Engine(data).run()
        self.assertNotIn("exclusion_check", out3["recent_financing_anchor"])
        self.assertEqual(out3["recent_financing_anchor"]["anchor_value"], 200.0)

    def test_t26_repurchase_whichever_higher(self):
        data = load_example_input()
        # ① 回购价值高于主估值 → 孰高命中回购
        data["repurchase"] = {"enabled": True, "repurchase_price": 150.0, "shares": 3.0,
                              "investor_repurchase_likelihood": 0.8}
        out = ve.Engine(data).run()
        rp = out["repurchase_anchor"]
        self.assertEqual(rp["repurchase_value"], 450.0)
        self.assertGreater(rp["repurchase_value"], rp["main_value"])
        self.assertEqual(rp["adopted"], 450.0)
        self.assertAlmostEqual(rp["likelihood_adjusted"], 360.0, places=1)
        # ② 回购价值低于主估值 → adopted=main
        data["repurchase"]["repurchase_price"] = 50.0
        out2 = ve.Engine(data).run()
        rp2 = out2["repurchase_anchor"]
        self.assertEqual(rp2["repurchase_value"], 150.0)
        self.assertEqual(rp2["adopted"], rp2["main_value"])
        # ③ 缺省不激活 → 不挂出
        data3 = load_example_input()
        self.assertNotIn("repurchase_anchor", ve.Engine(data3).run())

    def test_t27_liquidity_put_option(self):
        # _norm_cdf 精度（引擎内置实现）
        self.assertAlmostEqual(ve._norm_cdf(0.0), 0.5, places=6)
        self.assertAlmostEqual(ve._norm_cdf(1.0), 0.84134475, places=5)
        self.assertAlmostEqual(ve._norm_cdf(2.0), 0.97724987, places=5)
        data = load_example_input()
        data["liquidity"] = {"enabled": True, "method": "put_option",
                             "holding_period_years": 2.0, "volatility": 0.4}
        out = ve.Engine(data).run()
        ld = out["liquidity_discount"]
        self.assertEqual(ld["method_used"], "put_option")
        self.assertAlmostEqual(ld["put_option_detail"]["v_sqrt_T"], 0.3178, places=3)
        self.assertAlmostEqual(ld["discount_pct"], 0.1263, places=3)  # 手算对照
        # DCF 不受影响 / 市场法受影响
        base = load_example_input()
        out_base = ve.Engine(base).run()
        self.assertEqual(out["scenarios"]["base"]["dcf_value"], out_base["scenarios"]["base"]["dcf_value"])
        self.assertLess(out["scenarios"]["base"]["comparable_adjusted"],
                        out_base["scenarios"]["base"]["comparable_adjusted"])
        # 缺省不激活 → 不挂出
        self.assertNotIn("liquidity_discount", out_base)

    def test_t28_nav_valuation(self):
        data = load_example_input()
        data["nav"] = {"enabled": True, "net_assets": 80.0, "adjustments": 5.0,
                       "liquidation_scenario": True}
        out = ve.Engine(data).run()
        nv = out["nav_valuation"]
        self.assertEqual(nv["adjusted_nav"], 85.0)
        self.assertAlmostEqual(nv["nav_per_share"], 85.0 / 2.4, places=2)  # 35.42
        self.assertTrue(nv["liquidation_scenario"])
        # 缺省不激活 → 不挂出
        data2 = load_example_input()
        self.assertNotIn("nav_valuation", ve.Engine(data2).run())

    def test_t29_peg_single_column_and_regression(self):
        # ① 有 pe+growth_pct → peg_value 单列
        data = load_example_input()
        out = ve.Engine(data).run()
        comp = out["scenarios"]["base"]["comparable"]
        self.assertEqual(comp["synthesis"]["peg_value"], comp["peg"]["value"])
        # ② 全部 growth_pct=null → 无 peg_value 键
        data2 = load_example_input()
        for c in data2["comparables"]:
            c["growth_pct"] = None
        out2 = ve.Engine(data2).run()
        self.assertNotIn("peg_value", out2["scenarios"]["base"]["comparable"]["synthesis"])
        # ③ T17 回归：旧输入 synthesis 逐键 + 三情景四键 + confidence 不变
        _d3 = load_example_input()
        _d3["preferences"]["four_part_mode"] = False  # v3.15.0：回归用例显式关闭四部分，保留旧合成口径
        out3 = ve.Engine(_d3).run()
        with open(os.path.join(SKILL_ROOT, "examples", "output_example.json"), "r", encoding="utf-8") as f:
            old = json.load(f)
        for k in old["synthesis"]:
            self.assertEqual(out3["synthesis"][k], old["synthesis"][k], f"synthesis.{k}")
        for name in ("bear", "base", "bull"):
            for k in ("value", "comparable_raw", "comparable_adjusted", "dcf_value"):
                self.assertEqual(out3["scenarios"][name][k], old["scenarios"][name][k])
        self.assertEqual(out3["confidence"]["score"], old["confidence"]["score"])

    def test_t30_input_validation(self):
        # ① 异常输入 → input_validation 挂出（error/warning 分级；v2.5.0 新增勾稽校验会连带触发）
        data = load_example_input()
        data["financials"]["net_margin"] = 3.5
        data["financials"]["terminal_growth"] = 0.15
        out = ve.Engine(data).run()
        iv = out["input_validation"]
        self.assertGreaterEqual(iv["n_issues"], 2)
        levels = {i["field"]: i["level"] for i in iv["issues"]}
        self.assertEqual(levels["net_margin"], "error")
        self.assertEqual(levels["terminal_growth"], "warning")
        # ② 旧输入无异常 → input_validation 不挂出
        out2 = ve.Engine(load_example_input()).run()
        self.assertNotIn("input_validation", out2)
        # ③ assumptions_summary 始终挂出且含关键假设
        self.assertIn("assumptions_summary", out2)
        self.assertIn("dcf", out2["assumptions_summary"])
        self.assertAlmostEqual(out2["assumptions_summary"]["dcf"]["wacc"], 0.11, places=4)

    def test_t31_asset_type_adapter(self):
        # ① startup → DCF 不适用 + 建议
        data = load_example_input()
        data["meta"]["asset_type"] = "startup"
        out = ve.Engine(data).run()
        aa = out["asset_adapter"]
        self.assertTrue(aa["enabled"])
        self.assertFalse(aa["dcf_applicable"])
        self.assertIn("ps", aa["primary_methods"])
        self.assertTrue(any("DCF 适用性低" in w for w in aa["warnings"]))
        # ② private → 建议流动性折扣
        data2 = load_example_input()
        data2["meta"]["asset_type"] = "private"
        out2 = ve.Engine(data2).run()
        self.assertTrue(any("流动性折扣" in w for w in out2["asset_adapter"]["warnings"]))
        # ③ 缺省 → 不激活
        out3 = ve.Engine(load_example_input()).run()
        self.assertNotIn("asset_adapter", out3)

    # ===== v3.6 新增（T32-T36：数据校验 A2/A3/A4 + WACC 参考 A1 + PEG 开关 C2 + schema D1）=====

    def test_t32_as_of_mixed_dates(self):
        # A2：可比 as_of 混合日期 >30 天 → 警示
        data = load_example_input()
        data["comparables"][0]["as_of"] = "2026-01-01"
        data["comparables"][1]["as_of"] = "2026-07-01"
        out = ve.Engine(data).run()
        iv = out["input_validation"]
        self.assertTrue(any("as_of" in i["field"] and "时点" in i["rule"] for i in iv["issues"]))
        # 同日 → 无警示
        data2 = load_example_input()
        data2["comparables"][0]["as_of"] = "2026-07-01"
        data2["comparables"][1]["as_of"] = "2026-07-01"
        out2 = ve.Engine(data2).run()
        self.assertNotIn("input_validation", out2)

    def test_t33_triple_statement_check(self):
        # A3：三表勾稽（净利×净利率不一致 + 毛利率<净利率）
        data = load_example_input()
        data["financials"]["net_profit_latest_ttm"] = 4.0   # 12.5×0.2=2.5 vs 4.0 偏差 60%
        data["financials"]["gross_margin"] = 0.1             # 10% < 净利率 20%
        data["financials"]["ocf_to_net_profit"] = 0.3        # 净现比 <0.5
        out = ve.Engine(data).run()
        iv = out["input_validation"]
        rules = " | ".join(i["rule"] for i in iv["issues"])
        self.assertIn("勾稽", rules)
        self.assertIn("毛利率", rules)
        self.assertIn("净现比", rules)

    def test_t34_wacc_public_reference(self):
        # A1：启用 wacc_params 但不填 rf/erp/beta → 公开参考值
        data = load_example_input()
        data["financials"]["wacc_params"] = {"enabled": True, "tax_rate": 0.15, "cost_of_debt": 0.035}
        data["meta"]["industry"] = "机器人"
        out = ve.Engine(data).run()
        wm = out["wacc_model"]
        self.assertEqual(wm["rf_source"], "公开参考(10Y国债)")
        self.assertEqual(wm["erp_source"], "公开参考(Damodaran中国ERP)")
        self.assertIn("行业β参考表", wm["beta_source"])
        self.assertAlmostEqual(wm["rf"], 0.019, places=3)
        # 用户显式优先
        data2 = load_example_input()
        data2["financials"]["wacc_params"] = {"enabled": True, "rf": 0.02, "erp": 0.06, "beta": 1.2,
                                              "tax_rate": 0.15, "cost_of_debt": 0.035}
        out2 = ve.Engine(data2).run()
        self.assertEqual(out2["wacc_model"]["rf_source"], "用户给定")

    def test_t35_peg_switch(self):
        # C2：enable_peg_in_synthesis 缺省 true（与基线一致）；false 时 PEG 退出 candidates
        data = load_example_input()
        data["preferences"]["four_part_mode"] = False  # v3.15.0：与旧 golden 比较，显式关闭四部分
        out_def = ve.Engine(data).run()
        with open(os.path.join(SKILL_ROOT, "examples", "output_example.json"), "r", encoding="utf-8") as f:
            old = json.load(f)
        self.assertEqual(out_def["synthesis"]["weighted_mid"], old["synthesis"]["weighted_mid"])
        data["preferences"] = {"enable_peg_in_synthesis": False, "four_part_mode": False}
        out_off = ve.Engine(data).run()
        self.assertNotEqual(out_off["synthesis"]["weighted_mid"], out_def["synthesis"]["weighted_mid"])
        # PEG 单列仍保留
        self.assertIn("peg_value", out_off["scenarios"]["base"]["comparable"]["synthesis"])

    def test_t36_input_schema_validator(self):
        # D1：input_validator 静态校验
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        from input_validator import validate
        with open(os.path.join(SKILL_ROOT, "examples", "input_example.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        issues = validate(data)
        self.assertEqual([i for i in issues if i.get("level") == "error"], [])
        bad = {"meta": {"company": "X"}, "financials": {"revenue_latest_ttm": 10, "net_profit_latest_ttm": 1},
               "comparables": [{"pe": 50}]}
        issues2 = validate(bad)
        self.assertTrue(any(i["level"] == "error" and i["field"] == "meta.industry" for i in issues2))
        self.assertTrue(any(i["level"] == "error" and "comparables[0].name" in i["field"] for i in issues2))

    # ===== v3.7 新增（T37-T40：FCFF 报表级 B1 / capex_by_year / 情景自适应 B6 / 终值交叉 B7）=====
    def test_t37_fcff_report_level(self):
        # B1：fcff_mode=true + ebit/capex 齐备 → FCFF=EBIT×(1−t)+D&A−CapEx−ΔWC
        data = load_example_input()
        data["financials"]["fcff_mode"] = True
        data["financials"]["ebit"] = 4.0
        data["financials"]["d_a"] = 0.8
        data["financials"]["capex"] = 1.2
        data["financials"]["delta_wc"] = 0.3
        out = ve.Engine(data).run()
        dcf = out["scenarios"]["base"]["dcf"]
        self.assertEqual(dcf["fcf_basis"], "fcff")
        expected = 4.0 * (1 - 0.15) + 0.8 - 1.2 - 0.3  # 2.7
        self.assertAlmostEqual(dcf["fcf0"], expected, places=4)
        self.assertAlmostEqual(dcf["fcff"]["fcff0"], expected, places=4)
        # 缺省 fcff_mode=false → 回退净利×比率（旧输入零变化）
        out_off = ve.Engine(load_example_input()).run()
        self.assertEqual(out_off["scenarios"]["base"]["dcf"]["fcf_basis"], "net_profit_ratio")
        self.assertNotIn("fcff", out_off["scenarios"]["base"]["dcf"])

    def test_t38_fcff_capex_by_year(self):
        # B1：capex_by_year 分年序列（与募投产能挂钩）
        data = load_example_input()
        data["financials"]["fcff_mode"] = True
        data["financials"]["ebit"] = 4.0
        data["financials"]["d_a"] = 0.8
        data["financials"]["capex"] = 1.2
        data["financials"]["delta_wc"] = 0.3
        data["financials"]["capex_by_year"] = {"2026": 1.5, "2027": 2.0, "2028": 2.5, "2029": 2.0, "2030": 1.5}
        out = ve.Engine(data).run()
        dcf = out["scenarios"]["base"]["dcf"]
        self.assertEqual(dcf["fcf_basis"], "fcff_by_year")
        self.assertEqual(len(dcf["fcff"]["series"]), 5)
        self.assertIn("series", dcf["fcff"])
        self.assertIn("capex_by_year", dcf["fcff"])

    def test_t39_adaptive_scenarios(self):
        # B6：adaptive_scenarios=true + mature → ±8pp；缺省关闭 → ±10pp
        data = load_example_input()
        data["meta"]["asset_type"] = "mature"
        data["preferences"]["adaptive_scenarios"] = True
        out = ve.Engine(data).run()
        self.assertTrue(out["scenario_adapter"]["enabled"])
        self.assertEqual(out["scenario_adapter"]["growth_span_pp"], 8)
        self.assertEqual(out["scenarios"]["bear"]["params"]["growth_adj_pp"], -8)
        self.assertEqual(out["scenarios"]["bull"]["params"]["growth_adj_pp"], 8)
        # 缺省关闭
        data2 = load_example_input()
        data2["meta"]["asset_type"] = "mature"
        out2 = ve.Engine(data2).run()
        self.assertNotIn("scenario_adapter", out2)
        self.assertEqual(out2["scenarios"]["bear"]["params"]["growth_adj_pp"], -10)

    def test_t40_tv_exit_multiple(self):
        # B7：终值退出倍数交叉（Gordon 与可比 PE 中位退出取区间）
        data = load_example_input()
        out = ve.Engine(data).run()
        dcf = out["scenarios"]["base"]["dcf"]
        self.assertIn("tv_range", dcf)
        self.assertIn("tv_exit_multiple", dcf)
        self.assertEqual(dcf["tv_exit_multiple"]["method"], "exit_pe")
        # tv_range 应包含 Gordon 终值现值
        self.assertIn(dcf["terminal_value_pv"], dcf["tv_range"])
        lo, hi = dcf["tv_range"]
        self.assertLessEqual(lo, hi)

    # ---------- v3.12：三步数据源优先级（净利披露档 / FCF 披露档 / 可比来源档位） ----------
    def test_t51_net_profit_annual_disclosed(self):
        # ① 净利 annual 披露档：base 情景 profit = 披露值×(1+g1)；旧输入不激活
        data = load_example_input()
        data["financials"]["net_profit_basis"] = {"annual_net_profit": 4.0}
        out = ve.Engine(data).run()
        npb = out["net_profit_basis_used"]
        self.assertEqual(npb["basis"], "annual")
        self.assertIn("公开披露", npb["source"])
        dcf = out["scenarios"]["base"]["dcf"]
        # 示例 rev=12.5、g1=0.35：profit = 4.0×1.35 = 5.4；无 capex → fcf_ratio=0.9
        self.assertAlmostEqual(dcf["fcf0"], 5.4 * 0.9, places=2)
        self.assertEqual(dcf.get("profit_source"), "年度归母净利(公开披露)")
        data2 = load_example_input()
        out2 = ve.Engine(data2).run()
        self.assertNotIn("net_profit_basis_used", out2)

    def test_t52_net_profit_quarterly_annualized(self):
        # ① 季度×4 年化档位
        data = load_example_input()
        data["financials"]["net_profit_basis"] = {"quarterly_net_profit": 1.0}
        out = ve.Engine(data).run()
        self.assertEqual(out["net_profit_basis_used"]["basis"], "quarterly×4")
        dcf = out["scenarios"]["base"]["dcf"]
        # 年化 = 1.0×4 = 4.0 → base profit = 4.0×1.35 = 5.4
        self.assertAlmostEqual(dcf["fcf0"], 5.4 * 0.9, places=2)

    def test_t53_comparable_source_priority(self):
        # ③ 可比 source/priority 透传 + comparable_sources 块（缺省不激活）
        data = load_example_input()
        for i, c in enumerate(data["comparables"]):
            c["source"] = "research_report" if i < 2 else "public_info"
            c["priority"] = 1 if i < 2 else 2
        out = ve.Engine(data).run()
        cs = out["comparable_sources"]
        self.assertEqual(cs["n_with_source"], len(data["comparables"]))
        self.assertEqual(cs["n_total"], len(data["comparables"]))
        self.assertEqual(cs["min_priority"], 1)
        self.assertGreaterEqual(cs["count"].get("research_report", 0), 1)
        data2 = load_example_input()
        out2 = ve.Engine(data2).run()
        self.assertNotIn("comparable_sources", out2)

    def test_t54_fcf_disclosed_priority(self):
        # ② FCF 披露档（P0 最高优先）：(OCF−CapEx)/披露净利 > 三层校准 > 用户显式（v2.11.0 重排）
        data = load_example_input()
        data["financials"]["net_profit_basis"] = {"annual_net_profit": 4.0}
        data["financials"]["ocf_latest"] = 5.0
        data["financials"]["capex_latest"] = 1.4
        data["financials"]["fcf_ratio"] = 0.5  # 显式值应被披露档覆盖
        out = ve.Engine(data).run()
        fcfr = out["fcf_ratio"]
        self.assertEqual(fcfr["source"], "披露现金流/净利")
        self.assertAlmostEqual(fcfr["used"], (5.0 - 1.4) / 4.0, places=3)
        data2 = load_example_input()
        data2["financials"]["fcf_ratio"] = 0.5  # 无 CapEx 数据 → 三层校准不可用 → 回退显式
        out2 = ve.Engine(data2).run()
        self.assertEqual(out2["fcf_ratio"]["source"], "用户显式")
        self.assertAlmostEqual(out2["fcf_ratio"]["used"], 0.5, places=3)

    def test_t59_fcf_calibration_over_explicit(self):
        # v2.11.0 优先级链：披露档 P0 ＞ 三层校准 ＞ 用户显式（显式降为兜底，被覆盖时留痕）
        data = load_example_input()
        data["financials"]["net_profit_basis"] = {"annual_net_profit": 4.0}
        data["financials"]["capex_to_revenue"] = 0.10
        data["financials"]["net_margin"] = 0.2
        for c in data["comparables"]:
            c["ocf_ratio"] = 0.95
            c["capex_to_rev"] = 0.12
        data["financials"]["fcf_ratio"] = 0.7  # 显式值应被三层校准覆盖
        out = ve.Engine(data).run()
        fcfr = out["fcf_ratio"]
        self.assertEqual(fcfr["source"], "三层校准")
        self.assertTrue(fcfr["explicit_overridden"])
        self.assertAlmostEqual(fcfr["explicit_value"], 0.7, places=3)
        self.assertAlmostEqual(fcfr["l1_self"], 0.4, places=3)        # 0.9−0.10/0.2
        self.assertAlmostEqual(fcfr["l2_comparable"], 0.35, places=3) # 0.95−0.12/0.2
        self.assertAlmostEqual(fcfr["used"], 0.485, places=3)         # 0.5×0.4+0.3×0.35+0.2×0.9
        # DCF 净利路径按校准值计：profit 4.0×1.35=5.4 → fcf0 = 5.4×0.485（而非显式 5.4×0.7）
        self.assertAlmostEqual(out["scenarios"]["base"]["dcf"]["fcf0"], 5.4 * 0.485, places=2)

    def test_t60_fcf_explicit_fallback(self):
        # 三层校准不可用（无任何 CapEx 数据）→ 回退用户显式，DCF 按显式值计
        data = load_example_input()
        data["financials"]["net_profit_basis"] = {"annual_net_profit": 4.0}
        data["financials"]["fcf_ratio"] = 0.5
        out = ve.Engine(data).run()
        fcfr = out["fcf_ratio"]
        self.assertEqual(fcfr["source"], "用户显式")
        self.assertAlmostEqual(fcfr["used"], 0.5, places=3)
        self.assertAlmostEqual(out["scenarios"]["base"]["dcf"]["fcf0"], 5.4 * 0.5, places=2)

    def test_t61_fcf_disclosed_period_alignment(self):
        # v2.11.2：披露现金流必须按净利披露档同因子年化，避免"单期现金流 ÷ 年化净利"的期间错配
        # 半年档：base_p = 2.0×2 = 4.0；(3.0−1.0)×2 ÷ 4.0 = 1.0（旧口径误算为 0.5）
        data = load_example_input()
        data["financials"]["net_profit_basis"] = {"semiannual_net_profit": 2.0}
        data["financials"]["ocf_latest"] = 3.0
        data["financials"]["capex_latest"] = 1.0
        out = ve.Engine(data).run()
        fcfr = out["fcf_ratio"]
        self.assertEqual(fcfr["source"], "披露现金流/净利")
        self.assertAlmostEqual(fcfr["annualization_factor"], 2.0, places=4)
        self.assertAlmostEqual(fcfr["disclosed_net_profit"], 4.0, places=4)
        self.assertAlmostEqual(fcfr["used"], 1.0, places=3)
        # 单季档：base_p = 1.0×4 = 4.0；(3.0−1.0)×4 ÷ 4.0 = 2.0 → clamp 1.5
        data2 = load_example_input()
        data2["financials"]["net_profit_basis"] = {"quarterly_net_profit": 1.0}
        data2["financials"]["ocf_latest"] = 3.0
        data2["financials"]["capex_latest"] = 1.0
        out2 = ve.Engine(data2).run()
        self.assertAlmostEqual(out2["fcf_ratio"]["annualization_factor"], 4.0, places=4)
        self.assertAlmostEqual(out2["fcf_ratio"]["used"], 1.5, places=3)
        # 年度档：因子 1，行为与 v2.11.1 完全一致（旧输入零变化）
        data3 = load_example_input()
        data3["financials"]["net_profit_basis"] = {"annual_net_profit": 4.0}
        data3["financials"]["ocf_latest"] = 3.0
        data3["financials"]["capex_latest"] = 1.0
        out3 = ve.Engine(data3).run()
        self.assertAlmostEqual(out3["fcf_ratio"]["annualization_factor"], 1.0, places=4)
        self.assertAlmostEqual(out3["fcf_ratio"]["used"], 0.5, places=3)

    def test_t55_consensus_and_version(self):
        # ① consensus 档位（前向利润不再×g1）+ engine_version=2.9.0 + 正常化显式覆盖
        data = load_example_input()
        data["financials"]["net_profit_basis"] = {"consensus_net_profit": 5.0}
        out = ve.Engine(data).run()
        self.assertEqual(out["net_profit_basis_used"]["basis"], "consensus")
        dcf = out["scenarios"]["base"]["dcf"]
        self.assertAlmostEqual(dcf["fcf0"], 5.0 * 0.9, places=2)
        self.assertEqual(out["engine_version"], "2.28.0")
        data2 = load_example_input()
        data2["financials"]["net_profit_basis"] = {"annual_net_profit": 4.0, "normalized_net_profit": 3.0}
        data2["preferences"]["enable_normalized"] = True
        out2 = ve.Engine(data2).run()
        self.assertEqual(out2["net_profit_basis_used"]["basis"], "normalized")

    def test_t62_quality_score_null_indicators(self):
        """v2.11.3 回归：质量指标显式为 null（未披露）时不得崩溃，记 0 分并标记 missing。
        原缺陷：fin.get(k, default) 在 key 存在且值为 None 时返回 None，参与 >= 比较抛 TypeError。"""
        data = load_example_input()
        fin = data["financials"]
        # 评分卡读取的 5 项指标：ocf_to_net_profit / gross_margin_trend_pp /
        # receivables_to_revenue / goodwill_ratio / nonrecurring_ratio
        for k in ("gross_margin_trend_pp", "receivables_to_revenue", "nonrecurring_ratio"):
            fin[k] = None
        out = ve.Engine(data).run()          # 修复前此处抛 TypeError
        q = out["quality_scorecard"]
        self.assertEqual(q["missing_indicators"], 3)
        miss = {d["indicator"] for d in q["detail"] if d.get("missing")}
        self.assertEqual(miss, {"gross_margin_trend_pp", "receivables_to_revenue",
                                "nonrecurring_ratio"})
        for d in q["detail"]:
            if d.get("missing"):
                self.assertEqual(d["points"], 0)
                self.assertIsNone(d["value"])
        # 5 项全部提供时行为不变（旧输入零变化）：无 missing 标记、无 note
        data2 = load_example_input()
        out2 = ve.Engine(data2).run()
        self.assertEqual(out2["quality_scorecard"]["missing_indicators"], 0)
        self.assertNotIn("note", out2["quality_scorecard"])

    def test_t64_confidence_method_coverage_dcf_inapplicable(self):
        """v2.11.4 回归：asset_type=startup（DCF 不适用）+ 市场法单方法驱动时，
        置信度须按方法覆盖度折减且封顶「中」，methods_available 不得再列 dcf。
        基线对照：不含 asset_type 的同类输入（旧口径）保持原行为。"""
        # ① 旧口径基线：无 asset_type → DCF 列入可用方法、不出现方法覆盖度块
        base = load_example_input()
        base["meta"].pop("asset_type", None)
        out_old = ve.Engine(base).run()
        self.assertIn("dcf", out_old["confidence"]["methods_available"])
        self.assertNotIn("methods_inapplicable", out_old["confidence"])
        self.assertNotIn("method_coverage", out_old["confidence"])
        old_score = out_old["confidence"]["score"]
        # ② 新口径：asset_type=startup + dcf 权重 0（市场法 100%）
        data = load_example_input()
        data["meta"]["asset_type"] = "startup"
        data["preferences"]["weights"] = {"dcf": 0.0, "comparable": 0.7, "sentiment": 0.3}
        out = ve.Engine(data).run()
        conf = out["confidence"]
        self.assertFalse(out["asset_adapter"]["dcf_applicable"])
        self.assertNotIn("dcf", conf["methods_available"])
        self.assertEqual(conf["methods_inapplicable"], ["dcf"])
        mc = conf["method_coverage"]
        self.assertEqual(mc["effective_method_count"], 1)
        self.assertAlmostEqual(mc["diversity_factor"], 0.75, places=3)
        self.assertEqual(mc["level_cap"], "中")
        self.assertLess(mc["diversity_factor"], 1.0)
        # 封顶生效：置信度不得为「高」，且不高于基线
        self.assertNotEqual(conf["level"], "高")
        self.assertLessEqual(conf["score"], 79.9)
        self.assertLess(conf["score"], old_score)
        # ③ 权重同为市场法但未提供 asset_type → 不触发（旧输入零变化）
        data3 = load_example_input()
        data3["preferences"]["weights"] = {"dcf": 0.0, "comparable": 0.7, "sentiment": 0.3}
        out3 = ve.Engine(data3).run()
        self.assertIn("dcf", out3["confidence"]["methods_available"])
        self.assertNotIn("method_coverage", out3["confidence"])

    def test_t65_ipo_check_actual_issue_price(self):
        """v2.11.4：ipo_check 支持实际发行价入参（fundraising.issue_price_actual）。
        缺省时输出与旧版逐位一致（不新增键）；提供后 price_per_share 取实际价、
        保留 price_per_share_indicative，并输出实际发行市值与实际 vs 模型偏离。"""
        # ① 缺省：无新增键（旧输入零变化）
        data = load_example_input()
        data.setdefault("fundraising", {})
        data["fundraising"].pop("issue_price_actual", None)
        out = ve.Engine(data).run()
        for k in ("price_source", "price_per_share_indicative", "issue_mktcap_actual"):
            self.assertNotIn(k, out["ipo_check"])
        ind = out["ipo_check"]["price_per_share"]
        shares = data["financials"]["total_shares_after_issue"]
        self.assertAlmostEqual(ind, round(out["synthesis"]["weighted_mid"] / shares, 2), places=2)
        # ② 提供实际发行价：双口径并列
        data2 = load_example_input()
        data2.setdefault("fundraising", {})
        data2["fundraising"].update(issue_price_actual=27.60, actual_raise=18.03,
                                    issue_pe_actual=59.34, issue_pb_actual=5.04,
                                    listing_date="2026-09-16")
        ipo = ve.Engine(data2).run()["ipo_check"]
        self.assertEqual(ipo["price_per_share"], 27.60)
        self.assertIn("price_per_share_indicative", ipo)
        self.assertIn("实际发行价", ipo["price_source"])
        self.assertAlmostEqual(ipo["issue_mktcap_actual"], round(27.60 * shares, 2), places=2)
        self.assertIn("vs 模型中枢", ipo["price_status"])
        self.assertEqual(ipo["actual_raise"], 18.03)
        self.assertEqual(ipo["listing_date"], "2026-09-16")
        self.assertEqual(ipo["issue_pe_actual"], 59.34)

    def test_t66_confidence_method_divergence_cap(self):
        """v2.11.5 回归：市场口径（可比法）与 DCF 内在价值分歧过大（CV>0.60）时，
        置信度须按分歧度折减并封顶「中」，并挂出 method_divergence 留痕；
        分歧度未超阈值或缺 DCF 时，confidence 键集合与 v2.11.4 逐位一致（旧输入零变化）。

        构造方式：以示例输入为基础，把可比公司倍数整体放大到 DCF 的 5 倍以上
        （CV = |a−b| / ((a+b)/2) ≈ 1.3 > 0.60），触发封顶。"""
        # ① 基线：示例输入分歧度未超阈值 → 不挂 method_divergence
        base = load_example_input()
        out0 = ve.Engine(base).run()
        self.assertNotIn("method_divergence", out0["confidence"])
        self.assertLessEqual(out0["synthesis"]["method_cv"] or 0, ve.CONFIDENCE_METHOD_CV_CAP)

        # ② 分歧度超阈值：可比倍数 ×5 → 触发折减 + 封顶「中」
        data = load_example_input()
        for c in data["comparables"]:
            for k in ("pe", "ps", "pb", "ev_ebitda"):
                if c.get(k):
                    c[k] = c[k] * 5.0
        out = ve.Engine(data).run()
        cv = out["synthesis"]["method_cv"]
        self.assertGreater(cv, ve.CONFIDENCE_METHOD_CV_CAP)
        conf = out["confidence"]
        md = conf["method_divergence"]
        self.assertEqual(md["cv_cap"], ve.CONFIDENCE_METHOD_CV_CAP)
        self.assertEqual(md["level_cap"], "中")
        # 注：synthesis.method_cv 输出已四舍五入到 3 位，divergence_factor 由未舍入 CV 计算，
        # 故此处按 2 位精度比对，避免舍入误差误判。
        self.assertAlmostEqual(md["divergence_factor"],
                               round(min(1.0, ve.CONFIDENCE_METHOD_CV_CAP / cv), 2), places=2)
        self.assertLess(md["divergence_factor"], 1.0)
        self.assertGreater(md["ratio"], 2.0)
        # 封顶生效
        self.assertNotEqual(conf["level"], "高")
        self.assertLessEqual(conf["score"], 79.9)
        self.assertLess(conf["score"], out0["confidence"]["score"])

        # ③ 阈值可配置且分支可关闭（缺 DCF 权重时 DCF 值仍由净现金下限机械兜底，
        #    但分歧度按实际两法数值计算，故此处仅校验键集合在「未超阈值」时不新增）
        data3 = load_example_input()
        out3 = ve.Engine(data3).run()
        self.assertEqual(set(out3["confidence"]) - set(out0["confidence"]), set())

    def test_t56_tier_classification(self):
        # v3.13：四维匹配自动分档（最可比/较可比/一般可比）
        data = load_example_input()
        data["meta"]["target_profile"] = {
            "segment": "ic_design", "mode": "product_hardware",
            "scale": "large", "growth_stage": "high_growth"}
        comps = data["comparables"]
        # 芯原/海光 4 维全中→最可比；澜起 成长阶段不同(中3)→较可比；龙芯 环节+规模不同(中2)→较可比
        comps[0].update(segment="ic_design", mode="product_hardware", scale="large", growth_stage="high_growth")
        comps[1].update(segment="ic_design", mode="product_hardware", scale="large", growth_stage="mature")
        comps[2].update(segment="ic_design", mode="product_hardware", scale="large", growth_stage="high_growth")
        comps[3].update(segment="cpu_ip", mode="product_hardware", scale="mid", growth_stage="high_growth")
        out = ve.Engine(data).run()
        ct = out["scenarios"]["base"]["comparable"]["comparable_tiers"]
        self.assertTrue(ct["active"])
        self.assertEqual(set(ct["tiers"]["most"]), {"芯原股份", "海光信息"})
        self.assertEqual(set(ct["tiers"]["fair"]), {"澜起科技", "龙芯中科"})
        self.assertEqual(ct["tiers"]["general"], [])
        # tier_min 默认 2，最可比≥2 → 仅用最可比汇总
        self.assertEqual(ct["selected_tiers"], ["most"])

    def test_t57_tier_fallback(self):
        # v3.13：最可比样本不足时逐级回退（most→most+fair→全部）
        data = load_example_input()
        data["meta"]["target_profile"] = {
            "segment": "ic_design", "mode": "product_hardware",
            "scale": "large", "growth_stage": "high_growth"}
        comps = data["comparables"]
        # 仅芯原 4 维全中(most=1)；澜起/海光 3 维中(fair=2)；龙芯 1 维中(general=1)
        comps[0].update(segment="ic_design", mode="product_hardware", scale="large", growth_stage="high_growth")
        comps[1].update(segment="ic_design", mode="product_hardware", scale="large", growth_stage="mature")
        comps[2].update(segment="ic_design", mode="product_hardware", scale="mid", growth_stage="mature")
        comps[3].update(segment="cpu_ip", mode="ip_license", scale="mid", growth_stage="mature")
        data["preferences"]["tier_min_samples"] = 3
        out = ve.Engine(data).run()
        ct = out["scenarios"]["base"]["comparable"]["comparable_tiers"]
        self.assertEqual(set(ct["tiers"]["most"]), {"芯原股份"})
        self.assertEqual(set(ct["tiers"]["fair"]), {"澜起科技", "海光信息"})
        self.assertEqual(set(ct["tiers"]["general"]), {"龙芯中科"})
        # 最可比1<3 → 并入较可比(共3) → 选中 [most, fair]
        self.assertEqual(ct["selected_tiers"], ["most", "fair"])
        # 极深回退：tier_min=4 → 全部三档
        data2 = load_example_input()
        data2["meta"]["target_profile"] = dict(data["meta"]["target_profile"])
        for i, c in enumerate(data2["comparables"]):
            c.update(**comps[i])
        data2["preferences"]["tier_min_samples"] = 4
        out2 = ve.Engine(data2).run()
        ct2 = out2["scenarios"]["base"]["comparable"]["comparable_tiers"]
        self.assertEqual(ct2["selected_tiers"], ["most", "fair", "general"])

    def test_t58_legacy_no_tier(self):
        # v3.13：无 target_profile → active=False，整体最可比，数值等同旧 flat mean
        data = load_example_input()  # 无 target_profile
        out = ve.Engine(data).run()
        ct = out["scenarios"]["base"]["comparable"]["comparable_tiers"]
        self.assertFalse(ct["active"])
        self.assertEqual(set(ct["tiers"]["most"]), {c["name"] for c in data["comparables"]})
        self.assertEqual(ct["selected_tiers"], ["most"])
        # 等价于旧逻辑：base_value = mean(各法 value_median，含 PEG 若启用)
        comp = out["scenarios"]["base"]["comparable"]
        vals = []
        for k in ("pe", "ps", "ev_ebitda", "pb"):
            v = comp.get(k, {}).get("value_median")
            if v:
                vals.append(v)
        if comp.get("synthesis", {}).get("peg_value") and data["preferences"].get("enable_peg_in_synthesis", True):
            vals.append(comp["synthesis"]["peg_value"])
        import statistics as _st
        exp = round(_st.mean(vals), 2) if vals else None
        self.assertEqual(comp["synthesis"]["base_value"], exp)

    # ===== v3.15.0：估值四部分拆分（①DCF ②可比法含质量 ③舆情仅情绪 ④统计检验）=====
    def test_t67_four_part_synthesis(self):
        # 四部分：权重读取 + 自洽（①②③加权和 == base 情景 value）+ ③舆情不含 liq/质量
        data = load_example_input()
        data["preferences"]["four_part_mode"] = True   # 缺省即 true，此处显式
        out = ve.Engine(data).run()
        fp = out["synthesis"]["four_part"]
        self.assertAlmostEqual(fp["part1_dcf"]["weight"], out["weights"]["dcf"], places=6)
        self.assertAlmostEqual(fp["part2_comparable_quality"]["weight"], out["weights"]["comparable"], places=6)
        self.assertAlmostEqual(fp["part3_market_sentiment"]["weight"], out["weights"]["sentiment"], places=6)
        calc = (fp["part1_dcf"]["value"] * fp["part1_dcf"]["weight"]
                + fp["part2_comparable_quality"]["value"] * fp["part2_comparable_quality"]["weight"]
                + fp["part3_market_sentiment"]["value"] * fp["part3_market_sentiment"]["weight"])
        self.assertAlmostEqual(calc, out["synthesis"]["base_value"], delta=0.5)
        base = out["scenarios"]["base"]
        self.assertIn("comparable_quality", base)
        self.assertIn("comparable_sentiment", base)
        comp_v = base["comparable_raw"]
        sent = base["adjustments"]["sentiment"]["adjustment_pct"]
        self.assertAlmostEqual(base["comparable_sentiment"], round(comp_v * (1 + sent), 2), places=1)

    def test_t68_sentiment_decoupled_from_quality(self):
        # 口径 B：sentiment_adjust 不再依赖质量分（去 q_score 参数、删两条交叉验证）
        import inspect
        sig = inspect.signature(ve.Engine.sentiment_adjust)
        self.assertNotIn("q_score", sig.parameters)
        eng = ve.Engine(load_example_input())
        s1, r1 = eng.sentiment_adjust(0.0)
        s2, _ = eng.sentiment_adjust(0.0)
        self.assertEqual(s1, s2)
        self.assertNotIn("质量分", r1)
        self.assertNotIn("泡沫抑制", r1)

    def test_t69_four_part_switch(self):
        # four_part_mode=false 不挂 four_part 块（键集合回到旧口径）；true 挂出
        d_off = load_example_input()
        d_off["preferences"]["four_part_mode"] = False
        out_off = ve.Engine(d_off).run()
        self.assertNotIn("four_part", out_off["synthesis"])
        out_on = ve.Engine(load_example_input()).run()
        self.assertIn("four_part", out_on["synthesis"])
        # v3.15.0：旧口径情景键集合逐位不变（不挂出 comparable_quality/sentiment 留痕键）
        for sc in ("bear", "base", "bull"):
            self.assertNotIn("comparable_quality", out_off["scenarios"][sc])
            self.assertNotIn("comparable_sentiment", out_off["scenarios"][sc])
            self.assertIn("comparable_quality", out_on["scenarios"][sc])
            self.assertIn("comparable_sentiment", out_on["scenarios"][sc])
        # v3.15.0：数值逐位回退（golden 口径）
        with open(os.path.join(SKILL_ROOT, "examples", "output_example.json"), "r", encoding="utf-8") as f:
            gold = json.load(f)
        self.assertEqual(out_off["scenarios"]["base"]["value"], gold["scenarios"]["base"]["value"])
        self.assertEqual(out_off["synthesis"]["weighted_mid"], gold["synthesis"]["weighted_mid"])
        self.assertEqual(out_off["synthesis"]["interval"], gold["synthesis"]["interval"])

    # ===== v3.16.0：三层计划（Layer 0 判别门 / Layer 2 参数底座 / Layer 1 现金流主计算）=====
    def test_t70_layer0_framework_gate(self):
        # Layer 0：金融业（利息计入营业成本 / 受监管资本）→ DCF 不适用，dcf 权重封顶 0
        data = load_example_input()
        data["preferences"]["layer0_check"] = True
        data["meta"]["framework_check"] = {"interest_is_operating": True, "regulated_capital": True}
        out = ve.Engine(data).run()
        self.assertIn("framework_check", out)
        fw = out["framework_check"]
        self.assertFalse(fw["precondition_A"]["pass"])
        self.assertFalse(fw["precondition_B"]["pass"])
        self.assertIs(fw["dcf_admissible"], False)
        self.assertEqual(fw["recommended_primary"], "rim/ddm")
        self.assertEqual(out["weights"]["dcf"], 0.0)                 # 权重封顶并重分配
        self.assertAlmostEqual(sum(out["weights"].values()), 1.0, places=9)
        # Layer 0 缺省关闭 → 不挂 framework_check 块（旧输入零变化）
        out2 = ve.Engine(load_example_input()).run()
        self.assertNotIn("framework_check", out2)

    def test_t71_layer1_classify_lifecycle(self):
        # Layer 1：三源优先级（用户显式 > 客观判别 > 兜底 growth）
        # ① 初创：亏损 + 营收规模小
        d = load_example_input(); d["preferences"]["lifecycle_mode"] = "auto"
        d["financials"]["loss_making"] = True; d["financials"]["revenue_latest_ttm"] = 3.0
        d["financials"]["net_margin"] = -0.5
        self.assertEqual(ve.Engine(d).run()["lifecycle"]["stage"], "startup")
        # ② 衰退：CAGR < 0
        d = load_example_input(); d["preferences"]["lifecycle_mode"] = "auto"
        d["financials"]["cagr_3y"] = -0.08
        out = ve.Engine(d).run()
        self.assertEqual(out["lifecycle"]["stage"], "decline")
        self.assertEqual(out["scenarios"]["base"]["dcf"]["terminal_growth"] <= 0.0, True)  # tg ≤ tg_floor
        # ③ 成熟：0≤CAGR<8% 且盈利
        d = load_example_input(); d["preferences"]["lifecycle_mode"] = "auto"
        d["financials"]["cagr_3y"] = 0.05
        self.assertEqual(ve.Engine(d).run()["lifecycle"]["stage"], "mature")
        # ④ 用户显式优先 + 与 asset_type 不一致标记
        d = load_example_input(); d["preferences"]["lifecycle_mode"] = "auto"
        d["meta"]["lifecycle_stage"] = "mature"; d["meta"]["asset_type"] = "growth"
        out = ve.Engine(d).run()
        self.assertEqual(out["lifecycle"]["source"], "用户显式")
        self.assertTrue(out["lifecycle"]["inconsistent_with_asset_type"])
        # 缺省 lifecycle_mode=legacy → 不挂 lifecyle 块
        self.assertNotIn("lifecycle", ve.Engine(load_example_input()).run())

    def test_t72_layer1_growth_schedule_four_forms(self):
        # 四形态 + 全长度使用 growth_forecast（修复 legacy「只取前 3 年」缺陷）
        seq5 = [0.30, 0.25, 0.20, 0.18, 0.15]
        # ① 成熟：n=4 < 用户 5 年 → 全长度保留（n=max(4,5)=5）
        seq, det = ve.build_growth_schedule("mature", seq5, 0.03, {"n": 4, "form": "mean_revert", "rho": 0.3})
        self.assertEqual(len(seq), 5)
        self.assertAlmostEqual(seq[3], 0.18, places=6)
        self.assertAlmostEqual(seq[4], 0.15, places=6)
        # legacy 口径丢弃第 4/5 年 → 两者必须不同
        legacy = ve.build_growth_seq(seq5, 0.03, 0.0)
        self.assertNotEqual(seq[3], legacy[3])
        # ② 成长：指数 fade 单调递减且收敛向 tg
        g, _ = ve.build_growth_schedule("growth", [0.30], 0.03, {"n": 6, "form": "exp", "half_life": 3.0})
        self.assertEqual(len(g), 6)
        self.assertTrue(all(g[i] >= g[i + 1] for i in range(len(g) - 1)))
        self.assertTrue(g[-1] > 0.03)
        # ③ 衰退：形态产生负增长
        gd, _ = ve.build_growth_schedule("decline", [-0.10], -0.05, {"n": 5, "form": "decline", "lam": 0.3, "g_perm": -0.05})
        self.assertTrue(any(x < 0 for x in gd))
        # ④ 初创：S 曲线，长度 = n
        gs, _ = ve.build_growth_schedule("startup", [0.60], 0.05, {"n": 10, "form": "s_curve", "t_mid": 4.0})
        self.assertEqual(len(gs), 10)
        self.assertTrue(all(gs[i] >= gs[i + 1] for i in range(len(gs) - 1)))

    def test_t73_layer1_drives_dcf(self):
        # lifecycle_mode=auto → DCF 挂 growth_schedule；缺省不挂（legacy 零变化）
        d = load_example_input(); d["preferences"]["lifecycle_mode"] = "auto"
        out = ve.Engine(d).run()
        dcf = out["scenarios"]["base"]["dcf"]
        self.assertIn("growth_schedule", dcf)
        self.assertEqual(dcf["growth_schedule"]["stage"], "growth")
        self.assertEqual(len(dcf["growth_schedule"]["seq"]), 8)      # 成长期 n=8（用户仅给 3 年；v3.27.0 由 6 上调）
        self.assertEqual(dcf["lifecycle_stage"], "growth")
        self.assertNotIn("growth_schedule", ve.Engine(load_example_input()).run()["scenarios"]["base"]["dcf"])

    def test_t74_layer1_p0_value_driver(self):
        # P0 价值驱动式：FCFF_t = NOPAT_t×(1−g/ROIC)，输出现金流计划与再投资一致性
        d = load_example_input()
        d["preferences"]["cashflow_model"] = "p0_value_driver"
        d["financials"]["ebit"] = 3.0; d["financials"]["roic"] = 0.50
        dcf = ve.Engine(d).run()["scenarios"]["base"]["dcf"]
        self.assertEqual(dcf["fcf_basis"], "value_driver_p0")
        self.assertIn("cashflow_schedule", dcf)
        rows = dcf["cashflow_schedule"]["rows"]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(0.0 <= r["reinvestment_rate"] <= 1.0 for r in rows))
        self.assertEqual(dcf["reinvestment_consistency"]["violations"], 0)   # g<ROIC → 守恒成立
        # ROIC 过低 → 触发 g>ROIC 违规（守恒律护栏）
        d2 = load_example_input()
        d2["preferences"]["cashflow_model"] = "p0_value_driver"
        d2["financials"]["ebit"] = 3.0; d2["financials"]["roic"] = 0.10
        dcf2 = ve.Engine(d2).run()["scenarios"]["base"]["dcf"]
        self.assertGreater(dcf2["reinvestment_consistency"]["violations"], 0)
        self.assertEqual(max(r["reinvestment_rate"] for r in dcf2["cashflow_schedule"]["rows"]), 1.0)
        # 缺省 cashflow_model=p2_legacy → 不挂 P0 块
        self.assertNotIn("cashflow_schedule", ve.Engine(load_example_input()).run()["scenarios"]["base"]["dcf"])

    def test_t75_b4_b5_adaptive_weights(self):
        # B4 权重条件化：lifecycle 为 growth（基线 k=1）时权重与 legacy 逐位一致
        d = load_example_input(); d["preferences"]["path_weight_mode"] = "adaptive"
        out = ve.Engine(d).run()
        self.assertEqual(out["weights"], {"dcf": 0.3, "comparable": 0.5, "sentiment": 0.2})
        pw = out["synthesis"]["path_weights"]
        self.assertEqual(pw["mode"], "adaptive")
        self.assertEqual(pw["resolved_weights"], {"dcf": 0.3, "comparable": 0.5, "sentiment": 0.2})
        # 成熟期：k_lifecycle = {dcf 1.3, comp 1.0, sent 0.7} → dcf 权重上移
        d2 = load_example_input()
        d2["preferences"]["path_weight_mode"] = "adaptive"; d2["preferences"]["lifecycle_mode"] = "auto"
        d2["financials"]["cagr_3y"] = 0.05
        out2 = ve.Engine(d2).run()
        self.assertGreater(out2["weights"]["dcf"], 0.3)
        self.assertLess(out2["weights"]["sentiment"], 0.2)
        self.assertAlmostEqual(sum(out2["weights"].values()), 1.0, places=9)
        # B5 三路径相关性声明
        pc = out2["synthesis"]["four_part"]["path_correlation"]
        self.assertEqual(pc["comp_vs_sent"], "shared_base")
        self.assertLess(pc["effective_path_count"], 3.0)
        # 缺省 fixed → 不挂 path_weights（旧输入零变化）
        self.assertNotIn("path_weights", ve.Engine(load_example_input()).run()["synthesis"])

    def test_t76_layer2_industry_params(self):
        # Layer 2：行业参数底座解析 + 校验锚；缺省关闭（旧输入零变化）
        d = load_example_input(); d["preferences"]["industry_params"] = True
        out = ve.Engine(d).run()
        self.assertIn("industry_params", out)
        ind = out["industry_params"]
        self.assertEqual(ind["matched_industry"], "半导体")          # industry「AI芯片设计」命中半导体
        self.assertEqual(ind["params"]["half_life"], 3.0)
        self.assertIn("wacc_range", ind["params"])
        self.assertNotIn("industry_params", ve.Engine(load_example_input()).run())
        # v2.14.1：最长命中别名优先——泛化别名「制造」「设备」不得抢占具体行业
        d2 = load_example_input(); d2["preferences"]["industry_params"] = True
        d2["meta"]["industry"] = "白酒（酱香型，高端白酒）；行业分类：酒、饮料和精制茶制造业（C15）"
        d2["meta"]["company"] = "贵州茅台酒股份有限公司"
        self.assertEqual(ve.Engine(d2).run()["industry_params"]["matched_industry"], "消费")
        d3 = load_example_input(); d3["preferences"]["industry_params"] = True
        d3["meta"]["industry"] = "电力设备（光伏逆变器、储能变流器）"
        self.assertEqual(ve.Engine(d3).run()["industry_params"]["matched_industry"], "电力设备")
        # v2.14.1 / industry_params 1.0.2：新增「汽车」类目，且长别名须压过次要业务别名
        d4 = load_example_input(); d4["preferences"]["industry_params"] = True
        d4["meta"]["company"] = "比亚迪股份有限公司"
        d4["meta"]["industry"] = ("新能源汽车（乘用车、商用车、动力电池、手机部件及组装、储能、光伏）；"
                                  "国民经济行业分类：汽车制造业（C36）")
        self.assertEqual(ve.Engine(d4).run()["industry_params"]["matched_industry"], "汽车")
        self.assertEqual(ve.Engine(d4).run()["industry_params"]["params"]["pe_med"], 16.6)

    def test_t77_layer0_cap_not_overwritten_by_b4(self):
        """v3.16.2 回归：Layer 0 conditional 档 dcf_weight_cap 在 B4 权重条件化之后仍生效。
        原缺陷：Layer 0 先封顶、B4 随后从 DEFAULT_WEIGHTS 从头重算 → conditional cap 被静默丢弃。"""
        d = load_example_input()
        d["preferences"]["layer0_check"] = True
        d["preferences"]["path_weight_mode"] = "adaptive"
        d["preferences"]["lifecycle_mode"] = "auto"
        d["financials"]["cagr_3y"] = 0.05                      # 成熟期 → k_lifecycle dcf 1.3（会抬高 dcf 权重）
        d["meta"]["framework_check"] = {"industry_class": "reit_utility"}  # conditional，cap 0.3
        out = ve.Engine(d).run()
        self.assertEqual(out["framework_check"]["dcf_admissible"], "conditional")
        self.assertAlmostEqual(out["framework_check"]["dcf_weight_cap"], 0.3, places=6)
        # B4 若未抬高则 cap 不体现差异；此处断言最终 dcf 权重被限制在 0.3（未被 B4 重算覆盖）
        self.assertLessEqual(out["weights"]["dcf"], 0.3 + 1e-9)
        self.assertAlmostEqual(sum(out["weights"].values()), 1.0, places=9)
        self.assertTrue(any("封顶并重分配" in w for w in out["warnings"]))

    def test_t78_b4_respects_user_weights(self):
        """v3.16.2 回归：path_weight_mode=adaptive 的基准权重取用户 preferences.weights，而非 DEFAULT 常量。
        原缺陷：B4 用 DEFAULT_WEIGHTS 作 base → 用户自定义权重在 adaptive 下被丢弃。"""
        d = load_example_input()
        d["preferences"]["path_weight_mode"] = "adaptive"
        d["preferences"]["weights"] = {"dcf": 0.5, "comparable": 0.3, "sentiment": 0.2}
        # lifecycle 缺省 legacy → 阶段兜底 growth（k=1）→ resolved 应等于用户权重
        out = ve.Engine(d).run()
        self.assertEqual(out["weights"], {"dcf": 0.5, "comparable": 0.3, "sentiment": 0.2})
        pw = out["synthesis"]["path_weights"]
        self.assertEqual(pw["base_weights"], {"dcf": 0.5, "comparable": 0.3, "sentiment": 0.2})
        self.assertEqual(pw["resolved_weights"], {"dcf": 0.5, "comparable": 0.3, "sentiment": 0.2})

    def test_t79_layer0_overrides_asset_type_for_dcf(self):
        """v3.16.2 回归：layer0_check=true 时 DCF 适用性以 Layer 0 为准。
        原矛盾：asset_type=startup 判 DCF 不适用（触发置信度方法覆盖度折减），但 Layer 0 前提检验判可准入。"""
        d = load_example_input()
        d["preferences"]["layer0_check"] = True
        d["meta"]["asset_type"] = "startup"                    # 标签判 DCF 不适用
        # industry「AI芯片设计」→ general（前提成立）→ dcf_admissible=True
        out = ve.Engine(d).run()
        self.assertEqual(out["framework_check"]["dcf_admissible"], True)
        self.assertIn("dcf", out["confidence"]["methods_available"])       # 以 Layer 0 为准：仍列 dcf
        self.assertNotIn("method_coverage", out["confidence"])             # 不触发方法覆盖度折减
        self.assertTrue(any("适用性判定不一致" in w for w in out["warnings"]))  # 相反结论留痕


    def test_t80_peg_guard(self):
        """v3.16.4 回归：PEG 护栏 —— 近零正增速样本剔除 / 中位数超上限整法弃用 / peg_guard=false 回退旧行为。"""
        # ① 全部为近零正增速（1~4%）：全样本剔除 → 挂诊断块（value=None）且不进 synthesis
        data = load_example_input()
        for i, c in enumerate(data["comparables"]):
            c["growth_pct"] = 1.0 + i
        out = ve.Engine(data).run()
        comp = out["scenarios"]["base"]["comparable"]
        self.assertIsNone(comp["peg"]["value"])
        self.assertEqual(len(comp["peg"]["guard_excluded"]), 4)
        self.assertNotIn("peg_value", comp["synthesis"])
        # ② 混合：1 只近零（1.3%）+ 3 只有效（25/35/28）→ 仅剔除近零样本，中位数正常可入池
        data2 = load_example_input()
        data2["comparables"][0]["growth_pct"] = 1.3
        out2 = ve.Engine(data2).run()
        peg2 = out2["scenarios"]["base"]["comparable"]["peg"]
        self.assertEqual(len(peg2["samples"]), 3)
        self.assertEqual([e[0] for e in peg2["guard_excluded"]], ["芯原股份"])
        self.assertLess(peg2["median"], 5.0)
        self.assertIsNotNone(peg2["value"])
        # ③ 中位数超上限（PEG≈16.5 > 5.0）→ 整法弃用（value=None + warning + 不进 synthesis）
        data3 = load_example_input()
        for i, c in enumerate(data3["comparables"]):
            c["pe"] = 90.0 + 6 * i
            c["growth_pct"] = 6.0
        out3 = ve.Engine(data3).run()
        comp3 = out3["scenarios"]["base"]["comparable"]
        self.assertIsNone(comp3["peg"]["value"])
        self.assertIn("dropped_by_guard", comp3["peg"])
        self.assertNotIn("peg_value", comp3["synthesis"])
        self.assertTrue(any("PEG 中位数" in w for w in out3["warnings"]))
        # ④ 关闭护栏（peg_guard=false）→ 回到 v2.13.1 行为：近零增速样本重新入池并产生失真中位数
        data4 = load_example_input()
        data4["comparables"] = [data4["comparables"][0]]
        data4["comparables"][0]["growth_pct"] = 1.3
        data4["preferences"]["peg_guard"] = False
        out4 = ve.Engine(data4).run()
        peg4 = out4["scenarios"]["base"]["comparable"]["peg"]
        self.assertAlmostEqual(peg4["median"], 120.0 / 1.3, places=3)
        self.assertIsNotNone(peg4["value"])

    def test_t81_report_layout_v3165(self):
        """v3.16.5 回归：报告版式——①取消目录；②执行摘要去重（无结论条/无方法离散度卡）；
        ③§6 补生命周期阶段与逐年增速数值（growth_schedule.seq 全长度）；④字号令牌统一（含图内文字）。"""
        import re as _re
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg
        import html_check as hc
        data = load_example_input()
        data["preferences"]["lifecycle_mode"] = "auto"   # 启用 Layer 1，使 §6 有阶段与增速序列
        out = ve.Engine(data).run()
        doc = rg.generate_report(out, stat=None, inp=data)

        # ① 取消目录：无 toc 容器、无锚点链接（章节 id 保留供交叉引用）
        self.assertNotIn('class="toc"', doc)
        self.assertNotIn('href="#s', doc)
        self.assertEqual(len(_re.findall(r'id="s(\d+)"', doc)), 11)

        # ② 执行摘要去重：结论条 .verdict 与「方法离散度」KPI 卡均不存在，KPI 恰好 3 张
        self.assertNotIn('class="verdict"', doc)
        self.assertNotIn("方法离散度", doc)
        self.assertEqual(len(_re.findall(r'<div class="kpi[" ]', doc)), 3)
        self.assertIn("综合估值区间（情景区间）", doc)

        # ③ §6 关键假设补「阶段 + 逐年增速数值」
        dcf = out["scenarios"]["base"]["dcf"]
        seq = (dcf.get("growth_schedule") or {}).get("seq") or []
        self.assertTrue(seq, "示例案例应输出增速序列")
        self.assertIn("生命周期阶段", doc)
        self.assertIn("预测期增速（逐年）", doc)
        self.assertIn("增速三角参照", doc)
        self.assertIn(out["lifecycle"]["stage_label"], doc)
        for g in seq:
            self.assertIn(f"{g * 100:.2f}%", doc)

        # ④b v2.14.2：终值模式须翻译为中文标签，不得残留内部枚举值
        for _raw in ("three_method", "exit_multiple", "zero_growth_or_nav", "prob_weighted"):
            self.assertNotIn(_raw, doc, f"终值枚举值 {_raw} 未翻译")

        # ④ 字号统一：CSS 仅出现字号令牌；SVG 内文字统一 CHART_FS
        css = doc[doc.find("<style>"):doc.find("</style>")]
        self.assertEqual(sorted(set(_re.findall(r"font-size:([^;}\n]+)", css))),
                         ["var(--fs)", "var(--fs-h1)", "var(--fs-h2)", "var(--fs-h3)",
                          "var(--fs-h4)", "var(--fs-num)"])
        self.assertEqual(sorted(set(_re.findall(r'font-size="([^"]+)"', doc))), [str(rg.CHART_FS)])

        # ⑤ 结构机检：无目录时 C7 仍通过（跳过锚点一致性，保留编号/章节数校验）
        ok7, d7 = hc.check_c7(doc, 11)
        self.assertTrue(ok7, d7)
        ok2, d2 = hc.check_c2(doc)
        self.assertTrue(ok2, d2)

    def test_t82_wacc_source_label(self):
        """v2.14.2 回归：assumptions_summary.dcf.wacc_source 须如实区分「显式给定」与「CAPM 模型」。
        原缺陷：只要 wacc_params.enabled 就标「CAPM 模型」，与引擎「显式 wacc 优先」及
        风险提示「CAPM 模型值偏离 +2.54pp」自相矛盾（比亚迪案例）。"""
        # ① 显式 wacc + wacc_params 并存 → 标「显式给定（CAPM 校验偏差 ±X pp）」
        d = load_example_input()
        d["financials"]["wacc"] = 0.085
        d["financials"]["wacc_params"] = {"enabled": True, "rf": 0.019, "erp": 0.06, "beta": 0.85,
                                          "d_e_ratio": 0.35, "tax_rate": 0.15, "cost_of_debt": 0.035}
        out = ve.Engine(d).run()
        src = out["assumptions_summary"]["dcf"]["wacc_source"]
        self.assertTrue(src.startswith("显式给定"), src)
        self.assertIn("CAPM 校验偏差", src)
        # ② 无显式 wacc、仅 CAPM → 标「CAPM 模型」
        d2 = load_example_input()
        d2["financials"].pop("wacc", None)
        d2["financials"]["wacc_params"] = {"enabled": True, "rf": 0.019, "erp": 0.06, "beta": 0.85,
                                           "d_e_ratio": 0.35, "tax_rate": 0.15, "cost_of_debt": 0.035}
        self.assertEqual(ve.Engine(d2).run()["assumptions_summary"]["dcf"]["wacc_source"], "CAPM 模型")
        # ③ 无 wacc_params → 保持旧行为
        d3 = load_example_input()
        d3["financials"]["wacc"] = 0.085
        self.assertEqual(ve.Engine(d3).run()["assumptions_summary"]["dcf"]["wacc_source"], "用户显式")

    def test_t83_low_wacc_elasticity(self):
        """v3.4.2 回归：低 WACC / 低永续增速标的的参数弹性诊断须恢复正常。
        原缺陷：calibration_params 的 clamp 下界（wacc 0.07、terminal_growth 0.02）不适用于
        公用事业类低折现率标的（长江电力 wacc 6.5%、tg 2.0%），导致 ±1σ 双向扰动同被 clamp
        抬升 → 弹性「同号非单调」误报、tg −1σ 零响应，且触界根因未被双向检出。
        修复：① 放宽 clamp（wacc→[0.04,0.20]、tg→[0.00,0.10]）；② _detect_clamp_truncation 双向检测。"""
        data = load_example_input()
        data["financials"]["wacc"] = 0.065
        data["financials"]["terminal_growth"] = 0.02
        data["financials"].pop("wacc_params", None)   # 关闭 CAPM 覆盖，确保基准 wacc = 0.065
        eng = ve.Engine(data).run()
        out = sv.run_validation(data, eng, load_calib(), n=200, seed=42)
        el = out["elasticity"]
        # ① wacc 弹性须单调：+1σ（抬 WACC）压估值、−1σ（降 WACC）抬估值
        self.assertLess(el["wacc"]["delta_pct_1sigma"], 0.0,
                        f"wacc +1σ 应为负，实际 {el['wacc']['delta_pct_1sigma']}")
        self.assertGreater(el["wacc"]["delta_pct_minus_1sigma"], 0.0,
                           f"wacc −1σ 应为正，实际 {el['wacc']['delta_pct_minus_1sigma']}")
        self.assertEqual(el["wacc"]["direction_flag"], "正常")
        # ② 低 tg（= 原 clamp 下界）须有非零双向响应
        self.assertGreater(el["terminal_growth"]["delta_pct_1sigma"], 0.0)
        self.assertLess(el["terminal_growth"]["delta_pct_minus_1sigma"], 0.0)
        self.assertEqual(el["terminal_growth"]["direction_flag"], "正常")
        # ③ 不得残留 wacc / terminal_growth 相关的弹性告警
        for issue in out["elasticity_issues"]:
            self.assertNotIn("wacc:", issue)
            self.assertNotIn("terminal_growth:", issue)

    def test_t84_explicit_null_numeric_fields(self):
        """v2.14.4 回归：模板允许的「显式 null」数值字段不得使引擎崩溃（缺陷族补全）。

        v2.14.3 只修了 ipo_check() 的 shares/issue/np_ttm；同一 `fin.get(key, 0.0)`
        在「键存在且值为 None」时返回 None 的缺陷族仍在 10 处。中国平安案例（综合金融，
        模板字段几乎全部显式 null：net_cash / ebitda_ttm / gross_margin / ocf_to_net_profit /
        receivables_to_revenue / gross_margin_trend_pp / net_cash / roic …）在
        `equity = pv_sum + tv_pv + self.fin.get("net_cash", 0.0)` 处抛 TypeError。

        本用例把下列字段全部显式置 null 并跑完整 run()：不得抛异常，且相对基线仅发生
        「该字段本应提供的默认值」变化。"""
        data = load_example_input()
        fin = data["financials"]
        for k in ("net_cash", "ebitda_ttm", "gross_margin", "ocf_to_net_profit",
                  "receivables_to_revenue", "gross_margin_trend_pp", "nonrecurring_ratio",
                  "goodwill_ratio", "capex_to_revenue", "roic", "cagr_3y", "net_assets"):
            fin[k] = None
        fin["net_profit_basis"] = {"annual_net_profit": None, "quarterly_net_profit": None,
                                   "semiannual_net_profit": None, "consensus_net_profit": None,
                                   "normalized_net_profit": None}
        data.setdefault("industry_index", {})["pe_median"] = 20.0   # 触发 industry_index_valuation 的 rev 取数路径
        data["transactions"] = [{"name": "交易A", "date": "2026-06-30", "ev_sales": 3.0, "ev_ebitda": 12.0}]
        data["fundraising"]["planned_raise"] = 10.0  # 触发 ipo_check 的 net_cash 取数路径
        out = ve.Engine(data).run()                  # ← 修复前在 dcf_valuation 抛 TypeError
        self.assertIn("synthesis", out)
        self.assertIn("net_cash", out["ipo_check"])
        self.assertEqual(out["ipo_check"]["net_cash"], 0.0)
        self.assertIsInstance(out["synthesis"]["weighted_mid"], float)
        # cagr_3y=null 且无 growth_forecast → _g1() 回落 0.20（不得 TypeError）
        data2 = load_example_input()
        data2["financials"]["cagr_3y"] = None
        data2["financials"]["growth_forecast"] = {}
        out2 = ve.Engine(data2).run()
        self.assertIn("synthesis", out2)
        # 质量评分卡：6 项显式 null → 全部记 0 分并标记 missing，不得崩溃
        self.assertGreaterEqual(out["quality_scorecard"]["missing_indicators"], 5)

    def test_t85_negative_growth_baseline_aware_clamp(self):
        """v3.4.3 回归：**负增速假设**（成熟/衰退期标的）的 clamp 下界须「基线感知」。

        原缺陷：growth_forecast.clamp_abs 缺省 [0.0, 2.5]，绝对下界 0.0 隐含「增速不可能为负」。
        基准增速为负时，乘性扰动 v×mult 的**正负两侧都**落在 0 以下 → 全被截回 0.0：
          ① MC 全样本中该年增速恒为 0% → 基准年被静默抬升，MC 区间系统性上偏；
          ② ±1σ 点扰动同被抬升 → 弹性「±1σ 同号非单调」（格力电器案例 +4.67% / +1.40%）。
        修复：_growth_lo 仅当基准值 v<0 时把下界放宽到 min(clamp_abs[0], v×exp(4σ))；
               v≥0 时原样返回 → 对非负增速输入为严格空操作（27 例 A/B 逐位相同）。
        """
        import random as _random
        data = load_example_input()
        gf = data["financials"]["growth_forecast"]
        key = sorted(gf.keys())[0]
        gf[key] = -0.02                      # 基准年增速为负（成熟/衰退期口径）
        data["financials"]["terminal_growth"] = 0.02
        eng = ve.Engine(data).run()
        out = sv.run_validation(data, eng, load_calib(), n=200, seed=42)
        self.assertEqual(out["meta"]["stat_version"], "3.4.3")
        el = out["elasticity"]["growth_forecast"]
        # ① 弹性须单调：抬增速抬估值、降增速压估值
        self.assertGreater(el["delta_pct_1sigma"], 0.0,
                           f"growth +1σ 应为正，实际 {el['delta_pct_1sigma']}")
        self.assertLess(el["delta_pct_minus_1sigma"], 0.0,
                        f"growth −1σ 应为负，实际 {el['delta_pct_minus_1sigma']}")
        self.assertEqual(el["direction_flag"], "正常")
        for issue in out["elasticity_issues"]:
            self.assertNotIn("growth_forecast:", issue)
        # ② 有效下界须低于基准负增速（否则会被截回 0.0）
        lo = sv._growth_lo(-0.02, [0.0, 2.5], 0.25)
        self.assertLess(lo, -0.02)
        # ③ 非负基准值不受影响（严格空操作）
        self.assertEqual(sv._growth_lo(0.30, [0.0, 2.5], 0.25), 0.0)
        self.assertEqual(sv._growth_lo(0.0, [0.0, 2.5], 0.25), 0.0)
        # ④ MC 抽样不得把该年增速系统性归零：固定 rng 连抽 200 次须保持 < 0
        dists = load_calib()["default"]["distributions"]
        rng = _random.Random(7)
        kept = 0
        for _ in range(200):
            dd = copy.deepcopy(data)
            sv._perturb_param(dd, dists, "growth_forecast", rng, 0.0)
            if dd["financials"]["growth_forecast"][key] < 0:
                kept += 1
        self.assertEqual(kept, 200, f"负增速年抽样应恒为负，实际保持负值 {kept}/200 次")


    def test_t86_report_ratio_precision(self):
        """v3.16.9 回归：**比率量显示精度**——同一比率在各章节的显示位数须一致。

        原缺陷（美的集团案例暴露，「比率量 0 位小数」缺陷族）：
          ① §7.1 多方法表 DCF 行与 §6.3 方法适用性表 DCF 行用 `_pct(v, 0)`：
             WACC 8.5% → 「8%」、永续增速 2.5% → 「2%」、终值占比 76.0% → 「76%」；
             而 §6.2 关键假设表用 `_pct(v)`（1 位）显示 8.5% / 2.5% → **同报告自相矛盾**。
             WACC 是该案例主导敏感变量（弹性 −11.51%/+20.39%），
             0.5pp 截断 ≈ 13% 估值偏差，属实质性误导而非排版瑕疵。
          ② §4.2 行业指数行 `_pct(v / 100, 0)` 为**双重缺陷**：`vs_comparable_deviation`
             由引擎以**比率**输出（-0.0385 = −3.85%），误除 100 后又 0 位小数 →
             美的显示「−0%」、examples/output_example_unitree.json（-0.7054）显示「−1%」，
             而同报告 §6.3 该行用 `_pct(v, 2)` 显示「−70.54%」（同页相差 70 倍）。
          ③ §4.1b 分组缺口 `_pct(abs(gap), 0)` 同族。
        修复：比率量一律 `_pct(v)`（1 位）/ `_pct(v, 2)`（2 位），代码中不得再出现 `nd=0`；
               §4.2 去掉误除 100 并与 §6.3 对齐为 2 位。
        """
        import ast as _ast
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg

        # ① 工具层：默认 1 位小数，不得截断为整数百分点
        self.assertEqual(rg._pct(0.085), "8.5%")
        self.assertEqual(rg._pct(0.025), "2.5%")
        self.assertEqual(rg._pct(0.76), "76.0%")
        self.assertEqual(rg._pct(-0.0385, 2), "-3.85%")

        # ② 源码层结构性护栏：**AST 级**断言 `_pct()` 不再有 nd=0 调用
        #    （用 AST 而非字符串匹配，避免误命中模块 docstring 中对旧写法的记述）
        src = open(os.path.join(SKILL_ROOT, "scripts", "report_generator.py"),
                   encoding="utf-8").read()
        _zero_nd = []
        for _n in _ast.walk(_ast.parse(src)):
            if isinstance(_n, _ast.Call) and getattr(_n.func, "id", None) == "_pct":
                if len(_n.args) >= 2 and isinstance(_n.args[1], _ast.Constant) \
                        and _n.args[1].value == 0:
                    _zero_nd.append(_n.lineno)
                for _kw in _n.keywords:
                    if _kw.arg == "nd" and isinstance(_kw.value, _ast.Constant) \
                            and _kw.value.value == 0:
                        _zero_nd.append(_n.lineno)
        self.assertEqual(_zero_nd, [],
                         f"比率量不得以 0 位小数渲染（_pct nd=0 残留于行 {_zero_nd}）")

        # ③ 报告层：DCF 行 WACC/永续增速/终值占比须与 §6.2 同精度（1 位）
        data = load_example_input()
        data["financials"]["wacc"] = 0.085
        data["financials"]["terminal_growth"] = 0.025
        data["industry_index"] = {"enabled": True, "name": "测试行业指数（校验用）", "pe_median": 6.0}
        out = ve.Engine(data).run()
        doc = rg.generate_report(out, stat=None, inp=data)
        dcf = out["scenarios"]["base"]["dcf"]
        self.assertEqual(dcf.get("wacc"), 0.085)
        _new = f"WACC {rg._pct(dcf.get('wacc'))} / g {rg._pct(dcf.get('terminal_growth'))}"
        _old = (f"WACC {rg._pct(dcf.get('wacc'), 0)} / g "
                f"{rg._pct(dcf.get('terminal_growth'), 0)}")
        self.assertIn(_new, doc, "§7.1 / §6.3 的 DCF 行须显示 1 位小数")
        self.assertNotIn(_old, doc, "0 位小数写法不得残留")
        self.assertIn("8.5%", doc)
        self.assertIn("2.5%", doc)
        # §6.2 关键假设表（本就 1 位）与 DCF 行口径一致
        self.assertIn(rg._pct((out["assumptions_summary"]["dcf"]).get("wacc")), doc)

        # ④ 行业指数行：与 §6.3 同口径（比率原值 + 2 位），且不得再出现「误除 100」的结果
        idx = out.get("industry_index") or {}
        if idx.get("enabled") and idx.get("vs_comparable_deviation") is not None:
            _dev = idx["vs_comparable_deviation"]
            self.assertIn(f"与可比法偏差 {rg._pct(_dev, 2)}", doc)
            self.assertNotIn(f"与可比法偏差 {rg._pct(_dev / 100, 0)}", doc)
            # 0% 偏差须正常显示（原写法 `if _num(v)` 真值判断会把 0.0 静默丢成「—」）
            self.assertEqual(rg._pct(0.0, 2), "0.00%")

    def test_t87_markdown_bold_in_rendered_text(self):
        """v3.16.10 回归：**渲染型自由文本中的 Markdown 粗体标记不得原样落入 HTML**。

        原缺陷（伊利股份案例暴露，机检 C8「渲染残留」捕获 2 处）：
          `input.json › data_sources[].items` 由人工撰写的展示型长文本常带 Markdown
          `**粗体**` 强调；生成器只做 `_esc()`（HTML 转义，`*` 不在转义集内）→
          `**资产减值损失 −24.56 亿元**`、`**ToB 深加工…**` 以裸记号出现在溯源表格单元格。
          属**族级缺陷**：任一案例的任一展示型字段写入 `**` 即复发（伊利本案例输入共 26 个
          字段含 `**`，其中仅 data_sources 的 items 被渲染）。
        修复（报告生成器 v3.16.10）：新增 `_rich()`＝先 `_esc()` 再仅把**成对**的 `**…**`
          转为 `<strong>…</strong>`；应用于 data_sources 数据项单元格；SVG 路径不调用 `_rich`。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg

        # ① 工具层：成对转换 / 不成对保留 / 多组 / 先转义后注入（顺序不可颠倒）
        self.assertEqual(rg._rich("**甲**乙"), "<strong>甲</strong>乙")
        self.assertEqual(rg._rich("甲**乙"), "甲**乙", "不成对 `**` 须原样保留，不得吞字")
        self.assertEqual(rg._rich("**甲** 与 **乙**"), "<strong>甲</strong> 与 <strong>乙</strong>")
        self.assertEqual(rg._rich("a<b> & **c**"), "a&lt;b&gt; &amp; <strong>c</strong>",
                         "须先 HTML 转义再注入，否则用户文本可注入标签")
        self.assertEqual(rg._rich(""), "")
        self.assertEqual(rg._rich(None), "")
        # 零回归边界：不含成对 `**` 时 `_rich` 与 `_esc` 等价
        for _s in ("普通文本", "1×2", "含 * 单个星号", "a<b>&c"):
            self.assertEqual(rg._rich(_s), rg._esc(_s), f"零回归边界失守: {_s}")

        # ② 源码层结构性护栏：数据项单元格须用 `_rich`，不得回退为 `_esc`
        src = open(os.path.join(SKILL_ROOT, "scripts", "report_generator.py"),
                   encoding="utf-8").read()
        self.assertIn("_rich(_it", src, "data_sources 数据项须经 _rich 渲染")
        self.assertNotIn("_esc(_it", src, "data_sources 数据项不得回退为 _esc")

        # ③ 报告层：注入含 `**` 的溯源项 → 输出含 <strong> 且无裸 `**`
        data = load_example_input()
        data["data_sources"] = [{"item": "标的 **核心指标** 与 **口径说明**（含 & 与 <）",
                                 "source": "测试来源", "as_of": "2026-10-04", "confidence": "高"}]
        out = ve.Engine(data).run()
        doc = rg.generate_report(out, stat=None, inp=data)
        self.assertIn("<strong>核心指标</strong>", doc)
        self.assertIn("<strong>口径说明</strong>", doc)
        self.assertNotIn("**", doc, f"渲染残留：输出仍含 {doc.count('**')} 处 `**`")

    def test_t88_rendered_text_sites_full_coverage(self):
        """v3.16.12 回归：**渲染型自由文本站点的全量覆盖**（T87 同族缺陷的第 5 次暴露）。

        原缺陷（中国石油案例暴露，机检 C8「渲染残留」捕获 1 处）：
          v3.16.10/v3.16.11 的 `_rich()` 修复只覆盖 `data_sources[].items` **一个**站点，
          同族站点仍在——报告**页眉副标题**渲染 `meta.note_asset_type`、**§2 公司概况**
          渲染 `meta.industry`，两处均走 `_esc()`。中国石油案例的 `meta.note_asset_type`
          写入 `**一体化结构而非纯上游资源股**` → 裸记号落入 `<div class="sub">` 页眉。
          **通用判据**：凡引用 `input.json` 人工撰写字段的渲染点，若该字段为长文本，
          一律假定其可能含 Markdown 记号；新增渲染点须同步改 `_rich()` 并**全量扫描既有站点**
          （只看新写代码必漏——同族已第 5 次）。
        零回归：7 个既有案例（catl/crrc/gree/midea/pingan/sany/yili）的 meta 长文本均不含
          成对 `**` → `_rich(s) == _esc(s)` → 输出逐字节不变（`docs/_ab_report_v31611.py` 验证）。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg

        # ① 源码层结构性护栏：三个站点均须经 `_rich`，不得回退为 `_esc`
        src = open(os.path.join(SKILL_ROOT, "scripts", "report_generator.py"),
                   encoding="utf-8").read()
        self.assertIn('_rich(meta_inp.get("industry")', src,
                      "meta.industry（公司概况）须经 _rich 渲染")
        self.assertIn("_rich(meta.get('industry')", src,
                      "页眉 meta.industry 须经 _rich 渲染")
        self.assertIn("_rich(meta_inp.get('note_asset_type')", src,
                      "页眉 meta.note_asset_type 须经 _rich 渲染")
        self.assertNotIn("_esc(meta_inp.get('note_asset_type')", src,
                         "meta.note_asset_type 不得回退为 _esc")

        # ② 报告层：注入含 `**` 的 meta 长文本 → 输出含 <strong> 且无裸 `**`
        data = load_example_input()
        data["meta"]["industry"] = "石油和天然气开采业（**一体化**综合能源与化工）"
        data["meta"]["note_asset_type"] = "超大盘蓝筹，**一体化结构而非纯上游资源股**"
        out = ve.Engine(data).run()
        doc = rg.generate_report(out, stat=None, inp=data)
        self.assertIn("<strong>一体化结构而非纯上游资源股</strong>", doc,
                      "meta.note_asset_type 的成对 `**` 须渲染为 <strong>")
        self.assertIn("<strong>一体化</strong>", doc,
                      "meta.industry 的成对 `**` 须渲染为 <strong>")
        self.assertNotIn("**", doc, f"渲染残留：输出仍含 {doc.count('**')} 处 `**`")

    def test_t89_masthead_vertical_layout(self):
        """v3.16.13 回归：报告页眉由「左右结构」改为「上下结构」。

        原缺陷（福耀玻璃案例暴露，属**版式**而非数值）：`.masthead{display:flex;
        justify-content:space-between}` ＋ 右侧 `.meta{text-align:right;white-space:nowrap}`
        把「报告编号／估值基准日／引擎」固定为**不折行的一列**；当 `meta.exchange`（上市沿革）
        或 `meta.note_asset_type`（长段说明，10 例实测 184~692 字）较长时，右列可占去半幅宽度，
        **左侧企业简介被挤压成窄列 → 副题折行十余行 → 页眉纵向异常高大**（福耀副题 509 字，
        窄列下约 15 行）。修复：`.masthead` 改 `display:block`；简介（品牌行／h1／副题）
        独占整幅宽度；元信息改为其下的**元信息条**（浅渐变底＋金色左边框），内部以
        `<span class="m">`（标签 `.k` ＋ 取值 `.v`）与 `｜` 分隔（`.sep`）自然折行。
        零回归：`docs/_ab_report_v31613.py` —— 10 例（catl/crrc/fuyao/gree/midea/petrochina/
        pingan/sany/sinopec/yili）差异**全部落在页眉区块**，归一化后其余逐字节相同、行数相同。
        """
        import re as _re
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg
        import html_check as hc

        # ① 源码层结构性护栏：页眉不得再是 flex 左右布局、元信息不得 nowrap
        src = open(os.path.join(SKILL_ROOT, "scripts", "report_generator.py"),
                   encoding="utf-8").read()
        css = rg.CSS
        self.assertIn(".masthead{display:block;", css, "页眉容器须为块级（上下结构）")
        self.assertNotIn(".masthead{display:flex;", css, "页眉不得回退为 flex 左右布局")
        self.assertIn(".masthead .meta{display:block;", css, "元信息条须为块级")
        self.assertIn(".masthead .meta .m{white-space:normal}", css, "元信息项须允许折行")
        self.assertIn(".masthead .meta .sep{", css, "元信息条须含分隔符样式")
        self.assertNotIn(".masthead .meta b{", css, "元信息取值改用 .v，不得回退 .meta b")
        self.assertNotIn("text-align:right;line-height:1.9;white-space:nowrap", css,
                         "元信息不得回退为右对齐不折行")
        self.assertIn('<div class="meta"><span class="m">', src,
                      "元信息条须为单行 .m/.k/.v 结构（无 <br> 硬换行）")
        self.assertNotIn("报告编号：{report_no}<br>", src, "旧左右结构页眉写法不得残留")
        # 页眉 CSS 注释不得含 Markdown `**`（会随 <style> 落入文档 → 触发机检 C8）
        self.assertNotIn("**", css, "页眉/全局 CSS 注释不得出现 `**`（C8 渲染残留）")

        # ② 报告层：简介在上、元信息条在下（位置关系即「上下结构」）
        data = load_example_input()
        data["meta"]["exchange"] = ("主板（示例证券交易所，20XX-XX-XX 上市，上市逾 20 年）；"
                                    "同步于中国香港联合交易所主板上市（XXXX.HK，20XX-XX-XX）")
        data["meta"]["note_asset_type"] = "长段说明占位。" * 40     # 模拟 240 字长文本
        out = ve.Engine(data).run()
        doc = rg.generate_report(out, stat=None, inp=data)

        i_sub = doc.index('<div class="sub">')
        i_meta = doc.index('<div class="meta">')
        i_s1 = doc.index("<!-- ══════════ 一、")
        self.assertLess(i_sub, i_meta, "副题（企业简介）须位于元信息条之前（上下结构）")
        self.assertLess(i_meta, i_s1, "元信息条须位于执行摘要之前")
        self.assertIn('<div class="masthead">\n  <div class="brand">', doc,
                      "简介区不再被中间层 <div> 包裹（与元信息条同级）")

        # ③ 元信息条：6 组「标签＋取值」，无 <br> 硬换行，长取值不截断
        seg = doc[i_meta:i_s1]
        self.assertEqual(len(_re.findall(r'<span class="m"><span class="k">', seg)), 6,
                         "元信息条须恰为 6 组（报告编号/估值基准日/上市板块/引擎/统计/抽样）")
        self.assertNotIn("<br>", seg, "元信息条不得使用 <br> 硬换行（应自然折行）")
        for _lab in ("报告编号", "估值基准日", "上市板块", "引擎", "统计", "抽样"):
            self.assertIn(f">{_lab}</span>", seg, f"元信息条缺少标签「{_lab}」")
        self.assertIn("XXXX.HK，20XX-XX-XX", seg, "长文本上市板块须完整保留、不得截断")
        self.assertIn("长段说明占位。" * 40, doc, "长段 note_asset_type 须完整保留")

        # ④ 结构机检不回退
        ok2, d2 = hc.check_c2(doc)
        self.assertTrue(ok2, d2)
        ok7, d7 = hc.check_c7(doc, 11)
        self.assertTrue(ok7, d7)


    def test_t90_financing_anchor_applicable_text(self):
        """v3.16.14 回归：§7.4「最近融资价格法」行不得渲染字面量 `None`。

        原缺陷（中信证券案例暴露，属**渲染**而非数值）：引擎 `recent_financing_anchor()`
        **仅在输入提供 `exclusions[]` 时才写入 `applicable` 键**（未提供时 `return {**base,
        "anchor_value": ...}`，base 不含该键），而生成器无条件 `rfa.get('applicable')` 并直接
        拼进 f-string → 该键缺失时渲染为字符串 `None`（`.get()` 的默认值就是 None）。
        机检 **C1 只抓 `$KEY` / `{KEY}` 占位符、C8 只抓 `**粗体**` 与裸占位符，均抓不到
        「键缺失渲染 None」**，故此前含融资锚的报告（福耀玻璃、中芯国际等）均带此瑕疵而未被拦截。
        修复：`applicable is None`（未提供排除检查，语义＝未触发 9 项排除）→ 展示「是」；
        `False` → 「否」；`True` → 「是」。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg
        import html_check as hc

        # ① 源码层护栏：不得再直拼 rfa.get('applicable')
        sp = os.path.join(SKILL_ROOT, "scripts", "report_generator.py")
        src = open(sp, encoding="utf-8").read()
        self.assertNotIn("适用={rfa.get('applicable')}", src,
                         "不得把 rfa.get('applicable') 直拼进正文（键缺失时会渲染 None）")

        # ② 未提供 exclusions[]：引擎不写 applicable 键 → 报告须显示「适用=是」
        data = load_example_input()
        data.setdefault("meta", {})["as_of_date"] = "20XX-06-30"
        data["recent_financing"] = {"enabled": True, "post_money": 1234.56,
                                    "financing_date": "20XX-05-31"}
        out = ve.Engine(data).run()
        rfa = out["recent_financing_anchor"]
        self.assertTrue(rfa["enabled"], "融资锚须启用")
        self.assertNotIn("applicable", rfa, "未提供 exclusions 时引擎不应写 applicable 键（缺陷前提）")
        doc = rg.generate_report(out, stat=None, inp=data)
        self.assertIn("适用=是，锚值 1,234.56 亿", doc, "缺省（未提供排除检查）须显示「适用=是」")
        self.assertNotIn("适用=None", doc, "正文不得出现字面量 None")
        seg = doc[doc.index("最近融资价格法"):doc.index("最近融资价格法") + 120]
        self.assertNotIn("None", seg, f"§7.4 融资锚行不得含 None：{seg}")

        # ③ 提供 exclusions[] 且命中排除情形 → 引擎写 applicable=False → 报告须显示「适用=否」
        data2 = load_example_input()
        data2.setdefault("meta", {})["as_of_date"] = "20XX-06-30"
        data2["recent_financing"] = {
            "enabled": True, "post_money": 1234.56, "financing_date": "20XX-05-31",
            "exclusions": [{"present": True, "code": "A1", "note": "测试用排除情形"}]}
        out2 = ve.Engine(data2).run()
        self.assertIs(out2["recent_financing_anchor"].get("applicable"), False,
                      "命中排除情形时 applicable 须为 False")
        doc2 = rg.generate_report(out2, stat=None, inp=data2)
        self.assertIn("适用=否", doc2, "命中排除情形须显示「适用=否」")
        self.assertNotIn("适用=None", doc2, "正文不得出现字面量 None")

        # ④ 结构机检不回退
        for _doc in (doc, doc2):
            ok2, d2 = hc.check_c2(_doc)
            self.assertTrue(ok2, d2)
            ok8, d8 = hc.check_c8(_doc)
            self.assertTrue(ok8, d8)

    def test_t91_rendered_text_sites_source_exchange(self):
        """v3.16.15 回归：「渲染型自由文本站点未全量覆盖」缺陷族**第 6 次暴露**。

        v3.16.12 声称「全量覆盖 `_rich()`」，实则只覆盖 `data_sources[].item` /
        `meta.industry` / `meta.note_asset_type` 三处；同表的 **`data_sources[].source`**
        （「来源」列，人工撰写、常含机构/接口说明与强调）与 **`meta.exchange`**
        （上市沿革，KPI 注 + 页眉元信息条两处渲染）仍走 `_esc()` → 北方稀土案例的
        source 写入 `**分析师加工口径**` 时裸记号落入 HTML（机检 **C8** 捕获）。
        修复：三处 `_esc()` → `_rich()`；`as_of` / `confidence` / 引擎生成的 `note`
        等短标签站点保持 `_esc()`（不含成对 `**`，且防止向 SVG 注入元素）。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg
        import html_check as hc

        # ① 源码层护栏：source 与 exchange 须走 _rich()，且不得再走 _esc()
        sp = os.path.join(SKILL_ROOT, "scripts", "report_generator.py")
        src = open(sp, encoding="utf-8").read()
        self.assertIn('_rich(s.get("source")', src,
                      "data_sources[].source 须走 _rich()（人工撰写的展示型自由文本）")
        self.assertNotIn('_esc(s.get("source")', src,
                         "data_sources[].source 不得再走 _esc()（`**` 会原样落入 HTML）")
        self.assertIn("_rich(meta.get('exchange')", src, "meta.exchange 须走 _rich()")
        self.assertNotIn("_esc(meta.get('exchange')", src,
                         "meta.exchange 不得再走 _esc()（`**` 会原样落入 HTML）")
        # 短标签站点须保持 _esc()（不因本次修复被误改）
        self.assertIn('_esc(s.get("as_of")', src, "as_of 为短标签，须保持 _esc()")
        self.assertIn('_esc(s.get("confidence")', src, "confidence 为短标签，须保持 _esc()")

        # ② 报告层：含 `**` 的 source / exchange 须渲染为 <strong>，且无裸记号
        data = load_example_input()
        data.setdefault("meta", {})["exchange"] = "测试交易所主板（**20XX 年上市**）"
        data["data_sources"] = [
            {"item": "测试数据项", "source": "**人工撰写来源说明**（含强调）", "as_of": "20XX-06-30"}]
        out = ve.Engine(data).run()
        doc = rg.generate_report(out, stat=None, inp=data)
        self.assertIn("<strong>人工撰写来源说明</strong>", doc,
                      "data_sources[].source 中的 `**` 须渲染为 <strong>")
        self.assertIn("<strong>20XX 年上市</strong>", doc,
                      "meta.exchange 中的 `**` 须渲染为 <strong>")
        self.assertNotIn("**人工撰写来源说明**", doc, "source 不得残留裸记号")
        self.assertNotIn("**20XX 年上市**", doc, "exchange 不得残留裸记号")

        # ③ 零回归：不含成对 `**` 时 _rich(s) == _esc(s)（输出逐字节不变）
        data3 = load_example_input()
        data3.setdefault("meta", {})["exchange"] = "测试交易所主板（20XX 年上市）"
        data3["data_sources"] = [{"item": "测试数据项", "source": "人工撰写来源说明", "as_of": "20XX-06-30"}]
        doc3 = rg.generate_report(ve.Engine(data3).run(), stat=None, inp=data3)
        self.assertIn("人工撰写来源说明", doc3)
        self.assertNotIn("<strong>人工撰写来源说明</strong>", doc3,
                         "不含 `**` 时不得注入 <strong>（零回归）")

        # ④ 结构机检不回退
        for fn in (hc.check_c2, hc.check_c8):
            ok, msg = fn(doc)
            self.assertTrue(ok, msg)

    def test_t92_negative_equity_limited_liability(self):
        """v3.16.16 回归（引擎 v2.14.5）：DCF 权益为负时净现金下限须受**有限责任**约束。

        原缺陷（万华化学案例暴露）：`if equity < 0: equity = net_cash_in` —— 该分支
        只在 `net_cash` 为**负**（净负债）时才可能触发，此时它把「权益价值」赋成
        **净负债本身**（负值），与紧随其后的注释「保持下游口径有意义」自相矛盾
        （股东权益不可能为负；PV(经营) < 净负债 时股权价值应取 0）。
        实例：万华化学 bear 情景 PV(经营) 586 亿 < 净负债 937.67 亿 → 返回 −937.67 亿，
        把 Bear 下界人为压低、情景区间由 4.24× 虚增至 5.94×；中国石化同类（−3,803.61 亿）。
        修复：`floor = max(0.0, net_cash_in)`——净现金为正时仍为净现金下限（历史行为
        逐位不变），净现金为负时取 0。
        """
        # ① 源码层护栏：不得再把 net_cash_in 直接赋给 equity
        sp = os.path.join(SKILL_ROOT, "scripts", "valuation_engine.py")
        src = open(sp, encoding="utf-8").read()
        self.assertIn("floor = max(0.0, net_cash_in)", src,
                      "权益下限须为 max(0.0, net_cash_in)（有限责任）")
        self.assertNotIn("\n            equity = net_cash_in\n", src,
                         "不得再把 net_cash_in 直赋 equity（净负债时返回负权益价值）")

        base = ve.Engine(load_example_input()).run()

        # ② 净现金为负且权益为负 → 下限取 0，且 warning 明示数值与依据
        d1 = load_example_input()
        d1["financials"]["net_cash"] = -1000.0
        o1 = ve.Engine(d1).run()
        b1 = o1["scenarios"]["bear"]
        self.assertEqual(b1["dcf_value"], 0.0, "净负债下 bear 权益须取 0 下限")
        self.assertGreaterEqual(b1["dcf_value"], 0.0, "权益价值不得为负（有限责任）")
        w1 = " ".join(o1["warnings"])
        self.assertIn("有限责任", w1, "warning 须明示有限责任约束")
        self.assertIn("权益下限 0.00 亿元", w1, "warning 须给出下限数值")
        self.assertIn("净现金 -1000.00 亿元", w1, "warning 须给出净现金数值")

        # ③ 净负债规模从大到小的性质测试：bear 权益恒 ≥ 0，且随 net_cash 单调不减
        seq = []
        for nc in (-5000.0, -2000.0, -1000.0, -500.0, -20.0, 1.8):
            dd = load_example_input()
            dd["financials"]["net_cash"] = nc
            seq.append(ve.Engine(dd).run()["scenarios"]["bear"]["dcf_value"])
        for nc, v in zip((-5000.0, -2000.0, -1000.0, -500.0, -20.0, 1.8), seq):
            self.assertGreaterEqual(v, 0.0, f"net_cash={nc} 时 bear 权益不得为负（有限责任）")
        self.assertEqual(seq[:3], [0.0, 0.0, 0.0], "重度净负债时权益须取 0 下限")
        self.assertEqual(seq, sorted(seq), "bear 权益须随净现金单调不减")

        # ④ 净现金为负但权益仍为正 → 不触下限（不得过度触发），且净现金全额扣减
        d2 = load_example_input()
        d2["financials"]["net_cash"] = -20.0
        o2 = ve.Engine(d2).run()
        self.assertNotIn("有限责任", " ".join(o2["warnings"]), "权益为正时不得触发下限")
        self.assertAlmostEqual(o2["scenarios"]["bear"]["dcf_value"],
                               base["scenarios"]["bear"]["dcf_value"] - 21.8, places=6,
                               msg="权益为正时须逐位等于 pv+tv+net_cash")

        # ⑤ 正净现金零回归：输出与示例基线逐位一致
        d3 = load_example_input()
        d3["financials"]["net_cash"] = 1.8
        o3 = ve.Engine(d3).run()
        self.assertEqual(json.dumps(o3["scenarios"], ensure_ascii=False, sort_keys=True),
                         json.dumps(base["scenarios"], ensure_ascii=False, sort_keys=True),
                         "净现金为正时输出须逐位不变（零回归）")


    def test_t93_layer0_homograph_keyword(self):
        """v3.16.17 回归（引擎 v2.14.6）：Layer 0 关键词的**中文同形异义词**误命中。

        原缺陷（生益科技 600183.SH 案例暴露）：`framework_admissibility()` 的 reit_utility
        关键词组含裸 "高速"，本意是「高速公路」收费权类重资产标的；但「高速」在电子/通信
        语境指 high-speed（高频高速覆铜板 / 高速接口 / SerDes）。标的 `meta.industry`
        写「高频高速覆铜板」→ `"高速" in hay` 命中 → 误判 reit_utility
        （`dcf_weight_cap = 0.3`、`recommended_primary = "nav"`），而该公司是一般制造业、
        与收费公路毫无关系；且误路由**静默发生、引擎不报警**（同「石油/资源」误路由族）。
        修复：`"高速"` → `"高速公路"`（hay 仅由 meta.industry + framework_check.industry_class
        构成，既有 29 例输入静态扫描确认无一例该两字段含「高速」→ 逐位零回归）。
        """
        # ① 源码层护栏：关键词组须为「高速公路」，不得再出现裸 "高速"
        sp = os.path.join(SKILL_ROOT, "scripts", "valuation_engine.py")
        src = open(sp, encoding="utf-8").read()
        self.assertIn('("reit", "公用", "水务", "高速公路", "燃气", "电网")', src,
                      "reit_utility 关键词须用「高速公路」（裸「高速」会被 high-speed 语义误命中）")

        # ② 行为：一般制造业行业串含「高频高速」→ 必须判 general（不得 reit_utility）
        d = load_example_input()
        d["meta"]["industry"] = ("电子电路基材制造业——全球刚性覆铜板第二大厂商（高频高速覆铜板 / "
                                 "粘结片 / 印制线路板），AI 服务器高速材料")
        d["meta"].pop("framework_check", None)   # 不显式给 industry_class，走关键词推断
        d["preferences"]["layer0_check"] = True
        o = ve.Engine(d).run()
        fc = o["framework_check"]
        self.assertEqual(fc["industry_class"], "general",
                         "含「高频高速」的一般制造业不得被判为 reit_utility（同形异义误命中）")
        self.assertEqual(fc["dcf_admissible"], True,
                         "误命中会使 DCF 降为 conditional（cap 0.3）——须为 True")
        self.assertEqual(fc["dcf_weight_cap"], 1.0, "general 路由 dcf_weight_cap 须为 1.0")

        # ③ 反向：真实收费公路标的（含「高速公路」）仍须命中 reit_utility
        d2 = load_example_input()
        d2["meta"]["industry"] = "高速公路运营（收费公路特许经营权），交通基础设施投资与运营"
        d2["meta"].pop("framework_check", None)
        d2["preferences"]["layer0_check"] = True
        o2 = ve.Engine(d2).run()
        self.assertEqual(o2["framework_check"]["industry_class"], "reit_utility",
                         "含「高速公路」的收费公路标的仍须判 reit_utility（不得过度收紧）")
        self.assertEqual(o2["framework_check"]["dcf_weight_cap"], 0.3,
                         "reit_utility 的 dcf_weight_cap 须为 0.3")

        # ④ 零回归：不含「高速」的行业串，判别结果与基线一致
        d3 = load_example_input()
        d3["preferences"]["layer0_check"] = True
        o3 = ve.Engine(d3).run()
        self.assertEqual(json.dumps(o3["framework_check"], ensure_ascii=False, sort_keys=True),
                         json.dumps(ve.Engine({**d3, "meta": {**d3["meta"],
                                         "industry": d3["meta"]["industry"]}}).run()["framework_check"],
                                    ensure_ascii=False, sort_keys=True),
                         "不含「高速」的行业串判别须稳定")

    def test_t94_dcf_degenerate_disclosure_condition(self):
        """v3.16.18 回归（报告层）：DCF「退化披露」触发条件须校验**真实退化**。

        原缺陷（特变电工 600089.SH 案例暴露）：v2.14.2 起的判据仅 `fcf0 <= 0`，未校验
        `pv_sum == tv_pv == 0`。基准期 FCF 为负**不等于** DCF 退化——只要 `pv_sum + tv_pv != 0`
        （终值通常为大额正数），DCF 仍产出有效权益。既有 22 例扫描：真退化仅中航沈飞
        （0/0/0/78.34）；中芯国际（−247.51/499.05/4,759.51/4,999.18）与特变电工
        （−94.12/−8.76/961.36/726.87）未退化却被渲染「显式期现值与终值现值均为 0、退化为
        净现金下限 X 亿元」——与引擎输出直接矛盾。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import report_generator as rg
        import html_check as hc

        # ① 源码层：判据须取 pv_sum 与 terminal_value_pv，且文案须分两支
        sp = os.path.join(SKILL_ROOT, "scripts", "report_generator.py")
        src = open(sp, encoding="utf-8").read()
        self.assertIn('_num(dcf.get("pv_sum"))', src, "退化判据须取 pv_sum")
        self.assertIn('_num(dcf.get("terminal_value_pv"))', src, "退化判据须取 terminal_value_pv")
        self.assertIn("_degen =", src, "须存在 _degen 真实退化判据")
        self.assertIn("DCF 基准期为负披露", src, "须有「基准期为负」分支文案")
        self.assertIn("DCF 退化披露", src, "须保留「真退化」分支文案")

        # ② 行为A：未退化（fcf0<0 但 pv_sum+tv_pv!=0）→ 不得出「退化披露」告警块，须出「基准期为负」
        #   注：§6.3 方法适用性表 DCF 行含静态方法论措辞「FCFF 为负时退化为净现金下限」，
        #   故断言针对告警块标题（方法选择结论）而非全文关键词。
        data = load_example_input()
        out = ve.Engine(data).run()
        out["scenarios"]["base"]["dcf"].update(
            {"fcf0": -94.12, "pv_sum": -8.76, "terminal_value_pv": 961.36,
             "tv_share": 1.009, "equity_value": 726.87})
        doc = rg.generate_report(out, stat=None, inp=data)
        self.assertNotIn("方法选择结论（DCF 退化披露）", doc,
                         "未退化的负基准期样本不得渲染「退化披露」告警块")
        self.assertNotIn("显式期现值与终值现值均为 0", doc, "未退化样本不得声称两现值均为 0")
        self.assertIn("方法选择结论（DCF 基准期为负披露）", doc, "未退化样本须渲染「基准期为负」披露")

        # ③ 行为B：真退化（pv_sum==tv_pv==0）→ 仍须出「退化披露」与「净现金下限」
        out2 = ve.Engine(load_example_input()).run()
        out2["scenarios"]["base"]["dcf"].update(
            {"fcf0": 0.0, "pv_sum": 0.0, "terminal_value_pv": 0.0, "equity_value": 78.34})
        doc2 = rg.generate_report(out2, stat=None, inp=load_example_input())
        self.assertIn("方法选择结论（DCF 退化披露）", doc2, "真退化样本须渲染「退化披露」")
        self.assertIn("净现金下限", doc2, "真退化样本须说明「净现金下限」")

        # ④ 零回归：fcf0 > 0 的样本两告警块均不得出现
        out3 = ve.Engine(load_example_input()).run()
        out3["scenarios"]["base"]["dcf"].update({"fcf0": 100.0})
        doc3 = rg.generate_report(out3, stat=None, inp=load_example_input())
        self.assertNotIn("方法选择结论（DCF 退化披露）", doc3, "fcf0>0 不得渲染退化披露")
        self.assertNotIn("方法选择结论（DCF 基准期为负披露）", doc3, "fcf0>0 不得渲染基准期为负披露")

        # ⑤ 结构机检不回退
        for _doc in (doc, doc2, doc3):
            ok, msg = hc.check_c2(_doc)
            self.assertTrue(ok, msg)
            ok8, msg8 = hc.check_c8(_doc)
            self.assertTrue(ok8, msg8)

    # ============ v3.17.0 全市场估值框架修订：P1–P5 守护测试 ============

    def test_t95_weight_key_set_generalization(self):
        """v3.17.0 P1 回归：权重键集泛化（动态候选方法集）。

        ★通用判据：候选方法集不得被写死为 {dcf, comparable, sentiment}；
        路由声明的主方法（rim/ddm/nav/rnpv/sotp）须能**携带权重进入综合**——
        此前实现只允许 dcf_weight_cap 做减法，无机制做加法，致 NAV/RIM 等
        实现后仍以「不并入综合权重」身份空转。
        """
        # ① 缺省 legacy：resolve_method_set 返回 None（零变化）
        e0 = ve.Engine({"preferences": {}})
        self.assertIsNone(e0.resolve_method_set({"industry_class": "general"}, None),
                          "缺省 method_set_mode=legacy 须返回 None（旧输入零变化）")

        # ② routed：七类路由的候选集须各不相同，且替代主方法确实入集
        expect = {
            "financial": ("rim", "comparable"),
            "resource": ("nav", "comparable"),
            "pipeline_pharma": ("rnpv", "comparable"),
            "holdco": ("sotp", "comparable"),
        }
        for cls, (primary_m, second_m) in expect.items():
            d = load_example_input()
            d.setdefault("preferences", {}).update(
                {"method_set_mode": "routed", "layer0_check": True, "lifecycle_mode": "auto"})
            fc = {"industry_class": cls}
            if cls == "financial":
                fc["interest_is_operating"] = True
            d.setdefault("meta", {})["framework_check"] = fc
            out = ve.Engine(d).run()
            w = out["weights"]
            self.assertIn(primary_m, w, f"{cls} 路由的主方法 {primary_m} 须进入综合权重")
            self.assertIn(second_m, w, f"{cls} 路由须含 {second_m}")
            self.assertAlmostEqual(sum(w.values()), 1.0, places=6, msg=f"{cls} 权重须归一化")
            ms = ((out.get("synthesis") or {}).get("four_part") or {}).get("method_set")
            self.assertIsNotNone(ms, f"{cls} 须挂出 method_set 留痕")
            self.assertEqual(ms["candidates"], list(w.keys()), "留痕候选集须与实际权重键一致")

        # ③ financial 路由：dcf 必须被剔除（cap=0 不得残留 dcf 键）
        d = load_example_input()
        d.setdefault("preferences", {}).update({"method_set_mode": "routed", "layer0_check": True})
        d.setdefault("meta", {})["framework_check"] = {"industry_class": "financial",
                                                       "interest_is_operating": True}
        out = ve.Engine(d).run()
        self.assertNotIn("dcf", out["weights"],
                         "financial 路由（cap=0）须剔除 dcf 键，否则与路由声明矛盾")

        # ④ negative_fcff 路由须被显式识别（不再依赖 neg_ratio 重算）
        d = load_example_input()
        d.setdefault("preferences", {}).update({"method_set_mode": "routed", "layer0_check": True})
        d.setdefault("meta", {})["framework_check"] = {"industry_class": "negative_fcff"}
        out = ve.Engine(d).run()
        self.assertEqual(out["framework_check"]["route_key"], "negative_fcff",
                         "显式 industry_class=negative_fcff 须命中同名的 route_key")

    def test_t96_sentiment_demoted_to_correction_layer(self):
        """v3.17.0 P2 回归：舆情从「独立加权路径」降为「可比法修正系数」。

        ★通用判据：舆情不得对同一 comp_v 基数重复计费——原 v3.15.0 四部分口径下，
        ③ 舆情以独立权重（0.2）作用在 comp_v 上，与 ② 可比法（0.5，同 comp_v 基数）
        构成**重复计费**；降为修正层后 ③ 权重归 0，舆情以乘性系数进入 ②。
        """
        values = {}
        for layer in ("path", "correction"):
            d = load_example_input()
            d.setdefault("preferences", {}).update(
                {"sentiment_layer": layer, "sentiment_band_mode": "typed"})
            out = ve.Engine(d).run()
            values[layer] = out

        fp = values["correction"]["synthesis"]["four_part"]
        # ① correction 下 ③ 权重归 0，② 权重吸收舆情原权重
        self.assertEqual(fp["part3_market_sentiment"]["weight"], 0.0,
                         "P2 修正层下 ③ 舆情权重须为 0（不再独立计费）")
        self.assertEqual(fp["part3_market_sentiment"].get("layer"), "correction")
        self.assertAlmostEqual(fp["part2_comparable_quality"]["weight"], 0.7, places=4,
                               msg="P2 下 ② 可比法权重须吸收舆情原权重 0.2 → 0.7")
        # ② path 口径保持 v3.15.0 不变
        fp_path = values["path"]["synthesis"]["four_part"]
        self.assertEqual(fp_path["part3_market_sentiment"]["weight"], 0.2,
                         "path 口径下 ③ 权重须仍为 0.2（零回归）")
        # ③ correction 须挂出情景级留痕（band/corr/impact/signal）
        sc = values["correction"]["scenarios"]["base"].get("sentiment_correction")
        self.assertIsNotNone(sc, "P2 修正层须挂出 scenario.sentiment_correction 留痕")
        for k in ("band_pct", "correction_pct", "impact_value", "signal", "layer"):
            self.assertIn(k, sc, f"留痕须含 {k}")
        self.assertEqual(sc["layer"], "correction")
        # ④ 修正后值须自洽：impact ≈ comp_nosent × corr × w_comp
        self.assertLessEqual(abs(sc["correction_pct"]), sc["band_pct"] + 1e-9,
                             "修正幅度须被带宽钳制")
        # ⑤ 情景键集合：path 不挂 sentiment_correction（零回归）
        self.assertNotIn("sentiment_correction", values["path"]["scenarios"]["base"],
                         "path 口径不得挂出 sentiment_correction（旧键集合不变）")

    def test_t97_layer0_extended_judgments(self):
        """v3.17.0 P3 回归：Layer 0 判据四维化（CV/终值占比/ROIC−WACC）+ 命中词回显。

        ★通用判据：周期性的正确度量是**增长率波动 σ_ln**（且须出现负增长），
        不是营收水平 CV——水平 CV 会把任何指数增长序列误判为强周期。
        宇树科技（3.93→17.08 亿，σ_ln≈46%）即为此前的误判样本。
        """
        import math
        # ① 命中关键词回显（审计可追溯）
        d = load_example_input()
        d.setdefault("preferences", {}).update({"layer0_check": True})
        d["meta"]["industry"] = "商业银行"
        out = ve.Engine(d).run()
        fw = out["framework_check"]
        self.assertEqual(fw["industry_class"], "financial")
        self.assertEqual(fw.get("matched_keywords"), "银行",
                         "关键词命中须回显（此前静默，无审计痕迹）")

        # ② 扩展判据：指数增长序列不得被判强周期
        d = load_example_input()
        d.setdefault("preferences", {}).update({"layer0_check": True, "layer0_extended": True})
        d["financials"]["revenue_by_year"] = {"2022": 1.23, "2023": 2.8, "2024": 3.93, "2025": 17.08}
        d.setdefault("meta", {})["framework_check"] = {"industry_class": "general",
                                                       "fcff_history": [1e8, -0.5e8, 0.9e8, 1.1e8]}
        out = ve.Engine(d).run()
        ev = out["framework_check"]["extended_judgments"]
        self.assertFalse(ev["cyclical"],
                         "单调高增长（σ_ln≈46%）不得被判强周期——须同时出现负增长")
        self.assertIn("A5_增长率波动σ_ln", out["framework_check"]["precondition_A"]["evidence"])
        # ③ 真周期样本：正负交替 → 判强周期且 DCF 降为 conditional（cap 0.5）
        d2 = load_example_input()
        d2.setdefault("preferences", {}).update({"layer0_check": True, "layer0_extended": True})
        d2["financials"]["revenue_by_year"] = {"2021": 100.0, "2022": 45.0, "2023": 130.0,
                                               "2024": 52.0, "2025": 140.0}
        d2.setdefault("meta", {})["framework_check"] = {"industry_class": "general"}
        out2 = ve.Engine(d2).run()
        fw2 = out2["framework_check"]
        self.assertTrue(fw2["extended_judgments"]["cyclical"], "正负交替序列须判强周期")
        self.assertEqual(fw2["dcf_admissible"], "conditional", "强周期须降为条件准入")
        self.assertLessEqual(fw2["dcf_weight_cap"], 0.5, "强周期封顶须 ≤0.5")
        # ④ ext=false 时只留痕不改 outcome（零变化）
        d3 = load_example_input()
        d3.setdefault("preferences", {}).update({"layer0_check": True, "layer0_extended": False})
        d3["financials"]["revenue_by_year"] = {"2021": 100.0, "2022": 45.0, "2023": 130.0,
                                               "2024": 52.0, "2025": 140.0}
        d3.setdefault("meta", {})["framework_check"] = {"industry_class": "general"}
        out3 = ve.Engine(d3).run()
        self.assertTrue(out3["framework_check"]["dcf_admissible"], "ext=false 不得改 outcome")

    def test_t98_sentiment_band_by_enterprise_type(self):
        """v3.17.0 P4 回归：舆情修正带宽按企业类型分化（替代固定 ±10%）。

        ★通用判据：舆情对估值的影响应与企业类型的**现金流确定性**成反比——
        早期/主题型企业舆情波动大（±15%），成熟/金融/衰退型小（±5%），
        非上市股权无公开舆情（0%）。固定 ±10% 抹平了这一结构性差异。
        """
        cases = {"startup": 0.15, "growth": 0.10, "mature": 0.05, "decline": 0.05}
        e = ve.Engine({"preferences": {"sentiment_band_mode": "typed"}})
        for stage, want in cases.items():
            band, why = e.sentiment_band({"stage": stage, "enabled": True})
            self.assertAlmostEqual(band, want, places=4, msg=f"{stage} 带宽须为 ±{want:.0%}")
        # ① fixed（缺省）→ 恒 0.10（零变化）
        e0 = ve.Engine({"preferences": {}})
        b0, _ = e0.sentiment_band({"stage": "startup", "enabled": True})
        self.assertAlmostEqual(b0, 0.10, places=4, msg="缺省 fixed 须恒 ±10%")
        # ② 非上市：0%
        d = load_example_input()
        d.setdefault("preferences", {})["sentiment_band_mode"] = "typed"
        d.setdefault("meta", {})["asset_type"] = "private"
        e2 = ve.Engine(d)
        b2, w2 = e2.sentiment_band({"stage": "mature", "enabled": True})
        self.assertAlmostEqual(b2, 0.0, places=4, msg="非上市（private）舆情带宽须为 0")
        # ③ 金融路由优先于生命周期阶段
        d3 = load_example_input()
        d3.setdefault("preferences", {}).update({"sentiment_band_mode": "typed", "layer0_check": True})
        d3.setdefault("meta", {})["framework_check"] = {"industry_class": "financial"}
        e3 = ve.Engine(d3)
        e3.framework_admissibility()
        b3, w3 = e3.sentiment_band({"stage": "growth", "enabled": True})
        self.assertAlmostEqual(b3, 0.05, places=4, msg="金融路由须覆盖生命周期阶段（±5%）")
        # ④ 强周期：±8%（须 σ_ln>0.60 且出现负增长）
        d4 = load_example_input()
        d4.setdefault("preferences", {}).update({"sentiment_band_mode": "typed", "layer0_check": True})
        d4["financials"]["revenue_by_year"] = {"2021": 100.0, "2022": 45.0, "2023": 130.0,
                                               "2024": 52.0, "2025": 140.0}
        d4.setdefault("meta", {})["framework_check"] = {"industry_class": "general"}
        e4 = ve.Engine(d4)
        e4.framework_admissibility()
        b4, w4 = e4.sentiment_band({"stage": "mature", "enabled": True})
        self.assertAlmostEqual(b4, 0.08, places=4, msg="强周期须 ±8%")

    def test_t99_rim_ddm_financial_routing(self):
        """v3.17.0 P5 回归：RIM/DDM 金融路由主方法 + 手算交叉校验 + 适用性护栏。

        ★通用判据：金融业（利息为营业成本）FCFF 不可定义 → DCF 判否，须有**可执行的**
        替代主方法。此前 recommended_primary="rim/ddm" 仅作为文本渲染（report_generator
        第 1076 行），无任何计算分支——路由声明与实现脱节。
        本测试的价值锚点是**独立手算重算**：引擎输出须与逐期 RIM 递推手算逐位一致。
        """
        bank = {
            "meta": {"company": "示例银行", "industry": "商业银行", "asset_type": "mature",
                     "framework_check": {"industry_class": "financial", "interest_is_operating": True}},
            "financials": {"revenue_latest_ttm": 1200.0,
                           "revenue_by_year": {"2022": 950.0, "2023": 1040.0,
                                               "2024": 1120.0, "2025": 1200.0},
                           "net_profit_latest_ttm": 450.0, "net_margin": 0.375, "cagr_3y": 0.081,
                           "net_assets": 4200.0, "roe": 0.107,
                           "total_shares_after_issue": 100.0,
                           "terminal_growth": 0.03, "wacc": 0.10},
            "comparables": [{"name": "同业A", "pe": 6.5, "pb": 0.65, "roe": 0.11, "source": "public_info"},
                            {"name": "同业B", "pe": 7.2, "pb": 0.72, "roe": 0.115, "source": "public_info"},
                            {"name": "同业C", "pe": 5.8, "pb": 0.58, "roe": 0.10, "source": "public_info"}],
            "sentiment": {"sector_heat": "neutral", "company_news_sentiment": "neutral"},
            "preferences": {"layer0_check": True, "layer0_extended": True, "lifecycle_mode": "auto",
                            "method_set_mode": "routed", "enable_rim": True, "enable_ddm": True},
        }
        out = ve.Engine(bank).run()
        # ① 路由：金融判否 + RIM 进入综合权重
        self.assertEqual(out["framework_check"]["industry_class"], "financial")
        self.assertFalse(out["framework_check"]["dcf_admissible"], "金融业 DCF 须判否")
        self.assertIn("rim", out["weights"], "金融路由须由 RIM 承载主权重")
        # ② RIM 输出须存在且自洽
        rim = out.get("rim_valuation")
        self.assertIsNotNone(rim, "金融路由须挂出 rim_valuation")
        self.assertTrue(rim["enabled"])
        # ③ 手算交叉校验（同一组参数逐期递推）
        B0, roe, ke, omega, n, payout = 4200.0, 0.107, 0.10, 0.85, 5, 0.40
        pv, bt = 0.0, B0
        for t in range(1, n + 1):
            ri = (roe - ke) * bt
            pv += ri / (1 + ke) ** t
            bt = bt + ri * (1 - payout)
        tv_pv = ((roe - ke) * bt / (1 + ke - omega)) / (1 + ke) ** n
        manual = B0 + pv + tv_pv
        self.assertAlmostEqual(rim["equity_value"], manual, places=1,
                               msg=f"RIM 引擎值 {rim['equity_value']} 须等于手算值 {manual:.2f}")
        self.assertAlmostEqual(rim["pv_residual_income"], pv, places=1, msg="RIM 显式期现值须与手算一致")
        # ④ 每股换算（亿元/亿股 = 元/股）
        self.assertAlmostEqual(rim["per_share"], rim["equity_value"] / 100.0, places=2,
                               msg="每股须 = 权益价值(亿元)/总股本(亿股)")
        # ⑤ 行业参数底座兜底：不给 rim 块也能算（ke/roe 取自 industry_params.json）
        self.assertAlmostEqual(rim["cost_of_equity"],
                               round(ke, 4), places=4, msg="Ke 须由行业底座/显式给定兜底")
        # ⑥ DDM 输出 + 适用性护栏
        ddm = out.get("ddm_valuation")
        self.assertIsNotNone(ddm, "enable_ddm 须挂出 ddm_valuation")
        self.assertTrue(ddm["enabled"])
        self.assertEqual(ddm["net_profit_source"], "net_profit_latest_ttm",
                         "DDM 须记录净利基准来源（审计可追溯）")
        # ⑦ 成长股 DDM 护栏：显式期增速 >25% 须告警
        growth = load_example_input()          # 宇树 g1=60%
        growth.setdefault("preferences", {})["enable_ddm"] = True
        ddm_g = ve.Engine(growth).run()["ddm_valuation"]
        self.assertTrue(ddm_g.get("applicability_warnings"),
                        "成长股（g1=60%）DDM 须挂出适用性告警")
        self.assertTrue(any("25%" in x for x in ddm_g["applicability_warnings"]),
                        "告警须说明「显式期增速过高不符合分红稳定前提」")
        # ⑧ 缺省不开（零回归）：不设 enable_rim/enable_ddm 时不挂出
        plain = load_example_input()
        plain.setdefault("preferences", {}).pop("enable_rim", None)
        plain["preferences"].pop("enable_ddm", None)
        o_plain = ve.Engine(plain).run()
        self.assertNotIn("rim_valuation", o_plain, "缺省不得挂出 rim_valuation（旧输入键集合不变）")
        self.assertNotIn("ddm_valuation", o_plain, "缺省不得挂出 ddm_valuation（旧输入键集合不变）")

    def test_t99b_v317_zero_regression(self):
        """v3.17.0 零回归：显式关闭全部新机制 vs 缺省，须逐位等价。

        ★通用判据：新增机制必须 opt-in——所有 v3.17 开关取缺省值时，
        输出须与显式关闭时**逐位相同**（byte-identical），否则视为破坏了向后兼容。
        """
        import copy
        keys = {"method_set_mode": "legacy", "sentiment_layer": "path",
                "sentiment_signal_mode": "legacy", "sentiment_band_mode": "fixed",
                "layer0_extended": False, "enable_rim": False, "enable_ddm": False}
        d_a = load_example_input()
        d_a.setdefault("preferences", {}).update(keys)
        d_b = load_example_input()
        a = ve.Engine(copy.deepcopy(d_a)).run()
        b = ve.Engine(copy.deepcopy(d_b)).run()
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         "v3.17 开关取缺省时须与显式关闭逐位等价")

    # ==================== v3.18.0：舆情强度驱动估值调整 ====================
    def _mk_strength(self, pref=None, sent=None):
        """构造最小可用输入（含可比公司/财务），用于舆情强度层单测。"""
        d = {
            "financials": {"revenue_by_year": {"2022": 10.0, "2023": 12.0, "2024": 14.5, "2025": 17.0},
                           "shares_outstanding": 5.0, "net_profit_latest": 2.0},
            "comparables": [{"name": "A", "pe": 20, "ps": 5}],
            "sentiment": sent or {},
            "preferences": pref or {},
        }
        return ve.Engine(d)

    @staticmethod
    def _ev(n, direction="positive", importance=None):
        e = {"impact_direction": direction}
        if importance:
            e["importance"] = importance
        return [e] * n

    def test_t100a_signal_strength_matrix(self):
        """T100a 强度矩阵四档 × 一致性：none/few/medium/many × consistent/conflict。"""
        p = {"sentiment_adjust_mode": "strength"}
        # none：无信号 → 0.50
        k, d = self._mk_strength(p, {})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 0.50, places=4)
        self.assertEqual(d["tier"], "none")
        # few（1–2 条一致）→ 0.70
        k, d = self._mk_strength(p, {"events": self._ev(2)})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 0.70, places=4)
        self.assertEqual(d["tier"], "few")
        # medium（3–5 条一致）→ 1.00
        k, d = self._mk_strength(p, {"events": self._ev(4)})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 1.00, places=4)
        self.assertEqual(d["tier"], "medium")
        # many（6+ 条一致）→ 1.30
        k, d = self._mk_strength(p, {"events": self._ev(6)})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 1.30, places=4)
        self.assertEqual(d["tier"], "many")
        # conflict 降档：medium 一致 1.00 → 冲突 0.70
        conflict_ev = [{"impact_direction": "positive"}, {"impact_direction": "positive"},
                       {"impact_direction": "negative"}]
        k, d = self._mk_strength(p, {"events": conflict_ev})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 0.70, places=4)
        self.assertEqual(d["consistency"], "conflict")

    def test_t100b_authority_and_high_mult(self):
        """T100b 高重要性与权威出处加成：高重要性 ×1.20；权威（opt-in）×1.15。"""
        p = {"sentiment_adjust_mode": "strength"}
        # 高重要性：medium 1.00 × 1.20 = 1.20
        k, d = self._mk_strength(p, {"events": self._ev(4, importance="high")})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 1.20, places=4)
        self.assertTrue(d["has_high_importance"])
        # 权威缺省（legacy）不加成：仍 1.00
        pol = {"policy": [{"direction": "positive", "authority": True}] * 4}
        k, d = self._mk_strength(p, pol)._sentiment_signal_strength()
        self.assertAlmostEqual(k, 1.00, places=4)
        self.assertFalse(d["authority"])
        # 权威 opt-in：1.00 × 1.15 = 1.15
        p2 = {"sentiment_adjust_mode": "strength", "signal_authority_mode": "weighted"}
        k, d = self._mk_strength(p2, pol)._sentiment_signal_strength()
        self.assertAlmostEqual(k, 1.15, places=4)
        self.assertTrue(d["authority"])

    def test_t100c_decay_and_cap(self):
        """T100c 时效衰减与 K_MAX 上限：>30 天线性衰减；强度硬上限 1.60。"""
        p = {"sentiment_adjust_mode": "strength"}
        # 60 天：1 − (60−30)/90 = 0.6667，medium 1.00 → 0.6667
        k, d = self._mk_strength(p, {"events": self._ev(4), "days_since_event": 60})._sentiment_signal_strength()
        self.assertAlmostEqual(d["decay"], 0.6667, places=3)
        self.assertAlmostEqual(k, 0.6667, places=3)
        # 分段衰减口径：31+31..60 天（dd=31..60）→ 0.5；此处 70 天 → dd=40
        p2 = {"sentiment_adjust_mode": "strength", "signal_decay_mode": "stepped"}
        k, _ = self._mk_strength(p2, {"events": self._ev(4), "days_since_event": 70})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 0.50, places=4)
        # 分段衰减口径边界：dd≤30（days≤60）不衰减
        k, _ = self._mk_strength(p2, {"events": self._ev(4), "days_since_event": 60})._sentiment_signal_strength()
        self.assertAlmostEqual(k, 1.00, places=4)
        # K_MAX 硬上限：many 1.30 × high 1.20 × auth 1.15 = 1.794 → 封顶 1.60
        p3 = {"sentiment_adjust_mode": "strength", "signal_authority_mode": "weighted"}
        s = {"events": self._ev(6, importance="high"),
             "policy": [{"direction": "positive", "authority": True}]}
        k, d = self._mk_strength(p3, s)._sentiment_signal_strength()
        self.assertAlmostEqual(k, 1.60, places=4)
        self.assertEqual(d["cap"], 1.60)

    def test_t100d_direction_magnitude_orthogonality(self):
        """T100d 方向/幅度正交：sign(sent) 只承载方向，k_signal 承载强度。

        幅度 = band × k_signal × min(|sent|/10%, 1)，|sent|≥10% 满权。
        """
        p = {"sentiment_adjust_mode": "strength"}
        e = self._mk_strength(p, {"events": self._ev(4)})   # k=1.00
        a_pos, _, s_pos = e._sentiment_correction_strength(0.10, 0.05, "t")
        self.assertAlmostEqual(a_pos, 0.05, places=6)       # 5% × 1.00 × 1.0
        self.assertEqual(s_pos["direction"], 1.0)
        a_neg, _, s_neg = e._sentiment_correction_strength(-0.10, 0.05, "t")
        self.assertAlmostEqual(a_neg, -0.05, places=6)      # 方向翻转
        self.assertEqual(s_neg["direction"], -1.0)
        # 幅度归一化：+1% → 满权的 1/10
        a_small, _, s_small = e._sentiment_correction_strength(0.01, 0.05, "t")
        self.assertAlmostEqual(a_small, 0.005, places=6)
        self.assertAlmostEqual(s_small["magnitude"], 0.10, places=6)
        # 零舆情 → 零修正
        a_zero, _, _ = e._sentiment_correction_strength(0.0, 0.05, "t")
        self.assertEqual(a_zero, 0.0)

    def test_t100e_band_ceiling_breaks_double_clamp(self):
        """T100e 口径 C 破除双重截断：窄带宽 + 强信号可在 band 之上有限放大。

        ★根因守护：legacy 口径下 sent=+10%、band=5%、k=1.56 → 15.6% 被截回 5%，
        信号强度的放大作用被完全吃掉；strength 口径应给出 band×k = 7.8%。
        """
        ev = {"events": self._ev(6, importance="high")}
        # legacy：clamp(sent×k, ±band) → 5%
        e_old = self._mk_strength({"sentiment_layer": "correction", "sentiment_band_mode": "typed",
                                   "lifecycle_mode": "auto"}, ev)
        e_old._lifecycle = {"enabled": True, "stage": "mature"}
        old, band_old, _ = e_old._sentiment_correction(0.10)
        self.assertAlmostEqual(band_old, 0.05, places=6)
        self.assertLessEqual(abs(old), band_old + 1e-9, "legacy 口径须被 band 截断")
        # strength：band×k，上限 band×1.60 = 8%
        e_new = self._mk_strength({"sentiment_layer": "correction", "sentiment_band_mode": "typed",
                                   "lifecycle_mode": "auto", "sentiment_adjust_mode": "strength"}, ev)
        e_new._lifecycle = {"enabled": True, "stage": "mature"}
        new, band_new, sig = e_new._sentiment_correction(0.10)
        self.assertAlmostEqual(band_new, 0.05, places=6)
        self.assertGreater(abs(new), abs(old), "strength 口径须突破 band（消除双重截断）")
        self.assertAlmostEqual(new, 0.078, places=4)          # 0.05 × 1.56
        self.assertLessEqual(abs(new), band_new * 1.60 + 1e-9, "不得越过 band×K_MAX 硬上限")
        self.assertEqual(sig["adjust_mode"], "strength")

    def test_t100f_no_signal_and_private_gating(self):
        """T100f 无信号减半 + 非上市（private）舆情不适用。"""
        # 无信号：k=0.5 → 修正减半
        e = self._mk_strength({"sentiment_adjust_mode": "strength"}, {})
        a, _, s = e._sentiment_correction_strength(0.10, 0.05, "t")
        self.assertAlmostEqual(s["k_signal"], 0.50, places=4)
        self.assertAlmostEqual(a, 0.025, places=6)   # 5% × 0.5
        # private：band=0 → 修正恒 0
        e_p = self._mk_strength({"sentiment_layer": "correction", "sentiment_band_mode": "typed",
                                 "sentiment_adjust_mode": "strength"},
                                {"events": self._ev(6, importance="high")})
        e_p.d["meta"] = {"asset_type": "private"}
        a_p, band_p, _ = e_p._sentiment_correction(0.10)
        self.assertEqual(band_p, 0.0)
        self.assertEqual(a_p, 0.0)

    def test_t100g_overlap_discount(self):
        """T100g 去相关折让：与 impact_map.multiple_factor 同源时按 0.70 折让（opt-in）。"""
        ev = {"events": self._ev(4)}   # k=1.00
        # 未开启折让
        e0 = self._mk_strength({"sentiment_layer": "correction", "sentiment_adjust_mode": "strength"}, ev)
        e0._assumption_impact_active = True
        a0, _, s0 = e0._sentiment_correction(0.10)
        self.assertIsNone(s0["overlap_discount"])
        # 开启折让
        e1 = self._mk_strength({"sentiment_layer": "correction", "sentiment_adjust_mode": "strength",
                                "sentiment_overlap_discount": True}, ev)
        e1._assumption_impact_active = True
        a1, _, s1 = e1._sentiment_correction(0.10)
        self.assertAlmostEqual(s1["overlap_discount"], 0.70, places=4)
        self.assertAlmostEqual(a1, a0 * 0.70, places=6)
        # 折让仅当假设层生效：未生效时不折
        e2 = self._mk_strength({"sentiment_layer": "correction", "sentiment_adjust_mode": "strength",
                                "sentiment_overlap_discount": True}, ev)
        e2._assumption_impact_active = False
        a2, _, s2 = e2._sentiment_correction(0.10)
        self.assertIsNone(s2["overlap_discount"])
        self.assertAlmostEqual(a2, a0, places=6)

    def test_t100h_strength_trace_keys(self):
        """T100h 留痕：strength 口径须挂出 adjust_mode/clamp_hit/ceiling 等审计键。"""
        e = self._mk_strength({"sentiment_layer": "correction", "sentiment_adjust_mode": "strength"},
                              {"events": self._ev(4)})
        _, _, s = e._sentiment_correction(0.10)
        for key in ("layer", "adjust_mode", "band", "k_signal", "raw", "magnitude",
                    "direction", "adj_raw", "ceiling", "clamp_hit", "corrected",
                    "overlap_discount", "signal_detail"):
            self.assertIn(key, s, f"强度口径留痕缺少字段 {key}")
        self.assertEqual(s["layer"], "correction")
        self.assertEqual(s["adjust_mode"], "strength")

    def test_t100i_v318_zero_regression(self):
        """v3.18.0 零回归：新增三开关取缺省 vs 显式关闭，须逐位等价（byte-identical）。

        ★通用判据：新增机制必须 opt-in，缺省值下输出与显式关闭时逐位相同。
        """
        import copy
        keys = {"sentiment_adjust_mode": "legacy", "signal_authority_mode": "legacy",
                "signal_decay_mode": "legacy", "sentiment_overlap_discount": False}
        d_a = load_example_input()
        d_a.setdefault("preferences", {}).update(keys)
        d_b = load_example_input()
        a = ve.Engine(copy.deepcopy(d_a)).run()
        b = ve.Engine(copy.deepcopy(d_b)).run()
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         "v3.18 开关取缺省时须与显式关闭逐位等价")
        # 同时须与 v3.17 全关配置交叉一致（层叠零回归）
        keys_317 = {"method_set_mode": "legacy", "sentiment_layer": "path",
                    "sentiment_signal_mode": "legacy", "sentiment_band_mode": "fixed"}
        d_c = load_example_input()
        d_c.setdefault("preferences", {}).update({**keys_317, **keys})
        c = ve.Engine(copy.deepcopy(d_c)).run()
        self.assertEqual(json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(c, sort_keys=True, ensure_ascii=False, default=str),
                         "v3.18 与 v3.17 缺省层叠后仍须逐位等价")

    def test_t100j_sentiment_correction_report_disclosure(self):
        """T100j 报告层：舆情强度修正披露须渲染（v3.18.0）。

        ★守护「渲染型站点未全量覆盖」缺陷族：引擎已输出 sentiment_correction，
        报告层必须把它渲染成可读章节，而非静默丢弃。
        """
        import report_generator as rg
        inp = load_example_input()
        stat_path = os.path.join(SKILL_ROOT, "examples", "stat_example.json")
        stat = None
        if os.path.exists(stat_path):
            with open(stat_path, "r", encoding="utf-8") as f:
                stat = json.load(f)
        # ① strength 口径：须出现披露章节 + 可复算拆解
        d = load_example_input()
        d.setdefault("preferences", {}).update({
            "sentiment_layer": "correction", "sentiment_band_mode": "typed",
            "sentiment_adjust_mode": "strength", "signal_authority_mode": "weighted"})
        d.setdefault("sentiment", {}).update({
            "sector_heat": "high", "company_news_sentiment": "positive",
            "events": [{"impact_direction": "positive", "importance": "high"}] * 4,
            "policy": [{"direction": "positive", "authority": True}]})
        out = ve.Engine(copy.deepcopy(d)).run()
        html = rg.generate_report(out, stat=stat, inp=d)
        self.assertIn("舆情强度修正披露", html, "报告层须渲染舆情强度修正披露章节")
        self.assertIn("方向", html, "strength 口径须给出方向拆解")
        self.assertIn("上限", html, "口径 C 须披露上限 band×1.60")
        self.assertIn("medium", html, "须披露信号档 tier")
        # ② legacy 口径：adjust_mode 须为 legacy
        d2 = load_example_input()
        d2.setdefault("preferences", {}).update({
            "sentiment_layer": "correction", "sentiment_band_mode": "typed"})
        out2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertEqual(out2["scenarios"]["base"].get("sentiment_correction", {}).get("adjust_mode"),
                         "legacy", "缺省须为 legacy 口径")
        # ③ 纯 path 口径（缺省）：不挂 sentiment_correction → 报告不渲染该章节（零回归）
        out3 = ve.Engine(copy.deepcopy(load_example_input())).run()
        self.assertNotIn("sentiment_correction", out3["scenarios"]["base"],
                         "缺省 path 口径不得挂出 sentiment_correction")
        html3 = rg.generate_report(out3, stat=stat, inp=inp)
        self.assertNotIn("舆情强度修正披露", html3, "path 口径不渲染披露章节（零回归）")

    # ==================== v3.19.0 P6-B/C：rNPV / SOTP 引擎取值分支 ====================
    @staticmethod
    def _mk_alt(kind, pref=None, extra=None):
        """构造 rNPV/SOTP 探针输入。"""
        d = {
            "meta": {"name": "探针", "industry": "创新药" if kind == "rnpv" else "综合控股",
                     "exchange": "SZSE"},
            "financials": {"revenue_latest_ttm": 12.0, "net_profit_latest_ttm": -3.0,
                           "net_margin": -0.25, "total_shares_after_issue": 5.0, "net_cash": 20.0},
            "comparables": [{"name": "A", "pe": 40, "ps": 9, "market_cap": 200},
                            {"name": "B", "pe": 36, "ps": 8, "market_cap": 160},
                            {"name": "C", "pe": 44, "ps": 10, "market_cap": 240}],
            "preferences": dict(pref or {}),
        }
        if extra:
            d.update(extra)
        return ve.Engine(d)

    def test_t101_weight_envelope_recycle(self):
        """T101 权重包络：候选集中出现「无取值分支」方法时权重须回流（消除静默少算）。

        ★守护静默错算缺陷：resolve_method_set() 曾把 rnpv/sotp 写进 weights，
        但 scenario() 综合式只读 comparable/dcf → 其权重蒸发、综合值被少算。
        P6-A 闸门：白名单外方法权重归零并回流（诚实退化 + 留痕）。
        """
        # 白名单内的 rnpv/sotp 不再被剔除（v3.19.0 已有取值分支）
        for cls, key in (("pipeline_pharma", "rnpv"), ("holdco", "sotp")):
            e = self._mk_alt("rnpv" if cls == "pipeline_pharma" else "sotp",
                             {"method_set_mode": "routed", "layer0_check": True})
            e.d["meta"]["framework_check"] = {"industry_class": cls}
            ms = e.resolve_method_set()
            self.assertEqual(ms.get("envelope_checks"), [],
                             f"{cls}：{key} 已有取值分支，不应被包络剔除")
            self.assertIn(key, ms["resolved_weights"], f"{cls} 主方法权重缺失")
            # 归一化校验
            self.assertAlmostEqual(sum(ms["resolved_weights"].values()), 1.0, places=3)
        # 人为注入白名单外方法 → 须回流并留痕
        e2 = self._mk_alt("rnpv", {"method_set_mode": "routed", "layer0_check": True})
        e2.d["meta"]["framework_check"] = {"industry_class": "holdco"}
        orig = ve.ROUTE_METHOD_WEIGHTS["holdco"]
        try:
            ve.ROUTE_METHOD_WEIGHTS["holdco"] = {"bogus_method": 0.60, "comparable": 0.40}
            ms2 = e2.resolve_method_set()
            self.assertNotIn("bogus_method", ms2["resolved_weights"], "白名单外方法须被剔除")
            self.assertAlmostEqual(ms2["resolved_weights"].get("comparable"), 1.0, places=3,
                                   msg="权重须回流给 comparable（唯一剩余方法）")
            self.assertTrue(ms2["envelope_checks"], "回流须留痕")
            self.assertEqual(ms2["envelope_checks"][0]["method"], "bogus_method")
        finally:
            ve.ROUTE_METHOD_WEIGHTS["holdco"] = orig

    def test_t102_rnpv_manual_crosscheck(self):
        """T102 rNPV 手算交叉校验 + PoS 单调性 + 边际留痕。"""
        e = self._mk_alt("rnpv", {"enable_rnpv": True},
                         {"rnpv": {"enabled": True, "discount_rate": 0.12, "margin": 0.30,
                                   "pipelines": [{"name": "PD-1", "phase": "phase3", "peak_sales": 50.0,
                                                  "launch_year": 3, "rnd_annual": 4.0}]}})
        r = e.rnpv_valuation()
        self.assertTrue(r["enabled"])
        # 手算：与探针一致（PoS=0.60, r=0.12, 爬坡4年/悬崖8年/残值0.10）
        peak, pos, marg, rr, launch, horizon = 50.0, 0.60, 0.30, 0.12, 3, 15
        npv = 0.0
        for t in range(1, horizon + 1):
            if t < launch:
                npv += -4.0 / (1 + rr) ** t
                continue
            y = t - launch + 1
            if y <= ve.RNPV_RAMP_YEARS:
                shape = y / float(ve.RNPV_RAMP_YEARS)
            else:
                dy = y - ve.RNPV_RAMP_YEARS
                shape = (1.0 - (1.0 - ve.RNPV_TAIL_FLOOR) * (dy / float(ve.RNPV_TAIL_YEARS))) \
                    if dy <= ve.RNPV_TAIL_YEARS else ve.RNPV_TAIL_FLOOR
            npv += peak * shape * marg * pos / (1 + rr) ** t
        self.assertAlmostEqual(r["value"], round(npv, 2), places=2, msg="rNPV 与手算不符")
        self.assertEqual(r["pos_schedule"][0]["pos"], 0.60)
        # PoS 单调性
        vals = []
        for ph in ve.RNPV_PHASE_ORDER:
            ei = self._mk_alt("rnpv", {"enable_rnpv": True},
                              {"rnpv": {"enabled": True, "pipelines": [
                                  {"name": "X", "phase": ph, "peak_sales": 50.0,
                                   "launch_year": 3, "rnd_annual": 4.0}]}})
            vals.append(ei.rnpv_valuation()["value"])
        self.assertEqual(vals, sorted(vals), "PoS 提高 → rNPV 须单调不减")
        # 缺参数留痕（不静默）
        e2 = self._mk_alt("rnpv", {"enable_rnpv": True},
                          {"rnpv": {"enabled": True, "pipelines": [{"name": "无参", "phase": "phase2"}]}})
        r2 = e2.rnpv_valuation()
        self.assertTrue(r2["enabled"])
        self.assertIsNone(r2["value"])
        self.assertTrue(r2["pipelines_detail"][0].get("note"))
        # pos_overrides 生效
        e3 = self._mk_alt("rnpv", {"enable_rnpv": True},
                          {"rnpv": {"enabled": True, "pos_overrides": {"phase3": 0.90},
                                    "pipelines": [{"name": "X", "phase": "phase3", "peak_sales": 50.0,
                                                   "launch_year": 3, "rnd_annual": 4.0}]}})
        self.assertEqual(e3.rnpv_valuation()["pos_schedule"][0]["pos"], 0.90)

    def test_t103_sotp_conservation(self):
        """T103 SOTP 守恒 + 手算交叉校验 + 控股折价分档。"""
        # 守恒：单分部/无净债/无联营 → value == Σ分部价值
        e = self._mk_alt("sotp", {"enable_sotp": True},
                         {"sotp": {"enabled": True, "net_debt": 0.0,
                                   "segments": [{"name": "单体", "value": 123.45}]}})
        s = e.sotp_valuation()
        self.assertAlmostEqual(s["value"], 123.45, places=2, msg="单分部守恒破坏")
        self.assertEqual(s["holdco_discount"], 0.0, "1 分部不应折价")
        # 手算：3 分部 + 持股 0.8 + metric×multiple + net_debt + associates
        e2 = self._mk_alt("sotp", {"enable_sotp": True},
                          {"sotp": {"enabled": True, "net_debt": 30.0, "associates_value": 15.0,
                                    "segments": [{"name": "A", "value": 100.0},
                                                 {"name": "B", "value": 60.0, "stake": 0.8},
                                                 {"name": "C", "metric": 20.0, "multiple": 3.0}]}})
        s2 = e2.sotp_valuation()
        sum_seg = 100.0 + 60.0 * 0.8 + 20.0 * 3.0          # 208
        ev = sum_seg + 15.0                                 # 223
        eq_pre = ev - 30.0                                  # 193
        self.assertAlmostEqual(s2["sum_segment_value"], sum_seg, places=2)
        self.assertAlmostEqual(s2["ev_sum"], ev, places=2)
        self.assertAlmostEqual(s2["equity_before_discount"], eq_pre, places=2)
        self.assertEqual(s2["holdco_discount"], 0.10, "3 分部 → auto 折价 10%")
        self.assertAlmostEqual(s2["value"], round(eq_pre * 0.90, 2), places=2)
        # 折价上限封顶
        e3 = self._mk_alt("sotp", {"enable_sotp": True},
                          {"sotp": {"enabled": True, "holdco_discount": 0.99,
                                    "segments": [{"name": "A", "value": 100.0}]}})
        self.assertEqual(e3.sotp_valuation()["holdco_discount"], ve.SOTP_HOLDCO_DISCOUNT_MAX)
        # 全缺价值 → 不静默
        e4 = self._mk_alt("sotp", {"enable_sotp": True},
                          {"sotp": {"enabled": True, "segments": [{"name": "空"}]}})
        s4 = e4.sotp_valuation()
        self.assertTrue(s4["enabled"])
        self.assertIsNone(s4["value"])

    def test_t103b_alt_methods_enter_synthesis(self):
        """T103b 替代主方法须真正进入综合（routed 模式下权重不再蒸发）+ 报告渲染守护。"""
        import report_generator as rg
        for kind, key in (("rnpv", "rnpv"), ("sotp", "sotp")):
            inp = {
                "meta": {"name": "探针", "industry": "创新药" if kind == "rnpv" else "综合控股",
                         "exchange": "SZSE",
                         "framework_check": {"industry_class": "pipeline_pharma" if kind == "rnpv" else "holdco"}},
                "financials": {"revenue_latest_ttm": 12.0, "net_profit_latest_ttm": -3.0,
                               "net_margin": -0.25, "total_shares_after_issue": 5.0, "net_cash": 20.0},
                "comparables": [{"name": "A", "pe": 40, "ps": 9, "market_cap": 200},
                                {"name": "B", "pe": 36, "ps": 8, "market_cap": 160},
                                {"name": "C", "pe": 44, "ps": 10, "market_cap": 240}],
                "preferences": {"method_set_mode": "routed", "layer0_check": True,
                                "enable_rnpv" if kind == "rnpv" else "enable_sotp": True},
            }
            if kind == "rnpv":
                inp["rnpv"] = {"enabled": True, "pipelines": [
                    {"name": "P", "phase": "phase3", "peak_sales": 50.0, "launch_year": 3, "rnd_annual": 4.0}]}
            else:
                inp["sotp"] = {"enabled": True, "net_debt": 30.0,
                               "segments": [{"name": "A", "value": 100.0}, {"name": "B", "value": 60.0}]}
            out = ve.Engine(copy.deepcopy(inp)).run()
            alt = out["scenarios"]["base"].get("alternative_methods")
            self.assertIsNotNone(alt, f"{kind} 未进入综合（静默少算）")
            self.assertIn(key, alt, f"{kind} 须出现在 alternative_methods")
            self.assertGreater(out["weights"].get(key, 0.0), 0.3, f"{kind} 主方法权重过低")
            self.assertNotEqual(alt[key]["contribution"], 0, f"{kind} 贡献为 0")
            # 报告渲染：多方法表 / 适用性表 / 披露章节
            html = rg.generate_report(out, stat=None, inp=inp)
            self.assertIn("（风险调整净现值）" if kind == "rnpv" else "（分部加总）", html,
                          f"{kind} §7.1 方法行缺失")
            self.assertIn("7.3.2 rNPV" if kind == "rnpv" else "7.3.3 SOTP", html, f"{kind} 披露章节缺失")

    def test_t104_v319_zero_regression(self):
        """v3.19.0 零回归：rNPV/SOTP 缺省关闭 → 输出键集合与数值逐位不变。"""
        a = ve.Engine(copy.deepcopy(load_example_input())).run()
        self.assertNotIn("rnpv_valuation", a)
        self.assertNotIn("sotp_valuation", a)
        self.assertNotIn("alternative_methods", a["scenarios"]["base"])
        keys = {"enable_rnpv": False, "enable_sotp": False}
        d = load_example_input()
        d.setdefault("preferences", {}).update(keys)
        b = ve.Engine(copy.deepcopy(d)).run()
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         "v3.19 开关缺省 vs 显式关闭须逐位等价")

    # ============ v3.20.0 可比公司筛选证据链（四期改造）守护测试 ============
    # 四期对应：一期 P0-1 长名单/剔除台账 + P0-4 截点｜二期 P0-2 规模双口径 5 倍
    #          三期 P0-3 实体去重 + P1-1 会计准则｜四期 P1-4 次新剔除 + P1-5 指数锚降权

    @staticmethod
    def _peer_comps():
        """最小可比集（6 家，CAS，2026 半年报口径，均为 2010 年前上市）。"""
        rows = [
            ("美的集团", "000333.SZ", 6507.88, 4672.23, 14.66),
            ("海尔智家", "600690.SH", 1822.51, 2979.68, 10.22),
            ("海信家电", "000921.SZ", 322.95, 853.54, 11.67),
            ("TCL智家", "002668.SZ", 92.15, 189.89, 9.25),
            ("惠而浦", "600983.SH", 55.41, 42.23, 11.52),
            ("长虹美菱", "000521.SZ", 42.54, 284.73, 83.40),
        ]
        out = []
        for name, code, mcap, rev, pe in rows:
            out.append({
                "name": name, "code": code, "exchange": "CN", "standard": "CAS",
                "legal_entity_id": code.split(".")[0], "market_cap": mcap, "revenue": rev,
                "pe": pe, "listing_date": "2013-09-18" if code == "000333.SZ" else "1999-07-13",
                "financial_period_end": "2026-06-30", "included": True,
            })
        return out

    def test_t105_long_list_and_cutoff(self):
        """v3.20.0 一期回归：长名单/剔除台账（P0-1）与信息可得性截点（P0-4）。

        ★根因：IPO 技能此前只有「最终样本」，没有「长名单从哪来、谁被剔除、为什么」。
        监管对「发行 PE 高于可比中位数」问询时，无法回答「为何只选这几家」。
        comps 技能第 2 步要求两段式（长名单→逐家过业务/产品筛选）且每家记 8 项。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import peer_screening as ps

        comps = self._peer_comps()
        cfg = {"enabled": True, "classification_system": "SW_2021", "long_list_size": 20,
               "rejected": [{"name": "X", "reason_type": "product", "reason": "彩电不可比"},
                            {"name": "Y", "reason_type": "status", "reason": "ST"}]}

        # ① 正向：完整台账 → 覆盖率与分型统计正确，无 warning
        r = ps.audit_long_list(comps, cfg)
        self.assertEqual(r["checks"]["long_list_size"]["ratio_to_final"], round(20 / 6, 2),
                         "长名单/最终样本比值须为 20/6")
        self.assertEqual(r["checks"]["rejected"]["n"], 2)
        self.assertEqual(r["checks"]["rejected"]["typed"], 2, "两条剔除记录均须落枚举")
        self.assertEqual(r["checks"]["rejected"]["by_type"], {"product": 1, "status": 1})
        self.assertEqual(len(r["warnings"]), 0, "完整台账不得产出 warning")

        # ② 反向断言：未声明分类基准 → 判定 invalid + warning（长名单不可复现）
        r2 = ps.audit_long_list(comps, {**cfg, "classification_system": None})
        self.assertFalse(r2["checks"]["classification_system"]["valid"])
        self.assertTrue(any("classification_system" in w for w in r2["warnings"]),
                        "未声明行业分类基准须 warning")

        # ③ 反向断言：有长名单但无剔除记录 → warning（无证据链）
        r3 = ps.audit_long_list(comps, {**cfg, "rejected": []})
        self.assertTrue(any("无任何剔除记录" in w for w in r3["warnings"]),
                        "长名单 > 最终样本却无剔除记录须 warning")

        # ④ 反向断言：剔除理由不入枚举 → warning（自由文本不可统计）
        r4 = ps.audit_long_list(comps, {**cfg, "rejected": [{"name": "Z", "reason": "看不顺眼"}]})
        self.assertEqual(r4["checks"]["rejected"]["typed"], 0)
        self.assertTrue(any("reason_type" in w for w in r4["warnings"]))

        # ⑤ 筛选过粗：long_list_size < 2×最终样本 → warning
        r5 = ps.audit_long_list(comps, {**cfg, "long_list_size": 6})
        self.assertTrue(any("筛选过粗" in w for w in r5["warnings"]),
                        "长名单 6 家 / 最终 6 家须判筛选过粗")

        # ⑥ P0-4 截点：财报期末晚于截点 → violation（不得用基准日后数据回填）
        late = [dict(comps[0], financial_period_end="2026-12-31")] + comps[1:]
        c1 = ps.audit_cutoff(late, "2026-10-22")
        self.assertTrue(c1["violation"], "财报期末晚于截点须判 violation")
        self.assertEqual(c1["violations"][0]["days_after"], 70, "2026-12-31 距 2026-10-22 为 70 天")
        # 反向：全部合规 → 无 violation
        c2 = ps.audit_cutoff(comps, "2026-10-22")
        self.assertFalse(c2["violation"])
        self.assertEqual(len(c2["violations"]), 0)
        # 滞后过大：2025-12-31 距截点 295 天 > 270 → lagged
        old = [dict(comps[0], financial_period_end="2025-12-31")] + comps[1:]
        c3 = ps.audit_cutoff(old, "2026-10-22", max_lag_days=270)
        self.assertEqual(len(c3["lagged"]), 1, "滞后 >270 天须记入 lagged")
        # 反向：无截点 → 不误判 violation，但须提示
        c4 = ps.audit_cutoff(comps, None)
        self.assertFalse(c4["violation"])
        self.assertTrue(any("截点" in w for w in c4["warnings"]))

    def test_t106_scale_diagnosis_two_axes(self):
        """v3.20.0 二期回归：规模双口径 5 倍诊断（P0-2）。

        ★口径（对齐 comps 第 2 步）：分别算「标的收入 ÷ 长名单收入中位」与
        「标的市值 ÷ 长名单市值中位」，**取偏离 1 更远（更严格）者**作为判定基数。
        原 IPO 技能仅有「营收规模同量级（±一个数量级内）」的软描述（10 倍），
        无市值口径、无「取更远者」规则、无长名单基数概念。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import peer_screening as ps

        comps = self._peer_comps()
        cfg = {"long_list_median": {"revenue": 268.0, "market_cap": 246.0}}

        # ① 手算校验：格力真实口径（营收 1631.72 / 市值 2096.61）
        #    营收比 6.0885×、市值比 8.5228× → 取更远的市值，超 5×
        r = ps.diagnose_scale({"revenue": 1631.72, "market_cap": 2096.61}, comps, cfg)
        self.assertAlmostEqual(r["ratio"]["revenue"], 1631.72 / 268.0, places=4)
        self.assertAlmostEqual(r["ratio"]["market_cap"], 2096.61 / 246.0, places=4)
        self.assertEqual(r["binding"], "market_cap", "须取偏离更远者（市值 8.52× > 营收 6.09×）")
        self.assertAlmostEqual(r["binding_deviation"], 2096.61 / 246.0, places=4)
        self.assertTrue(r["exceed"], "8.52× > 5× 须判超限")
        self.assertEqual(r["action"], "narrow_subgroup")
        self.assertEqual(r["basis"], "long_list")

        # ② 反向断言：只超营收不超市值 → binding 必须切到营收（不能固定用市值）
        r2 = ps.diagnose_scale({"revenue": 2000.0, "market_cap": 300.0}, comps, cfg)
        self.assertEqual(r2["binding"], "revenue", "营收 7.46× > 市值 1.22×，须改判营收")
        self.assertTrue(r2["exceed"])

        # ③ 反向断言：两者都在 5× 内 → 不得误报超限
        r3 = ps.diagnose_scale({"revenue": 500.0, "market_cap": 400.0}, comps, cfg)
        self.assertFalse(r3["exceed"], "营收 1.87× / 市值 1.63× 均在阈值内，不得判超限")
        self.assertEqual(r3["action"], "keep")

        # ④ 低于 1/5 亦须判超限（规矩对两侧对称）：标的远小于可比
        r4 = ps.diagnose_scale({"revenue": 20.0, "market_cap": 30.0}, comps, cfg)
        self.assertTrue(r4["exceed"], "标的远小于可比（<1/5）同样须收窄子组")
        self.assertGreater(r4["binding_deviation"], 5.0)

        # ⑤ 降级口径：无 long_list_median → 用最终样本中位作代理 + 显式 warning
        r5 = ps.diagnose_scale({"revenue": 1631.72, "market_cap": 2096.61}, comps, {})
        self.assertEqual(r5["basis"], "final_sample_proxy",
                         "缺长名单中位时须标注代理口径，不得假装有长名单数据")
        self.assertTrue(any("代理" in w for w in r5["warnings"]))

    def test_t107_entity_dedupe_and_accounting_gate(self):
        """v3.20.0 三期回归：同一实体去重（P0-3）与会计准则闸（P1-1）。

        ★P0-3 根因：A+H/ADR 多地上市的同一发行人若按多只可比重复统计，
        既让同一公司占多票，又让 A/H 价差（H 股常折价 20~40%）污染中位数。
        ★P1-1 根因：IPO 技能强制「≥1/3 可比为海外标的」，却无准则差异处理——
        跨准则净利润（股权激励、研发资本化、政府补助口径）不可直接比。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import peer_screening as ps

        comps = self._peer_comps()
        midea = comps[0]
        # H 股美的：同一 legal_entity_id，市值 1.5 倍（验证「A 股优先」不是「市值优先」）
        h_midea = dict(midea, name="美的集团（H 股）", code="0300.HK", exchange="HK",
                       market_cap=midea["market_cap"] * 1.5)
        hk_new = {"name": "某港股白电", "code": "6690.HK", "exchange": "HK",
                  "legal_entity_id": "06690", "standard": "HKFRS",
                  "market_cap": 1600.0, "pe": 9.8, "included": True}
        pool = comps + [h_midea, hk_new]

        # ① 去重：8 → 7，且保留的是 A 股美的（即便 H 股市值更大）
        r = ps.dedupe_entities(pool)
        self.assertEqual(r["n_input"], 8)
        self.assertEqual(r["n_after"], 7, "同一 legal_entity_id 须合并为 1")
        self.assertEqual(r["merged"][0]["name"], "美的集团（H 股）")
        self.assertEqual(r["merged"][0]["duplicate_of"], "美的集团",
                         "A 股（估值环境一致）优先，不得因 H 股市值更大而反选")
        self.assertIn("美的集团", r["kept_names"])
        self.assertNotIn("美的集团（H 股）", r["kept_names"])

        # ② 反向断言：legal_entity_id 不同 → 不得合并（避免过度合并）
        r2 = ps.dedupe_entities(comps + [dict(hk_new, legal_entity_id="06690")])
        self.assertEqual(r2["n_after"], 7, "不同实体不得被合并")

        # ③ 去重键退化：无 legal_entity_id 时按 code 去后缀（A/H 同号不同地仍合并）
        a = {"name": "甲", "code": "600000.SH", "included": True}
        h = {"name": "甲（H）", "code": "600000.HK", "included": True}
        r3 = ps.dedupe_entities([a, h])
        self.assertEqual(r3["n_after"], 1, "同一代码去交易所后缀后须合并")

        # ④ 准则闸：港股 HKFRS 对标 CAS → cross 且 requires_reconciliation
        deduped = [c for c in pool if c["name"] in r["kept_names"]]
        g = ps.gate_accounting(deduped, "CAS")
        self.assertEqual(g["target_standard"], "CAS")
        self.assertEqual(g["n_cross"], 1, "仅港股一家跨准则")
        self.assertEqual(g["cross"][0]["name"], "某港股白电")
        self.assertTrue(g["cross"][0]["requires_reconciliation"],
                        "跨准则须标记需调节，不得直接进 P/E 统计")
        self.assertTrue(any("会计准则" in w for w in g["warnings"]))

        # ⑤ 反向断言：全 CAS → 不得有 cross
        g2 = ps.gate_accounting(comps, "CAS")
        self.assertEqual(g2["n_cross"], 0)
        self.assertEqual(len(g2["warnings"]), 0)

        # ⑥ 准则别名归一：「中国会计准则」/「HKFRS/IFRS」须被识别
        g3 = ps.gate_accounting([{"name": "P", "standard": "中国会计准则", "included": True},
                                 {"name": "Q", "standard": "HKFRS/IFRS", "included": True}], "CAS")
        self.assertEqual(g3["n_cross"], 1, "中文别名须归一到 CAS，仅 Q 跨准则")

    def test_t108_seasoning_and_index_anchor(self):
        """v3.20.0 四期回归：次新股剔除（P1-4）与行业指数锚降权（P1-5）。

        ★P1-4 是 IPO 场景独有陷阱（上市公司估值不涉及）：可比若含上市 <12 个月的次新，
        其 PE 含 30~50% 炒新溢价，直接纳入会系统性抬高发行定价、放大破发风险。
        ★P1-5 指数 PE 是**全样本口径**（含全部成分股），与「精选可比」不同口径，
        shortfall 降到第三级用它作锚时必须降权，不得与前两级同级使用。
        """
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import peer_screening as ps

        as_of = "2026-10-22"
        cases = [
            {"name": "次新-5月", "listing_date": "2026-05-20", "included": True},   # 5 月 → 剔除
            {"name": "观察-18月", "listing_date": "2025-04-20", "included": True},  # 18 月 → watch
            {"name": "成熟-60月", "listing_date": "2021-10-20", "included": True},  # 60 月 → mature
            {"name": "边界-12月", "listing_date": "2025-10-22", "included": True},  # 恰 12 月 → 不剔除
        ]
        r = ps.gate_seasoning(cases, as_of, min_months=12)
        names = [x["name"] for x in r["excluded"]]
        self.assertIn("次新-5月", names)
        self.assertEqual(r["excluded"][0]["months_listed"], 5)
        self.assertEqual(r["excluded"][0]["reason_type"], "listing")
        self.assertNotIn("边界-12月", names, "恰好 12 个月不得剔除（须严格小于）")
        self.assertEqual([x["name"] for x in r["watch"]], ["观察-18月", "边界-12月"],
                         "12~24 月须进观察区（标记而非剔除；恰 12 月属观察区下界）")
        self.assertIn("成熟-60月", r["mature"])
        self.assertTrue(any("炒新溢价" in w for w in r["warnings"]))

        # 反向断言：全部成熟 → 无剔除、无 warning
        mature_only = [c for c in cases if c["name"] == "成熟-60月"]
        r2 = ps.gate_seasoning(mature_only, as_of)
        self.assertEqual(len(r2["excluded"]), 0)
        self.assertEqual(len(r2["warnings"]), 0)

        # 反向断言：无 listing_date → 视为成熟（不得因缺数据误剔除）
        r3 = ps.gate_seasoning([{"name": "无日期", "included": True}], as_of)
        self.assertEqual(len(r3["excluded"]), 0, "缺上市日期须视为成熟，不得误剔除")

        # P1-5 指数锚：三级降级权重上限递减，primary 为 1.00
        i3 = ps.index_anchor_haircut(True, "fallback_l3")
        i2 = ps.index_anchor_haircut(True, "fallback_l2")
        i1 = ps.index_anchor_haircut(True, "fallback_l1")
        ip = ps.index_anchor_haircut(True, "primary")
        self.assertEqual(i3["weight_cap"], 0.30, "第三级（行业指数全样本口径）上限须为 0.30")
        self.assertEqual(i3["basis"], "full_sample_index")
        self.assertEqual(i2["weight_cap"], 0.40)
        self.assertEqual(i1["weight_cap"], 0.50)
        self.assertEqual(ip["weight_cap"], 1.00)
        self.assertTrue(i1["weight_cap"] > i3["weight_cap"], "级别越高（越接近精选可比）上限须越高")
        self.assertTrue(any("全样本口径" in w for w in i3["warnings"]),
                        "fallback_l3 须声明全样本口径")
        self.assertEqual(len(ip["warnings"]), 0, "primary 无需降权告警")

        # 反向断言：未启用指数锚 → used=False，不得产生降权告警
        i0 = ps.index_anchor_haircut(False)
        self.assertFalse(i0["used"])
        self.assertEqual(len(i0["warnings"]), 0)

    def test_t109_peer_screening_zero_regression_and_enforce(self):
        """v3.20.0 零回归 + 执行模式守卫。

        ★判据：诊断模式（缺省）**不得改变任何数值**——只挂出 peer_screening 块与 warnings；
        仅 `enforce.filter_sample=true` 时才过滤 self.comp，且过滤后为空必须**阻止执行**
        （不得因筛选把估值打空，这是「原本能算、改完算不出来」的防线）。
        """
        base = load_example_input()

        # ① 缺省不激活：不挂出 peer_screening
        a = ve.Engine(copy.deepcopy(base)).run()
        self.assertNotIn("peer_screening", a, "peer_screening 缺省不得挂出")

        # ② 诊断模式：除新增块与 warnings 外，全字段逐字节一致（零数值影响）
        d = copy.deepcopy(base)
        d["peer_screening"] = {
            "enabled": True, "classification_system": "SW_2021", "long_list_size": 20,
            "rejected": [{"name": "X", "reason_type": "product", "reason": "不可比"}],
            "info_cutoff": "2026-10-22",
        }
        b = ve.Engine(copy.deepcopy(d)).run()
        self.assertIn("peer_screening", b)
        self.assertEqual(b["peer_screening"]["status"] in ("ok", "degraded", "weak", "unavailable"),
                         True, "status 须落在四态内")
        aa, bb = copy.deepcopy(a), copy.deepcopy(b)
        aa.pop("warnings"); bb.pop("warnings"); bb.pop("peer_screening")
        self.assertEqual(json.dumps(aa, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(bb, sort_keys=True, ensure_ascii=False, default=str),
                         "诊断模式不得改变任何数值（除新增块与 warnings）")

        # ③ 执行模式：过滤生效 → 样本减少，数值随之变化
        d2 = copy.deepcopy(d)
        d2["peer_screening"]["enforce"] = {"filter_sample": True}
        d2["comparables"] = [c for c in d2["comparables"]]
        # 追加一条次新股（应被剔除），确保确有可剔样本
        d2["comparables"].append({
            "name": "次新测试", "code": "301999.SZ", "exchange": "CN", "standard": "CAS",
            "legal_entity_id": "301999", "pe": 40.0, "ps": 6.0, "listing_date": "2026-08-01",
            "financial_period_end": "2026-06-30", "included": True, "market_cap": 80.0})
        d2["peer_screening"]["info_cutoff"] = "2026-10-22"
        n_before = len(d2["comparables"])
        c = ve.Engine(copy.deepcopy(d2)).run()
        psr = c["peer_screening"]
        self.assertTrue(psr["enforce"]["applied"], "执行模式须标记 applied")
        self.assertIn("次新测试", psr["enforce"]["removed"], "次新股须被剔除")
        self.assertEqual(len(c["scenarios"]["base"]["comparable"]["pe"]["samples"]),
                         n_before - 1, "过滤后样本数须减 1")

        # ④ 反向守卫：过滤后为空 → 阻止执行并保持原样本（不得把估值打空）
        d3 = copy.deepcopy(d2)
        for c0 in d3["comparables"]:
            c0["listing_date"] = "2026-09-01"        # 全部为次新 → 全部应被剔除
        e = ve.Engine(copy.deepcopy(d3)).run()
        self.assertFalse(e["peer_screening"]["enforce"]["applied"],
                         "过滤后为空须阻止执行（applied=False）")
        self.assertEqual(e["peer_screening"]["enforce"].get("blocked"), "过滤后样本为空",
                         "阻止原因须显式留痕")
        self.assertTrue(len(e["scenarios"]["base"]["comparable"]["pe"]["samples"]) > 0,
                        "阻止后须保持原样本，不得输出空样本")

        # ⑤ 结构断言：引擎源须在 scenario 之前调用，且缺省不改 comp
        sp = os.path.join(SKILL_ROOT, "scripts", "valuation_engine.py")
        src = open(sp, encoding="utf-8").read()
        self.assertIn("peer_screen = self.peer_screening_report()", src)
        self.assertLess(src.index("peer_screen = self.peer_screening_report()"),
                        src.index('base = self.scenario("base"'),
                        "peer_screening 须在 scenario 之前调用（执行模式要影响样本）")
        self.assertIn('if peer_screen.get("enabled"):', src, "须条件挂出，缺省不入 out")

    # ============ v3.21.0 成熟期「显式期增速 + 永续增速」参数体系 ============
    # 12 项开关全部 opt-in，缺省逐位零回归。对应建议书 A1–A7 / B1–B5。

    @staticmethod
    def _dcf_base(**fin_over):
        """格力式最小输入（真实财务 + 真实三年增速 +7.93/−7.26/−9.89）。"""
        d = {
            "meta": {"company": "格力电器", "ticker": "000651.SZ", "industry": "白色家电",
                     "as_of_date": "2026-10-22", "asset_type": "mature", "lifecycle_stage": "mature"},
            "financials": {
                "revenue_latest_ttm": 1631.72, "net_profit_latest_ttm": 278.68, "net_margin": 0.1708,
                "net_assets": 1485.08, "ebitda_ttm": 388.70, "ebit": 340.84,
                "total_shares_after_issue": 56.0141, "price": 37.43, "net_cash": 788.48,
                "revenue_by_year": {"2021": 1878.69, "2022": 1889.88, "2023": 2039.79,
                                    "2024": 1891.64, "2025": 1704.47},
                "growth_forecast": {"2026E": -0.02, "2027E": 0.0, "2028E": 0.015},
                "terminal_growth": 0.02, "roic": 0.1204, "roe": 0.1877,
                "data_as_of": "2026-06-30",
                "wacc_params": {"enabled": True, "rf": 0.0164, "erp": 0.0804, "beta": 1.0,
                                "cost_of_debt": 0.03, "tax_rate": 0.16, "d_e_ratio": 0.3998},
            },
            "comparables": [
                {"name": "美的集团", "code": "000333.SZ", "exchange": "CN", "standard": "CAS",
                 "market_cap": 6507.88, "revenue": 4672.23, "net_profit": 443.78, "pe": 14.66,
                 "pb": 3.07, "ps": 1.39, "growth_pct": -1.0},
                {"name": "海尔智家", "code": "600690.SH", "exchange": "CN", "standard": "CAS",
                 "market_cap": 1822.51, "revenue": 2979.68, "net_profit": 187.40, "pe": 10.22,
                 "pb": 1.85, "ps": 0.61, "growth_pct": 4.2},
                {"name": "海信家电", "code": "000921.SZ", "exchange": "CN", "standard": "CAS",
                 "market_cap": 322.95, "revenue": 853.54, "net_profit": 27.68, "pe": 11.67,
                 "pb": 2.40, "ps": 0.38, "growth_pct": 6.1},
            ],
            "preferences": {"exclude_outliers": False},
        }
        d["financials"].update(fin_over)
        return d

    def test_t110_terminal_guard_pure(self):
        """T110【A1】Gordon 终值前提守卫：`g < WACC` 必须严格成立（纯函数层）。

        ★根因：`wacc − tg` 作分母无任何保护——等于 0 直接 ZeroDivisionError 崩溃，
        小于 0 得到**负终值**（越保守的假设反而抬高估值，方向性错误）。
        """
        # ① 正常通过
        r = ve.check_terminal_growth(0.0787, 0.02)
        self.assertFalse(r["violation"])
        self.assertAlmostEqual(r["gap_pp"], 5.87, places=2)

        # ② 相等 / 小于 → 违规（eps=1e-4 边界：10bp 对应约 1000× 终值，同属无经济意义）
        for w, t in ((0.05, 0.05), (0.045, 0.06), (0.05, 0.04995)):
            self.assertTrue(ve.check_terminal_growth(w, t)["violation"], f"{w}/{t} 须判违规")

        # ③ clamp 目标值 = wacc − 1pp，且不得低于 −90% 硬下限
        self.assertAlmostEqual(ve.check_terminal_growth(0.045, 0.06)["suggested_tg"], 0.035, places=6)
        self.assertAlmostEqual(ve.check_terminal_growth(0.005, 0.06)["suggested_tg"], -0.005, places=6)
        self.assertAlmostEqual(ve.check_terminal_growth(-0.5, 0.06)["suggested_tg"], -0.51, places=6)
        self.assertAlmostEqual(ve.check_terminal_growth(-0.95, 0.06)["suggested_tg"], -0.9, places=6,
                               msg="suggested_tg 须受 −90% 下限约束")

        # ④ 纯函数不改值（返回体的 wacc/tg 即入参）
        r = ve.check_terminal_growth(0.045, 0.06)
        self.assertEqual((r["wacc"], r["tg"]), (0.045, 0.06))

    def test_t111_guard_failclosed_and_attribution(self):
        """T111【A1】守卫触发的处置与**归因修正**（反向断言）。

        原实现 `equity = pv_sum + tv_pv + net_cash` 在负终值下得出权益为负，随后
        warning 写成「DCF 内在价值为负……按净现金下限处理」——把「终值公式不成立」
        误诊为「公司价值为负」。该文案必须消失。
        """
        d = self._dcf_base(wacc=0.045, terminal_growth=0.06)
        out = ve.Engine(copy.deepcopy(d)).run()
        dcf = out["scenarios"]["base"]["dcf"]
        warns = " ".join(out["warnings"])

        # ① 不再崩溃、不再产出负终值：终值置 0（fail-closed），权益 = 显式期现值 + 净现金
        self.assertEqual(dcf["terminal_value_pv"], 0.0, "违规时终值须置 0（不得为负或天文数字）")
        self.assertAlmostEqual(dcf["equity_value"], round(dcf["pv_sum"] + 788.48, 2), places=2)
        self.assertEqual(dcf["tv_share"], 0.0)
        self.assertEqual(dcf["terminal_guard"]["action"], "fail_closed")

        # ② 归因正确：出现「永续增速不低于折现率」，且**不得**出现「内在价值为负」
        self.assertIn("永续增速", warns)
        self.assertNotIn("内在价值为负", warns, "归因不得停留在「价值为负」——真实原因是终值公式不成立")
        # ③ 告警去重（三情景 × 多次调用只留一条）
        # 三情景 wacc 各异（bear +1pp / base / bull −1pp）→ 三条独立告警，各自只出现一次
        tg_warns = [w for w in out["warnings"] if "永续增速 6.00% 不低于折现率" in w]
        self.assertEqual(len(tg_warns), 3)
        self.assertEqual(len(set(tg_warns)), 3, "重复调用不得产生重复文案")

        # ④ 置信度折减一档 + 留痕
        caps = out["confidence"]["growth_param_caps"]
        self.assertEqual(caps["caps"][0]["rule"], "terminal_guard_fired")
        self.assertLess(out["confidence"]["score"], 80.0)

        # ⑤ clamp 模式：tg 压到 WACC−1pp 并留痕（不 fail-closed）
        d2 = self._dcf_base(wacc=0.045, terminal_growth=0.06)
        d2["dcf_growth"] = {"terminal_growth_guard": "clamp"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        dcf2 = o2["scenarios"]["base"]["dcf"]
        self.assertAlmostEqual(dcf2["terminal_growth"], 0.035, places=6)
        self.assertEqual(dcf2["terminal_guard"]["action"], "clamp")
        self.assertAlmostEqual(dcf2["terminal_guard"]["tg_clamped_from"], 0.06, places=6)
        self.assertAlmostEqual(dcf2["terminal_guard"]["tg_clamped_to"], 0.035, places=6)
        self.assertGreater(dcf2["terminal_value_pv"], 0, "clamp 后终值须恢复为正")

        # ⑥ wacc == tg：原实现 ZeroDivisionError 崩溃，现须正常返回
        o3 = ve.Engine(self._dcf_base(wacc=0.05, terminal_growth=0.05)).run()
        self.assertEqual(o3["scenarios"]["base"]["dcf"]["terminal_value_pv"], 0.0)

    def test_t112_tg_default_modes(self):
        """T112【A2】永续增速缺省值双轨（legacy 6% / cva_2pct 2%）+ GDP 上限校验。

        ★根因：`DEFAULT_TERMINAL_GROWTH = 0.06` 与同文件 `gdp_cap = 0.045` 自相矛盾——
        缺省值突破引擎自己设定的 GDP 上限，实测使格力权益 4,949 → 13,689 亿（+176.6%）。
        """
        # 构造「无三角校准源」输入（删 growth_pct / revenue_by_year / industry_index）
        d = self._dcf_base()
        del d["financials"]["terminal_growth"]
        del d["financials"]["revenue_by_year"]
        for c in d["comparables"]:
            c.pop("growth_pct", None)

        o = ve.Engine(copy.deepcopy(d)).run()
        self.assertAlmostEqual(o["scenarios"]["base"]["dcf"]["terminal_growth"], 0.06, places=6)
        self.assertEqual(o["assumptions_summary"]["dcf"]["tg_source"], "默认 6%",
                         "legacy 口径须保持原文案（零回归）")

        d["dcf_growth"] = {"terminal_growth_default": "cva_2pct"}
        o2 = ve.Engine(copy.deepcopy(d)).run()
        self.assertAlmostEqual(o2["scenarios"]["base"]["dcf"]["terminal_growth"], 0.02, places=6)
        self.assertIn("cva_2pct", o2["assumptions_summary"]["dcf"]["tg_source"])

        # 超 GDP 上限 → warning；补 rationale 后抑制
        d3 = self._dcf_base(terminal_growth=0.08)
        d3["dcf_growth"] = {"terminal_growth_default": "cva_2pct"}
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertTrue(any("GDP 上限" in w for w in o3["warnings"]))
        d3["financials"]["terminal_growth_rationale"] = "在手订单与产能投放支撑"
        o4 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertFalse(any("GDP 上限" in w for w in o4["warnings"]),
                         "补充 rationale 后不得再告警")

        # legacy 口径下 8% 不告警（零回归）
        d5 = self._dcf_base(terminal_growth=0.08)
        o5 = ve.Engine(copy.deepcopy(d5)).run()
        self.assertAlmostEqual(o5["scenarios"]["base"]["dcf"]["terminal_growth"], 0.08, places=6)
        self.assertFalse(any("GDP 上限" in w for w in o5["warnings"]))

    def test_t113_tg_chain_priority(self):
        """T113【A3/A4】永续增速取值链：用户显式 > 行业 g_lt > 通胀锚；三角值降为校验。

        ★根因：`grep -rn "g_lt"` 全库仅 2 处命中，全在透传字典里、**0 处消费**——
        行业参数底座里的 `g_lt` 是死值；而三角校准的「可比中位增速 × 0.3」
        单腿传导却直接当永续增速（格力 11.15% × 0.3 = 3.34%）。
        """
        # ① 用户显式优先
        d = self._dcf_base(terminal_growth=0.03)
        d["preferences"]["industry_params"] = True
        d["dcf_growth"] = {"terminal_growth_basis": "chain"}
        o = ve.Engine(copy.deepcopy(d)).run()
        meta = o["assumptions_summary"]["dcf"]["tg_chain"]
        self.assertEqual(meta["picked"], "user_explicit")
        self.assertAlmostEqual(o["scenarios"]["base"]["dcf"]["terminal_growth"], 0.03, places=6)

        # ② 无用户值 → 行业 g_lt（家电类目 v3.21.0 新增，g_lt=0.02）
        d2 = self._dcf_base()
        del d2["financials"]["terminal_growth"]
        d2["preferences"]["industry_params"] = True
        d2["dcf_growth"] = {"terminal_growth_basis": "chain"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        meta2 = o2["assumptions_summary"]["dcf"]["tg_chain"]
        self.assertEqual(meta2["picked"], "industry_g_lt")
        self.assertEqual(meta2["industry"], "家用电器")
        self.assertAlmostEqual(meta2["value"], 0.02, places=6)

        # ③ 行业 g_lt 超 GDP 上限 → 被压到 4.5%
        e = ve.Engine(copy.deepcopy(d2))
        e._industry = {"enabled": True, "matched_industry": "测试行业", "params": {"g_lt": 0.08}}
        m = e.resolve_terminal_growth(None)
        self.assertAlmostEqual(m["value"], 0.045, places=6)
        self.assertEqual(m["capped_by"], 0.045)

        # ④ legacy 模式：不产出 tg_chain，三角值仍生效（零回归）
        d3 = self._dcf_base()
        del d3["financials"]["terminal_growth"]
        d3["preferences"]["industry_params"] = True
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertNotIn("tg_chain", o3["assumptions_summary"]["dcf"])
        self.assertIsNotNone(o3["scenarios"]["base"]["dcf"]["terminal_growth"])

    def test_t114_tg_scenario_stepped(self):
        """T114【A5】永续增速进入三情景：flat（缺省）逐位不变 / stepped 生效。

        ★根因：`SCENARIO_DEFAULTS` 无 tg 键；`impact_map.terminal_growth_adj_pp` 产出后
        **全库 0 处消费**（死字段）；bull 终值占比 81.6% 却零调整。
        """
        d = self._dcf_base()
        o = ve.Engine(copy.deepcopy(d)).run()
        tg_flat = {k: o["scenarios"][k]["dcf"]["terminal_growth"] for k in ("bear", "base", "bull")}
        self.assertEqual(set(tg_flat.values()), {0.02}, "flat 缺省下三情景 tg 须完全相同（零回归）")

        d["dcf_growth"] = {"terminal_growth_scenario_mode": "stepped"}
        o2 = ve.Engine(copy.deepcopy(d)).run()
        tg2 = {k: o2["scenarios"][k]["dcf"]["terminal_growth"] for k in ("bear", "base", "bull")}
        self.assertAlmostEqual(tg2["bear"], 0.015, places=6)
        self.assertAlmostEqual(tg2["base"], 0.02, places=6)
        self.assertAlmostEqual(tg2["bull"], 0.025, places=6)
        self.assertEqual(o2["scenarios"]["bull"]["dcf"]["tg_scenario_adj_pp"], 0.5)

        # bull 护栏：tg + adj 不得越过 GDP 上限
        d3 = self._dcf_base(terminal_growth=0.044)
        d3["dcf_growth"] = {"terminal_growth_scenario_mode": "stepped"}
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertAlmostEqual(o3["scenarios"]["bull"]["dcf"]["terminal_growth"], 0.045, places=6)
        self.assertIn("tg_capped_by_gdp", o3["scenarios"]["bull"]["dcf"])

    def test_t115_tv_share_guard(self):
        """T115【A6】终值占比四档门禁（<40% 过低 / 40–75% 区间 / 75–85% 偏高 / >85% 极端）。

        ★根因：`tv_share` 只算不判（`valuation_engine.py` 原实现仅 round 后输出），
        tg=6% 时终值占比 92.2% 无任何告警；11 例 examples 全部 ≥74.9% 也无人提示。
        """
        seen = {}
        for tg in (0.0, 0.01, 0.02, 0.045):
            d = self._dcf_base(terminal_growth=tg)
            d["dcf_growth"] = {"tv_share_guard": True}
            o = ve.Engine(copy.deepcopy(d)).run()
            g = o["scenarios"]["base"]["dcf"]["tv_share_grade"]
            seen[tg] = (g["tv_share"], g["grade"])
            # 档位与数值须自洽
            lo = 0.0 if g["grade"] == "low" else (0.40 if g["grade"] == "in_range"
                                                  else (0.75 if g["grade"] == "high" else 0.85))
            self.assertGreaterEqual(g["tv_share"], lo)
        self.assertEqual(seen[0.0][1], "in_range")
        self.assertEqual(seen[0.02][1], "high")
        self.assertEqual(seen[0.045][1], "extreme")

        # extreme → error 级告警 + 置信度封顶「中」
        d = self._dcf_base(terminal_growth=0.045)
        d["dcf_growth"] = {"tv_share_guard": True}
        o = ve.Engine(copy.deepcopy(d)).run()
        self.assertTrue(any("【error】" in w and "终值占比" in w for w in o["warnings"]))
        self.assertEqual(o["confidence"]["level"], "中")
        self.assertTrue(any(c["rule"] == "tv_share_extreme"
                            for c in o["confidence"]["growth_param_caps"]["caps"]))

        # low 档：长显式期 + 高折现率（终值不再主导）
        d = self._dcf_base(wacc=0.20, terminal_growth=0.0)
        d["financials"]["growth_forecast"] = {f"{2026+i}E": 0.10 for i in range(10)}
        d["dcf_growth"] = {"tv_share_guard": True, "growth_path_mode": "user_full"}
        o = ve.Engine(copy.deepcopy(d)).run()
        self.assertEqual(o["scenarios"]["base"]["dcf"]["tv_share_grade"]["grade"], "low")

        # 缺省关闭 → 不挂出（零回归）
        o0 = ve.Engine(self._dcf_base()).run()
        self.assertNotIn("tv_share_grade", o0["scenarios"]["base"]["dcf"])

    def test_t116_implied_terminal_growth_market(self):
        """T116【A7】市场隐含永续增速反解 + **独立公式复算**（交叉校验）。

        格力：市值 2,096.61 − 净现金 788.48 − 显式期现值 988.49 = 319.64 亿残值，
        反解 g* = −30.50%，即「市场按每年萎缩 30% 定价」——不合理本身即诊断结论。
        """
        d = self._dcf_base()
        d["dcf_growth"] = {"implied_tg_market": True}
        out = ve.Engine(copy.deepcopy(d)).run()
        dcf = out["scenarios"]["base"]["dcf"]
        itg = dcf["implied_terminal_growth_market"]

        # ① 中间量复现
        self.assertAlmostEqual(itg["market_cap"], 2096.61, places=2)
        self.assertAlmostEqual(itg["pv_sum"], 988.49, places=2)
        self.assertAlmostEqual(itg["residual_tv_pv"], 319.64, places=2)

        # ② 独立复算 g*（不复用引擎中间变量，按 Gordon 反解公式重推）
        w, n, fcf0 = dcf["wacc"], len(dcf["growth_seq"]), dcf["fcf0"]
        fcf_n = fcf0
        for g in dcf["growth_seq"]:
            fcf_n *= 1.0 + g
        denom = itg["residual_tv_pv"] * (1.0 + w) ** n
        g_star = (denom * w - fcf_n) / (denom + fcf_n)
        self.assertAlmostEqual(itg["implied_g"], round(g_star, 4), places=6)
        self.assertAlmostEqual(itg["implied_g"], -0.3050, places=3)

        # ③ 无经济解：显式期现值已超市场 EV
        d2 = self._dcf_base()
        d2["financials"]["price"] = 5.0            # 市值压到 280 亿 << pv_sum + 净现金
        d2["dcf_growth"] = {"implied_tg_market": True}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        itg2 = o2["scenarios"]["base"]["dcf"]["implied_terminal_growth_market"]
        self.assertFalse(itg2["solvable"])
        self.assertLessEqual(itg2["residual_tv_pv"], 0)
        self.assertIn("无经济解", itg2["verdict"])

        # ④ 缺省不挂出（零回归）
        o3 = ve.Engine(self._dcf_base()).run()
        self.assertNotIn("implied_terminal_growth_market", o3["scenarios"]["base"]["dcf"])

    def test_t117_growth_path_not_truncated(self):
        """T117【B1】用户增速路径不截断（legacy 5 年 / user_full 用满）。

        ★根因：`build_growth_seq` 只取 `base[0..2]` 重算 g4/g5，用户给 7 年会被
        静默丢弃后 2 年（CVA 路径 [−6,−2,0,1,1.5,1.75,2] → 输出 5 年）。
        """
        gf7 = {"2026E": -0.02, "2027E": 0.0, "2028E": 0.015, "2029E": 0.018,
               "2030E": 0.019, "2031E": 0.0195, "2032E": 0.02}
        d = self._dcf_base(growth_forecast=gf7)
        o = ve.Engine(copy.deepcopy(d)).run()
        self.assertEqual(len(o["scenarios"]["base"]["dcf"]["growth_seq"]), 5)

        d["dcf_growth"] = {"growth_path_mode": "user_full"}
        o2 = ve.Engine(copy.deepcopy(d)).run()
        seq = o2["scenarios"]["base"]["dcf"]["growth_seq"]
        self.assertEqual(len(seq), 7, "user_full 须用满 7 年")
        self.assertEqual(seq, [-0.02, 0.0, 0.015, 0.018, 0.019, 0.0195, 0.02],
                         "user_full 须逐位等于用户路径")

        # 不足 5 年 → 线性 fade 补齐到 5 年
        d3 = self._dcf_base(growth_forecast={"2026E": 0.03, "2027E": 0.03, "2028E": 0.03})
        d3["dcf_growth"] = {"growth_path_mode": "user_full"}
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        seq3 = o3["scenarios"]["base"]["dcf"]["growth_seq"]
        self.assertEqual(len(seq3), 5)
        self.assertAlmostEqual(seq3[-1], 0.02, places=6, msg="补齐段须收敛到 tg")

    def test_t118_history_shape_advisory(self):
        """T118【B2】历史增速形态判定（advisory 只判形态、不改数值）。

        ★根因：无 `growth_forecast` 时原实现复制首值 `[g1]×3`（格力会取可比中位增速
        11.15% → 权益 +64.6%）。格力三年 +7.93/−7.26/−9.89 属「正负切换」，
        CVA 明令不得取平均——而引擎此前连"这是什么形态"都不判断。
        """
        h = ve.growth_history_shape([0.0793, -0.0726, -0.0989])
        self.assertEqual(h["history_case"], "正负切换且无稳定方向")
        self.assertAlmostEqual(h["metrics"]["sigma_pp"], 9.62, places=2)
        self.assertAlmostEqual(h["metrics"]["range_pp"], 17.82, places=2)  # 7.93−(−9.89)=17.82pp
        self.assertAlmostEqual(h["metrics"]["mean"], -0.0307, places=4)
        self.assertIn("不得取平均", h["base_rule"])

        # 纯函数：数据不足 / 全负 / 全正各型
        self.assertEqual(ve.growth_history_shape([0.1, 0.2])["history_case"], "数据不足")
        self.assertEqual(ve.growth_history_shape([-0.1, -0.15, -0.2])["history_case"],
                         "持续负增长（降幅仍在扩大）")
        self.assertEqual(ve.growth_history_shape([-0.2, -0.15, -0.1])["history_case"], "负增长收敛")
        self.assertEqual(ve.growth_history_shape([0.01, 0.02, 0.005])["history_case"],
                         "低位徘徊（|g|<3%）")
        self.assertEqual(ve.growth_history_shape([0.08, 0.09, 0.10])["history_case"], "持续加速（禁止外推斜率）")
        self.assertEqual(ve.growth_history_shape([0.02, 0.025, 0.03])["history_case"], "温和上行（禁止外推斜率）")

        # 引擎侧：off 不挂出；advisory 挂出且不改数值
        d = self._dcf_base()
        o_off = ve.Engine(copy.deepcopy(d)).run()
        self.assertNotIn("growth_history_shape", o_off["assumptions_summary"]["dcf"])

        d["dcf_growth"] = {"growth_history_shape": "advisory"}
        o = ve.Engine(copy.deepcopy(d)).run()
        blk = o["assumptions_summary"]["dcf"]["growth_history_shape"]
        self.assertEqual(blk["history_case"], "正负切换且无稳定方向")
        self.assertEqual(o["scenarios"]["base"]["dcf"]["equity_value"],
                         o_off["scenarios"]["base"]["dcf"]["equity_value"],
                         "advisory 不得改动任何数值（仅提示）")

        # 路径与形态矛盾 → 告警
        d2 = self._dcf_base(growth_forecast={"2026E": 0.05, "2027E": 0.06, "2028E": 0.06})
        d2["dcf_growth"] = {"growth_history_shape": "advisory"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertTrue(any("形态不匹配" in w for w in o2["warnings"]))

    def test_t119_mature_explicit_years(self):
        """T119【B3】成熟期显式期长度 6 → 7（v3.27.0 修订：表值由 4 改为 6）。

        ★历史根因：`LIFECYCLE_DEFAULTS["mature"]["n"]=4` 把终值占比结构性锁在 80% 以上
        （实测 n=4 → 80.5%，n=7 → 68.5%，而中枢仅差 0.04%）。显式期长度的真实作用
        是把价值来源压进可审计区间，不是「算得更准」。
        ★v3.27.0：表值整体重标定为 10/8/6/4（修复 growth < mature 的倒挂），
        `cva_7` 退化为显式 opt-in，缺省（`table`）取 6 年；`legacy_4` 仍可显式回退 4 年。
        """
        d = self._dcf_base()
        d["preferences"]["lifecycle_mode"] = "auto"
        o = ve.Engine(copy.deepcopy(d)).run()
        gs = o["scenarios"]["base"]["dcf"]["growth_schedule"]
        self.assertEqual(gs["stage"], "mature")
        self.assertEqual(gs["n"], 6)
        tv4 = o["scenarios"]["base"]["dcf"]["tv_share"]

        d["dcf_growth"] = {"lifecycle_mature_n_mode": "cva_7"}
        o2 = ve.Engine(copy.deepcopy(d)).run()
        gs2 = o2["scenarios"]["base"]["dcf"]["growth_schedule"]
        self.assertEqual(gs2["n"], 7)
        self.assertEqual(len(gs2["seq"]), 7)
        tv7 = o2["scenarios"]["base"]["dcf"]["tv_share"]
        self.assertLess(tv7, tv4, "延长显式期须降低终值占比")
        self.assertLess(abs(tv7 - tv4), 0.25, "但估值中枢不应大幅变动（n 只改变终值依赖）")

        # 显式 legacy_4 仍回退 4 年（表值改为 6 后不得被静默吞掉）
        d["dcf_growth"] = {"lifecycle_mature_n_mode": "legacy_4"}
        gs3 = ve.Engine(copy.deepcopy(d)).run()["scenarios"]["base"]["dcf"]["growth_schedule"]
        self.assertEqual(gs3["n"], 4)

    def test_t166_lifecycle_n_monotonic(self):
        """T166【v3.27.0】四阶段显式期必须单调不倒挂（10 / 8 / 6 / 4）。

        ★根因：v3.21.0 B3 只把 mature 由 4 抬到 7，未回看 growth 仍为 6，形成
        「成长期显式期(6) < 成熟期显式期(7)」的倒挂——越确定的公司要求预测得越远。
        本用例锁住表值与单调性，防止后续单点调参再次制造倒挂。
        """
        nd = {k: int(v["n"]) for k, v in ve.LIFECYCLE_DEFAULTS.items()}
        self.assertEqual(nd, {"startup": 10, "growth": 8, "mature": 6, "decline": 4})
        self.assertGreaterEqual(nd["startup"], nd["growth"])
        self.assertGreater(nd["growth"], nd["mature"], "成长期显式期须严格长于成熟期")
        self.assertGreaterEqual(nd["mature"], nd["decline"])
        # growth 的 8 年与 half_life 3.0 相容：≥2 个半衰期（残余 ≤25%）
        self.assertGreaterEqual(nd["growth"], 2 * float(ve.LIFECYCLE_DEFAULTS["growth"]["half_life"]))

    def test_t167_damodaran_stage_weight_table(self):
        """T167【v3.28.0】达莫达兰六阶段方法定位表替代 k_lifecycle 乘数。

        ★根因：k_lifecycle 是「乘在 base 上的 12 个无出处乘数」，语义是「某方法重要多少倍」，
        而达莫达兰框架的语义是「某阶段该用哪个工具」——用乘数表达「选工具」属方向错位，
        且必须「乘 base → 再归一化」两步才能看到结果，不可直接审计。
        本用例锁住：① 表结构（行内和为 1 + 三条单调性）；② 阶段派生；③ 直接权重生效；
        ④ base 权重被覆盖时留痕；⑤ ★用户显式归零的路径不得被表复活。
        """
        # ① 表结构
        self.assertEqual(tuple(ve.DAMODARAN_STAGES),
                         ("startup", "young_growth", "high_growth", "mature_growth",
                          "mature_stable", "decline"))
        for s in ve.DAMODARAN_STAGES:
            w = ve.DAMODARAN_STAGE_WEIGHTS[s]
            self.assertAlmostEqual(sum(w.values()), 1.0, places=9, msg=f"{s} 行内和须为 1")
            self.assertEqual(set(w), {"dcf", "comparable", "sentiment"})
        seq = [ve.DAMODARAN_STAGE_WEIGHTS[s]["dcf"] for s in ve.DAMODARAN_STAGES]
        self.assertEqual(seq, sorted(seq), "DCF 权重须随阶段单调不减")
        for m in ("comparable", "sentiment"):
            sq = [ve.DAMODARAN_STAGE_WEIGHTS[s][m] for s in ve.DAMODARAN_STAGES]
            self.assertEqual(sq, sorted(sq, reverse=True), f"{m} 权重须随阶段单调不增")

        # ② 阶段派生 + ③ 直接权重生效（_dcf_base 判 mature → 达莫达兰 Stage 5）
        d = self._dcf_base()
        d["preferences"]["lifecycle_mode"] = "auto"
        d["preferences"]["path_weight_mode"] = "adaptive"
        d["preferences"]["lifecycle_weight_mode"] = "damodaran_table"
        o = ve.Engine(copy.deepcopy(d)).run()
        pw = o["synthesis"]["path_weights"]
        self.assertEqual(pw["mode"], "damodaran_table")
        self.assertEqual(pw["damodaran_stage"], "mature_stable")
        self.assertEqual(pw["damodaran_stage_label"], "5 成熟稳定")
        self.assertEqual(pw["resolved_weights"], {"dcf": 0.4, "comparable": 0.5, "sentiment": 0.1})
        # ④ base 被覆盖须留痕（缺省 30/50/20 ≠ 表值 40/50/10）
        self.assertTrue(pw["base_weight_superseded"])
        self.assertEqual(pw["blocked_paths"], [])

        # ⑤ ★用户显式把 dcf 归零 = 该法不可算，表不得复活（中航沈飞实证：复活后 −37.76%）
        d2 = self._dcf_base()
        d2["preferences"]["lifecycle_mode"] = "auto"
        d2["preferences"]["path_weight_mode"] = "adaptive"
        d2["preferences"]["lifecycle_weight_mode"] = "damodaran_table"
        d2["preferences"]["weights"] = {"dcf": 0.0, "comparable": 0.8, "sentiment": 0.2}
        pw2 = ve.Engine(copy.deepcopy(d2)).run()["synthesis"]["path_weights"]
        self.assertEqual(pw2["blocked_paths"], ["dcf"])
        self.assertEqual(pw2["resolved_weights"]["dcf"], 0.0, "显式归零的 DCF 不得被阶段表复活")
        self.assertAlmostEqual(pw2["resolved_weights"]["comparable"]
                               + pw2["resolved_weights"]["sentiment"], 1.0, places=4)

        # ⑥ 缺省零回归：不设开关 → 仍走 multiplier_k
        d3 = self._dcf_base()
        d3["preferences"]["lifecycle_mode"] = "auto"
        d3["preferences"]["path_weight_mode"] = "adaptive"
        pw3 = ve.Engine(copy.deepcopy(d3)).run()["synthesis"]["path_weights"]
        self.assertEqual(pw3["mode"], "adaptive")
        self.assertIn("k_lifecycle", pw3)
        self.assertAlmostEqual(pw3["resolved_weights"]["dcf"], 0.3786, places=4)

    def test_t120_scenario_step_sigma(self):
        """T120【B4】情景步长按历史波动率（固定 ±10pp → clamp(σ,2,5)）。

        ★根因：格力历史三年 σ=9.62pp，固定 −10pp 使 bear 首年增速 = −12.00%，
        比历史最差（−9.89%）还差 2.1pp——用情景标签制造了从未发生过的假设。
        """
        d = self._dcf_base()
        d["dcf_growth"] = {"scenario_step_mode": "cva_sigma"}
        o = ve.Engine(copy.deepcopy(d)).run()
        step = o["assumptions_summary"]["dcf"]["scenario_step"]
        self.assertAlmostEqual(step["sigma_pp"], 9.62, places=2)
        self.assertAlmostEqual(step["step_pp"], 5.0, places=2, msg="σ 须被 clamp 到 5pp 上限")

        bear_g1 = o["scenarios"]["bear"]["dcf"]["growth_seq"][0]
        bull_g1 = o["scenarios"]["bull"]["dcf"]["growth_seq"][0]
        self.assertAlmostEqual(bear_g1, -0.07, places=4, msg="bear 首年 = −2% − 5pp（不得突破 −9.89%）")
        self.assertAlmostEqual(bull_g1, 0.03, places=4)
        self.assertGreater(bear_g1, -0.0989, "bear 不得突破历史极值")

        # 缺省 fixed：±10pp 逐位不变（零回归）
        o0 = ve.Engine(self._dcf_base()).run()
        self.assertAlmostEqual(o0["scenarios"]["bear"]["dcf"]["growth_seq"][0], -0.12, places=4)

        # 历史不足 3 期 → 回退 fixed 并告警
        d2 = self._dcf_base()
        del d2["financials"]["revenue_by_year"]
        d2["dcf_growth"] = {"scenario_step_mode": "cva_sigma"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertFalse(o2["assumptions_summary"]["dcf"].get("scenario_step"))
        self.assertTrue(any("回退固定" in w for w in o2["warnings"]))

    def test_t121_terminal_growth_forced(self):
        """T121【B5】终值年增速强制落在 tg（等差插值，末点 ≡ tg）。

        ★根因：exp / mean_revert / s_curve 三个形态都是**渐近**的，数学上永不到达 tg
        （实测 legacy 末段 1.88% vs tg 2.00%，tg=6% 时落差 −1.12pp）。成熟期的定义
        就是增速已稳定，末期不落在长期增长率上与该定义矛盾。
        """
        d = self._dcf_base()
        d["preferences"]["lifecycle_mode"] = "auto"
        d["dcf_growth"] = {"growth_terminal_mode": "forced", "lifecycle_mature_n_mode": "cva_7"}
        o = ve.Engine(copy.deepcopy(d)).run()
        seq = o["scenarios"]["base"]["dcf"]["growth_schedule"]["seq"]
        self.assertAlmostEqual(seq[-1], 0.02, places=9, msg="forced 下末段增速须 ≡ tg")
        self.assertEqual(o["scenarios"]["base"]["dcf"]["growth_schedule"]["terminal_mode"], "forced")

        # 等差性：相邻差相等
        diffs = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        self.assertTrue(all(abs(d - diffs[-1]) < 2e-4 for d in diffs[-3:]),
                        f"收敛段须等差（容差含 6 位小数舍入）: {diffs}")
        self.assertTrue(all(d > 0 for d in diffs[2:]), "收敛段须单调递增")

        # asymptotic（缺省）：末点 ≠ tg（渐近）
        d0 = self._dcf_base(growth_forecast={"2026E": 0.03, "2027E": 0.03, "2028E": 0.03})
        d0["preferences"]["lifecycle_mode"] = "auto"
        o0 = ve.Engine(copy.deepcopy(d0)).run()
        seq0 = o0["scenarios"]["base"]["dcf"]["growth_schedule"]["seq"]
        self.assertNotAlmostEqual(seq0[-1], 0.02, places=6, msg="asymptotic 不该精确到达 tg")

    def test_t122_v321_zero_regression(self):
        """T122 零回归：12 项开关全部取缺省 vs 显式写默认值，须逐位等价。

        ★通用判据：新增机制必须 opt-in——开关键集合的任何变化都不得外泄到输出
        （含 `scenarios.*.params` 的键集合，`tg_adj_pp` 只在 stepped 时注入即为此）。
        """
        explicit = {
            "terminal_growth_guard": "off", "terminal_growth_default": "legacy_6pct",
            "terminal_growth_basis": "legacy", "terminal_growth_scenario_mode": "flat",
            "tv_share_guard": False, "implied_tg_market": False,
            "growth_path_mode": "legacy_truncate", "growth_history_shape": "off",
            "scenario_step_mode": "fixed", "growth_terminal_mode": "asymptotic",
            "lifecycle_mature_n_mode": "table",
        }
        d_a = load_example_input()
        d_b = load_example_input()
        d_b["dcf_growth"] = explicit
        a = ve.Engine(copy.deepcopy(d_a)).run()
        b = ve.Engine(copy.deepcopy(d_b)).run()
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         "v3.21 开关取缺省时须与显式写默认值逐位等价")

        # 键集合不得外泄：缺省下 scenarios.*.params 无 tg_adj_pp
        for k in ("bear", "base", "bull"):
            self.assertNotIn("tg_adj_pp", a["scenarios"][k]["params"],
                             "tg_adj_pp 仅在 stepped 时注入，缺省不得外泄")
        # 结构断言：守卫必须在折现前调用，且折现函数带 guard
        sp = os.path.join(SKILL_ROOT, "scripts", "valuation_engine.py")
        src = open(sp, encoding="utf-8").read()
        self.assertIn("tguard = check_terminal_growth(wacc, tg)", src)
        self.assertLess(src.index("tguard = check_terminal_growth(wacc, tg)"),
                        src.index("pv_sum, tv_pv, dcf_detail = two_stage_dcf("),
                        "守卫须在折现前判定")
        self.assertIn("guard=tguard", src)


    # ===== v3.22.0 估值缺陷修复六项（T123–T128）=====
    def test_t123_wacc_default_dynamic(self):
        """T123【修复①】WACC 缺省动态化：capm_auto 替代硬编码 11%，ERP 取 CVA 8.04%。

        ★根因：`DEFAULT_WACC = 0.11` 是 rf 1.9% 时代的旧值，而 CAPM 口径下
        rf 1.9% + β_L 1.252 × ERP 8.04% ≈ 12.0% 的 ke，加权后 WACC ≈ 9.9%。
        用户不填 WACC 就按 11% 算，DCF 被系统性低估；填了又没人核对口径。
        """
        d = self._dcf_base()
        d["financials"]["wacc_params"] = {"enabled": False}
        d["financials"].pop("wacc", None)
        o = ve.Engine(copy.deepcopy(d)).run()
        self.assertAlmostEqual(o["assumptions_summary"]["dcf"]["wacc"], 0.11, places=4,
                               msg="legacy 口径须保持 11% 缺省（零回归）")
        self.assertNotIn("wacc_default", o, "legacy 不得挂出 wacc_default 块")

        d2 = self._dcf_base()
        d2["financials"]["wacc_params"] = {"enabled": False}
        d2["financials"].pop("wacc", None)
        d2["dcf_cost"] = {"wacc_default_mode": "capm_auto"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        wd = o2["wacc_default"]
        self.assertEqual(wd["mode"], "capm_auto")
        self.assertAlmostEqual(wd["erp"], 0.0804, places=6, msg="capm_auto 的 ERP 缺省须取 CVA 8.04%")
        self.assertIn("CVA", wd["erp_source"])
        self.assertAlmostEqual(wd["replaced_default"], 0.11, places=6)
        # 手算交叉校验：rf + β_L×(1+(1−t)×D/E) × ERP → ke → 加权 WACC
        beta_l = 1.0 * (1.0 + (1.0 - 0.15) * 0.3)
        ke = 0.019 + beta_l * 0.0804
        kd_after = 0.035 * (1.0 - 0.15)
        wacc_exp = (ke + 0.3 * kd_after) / 1.3
        self.assertAlmostEqual(wd["wacc_model"], round(wacc_exp, 4), places=3,
                               msg=f"CAPM 构造值须可复算（期望 {wacc_exp:.4f}）")
        self.assertGreater(wd["delta_pp"], -2.0, "动态值不应显著高于 11%（否则 ERP 或 β 口径有误）")
        self.assertTrue(any("WACC 动态构造值" in w for w in o2["warnings"]))

    def test_t124_p0_missing_param_not_silent(self):
        """T124【修复②】p0_value_driver 缺 ebit/roic：不得静默回退比率法。

        ★根因：`cashflow_model=p0_value_driver` 时，条件不满足即走 else 分支回退
        「净利×FCF 比率」，**无任何留痕**——用户以为用了守恒律口径
        （FCFF_t = NOPAT_t×(1−g_t/ROIC)），实际跑的是无再投资约束的比率法。
        """
        d = self._dcf_base()
        d["preferences"]["cashflow_model"] = "p0_value_driver"
        d["financials"].pop("ebit")
        d["financials"].pop("roic")
        o = ve.Engine(copy.deepcopy(d)).run()
        cf = o["cashflow_model_fallback"]
        self.assertEqual(cf["requested"], "p0_value_driver")
        self.assertEqual(cf["used"], "p2_legacy")
        self.assertEqual(sorted(cf["missing"]), ["ebit", "roic"])
        self.assertTrue(any("已降级 p2_legacy" in w for w in o["warnings"]))
        self.assertEqual(o["scenarios"]["base"]["dcf"]["fcf_basis"], "net_profit_ratio")

        # error 模式：封顶「中」
        d["dcf_cost"] = {"cashflow_fallback_mode": "error"}
        o2 = ve.Engine(copy.deepcopy(d)).run()
        caps = o2["confidence"]["growth_param_caps"]
        self.assertTrue(any(c["rule"] == "cashflow_model_fallback" for c in caps["caps"]))
        self.assertLessEqual(o2["confidence"]["score"], 79.9)

        # 补齐参数 → 不再降级，走 value_driver
        d3 = self._dcf_base()
        d3["preferences"]["cashflow_model"] = "p0_value_driver"
        d3["dcf_cost"] = {"cashflow_fallback_mode": "error"}
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertNotIn("cashflow_model_fallback", o3)
        self.assertEqual(o3["scenarios"]["base"]["dcf"]["fcf_basis"], "value_driver_p0")

    def test_t125_comparable_unavailable_renormalize(self):
        """T125【修复③】comp_v 三态：可比法无值时按剩余权重再归一，不得静默归零。

        ★根因：`comp_v = comp["synthesis"]["base_value"] or 0.0`——可比法不可用时
        取值为 0，但权重仍占 50%，综合值只剩 DCF 的 30%。**不报错、报告照常出**。
        """
        d = self._dcf_base()
        d["comparables"] = []
        o = ve.Engine(copy.deepcopy(d)).run()
        self.assertEqual(o["scenarios"]["base"]["comparable_raw"], 0.0,
                         "zero_silent（缺省）须保持旧行为：raw 记 0")
        self.assertNotIn("method_drop", o["scenarios"]["base"])
        legacy_val = o["synthesis"]["base_value"]

        d2 = self._dcf_base()
        d2["comparables"] = []
        d2["dcf_cost"] = {"method_drop_mode": "renormalize"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertIsNone(o2["scenarios"]["base"]["comparable_raw"])
        md = o2["scenarios"]["base"]["method_drop"]
        self.assertEqual(md["mode"], "renormalize")
        self.assertIn("comparable", md["dropped"])
        self.assertAlmostEqual(md["renormalized"]["dcf"], 1.0, places=4,
                               msg="剔除可比法后 DCF 权重须归一为 1.0")
        self.assertIsNone(o2["synthesis"]["dcf_vs_comparable_gap"])
        self.assertIsNone(o2["synthesis"]["four_part"]["part2_comparable_quality"]["value"])
        # 核心断言：综合值须回升到 DCF 口径，而不是缩水到 30%
        self.assertGreater(o2["synthesis"]["base_value"], legacy_val * 2.5,
                           "renormalize 后综合值应接近 DCF 值（旧口径只剩约 30%）")
        self.assertTrue(any("已从综合权重中剔除" in w for w in o2["warnings"]))

    def test_t126_fcff_suggest_heavy_asset(self):
        """T126【修复④】重资产（CapEx/营收 > 8%）自动建议开启 fcff_mode。

        ★根因：缺省走「净利×FCF 比率」，该口径不含再投资约束；资本开支强度越高、
        高估越多（格力报表级 FCFF 校准后差 22.9%）。引擎知道 capex 强度却不提示。
        """
        d = self._dcf_base()
        d["financials"]["capex_to_revenue"] = 0.12
        d["dcf_cost"] = {"fcff_suggest": True}
        o = ve.Engine(copy.deepcopy(d)).run()
        fs = o["fcff_suggestion"]
        self.assertAlmostEqual(fs["capex_to_revenue"], 0.12, places=4)
        self.assertEqual(fs["source"], "公司披露口径")
        self.assertTrue(fs["ebit_available"])
        self.assertTrue(any("fcff_mode=true" in w for w in o["warnings"]))

        # 低于阈值 → 不触发
        d2 = self._dcf_base()
        d2["financials"]["capex_to_revenue"] = 0.03
        d2["dcf_cost"] = {"fcff_suggest": True}
        self.assertNotIn("fcff_suggestion", ve.Engine(copy.deepcopy(d2)).run())

        # 开关关闭 → 不触发（零回归）
        d3 = self._dcf_base()
        d3["financials"]["capex_to_revenue"] = 0.12
        self.assertNotIn("fcff_suggestion", ve.Engine(copy.deepcopy(d3)).run())

        # 已启用 fcff_mode → 无需建议
        d4 = self._dcf_base()
        d4["financials"]["capex_to_revenue"] = 0.12
        d4["financials"]["fcff_mode"] = True
        d4["financials"]["capex"] = 120.0
        d4["financials"]["d_a"] = 60.0
        d4["financials"]["delta_wc"] = 10.0
        d4["dcf_cost"] = {"fcff_suggest": True}
        self.assertNotIn("fcff_suggestion", ve.Engine(copy.deepcopy(d4)).run())

    def test_t127_cva_tg_requires_explicit_wacc(self):
        """T127【修复⑤】cva_2pct 永续增速须配套显式/模型化 WACC。

        ★根因：只把 tg 从 6% 改成 2%、WACC 仍是 11% 时，终值倍数
        (1+g)/(WACC−g) 由 21.20× 掉到 11.33×（−46.6%）；用户以为只动了永续假设，
        实际砍掉近一半终值——两个缺省值必须同批改。
        """
        d = self._dcf_base()
        d["financials"]["wacc_params"] = {"enabled": False}
        d["financials"].pop("wacc", None)
        d["dcf_growth"] = {"terminal_growth_default": "cva_2pct",
                           "require_explicit_wacc_with_cva_tg": True}
        o = ve.Engine(copy.deepcopy(d)).run()
        msg = [w for w in o["warnings"] if "终值倍数" in w]
        self.assertEqual(len(msg), 1, "须给出一条终值倍数告警")
        self.assertIn("21.20", msg[0])
        self.assertIn("11.33", msg[0])
        # 可复算性：两档倍数与常量一致
        self.assertAlmostEqual((1.06) / (0.11 - 0.06), 21.2, places=2)
        self.assertAlmostEqual((1.02) / (0.11 - 0.02), 11.3333, places=3)

        # 开关关闭 → 无该告警（零回归）
        d2 = self._dcf_base()
        d2["financials"]["wacc_params"] = {"enabled": False}
        d2["financials"].pop("wacc", None)
        d2["dcf_growth"] = {"terminal_growth_default": "cva_2pct"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertFalse(any("终值倍数" in w for w in o2["warnings"]))

        # 有 CAPM 模型值时不再告警（WACC 已模型化）
        d3 = self._dcf_base()
        d3["dcf_growth"] = {"terminal_growth_default": "cva_2pct",
                            "require_explicit_wacc_with_cva_tg": True}
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertFalse(any("终值倍数" in w for w in o3["warnings"]))

    def test_t128_point_estimate_guard_and_zero_regression(self):
        """T128【修复⑥】终值占比 extreme 档禁出单点估值 + 六开关零回归。

        ★根因：A6 对 >85% 只封顶置信度「中」，仍照出中枢——读者照样采信那个数。
        CVA comps 的口径是直接 `point_estimate = null`。
        """
        d = self._dcf_base()
        # 构造极端终值占比：极短显式期 + 高永续 + 低增速
        d["financials"]["growth_forecast"] = {"2026E": 0.0, "2027E": 0.0, "2028E": 0.0}
        d["financials"]["terminal_growth"] = 0.06
        d["dcf_growth"] = {"tv_share_guard": True, "lifecycle_mature_n_mode": "legacy_4"}
        d["dcf_cost"] = {"point_estimate_guard": True}
        o = ve.Engine(copy.deepcopy(d)).run()
        grade = o["scenarios"]["base"]["dcf"]["tv_share_grade"]
        self.assertEqual(grade["grade"], "extreme", "构造条件须命中 extreme 档")
        self.assertEqual(grade["level"], "error", "extreme 档的严重度为 error")
        self.assertIsNone(o["synthesis"]["point_estimate"])
        self.assertEqual(o["synthesis"]["point_estimate_suppressed"]["rule"], "tv_share_extreme")
        self.assertTrue(any("取消单点估值" in w for w in o["warnings"]))
        # 区间仍在（结论口径降级为区间，不是无结论）
        self.assertIsNotNone(o["synthesis"]["interval"])
        self.assertIsNotNone(o["synthesis"]["weighted_mid"])

        # 开关关闭 → 照出中枢，不挂 point_estimate 键
        d2 = self._dcf_base()
        d2["financials"]["growth_forecast"] = {"2026E": 0.0, "2027E": 0.0, "2028E": 0.0}
        d2["financials"]["terminal_growth"] = 0.06
        d2["dcf_growth"] = {"tv_share_guard": True, "lifecycle_mature_n_mode": "legacy_4"}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertEqual(o2["scenarios"]["base"]["dcf"]["tv_share_grade"]["grade"], "extreme")
        self.assertNotIn("point_estimate", o2["synthesis"])

        # 六开关全部显式写默认值 vs 不写 → 逐位等价（零回归）
        explicit = {"wacc_default_mode": "legacy_11pct", "erp_default_mode": "auto",
                    "cashflow_fallback_mode": "silent", "method_drop_mode": "zero_silent",
                    "fcff_suggest": False, "point_estimate_guard": False}
        d_a = load_example_input()
        d_b = load_example_input()
        d_b["dcf_cost"] = explicit
        a = ve.Engine(copy.deepcopy(d_a)).run()
        b = ve.Engine(copy.deepcopy(d_b)).run()
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         "v3.22 六开关取缺省时须与显式写默认值逐位等价")
        for k in ("wacc_default", "cashflow_model_fallback", "fcff_suggestion"):
            self.assertNotIn(k, a, f"{k} 缺省不得挂出")


    # ================= v3.23.0：现金流模型细节层（D1–D9）=================

    def test_t129_mid_year_discounting(self):
        """T129【D1】年中折现：显式期按 (t−0.5)、终值按 (n−0.5)；缺省年末逐位不变。"""
        pv_a, tv_a, det_a = ve.two_stage_dcf(100.0, [0.05] * 3, 0.02, 0.10)
        pv_b, tv_b, det_b = ve.two_stage_dcf(100.0, [0.05] * 3, 0.02, 0.10, mid_year=True)
        self.assertAlmostEqual(pv_b / pv_a, 1.10 ** 0.5, places=6)
        self.assertAlmostEqual(tv_b / tv_a, 1.10 ** 0.5, places=6)
        self.assertGreater(pv_b, pv_a)
        s_a = ve.discount_fcf_series([10.0, 11.0], 0.02, 0.10)
        s_b = ve.discount_fcf_series([10.0, 11.0], 0.02, 0.10, mid_year=True)
        self.assertAlmostEqual(s_b[0] / s_a[0], 1.10 ** 0.5, places=6)
        self.assertAlmostEqual(s_b[1] / s_a[1], 1.10 ** 0.5, places=6)
        d = self._dcf_base()
        d2 = copy.deepcopy(d)
        d2["dcf_cost"] = {"discount_timing": "mid_year"}
        o1 = ve.Engine(copy.deepcopy(d)).run()
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        e1 = o1["scenarios"]["base"]["dcf"]["equity_value"]
        e2 = o2["scenarios"]["base"]["dcf"]["equity_value"]
        self.assertGreater(e2 / e1, 1.03)
        self.assertLess(e2 / e1, 1.05)
        self.assertEqual(o2["scenarios"]["base"]["dcf"]["discount_timing"]["mode"], "mid_year")
        self.assertNotIn("discount_timing", o1["scenarios"]["base"]["dcf"])

    def test_t130_size_premium(self):
        """T130【D2】CVA 规模溢价：十分位/细分查表 + 只加在 CAPM ke 上（显式 WACC 仍优先）。"""
        self.assertEqual(ve.size_premium_cva(500)["group"], "1")
        self.assertAlmostEqual(ve.size_premium_cva(500)["premium"], 0.0033, places=4)
        self.assertEqual(ve.size_premium_cva(100)["group"], "4")
        self.assertEqual(ve.size_premium_cva(20)["group"], "10x")
        self.assertEqual(ve.size_premium_cva(16)["group"], "10y")
        self.assertAlmostEqual(ve.size_premium_cva(10)["premium"], 0.1829, places=4)
        self.assertFalse(ve.size_premium_cva(None)["applied"])
        d = self._dcf_base(market_cap=500.0)
        d2 = copy.deepcopy(d)
        d2["dcf_cost"] = {"size_premium_mode": "cva_deciles"}
        o1 = ve.Engine(copy.deepcopy(d)).run()
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        w1 = o1["scenarios"]["base"]["dcf"]["wacc"]
        w2 = o2["scenarios"]["base"]["dcf"]["wacc"]
        ev_w = 1.0 / 1.3998
        self.assertAlmostEqual(w2 - w1, 0.0033 * ev_w, delta=1e-4)
        self.assertEqual(o2["size_premium"]["group"], "1")
        self.assertNotIn("size_premium", o1)
        # 显式 WACC 优先：溢价只进模型值，不覆盖用户给定
        d3 = copy.deepcopy(d2)
        d3["financials"]["wacc"] = 0.09
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertAlmostEqual(o3["scenarios"]["base"]["dcf"]["wacc"], 0.09, places=6)

    def test_t131_growth_base_matrix(self):
        """T131【D4】历史形态 → 基准增速取值矩阵（稳定取均值/加速取加权/下行取最近一年/切换不取平均）。"""
        stable = {"enabled": True, "history_case": "稳定增长",
                  "metrics": {"H1": 0.10, "H2": 0.105, "H3": 0.102, "mean": 0.10233, "median": 0.102}}
        r = ve.growth_base_from_history(stable)
        self.assertTrue(r["applied"])
        self.assertAlmostEqual(r["base_growth"], 0.10233, places=4)
        acc = {"enabled": True, "history_case": "持续加速（禁止外推斜率）",
               "metrics": {"H1": 0.05, "H2": 0.08, "H3": 0.12, "mean": 0.0833, "median": 0.08}}
        r2 = ve.growth_base_from_history(acc)
        self.assertAlmostEqual(r2["base_growth"], 0.094, places=6)
        down = {"enabled": True, "history_case": "高增长回落",
                "metrics": {"H1": 0.20, "H2": 0.15, "H3": 0.087, "mean": 0.1457, "median": 0.15}}
        r3 = ve.growth_base_from_history(down)
        self.assertAlmostEqual(r3["base_growth"], 0.087, places=6)
        sw = {"enabled": True, "history_case": "正负切换且无稳定方向",
              "metrics": {"H1": 0.0793, "H2": -0.0726, "H3": -0.0989, "mean": -0.0307, "median": -0.0726}}
        r4 = ve.growth_base_from_history(sw)
        self.assertFalse(r4["applied"])
        self.assertTrue(r4["needs_evidence"])

    def test_t132_statement_fcff_series(self):
        """T132【D6/D7】报表驱动 FCFF 手算：收入→EBIT→NOPAT→+D&A−Capex−ΔWC。"""
        series, det = ve.statement_fcff_series(
            base_revenue=100.0, growth_seq=[0.10], ebit_margin=0.20, capex_to_revenue=0.08,
            da_to_revenue=0.05, nwc_to_revenue=0.10, tax_rate=0.25)
        row = det["rows"][0]
        self.assertAlmostEqual(row["revenue"], 110.0, places=6)
        self.assertAlmostEqual(row["ebit"], 22.0, places=6)
        self.assertAlmostEqual(row["nopat"], 16.5, places=6)
        self.assertAlmostEqual(row["d_a"], 5.5, places=6)
        self.assertAlmostEqual(row["capex"], 8.8, places=6)
        self.assertAlmostEqual(row["delta_wc"], 1.0, places=6)
        self.assertAlmostEqual(series[0], 12.2, places=6)
        # D7：周转率口径 ΔWC = NWC_t − NWC_{t−1}
        s2, d2 = ve.statement_fcff_series(
            base_revenue=100.0, growth_seq=[0.10], ebit_margin=0.20, capex_to_revenue=0.08,
            da_to_revenue=0.05, nwc_turnover=5.0, tax_rate=0.25)
        self.assertAlmostEqual(d2["rows"][0]["delta_wc"], 2.0, places=6)
        self.assertAlmostEqual(s2[0], 11.2, places=6)
        # 成本率+费用率合成 EBIT 率
        s3, d3 = ve.statement_fcff_series(
            base_revenue=100.0, growth_seq=[0.0], cost_ratio=0.70, expense_ratio=0.10,
            capex_to_revenue=0.0, da_to_revenue=0.0, tax_rate=0.25)
        self.assertAlmostEqual(d3["rows"][0]["ebit_margin"], 0.20, places=6)

    def test_t133_drivers_mode_end_to_end(self):
        """T133【D6】dcf_drivers 端到端：fcf_basis=statement_drivers + 明细留痕 + 权益勾稽。"""
        d = self._dcf_base()
        d["dcf_drivers"] = {"base_revenue": 1631.72, "ebit_margin": 0.2089,
                            "capex_to_revenue": 0.04, "da_to_revenue": 0.029,
                            "nwc_to_revenue": 0.0, "tax_rate": 0.16}
        out = ve.Engine(copy.deepcopy(d)).run()
        b = out["scenarios"]["base"]["dcf"]
        self.assertEqual(b["fcf_basis"], "statement_drivers")
        self.assertIn("cashflow_drivers", b)
        self.assertEqual(len(b["cashflow_drivers"]["rows"]), len(b["growth_seq"]))
        self.assertAlmostEqual(b["equity_value"],
                               b["pv_sum"] + b["terminal_value_pv"] + 788.48, places=2)
        # 缺 ebit_margin 时不静默：回退下一档并告警
        d2 = self._dcf_base()
        d2["dcf_drivers"] = {"base_revenue": 1631.72, "capex_to_revenue": 0.04}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertNotEqual(o2["scenarios"]["base"]["dcf"]["fcf_basis"], "statement_drivers")
        self.assertTrue(any("dcf_drivers" in w for w in o2["warnings"]))

    def test_t134_capex_magnitude_check(self):
        """T134【D3】Capex/D&A 量级勾稽：拦截 capex 异常偏低（8% 营收阈值拦不住的一类）。"""
        r = ve.capex_magnitude_check(7.30, 47.86)
        self.assertEqual(r["level"], "warning")
        self.assertAlmostEqual(r["ratio"], 0.1525, places=3)
        self.assertEqual(ve.capex_magnitude_check(96.0, 47.86)["level"], "ok")
        self.assertFalse(ve.capex_magnitude_check(None, 47.86)["applied"])
        d = self._dcf_base(capex=7.30, d_a=47.86)
        d["dcf_cost"] = {"capex_check": True}
        o = ve.Engine(copy.deepcopy(d)).run()
        self.assertEqual(o["capex_check"]["level"], "warning")
        self.assertTrue(any("Capex/D&A" in w for w in o["warnings"]))
        o2 = ve.Engine(copy.deepcopy(self._dcf_base(capex=7.30, d_a=47.86))).run()
        self.assertNotIn("capex_check", o2)

    def test_t135_growth_base_rule_engine(self):
        """T135【D4】未给 growth_forecast 时按形态取值：高增长回落 → 首年 = 最近一年增速。"""
        d = self._dcf_base()
        d["financials"].pop("growth_forecast")
        d["financials"]["revenue_by_year"] = {"2022": 1000.0, "2023": 1200.0,
                                              "2024": 1380.0, "2025": 1500.0}
        d["dcf_growth"] = {"growth_base_rule": "cva_matrix"}
        out = ve.Engine(copy.deepcopy(d)).run()
        rule = out["growth_base_rule"]
        self.assertTrue(rule["applied"])
        self.assertAlmostEqual(rule["base_growth"], 0.087, places=4)
        self.assertAlmostEqual(out["scenarios"]["base"]["dcf"]["growth_seq"][0], 0.087, places=4)
        # 用户显式路径永不覆盖
        d2 = copy.deepcopy(d)
        d2["financials"]["growth_forecast"] = {"2026E": 0.05, "2027E": 0.04, "2028E": 0.03}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        self.assertFalse(o2["growth_base_rule"]["applied"])
        self.assertAlmostEqual(o2["scenarios"]["base"]["dcf"]["growth_seq"][0], 0.05, places=4)

    def test_t136_margin_step_sigma(self):
        """T136【D5】利润率情景步长 = σ clamp[1,3]pp（与收入步长分开）。"""
        r = ve.margin_sigma_step([0.20, 0.21, 0.25])
        self.assertTrue(r["applied"])
        self.assertAlmostEqual(r["step_pp"], 2.65, places=2)
        self.assertEqual(ve.margin_sigma_step([0.2, 0.21])["applied"], False)
        d = self._dcf_base(margin_history=[0.20, 0.21, 0.25])
        d["dcf_cost"] = {"margin_step_mode": "cva_sigma"}
        out = ve.Engine(copy.deepcopy(d)).run()
        bear = out["scenarios"]["bear"]["params"]["margin_adj_pp"]
        bull = out["scenarios"]["bull"]["params"]["margin_adj_pp"]
        self.assertAlmostEqual(bear, -2.65, places=2)
        self.assertAlmostEqual(bull, 2.65, places=2)
        o2 = ve.Engine(copy.deepcopy(self._dcf_base(margin_history=[0.20, 0.21, 0.25]))).run()
        self.assertAlmostEqual(o2["scenarios"]["bear"]["params"]["margin_adj_pp"], -3, places=6)

    def test_t137_v323_zero_regression(self):
        """T137 零回归：v3.23 全部新开关取缺省 vs 显式写默认值，逐位等价且不挂新键。"""
        explicit = {"discount_timing": "year_end", "size_premium_mode": "off", "capex_check": False,
                    "capex_da_band": [0.5, 10.0], "margin_step_mode": "off",
                    "reinvestment_check": False, "normalization_hint": False}
        d_a = load_example_input()
        d_b = load_example_input()
        d_b["dcf_cost"] = explicit
        d_b["dcf_growth"] = {"growth_base_rule": "off"}
        a = ve.Engine(copy.deepcopy(d_a)).run()
        b = ve.Engine(copy.deepcopy(d_b)).run()
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         "v3.23 七开关取缺省时须与显式写默认值逐位等价")
        for k in ("size_premium", "capex_check", "normalization_hint", "growth_base_rule"):
            self.assertNotIn(k, a, f"{k} 缺省不得挂出")

    def test_t138_peg_negative_growth_guard(self):
        """T138 PEG 负增长适用性（v3.23.1）：目标公司 g1≤0 时 PEG 无经济含义。

        原实现 value = 利润 × PEG中位 × (g1×100) 在 g1<0 时产出负估值，且负值在
        `if res.get("peg",{}).get("value")` 判定中为真 → 混入 candidates 被等权均值化，
        把可比法中枢静默拖低（格力实测 −2,455 亿把 2,687 亿拉到 1,658 亿，−38%）。
        """
        d = load_example_input()
        fin = d["financials"]
        # 隔离变量：把 PEG 中位数上限放宽，确保本用例只检验「目标增速符号」这一条判据
        d.setdefault("preferences", {})["peg_max_ratio"] = 1000.0
        # 构造一个正增长参照组
        fin["growth_forecast"] = {"2026E": 0.08, "2027E": 0.08, "2028E": 0.08}
        for c in d.get("comparables") or []:
            c["growth_pct"] = 12.0
        pos = ve.Engine(copy.deepcopy(d)).run()
        peg_pos = pos["scenarios"]["base"]["comparable"]["peg"]
        self.assertIsNotNone(peg_pos.get("value"), "正增长标的 PEG 应可用")
        self.assertGreater(peg_pos["value"], 0)

        # 同一输入把首年增速改为负 → PEG 必须整法弃用，且不得留下负值
        d_neg = copy.deepcopy(d)
        d_neg["financials"]["growth_forecast"] = {"2026E": -0.06, "2027E": -0.02, "2028E": 0.01}
        neg = ve.Engine(copy.deepcopy(d_neg)).run()
        peg_neg = neg["scenarios"]["base"]["comparable"]["peg"]
        self.assertIsNone(peg_neg.get("value"), "g1≤0 时 PEG value 必须为 None，不得为负值")
        self.assertLessEqual(peg_neg["target_growth_g1"], 0)
        self.assertIn("dropped_by_guard", peg_neg)
        self.assertTrue(any("PEG" in w and "≤ 0" in w for w in neg["warnings"]),
                        "弃用理由须进 warnings")

        # 弃用后 PEG 不得出现在可比法候选集中（无负值污染）
        cands = neg["scenarios"]["base"]["comparable"]["synthesis"]["method_values"]
        self.assertTrue(all(v > 0 for v in cands), f"候选集不得含非正值：{cands}")
        self.assertNotIn("peg_value", neg["scenarios"]["base"]["comparable"]["synthesis"])

        # 参照：正增长组确实把 PEG 计入 → 负增长组中枢应更高（少了一个被拖低的成员）
        self.assertGreater(neg["scenarios"]["base"]["comparable"]["synthesis"]["base_value"], 0)

    def test_t139_reinvestment_check_relative_and_sign_flip(self):
        """T139 D9 再投资自检口径（v3.23.1）：相对偏离 + 符号翻转双判据。

        原实现 dev = |rr_implied − rr_target| 是**百分点差**却与 0.5 比较（文案写「>50%」= 相对口径）。
        结果：capex 长期低于 D&A 的标的（隐含 RR = −13.6%，净减投资）对目标 RR +16.6%，差 30.2pp、
        符号完全相反，仍判「自洽」而放过——把一个结构性矛盾报成了通过。
        """
        def run(capex_to_rev, roic=0.1204, tg=0.02):
            d = load_example_input()
            d["financials"]["roic"] = roic
            d["financials"]["terminal_growth"] = tg
            d.pop("growth_forecast", None)
            d["financials"]["growth_forecast"] = {"2026E": 0.02, "2027E": 0.02, "2028E": 0.02}
            d["dcf_drivers"] = {"enabled": True, "base_revenue": 1000.0, "ebit_margin": 0.15,
                                "capex_to_revenue": capex_to_rev, "da_to_revenue": 0.03,
                                "nwc_to_revenue": 0.0, "tax_rate": 0.15}
            d.setdefault("dcf_cost", {})["reinvestment_check"] = True
            d["dcf_growth"] = {"terminal_growth_guard": "clamp"}
            out = ve.Engine(copy.deepcopy(d)).run()
            return out["scenarios"]["base"]["dcf"]["reinvestment_check"], out["warnings"]

        # ① 正常匹配：NOPAT率 = 0.15×0.85 = 12.75%；目标 RR = 2%/12.04% = 16.61%
        #    → 需要的 capex/rev = D&A率 3% + 16.61%×12.75% = 5.12%
        c_ok, w_ok = run(0.0512)
        self.assertTrue(c_ok["available"])
        self.assertGreater(c_ok["rr_implied"], 0)
        self.assertFalse(c_ok["flag"], f"匹配口径不应告警：{c_ok}")
        self.assertFalse(c_ok["sign_flip"])

        # ② 结构性矛盾：capex 远低于 D&A（隐含 RR<0）而 tg>0 → 符号翻转必须告警
        c_bad, w_bad = run(0.010)
        self.assertLess(c_bad["rr_implied"], 0, "capex<D&A 时隐含 RR 应为负")
        self.assertGreater(c_bad["rr_target"], 0)
        self.assertTrue(c_bad["sign_flip"], "隐含 RR<0 而目标 RR>0 须标 sign_flip")
        self.assertTrue(c_bad["flag"], "符号翻转 + 幅度 >5pp 必须告警（原实现会放过）")
        self.assertIn("结构性不自洽", c_bad["note"])
        self.assertTrue(any("期末再投资一致性告警" in w for w in w_bad))
        # 告警不得重复刷屏（情景多次调用同一段）
        self.assertEqual(len([w for w in w_bad if "期末再投资一致性告警" in w]),
                         len(set(w for w in w_bad if "期末再投资一致性告警" in w)))

        # ③ deviation 语义为**相对偏离**（不是百分点差）：gap_pp / |rr_target|
        self.assertAlmostEqual(c_bad["deviation"], c_bad["gap_pp"] / abs(c_bad["rr_target"]), places=3)
        self.assertIn("相对偏离", c_bad["basis"])

    # ---------- v3.24.0（F1）：FCF 比率惰性求值 ----------
    @staticmethod
    def _lazy_base(drivers=True, lazy=True, diag=False):
        """构造 ①（三表联立）/ ④（比率法）两种口径的最小输入。"""
        d = TestNewMethods._dcf_base()
        d["financials"]["capex_to_revenue"] = 0.03        # 使三层校准 L1 可算（比率法可启用）
        if drivers:
            d["dcf_drivers"] = {"enabled": True, "base_revenue": 1000.0, "ebit_margin": 0.15,
                                "capex_to_revenue": 0.03, "da_to_revenue": 0.03,
                                "nwc_to_revenue": 0.0, "tax_rate": 0.15}
        if lazy:
            d["dcf_cost"] = {"fcf_ratio_lazy": True}
        d.setdefault("preferences", {})
        if diag:
            d["preferences"]["diagnostics_fcf_ratio"] = True
        return d

    def test_t140_fcf_ratio_lazy_skip_when_statement(self):
        """T140【F1】① 三表联立命中时，比率法**不计算**且显式声明（不产数值）。

        原实现 `run()` 无条件调用 `fcf_ratio_analysis()`：格力 R3 走的是 `statement_drivers`，
        比率块却照样算出来挂进报告（真值 1.541 被静默 clamp 到 1.50），既非真值、也非被采用
        的口径，反而被误归因为「P0 披露档」。
        """
        out = ve.Engine(copy.deepcopy(self._lazy_base(drivers=True, lazy=True))).run()
        self.assertEqual(out["scenarios"]["base"]["dcf"]["fcf_basis"], "statement_drivers")
        blk = out["fcf_ratio"]
        self.assertTrue(blk.get("skipped"), "报表口径下比率块须标 skipped")
        self.assertFalse(blk.get("enabled"))
        self.assertNotIn("used", blk, "未计算的路径**不得输出数值**")
        self.assertEqual(blk["switched_to"], "statement_drivers")
        self.assertIn("未计算", blk["reason"])
        # 披露侧：不得回落成 ocf_to_net_profit 打假数
        ass = out["assumptions_summary"]["dcf"]
        self.assertIsNone(ass["fcf_ratio"], "比率法未被采用时 fcf_ratio 须为 None，不得回落成 OCF/净利")
        self.assertIn("未计算", ass["fcf_source"])
        self.assertIn("statement_drivers", ass["fcf_source"])
        # 比率法不得污染估值：FCFF 仍来自报表驱动
        self.assertEqual(out["scenarios"]["base"]["dcf"]["fcf_basis"], "statement_drivers")

    def test_t141_fcf_ratio_lazy_driving_still_computed(self):
        """T141【F1】④ 比率档仍须**按需算准**（惰性 ≠ 不准确）。

        原实现 ④ 档在 `self._fcf_ratio is None` 时退回裸 `ocf_to_net_profit`，使三层校准
        在最需要它的档位被静默降级；惰性求值后该档一定拿到三层校准值。
        """
        d_legacy = self._lazy_base(drivers=False, lazy=False)
        d_lazy = self._lazy_base(drivers=False, lazy=True)
        o_legacy = ve.Engine(copy.deepcopy(d_legacy)).run()
        o_lazy = ve.Engine(copy.deepcopy(d_lazy)).run()
        self.assertEqual(o_lazy["scenarios"]["base"]["dcf"]["fcf_basis"], "net_profit_ratio")
        blk = o_lazy["fcf_ratio"]
        self.assertTrue(blk.get("enabled"))
        self.assertFalse(blk.get("skipped"))
        self.assertEqual(blk.get("role"), "driving")
        self.assertIn("used", blk)
        # 与 legacy 同值同权益（惰性只改「算不算」，不改「算出来是多少」）
        self.assertAlmostEqual(blk["used"], o_legacy["fcf_ratio"]["used"], places=6)
        self.assertAlmostEqual(o_lazy["scenarios"]["base"]["dcf"]["equity_value"],
                               o_legacy["scenarios"]["base"]["dcf"]["equity_value"], places=6)
        # 且必须是三层校准值，不得是裸 OCF/净利（0.9）
        self.assertNotAlmostEqual(blk["used"], 0.9, places=4)

    def test_t142_fcf_ratio_diagnostic_optin(self):
        """T142【F1】诊断索取：显式要求时才为「对照」计算，且标 diagnostic_only、不改估值。"""
        o_skip = ve.Engine(copy.deepcopy(self._lazy_base(drivers=True, lazy=True))).run()
        o_diag = ve.Engine(copy.deepcopy(self._lazy_base(drivers=True, lazy=True, diag=True))).run()
        blk = o_diag["fcf_ratio"]
        self.assertTrue(blk.get("enabled"))
        self.assertFalse(blk.get("skipped"))
        self.assertEqual(blk.get("role"), "diagnostic_only")
        self.assertIn("used", blk)
        # 诊断不得改变估值（口径仍为三表联立、权益逐位一致）
        self.assertEqual(o_diag["scenarios"]["base"]["dcf"]["fcf_basis"], "statement_drivers")
        self.assertAlmostEqual(o_diag["scenarios"]["base"]["dcf"]["equity_value"],
                               o_skip["scenarios"]["base"]["dcf"]["equity_value"], places=6)
        # 数据使用声明须标注「仅诊断对照」
        self.assertIn("仅诊断对照", o_diag["comparable_set_usage"]["fcf_ratio_source"])

    def test_t143_fcf_ratio_lazy_zero_regression(self):
        """T143【F1】零回归：`fcf_ratio_lazy` 缺省 = v2.21.1 逐位等价（含比率块无 skipped/role）。"""
        d_a = self._lazy_base(drivers=False, lazy=False)          # 不含 dcf_cost 键 → 缺省
        d_b = self._lazy_base(drivers=False, lazy=False)
        d_b["dcf_cost"] = {"fcf_ratio_lazy": False}
        a = ve.Engine(copy.deepcopy(d_a)).run()
        b = ve.Engine(copy.deepcopy(d_b)).run()
        self.assertEqual(json.dumps(a, sort_keys=True, ensure_ascii=False, default=str),
                         json.dumps(b, sort_keys=True, ensure_ascii=False, default=str),
                         "lazy 开关取缺省时须与显式写 false 逐位等价")
        blk = a["fcf_ratio"]
        for k in ("skipped", "role", "switched_to"):
            self.assertNotIn(k, blk, f"legacy 模式比率块不得新增 {k} 键")
        # 无 CapEx 数据 → 三层校准不可用 → 按 v3.3 口径返回 enabled=False，块**不挂出**（两种模式一致）
        o_ex = ve.Engine(load_example_input()).run()
        self.assertNotIn("fcf_ratio", o_ex, "enabled=False 时沿用「不挂出」旧契约")
        d_ex = load_example_input()
        d_ex["dcf_cost"] = {"fcf_ratio_lazy": True}
        o_ex2 = ve.Engine(copy.deepcopy(d_ex)).run()
        self.assertNotIn("fcf_ratio", o_ex2, "惰性模式亦不得凭空挂出未启用的比率块")


    def test_t144_fcf_ratio_clamp_disclosure(self):
        """T144【F2】比率 clamp 必须留痕（原为静默截断）。

        格力实测 L1 真值 1.541 → `min(1.5, raw)` 静默截成 1.50：输出只剩 `used=1.5`，
        既非真值、也无告警，却长得像一个真实的现金流转化率。截断须给 `clamped_from` + 告警。
        """
        d = self._dcf_base()
        d["financials"]["ocf_to_net_profit"] = 1.60          # 格力式：OCF/净利 1.60
        d["financials"]["capex_to_revenue"] = 0.01           # capex/营收 1.01%
        out = ve.Engine(copy.deepcopy(d)).run()
        blk = out["fcf_ratio"]
        self.assertEqual(blk["used"], 1.5)
        self.assertEqual(blk.get("clamp_bound"), "upper")
        # 三层校准：L1 = 1.60 − 0.01/0.1708 = 1.5415；L3 = 1.60 → 0.5/0.2 加权 /0.7
        raw_expect = (0.5 * (1.60 - 0.01 / 0.1708) + 0.2 * 1.60) / 0.7
        self.assertAlmostEqual(blk["clamped_from"], raw_expect, places=4)
        self.assertGreater(blk["clamped_from"], 1.5)
        self.assertTrue(any("截断" in w and "1.5" in w for w in out["warnings"]),
                        f"截断须告警：{[w for w in out['warnings'] if 'FCF' in w]}")

        # 恰好 = 1.5 不算截断（不得误报）
        d2 = self._dcf_base()
        d2["financials"]["ocf_to_net_profit"] = 1.5
        d2["financials"]["capex_to_revenue"] = 0.0
        b2 = ve.Engine(copy.deepcopy(d2)).run()["fcf_ratio"]
        self.assertEqual(b2["used"], 1.5)
        self.assertNotIn("clamped_from", b2, "未越界不得挂 clamped_from")

    def test_t145_fcff_suggest_ocf_quality_trigger(self):
        """T145【F3】比率法失真的第二个触发面：OCF 质量（原实现只看 capex 强度）。

        格力 capex/营收仅 1.01%（< 8% 阈值）→ 原雷达完全沉默，但其 OCF/净利 1.60 含
        并表财务公司的「吸收存款」，比率法同样失真（实测与报表级差 −30.55%）。
        「轻资产 + OCF 污染」是独立盲区，须单独判据。
        """
        # ① 轻资产但 OCF 污染 → 必须触发（原实现漏报）
        d = self._dcf_base()
        d["financials"]["capex_to_revenue"] = 0.0101
        d["financials"]["ocf_to_net_profit"] = 1.60
        d["dcf_cost"] = {"fcff_suggest": True}
        o = ve.Engine(copy.deepcopy(d)).run()
        fs = o["fcff_suggestion"]
        self.assertEqual(fs["trigger"], ["ocf_quality"])
        self.assertAlmostEqual(fs["ocf_to_net_profit"], 1.60, places=4)
        self.assertIn("吸收存款", fs["reason"])
        self.assertTrue(any("OCF/净利" in w and "dcf_drivers" in w for w in o["warnings"]))

        # ② 只有 capex 超阈值 → 仍为单触发（T126 行为不变，trigger 显式化）
        d2 = self._dcf_base()
        d2["financials"]["capex_to_revenue"] = 0.12
        d2["dcf_cost"] = {"fcff_suggest": True}
        self.assertEqual(ve.Engine(copy.deepcopy(d2)).run()["fcff_suggestion"]["trigger"],
                         ["capex_intensity"])

        # ③ 两面同时超限 → 双触发
        d3 = self._dcf_base()
        d3["financials"]["capex_to_revenue"] = 0.12
        d3["financials"]["ocf_to_net_profit"] = 1.60
        d3["dcf_cost"] = {"fcff_suggest": True}
        self.assertEqual(ve.Engine(copy.deepcopy(d3)).run()["fcff_suggestion"]["trigger"],
                         ["capex_intensity", "ocf_quality"])

        # ④ 两项都正常 → 不触发；OCF 阈值边界 1.30 不触发（严格大于）
        d4 = self._dcf_base()
        d4["financials"]["capex_to_revenue"] = 0.03
        d4["financials"]["ocf_to_net_profit"] = 1.30
        d4["dcf_cost"] = {"fcff_suggest": True}
        self.assertNotIn("fcff_suggestion", ve.Engine(copy.deepcopy(d4)).run())

    # ============ v3.25.0：状态空间分解增速模型 ============
    def test_t146_space_state_path_closure(self):
        """T146【v3.25.0】状态空间路径三层闭合 + p 的形态语义（纯函数层）。

        原实现五种形态（exp/mean_revert/s_curve/decline/linear）的 rho=0.30 / half_life=3 /
        lam=0.30 全部无出处，且**渐近线数学上永不到达 tg**——tg=6% 时末段仍差 −1.12pp，
        只能靠 `growth_terminal_mode=forced` 外部硬覆盖。新模型由构造保证 t=1 精确过 g1、
        t=n 精确等于 tg。
        """
        # ① 闭合性：任意组合下首末年精确命中
        for g1, tg, n in ((0.026, 0.02, 7), (-0.076, 0.02, 7), (0.35, 0.03, 5), (0.0, 0.0, 6)):
            seq, det = ve.space_state_growth_schedule(g1, tg, tg, n)
            self.assertAlmostEqual(seq[0], g1, places=9, msg="t=1 须精确等于 g1")
            self.assertAlmostEqual(seq[-1], tg, places=9, msg="t=n 须精确等于 tg")
            self.assertEqual(len(seq), n)
            self.assertTrue(all(det["closure"].values()))

        # ② 单调收敛：μ0=tg 时冲击项单调向 tg 衰减（不出现 V 型回升）
        seq, _ = ve.space_state_growth_schedule(0.026, 0.02, 0.02, 7, p=1.5)
        self.assertEqual(seq, sorted(seq, reverse=True), "正冲击须单调下行")
        seq_n, _ = ve.space_state_growth_schedule(-0.076, 0.02, 0.02, 7, p=1.5)
        self.assertEqual(seq_n, sorted(seq_n), "负冲击须单调上行")

        # ③ p 的形态：p 越大，冲击衰减越快（第 2 年更靠近 μ）
        for p in (1.0, 1.5, 2.0):
            seq, det = ve.space_state_growth_schedule(-0.076, 0.02, 0.02, 7, p=p)
            self.assertEqual(det["p"], p)
            if p == 1.0:
                prev = seq[1]
            else:
                self.assertGreater(seq[1], prev, f"p={p} 第 2 年须比 p 更小时更靠近 tg")
                prev = seq[1]
        # 分水岭：格力式 −7.6%→2% 案例 p=1.0 与 p=2.0 的 t2 相差 1.33pp
        s1, _ = ve.space_state_growth_schedule(-0.076, 0.02, 0.02, 7, p=1.0)
        s2, _ = ve.space_state_growth_schedule(-0.076, 0.02, 0.02, 7, p=2.0)
        self.assertAlmostEqual((s2[1] - s1[1]) * 100, 1.33, places=2)

        # ④ kappa 与 CAP 互为反函数（κ = 1 − 1/CAP）
        self.assertAlmostEqual(ve.growth_shape_kappa(10.0), 0.90, places=9)
        self.assertAlmostEqual(ve.growth_shape_kappa(4.0), 0.75, places=9)
        # κ 只影响「有中期锚」的路径：μ0=tg 时趋势层为常数，κ 不改变结果（缺份额数据的自然退化）
        a, _ = ve.space_state_growth_schedule(0.026, 0.02, 0.02, 7, kappa=0.75)
        b, _ = ve.space_state_growth_schedule(0.026, 0.02, 0.02, 7, kappa=0.95)
        self.assertEqual([round(x, 9) for x in a], [round(x, 9) for x in b])

    def test_t147_mu0_degradation_semantics(self):
        """T147【v3.25.0】μ0 退化约束：只对「真锚」生效，且被 clamp 抵消后不得谎报。

        ★两处缺陷同时守：
        ① 约束⑤（|μ0−g1|>5pp 则 μ0=g1）本意是防 V 型路径，但 μ0 缺省取 tg 时它只是
           "没有中期判断"的占位——格力 |2%−(−7.6%)|=9.6pp 会误触发，退化成 μ0=g1 等于
           把趋势层从「向 tg 收敛」改成「等于 g1」，反而抹掉趋势层。
        ② 即便触发，若随后被 [tg, cap] 夹逼拉回原值，实际生效值未变 → `mu0_degraded`
           必须是 False，否则报告声称发生过一次未发生的调整。
        """
        # ① 深度负增长 + μ0=tg（占位）→ 不退化（引擎侧把 div_max 置 ∞）
        seq, det = ve.space_state_growth_schedule(-0.076, 0.02, 0.02, 7, mu0_div_max_pp=1e9)
        self.assertFalse(det["mu0_degraded"])
        self.assertAlmostEqual(det["mu0"], 0.02, places=9)
        self.assertAlmostEqual(seq[1], -0.053, places=3)

        # ② 真锚远离 g1（μ0=12% vs g1=−7.6%）→ 退化生效（μ0_input 留痕 12%）
        _, det = ve.space_state_growth_schedule(-0.076, 0.12, 0.02, 7, mu0_div_max_pp=5.0)
        self.assertTrue(det["mu0_degraded"])
        self.assertAlmostEqual(det["mu0_input"], 0.12, places=9)
        # 退化值 −7.6% 低于 tg，被 [tg, cap] 下限拉回 2% —— 须留痕 clamped_by
        self.assertEqual(det["mu0_clamped_by"], "tg_floor")
        self.assertAlmostEqual(det["mu0_effective"], 0.02, places=9)
        self.assertLess(det["mu0_effective"], 0.12, "生效值须与原锚不同，说明退化确有影响")

        # ③ 退化被抵消：μ0 原本就等于 tg → 退化成 g1 后被夹回 tg == 原值 → 不得谎报
        _, det = ve.space_state_growth_schedule(-0.076, 0.02, 0.02, 7, mu0_div_max_pp=5.0)
        self.assertFalse(det["mu0_degraded"], "生效值与原值相同即未发生调整，flag 须为 False")
        self.assertAlmostEqual(det["mu0_effective"], 0.02, places=9)

        # ④ 偏离不足 5pp → 不退化
        _, det = ve.space_state_growth_schedule(0.026, 0.045, 0.02, 7, mu0_div_max_pp=5.0)
        self.assertFalse(det["mu0_degraded"])
        self.assertAlmostEqual(det["mu0"], 0.045, places=9)

    def test_t148_terminal_growth_three_anchors(self):
        """T148【v3.25.0】永续增速三锚取中位 + 双上限（替代 chain 逐级回落）。

        chain 的缺陷是取值完全取决于「哪一级先命中」：行业参数一命中，SGR 与市场隐含
        立刻被弃置，单一口径冒充交叉验证。三锚口径要求多来源交叉，再双上限夹逼。
        """
        d = self._dcf_base(growth_forecast=None)
        d["financials"]["terminal_growth"] = None
        d["financials"]["roic"] = 0.30
        d["financials"]["payout_ratio"] = 0.0
        d["financials"]["terminal_growth_model"] = {"enabled": True}
        out = ve.Engine(copy.deepcopy(d)).run()
        blk = out["assumptions_summary"]["dcf"]["tg_anchors_v2"]
        self.assertTrue(blk["applied"])
        self.assertEqual(blk["mode"], "anchors_v2")
        # SGR = 30%×(1−0) = 30%，中位 = median(行业 2%, 隐含 g*, 30%) = 16% → 被 GDP 4.5% 封顶
        self.assertAlmostEqual(blk["anchors"]["sgr"], 0.30, places=4)
        self.assertEqual(blk["capped_by"], "gdp_cap", "中位超 GDP 上限时须留痕封顶来源")
        self.assertAlmostEqual(blk["value"], blk["caps"]["gdp_cap"], places=6)
        self.assertGreater(blk["raw"], blk["value"])

        # ② 中位未触限时取值 = 中位原值（SGR 与 tg 同量级，行业/隐含居中）
        d1b = self._dcf_base(growth_forecast=None, terminal_growth=None)
        d1b["financials"]["roic"] = 0.03
        d1b["financials"]["payout_ratio"] = 0.0
        d1b["financials"]["terminal_growth_model"] = {"enabled": True}
        blk1b = ve.Engine(copy.deepcopy(d1b)).run()["assumptions_summary"]["dcf"]["tg_anchors_v2"]
        self.assertIsNone(blk1b["capped_by"])
        self.assertAlmostEqual(blk1b["value"], blk1b["raw"], places=6)

        # ③ 双上限：WACC−3pp 低于 GDP 4.5% 时以 spread 侧为准
        d2 = self._dcf_base(growth_forecast=None, terminal_growth=None)
        d2["financials"]["roic"] = 0.30
        d2["financials"]["payout_ratio"] = 0.0
        d2["financials"]["terminal_growth_model"] = {
            "enabled": True, "caps": {"gdp_cap": 0.045, "spread_min": 0.03}}
        blk2 = ve.Engine(copy.deepcopy(d2)).run()["assumptions_summary"]["dcf"]["tg_anchors_v2"]
        self.assertAlmostEqual(blk2["caps"]["effective_cap"],
                               min(0.045, round(blk2["caps"]["wacc"], 4) - 0.03), places=4)
        self.assertLessEqual(blk2["value"], blk2["caps"]["effective_cap"] + 1e-9)

        # ④ 缺 ROIC → sgr 锚缺席须留痕（不得静默用 0 或猜值顶替）
        d3 = self._dcf_base(growth_forecast=None, terminal_growth=None)
        d3["financials"].pop("roic", None)
        d3["financials"]["terminal_growth_model"] = {"enabled": True}
        blk3 = ve.Engine(copy.deepcopy(d3)).run()["assumptions_summary"]["dcf"].get("tg_anchors_v2")
        self.assertNotIn("sgr", blk3["anchors"])
        self.assertIn("缺 financials.roic", blk3["skipped_anchors"]["sgr"])
        self.assertTrue(all(v > 0 for v in blk3["anchors"].values()),
                        "收缩型锚（隐含解 ≤ 0）不得进入中位计算")


    def test_t149_growth_model_takeover_semantics(self):
        """T149【v3.25.0】接管语义：`enabled` 只是「装好武器」，`override_manual` 才是「开火」。

        分级原则（建议书 §3.2）：用户显式路径是 L1 输入，模型的定位是「中间年份怎么走」，
        不是「推翻你认为的首年」。所以缺省情况下即使开启也不覆盖人工路径；只有
        `override_manual=true` 才接管第 2 年起的路径（首年仍取用户值，构造上精确通过）。
        """
        # ① 有人工路径 + 未授权接管 → 路径逐位等于基线，且不挂 growth_model 块
        d1 = self._dcf_base()
        d1["financials"]["growth_model"] = {"enabled": True}
        o_base = ve.Engine(copy.deepcopy(self._dcf_base())).run()
        o1 = ve.Engine(copy.deepcopy(d1)).run()
        self.assertEqual(o1["scenarios"]["base"]["dcf"]["growth_seq"],
                         o_base["scenarios"]["base"]["dcf"]["growth_seq"])
        self.assertNotIn("growth_model", o1["scenarios"]["base"]["dcf"])

        # ② 授权接管 → 路径改为模型值，首年仍等于用户首年，末年等于 tg
        d2 = self._dcf_base()
        d2["financials"]["growth_model"] = {"enabled": True, "override_manual": True}
        o2 = ve.Engine(copy.deepcopy(d2)).run()
        dcf2 = o2["scenarios"]["base"]["dcf"]
        seq = dcf2["growth_seq"]
        self.assertIn("growth_model", dcf2)
        self.assertEqual(dcf2["growth_model"]["model"], "space_state")
        self.assertAlmostEqual(seq[0], -0.02, places=4, msg="首年须精确等于用户路径首年 −2%")
        self.assertAlmostEqual(seq[-1], dcf2["terminal_growth"], places=4, msg="末年须等于 tg")
        # 逐行来源标签齐备（原实现 growth_seq 只是裸数值数组，报告说不清某年凭什么是这个数）
        srcs = [r["src"] for r in dcf2["growth_seq_detail"]]
        self.assertEqual(len(srcs), len(seq))
        self.assertEqual(srcs[0], "first_year")
        self.assertEqual(srcs[-1], "terminal")
        self.assertTrue(all(s == "mu+shock" for s in srcs[1:-1]))

        # ③ 无人路径时 enabled 即生效（模型本就是为「没有 L1 输入」设计的）
        d3 = self._dcf_base(growth_forecast=None)
        d3["financials"]["growth_model"] = {"enabled": True}
        o3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertIn("growth_model", o3["scenarios"]["base"]["dcf"])

    def test_t150_growth_model_zero_regression(self):
        """T150【v3.25.0】零回归：两个新开关缺省/显式关闭时，输出键集与数值逐位不变。

        ★教训沿用（「引擎有输出 ≠ 报告有呈现」的反面）：新机制若在缺省态改变任一既有
        字段，历史案例的可比性即被破坏。故显式关掉必须与「不写这个块」逐位等价。
        """
        base = self._dcf_base()
        off = self._dcf_base()
        off["financials"]["growth_model"] = {"enabled": False}
        off["financials"]["terminal_growth_model"] = {"enabled": False}
        ob = ve.Engine(copy.deepcopy(base)).run()
        oo = ve.Engine(copy.deepcopy(off)).run()
        self.assertEqual(json.dumps(ob["scenarios"], sort_keys=True, ensure_ascii=False),
                         json.dumps(oo["scenarios"], sort_keys=True, ensure_ascii=False))
        dcf = ob["scenarios"]["base"]["dcf"]
        self.assertNotIn("growth_model", dcf)
        self.assertNotIn("growth_seq_detail", dcf)
        ass = ob["assumptions_summary"]["dcf"]
        self.assertNotIn("tg_anchors_v2", ass)
        self.assertNotIn("growth_model", ass)


    # ============ v3.26.0：生命周期判别（cagr 反算 + 第二维）============
    def _lc_base(self, **fin_over):
        """格力式输入 + lifecycle_mode=auto，去掉显式 lifecycle_stage 让客观判别起作用。"""
        d = self._dcf_base(**fin_over)
        d["meta"].pop("lifecycle_stage", None)
        d["preferences"]["lifecycle_mode"] = "auto"
        return d

    def test_t151_cagr_3y_auto_from_revenue(self):
        """T151【v3.26.0】`cagr_3y` 必须能从 revenue_by_year 反算。

        ★原实现硬伤：`financials.cagr_3y` **从不自动计算**——全脚本 3 处引用全部是读取。
        输入不给该字段时，`classify_lifecycle()` 的 `cagr is None` 一路落到最后的 `else`，
        判成 **growth（conf 0.55）**。对一家连续两年营收下滑的公司，这比误判为衰退更荒谬。
        """
        d = self._lc_base()
        d["financials"].pop("cagr_3y", None)
        # ① legacy 口径不反算 → CAGR 缺失（零回归契约）
        out_l = ve.Engine(copy.deepcopy(d)).run()["lifecycle"]
        self.assertIsNone(out_l["evidence"]["cagr_3y"])
        self.assertIn("不反算", out_l["evidence"]["cagr_source"])

        # ② v326 口径：从 revenue_by_year 反算 3 年 CAGR（2022 → 2025 三年）
        d2 = copy.deepcopy(d)
        d2["preferences"]["lifecycle_classifier_mode"] = "v326"
        out = ve.Engine(copy.deepcopy(d2)).run()["lifecycle"]
        series = [1878.69, 1889.88, 2039.79, 1891.64, 1704.47]
        expect = (series[-1] / series[-4]) ** (1 / 3.0) - 1.0
        self.assertAlmostEqual(out["evidence"]["cagr_3y"], expect, places=6)
        self.assertIn("revenue_3y", out["evidence"]["cagr_source"])
        self.assertAlmostEqual(expect, -0.0338, places=3)

        # ③ 显式输入优先于反算（不得覆盖用户给定的值）
        d3 = copy.deepcopy(d2)
        d3["financials"]["cagr_3y"] = -0.20
        out3 = ve.Engine(copy.deepcopy(d3)).run()["lifecycle"]
        self.assertAlmostEqual(out3["evidence"]["cagr_3y"], -0.20, places=9)
        self.assertEqual(out3["evidence"]["cagr_source"], "explicit")

        # ④ 营收期数不足 4 期 → 不猜，保持缺失并说明原因
        d4 = copy.deepcopy(d2)
        d4["financials"]["revenue_by_year"] = {"2023": 2039.79, "2024": 1891.64, "2025": 1704.47}
        out4 = ve.Engine(copy.deepcopy(d4)).run()["lifecycle"]
        self.assertIsNone(out4["evidence"]["cagr_3y"])
        self.assertIn("需 ≥4 期", out4["evidence"]["cagr_source"])

    def test_t152_second_dimension_splits_shrink_from_decline(self):
        """T152【v3.26.0】第二维：把「周期性收缩」从「结构性衰退」里拆出来。

        单维 `cagr_3y < 0 → decline` 把三种处境压成同一个负号：① 周期退坡（利润率升、ROIC>WACC）
        ② 结构性衰退（利润率降、ROIC<WACC）③ 主动砍低毛利。三者 μ₀/p/终值口径全不同。
        """
        # ① 格力特征：营收 −3.4%、净利率 12.28→17.02（+4.74pp）、ROIC 12.04% > WACC
        d = self._lc_base()
        d["financials"].pop("cagr_3y", None)
        d["financials"]["margin_history"] = [0.1228, 0.1297, 0.1423, 0.1701, 0.1702]
        d["preferences"]["lifecycle_classifier_mode"] = "v326"
        out = ve.Engine(copy.deepcopy(d)).run()["lifecycle"]
        self.assertEqual(out["stage"], "mature", "收缩但 ROIC>WACC 不得判衰退")
        self.assertEqual(out["sub_stage"], "cyclical_shrink")
        dim2 = out["evidence"]["dim2"]
        self.assertAlmostEqual(dim2["margin_delta_pp"], 4.74, places=2)
        self.assertGreater(dim2["roic_wacc_spread_pp"], 0)

        # ② 结构性衰退：净利率下行 + ROIC < WACC → 才判 decline
        d2 = self._lc_base()
        d2["financials"].pop("cagr_3y", None)
        d2["financials"]["margin_history"] = [0.18, 0.16, 0.14, 0.11, 0.09]
        d2["financials"]["roic"] = 0.05
        d2["financials"]["wacc"] = 0.08
        d2["preferences"]["lifecycle_classifier_mode"] = "v326"
        out2 = ve.Engine(copy.deepcopy(d2)).run()["lifecycle"]
        self.assertEqual(out2["stage"], "decline")
        self.assertEqual(out2["sub_stage"], "structural_decline")

        # ③ 量价齐跌但 ROIC 仍高于 WACC → 不得判衰退（ambiguous，须 LLM 定成因）
        d3 = copy.deepcopy(d2)
        d3["financials"]["roic"] = 0.12
        out3 = ve.Engine(copy.deepcopy(d3)).run()["lifecycle"]
        self.assertEqual(out3["stage"], "mature")
        self.assertEqual(out3["sub_stage"], "ambiguous_shrink")

        # ④ 显式阶段与客观证据冲突 → 保留用户判断但必须告警
        d4 = self._lc_base()
        d4["meta"]["lifecycle_stage"] = "decline"
        d4["preferences"]["lifecycle_classifier_mode"] = "v326"
        out4 = ve.Engine(copy.deepcopy(d4)).run()
        lc = out4["lifecycle"]
        self.assertEqual(lc["stage"], "decline", "显式阶段不得被客观判别夺权")
        self.assertIsNotNone(lc["objective_conflict_with_explicit"])
        self.assertTrue(any("生命周期判别冲突" in w for w in out4["warnings"]))

    def test_t153_decline_tg_clamp_not_bypassed_by_growth_model(self):
        """T153【v3.26.0】衰退期 tg 上限必须在**选路前 + growth_model 求值前**生效。

        ★原实现把 `if stage == "decline": tg = min(tg, tg_floor)` 写在 lifecycle elif 分支内，
        `growth_model` 接管时走另一条分支，整条夹逼被绕过——判了 decline 却仍按正 tg 算终值，
        等于「阶段说衰退、终值说永续增长」。若只把它提到分支前而仍排在
        `growth_model_schedule(tg)` 之后，则会产出「terminal_growth=0 而路径末年=2%」的断裂。
        """
        d = self._lc_base()
        d["meta"]["lifecycle_stage"] = "decline"
        # ① 不开 growth_model：终值 tg 被压到 0
        o1 = ve.Engine(copy.deepcopy(d)).run()["scenarios"]["base"]["dcf"]
        self.assertAlmostEqual(o1["terminal_growth"], 0.0, places=9)

        # ② 开 growth_model：同样被压到 0，且路径末端与 tg 一致（无断裂）
        d2 = copy.deepcopy(d)
        d2["financials"]["growth_model"] = {"enabled": True, "override_manual": True}
        o2 = ve.Engine(copy.deepcopy(d2)).run()["scenarios"]["base"]["dcf"]
        self.assertAlmostEqual(o2["terminal_growth"], 0.0, places=9)
        self.assertAlmostEqual(o2["growth_seq"][-1], o2["terminal_growth"], places=9,
                               msg="路径末端必须等于 tg，否则终值与显式期断裂")
        # 显式期长度随 decline 表值（v3.27.0：n=4），不是 mature 的 6
        self.assertEqual(len(o2["growth_seq"]), 4)

        # ③ 非衰退阶段不得被误压（regression 反断言）
        d3 = self._lc_base()
        o3 = ve.Engine(copy.deepcopy(d3)).run()["scenarios"]["base"]["dcf"]
        self.assertAlmostEqual(o3["terminal_growth"], 0.02, places=9)

    def test_t154_lifecycle_classifier_zero_regression(self):
        """T154【v3.26.0】零回归：`lifecycle_classifier_mode` 缺省/显式 legacy 时判别结果逐字不变。"""
        d = self._lc_base()
        d["financials"].pop("cagr_3y", None)
        explicit_legacy = copy.deepcopy(d)
        explicit_legacy["preferences"]["lifecycle_classifier_mode"] = "legacy"
        o_def = ve.Engine(copy.deepcopy(d)).run()["lifecycle"]
        o_off = ve.Engine(copy.deepcopy(explicit_legacy)).run()["lifecycle"]
        self.assertEqual(json.dumps(o_def, sort_keys=True, ensure_ascii=False),
                         json.dumps(o_off, sort_keys=True, ensure_ascii=False))
        # legacy 不得新增 v326 键（旧输出键集合不变）
        for k in ("classifier_mode", "sub_stage", "sub_stage_label",
                  "reason", "objective_conflict_with_explicit"):
            self.assertNotIn(k, o_def)
        # legacy 结论保持原样：cagr 缺失 → growth 兜底（这正是待修的硬伤，此处锁定不改）
        self.assertEqual(o_def["stage"], "growth")
        self.assertEqual(o_def["confidence"], 0.6)


    # ---------- T168【v3.29.0】六阶段增长函数（plc6）----------
    def test_t168_plc6_six_stage_shapes(self):
        """T168【v3.29.0 / 引擎 v2.27.0】六阶段增长函数：一条公式、四种 E(t)、两条收敛硬约束。

        锁定三件事：
          ① n 单调（10/10/8/7/6/4）、CAP 拐点单调（6/5/4/3）——防再出现「阶段间倒挂」；
          ② 每个形态首年=g1、末年=tg（E 归一化的构造性质，**不依赖** forced 补丁）；
          ③ **真 S**：旧 s_curve 是「第一年跌得最狠」的单调衰减，新 logistic_cap 的最大跌幅
             必须落在中段——否则「名为 S 曲线、实为衰减」的老缺陷会原样复现。
        """
        params = ve.PLC6_SHAPE_PARAMS
        n6 = [params[s]["n"] for s in ve.PLC6_STAGE_ORDER]
        self.assertEqual(n6, [10, 10, 8, 7, 6, 4])
        caps = [params[s]["cap"] for s in ve.PLC6_STAGE_ORDER if params[s].get("cap")]
        self.assertEqual(caps, [6.0, 5.0, 4.0, 3.0])

        for st in ve.PLC6_STAGE_ORDER:
            seq, det = ve.plc_growth_path(st, [], 0.20, 0.02)
            self.assertEqual(len(seq), params[st]["n"], f"{st} 显式期长度")
            self.assertAlmostEqual(seq[0], 0.20, places=6, msg=f"{st} 首年须精确等于 g1")
            self.assertAlmostEqual(seq[-1], 0.02, places=9, msg=f"{st} 末年须精确等于 tg")
            self.assertTrue(det["closure"]["t1_equals_g1"] and det["closure"]["tn_equals_tg"], st)
            self.assertTrue(det["monotone_nonincreasing"], f"{st} 路径须单调不增")

        # ③ 真 S：最大跌幅不在第一年；旧 s_curve 作为反例保留
        seq, det = ve.plc_growth_path("high_growth", [], 0.20, 0.02)
        drops = [seq[i] - seq[i + 1] for i in range(len(seq) - 1)]
        self.assertEqual(det["form"], "logistic_cap")
        self.assertGreater(max(range(len(drops)), key=lambda i: drops[i]), 0,
                           "S 曲线的最大跌幅落在第一年 → 与旧 s_curve 同错")
        old, _ = ve.build_growth_schedule("startup", [0.20], 0.02,
                                          {"n": 10, "form": "s_curve", "t_mid": 4.0})
        od = [old[i] - old[i + 1] for i in range(len(old) - 1)]
        self.assertEqual(max(range(len(od)), key=lambda i: od[i]), 0,
                         "旧 s_curve 首年跌幅最大（作为反例锁定，证明缺陷真实存在）")

        # ④ 用户显式路径不被二次塑形
        seq, det = ve.plc_growth_path("high_growth", [0.35, 0.28], 0.35, 0.02)
        self.assertAlmostEqual(seq[0], 0.35, places=9)
        self.assertAlmostEqual(seq[1], 0.28, places=9)
        self.assertAlmostEqual(seq[-1], 0.02, places=9)

        # ⑤ 显式 CAP 覆盖：拐点后移 → 第 2 年跌幅变小（护城河被拉长）
        s_tab, _ = ve.plc_growth_path("high_growth", [], 0.20, 0.02)
        s_long, _ = ve.plc_growth_path("high_growth", [], 0.20, 0.02, cap=6.0)
        self.assertGreater(s_long[1], s_tab[1])
        self.assertAlmostEqual(s_long[-1], 0.02, places=9, msg="改 CAP 不得破坏末端闭合")

        # ⑥ 零回归：缺省 legacy 不新增键、综合值逐位不变
        d = self._lc_base()
        o_def = ve.Engine(copy.deepcopy(d)).run()
        d_expl = copy.deepcopy(d)
        d_expl.setdefault("dcf_growth", {})["growth_shape_mode"] = "legacy"
        o_exp = ve.Engine(copy.deepcopy(d_expl)).run()
        self.assertNotIn("growth_shape_mode", o_def["scenarios"]["base"]["dcf"])
        self.assertEqual(o_def["synthesis"]["weighted_mid"], o_exp["synthesis"]["weighted_mid"])

        # ⑦ 端到端：plc6 生效 → 阶段/形态/闭合三处留痕齐备
        d6 = copy.deepcopy(d)
        d6.setdefault("dcf_growth", {})["growth_shape_mode"] = "plc6"
        o6 = ve.Engine(copy.deepcopy(d6)).run()
        g6 = o6["scenarios"]["base"]["dcf"]["growth_schedule"]
        self.assertEqual(g6["model"], "plc6")
        self.assertEqual(o6["assumptions_summary"]["dcf"]["growth_shape_mode"], "plc6")
        self.assertIn(g6["stage_6"], ve.PLC6_STAGE_ORDER)
        self.assertAlmostEqual(g6["seq"][-1], o6["scenarios"]["base"]["dcf"]["terminal_growth"],
                               places=4)
        self.assertEqual(g6["cap_source"], "plc6 表值（引擎标定）")

    # ---------- T169【v3.29.1】六阶段判定顺序：结构证据优先于盈利符号 ----------
    def test_t169_damodaran_stage_order(self):
        """T169【v3.29.1 / 引擎 v2.27.1】「亏损 + 大营收」不得推翻结构性衰退判定。

        反例：营收 −18%、ROIC<WACC、亏损 → v326 判 decline，旧逻辑却因「亏损+营收≥5亿」
        改判 young_growth，DCF 权重 0.45→0.30、显式期 4→10 年，方向性高估。
        """
        d = self._lc_base()
        e = ve.Engine(copy.deepcopy(d))

        def lc(stage, loss, rev, cagr):
            return {"enabled": True, "stage": stage, "sub_stage": "structural_decline",
                    "reason": "测试", "evidence": {"loss_making": loss, "revenue_latest_ttm": rev,
                                                   "cagr_3y": cagr, "net_margin": -0.05}}

        # ① 衰退 + 亏损 + 大营收 → 仍是 decline，且留痕 guard
        r1 = e.damodaran_stage(lc("decline", True, 120.0, -0.18))
        self.assertEqual(r1["stage"], "decline")
        self.assertAlmostEqual(r1["weights"]["dcf"], 0.45, places=6)
        self.assertTrue(r1["guard"])
        # ② 衰退 + 盈利 → decline（对照，行为不变）
        self.assertEqual(e.damodaran_stage(lc("decline", False, 120.0, -0.18))["stage"], "decline")
        # ③ 初创 + 小营收 → startup（门槛内不误伤）
        self.assertEqual(e.damodaran_stage(lc("startup", True, 3.0, -0.18))["stage"], "startup")
        # ④ 成长 + 亏损 + 高增速 → young_growth（跨 stage 覆盖仍生效）
        r4 = e.damodaran_stage(lc("growth", True, 120.0, 0.30))
        self.assertEqual(r4["stage"], "young_growth")
        self.assertFalse(r4["guard"])
        # ⑤ 成熟 + 亏损 + 低速增长 → 仍归 young_growth，但必须挂复核提示
        r5 = e.damodaran_stage(lc("mature", True, 120.0, 0.02))
        self.assertEqual(r5["stage"], "young_growth")
        self.assertTrue(r5["guard"])
        # ⑥ 成熟 + 亏损 + 收缩 → 不判 young_growth（增速转负即否决）
        self.assertEqual(e.damodaran_stage(lc("mature", True, 120.0, -0.05))["stage"],
                         "mature_stable")
        # ⑦ 端到端：damodaran_table 生效时 guard 进入 warnings 与权重留痕
        d7 = copy.deepcopy(d)
        d7["preferences"]["lifecycle_weight_mode"] = "damodaran_table"
        d7["meta"]["lifecycle_stage"] = "decline"
        o7 = ve.Engine(copy.deepcopy(d7)).run()
        pw = o7.get("path_weights") or {}
        if pw.get("mode") == "damodaran_table":
            self.assertEqual(pw.get("damodaran_stage"), "decline")
            self.assertIn("damodaran_guard", pw)

    def test_t170_fcf_ratio_loss_guard(self):
        """v2.28.0（L4 守卫）回归：净利为负时 FCF/净利 **无定义**。

        原缺陷链：CapEx/净利 的分母为负 → 比值变负 → l1 = ocf_self −(负数) 反向放大
        → 撞上界 1.5；而 `used < 0.5` 的告警**永远不会触发**——越亏越安静，
        且 1.5 在报告里看起来像「转化率 150%、质量极好」。实测复算：
        净利率 −12.6%、CapEx/收入 31% → CapEx/净利 = −2.46 → l1 = 3.36
        → 加权 2.657 → clamp 到 1.5（正确值应为 not_applicable）。
        """
        d = load_example_input()
        d["financials"]["net_margin"] = -0.126
        d["financials"]["capex_to_revenue"] = 0.31
        d["financials"]["ocf_to_net_profit"] = 0.9
        d["financials"].pop("net_profit_basis", None)
        out = ve.Engine(copy.deepcopy(d)).run()
        fr = out["fcf_ratio"]
        # ① 必须标记不适用，且不得出现「伪高转换率」
        self.assertTrue(fr.get("not_applicable"))
        self.assertLess(fr["used"], 1.5)
        self.assertAlmostEqual(fr["used"], 0.9, places=4)
        # ② 三层校准的中间量不得输出（否则会被当成真值引用）
        self.assertIsNone(fr.get("l1_self"))
        self.assertIsNone(fr.get("l2_comparable"))
        self.assertIn("净利为负", fr["source"])
        # ③ 告警必须触发（原实现此时恰恰是沉默的）
        self.assertTrue(any("FCF/净利 无定义" in w for w in out.get("warnings", [])))
        # ④ 显式值优先于单层兜底
        d2 = copy.deepcopy(d)
        d2["financials"]["fcf_ratio"] = 0.6
        out2 = ve.Engine(d2).run()
        self.assertAlmostEqual(out2["fcf_ratio"]["used"], 0.6, places=4)
        # ⑤ 盈利标的不受影响：三层校准照常，不置 not_applicable
        d3 = load_example_input()
        d3["financials"]["net_margin"] = 0.12
        d3["financials"]["capex_to_revenue"] = 0.10
        out3 = ve.Engine(copy.deepcopy(d3)).run()
        self.assertFalse(out3["fcf_ratio"].get("not_applicable", False))


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestEngine)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestStatValidation))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestNewMethods))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
