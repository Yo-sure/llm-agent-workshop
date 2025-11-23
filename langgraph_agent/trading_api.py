#!/usr/bin/env python3
"""
Trading Bot FastAPI Application

═══════════════════════════════════════════════════════════════════════════════
API 구조
═══════════════════════════════════════════════════════════════════════════════

REST API:
  - GET  /                → Web UI 서빙
  - POST /api/trade       → 거래 분석 시작 (백그라운드 실행)
  - GET  /api/stocks      → 종목 리스트 조회 (MCP resource)

WebSocket:
  - /ws                   → 실시간 양방향 통신
    * Server → Client: Agent 메시지, Tool 결과, 승인 요청
    * Client → Server: 승인/거부 응답

Background Tasks:
  - lifespan.broadcast_loop: ui_message_queue 소비 → WebSocket 브로드캐스트
  - asyncio.create_task: Agent 실행 (HTTP 타임아웃 방지)

═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import time
import uuid
import asyncio
from queue import Empty as QueueEmpty
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# Agent 모듈에서 필요한 것들 import
from . import trading_agent
from .trading_agent import MessageType

# =============================================================================
# GLOBAL STATE
# =============================================================================

active_connections: Dict[str, WebSocket] = {}

BASE_DIR = Path(__file__).resolve().parent


# =============================================================================
# LIFESPAN & APP
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 애플리케이션 생명주기 관리.
    
    시작 시:
        - 백그라운드 브로드캐스트 루프 시작
        - trading_agent.ui_message_queue를 소비하여 WebSocket으로 전송
    
    종료 시:
        - 브로드캐스트 태스크 취소 및 정리
    """
    async def broadcast_loop():
        """
        ui_message_queue에서 메시지를 가져와 모든 WebSocket 연결에 브로드캐스트.
        
        동작:
            - queue.get_nowait()로 non-blocking 읽기
            - 메시지가 없으면 0.2초 대기
            - 메시지가 있으면 즉시 다음 메시지 확인 (지연 최소화)
        """
        while True:
            sent_any = False
            try:
                while True:
                    msg = trading_agent.ui_message_queue.get_nowait()
                    await broadcast_to_all_connections(msg)
                    sent_any = True
            except QueueEmpty:
                # 큐가 비었으면 잠시 대기 (CPU 사용률 감소)
                await asyncio.sleep(0.2 if not sent_any else 0)
            except Exception as e:
                # 브로드캐스트 실패 시 로깅 (루프는 계속)
                print(f"❌ 브로드캐스트 오류: {e}")
                await asyncio.sleep(0.2)

    # 백그라운드 태스크 시작
    app.state.broadcast_task = asyncio.create_task(broadcast_loop())
    
    try:
        yield  # FastAPI 애플리케이션 실행
    finally:
        # 종료 시 정리
        task = getattr(app.state, "broadcast_task", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Trading Bot HITL Interface",
    lifespan=lifespan,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def load_html_template() -> str:
    """UI 템플릿 파일 로드"""
    template_path = BASE_DIR / "ui_template.html"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>UI Template not found</h1>"


async def broadcast_to_all_connections(message: dict):
    """
    모든 활성 WebSocket 연결에 메시지 브로드캐스트.
    
    Args:
        message: 전송할 메시지 (dict, JSON으로 변환됨)
    
    동작:
        - 모든 연결에 병렬로 전송 시도
        - 실패한 연결은 disconnects 리스트에 추가
        - 전송 완료 후 끊어진 연결 정리
    """
    if not active_connections:
        return
    
    payload = json.dumps(message, ensure_ascii=False)
    disconnects = []
    
    for conn_id, ws in active_connections.items():
        try:
            await ws.send_text(payload)
        except Exception as e:
            print(f"❌ WS 전송 실패({conn_id}): {e}")
            disconnects.append(conn_id)
    
    # 끊어진 연결 정리
    for conn_id in disconnects:
        active_connections.pop(conn_id, None)


async def handle_approval_response(request_id: str, approved: bool):
    """
    WebSocket으로 수신한 승인/거부 응답 처리.
    
    Args:
        request_id: 승인 요청 ID
        approved: 승인 여부 (True=승인, False=거부)
    
    동작:
        1. request_id로 thread_id 조회
        2. 승인 처리 브로드캐스트
        3. Agent 재개 (백그라운드 태스크)
        4. 매핑 정리
    """
    print(f"✅ 승인 응답 수신: {request_id} - {'승인' if approved else '거부'}")
    
    # request_id로 thread_id 조회
    thread_id = trading_agent.pending_approvals.get(request_id)
    
    if not thread_id:
        print(f"⚠️  thread_id를 찾을 수 없음: {request_id}")
        return
    
    try:
        # 승인 처리 브로드캐스트
        await broadcast_to_all_connections({
            "type": "approval_processed",
            "request_id": request_id,
            "approved": approved,
            "status": "resuming"
        })
        
        # Agent 재개 (백그라운드 태스크)
        # 주의: FastAPI BackgroundTasks 대신 asyncio.create_task 사용
        #       이유: WebSocket 연결이 유지된 상태에서 비동기 실행 필요
        # 
        # ⚠️ 중요: pending_approvals는 여기서 삭제하지 않음!
        #    이유: resume 시 tool이 재실행되므로, 기존 요청을 찾을 수 있어야 중복 방지 가능
        #    삭제는 tool 함수 내에서 최종 응답 반환 직전에 수행
        response = {"approved": approved, "request_id": request_id}
        asyncio.create_task(
            trading_agent.resume_agent_execution(thread_id, response)
        )
        
    except Exception as e:
        print(f"❌ Agent 재개 실패: {e}")
        await broadcast_to_all_connections({
            "type": "approval_error",
            "request_id": request_id,
            "error": str(e)
        })


# =============================================================================
# REST API ROUTES
# =============================================================================


@app.get("/", response_class=HTMLResponse)
async def get_web_ui():
    """메인 웹 UI 페이지"""
    return load_html_template()


@app.post("/api/trade")
async def request_trade(request: Request):
    """
    거래 분석 요청 API.
    
    Request Body:
        {"ticker": "AAPL"}
    
    Response:
        {"status": "started", "ticker": "AAPL", "thread_id": "...", "message": "..."}
    
    동작:
        1. Agent 초기화 대기 (최대 20초)
        2. thread_id 생성
        3. 백그라운드 태스크로 Agent 실행
        4. 즉시 HTTP 응답 반환 (타임아웃 방지)
        5. Agent 진행 상황은 WebSocket으로 스트리밍
    
    주의:
        - asyncio.create_task 사용 (FastAPI BackgroundTasks 아님)
        - 이유: Agent가 interrupt()로 중단될 수 있어 장시간 실행 가능
        - HTTP 응답 후에도 태스크가 계속 실행되어야 함
    """
    try:
        # 요청 데이터 파싱
        data = await request.json()
        ticker = (data.get("ticker") or "").upper()
        prompt_style = data.get("prompt_style", "default")  # "default" | "neutral_analyst"

        # Agent 초기화 대기
        await asyncio.wait_for(trading_agent.agent_ready.wait(), timeout=20)
        
        # 입력 검증
        if not ticker:
            return {"status": "error", "error": "Ticker symbol is required"}

        if trading_agent.agent_graph is None:
            return {"status": "error", "error": "Agent not initialized"}

        print(f"\n🚀 API 거래 요청 수신: {ticker} (스타일: {prompt_style})")
        
        # Thread ID 생성 (고유 식별자)
        thread_id = f"trade_{ticker}_{int(time.time())}"
        
        # 백그라운드 태스크로 Agent 실행
        asyncio.create_task(
            trading_agent.run_trading_analysis(
                trading_agent.agent_graph,
                ticker,
                thread_id=thread_id,
                prompt_style=prompt_style
            )
        )
        
        return {
            "status": "started",
            "ticker": ticker,
            "thread_id": thread_id,
            "message": "거래 분석이 시작되었습니다. 승인 요청을 기다려주세요."
        }

    except asyncio.TimeoutError:
        return {"status": "error", "error": "Agent not initialized (timeout)"}
    except Exception as e:
        print(f"❌ API 거래 요청 실패: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/api/stocks")
async def get_stock_list():
    """
    주식 목록 조회 API (드롭다운용 정적 데이터).
    
    Response:
        {"stocks": [{"ticker": "AAPL", "name": "Apple Inc.", "category": "Technology"}, ...]}
    
    설계 결정:
        - UI 드롭다운용 데이터는 단순 정적 데이터이므로 API에서 직접 관리
        - MCP는 Agent가 사용할 도구/문서/프롬프트만 제공
        - 불필요한 추상화 제거 (stock_data.py 제거)
    """
    # 주식 데이터 (하드코딩 - 드롭다운용)
    # Tech giants
    tech_stocks = [
        {"ticker": "AAPL", "name": "Apple Inc.", "category": "Technology"},
        {"ticker": "MSFT", "name": "Microsoft Corporation", "category": "Technology"},
        {"ticker": "GOOGL", "name": "Alphabet Inc. (Class A)", "category": "Technology"},
        {"ticker": "GOOG", "name": "Alphabet Inc. (Class C)", "category": "Technology"},
        {"ticker": "AMZN", "name": "Amazon.com Inc.", "category": "Technology"},
        {"ticker": "META", "name": "Meta Platforms Inc.", "category": "Technology"},
        {"ticker": "TSLA", "name": "Tesla Inc.", "category": "Technology"},
        {"ticker": "NVDA", "name": "NVIDIA Corporation", "category": "Technology"},
        {"ticker": "NFLX", "name": "Netflix Inc.", "category": "Technology"},
        {"ticker": "ADBE", "name": "Adobe Inc.", "category": "Technology"},
    ]
    
    # Financial
    financial_stocks = [
        {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "category": "Financial"},
        {"ticker": "BAC", "name": "Bank of America Corp.", "category": "Financial"},
        {"ticker": "WFC", "name": "Wells Fargo & Company", "category": "Financial"},
        {"ticker": "GS", "name": "Goldman Sachs Group Inc.", "category": "Financial"},
        {"ticker": "MS", "name": "Morgan Stanley", "category": "Financial"},
        {"ticker": "C", "name": "Citigroup Inc.", "category": "Financial"},
        {"ticker": "AXP", "name": "American Express Company", "category": "Financial"},
        {"ticker": "BLK", "name": "BlackRock Inc.", "category": "Financial"},
        {"ticker": "SCHW", "name": "Charles Schwab Corporation", "category": "Financial"},
        {"ticker": "USB", "name": "U.S. Bancorp", "category": "Financial"},
    ]
    
    # Healthcare
    healthcare_stocks = [
        {"ticker": "JNJ", "name": "Johnson & Johnson", "category": "Healthcare"},
        {"ticker": "PFE", "name": "Pfizer Inc.", "category": "Healthcare"},
        {"ticker": "UNH", "name": "UnitedHealth Group Inc.", "category": "Healthcare"},
        {"ticker": "ABBV", "name": "AbbVie Inc.", "category": "Healthcare"},
        {"ticker": "TMO", "name": "Thermo Fisher Scientific Inc.", "category": "Healthcare"},
        {"ticker": "DHR", "name": "Danaher Corporation", "category": "Healthcare"},
        {"ticker": "BMY", "name": "Bristol Myers Squibb Company", "category": "Healthcare"},
        {"ticker": "MRK", "name": "Merck & Co. Inc.", "category": "Healthcare"},
        {"ticker": "CVS", "name": "CVS Health Corporation", "category": "Healthcare"},
        {"ticker": "GILD", "name": "Gilead Sciences Inc.", "category": "Healthcare"},
    ]
    
    # Consumer
    consumer_stocks = [
        {"ticker": "KO", "name": "Coca-Cola Company", "category": "Consumer"},
        {"ticker": "PEP", "name": "PepsiCo Inc.", "category": "Consumer"},
        {"ticker": "WMT", "name": "Walmart Inc.", "category": "Consumer"},
        {"ticker": "HD", "name": "Home Depot Inc.", "category": "Consumer"},
        {"ticker": "MCD", "name": "McDonald's Corporation", "category": "Consumer"},
        {"ticker": "NKE", "name": "Nike Inc.", "category": "Consumer"},
        {"ticker": "SBUX", "name": "Starbucks Corporation", "category": "Consumer"},
        {"ticker": "TGT", "name": "Target Corporation", "category": "Consumer"},
        {"ticker": "LOW", "name": "Lowe's Companies Inc.", "category": "Consumer"},
        {"ticker": "COST", "name": "Costco Wholesale Corporation", "category": "Consumer"},
    ]
    
    # Industrial
    industrial_stocks = [
        {"ticker": "BA", "name": "Boeing Company", "category": "Industrial"},
        {"ticker": "CAT", "name": "Caterpillar Inc.", "category": "Industrial"},
        {"ticker": "GE", "name": "General Electric Company", "category": "Industrial"},
        {"ticker": "MMM", "name": "3M Company", "category": "Industrial"},
        {"ticker": "HON", "name": "Honeywell International Inc.", "category": "Industrial"},
        {"ticker": "UPS", "name": "United Parcel Service Inc.", "category": "Industrial"},
        {"ticker": "FDX", "name": "FedEx Corporation", "category": "Industrial"},
        {"ticker": "LMT", "name": "Lockheed Martin Corporation", "category": "Industrial"},
        {"ticker": "RTX", "name": "RTX Corporation", "category": "Industrial"},
        {"ticker": "NOC", "name": "Northrop Grumman Corporation", "category": "Industrial"},
    ]
    
    # Energy
    energy_stocks = [
        {"ticker": "XOM", "name": "Exxon Mobil Corporation", "category": "Energy"},
        {"ticker": "CVX", "name": "Chevron Corporation", "category": "Energy"},
        {"ticker": "COP", "name": "ConocoPhillips", "category": "Energy"},
        {"ticker": "SLB", "name": "Schlumberger Limited", "category": "Energy"},
        {"ticker": "EOG", "name": "EOG Resources Inc.", "category": "Energy"},
        {"ticker": "PXD", "name": "Pioneer Natural Resources Company", "category": "Energy"},
        {"ticker": "KMI", "name": "Kinder Morgan Inc.", "category": "Energy"},
        {"ticker": "OXY", "name": "Occidental Petroleum Corporation", "category": "Energy"},
        {"ticker": "VLO", "name": "Valero Energy Corporation", "category": "Energy"},
        {"ticker": "PSX", "name": "Phillips 66", "category": "Energy"},
    ]
    
    # Korean stocks
    korean_stocks = [
        {"ticker": "005930.KS", "name": "Samsung Electronics Co., Ltd.", "category": "Korean Tech"},
        {"ticker": "018260.KS", "name": "Samsung SDS Co., Ltd.", "category": "Korean Tech"},
        {"ticker": "000660.KS", "name": "SK Hynix Inc.", "category": "Korean Tech"},
        {"ticker": "035420.KS", "name": "NAVER Corporation", "category": "Korean Tech"},
        {"ticker": "207940.KS", "name": "Samsung Biologics Co., Ltd.", "category": "Korean Healthcare"},
        {"ticker": "051910.KS", "name": "LG Chem Ltd.", "category": "Korean Industrial"},
    ]
    
    all_stocks = tech_stocks + financial_stocks + healthcare_stocks + consumer_stocks + industrial_stocks + energy_stocks + korean_stocks
    
    return {"stocks": all_stocks}


# =============================================================================
# WEBSOCKET
# =============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 연결 처리 (양방향 실시간 통신).
    
    Server → Client 메시지 타입:
        - agent_message: AI 응답/사고 과정
        - tool_result: Tool 실행 결과
        - agent_completed: Agent 실행 완료
        - agent_error: Agent 실행 오류
        - approval_request: 승인 요청
        - approval_processed: 승인 처리 완료
        - ping: 연결 유지
    
    Client → Server 메시지 타입:
        - approval_response: 승인/거부 응답
    
    동작:
        1. 연결 수락 및 등록
        2. 환영 메시지 전송
        3. 메시지 수신 루프 (2초 타임아웃)
        4. 승인 응답 처리
        5. 20초마다 ping 전송 (연결 유지)
        6. 연결 종료 시 정리
    """
    # 연결 ID 생성 및 등록
    conn_id = uuid.uuid4().hex[:8]
    await websocket.accept()
    active_connections[conn_id] = websocket
    print(f"🌐 웹소켓 연결: {conn_id}")

    try:
        # 환영 메시지
        await websocket.send_text(json.dumps({
            "type": "system",
            "message": "connected"
        }))
        
        last_ping = time.time()
        
        # 메시지 수신 루프
        while True:
            try:
                # 2초 타임아웃으로 메시지 수신 (비차단)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
                msg = json.loads(data)
                
                # 승인/거부 응답 처리
                if msg.get("type") == "approval_response":
                    request_id = msg.get("request_id")
                    approved = bool(msg.get("approved"))
                    await handle_approval_response(request_id, approved)
                    
            except asyncio.TimeoutError:
                # 타임아웃: ping 전송 (연결 유지)
                if time.time() - last_ping > 20:
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "t": time.time()
                    }))
                    last_ping = time.time()
                continue
                
    except WebSocketDisconnect:
        print(f"🔌 웹소켓 종료: {conn_id}")
    except Exception as e:
        print(f"❌ WebSocket 오류({conn_id}): {e}")
    finally:
        # 연결 정리
        active_connections.pop(conn_id, None)

