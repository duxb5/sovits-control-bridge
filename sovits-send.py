import argparse
import json
import sys
from urllib import request


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Send explicit text to the local SoVITS Voice Bridge.")
    parser.add_argument("text", nargs="*", help="Text to speak. If omitted, stdin is used.")
    parser.add_argument("--url", default="http://127.0.0.1:18088/api/speak")
    parser.add_argument("--no-play", action="store_true")
    args = parser.parse_args()

    text = " ".join(args.text).strip() if args.text else sys.stdin.read().strip()
    if not text:
        raise SystemExit("읽을 텍스트가 없습니다.")

    body = json.dumps({"text": text, "play": not args.no_play}, ensure_ascii=False).encode("utf-8")
    req = request.Request(args.url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=240) as res:
        data = json.loads(res.read().decode("utf-8"))

    if not data.get("ok"):
        raise SystemExit(data.get("error") or "SoVITS Voice Bridge 요청 실패")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
