# Repository Guidelines

## Scope

This repository is a local GPT-SoVITS voice bridge for explicit agent/text-to-speech requests.

Keep the public project focused on:

- `/api/speak`
- the local web UI
- GPT-SoVITS API integration
- PyAudio playback
- voice profile discovery and switching

## Important Decisions

- Do not reintroduce clipboard monitoring. The bridge should only speak text explicitly sent to `/api/speak` or typed into the UI.
- Do not add news readers, app-specific integrations, or other personal automation to the public repository.
- Keep PyAudio as the server playback backend. It was chosen to avoid Windows-only playback and keep the audio path more portable.
- Treat `sovits-control.config.json` as local machine state. Do not commit user-specific paths, generated WAV files, logs, PID files, or fetched/generated content.
- Preserve UTF-8 handling in Python and PowerShell scripts. Korean and CJK model paths/prompts are expected.
- Avoid printing or committing secrets from adjacent local projects.

## Default Layout

The default public layout assumes:

```text
sovits-control-bridge/
  GPT-SoVITS/
  sovits-control-server.py
```

Model collections should default to:

```text
GPT-SoVITS/models/GPT-SoVITS_Model_Collection/
```

The bridge should still allow paths to be configured from the UI or config file for other machines.

## Verification

Before finishing code changes, run:

```powershell
py -X utf8 -m py_compile .\sovits-control-server.py .\sovits-send.py .\sovits-say.py
```

When the local bridge is running, also check:

```powershell
Invoke-RestMethod http://127.0.0.1:18088/api/status
Invoke-RestMethod http://127.0.0.1:18088/api/profiles
```
