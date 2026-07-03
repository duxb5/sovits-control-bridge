import json
import hashlib
import mimetypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
import wave
import pyaudio
from queue import Queue
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "sovits-control.config.json"
OUTPUT_DIR = ROOT / "sovits-output"
LOG_DIR = ROOT / "logs"
GPT_SOVITS_API_PORT = 9880
DEFAULT_MODEL_COLLECTION_ROOT = (
    ROOT
    / "GPT-SoVITS"
    / "models"
    / "GPT-SoVITS_Model_Collection"
)
KNOWN_PROMPTS = {
    "furina_ko": "방금 이야기를 하면서 느꼈지…. 이 왕생당의 객경이란 자는… 절대 평범한 사람이 아니야",
}


def find_default_ref_audio():
    model_root = DEFAULT_MODEL_COLLECTION_ROOT
    preferred = list(model_root.glob("**/furina_ko/ref_audio.wav"))
    if preferred:
        return preferred[0]
    matches = list(model_root.glob("**/ref_audio.wav"))
    if matches:
        return matches[0]
    return model_root / "ref_audio.wav"


DEFAULT_CONFIG = {
    "api_url": "http://127.0.0.1:9880/tts",
    "ref_audio_path": str(find_default_ref_audio()),
    "prompt_text": "방금 이야기를 하면서 느꼈지…. 이 왕생당의 객경이란 자는… 절대 평범한 사람이 아니야",
    "text_lang": "ko",
    "prompt_lang": "ko",
    "text_split_method": "cut5",
    "batch_size": 1,
    "timeout": 180,
    "auto_play": True,
    "normalize_english_tokens": True,
    "max_chars": 3500,
    "max_saved_wavs": 50,
    "model_collection_root": str(DEFAULT_MODEL_COLLECTION_ROOT),
    "voice_profile_id": "",
    "gpt_weight_path": "",
    "sovits_weight_path": "",
    "mirroring_mode": "full",
    "mirroring_scope": "final_only",
}


LAST_RESULT = {
    "file": "",
    "audio_url": "",
    "text_preview": "",
    "spoken_text_preview": "",
    "created_at": "",
}
PLAYBACK_QUEUE = Queue()
PLAYBACK_STATE = {
    "queued": 0,
    "current": "",
    "last_played": "",
}


def normalize_prompt_from_audio(path):
    stem = path.stem.replace("\u00a0", " ").replace("_", " ").strip()
    if "】" in stem:
        stem = stem.split("】", 1)[1].strip()
    return " ".join(stem.split())


def profile_id_from_path(path):
    rel = str(path.resolve()).lower()
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]


def resolve_local_path(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def path_for_gptsovits_api(path):
    resolved = str(Path(path).resolve())
    if os.name != "nt":
        return resolved

    drive, tail = os.path.splitdrive(resolved)
    if not drive:
        return resolved.replace("\\", "/")

    drive_letter = drive.rstrip(":").lower()
    tail = tail.replace("\\", "/")
    return f"/mnt/{drive_letter}{tail}"


ENGLISH_TOKEN_REPLACEMENTS = [
    ("GPT-SoVITS", "지피티 소비츠"),
    ("GPTSoVITS", "지피티 소비츠"),
    ("SoVITS", "소비츠"),
    ("PowerShell", "파워셸"),
    ("JavaScript", "자바스크립트"),
    ("TypeScript", "타입스크립트"),
    ("Node.js", "노드 제이에스"),
    ("GitHub", "깃허브"),
    ("Windows", "윈도우"),
    ("Linux", "리눅스"),
    ("Python", "파이썬"),
    ("PyAudio", "파이오디오"),
    ("PyTorch", "파이토치"),
    ("CUDA", "쿠다"),
    ("Miniforge", "미니포지"),
    ("Conda", "콘다"),
    ("WSL2", "더블유 에스 엘 투"),
    ("WSL", "더블유 에스 엘"),
    ("UTF-8", "유티에프 에잇"),
    ("API", "에이피아이"),
    ("HTTP", "에이치 티 티 피"),
    ("JSON", "제이슨"),
    ("URL", "유알엘"),
    ("TTS", "티티에스"),
    ("UI", "유아이"),
    ("CLI", "씨엘아이"),
    ("PR", "피알"),
    ("PID", "피아이디"),
    ("WAV", "웨이브"),
    ("GPU", "지피유"),
    ("CPU", "씨피유"),
    ("RTX", "알티엑스"),
    ("README", "리드미"),
]

LETTER_NAMES = {
    "A": "에이",
    "B": "비",
    "C": "씨",
    "D": "디",
    "E": "이",
    "F": "에프",
    "G": "지",
    "H": "에이치",
    "I": "아이",
    "J": "제이",
    "K": "케이",
    "L": "엘",
    "M": "엠",
    "N": "엔",
    "O": "오",
    "P": "피",
    "Q": "큐",
    "R": "알",
    "S": "에스",
    "T": "티",
    "U": "유",
    "V": "브이",
    "W": "더블유",
    "X": "엑스",
    "Y": "와이",
    "Z": "지",
}


def normalize_english_tokens_for_korean_tts(text):
    normalized = text
    for source, replacement in ENGLISH_TOKEN_REPLACEMENTS:
        pattern = re.compile(rf"(?<![A-Za-z]){re.escape(source)}(?![A-Za-z])", re.IGNORECASE)
        normalized = pattern.sub(replacement, normalized)

    def spell_acronym(match):
        token = match.group(0)
        return " ".join(LETTER_NAMES.get(ch, ch) for ch in token)

    normalized = re.sub(r"(?<![A-Za-z])v(\d+)(?![A-Za-z])", r"브이 \1", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(?<![A-Za-z])([A-Z]{2,6})(?![A-Za-z])", spell_acronym, normalized)
    return normalized


def model_collection_root(config=None):
    value = (config or {}).get("model_collection_root") or str(DEFAULT_MODEL_COLLECTION_ROOT)
    return resolve_local_path(value)


def pick_reference_audio(model_dir):
    direct = model_dir / "ref_audio.wav"
    if direct.exists():
        return direct
    refs = list(model_dir.glob("reference_audios/**/*.wav"))
    if not refs:
        refs = list(model_dir.glob("**/*.wav"))
    if not refs:
        return None

    def score(path):
        name = path.name
        if "【默认】" in name:
            return (0, len(name), name)
        if "【中立】" in name:
            return (1, len(name), name)
        return (2, len(name), name)

    return sorted(refs, key=score)[0]


def discover_voice_profiles(config=None):
    root = model_collection_root(config)
    if not root.exists():
        return []

    profiles = []
    for ckpt_path in sorted(root.glob("**/*.ckpt"), key=lambda p: str(p)):
        model_dir = ckpt_path.parent
        pth_candidates = sorted(model_dir.glob("*.pth"), key=lambda p: str(p))
        ref_audio_path = pick_reference_audio(model_dir)
        if not pth_candidates or not ref_audio_path:
            continue

        pth_path = pth_candidates[0]
        profile_id = profile_id_from_path(model_dir)
        rel_dir = model_dir.relative_to(root)
        model_name = model_dir.name
        prompt_text = KNOWN_PROMPTS.get(model_name.lower()) or normalize_prompt_from_audio(ref_audio_path)
        profiles.append(
            {
                "id": profile_id,
                "name": model_name,
                "label": str(rel_dir),
                "version": next((part for part in rel_dir.parts if part.lower().startswith("v")), ""),
                "gpt_weight_path": str(ckpt_path),
                "sovits_weight_path": str(pth_path),
                "ref_audio_path": str(ref_audio_path),
                "prompt_text": prompt_text,
                "prompt_lang": "ko",
                "text_lang": "ko",
                "text_split_method": "cut5",
            }
        )
    return profiles


def get_profile(profile_id):
    config = load_config()
    for profile in discover_voice_profiles(config):
        if profile["id"] == profile_id:
            return profile
    return None


def infer_current_profile_id(config, profiles=None):
    profiles = profiles or discover_voice_profiles(config)
    configured = config.get("voice_profile_id", "")
    if configured and any(profile["id"] == configured for profile in profiles):
        return configured

    ref_audio = str(resolve_local_path(config.get("ref_audio_path", "")).resolve()).lower() if config.get("ref_audio_path") else ""
    gpt_weight = str(resolve_local_path(config.get("gpt_weight_path", "")).resolve()).lower() if config.get("gpt_weight_path") else ""
    sovits_weight = str(resolve_local_path(config.get("sovits_weight_path", "")).resolve()).lower() if config.get("sovits_weight_path") else ""

    for profile in profiles:
        if ref_audio and str(Path(profile["ref_audio_path"]).resolve()).lower() == ref_audio:
            return profile["id"]
        if (
            gpt_weight
            and sovits_weight
            and str(Path(profile["gpt_weight_path"]).resolve()).lower() == gpt_weight
            and str(Path(profile["sovits_weight_path"]).resolve()).lower() == sovits_weight
        ):
            return profile["id"]
    return ""


HTML = r"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SoVITS Voice Bridge</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      background: #101114;
      color: #eef1f6;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: #101114; }
    main { max-width: 1040px; margin: 0 auto; padding: 24px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
    h1 { margin: 0; font-size: 24px; font-weight: 760; }
    h2 { margin: 0 0 14px; font-size: 16px; font-weight: 720; color: #dce3f0; }
    .subtle { color: #98a3b5; font-size: 13px; }
    .status { display: inline-flex; align-items: center; gap: 8px; border: 1px solid #2a303b; background: #171a21; border-radius: 8px; padding: 9px 11px; white-space: nowrap; }
    .dot { width: 10px; height: 10px; border-radius: 999px; background: #77808f; }
    .dot.ok { background: #20d17d; }
    .dot.bad { background: #ff6262; }
    section { border-top: 1px solid #2a303b; padding: 20px 0; }
    label { display: block; margin: 12px 0 6px; color: #b8c1d1; font-size: 13px; }
    textarea, input, select {
      width: 100%;
      border: 1px solid #363e4c;
      border-radius: 7px;
      background: #151922;
      color: #eef1f6;
      padding: 10px 11px;
      font-size: 14px;
      line-height: 1.45;
      outline: none;
    }
    textarea:focus, input:focus, select:focus { border-color: #6f8fff; }
    textarea { min-height: 138px; resize: vertical; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; align-items: center; }
    button {
      border: 0;
      border-radius: 7px;
      padding: 10px 14px;
      background: #5577ee;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary { background: #303745; }
    button.good { background: #15865d; }
    button.warn { background: #9a6418; }
    button:disabled { opacity: .58; cursor: wait; }
    code { color: #93d7ff; }
    audio { width: 100%; margin-top: 12px; }
    pre { min-height: 96px; white-space: pre-wrap; word-break: break-word; background: #151922; border: 1px solid #2a303b; padding: 12px; border-radius: 7px; color: #cbd3e3; }
    @media (max-width: 760px) {
      main { padding: 18px; }
      header { display: block; }
      .status { margin-top: 12px; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>SoVITS Voice Bridge</h1>
        <div class="subtle">명시적으로 보낸 텍스트만 GPT-SoVITS 목소리로 읽습니다.</div>
      </div>
      <div class="status"><span id="dot" class="dot"></span><span id="statusText">확인 중...</span></div>
    </header>

    <section>
      <h2>읽을 텍스트</h2>
      <textarea id="text" placeholder="여기에 읽을 텍스트를 넣거나, /api/speak 로 보내세요."></textarea>
      <div class="actions">
        <button id="speakPlay" onclick="speak(true)">소리 재생</button>
        <button class="good" onclick="startApi()">GPT-SoVITS API 켜기</button>
        <button class="secondary" onclick="refreshStatus()">상태 새로고침</button>
      </div>
      <audio id="audio" controls></audio>
      <p id="lastFile" class="subtle"></p>
    </section>

    <section>
      <h2>모델 프로필</h2>
      <label for="voice_profile">Voice profile</label>
      <select id="voice_profile"></select>
      <div class="actions">
        <button class="good" onclick="applyProfile()">선택한 모델 적용</button>
        <button class="secondary" onclick="loadProfiles(true)">프로필 새로고침</button>
      </div>
      <p id="profileInfo" class="subtle"></p>
    </section>

    <section>
      <h2>음성 설정</h2>
      <label for="api_url">GPT-SoVITS API URL</label>
      <input id="api_url" />

      <label for="model_collection_root">Model collection root</label>
      <input id="model_collection_root" />

      <label for="ref_audio_path">Reference audio path</label>
      <input id="ref_audio_path" />

      <label for="prompt_text">Reference audio prompt text</label>
      <textarea id="prompt_text"></textarea>

      <div class="grid">
        <div>
          <label for="text_lang">Text language</label>
          <input id="text_lang" />
        </div>
        <div>
          <label for="prompt_lang">Prompt language</label>
          <input id="prompt_lang" />
        </div>
        <div>
          <label for="text_split_method">Split method</label>
          <input id="text_split_method" />
        </div>
      </div>

      <div class="grid">
        <div>
          <label for="batch_size">Batch size</label>
          <input id="batch_size" type="number" min="1" />
        </div>
        <div>
          <label for="timeout">Timeout seconds</label>
          <input id="timeout" type="number" min="10" />
        </div>
        <div>
          <label for="max_chars">Max characters</label>
          <input id="max_chars" type="number" min="100" />
        </div>
        <div>
          <label for="max_saved_wavs">Saved WAV limit</label>
          <input id="max_saved_wavs" type="number" min="1" />
        </div>
      </div>

      <label for="auto_play">Default playback</label>
      <select id="auto_play">
        <option value="true">PC에서 재생</option>
        <option value="false">자동 재생 안 함</option>
      </select>

      <label for="normalize_english_tokens">English token preprocessing</label>
      <select id="normalize_english_tokens">
        <option value="true">Normalize tech terms and acronyms</option>
        <option value="false">Send text unchanged</option>
      </select>

      <label for="mirroring_mode">에이전트 음성 미러링 모드 (Agent voice mirroring mode)</label>
      <select id="mirroring_mode">
        <option value="full">전체 답변 읽기 (Full response)</option>
        <option value="summary">요약해서 읽기 (Concise summary)</option>
      </select>

      <label for="mirroring_scope">에이전트 음성 미러링 범위 (Agent voice mirroring scope)</label>
      <select id="mirroring_scope">
        <option value="final_only">최종 답변만 읽기 (Final response only)</option>
        <option value="all">중간 진행 과정 및 최종 답변 모두 읽기 (All progress & final)</option>
      </select>

      <div class="actions">
        <button onclick="saveConfig()">설정 저장</button>
        <button class="secondary" onclick="loadConfig()">다시 불러오기</button>
      </div>
    </section>

    <section>
      <h2>연동 API</h2>
      <pre>POST http://127.0.0.1:18088/api/speak
Content-Type: application/json

{"text":"읽을 문장","play":true}</pre>
    </section>

    <section>
      <h2>에이전트 음성 미러링</h2>
      <div class="actions">
        <button class="good" onclick="agentTest()">미러링 테스트</button>
      </div>
      <pre>POST http://127.0.0.1:18088/api/agent/speak
Content-Type: application/json

{"text":"에이전트가 화면에 표시한 답변 그대로","play":true}

.\sovits-agent-send.ps1 "에이전트가 화면에 표시한 답변 그대로"</pre>
    </section>

    <section>
      <h2>로그</h2>
      <pre id="log"></pre>
    </section>
  </main>

  <script>
    const fields = ["api_url","model_collection_root","ref_audio_path","prompt_text","text_lang","prompt_lang","text_split_method","batch_size","timeout","auto_play","normalize_english_tokens","max_chars","max_saved_wavs","mirroring_mode","mirroring_scope"];
    let voiceProfiles = [];

    function log(msg) {
      const el = document.getElementById("log");
      el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + el.textContent;
    }

    async function api(path, options = {}) {
      const res = await fetch(path, { headers: {"Content-Type": "application/json"}, ...options });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || res.statusText);
      return data;
    }

    function readForm() {
      const cfg = {};
      for (const id of fields) {
        const el = document.getElementById(id);
        if (id === "batch_size" || id === "timeout" || id === "max_chars" || id === "max_saved_wavs") cfg[id] = Number(el.value);
        else if (id === "auto_play" || id === "normalize_english_tokens") cfg[id] = el.value === "true";
        else cfg[id] = el.value;
      }
      return cfg;
    }

    function writeForm(cfg) {
      for (const id of fields) {
        const el = document.getElementById(id);
        if (!el || cfg[id] === undefined) continue;
        el.value = String(cfg[id]);
      }
    }

    function setBusy(isBusy) {
      document.querySelectorAll("button").forEach(button => button.disabled = isBusy);
    }

    async function loadConfig() {
      const data = await api("/api/config");
      writeForm(data.config);
      log("설정을 불러왔습니다.");
    }

    async function saveConfig() {
      const data = await api("/api/config", { method: "POST", body: JSON.stringify(readForm()) });
      writeForm(data.config);
      log("설정을 저장했습니다.");
    }

    function writeProfiles(profiles, currentProfileId) {
      voiceProfiles = profiles || [];
      const select = document.getElementById("voice_profile");
      select.innerHTML = "";
      for (const profile of voiceProfiles) {
        const option = document.createElement("option");
        option.value = profile.id;
        option.textContent = profile.label;
        select.appendChild(option);
      }
      if (currentProfileId) select.value = currentProfileId;
      writeProfileInfo();
    }

    function writeProfileInfo() {
      const select = document.getElementById("voice_profile");
      const profile = voiceProfiles.find(item => item.id === select.value);
      const info = document.getElementById("profileInfo");
      if (!profile) {
        info.textContent = "사용 가능한 프로필이 없습니다.";
        return;
      }
      info.textContent = `${profile.label} · ${profile.version || "unknown"} · ${profile.prompt_text}`;
    }

    async function loadProfiles(saveCurrentForm = false) {
      if (saveCurrentForm) {
        await api("/api/config", { method: "POST", body: JSON.stringify(readForm()) });
      }
      const data = await api("/api/profiles");
      writeProfiles(data.profiles, data.current_profile_id);
      log(`모델 프로필 ${data.profiles.length}개를 불러왔습니다.`);
    }

    async function applyProfile() {
      const profileId = document.getElementById("voice_profile").value;
      if (!profileId) return log("선택한 모델 프로필이 없습니다.");
      setBusy(true);
      try {
        await api("/api/config", { method: "POST", body: JSON.stringify(readForm()) });
        log("모델 프로필을 적용하는 중입니다.");
        const data = await api("/api/profiles/apply", { method: "POST", body: JSON.stringify({ profile_id: profileId }) });
        writeForm(data.config);
        writeProfiles(data.profiles, data.config.voice_profile_id);
        log(`모델 프로필을 적용했습니다: ${data.profile.label}`);
      } catch (err) {
        log("오류: " + err.message);
      } finally {
        setBusy(false);
      }
    }

    async function refreshStatus() {
      try {
        const data = await api("/api/status");
        document.getElementById("dot").className = "dot " + (data.gptsovits.running ? "ok" : "bad");
        document.getElementById("statusText").textContent = data.gptsovits.running
          ? `GPT-SoVITS API 실행 중 (${data.gptsovits.url})`
          : "GPT-SoVITS API 꺼짐";
        if (data.last && data.last.audio_url) {
          document.getElementById("audio").src = data.last.audio_url;
          document.getElementById("lastFile").textContent = `최근 음성: ${data.last.created_at || "생성됨"}`;
        }
      } catch (err) {
        document.getElementById("dot").className = "dot bad";
        document.getElementById("statusText").textContent = err.message;
      }
    }

    async function startApi() {
      try {
        const data = await api("/api/gptsovits/start", { method: "POST", body: "{}" });
        log(data.message);
        setTimeout(refreshStatus, 2500);
      } catch (err) {
        log("오류: " + err.message);
      }
    }

    async function speak(play) {
      const text = document.getElementById("text").value.trim();
      if (!text) return log("읽을 텍스트가 없습니다.");
      setBusy(true);
      try {
        log("합성을 요청했습니다.");
        const data = await api("/api/speak", {
          method: "POST",
          body: JSON.stringify({ text, play, config: readForm() })
        });
        document.getElementById("lastFile").textContent = `최근 음성: ${data.created_at || "생성됨"}`;
        document.getElementById("audio").src = data.audio_url + `?t=${Date.now()}`;
        log("합성 완료. PC에서 재생을 시작했습니다.");
        refreshStatus();
      } catch (err) {
        log("오류: " + err.message);
      } finally {
        setBusy(false);
      }
    }

    async function agentTest() {
      setBusy(true);
      try {
        log("에이전트 음성 미러링을 보냈습니다.");
        const data = await api("/api/agent/speak", {
          method: "POST",
          body: JSON.stringify({ text: "에이전트가 화면에 표시한 메시지를 그대로 음성 미러링하는 테스트입니다.", play: true })
        });
        document.getElementById("lastFile").textContent = `최근 음성: ${data.created_at || "생성됨"}`;
        document.getElementById("audio").src = data.audio_url + `?t=${Date.now()}`;
        log("에이전트 음성 미러링이 완료됐습니다.");
        refreshStatus();
      } catch (err) {
        log("오류: " + err.message);
      } finally {
        setBusy(false);
      }
    }

    document.getElementById("voice_profile").addEventListener("change", writeProfileInfo);
    Promise.all([loadConfig(), loadProfiles(), refreshStatus()]).catch(err => log("초기화 오류: " + err.message));
  </script>
</body>
</html>
"""


CONFIG_LOCK = threading.Lock()


def load_config():
    with CONFIG_LOCK:
        if not CONFIG_PATH.exists():
            return dict(DEFAULT_CONFIG)
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            return dict(DEFAULT_CONFIG)


def save_config(config):
    with CONFIG_LOCK:
        merged = {**DEFAULT_CONFIG, **(config or {})}
        merged["batch_size"] = max(1, int(merged.get("batch_size") or 1))
        merged["timeout"] = max(10, int(merged.get("timeout") or 180))
        merged["max_chars"] = max(100, int(merged.get("max_chars") or 3500))
        merged["max_saved_wavs"] = max(1, int(merged.get("max_saved_wavs") or 50))
        merged["normalize_english_tokens"] = bool(merged.get("normalize_english_tokens", True))
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return merged


def is_port_open(host="127.0.0.1", port=GPT_SOVITS_API_PORT, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def output_stats():
    OUTPUT_DIR.mkdir(exist_ok=True)
    files = [path for path in OUTPUT_DIR.glob("*.wav") if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in files)
    return {"count": len(files), "bytes": total_bytes}


def cleanup_output_files(max_saved, protected_paths=None):
    OUTPUT_DIR.mkdir(exist_ok=True)
    protected = {Path(path).resolve() for path in (protected_paths or []) if path}
    files = sorted(
        [path for path in OUTPUT_DIR.glob("*.wav") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    keep = set(path.resolve() for path in files[:max_saved]) | protected
    deleted_count = 0
    failed_count = 0
    for path in files:
        if path.resolve() in keep:
            continue
        try:
            path.unlink()
            deleted_count += 1
        except OSError:
            failed_count += 1
    return {"deleted_count": deleted_count, "failed_count": failed_count}


def call_gptsovits_api(api_url, endpoint, params):
    base_url = api_url.rsplit("/", 1)[0]
    url = f"{base_url}/{endpoint}?" + parse.urlencode(params)
    try:
        with request.urlopen(url, timeout=240) as res:
            body = res.read().decode("utf-8", errors="replace")
    except error.URLError as exc:
        raise RuntimeError(f"GPT-SoVITS {endpoint} 호출 실패: {exc}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {"message": body}

    if isinstance(data, dict) and data.get("message") not in ["success", None]:
        raise RuntimeError(f"GPT-SoVITS {endpoint} 실패: {data}")
    return data


def apply_voice_profile(profile_id):
    profile = get_profile(profile_id)
    if not profile:
        raise RuntimeError("선택한 모델 프로필을 찾지 못했습니다.")

    config = load_config()
    api_url = config["api_url"]
    call_gptsovits_api(api_url, "set_gpt_weights", {"weights_path": path_for_gptsovits_api(profile["gpt_weight_path"])})
    call_gptsovits_api(api_url, "set_sovits_weights", {"weights_path": path_for_gptsovits_api(profile["sovits_weight_path"])})
    call_gptsovits_api(api_url, "set_refer_audio", {"refer_audio_path": path_for_gptsovits_api(profile["ref_audio_path"])})

    config.update(
        {
            "voice_profile_id": profile["id"],
            "gpt_weight_path": profile["gpt_weight_path"],
            "sovits_weight_path": profile["sovits_weight_path"],
            "ref_audio_path": profile["ref_audio_path"],
            "prompt_text": profile["prompt_text"],
            "prompt_lang": profile["prompt_lang"],
            "text_lang": profile["text_lang"],
            "text_split_method": profile["text_split_method"],
        }
    )
    return profile, save_config(config)


def sync_configured_profile_on_start():
    config = load_config()
    profile_id = infer_current_profile_id(config)
    if not profile_id:
        return
    try:
        profile, _ = apply_voice_profile(profile_id)
        print(f"[sovits-control] synced voice profile on start: {profile['label']}")
    except Exception as exc:
        print(f"[sovits-control] voice profile sync skipped: {exc}", file=sys.stderr)


def synthesize(text, config):
    text = text.strip()
    if not text:
        raise RuntimeError("읽을 텍스트가 없습니다.")

    max_chars = int(config.get("max_chars") or 3500)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
    original_text = text
    spoken_text = normalize_english_tokens_for_korean_tts(text) if config.get("normalize_english_tokens", True) else text

    ref_audio_path = resolve_local_path(config["ref_audio_path"])
    if not ref_audio_path.exists():
        raise RuntimeError(f"reference audio 파일을 찾지 못했습니다: {ref_audio_path}")

    params = {
        "text": spoken_text,
        "text_lang": config["text_lang"],
        "ref_audio_path": path_for_gptsovits_api(ref_audio_path),
        "prompt_lang": config["prompt_lang"],
        "prompt_text": config["prompt_text"],
        "text_split_method": config["text_split_method"],
        "batch_size": str(config["batch_size"]),
        "media_type": "wav",
        "streaming_mode": "false",
    }
    url = config["api_url"] + "?" + parse.urlencode(params)
    req = request.Request(url, headers={"Accept": "audio/wav"})
    try:
        with request.urlopen(req, timeout=int(config["timeout"])) as res:
            data = res.read()
    except error.URLError as exc:
        raise RuntimeError(f"GPT-SoVITS API 호출 실패: {exc}")

    if not data:
        raise RuntimeError("GPT-SoVITS API가 빈 응답을 반환했습니다.")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"sovits-control-{time.time_ns()}.wav"
    out_path.write_bytes(data)
    return out_path, original_text, spoken_text


def play_async(path):
    PLAYBACK_QUEUE.put(Path(path))
    PLAYBACK_STATE["queued"] = PLAYBACK_QUEUE.qsize()


def play_wav_pyaudio(path):
    wf = wave.open(str(path), 'rb')
    p = pyaudio.PyAudio()
    try:
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )
        try:
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(chunk_size)
        finally:
            stream.stop_stream()
            stream.close()
    finally:
        p.terminate()
        wf.close()


def playback_worker():
    while True:
        path = PLAYBACK_QUEUE.get()
        PLAYBACK_STATE["queued"] = PLAYBACK_QUEUE.qsize()
        PLAYBACK_STATE["current"] = str(path)
        try:
            play_wav_pyaudio(path)
            PLAYBACK_STATE["last_played"] = str(path)
        except Exception as exc:
            print(f"[sovits-control] playback failed: {exc}", file=sys.stderr)
            traceback.print_exc()
        finally:
            PLAYBACK_STATE["current"] = ""
            PLAYBACK_STATE["queued"] = PLAYBACK_QUEUE.qsize()
            PLAYBACK_QUEUE.task_done()


class Handler(BaseHTTPRequestHandler):
    server_version = "SovitsVoiceBridge/0.2"

    def log_message(self, fmt, *args):
        print(f"[sovits-control] {self.address_string()} - {fmt % args}")

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:18088")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, content_type="text/html; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = parse.urlparse(self.path)
        if parsed.path == "/":
            return self.send_text(HTML)
        if parsed.path == "/api/config":
            return self.send_json({"ok": True, "config": load_config()})
        if parsed.path == "/api/profiles":
            config = load_config()
            profiles = discover_voice_profiles(config)
            return self.send_json(
                {
                    "ok": True,
                    "profiles": profiles,
                    "current_profile_id": infer_current_profile_id(config, profiles),
                }
            )
        if parsed.path == "/api/status":
            config = load_config()
            return self.send_json(
                {
                    "ok": True,
                    "gptsovits": {"running": is_port_open(), "url": config["api_url"]},
                    "last": LAST_RESULT,
                    "playback": PLAYBACK_STATE,
                    "output": output_stats(),
                }
            )
        if parsed.path.startswith("/audio/"):
            name = Path(parse.unquote(parsed.path.removeprefix("/audio/"))).name
            path = OUTPUT_DIR / name
            if not path.exists():
                return self.send_json({"ok": False, "error": "audio not found"}, 404)
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return self.send_json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        parsed = parse.urlparse(self.path)
        try:
            if parsed.path == "/api/config":
                config = save_config(self.read_json())
                return self.send_json({"ok": True, "config": config})

            if parsed.path == "/api/profiles/apply":
                payload = self.read_json()
                profile_id = str(payload.get("profile_id") or "").strip()
                profile, config = apply_voice_profile(profile_id)
                return self.send_json(
                    {
                        "ok": True,
                        "profile": profile,
                        "config": config,
                        "profiles": discover_voice_profiles(config),
                    }
                )

            if parsed.path == "/api/gptsovits/start":
                if is_port_open():
                    return self.send_json({"ok": True, "message": "GPT-SoVITS API가 이미 실행 중입니다."})
                script = ROOT / "start-gptsovits-api.ps1"
                subprocess.Popen(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                    cwd=str(ROOT),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return self.send_json({"ok": True, "message": "GPT-SoVITS API 시작을 요청했습니다."})

            if parsed.path in ["/api/speak", "/api/agent/speak"]:
                payload = self.read_json()
                text = str(payload.get("text") or "").strip()
                if not text:
                    return self.send_json({"ok": False, "error": "읽을 텍스트가 없습니다."}, 400)
                config = save_config(payload.get("config") or load_config())
                path, original_text, spoken_text = synthesize(text, config)
                should_play = bool(payload.get("play", config.get("auto_play", True)))
                if should_play:
                    play_async(path)
                cleanup_output_files(
                    int(config.get("max_saved_wavs") or 50),
                    [path, PLAYBACK_STATE.get("current"), PLAYBACK_STATE.get("last_played")],
                )

                LAST_RESULT.update(
                    {
                        "file": str(path),
                        "audio_url": "/audio/" + parse.quote(path.name),
                        "text_preview": original_text[:160],
                        "spoken_text_preview": spoken_text[:160],
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
                return self.send_json({"ok": True, **LAST_RESULT})

            return self.send_json({"ok": False, "error": "not found"}, 404)
        except Exception as exc:
            traceback.print_exc()
            return self.send_json({"ok": False, "error": str(exc)}, 500)


def main():
    host = "127.0.0.1"
    port = 18088
    LOG_DIR.mkdir(exist_ok=True)
    save_config(load_config())
    sync_configured_profile_on_start()
    threading.Thread(target=playback_worker, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"SoVITS Voice Bridge: http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
