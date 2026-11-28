#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
input_validator.py — 输入 JSON 静态结构校验器（v3.6 D1，纯标准库）
按 assets/input_schema.json 检查必填块/字段类型/数值范围/枚举/数组项规则。
与引擎 _validate_input（业务勾稽）分层：本脚本 = 静态结构检查，可在运行引擎前调用。

用法：
  python input_validator.py <input.json> [-o <issues.json>]
  返回 0 = 通过（无 error 级问题）；返回 1 = 存在 error 级问题。
"""
import argparse
import json
import os
import sys

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "input_schema.json")


def _get_path(d, path):
    """点路径取值（如 financials.revenue_latest_ttm）。"""
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _check_type(value, spec, issues, field):
    t = spec.get("type")
    ok = True
    if t == "str":
        ok = isinstance(value, str)
    elif t == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif t == "object":
        ok = isinstance(value, dict)
    elif t == "array":
        ok = isinstance(value, list)
    if not ok:
        issues.append({"level": "error", "field": field, "value": value,
                       "rule": f"类型应为 {t}"})
        return False
    if t == "number" and ok:
        if "min" in spec and value < spec["min"]:
            issues.append({"level": "warning", "field": field, "value": value,
                           "rule": f"低于下限 {spec['min']}"})
        if "max" in spec and value > spec["max"]:
            issues.append({"level": "warning", "field": field, "value": value,
                           "rule": f"高于上限 {spec['max']}"})
    if t == "str" and ok and "enum" in spec and value not in spec["enum"]:
        issues.append({"level": "warning", "field": field, "value": value,
                       "rule": f"应为 {spec['enum']} 之一"})
    return ok


def validate(data, schema=None):
    """按 schema 校验 data，返回 issues 列表。"""
    issues = []
    if schema is None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)
    # 必填块
    for block in schema.get("required_blocks", []):
        if block not in data:
            issues.append({"level": "error", "field": block,
                           "rule": f"必填块缺失"})
    # 标量字段
    for field, spec in (schema.get("fields") or {}).items():
        val = _get_path(data, field)
        if val is None:
            if spec.get("required"):
                issues.append({"level": "error", "field": field, "rule": "必填字段缺失"})
            continue
        _check_type(val, spec, issues, field)
        if spec.get("type") == "object" and spec.get("minItems") and isinstance(val, dict) and len(val) < spec["minItems"]:
            issues.append({"level": "warning", "field": field, "rule": f"对象项数不足（<{spec['minItems']}）"})
    # 数组项规则
    for arr, ar in (schema.get("array_rules") or {}).items():
        items = data.get(arr)
        if items is None:
            continue
        if not isinstance(items, list):
            issues.append({"level": "error", "field": arr, "value": items, "rule": "应为数组"})
            continue
        if len(items) < ar.get("minItems", 0):
            issues.append({"level": "warning", "field": arr, "value": len(items),
                           "rule": f"数组项数不足（<{ar['minItems']}）"})
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            for fld, spec in (ar.get("itemFields") or {}).items():
                val = it.get(fld)
                if val is None:
                    if spec.get("required"):
                        issues.append({"level": "error", "field": f"{arr}[{i}].{fld}", "rule": "必填字段缺失"})
                    continue
                _check_type(val, spec, issues, f"{arr}[{i}].{fld}")
    return issues


def main():
    ap = argparse.ArgumentParser(description="输入 JSON 静态结构校验器（v3.6 D1）")
    ap.add_argument("input", help="估值输入 JSON")
    ap.add_argument("-o", "--output", default=None, help="issues 输出 JSON 路径")
    ap.add_argument("--schema", default=None, help="自定义 schema 路径")
    args = ap.parse_args()
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    schema = None
    if args.schema:
        with open(args.schema, "r", encoding="utf-8") as f:
            schema = json.load(f)
    issues = validate(data, schema)
    errors = [i for i in issues if i.get("level") == "error"]
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"n_issues": len(issues), "n_errors": len(errors), "issues": issues},
                      f, ensure_ascii=False, indent=2)
    for i in issues:
        print(f"[{i['level'].upper()}] {i['field']}: {i['rule']}")
    print(f"校验完成：{len(issues)} 项问题（error {len(errors)} / warning {len(issues)-len(errors)}）")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
