# News Content Extractor

뉴스 웹사이트에서 본문 내용을 추출하는 LangFlow 커스텀 컴포넌트입니다.

HTML에서 불필요한 요소(네비게이션, 광고, 소셜 버튼 등)를 제거하고 기사 본문을 추출합니다.

## 📦 컴포넌트 개요

### **주요 기능**:
- HTML에서 기사 본문 추출
- 불필요한 요소 자동 제거 (네비게이션, 광고, 소셜 버튼 등)
- 페이지 제목과 메타 설명 추출
- 여러 URL 일괄 처리
- 개별 URL 실패 시에도 다른 URL 계속 처리

---

## 🔧 주요 기능

### 1. 불필요한 요소 제거
다음 요소들을 HTML에서 제거합니다:
- 페이지 구조: `nav`, `header`, `footer`
- 네비게이션: `.nav`, `.navigation`, `.menu`
- 광고: `.ad`, `.advertisement`, `.ads`
- 소셜 버튼: `.social`, `.share`, `.sharing`
- 기타: `.sidebar`, `.comments`, `script`, `style` 등

### 2. 본문 영역 탐지
다음 CSS 셀렉터로 본문 영역을 찾습니다:
- `article` (HTML5 표준)
- `.article-body`, `.article-content`
- `.story-body`, `.story-content`
- `.post-content`, `.post-body`
- `.content`, `.main-content`
- `[data-module="ArticleBody"]` (CNBC)
- `[itemprop="articleBody"]` (Schema.org)

### 3. 텍스트 후처리
- 연속된 공백을 하나로 정리
- 불필요한 패턴 제거 (Skip Navigation, Subscribe 등)
- 짧은 문단 필터링 (설정 가능)

---

## 🎯 사용 방법

### LangFlow에서 사용
1. "News Content Extractor" 컴포넌트 추가
2. URLs 필드에 뉴스 기사 URL 입력 (여러 개 가능)
3. 설정 조정:
   - Max Content Length: 추출할 최대 글자 수 (기본값: 5000)
   - Include Metadata: 제목, 설명 포함 여부 (기본값: True)
   - Remove Short Paragraphs: 짧은 문단 제거 여부 (기본값: True)
   - Timeout: 요청 타임아웃 초 (기본값: 15)
4. 실행하여 DataFrame 결과 받기

### 테스트 실행
```bash
uv run custom_components/news_content_extractor.py
```

---

## 📋 컴포넌트 설정

### 입력 파라미터

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `urls` | list[str] | - | 뉴스 기사 URL 목록 (필수) |
| `max_content_length` | int | 5000 | 추출할 최대 콘텐츠 길이 |
| `timeout` | int | 15 | 요청 타임아웃 (초) |
| `include_metadata` | bool | True | 제목, 설명 등 메타데이터 포함 여부 |
| `remove_short_paragraphs` | bool | True | 짧은 문단 제거 여부 |

### 출력 DataFrame

| 필드 | 타입 | 설명 |
|------|------|------|
| `url` | str | 원본 URL |
| `title` | str | 페이지 제목 |
| `description` | str | 메타 설명 |
| `content` | str | 추출된 본문 |
| `content_length` | int | 추출된 콘텐츠 길이 |
| `paragraphs_count` | int | 문단 수 |
| `success` | bool | 추출 성공 여부 |
| `error` | str | 오류 메시지 (실패 시) |

---

## 🔧 추출 방식

이 컴포넌트는 범용 추출 로직을 사용합니다:

1. **일반적인 CSS 셀렉터**로 본문 영역 탐지
2. **공통적인 불필요 요소** 제거
3. **기본적인 텍스트 후처리**

사이트마다 구조가 다르므로 모든 사이트에서 완벽하게 동작하지는 않을 수 있습니다. 특정 사이트에 최적화하려면 해당 사이트의 CSS 셀렉터를 추가로 구현해야 합니다.

---

## 🐛 문제 해결

### 자주 발생하는 문제

#### 본문을 찾지 못하는 경우
- **원인**: 사이트가 특수한 구조를 사용
- **해결**: 해당 사이트의 CSS 셀렉터를 코드에 추가 필요

#### 불필요한 텍스트가 포함되는 경우  
- **원인**: 새로운 패턴의 불필요 요소
- **해결**: 해당 패턴을 제거 로직에 추가 필요

#### 중요한 내용이 제거되는 경우
- **원인**: 과도한 필터링
- **해결**: 필터링 규칙 조정 필요

### 디버깅
컴포넌트의 로그를 확인하여 처리 과정을 파악할 수 있습니다.

---

## 📚 참고 자료

- [BeautifulSoup 공식 문서](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [CSS 셀렉터 가이드](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Selectors)
