import argparse
import sys
import time
import wave
import pyaudio
from pathlib import Path
from urllib import error, parse, request


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "sovits-output"

DEFAULT_API_URL = "http://127.0.0.1:9880/tts"
DEFAULT_REF_AUDIO = (
    ROOT
    / "GPT-SoVITS"
    / "models"
    / "GPT-SoVITS_Model_Collection"
    / "your-model"
    / "ref_audio.wav"
)
DEFAULT_PROMPT_TEXT = "방금 이야기를 하면서 느꼈지…. 이 왕생당의 객경이란 자는… 절대 평범한 사람이 아니야"


def resolve_local_path(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def synthesize(text, args):
    ref_audio_path = resolve_local_path(args.ref_audio_path)
    params = {
        "text": text,
        "text_lang": args.text_lang,
        "ref_audio_path": str(ref_audio_path),
        "prompt_lang": args.prompt_lang,
        "prompt_text": args.prompt_text,
        "text_split_method": args.text_split_method,
        "batch_size": str(args.batch_size),
        "media_type": "wav",
        "streaming_mode": "false",
    }
    url = args.api_url + "?" + parse.urlencode(params)
    req = request.Request(url, headers={"Accept": "audio/wav"})
    try:
        with request.urlopen(req, timeout=args.timeout) as res:
            data = res.read()
    except error.URLError as exc:
        raise RuntimeError(
            f"GPT-SoVITS API 호출 실패: {exc}. 먼저 start-gptsovits-api.ps1을 실행했는지 확인하세요."
        )

    if not data:
        raise RuntimeError("GPT-SoVITS API가 빈 응답을 반환했습니다.")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else OUTPUT_DIR / f"sovits-{int(time.time())}.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path


def play_wav_pyaudio(path):
    wf = wave.open(str(path), "rb")
    p = pyaudio.PyAudio()
    try:
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )
        try:
            chunk_size = 1024
            data = wf.readframes(chunk_size)
            while data:
                stream.write(data)
                data = wf.readframes(chunk_size)
        finally:
            stream.stop_stream()
            stream.close()
    finally:
        p.terminate()
        wf.close()


def main():
    parser = argparse.ArgumentParser(
        description="Speak text directly through the local GPT-SoVITS API."
    )
    parser.add_argument("text", nargs="*", help="Text to synthesize. If omitted, stdin is used.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--ref-audio-path", default=str(DEFAULT_REF_AUDIO))
    parser.add_argument("--prompt-text", default=DEFAULT_PROMPT_TEXT)
    parser.add_argument("--text-lang", default="ko")
    parser.add_argument("--prompt-lang", default="ko")
    parser.add_argument("--text-split-method", default="cut5")
    parser.add_argument("--batch-size", default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", default="")
    parser.add_argument("--no-play", action="store_true")
    args = parser.parse_args()

    text = " ".join(args.text).strip() if args.text else sys.stdin.read().strip()
    if not text:
        raise SystemExit("읽을 텍스트가 없습니다.")

    if not resolve_local_path(args.ref_audio_path).exists():
        raise SystemExit(f"ref audio 파일을 찾지 못했습니다: {args.ref_audio_path}")

    out_path = synthesize(text, args)
    print(f"[sovits-say] generated: {out_path}")

    if not args.no_play:
        play_wav_pyaudio(out_path)
        print("[sovits-say] playback complete")


if __name__ == "__main__":
    main()
