# Repository Guidelines

## Scope

This repository is a local GPT-SoVITS voice bridge. Keep changes focused on explicit text-to-speech requests, local model profile control, and optional news-to-voice helpers.

## Important Decisions

- Do not reintroduce clipboard monitoring. The bridge should only speak text explicitly sent to `/api/speak` or typed into the UI.
- Keep PyAudio as the server playback backend. It was chosen to avoid Windows-only playback and to keep the audio path more portable.
- Treat `sovits-control.config.json` and `finance-vtuber-bridge.config.json` as local machine files. Do not commit user-specific paths, generated WAV files, logs, PID files, or fetched news snapshots.
- Preserve UTF-8 handling in Python and PowerShell scripts. Korean model paths and prompts are expected.
- Avoid printing or committing secrets from adjacent projects, especially Open-LLM-VTuber config files.

## Local Layout

The default development layout assumes:

```text
VTuber/
  GPT-SoVITS/
  Open-LLM-VTuber/
  FinanceAgentGUI/
  sovits-control-server.py
```

The bridge should still allow paths to be configured from the UI or config file for other machines.

## Verification

Before finishing code changes, run:

```powershell
py -X utf8 -m py_compile .\sovits-control-server.py .\sovits-send.py .\sovits-say.py .\finance-vtuber-bridge.py
```

When the local bridge is running, also check:

```powershell
Invoke-RestMethod http://127.0.0.1:18088/api/status
Invoke-RestMethod http://127.0.0.1:18088/api/profiles
```
