# GDELT Doc Search Component

전 세계 뉴스·블로그를 실시간으로 수집·분석하는 **GDELT DOC 2.0 API**를 LangFlow에서 활용할 수 있는 커스텀 컴포넌트입니다.

## 🎯 주요 기능

### 1. **기사 검색** (Articles)
- 최신 뉴스 기사 목록을 DataFrame으로 반환
- 도메인, 언어, 국가별 필터링
- 감성 톤 분석 및 필터링
- 금융 미디어 프리셋 지원

### 2. **트렌드 분석** (Timeline)
- 시간별 기사량 추이
- 시간별 감성 변화 추적
- 언어/국가별 분포 분석

---

## 🚀 퀵스타트

### 1. 금융 미디어에서 긍정적인 뉴스만

```python
Query: NVIDIA earnings
Mode: Articles (기사 목록)
Financial Media Only: True
Sentiment Filter: Positive
Max Records: 10
```

**결과**: Bloomberg, Reuters 등 금융 미디어에서 NVIDIA 실적 관련 긍정적 기사 10개

---

### 2. 특정 종목 리스크 모니터링

```python
Query: (Tesla OR TSLA) AND (recall OR lawsuit)
Mode: Articles (기사 목록)
Financial Media Only: True
Sentiment Filter: Negative
Timespan: 7days
```

**결과**: 최근 7일간 Tesla 리콜/소송 관련 부정적 금융 뉴스

---

### 3. 섹터별 감성 변화 추적

```python
Query: semiconductor industry
Mode: Timeline - Sentiment (시간별 감성 변화)
Timespan: 30days
```

**결과**: 최근 30일간 반도체 산업 보도의 감성 톤 변화 추이

---

### 4. 글로벌 이슈 확산 분석

```python
Query: "AI regulation"
Mode: Timeline - Country (국가별 분포)
Countries: ["US", "KR", "JP", "CN"]
Timespan: 14days
```

**결과**: AI 규제 관련 국가별 보도량 변화

---

## 📋 입력 필드

### 🔍 검색 기본 설정

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `query` | string | **필수** | 검색 키워드. 예: `NVIDIA`, `(Tesla OR TSLA)` |
| `mode` | dropdown | Articles (기사 목록) | 검색 모드 선택 (아래 상세 참고) |
| `maxrecords` | int | 5 | 반환할 결과 개수 (1~250) |

#### 모드 옵션
- **Articles (기사 목록)** - 뉴스 기사 목록 반환
- **Timeline - Volume (시간별 기사량)** - 시간에 따른 기사 수 추이
- **Timeline - Sentiment (시간별 감성 변화)** - 시간에 따른 감성 톤 변화
- **Timeline - Language (언어별 분포)** - 언어별 기사 분포
- **Timeline - Country (국가별 분포)** - 국가별 기사 분포

---

### 🎯 필터링 (Advanced)

| 필드 | 타입 | 설명 |
|------|------|------|
| `domains` | list[str] | 도메인 필터. 예: `["reuters.com", "bloomberg.com"]` |
| `languages` | list[str] | 언어 필터 (ISO 639-3, 3자리). 예: `["eng", "kor", "jpn", "zho"]` |
| `countries` | list[str] | 발행 국가 (FIPS 2자리). 예: `["US", "KS"]` |
| `financial_media_only` | bool | **🆕** 금융 미디어만 검색 (10개 주요 금융 매체) |
| `tone_filter` | dropdown | **🆕** 감성 필터: All / Positive / Negative / Neutral |

#### 금융 미디어 프리셋 (10개)
`financial_media_only=True` 설정 시 자동 적용:
- Reuters, Bloomberg, Financial Times, Wall Street Journal
- CNBC, MarketWatch, Barron's, Seeking Alpha
- Investopedia, Motley Fool

---

### 📅 시간 범위

| 필드 | 타입 | 설명 |
|------|------|------|
| `timespan` | string | 상대 기간. 예: `7days`, `24hours`, `30days` |
| `start_datetime` | string | 절대 시작 시각. 형식: `YYYYMMDDHHMMSS` |
| `end_datetime` | string | 절대 종료 시각. 형식: `YYYYMMDDHHMMSS` |

**⚠️ 주의**: `timespan`과 `start_datetime/end_datetime` 중 하나만 사용

---

### 🌐 코드 참고

#### 주요 언어 코드 (ISO 639-3, 3자리)
| 언어 | 코드 | 언어 | 코드 | 언어 | 코드 |
|------|------|------|------|------|------|
| 영어 | `eng` | 한국어 | `kor` | 일본어 | `jpn` |
| 중국어 | `zho` | 스페인어 | `spa` | 프랑스어 | `fra` |
| 독일어 | `deu` | 러시아어 | `rus` | 아랍어 | `ara` |
| 포르투갈어 | `por` | 이탈리아어 | `ita` | 힌디어 | `hin` |

📖 [GDELT 공식 언어 코드 전체 목록](http://data.gdeltproject.org/api/v2/guides/LOOKUP-LANGUAGES.TXT)

#### 주요 국가 코드 (FIPS 2자리)
| 국가 | 코드 | 국가 | 코드 | 국가 | 코드 |
|------|------|------|------|------|------|
| 미국 | `US` | **한국** | **`KS`** | 일본 | `JA` |
| 중국 | `CH` | 영국 | `UK` | 독일 | `GM` |
| 프랑스 | `FR` | 캐나다 | `CA` | 호주 | `AS` |

📖 [GDELT 공식 국가 코드 전체 목록](http://data.gdeltproject.org/api/v2/guides/LOOKUP-COUNTRIES.TXT)

---

### ⚙️ 기타 설정 (Advanced)

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `sort` | dropdown | DateDesc | Articles 모드 전용. DateDesc / DateAsc |
| `timeline_smooth` | int | 0 | Timeline 모드 전용. 평활화 정도 (0=없음) |
| `timeout` | int | 25 | API 요청 타임아웃 (초) |
| `use_cache` | bool | True | HTTP 캐시 사용 여부 |
| `cache_ttl` | int | 300 | 캐시 유효 시간 (초) |

---

## 📤 출력 결과

### Articles (기사 목록) 모드

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `title` | string | 기사 제목 |
| `url` | string | 기사 URL |
| `seendate` | string | 수집 일시 (YYYYMMDDHHMMSS) |
| `domain` | string | 출처 도메인 |
| `language` | string | 기사 언어 |
| `sourcecountry` | string | 발행 국가 (FIPS 코드) |
| `tone` | float | **🆕** 감성 톤 (-10 ~ +10, 높을수록 긍정적) |

#### 감성 톤 해석
- **> 5**: 긍정적 (Positive)
- **-5 ~ 5**: 중립적 (Neutral)
- **< -5**: 부정적 (Negative)

---

### Timeline 모드

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `series` | string | 시리즈 이름 |
| `date` | string | 날짜/시간 |
| `value` | float | 측정값 (모드별 의미 상이) |
| 기타 | - | 모드에 따라 언어/국가 분포 필드 추가 |

#### 모드별 `value` 의미
- **Volume**: 기사 수
- **Sentiment**: 평균 감성 톤
- **Language**: 언어별 비율
- **Country**: 국가별 비율

---

## 💡 활용 시나리오

### 📈 금융/주식 분석

#### 1. 실적 발표 전후 감성 변화
```python
mode: Timeline - Sentiment (시간별 감성 변화)
query: (NVIDIA OR NVDA) AND earnings
timespan: 30days
financial_media_only: True
```
→ 실적 발표를 기점으로 언론 보도의 감성이 어떻게 변했는지 추적

#### 2. 섹터별 긍정 뉴스 발굴
```python
mode: Articles (기사 목록)
query: electric vehicle
tone_filter: Positive
financial_media_only: True
maxrecords: 20
```
→ 전기차 섹터의 긍정적 뉴스만 수집 (투자 아이디어 발굴)

#### 3. 리스크 모니터링
```python
mode: Articles (기사 목록)
query: (삼성전자 OR Samsung Electronics) AND (lawsuit OR fine OR penalty)
tone_filter: Negative
timespan: 7days
```
→ 최근 법률/규제 리스크 관련 부정적 뉴스 모니터링

---

### 🌍 글로벌 이슈 추적

#### 4. 국가별 이슈 확산 패턴
```python
mode: Timeline - Country (국가별 분포)
query: "AI regulation"
countries: ["US", "KR", "JP", "CN", "GB"]
timespan: 60days
```
→ AI 규제 논의가 어느 국가에서 먼저 시작되고 확산되는지 분석

#### 5. 언어권별 관심도 비교
```python
mode: Timeline - Language (언어별 분포)
query: ChatGPT
languages: ["eng", "kor", "zho", "jpn"]  # ISO 639-3 (3자리)
timespan: 30days
```
→ ChatGPT에 대한 언어권별 관심도 변화 추이

---

## ✍️ 쿼리 작성 가이드

### 기본 문법

#### 1. OR 조건 (반드시 괄호 사용)
```
✅ (NVIDIA OR NVDA OR "Nvidia Corporation")
❌ NVIDIA OR NVDA  # 괄호 없으면 오작동 가능
```

#### 2. AND 조건
```
✅ Tesla AND recall
✅ (Tesla OR TSLA) AND (battery OR fire)
```

#### 3. 구문 검색 (따옴표)
```
✅ "artificial intelligence"
✅ "climate change" AND policy
```

#### 4. NOT 조건
```
✅ Apple NOT (fruit OR food)
✅ Samsung NOT (Galaxy OR smartphone)  # 삼성그룹 뉴스만
```

---

### 필터 조합 전략

#### 패턴 1: 금융 프리셋 + 추가 도메인
```python
financial_media_only: True
domains: ["naver.com", "investing.com"]
```
→ 금융 미디어 10개 + 추가 도메인 2개 = 총 12개 도메인

#### 패턴 2: 감성 필터 + 키워드
```python
query: NVIDIA
tone_filter: Positive
timespan: 7days
```
→ 최근 7일간 NVIDIA 긍정 뉴스만

#### 패턴 3: 다국어 검색
```python
query: (삼성전자 OR "Samsung Electronics" OR サムスン電子)
languages: ["kor", "eng", "jpn"]  # ISO 639-3 (3자리)
countries: ["KS", "US", "JA"]     # FIPS (2자리)
```
→ 한·미·일 3개국에서 삼성전자 관련 뉴스

---

## ⚙️ 최적화 팁

### 성능 최적화

| 상황 | 권장 설정 | 이유 |
|------|-----------|------|
| Agent Tool로 사용 | `maxrecords=5~10` | LLM 컨텍스트 절약 |
| 실시간 모니터링 | `use_cache=False` | 최신 데이터 보장 |
| 대량 분석 | `maxrecords=100~250` | 통계적 유의성 확보 |
| 복잡한 쿼리 | `timeout=30~60` | API 처리 시간 고려 |

### Agent 프롬프트 예시

```
You are a financial news analyst. Use search_gdelt tool:

- For positive news: tone_filter="Positive"
- For risk monitoring: tone_filter="Negative"
- For financial analysis: financial_media_only=True
- Always use mode="Articles (기사 목록)" for article lists
- Use Timeline modes for trend analysis
```

---

## 🐛 문제 해결

### 빈 결과가 나올 때

| 원인 | 해결 방법 |
|------|-----------|
| 쿼리가 너무 구체적 | 키워드를 줄이고 OR 조건 활용 |
| 시간 범위가 짧음 | `timespan=30days` 또는 `60days`로 확대 |
| 필터가 과도함 | `domains`, `countries` 필터 제거 |
| 감성 필터가 강함 | `tone_filter="All"`로 변경 |

### 타임아웃 발생 시

| 해결 방법 | 설정 |
|-----------|------|
| 타임아웃 증가 | `timeout=60` |
| 기간 축소 | `timespan=7days` 대신 `3days` |
| 쿼리 단순화 | AND 조건 줄이기 |
| 결과 수 감소 | `maxrecords=10` 대신 `5` |

### 예상치 못한 결과

| 문제 | 원인 | 해결책 |
|------|------|--------|
| 관련 없는 기사 | 동음이의어 | NOT 조건으로 제외: `Apple NOT fruit` |
| 언어 혼합 | 언어 필터 없음 | `languages=["eng"]` 명시 (ISO 639-3, 3자리) |
| 오래된 기사 | 시간 필터 없음 | `timespan=7days` 추가 |

---

## 🔗 다른 컴포넌트와 연결

### NewsContentExtractor와 조합

```
[GDELTDocSearch] → [NewsContentExtractor]
```

**용도**: 기사 URL 수집 → 전체 본문 추출

```python
# 1. GDELT로 URL 수집
gdelt.query = "NVIDIA AI chip"
gdelt.mode = "Articles (기사 목록)"
gdelt.maxrecords = 10

# 2. NewsContentExtractor로 본문 추출
# (자동으로 GDELT 결과의 URL 컬럼 사용)
```

### Agent Tool로 활용

```
[ChatInput] → [Agent] → [GDELTDocSearch] → [ChatOutput]
                ↓
         [OpenAI Model]
```

**용도**: 사용자 질문에 따라 동적으로 뉴스 검색

```python
# System Prompt 예시
"""
You are a financial analyst assistant.
When user asks about stock news:
1. Use search_gdelt with financial_media_only=True
2. Set appropriate tone_filter based on user intent
3. Summarize key points from the results
"""
```

---

## 📚 참고 자료

### GDELT 공식 문서
- [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [GDELT 2.0 기능 소개](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/)
- [GDELT 프로젝트 홈](https://www.gdeltproject.org/)

### Langflow 문서
- [Custom Components 가이드](https://docs.langflow.org/)
- [DataFrame 객체 사용법](https://docs.langflow.org/components/data)

---

## 📝 버전 히스토리

### v2.0 (2025-11-23)
- 🆕 금융 미디어 프리셋 추가 (`financial_media_only`)
- 🆕 감성 톤 필터링 추가 (`tone_filter`)
- 🆕 감성 톤 컬럼 출력 (`tone`)
- 🎨 모드명을 사용자 친화적으로 변경 (Articles, Timeline - Volume 등)
- 📖 문서 전면 개편 (활용 시나리오, 쿼리 가이드 추가)

### v1.0
- 기본 GDELT DOC 2.0 API 연동
- ArtList, Timeline 모드 지원
- 도메인, 언어, 국가 필터링

---
