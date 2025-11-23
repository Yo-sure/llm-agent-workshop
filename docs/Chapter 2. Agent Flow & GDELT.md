## 2. Langflow Agent Flow 실습

>[!check] 간단한 UI 투어 및 Agent Flow Hands On 진행
### 1. 도구 호출의 개념과 Agent의 구성 요소 시각적으로 확인하기

![[Pasted image 20250827014504.png]]

### 2. Agent의 각 구성 요소 쪼개보기

*Tavily 검색 API Key 발급받기 (월 1000회 무료)*
[Tavily API Platform](https://app.tavily.com/home)


>[!todo] Research Agent 살펴보기

![[Pasted image 20251123181353.png|Research Agent의 구조]]

![[Pasted image 20251123181031.png|ResearchAgent를 통한 조사 결과]]




### 3. 추가 도구 만들어보기
[The GDELT Project](https://www.gdeltproject.org/)
![[Pasted image 20250827014721.png]]
## GDELT 프로젝트란?

- **정의**: GDELT(Global Database of Events, Language, and Tone)는 전 세계 뉴스 미디어를 통해 드러나는 **인간 사회의 사건, 정서, 맥락**을 컴퓨터가 이해할 수 있는 형태로 실시간 수집하는 오픈 데이터 플랫폼이에요. 매 15분마다 업데이트되고, 100개 이상의 언어로 제공되는 광범위한 데이터 소스가 기반이에요.
  
- **시계열적 아카이브**: 1979년 1월 1일부터의 데이터를 보유하고 있고, 이를 통해 몇십 년간의 글로벌 트렌드를 분석할 수 있어요.
  
- **데이터 구조**:
    
    - **이벤트 데이터베이스**: 폭동, 시위, 외교 교류 등 300개 이상의 물리적 사건 카테고리를 구조화된 형태로 기록[GDELT Project](https://www.gdeltproject.org/?utm_source=chatgpt.com)[GitHub](https://github.com/edumunozsala/GDELT-Events-Data-Eng-Project?utm_source=chatgpt.com).
        
    - **글로벌 지식 그래프(Global Knowledge Graph, GKG)**: 뉴스에 등장하는 인물, 조직, 장소, 주제, 감정 등을 추출하여 구조화된 지식 네트워크를 형성[GDELT Project+1](https://www.gdeltproject.org/?utm_source=chatgpt.com).
        

---

## 기능 & 기술적 특징

[GDELT DOC 2.0 API 데뷔! – GDELT 프로젝트](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)

- **통번역 및 감정 분석**:
    
    - 비영어권 뉴스는 65개 언어에서 영어로 실시간 번역되고, 이를 바탕으로 뉴스의 정서(감정)와 주제를 분석해요.
    - 감정 분석은 2,300여 개 이상 감정/주제를 활용하며, 다층적인 감정 인사이트를 제공합니다.

- **다양한 미디어 포맷과 시각화**:
    
    - 텍스트 외에도 이미지, 비디오, 인용문, 수치 정보 등도 수집하고 분석해요.        
    - 이벤트 히트맵, 네트워크 다이어그램, 타임라인 등의 시각화 도구를 제공하여 **연구·분석·정책 환경**에서 유용하게 활용 가능해요.

---

## 활용 사례 & 영향력

- **학계 및 연구**:
    
    - 정치현상 분석, 재난 보도 패턴, 이미지 기반 감정 표현 등 다양한 연구에서 활용되며, 페인팅틱한 분석이 가능한 데이터셋으로 평가받고 있어요.[위키백과+2위키백과+2](https://en.wikipedia.org/wiki/GDELT_Project?utm_source=chatgpt.com)

- **실시간 상황 인식 및 응답**:
    
    - 위기 발생 시 GDELT 데이터를 통해 즉각적 상황 파악 및 대비가 가능 – 예를 들어 정책 반응 모니터링, 위기 대응 등.[GitHub+1](https://github.com/edumunozsala/GDELT-Events-Data-Eng-Project?utm_source=chatgpt.com)[GitHub+14GDELT Project+14GDELT Project+14](https://www.gdeltproject.org/solutions.html?utm_source=chatgpt.com)

- **인플루언서·트렌드 분석**:
    
    - 특정 주제나 지역, 인물을 중심으로 **중요한 영향력자(Influencers)** 식별 및 사회적 동향 분석하는 데 활용될 수 있어요.[GDELT Project](https://www.gdeltproject.org/solutions.html?utm_source=chatgpt.com)


---

![[Pasted image 20250827020202.png]]
![[Pasted image 20250827020342.png]]
![[Pasted image 20250827020638.png]]
![[Pasted image 20250827020608.png]]
![[Pasted image 20250827020617.png]]


>[!check] (이후 실습으로 대체) 함께 코드 살펴보기

![[Pasted image 20250827021054.png]]

>[!danger] Agent 도구는 다 같은 코드인데, 인터페이스는 모두 제각각!


