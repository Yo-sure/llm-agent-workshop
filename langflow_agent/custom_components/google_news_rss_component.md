# Google News RSS Component

Google News RSS는 Google News의 RSS 피드를 통해 전 세계 뉴스를 실시간으로 검색하고 수집하는 LangFlow 컴포넌트입니다.

키워드 검색, 토픽별 뉴스, 지역 기반 뉴스를 지원하며, 결과를 깔끔한 DataFrame으로 반환합니다.

## 🚀 퀵스타트

### 1. 키워드로 최신 뉴스 검색
```
Query: "artificial intelligence"
Max Results: 15
```
→ AI 관련 최신 뉴스 15개를 DataFrame으로 받음

### 2. 특정 토픽의 뉴스 가져오기
```
Topic: TECHNOLOGY
Language (hl): ko-KR
Country (gl): KR
Max Results: 10
```
→ 한국 기술 뉴스 10개 (한국어)

### 3. 지역 기반 뉴스 수집
```
Location: Seoul
Language (hl): en-US
Max Results: 20
```
→ 서울 관련 뉴스 20개 (영어)

### 4. 다국가 비즈니스 뉴스
```
Topic: BUSINESS
Country (gl): US
ceid: US:en
Max Results: 25
```
→ 미국 비즈니스 뉴스 25개

---

## 📋 컴포넌트 개요

| 필드 | 타입 | 기본값 | 설명 / 팁 |
|------|------|--------|-----------|
| `query` | string | - | 검색 키워드. 예: "climate change", "NVIDIA earnings" |
| `hl` | string | en-US | 언어 코드. 예: en-US, ko-KR, ja-JP, fr-FR |
| `gl` | string | US | 국가 코드. 예: US, KR, JP, FR, DE |
| `ceid` | string | US:en | 국가:언어 조합. 예: US:en, KR:ko, JP:ja |
| `topic` | string | - | 토픽 카테고리 (아래 참조) |
| `location` | string | - | 지역명. 예: "Seoul", "New York", "Tokyo" |
| `max_results` | int | 10 | 반환할 기사 수 (1-100 권장) |
| `timeout` | int | 10 | 요청 타임아웃 (초) |

### 📰 지원 토픽 카테고리
- `WORLD` - 세계 뉴스
- `NATION` - 국내 뉴스  
- `BUSINESS` - 비즈니스
- `TECHNOLOGY` - 기술
- `ENTERTAINMENT` - 엔터테인먼트
- `SCIENCE` - 과학
- `SPORTS` - 스포츠
- `HEALTH` - 건강

**⚠️ 우선순위**: topic > location > query 순서로 적용됩니다.

---

## 📤 출력(Outputs)

**News Articles**: DataFrame

### 스키마
- `title`: 기사 제목
- `link`: 기사 URL
- `published`: 발행 시간 (RFC 2822 형식)
- `summary`: 기사 요약/설명

---

## 🎯 사용 시나리오별 가이드

| 시나리오 | 설정 방법 | 활용 팁 |
|----------|-----------|---------|
| **키워드 모니터링** | query 설정, topic/location 비움 | 특정 브랜드/이슈 추적 |
| **토픽별 정기 수집** | topic 설정, query 비움 | 카테고리별 뉴스 큐레이션 |
| **지역 뉴스 수집** | location 설정, query 비움 | 특정 도시/국가 이슈 파악 |
| **다국가 비교** | gl, hl, ceid 조합 활용 | 같은 이슈의 국가별 시각 |

---

## 🔧 고급 활용 팁

### 언어/지역 조합 예시
```python
# 한국 뉴스 (한국어)
hl="ko-KR", gl="KR", ceid="KR:ko"

# 일본 뉴스 (영어)
hl="en-US", gl="JP", ceid="JP:en"

# 프랑스 뉴스 (프랑스어)
hl="fr-FR", gl="FR", ceid="FR:fr"
```

### 키워드 검색 최적화
```python
# 정확한 구문 검색
query='"artificial intelligence"'

# 복합 키워드
query="NVIDIA earnings report"

# 브랜드 모니터링  
query="Tesla OR SpaceX"
```

### 결과 수 조절
```python
# 빠른 샘플링
max_results=5

# 충분한 데이터
max_results=50

# 대량 수집 (주의: 느려질 수 있음)
max_results=100
```

---

## 🆚 기존 버전 대비 개선사항

### ✅ 새로운 기능
- **`max_results` 파라미터**: 결과 수 제한으로 성능 최적화
- **구조화된 에러 처리**: 개별 기사 파싱 실패가 전체에 영향 주지 않음
- **한국어 인터페이스**: 설명과 안내가 한국어로 제공
- **User-Agent 추가**: 요청 차단 방지

### 🔧 코드 품질 개선
- **메서드 분리**: `_build_rss_url()`, `_parse_rss_items()`, `_clean_html()`
- **타임아웃 증가**: 5초 → 10초 (안정성 향상)
- **빈 제목 필터링**: 의미없는 기사 자동 제외
- **로깅 강화**: 더 상세한 처리 과정 로그

---

## ⚡ 사용 팁

### 결과 수 조절
- **빠른 테스트**: `max_results = 5-10`
- **일반적인 사용**: `max_results = 20-30`
- **대량 수집**: `max_results = 50-100` (느려질 수 있음)

### 타임아웃 설정
- 네트워크 상황에 따라 `timeout` 값 조정
- 기본값 10초로 대부분 상황에서 적절함

### RSS 피드 특성
- RSS 피드는 보통 15-30분마다 업데이트됨
- 같은 쿼리를 짧은 시간 내 반복 실행할 필요 없음

---

## 🐛 문제 해결

### 자주 발생하는 문제

#### 1. 빈 결과
```
원인: 너무 구체적인 키워드, 잘못된 토픽명
해결: 키워드 단순화, 토픽명 대문자 확인
```

#### 2. 타임아웃 오류
```
원인: 네트워크 지연, 서버 응답 지연
해결: timeout 값 증가 (10 → 20초)
```

#### 3. 언어/지역 불일치
```
원인: hl, gl, ceid 조합 오류
해결: 일관된 조합 사용 (예: hl="ko-KR", gl="KR", ceid="KR:ko")
```

### 디버깅 팁
1. **단순한 쿼리부터**: topic="TECHNOLOGY"로 기본 동작 확인
2. **로그 확인**: 컴포넌트 로그에서 실제 RSS URL 확인
3. **브라우저 테스트**: 생성된 RSS URL을 브라우저에서 직접 확인

---

## 🌐 실제 RSS URL 예시

### 키워드 검색
```
https://news.google.com/rss/search?q=artificial%20intelligence&hl=en-US&gl=US&ceid=US:en
```

### 토픽 기반
```  
https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko-KR&gl=KR&ceid=KR:ko
```

### 지역 기반
```
https://news.google.com/rss/headlines/section/geo/Seoul?hl=en-US&gl=KR&ceid=KR:en
```

---

## 📚 참고 자료

- [Google News RSS 공식 가이드](https://support.google.com/news/publisher-center/answer/9606710)
- [RSS 2.0 스펙](https://cyber.harvard.edu/rss/rss.html)
- [LangFlow 커스텀 컴포넌트](https://docs.langflow.org/components-custom)
- [BeautifulSoup 문서](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
