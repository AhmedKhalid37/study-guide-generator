#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-}"
if [ -z "$MODEL_PATH" ]; then
  echo "Usage: bash scripts/run_llama_server.sh ~/models/model.gguf"
  exit 1
fi

LLAMA_SERVER="${LLAMA_SERVER:-$HOME/projects/llama.cpp/build/bin/llama-server}"

"$LLAMA_SERVER" \
  -m "$MODEL_PATH" \
  --host 127.0.0.1 \
  --port "${PORT:-8080}" \
  -c "${CTX:-32768}" \
  -ngl "${NGL:-99}" \
  --flash-attn "${FLASH_ATTN:-auto}"
