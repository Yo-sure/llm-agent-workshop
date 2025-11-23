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

```bash
# 프로젝트 클론
git clone https://github.com/Yo-sure/llm-agent-workshop
cd llm-agent-workshop

# 의존성 설치
uv sync

# Langflow 실행
PYTHONPATH=$(pwd) uv run langflow run
```

---

## 📚 실습 가이드

강의 진행에 따라 **Git Branch**를 변경하며 실습합니다.

- **`main`**: 환경 구성 및 Langflow UI 익히기
- **`01-news-agent`**: GDELT 뉴스 데이터 분석 에이전트 구축
- **`02-news-agent-with-mcp`**: MCP 서버 통합 및 Claude Desktop 연동

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
├── core_services/                 # 🔥 공통 비즈니스 로직
│   ├── gdelt_service.py           # GDELT API 서비스
│   └── content_extractor_service.py # 콘텐츠 추출 서비스
├── custom_components/             # Langflow 컴포넌트
│   ├── gdelt_doc_search_component.py
│   └── news_content_extractor.py
├── mcp_news_server.py             # 🆕 MCP 서버
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

##### 서버 실행

```bash
uv run python mcp_news_server.py --sse
```

Langflow UI에서 MCP Tools 컴포넌트 추가 후 `http://127.0.0.1:8080/sse` 연결

---

## 🎯 MCP 도구 목록

### 1. `search_gdelt_news`

전 세계 뉴스 검색 (GDELT DOC 2.0)

```python
search_gdelt_news(
  query="artificial intelligence", 
  max_results=10,
  timespan="7d"
)
```

### 2. `extract_article_content`

뉴스 기사 본문 추출

```python
extract_article_content(
  urls="https://example.com/article1,https://example.com/article2",
  max_length=3000
)
```

---

## 🏗️ 아키텍처 설계 원칙

1. **DRY**: 공통 로직을 `core_services`로 분리
2. **단일 책임**: 각 서비스는 하나의 명확한 기능 담당
3. **재사용성**: Langflow와 MCP 모두에서 동일한 서비스 활용
4. **테스트 용이성**: 순수 함수 기반 서비스 설계

### 컴포지션 패턴 예시

```python
# Langflow 컴포넌트
class GDELTDocSearchComponent(Component):
    def search_gdelt(self) -> DataFrame:
        df = GDELTService.search_news(...)  # 서비스 위임
        return DataFrame(df)

# MCP 도구
@mcp.tool()
async def search_gdelt_news(...) -> str:
    df = GDELTService.search_news(...)  # 동일한 서비스 사용
    return format_results(df)
```

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
