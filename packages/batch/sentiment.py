# -*- coding: utf-8 -*-
"""东财免费公开舆情：新闻搜索 + 股吧帖 → 词频 + 规则打分 → 技能情绪字段。

输出契约（对接 llm-ipo-valuation 引擎）：
- company_news_sentiment: positive / neutral / negative（引擎按其 ±3% 档映射）
- sentiment_adjustment_pct: 显式百分比（引擎优先消费，恒在 ±0.10 内）
- sector_heat 恒为 neutral（行业热度不属本管道范围）

数据源（免费公开、无鉴权）：search-api-web.eastmoney.com/search/jsonp
- type=cmsArticleWebOld，keyword=股票名称 → 新闻（标题+正文）
- type=gubaArticle，keyword=股票代码 → 股吧帖

打分：情绪词典词频加权 + 程度副词（强×2 / 弱×0.5）+ 否定词翻转 + 标题权重×2，
重叠片段去重后归一化到 [-1, 1] → 阈值定 label → 线性映射 adjustment_pct（±1.5~5.0）。
任何失败回退 neutral/0.0，绝不抛异常——舆情是辅助信号，不阻断批跑。
结果缓存 runtime/cache/sentiment_<code>.json，TTL 6 小时，按线程临时名落盘。
"""
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from config import CACHE

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
SEARCH_API = 'https://search-api-web.eastmoney.com/search/jsonp'
TTL_SECONDS = 6 * 3600
MAX_DAYS = 30
DEFAULT_ROUNDS = 10

NEGATIONS = ('不', '无', '未', '没', '非', '莫', '勿', '别')
DEGREE_MULT = (
    (('大幅', '显著', '明显', '严重', '急剧', '强烈', '大举', '持续', '连续',
      '快速', '加速', '罕见', '全面', '深度'), 2.0),
    (('小幅', '略微', '轻微', '略有', '有所', '略', '稍', '微', '缓慢'), 0.5),
)

# 情绪词典：正面/负面，值为权重（0.5~2.0）
POS_WORDS = {
    '涨停': 2.0, '大涨': 2.0, '暴涨': 2.0, '新高': 2.0, '超预期': 2.0,
    '涨停潮': 2.0,
    '扭亏': 1.5, '突破': 1.5, '强劲': 1.5, '回购': 1.5, '增持': 1.5,
    '中标': 1.5, '利好': 1.5, '领涨': 1.5, '血赚': 1.5, '大肉': 1.5,
    '起飞': 1.5, '主力买入': 1.5, '主力加仓': 1.5,
    '增长': 1.0, '上涨': 1.0, '盈利': 1.0, '买入': 1.0, '看好': 1.0,
    '分红': 1.0, '派息': 1.0, '扩产': 1.0, '签署': 1.0, '获批': 1.0,
    '反弹': 1.0, '走强': 1.0, '亮眼': 1.0, '复苏': 1.0, '回暖': 1.0,
    '优异': 1.0, '景气': 1.0, '反转': 1.0, '加仓': 1.0, '低吸': 1.0,
    '抄底': 1.0, '护盘': 1.0, '稳了': 1.0, '订单': 1.0, '净流入': 1.0,
    '签单': 1.0, '增资': 1.0, '提升': 0.8, '改善': 0.8, '创新': 0.8,
    '稳步': 0.8, '合作': 0.8, '授予': 0.8,
}
NEG_WORDS = {
    '跌停': 2.0, '暴跌': 2.0, '重挫': 2.0, '崩盘': 2.0, '爆雷': 2.0,
    '血亏': 2.0, '退市': 2.0, '造假': 2.0, '破产': 2.0, '熔断': 2.0,
    '低于预期': 2.0, '不及预期': 2.0, '跌停潮': 2.0,
    '大跌': 1.5, '亏损': 1.5, '减持': 1.5, '违规': 1.5, '处罚': 1.5,
    '罚款': 1.5, '立案': 1.5, '危机': 1.5, '恶化': 1.5, '违约': 1.5,
    '利空': 1.5, '跳水': 1.5, '出货': 1.5, '砸盘': 1.5, '下挫': 1.5,
    '停产': 1.5, '召回': 1.5, '事故': 1.5, '破发': 1.5, '告急': 1.5,
    '凉凉': 1.5, '割肉': 1.5, '主力出逃': 1.5, '主力减持': 1.5,
    '下跌': 1.0, '下滑': 1.0, '调查': 1.0, '诉讼': 1.0, '警示': 1.0,
    '裁员': 1.0, '下调': 1.0, '疲软': 1.0, '承压': 1.0, '萎缩': 1.0,
    '缩水': 1.0, '质疑': 1.0, '债务': 1.0, '失速': 1.0, '惨淡': 1.0,
    '拖累': 1.0, '乏力': 1.0, '走低': 1.0, '阴跌': 1.0, '套牢': 1.0,
    '破位': 1.0, '清仓': 1.0, '减仓': 1.0, '净流出': 1.0, '问询': 1.0,
    '冻结': 1.5, '查封': 1.5, '高抛': 0.8,
}

LEXICON = {}
LEXICON.update(POS_WORDS)
for word, w in NEG_WORDS.items():
    LEXICON[word] = -w


def _search_jsonp(params, timeout=15.0):
    url = SEARCH_API + '?cb=cb&param=' + urllib.parse.quote(
        json.dumps(params, ensure_ascii=False))
    req = urllib.request.Request(url, headers={
        'User-Agent': UA, 'Referer': 'https://so.eastmoney.com/'})
    last = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', 'replace')
            break
        except Exception as exc:
            last = exc
            time.sleep(1.0)
    else:
        raise RuntimeError('搜索接口请求失败: %s' % last)
    m = re.search(r'cb\((.*)\)\s*;?\s*$', raw, re.S)
    if not m:
        raise RuntimeError('搜索接口返回异常: %s' % raw[:120])
    return json.loads(m.group(1))


def _search(keyword, type_key, rounds):
    params = {
        'uid': '',
        'keyword': keyword,
        'type': [type_key],
        'client': 'web',
        'clientType': 'web',
        'clientVersion': 'curr',
        'param': {
            type_key: {
                'searchScope': 'default',
                'sort': 'default',
                'pageIndex': 1,
                'pageSize': max(int(rounds), 5),
                'preTag': '<em>',
                'postTag': '</em>',
            },
        },
    }
    items = ((_search_jsonp(params) or {}).get('result') or {}).get(type_key) or []
    cutoff = (datetime.now() - timedelta(days=MAX_DAYS)).strftime('%Y-%m-%d')
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        date = str(it.get('date') or '')[:10]
        if date and date < cutoff:
            continue
        title = re.sub(r'</?em>', '', str(it.get('title') or ''))
        content = re.sub(r'</?em>', '', str(it.get('content') or ''))
        if not title and not content:
            continue
        out.append({'title': title, 'content': content, 'date': date})
    return out


def _spans(text):
    spans = []
    for word, w in LEXICON.items():
        for m in re.finditer(re.escape(word), text):
            start = m.start()
            value = float(w)
            for deg_words, mult in DEGREE_MULT:
                if any(text[max(0, start - len(d)):start] == d for d in deg_words):
                    value *= mult
                    break
            pre = text[max(0, start - 4):start]
            if any(n in pre for n in NEGATIONS):
                value = -value
            spans.append((start, m.end(), value))
    spans.sort(key=lambda s: (s[0], -s[1]))
    kept = []
    last_end = -1
    for s in spans:
        if s[0] >= last_end:
            kept.append(s)
            last_end = s[1]
    return kept


def _score_texts(texts):
    pos = neg = 0.0
    pos_hits = {}
    neg_hits = {}
    for text, mult in texts:
        for _, _, v in _spans(text):
            v *= mult
            if v > 0:
                pos += v
            else:
                neg += -v
        for word in POS_WORDS:
            c = text.count(word)
            if c:
                pos_hits[word] = pos_hits.get(word, 0) + c
        for word in NEG_WORDS:
            c = text.count(word)
            if c:
                neg_hits[word] = neg_hits.get(word, 0) + c
    total = pos + neg
    if total < 0.5:
        return 0.0, pos, neg, pos_hits, neg_hits
    ratio = (pos - neg) / total
    coverage = min(1.0, total / 5.0)
    return ratio * coverage, pos, neg, pos_hits, neg_hits


def _label_pct(score):
    if score >= 0.18:
        return 'positive', round(min(5.0, 1.5 + 3.5 * score), 1)
    if score <= -0.18:
        return 'negative', -round(min(5.0, 1.5 + 3.5 * abs(score)), 1)
    return 'neutral', 0.0


def _top(hits, n=3):
    return [w for w, _ in sorted(hits.items(), key=lambda kv: -kv[1])[:n]]


def _compute(code, name, rounds):
    news = _search(name, 'cmsArticleWebOld', rounds)
    if len(news) < 3:
        seen = {(x['title'], x['date']) for x in news}
        for it in _search(code, 'cmsArticleWebOld', rounds):
            if (it['title'], it['date']) not in seen:
                news.append(it)
    guba = _search(code, 'gubaArticle', rounds)
    texts = []
    for it in news:
        texts.append((it['title'], 2.0))
        texts.append((it['content'], 1.0))
    for it in guba:
        texts.append((it['title'], 2.0))
        texts.append((it['content'], 1.0))
    score, pos_w, neg_w, pos_hits, neg_hits = _score_texts(texts)
    label, pct = _label_pct(score)
    parts = ['新闻 %d 条 / 股吧 %d 条（东财免费公开接口，近 30 天）' % (len(news), len(guba)),
             '词频+规则打分：正面词 %d 个、负面词 %d 个，情绪分 %+.2f' % (int(pos_w), int(neg_w), score)]
    top_pos, top_neg = _top(pos_hits), _top(neg_hits)
    if top_pos:
        parts.append('正面关键词：%s' % '、'.join(top_pos))
    if top_neg:
        parts.append('负面关键词：%s' % '、'.join(top_neg))
    return {
        'label': label,
        'adjustment_pct': pct,
        'score': round(score, 3),
        'evidence': '%s。→ %s（调整 %+.1f%%）' % (
            '；'.join(parts),
            {'positive': '偏正面', 'neutral': '中性', 'negative': '偏负面'}[label], pct),
        'news_count': len(news),
        'guba_count': len(guba),
    }


def score_stock(code, name, rounds=DEFAULT_ROUNDS, force=False):
    # 批跑传入带交易所后缀的 secucode（如 600519.SH），统一剥成裸代码：
    # 缓存 key 与股吧搜索关键词都用裸代码，CLI 与批跑共享缓存。
    bare = str(code or '').split('.')[0] or code
    key = 'sentiment_%s' % bare
    path = CACHE / (key + '.json')
    if not force and path.exists():
        try:
            if time.time() - path.stat().st_mtime < TTL_SECONDS:
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    try:
        result = _compute(bare, name, int(rounds) if rounds else DEFAULT_ROUNDS)
    except Exception as exc:
        result = {
            'label': 'neutral', 'adjustment_pct': 0.0, 'score': 0.0,
            'evidence': '舆情管道异常（%s），回退默认口径 neutral/0.0' % str(exc)[:120],
            'news_count': 0, 'guba_count': 0,
        }
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
        print('usage: python3 sentiment.py <code> [name] [--rounds N] [--force]',
              file=sys.stderr)
        sys.exit(2)
    code = sys.argv[1]
    i = 2
    name = code
    rounds = DEFAULT_ROUNDS
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
