# Project Structure

## 📁 디렉토리 구조

```
llm-agent-workshop/
├── core_services/                    # 🔥 공통 비즈니스 로직
│   ├── gdelt_service.py              # GDELT API 서비스
│   └── content_extractor_service.py  # 콘텐츠 추출 서비스
│
├── custom_components/                # Langflow 컴포넌트
│   ├── gdelt_doc_search_component*.py
│   └── news_content_extractor*.py
│
├── langflow_agent/                   # Langflow 관련 파일
│   ├── core_services/                # Langflow용 서비스 복사본
│   ├── custom_components/            # Langflow 커스텀 컴포넌트
│   └── custom_flows/                 # Langflow 플로우 예제
│
├── langgraph_agent/                  # 🎯 LangGraph Trading Bot
│   ├── trading_agent.py              # Agent 로직 (MCP + A2A)
│   ├── trading_api.py                # FastAPI 서버
│   ├── trading_bot_host.py           # 메인 진입점
│   ├── trading_mcp_server.py         # MCP Tools/Resources/Prompts
│   ├── ui_template.html              # Web UI
│   ├── langgraph_tutorial.ipynb     # LangGraph 튜토리얼
│   ├── start_a2a_server.sh           # A2A 서버 시작 스크립트
│   └── A2A_IMPLEMENTATION_REVIEW.md  # A2A 구현 검증 리포트
│
├── docs/                             # 📚 강의 자료
│   ├── Chapter 1. Langflow 시작.md
│   ├── Chapter 2. Langflow 심화.md
│   ├── Chapter 3. MCP 이론.md
│   └── Chapter 4. MCP 전환.md
│
├── mcp_news_server.py                # 🔌 MCP 뉴스 서버 (STDIO/SSE/HTTP)
├── a2a_news_server.py                # 🤝 A2A 뉴스 서버 (Langflow 래퍼)
├── a2a_news_server_simplified.py    # 📝 A2A 단순 버전 (참고용)
├── a2a_news_client.py                # 📡 A2A 클라이언트
│
├── pyproject.toml                    # 의존성 관리 (uv)
├── uv.lock                           # 락 파일
├── env.example                       # 환경변수 템플릿
├── .gitignore                        # Git 무시 파일
└── README.md                         # 프로젝트 README
```

## 🎯 주요 파일 역할

### 프로토콜 서버들 (루트)
```
mcp_news_server.py         → MCP 프로토콜로 뉴스 검색 노출
a2a_news_server.py         → A2A 프로토콜로 Langflow 래핑
a2a_news_client.py         → A2A 서버와 통신하는 클라이언트
```

**공통점**: 모두 `core_services/`를 재사용하여 DRY 원칙 준수

### Trading Bot (langgraph_agent/)
```
trading_bot_host.py        → 메인 진입점 (lifespan 관리)
trading_api.py             → FastAPI (REST + WebSocket)
trading_agent.py           → LangGraph Agent (MCP + A2A 통합)
trading_mcp_server.py      → MCP 서버 (Tools/Resources/Prompts)
ui_template.html           → 실시간 승인 Web UI
```

### Langflow Components (langflow_agent/)
```
custom_components/         → Langflow 드래그앤드롭 컴포넌트
custom_flows/              → 플로우 예제 JSON
core_services/             → 비즈니스 로직 (루트와 동일)
```

## 🔄 데이터 흐름

### 1. MCP 프로토콜 (Claude Desktop)
```
Claude Desktop
    ↓ STDIO (JSON-RPC)
mcp_news_server.py
    ↓ Python Function Call
core_services/
    ↓ HTTP
GDELT API / News Websites
```

### 2. A2A 프로토콜 (Agent-to-Agent)
```
Trading Bot (LangGraph)
    ↓ HTTP (A2A Client)
a2a_news_server.py
    ↓ HTTP (REST)
Langflow (WSL)
    ↓ MCP/Custom Components
core_services/
    ↓ HTTP
GDELT API / News Websites
```

### 3. Trading Bot 전체 흐름
```
User (Web UI)
    ↓ WebSocket
trading_api.py
    ↓ Function Call
trading_agent.py (LangGraph)
    ├─→ A2A Client → Langflow (뉴스)
    └─→ MCP Client → trading_mcp_server.py (시장 분석)
    ↓ interrupt() → Human Approval
    ↓ resume() → execute_trade()
User (Web UI)
```

## 🧩 왜 이렇게 구조화했나?

### 1. 프로토콜 서버를 루트에 배치
- ✅ `mcp_news_server.py`와 `a2a_news_server.py`는 **독립 실행 가능한 서버**
- ✅ 여러 에이전트에서 재사용 가능
- ✅ `core_services/`와 동일 레벨로 명확한 의존성

### 2. LangGraph Agent를 별도 디렉토리에
- ✅ `langgraph_agent/`는 **하나의 완전한 애플리케이션**
- ✅ 내부 파일들이 서로 강하게 결합 (Agent ↔ API ↔ Host)
- ✅ 독립적으로 실행되고 테스트 가능

### 3. Langflow를 별도 디렉토리에
- ✅ `langflow_agent/`는 **Langflow 전용 컴포넌트 모음**
- ✅ 의존성 충돌 방지 (별도 환경에서 실행)
- ✅ Langflow UI에서 직접 로드 가능

### 4. Core Services 중복
- ⚠️ `core_services/`가 루트와 `langflow_agent/`에 중복 존재
- **이유**: Langflow가 상대 경로 import만 지원
- **장점**: 각 환경에서 독립 실행 가능

## 🚀 실행 순서 (04 브랜치)

```bash
# 1. Langflow 실행 (별도 환경)
langflow run                          # WSL 또는 별도 venv

# 2. A2A News Server 실행
uv run python a2a_news_server.py      # 루트 디렉토리에서

# 3. Trading Bot 실행
uv run python langgraph_agent/trading_bot_host.py
```

## 📊 브랜치별 사용 파일

| 브랜치 | 사용 파일 | 목적 |
|--------|-----------|------|
| `01-news-agent` | `langflow_agent/`, `core_services/` | Langflow 기초 |
| `02-news-agent-with-mcp` | `mcp_news_server.py`, `core_services/` | MCP 통합 |
| `03-langgraph-agent` | `langgraph_agent/langgraph_tutorial.ipynb` | LangGraph 학습 |
| `04-langgraph-mcp-trading` | `langgraph_agent/`, `a2a_news_server.py`, `a2a_news_client.py` | 전체 통합 |

## 💡 설계 원칙

1. **DRY (Don't Repeat Yourself)**: `core_services/`로 비즈니스 로직 재사용
2. **Single Responsibility**: 각 파일은 하나의 명확한 책임
3. **Protocol Independence**: MCP/A2A 서버는 독립 실행 가능
4. **Separation of Concerns**: UI/API/Agent/Tools 분리
5. **Environment Isolation**: Langflow는 별도 환경에서 실행

