# LLM Agent Workshop - News Research Tools

뉴스 연구를 위한 **Langflow 컴포넌트**와 **MCP(Model Context Protocol) 서버**를 제공합니다.

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
│   ├── google_news_service.py     # Google News RSS 서비스
│   └── content_extractor_service.py # 콘텐츠 추출 서비스
├── custom_components/             # Langflow 컴포넌트
│   ├── gdelt_doc_search_component.py
│   ├── google_news_rss_component.py
│   └── news_content_extractor.py
├── mcp_news_server.py             # 🆕 MCP 서버
└── custom_flows/                 # Langflow 플로우 예제
```

---

## 🛠️ 설치 및 설정

### 환경 설정

```bash
# 프로젝트 클론
git clone https://github.com/Yo-sure/llm-agent-workshop
cd llm-agent-workshop

# 의존성 설치
uv sync
```

---

### Langflow에서 사용

#### **로컬 환경**

```bash
# PYTHONPATH 설정 후 Langflow 실행
PYTHONPATH=$(pwd) uv run langflow run
```

#### **Replit 환경**

```bash
# Replit Run 버튼 클릭 또는 수동 실행
PYTHONPATH=$PWD uv run langflow run
```

---

### MCP 서버로 사용

#### **1. 서버 테스트**

##### STDIO 모드 *(Claude Desktop / Langflow용)*

```bash
uv run python mcp_news_server.py
```

```json
{
  "mcpServers": {
    "news_research": {
      "command": "uv",
      "args": [
        "--directory",
        ".",
        "run",
        "python",
        "mcp_news_server.py"
      ],
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}

```
##### HTTP 모드 *(서버 배포용, 기본 포트 8080)*

```bash
uv run python mcp_news_server.py --http
```

##### SSE 모드 *(Langflow MCP Tools 연동 권장)*

```bash
uv run python mcp_news_server.py --sse
```

```json
{
  "mcpServers": {
    "news-research-sse": {
      "transport": "sse",
      "url": "http://127.0.0.1:8080/sse"
    }
  }
}
```
---

#### **2. Claude Desktop 연동**

`~/Library/Application Support/Claude/claude_desktop_config.json`에 다음을 추가:

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

#### **3. Langflow MCP Tools 연동**

##### 서버 실행

```bash
uv run python mcp_news_server.py --sse
```

---

## 🎯 MCP 도구 사용법

MCP 서버는 다음 3개 도구를 제공합니다:

### 1. `search_gdelt_news`

전 세계 뉴스 검색 (GDELT DOC 2.0)

```python
search_gdelt_news(
  query="artificial intelligence", 
  max_results=10,
  timespan="7d"
)
```

### 2. `search_google_news`

최신 뉴스 검색 (Google News RSS)

```python
search_google_news(
  query="기술 뉴스",
  max_results=5,
  language="ko",
  country="KR"
)
```

### 3. `extract_article_content`

뉴스 기사 본문 추출

```python
extract_article_content(
  urls="https://example.com/news/article1,https://example.com/news/article2",
  max_length=3000
)
```

---

## 🏗️ 아키텍처 설계

### 핵심 설계 원칙

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

## 🧪 개발 및 테스트

### 서비스 단위 테스트

```bash
uv run python -c "from core_services.gdelt_service import GDELTService; print('✅ OK')"
uv run python -c "from core_services.google_news_service import GoogleNewsService; print('✅ OK')"
uv run python -c "from core_services.content_extractor_service import ContentExtractorService; print('✅ OK')"
```

### MCP 서버 테스트

```bash
uv run python -c "import mcp_news_server; print('✅ MCP Server OK')"
```

---

## 📚 사용 예제

### Claude Desktop에서 사용

```
"최근 7일간 NVIDIA 관련 뉴스를 GDELT에서 검색해줘"
"한국의 AI 기술 뉴스를 Google News에서 찾아줘"
"이 뉴스 기사의 본문을 깔끔하게 추출해줘: https://..."
```

### Langflow에서 사용

1. GDELT 컴포넌트로 뉴스 검색
2. Content Extractor로 본문 추출
3. LLM 컴포넌트로 요약 생성

---

## 📝 Git 설정 참고

### 원격 브랜치 동기화 문제 해결

```bash
git checkout -B main origin/main
```

---

## 🔧 Replit 환경 설정

### 자동 실행 설정 완료

* **Run 버튼** 클릭 → PYTHONPATH 자동 설정
* **`.replit` 파일** → 환경 변수 자동 설정 완료

### Replit venv 위치 확인

```bash
echo $UV_PROJECT_ENVIRONMENT
# /home/runner/workspace/.pythonlibs
```

### 수동 실행 (필요 시)

```bash
PYTHONPATH=$PWD uv run langflow run
```
