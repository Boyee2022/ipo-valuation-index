#!/bin/bash
# 一键启动：估值跑批 Web 服务（绑定单个内网地址，默认 3081）
# 幂等：已在运行则跳过。用法： bash ~/workspace/valuation-up.sh
set -uo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# 数据隔离：本实例使用独立 DSH_HOME（会话/工作区/存储/附件与 FactorLab 的 ~/.dsh 互不可见）。
# profiles 通过符号链接共享（应用配置，非用户数据）。
export DSH_HOME="$HOME/.dsh-valuation"
mkdir -p "$DSH_HOME"

# 技能隔离：用户级技能目录独立（~/.dsh-valuation/agents），不再读取 FactorLab 共享的
# ~/.agents/skills；内置技能来自仓库/project 目录，不受影响。解析优先级：配置 > DSH_AGENTS_HOME > ~/.agents。
export DSH_AGENTS_HOME="$HOME/.dsh-valuation/agents"
mkdir -p "$DSH_AGENTS_HOME"

REPO="$HOME/workspace/csi-dsh"
PROFILE="valuation"
LOGDIR="$HOME/Library/Logs/valuation"
WEBLOG="$LOGDIR/web.log"
PIDFILE="$LOGDIR/web.pid"
PORT="${VALUATION_PORT:-3081}"
UP_DEADLINE=60   # 秒：等端口进入 LISTEN

mkdir -p "$LOGDIR"
fail() { echo "FAIL: $*" >&2; exit 1; }
listening() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }
token_url() { grep -o 'http://[^[:space:]]*token=[^[:space:]]*' "$WEBLOG" 2>/dev/null | tail -1; }

[ -d "$REPO" ] || fail "缺少仓库目录（$REPO）"
command -v node >/dev/null 2>&1 || fail "缺少 node（应在 $HOME/.local/bin）"
# --host 只接受一个具体地址：通配地址会被拒绝（绑全部接口等于把远程执行暴露给整个网络）。
HOST="${VALUATION_HOST:-$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)}"
[ -n "$HOST" ] || fail "取不到内网 IP；请用 VALUATION_HOST=<ip> 指定"
cd "$REPO" || fail "无法进入 $REPO"

echo "[1/1] Web 服务 ${HOST}:${PORT} (profile ${PROFILE}, DSH_HOME ${DSH_HOME})"
if listening; then
  echo "      already running"
else
  : > "$WEBLOG"
  nohup node --import tsx/esm apps/cli/src/bin.ts --profile "$PROFILE" \
    --host "$HOST" --port "$PORT" --no-open --trusted-host "$HOST" \
    </dev/null >>"$WEBLOG" 2>&1 &
  launcher_pid=$!
  echo "$launcher_pid" > "$PIDFILE"
  i=0
  while [ "$i" -lt "$UP_DEADLINE" ]; do
    listening && break
    kill -0 "$(cat "$PIDFILE")" 2>/dev/null || break
    i=$((i + 1)); sleep 1
  done
  if ! listening; then
    echo "      启动失败，日志尾部：" >&2
    tail -n 30 "$WEBLOG" >&2
    rm -f "$PIDFILE"
    exit 1
  fi
  listener_pid="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t | head -1)"
  [ -n "$listener_pid" ] && echo "$listener_pid" > "$PIDFILE"
  echo "      started (pid $(cat "$PIDFILE"))"
fi

URL=""
i=0
while [ "$i" -lt 10 ]; do
  URL="$(token_url)"
  [ -n "$URL" ] && break
  i=$((i + 1)); sleep 1
done
echo
echo "就绪"
echo "  内网 : ${URL:-http://${HOST}:${PORT}/  （token 未生成，见日志）}"
echo "  停止 : bash ~/workspace/valuation-down.sh"
echo "  日志 : $WEBLOG"
