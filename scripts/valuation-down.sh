#!/bin/bash
# 一键停止：估值跑批 Web 服务。幂等：已停止则跳过。
# 用法： bash ~/workspace/valuation-down.sh
set -uo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

LOGDIR="$HOME/Library/Logs/valuation"
WEBLOG="$LOGDIR/web.log"
PIDFILE="$LOGDIR/web.pid"
PORT="${VALUATION_PORT:-3081}"
DOWN_DEADLINE=30   # 秒：等端口释放

mkdir -p "$LOGDIR"
fail() { echo "FAIL: $*" >&2; exit 1; }
listening() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

echo "[1/1] 停止 Web 服务 :$PORT"
if listening; then
  pid=""
  [ -f "$PIDFILE" ] && pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  listener_pid="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t | head -1)"
  [ -n "$listener_pid" ] || fail "端口 $PORT 被监听但取不到 pid；请自行确认后处理，避免误杀别的进程"
  ps -o command= -p "$listener_pid" | grep -q "apps/cli/src/bin.ts" || fail "监听进程 $listener_pid 不是本服务；请自行确认后处理"
  [ -n "$pid" ] || echo "      警告：缺少 pid 文件，按监听进程 $listener_pid 停止" >&2
  [ -z "$pid" ] || [ "$pid" = "$listener_pid" ] || echo "      警告：pid 文件 $pid 与监听进程 $listener_pid 不符，按监听进程停止" >&2
  pid="$listener_pid"
  kill "$pid" 2>/dev/null || true
  i=0
  while [ "$i" -lt "$DOWN_DEADLINE" ]; do
    listening || break
    i=$((i + 1)); sleep 1
  done
  if listening; then
    echo "      正常结束超时，强制结束" >&2
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
  fi
  listening && fail "服务未停止（$PORT 仍被监听）"
  rm -f "$PIDFILE"
  echo "      stopped"
else
  rm -f "$PIDFILE"
  echo "      already stopped"
fi

echo
echo "已停止"
echo "  重启 : bash ~/workspace/valuation-up.sh"
echo "  日志 : $WEBLOG"
