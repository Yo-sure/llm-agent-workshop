# News Content Extractor

뉴스 URL에서 깨끗한 본문만 추출하는 컴포넌트입니다.

> 광고, 네비게이션, 소셜 버튼 등 불필요한 요소를 자동으로 제거하고 기사 본문만 가져옵니다.

---

## ⚡ 빠른 시작

### Langflow에서 사용하기
1. 컴포넌트 추가: **News Content Extractor**
2. URL 입력: 뉴스 기사 URL 입력 (여러 개 가능)
3. 실행 → 본문 추출 완료!

### 독립 테스트
```bash
python custom_components/news_content_extractor.py
```

---

## 📥 입력

| 필드 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| **URLs** | ✅ | - | 추출할 뉴스 기사 URL (복수 입력 가능) |
| Max Content Length | | 5000 | 추출할 최대 글자 수 |
| Timeout | | 15초 | 요청 타임아웃 |
| Include Metadata | | True | 제목/설명 포함 여부 |
| Remove Short Paragraphs | | True | 50자 미만 문단 제거 |

---

## 📤 출력 (DataFrame)

| 필드 | 타입 | 설명 |
|------|------|------|
| `url` | str | 원본 URL |
| `title` | str | 페이지 제목 |
| `description` | str | 메타 설명 (og:description) |
| `content` | str | **추출된 본문 텍스트** |
| `content_length` | int | 본문 길이 (글자 수) |
| `paragraphs_count` | int | 문단 수 |
| `success` | bool | 성공 여부 |
| `error` | str | 실패 시 에러 메시지 |

---

## 🔍 작동 원리

### 1단계: 불필요 요소 제거
```
광고, 네비게이션, 소셜 버튼, 댓글, 사이드바 등 제거
```

### 2단계: 본문 영역 찾기
```
article, .article-body, [itemprop="articleBody"] 등
우선순위 기반으로 본문 영역 탐지
```

### 3단계: 텍스트 정리
```
- 연속 공백 제거
- "Subscribe", "Share" 등 불필요 패턴 제거
- 짧은 문단 필터링
```

### 4단계: 길이 제한 적용
```
설정된 최대 길이로 자르기 (기본 5000자)
```

---

## 💡 사용 예시

### Agent Tool로 사용
```python
# System Prompt에 추가
"Use extract_content tool to fetch article body from news URLs"

# Agent가 자동으로 호출
extract_content(urls=["https://example.com/news/article1"])
```

### 직접 연결
```
[GDELT Search] → [News Content Extractor] → [Agent]
     ↓                     ↓                    ↓
   URL 리스트          본문 추출            분석/요약
```

---

## 🚨 주의사항

### ❌ 지원하지 않는 URL
- **RSS/Feed URL**: `/rss`, `rss.`, `.rss` 포함 URL은 에러 반환
- **동적 렌더링 사이트**: JavaScript로만 본문 로드하는 사이트는 추출 실패 가능

### ⚠️ 사이트별 차이
- 모든 뉴스 사이트에서 100% 동작을 보장하지 않습니다
- 사이트마다 HTML 구조가 다르기 때문에 일부 사이트는 본문 추출이 불완전할 수 있습니다
- 주요 뉴스 사이트(Reuters, Bloomberg, CNBC 등)에서 테스트 완료

---

## 🐛 문제 해결

### 본문이 추출되지 않아요
**원인**: 사이트가 특수한 구조 사용  
**해결**: 해당 사이트의 CSS 선택자를 `CONTENT_SELECTORS`에 추가

### 광고/버튼이 섞여 나와요
**원인**: 새로운 패턴의 불필요 요소  
**해결**: 해당 요소를 `UNWANTED_SELECTORS`에 추가

### 중요한 내용이 잘려요
**원인**: 과도한 필터링 또는 길이 제한  
**해결**: 
- `Remove Short Paragraphs` → False
- `Max Content Length` 값 증가

---

## 🔧 커스터마이징

### 특정 사이트 지원 추가
`news_content_extractor.py` 파일의 클래스 상수 수정:

```python
CONTENT_SELECTORS = [
    'article',
    '.article-body',
    '.your-site-selector',  # 여기에 추가
]
```

### 제거 패턴 추가
```python
UNWANTED_SELECTORS = [
    '.ad',
    '.your-unwanted-element',  # 여기에 추가
]
```

---

## 📚 참고

- 코드: `custom_components/news_content_extractor.py`
- [BeautifulSoup 문서](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [CSS 셀렉터 가이드](https://developer.mozilla.org/ko/docs/Web/CSS/CSS_Selectors)
