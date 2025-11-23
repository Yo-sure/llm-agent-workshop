#!/usr/bin/env python3
"""
Trading MCP Server - Educational Demo for LangGraph + MCP Integration

===============================================================================
MCP Components (Tools, Resources, Prompts)
===============================================================================

🔧 TOOLS (3 patterns demonstrated):
  1. analyze_market_trend(ticker)
     → Pattern: Detailed docstring (LLM sees the entire docstring)
     
  2. execute_trade(ticker, action, reason)
     → Pattern: description= parameter (LLM sees only description, not docstring)
     
  3. health_check()
     → Pattern: Short tool with tags (categorization)

📄 RESOURCES (Agent knowledge base):
  - trade://terms-and-conditions (약관 - Agent가 거래 후 읽음)

🎭 PROMPTS (Agent personality):
  - neutral_analyst (중립적 분석가 - 보수적 관망 스타일)

===============================================================================
Tool Description Best Practices
===============================================================================

FastMCP automatically exposes tools to LLMs with:
  - Name: Function name or @mcp.tool(name="...")
  - Description: Docstring OR description= parameter
  - Schema: Auto-generated from type hints

Key Points:
  1. **Docstring = LLM sees it**: Write clear, actionable descriptions
  2. **description= parameter**: Overrides docstring (use for separation of concerns)
  3. **When to use which**:
     - Docstring: Simple tools, documentation = tool description
     - description=: Complex tools, need detailed internal docs separate from LLM prompt

===============================================================================
Transport: STDIO (no port usage)
===============================================================================
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
# Utils
# -----------------------------------------------------------------------------
def validate_ticker(ticker: str) -> tuple[bool, str]:
    """
    티커 심볼 검증 (간단한 형식 검사만).
    
    주의:
        - 실제 종목 DB 확인은 하지 않음 (UI에서 이미 검증됨)
        - 형식만 간단히 확인 (정규식)
    """
    if not ticker:
        return False, "티커 심볼이 비어있습니다"

    ticker = ticker.strip().upper()
    if not re.match(r"^[A-Z0-9.-]+$", ticker):
        return False, f"잘못된 티커 형식: {ticker}"

    # 최대 10자 ('.KS', '.KQ' 같은 접미사 포함)
    if len(ticker) > 10:
        return False, f"티커가 너무 깁니다: {ticker}"

    return True, ""

# -----------------------------------------------------------------------------
# Resources (Agent가 참고할 문서/데이터)
# -----------------------------------------------------------------------------

@mcp.resource("trade://terms-and-conditions")
def get_terms_and_conditions():
    """
    거래 약관 및 면책 사항 (MCP Resource 표준 사례).
    
    Agent가 거래 실행 후 이 약관을 읽고 사용자에게 안내하도록 설계됨.
    """
    terms = """
# 📋 거래 약관 및 면책 사항

## 1. 서비스 성격
본 거래 시스템은 **데모/교육 목적**으로 제공됩니다.
- 실제 금융 거래가 아닙니다.
- 실제 자금이 이동하지 않습니다.
- 모든 거래는 시뮬레이션입니다.

## 2. 투자 책임
- 모든 투자 결정의 책임은 본인에게 있습니다.
- 과거 수익률이 미래 수익을 보장하지 않습니다.
- AI 추천은 참고 자료일 뿐, 투자 권유가 아닙니다.

## 3. 리스크 고지
- 주식 투자는 원금 손실 위험이 있습니다.
- 변동성이 큰 종목은 큰 손실을 초래할 수 있습니다.
- 분산 투자를 권장합니다.

## 4. 데이터 정확성
- 제공되는 시장 데이터는 실시간이 아닐 수 있습니다.
- 기술적 지표는 참고용이며, 절대적이지 않습니다.

## 5. 문의
본 시스템은 LangGraph + MCP 학습용 예제입니다.
실제 투자 상담은 금융 전문가와 상의하시기 바랍니다.

---
_마지막 업데이트: 2025-01-01_
"""
    return terms


# -----------------------------------------------------------------------------
# Prompts (Agent 역할/성격 설정)
# -----------------------------------------------------------------------------

@mcp.prompt("neutral_analyst")
def neutral_analyst_prompt():
    """
    무조건 HOLD 프롬프트 (MCP Prompt 표준 사례).
    
    이 프롬프트를 사용하면 어떤 상황에서도 거래를 권장하지 않고
    항상 HOLD(관망)를 추천합니다.
    """
    return """당신은 극도로 보수적인 주식 분석 전문가입니다.

## 핵심 원칙
- **무조건 HOLD**: 어떤 상황에서도 매수/매도를 권장하지 않습니다.
- **거래 반대**: 시장이 아무리 좋아 보여도 거래는 위험하다고 판단합니다.
- **관망 유지**: 모든 분석 결과는 "현재는 관망하는 것이 최선"으로 결론 내립니다.

## 분석 방식
1. analyze_market_trend 도구로 시장 데이터를 분석합니다
2. 데이터와 무관하게 항상 다음과 같이 결론을 내립니다:
   - **추천: HOLD (관망)**
   - 이유: "시장 불확실성이 높아 현재는 거래하지 않는 것이 안전합니다"

## 답변 스타일
- "시장 데이터를 분석한 결과, 현재는 관망을 권장합니다"
- "불확실한 시장 상황에서는 거래를 자제하는 것이 최선입니다"
- "추가 확인이 필요하므로 HOLD를 유지하시기 바랍니다"

## 중요
- **절대로 BUY나 SELL을 추천하지 마세요**
- **request_human_approval 도구를 호출하지 마세요** (HOLD는 승인 불필요)
- 분석 완료 후 간단히 HOLD 추천 이유를 설명하고 종료하세요
"""



# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------
@mcp.tool()
def analyze_market_trend(ticker: str) -> str:
    """
    Analyzes the market trend for a given stock ticker symbol.
    
    Use this tool to get comprehensive market analysis including:
    - Current and previous price information with percentage changes
    - Trading volume compared to historical average
    - Technical indicators (RSI, MACD) with interpretations
    - Trend direction, strength, and trading recommendation (BUY/SELL/HOLD)
    
    When to use:
    - Before making any trading decision
    - When user asks about a stock's current market status
    - To gather data for informed investment recommendations
    
    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "NVDA", "TSLA", "005930.KS")
    
    Returns:
        JSON string containing market analysis data with price, volume, 
        technical indicators, and recommendation.
    
    Note: This is a DEMO tool using simulated data for educational purposes.
    """
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

@mcp.tool(
    description=(
        "Executes a trade (BUY/SELL/HOLD) for the specified stock ticker. "
        "IMPORTANT: Only call this AFTER receiving explicit user approval via 'request_human_approval' tool. "
        "Always provide a clear 'reason' explaining why this trade is being executed. "
        "Returns execution details including price, shares, and total amount. "
        "Note: This is a DEMO tool with simulated execution for educational purposes."
    )
)
def execute_trade(
    ticker: str,
    action: Literal["BUY", "SELL", "HOLD"],
    reason: str
) -> str:
    """
    [INTERNAL IMPLEMENTATION DOCS - NOT SHOWN TO LLM]
    
    거래 실행 함수 (시뮬레이션).
    
    실제 구현:
        - BUY/SELL: 랜덤 가격/수량으로 체결 시뮬레이션
        - HOLD: 거래 없음 표시
        - 모든 경우 JSON 형태로 결과 반환
    
    주의:
        - 이 docstring은 LLM이 보지 못함
        - LLM은 위의 description 파라미터만 봄
        - FastMCP의 description 파라미터가 docstring보다 우선순위가 높음
    """
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

@mcp.tool(
    name="health_check",
    description="Checks if the trading MCP server is healthy and responsive. Use this to verify server connectivity before making trades."
)
def health_check() -> str:
    """
    [INTERNAL] 서버 헬스 체크 함수.
    
    이 tool은 간단한 패턴의 예시:
        - 매개변수 없음 (항상 같은 결과)
        - 빠른 응답
        - description= 파라미터로 명확한 설명 제공
        
    LLM은 위의 description만 보고, 이 긴 docstring은 개발자용.
    """
    return json.dumps({
        "status": "healthy",
        "server": "Trading MCP Server (Demo)",
        "version": "1.0.0",
        "timestamp": time.time(),
        "tools_available": ["analyze_market_trend", "execute_trade", "health_check"],
        "message": "✅ Server is running normally"
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