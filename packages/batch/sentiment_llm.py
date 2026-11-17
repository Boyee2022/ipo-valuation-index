# -*- coding: utf-8 -*-
"""LLM 语义舆情：同一新闻/股吧语料 → DeepSeek 语义打分 → 技能情绪字段。

与 sentiment.py（词频+规则）共用抓取与输出契约，便于同口径对比：
- 输入：东财新闻搜索 + 股吧帖（近 30 天），与规则口径同一接口、同一调用方式
- 打分：DeepSeek chat API 语义分析（事件性质/影响方向/证据充分度），
  输出 label / score / adjustment_pct（中性 0；偏正/负取 ±1.5~±5.0，与规则口径同区间）
- 密钥：只从仓库外读取——环境变量 DEEPSEEK_API_KEY，或
  ~/.dsh-valuation/sentiment-llm.env 中 DEEPSEEK_API_KEY=...（不落日志、不入 git）
- 可选：DEEPSEEK_BASE_URL（默认 https://api.deepseek.com）、DEEPSEEK_MODEL（默认 deepseek-chat）
- 失败回退规则打分（evidence 注明回退原因），绝不阻断批跑；结果缓存 6 小时
"""
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

import sentiment
from config import CACHE

ENV_FILE = Path(os.environ.get(
    'VALUATION_LLM_ENV',
    str(Path.home() / '.dsh-valuation' / 'sentiment-llm.env'),
))
TTL_SECONDS = 6 * 3600
DEFAULT_BASE = 'https://api.deepseek.com'
DEFAULT_MODEL = 'deepseek-chat'


def _env():
    vals = {}
    try:
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            vals[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    for k in ('DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL'):
        if os.environ.get(k):
            vals[k] = os.environ[k]
    return vals


def available():
    return bool(_env().get('DEEPSEEK_API_KEY'))


SYSTEM_PROMPT = (
    '你是 A 股舆情语义分析器。给定某上市公司近 30 天的新闻与股吧帖子（标题+摘要），'
    '判断这些信息对该公司的净情绪方向与强度。要求：\n'
    '1) 关注公司基本面与事件（订单、业绩、回购增持、监管处罚、诉讼、事故、减持、政策等），'
    '忽略纯股价涨跌讨论与情绪化噪音；\n'
    '2) 区分「事实性事件」与「观点/传闻」，传闻权重减半；\n'
    '3) 输出严格 JSON：{"label":"positive|neutral|negative","score":-1到1的小数,'
    '"adjustment_pct":数字,"evidence":"不超过80字的中文依据"}\n'
    '4) adjustment_pct 为舆情修正幅度：偏正面取 +1.5~+5.0，偏负面取 -1.5~-5.0，'
    '中性取 0；强度与证据充分度成正比；\n'
    '5) 只输出 JSON，不要任何其他文字。'
)


def _chat(messages, env, timeout=90.0):
    base = (env.get('DEEPSEEK_BASE_URL') or DEFAULT_BASE).rstrip('/')
    model = env.get('DEEPSEEK_MODEL') or DEFAULT_MODEL
    body = {
        'model': model,
        'messages': messages,
        'temperature': 0.1,
        'max_tokens': 400,
        'response_format': {'type': 'json_object'},
        'stream': False,
    }
    req = urllib.request.Request(
        base + '/chat/completions',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + env['DEEPSEEK_API_KEY'],
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    content = ((data.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
    return content, model


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _parse(content):
    text = content.strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.startswith('json'):
            text = text[4:]
    data = json.loads(text)
    pct = _clamp(float(data.get('adjustment_pct') or 0.0), -5.0, 5.0)
    # 方向以调整幅度为准（模型 label 与幅度偶有冲突时）
    if abs(pct) < 1.5:
        label, pct = 'neutral', 0.0
    else:
        label = 'positive' if pct > 0 else 'negative'
    score = _clamp(float(data.get('score') or (pct / 5.0)), -1.0, 1.0)
    evidence = str(data.get('evidence') or '').strip().replace('\n', ' ')[:160]
    return label, round(pct, 1), round(score, 3), evidence


def _prompt(name, code, news, guba):
    lines = ['公司：%s（%s）' % (name, code)]
    lines.append('一、新闻（%d 条，近 30 天）：' % len(news))
    for i, it in enumerate(news[:12], 1):
        lines.append('%d. [%s] %s %s' % (i, it['date'], it['title'], it['content'][:90]))
    lines.append('二、股吧帖（%d 条）：' % len(guba))
    for i, it in enumerate(guba[:10], 1):
        lines.append('%d. %s %s' % (i, it['title'], it['content'][:60]))
    return '\n'.join(lines)


def _score(bare, name, rounds, env):
    news = sentiment._search(name, 'cmsArticleWebOld', rounds)
    if len(news) < 3:
        seen = {(x['title'], x['date']) for x in news}
        for it in sentiment._search(bare, 'cmsArticleWebOld', rounds):
            if (it['title'], it['date']) not in seen:
                news.append(it)
    guba = sentiment._search(bare, 'gubaArticle', rounds)
    if not news and not guba:
        return {
            'label': 'neutral', 'adjustment_pct': 0.0, 'score': 0.0,
            'evidence': 'LLM 语义分析：近 30 天无可用新闻/股吧样本 → 中性（调整 0.0%）',
            'news_count': 0, 'guba_count': 0, 'engine': 'llm',
        }
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': _prompt(name, bare, news, guba)},
    ]
    last = None
    for _ in range(2):
        try:
            content, model = _chat(messages, env)
            label, pct, score, why = _parse(content)
            label_name = {'positive': '偏正面', 'neutral': '中性', 'negative': '偏负面'}[label]
            return {
                'label': label, 'adjustment_pct': pct, 'score': score,
                'evidence': 'LLM 语义分析（%s；新闻 %d 条 / 股吧 %d 条，近 30 天）：%s → %s（调整 %+.1f%%）' % (
                    model, len(news), len(guba), why or '—', label_name, pct),
                'news_count': len(news), 'guba_count': len(guba), 'engine': 'llm',
            }
        except Exception as exc:
            last = exc
            time.sleep(1.5)
    raise RuntimeError('LLM 调用失败: %s' % last)


def score_stock(code, name, rounds=sentiment.DEFAULT_ROUNDS, force=False):
    bare = str(code or '').split('.')[0] or code
    key = 'sentiment_llm_%s' % bare
    path = CACHE / (key + '.json')
    if not force and path.exists():
        try:
            if time.time() - path.stat().st_mtime < TTL_SECONDS:
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    env = _env()
    if not env.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('LLM 舆情未配置：请在 %s 写入 DEEPSEEK_API_KEY（仓库外）' % ENV_FILE)
    try:
        result = _score(bare, name, int(rounds) if rounds else sentiment.DEFAULT_ROUNDS, env)
    except Exception as exc:
        base = sentiment.score_stock(code, name, rounds=rounds)
        result = dict(base)
        result['engine'] = 'rule-fallback'
        result['evidence'] = 'LLM 语义分析失败（%s），回退规则打分：%s' % (
            str(exc)[:120], base.get('evidence', ''))
    if result.get('engine') == 'llm':
        # 只缓存真正的 LLM 结果：密钥失灵/接口故障时的回退不落缓存，修复后可立即重跑
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp = CACHE / ('%s.tmp.%d' % (key, threading.get_ident()))
            tmp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
            tmp.replace(path)
        except Exception:
            pass
    return result


def main():
    if len(sys.argv) < 2:
        print('usage: python3 sentiment_llm.py <code> [name] [--rounds N] [--force]',
              file=sys.stderr)
        sys.exit(2)
    code = sys.argv[1]
    i = 2
    name = code
    rounds = sentiment.DEFAULT_ROUNDS
    force = False
    if i < len(sys.argv) and not sys.argv[i].startswith('--'):
        name = sys.argv[i]
        i += 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == '--rounds':
            rounds = int(sys.argv[i + 1])
            i += 2
        elif a == '--force':
            force = True
            i += 1
        else:
            i += 1
    print(json.dumps(score_stock(code, name, rounds=rounds, force=force),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
