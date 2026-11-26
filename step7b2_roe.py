# -*- coding: utf-8 -*-
"""第 7 步（b2）：RIM 的 ROE 与 B0 同口径（归母净利 / 归母普通股权益）。

指数成分 ROE（600036 为 10.12%）与 B0（F10 BPS×总股本，FY2025 归母普通股权益）不同口径：
F10 加权 ROE 13.44% 的分母含其他权益工具，直接用会与 B0 混口径。RIM 采用 NP/B0。
"""
import shutil
import sys
import time
from pathlib import Path

f = Path.home() / 'workspace/valuation-workbench/packages/batch/input_builder.py'
s = f.read_text(encoding='utf-8')
if 'roe_rim' in s:
    print('already patched')
    sys.exit(0)

edits = [
    ("""        roe_dec = inp['financials'].get('roe')
        if roe_dec is None and b0 and np_:
            roe_dec = round(np_ / b0, 4)
        payout = 0.30
""",
     """        roe_dec = inp['financials'].get('roe')
        # RIM 的 ROE 必须与 B0 同口径（归母普通股权益）：优先 归母净利 / B0，其次指数成分 ROE
        roe_rim = round(float(np_) / float(b0), 4) if (b0 and np_ and np_ > 0) else roe_dec
        payout = 0.30
"""),
    ("""        if b0 and roe_dec is not None:
            inp['rim'] = {
                'enabled': True,
                'book_value_equity': b0,
                'roe_steady': round(float(roe_dec), 4),
""",
     """        if b0 and roe_rim is not None:
            inp['rim'] = {
                'enabled': True,
                'book_value_equity': b0,
                'roe_steady': round(float(roe_rim), 4),
"""),
    ("""            _fs_items.append('RIM：B0 %.2f 亿元（FY%s，BPS %s × 总股本 %.2f 亿股）、ROE %.2f%%、Ke %.2f%%' % (
                b0, be.get('year') or '—', be.get('bps'), (be.get('total_share') or 0) / 1e8,
                roe_dec * 100, ke * 100))
""",
     """            _fs_items.append('RIM：B0 %.2f 亿元（FY%s，BPS %s × 总股本 %.2f 亿股）、ROE %.2f%%（归母净利/B0）、Ke %.2f%%' % (
                b0, be.get('year') or '—', be.get('bps'), (be.get('total_share') or 0) / 1e8,
                roe_rim * 100, ke * 100))
"""),
    ("""                g1 = max(0.0, min(0.10, round(float(roe_dec) * (1 - payout), 4)))
""",
     """                g1 = max(0.0, min(0.10, round(float(roe_rim) * (1 - payout), 4)))
"""),
]
for i, (old, new) in enumerate(edits, 1):
    if s.count(old) != 1:
        sys.exit('[edit %d] anchor count = %d' % (i, s.count(old)))
    s = s.replace(old, new, 1)

ts = time.strftime('%Y%m%d_%H%M%S')
shutil.copy2(f, f.with_suffix(f.suffix + '.bak.%s' % ts))
f.write_text(s, encoding='utf-8')
print('patched roe_rim (backup .bak.%s)' % ts)