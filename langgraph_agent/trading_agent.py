#!/usr/bin/env python3
"""
LangGraph Trading Agent with Human-in-the-Loop (HITL)

═══════════════════════════════════════════════════════════════════════════════
시스템 아키텍처 (전체 흐름)
═══════════════════════════════════════════════════════════════════════════════

1. 사용자가 Web UI에서 종목 분석 요청
2. trading_api.py → run_trading_analysis() 호출
3. LangGraph Agent 실행 시작
4. Agent가 analyze_market_trend (MCP tool) 호출
5. Agent가 BUY/SELL 결정 → request_human_approval 호출
6. interrupt()로 그래프 실행 중단 → WebSocket으로 승인 요청 전송
7. 사용자가 승인/거부 → WebSocket으로 응답 수신
8. resume_agent_execution()으로 그래프 재개
9. Agent가 execute_trade (MCP tool) 호출하여 거래 실행
10. 완료 메시지 전송

═══════════════════════════════════════════════════════════════════════════════
LangGraph 구조 (create_react_agent가 생성하는 그래프)
═══════════════════════════════════════════════════════════════════════════════

    ┌─────────┐
    │  START  │
    └────┬────┘
         │
         v
    ┌────────────────────────────────────────────┐
    │  Agent Node (ReAct Loop)                   │
    │  - LLM이 다음 행동 결정                      │
    │  - Tool 호출 또는 최종 응답 생성              │
    └────┬────────────────────────────────────┬──┘
         │                                    │
         │ (Tool 호출 필요)                    │ (최종 응답)
         v                                    v
    ┌─────────────────┐                  ┌────────┐
    │  Tools Node     │                  │  END   │
    │  - MCP tools    │                  └────────┘
    │  - HITL tool    │
    └────┬────────────┘
         │
         │ (interrupt() 호출 시)
         v
    ┌─────────────────────────┐
    │  🔴 INTERRUPT           │  ← 여기서 멈춤!
    │  사용자 승인 대기          │    Command(resume=...) 필요
    └─────────────────────────┘

    재개 시: Command(resume=response) → Tools Node 완료 → Agent Node로 복귀

═══════════════════════════════════════════════════════════════════════════════
모듈 책임
═══════════════════════════════════════════════════════════════════════════════

- build_agent(): MCP Client + LangGraph Agent 초기화
- request_human_approval(): HITL Tool (interrupt 사용)
- run_trading_analysis(): 거래 분석 실행 (초기 시작)
- resume_agent_execution(): 중단된 Agent 재개
"""

import os
import json
import sys
import time
import uuid
import asyncio
from typing import Dict, Any, Literal, Optional
from datetime import datetime
from pathlib import Path
from queue import SimpleQueue
from contextvars import ContextVar

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langgraph.graph.state import CompiledStateGraph
from langgraph.errors import GraphInterrupt
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage

# A2A News Client
try:
    from a2a_news_client import NewsA2AClient
    A2A_AVAILABLE = True
except ImportError:
    NewsA2AClient = None  # 타입 힌트용 Fallback
    A2A_AVAILABLE = False
    print("⚠️  A2A Client를 사용할 수 없습니다. 뉴스 기능이 비활성화됩니다.")
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
# CONSTANTS
# =============================================================================

# WebSocket 메시지 타입 (UI와 통신)
class MessageType:
    """WebSocket을 통해 UI로 전송되는 메시지 타입"""
    AGENT_MESSAGE = "agent_message"      # AI의 사고 과정/응답
    TOOL_RESULT = "tool_result"          # Tool 실행 결과
    AGENT_COMPLETED = "agent_completed"  # Agent 실행 완료
    AGENT_ERROR = "agent_error"          # Agent 실행 오류
    APPROVAL_REQUEST = "approval_request"  # 승인 요청
    PROMPT_LOADED = "prompt_loaded"      # 프롬프트 정보 표시

# =============================================================================
# GLOBAL STATE (In-Memory)
# =============================================================================

# UI 브로드캐스트 큐
# - Agent 실행 중 발생하는 이벤트를 WebSocket으로 전송하기 위한 큐
# - trading_api.py의 lifespan이 이 큐를 읽어서 모든 연결에 브로드캐스트
ui_message_queue: SimpleQueue[dict] = SimpleQueue()

# Agent 초기화 상태
# - build_agent() 완료 시 set()
# - API 요청 전 wait()로 초기화 대기
agent_ready = asyncio.Event()

# LangGraph Agent 인스턴스
# - create_react_agent()로 생성된 실행 가능한 그래프
# - checkpointer를 통해 상태 관리 (thread_id별 독립)
agent_graph = None

# MCP Client 인스�ance
# - STDIO로 trading_mcp_server.py와 통신
# - analyze_market_trend, execute_trade 등 Tool 제공
mcp_client: MultiServerMCPClient | None = None

# A2A News Client 인스턴스
# - HTTP로 A2A 서버(Langflow 래퍼)와 통신
# - 종목 뉴스 분석 데이터 제공
news_a2a_client = None  # Type: NewsA2AClient | None

# 승인 요청 매핑
# - key: request_id (승인 요청 고유 ID)
# - value: thread_id (해당 승인이 속한 Agent 실행 thread)
# - WebSocket으로 승인 응답 받을 때 어느 thread를 재개할지 찾기 위함
pending_approvals: Dict[str, str] = {}
pending_request_payloads: Dict[str, Dict[str, Any]] = {}

# 현재 실행 중인 thread_id (ContextVar)
# - Tool 함수는 동기 함수라 thread_id를 직접 전달받을 수 없음
# - ContextVar로 async context에서 thread_id를 공유
# - run_trading_analysis()에서 set(), tool에서 get()
active_thread_context: ContextVar[Optional[str]] = ContextVar('active_thread_context', default=None)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _create_approval_response(approved: bool, message: str, request_id: str = "", 
                              error: str = "") -> str:
    """
    승인 응답 JSON을 생성합니다.
    
    Args:
        approved: 승인 여부
        message: 응답 메시지
        request_id: 요청 ID (승인 시 토큰 생성용)
        error: 에러 메시지 (에러 시)
    
    Returns:
        JSON 문자열
    """
    response = {
        "approved": approved,
        "message": message,
        "timestamp": time.time()
    }
    
    if approved and request_id:
        response["approval_token"] = f"token_{request_id}_{int(time.time())}"
    
    if error:
        response["error"] = error
    
    return json.dumps(response, ensure_ascii=False)


def _broadcast(message_type: str, **payload) -> None:
    """UI 브로드캐스트 큐에 공통 포맷으로 메시지 추가."""
    payload.setdefault("timestamp", time.time())
    payload["type"] = message_type
    ui_message_queue.put(payload)


def _emit_agent_message(thread_id: str, content: str) -> None:
    _broadcast(MessageType.AGENT_MESSAGE, thread_id=thread_id, content=content)


def _emit_tool_result(thread_id: str, tool_name: str, content: str) -> None:
    _broadcast(
        MessageType.TOOL_RESULT,
        thread_id=thread_id,
        tool_name=tool_name,
        content=content,
    )


def _emit_agent_completed(thread_id: str, content: str) -> None:
    _broadcast(MessageType.AGENT_COMPLETED, thread_id=thread_id, content=content)


def _emit_agent_error(thread_id: str, error: str) -> None:
    _broadcast(MessageType.AGENT_ERROR, thread_id=thread_id, error=error)


def _emit_prompt_loaded(prompt_name: str, prompt_content: str) -> None:
    _broadcast(
        MessageType.PROMPT_LOADED,
        prompt_name=prompt_name,
        prompt_content=prompt_content,
    )


async def _fetch_news_for_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """
    A2A 서버를 통해 종목 뉴스를 가져옵니다.
    
    Args:
        ticker: 종목 심볼 (예: "AAPL", "005930.KS")
    
    Returns:
        {"news": {...}} 또는 None (오류/비활성화 시)
    """
    if not news_a2a_client:
        print("📰 A2A News Client가 초기화되지 않았습니다 (뉴스 기능 비활성화)")
        return None
    
    try:
        print(f"📰 뉴스 조회 중: {ticker}")
        news_data = await news_a2a_client.fetch(ticker)
        
        if news_data and news_data.get("news"):
            summary = news_data["news"].get("summary", "")
            print(f"✅ 뉴스 조회 완료: {len(summary)} 글자")
            return news_data
        else:
            print(f"⚠️  뉴스 데이터가 비어있습니다: {ticker}")
            return None
            
    except Exception as e:
        print(f"❌ 뉴스 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


def _emit_approval_request(approval_request: Dict[str, Any]) -> None:
    """UI에 승인 요청을 전송하고 pending 맵을 관리."""
    request_id = approval_request["request_id"]
    thread_id = approval_request["thread_id"]

    # 동일 thread의 이전 요청이 남아있다면 정리 (중복 방지)
    for old_id, old_thread in list(pending_approvals.items()):
        if old_thread == thread_id:
            pending_approvals.pop(old_id, None)
            pending_request_payloads.pop(old_id, None)

    pending_approvals[request_id] = thread_id
    pending_request_payloads[request_id] = approval_request
    _broadcast(MessageType.APPROVAL_REQUEST, data=approval_request)


def _get_pending_request_for_thread(thread_id: str) -> tuple[str | None, Dict[str, Any] | None]:
    for req_id, tid in pending_approvals.items():
        if tid == thread_id:
            return req_id, pending_request_payloads.get(req_id)
    return None, None

def _process_agent_chunk(chunk: Dict[str, Any], thread_id: str) -> None:
    """
    Agent에서 흘러나온 chunk를 UI 이벤트로 변환한다.
    """
    messages = chunk.get("messages", [])
    if not messages:
        return

    last_msg = messages[-1]

    if isinstance(last_msg, AIMessage) and last_msg.content:
        _emit_agent_message(thread_id, last_msg.content)
        print(f"💬 Agent: {last_msg.content[:120]}...")
    elif isinstance(last_msg, ToolMessage):
        tool_name = getattr(last_msg, "name", "unknown")
        tool_content = last_msg.content[:500]
        _emit_tool_result(thread_id, tool_name, tool_content)
        print(f"🔧 Tool ({tool_name}): {tool_content[:120]}...")


# =============================================================================
# HITL (Human-in-the-Loop) TOOL
# =============================================================================
# 이 Tool은 LangGraph의 interrupt() 메커니즘을 사용하여 사람의 승인을 받습니다.
# 
# 동작 원리:
# 1. LLM이 이 tool을 호출 (매수/매도 결정 시)
# 2. interrupt()가 그래프 실행을 중단 (StateSnapshot 저장)
# 3. WebSocket으로 승인 요청을 UI에 전송
# 4. 사용자가 승인/거부 버튼 클릭
# 5. trading_api.py가 Command(resume=response)로 재개
# 6. interrupt()가 반환되고 이 함수가 계속 실행됨


@tool("request_human_approval")
def request_human_approval(ticker: str,
                           action: Literal["BUY", "SELL"],
                           reason: str,
                           market_data: str = "") -> str:
    """
    거래 실행 전 사람의 승인을 요청합니다.
    
    Args:
        ticker: 종목 심볼 (예: "AAPL")
        action: 거래 액션 ("BUY" 또는 "SELL")
        reason: 거래 근거 설명
        market_data: 추가 시장 데이터 (선택)
    
    Returns:
        JSON 문자열: {"approved": bool, "message": str, ...}
    
    주의:
        - 이 함수는 interrupt()로 인해 동기적으로 보이지만, 
          실제로는 그래프 실행이 중단되고 외부 입력을 기다립니다.
        - thread_id는 ContextVar에서 가져옵니다 (tool은 동기 함수라 매개변수로 받을 수 없음)
    """
    try:
        # 1. 입력 검증
        if action not in ("BUY", "SELL"):
            return _create_approval_response(
                approved=False,
                message="승인은 BUY/SELL 액션에만 필요합니다 (HOLD는 승인 불요)",
                error="Invalid action"
            )

        # 2. ContextVar에서 현재 실행 중인 thread_id 가져오기
        thread_id = active_thread_context.get()
        if not thread_id:
            raise RuntimeError("thread_id를 찾을 수 없습니다. ContextVar가 설정되지 않았습니다.")
        
        # 3. 이미 pending 상태인지 확인 (재실행 시 중복 방지)
        existing_request_id, existing_request = _get_pending_request_for_thread(thread_id)
        if existing_request_id and existing_request:
            request_id = existing_request_id
            approval_request = existing_request
            print(f"🔁 기존 승인 요청 재사용: {ticker} {action} (ID: {request_id})")
        else:
            # 4. 승인 요청 ID 생성 (고유 식별자)
            request_id = f"approval_{ticker}_{action}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # 5. 승인 요청 데이터 구성
            approval_request = {
                "request_id": request_id,
                "thread_id": thread_id,
                "ticker": ticker,
                "action": action,
                "reason": reason,
                "market_data": market_data,
                "timestamp": time.time(),
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }

            # 6. UI로 승인 요청 전송 (중복 방지 헬퍼 사용)
            _emit_approval_request(approval_request)
        
        print(f"🔔 승인 요청 생성: {ticker} {action} (ID: {request_id}, Thread: {thread_id})")

        # 7. ⚡ 핵심: LangGraph interrupt() 호출
        #    - 그래프 실행이 여기서 멈춤
        #    - StateSnapshot이 저장됨
        #    - Command(resume=...)로 재개될 때까지 대기
        #    - 재개 시 response에 사용자 응답이 담겨 반환됨
        response = interrupt(approval_request)

        # 8. 사용자 응답 처리 (interrupt가 재개되면 여기부터 실행)
        print(f"🔄 interrupt 재개됨 - 응답: {response}")
        
        # 9. Pending 매핑 정리 (완료 후 재사용 방지)
        #    ⚠️ 중요: 여기서 삭제해야 함! (trading_api.py에서 삭제하면 안 됨)
        #    이유: resume 시 tool이 재실행되므로, 기존 요청을 찾을 수 있도록
        #          interrupt 전까지는 유지하고, 응답 처리 후에만 삭제
        pending_approvals.pop(request_id, None)
        pending_request_payloads.pop(request_id, None)
        print(f"🧹 승인 요청 정리 완료: {request_id}")
        
        if isinstance(response, dict):
            if response.get("approved"):
                print(f"✅ 승인됨: {ticker} {action}")
                return _create_approval_response(
                    approved=True,
                    message="승인 완료",
                    request_id=request_id
                )
            else:
                print(f"❌ 거부됨: {ticker} {action}")
                return _create_approval_response(
                    approved=False,
                    message="거래가 거부되었습니다"
                )
        
        # 10. 잘못된 응답 형식
        pending_approvals.pop(request_id, None)
        pending_request_payloads.pop(request_id, None)
        return _create_approval_response(
            approved=False,
            message="잘못된 승인 응답 형식",
            error="Invalid response format"
        )

    except GraphInterrupt:
        # LangGraph의 GraphInterrupt 예외는 프레임워크가 처리하도록 다시 raise
        # 이 예외를 잡으면 interrupt/resume 메커니즘이 망가짐!
        # ⚠️ 주의: 여기서는 pending을 정리하면 안 됨! (재개 시 필요)
        raise
    except Exception as e:
        # 일반 예외 시에는 pending 정리 (재시도 불가능한 오류)
        thread_id = active_thread_context.get()
        if thread_id:
            # thread_id로 request_id 찾아서 정리
            for req_id, tid in list(pending_approvals.items()):
                if tid == thread_id:
                    pending_approvals.pop(req_id, None)
                    pending_request_payloads.pop(req_id, None)
        
        print(f"❌ 승인 요청 오류 (일반 예외): {e}")
        return _create_approval_response(
            approved=False,
            message="승인 요청 중 오류 발생",
            error=str(e)
        )


# =============================================================================
# AGENT INITIALIZATION
# =============================================================================


async def build_agent() -> tuple[MultiServerMCPClient, CompiledStateGraph]:
    """
    interrupt()로 중단된 Agent를 재개합니다.
    
    호출 시점:
        - WebSocket으로 사용자 승인/거부 응답을 받았을 때
        - trading_api.py의 websocket_endpoint에서 호출
    
    Args:
        thread_id: 재개할 Agent의 thread ID
        response: 사용자 응답 (예: {"approved": True, "request_id": "..."})
    
    동작 원리:
        1. Command(resume=response)로 재개 지시
        2. LangGraph는 저장된 StateSnapshot을 로드
        3. interrupt()가 response를 반환하며 tool 함수가 계속 실행
        4. Agent는 tool 결과를 받아 다음 단계 진행
    
    Returns:
        {"status": "completed"|"interrupted", "thread_id": str}
    """
    # 1. MCP Client 초기화 (STDIO Transport)
    PYTHON = os.environ.get("PYTHON_EXECUTABLE") or sys.executable
    
    client = MultiServerMCPClient({
        "trade": {
            "transport": "stdio",              # 표준 입출력으로 통신
            "command": PYTHON,                 # Python 인터프리터
            "args": [MCP_SERVER_PATH],         # 서버 스크립트 경로
        }
    })

    # 2. MCP Tools 가져오기
    #    - analyze_market_trend: 시장 분석
    #    - execute_trade: 거래 실행
    #    - health_check: 서버 상태 확인
    mcp_tools = await client.get_tools()
    print(f"📦 MCP Tools 로드 완료: {[t.name for t in mcp_tools]}")

    # 3. OpenAI API Key 확인
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    # 4. LLM 모델 생성
    model = ChatOpenAI(
        model="gpt-4.1-mini",  # 빠르고 저렴한 모델
        temperature=0          # 결정론적 응답 (일관성 향상)
    )
    
    # 5. Checkpointer 생성 (상태 저장소)
    #    - thread_id별로 Agent 상태를 메모리에 저장
    #    - interrupt/resume 시 필요
    memory = MemorySaver()
    
    # 6. ReAct Agent 그래프 생성
    #    - create_react_agent: LangGraph의 사전 정의된 그래프
    #    - ReAct (Reasoning + Acting) 패턴 구현
    #    - Tools: HITL tool + MCP tools
    agent = create_react_agent(
        model=model,
        tools=[request_human_approval] + mcp_tools,
        checkpointer=memory
    )

    # 7. A2A News Client 초기화 (선택사항)
    #    - A2A 서버가 실행 중이면 뉴스 기능 활성화
    #    - 실행되지 않았으면 기존 기능만 사용
    global agent_graph, mcp_client, news_a2a_client
    
    if A2A_AVAILABLE:
        a2a_url = os.getenv("A2A_SERVER_URL", f"http://localhost:{os.getenv('A2A_SERVER_PORT', '9999')}")
        try:
            news_a2a_client = NewsA2AClient(base_url=a2a_url)
            print(f"📰 A2A News Client 초기화 완료: {a2a_url}")
        except Exception as e:
            print(f"⚠️  A2A News Client 초기화 실패: {e}")
            news_a2a_client = None
    
    # 8. 전역 변수에 저장
    #    Python 규칙: 함수 내에서 전역 변수에 할당 시 `global` 선언 필수
    #    (읽기만 할 때는 불필요)
    #    용도: trading_api.py와 resume_agent_execution()에서 접근
    agent_graph = agent
    mcp_client = client
    agent_ready.set()  # 초기화 완료 시그널 (API 요청 대기 해제)
    
    print("✅ LangGraph Agent 초기화 완료")
    
    return client, agent


# =============================================================================
# AGENT EXECUTION & RESUME
# =============================================================================
# 
# LangGraph 표준 패턴 vs 우리 구현:
# ─────────────────────────────────────────────────────────────────────────
# LangGraph 공식 문서의 표준 패턴은 interrupt/resume을 단일 호출로 처리:
#   result = graph.invoke(input, config)  # interrupt까지 실행
#   result = graph.invoke(Command(resume=value), config)  # 바로 재개
#
# 우리 구현은 WebSocket 기반 비동기 웹 애플리케이션이므로 분리 필요:
#   1. run_trading_analysis(): 초기 실행 → interrupt 발생 시 HTTP 응답 반환
#   2. [사용자가 UI에서 승인/거부 버튼 클릭, WebSocket으로 별도 메시지 수신]
#   3. resume_agent_execution(): WebSocket 메시지로 재개
#
# 분리 이유:
#   - HTTP 요청과 WebSocket 메시지는 별도 연결
#   - 사용자 응답 시점 예측 불가 (수초~수분)
#   - FastAPI 엔드포인트는 즉시 응답 필요 (타임아웃 방지)
#
# 참고: https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/
# ─────────────────────────────────────────────────────────────────────────


async def run_trading_analysis(
    agent, 
    ticker: str = "NVDA", 
    thread_id: Optional[str] = None,
    prompt_style: str = "default"
):
    """
    거래 분석을 시작합니다 (초기 실행).
    
    호출 시점:
        - 사용자가 Web UI에서 종목을 선택하고 "분석 요청" 버튼 클릭
        - trading_api.py의 /api/trade 엔드포인트에서 호출
    
    Args:
        agent: LangGraph Agent 인스턴스
        ticker: 분석할 종목 심볼 (예: "AAPL", "NVDA")
        thread_id: Agent 실행 thread ID (없으면 자동 생성)
        prompt_style: 분석 스타일 ("default" | "neutral_analyst")
    
    동작 흐름:
        1. thread_id를 ContextVar에 설정 (tool에서 접근 가능하도록)
        2. prompt_style에 따라 MCP Prompt 로드 (또는 기본 프롬프트 사용)
        3. LLM에게 거래 분석 지시 프롬프트 전달
        4. Agent가 ReAct 루프 시작:
           - 시장 분석 (analyze_market_trend tool)
           - 의사결정 (BUY/SELL/HOLD)
           - 승인 요청 (request_human_approval tool) ← 여기서 interrupt
           - 거래 실행 (execute_trade tool)
        5. 중간 결과를 WebSocket으로 스트리밍
    
    Returns:
        {"status": "completed"|"interrupted", "thread_id": str, ...}
    """
    # 1. thread_id 준비
    if not thread_id:
        thread_id = f"trade_{ticker}_{int(time.time())}"
    
    # 2. ContextVar에 thread_id 설정
    #    - tool 함수는 동기 함수라 매개변수로 전달 불가
    #    - ContextVar로 async context 공유
    token = active_thread_context.set(thread_id)
    
    # 3. MCP Prompt 로드 (선택사항)
    mcp_prompt_messages = []
    if prompt_style == "neutral_analyst":
        try:
            print(f"📖 MCP Prompt '{prompt_style}' 로드 중...")
            
            # MultiServerMCPClient의 세션 생성
            session_ctx = mcp_client.session("trade")
            session = await session_ctx.__aenter__()
            
            try:
                # MCP 프로토콜: get_prompt(name)
                # 반환값: GetPromptResult { messages: List[PromptMessage], description: Optional[str] }
                prompt_result = await session.get_prompt("neutral_analyst")
                
                if prompt_result and prompt_result.messages:
                    # PromptMessage를 dict로 변환 (role, content)
                    print(f"📋 MCP Prompt 원본 구조:")
                    for i, msg in enumerate(prompt_result.messages):
                        # FastMCP는 문자열을 UserMessage로 변환
                        # messages는 PromptMessage 객체들의 리스트
                        content = msg.content.text if hasattr(msg.content, 'text') else str(msg.content)
                        print(f"   메시지 #{i+1}:")
                        print(f"     - role: {msg.role}")
                        print(f"     - content 타입: {type(msg.content)}")
                        print(f"     - content 길이: {len(content)}")
                        print(f"     - content 앞 100자: {content[:100]}")
                        
                        mcp_prompt_messages.append({
                            "role": msg.role,
                            "content": content
                        })
                    
                    print(f"✅ MCP Prompt 로드 완료: {len(mcp_prompt_messages)}개 메시지")
                    
                    # UI로 프롬프트 정보 전송
                    first_content = mcp_prompt_messages[0]["content"] if mcp_prompt_messages else ""
                    _emit_prompt_loaded("neutral_analyst", first_content)
                else:
                    print("⚠️  MCP Prompt 결과가 비어있습니다")
            finally:
                # 세션 정리
                await session_ctx.__aexit__(None, None, None)
                
        except Exception as e:
            print(f"⚠️  MCP Prompt 로드 실패 (기본 프롬프트 사용): {e}")
            import traceback
            traceback.print_exc()
    
    # 4. 뉴스 데이터 조회 (A2A)
    news_summary = ""
    news_data = await _fetch_news_for_ticker(ticker)
    if news_data and news_data.get("news"):
        news_summary = news_data["news"].get("summary", "")[:500]  # 최대 500자
        if news_summary:
            news_summary = f"\n\n📰 **최근 뉴스 요약:**\n{news_summary}\n"
    
    # 5. LLM 프롬프트 구성
    task_instruction = f"""
{ticker} 종목에 대해 거래 분석을 수행해주세요.
{news_summary}
다음 단계를 반드시 따라주세요:
1. analyze_market_trend 도구를 사용해서 {ticker}의 시장 동향을 분석하세요
2. 위의 뉴스 요약 (있는 경우)과 시장 데이터를 종합하여 BUY/SELL/HOLD 결정을 내리세요
3. BUY 또는 SELL 추천 시에는 request_human_approval 도구로 사용자 승인을 요청하세요
   (HOLD는 승인 불필요)
4. 승인을 받으면 execute_trade 도구로 거래를 실행하세요

모든 응답은 한국어로 해주세요.
""".strip()

    # 6. 최종 메시지 구성
    #    - MCP Prompt가 있으면 먼저 포함 (Agent 성격/역할 설정)
    #    - 그 다음 task_instruction 추가 (구체적 작업 지시)
    messages = []
    
    if mcp_prompt_messages:
        # MCP Prompt 메시지 추가
        print(f"\n🔧 LangChain 메시지 변환:")
        for msg in mcp_prompt_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Role에 따라 적절한 LangChain 메시지 타입 선택
            if role == "user":
                lc_msg = HumanMessage(content=content)
                print(f"   user → HumanMessage (길이: {len(content)})")
            elif role == "assistant":
                lc_msg = AIMessage(content=content)
                print(f"   assistant → AIMessage (길이: {len(content)})")
            else:  # system or unknown
                lc_msg = SystemMessage(content=content)
                print(f"   {role} → SystemMessage (길이: {len(content)})")
            
            messages.append(lc_msg)
    
    # Task instruction 추가
    messages.append(HumanMessage(content=task_instruction))
    
    # 7. LangGraph 실행 설정
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # ═════════════════════════════════════════════════════════════════
        # Agent 실행 시작 (astream으로 스트리밍)
        # ═════════════════════════════════════════════════════════════════
        result = None
        async for chunk in agent.astream(
            {"messages": messages}, 
            config
        ):
            result = chunk
            
            # Chunk 처리: 헬퍼 함수로 위임
            _process_agent_chunk(chunk, thread_id)
            
            # Interrupt 감지: request_human_approval이 interrupt() 호출
            if '__interrupt__' in chunk:
                print(f"⏸️  Interrupt 발생: {thread_id}")
                print(f"   → 사용자 승인 대기 중...")
                return {
                    "status": "interrupted", 
                    "thread_id": thread_id, 
                    "interrupt": chunk['__interrupt__']
                }
        
        # ═════════════════════════════════════════════════════════════════
        # 완료: 모든 chunk 소진 → Agent 실행 종료 (interrupt 없이 완료)
        # ═════════════════════════════════════════════════════════════════
        print("\n📋 거래 분석 완료:")
        
        # result 구조 디버깅
        if result:
            print(f"   result keys: {result.keys() if hasattr(result, 'keys') else type(result)}")
            print(f"   result 내용: {str(result)[:200]}")
        
        # Agent node에서 반환된 메시지 찾기
        final_content = None
        
        if result and 'messages' in result and result['messages']:
            final_msg = result['messages'][-1]
            final_content = getattr(final_msg, 'content', '')
            print(f"   [messages] 타입: {type(final_msg).__name__}, 내용: {final_content[:100] if final_content else '(비어있음)'}")
        
        # Agent node가 다른 형태로 반환할 수도 있음
        elif result and 'agent' in result and 'messages' in result['agent']:
            final_msg = result['agent']['messages'][-1]
            final_content = getattr(final_msg, 'content', '')
            print(f"   [agent.messages] 타입: {type(final_msg).__name__}, 내용: {final_content[:100] if final_content else '(비어있음)'}")
        
        if final_content:
            _emit_agent_completed(thread_id, final_content)
        else:
            print("   ⚠️  최종 메시지를 찾을 수 없습니다")
        
        return {"status": "completed", "result": result, "thread_id": thread_id}
        
    except Exception as e:
        print(f"❌ Agent 실행 오류: {e}")
        _emit_agent_error(thread_id, str(e))
        raise
    finally:
        # ContextVar 정리
        active_thread_context.reset(token)


async def resume_agent_execution(thread_id: str, response: Dict[str, Any]):
    """
    interrupt()로 중단된 Agent를 재개합니다.
    
    호출 시점:
        - WebSocket으로 사용자 승인/거부 응답을 받았을 때
        - trading_api.py의 websocket_endpoint에서 호출
    
    Args:
        thread_id: 재개할 Agent의 thread ID
        response: 사용자 응답 (예: {"approved": True, "request_id": "..."})
    
    동작 원리:
        1. Command(resume=response)로 재개 지시
        2. LangGraph는 저장된 StateSnapshot을 로드
        3. interrupt()가 response를 반환하며 tool 함수가 계속 실행
        4. Agent는 tool 결과를 받아 다음 단계 진행
    
    Returns:
        {"status": "completed"|"interrupted", "thread_id": str}
    """
    if not agent_graph:
        raise RuntimeError("Agent가 초기화되지 않았습니다")
    
    # ContextVar 설정 (tool 함수에서 thread_id 접근 가능하도록)
    token = active_thread_context.set(thread_id)
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        print(f"🔄 Agent 재개 시작: thread_id={thread_id}, response={response}")
        
        # Command(resume=...)로 Agent 재개
        # - interrupt()가 response를 반환
        # - Agent는 중단된 지점부터 계속 실행
        async for chunk in agent_graph.astream(Command(resume=response), config):
            # Chunk 처리: 헬퍼 함수로 위임
            _process_agent_chunk(chunk, thread_id)
            
            # 추가 interrupt 감지 (예: 연속된 여러 승인 요청)
            if '__interrupt__' in chunk:
                print(f"⏸️  추가 Interrupt 발생: {thread_id}")
                return {"status": "interrupted", "thread_id": thread_id}
        
        # ─────────────────────────────────────────────────────────────────
        # 완료: 모든 chunk 소진 → Agent 실행 종료
        # ─────────────────────────────────────────────────────────────────
        print(f"✅ Agent 재개 완료: thread_id={thread_id}")
        
        # MCP Resource 읽기: 거래 약관
        # BUY/SELL 승인 후 완료 시점에 약관을 읽어서 사용자에게 안내
        completion_message = "거래가 성공적으로 처리되었습니다."
        
        if response.get("approved"):  # 승인된 경우에만
            try:
                async with mcp_client.session("trade") as session:
                    # MCP Resource 읽기
                    resource_result = await session.read_resource("trade://terms-and-conditions")
                    if resource_result and resource_result.contents:
                        terms_text = resource_result.contents[0].text
                        # 약관 요약 (간단히 첫 3줄만)
                        terms_lines = [line for line in terms_text.split('\n') if line.strip()][:3]
                        terms_summary = '\n'.join(terms_lines)
                        completion_message += f"\n\n📋 거래 약관:\n{terms_summary}\n(상세 내용은 약관 전문 참조)"
            except Exception as e:
                print(f"⚠️  Resource 읽기 실패: {e}")
        
        _emit_agent_completed(thread_id, completion_message)
        
        return {"status": "completed", "thread_id": thread_id}
        
    except Exception as e:
        print(f"❌ Agent 재개 실패: {e}")
        _emit_agent_error(thread_id, str(e))
        raise
    finally:
        # ContextVar 정리
        active_thread_context.reset(token)

