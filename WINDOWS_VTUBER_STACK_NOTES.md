# Windows VTuber Stack 재설치/이식 노트

이 문서는 `Installation_Guide_Windows.md`를 바탕으로, 이 PC에서 실제로 Open-LLM-VTuber, GPT-SoVITS, FinanceAgentGUI, 뉴스 브릿지를 붙이면서 확인한 함정과 재현 절차를 정리한 운영 노트입니다.

목표는 새 Windows PC에서 같은 구성을 다시 만들 때 설치 추론을 줄이고, 경로/포트/인코딩 문제를 빠르게 통과하는 것입니다.

## 기준 폴더 구조

권장 루트:

```text
C:\Users\<USER>\Documents\VTuber
```

현재 사용한 배치:

```text
VTuber\
  Open-LLM-VTuber\
  GPT-SoVITS\
  FinanceAgentGUI\
  finance-vtuber-bridge.py
  finance-vtuber-bridge.config.json
  start-gptsovits-api.ps1
  start-finance-vtuber-bridge.ps1
```

다른 PC에서는 `<USER>`만 바꾸고, 가능하면 `Documents\VTuber` 아래 구조는 그대로 유지하는 편이 가장 덜 흔들립니다.

## 포트 지도

| 포트 | 프로그램 | 확인 URL/용도 |
|---:|---|---|
| `12393` | Open-LLM-VTuber | `http://localhost:12393` |
| `9880` | GPT-SoVITS API | `http://127.0.0.1:9880/docs` |
| `5173` | FinanceAgentGUI | `http://127.0.0.1:5173` |

빠른 확인:

```powershell
Get-NetTCPConnection -LocalPort 12393,9880,5173 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,OwningProcess
```

## 권장 실행 순서

1. GPT-SoVITS API

```powershell
cd C:\Users\<USER>\Documents\VTuber
powershell -ExecutionPolicy Bypass -File .\start-gptsovits-api.ps1
```

이 스크립트는 `runtime\python.exe -X utf8 api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml` 형태로 실행합니다. `-X utf8`은 한국어 Windows에서 필수에 가깝습니다.

2. Open-LLM-VTuber

```powershell
cd C:\Users\<USER>\Documents\VTuber\Open-LLM-VTuber
powershell -ExecutionPolicy Bypass -File .\start-open-llm-vtuber.ps1
```

3. FinanceAgentGUI

프로젝트의 기존 실행 방식에 맞춰 `127.0.0.1:5173`이 열리도록 실행합니다. 이 PC에서는 FinanceAgentGUI 서버가 켜져 있어야 브릿지의 `/api/news-feed/items`, `/api/news-feed/refresh`가 동작했습니다.

4. 브라우저

```text
http://localhost:12393
```

브라우저 클라이언트가 붙었는지 확인:

```powershell
Invoke-RestMethod http://localhost:12393/local/clients | ConvertTo-Json -Compress
```

`count`가 `1` 이상이어야 `/local/speak`와 뉴스 읽기가 정상 동작합니다.

## GPT-SoVITS 쪽 핵심 팁

### VTuber 없이 GPT-SoVITS만 쓰기

Live2D/브라우저 없이 에이전트 답변이나 임의 문장을 바로 음성으로 듣고 싶으면 루트의 `sovits-say.py`를 사용합니다.

```powershell
cd C:\Users\<USER>\Documents\VTuber
powershell -ExecutionPolicy Bypass -File .\start-gptsovits-api.ps1
powershell -ExecutionPolicy Bypass -File .\sovits-say.ps1 "준님, GPT-SoVITS 직접 재생 테스트입니다."
```

파일만 만들고 재생하지 않으려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\sovits-say.ps1 "테스트 문장입니다." --no-play
```

클립보드에 복사한 에이전트 답변을 바로 읽게 하려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\sovits-clipboard.ps1
```

Codex 답변을 복사할 때마다 자동으로 읽게 하려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-sovits-auto-clipboard.ps1
```

평소에 창을 계속 열어두지 않고 백그라운드로 연동하려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-sovits-auto-background.ps1
```

상태 확인:

```powershell
powershell -ExecutionPolicy Bypass -File .\status-sovits-auto-background.ps1
```

백그라운드 자동 낭독 끄기:

```powershell
powershell -ExecutionPolicy Bypass -File .\stop-sovits-auto-background.ps1
```

처음 실행할 때 이미 클립보드에 들어 있는 텍스트까지 바로 읽고 싶으면:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-sovits-auto-clipboard.ps1 --speak-existing
```

멈출 때는 해당 PowerShell 창에서 `Ctrl+C`를 누릅니다.

생성된 wav는 `sovits-output\` 아래에 저장됩니다.

### 클립보드 없이 SoVITS Voice Bridge 쓰기

모든 클립보드를 감시하지 않고, 명시적으로 보낸 텍스트만 읽게 하려면 로컬 브릿지 앱을 사용합니다.

```powershell
cd C:\Users\<USER>\Documents\VTuber
powershell -ExecutionPolicy Bypass -File .\start-sovits-control-background.ps1
```

브라우저에서 엽니다.

```text
http://127.0.0.1:18088
```

여기서 reference audio, prompt text, 언어, 분할 방식, 자동 재생 여부를 저장할 수 있습니다.

브릿지는 다음 폴더에서 GPT-SoVITS 모델 프로필을 자동 스캔합니다.

```text
Open-LLM-VTuber\models\GPT-SoVITS_Model_Collection\原神\韩语
```

브릿지 화면의 `모델 프로필`에서 항목을 고르고 `선택한 모델 적용`을 누르면 다음 값이 한 번에 바뀝니다.

- GPT weight
- SoVITS weight
- Reference audio path
- Reference audio prompt text
- `text_lang`, `prompt_lang`, `text_split_method`

현재 확인된 프로필:

```text
v2ProPlus\卡芙卡
v2ProPlus\流萤
v2ProPlus\知更鸟
v4\纳西妲_KO
芙宁娜_KO\v4\furina_ko
```

브릿지는 시작할 때 저장된 `voice_profile_id`를 GPT-SoVITS API에 다시 적용해서, 브릿지 설정과 본서버 weight가 어긋나지 않게 합니다.

외부에서 텍스트만 보내려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\sovits-send.ps1 "읽을 문장입니다."
```

또는 HTTP API:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:18088/api/speak `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"text":"읽을 문장입니다.","play":true}'
```

브릿지 상태/종료:

```powershell
powershell -ExecutionPolicy Bypass -File .\status-sovits-control-background.ps1
powershell -ExecutionPolicy Bypass -File .\stop-sovits-control-background.ps1
```

#### 문장 끝부분만 들릴 때

Codex 보이스 미러링처럼 짧은 메시지를 연속으로 보내면 “마지막 세 단어만 들리는” 것처럼 느껴질 수 있습니다.

확인할 것:

- `sovits-output\`의 wav 파일 크기가 충분히 크면 GPT-SoVITS 합성 자체는 전체 문장으로 된 것입니다.
- 이전 브릿지 구현처럼 요청마다 `winsound.PlaySound`를 새 스레드에서 바로 호출하면, 뒤 요청이 앞 재생을 끊을 수 있습니다.
- 파일명이 초 단위 timestamp이면 빠른 연속 요청이 같은 wav 파일을 덮어써서 큐에 넣은 항목들이 마지막 파일로 바뀔 수 있습니다.

현재 브릿지는 재생 큐를 사용하고, 파일명은 `time.time_ns()` 기반으로 생성해서 이 문제를 피합니다.

#### 응응거리거나 문장이 뭉개질 때

wav가 생성되고 재생도 되지만 “응응응”처럼 들리거나 문장이 비정상적으로 짧게 압축되면 GPT-SoVITS의 reference 설정을 먼저 봅니다.

- `ref_audio_path`와 `prompt_text`는 반드시 같은 샘플의 오디오와 실제 대사여야 합니다.
- 이 PC의 푸리나 KO 모델은 Open-LLM-VTuber 설정의 값과 맞춰야 정상 발화했습니다.
- 현재 브릿지 설정:

```json
{
  "ref_audio_path": "C:\\Users\\jun\\Documents\\VTuber\\Open-LLM-VTuber\\models\\GPT-SoVITS_Model_Collection\\原神\\韩语\\芙宁娜_KO\\v4\\furina_ko\\ref_audio.wav",
  "prompt_text": "방금 이야기를 하면서 느꼈지…. 이 왕생당의 객경이란 자는… 절대 평범한 사람이 아니야"
}
```

다른 모델이나 다른 reference audio로 바꾸면 `prompt_text`도 해당 오디오의 실제 녹음 대사로 같이 바꿉니다.

### V3/V4 모델

푸리나 KO 모델처럼 V3/V4 기반 모델은 구버전 GPT-SoVITS API에서 `SynthesizerTrnV3 object has no attribute 'decode'` 같은 오류가 날 수 있습니다.

해결 방향:

- `TTS.py`가 V3/V4의 Flow Matching 및 BigVGAN 보코더 경로를 지원해야 합니다.
- 화자 인증 관련 패키지(`ERes2NetV2`, Kaldi 등)가 없어 서버가 죽는 경우, 사용하지 않는 환경에서는 mock `sv.py`로 우회할 수 있습니다.
- API는 반드시 UTF-8 모드로 실행합니다.

```powershell
runtime\python.exe -X utf8 api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
```

### 한국어 Windows CP949 문제

한국어 대사나 로그 출력 중 `CP949 codec can't encode character`가 나면 서버가 비정상 응답을 줄 수 있습니다.

우선순위:

1. Python 실행에 `-X utf8` 추가
2. PowerShell 세션에 `$env:PYTHONUTF8=1`
3. 브릿지/보조 스크립트에서 stdout/stderr를 UTF-8로 reconfigure

PowerShell에서 한글 인자나 파이프 입력이 깨질 때는 루트의 `set-powershell-utf8.ps1`을 먼저 dot-source합니다.

```powershell
cd C:\Users\<USER>\Documents\VTuber
. .\set-powershell-utf8.ps1
```

이 스크립트는 `[Console]::InputEncoding`, `[Console]::OutputEncoding`, `$OutputEncoding`, `PYTHONUTF8`, `chcp 65001`을 UTF-8 쪽으로 맞춥니다. SoVITS 관련 PowerShell 래퍼들은 이 파일을 자동으로 불러오도록 구성했습니다.

## 뉴스 브릿지

현재 루트의 `finance-vtuber-bridge.py`는 세 가지 소스를 다룹니다.

| 명령 | 동작 |
|---|---|
| `once` | FinanceAgentGUI에서 최신 금융 뉴스 1건 읽기 |
| `auto` | 새 뉴스 폴링 후 자동 읽기 |
| `saveticker-today` | SaveTicker 오늘 주요뉴스 읽기 |

설정 파일:

```text
C:\Users\<USER>\Documents\VTuber\finance-vtuber-bridge.config.json
```

주요 설정:

```json
{
  "financeApiBase": "http://127.0.0.1:5173",
  "savetickerApiBase": "https://saveticker.com/api",
  "vtuberApiBase": "http://localhost:12393",
  "manualItemCount": 1,
  "savetickerTopStoryCount": 3,
  "refreshBeforeRead": true
}
```

수동 테스트:

```powershell
cd C:\Users\<USER>\Documents\VTuber
py -X utf8 .\finance-vtuber-bridge.py once
py -X utf8 .\finance-vtuber-bridge.py saveticker-today
```

VTuber 입력창에서 사용할 문장:

```text
2시이후에 나온 경제뉴스 브리핑해줘
세이브티커 오늘 주요뉴스 읽어줘
```

중요: 브릿지가 다시 `/local/speak`로 VTuber에게 뉴스 본문을 넣을 때 `skip_finance_bridge: true`를 같이 보내야 합니다. 이 값이 없으면 “뉴스를 읽어줘” 문장이 다시 뉴스 명령으로 감지되어 재귀 루프가 생깁니다.

## Open-LLM-VTuber 로컬 API 패치

이 환경에서는 다음 로컬 API를 추가해서 브릿지와 연결했습니다.

| API | 용도 |
|---|---|
| `GET /local/clients` | 브라우저 클라이언트 연결 여부 확인 |
| `POST /local/speak` | 외부 스크립트가 VTuber에게 텍스트 입력 전달 |

`/local/speak` 요청 예:

```json
{
  "text": "읽을 문장",
  "wait": true,
  "timeout": 600,
  "skip_finance_bridge": true
}
```

`wait: true`는 브라우저 재생 완료까지 기다리므로 프로세스가 오래 살아 있을 수 있습니다. 자동화가 자주 막히면 `wait: false` 방식으로 바꾸는 것도 고려할 수 있습니다.

## SaveTicker 연동

SaveTicker 뉴스 페이지는 프론트엔드에서 API를 호출합니다. 현재 확인된 공개 호출:

```text
https://saveticker.com/api/news/top-stories
https://saveticker.com/api/news/list?page=1&page_size=20&sort=created_at_desc
```

브릿지는 KST 기준 오늘 날짜의 주요뉴스를 우선 고르고, 부족하면 최신 뉴스에서 오늘 기사로 보충합니다.

## Live2D 모델 추가

모델 폴더:

```text
Open-LLM-VTuber\live2d-models
```

권장 배치:

```text
live2d-models\<model_name>\runtime\<actual model files>
live2d-models\<model_name>\<model_name>.model3.json
```

그리고 `Open-LLM-VTuber\model_dict.json`에 등록합니다.

현재 추가한 모델:

```text
yili
nahida_1080
```

기본 모델 변경:

```yaml
# Open-LLM-VTuber\conf.yaml
character_config:
  live2d_model_name: 'nahida_1080'
```

변경 후 Open-LLM-VTuber 서버를 재시작하고 브라우저를 새로고침합니다.

## 로그 위치

| 로그 | 경로 |
|---|---|
| Open-LLM-VTuber stdout | `Open-LLM-VTuber\logs\server.out.log` |
| Open-LLM-VTuber stderr | `Open-LLM-VTuber\logs\server.err.log` |
| GPT-SoVITS stdout | `GPT-SoVITS\logs\api-v2-9880.out.log` |
| GPT-SoVITS stderr | `GPT-SoVITS\logs\api-v2-9880.err.log` |

자주 보는 명령:

```powershell
Get-Content .\Open-LLM-VTuber\logs\server.err.log -Tail 120
Get-Content .\GPT-SoVITS\logs\api-v2-9880.out.log -Tail 120
Get-Content .\GPT-SoVITS\logs\api-v2-9880.err.log -Tail 120
```

## 흔한 증상별 체크

### VTuber가 말풍선은 뜨는데 소리가 안 남

1. GPT-SoVITS API가 `9880`에서 응답하는지 확인
2. GPT-SoVITS 로그에서 `/tts ... 200 OK` 확인
3. 브라우저 탭 음소거/사이트 소리 권한/Windows 출력 장치 확인
4. `/local/clients`가 `count: 1` 이상인지 확인

### 뉴스 요청이 반응 없는 것처럼 보임

1. `server.err.log`에 `Finance news bridge command detected`가 있는지 확인
2. `finance-vtuber-bridge.py` 프로세스가 오래 남아 있으면 `/local/speak`가 완료 대기 중일 수 있음
3. GPT-SoVITS 로그에서 실제 TTS 요청이 완료됐는지 확인
4. 브라우저 재생 완료 이벤트가 돌아오지 않으면 `wait: false` 전환 검토

### FinanceAgentGUI 뉴스 수집 오류

`Walter Bloomberg: HTTP 429`처럼 일부 피드가 막혀도 다른 피드가 살아 있으면 브릿지는 작동할 수 있습니다. 전체 실패인지 일부 피드 실패인지 `/api/news-feed/items` 응답으로 구분합니다.

### SaveTicker 날짜가 이상해 보임

API 응답은 UTC와 `+09:00` 표기가 섞일 수 있습니다. 브릿지는 KST 날짜로 변환해서 “오늘”을 판단합니다.

## 새 PC에서 복사할 때 주의

- `conf.yaml` 안의 API 키나 개인 설정은 외부에 공유하지 않습니다.
- `GPT-SoVITS` 모델 가중치와 Live2D 모델은 라이선스를 확인합니다.
- `Documents\VTuber` 경로를 바꾸면 스크립트와 설정의 절대 경로를 다시 점검합니다.
- Python 실행은 가능하면 `py -X utf8` 또는 스크립트 내부 `-X utf8`을 유지합니다.
- Open-LLM-VTuber 서버 재시작 후에는 브라우저를 새로고침해야 `/local/clients`가 다시 잡힙니다.

## 최소 검증 체크리스트

```powershell
# 1. 포트
Get-NetTCPConnection -LocalPort 12393,9880,5173 -State Listen -ErrorAction SilentlyContinue

# 2. GPT-SoVITS
Invoke-WebRequest http://127.0.0.1:9880/docs -UseBasicParsing

# 3. VTuber 클라이언트
Invoke-RestMethod http://localhost:12393/local/clients

# 4. FinanceAgentGUI 뉴스
Invoke-RestMethod http://127.0.0.1:5173/api/news-feed/items

# 5. 브릿지
py -X utf8 .\finance-vtuber-bridge.py status
```

이 다섯 개가 통과하면 기본 스택은 거의 살아 있는 상태입니다.
