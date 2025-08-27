#!/usr/bin/env python3
"""
Trading MCP Server (clean, STDIO-default)

- Tools:
  - analyze_market_trend(ticker)
  - execute_trade(ticker, action, reason)
  - health_check()

- Default: STDIO (포트 사용 안 함)
"""

import json
import logging
import re
import time
from random import uniform
from typing import Literal

from mcp.server.fastmcp import FastMCP

# -----------------------------------------------------------------------------
# Logging (stderr)
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,  # 필요하면 DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]  # stderr
)
logger = logging.getLogger("mcp-trade-server")

# -----------------------------------------------------------------------------
# FastMCP 서버 인스턴스 (host/port는 SSE/HTTP에서만 사용)
# -----------------------------------------------------------------------------
mcp = FastMCP(
    name="trade",
)

# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------
STOCK_DATABASE = {
    # Tech giants
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc. (Class A)",
    "GOOG": "Alphabet Inc. (Class C)",
    "AMZN": "Amazon.com Inc.",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "NVDA": "NVIDIA Corporation",
    "NFLX": "Netflix Inc.",
    "ADBE": "Adobe Inc.",

    # Financial
    "JPM": "JPMorgan Chase & Co.",
    "BAC": "Bank of America Corp.",
    "WFC": "Wells Fargo & Company",
    "GS": "Goldman Sachs Group Inc.",
    "MS": "Morgan Stanley",
    "C": "Citigroup Inc.",
    "AXP": "American Express Company",
    "BLK": "BlackRock Inc.",
    "SCHW": "Charles Schwab Corporation",
    "USB": "U.S. Bancorp",

    # Healthcare
    "JNJ": "Johnson & Johnson",
    "PFE": "Pfizer Inc.",
    "UNH": "UnitedHealth Group Inc.",
    "ABBV": "AbbVie Inc.",
    "TMO": "Thermo Fisher Scientific Inc.",
    "DHR": "Danaher Corporation",
    "BMY": "Bristol Myers Squibb Company",
    "MRK": "Merck & Co. Inc.",
    "CVS": "CVS Health Corporation",
    "GILD": "Gilead Sciences Inc.",

    # Consumer
    "KO": "Coca-Cola Company",
    "PEP": "PepsiCo Inc.",
    "WMT": "Walmart Inc.",
    "HD": "Home Depot Inc.",
    "MCD": "McDonald's Corporation",
    "NKE": "Nike Inc.",
    "SBUX": "Starbucks Corporation",
    "TGT": "Target Corporation",
    "LOW": "Lowe's Companies Inc.",
    "COST": "Costco Wholesale Corporation",

    # Industrial
    "BA": "Boeing Company",
    "CAT": "Caterpillar Inc.",
    "GE": "General Electric Company",
    "MMM": "3M Company",
    "HON": "Honeywell International Inc.",
    "UPS": "United Parcel Service Inc.",
    "FDX": "FedEx Corporation",
    "LMT": "Lockheed Martin Corporation",
    "RTX": "RTX Corporation",
    "NOC": "Northrop Grumman Corporation",

    # Energy
    "XOM": "Exxon Mobil Corporation",
    "CVX": "Chevron Corporation",
    "COP": "ConocoPhillips",
    "SLB": "Schlumberger Limited",
    "EOG": "EOG Resources Inc.",
    "PXD": "Pioneer Natural Resources Company",
    "KMI": "Kinder Morgan Inc.",
    "OXY": "Occidental Petroleum Corporation",
    "VLO": "Valero Energy Corporation",
    "PSX": "Phillips 66",

    # Korean stocks
    "005930.KS": "Samsung Electronics Co., Ltd.",
    "018260.KS": "Samsung SDS Co., Ltd.",
    "000660.KS": "SK Hynix Inc.",
    "035420.KS": "NAVER Corporation",
    "207940.KS": "Samsung Biologics Co., Ltd.",
    "051910.KS": "LG Chem Ltd."
}
VALID_TICKERS = set(STOCK_DATABASE.keys())

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def validate_ticker(ticker: str) -> tuple[bool, str]:
    if not ticker:
        return False, "티커 심볼이 비어있습니다"

    ticker = ticker.strip().upper()
    if not re.match(r"^[A-Z0-9.-]+$", ticker):
        return False, f"잘못된 티커 형식: {ticker}"

    # 최대 6자 ('.KS' 같은 접미사는 예외적으로 허용)
    core = ticker.replace(".KS", "").replace(".", "")
    if len(core) > 6:
        return False, f"티커가 너무 깁니다: {ticker}"

    if ticker not in VALID_TICKERS:
        return False, f"알 수 없는 티커: {ticker}. 지원되는 주요 종목을 사용해주세요 (예: AAPL, NVDA, MSFT)"
    return True, ""

# -----------------------------------------------------------------------------
# Resource
# -----------------------------------------------------------------------------
@mcp.resource("trade://stocks")
def get_all_stocks():
    """모든 종목 리스트를 반환하는 리소스"""
    stocks = []
    for ticker, name in STOCK_DATABASE.items():
        if ticker in ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "NVDA", "NFLX", "ADBE"]:
            category = "Technology"
        elif ticker in ["JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SCHW", "USB"]:
            category = "Financial"
        elif ticker in ["JNJ", "PFE", "UNH", "ABBV", "TMO", "DHR", "BMY", "MRK", "CVS", "GILD"]:
            category = "Healthcare"
        elif ticker in ["KO", "PEP", "WMT", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "COST"]:
            category = "Consumer"
        elif ticker in ["BA", "CAT", "GE", "MMM", "HON", "UPS", "FDX", "LMT", "RTX", "NOC"]:
            category = "Industrial"
        elif ticker in ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "KMI", "OXY", "VLO", "PSX"]:
            category = "Energy"
        else:
            category = "Korean Tech" if ticker.endswith(".KS") else "Other"

        stocks.append({"ticker": ticker, "name": name, "category": category})

    return {"stocks": stocks}



# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------
@mcp.tool()
def analyze_market_trend(ticker: str) -> str:
    """주어진 종목의 시장 동향을 모사 데이터로 분석."""
    try:
        ok, err = validate_ticker(ticker)
        if not ok:
            return json.dumps({
                "ticker": ticker,
                "error": err,
                "valid_examples": ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA"],
                "timestamp": time.time()
            }, ensure_ascii=False)

        ticker = ticker.strip().upper()

        base_price = round(uniform(50, 400), 2)
        pct = round(uniform(-8, 8), 2)
        prev = base_price
        curr = round(base_price * (1 + pct / 100), 2)
        diff = round(curr - prev, 2)

        volume = int(uniform(1_000_000, 10_000_000))
        avg_volume = int(uniform(800_000, 1_200_000))

        rsi = round(uniform(20, 80), 1)
        macd = round(uniform(-2, 2), 3)

        if pct > 3:
            trend, strength, rec = "강한 상승", "매우 강함", "BUY"
        elif pct > 1:
            trend, strength, rec = "상승", "보통", "BUY"
        elif pct < -3:
            trend, strength, rec = "강한 하락", "매우 강함", "SELL"
        elif pct < -1:
            trend, strength, rec = "하락", "보통", "SELL"
        else:
            trend, strength, rec = "횡보", "중립", "HOLD"

        result = {
            "ticker": ticker,
            "timestamp": time.time(),
            "price_data": {
                "current_price": curr,
                "previous_price": prev,
                "price_change": diff,
                "price_change_percent": pct
            },
            "volume_data": {
                "current_volume": volume,
                "average_volume": avg_volume,
                "volume_ratio": round(volume / avg_volume, 2)
            },
            "technical_indicators": {
                "rsi": rsi,
                "macd": macd,
                "rsi_signal": "과매수" if rsi > 70 else "과매도" if rsi < 30 else "중립",
                "macd_signal": "상승" if macd > 0 else "하락"
            },
            "trend_analysis": {
                "direction": trend,
                "strength": strength,
                "recommendation": rec
            },
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "ticker": ticker,
            "error": f"시장 분석 중 오류 발생: {str(e)}",
            "timestamp": time.time()
        }, ensure_ascii=False)

@mcp.tool()
def execute_trade(
    ticker: str,
    action: Literal["BUY", "SELL", "HOLD"],
    reason: str
) -> str:
    """거래 실행(모사)."""
    try:
        if action == "BUY":
            result = "매수 주문 체결 완료"
            price = round(uniform(140, 180), 2)
            shares = int(uniform(10, 100))
            amount = round(price * shares, 2)
        elif action == "SELL":
            result = "매도 주문 체결 완료"
            price = round(uniform(140, 180), 2)
            shares = int(uniform(10, 100))
            amount = round(price * shares, 2)
        else:  # HOLD
            result = "포지션 유지 (거래 없음)"
            price = None
            shares = 0
            amount = 0

        payload = {
            "ticker": ticker,
            "action": action,
            "reason": reason,
            "execution_details": {
                "result": result,
                "execution_price": price,
                "shares": shares,
                "total_amount": amount,
                "execution_time": time.time()
            },
            "status": "COMPLETED",
            "message": f"{ticker} {action} 거래가 성공적으로 처리되었습니다."
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "ticker": ticker,
            "action": action,
            "status": "FAILED",
            "error": f"거래 실행 중 오류 발생: {str(e)}",
            "timestamp": time.time()
        }, ensure_ascii=False)

@mcp.tool()
def health_check() -> str:
    """헬스 체크."""
    return json.dumps({
        "status": "healthy",
        "server": "trading-mcp-server",
        "timestamp": time.time(),
        "tools_available": ["analyze_market_trend", "execute_trade", "health_check"]
    }, ensure_ascii=False)

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    logger.info("🔌 Starting Trading MCP Server in STDIO mode")
    logger.info("🔗 Ready for LangGraph via STDIO (no port usage)")
    mcp.run(transport="stdio")