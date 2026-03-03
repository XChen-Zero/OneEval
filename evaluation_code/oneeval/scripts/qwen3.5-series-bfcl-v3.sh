#!/usr/bin/env bash
set -euo pipefail

# =========================
# Required envs
# =========================
: "${MODEL_PATH:?Need env MODEL_PATH (model path or HF repo id)}"
: "${MODEL_NAME:?Need env MODEL_NAME (name for evaluation)}"
: "${BASE_PATH:?Need env BASE_PATH (datasets/workdir base path)}"
: "${BFCL_PROJECT_BASE:?Need env BFCL_PROJECT_BASE (BFCL project base path)}"
: "${BFCL_EVAL_PYTHONPATH:?Need env BFCL_EVAL_PYTHONPATH (path to bfcl_eval checkout)}"
: "${COT_MODEL_NAME:?Need env CT_MODEL_NAME (CT model name)}"
: "${NOCOT_MODEL_NAME:?Need env NOCOT_MODEL_NAME (NOCOT model name)}"

# =========================
# Optional envs (defaults)
# =========================
PYTHON_BIN="${PYTHON_BIN:-python}"

# Bind host can be 0.0.0.0, but health-check host should be connectable.
SGLANG_HOST="${SGLANG_HOST:-0.0.0.0}"          # bind host
SGLANG_CHECK_HOST="${SGLANG_CHECK_HOST:-0.0.0.0}"  # health check host
SGLANG_PORT="${SGLANG_PORT:-8080}"
SGLANG_TP="${SGLANG_TP:-8}"

# How long to wait for server readiness
WAIT_RETRIES="${WAIT_RETRIES:-1800}" # 1800 * 2s = 3600s = 1 hour
WAIT_SLEEP_SEC="${WAIT_SLEEP_SEC:-2}"

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
echo "[INFO] MODEL_NAME=${MODEL_NAME}"
echo "[INFO] SGLANG_PORT=${SGLANG_PORT} SGLANG_TP=${SGLANG_TP}"


SGLANG_LOG="/tmp/sglang_server_$$.log"
CHAT_TEMPLATE="${BASE_PATH}/codes/evalscope/xeval/chat_templates/qwen3_nonthinking.jinja"


export SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1
# setsid: create a new session; the PID becomes the PGID.
setsid "${PYTHON_BIN}" -m sglang.launch_server \
  --model-path "${MODEL_PATH}" \
  --served-model-name "${MODEL_NAME}" \
  --host "${SGLANG_HOST}" \
  --port "${SGLANG_PORT}" \
  --tp-size "${SGLANG_TP}" \
  --mem-fraction-static 0.8 \
  --context-length 262144 \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  > "${SGLANG_LOG}" 2>&1 &

SGLANG_PID=$!
echo "[INFO] SGLang PID=${SGLANG_PID}"

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
echo "[INFO] BFCL v3 evaluation for ${MODEL_NAME}"

export LOCAL_SERVER_PORT="${SGLANG_PORT}"
export LOCAL_SERVER_ENDPOINT="localhost"
export OPENAI_API_KEY="EMPTY"
export OVERRIDE_MAX_CONTEXT_LENGTH="${OVERRIDE_MAX_CONTEXT_LENGTH:-131072}"

echo "[INFO] Local server port=${LOCAL_SERVER_PORT} context_length=${OVERRIDE_MAX_CONTEXT_LENGTH}"
RUN_TIMES="${RUN_TIMES:-1}"

TEST_CATEGORIES="multi_turn,single_turn,live,non_live,python,non_python"
THREADS="${THREADS:-16}"
THINKINGS=("NoCoT" "CoT")

if [[ ! -d "${BFCL_EVAL_PYTHONPATH}" ]]; then
  echo "[ERROR] BFCL_EVAL_PYTHONPATH does not exist or is not a directory" >&2
  exit 1
fi

cd "${BFCL_EVAL_PYTHONPATH}"
echo "[INFO] BFCL evaluation checkout is ready."

export QWEN_AGENT_MODEL_SERVER="http://${LOCAL_SERVER_ENDPOINT}:${LOCAL_SERVER_PORT}/v1"
export QWEN_AGENT_SERVED_MODEL_NAME="${MODEL_NAME}"
export QWEN_AGENT_API_KEY="EMPTY"

for THINKING in "${THINKINGS[@]}"; do

  for ((i=1; i<=RUN_TIMES; i++)); do

    export BFCL_PROJECT_ROOT="${BFCL_PROJECT_BASE}/${MODEL_NAME}/${THINKING}/run_${i}"
    mkdir -p "$BFCL_PROJECT_ROOT"

    echo "========================================"
    echo "[INFO] MODEL_NAME=$MODEL_NAME"
    echo "[INFO] RUN=run_${i} MODE=${THINKING}"
    echo "[INFO] Output directory prepared."
    echo "========================================"
    if [ "$THINKING" == "CoT" ]; then
      export BFCL_MODEL_NAME="${COT_MODEL_NAME}"
    else
      export BFCL_MODEL_NAME="${NOCOT_MODEL_NAME}"
    fi
    echo "[INFO] BFCL_MODEL_NAME=$BFCL_MODEL_NAME"

    python bfcl_eval/__main__.py generate \
      --model "$BFCL_MODEL_NAME" \
      --test-category "$TEST_CATEGORIES" \
      --num-threads "$THREADS"

    python bfcl_eval/__main__.py evaluate --model "$BFCL_MODEL_NAME"
  done
done

echo "[DONE] Model $MODEL_NAME evaluation completed."
