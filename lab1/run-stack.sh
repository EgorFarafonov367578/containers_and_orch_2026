#!/usr/bin/env bash
# Живое демо ЛР 1: бэкенд + локальная LLM (llama.cpp, Qwen3-1.7B).
# Идемпотентен: повторный запуск пересоздаёт контейнеры.
# Модель (~1.3 ГБ) скачивается при первом старте greetings-model —
# следите за логами: docker logs -f greetings-model
set -euo pipefail

LLAMA_IMAGE="ghcr.io/ggml-org/llama.cpp:server"

# образ бэкенда собираем локально: на чистой машине его неоткуда скачать
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
docker build -t greetings-backend "$SCRIPT_DIR/backend"

# общая сеть для бэкенда и модели
docker network create greetings-net >/dev/null 2>&1 || true
docker volume create greetings-model-cache >/dev/null

# сервер модели: OpenAI-совместимый API на 8080, кэш GGUF на volume
docker rm -f greetings-model >/dev/null 2>&1 || true
docker run -d --name greetings-model --network greetings-net \
  -v greetings-model-cache:/root/.cache/llama.cpp \
  "$LLAMA_IMAGE" \
  -hf lmstudio-community/Qwen3-1.7B-GGUF:Q4_K_M \
  -c 4096 --host 0.0.0.0 --port 8080 --reasoning off

# бэкенд: ходит в модель по внутренней сети, наружу — 8002
docker rm -f greetings-llm >/dev/null 2>&1 || true
docker run -d --name greetings-llm --network greetings-net \
  -p 8002:8000 -v greetings-data:/data \
  -e LLM_BASE_URL=http://greetings-model:8080/v1 \
  -e LLM_MODEL=qwen3-1.7b \
  greetings-backend

echo "Модель загружается (при первом запуске ~1.3 ГБ): docker logs -f greetings-model"
echo "Проверка (после строки server listening): curl -s http://localhost:8002/api/greeting"
