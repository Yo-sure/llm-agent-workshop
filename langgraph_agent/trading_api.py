#!/usr/bin/env python3
"""
Trading Bot FastAPI Application

- Web UI 서빙
- REST API (/api/trade, /api/stocks)
- WebSocket (/ws)
"""

import os
import json
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# Agent 모듈에서 필요한 것들 import
from . import trading_agent

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
    """브로드캐스트 루프 시작/종료"""
    async def broadcast_loop():
        while True:
            sent_any = False
            try:
                while True:
                    msg = trading_agent.broadcast_queue.get_nowait()
                    await broadcast_to_all_connections(msg)
                    sent_any = True
            except Exception:
                await asyncio.sleep(0.2 if not sent_any else 0)

    app.state.broadcast_task = asyncio.create_task(broadcast_loop())
    try:
        yield
    finally:
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
# ROUTES
# =============================================================================


def load_html_template() -> str:
    """UI 템플릿 로드"""
    template_path = BASE_DIR / "ui_template.html"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>UI Template not found</h1>"


@app.get("/", response_class=HTMLResponse)
async def get_web_ui():
    """메인 웹 UI"""
    return load_html_template()


@app.post("/api/trade")
async def request_trade(request: Request):
    """거래 분석 요청 API"""
    try:
        data = await request.json()
        ticker = (data.get("ticker") or "").upper()

        await asyncio.wait_for(trading_agent.agent_ready.wait(), timeout=20)
        if not ticker:
            return {"status": "error", "error": "Ticker symbol is required"}

        if trading_agent.global_agent is None:
            return {"status": "error", "error": "Agent not initialized"}

        print(f"\n🚀 API 거래 요청 수신: {ticker}")
        response = await trading_agent.run_trading_demo(trading_agent.global_agent, ticker)
        tail = response['messages'][-1].content if response else "응답 없음"
        return {
            "status": "success",
            "ticker": ticker,
            "message": "거래 분석 완료",
            "response": tail
        }

    except asyncio.TimeoutError:
        return {"status": "error", "error": "Agent not initialized (timeout)"}
    except Exception as e:
        print(f"❌ API 거래 요청 실패: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/api/stocks")
async def get_stock_list():
    """주식 목록 조회 API"""
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
    """WebSocket 연결 처리"""
    conn_id = uuid.uuid4().hex[:8]
    await websocket.accept()
    active_connections[conn_id] = websocket
    print(f"🌐 웹소켓 연결: {conn_id}")

    try:
        await websocket.send_text(
            json.dumps({
                "type": "system",
                "message": "connected"
            }))
        last_ping = time.time()
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
                msg = json.loads(data)
                if msg.get("type") == "approval_response":
                    result = await trading_agent.handle_approval_response(msg)
                    if result:
                        await broadcast_to_all_connections(result)
            except asyncio.TimeoutError:
                if time.time() - last_ping > 20:
                    await websocket.send_text(
                        json.dumps({
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
        active_connections.pop(conn_id, None)


async def broadcast_to_all_connections(message: dict):
    """모든 WebSocket 연결에 메시지 브로드캐스트"""
    if not active_connections:
        return
    payload = json.dumps(message, ensure_ascii=False)
    disconnects = []
    for cid, ws in active_connections.items():
        try:
            await ws.send_text(payload)
        except Exception as e:
            print(f"❌ WS 전송 실패({cid}): {e}")
            disconnects.append(cid)
    for cid in disconnects:
        active_connections.pop(cid, None)

