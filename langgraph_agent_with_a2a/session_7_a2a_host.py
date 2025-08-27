#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph HITL을 사용한 트레이딩 봇 (Human-in-the-Loop)

핵심 기능:
- interrupt_before=["approval"]로 approval 노드 진입 직전에 실행 중단
- /api/trade가 GraphInterrupt를 잡아 승인카드 브로드캐스트하고 결정 대기
- approval_node는 부작용과 중복 브로드캐스트 방지를 위해 NOP

아키텍처:
- Agent A: 시장 분석 및 뉴스 수집
- Agent B: 승인 후 거래 실행
- Agent F: HOLD 또는 거부된 거래의 마무리 처리
- MCP 통합으로 시장 데이터 및 거래 실행
- 실시간 UI 통신을 위한 WebSocket
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional, TypedDict

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from langchain_core.globals import set_debug

from langchain_core.messages import AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from pydantic import BaseModel, Field, conlist, confloat, field_validator
from typing_extensions import Annotated

# 외부 모듈
from news_a2a_client import NewsA2AClient
from langchain_mcp_adapters.client import MultiServerMCPClient

set_debug(True)
# ==================== 설정 및 로깅 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("hitl")

BASE_DIR = Path(__file__).resolve().parent
MCP_SERVER_PATH = str(BASE_DIR / "session_7_mcp_server.py")

A2A_SERVER_PORT = int(os.getenv("A2A_SERVER_PORT", "9999"))
A2A_BASE_URL = os.getenv("A2A_BASE_URL", f"http://127.0.0.1:{A2A_SERVER_PORT}")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# ==================== FastAPI 애플리케이션 ====================
app = FastAPI(title="Trading Bot HITL",
              version="2.1",
              description="HITL without streaming (interrupt_before=approval)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


def load_html_template() -> str:
    """웹 UI용 HTML 템플릿을 로드합니다.

    Returns:
        str: HTML 템플릿 내용 또는 찾을 수 없는 경우 오류 페이지
    """
    template_path = BASE_DIR / "ui_template.html"
    try:
        return template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        log.error("UI template not found")
        return "<html><body><h1>UI Template not found</h1></body></html>"


@app.get("/", response_class=HTMLResponse)
async def get_web_ui():
    return load_html_template()


# ==================== 전역 상태 ====================
agent_ready = asyncio.Event()
compiled_graph = None  # type: ignore
global_mcp_client: Optional[MultiServerMCPClient] = None

agent_a = None  # type: ignore
agent_b = None  # type: ignore
agent_f = None  # type: ignore

news_client = NewsA2AClient(A2A_BASE_URL)

pending_approvals: Dict[str, Dict[str, Any]] = {}
completed_approvals: Dict[str, Dict[str, Any]] = {}
active_connections: Dict[str, WebSocket] = {}

execution_stats = {
    "total_requests": 0, "successful": 0, "failed": 0,
    "approved": 0, "rejected": 0, "timeouts": 0
}


# ==================== 스키마 및 상태 ====================
class Preliminary(BaseModel):
    """예비 거래 결정 스키마"""
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: confloat(ge=0.0, le=1.0)
    reason: str

    @field_validator("reason")
    @classmethod
    def _min_len(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Reason must be at least 10 characters")
        return v


class FinalDecision(BaseModel):
    """검증이 포함된 최종 거래 결정 스키마"""
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: confloat(ge=0.0, le=1.0)
    reason: str
    used: conlist(str, min_length=1)

    @field_validator("used")
    @classmethod
    def _whitelist(cls, v: list[str]) -> list[str]:
        valid = {"market_trend", "news", "technical_analysis", "sentiment"}
        for src in v:
            if src not in valid:
                raise ValueError(f"Invalid source: {src}")
        return v


class FinalizeInput(BaseModel):
    """마무리 도구의 입력 스키마"""
    ticker: str
    preliminary: Preliminary
    news_summary: Optional[str] = None
    final: FinalDecision


class NewsDelegateInput(BaseModel):
    """뉴스 위임의 입력 스키마"""
    ticker: str = Field(..., description="주식 티커 심볼 (예: AAPL 또는 018260.KS)")


class TraderState(TypedDict, total=False):
    """트레이딩 워크플로우의 상태 스키마"""
    thread_id: str
    ticker: str
    prelim: dict
    news: dict
    final: dict
    approval: dict
    trade: dict
    finalized: dict
    messages: Annotated[list[AnyMessage], add_messages]
    start_time: float
    end_time: float


# ==================== 유틸리티 함수 ====================
def _json_dict(x: Any) -> Optional[dict]:
    """입력값을 가능하면 dict로 변환합니다.

    Args:
        x: 변환할 입력값

    Returns:
        dict or None: 파싱된 dict 또는 변환 실패시 None
    """
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return None
    return None


def find_tool_result(messages: list[AnyMessage], tool_name: str) -> Optional[dict]:
    """메시지 기록에서 이름으로 가장 최근 도구 결과를 찾습니다.

    Args:
        messages: 검색할 메시지 목록
        tool_name: 찾을 도구 이름

    Returns:
        dict or None: 도구 결과 내용 또는 찾을 수 없는 경우 None
    """
    for m in reversed(messages or []):
        if isinstance(m, ToolMessage) and m.name == tool_name:
            return _json_dict(m.content)
    return None


async def broadcast(message: Dict[str, Any]):
    """모든 활성 WebSocket 연결에 메시지를 브로드캐스트합니다.

    Args:
        message: 연결된 모든 클라이언트에 브로드캐스트할 메시지
    """
    if not active_connections:
        return
    payload = json.dumps(message, ensure_ascii=False)
    drop = []
    for cid, ws in list(active_connections.items()):
        try:
            await ws.send_text(payload)
        except Exception:
            drop.append(cid)
    for cid in drop:
        active_connections.pop(cid, None)


def broadcast_sync(message: Dict[str, Any]):
    """브로드캐스트 함수의 동기 래퍼입니다.

    Args:
        message: 브로드캐스트할 메시지
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast(message))
    except RuntimeError:
        pass


# ==================== 도구 ====================
@tool("fetch_news_delegate", args_schema=NewsDelegateInput)
async def fetch_news_delegate(ticker: str) -> Dict[str, Any]:
    """A2A 뉴스 서버에서 티커의 뉴스를 가져옵니다.

    Args:
        ticker: 주식 티커 심볼

    Returns:
        dict: 뉴스 데이터 또는 오류 정보
    """
    log.info(f"[news] fetching: {ticker}")
    try:
        data = await news_client.fetch(ticker)
        await broadcast({
            "type": "stage", "name": "news", "status": "done",
            "ticker": ticker, "has_news": bool((data or {}).get("news")),
            "timestamp": time.time()
        })
        return data or {}
    except Exception as e:
        await broadcast({
            "type": "stage", "name": "news", "status": "error",
            "ticker": ticker, "error": str(e), "timestamp": time.time()
        })
        return {"error": str(e)}


@tool("finalize_and_notify", args_schema=FinalizeInput)
def finalize_and_notify(ticker: str, preliminary: Preliminary,
                        news_summary: Optional[str], final: FinalDecision) -> Dict[str, Any]:
    """최종 분석 결과를 반환하고 UI에 완료를 알립니다.

    Args:
        ticker: 주식 티커 심볼
        preliminary: 예비 분석 결과
        news_summary: 관련 뉴스 요약
        final: 최종 거래 결정

    Returns:
        dict: 포맷된 최종 분석 결과
    """
    result = {
        "ticker": ticker,
        "preliminary": preliminary.model_dump(),
        "news_summary": (news_summary or "")[:4000],
        "final": final.model_dump(),
        "generated_at": datetime.now().isoformat(),
        "confidence_score": final.confidence,
        "recommendation": final.action,
        "analysis_sources": final.used,
    }
    broadcast_sync({
        "type": "stage", "name": "final", "status": "done",
        "ticker": ticker, "final_decision": final.action,
        "confidence": final.confidence, "timestamp": time.time()
    })
    return result


# ==================== 그래프 노드 ====================
async def agent_a_node(state: TraderState) -> dict:
    """에이전트 A: 시장 분석 및 뉴스 수집

    시장 트렌드 분석과 선택적 뉴스 수집을 수행한 후
    예비 거래 결정을 생성합니다.

    Args:
        state: 현재 트레이더 상태

    Returns:
        dict: 분석 결과로 업데이트된 상태
    """
    ticker = state["ticker"]
    cfg = {"configurable": {"thread_id": f'{state["thread_id"]}#A'}}
    result = await agent_a.ainvoke(
        {"messages": [HumanMessage(content=f"대상 티커는 {ticker} 이다. 필요한 도구만 호출하라.")]},
        cfg
    )

    messages = result.get("messages", [])
    prelim = find_tool_result(messages, "analyze_market_trend") or {}
    news = find_tool_result(messages, "fetch_news_delegate") or {}

    final = {"action": "HOLD", "confidence": 0.6, "reason": "Neutral", "used": ["market_trend"]}
    trend = (prelim.get("trend_analysis") or {})
    rec = str(trend.get("recommendation", "")).upper()
    if rec in {"BUY", "SELL", "HOLD"}:
        final["action"] = rec
        final["confidence"] = 0.7
        final["reason"] = f"Market trend: {trend.get('direction', 'neutral')}"
    if news.get("news"):
        if "news" not in final["used"]:
            final["used"].append("news")

    await broadcast({
        "type": "stage", "name": "prelim", "status": "done",
        "ticker": ticker, "final": final, "timestamp": time.time()
    })
    log.info(f"[agent_a] ticker={ticker} final.action={final['action']} conf={final['confidence']}")
    return {"messages": messages, "prelim": prelim, "news": news, "final": final}


async def approval_node(state: TraderState) -> dict:
    """승인 노드 (NOP - No Operation)

    interrupt_before=["approval"]로 인해 이 노드에 도달하기 전에
    실행이 중단되므로 이 노드는 실행되지 않습니다. 승인 로직은
    /api/trade 엔드포인트에서 처리됩니다.

    Args:
        state: 현재 트레이더 상태

    Returns:
        dict: 빈 딕셔너리 (상태 변경 없음)
    """
    # 승인 결과는 라우팅 후 /api/trade가 Command(resume=...)를 통해 주입
    log.info(f"[approval_node] entered with keys={list(state.keys())}")
    return {}


async def agent_b_node(state: TraderState) -> dict:
    """에이전트 B: 승인 후 거래 실행

    승인된 거래를 실행하고 거래 프로세스를 마무리합니다.

    Args:
        state: 승인 결정이 포함된 현재 트레이더 상태

    Returns:
        dict: 거래 실행 결과로 업데이트된 상태
    """
    ticker = state["ticker"]
    cfg = {"configurable": {"thread_id": f'{state["thread_id"]}#B'}}
    input_data = {
        "ticker": ticker,
        "preliminary": state.get("prelim", {}),
        "news_summary": json.dumps(state.get("news", {}).get("news", {}), ensure_ascii=False)[:2000] if state.get(
            "news") else "",
        "final": state.get("final", {}),
    }
    res = await agent_b.ainvoke({"messages": [HumanMessage(content=json.dumps(input_data, ensure_ascii=False))]}, cfg)
    msgs = res.get("messages", [])
    trade = find_tool_result(msgs, "execute_trade") or {}
    finalized = find_tool_result(msgs, "finalize_and_notify") or {}

    # 거래 실행 결과 브로드캐스트
    if trade:
        broadcast_sync({
            "type": "trade",
            "status": "executed",
            "ticker": ticker,
            "order": trade,
            "timestamp": time.time(),
        })
    else:
        log.warning("[agent_b] execute_trade did not return a result; no trade payload")

    return {"messages": msgs, "trade": trade, "finalized": finalized}


async def finalizer_node(state: TraderState) -> dict:
    """HOLD 결정 또는 거부된 거래를 위한 마무리 노드

    실행이 필요하지 않은 거래(HOLD) 또는 사용자가 거부한
    거래에 대한 문서화 및 마무리를 처리합니다.

    Args:
        state: 현재 트레이더 상태

    Returns:
        dict: 마무리 결과로 업데이트된 상태
    """
    ticker = state["ticker"]
    cfg = {"configurable": {"thread_id": f'{state["thread_id"]}#F'}}
    input_data = {
        "ticker": ticker,
        "preliminary": state.get("prelim", {}),
        "news_summary": json.dumps(state.get("news", {}).get("news", {}), ensure_ascii=False)[:2000] if state.get(
            "news") else "",
        "final": state.get("final", {}),
    }
    res = await agent_f.ainvoke({"messages": [HumanMessage(content=json.dumps(input_data, ensure_ascii=False))]}, cfg)
    msgs = res.get("messages", [])
    finalized = find_tool_result(msgs, "finalize_and_notify") or {}
    return {"messages": msgs, "finalized": finalized}


def route_after_a_or_approval(state: TraderState) -> Literal["approval", "agent_b", "finalizer"]:
    """에이전트 A 또는 승인 후 라우팅 결정

    최종 결정 액션과 승인 상태를 기반으로 다음 노드를 결정합니다.

    Args:
        state: 현재 트레이더 상태

    Returns:
        str: 다음 노드 이름 ("approval", "agent_b", 또는 "finalizer")
    """
    action = str(state.get("final", {}).get("action", "")).upper()
    approved = state.get("approval", {}).get("approved")
    if action in {"BUY", "SELL"} and approved is None:
        return "approval"
    if action in {"BUY", "SELL"} and approved is True:
        return "agent_b"
    return "finalizer"


# ==================== 그래프 구성 ====================
async def build_agents_and_graph():
    """에이전트를 빌드하고 트레이딩 워크플로우 그래프를 컴파일합니다.

    MCP 클라이언트, 에이전트를 생성하고 인터럽트 설정으로
    상태 그래프를 컴파일합니다.

    Returns:
        tuple: (MultiServerMCPClient, 컴파일된 그래프)

    Raises:
        RuntimeError: 필수 환경 변수나 도구가 누락된 경우
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    PY = os.environ.get("PYTHON_EXECUTABLE", sys.executable)
    mcp = MultiServerMCPClient({
        "trade": {"transport": "stdio", "command": PY, "args": [MCP_SERVER_PATH], "env": os.environ.copy()}
    })
    tools = await mcp.get_tools()

    def pick(name: str):
        return next((t for t in tools if getattr(t, "name", "") == name), None)

    analyze_market_trend = pick("analyze_market_trend")
    execute_trade = pick("execute_trade")
    if not analyze_market_trend or not execute_trade:
        raise RuntimeError("MCP tools missing: analyze_market_trend, execute_trade")

    memory = MemorySaver()
    model = ChatOpenAI(model=OPENAI_MODEL, temperature=0)

    global agent_a, agent_b, agent_f
    # 에이전트 프롬프트
    AGENT_A_PROMPT = (
        "분석 에이전트 A (TOOLS-ONLY)\n"
        "- 자연어 출력 절대 금지. 도구 호출만 수행하라.\n"
        "- 입력으로 단일 티커가 주어진다. 티커 문자열을 그대로 사용한다(대소문자/공백 보정만).\n"
        "- 아래 순서를 지켜라:\n"
        "  1) analyze_market_trend(ticker) 를 반드시 정확히 1회 호출한다.\n"
        "  2) 필요 시 fetch_news_delegate(ticker) 를 최대 1회 호출한다.\n"
        "- 도구의 반환을 요약/재서술하지 말고 추가 출력 없이 종료한다.\n"
    )

    AGENT_B_PROMPT = (
        "트레이더 에이전트 B (STRICT TOOL ORDER)\n"
        "- 자연어 출력 절대 금지. 반드시 도구만 호출한다.\n"
        "- 입력으로 다음 키를 가진 단일 JSON 메시지가 주어진다: "
        "ticker, preliminary, news_summary, final (final.action ∈ {BUY, SELL}).\n"
        "- 정확히 아래 순서로 '두 번'만 호출하고 종료하라:\n"
        "  1) execute_trade(...)\n"
        "     - tool 스키마에 맞춰 인자를 구성한다(가능한 값은 입력 JSON에서 추출).\n"
        "     - 시뮬레이션 텍스트를 출력하거나 거래를 텍스트로 보고하지 말라. 반드시 도구를 호출하라.\n"
        "     - 이 호출은 정확히 1회만 수행한다.\n"
        "  2) finalize_and_notify(ticker, preliminary, news_summary, final)\n"
        "     - 위 입력 JSON의 동일한 값을 전달한다(가공/의역 금지).\n"
        "- 다른 도구 호출 금지, 순서 변경 금지, 중복 호출 금지.\n"
        "- 어떤 경우에도 텍스트를 출력하지 말고, 도구 두 번 호출 후 종료한다.\n"
    )

    AGENT_F_PROMPT = (
        "파이널라이저 에이전트 F (SINGLE TOOL)\n"
        "- 자연어 출력 절대 금지. finalize_and_notify 만 1회 호출하고 종료하라.\n"
        "- 인자: ticker, preliminary, news_summary, final 을 입력 JSON에서 그대로 전달한다.\n"
        "- 다른 도구 호출 금지, 추가 출력 금지.\n"
    )

    # 에이전트 생성
    agent_a = create_react_agent(
        model=model,
        tools=[analyze_market_trend, fetch_news_delegate],
        prompt=AGENT_A_PROMPT,
        checkpointer=memory,
    )

    agent_b = create_react_agent(
        model=model,
        tools=[execute_trade, finalize_and_notify],
        prompt=AGENT_B_PROMPT,
        checkpointer=memory,
    )

    agent_f = create_react_agent(
        model=model,
        tools=[finalize_and_notify],
        prompt=AGENT_F_PROMPT,
        checkpointer=memory,
    )

    builder = StateGraph(TraderState)
    builder.add_node("agent_a", agent_a_node)
    builder.add_node("approval", approval_node)
    builder.add_node("agent_b", agent_b_node)
    builder.add_node("finalizer", finalizer_node)

    builder.add_edge(START, "agent_a")
    builder.add_conditional_edges("agent_a", route_after_a_or_approval,
                                  {"approval": "approval", "agent_b": "agent_b", "finalizer": "finalizer"})
    builder.add_conditional_edges("approval", route_after_a_or_approval,
                                  {"agent_b": "agent_b", "finalizer": "finalizer"})
    builder.add_edge("agent_b", END)
    builder.add_edge("finalizer", END)

    log.info("compiling graph with interrupt_before=['approval']")
    graph = builder.compile(checkpointer=memory, interrupt_before=["approval"])
    log.info("graph compiled")
    return mcp, graph


# ==================== API 엔드포인트 ====================
@app.get("/api/health")
async def health():
    """헬스 체크 엔드포인트

    Returns:
        dict: 시스템 헬스 상태 및 통계
    """
    return {
        "status": "ok",
        "agent_ready": agent_ready.is_set(),
        "active_connections": len(active_connections),
        "pending_approvals": len(pending_approvals),
        "stats": execution_stats
    }


@app.get("/api/stocks-by-mcp")
async def get_stock_list():
    """MCP 서버에서 사용 가능한 주식 목록을 가져옵니다.

    Returns:
        dict: 사용 가능한 주식 목록 또는 폴백 데이터
    """
    try:
        await asyncio.wait_for(agent_ready.wait(), timeout=10)
        if not global_mcp_client:
            raise RuntimeError("MCP client not initialized")
        blobs = await global_mcp_client.get_resources("trade", uris="trade://stocks")
        data = json.loads(blobs[0].as_string()) if blobs else {}
        stocks = [{
            "ticker": s.get("ticker") or s.get("symbol") or "",
            "name": s.get("name") or "",
            "category": s.get("category") or "EQUITY"
        } for s in data.get("stocks", [])]
        if not stocks:
            raise RuntimeError("Empty `stocks` list from MCP")
        return {"stocks": stocks}
    except Exception as e:
        log.warning(f"[stocks-by-mcp] fallback: {e}")
        return {
            "stocks": [
                {"ticker": "AAPL", "name": "Apple Inc.", "category": "TECH"},
                {"ticker": "MSFT", "name": "Microsoft Corp.", "category": "TECH"},
                {"ticker": "NVDA", "name": "NVIDIA Corp.", "category": "TECH"},
                {"ticker": "GOOGL", "name": "Alphabet Inc. (Class A)", "category": "TECH"},
                {"ticker": "AMZN", "name": "Amazon.com Inc.", "category": "CONSUMER"},
                {"ticker": "TSLA", "name": "Tesla Inc.", "category": "AUTO"},
                {"ticker": "META", "name": "Meta Platforms", "category": "TECH"},
                {"ticker": "NFLX", "name": "Netflix Inc.", "category": "MEDIA"},
            ],
            "error": str(e),
        }


@app.post("/api/trade")
async def request_trade(request: Request):
    """휴먼 인 더 루프 승인이 포함된 메인 트레이딩 엔드포인트

    BUY/SELL 결정에 대한 승인 인터럽트와 함께 트레이딩 워크플로우를
    실행합니다. GraphInterrupt 예외를 처리하고 승인 워크플로우를 관리합니다.

    Args:
        request: 티커 정보가 포함된 FastAPI 요청

    Returns:
        dict: 트레이딩 결과 또는 오류 정보
    """
    body = await request.json()
    ticker = (body.get("ticker") or "").upper().strip()
    log.info(f"[api/trade] start ticker={ticker}")
    if not ticker:
        return {"status": "error", "error": "Ticker is required"}

    await asyncio.wait_for(agent_ready.wait(), timeout=20)
    if compiled_graph is None:
        return {"status": "error", "error": "Graph not initialized"}

    execution_stats["total_requests"] += 1
    thread_id = f"trade_{ticker}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    cfg = {"configurable": {"thread_id": thread_id}}
    state: TraderState = {
        "thread_id": thread_id,
        "ticker": ticker,
        "messages": [],
        "start_time": time.time(),
    }

    async def wait_for_approval_and_resume(req_id: str, card: dict):
        """승인 워크플로우 처리: 브로드캐스트 → 대기 → 주입 → 재개

        Args:
            req_id: 추적을 위한 고유 요청 ID
            card: 브로드캐스트할 승인 카드 데이터

        Returns:
            Command: 승인 결정이 포함된 재개 명령
        """
        pending_approvals[req_id] = card
        await broadcast({"type": "approval_request", "data": card})
        log.info(f"[api/trade] approval broadcast: {req_id}")

        decision = None
        start = time.time()
        timeout = 300.0
        while req_id not in completed_approvals:
            if time.time() - start > timeout:
                decision = {
                    "approved": False,
                    "notes": "Timeout - auto rejected",
                    "timestamp": time.time(),
                }
                pending_approvals.pop(req_id, None)
                execution_stats["timeouts"] += 1
                log.info(f"[api/trade] approval timeout: {req_id}")
                break
            await asyncio.sleep(0.4)

        if decision is None:
            decision = completed_approvals.pop(req_id, {"approved": False})

        if decision.get("approved"):
            execution_stats["approved"] += 1
        else:
            execution_stats["rejected"] += 1

        # 승인 결과를 승인 노드 컨텍스트에 주입
        try:
            compiled_graph.update_state(
                cfg,
                {
                    "approval": {
                        "approved": bool(decision.get("approved")),
                        "notes": decision.get("notes", ""),
                        "timestamp": decision.get("timestamp", time.time()),
                    }
                },
                as_node="approval",
            )
            log.info("[api/trade] update_state(as_node='approval') OK")
        except Exception as e:
            log.warning(f"[api/trade] update_state failed: {e}")

        # 그래프 실행 재개
        return Command(resume=decision)

    # 무한 루프 방지를 위한 안전 가드
    ticks, max_ticks = 0, 20

    while True:
        ticks += 1
        if ticks > max_ticks:
            log.error("[api/trade] exceeded max ticks")
            return {"status": "error", "error": "Internal loop guard triggered"}

        try:
            out = await compiled_graph.ainvoke(state, cfg)

            # 폴백 경로: 인터럽트가 발생하지 않았을 때 승인 필요 여부 확인
            final_after = (out.get("final") or {})
            approval_after = (out.get("approval") or {})
            action_after = str(final_after.get("action", "")).upper()
            needs_approval = action_after in {"BUY", "SELL"} and ("approved" not in approval_after)

            log.info(
                f"[api/trade] after invoke: action={action_after} "
                f"approved={approval_after.get('approved')} needs_approval={needs_approval}"
            )

            if needs_approval:
                req_id = f"approval_{ticker}_{action_after}_{uuid.uuid4().hex[:6]}"
                card = {
                    "request_id": req_id,
                    "ticker": ticker,
                    "action": action_after,
                    "reason": final_after.get("reason", ""),
                    "confidence": final_after.get("confidence", 0),
                    "timestamp": time.time(),
                    "status": "pending",
                }
                state = await wait_for_approval_and_resume(req_id, card)
                continue  # 승인 결과 적용 후 계속

            # 정상 완료 경로: 여기서 반드시 반환해야 함
            out["end_time"] = time.time()
            execution_stats["successful"] += 1

            finalized = out.get("finalized")
            trade = out.get("trade", {})
            if finalized:
                payload = {**finalized}
                if trade:
                    payload["trade"] = trade
                return {"status": "success", "ticker": ticker, "response": payload}

            final_decision = out.get("final", {})
            approval = out.get("approval", {})
            msg = "No trade executed - " + (
                "HOLD recommendation"
                if str(final_decision.get("action", "")).upper() == "HOLD"
                else ("Trade rejected by user" if approval.get("approved") is False else "")
            )
            return {
                "status": "success",
                "ticker": ticker,
                "response": {
                    "ticker": ticker,
                    "preliminary": out.get("prelim", {}),
                    "final": final_decision,
                    "approval": approval,
                    "generated_at": datetime.now().isoformat(),
                    "message": msg,
                },
            }

        except GraphInterrupt as gi:
            # interrupt_before=["approval"] 경로: 승인 카드 표시 후 재개
            payload = {}
            v = getattr(gi, "value", None)
            if isinstance(v, tuple) and v and hasattr(v[0], "value") and isinstance(v[0].value, dict):
                payload = v[0].value

            req_id = payload.get("request_id") or f"approval_{ticker}_{uuid.uuid4().hex[:6]}"

            # 승인 카드를 위해 스냅샷에서 액션/이유/신뢰도 가져오기 (우아한 실패)
            action_for_card, reason_for_card, conf_for_card = "", "", 0
            try:
                snap = compiled_graph.get_state(cfg)  # StateSnapshot
                values = getattr(snap, "values", {}) or {}
                final_now = values.get("final", {}) or {}
                action_for_card = str(final_now.get("action", "")).upper()
                reason_for_card = final_now.get("reason", "")
                conf_for_card = final_now.get("confidence", 0)
            except Exception:
                pass

            card = {
                "request_id": req_id,
                "ticker": ticker,
                "action": action_for_card,
                "reason": reason_for_card,
                "confidence": conf_for_card,
                "timestamp": time.time(),
                "status": "pending",
            }
            state = await wait_for_approval_and_resume(req_id, card)
            continue  # 승인 결과 적용 후 계속

        except Exception as e:
            execution_stats["failed"] += 1
            log.exception("trade error")
            log.exception(f"[api/trade] error ticker={ticker}: {e}")
            return {"status": "error", "error": str(e)}


# ==================== WebSocket 핸들러 ====================
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """실시간 통신을 위한 WebSocket 엔드포인트

    클라이언트 연결 및 승인 응답을 처리합니다.

    Args:
        ws: WebSocket 연결
    """
    cid = uuid.uuid4().hex[:8]
    log.info(f"[ws] connected: {cid}")
    await ws.accept()
    active_connections[cid] = ws
    try:
        await ws.send_text(json.dumps({"type": "system", "message": "Connected", "connection_id": cid}))
        while True:
            data = json.loads(await ws.receive_text())
            if data.get("type") == "approval_response":
                req_id = data["request_id"]
                result = {
                    "approved": bool(data["approved"]),
                    "notes": data.get("notes", ""),
                    "timestamp": data.get("timestamp", time.time()),
                }
                log.info(f"[ws] approval_response req_id={req_id} approved={result['approved']}")
                completed_approvals[req_id] = result
                pending_approvals.pop(req_id, None)
                await broadcast({"type": "approval_processed", "request_id": req_id, **result})
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.pop(cid, None)


# ==================== 부트스트랩 및 메인 ====================
async def main():
    """메인 애플리케이션 진입점

    에이전트, 그래프를 초기화하고 FastAPI 서버를 시작합니다.
    """
    log.info("bootstrapping...")
    try:
        mcp, graph = await build_agents_and_graph()
    except Exception:
        log.exception("build failed")
        raise

    global compiled_graph, global_mcp_client
    compiled_graph = graph
    global_mcp_client = mcp

    agent_ready.set()
    log.info("ready.")

    # 컨테이너 및 로컬 배포 모두 호환
    port = int(os.getenv("PORT", "8080"))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
