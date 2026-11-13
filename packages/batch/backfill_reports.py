# -*- coding: utf-8 -*-
"""一次性回填：把 runtime/jobs 下历史任务的 HTML 报告复制到 REPORTS_DIR（估值跑批工作台存档目录）。"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import JOBS, REPORTS_DIR

n = 0
for jd in sorted(JOBS.iterdir()):
    if not jd.is_dir():
        continue
    dst = REPORTS_DIR / jd.name
    dst.mkdir(parents=True, exist_ok=True)
    for f in jd.glob('*.html'):
        shutil.copy2(f, dst / f.name)
        n += 1
print('backfilled %d html files: %s -> %s' % (n, JOBS, REPORTS_DIR))
