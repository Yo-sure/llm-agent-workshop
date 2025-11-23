#!/usr/bin/env python3
"""
Trading Bot Host - Main Entry Point

LangGraph Agent + MCP + FastAPI + WebSocket HITL

사용법:
    python langgraph_agent/trading_bot_host.py
    
    브라우저: http://localhost:8080
    API: POST /api/trade {"ticker": "AAPL"}
"""

import os
import sys
import asyncio
import threading
from pathlib import Path

import uvicorn

# 모듈 경로 추가
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

from langgraph_agent import trading_agent, trading_api


def run_web_server():
    """FastAPI 서버 실행 (별도 스레드)"""
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        trading_api.app,
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


async def main():
    """메인 실행 로직"""
    print("🤖 MCP 기반 Trading Bot with HITL (STDIO) 시작")
    print("=" * 60)

    try:
        # Agent 초기화
        mcp_client, agent = await trading_agent.build_agent()

        print("\n🎯 시스템 준비 완료!")
        print(f"💡 Web UI: http://localhost:{os.getenv('PORT', '8080')}")
        print("💡 API: POST /api/trade {'ticker':'AAPL'}")

        # FastAPI 서버를 별도 스레드로 실행
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()

        # 메인 루프 유지
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n👋 종료 요청")
    except Exception as e:
        print(f"\n❌ 시스템 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔚 시스템 종료됨")


if __name__ == "__main__":
    asyncio.run(main())
