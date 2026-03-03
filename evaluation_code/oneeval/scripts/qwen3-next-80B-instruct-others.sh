#!/usr/bin/env bash
set -euo pipefail

# =========================
# Required envs
# =========================
: "${MODEL_PATH:?Need env MODEL_PATH (model path or HF repo id)}"
: "${BASE_PATH:?Need env BASE_PATH (datasets/workdir base path)}"
: "${MODEL_NAME:?Need env MODEL_NAME (name for evaluation)}"
: "${ENABLE_THINKING:?Need env ENABLE_THINKING (true|false|none)}"

# =========================
# Optional envs (defaults)
# =========================
PYTHON_BIN="${PYTHON_BIN:-python}"
TRACK="${TRACK:-non_thinking}"

# Bind host can be 0.0.0.0, but health-check host should be connectable.
SGLANG_HOST="${SGLANG_HOST:-0.0.0.0}"          # bind host
SGLANG_CHECK_HOST="${SGLANG_CHECK_HOST:-0.0.0.0}"  # health check host
SGLANG_PORT="${SGLANG_PORT:-8080}"
SGLANG_TP="${SGLANG_TP:-8}"

FILTER_THINKING="${FILTER_THINKING:-false}"

# How long to wait for server readiness
WAIT_RETRIES="${WAIT_RETRIES:-1800}" # 1800 * 2s = 3600s = 1 hour
WAIT_SLEEP_SEC="${WAIT_SLEEP_SEC:-2}"

# Eval script path (relative to this file)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVAL_SCRIPT="${SCRIPT_DIR}/../qwen3-series-others.py"
[[ -f "${EVAL_SCRIPT}" ]] || { echo "Error: Evaluation script not found: ${EVAL_SCRIPT}" >&2; exit 1; }

# =========================
# Cleanup (kill process group)
# =========================
cleanup() {
  echo "[INFO] Cleaning up..."
  if [[ -n "${SGLANG_PID:-}" ]] && kill -0 "${SGLANG_PID}" 2>/dev/null; then
    echo "[INFO] Stopping SGLang server process group (PGID=${SGLANG_PID})..."
    # Terminate the whole process group created by setsid
    kill -TERM -- "-${SGLANG_PID}" 2>/dev/null || true

    # Wait a bit for graceful shutdown
    for _ in {1..10}; do
      if ! kill -0 "${SGLANG_PID}" 2>/dev/null; then
        echo "[INFO] SGLang server stopped gracefully."
        return 0
      fi
      sleep 30
    done

    # Force kill if still alive
    echo "[WARN] SGLang server still running; forcing kill..."
    kill -KILL -- "-${SGLANG_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

# =========================
# Wait for server ready
# =========================
wait_for_server() {
  local url="http://${SGLANG_CHECK_HOST}:${SGLANG_PORT}/v1/models"
  echo "[INFO] Waiting for SGLang server: ${url}"
  for _ in $(seq 1 "${WAIT_RETRIES}"); do
    if curl -s -f "${url}" >/dev/null 2>&1; then
      echo "[INFO] SGLang server is ready!"
      return 0
    fi
    if [[ -n "${SGLANG_PID:-}" ]] && ! kill -0 "${SGLANG_PID}" 2>/dev/null; then
      echo "[ERROR] SGLang server process died unexpectedly" >&2
      return 1
    fi
    sleep "${WAIT_SLEEP_SEC}"
  done
  echo "[ERROR] SGLang server not ready in time" >&2
  return 1
}

# =========================
# Start SGLang server (setsid => new process group)
# =========================
echo "[INFO] Starting SGLang server..."
echo "[INFO] MODEL_PATH=${MODEL_PATH}"
echo "[INFO] SGLANG_HOST=${SGLANG_HOST} SGLANG_PORT=${SGLANG_PORT} SGLANG_TP=${SGLANG_TP}"
echo "[INFO] SGLANG_CHECK_HOST=${SGLANG_CHECK_HOST}"
echo "[INFO] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-<empty>}"

export CUDA_VISIBLE_DEVICES

SGLANG_LOG="/tmp/sglang_server_$$.log"

# setsid: create a new session; the PID becomes the PGID.
setsid "${PYTHON_BIN}" -m sglang.launch_server \
  --model-path "${MODEL_PATH}" \
  --host "${SGLANG_HOST}" \
  --port "${SGLANG_PORT}" \
  --tp "${SGLANG_TP}" \
  --context-length 262144 \
  --mem-fraction-static 0.8 \
  --speculative-algo NEXTN \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 > "${SGLANG_LOG}" 2>&1 &

SGLANG_PID=$!
echo "[INFO] SGLang PID=${SGLANG_PID} LOG=${SGLANG_LOG}"

sleep 2
kill -0 "${SGLANG_PID}" 2>/dev/null || {
  echo "[ERROR] Server failed to start. Logs:" >&2
  tail -n 200 "${SGLANG_LOG}" >&2
  exit 1
}

wait_for_server || {
  echo "[ERROR] Logs:" >&2
  tail -n 200 "${SGLANG_LOG}" >&2
  exit 1
}

# =========================
# Run evaluation
# =========================
echo "[INFO] Starting evaluation..."
echo "[INFO] BASE_PATH=${BASE_PATH} MODEL_NAME=${MODEL_NAME} TRACK=${TRACK}"
echo "[INFO] ENABLE_THINKING=${ENABLE_THINKING} FILTER_THINKING=${FILTER_THINKING}"

EVAL_ARGS=(
  --base-path "${BASE_PATH}"
  --model-name "${MODEL_NAME}"
  --track "${TRACK}"
  --enable-thinking "${ENABLE_THINKING}"
)

case "${FILTER_THINKING,,}" in
  1|true|yes|y)
    EVAL_ARGS+=(--filter-thinking)
    ;;
esac

echo "${EVAL_ARGS[@]}"


"${PYTHON_BIN}" "${EVAL_SCRIPT}" "${EVAL_ARGS[@]}"
echo "[INFO] Evaluation Non-Thinking completed successfully!"

echo "[INFO] Evaluation finished. Exiting; trap will stop SGLang."
