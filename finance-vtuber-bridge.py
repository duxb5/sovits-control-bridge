import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import parse
import requests


SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json",
    "Referer": "https://saveticker.com/news",
    "User-Agent": "Mozilla/5.0",
})


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "finance-vtuber-bridge.config.json"
STATE_PATH = ROOT / "finance-vtuber-bridge.state.json"


DEFAULT_CONFIG = {
    "mode": "manual",
    "financeApiBase": "http://127.0.0.1:5173",
    "savetickerApiBase": "https://saveticker.com/api",
    "vtuberApiBase": "http://localhost:12393",
    "pollSeconds": 60,
    "manualItemCount": 1,
    "savetickerTopStoryCount": 3,
    "savetickerFallbackToLatest": True,
    "maxItemsPerCycle": 20,
    "readExistingOnFirstAutoRun": False,
    "speakTimeoutSeconds": 600,
    "betweenItemsSeconds": 2,
    "refreshBeforeRead": True,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, fallback):
    if not path.exists():
        return dict(fallback)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {**fallback, **data}
    except Exception:
        return dict(fallback)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def http_json(method, url, payload=None, timeout=30):
    try:
        if payload is not None:
            res = SESSION.request(method, url, json=payload, timeout=timeout)
        else:
            res = SESSION.request(method, url, timeout=timeout)

        if res.status_code >= 400:
            try:
                details = res.json()
            except Exception:
                details = {"error": res.text}
            details["status"] = res.status_code
            raise RuntimeError(json.dumps(details, ensure_ascii=False))

        try:
            return res.json()
        except Exception:
            return {}
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(str(exc))


def api_url(base, path, query=None):
    url = base.rstrip("/") + path
    if query:
        url += "?" + parse.urlencode(query)
    return url


def normalize_item(item):
    title = item.get("translatedTitle") or item.get("title") or "Untitled"
    body = item.get("translatedText") or item.get("originalText") or ""
    source = item.get("feedTitle") or item.get("feedId") or "News"
    published = item.get("publishedAt") or item.get("fetchedAt") or ""
    url = item.get("sourceUrl") or ""
    return {
        "id": item.get("id") or item.get("sourceFingerprint") or f"{source}:{title}",
        "title": str(title).strip(),
        "body": str(body).strip(),
        "source": str(source).strip(),
        "published": str(published).strip(),
        "url": str(url).strip(),
    }


def text_blocks(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for block in value:
            if isinstance(block, dict):
                parts.append(str(block.get("content") or "").strip())
            else:
                parts.append(str(block).strip())
        return "\n".join(part for part in parts if part)
    return ""


def translated_text(item, field):
    translations = item.get("translations") or {}
    translated = translations.get("translated") or {}
    korean = translated.get("ko_KR") or {}
    value = korean.get(field)
    if value:
        return text_blocks(value)
    return ""


def normalize_saveticker_item(item):
    title = translated_text(item, "title") or item.get("title") or "Untitled"
    summary = translated_text(item, "summary")
    content = translated_text(item, "content") or item.get("content") or ""
    body = summary or content or title
    source = item.get("source") or "SaveTicker"
    published = item.get("created_at") or (item.get("extra") or {}).get("source_created_at") or ""
    news_id = str(item.get("id") or f"{source}:{title}")
    return {
        "id": f"saveticker:{news_id}",
        "title": str(title).strip(),
        "body": str(body).strip(),
        "source": f"SaveTicker/{source}",
        "published": str(published).strip(),
        "url": f"https://saveticker.com/news/{news_id}",
    }


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_today_kst(item):
    kst = timezone(timedelta(hours=9))
    published = item.get("created_at") or (item.get("extra") or {}).get("source_created_at")
    parsed = parse_datetime(published)
    if parsed is None:
        print(f"[bridge] [WARNING] Failed to parse date: {published}", file=sys.stderr)
        return False
    return parsed.astimezone(kst).date() == datetime.now(kst).date()


def speech_prompt(item):
    body = item["body"] or item["title"]
    return (
        "다음 금융 뉴스 한 건을 한국어로 자연스럽게 읽어줘. "
        "너무 길게 분석하지 말고, 제목과 핵심 내용, 시장에 줄 수 있는 의미를 2~3문장으로 말해줘.\n\n"
        f"출처: {item['source']}\n"
        f"게시 시각: {item['published']}\n"
        f"제목: {item['title']}\n"
        f"본문: {body}\n"
        f"링크: {item['url']}"
    )


def refresh_finance(config):
    if not config.get("refreshBeforeRead", True):
        return None
    return http_json(
        "POST",
        api_url(config["financeApiBase"], "/api/news-feed/refresh"),
        payload={},
        timeout=90,
    )


def fetch_items(config, limit):
    data = http_json(
        "GET",
        api_url(config["financeApiBase"], "/api/news-feed/items", {"limit": limit}),
        timeout=30,
    )
    return [normalize_item(item) for item in data.get("items", [])]


def fetch_saveticker_today_top_items(config, limit):
    base = config.get("savetickerApiBase") or DEFAULT_CONFIG["savetickerApiBase"]
    top_data = http_json(
        "GET",
        api_url(base, "/news/top-stories"),
        timeout=30,
    )
    selected = [item for item in top_data.get("news_list", []) if is_today_kst(item)]

    if len(selected) < limit and config.get("savetickerFallbackToLatest", True):
        latest_data = http_json(
            "GET",
            api_url(
                base,
                "/news/list",
                {
                    "page": 1,
                    "page_size": max(limit * 5, 20),
                    "sort": "created_at_desc",
                },
            ),
            timeout=30,
        )
        seen_ids = {str(item.get("id")) for item in selected}
        for item in latest_data.get("news_list", []):
            item_id = str(item.get("id"))
            if item_id not in seen_ids and is_today_kst(item):
                selected.append(item)
                seen_ids.add(item_id)
            if len(selected) >= limit:
                break

    return [normalize_saveticker_item(item) for item in selected[:limit]]


def ensure_vtuber_client(config):
    data = http_json(
        "GET",
        api_url(config["vtuberApiBase"], "/local/clients"),
        timeout=10,
    )
    count = int(data.get("count") or 0)
    if count < 1:
        raise RuntimeError("Open http://localhost:12393 first so a VTuber browser client is connected.")
    return data


def speak(config, item):
    payload = {
        "text": speech_prompt(item),
        "wait": True,
        "timeout": config.get("speakTimeoutSeconds", 600),
        "skip_finance_bridge": True,
    }
    return http_json(
        "POST",
        api_url(config["vtuberApiBase"], "/local/speak"),
        payload=payload,
        timeout=int(config.get("speakTimeoutSeconds", 600)) + 30,
    )


def read_items(config, state, items):
    if not items:
        return 0
    ensure_vtuber_client(config)
    read_count = 0
    for item in items:
        print(f"[bridge] speaking: {item['source']} - {item['title']}", flush=True)
        speak(config, item)
        state.setdefault("seenIds", [])
        if item["id"] not in state["seenIds"]:
            state["seenIds"].append(item["id"])
        state["lastReadAt"] = now_iso()
        save_json(STATE_PATH, state)
        read_count += 1
        time.sleep(float(config.get("betweenItemsSeconds", 2)))
    return read_count


def command_once(config, state):
    refresh_finance(config)
    count = int(config.get("manualItemCount", 1))
    items = fetch_items(config, max(count, 1))
    read_count = read_items(config, state, items[:count])
    print(f"[bridge] manual read complete: {read_count} item(s)")


def command_saveticker_today(config, state):
    count = int(config.get("savetickerTopStoryCount", 3))
    items = fetch_saveticker_today_top_items(config, max(count, 1))
    if not items:
        raise RuntimeError("SaveTicker에서 오늘 날짜의 주요뉴스를 찾지 못했습니다.")
    read_count = read_items(config, state, items[:count])
    print(f"[bridge] saveticker today read complete: {read_count} item(s)")


def command_auto(config, state):
    print("[bridge] auto mode started")
    while True:
        try:
            refresh_finance(config)
            limit = int(config.get("maxItemsPerCycle", 20))
            items = fetch_items(config, max(limit, 1))
            seen = set(state.get("seenIds") or [])

            if not state.get("initialized"):
                state["initialized"] = True
                if not config.get("readExistingOnFirstAutoRun", False):
                    state["seenIds"] = list({item["id"] for item in items})
                    state["lastScanAt"] = now_iso()
                    save_json(STATE_PATH, state)
                    print("[bridge] initialized; existing items marked as seen")
                    time.sleep(float(config.get("pollSeconds", 60)))
                    continue

            new_items = [item for item in reversed(items) if item["id"] not in seen]
            if new_items:
                new_items = new_items[:limit]
                print(f"[bridge] new items: {len(new_items)}")
                read_items(config, state, new_items)
            else:
                print("[bridge] no new items")

            state["lastScanAt"] = now_iso()
            save_json(STATE_PATH, state)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            state["lastError"] = str(exc)
            state["lastErrorAt"] = now_iso()
            save_json(STATE_PATH, state)
            print(f"[bridge] error: {exc}", file=sys.stderr, flush=True)

        time.sleep(float(config.get("pollSeconds", 60)))


def command_status(config, state):
    print(json.dumps({"config": config, "state": state}, ensure_ascii=False, indent=2))


def command_reset_state():
    save_json(STATE_PATH, {"seenIds": [], "initialized": False, "lastResetAt": now_iso()})
    print(f"[bridge] reset state: {STATE_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        choices=["once", "auto", "status", "reset-state", "saveticker-today"],
    )
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, DEFAULT_CONFIG)
    state = load_json(STATE_PATH, {"seenIds": [], "initialized": False})

    command = args.command or config.get("mode", "manual")
    if command == "manual":
        command = "once"

    if command == "once":
        command_once(config, state)
    elif command == "saveticker-today":
        command_saveticker_today(config, state)
    elif command == "auto":
        command_auto(config, state)
    elif command == "status":
        command_status(config, state)
    elif command == "reset-state":
        command_reset_state()


if __name__ == "__main__":
    main()
