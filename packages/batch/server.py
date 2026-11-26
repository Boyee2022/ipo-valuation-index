# -*- coding: utf-8 -*-
"""估值跑批 HTTP 服务（内网 3089）。

路由：
  GET  /api/health                                  → 存活与数据源状态
  GET  /api/constituents?index=sh50                 → 真实成分券 + 权重 + 指数收盘
  GET  /api/agents                                  → 智能体配置（唯一配置源）+ 默认值 + 环境信息
  POST /api/agents {config}                         → 严格校验后保存，版本号自增，下一批生效
  POST /api/run  {index, parallel, stat_n, weights{dcf,comp,sent}, sentiment_rounds,
                  wacc_pct?, terminal_growth_pct?, shadow?} → {job_id}
  POST /api/shadow/adopt {job, code, action:adopted|rejected|clear} → 采纳标记与刷新后指标
  GET  /api/jobs                                   → 任务列表
  GET  /api/jobs/<id>                              → 任务状态（进度/逐券结果/拟合点位）
  GET  /api/jobs/<id>/reports/<file>               → 逐券 HTML 报告 / summary.html / shadow.html

CORS 放行（仅内网使用）；文件名白名单校验。无密钥、无鉴权——服务只读公开数据、只写本机任务目录。
"""
import json
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import agent_config
import dsources
import pipeline
import report_theme
import sentiment_llm
import shadow
from config import INDEX_NAMES, INDEX_TENCENT, INDEX_TYPES, JOBS, PORT, SKILL_DIR

SAFE = re.compile(r'^[\w.\-]+$')


def _opt_pct(body, key, lo, hi, label):
    """可选百分比覆盖参数：缺省/空串 → None；越界直接拒绝。"""
    v = body.get(key)
    if v is None or v == '':
        return None
    v = float(v)
    if not (lo <= v <= hi):
        raise ValueError('%s 超出允许范围 %g%%~%g%%' % (label, lo, hi))
    return round(v, 2)


def _lan_host():
    for iface in ('en0', 'en1'):
        try:
            out = subprocess.run(['ipconfig', 'getifaddr', iface], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
            if out:
                return out
        except Exception:
            continue
    return '0.0.0.0'


def _agents_payload(saved=False):
    cfg = agent_config.load()
    try:
        model_env = (sentiment_llm._env() or {}).get('DEEPSEEK_MODEL') or ''
    except Exception:
        model_env = ''
    return {
        'config': cfg,
        'defaults': agent_config.DEFAULTS,
        'labels': agent_config.AGENT_LABEL,
        'path': agent_config.display_path(),
        'exists': agent_config.path().exists(),
        'updated_at': agent_config.updated_at(),
        'model_env': model_env,
        'llm_ready': sentiment_llm.available(),
        'prompts': shadow.prompt_preview(cfg),
        'saved': saved,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = 'valuation-batch/1.0'

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, content_type, transform=None):
        p = Path(path)
        if not p.exists():
            self._json({'error': 'not found'}, 404)
            return
        body = p.read_bytes()
        if transform is not None:
            body = transform(body)
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == '/api/health':
                c = None
                err = None
                try:
                    c = dsources.components(INDEX_TYPES['sh50'])
                    rows_n = len(c.get('rows') or [])
                except Exception as ex:
                    rows_n = 0
                    err = str(ex)
                self._json({'ok': True, 'components_as_of': (c or {}).get('as_of'),
                            'components_rows': rows_n, 'error': err,
                            'shadow_ready': sentiment_llm.available()})
                return
            if path == '/api/constituents':
                idx = (qs.get('index') or ['sh50'])[0]
                if idx not in INDEX_TYPES:
                    self._json({'error': '未知指数: %s' % idx}, 400)
                    return
                c = dsources.components(INDEX_TYPES[idx])
                try:
                    ix = dsources.index_quote(INDEX_TENCENT[idx])
                    today = time.strftime('%Y-%m-%d')
                    close = ix.get('prev_close') if c['as_of'] < today else ix.get('price')
                except Exception:
                    close = None
                self._json({
                    'index': idx, 'index_name': INDEX_NAMES[idx], 'as_of': c['as_of'],
                    'index_close': close, 'weight_computed': bool(c.get('weight_computed')),
                    'rows': [{k: r.get(k) for k in
                              ('code', 'secucode', 'name', 'industry', 'weight', 'close', 'pe',
                               'eps', 'roe', 'total_shares', 'free_cap')} for r in c['rows']],
                })
                return
            if path == '/api/agents':
                self._json(_agents_payload())
                return
            if path == '/api/jobs':
                self._json({'jobs': pipeline.list_jobs()})
                return
            m = re.match(r'^/api/jobs/([\w\-]+)$', path)
            if m:
                job = pipeline.get(m.group(1))
                if job is None:
                    self._json({'error': '任务不存在'}, 404)
                else:
                    self._json(job)
                return
            m = re.match(r'^/api/jobs/([\w\-]+)/reports/([\w.\-]+)$', path)
            if m and SAFE.match(m.group(1)) and SAFE.match(m.group(2)):
                f = JOBS / m.group(1) / m.group(2)
                if f.is_file() and str(f.resolve()).startswith(str(JOBS.resolve())):
                    ct = 'text/html; charset=utf-8' if f.suffix == '.html' else 'application/json; charset=utf-8'
                    transform = report_theme.inject_bytes if f.suffix == '.html' else None
                    self._file(f, ct, transform)
                else:
                    self._json({'error': 'not found'}, 404)
                return
            self._json({'error': 'not found'}, 404)
        except Exception as e:
            self._json({'error': '服务内部错误: %s' % str(e)[:300]}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == '/api/agents':
                n = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(n).decode('utf-8') or '{}')
                raw = body.get('config') if isinstance(body.get('config'), dict) else body
                if not isinstance(raw, dict) or not raw:
                    self._json({'error': '缺少配置内容'}, 400)
                    return
                try:
                    agent_config.save(raw)
                except ValueError as ex:
                    self._json({'error': str(ex)}, 400)
                    return
                self._json(_agents_payload(saved=True))
                return
            if parsed.path == '/api/run':
                n = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(n).decode('utf-8') or '{}')
                idx = body.get('index', 'sh50')
                if idx not in INDEX_TYPES:
                    self._json({'error': '未知指数: %s' % idx}, 400)
                    return
                parallel = int(body.get('parallel') or 3)
                if parallel not in (3, 10):
                    parallel = 3
                weights = body.get('weights') or {}
                sentiment_mode = 'llm' if body.get('sentiment_mode') == 'llm' else 'rule'
                agent_mode = body.get('agent_mode')
                if agent_mode not in ('off', 'shadow', 'apply'):
                    agent_mode = 'shadow' if body.get('shadow') else 'off'
                if (sentiment_mode == 'llm' or agent_mode != 'off') and not sentiment_llm.available():
                    self._json({'error': 'LLM 未配置：请在 ~/.dsh-valuation/sentiment-llm.env 写入 DEEPSEEK_API_KEY（仓库外）'}, 400)
                    return
                wacc_pct = _opt_pct(body, 'wacc_pct', 1, 20, 'WACC 覆盖')
                tg_pct = _opt_pct(body, 'terminal_growth_pct', 0, 5, '永续增速覆盖')
                if wacc_pct is not None and tg_pct is not None and wacc_pct <= tg_pct:
                    self._json({'error': 'WACC 覆盖必须高于永续增速覆盖'}, 400)
                    return
                params = {
                    'index': idx,
                    'parallel': parallel,
                    'stat_n': int(body.get('stat_n') or 1000),
                    'weights': {
                        'dcf': float(weights.get('dcf', 0.3)),
                        'comp': float(weights.get('comp', 0.5)),
                        'sent': float(weights.get('sent', 0.2)),
                    },
                    'sentiment_rounds': int(body.get('sentiment_rounds') or 10),
                    'sentiment_mode': sentiment_mode,
                    'wacc_pct': wacc_pct,
                    'terminal_growth_pct': tg_pct,
                    'agent_mode': agent_mode,
                    'shadow_mode': agent_mode != 'off',
                }
                job_id = pipeline.start(params)
                self._json({'job_id': job_id})
                return
            if parsed.path == '/api/shadow/adopt':
                n = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(n).decode('utf-8') or '{}')
                job_id = str(body.get('job') or '')
                code = str(body.get('code') or '')
                action = str(body.get('action') or '')
                if not job_id or not code or not SAFE.match(job_id):
                    self._json({'error': '缺少有效的任务或证券代码'}, 400)
                    return
                if action not in ('adopted', 'rejected', 'clear'):
                    self._json({'error': '未知采纳操作: %s' % action}, 400)
                    return
                res = pipeline.set_shadow_adoption(job_id, code, action, body.get('by') or '')
                if res is None:
                    self._json({'error': '任务或成分券不存在'}, 404)
                    return
                self._json(res)
                return
            self._json({'error': 'not found'}, 404)
        except Exception as e:
            self._json({'error': '提交失败: %s' % str(e)[:300]}, 400)

    def log_message(self, fmt, *args):
        pass


def main():
    host = _lan_host()
    ThreadingHTTPServer.allow_reuse_address = True
    srv = ThreadingHTTPServer((host, PORT), Handler)
    print('估值批跑服务启动 http://%s:%d  （技能目录 %s）' % (host, PORT, str(SKILL_DIR)))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == '__main__':
    main()
