# -*- coding: utf-8 -*-
"""跑批执行：并行逐券「输入组装→引擎→统计校验→HTML 报告→八项机检」，按权重合成拟合点位。

- 失败券自动跳过并留痕（对应需求「单券估不出 → 跳过」，不阻断整批）；
- agent_mode=shadow：逐券追加「三专家 + 主审」评审，只留痕，不改引擎参数；
- agent_mode=apply：评审通过项写回输入后重跑引擎（基线输入/输出保留 *.baseline.json，失败回滚）；
- 智能体配置在每批开始时读一次并写入 state.json，运行中的任务不受后续保存影响；
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

import agent_config
import dsources
import input_builder
import report_theme
import shadow
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


def _engine(inp_f, out_f):
    r = _run([PY, str(ENGINE), str(inp_f), '-o', str(out_f)], 600)
    if r.returncode != 0:
        raise RuntimeError('估值引擎失败: %s' % _tail(r.stderr or r.stdout))
    return json.loads(Path(out_f).read_text(encoding='utf-8'))


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
    """创建任务并后台执行。params: {index, parallel, stat_n, weights{dcf,comp,sent}, sentiment_rounds,
    wacc_pct?, terminal_growth_pct?, agent_mode?, shadow_mode?}"""
    agent_mode = params.get('agent_mode')
    if agent_mode not in ('off', 'shadow', 'apply'):
        agent_mode = 'shadow' if params.get('shadow_mode') else 'off'
    job_id = 'job_%s_%s' % (time.strftime('%Y%m%d_%H%M%S'), uuid.uuid4().hex[:6])
    job = {
        'id': job_id,
        'index': params.get('index', 'sh50'),
        'parallel': int(params.get('parallel') or 3),
        'stat_n': int(params.get('stat_n') or 1000),
        'weights': params.get('weights') or {'dcf': 0.3, 'comp': 0.5, 'sent': 0.2},
        'sentiment_rounds': int(params.get('sentiment_rounds') or 10),
        'sentiment_mode': 'llm' if params.get('sentiment_mode') == 'llm' else 'rule',
        'wacc_pct': params.get('wacc_pct'),
        'terminal_growth_pct': params.get('terminal_growth_pct'),
        'agent_mode': agent_mode,
        'shadow_mode': agent_mode != 'off',
        'agent_config': agent_config.load() if agent_mode != 'off' else None,
        'shadow_metrics': None,
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
                'sentiment_mode': j.get('sentiment_mode') or 'rule',
                'agent_mode': j.get('agent_mode') or ('shadow' if j.get('shadow_mode') else 'off'),
                'shadow_mode': bool(j.get('shadow_mode')),
                'agent_config_version': (j.get('agent_config') or {}).get('version'),
            })
        except Exception:
            continue
    return out


def _persist_review(job, row, rec):
    """评审记录落盘：完整记录在 <code>.shadow.json，摘要已随 state.json 保存。"""
    stem = row['secucode'].replace('.', '_')
    try:
        shadow.save_record(_job_dir(job['id']) / ('%s.shadow.json' % stem), rec)
    except Exception:
        pass


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

        eng = _engine(inp_f, out_f)
        syn = eng.get('synthesis') or {}
        mid = syn.get('weighted_mid')
        n_comp = len(inp.get('comparables') or [])
        if mid is None or mid <= 0:
            raise ValueError('无可比且 DCF 未形成有效估值' if n_comp == 0 else '估值中枢无效（≤0）')

        mode = (job or {}).get('agent_mode') or ('shadow' if (job or {}).get('shadow_mode') else 'off')
        rec = None
        if mode in ('shadow', 'apply'):
            cfg = (job or {}).get('agent_config')
            try:
                rec = shadow.review(inp, eng, (job or {}).get('weights') or {}, mode=mode, cfg=cfg)
            except Exception as exc:
                rec = shadow.error_record(inp, eng, (job or {}).get('weights') or {}, exc,
                                          mode=mode, cfg=cfg)
            if mode == 'apply' and rec.get('decision') != 'error':
                mid0 = mid
                new_inp, changes, skipped = shadow.apply_to_input(inp, eng, rec)
                apply_info = {'mode': 'apply', 'changed': False, 'changes': changes,
                              'skipped': skipped, 'baseline_mid': round(mid0, 2),
                              'final_mid': round(mid0, 2), 'error': None}
                if changes:
                    base_in = jdir / ('%s.input.baseline.json' % stem)
                    base_out = jdir / ('%s.out.baseline.json' % stem)
                    try:
                        shutil.copy2(inp_f, base_in)
                        shutil.copy2(out_f, base_out)
                        inp_f.write_text(json.dumps(new_inp, ensure_ascii=False, indent=2), encoding='utf-8')
                        eng2 = _engine(inp_f, out_f)
                        mid2 = (eng2.get('synthesis') or {}).get('weighted_mid')
                        if mid2 is None or mid2 <= 0:
                            raise ValueError('回写后估值中枢无效（≤0）')
                        inp, eng, syn, mid = new_inp, eng2, eng2.get('synthesis') or {}, mid2
                        apply_info.update({'changed': True, 'final_mid': round(mid2, 2)})
                    except Exception as exc:
                        try:
                            shutil.copy2(base_in, inp_f)
                            shutil.copy2(base_out, out_f)
                        except Exception:
                            pass
                        apply_info['error'] = '回写重跑失败，已回滚基线: %s' % str(exc)[:180]
                rec['apply'] = apply_info

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

        try:
            report_theme.theme_file(rep_f)
        except Exception:
            pass

        shares = (inp.get('financials') or {}).get('total_shares_after_issue')
        per_share = round(mid / shares, 2) if mid is not None and shares else None
        conf = (eng.get('confidence') or {}).get('level')
        conf_note = None
        if n_comp == 0:
            # 引擎只给区间加宽与警示；产品层面按「可比法剔除」再下调一档置信度。
            conf = {'高': '中', '中': '低'}.get(conf, conf)
            conf_note = '无可比，已剔除可比法'
        elif n_comp < 3:
            conf_note = '可比仅 %d 家' % n_comp
        with _state_lock:
            row.update({
                'status': 'ok',
                'weighted_mid': mid,
                'per_share': per_share,
                'interval': syn.get('interval'),
                'four_part': {k: (v.get('value') if isinstance(v, dict) else v)
                              for k, v in (syn.get('four_part') or {}).items()
                              if k in ('part1_dcf', 'part2_comparable_quality', 'part3_market_sentiment')},
                'confidence_level': conf,
                'confidence_note': conf_note,
                'n_comp': n_comp,
                'stage_label': (eng.get('lifecycle') or {}).get('stage_label'),
                'basis': (eng.get('net_profit_basis_used') or {}).get('basis'),
                'warnings': (eng.get('warnings') or [])[:6],
                'check_ok': check_ok,
                'report': rep_f.name,
            })
            if rec is not None:
                row['shadow'] = shadow.row_summary(rec)
                if rec.get('apply'):
                    row['apply'] = rec['apply']
            _bump_done_and_save(job)
        if rec is not None and job is not None:
            _persist_review(job, row, rec)
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
            if r.get('confidence_note'):
                conf += '<br><small style="color:#b45309">%s</small>' % esc(str(r['confidence_note']))
            link = '<a href="./%s">报告</a>' % esc(r.get('report', ''))
        else:
            tag = '<span style="color:#b45309">跳过</span>'
            val = '—'
            conf = '—'
            reason = str(r.get('error') or '')[:80].removesuffix('，跳过')
            link = esc(reason)
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
    ov = []
    if job.get('wacc_pct') is not None:
        ov.append('WACC %.2f%%' % job['wacc_pct'])
    if job.get('terminal_growth_pct') is not None:
        ov.append('永续增速 %.2f%%' % job['terminal_growth_pct'])
    cost_note = ('本批参数覆盖：%s（全批统一，引擎显式采用）' % '、'.join(ov)) if ov else (
        'WACC/永续增速未显式给定，由引擎行业参数底座自动解析')
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
table{width:100%%;border-collapse:collapse;background:#fff;font-size:13px;table-layout:fixed}
th:nth-child(1){width:4.5%%}th:nth-child(2){width:10%%}th:nth-child(3){width:11%%}
th:nth-child(4){width:11%%}th:nth-child(5){width:8.5%%}th:nth-child(6){width:9.5%%}
th:nth-child(7){width:10%%}th:nth-child(8){width:8%%}th:nth-child(9){width:6.5%%}
th:nth-child(10){width:10%%}th:nth-child(11){width:11%%}
th,td{border-bottom:1px solid #eef0f3;padding:7px 9px;text-align:right}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3),
th:nth-child(4),td:nth-child(4){text-align:left}
thead th{background:#0e7490;color:#fff;font-weight:600;text-align:right}
thead th:first-child,thead th:nth-child(2),thead th:nth-child(3),thead th:nth-child(4){text-align:left}
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
口径：成分权重为前一日收盘权重（东财指数成分表）；估值中枢=引擎综合中枢÷总股本；%(cost_note)s；舆情=东财免费公开数据（近30天新闻搜索+股吧帖）词频+规则打分，情绪字段显式传入引擎。<br>
本报告由估值跑批管线自动生成，仅作探索性研究参考，不构成投资建议。
</div></div></body></html>""" % {
        'index': esc(INDEX_NAMES.get(job.get('index'), job.get('index'))),
        'jobid': esc(job['id']), 'as_of': esc(str(job.get('components_as_of') or '—')),
        'ts': _now(), 'fitted': ('%.2f' % fitted) if fitted is not None else '—',
        'close': ('%.2f' % s.get('index_close')) if s.get('index_close') is not None else '—',
        'total': job.get('total', 0), 'ok': s.get('ok', 0), 'skip': s.get('skip', 0),
        'rows': ''.join(body_rows), 'cost_note': cost_note,
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
    shadow_metrics = None
    shadow_warning = None
    if job.get('shadow_mode'):
        try:
            shadow_metrics = shadow.metrics(job, _prev_shadow_job(job))
        except Exception as e:
            shadow_warning = '影子指标计算失败: %s' % str(e)[:200]
    with _state_lock:
        job['summary'] = {
            'fitted_point': fitted,
            'index_close': idx,
            'ok': len(ok),
            'skip': sum(1 for r in job['rows'] if r.get('status') == 'skip'),
            'total': job['total'],
        }
        if job.get('shadow_mode'):
            job['shadow_metrics'] = shadow_metrics
            if shadow_warning:
                job['shadow_warning'] = shadow_warning
        job['state'] = 'done'
        job['finished'] = _now()
        _save(job)
    try:
        summary_f = _job_dir(job['id']) / 'summary.html'
        summary_f.write_text(report_theme.inject(_summary_html(job)), encoding='utf-8')
    except Exception as e:
        with _state_lock:
            job['summary_warning'] = 'summary.html 生成失败: %s' % str(e)[:200]
            _save(job)
    if job.get('shadow_mode'):
        try:
            shadow_f = _job_dir(job['id']) / 'shadow.html'
            shadow_f.write_text(report_theme.inject(shadow.report_html(job)), encoding='utf-8')
        except Exception as e:
            with _state_lock:
                job['shadow_warning'] = 'shadow.html 生成失败: %s' % str(e)[:200]
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


def _prev_shadow_job(job):
    """同指数、更早的已完成影子任务，用于周环比参数稳定性。"""
    for meta in list_jobs():
        if meta.get('id') == job.get('id') or meta.get('index') != job.get('index'):
            continue
        if not meta.get('shadow_mode') or meta.get('state') != 'done':
            continue
        if meta.get('created') and job.get('created') and meta['created'] >= job['created']:
            continue
        prev = get(meta['id'])
        if prev and prev.get('rows'):
            return prev
    return None


def set_shadow_adoption(job_id, code, action, by='operator'):
    """人工采纳标记：adopted / rejected / clear；返回该券摘要与刷新后的任务级指标。"""
    if action not in ('adopted', 'rejected', 'clear'):
        raise ValueError('未知采纳操作: %s' % action)
    with _state_lock:
        job = get(job_id)
        if job is None:
            return None
        if not job.get('shadow_mode'):
            raise ValueError('该任务未开启影子模式')
        if job.get('state') != 'done':
            raise ValueError('任务尚未完成，暂不能标记采纳')
        row = next((r for r in job.get('rows') or [] if r.get('secucode') == code), None)
        if row is None:
            return None
        summary = row.get('shadow') or {}
        if summary.get('decision') in (None, 'error'):
            raise ValueError('该券没有有效影子评审记录')
        adoption = None if action == 'clear' else {
            'action': action, 'by': str(by or 'operator')[:40], 'at': _now(),
        }
        rec_path = _job_dir(job_id) / (str(code).replace('.', '_') + '.shadow.json')
        if rec_path.exists():
            try:
                rec = json.loads(rec_path.read_text(encoding='utf-8'))
                rec['adoption'] = adoption
                shadow.save_record(rec_path, rec)
            except Exception:
                pass
        row['shadow'] = dict(summary, adoption=None if adoption is None else adoption['action'])
        try:
            job['shadow_metrics'] = shadow.metrics(job, _prev_shadow_job(job))
        except Exception:
            pass
        _save(job)
        return {'shadow': row['shadow'], 'shadow_metrics': job.get('shadow_metrics')}


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
