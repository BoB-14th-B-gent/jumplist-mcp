# JumpList MCP 설치 가이드

완전한 설치 가이드입니다. 단계별로 따라하시면 10분 내에 설치 완료할 수 있습니다.

## 📋 사전 준비

### 필수 소프트웨어 확인

```powershell
# PowerShell에서 실행

# Python 버전 확인 (3.8 이상 필요)
python --version

# Git 확인 (선택)
git --version

# Windows 버전 확인
winver
```

**Python이 없다면:**
- https://www.python.org/downloads/
- "Add Python to PATH" 체크 필수!

---

## 🚀 설치 단계

### 1단계: 프로젝트 다운로드 (2분)

#### 방법 A: Git 사용 (권장)

```powershell
# 원하는 위치로 이동
cd D:\projects

# 저장소 클론
git clone https://github.com/YOUR_USERNAME/jumplist-mcp.git
cd jumplist-mcp
```

#### 방법 B: ZIP 다운로드

1. GitHub에서 "Code" → "Download ZIP"
2. 압축 해제: 

---

### 2단계: Python 가상환경 생성 (2분)

```powershell
# 프로젝트 디렉터리로 이동
cd D:\projects\jumplist-mcp

# 가상환경 생성
python -m venv venv

# 생성 확인
dir venv\Scripts\python.exe
```



---

### 3단계: 가상환경 활성화 (1분)

#### PowerShell

```powershell
# 실행 정책 설정 (최초 1회만)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 가상환경 활성화
.\venv\Scripts\Activate.ps1
```



### 4단계: 의존성 설치 (2분)

```powershell
# pip 업그레이드
pip install --upgrade pip

# MCP 설치
pip install mcp

# 설치 확인
pip show mcp
```

**예상 출력:**
```
Name: mcp
Version: 1.x.x
Summary: Model Context Protocol
...
```

---

### 5단계: JLECmd.exe 설치 (3분)

#### 다운로드

1. 브라우저에서 열기:
   ```
   https://f001.backblazeb2.com/file/EricZimmermanTools/JLECmd.zip
   ```

2. ZIP 파일 저장 (약 2MB)

#### 설치

```powershell
# tools 디렉터리 생성
mkdir tools\JLECmd

# ZIP 압축 해제
# 다운로드폴더\JLECmd.zip을 압축 해제

# JLECmd.exe 복사

# 설치 확인
.\tools\JLECmd\JLECmd.exe --version
```

**예상 출력:**
```
JLECmd version 1.x.x.x
```

---

## ✅ 설치 검증

### 체크리스트

```powershell
# 1. Python 경로 확인
where.exe python


# 2. MCP 설치 확인
pip list | findstr mcp
# 예상: mcp    1.x.x

# 3. JLECmd.exe 확인
Test-Path .\tools\JLECmd\JLECmd.exe
# 예상: True

# 4. 디렉터리 구조 확인
tree /F /A
```

**예상 구조:**
```
jumplist-mcp
├── jumplist_mcp_server.py
├── venv\
│   └── Scripts\
│       └── python.exe
└── tools\
    └── JLECmd\
        └── JLECmd.exe
```

---

## 🔧 Claude Desktop 설정

### 1. 설정 파일 위치

```powershell
# 설정 파일 열기
notepad %APPDATA%\Claude\claude_desktop_config.json
```

**파일이 없다면 새로 생성:**
```powershell
# 디렉터리 생성
mkdir %APPDATA%\Claude -Force

# 파일 생성
echo {} > %APPDATA%\Claude\claude_desktop_config.json
```

### 2. MCP 서버 설정 추가

```json
{
  "mcpServers": {
    "jumplist": {
      "command": "D:\\projects\\jumplist-mcp\\venv\\Scripts\\python.exe",
      "args": [
        "D:\\projects\\jumplist-mcp\\jumplist_mcp_server.py"
      ]
    }
  }
}
```

**⚠️ 중요:**
- 경로는 **절대 경로**
- 백슬래시는 **이중** (`\\`)
- **venv의 python.exe** 사용

### 3. 경로 확인 및 변경

```powershell
# 현재 프로젝트 경로 확인
pwd

# 예시 경로
D:\projects\jumplist-mcp

# 설정 파일에서 경로 교체
# YOUR_PATH → 실제 경로로 변경
```

### 4. JSON 유효성 검증

https://jsonlint.com/ 에서 검증

또는:

```powershell
# PowerShell로 검증
Get-Content %APPDATA%\Claude\claude_desktop_config.json | ConvertFrom-Json
```

**에러 없으면 OK!**

---

## 🎯 Claude Desktop 연결

### 1. Claude Desktop 재시작

```powershell
# 완전 종료
taskkill /F /IM Claude.exe

# 프로세스 종료 확인
Get-Process | Where-Object {$_.Name -like "*claude*"}
# 출력 없으면 OK

# 3초 대기
Start-Sleep -Seconds 3

# Claude Desktop 실행 (시작 메뉴에서)
```

### 2. 연결 확인

Claude Desktop에서 메시지 입력:

```
jumplist MCP 도구가 연결되었는지 확인해줘.
```

**예상 응답:**
```
✅ JumpList MCP 서버가 연결되어 있습니다.

사용 가능한 도구:
- parse_jumplists
- get_jumplist_statistics
- search_jumplists
- get_cache_info
- clear_cache
```

### 3. 첫 번째 테스트

```
D:\projects\jumplist-mcp\test-data\jumplists 디렉터리의
JumpList 통계를 요약해줘.
```

**성공 시:**
```
📊 JumpList 통계

총 이벤트: X개
...
```

---

## 🐛 문제 해결

### 문제 1: venv 활성화 실패

**에러:**
```
cannot be loaded because running scripts is disabled
```

**해결:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### 문제 2: MCP가 설치 안됨

**에러:**
```
ModuleNotFoundError: No module named 'mcp'
```

**해결:**
```powershell
# venv 활성화 확인
# 프롬프트에 (venv) 표시되어야 함

# MCP 재설치
pip install --force-reinstall mcp
```

---

### 문제 3: JLECmd.exe not found

**에러:**
```
FileNotFoundError: JLECmd.exe not found
```

**해결:**
```powershell
# JLECmd.exe 경로 확인
Test-Path D:\projects\jumplist-mcp\tools\JLECmd\JLECmd.exe

# False면 다시 다운로드
# https://f001.backblazeb2.com/file/EricZimmermanTools/JLECmd.zip
```

---

### 문제 4: Claude에 도구가 안 보임

**원인:** 설정 파일 경로 오류

**해결:**
```powershell
# 1. Python 경로 확인
D:\projects\jumplist-mcp\venv\Scripts\python.exe
Test-Path "위 경로"

# 2. 서버 파일 경로 확인
D:\projects\jumplist-mcp\jumplist_mcp_server.py
Test-Path "위 경로"

# 3. 설정 파일에서 백슬래시 확인
# \ → \\ (이중 백슬래시)

# 4. Claude 완전 재시작
taskkill /F /IM Claude.exe
```

---

### 문제 5: 한글 경로 문제

**에러:**
```
UnicodeDecodeError
```

**해결:**
```
경로에 한글 사용 금지!

나쁨: C:\사용자\홍길동\프로젝트\
좋음: C:\Users\username\projects\
```

---

## 📊 설치 후 체크리스트

- [ ] Python 3.8+ 설치됨
- [ ] 가상환경 생성됨
- [ ] venv 활성화 가능
- [ ] MCP 설치됨
- [ ] JLECmd.exe 설치됨
- [ ] Claude Desktop 설정 완료
- [ ] Claude 재시작함
- [ ] MCP 도구 목록 확인됨
- [ ] 첫 번째 테스트 성공

---

## 🎉 설치 완료!

축하합니다! JumpList MCP가 설치되었습니다.

### 다음 단계

1. [사용 가이드](USAGE.md) 읽기
2. 예제 시나리오 실행
3. 실제 케이스에 적용

### 도움말

- **문제 발생 시**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **GitHub Issues**: [Issues](https://github.com/min0116/jumplist-mcp/issues)

---

**Happy Analyzing! 🔍**
