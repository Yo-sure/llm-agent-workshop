# GDELT Doc Search Component

GDELT Doc Search는 전 세계 뉴스·블로그를 수집·분석하는 **GDELT DOC 2.0 API**를 LangFlow에서 바로 활용할 수 있는 노드입니다.
**두 가지 주요 기능**을 지원합니다:

* **ArtList** → 기사 목록을 JSON → DataFrame 변환
* **Timeline**\* → 특정 주제의 시간축 지표(기사량, 톤, 언어/국가 분포)를 DataFrame 변환

---

## 🚀 퀵스타트

### 1. 최신 NVIDIA 뉴스

```
Query: NVIDIA
Mode: ArtList
Max Records: 10
```

→ 최근 NVIDIA 관련 기사 10개를 DataFrame으로 반환

### 2. 특정 도메인 + 키워드 검색

```
Query: (NVIDIA OR NVDA) AND "AI chip"
Domains: ["reuters.com", "bloomberg.com"]
Mode: ArtList
```

→ 로이터/블룸버그에서만 NVIDIA AI 칩 관련 기사 검색

### 3. 시간대별 트렌드 분석

```
Query: ChatGPT
Mode: timelinevol
Timespan: 7days
```

→ 최근 7일간 ChatGPT 언급량 추세

### 4. 다국가 이슈 모니터링

```
Query: "climate change"
Mode: timelinesourcecountry
Countries: ["US", "KR", "JP"]
```

→ 국가별 기후변화 보도량 변화

---

## 📋 입력값(Inputs)

| 필드                | 타입         | 기본값      | 설명                                         |
| ----------------- | ---------- | -------- | ------------------------------------------ |
| `query`           | string     | -        | 검색식. 예: `NVIDIA`, `(NVIDIA OR NVDA)`       |
| `domains`         | list\[str] | -        | 특정 도메인 필터. 예: `["reuters.com"]`            |
| `languages`       | list\[str] | -        | 언어 필터. 예: `["English","Korean"]`           |
| `countries`       | list\[str] | -        | 발행국가(FIPS). 예: `["US","KR"]`               |
| `mode`            | enum       | ArtList  | `ArtList`, `timelinevol`, `timelinetone` 등 |
| `timespan`        | string     | -        | 상대 기간. 예: `7days`, `24hours`               |
| `start_datetime`  | string     | -        | 시작 시각(절대). `YYYYMMDDHHMMSS`                |
| `end_datetime`    | string     | -        | 종료 시각(절대). `YYYYMMDDHHMMSS`                |
| `maxrecords`      | int        | **5**    | 반환 개수(1\~250). 모든 모드 공통 적용                 |
| `sort`            | enum       | DateDesc | ArtList 전용. `DateDesc` / `DateAsc`         |
| `timeline_smooth` | int        | 0        | Timeline 전용. 0=평활화 없음                      |
| `timeout`         | int        | 25       | 요청 타임아웃(초)                                 |
| `use_cache`       | bool       | True     | HTTP 캐시 사용 여부                              |
| `cache_ttl`       | int        | 300      | 캐시 TTL(초)                                  |

**⚠️ 주의**

* `timespan`과 `start_datetime`/`end_datetime` 중 **하나만** 설정하세요.
* `maxrecords`는 ArtList + Timeline 모두에 공통 적용됩니다.

---

## 📤 출력(Outputs)

**Results** → DataFrame

### ArtList 스키마

| 컬럼            | 설명     |
| ------------- | ------ |
| title         | 기사 제목  |
| url           | 기사 URL |
| seendate      | 수집 일시  |
| domain        | 도메인    |
| language      | 언어     |
| sourcecountry | 발행국가   |

### Timeline 스키마

| 컬럼     | 설명                 |
| ------ | ------------------ |
| series | 시리즈명               |
| date   | 날짜                 |
| value  | 값                  |
| 기타     | 모드별 언어·국가 분포 필드 포함 |

---

## 🎯 모드별 활용 가이드

| 모드                      | 의미        | 언제 사용                | 주요 컬럼                          |
| ----------------------- | --------- | -------------------- | ------------------------------ |
| `ArtList`               | 기사 목록     | 최신 기사 수집, 도메인/언어 필터링 | title, url, seendate, domain   |
| `timelinevol`           | 시간대별 기사 수 | 급증 탐지, 트렌드 분석        | series, date, value            |
| `timelinevolraw`        | 원시 기사량    | 전체 기사 흐름 확인          | series, date, value            |
| `timelinetone`          | 톤(감정 점수)  | 긍/부정 전환점 분석          | series, date, value            |
| `timelinelang`          | 언어 분포     | 언어권 확산 분석            | series, date, value, lang 등    |
| `timelinesourcecountry` | 국가별 분포    | 지역별 이슈 집중도 분석        | series, date, value, country 등 |

---

## ✍️ 쿼리 작성 팁

1. **OR 조건엔 괄호 사용**

   ```
   ✅ (NVIDIA OR NVDA)
   ❌ NVIDIA OR NVDA
   ```
2. **필터 자동 적용**

   * `domains=["reuters.com"]` → `domain:reuters.com`
   * `languages=["English"]` → `sourcelang:English`
3. **기간 설정 전략**

   * 간단히: `timespan="7days"`
   * 정밀히: `start_datetime="20250701000000"`, `end_datetime="20250731235959"`

---

## 🔧 사용 팁

* **실시간 데이터 필요 시** → `use_cache=False`
* **LLM Tool에서 권장값** → `maxrecords=5~20`
* 복잡한 쿼리 + 긴 기간일 경우 `timeout`을 늘려야 함

---

## 🐛 문제 해결 가이드

| 문제    | 원인                | 해결책                           |
| ----- | ----------------- | ----------------------------- |
| 빈 결과  | 쿼리 과도한 제한 / 기간 짧음 | `timespan` 확대 또는 조건 단순화       |
| 타임아웃  | 긴 기간 + 복잡 쿼리      | `timeout` 늘리거나 `timespan` 줄이기 |
| 파싱 오류 | GDELT API 구조 변경   | API 응답 구조 로그 확인 후 수정          |

---

## 📚 참고 자료

* [GDELT DOC 2.0 API 문서](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
* [GDELT 프로젝트 메인](https://www.gdeltproject.org/)
* [LangFlow 커스텀 컴포넌트 가이드](https://docs.langflow.org/)

---
