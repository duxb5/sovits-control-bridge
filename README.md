# SoVITS Control Bridge

Agent text to GPT-SoVITS voice.

SoVITS Control Bridge is a small local HTTP bridge that sends explicit text to a local GPT-SoVITS API, saves the generated WAV file, and plays it through PyAudio. It is meant for agent answer mirroring, local assistants, and simple text-to-speech automation.

It does not watch your clipboard. It only speaks text you type into the UI or send to `/api/speak`.

## Features

- Local web UI at `http://127.0.0.1:18088`
- `POST /api/speak` for explicit text-to-speech requests
- GPT-SoVITS `/tts` integration
- PyAudio playback queue so responses are spoken in order
- Voice profile switching for GPT weight, SoVITS weight, reference audio, and prompt text
- Configurable WAV retention so old generated audio is cleaned up automatically
- UTF-8 PowerShell helpers for Korean and CJK paths/prompts

## Recommended Layout

The public default layout is intentionally small:

```text
sovits-control-bridge/
  sovits-control-server.py
  GPT-SoVITS/
    api_v2.py
    runtime/
    models/
      GPT-SoVITS_Model_Collection/
```

The bridge assumes `GPT-SoVITS/` lives beside `sovits-control-server.py`. If your GPT-SoVITS install is elsewhere, change `GPT-SoVITS API URL`, `Model collection root`, and `Reference audio path` in the web UI or `sovits-control.config.json`.

## Model Collection

Put downloaded voice models under:

```text
GPT-SoVITS/models/GPT-SoVITS_Model_Collection/
```

The bridge scans this folder recursively. A voice profile is discovered when a model folder contains:

- one `.ckpt` GPT weight
- one `.pth` SoVITS weight
- a `ref_audio.wav` file or another `.wav` reference audio

Example:

```text
GPT-SoVITS/models/GPT-SoVITS_Model_Collection/
  Genshin/Korean/furina_ko/
    furina_ko.ckpt
    furina_ko.pth
    ref_audio.wav
```

If you also use another app that expects the old model collection path, point that app to this folder. On Windows, another practical option is a directory junction:

```powershell
New-Item -ItemType Junction `
  -Path "C:\path\to\OtherApp\models\GPT-SoVITS_Model_Collection" `
  -Target "C:\path\to\sovits-control-bridge\GPT-SoVITS\models\GPT-SoVITS_Model_Collection"
```

Keeping the model collection under `GPT-SoVITS/` makes the bridge usable without any app-specific model path.

## Install

```powershell
git clone https://github.com/duxb5/sovits-control-bridge.git
cd sovits-control-bridge
py -m pip install -r requirements.txt
Copy-Item .\sovits-control.config.example.json .\sovits-control.config.json
```

PyAudio is required for bridge playback. If installation fails on Windows, install a wheel that matches your Python version or use a Python distribution with PortAudio support.

## Run

If `GPT-SoVITS/` is in the recommended layout:

```powershell
.\start-sovits-control-background.ps1
```

Open:

```text
http://127.0.0.1:18088
```

If the GPT-SoVITS API is already running, you can start only the bridge:

```powershell
py -X utf8 .\sovits-control-server.py
```

Status and stop helpers:

```powershell
.\status-sovits-control-background.ps1
.\stop-sovits-control-background.ps1
```

## Speak Text

PowerShell:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:18088/api/speak `
  -ContentType 'application/json; charset=utf-8' `
  -Body (@{ text = '안녕하세요. 이 문장을 GPT-SoVITS 목소리로 읽습니다.'; play = $true } | ConvertTo-Json)
```

CLI helper:

```powershell
.\sovits-send.ps1 "Mirror this agent response as speech."
```

## Voice Profiles

In the web UI, choose a voice profile and click `선택한 모델 적용`. The bridge updates these values together:

- GPT weight
- SoVITS weight
- Reference audio path
- Reference audio prompt text
- Text / prompt language
- Split method

Reference audio and prompt text must match. If they do not, GPT-SoVITS may cut off sentences, repeat sounds, or generate unstable speech.

## Local Files

These files are local machine state and are ignored by Git:

- `sovits-control.config.json`
- `sovits-output/`
- `logs/`
- `*.pid`

Use `sovits-control.config.example.json` as the starting point for a new machine.

Generated WAV files are kept for browser playback and debugging. The `Saved WAV limit` setting controls how many recent files remain; older files are deleted automatically after new speech is generated.

## Security

This is a local automation tool. It binds to `127.0.0.1` by default and is not designed to be exposed to the internet. Add authentication, request limits, and stronger path validation before using it on a shared network.
