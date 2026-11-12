# -*- coding: utf-8 -*-
"""批跑服务配置。无密钥：仅访问公开行情与披露接口；技能目录在仓库外（陈老师成果不公开）。"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get('VALUATION_RUNTIME', str(REPO / 'runtime')))
CACHE = RUNTIME / 'cache'
JOBS = RUNTIME / 'jobs'

SKILL_DIR = Path(os.environ.get(
    'VALUATION_SKILL_DIR',
    str(Path.home() / '.dsh-valuation' / 'agents' / 'skills' / 'llm-ipo-valuation'),
))

# 东财 datacenter 指数成分 TYPE 映射（上证180/科创50 待核实后追加）
INDEX_TYPES = {'sh50': '2'}
INDEX_NAMES = {'sh50': '上证50'}
INDEX_TENCENT = {'sh50': 'sh000016'}

PORT = int(os.environ.get('VALUATION_BATCH_PORT', '3089'))
