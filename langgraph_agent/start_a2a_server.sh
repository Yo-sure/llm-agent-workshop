#!/usr/bin/env bash
# A2A News Server 시작 스크립트 (Langflow 래퍼)
# 
# 사용법:
#   ./start_a2a_server.sh
#
# 환경변수 (필수):
#   LANGFLOW_BASE_URL: Langflow 서버 주소 (예: http://localhost:7860)
#   LANGFLOW_FLOW_ID: 실행할 Flow ID (Langflow UI에서 확인)
#   LANGFLOW_API_KEY: Langflow API Key (Langflow UI에서 발급)
#   A2A_SERVER_PORT: A2A 서버 포트 (기본: 9999)

set -e

cd "$(dirname "$0")"

# .env 파일 로드 (프로젝트 루트)
if [ -f "../.env" ]; then
    echo "📄 .env 파일 로드 중..."
    export $(grep -v '^#' ../.env | xargs)
fi

# 필수 환경변수 확인
if [ -z "$LANGFLOW_BASE_URL" ] || [ -z "$LANGFLOW_FLOW_ID" ] || [ -z "$LANGFLOW_API_KEY" ]; then
    echo "❌ 필수 환경변수가 설정되지 않았습니다"
    echo "필요한 환경변수:"
    echo "  - LANGFLOW_BASE_URL"
    echo "  - LANGFLOW_FLOW_ID"
    echo "  - LANGFLOW_API_KEY"
    echo ""
    echo ".env 파일을 확인하거나 환경변수를 직접 설정하세요"
    exit 1
fi

PORT=${A2A_SERVER_PORT:-9999}

echo "🚀 A2A News Server 시작 중..."
echo "   Langflow: $LANGFLOW_BASE_URL"
echo "   Flow ID: $LANGFLOW_FLOW_ID"
echo "   Port: $PORT"

cd ..
uv run python a2a_news_server.py

