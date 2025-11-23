#!/usr/bin/env python3
"""
LangGraph Trading Agent with HITL

- MCP Client 초기화
- LangGraph Agent 생성
- HITL (Human-in-the-Loop) 도구
- 거래 분석 실행
"""

import os
import json
import sys
import time
import uuid
import asyncio
from typing import Dict, Any, Literal
from datetime import datetime
from pathlib import Path
from queue import SimpleQueue

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from langchain_mcp_adapters.client import MultiServerMCPClient

# =============================================================================
# PATHS & ENV
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
MCP_SERVER_PATH = str(BASE_DIR / "trading_mcp_server.py")

# .env 파일 로드 (프로젝트 루트)
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# =============================================================================
# GLOBAL STATE (In-Memory)
# =============================================================================

pending_approvals: Dict[str, Dict[str, Any]] = {}
completed_approvals: Dict[str, Dict[str, Any]] = {}

# API에서 사용하는 broadcast queue
broadcast_queue: SimpleQueue[dict] = SimpleQueue()

agent_ready = asyncio.Event()
global_agent = None
global_mcp_client: MultiServerMCPClient | None = None


# =============================================================================
# HITL TOOL
# =============================================================================


@tool("request_human_approval")
async def request_human_approval(ticker: str,
                                 action: Literal["BUY", "SELL"],
                                 reason: str,
                                 market_data: str = "") -> str:
    """
    BUY/SELL 의사결정에 대한 인간 승인을 요청하고 5분간 대기한다.
    """
    try:
        if action not in ("BUY", "SELL"):
            return json.dumps(
                {
                    "approved": False,
                    "error": "승인은 BUY/SELL 액션에만 필요합니다",
                    "timestamp": time.time()
                },
                ensure_ascii=False)

        request_id = f"approval_{ticker}_{action}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        approval_request = {
            "request_id": request_id,
            "ticker": ticker,
            "action": action,
            "reason": reason,
            "market_data": market_data,
            "timestamp": time.time(),
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        pending_approvals[request_id] = approval_request

        broadcast_queue.put({"type": "approval_request", "data": approval_request})

        print(f"🔔 승인 요청 생성: {ticker} {action} (ID: {request_id})")

        max_wait_time = 300  # 5분
        check_interval = 2
        waited = 0
        while waited < max_wait_time:
            if request_id not in pending_approvals:
                break
            await asyncio.sleep(check_interval)
            waited += check_interval

        if request_id in pending_approvals:
            del pending_approvals[request_id]
            return json.dumps(
                {
                    "approved": False,
                    "error": "승인 요청 시간 초과 (5분)",
                    "timeout": True,
                    "timestamp": time.time()
                },
                ensure_ascii=False)

        result = completed_approvals.pop(request_id, None)
        if result:
            return json.dumps(result, ensure_ascii=False)

        return json.dumps(
            {
                "approved": False,
                "error": "승인 상태를 확인할 수 없습니다",
                "timestamp": time.time()
            },
            ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {
                "approved": False,
                "error": f"승인 요청 중 오류 발생: {str(e)}",
                "timestamp": time.time()
            },
            ensure_ascii=False)


# =============================================================================
# APPROVAL HANDLERS
# =============================================================================


async def handle_approval_response(message: Dict[str, Any]):
    """승인/거부 응답 처리"""
    req_id = message["request_id"]
    approved = bool(message["approved"])

    if req_id in pending_approvals:
        req = pending_approvals[req_id]
        print(
            f"\n✅ 승인 응답: {req['ticker']} {req['action']} - {'승인' if approved else '거부'}"
        )

        if approved:
            token = f"token_{req_id}_{int(time.time())}"
            result = {
                "approved": True,
                "message": "승인 완료",
                "approval_token": token,
                "timestamp": time.time()
            }
            print(f"🎫 승인 토큰: {token}")
        else:
            result = {
                "approved": False,
                "message": "거래가 거부되었습니다",
                "timestamp": time.time()
            }

        completed_approvals[req_id] = result
        del pending_approvals[req_id]

        return {
            "type": "approval_processed",
            "request_id": req_id,
            "approved": approved
        }
    return None


# =============================================================================
# AGENT BUILDER
# =============================================================================


async def build_agent() -> tuple[MultiServerMCPClient, any]:
    """
    STDIO로 trade MCP 서버(trading_mcp_server.py)를 자식 프로세스로 실행하고,
    노출된 MCP tools를 LangGraph ReAct agent에 바인딩한다.
    """
    PYTHON = os.environ.get("PYTHON_EXECUTABLE") or sys.executable

    client = MultiServerMCPClient({
        "trade": {
            "transport": "stdio",
            "command": PYTHON,
            "args": [MCP_SERVER_PATH],
        }
    })

    tools = await client.get_tools()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
    memory = MemorySaver()
    agent = create_react_agent(model=model,
                               tools=[request_human_approval] + tools,
                               checkpointer=memory)

    global global_agent, global_mcp_client
    global_agent = agent
    global_mcp_client = client
    agent_ready.set()
    
    return client, agent


async def run_trading_demo(agent, ticker: str = "NVDA"):
    """거래 분석 실행"""
    msg = f"""
{ticker} 종목에 대해 거래 분석을 수행해주세요.

다음 단계를 따라주세요:
1. analyze_market_trend 도구를 사용해서 {ticker}의 시장 동향을 분석하세요
2. 분석 결과를 바탕으로 BUY/SELL/HOLD 결정을 내리세요
3. BUY 또는 SELL 추천 시에는 request_human_approval 도구로 사용자 승인을 요청하세요
4. 승인 후 execute_trade 도구로 거래를 실행하세요

모든 응답은 한국어로 해주세요.
""".strip()

    config = {"configurable": {"thread_id": f"demo_{int(time.time())}"}}
    res = await agent.ainvoke({"messages": [HumanMessage(content=msg)]},
                              config)
    print("\n📋 에이전트 응답(요약):")
    print(res['messages'][-1].content if res else "")
    return res

