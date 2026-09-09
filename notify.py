import json
import os
import sys
import requests
from datetime import datetime

STATE_FILE = "state.json"
NOTION_VERSION = "2022-06-28"


def load_state(path=STATE_FILE):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state, path=STATE_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def parse_page(page):
    props = page["properties"]

    title_list = props["이름"]["title"]
    name = title_list[0]["plain_text"] if title_list else "(제목 없음)"

    summary_list = props["요약"]["rich_text"]
    summary = summary_list[0]["plain_text"] if summary_list else ""

    checklist_list = props["체크할것"]["rich_text"]
    checklist = checklist_list[0]["plain_text"] if checklist_list else ""

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
            "property": "생성일",
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


def format_message(page):
    emoji = "🌙" if page["name"].startswith("야간") else "☀️"

    created_dt = datetime.fromisoformat(page["created_time"].replace("Z", "+00:00"))
    date_str = created_dt.strftime("%Y-%m-%d")

    lines = [f"{emoji} {page['name']} ({date_str})"]
    if page["summary"]:
        lines.append(f"요약: {page['summary']}")
    if page["checklist"]:
        lines.append(f"체크할것: {page['checklist']}")
    lines.append(f"[노션에서 보기]({page['url']})")

    return "\n".join(lines)


def send_telegram_message(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[ERROR] 텔레그램 전송 실패: {exc}", file=sys.stderr)
        return False


def run(notion_token, database_id, bot_token, chat_id, state_path=STATE_FILE):
    state = load_state(state_path)
    since_iso = state["last_checked"]

    try:
        raw_pages = fetch_new_pages(notion_token, database_id, since_iso)
    except requests.RequestException as exc:
        print(f"[ERROR] Notion 조회 실패: {exc}", file=sys.stderr)
        return

    pages = [parse_page(p) for p in raw_pages]

    latest_sent = since_iso
    for page in pages:
        message = format_message(page)
        if send_telegram_message(bot_token, chat_id, message):
            latest_sent = page["created_time"]
        else:
            break

    if latest_sent != since_iso:
        save_state({"last_checked": latest_sent}, state_path)


def main():
    run(
        notion_token=os.environ["NOTION_API_KEY"],
        database_id=os.environ["NOTION_DATABASE_ID"],
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )


if __name__ == "__main__":
    main()
