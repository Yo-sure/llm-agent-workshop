import json
import logging
import os
from datetime import datetime, timezone

import httpx
import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, Part, DataPart
from a2a.utils import new_agent_parts_message, get_data_parts, get_text_parts
from typing_extensions import override

log = logging.getLogger("a2a.news")
log.setLevel(logging.DEBUG)


class LangFlowRESTAdapter:
    """LangFlow API와 통신하여 뉴스 연구를 수행하는 어댑터"""

    def __init__(self,
                 base_url: str,
                 flow_id: str,
                 api_key: str,
                 timeout: int = 120):
        """
        LangFlow REST API 어댑터 초기화

        Args:
            base_url: LangFlow 서버 베이스 URL
            flow_id: 실행할 플로우 ID
            api_key: API 인증 키
            timeout: 요청 타임아웃 (초)
        """
        self.url = base_url.rstrip("/") + f"/api/v1/run/{flow_id}?stream=false"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key
        }
        self.timeout = timeout

    async def run(self, query_text: str) -> str:
        """LangFlow에 쿼리를 전송하고 텍스트 응답을 받아옴"""

        payload = {
            "output_type": "chat",
            "input_type": "chat",
            "input_value": query_text,
        }
        log.debug("LF.url=%s", self.url)
        # 키는 일부 마스킹
        _hdr = {
            **self.headers, "x-api-key":
            f"{self.headers.get('x-api-key','')[:6]}***"
        }
        log.debug("LF.headers=%s", _hdr)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                resp = await http.post(self.url,
                                       json=payload,
                                       headers=self.headers)
                resp.raise_for_status()
                text = resp.text or ""
                log.debug("LF.status=%s, len=%d", resp.status_code, len(text))
                return text
        except httpx.HTTPError as e:
            log.exception("LF.http_error url=%s err=%r", self.url, e)
            raise

    def to_standard_schema(self, raw_text: str) -> dict:
        """LangFlow 응답을 표준 스키마로 변환"""
        text = self._extract_text_from_langflow(raw_text)
        return {
            "news": {
                "summary": text[:4000],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        }

    def _extract_text_from_langflow(self, raw_text: str) -> str:
        """LangFlow JSON 응답에서 실제 텍스트를 추출"""
        try:
            obj = json.loads(raw_text)
            # 표준 경로: outputs[0].outputs[0].results.message.data.text
            outs = obj.get("outputs", [])
            if outs and outs[0].get("outputs"):
                results = outs[0]["outputs"][0].get("results", {})
                text = results.get("message", {}).get("data", {}).get("text")
                if text and text.strip():
                    return text

            # 최상위 text 필드 확인
            if obj.get("text"):
                return obj["text"]
        except json.JSONDecodeError:
            pass

        return raw_text or ""


class NewsResearchExecutor(AgentExecutor):
    """뉴스 연구를 수행하는 A2A Agent Executor"""

    def __init__(self, adapter: LangFlowRESTAdapter):
        self.adapter = adapter

    @override
    async def execute(self, context: RequestContext,
                      event_queue: EventQueue) -> None:
        """
        뉴스 연구 요청을 처리하고 결과를 이벤트 큐에 전송

        요청 형식: {"type":"news_research_request","ticker":"018260.KS","lang":"ko-KR","country":"KR"}
        """
        # 요청에서 ticker 추출
        req = self._parse_request(context)
        ticker = req.get("ticker") or req.get("query") or "UNKNOWN"
        log.debug(">>> [SERVER] ticker=%s", ticker)

        # LangFlow로 뉴스 조회
        query_text = f"{ticker} 뉴스 동향 요약"
        raw_text = await self.adapter.run(query_text)
        log.debug(">>> [SERVER] raw_text=%s", raw_text[:200])

        # 표준 형식으로 변환 후 이벤트 큐에 전송
        result = self.adapter.to_standard_schema(raw_text)
        log.debug(">>> [SERVER] result=%s",
                  json.dumps(result, ensure_ascii=False))

        msg = new_agent_parts_message(parts=[Part(root=DataPart(data=result))])
        await event_queue.enqueue_event(msg)
        log.debug(">>> [SERVER] enqueue 완료")

    def _parse_request(self, context: RequestContext) -> dict:
        """요청 메시지에서 데이터를 파싱"""
        if not context.message or not context.message.parts:
            return {}

        # 1. DataPart에서 JSON 데이터 추출 시도
        data_list = get_data_parts(context.message.parts)
        if data_list:
            return data_list[0] or {}

        # 2. 텍스트 부분 추출 시도
        texts = get_text_parts(context.message.parts)
        if texts:
            return {"query": texts[0]}

        # 3. 첫 번째 part의 json 속성 확인
        part0 = context.message.parts[0]
        return getattr(part0, "json", {})

    @override
    async def cancel(self, context: RequestContext,
                     event_queue: EventQueue) -> None:
        """단발 응답에서는 취소 처리 불필요"""
        pass


def build_app() -> A2AStarletteApplication:
    """A2A 애플리케이션 구성 및 반환"""
    skill = AgentSkill(
        id="news.research",
        name="News Research",
        description="LangFlow를 사용한 티커 뉴스 수집 및 요약",
        tags=["news", "research"],
        examples=["{'type':'news_research_request','ticker':'018260.KS'}"],
    )

    card = AgentCard(
        name="LangFlow News Researcher (A2A Wrapper)",
        description="LangFlow REST API를 래핑하는 A2A 서버",
        url=os.getenv("PUBLIC_URL", "http://localhost:9999/"),
        version="0.1.0",
        default_input_modes=["json"],
        default_output_modes=["json", "text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
        supports_authenticated_extended_card=False,
    )

    adapter = LangFlowRESTAdapter(
        base_url=os.environ["LANGFLOW_BASE_URL"],
        flow_id=os.environ["LANGFLOW_FLOW_ID"],
        api_key=os.environ["LANGFLOW_API_KEY"],
        timeout=120,
    )

    executor = NewsResearchExecutor(adapter)
    handler = DefaultRequestHandler(agent_executor=executor,
                                    task_store=InMemoryTaskStore())

    return A2AStarletteApplication(agent_card=card, http_handler=handler)


if __name__ == "__main__":
    app = build_app().build()
    port = int(os.getenv("PORT", os.getenv("A2A_SERVER_PORT", "9999")))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="debug")
