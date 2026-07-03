# SoVITS Control Bridge

GPT-SoVITS API에 텍스트를 보내고, 생성된 음성을 로컬 PC에서 재생하는 작은 브릿지입니다.

Open-LLM-VTuber 없이도 에이전트 답변, 뉴스 브리핑, 직접 입력한 문장을 GPT-SoVITS 목소리로 들을 수 있게 만드는 것이 목표입니다. 클립보드 감시는 사용하지 않습니다. 읽히는 텍스트는 `/api/speak`로 명시적으로 보낸 내용뿐입니다.

## 주요 기능

- `http://127.0.0.1:18088` 로컬 웹 UI
- GPT-SoVITS `/tts` 호출 및 WAV 파일 저장
- PyAudio 기반 순차 재생 큐
- GPT weight, SoVITS weight, reference audio, prompt text를 함께 바꾸는 모델 프로필
- 한국어 Windows 콘솔을 위한 UTF-8 PowerShell 헬퍼
- SaveTicker / FinanceAgentGUI 뉴스를 Open-LLM-VTuber 쪽으로 읽히는 보조 브릿지

## 폴더 배치

기본 스크립트는 아래처럼 같은 루트에 관련 프로젝트가 있다고 가정합니다.

```text
VTuber/
  sovits-control-server.py
  GPT-SoVITS/
  Open-LLM-VTuber/
  FinanceAgentGUI/              # optional
```

다른 위치에 설치했다면 웹 UI의 `Model collection root`, `Reference audio path`, `GPT-SoVITS API URL` 값을 바꾸면 됩니다.

## 설치

```powershell
git clone https://github.com/duxb5/sovits-control-bridge.git VTuber
cd VTuber
py -m pip install -r requirements.txt
Copy-Item .\sovits-control.config.example.json .\sovits-control.config.json
```

`pyaudio` 설치가 Windows에서 실패하면 Python 버전과 맞는 wheel을 설치하거나, PortAudio가 포함된 배포 환경을 사용하세요. 브릿지 서버의 재생 경로는 PyAudio를 전제로 합니다.

## 실행

GPT-SoVITS가 `.\GPT-SoVITS` 아래에 설치되어 있다면:

```powershell
.\start-sovits-control-background.ps1
```

그 후 브라우저에서 엽니다.

```text
http://127.0.0.1:18088
```

이미 GPT-SoVITS API를 직접 띄웠다면 `sovits-control-server.py`만 실행해도 됩니다.

```powershell
py -X utf8 .\sovits-control-server.py
```

상태 확인과 종료:

```powershell
.\status-sovits-control-background.ps1
.\stop-sovits-control-background.ps1
```

## API 사용

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:18088/api/speak `
  -ContentType 'application/json; charset=utf-8' `
  -Body (@{ text = '안녕하세요. 이 문장을 GPT-SoVITS 목소리로 읽습니다.'; play = $true } | ConvertTo-Json)
```

간단한 CLI 래퍼:

```powershell
.\sovits-send.ps1 "지금 보이는 답변을 그대로 읽어줘."
```

## 모델 프로필

브릿지는 기본적으로 다음 폴더를 스캔합니다.

```text
Open-LLM-VTuber/models/GPT-SoVITS_Model_Collection/原神/韩语
```

각 프로필은 같은 폴더의 `.ckpt`, `.pth`, reference audio를 묶습니다. 웹 UI에서 프로필을 적용하면 다음 값이 함께 변경됩니다.

- GPT weight
- SoVITS weight
- Reference audio path
- Reference audio prompt text
- Text / prompt language
- Split method

reference audio와 prompt text가 어긋나면 문장이 잘리거나 이상한 반복음이 날 수 있습니다. 새 모델을 추가했다면 UI에서 프로필을 적용한 뒤 짧은 문장으로 테스트하세요.

## 뉴스 브릿지

`finance-vtuber-bridge.py`는 선택 기능입니다. FinanceAgentGUI 또는 SaveTicker 뉴스를 가져와 Open-LLM-VTuber의 로컬 speak API로 보내는 용도입니다.

```powershell
Copy-Item .\finance-vtuber-bridge.config.example.json .\finance-vtuber-bridge.config.json
py -X utf8 .\finance-vtuber-bridge.py saveticker-today
py -X utf8 .\finance-vtuber-bridge.py once
py -X utf8 .\finance-vtuber-bridge.py auto
```

## 로컬 설정 파일

다음 파일은 개인 PC 경로와 실행 상태를 담기 때문에 Git에 올리지 않습니다.

- `sovits-control.config.json`
- `finance-vtuber-bridge.config.json`
- `finance-vtuber-bridge.state.json`
- `sovits-output/`
- `logs/`

필요한 기본값은 `*.example.json`에서 복사해서 사용하세요.

## 보안 메모

이 브릿지는 로컬 자동화용입니다. 기본 바인딩은 `127.0.0.1`이며, 인터넷에 공개하는 서버로 설계되어 있지 않습니다. 외부 네트워크에 열기 전에 인증, 요청 제한, 파일 경로 검증을 별도로 추가하세요.
