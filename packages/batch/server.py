# -*- coding: utf-8 -*-
"""估值跑批 HTTP 服务（内网 3089）。

路由：
  GET  /api/health                                  → 存活与数据源状态
  GET  /api/constituents?index=sh50                 → 真实成分券 + 权重 + 指数收盘
  POST /api/run  {index, parallel, stat_n, weights{dcf,comp,sent}, sentiment_rounds} → {job_id}
  GET  /api/jobs                                   → 任务列表
  GET  /api/jobs/<id>                              → 任务状态（进度/逐券结果/拟合点位）
  GET  /api/jobs/<id>/reports/<file>               → 逐券 HTML 报告 / summary.html

CORS 放行（仅内网使用）；文件名白名单校验。无密钥、无鉴权——服务只读公开数据、只写本机任务目录。
"""
import json
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import dsources
import pipeline
from config import INDEX_NAMES, INDEX_TENCENT, INDEX_TYPES, JOBS, PORT, SKILL_DIR

SAFE = re.compile(r'^[\w.\-]+$')


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

    def _file(self, path, content_type):
        p = Path(path)
        if not p.exists():
            self._json({'error': 'not found'}, 404)
            return
        body = p.read_bytes()
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
                            'components_rows': rows_n, 'error': err})
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
                    'index_close': close,
                    'rows': [{k: r.get(k) for k in
                              ('code', 'secucode', 'name', 'industry', 'weight', 'close', 'pe',
                               'eps', 'roe', 'total_shares', 'free_cap')} for r in c['rows']],
                })
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
                    self._file(f, ct)
                else:
                    self._json({'error': 'not found'}, 404)
                return
            self._json({'error': 'not found'}, 404)
        except Exception as e:
            self._json({'error': '服务内部错误: %s' % str(e)[:300]}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
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
                }
                job_id = pipeline.start(params)
                self._json({'job_id': job_id})
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
