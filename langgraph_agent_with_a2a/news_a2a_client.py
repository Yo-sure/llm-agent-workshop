#!/usr/bin/env python3
"""
A2A 뉴스 서버와 통신하여 뉴스 데이터를 조회하는 클라이언트

사용법:
    # 모듈로 사용
    from news_a2a_client import NewsA2AClient
    client = NewsA2AClient("http://localhost:9999")
    news = asyncio.run(client.fetch("018260.KS"))

    # CLI로 실행
    python news_a2a_client.py --url http://localhost:9999 --ticker 018260.KS
"""

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx
from a2a.client.client import ClientConfig
from a2a.client.client_factory import ClientFactory
from a2a.client.middleware import ClientCallContext
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Message,
    Part,
    DataPart,
    TransportProtocol,
    Role,
)

__all__ = ["NewsA2AClient"]


class NewsA2AClient:
    """A2A 뉴스 서버와 통신하는 간단한 클라이언트"""

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---------------------------
    # Internal helpers
    # ---------------------------

    def _build_bootstrap_card(self) -> AgentCard:
        """서버 카드 조회용 부트스트랩 카드 생성 (-32007 방지 설정 포함)"""
        return AgentCard(
            url=self.base_url,
            preferred_transport=TransportProtocol.jsonrpc,
            additional_interfaces=[],
            supports_authenticated_extended_card=False,  # 확장 카드 요구 안함
            capabilities=AgentCapabilities(streaming=False),
            default_input_modes=["json"],
            default_output_modes=["json", "text"],
            description="bootstrap card for server discovery",
            skills=[
                AgentSkill(
                    id="news.research",
                    name="News Research",
                    description="",
                    tags=["news", "research"],
                )
            ],
            version="0.0.0",
            name="bootstrap",
        )

    @staticmethod
    def _build_request_message(ticker: str) -> Message:
        """뉴스 조회 요청 메시지 생성"""
        payload = {
            "type": "news_research_request",
            "ticker": ticker,
            "lang": "ko-KR",
            "country": "KR",
        }
        return Message(
            role=Role.user,
            parts=[Part(root=DataPart(data=payload))],
            message_id=str(uuid4()),
        )

    @staticmethod
    def _extract_news_from_message(msg: Message) -> Optional[dict]:
        """메시지에서 뉴스 데이터 추출"""
        if not hasattr(msg, "parts") or not msg.parts:
            return None

        for p in msg.parts:
            root = getattr(p, "root", None)
            data = None

            if isinstance(root, DataPart):
                data = root.data
            elif isinstance(root, dict):
                data = root.get("data")
            elif hasattr(root, "data"):
                data = getattr(root, "data")

            if isinstance(data, dict) and "news" in data:
                return data["news"]

        return None

    # ---------------------------
    # Public API
    # ---------------------------

    async def fetch(self, ticker: str) -> Dict[str, Any]:
        """
        A2A 서버에서 뉴스 데이터를 조회한다.

        Args:
            ticker: 조회할 티커 (예: 018260.KS)

        Returns:
            {"news": {...}} 또는 {} (뉴스가 없거나 파싱 실패 시)
        """
        async with httpx.AsyncClient(timeout=self.timeout) as http_client:
            config = ClientConfig(
                streaming=False,
                polling=False,
                httpx_client=http_client,
                supported_transports=[TransportProtocol.jsonrpc],
                accepted_output_modes=["json", "text"],
                use_client_preference=True,
            )
            factory = ClientFactory(config=config)

            # 1) 부트스트랩 카드로 임시 클라이언트 생성
            bootstrap_card = self._build_bootstrap_card()
            tmp_client = factory.create(bootstrap_card)

            # 2) 서버의 실제 카드 조회
            real_card = await tmp_client.get_card()

            # 3) 실제 클라이언트로 요청 전송
            client = factory.create(real_card)
            req_msg = self._build_request_message(ticker)
            ctx = ClientCallContext()

            # 4) 응답 스트림에서 뉴스 데이터 추출
            result_news = None
            async for event in client.send_message(req_msg, context=ctx):
                if isinstance(event, tuple):  # task, update 이벤트는 무시
                    continue
                news = self._extract_news_from_message(event)
                if news:
                    result_news = news
                    break

            return {"news": result_news} if result_news else {}


# (선택) 모듈 내부에서 환경변수 기본 허용
def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
    base_url = f"http://127.0.0.1:{os.getenv('A2A_SERVER_PORT','9999')}"
    self.base_url = base_url.rstrip("/")
    self.timeout = timeout
