# LLM Agent Workshop: Langflow & GDELT

Langflow와 GDELT 데이터를 활용해 AI 에이전트를 구축해보는 실습 워크샵입니다.  
현재 **`main` 브랜치**는 실습 환경 설정 및 UI 투어를 위한 기본 상태입니다.

## 🚀 빠른 시작 (Replit)

1. **실행 (Run)**: 화면 상단의 `Run` 버튼을 클릭하세요.
   - 자동으로 의존성을 설치하고 Langflow를 실행합니다.
   - 실행 명령: `uv run langflow run`
2. **접속**: 터미널에 표시되는 URL을 통해 Langflow UI에 접속합니다.

## 📚 실습 가이드

강의 진행에 따라 **Git Branch**를 변경하며 실습합니다.

- **`main`** (Current): 환경 구성 및 Langflow UI 익히기
- **`01-news-agent`** (Next): GDELT 뉴스 데이터 분석 에이전트 구축

---

## 🔧 트러블슈팅 (Troubleshooting)

### 1. Git이 원격과 어긋나는 경우
강의장 환경에서 로컬 변경사항 등으로 Git 충돌이 발생하면 아래 명령어로 원격 상태를 강제 동기화하세요.
(주의: 로컬 작업 내용이 삭제될 수 있습니다)

```bash
# 원격 저장소 확인
https://github.com/Yo-sure/llm-agent-workshop

# 원격 main 브랜치로 강제 리셋
git checkout -B main origin/main
```

### 2. Replit 가상환경(venv) 위치 확인
Replit 환경에서 `uv`가 사용하는 가상환경 위치는 다음과 같습니다.

```bash
~/workspace$ echo $UV_PROJECT_ENVIRONMENT
/home/runner/workspace/.pythonlibs
```
