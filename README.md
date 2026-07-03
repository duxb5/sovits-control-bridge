# SoVITS Control Bridge

Agent text to GPT-SoVITS voice.

SoVITS Control Bridge is a small local HTTP bridge that sends explicit text to a local GPT-SoVITS API, saves the generated WAV file, and plays it through PyAudio. It is meant for agent answer voice mirroring: the agent sends the same message it shows to the user, and the bridge speaks that text.

It does not watch your clipboard. It only speaks text you type into the UI or send to `/api/speak` or `/api/agent/speak`.

## Features

- Local web UI at `http://127.0.0.1:18088`
- `POST /api/speak` for explicit text-to-speech requests
- `POST /api/agent/speak` for visible agent-message voice mirroring
- GPT-SoVITS `/tts` integration
- PyAudio playback queue so responses are spoken in order
- Voice profile switching for GPT weight, SoVITS weight, reference audio, and prompt text
- Optional English token preprocessing for Korean voice profiles
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

## Windows + WSL GPT-SoVITS Notes

On a Windows host with a recent NVIDIA GPU, it can be easier to run the bridge on Windows and run GPT-SoVITS inside WSL. This repository includes `scripts/start-gptsovits-api-wsl.sh` for that layout. The PowerShell launcher calls WSL, activates a conda environment named `GPTSoVits`, and starts `api_v2.py` on `127.0.0.1:9880`.

The setup that was verified while preparing this bridge used:

- Windows Python 3.12 for the bridge and PyAudio playback
- WSL with Miniforge under `~/miniforge3`
- conda environment `GPTSoVits` with Python 3.10
- GPT-SoVITS installed under `sovits-control-bridge/GPT-SoVITS`
- CUDA 12.8 PyTorch wheels: `torch==2.7.0+cu128` and `torchaudio==2.7.0+cu128`

Troubleshooting tips from that install:

- If GPT-SoVITS fails with `libcudart.so.13`, the installed PyTorch wheel expects CUDA 13 runtime libraries. Reinstall PyTorch/Torchaudio for the CUDA runtime available in WSL; CUDA 12.8 wheels fixed that issue on this machine.
- If GPT-SoVITS imports fail, check optional packages such as `onnxruntime` and a compatible `markupsafe` version.
- If applying a voice profile returns `400 Bad Request` from GPT-SoVITS, check whether Windows paths are being sent to the WSL API. The bridge converts local Windows paths such as `C:\...` into WSL paths such as `/mnt/c/...` before calling GPT-SoVITS.
- If the bridge starts but no speech is generated, check both sides: `.\status-sovits-control-background.ps1` should show the bridge PID and port `9880` listening.
- Keep reference audio and prompt text matched. A wrong prompt for the reference WAV can cause clipped, repeated, or unstable speech.

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
.\sovits-send.ps1 "Read this text aloud."
```

## Agent Voice Mirroring

Agent voice mirroring means the caller sends the same text that is visible to the user. The bridge does not create a separate TTS-only answer and it does not watch the clipboard.

Use `/api/agent/speak` when you want to make that intent explicit:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:18088/api/agent/speak `
  -ContentType 'application/json; charset=utf-8' `
  -Body (@{ text = 'This is the exact visible agent message.'; play = $true } | ConvertTo-Json)
```

Or use the helper:

```powershell
.\sovits-agent-send.ps1 "This is the exact visible agent message."
```

The web UI also includes an `Agent voice mirroring` test section so the endpoint can be checked without another app.

## Mirroring Mode

You can configure how the caller handles voice mirroring in the web UI or via `sovits-control.config.json` using the `mirroring_mode` setting:

*   **`full`**: Speaks the entire text of the agent's response word-for-word (excluding code blocks and raw markdown symbols).
*   **`summary`**: Directs the calling agent (via global `AGENTS.md` instructions) to dynamically summarize its final response into a concise 2-4 sentence overview for speech playback.

Developer agents (such as Codex and Antigravity) read this configuration dynamically at runtime and adapt their output generation based on your shared `AGENTS.md` rules.

## English Token Preprocessing

Korean voice profiles can sound awkward when they read English product names, acronyms, and technical terms directly. When `normalize_english_tokens` is enabled, the bridge keeps the original visible text for previews but sends a more speakable version to GPT-SoVITS.

Examples:

- `API` -> `에이피아이`
- `WSL` -> `더블유 에스 엘`
- `PowerShell` -> `파워셸`
- `GPT-SoVITS` -> `지피티 소비츠`

This option is enabled by default and can be changed in the web UI or in `sovits-control.config.json`.

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
