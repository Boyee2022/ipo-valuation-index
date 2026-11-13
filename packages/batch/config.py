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

# 东财 datacenter 指数成分 TYPE 映射（上证180/科创50 待核实后追加）
INDEX_TYPES = {'sh50': '2'}
INDEX_NAMES = {'sh50': '上证50'}
INDEX_TENCENT = {'sh50': 'sh000016'}

PORT = int(os.environ.get('VALUATION_BATCH_PORT', '3089'))
