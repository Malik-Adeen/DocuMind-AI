#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/CodeBase/backend"
FRONTEND_DIR="$SCRIPT_DIR/CodeBase/frontend/documind-ai"
COMPOSE_FILE="$BACKEND_DIR/docker-compose.yml"
DEV_DIR="$SCRIPT_DIR/.dev"

HEALTH_TIMEOUT=90
FRONTEND_PORT=5173

is_running() {
  local pidfile="$DEV_DIR/$1.pid"
  if [ -f "$pidfile" ]; then
    local pid
    pid="$(cat "$pidfile")"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

start_bg() {
  local name="$1" dir="$2"
  shift 2
  local logfile="$DEV_DIR/$name.log"
  local pidfile="$DEV_DIR/$name.pid"
  (
    cd "$dir"
    setsid "$@" >"$logfile" 2>&1 </dev/null &
    echo $! >"$pidfile"
  )
}

stop_bg() {
  local name="$1"
  local pidfile="$DEV_DIR/$name.pid"
  if [ ! -f "$pidfile" ]; then
    return 0
  fi
  local pid
  pid="$(cat "$pidfile")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM "-$pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -0 "$pid" 2>/dev/null && kill -KILL "-$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && return 0
  (exec 3<>"/dev/tcp/::1/$1") 2>/dev/null && return 0
  return 1
}

wait_for_health() {
  local waited=0
  local svc all_healthy cid status
  while true; do
    all_healthy=true
    for svc in postgres redis; do
      cid="$(docker compose -f "$COMPOSE_FILE" ps -q "$svc")"
      if [ -z "$cid" ]; then
        all_healthy=false
        break
      fi
      status="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo unknown)"
      if [ "$status" != "healthy" ]; then
        all_healthy=false
        break
      fi
    done
    if [ "$all_healthy" = true ]; then
      return 0
    fi
    waited=$((waited + 2))
    if [ "$waited" -ge "$HEALTH_TIMEOUT" ]; then
      echo "dev.sh: services did not become healthy within ${HEALTH_TIMEOUT}s" >&2
      docker compose -f "$COMPOSE_FILE" ps >&2
      exit 1
    fi
    sleep 2
  done
}

do_start() {
  if port_in_use "$FRONTEND_PORT"; then
    echo "dev.sh: ERROR: port $FRONTEND_PORT is already in use." >&2
    echo "  The frontend's CORS origin is fixed to http://localhost:$FRONTEND_PORT (see" >&2
    echo "  app/core/config.py's cors_allow_origins). Vite would silently fall back to the" >&2
    echo "  next free port instead, and the app would then fail to log in with a CORS error." >&2
    echo "  Free port $FRONTEND_PORT first (check what's on it: lsof -i :$FRONTEND_PORT) and rerun." >&2
    exit 1
  fi

  mkdir -p "$DEV_DIR"

  local name already
  already=false
  for name in celery uvicorn frontend; do
    if is_running "$name"; then
      already=true
    fi
  done
  if [ "$already" = true ]; then
    echo "dev.sh: already running (live PIDs found in $DEV_DIR). Run './dev.sh stop' first if you want to restart."
    exit 0
  fi

  echo "dev.sh: bringing up docker compose stack (postgres, redis)..."
  docker compose -f "$COMPOSE_FILE" up -d

  echo "dev.sh: waiting for postgres and redis to report healthy..."
  wait_for_health
  echo "dev.sh: both services healthy."

  echo "dev.sh: starting celery worker..."
  start_bg celery "$BACKEND_DIR" env CELERY_TASK_ALWAYS_EAGER=false uv run celery -A app.workers worker -l info --pool solo

  echo "dev.sh: starting uvicorn..."
  start_bg uvicorn "$BACKEND_DIR" env CELERY_TASK_ALWAYS_EAGER=false uv run uvicorn app.main:app --reload

  echo "dev.sh: starting frontend dev server..."
  start_bg frontend "$FRONTEND_DIR" npm run dev

  echo
  echo "dev.sh: started."
  echo "  celery worker : pid $(cat "$DEV_DIR/celery.pid")   log: $DEV_DIR/celery.log"
  echo "  uvicorn        : pid $(cat "$DEV_DIR/uvicorn.pid")  log: $DEV_DIR/uvicorn.log"
  echo "  frontend (vite): pid $(cat "$DEV_DIR/frontend.pid") log: $DEV_DIR/frontend.log"
  echo
  echo "  tail logs with: tail -f $DEV_DIR/celery.log $DEV_DIR/uvicorn.log $DEV_DIR/frontend.log"
  echo "  stop everything with: $SCRIPT_DIR/dev.sh stop"
}

do_stop() {
  local name
  for name in celery uvicorn frontend; do
    stop_bg "$name"
  done
  echo "dev.sh: bringing down docker compose stack..."
  docker compose -f "$COMPOSE_FILE" down
  echo "dev.sh: stopped."
}

cmd="${1:-start}"
case "$cmd" in
  start)
    do_start
    ;;
  stop)
    do_stop
    ;;
  *)
    echo "usage: $0 [start|stop]" >&2
    exit 1
    ;;
esac
