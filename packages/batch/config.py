# -*- coding: utf-8 -*-
"""批跑服务配置。无密钥：仅访问公开行情与披露接口；技能目录在仓库外（陈老师成果不公开）。"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get('VALUATION_RUNTIME', str(REPO / 'runtime')))
CACHE = RUNTIME / 'cache'
JOBS = RUNTIME / 'jobs'

# 估值跑批工作台存档目录：每次跑批完成后把 HTML 报告复制到这里，
# 由 dsh 工作区注册为「估值跑批工作台」文件夹供左侧面板浏览。
REPORTS_DIR = Path(os.environ.get(
    'VALUATION_REPORTS_DIR',
    str(Path.home() / '.dsh-valuation' / 'valuation-reports'),
))

SKILL_DIR = Path(os.environ.get(
    'VALUATION_SKILL_DIR',
    str(Path.home() / '.dsh-valuation' / 'agents' / 'skills' / 'llm-ipo-valuation'),
))

# 个股级输入覆写（人工核定的 rNPV 管线参数等）：<code>.json（secucode 点换下划线）；缺省不影响任何股票。
OVERRIDES = Path(os.environ.get(
    'VALUATION_OVERRIDES_DIR',
    str(Path.home() / '.dsh-valuation' / 'overrides'),
))

# 东财 datacenter 指数成分 TYPE 映射（已探测核实：1=沪深300，2=上证50，4=科创50，11=上证180）
# 'sse' 走东财 push2 行情列表（沪市主板 A + 科创板全量），datacenter 成分表不覆盖上证综指。
INDEX_TYPES = {'sh50': '2', 'hs300': '1', 'kc50': '4', 'sh180': '11', 'sse': 'sse'}
INDEX_NAMES = {'sh50': '上证50', 'hs300': '沪深300', 'kc50': '科创50', 'sh180': '上证180', 'sse': '上证综指'}
INDEX_TENCENT = {'sh50': 'sh000016', 'hs300': 'sh000300', 'kc50': 'sh000688', 'sh180': 'sh000010',
                 'sse': 'sh000001'}

PORT = int(os.environ.get('VALUATION_BATCH_PORT', '3089'))
