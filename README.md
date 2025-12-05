# JumpList MCP Server

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)

Windows JumpList 아티팩트 분석을 위한 Model Context Protocol (MCP) 서버입니다. SQLite 캐싱을 통해 빠른 포렌식 분석을 제공합니다.

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [시스템 요구사항](#시스템-요구사항)
- [설치 방법](#설치-방법)
- [사용 방법](#사용-방법)
- [MCP 도구](#mcp-도구)
- [포렌식 워크플로우](#포렌식-워크플로우)
- [문제 해결](#문제-해결)

---

## 개요

JumpList MCP Server는 Windows JumpList 파일(AutomaticDestinations-ms, CustomDestinations-ms)을 파싱하고 분석하는 MCP 서버입니다. Claude Desktop, Cline 등 MCP를 지원하는 AI 에이전트와 통합되어 대화형 포렌식 분석을 가능하게 합니다.

### JumpList란?

Windows 7 이상에서 제공되는 최근 사용 파일 추적 기능으로, 다음 정보를 포함합니다:
- 최근 열린 파일 경로
- 파일 접근 시간 (생성/수정/접근)
- 사용한 애플리케이션
- 파일 크기 및 메타데이터

**포렌식 가치:**
- 사용자 활동 타임라인 재구성
- 삭제된 파일 흔적 발견
- USB 드라이브 사용 추적
- 애플리케이션 사용 패턴 분석

---

## 주요 기능

### ✨ 핵심 기능

- **SQLite 캐싱**: 반복 쿼리 시 100배 빠른 성능
- **증분 업데이트**: 변경된 파일만 재파싱
- **대화형 분석**: AI 에이전트를 통한 자연어 쿼리
- **포렌식 검색**: 키워드, 시간 범위, 파일 타입 필터링
- **통계 요약**: TOP 10 앱, 파일 유형, 최근 활동

### 🔧 MCP 도구 (5개)

1. `parse_jumplists` - JumpList 파싱 및 이벤트 추출
2. `get_jumplist_statistics` - 통계 요약 (TOP 10, 기간 등)
3. `search_jumplists` - 키워드 기반 검색
4. `get_cache_info` - 캐시 상태 확인
5. `clear_cache` - 캐시 초기화

---

## 시스템 요구사항

### 필수 요구사항

| 항목 | 요구사항 |
|------|----------|
| **OS** | Windows 10/11 (64-bit) |
| **Python** | 3.8 이상 |
| **메모리** | 최소 4GB RAM |
| **디스크** | 100MB (도구 + 캐시) |

### 외부 도구

- **JLECmd.exe** (Eric Zimmerman's Tools)
  - Windows JumpList 파서
  - 다운로드: https://ericzimmerman.github.io/
  - 필수 설치

### MCP 클라이언트 (선택)

- **Claude Desktop** (권장)
- **Cline** (VS Code Extension)
- 기타 MCP 지원 클라이언트

---

## 설치 방법

### 1단계: 저장소 클론

```bash
git clone https://github.com/YOUR_USERNAME/jumplist-mcp.git
cd jumplist-mcp
```

### 2단계: Python 가상환경 생성

```powershell
# 가상환경 생성
python -m venv venv

# 활성화 (PowerShell)
.\venv\Scripts\Activate.ps1

# 활성화 (CMD)
.\venv\Scripts\activate.bat
```

### 3단계: 의존성 설치

```powershell
# pip 업그레이드
pip install --upgrade pip

# MCP 설치
pip install mcp
```

### 4단계: JLECmd.exe 설치

#### 방법 A: 프로젝트 내부 (권장)

```powershell
# 1. JLECmd.zip 다운로드
# https://f001.backblazeb2.com/file/EricZimmermanTools/JLECmd.zip

# 2. 디렉터리 생성
mkdir tools\JLECmd

# 3. JLECmd.exe 복사
# 다운로드폴더\JLECmd.exe → .\tools\JLECmd\JLECmd.exe
```

### 5단계: 설치 확인

```powershell
# Python 버전 확인
python --version

# MCP 설치 확인
pip show mcp

# JLECmd 실행 확인
.\tools\JLECmd\JLECmd.exe --version
```

---

## 사용 방법

### Claude Desktop 통합

#### 1. 설정 파일 편집

```powershell
notepad %APPDATA%\Claude\claude_desktop_config.json
```

#### 2. MCP 서버 추가

```json
{
  "mcpServers": {
    "jumplist": {
      "command": "D:\\path\\to\\jumplist-mcp\\venv\\Scripts\\python.exe",
      "args": [
        "D:\\path\\to\\jumplist-mcp\\jumplist_mcp_server_v2.py"
      ]
    }
  }
}
```

**⚠️ 주의사항:**
- 경로는 절대 경로로 지정
- 백슬래시는 이중으로 (`\\`)
- `venv\Scripts\python.exe` 경로 사용

#### 3. Claude Desktop 재시작

```powershell
# 완전 종료
taskkill /F /IM Claude.exe

# 3초 대기 후 재실행
```

#### 4. 연결 확인

Claude Desktop에서:
```
jumplist MCP 도구가 연결되었는지 확인해줘.
```

---

## MCP 도구

### 1. parse_jumplists

JumpList 파일을 파싱하고 이벤트를 반환합니다.

**Claude 사용 예:**
```
D:\forensics\case001\jumplists 디렉터리를 분석해서
최신 50개 이벤트를 보여줘.
```

---

### 2. get_jumplist_statistics

전체 JumpList 데이터의 통계를 요약합니다.

**Claude 사용 예:**
```
D:\forensics\case001\jumplists 디렉터리의
전체 통계를 요약해줘.
```

**예상 출력:**
```
📊 JumpList 통계 요약

총 이벤트: 2,456개
분석 기간: 2025-10-15 ~ 2025-12-04

💻 TOP 10 애플리케이션:
1. explorer.exe - 892회 (36.3%)
2. chrome.exe - 654회 (26.6%)
...
```

---

### 3. search_jumplists

키워드로 파일을 검색합니다.

**Claude 사용 예:**
```
"confidential" 키워드가 포함된 파일을 찾아줘.
```

---

### 4. get_cache_info

SQLite 캐시 상태를 확인합니다.

**Claude 사용 예:**
```
JumpList 캐시 정보를 보여줘.
```

---

### 5. clear_cache

캐시를 초기화합니다.

**Claude 사용 예:**
```
JumpList 캐시를 삭제해줘.
```

---

## 포렌식 워크플로우

### 시나리오 1: 디스크 이미지 분석

```
# Claude에게 질문

1. 전체 통계를 요약해줘.
2. 가장 많이 사용한 애플리케이션 TOP 5를 보여줘.
3. USB 드라이브(E:\)에서 접근한 파일을 찾아줘.
4. "confidential" 키워드를 포함한 파일을 찾아줘.
```

### 시나리오 2: 침해사고 대응

**민감 파일 접근:**
```
"confidential", "secret" 키워드를 포함한 파일을 찾아줘.
```

**외부 드라이브 사용:**
```
E:\, F:\ 드라이브의 파일 접근 기록을 보여줘.
```

**업무 시간 외 활동:**
```
밤 10시 이후 접근한 파일을 보여줘.
```

---

## 문제 해결

### 문제 1: "ModuleNotFoundError: No module named 'mcp'"

```powershell
cd jumplist-mcp
.\venv\Scripts\Activate.ps1
pip install mcp
```

### 문제 2: "JLECmd.exe not found"

```powershell
# JLECmd.exe 존재 확인
Test-Path .\tools\JLECmd\JLECmd.exe
```

### 문제 3: Claude Desktop에 도구가 안 보임

```powershell
# 설정 확인
type %APPDATA%\Claude\claude_desktop_config.json

# Claude 재시작
taskkill /F /IM Claude.exe
```

---

## 디렉터리 구조

```
jumplist-mcp/
├── jumplist_mcp_server_v2.py      # 메인 MCP 서버
├── venv/                           # Python 가상환경
├── tools/                          # 외부 도구
│   └── JLECmd/
│       └── JLECmd.exe
├── .jumplist_cache.db             # SQLite 캐시
└── README.md                       # 이 문서
```

---

## 라이선스

MIT License

---

## 감사의 말

- **Eric Zimmerman** - JLECmd.exe 개발
- **Anthropic** - MCP 프로토콜 및 Claude Desktop
- **포렌식 커뮤니티** - JumpList 연구

---

## 참고 자료

- [ForensicsWiki - Jump Lists](https://forensicswiki.xyz/wiki/index.php?title=Jump_Lists)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Eric Zimmerman's Tools](https://ericzimmerman.github.io/)

---

**⭐ 이 프로젝트가 유용하다면 Star를 눌러주세요!**
