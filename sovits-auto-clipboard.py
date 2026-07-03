import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parent
SOVITS_SAY = ROOT / "sovits-say.py"


def normalize_text(text):
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def read_clipboard_with_tk(root):
    try:
        root.update()
        return root.clipboard_get()
    except Exception:
        return ""


def make_clipboard_reader():
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        return lambda: read_clipboard_with_tk(root)
    except Exception:
        pass

    def read_with_powershell():
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.stdout if result.returncode == 0 else ""

    return read_with_powershell


def speak(text, args):
    command = [sys.executable, "-X", "utf8", str(SOVITS_SAY)]
    if args.no_play:
        command.append("--no-play")
    if args.output:
        command.extend(["--output", args.output])

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    subprocess.run(
        command,
        cwd=str(ROOT),
        input=text,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Watch the Windows clipboard and speak newly copied text through GPT-SoVITS."
    )
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--min-chars", type=int, default=2)
    parser.add_argument("--max-chars", type=int, default=3500)
    parser.add_argument("--speak-existing", action="store_true")
    parser.add_argument("--no-play", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if not SOVITS_SAY.exists():
        raise SystemExit(f"sovits-say.py not found: {SOVITS_SAY}")

    read_clipboard = make_clipboard_reader()
    last_text = normalize_text(read_clipboard())
    if args.speak_existing and last_text:
        print("[sovits-auto] speaking current clipboard text")
        speak(last_text[: args.max_chars], args)

    print("[sovits-auto] watching clipboard. Copy Codex text to hear it. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(max(args.poll_seconds, 0.2))
            text = normalize_text(read_clipboard())
            if not text or text == last_text:
                continue
            last_text = text
            if len(text) < args.min_chars:
                continue
            if len(text) > args.max_chars:
                print(f"[sovits-auto] text is long; reading first {args.max_chars} characters")
                text = text[: args.max_chars].rstrip()

            print(f"[sovits-auto] speaking {len(text)} characters")
            try:
                speak(text, args)
            except subprocess.CalledProcessError as exc:
                print(f"[sovits-auto] speak failed with exit code {exc.returncode}", file=sys.stderr)
            except Exception as exc:
                print(f"[sovits-auto] speak failed: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\n[sovits-auto] stopped")


if __name__ == "__main__":
    main()
