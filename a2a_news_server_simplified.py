#!/usr/bin/env python3
"""
Simplified A2A Server for Langflow News Agent
(Context7 Best Practices)

This is a simplified version following Context7's recommended patterns:
1. Use python-a2a's built-in patterns
2. Simpler request/response handling
3. Clear separation of concerns
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any

import httpx
import uvicorn
from python_a2a import A2AServer, run_server, AgentCard, AgentSkill, Message, TextContent, MessageRole

log = logging.getLogger("a2a.news")
log.setLevel(logging.DEBUG)


class LangFlowNewsAgent(A2AServer):
    """
    Simplified A2A Agent that wraps Langflow.
    
    Follows Context7 pattern: Extend A2AServer and implement handle_message.
    """
    
    def __init__(self, langflow_url: str, flow_id: str, api_key: str):
        """Initialize the agent with Langflow connection details."""
        agent_card = AgentCard(
            name="Langflow News Researcher",
            description="뉴스 연구 및 요약 에이전트 (Langflow 기반)",
            url=os.getenv("PUBLIC_URL", "http://localhost:9999"),
            version="1.0.0",
            skills=[
                AgentSkill(
                    name="news_research",
                    description="종목 뉴스 수집 및 분석",
                    examples=["AAPL 뉴스 분석", "삼성전자 최근 뉴스"]
                )
            ],
            capabilities={"streaming": False}
        )
        super().__init__(agent_card=agent_card)
        
        # Langflow connection
        self.langflow_url = f"{langflow_url.rstrip('/')}/api/v1/run/{flow_id}?stream=false"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key
        }
        self.timeout = 120
    
    def handle_message(self, message: Message) -> Message:
        """
        Handle incoming A2A messages.
        
        This is the main entry point following Context7 pattern.
        Much simpler than AgentExecutor + EventQueue approach!
        """
        # Extract ticker from message
        ticker = self._extract_ticker(message)
        log.debug(f"📰 Processing news request for: {ticker}")
        
        # Query Langflow
        try:
            news_summary = self._query_langflow(f"{ticker} 뉴스 동향 요약")
            log.debug(f"✅ Got news: {len(news_summary)} chars")
            
            # Return response as A2A Message
            return Message(
                content=TextContent(
                    text=json.dumps({
                        "news": {
                            "summary": news_summary,
                            "ticker": ticker,
                            "generated_at": datetime.now(timezone.utc).isoformat()
                        }
                    }, ensure_ascii=False)
                ),
                role=MessageRole.AGENT,
                parent_message_id=message.message_id,
                conversation_id=message.conversation_id
            )
        except Exception as e:
            log.exception(f"❌ Langflow query failed: {e}")
            return Message(
                content=TextContent(
                    text=json.dumps({"error": str(e)})
                ),
                role=MessageRole.AGENT,
                parent_message_id=message.message_id,
                conversation_id=message.conversation_id
            )
    
    def _extract_ticker(self, message: Message) -> str:
        """Extract ticker symbol from incoming message."""
        try:
            # Try parsing as JSON
            if hasattr(message.content, 'text'):
                data = json.loads(message.content.text)
                return data.get("ticker") or data.get("query") or "UNKNOWN"
            # Fallback: treat as plain text
            return str(message.content)
        except (json.JSONDecodeError, AttributeError):
            return str(message.content)
    
    def _query_langflow(self, query: str) -> str:
        """Query Langflow REST API and extract response text."""
        payload = {
            "output_type": "chat",
            "input_type": "chat",
            "input_value": query,
        }
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.langflow_url,
                json=payload,
                headers=self.headers
            )
            response.raise_for_status()
            
            # Extract text from Langflow response
            data = response.json()
            return self._extract_text_from_langflow(data)
    
    def _extract_text_from_langflow(self, data: Dict[str, Any]) -> str:
        """Extract actual text from Langflow's nested JSON response."""
        try:
            # Standard path: outputs[0].outputs[0].results.message.data.text
            outputs = data.get("outputs", [])
            if outputs and outputs[0].get("outputs"):
                results = outputs[0]["outputs"][0].get("results", {})
                text = results.get("message", {}).get("data", {}).get("text")
                if text and text.strip():
                    return text
            
            # Fallback: top-level text field
            if data.get("text"):
                return data["text"]
        except (KeyError, IndexError):
            pass
        
        return str(data)  # Last resort: stringify entire response


def main():
    """Run the A2A server."""
    # Load environment variables
    langflow_url = os.environ["LANGFLOW_BASE_URL"]
    flow_id = os.environ["LANGFLOW_FLOW_ID"]
    api_key = os.environ["LANGFLOW_API_KEY"]
    port = int(os.getenv("PORT", os.getenv("A2A_SERVER_PORT", "9999")))
    
    # Create and run agent
    agent = LangFlowNewsAgent(langflow_url, flow_id, api_key)
    
    print(f"🚀 Starting Langflow News A2A Server on port {port}")
    print(f"   Langflow: {langflow_url}")
    print(f"   Flow ID: {flow_id}")
    
    # Use python-a2a's built-in server runner (simpler!)
    run_server(agent, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

