"""四段式 demo runner：A 数据 → B 模型加载 → C 批处理/断点 → D 指数拟合。

运行（在 ``prototype/`` 目录下）::

    python3 -m valnet.runner_stages

会写入 ``prototype/runtime/graph/demo-3/``，第二次运行会命中已完成 chunk，
``executed_chunks=0``，用于演示断点恢复。
"""

from __future__ import annotations

from pathlib import Path

from .stages import demo_batch, demo_graph, stage_a, stage_b, stage_c, stage_d


def main() -> int:
    base = demo_batch()
    a = stage_a(base.features, base.masks, base.ids, base.meta)
    print("[A] 数据")
    print(f"    rows={a.manifest['rows']} as_of={a.manifest['as_of']} digest={a.manifest['digest']}")
    print(f"    features={len(a.batch.features)} masks={len(a.batch.masks)}")

    b = stage_b()
    print("[B] 模型加载")
    print(f"    loaded={', '.join(b.loaded)}")
    print(f"    failed={b.failed or '—'}")

    root = Path("runtime/graph")
    c = stage_c(demo_graph(), a.batch, root, "demo-3", chunk_size=1)
    print("[C] 批处理/断点")
    print(f"    chunks={c.chunks_done}/{c.chunks_total} executed_this_run={c.executed_chunks}")
    for security, value, interval, conf in zip(c.ids, c.values, c.intervals, c.confidence):
        interval_text = "—" if interval is None else f"[{interval[0]:.2f}, {interval[1]:.2f}]"
        value_text = "—" if value is None else f"{value:.2f}"
        conf_text = "—" if conf is None else f"{conf:.2f}"
        print(f"    {security}: value={value_text} interval={interval_text} conf={conf_text}")
    print(f"    trace={c.trace_status}")

    d = stage_d(c, a.batch)
    interval_text = "—" if d.interval is None else f"[{d.interval[0]:.2f}, {d.interval[1]:.2f}]"
    print("[D] 指数拟合")
    print(f"    covered={d.covered}/{d.total} value={d.value:.2f} interval={interval_text}")
    print(f"    weights={ {k: round(v, 4) for k, v in d.weights.items()} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
