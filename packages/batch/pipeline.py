# -*- coding: utf-8 -*-
"""跑批执行：并行逐券「输入组装→引擎→统计校验→HTML 报告→八项机检」，按权重合成拟合点位。

- 失败券自动跳过并留痕（对应需求「单券估不出 → 跳过」，不阻断整批）；
- 拟合点位 = 指数收盘 × Σ(权重×每股估值) / Σ(权重×收盘价)，跳过券不计入分子分母；
- 任务状态落盘 runtime/jobs/<id>/state.json，服务重启后可读。
"""
import html
import json
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import dsources
import input_builder
from config import INDEX_NAMES, INDEX_TENCENT, INDEX_TYPES, JOBS, REPORTS_DIR, SKILL_DIR

PY = sys.executable
ENGINE = SKILL_DIR / 'scripts' / 'valuation_engine.py'
STAT = SKILL_DIR / 'scripts' / 'stat_validation.py'
REPORT = SKILL_DIR / 'scripts' / 'report_generator.py'
CHECK = SKILL_DIR / 'scripts' / 'html_check.py'

_jobs = {}
_jobs_lock = threading.Lock()
_state_lock = threading.RLock()


def _now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def _run(cmd, timeout):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _tail(s, n=200):
    s = (s or '').strip()
    return s[-n:] if len(s) > n else s


def _job_dir(job_id):
    return JOBS / job_id


def _save(job):
    """落盘状态（内部持有 _state_lock；调用方须在同一锁内完成变更，避免序列化与变更并发）。"""
    with _state_lock:
        jdir = _job_dir(job['id'])
        jdir.mkdir(parents=True, exist_ok=True)
        tmp = jdir / ('state.json.tmp.%d' % threading.get_ident())
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(jdir / 'state.json')


def _bump_done_and_save(job):
    if job is None:
        return
    job['done'] = sum(1 for x in job['rows'] if x.get('status') in ('ok', 'skip'))
    _save(job)


def start(params):
    """创建任务并后台执行。params: {index, parallel, stat_n, weights{dcf,comp,sent}, sentiment_rounds}"""
    job_id = 'job_%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), uuid.uuid4().hex[:6])
    job = {
        'id': job_id,
        'index': params.get('index', 'sh50'),
        'parallel': int(params.get('parallel') or 3),
        'stat_n': int(params.get('stat_n') or 1000),
        'weights': params.get('weights') or {'dcf': 0.3, 'comp': 0.5, 'sent': 0.2},
        'sentiment_rounds': int(params.get('sentiment_rounds') or 10),
        'created': _now(),
        'state': 'running',
        'done': 0,
        'total': 0,
        'rows': [],
        'summary': None,
        'error': None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    _save(job)
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
    return job_id


def get(job_id):
    """从磁盘读任务状态（服务可重启不丢历史）。"""
    f = _job_dir(job_id) / 'state.json'
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding='utf-8'))


def list_jobs():
    if not JOBS.exists():
        return []
    out = []
    for jd in sorted(JOBS.iterdir(), reverse=True):
        sf = jd / 'state.json'
        if not sf.exists():
            continue
        try:
            j = json.loads(sf.read_text(encoding='utf-8'))
            s = j.get('summary') or {}
            out.append({
                'id': j.get('id'), 'index': j.get('index'), 'created': j.get('created'),
                'state': j.get('state'), 'done': j.get('done'), 'total': j.get('total'),
                'components_as_of': j.get('components_as_of'),
                'fitted_point': s.get('fitted_point'), 'index_close': s.get('index_close'),
                'ok': s.get('ok'), 'skip': s.get('skip'),
            })
        except Exception:
            continue
    return out


def _worker(job_id, row, universe, params):
    job = _jobs.get(job_id)
    jdir = _job_dir(job_id)
    try:
        with _state_lock:
            row['status'] = 'running'
            _save(job)
        stem = row['secucode'].replace('.', '_')
        inp = input_builder.build_input(row, universe, params, job['components_as_of'] if job else None)
        inp_f = jdir / ('%s.input.json' % stem)
        out_f = jdir / ('%s.out.json' % stem)
        stat_f = jdir / ('%s.stat.json' % stem)
        rep_f = jdir / ('%s.report.html' % stem)
        inp_f.write_text(json.dumps(inp, ensure_ascii=False, indent=2), encoding='utf-8')

        r = _run([PY, str(ENGINE), str(inp_f), '-o', str(out_f)], 600)
        if r.returncode != 0:
            raise RuntimeError('估值引擎失败: %s' % _tail(r.stderr or r.stdout))
        eng = json.loads(out_f.read_text(encoding='utf-8'))

        r = _run([PY, str(STAT), str(inp_f), str(out_f), '-o', str(stat_f),
                  '--n', str(params.get('stat_n') or 1000), '--seed', '42'], 1200)
        if r.returncode != 0:
            raise RuntimeError('统计校验失败: %s' % _tail(r.stderr or r.stdout))

        r = _run([PY, str(REPORT), str(out_f), '-o', str(rep_f),
                  '--stat', str(stat_f), '--input', str(inp_f)], 600)
        if r.returncode != 0:
            raise RuntimeError('报告生成失败: %s' % _tail(r.stderr or r.stdout))

        r = _run([PY, str(CHECK), str(rep_f), '--output', str(out_f)], 300)
        check_ok = r.returncode == 0

        syn = eng.get('synthesis') or {}
        shares = (inp.get('financials') or {}).get('total_shares_after_issue')
        mid = syn.get('weighted_mid')
        per_share = round(mid / shares, 2) if mid is not None and shares else None
        with _state_lock:
            row.update({
                'status': 'ok',
                'weighted_mid': mid,
                'per_share': per_share,
                'interval': syn.get('interval'),
                'four_part': {k: (v.get('value') if isinstance(v, dict) else v)
                              for k, v in (syn.get('four_part') or {}).items()
                              if k in ('part1_dcf', 'part2_comparable_quality', 'part3_market_sentiment')},
                'confidence_level': (eng.get('confidence') or {}).get('level'),
                'stage_label': (eng.get('lifecycle') or {}).get('stage_label'),
                'basis': (eng.get('net_profit_basis_used') or {}).get('basis'),
                'warnings': (eng.get('warnings') or [])[:6],
                'check_ok': check_ok,
                'report': rep_f.name,
            })
            _bump_done_and_save(job)
    except Exception as e:
        with _state_lock:
            row['status'] = 'skip'
            row['error'] = str(e)[:300]
            _bump_done_and_save(job)


def _summary_html(job):
    s = job.get('summary') or {}
    rows = job.get('rows') or []
    esc = html.escape
    body_rows = []
    for r in rows:
        st = r.get('status')
        if st == 'ok':
            tag = '<span style="color:#0f766e">估值完成</span>'
            val = '%s' % ('%.2f' % r['per_share'] if r.get('per_share') is not None else '—')
            conf = esc(str(r.get('confidence_level') or '—'))
            link = '<a href="./%s">报告</a>' % esc(r.get('report', ''))
        else:
            tag = '<span style="color:#b45309">跳过</span>'
            val = '—'
            conf = '—'
            link = esc(str(r.get('error') or '')[:80])
        ratio = ''
        if st == 'ok' and r.get('per_share') and r.get('close'):
            ratio = '%.2f' % (r['per_share'] / r['close'])
        body_rows.append(
            '<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%.2f%%</td><td>%s</td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                r.get('idx', 0) + 1, esc(r.get('name') or ''), esc(str(r.get('secucode') or '')),
                esc(str(r.get('industry') or '—')),
                (r.get('weight') or 0), '%.2f' % r['close'] if r.get('close') is not None else '—',
                val, ratio, conf, tag, link))
    fitted = s.get('fitted_point')
    return """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>估值跑批总结报告 · %(index)s · %(jobid)s</title>
<style>
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:0;background:#f5f7fa;color:#1f2937}
.wrap{max-width:1100px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:24px;margin:0 0 6px}h2{font-size:18px;margin:26px 0 10px}
.meta{color:#6b7280;font-size:13px;margin-bottom:18px}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px 20px;min-width:210px}
.card b{font-size:28px;display:block;margin:4px 0 2px}.card span{color:#6b7280;font-size:12px}
table{width:100%%;border-collapse:collapse;background:#fff;font-size:13px}
th,td{border-bottom:1px solid #eef0f3;padding:7px 9px;text-align:right}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3),
th:nth-child(4),td:nth-child(4),th:nth-child(11),td:nth-child(11){text-align:left}
thead th{background:#0e7490;color:#fff;font-weight:600;text-align:right}
thead th:first-child,thead th:nth-child(2),thead th:nth-child(3),thead th:nth-child(4),thead th:nth-child(11){text-align:left}
.note{color:#6b7280;font-size:12px;line-height:1.7;margin-top:14px}
a{color:#0e7490}
</style></head><body><div class="wrap">
<h1>%(index)s 估值跑批总结报告</h1>
<div class="meta">任务 %(jobid)s · 数据时点（成分权重）%(as_of)s · 生成时间 %(ts)s</div>
<div class="cards">
<div class="card"><span>拟合点位（陈老师口径）</span><b>%(fitted)s</b><span>指数收盘 %(close)s</span></div>
<div class="card"><span>样本</span><b>%(total)d</b><span>成分券</span></div>
<div class="card"><span>出估值 / 跳过</span><b>%(ok)d / %(skip)d</b><span>跳过券不计入合成</span></div>
</div>
<h2>逐券结果</h2>
<table><thead><tr><th>#</th><th>名称</th><th>代码</th><th>行业</th><th>权重</th><th>收盘价</th>
<th>估值中枢/股</th><th>估值/价</th><th>置信度</th><th>状态</th><th>报告/原因</th></tr></thead>
<tbody>%(rows)s</tbody></table>
<div class="note">
拟合点位 = 指数收盘 × Σ(权重×每股估值) / Σ(权重×收盘价)，跳过券不计入分子分母。<br>
口径：成分权重为前一日收盘权重（东财指数成分表）；估值中枢=引擎综合中枢÷总股本；WACC/永续增速未显式给定，
由引擎行业参数底座自动解析；舆情=东财免费公开数据（近30天新闻搜索+股吧帖）词频+规则打分，情绪字段显式传入引擎。<br>
本报告由估值跑批管线自动生成，仅作探索性研究参考，不构成投资建议。
</div></div></body></html>""" % {
        'index': esc(INDEX_NAMES.get(job.get('index'), job.get('index'))),
        'jobid': esc(job['id']), 'as_of': esc(str(job.get('components_as_of') or '—')),
        'ts': _now(), 'fitted': ('%.2f' % fitted) if fitted is not None else '—',
        'close': ('%.2f' % s.get('index_close')) if s.get('index_close') is not None else '—',
        'total': job.get('total', 0), 'ok': s.get('ok', 0), 'skip': s.get('skip', 0),
        'rows': ''.join(body_rows),
    }


def _finalize(job):
    ok = [r for r in job['rows'] if r.get('status') == 'ok' and r.get('per_share') is not None]
    w_v = w_p = 0.0
    for r in ok:
        w = r.get('weight') or 0
        w_v += w * r['per_share']
        w_p += w * (r.get('close') or 0)
    idx = job.get('index_close') or 0
    fitted = round(idx * w_v / w_p, 2) if w_p > 0 and idx else None
    with _state_lock:
        job['summary'] = {
            'fitted_point': fitted,
            'index_close': idx,
            'ok': len(ok),
            'skip': sum(1 for r in job['rows'] if r.get('status') == 'skip'),
            'total': job['total'],
        }
        job['state'] = 'done'
        job['finished'] = _now()
        _save(job)
    try:
        (_job_dir(job['id']) / 'summary.html').write_text(_summary_html(job), encoding='utf-8')
    except Exception as e:
        with _state_lock:
            job['summary_warning'] = 'summary.html 生成失败: %s' % str(e)[:200]
            _save(job)
    try:
        _archive_reports(job)
    except Exception as e:
        with _state_lock:
            job['archive_warning'] = '报告存档失败: %s' % str(e)[:200]
            _save(job)


def _archive_reports(job):
    """把本任务的 HTML 报告复制到「估值跑批工作台」存档目录（供 dsh 左侧工作区浏览）。"""
    archive = REPORTS_DIR / job['id']
    archive.mkdir(parents=True, exist_ok=True)
    for f in _job_dir(job['id']).glob('*.html'):
        shutil.copy2(f, archive / f.name)


def run_job(job_id):
    job = _jobs[job_id]
    try:
        itype = INDEX_TYPES[job['index']]
        comp = dsources.components(itype)
        job['components_as_of'] = comp['as_of']
        job['total'] = len(comp['rows'])
        job['rows'] = [dict(r, idx=i, status='pending') for i, r in enumerate(comp['rows'])]
        try:
            ix = dsources.index_quote(INDEX_TENCENT[job['index']])
            today = time.strftime('%Y-%m-%d')
            job['index_close'] = ix.get('prev_close') if comp['as_of'] < today else ix.get('price')
            if job['index_close'] is None:
                job['index_close'] = ix.get('price')
        except Exception:
            job['index_close'] = None
        _save(job)
        universe = dsources.peer_universe()['rows']
        with ThreadPoolExecutor(max_workers=max(1, job['parallel'])) as ex:
            futs = [ex.submit(_worker, job_id, r, universe, job) for r in job['rows']]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    job['worker_error'] = str(e)[:300]
        with _state_lock:
            for r in job['rows']:
                if r.get('status') in ('pending', 'running'):
                    r['status'] = 'skip'
                    r['error'] = '任务执行异常终止，未产出结果'
            _bump_done_and_save(job)
        _finalize(job)
    except Exception:
        job['state'] = 'error'
        job['error'] = traceback.format_exc(limit=6)
        _save(job)
