#!/usr/bin/env bash
set -euo pipefail

: "${EMBEDDING_API_KEY:?EMBEDDING_API_KEY is required}"

export CUDA_VISIBLE_DEVICES="${EMBEDDING_GPU_ID:-1}"

exec python -m vllm.entrypoints.openai.api_server \
  --model "${EMBEDDING_MODEL:-Qwen/Qwen3-Embedding-0.6B}" \
  --served-model-name "${EMBEDDING_SERVED_MODEL:-main}" \
  --runner pooling \
  --host "${EMBEDDING_HOST:-0.0.0.0}" \
  --port "${EMBEDDING_PORT:-8001}" \
  --max-model-len "${EMBEDDING_MAX_MODEL_LEN:-4096}" \
  --gpu-memory-utilization "${EMBEDDING_GPU_MEMORY_UTILIZATION:-0.06}" \
  --api-key "$EMBEDDING_API_KEY"
