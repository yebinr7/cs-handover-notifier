import html
import json
import os
import sys
import requests
from datetime import datetime, timedelta, timezone

STATE_FILE = "state.json"
NOTION_VERSION = "2022-06-28"
KST = timezone(timedelta(hours=9))
MAX_FIELD_LEN = 1000


def load_state(path=STATE_FILE):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state, path=STATE_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _plain_text(rich_items):
    return "".join(item["plain_text"] for item in rich_items)


def parse_page(page):
    props = page["properties"]

    name = _plain_text(props["이름"]["title"]) or "(제목 없음)"
    summary = _plain_text(props["요약"]["rich_text"])
    checklist = _plain_text(props["체크할것"]["rich_text"])

    return {
        "name": name,
        "summary": summary,
        "checklist": checklist,
        "created_time": page["created_time"],
        "url": page["url"],
    }


def build_notion_query_payload(since_iso):
    return {
        "filter": {
            "timestamp": "created_time",
            "created_time": {"after": since_iso},
        },
        "sorts": [{"timestamp": "created_time", "direction": "ascending"}],
    }


def fetch_new_pages(notion_token, database_id, since_iso):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = build_notion_query_payload(since_iso)
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()["results"]


def _truncate(text, limit=MAX_FIELD_LEN):
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def format_message(page):
    emoji = "🌙" if page["name"].startswith("야간") else "☀️"

    created_dt = datetime.fromisoformat(
        page["created_time"].replace("Z", "+00:00")
    ).astimezone(KST)
    date_str = created_dt.strftime("%Y-%m-%d")

    summary = _truncate(page["summary"])
    checklist = _truncate(page["checklist"])

    lines = [f"{emoji} {html.escape(page['name'])} ({date_str})"]
    if summary:
        lines.append(f"요약: {html.escape(summary)}")
    if checklist:
        lines.append(f"체크할것: {html.escape(checklist)}")
    lines.append(f'<a href="{html.escape(page["url"], quote=True)}">노션에서 보기</a>')

    return "\n".join(lines)


def send_telegram_message(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        safe_message = str(exc).replace(bot_token, "***")
        print(f"[ERROR] 텔레그램 전송 실패: {safe_message}", file=sys.stderr)
        return False


def send_telegram_photo(bot_token, chat_id, photo_url):
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url}
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        safe_message = str(exc).replace(bot_token, "***")
        print(f"[WARN] 이미지 전송 실패: {safe_message}", file=sys.stderr)
        return False


def run(notion_token, database_id, bot_token, chat_id, state_path=STATE_FILE):
    state = load_state(state_path)
    since_iso = state["last_checked"]

    try:
        raw_pages = fetch_new_pages(notion_token, database_id, since_iso)
    except requests.RequestException as exc:
        print(f"[ERROR] Notion 조회 실패: {exc}", file=sys.stderr)
        return False

    pages = [parse_page(p) for p in raw_pages]

    ok = True
    latest_sent = since_iso
    for page in pages:
        message = format_message(page)
        if send_telegram_message(bot_token, chat_id, message):
            latest_sent = page["created_time"]
        else:
            if latest_sent == page["created_time"]:
                latest_sent = since_iso
            ok = False
            break

    if latest_sent != since_iso:
        save_state({"last_checked": latest_sent}, state_path)

    return ok


def fetch_page_blocks(notion_token, page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()["results"]


def extract_body_text(blocks):
    lines = []
    for block in blocks:
        block_type = block.get("type")
        content = block.get(block_type, {})
        rich_text = content.get("rich_text")
        if rich_text:
            text = _plain_text(rich_text)
            if text:
                lines.append(text)
    return "\n".join(lines)


def extract_image_urls(blocks):
    urls = []
    for block in blocks:
        if block.get("type") != "image":
            continue
        image = block["image"]
        image_type = image.get("type")
        if image_type == "file":
            urls.append(image["file"]["url"])
        elif image_type == "external":
            urls.append(image["external"]["url"])
    return urls


ANTHROPIC_VERSION = "2023-06-01"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def condense_text(anthropic_api_key, text):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": anthropic_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 300,
        "messages": [
            {
                "role": "user",
                "content": (
                    "다음은 공장 CS 엔지니어가 작성한 인수인계 메모입니다. "
                    "핵심만 간결하게 한국어로 요약해줘. 인사말이나 서론 없이 "
                    "바로 내용만 적어줘.\n\n" + text
                ),
            }
        ],
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()["content"][0]["text"].strip()
    except Exception as exc:
        print(f"[WARN] AI 요약 실패, 원문 사용: {exc}", file=sys.stderr)
        return text


def main():
    required = ["NOTION_API_KEY", "NOTION_DATABASE_ID", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        print(f"[ERROR] 환경변수 누락: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    ok = run(
        notion_token=os.environ["NOTION_API_KEY"],
        database_id=os.environ["NOTION_DATABASE_ID"],
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
