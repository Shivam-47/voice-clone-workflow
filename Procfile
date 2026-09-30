llm: bash -c 'set -a; source .env; set +a; exec mlx_lm.server --model "${LLM_MODEL:-mlx-community/Qwen3-8B-4bit}" --host 127.0.0.1 --port "${LLM_PORT:-8080}"'
stt: bash -c 'set -a; source .env; set +a; exec mlx_audio.server --host 127.0.0.1 --port "${STT_PORT:-8000}"'
tts: bash -c 'set -a; source .env; set +a; exec uvicorn server.tts_server:app --host 127.0.0.1 --port "${TTS_PORT:-8001}"'
