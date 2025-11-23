# LLM Agent Workshop: Langflow & GDELT

Langflow와 GDELT 데이터를 활용해 AI 에이전트를 구축해보는 실습 워크샵입니다.

---

## 🚀 빠른 시작

### Replit 환경

1. **실행 (Run)**: 화면 상단의 `Run` 버튼을 클릭하세요.
   - 자동으로 의존성을 설치하고 Langflow를 실행합니다.
   - 실행 명령: `uv run langflow run`
2. **접속**: 터미널에 표시되는 URL을 통해 Langflow UI에 접속합니다.

### 로컬 환경

#### 브랜치별 실행 방법

```bash
# 프로젝트 클론
git clone https://github.com/Yo-sure/llm-agent-workshop
cd llm-agent-workshop

# 환경 변수 설정
cp env.example .env
# .env 파일을 열어 OPENAI_API_KEY를 입력하세요

# 의존성 설치
uv sync
```

**01-02 브랜치 (Langflow)**
```bash
git checkout 01-news-agent  # 또는 02-news-agent-with-mcp
uv sync
PYTHONPATH=$(pwd) uv run langflow run
```

**03 브랜치 (LangGraph Tutorial)**
```bash
git checkout 03-langgraph-agent
uv sync
jupyter notebook langgraph_agent/langgraph_tutorial.ipynb
```

**04 브랜치 (Trading Bot with A2A Integration)**

⚠️ **주의**: Langflow는 의존성 충돌로 인해 별도 환경에서 실행됩니다.

```bash
git checkout 04-langgraph-mcp-trading
uv sync

# 1. Langflow 설치 및 실행 (별도 환경 권장)
# 옵션 A: 별도 venv
python -m venv venv-langflow
source venv-langflow/bin/activate  # Windows: venv-langflow\Scripts\activate
pip install langflow
langflow run
deactivate

# 옵션 B: WSL 환경 (권장)
# WSL에서 이미 설치되어 있다면 그대로 사용
wsl -e langflow run

# 2. A2A News Server 실행 (Langflow 래퍼)
# .env 파일에 LANGFLOW_* 변수 설정 필수
uv run python a2a_news_server.py
# 또는: bash langgraph_agent/start_a2a_server.sh

# 3. Trading Bot 실행
uv run python langgraph_agent/trading_bot_host.py

# 4. 브라우저: http://localhost:8080
```

---

## 📚 실습 가이드

강의 진행에 따라 **Git Branch**를 변경하며 실습합니다.

- **`main`**: 환경 구성 및 Langflow UI 익히기
- **`01-news-agent`**: GDELT 뉴스 데이터 분석 에이전트 구축
- **`02-news-agent-with-mcp`**: MCP 서버 통합 및 Claude Desktop 연동
- **`03-langgraph-agent`**: LangGraph 기초 및 ReAct Agent 패턴 학습
- **`04-langgraph-mcp-trading`**: LangGraph + MCP + A2A 통합 Trading Bot (HITL + News)

---

## 🚀 주요 기능

### 📰 뉴스 검색 도구

* **GDELT DOC 2.0**: 전 세계 뉴스 데이터베이스 검색
* **Google News RSS**: 최신 뉴스 피드 검색  
* **Content Extractor**: 뉴스 웹사이트에서 깔끔한 본문 추출

### 🔧 이중 인터페이스 지원

* **Langflow Components** → 시각적 워크플로우 구성
* **MCP Server** → Claude 등 AI 모델과 직접 연동

---

## 📁 프로젝트 구조

```
llm-agent-workshop/
├── core_services/                 # 🔥 공통 비즈니스 로직 (DRY principle)
│   ├── gdelt_service.py           # GDELT API 서비스
│   └── content_extractor_service.py # 콘텐츠 추출 서비스
├── custom_components/             # Langflow 컴포넌트
│   ├── gdelt_doc_search_component.py         # Original implementation
│   ├── gdelt_doc_search_component_with_core.py   # Using core_services
│   ├── news_content_extractor.py             # Original implementation
│   └── news_content_extractor_with_core.py   # Using core_services
├── mcp_news_server.py             # 🆕 MCP 서버 (uses core_services)
└── custom_flows/                 # Langflow 플로우 예제
```

---

## 🛠️ MCP 서버 사용법 (02-news-agent-with-mcp 브랜치)

### 1. 서버 실행 모드

#### STDIO 모드 *(Claude Desktop용)*

```bash
uv run python mcp_news_server.py
```

#### SSE 모드 *(Langflow MCP Tools 연동 권장)*

```bash
uv run python mcp_news_server.py --sse
```

---

### 2. Claude Desktop 연동

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) 또는  
`%APPDATA%\Claude\claude_desktop_config.json` (Windows)에 추가:

```json
{
  "mcpServers": {
    "news-research": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/llm-agent-workshop",
        "run",
        "python",
        "mcp_news_server.py"
      ]
    }
  }
}
```

---

### 3. Langflow MCP Tools 연동

Langflow는 두 가지 transport 방식을 지원합니다. 상황에 맞게 선택하세요.

---

#### Option A: SSE 모드

##### 1) 서버 실행

```bash
uv run python mcp_news_server.py --sse
```

##### 2) Langflow JSON 설정

```json
{
  "news-research-sse": {
    "url": "http://127.0.0.1:8080/sse",
    "transport": "sse"
  }
}
```

---

#### Option B: STDIO 모드

##### Langflow JSON 설정 (서버 실행 불필요)

```json
{
  "news-research-stdio": {
    "command": "uv",
    "args": [
      "run",
      "python",
      "mcp_news_server.py"
    ],
    "transport": "stdio"
  }
}
```

⚠️ **STDIO 주의사항**: 
- STDIO는 표준 입출력(`stdin`/`stdout`)으로 JSON-RPC 메시지를 주고받습니다
- 서버 코드에서 **`print()` 사용 금지** - 통신이 깨집니다
- 로깅은 이미 `sys.stderr`로 설정되어 있어 안전합니다 (`mcp_news_server.py` 참고)

---

#### 📝 Langflow에서 JSON 설정 사용하기

1. Langflow UI → **Settings** → **MCP Servers**
2. **Import from JSON** 클릭
3. 위의 JSON 중 하나를 붙여넣기
4. **MCP Tools** 컴포넌트에서 서버 선택

---

## 🎯 MCP 도구 목록

### 1. `search_gdelt_news`

전 세계 뉴스 검색 (GDELT DOC 2.0)

```python
search_gdelt_news(
  query="Samsung SDS",  # Use ENGLISH keywords
  max_results=10,
  financial_media_only=True,  # Filter to financial media
  tone_filter="Positive",     # Sentiment filter
  timespan="7days"
)
```

**새로운 기능:**
- `financial_media_only`: 금융 미디어 프리셋 (Reuters, Bloomberg, WSJ 등)
- `tone_filter`: 감성 필터링 (Positive/Negative/Neutral)
- `languages`: ISO 639-3 언어 코드 (eng, kor, jpn, zho)
- `countries`: FIPS 국가 코드 (US, KS, JA, CH)

### 2. `extract_article_content`

뉴스 기사 본문 추출

```python
extract_article_content(
  urls="https://example.com/article1,https://example.com/article2",
  max_length=5000
)
```

**권장 사항:** GDELT 검색 후 상위 2-3개 URL만 추출

---

## 🏗️ 아키텍처 설계 원칙

1. **DRY**: 공통 로직을 `core_services`로 분리
2. **단일 책임**: 각 서비스는 하나의 명확한 기능 담당
3. **재사용성**: Langflow와 MCP 모두에서 동일한 서비스 활용
4. **테스트 용이성**: 순수 함수 기반 서비스 설계

### 컴포지션 패턴 예시

```python
# Langflow 컴포넌트 (_with_core 버전)
class GDELTDocSearchComponentWithCore(Component):
    def search_gdelt(self) -> DataFrame:
        df = GDELTService.search_news(...)  # 서비스 위임
        return DataFrame(df)

# MCP 도구
@mcp.tool()
async def search_gdelt_news(...) -> str:
    df = GDELTService.search_news(...)  # 동일한 서비스 사용
    return format_results(df)
```

### 컴포넌트 비교

- **Original Components** (`gdelt_doc_search_component.py`, `news_content_extractor.py`):
  - 자체 로직 구현
  - Langflow 전용
  
- **With Core Components** (`*_with_core.py`):
  - `core_services` 위임
  - 코드 중복 최소화
  - MCP 서버와 동일한 로직 공유

---

## 🔧 트러블슈팅

### Git 원격 브랜치 동기화

```bash
# 원격 저장소 확인
https://github.com/Yo-sure/llm-agent-workshop

# 원격 브랜치로 강제 리셋
git checkout -B main origin/main
```

### Replit 가상환경 위치 확인

```bash
echo $UV_PROJECT_ENVIRONMENT
# /home/runner/workspace/.pythonlibs
```

---

## 📚 사용 예제

### Claude Desktop에서 사용

```
"최근 7일간 NVIDIA 관련 뉴스를 GDELT에서 검색해줘"
"이 뉴스 기사의 본문을 깔끔하게 추출해줘: https://..."
```

### Langflow에서 사용

1. GDELT 컴포넌트로 뉴스 검색
2. Content Extractor로 본문 추출
3. LLM 컴포넌트로 요약 생성

### LangGraph Trading Bot (04 브랜치)

#### 🏗️ 시스템 아키텍처 (A2A 통합)

```
┌─────────────────────────────────────────┐
│    Web UI (http://localhost:8080)      │
│    - 실시간 승인 요청/응답              │
│    - WebSocket 연결                     │
└────────────┬────────────────────────────┘
             │ WebSocket
┌────────────▼────────────────────────────┐
│  FastAPI Host (trading_api.py)         │
│  - POST /api/trade                      │
│  - WebSocket /ws                        │
│  - GET /api/stocks                      │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  LangGraph Agent (trading_agent.py)    │
│  - 뉴스 조회 (A2A) → 시장 분석 (MCP)   │
│  - 종합 판단 → 거래 결정 → 승인 요청   │
│  - State Management (MemorySaver)       │
│  - interrupt() 기반 HITL                │
└──────┬──────────────────────┬───────────┘
       │ HTTP (A2A)           │ STDIO (MCP)
       │                      │
┌──────▼───────────┐  ┌───────▼─────────────┐
│ A2A News Server  │  │ MCP Trading Server  │
│ (port 9999)      │  │ (STDIO subprocess)  │
│                  │  │                     │
│ - News Research  │  │ Tools:              │
│   Skill          │  │ - analyze_market_   │
│                  │  │   trend()           │
└──────┬───────────┘  │ - execute_trade()   │
       │ HTTP REST    │ - health_check()    │
       │              │                     │
┌──────▼───────────┐  │ Resources:          │
│ Langflow         │  │ - terms-and-cond... │
│ (port 7860)      │  │                     │
│                  │  │ Prompts:            │
│ News Flow:       │  │ - neutral_analyst   │
│ - GDELT Search   │  └─────────────────────┘
│ - Content Extract│
│ - LLM Summary    │
└──────────────────┘
```

#### 🔄 HITL (Human-in-the-Loop) 워크플로우

```
1. 거래 요청
   POST /api/trade {"ticker": "NVDA"}
   
2. Agent: 시장 분석
   analyze_market_trend("NVDA")
   → {trend: "upward", recommendation: "BUY"}
   
3. 승인 요청 (interrupt)
   request_human_approval("NVDA", "BUY", "Strong uptrend...")
   → WebSocket으로 UI에 브로드캐스트
   → Agent 실행 중단 (5분 대기)
   
4. 사용자 승인/거부
   UI에서 "승인" 또는 "거부" 클릭
   → WebSocket으로 응답 전송
   
5. 거래 실행
   execute_trade("NVDA", "BUY", "...")
   → 결과 WebSocket으로 브로드캐스트
```

#### 🚀 실행 방법

```bash
# 1. 환경 변수 설정
cp env.example .env
# .env 파일을 열어 OPENAI_API_KEY를 입력하세요

# 2. Trading Bot 실행
uv run python langgraph_agent/trading_bot_host.py

# 3. 브라우저에서 접속
# http://localhost:8080
```

#### 📡 API 엔드포인트

- **`POST /api/trade`**: 거래 요청
  ```json
  {"ticker": "AAPL"}
  ```

- **`GET /`**: Web UI (실시간 승인 인터페이스)

- **`WebSocket /ws`**: 실시간 이벤트 스트림
  - `approval_request`: 승인 요청
  - `trade_executed`: 거래 완료
  - `trade_rejected`: 거래 거부

#### ⚙️ 주요 기능

- ✅ **종목 뉴스 분석** (A2A → Langflow)
- ✅ **시장 트렌드 분석** (MCP Tools)
- ✅ **종합 거래 결정** (뉴스 + 시장 데이터 → BUY/SELL/HOLD)
- ✅ **Human-in-the-Loop 승인 시스템** (interrupt() 기반)
- ✅ **실시간 WebSocket UI**
- ✅ **State 기반 에이전트** (MemorySaver)
- ✅ **Agent-to-Agent (A2A) 통합** (LangGraph ↔ Langflow)
- ✅ **MCP Resources & Prompts** (약관 표시, 중립 분석가 모드)
