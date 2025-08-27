#!/usr/bin/env bash
set -euo pipefail

# 내부 A2A 서버 포트 (기본 9999)
export A2A_SERVER_PORT="${A2A_SERVER_PORT:-9999}"

# Repl B LangFlow 연결에 필요한 값들(Secrets로 이미 설정되어 있어야 함)
: "${LANGFLOW_BASE_URL:?LANGFLOW_BASE_URL not set}"
: "${LANGFLOW_FLOW_ID:?LANGFLOW_FLOW_ID not set}"
: "${LANGFLOW_API_KEY:?LANGFLOW_API_KEY not set}"

# 1) A2A 서버 먼저 백그라운드로
uv run python langgraph_agent_with_a2a/news_a2a_server_for_langflow.py &
A2A_PID=$!

# 2) 호스트(8080) 포그라운드
uv run python langgraph_agent_with_a2a/session_7_a2a_host.py

# 3) 종료 시 백그라운드도 정리
trap "kill $A2A_PID 2>/dev/null || true" EXIT
