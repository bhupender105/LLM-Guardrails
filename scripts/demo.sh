#!/usr/bin/env bash
# Start the chat-UI demo: LangGraph server (both agents) + Next.js chat UI.
#   bash scripts/demo.sh
# Then open side by side:
#   http://localhost:3000/?assistantId=unguarded
#   http://localhost:3000/?assistantId=guarded
# LangGraph Studio (live graph view): https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d chat-ui/node_modules ] || npx -y pnpm@10 --dir chat-ui install
[ -f chat-ui/.env ] || printf 'NEXT_PUBLIC_API_URL=http://localhost:2024\nNEXT_PUBLIC_ASSISTANT_ID=guarded\n' > chat-ui/.env

uv run langgraph dev --no-browser --port 2024 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
npx -y pnpm@10 --dir chat-ui dev
