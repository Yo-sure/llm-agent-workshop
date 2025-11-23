## 1. 개발 환경 구성 (Windows + WSL2 + Ubuntu 24.04)

오늘 실습은 **Windows 10/11**에서 **WSL2**를 활용해 **Ubuntu 24.04** 환경을 구성하고, 그 위에서 `uv`로 Langflow OSS(1.6.8)를 실행하는 방식입니다. 

Windows에 설치된 Python/Anaconda 환경과 독립적으로 작동하기 때문에 깔끔하게 시작할 수 있습니다.



### 1-1. WSL2 설치하기

0. 윈도우에서 wsl 시작하기
![[Pasted image 20251123122814.png|window11에서 wsl 검색 후 클릭]]

만약 아래 메시지 발생 시 `아무 키` 나 눌러서 하위시스템 설치 후 => 재부팅 진행해주세요.
![[Pasted image 20251123123003.png|wsl:하위 시스템이 설치되어있지 않습니다. 경고]]

1. **PowerShell을 관리자 권한으로 실행**해주세요.
![[Pasted image 20251123123241.png|powershell 관리자로 실행 장면]]
2. 아래 명령어를 입력해 WSL2와 Ubuntu 24.04를 설치합니다.
   ```powershell
   wsl --set-default-version 2
   wsl --install -d Ubuntu-24.04
   ```
3. 설치가 완료되면 사용자명과 비밀번호를 설정하라는 메시지가 나옵니다.
   
  ![[Pasted image 20251123123432.png|Ubuntu 설치되는 장면]]
  
설치 완료 후, 자동 실행되지 않으면 직접 실행
```PowerShell
wsl -d Ubuntu-24.04
```

![[Pasted image 20251123123642.png]]
계정정보(자율) : sdsclass
비밀번호: 1234

> [!check] `wsl --install` 이후 최초 부팅 시 설정한 **Ubuntu 계정/비밀번호**를 반드시 기록해 두세요.

아래까지 하면 완료
![[Pasted image 20251123123742.png|wsl 진입한 장면]]

4. 필요 시 재부팅을 진행합니다.



### 1-2. Ubuntu 초기화 및 필수 도구 설치
1. 시작 메뉴에서 "WSL" 또는 "Ubuntu 24.04"를 검색해 실행합니다.

2. **(선택) 패키지 다운로드 속도 개선 - Kakao Mirror 설정**  
   네트워크 환경이 느린 경우, 한국 내 미러 서버로 변경하면 설치 속도가 크게 향상됩니다.

 *기존 설정 백업*
```bash
sudo cp /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.backup
```

*Kakao Mirror로 변경 (archive.ubuntu.com → mirror.kakao.com)*
```bash
sudo sed -i 's|http://archive.ubuntu.com|http://mirror.kakao.com|g' /etc/apt/sources.list.d/ubuntu.sources
   ```
  => 한국 환경에서만 미러 위치를 한국 CDN으로.
   
   > [!tip] 이 단계는 선택사항입니다. 건너뛰어도 실습 진행에는 문제 없지만, 설치 시간이 다소 길어질 수 있습니다.

*백업 복구(필요한 경우만)*
``` bash
sudo cp /etc/apt/sources.list.d/ubuntu.sources.backup /etc/apt/sources.list.d/ubuntu.sources
```

3. 터미널에서 아래 명령어로 최신 패키지와 개발 도구를 설치합니다.
```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install build-essential curl wget git -y
```
![[Pasted image 20251123130308.png|wsl에서 로딩바가 차오르며 설치중인 모습]]

4. Python 패키지 관리 도구인 `uv`를 설치한 후, 셸을 재시작합니다.
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec bash
uv --version
```

![[Pasted image 20251123130401.png|Ubuntu 터미널에서 `sudo apt update` 를 실행한 화면]]
``` bash
source $HOME/.local/bin/env
```


5. Langflow가 필요로 하는 Python 3.12를 미리 설치해 둡니다.
```bash
uv python install 3.12
```

### 1-3. VS Code와 Git 연동

1. Windows에 **VS Code**를 설치한 후, **WSL 확장(Remote - WSL)** 을 추가합니다.
   [Download Visual Studio Code - Mac, Linux, Windows](https://code.visualstudio.com/download)
   ![[Pasted image 20251123131804.png|확장 설치 캡쳐]]

2. VS Code 왼쪽 하단의 `><` 아이콘을 클릭한 뒤 **"WSL: Ubuntu-24.04에 새 창 열기"** 를 선택합니다.
![[Pasted image 20251123132321.png|remote 연결 장면]]

3. 터미널을 열고(단축키: `` Ctrl+` ``) 실습 저장소를 클론합니다.
   ```bash
   mkdir -p ~/work && cd ~/work
   git clone https://github.com/Yo-sure/llm-agent-workshop.git
   cd llm-agent-workshop
   ```
![[Pasted image 20251123132609.png|터미널 설치장면]]

4. 폴더에서 열어줍니다.
   ![[Pasted image 20251123132809.png]]
5. VS Code 확장 탭에서 **Python**, **Jupyter**, **Black Formatter**를 찾아 **"Install on WSL"** 버튼으로 설치합니다.
![[Pasted image 20251123133001.png|확장 설치 화면]]

### 1-4. Langflow OSS 실행하기
1. 프로젝트 루트에서 가상환경을 생성하고 의존성을 설치합니다.
   ```bash
   uv venv .venv
   uv sync
   ```
   의존성 설치에는 몇 분이 소요될 수 있습니다

2. 설치되는 동안 코드의 python 가상환경을 에디터에 묶어줍시다.
   `ctrl + shift + p` :  python select interpreter 검색
![[Pasted image 20251123133407.png|select interpreter 장면]]
![[Pasted image 20251123133500.png|설치한 .venv 선택하는 장면]]

3. Langflow 버전을 확인한 후 실행합니다.
```bash
uv run langflow --version   # 1.6.8 출력 확인
```

``` bash
uv run langflow run
```
3. 터미널에 표시되는 URL(`http://127.0.0.1:7860`)을 브라우저에서 열면 Langflow UI가 나타납니다.

![[Pasted image 20251123134504.png|terminal에 running중인 langflow]]

![[Pasted image 20251123134620.png]]

![[Pasted image 20251123134927.png|langflow 진입화면]]
### 1-5. 브랜치 로드맵
실습은 Git 브랜치를 이동하며 진행됩니다. 각 단계에 맞는 코드와 예제가 준비되어 있습니다.

*예시*

| 단계              | 설명                | 명령                           |
| --------------- | ----------------- | ---------------------------- |
| `main`          | WSL 환경 세팅 및 UI 투어 | `git checkout main`          |
| `01-news-agent` | GDELT 뉴스 분석 도구 실습 | `git checkout 01-news-agent` |

LLM API 키는 실습 중 제공되는 별도 링크(Notion)에서 확인하실 수 있습니다.

https://bit.ly/251124AGENT


> [!check] API 키는 `.env` 파일 또는 Langflow 환경 변수 입력란에만 보관해 주세요. Git에 절대 올리지 마세요.

---

>[!todo] Simple Agent 만들어보기

---
## 다음 단계

환경 설정이 완료되었습니다! 이제 **Chapter 2. Agent Flow & GDELT** 문서로 이동해서 실습을 진행합니다.
