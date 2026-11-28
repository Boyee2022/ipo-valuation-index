#!/bin/bash
# 四张学术海报一键编译 + 预览渲染。
# 用法：bash docs/posters/build.sh
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p previews

for f in cn-finance cn-core en-nlp en-finance; do
  [ -f "$f.tex" ] || { echo "skip $f (missing)"; continue; }
  echo "== $f"
  xelatex -interaction=nonstopmode "$f.tex" >/dev/null 2>&1
  xelatex -interaction=nonstopmode "$f.tex" >/dev/null 2>&1
  if [ -f "$f.pdf" ]; then
    sips -s format png "$f.pdf" --out "previews/$f.png" >/dev/null 2>&1
    pages=$(grep -oE 'Output written on .* \(([0-9]+) page' "$f.log" 2>/dev/null | grep -oE '[0-9]+ page' | tail -1)
    echo "   PDF: $(du -h "$f.pdf" | cut -f1)  ${pages:-?}"
  else
    echo "   FAILED: no PDF"
  fi
  rm -f "$f.aux" "$f.log" "$f.nav" "$f.out" "$f.snm" "$f.toc" "$f.synctex.gz"
done
